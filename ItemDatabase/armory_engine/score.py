"""Rank-derived role weights, and the two honest things they can say.

Stage 2 of ``docs/audit-2026-09-18/B-armory.md``; feature #1 of §3.4, in the
form §3.4's own last line says is defensible.

**What this module refuses to do.**  §3.4 #1 is titled "stat gap vs role
target" and its example sentence is *"you're 240 Accuracy under the
PvE-Angreifer profile"*.  That sentence needs an absolute target, and an
absolute target needs a combat model — how much a point of Accuracy is worth
against a level-45 boss, where the soft caps sit, what diminishing returns
look like.  The catalog does not ship one; §2.2 already records that the
profiles are **ordinal ranks, not weights**, and §3.4 closes with "a true
substat optimizer ... is gated on a combat model the data doesn't ship".
Inventing the 240 would mean inventing the model, and the player would have
no way to tell the difference between a number that came from the game and a
number that came from us.

So this module computes only what the data actually supports:

* a **weight vector** derived from the rank order the player already edits
  (``substats._DEFAULT_STAT_PRIORITY_BY_CATEGORY`` and their saved
  overrides), by geometric decay.  It says "rank 1 matters more than rank 4",
  which is exactly what a ranked list means and nothing more.
* **coverage**, not magnitude: which stats the profile ranks high are carried
  by *no equipped slot*, and which are carried by few.  A stat that no piece
  provides is a fact in no units at all, so it survives the absence of a
  combat model intact.  This is what makes the per-slot attribution from
  ``stats.compute_stat_totals_detailed``'s ``by_slot`` load-bearing rather
  than decorative.

Comparing the *magnitude* of two different stats is the thing that would
require the model — 3 000 Attack against 44 Critical Hit is not a comparison,
it is two different units — so nothing here does it.  The one place a
magnitude comparison IS legitimate is the same stat against a baseline
(``reference``): same units, same stat, so the ratio means something.

Everything returned is a :class:`~armory_engine.explain.Reason` or a
:class:`~armory_engine.explain.Recommendation`; ``text_key`` is always a
translation key, never a sentence.
"""

from __future__ import annotations

import re

from armory_engine.enchant import _GEAR_STAT_ID_ALIASES
from armory_engine.explain import Reason, Recommendation
from armory_engine.substats import _normalize_stat_name

__all__ = [
    "REASON_SLOT_OFF_PROFILE",
    "REASON_STAT_ABSENT",
    "REASON_STAT_BEHIND",
    "REASON_STAT_SUBSTAT_MISSING",
    "REASON_STAT_THIN",
    "RECO_SUBSTAT_ALIGNMENT",
    "display_names",
    "merge_role_weights",
    "normalize_stat_id",
    "role_weights",
    "stat_gap",
    "stat_gap_ranked",
    "stat_name_index",
    "substat_alignment",
]

#: Translation keys this module attaches to its reasons.  Constants rather
#: than literals at the construction site: the key is the contract with
#: ``core/translations.py`` and with the dashboard, and a typo in a literal
#: ships as the key itself rendered on screen (``tr`` falls back to the key).
REASON_STAT_ABSENT = "armory_reason_stat_absent"
REASON_STAT_THIN = "armory_reason_stat_thin"
REASON_STAT_BEHIND = "armory_reason_stat_behind"
REASON_STAT_SUBSTAT_MISSING = "armory_reason_substat_missing"
REASON_SLOT_OFF_PROFILE = "armory_reason_slot_off_profile"
RECO_SUBSTAT_ALIGNMENT = "armory_reco_substat_alignment"

#: ``"CriticalHit"`` -> ``"Critical Hit"``: split before a capital that
#: follows a lowercase or is followed by a lowercase, so ``"HPRegen"`` gives
#: ``"HP Regen"`` rather than ``"H P Regen"``.
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

#: Default decay between consecutive ranks.  0.75 puts rank 7 (the profile
#: cap, ``_STAT_PRIORITY_MAX_ENTRIES``) at 0.75**6 = 0.178 of rank 1 — an
#: order of magnitude, which is the shape a hand-ranked list of seven
#: implies, without the last entry collapsing to zero (the auto-pick walks
#: the WHOLE list and really does use rank 7, see ``_pick_priority_substats``).
DEFAULT_DECAY = 0.75


def normalize_stat_id(stat_id: str) -> str:
    """A stat **id** reduced to the same space as a stat **name**.

    The two halves of the Armory speak different dialects of the same stat:
    totals are keyed by id (``"CriticalHit"``, post
    ``_GEAR_STAT_ID_ALIASES``), the role profiles are lists of catalog names
    (``"Critical Hit"``).  Joining them needs a bridge, and the *correct*
    bridge is :func:`stat_name_index` — the details carry both spellings on
    every entry, so the real pairing is readable from the data.

    This is the fallback for an id no detail explained, and it is a good one
    because the ids are PascalCase renderings of the names.  It is a fallback
    rather than the method because the equality is a convention, not a
    guarantee: ``"WeaponFixingDamage"`` is displayed as ``"Attack"``.
    """
    spaced = _CAMEL_BOUNDARY.sub(" ", str(stat_id or ""))
    return _normalize_stat_name(spaced)


