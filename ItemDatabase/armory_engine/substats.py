"""Property-priority profiles and the substat auto-pick.

Moved verbatim out of ``ItemDatabase/app.py`` (audit B-armory.md §2.2/§3.1,
old app.py:10955–11122): the six ``(Gear-Typ x Rolle)`` profiles, their
per-category defaults, and the greedy first-match walk that turns one of
those ordered name lists into a set of substat indices.

What stayed in app.py: ``_ROLE_BUTTON_OBJECT_NAMES`` and ``_ROLE_LABEL_KEYS``
(Qt object names and translation keys — presentation, not model), and
``_load_stat_priority_options`` (reads ``data/stat_priority_options.json``
through a module-global cache; file I/O with app-relative paths belongs to
the caller, not the engine).

Audit §2.2 is blunt about what this algorithm is and is not: ordinal ranks
only, no weights, no marginal value, no interaction with what is already
stacked.  The *profile data structure* is the right seed for a real scoring
function; the *consumption* is a first-match walk.  Preserved exactly as it
behaves today so the scoring work has a fixed baseline to diff against.
"""

from __future__ import annotations

__all__ = [
    "_DEFAULT_STAT_PRIORITY_BY_CATEGORY",
    "_STAT_NAME_ALIASES",
    "_STAT_PRIORITY_GEAR_TYPES",
    "_STAT_PRIORITY_MAX_ENTRIES",
    "_STAT_PRIORITY_ROLES",
    "_default_stat_priority_profiles",
    "_merge_stat_priority_profiles",
    "_normalize_stat_name",
    "_pick_priority_substats",
]

# Eigenschaften-Priorität profiles are keyed [gear_type][role][category] ->
# an ordered list of up to _STAT_PRIORITY_MAX_ENTRIES stat names (User-
# Wunsch: "Filter PvP und PvE drin... Rollen Angreifer, Verteidiger und
# Support... Prioliste bis zu 7 Werte... als Profile, die man setzen kann").
_STAT_PRIORITY_GEAR_TYPES = ("PvE", "PvP")
_STAT_PRIORITY_ROLES = ("Angreifer", "Verteidiger", "Support")

_STAT_PRIORITY_MAX_ENTRIES = 7

# Starting point for every one of the 6 (Gear-Typ x Rolle) profiles, all
# identical until the player edits them via the gear-icon editor -- only
# PvE/Angreifer has real guide backing today (project_gear_stat_guide.md,
# 2026-08-24, offered as a "recommendation, please double-check"); the
# other 5 profiles reuse it as a reasonable starting point rather than
# shipping empty (an empty list would leave every substat slot unfilled).
# Names/casing must match the real catalog exactly (not the guide's own
# prose wording, e.g. "Attack increase"/"Move Speed", not "Attack Increase"/
# "Movement Speed") -- the editor's dropdown restore (QComboBox.findData) is
# an exact-string lookup, unlike the case-insensitive matching
# _pick_priority_substats uses for the real auto-pick, so a wording
# mismatch here silently resets to "— empty —" in the editor even though
# auto-pick itself would have matched fine.
_DEFAULT_STAT_PRIORITY_BY_CATEGORY: dict[str, list[str]] = {
    "weapon": ["Weapon Damage Boost", "Combat Speed", "Damage Boost", "Might", "Precision", "Attack", "Multi-hit Chance"],
    # Per-piece armor priorities straight from the guide's detailed
    # per-slot breakdown (User-Wunsch, 2026-08-27: "Jedes Rüstungsteil hat
    # eine eigene Prio Liste"). "Passive Skills" (every guide line's last
    # entry) isn't a literal matchable name -- whatever ranks remain after
    # these already get filled from the player's own Passive Skill Priority
    # List automatically (see _apply_quick_substats), no explicit entry
    # needed, same reasoning as Jewelry/Ring below.
    "helmet": ["Attack increase", "Smite", "Attack", "Endurance", "Incoming Heal"],
    "shoulder": ["Critical Damage Boost", "Attack", "Endurance", "Defense increase", "Accuracy", "Critical Hit"],
    "torso": ["Damage Boost", "Attack", "Endurance", "Defense increase", "Accuracy", "Critical Hit"],
    "gloves": ["Combat Speed", "Attack", "Perfect Chance", "Defense increase", "Accuracy", "Critical Hit"],
    "pants": ["Damage Tolerance", "Attack increase", "Attack", "Perfect Chance", "Endurance"],
    "boots": ["Move Speed", "Attack", "Perfect Chance", "Defense increase", "Accuracy", "Critical Hit"],
    # Guide: "Earrings & Necklace: Attack > Accuracy > Critical Hit >
    # Passive Skills" -- the trailing "Passive Skills" isn't a literal
    # matchable name (no fixed one is universal/class-agnostic), so it's
    # left off here; whatever substat slots remain after these 3 already
    # get filled from the player's own Passive Skill Priority List
    # automatically (see _apply_quick_substats), no explicit entry needed.
    "jewelry": ["Attack", "Accuracy", "Critical Hit"],
    # Guide: "Rings: Active Skill 1-6 (in slot order) > Attack" -- only the
    # "Attack" fallback is a universal name safe to bake in; the 6 Active
    # skill ranks ahead of it are class-/player-specific (same reasoning as
    # Bracelet below) and must be set by hand via the editor, which already
    # lists the player's own Active Skill Priority List first in this tab's
    # dropdown for convenience (see StatPriorityEditorDialog).
    "ring": ["Attack"],
    # Left empty on purpose (User-Wunsch, 2026-08-27): only the fixed,
    # non-random story-reward Bracelet ever rolled Attack/Critical Hit/HP,
    # and its stats can't be changed anyway. Every actually customizable
    # Bracelet (Abyssal and above) only rolls the 10 Deity stats instead
    # (see compute_stat_priority_options.py) -- no real guide backing
    # exists yet for ranking those against each other, so this stays empty
    # rather than pointing at values no Bracelet can ever roll.
    "bracelet": [],
}


