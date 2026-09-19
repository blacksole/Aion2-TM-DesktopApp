"""The Arcana Calculator's best-case Lord-card solver.

Moved verbatim out of ``ItemDatabase/app.py`` (audit B-armory.md §2.3/§3.1,
old app.py:3150–3543): the card model (slots, grades, derived level), the
per-type eligibility filter, the two-phase greedy card fill, the sequential
combination search with its exclusion-based diversification, and the three
tiers of "why is this wish uncovered".

What stayed in app.py: everything that draws or loads.  ``ARCANA_CARD_TYPES``
and ``ARCANA_THEME_ORDER`` (display order), ``_ARCANA_THEME_COLORS`` and
``ARCANA_CATEGORY_COLORS`` (``core.theme`` data tables), the icon/banner
paths, ``_load_arcana_theme_map`` / ``_load_arcana_class_skills`` (file I/O),
and ``ARCANA_LORD_EFFECTS`` / ``ARCANA_SET_BONUSES`` (label tables).

Two behaviours in here are load-bearing and easy to "tidy" into a bug, so
they are pinned by golden tests (``tests/test_armory_engine_golden.py``):

* ``_arcana_best_combination`` is **sequential over ``usable_types``** — a
  later type's remaining need already reflects what earlier types covered.
  The result therefore depends on that iteration order and is not a global
  optimum (audit §2.3, LOW-MED).  That is the approved model, not an
  oversight.
* ``_arcana_compute_combinations`` excludes only ``need_based_ids`` when
  searching for the next combination, never every skill a type touched.  The
  distinction fixed a real 2026-09-13 bug where one incidental filler pick
  collapsed every subsequent solve to 0 % coverage.

The duplicate ``_ARCANA_SKILL_SLOTS_PER_CARD = 4`` (audit §4.3, LOW) is kept
as it was: both assignments moved together, so the constant still has the
same value, and de-duplicating it is a change rather than a move.
"""

from __future__ import annotations

__all__ = [
    "_ARCANA_ACTIVE_THEMES",
    "_ARCANA_CARD_EXTRA_BUDGET",
    "_ARCANA_DEFAULT_GRADE",
    "_ARCANA_GRADE_MAX_LEVEL",
    "_ARCANA_LORD_CATEGORY",
    "_ARCANA_LORD_TYPES",
    "_ARCANA_MAX_CARD_LEVEL",
    "_ARCANA_PER_SKILL_CAP",
    "_ARCANA_SKILL_BASELINE",
    "_ARCANA_SKILL_SLOTS_PER_CARD",
    "_arcana_best_card_contribution",
    "_arcana_best_combination",
    "_arcana_card_grade",
    "_arcana_card_level",
    "_arcana_card_slot_list",
    "_arcana_compute_combinations",
    "_arcana_eligible_skills_for_type",
    "_arcana_eligible_types",
    "_arcana_full_pool_for_type",
    "_arcana_max_ceiling",
    "_arcana_result_coverage_percent",
    "_arcana_uncovered_reason",
    "_arcana_usable_lord_types",
]