def role_weights(profile_ranked_names: list[str], decay: float = DEFAULT_DECAY) -> dict[str, float]:
    """Turn one ranked stat-name list into ``{normalized name: weight}``.

    ``weight = decay ** rank``, rank 0 first, so the top entry is exactly
    1.0 and every step down multiplies by ``decay``.  Geometric rather than
    linear because a ranked list is a *preference order*, not a scale: with
    linear weights the gap between rank 1 and rank 2 would depend on how
    many entries the player happened to type, which is not information the
    player supplied.

    Names are normalized through ``substats._normalize_stat_name`` — the
    same function the live auto-pick matches with — so the alias table
    (``"movement speed"`` -> ``"move speed"``) and the case-insensitivity
    apply here identically.  A weight vector that disagreed with the
    auto-pick about what a name means would explain a pick the app never
    made.

    A repeated name keeps its FIRST (best) rank and does not consume one:
    the ranks stay dense, so a list with a duplicate is weighted like the
    list without it rather than silently demoting everything after it.
    """
    if not 0.0 < decay <= 1.0:
        raise ValueError(f"decay must be in (0, 1], got {decay!r}")
    weights: dict[str, float] = {}
    rank = 0
    for raw in profile_ranked_names or ():
        key = _normalize_stat_name(str(raw))
        if not key or key in weights:
            continue
        weights[key] = decay ** rank
        rank += 1
    return weights


def merge_role_weights(
    categories: dict[str, list[str]], decay: float = DEFAULT_DECAY
) -> dict[str, float]:
    """One build-wide vector out of a profile's per-category lists.

    The profiles are ``[gear_type][role][category] -> ranked names``: nine
    categories, each with its own ordering (the guide really does rank Move
    Speed first for boots and Damage Boost first for the torso).  A
    *build-wide* statement — "this build carries none of what the profile
    ranks highest" — needs one vector, and the honest merge is the best rank
    a stat achieves anywhere: a stat ranked #1 for one slot is a stat the
    role wants, even if another slot never asks for it.

    Taking the max (rather than a sum or a mean) is what keeps this free of
    an assumption about how many slots *could* carry a stat, which is again
    catalog-shaped knowledge we would be inventing.
    """
    merged: dict[str, float] = {}
    for names in (categories or {}).values():
        for key, weight in role_weights(names if isinstance(names, list) else [], decay).items():
            if weight > merged.get(key, 0.0):
                merged[key] = weight
    return merged


def display_names(categories: dict[str, list[str]]) -> dict[str, str]:
    """``{normalized name: the spelling the player/catalog uses}``.

    The weight vector is keyed by the normalized form so it joins reliably;
    a sentence shown to a player must use the real spelling
    (``"Defense increase"``, not ``"defense increase"`` and not the
    title-cased ``"Defense Increase"`` the catalog does not use).  First
    spelling wins, which is the profile's own top-ranked occurrence.

    These stay English on a German or Russian screen, and that is correct:
    they are catalog identifiers, like item names, and the Armory shows
    those untranslated everywhere else too.
    """
    names: dict[str, str] = {}
    for entries in (categories or {}).values():
        for raw in entries if isinstance(entries, list) else ():
            key = _normalize_stat_name(str(raw))
            if key and key not in names:
                names[key] = str(raw)
    return names


def stat_name_index(details) -> dict[str, str]:
    """``{stat_id: normalized stat name}`` read off any iterable of details.

    Every ``mainStats``/``subStats`` entry carries both ``id`` and ``name``
    (see ``model.StatEntry``), so the id-to-name pairing the join needs is
    data, not a table anyone has to maintain.  Built from the details of the
    *equipped* items, which is all the ids a build's totals can contain.

    Ids are put through ``_GEAR_STAT_ID_ALIASES`` first, because
    ``compute_stat_totals_detailed`` does: real gear spells the same stat
    two ways (``"Defense"`` on the piece, ``"DefenseBonus"`` in the totals),
    and an index keyed by the raw spelling would fail to join on exactly the
    stats the alias table exists for — silently, as "the build carries none
    of it".

    First spelling wins; the catalog is consistent enough that a conflict
    would itself be the finding.
    """
    index: dict[str, str] = {}
    for detail in details or ():
        if not isinstance(detail, dict):
            continue
        for bucket in ("mainStats", "subStats"):
            for entry in detail.get(bucket) or ():
                if not isinstance(entry, dict):
                    continue
                stat_id = entry.get("id")
                stat_id = _GEAR_STAT_ID_ALIASES.get(stat_id, stat_id)
                key = _normalize_stat_name(str(entry.get("name") or ""))
                if stat_id and key and stat_id not in index:
                    index[str(stat_id)] = key
    return index