def _default_stat_priority_profiles() -> dict[str, dict[str, dict[str, list[str]]]]:
    return {
        gear_type: {
            role: {cat: list(names) for cat, names in _DEFAULT_STAT_PRIORITY_BY_CATEGORY.items()}
            for role in _STAT_PRIORITY_ROLES
        }
        for gear_type in _STAT_PRIORITY_GEAR_TYPES
    }


def _merge_stat_priority_profiles(saved: dict | None) -> dict[str, dict[str, dict[str, list[str]]]]:
    """Merges a persisted profiles dict onto the defaults -- keeps a saved
    profile missing a not-yet-existing gear_type/role/category (e.g. an
    older profile from before this feature) filled in rather than blank."""
    result = _default_stat_priority_profiles()
    for gear_type, roles in (saved or {}).items():
        if gear_type not in result:
            continue
        for role, categories in (roles or {}).items():
            if role not in result[gear_type]:
                continue
            for category, names in (categories or {}).items():
                if category in result[gear_type][role] and isinstance(names, list):
                    result[gear_type][role][category] = [str(n) for n in names][:_STAT_PRIORITY_MAX_ENTRIES]
    return result


# Precomputed real subStat names per category (compute_stat_priority_
# options.py) -- shown as the editor's "Verfügbare Werte" reference list so
# the player picks from real, catalog-verified stat names instead of typing
# Known real-data wording that differs from the guide's own term -- matching
# is otherwise case-insensitive exact-name, which already covers e.g. the
# guide's "Defense Increase" vs. the catalog's "Defense increase".
_STAT_NAME_ALIASES = {"movement speed": "move speed"}


def _normalize_stat_name(name: str) -> str:
    key = (name or "").strip().lower()
    return _STAT_NAME_ALIASES.get(key, key)


def _pick_priority_substats(sub_stats: list[dict], count: int, priority_names: list[str]) -> set[int]:
    """Picks up to `count` indices into sub_stats, walking priority_names
    (the current Gear-Typ/Rolle/Kategorie profile's ordered stat-name list)
    top to bottom and taking the first still-unused match for each name --
    falls through the WHOLE list (not just the first few entries) so a
    slot whose top preferences aren't among its real options still gets its
    substat slots filled from lower-priority ones rather than being left
    empty (explicit user instruction: even the last-ranked entry should
    still be used if a slot has that many substat slots to fill)."""
    if count <= 0 or not sub_stats or not priority_names:
        return set()
    normalized = [_normalize_stat_name(s.get("name") or "") for s in sub_stats]
    chosen: list[int] = []
    used: set[int] = set()
    for wanted_name in priority_names:
        if len(chosen) >= count:
            break
        wanted = _normalize_stat_name(wanted_name)
        for i, name in enumerate(normalized):
            if i in used or name != wanted:
                continue
            chosen.append(i)
            used.add(i)
            break
    return set(chosen[:count])