# ---- Arcana Planner (2026-08-29) -------------------------------------------
# One equip slot per Lord card TYPE (not a generic duplicates-allowed pool --
# corrected by the user after an initial wrong assumption: "da bei Magic und
# Vigor keine Waage existiert, sind es nur 5 Karten, somit betraegt die
# gesamt Anzahl der Setkarten nur 5, nicht 6"). Each slot's real in-game
# card can be leveled up independently of its base grade -- each level-up
# always grants +1 to exactly ONE random skill from the card's pool (never
# player-chosen -- User, 2026-08-29: "Der Spieler kann nicht waehlen,
# welcher Wert gelevelt wird ... nur immer wieder neue Karten farmen und
# leveln") -- and grade caps the max level reachable (Rare=3, Legend=4,
# Unique=5, User-confirmed). The Calculator deliberately does NOT simulate
# that randomness -- "Wir machen das aber nicht im Kalkulator, wir gehen
# von den perfekten Werten aus": it shows the PERFECT/best-case reference
# (every level-up landing on the one skill you care about, on a maxed
# Unique card) so a player can judge how close their own randomly-rolled
# real cards are to that ceiling -- not a literal "buy this and get
# exactly this" recommendation. Same perfect-case logic applies to the
# card's own Empyrean Lord stat effect, which also gains +1 per level
# (User: "Bei Magic und Vigor geht der Hauptwert ... auch nur +1"), so a
# maxed Unique card's Lord effect is shown at its max level's value too.
# Applies to ONE skill chosen from that type's class-specific pool
# (grade-independent -- see _load_arcana_class_skills), constrained by the
# type's fixed skill category: Chalice can target either an Active or a
# Passive skill ("Mastery"), Parchment/Compass/Scales only Active, Bell/
# Mirror only Passive. Common grade doesn't exist for any Lord card.
_ARCANA_LORD_TYPES = ["Chalice", "Parchment", "Compass", "Bell", "Mirror", "Scales"]
_ARCANA_LORD_CATEGORY = {
    "Chalice": "both", "Parchment": "active", "Compass": "active",
    "Bell": "passive", "Mirror": "passive", "Scales": "active",
}
_ARCANA_GRADE_MAX_LEVEL = {"Rare": 3, "Legend": 4, "Unique": 5}
# The Calculator always reasons about the perfect/best case -- a maxed
# Unique card -- so this is simply the Unique entry above. This is the
# CARD's overall level (how many shared extra-points its leveling
# provides in total -- see _ARCANA_CARD_EXTRA_BUDGET below, same number),
# distinct from _ARCANA_PER_SKILL_CAP (the max any ONE skill on that card
# can individually reach).
_ARCANA_MAX_CARD_LEVEL = _ARCANA_GRADE_MAX_LEVEL["Unique"]

# "Season 1" assumption (User-Wunsch, 2026-08-29, explicitly UNVERIFIED --
# "die Wahrscheinlichkeit ist sehr hoch, dass nur Vigor und Magic
# existieren"): only these two themes are treated as currently obtainable.
# The other 5 (Frenzy/Purity/Punishment/Protection/Indomitability) stay out
# of the planner's candidate pool for now -- same forward-compat intent as
# the Daevanion Board's _s/_a split, but here it's one flat set rather than
# two named variants since the user wants more seasons/slots addable later
# without a redesign (see _arcana_usable_lord_types below).
_ARCANA_ACTIVE_THEMES = {"Vigor", "Magic"}


def _arcana_usable_lord_types(theme_map: dict, active_themes: set[str]) -> list[str]:
    """Which Lord card types actually exist in at least one of the given
    themes -- e.g. Scales has no Vigor/Magic entry at all, so it's excluded
    from the Season-1 candidate pool entirely, dropping the real usable
    total from 6 to 5. Data-driven (reads theme_map, already scanned from
    arcana_info.json) rather than a hardcoded count, so a later season
    adding Scales -- or a wholly new theme -- just changes the result here,
    no separate constant to update."""
    return [
        ct for ct in _ARCANA_LORD_TYPES
        if any(ct in theme_map.get(theme, {}) for theme in active_themes)
    ]


_ARCANA_SKILL_SLOTS_PER_CARD = 4
# A real card rolls _ARCANA_SKILL_SLOTS_PER_CARD (4) of its type's ~5-6
# possible skills; the instant one is rolled it already sits at
# _ARCANA_SKILL_BASELINE (1), not 0 (User, 2026-08-29: "bei diesen Skills
# ist das Startlevel nicht '0' sondern 1" / "kann eine Karte, wenn sie +0
# ist, folgende Werte haben: Rushing Smash +1, Spinning Strike +1,
# Impactful Crush +1, Dark Crush +1"). Leveling the card then spends a
# SHARED pool of _ARCANA_CARD_EXTRA_BUDGET (5, for Unique) extra points,
# one at a time, each landing on ONE random already-rolled skill (never
# player-chosen) -- but no single skill can exceed _ARCANA_PER_SKILL_CAP
# (4) regardless of how many hits land on it (User: "das Limit ist +4 auf
# den Skills und das maximale Level, das eine Arcana erhalten kann, ist
# +5, also 5 Level auf die vorhandenen Skills verteilen"). Verified
# against the user's own worked examples: Parchment showing Onslaught +4
# (needs 3 hits beyond baseline) and Spinning Strike +3 (needs 2 hits) =
# exactly 5 hits, the full shared budget, with the card's other 2
# (unlisted, uninteresting) slots staying at baseline; Chalice showing
# Dark Crush +4 (3 hits, AT the per-skill cap) + Rushing Smash +2 (1 hit)
# = 4 of 5 hits used, the 5th would be wasted since Dark Crush is already
# capped. Both examples are inconsistent with either "no shared budget,
# every skill independently to +5" (Parchment's 2 slots alone would need
# 5 hits for just +4/+3, leaving nothing baseline-related unaccounted)
# or "one skill per card" (both cards clearly show 2+ skills at once).
_ARCANA_SKILL_BASELINE = 1
_ARCANA_CARD_EXTRA_BUDGET = _ARCANA_MAX_CARD_LEVEL
_ARCANA_PER_SKILL_CAP = 4
_ARCANA_SKILL_SLOTS_PER_CARD = 4
_ARCANA_DEFAULT_GRADE = "Unique"