def _fold_by_name(totals: dict, index: dict[str, str]) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Regroup id-keyed totals under normalized stat names.

    Two ids can fold onto one name (the catalog does this: ``"Attack"`` is
    both a main stat id ``WeaponFixingDamage`` on a weapon and a substat id
    ``Attack`` on a ring), so the ids are kept as a list — a reason has to
    name one, and an attribution has to look at all of them.
    """
    values: dict[str, float] = {}
    ids: dict[str, list[str]] = {}
    for stat_id, value in (totals or {}).items():
        key = index.get(str(stat_id)) or normalize_stat_id(stat_id)
        if not key:
            continue
        try:
            values[key] = values.get(key, 0.0) + float(value)
        except (TypeError, ValueError):
            continue
        ids.setdefault(key, []).append(str(stat_id))
    return values, ids


def stat_gap_ranked(
    totals: dict,
    weights: dict[str, float],
    reference: dict | None = None,
    *,
    by_slot: dict | None = None,
    slots=(),
    index: dict[str, str] | None = None,
    names: dict[str, str] | None = None,
    top_k: int = 3,
) -> list[tuple[float, Reason]]:
    """:func:`stat_gap` with the shortfall each reason was ranked by.

    The shortfall is deliberately NOT a field on ``Reason``: ``Reason``'s
    ``delta``/``weight`` are defined (``explain.py``) as the stat's own
    change and what the role thinks of it, and a third number that is a
    function of both would be a second, competing score on the same record.
    Callers that need it — the orchestrator, which sums it into a
    ``Recommendation.score_delta`` — ask for it explicitly here.

    * ``shortfall = weight * (1 - slot coverage)`` with no reference: a stat
      no equipped slot carries scores its full weight; one every slot
      carries scores zero.  Unit-free, so comparable across stats.
    * ``shortfall = weight * (reference - current) / reference`` with one:
      the same stat against a baseline build, which is the only magnitude
      comparison the missing combat model does not invalidate.
    """
    index = index or {}
    names = names or {}
    by_slot = by_slot or {}
    current_by_name, ids_by_name = _fold_by_name(totals, index)
    reference_by_name = _fold_by_name(reference, index)[0] if reference is not None else None

    active = tuple(slots) or tuple(sorted({
        slot for per_slot in by_slot.values() for slot, value in per_slot.items() if value
    }))

    ranked: list[tuple[float, str, Reason]] = []
    for key, weight in weights.items():
        current = current_by_name.get(key, 0.0)
        stat_ids = ids_by_name.get(key, [])
        carrying = sorted({
            slot
            for stat_id in stat_ids
            for slot, value in (by_slot.get(stat_id) or {}).items()
            if value
        })
        label = names.get(key, key)
        kwargs = {"stat": label, "slots": len(carrying), "total": len(active)}

        if reference_by_name is not None:
            baseline = reference_by_name.get(key, 0.0)
            if baseline <= 0 or current >= baseline:
                continue
            shortfall = weight * (baseline - current) / baseline
            text_key = REASON_STAT_BEHIND
            kwargs = {**kwargs, "reference": baseline, "value": current}
        else:
            coverage = (len(carrying) / len(active)) if active else 0.0
            shortfall = weight * (1.0 - coverage)
            text_key = REASON_STAT_ABSENT if not carrying else REASON_STAT_THIN

        if shortfall <= 0.0:
            continue
        ranked.append((
            shortfall,
            key,
            Reason(
                # The id a caller can join back onto ``totals``/``by_slot``;
                # the normalized name when the build carries none of it,
                # which is the honest "joins onto nothing yet".
                stat_id=stat_ids[0] if stat_ids else key,
                delta=current,
                weight=weight,
                text_key=text_key,
                text_kwargs=kwargs,
            ),
        ))

    # Sorted by shortfall, then by weight, then by name: a deterministic
    # order matters more than the tie-break's merit, because this list is
    # rendered and a reshuffling dashboard is a broken one.
    ranked.sort(key=lambda row: (-row[0], -row[2].weight, row[1]))
    return [(shortfall, reason) for shortfall, _, reason in ranked[: max(0, top_k)]]


def stat_gap(
    totals: dict,
    weights: dict[str, float],
    reference: dict | None = None,
    **kwargs,
) -> list[Reason]:
    """The top-k stats the role profile wants and this build barely carries.

    See :func:`stat_gap_ranked` for the ranking rule and the module
    docstring for why this reports coverage rather than a target number.
    Each ``Reason`` carries the stat's CURRENT value as ``delta`` (the
    explain contract's "how much this stat changes if the recommendation is
    taken" degenerates, for a diagnosis rather than a pick, to "how much
    there is"), the role weight, and the per-slot attribution in
    ``text_kwargs``.
    """
    return [reason for _, reason in stat_gap_ranked(totals, weights, reference, **kwargs)]


def substat_alignment(
    equipped_substats: dict[str, list[str]],
    weights: dict[str, float],
    *,
    top_n: int = 3,
    names: dict[str, str] | None = None,
) -> Recommendation:
    """How much of the substat sheet the role profile actually asked for.

    This is audit §3.4 feature #1 in its defensible form.  The feature as
    written wants a gap against a target; what the data supports is a gap
    against the player's **own** stated preference — the profile is their
    ranking, the chosen substats are their picks, and the two disagreeing is
    a fact that needs no combat model to establish.

    Two findings, both unit-free:

    * the **share** of chosen substats that are among the profile's top-N;
    * the **slots whose picks are entirely off-profile**, which is where the
      share is actually losing, and is directly actionable (the Build
      Planner's per-slot substat picker is one click from the dashboard).

    ``score_delta`` is ``1 - share``: the fraction of the sheet on the
    table.  It is NOT a sum of the reasons' ``score_contribution``, and
    cannot be — ``explain.Recommendation`` promises that sum for a
    stat-space solver (§3.4 #3/#4, both gated on the combat model).  Here
    the reasons enumerate the finding instead of decomposing it, which is
    stated rather than hidden; MASTER §5 records the same caveat.

    An empty sheet (no substat chosen anywhere, e.g. no detail resolvable)
    returns a zero recommendation with no reasons and an empty ``text_key``;
    ``recommend.next_best_actions`` drops it rather than showing a card
    about nothing.
    """
    names = names or {}
    top = tuple(sorted(weights, key=lambda key: (-weights[key], key))[: max(0, top_n)])

    chosen: dict[str, list[str]] = {}
    # The raw catalog spelling of each pick, kept alongside the normalized
    # key: a pick that is NOT in the profile has no player-chosen spelling
    # to fall back on (``names`` only knows the profile's own entries), and
    # naming it "combat speed" in a sentence when the catalog and the
    # Armory both say "Combat Speed" is a needless mismatch.
    spelled: dict[str, list[str]] = {}
    for slot, picks in (equipped_substats or {}).items():
        pairs = [(_normalize_stat_name(str(pick)), str(pick)) for pick in picks or ()]
        pairs = [pair for pair in pairs if pair[0]]
        chosen[str(slot)] = [key for key, _ in pairs]
        spelled[str(slot)] = [raw for _, raw in pairs]

    total = sum(len(keys) for keys in chosen.values())
    aligned = sum(1 for keys in chosen.values() for key in keys if key in top)
    share = (aligned / total) if total else 0.0

    if not total:
        return Recommendation(
            pick={"kind": "substat_alignment", "aligned": 0, "total": 0, "share": 0.0,
                  "top": top, "top_n": top_n, "missing": (), "off_profile_slots": ()},
            score_delta=0.0,
        )

    off_profile_slots = tuple(
        slot for slot in sorted(chosen)
        if chosen[slot] and not any(key in weights for key in chosen[slot])
    )
    missing = tuple(key for key in top if not any(key in keys for keys in chosen.values()))

    reasons = [
        Reason(
            stat_id=key,
            delta=0.0,
            weight=weights[key],
            text_key=REASON_STAT_SUBSTAT_MISSING,
            text_kwargs={"stat": names.get(key, key)},
        )
        for key in missing
    ]
    reasons += [
        Reason(
            # The slot's own first pick: a real stat, so ``stat_id`` keeps
            # meaning what explain.py says it means.  The slot travels in
            # ``text_kwargs``, where the sentence needs it.
            stat_id=chosen[slot][0],
            delta=0.0,
            weight=0.0,
            text_key=REASON_SLOT_OFF_PROFILE,
            text_kwargs={"slot": slot, "stat": names.get(chosen[slot][0]) or spelled[slot][0]},
        )
        for slot in off_profile_slots
    ]

    return Recommendation(
        pick={
            "kind": "substat_alignment",
            "aligned": aligned,
            "total": total,
            "share": share,
            "top": top,
            "top_n": top_n,
            "missing": missing,
            "off_profile_slots": off_profile_slots,
        },
        score_delta=1.0 - share,
        reasons=tuple(reasons),
        text_key=RECO_SUBSTAT_ALIGNMENT,
        text_kwargs={"aligned": aligned, "total": total, "top_n": len(top)},
    )