def _arcana_card_slot_list(card_data: dict | None) -> list[dict | None]:
    """Exactly _ARCANA_SKILL_SLOTS_PER_CARD (4) positional entries, each
    either None (empty) or {"skill_id": ..., "level": ...} -- the shape
    manual per-slot editing needs (User-Wunsch, 2026-08-29: "Jede der 4
    Skill-Zeilen einzeln anklickbar", needs a stable index per slot).
    Migrates the older {"skill_ids": {sid: level}} shape on the fly (still
    what's stored in any profile saved before this existed, and still what
    the Calculator's Apply writes) -- a dict has no way to represent "slot
    2 is specifically empty while slot 3 has X", only "whatever order
    happened to get assigned"."""
    if not card_data:
        return [None] * _ARCANA_SKILL_SLOTS_PER_CARD
    slots = card_data.get("slots")
    if slots is None:
        old = card_data.get("skill_ids") or {}
        slots = [{"skill_id": sid, "level": lvl} for sid, lvl in old.items()]
    slots = list(slots[:_ARCANA_SKILL_SLOTS_PER_CARD])
    while len(slots) < _ARCANA_SKILL_SLOTS_PER_CARD:
        slots.append(None)
    return slots


def _arcana_card_grade(card_data: dict | None) -> str:
    if not card_data:
        return _ARCANA_DEFAULT_GRADE
    return card_data.get("grade", _ARCANA_DEFAULT_GRADE)


def _arcana_card_level(card_data: dict | None) -> int:
    """The card's overall Level (0 to its grade's max, see
    _ARCANA_GRADE_MAX_LEVEL) -- User-Wunsch, 2026-08-30: derive it from the
    already-assigned skill slots instead of a separate input ("wir
    berechnen das Level der Karten anhand der vergebenen Punkte. ... fuegt
    man eine Karte mit +3 und einem +4 hinzu ist sie +5"). Every point a
    slot sits above baseline (_ARCANA_SKILL_BASELINE) came out of the same
    shared per-card budget, so summing those points back up gives the
    exact Level that was spent to reach this slot assignment -- same math
    already used for the live wish-ceiling (see ArcanaSkillSlotDialog)."""
    slots = _arcana_card_slot_list(card_data)
    spent = sum(
        max(0, slot.get("level", _ARCANA_SKILL_BASELINE) - _ARCANA_SKILL_BASELINE)
        for slot in slots if slot
    )
    grade = _arcana_card_grade(card_data)
    return min(spent, _ARCANA_GRADE_MAX_LEVEL.get(grade, _ARCANA_MAX_CARD_LEVEL))


def _arcana_eligible_skills_for_type(
    ct: str, wishes: dict[str, int], class_skill_pools: dict[str, list[dict]], skill_type_by_id: dict[str, str],
) -> list[str]:
    """Wished skills this Lord type could ever roll (in its pool, matching
    its fixed Active/Passive/both category)."""
    category = _ARCANA_LORD_CATEGORY.get(ct)
    pool_ids = {s["id"] for s in class_skill_pools.get(ct, [])}
    return [
        sid for sid in wishes
        if sid in pool_ids and (category == "both" or skill_type_by_id.get(sid) == category)
    ]


def _arcana_full_pool_for_type(ct: str, class_skill_pools: dict[str, list[dict]]) -> list[str]:
    """Every real skill id this Lord type's pool can roll, wished or not --
    used to fill a card's 4 skill slots with something sensible once real
    wishes run out (User-Wunsch, 2026-08-29: "Immer alle 5 verteilen" /
    "kannst bei der Verteilung der restlichen Punkte auch gerne die
    Prioliste der Skills nehmen"), instead of leaving slots/budget
    stranded just because nothing was explicitly wished for them."""
    return [s["id"] for s in class_skill_pools.get(ct, [])]


def _arcana_best_card_contribution(
    eligible: list[str], full_pool: list[str], priority_rank: dict[str, int],
    wishes: dict[str, int], covered: dict[str, int],
) -> dict[str, int]:
    """What ONE card of this type contributes in the perfect/best case,
    given what's ALREADY covered by other assigned cards so far. Two
    phases:

    1. Choose up to _ARCANA_SKILL_SLOTS_PER_CARD (4) of the card's real
       skill slots: eligible (wished) skills with remaining unmet need
       first (an exchange argument shows no reason to pick a skill with
       less need over one with more, so no need to try every possible
       4-of-N subset), ranked by need then Priority List position as a
       tiebreak; if fewer than 4 wished skills have real need, the
       remaining slots are filled from the type's FULL pool ranked by
       Priority List position, then pool order as a last resort (User,
       2026-08-29: "kannst bei der Verteilung der restlichen Punkte auch
       gerne die Prioliste der Skills nehmen" / "wenn dort nur 4 Skills
       angegeben sind, nimm den erst besten") -- so a card's slots are
       never left conceptually "empty" just because nothing was wished.
    2. Spend the shared _ARCANA_CARD_EXTRA_BUDGET one point at a time,
       never past _ARCANA_PER_SKILL_CAP: real wish-need first, then once
       every chosen skill's own wish is met, keep spending the REST of
       the budget too (User: "Immer alle 5 verteilen") on whichever
       chosen skill ranks highest on the Priority List, falling back to
       pool order -- a real card's leveling doesn't stop just because
       your specific wish was already satisfied.

    Returns ({skill_id: added_value}, need_based_ids) for the chosen
    skills (empty only if the type's pool has nothing at all matching its
    category) -- need_based_ids is the subset of the RESULT that was
    actually chosen because of real remaining wish need (phase 1 above),
    as opposed to pure filler (phase 1's "fewer than 4 wished skills"
    fallback). _arcana_compute_combinations' diversification only
    excludes need_based_ids when searching for a second combination (see
    its own docstring) -- a filler pick landing on a skill that ANOTHER
    type already fully covered via real need is incidental (that type
    just had unused slots left over), not a genuine second path to that
    skill, and excluding it too was blocking real alternatives that
    should have been findable (User-reported, 2026-09-13: "hier gibt es
    doch sicher noch andere Kombinationen" -- confirmed via direct
    inspection that a single wished skill fully covered by one type still
    incidentally showed up as a 1-point filler pick on a second type,
    which then got excluded right along with the real assignment)."""
    def remaining_need(sid: str, value: int) -> int:
        return max(0, wishes.get(sid, 0) - covered.get(sid, 0) - value)

    def choice_key(sid: str) -> tuple:
        need = max(0, wishes.get(sid, 0) - covered.get(sid, 0))
        return (-need, priority_rank.get(sid, float("inf")), sid)

    need_chosen = sorted(
        (sid for sid in eligible if wishes.get(sid, 0) - covered.get(sid, 0) > 0),
        key=choice_key,
    )[:_ARCANA_SKILL_SLOTS_PER_CARD]
    chosen = list(need_chosen)
    if len(chosen) < _ARCANA_SKILL_SLOTS_PER_CARD:
        filler = sorted(
            (sid for sid in full_pool if sid not in chosen),
            key=lambda sid: (priority_rank.get(sid, float("inf")), sid),
        )
        chosen += filler[: _ARCANA_SKILL_SLOTS_PER_CARD - len(chosen)]
    if not chosen:
        return {}, set()

    values = {sid: _ARCANA_SKILL_BASELINE for sid in chosen}
    budget = _ARCANA_CARD_EXTRA_BUDGET
    while budget > 0:
        candidates = [sid for sid in chosen if values[sid] < _ARCANA_PER_SKILL_CAP]
        if not candidates:
            break
        best_sid = min(
            candidates,
            key=lambda sid: (-remaining_need(sid, values[sid]), priority_rank.get(sid, float("inf")), sid),
        )
        values[best_sid] += 1
        budget -= 1
    return values, set(need_chosen)


def _arcana_best_combination(
    usable_types: list[str], type_to_theme: dict[str, str],
    eligible_by_type: dict[str, list[str]], full_pool_by_type: dict[str, list[str]],
    priority_rank: dict[str, int], wishes: dict[str, int],
) -> tuple[dict[str, int], list[dict]]:
    """Each of the 5 usable Lord types is now a real, fixed card (its
    theme chosen up front via ArcanaThemeChoiceDialog, not searched) --
    so unlike the earlier count-budget model, there's no more "which
    theme"/"skip this type" decision left to explore. Each type's card
    independently contributes _arcana_best_card_contribution's perfect-
    case values (sequentially, in usable_types order, so a later type's
    "remaining need" already reflects what earlier types covered)."""
    covered: dict[str, int] = {}
    path: list[dict] = []
    for ct in usable_types:
        theme = type_to_theme.get(ct)
        if not theme:
            continue
        contribution, need_based_ids = _arcana_best_card_contribution(
            eligible_by_type.get(ct, []), full_pool_by_type.get(ct, []), priority_rank, wishes, covered,
        )
        if not contribution:
            continue
        for sid, value in contribution.items():
            covered[sid] = covered.get(sid, 0) + value
        path.append({"type": ct, "theme": theme, "skill_ids": contribution, "need_based_ids": need_based_ids})
    return covered, path


def _arcana_compute_combinations(
    usable_types: list[str], type_to_theme: dict[str, str],
    class_skill_pools: dict[str, list[dict]], wishes: dict[str, int],
    skill_type_by_id: dict[str, str], priority_rank: dict[str, int] | None = None,
    max_results: int = 3,
) -> list[dict]:
    """Up to max_results distinct combinations, best first: the single
    result from _arcana_best_combination, then that same sequential fill
    repeated with the previous result's (type, skill) pairs excluded from
    that type's eligible AND full pool each time, forcing a structurally
    different combination whenever a type's real pool has more viable
    wished skills than its 4 slots (or a skill is shared across more than
    one type's pool) -- the only remaining source of alternatives now
    that each type's theme is fixed rather than searched. Pruning
    full_pool_by_type too (not just eligible_by_type) matters: otherwise
    a skill excluded as a WISH target could still silently reappear as
    plain FILLER on the very same card (filler selection draws from the
    whole pool), quietly re-covering the same wish and making the
    "different" combination not actually different.

    Only excludes need_based_ids (see _arcana_best_card_contribution),
    not every skill_id a type touched -- a skill that ended up on a
    SECOND type purely as incidental filler (that type had unused slots
    left over after its own real wishes, and this skill happened to rank
    high in the fallback priority-list order) never actually contributed
    to satisfying the wish there, so excluding it too was blocking a real
    second combination that should have been findable by simply routing
    that wish through the other type instead (User-reported, 2026-09-13:
    "hier gibt es doch sicher noch andere Kombinationen" -- confirmed via
    direct inspection: a single wished skill, fully covered by one type
    alone, still incidentally showed up as a 1-point filler pick on a
    second type in the same result, and that filler pick alone was enough
    to make every subsequent solve attempt collapse to 0% coverage)."""
    if not wishes:
        return []

    eligible_by_type = {
        ct: _arcana_eligible_skills_for_type(ct, wishes, class_skill_pools, skill_type_by_id)
        for ct in usable_types
    }
    full_pool_by_type = {ct: _arcana_full_pool_for_type(ct, class_skill_pools) for ct in usable_types}
    priority_rank = priority_rank or {}

    results = []
    excluded: set[tuple] = set()
    for _ in range(max_results):
        pruned_eligible = {
            ct: [sid for sid in eligible if (ct, sid) not in excluded]
            for ct, eligible in eligible_by_type.items()
        }
        pruned_full_pool = {
            ct: [sid for sid in pool if (ct, sid) not in excluded]
            for ct, pool in full_pool_by_type.items()
        }
        covered, path = _arcana_best_combination(
            usable_types, type_to_theme, pruned_eligible, pruned_full_pool, priority_rank, wishes,
        )
        if not path:
            break
        results.append({"assignments": path, "covered": covered})
        for a in path:
            for sid in a["need_based_ids"]:
                excluded.add((a["type"], sid))
    return results


def _arcana_result_coverage_percent(result: dict, wishes: dict[str, int]) -> float:
    """What percentage of the total wishlist this combination covers,
    clamped per skill at its own wish (overshoot on one skill doesn't
    offset a shortfall on another) -- used to filter out combinations
    that aren't a useful alternative (User-Wunsch, 2026-08-29: "nur
    Kombinationen anzeigen, die besser als 50% sind")."""
    total_wish = sum(wishes.values())
    if total_wish <= 0:
        return 0.0
    covered = result.get("covered", {})
    total_useful = sum(min(covered.get(sid, 0), need) for sid, need in wishes.items())
    return total_useful / total_wish * 100.0


def _arcana_eligible_types(
    skill_id: str, category: str | None, usable_types: list[str], class_skill_pools: dict[str, list[dict]],
) -> list[str]:
    """Which usable Lord types could ever target this skill -- in its
    pool AND matching its Active/Passive category (Chalice's "both"
    always matches)."""
    return [
        ct for ct in usable_types
        if any(s["id"] == skill_id for s in class_skill_pools.get(ct, []))
        and (_ARCANA_LORD_CATEGORY.get(ct) == "both" or _ARCANA_LORD_CATEGORY.get(ct) == category)
    ]


def _arcana_max_ceiling(
    skill_id: str, category: str | None, usable_types: list[str], class_skill_pools: dict[str, list[dict]],
) -> int:
    """The absolute most this skill could ever gain from Arcana THIS
    season assuming perfect leveling, ignoring every other wish -- one
    maxed Unique card can push any ONE skill up to _ARCANA_PER_SKILL_CAP
    (4), per eligible Lord type, since a type can go to whichever theme
    still has budget when the real split is chosen later (User-Wunsch,
    2026-08-29: "wenn ein Skill bereits +4 ist, kann der Rest maximal
    noch +3 werden" -- this is the standalone half of that; the OTHER
    half, how much competing wishes actually leave once slots are shared,
    is what _arcana_compute_combinations/_arcana_uncovered_reason resolve
    for a specific split+wishlist instead of a live, always-on number)."""
    eligible = _arcana_eligible_types(skill_id, category, usable_types, class_skill_pools)
    return len(eligible) * _ARCANA_PER_SKILL_CAP


def _arcana_uncovered_reason(
    skill_id: str, wish: int, covered: int, usable_types: list[str],
    class_skill_pools: dict[str, list[dict]], skill_type_by_id: dict[str, str],
) -> tuple[str, dict]:
    """Why a wished skill didn't fully reach its target in a given result
    (User-Wunsch, 2026-08-29: "einen Grund zeigen, warum gewisse Skills
    nicht gepusht werden koennen") -- returns a translation key + kwargs
    for _t(), one of three tiers:

    1. No eligible Lord type at all -- structural, can never be covered
       regardless of slots (skill isn't in any usable card's pool, or
       none match its Active/Passive category).
    2. Eligible types exist, but even dedicating every one of them to
       ONLY this skill can't reach the wish -- a hard ceiling from this
       season's real card pool, not specific to this one combination
       (theme choice no longer matters here: every usable type is always
       a real card regardless of which theme it's set to).
    3. Eligible types exist and COULD in principle reach the wish, just
       not in this particular combination -- those slots went to other
       wishes instead in this solve."""
    category = skill_type_by_id.get(skill_id)
    eligible_types = _arcana_eligible_types(skill_id, category, usable_types, class_skill_pools)
    if not eligible_types:
        return "arm_arcana_reason_no_card", {}

    max_possible = len(eligible_types) * _ARCANA_PER_SKILL_CAP
    if max_possible < wish:
        return "arm_arcana_reason_not_enough_slots", {"max": max_possible}

    return "arm_arcana_reason_competing_wishes", {}
