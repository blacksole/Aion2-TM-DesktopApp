"""Precomputes the Dungeon-Set grouping used by the Build Planner's
Schnellauswahl (QuickGearSelectDialog) -- writes data/dungeon_sets.json so
the app never has to read ~3000 individual detail files live at dialog-open
time (that took ~17s in a from-scratch session; this makes it instant).

Groups Neutral-type (dungeon) gear by shared name root (e.g. "Abyssal Helm"/
"Abyssal Ring"/... -> root "Abyssal") and buckets each root under whichever
of _DUNGEON_SOURCE_TAGS its detail data's "sources" field mentions, merged
across every item sharing that name (bound/unbound copies of the identical
item don't always agree on "sources" -- confirmed real data quirk, e.g. one
"Abyssal Helm" copy lists Sanctuary, its unbound twin lists nothing).

"Crafting" (User-Wunsch, 2026-08-26: "jetzt müssen wir nur bei Expedition/
Sanctuary -> Crafting hinzufügen") needs a second, different grouping
strategy: its items are flavor-named weapons (e.g. "Corroded Sovereign's
Malice", "Lava Heart Flamesword") that don't end in a plain slot word at
all -- 0 matched the suffix rule above when checked directly. These are
grouped by their first-two-word PREFIX instead (e.g. "Corroded Sovereign's",
"Lava Heart"), only for items the suffix pass didn't already claim (so a
same-named armor root from Expedition/Sanctuary, e.g. "Lava Heart" the
level-128 armor set, can't get merged with the unrelated level-45 "Lava
Heart" Crafting weapons just because they share a name).

Only level-45 sets are kept (User-Wunsch, 2026-08-26: "Nimm bitte erstmal
alles an Gear unter level 45 raus ... Level 50 kannst du genauso rausnehmen -
Level 50 schalten wir später frei") -- current end-game level, Level 50
content isn't unlocked yet. A root is kept only if EVERY one of its slots
resolves to equipLevel 45 (a root with mixed/other levels is dropped
entirely rather than partially, e.g. "Judicator" itself is level 35 and
gets excluded, while "Corrupted Judicator" at level 45 is kept).

Standalone maintenance script -- run this whenever items_all.json/data/
details are refreshed (same rhythm as fetch_items.py/fetch_item_details.py),
not wired into cont_ToDo_app itself:
    python compute_dungeon_sets.py
"""

import json
from pathlib import Path

BASE = Path(__file__).parent
ITEMS_PATH = BASE / "data" / "items_all.json"
DETAILS_DIR = BASE / "data" / "details"
OUT_PATH = BASE / "data" / "dungeon_sets.json"

# Every source tag that appears anywhere in the catalog (User-Wunsch,
# 2026-08-26: "Dann solltest du alle anderen Sets auch jeweils definieren
# und dort entsprechend der anderen Filter einsetzen" -- Expedition/
# Sanctuary/Crafting alone left the Rarität filter useless on the crafted
# Gear-Stufe list, since that whole line is 100% Unique; the fix is more
# Dungeon-Quelle options with an actual rarity spread, not a UI change).
# Not every tag will produce a real >=3-slot level-45 set -- e.g. Attendance/
# Subscribe/Ascension are login/cash-shop rewards, not dungeon gear -- empty
# ones are simply omitted from the written result below.
DUNGEON_SOURCE_TAGS = [
    "Expedition", "Sanctuary", "Crafting", "Reward Chest", "Quest",
    "Looted from monsters", "Black Cloud Merchants", "Achievements",
    "Shugo Festival", "Trade Shop", "Rank", "Substance Morph",
    "Sealed Dungeon", "Hidden Cube", "Subscribe", "Stronghold",
    "Merchant NPC", "Gathering", "Ascension", "Monolith", "Attendance",
]
REQUIRED_LEVEL = 45

# Checked like any other tag above, but never written to the output (User-
# Wunsch, 2026-08-26, after checking: "Reward Chest ist die [Chest] der
# jeweiligen Dungeons ... Kannst du schauen, ob du die Rewardchests den
# Dungeons zuordnen kannst?"). Confirmed: of Reward Chest's 33 sets, 22
# already carry Expedition/Sanctuary too (so they're already reachable
# there, "Reward Chest" is just a redundant drop-METHOD label, not its own
# dungeon) -- the other 11 turned out to be World Boss drops, not dungeon
# gear at all (User: "Das scheinen alle Golddrops von Worldbossen zu sein
# ... wird aber sicher niemand als Rüstungsset ausrüsten"). "Looted from
# monsters" is the exact same story with ZERO Expedition/Sanctuary overlap
# (100% World Boss names). "Substance Morph" is a single set that's already
# fully covered by Expedition/Sanctuary -- redundant, not incorrect, just
# pointless as its own one-item dropdown option.
EXCLUDED_FROM_OUTPUT = {"Reward Chest", "Looted from monsters", "Substance Morph"}

# "Crafting" itself is excluded here too (User-Wunsch, 2026-08-26: "das sind
# in dem Fall aber Transfer Crafting. Da Transfercrafting aber gefühlt alles
# abbildet, hier rausnehmen.") -- its 3 sets (Corroded Sovereign's/Faded
# Shadow/Lava Heart) are reachable via Transfer Crafting from almost
# anything, not a meaningful distinct category. "Crafting" as a Gear
# Type-Filter option still exists in the app (app.py special-cases it to
# show the crafted Dragon Lord chain), it just no longer merges in these 3
# via this data file -- see CORRODED_SOVEREIGNS_MOVED_TO_EXPEDITION below
# for where they go instead.
EXCLUDED_FROM_OUTPUT.add("Crafting")

# 2 of the 3 (Faded Shadow/Lava Heart) already carry the "Expedition" tag
# too and stay reachable there unchanged. "Corroded Sovereign's" does NOT
# (only Crafting/Reward Chest/Sanctuary in the raw data) -- moved into
# Expedition explicitly instead of just dropping it entirely (User-Wunsch:
# "Du kannst diese 3 Sets aber bei Dungeons anzeigen, falls nicht bereits
# vorhanden").
CORRODED_SOVEREIGNS_MOVED_TO_EXPEDITION = "Corroded Sovereign's"

# Temporarily held back (User-Wunsch, 2026-08-26: "Da ich Lunatic nicht
# kenne und die Raids ab 98 losgehen ... wir das aber nicht genau wissen,
# sollten wir Sanctuary rausnehmen fürs erste und später mit reinnehmen.
# Zeigen wir erstmal Crafting und Dungeons nur als Vorfilter an.") -- not a
# data problem like the tags above, just not confident enough yet about
# what's actually current/correct on Global. Remove from this set once
# that's confirmed to bring Sanctuary back.
TEMPORARILY_HELD_BACK = {"Sanctuary"}

# PvP Abyss-shop gear (User-Wunsch, 2026-08-27: "wenn PvP ausgewählt - bitte
# 'Abyss Gear' anzeigen"). Not sourced via the generic "sources" tag scan
# above at all -- these are rank-shop rewards, identified by name instead:
# "{Guardian|Archon} {Rank} {Slot}". Guardian = Elyos, Archon = Asmodae,
# confirmed directly in-game (User screenshot, 2026-08-27: Elyos's own Abyss
# shop only ever lists "Guardian ..." items, in this exact rank order).
ABYSS_GEAR_RACE_PREFIXES = ["Guardian", "Archon"]
ABYSS_GEAR_RANKS = ["Decanus", "Centurion", "Tribunus", "Praetorian Captain", "High Commander"]


def build_abyss_gear(by_name: dict[str, list[dict]]) -> dict[str, dict]:
    """Root names keep the race prefix (e.g. "Guardian Decanus") -- unlike
    every other tag here, Guardian/Archon roots are NOT interchangeable
    between races, so app.py's Item-Set dropdown filters these down to only
    the character's own race's 5 roots by prefix at display time. Excludes
    unrelated same-prefix items that don't fit the "{Rank} {Slot}" pattern
    (e.g. "Guardian Lord Nahma", "Guardian Token (Skin: Helm)", "Guardian of
    Honor (Skin: Boots)") automatically, since only the 5 known rank names
    are checked -- no generic prefix scan."""
    result: dict[str, dict] = {}
    for prefix in ABYSS_GEAR_RACE_PREFIXES:
        for rank in ABYSS_GEAR_RANKS:
            root = f"{prefix} {rank}"
            # Ring as the reference slot -- every rank has exactly one,
            # unlike the weapon slots (class-specific); same convention as
            # app.py's own _tier_grade() for the crafted Dragon Lord chain.
            variants = by_name.get(f"{root} Ring")
            if not variants:
                continue
            grades = {v.get("grade") for v in variants if v.get("grade")}
            gearscores: set[int] = set()
            for variant in variants:
                detail_path = DETAILS_DIR / f"{variant.get('id')}.json"
                if detail_path.exists():
                    detail = json.loads(detail_path.read_text(encoding="utf-8"))
                    if detail.get("level"):
                        gearscores.add(detail["level"])
            if len(grades) != 1 or len(gearscores) != 1:
                continue
            result[root] = {"grade": next(iter(grades)), "gearscore": next(iter(gearscores))}
    return result


DUNGEON_SET_SLOT_WORDS = [
    "Helm", "Ring", "Boots", "Greatsword", "Breastplate", "Greaves", "Gloves",
    "Pauldrons", "Necklace", "Earrings", "Dagger", "Longsword", "Bow",
    "Spellbook", "Orb", "Mace", "Staff", "Fist", "Guard",
    # Missing these undercounted sets and, for "Faded Shadow" specifically,
    # its Crafting source tag (only found on its Bracelet piece) -- real bug
    # caught by the User: "aktuell müssen wir daran denken, die Bracelet
    # Slots mit reinzubringen" / "der aktuelle Eintrag Crafting hat mehr als
    # 2 Sets".
    "Bracelet", "Brooch", "Amulet",
]


def gear_type(item: dict) -> str:
    options = item.get("options") or []
    if not options:
        return ""
    if any("PvP" in o for o in options):
        return "PvP"
    if any("PvE" in o for o in options):
        return "PvE"
    return "Neutral"


def main():
    data = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
    items = data.get("items", data) if isinstance(data, dict) else data

    by_name: dict[str, list[dict]] = {}
    for item in items:
        name = item.get("name")
        if name:
            by_name.setdefault(name, []).append(item)

    root_sources: dict[str, set[str]] = {}
    root_slot_count: dict[str, int] = {}
    root_levels: dict[str, set[int]] = {}
    root_grades: dict[str, set[str]] = {}
    root_gearscores: dict[str, set[int]] = {}
    claimed_names: set[str] = set()

    def _accumulate(root: str, name: str, variants: list[dict]):
        root_slot_count[root] = root_slot_count.get(root, 0) + 1
        merged = root_sources.setdefault(root, set())
        levels = root_levels.setdefault(root, set())
        grades = root_grades.setdefault(root, set())
        gearscores = root_gearscores.setdefault(root, set())
        for variant in variants:
            if variant.get("grade"):
                grades.add(variant["grade"])
            detail_path = DETAILS_DIR / f"{variant.get('id')}.json"
            if detail_path.exists():
                detail = json.loads(detail_path.read_text(encoding="utf-8"))
                merged.update(detail.get("sources") or [])
                if detail.get("equipLevel"):
                    levels.add(detail["equipLevel"])
                # "level" is the item's own GearScore contribution -- same
                # field _update_gearscore() in app.py already sums up.
                if detail.get("level"):
                    gearscores.add(detail["level"])
        claimed_names.add(name)

    # Pass 1: armor/weapon sets whose item names end in a plain slot word
    # (e.g. "Abyssal Helm" -> root "Abyssal").
    for name, variants in by_name.items():
        if gear_type(variants[0]) != "Neutral":
            continue
        for word in DUNGEON_SET_SLOT_WORDS:
            if not name.endswith(" " + word):
                continue
            root = name[: -(len(word) + 1)]
            _accumulate(root, name, variants)
            break

    # Pass 2: flavor-named weapons (e.g. Crafting's "Corroded Sovereign's
    # Malice") that pass 1 couldn't group at all since they don't end in a
    # plain slot word -- grouped by first-two-word prefix instead, only
    # among names pass 1 didn't already claim.
    prefix_candidates: dict[str, list[tuple[str, list[dict]]]] = {}
    for name, variants in by_name.items():
        if name in claimed_names or gear_type(variants[0]) != "Neutral":
            continue
        words = name.split(" ")
        if len(words) < 3:
            continue
        prefix = " ".join(words[:2])
        prefix_candidates.setdefault(prefix, []).append((name, variants))

    for prefix, entries in prefix_candidates.items():
        if len(entries) < 3:
            continue
        for name, variants in entries:
            _accumulate(prefix, name, variants)

    # {tag: {root: {"grade": ..., "gearscore": ...}}} -- every kept root is
    # confirmed to resolve to exactly one grade AND one gearscore across all
    # its slots (verified against the real data: 0 of 25 checked roots span
    # more than one of either), so single values per root are safe, not
    # lists. gearscore is the "DungeonsetName (Gearscore Standard)" display
    # value (User-Wunsch, 2026-08-26: move the Dungeon-Set dropdown to the
    # main position, formatted with its GearScore).
    result: dict[str, dict[str, dict]] = {tag: {} for tag in DUNGEON_SOURCE_TAGS}
    for root, count in root_slot_count.items():
        if count < 3:
            continue
        if root_levels.get(root) != {REQUIRED_LEVEL}:
            continue
        grades = root_grades.get(root) or set()
        if len(grades) != 1:
            continue
        gearscores = root_gearscores.get(root) or set()
        if len(gearscores) != 1:
            continue
        grade = next(iter(grades))
        gearscore = next(iter(gearscores))
        for tag in DUNGEON_SOURCE_TAGS:
            if tag in root_sources.get(root, set()):
                result[tag][root] = {"grade": grade, "gearscore": gearscore}

    # User-Wunsch, 2026-08-26 (revised after the exact dungeon-per-set
    # mapping turned out not worth chasing): "Wir ignorieren, welches Set zu
    # welchem Dungeon gehört ... Es reicht, wenn Sanctuary nur die Sets
    # zeigt, die in Dungeons [Expedition] nicht verfügbar sind." -- Sanctuary
    # is genuinely a superset of Expedition (confirmed real game mechanic,
    # see git history), but for this quick-select button showing the
    # redundant overlap adds no value -- only Sanctuary's own exclusives are
    # worth a separate entry here; anyone wanting a specific overlapping
    # item can already pick it directly via the regular item picker.
    if "Sanctuary" in result and "Expedition" in result:
        result["Sanctuary"] = {
            root: info for root, info in result["Sanctuary"].items()
            if root not in result["Expedition"]
        }

    # Move "Corroded Sovereign's" into Expedition before "Crafting" gets
    # excluded below (User-Wunsch: "Du kannst diese 3 Sets aber bei Dungeons
    # anzeigen, falls nicht bereits vorhanden") -- already passed the same
    # >=3-slot/level-45/single-grade/single-gearscore gate as everything
    # else above (User: "auch hier 'auf level 50' prüfen und ggf
    # rausfiltern" -- already satisfied, nothing further needed).
    root = CORRODED_SOVEREIGNS_MOVED_TO_EXPEDITION
    if "Expedition" in result and root not in result["Expedition"] and root in result.get("Crafting", {}):
        result["Expedition"][root] = result["Crafting"][root]

    abyss_gear = build_abyss_gear(by_name)
    if abyss_gear:
        result["Abyss Gear"] = abyss_gear

    # Drop tags with zero real sets (e.g. Attendance/Subscribe/Ascension are
    # login/cash-shop rewards, not dungeon gear), the confirmed non-dungeon/
    # redundant tags in EXCLUDED_FROM_OUTPUT, and anything TEMPORARILY_HELD_
    # BACK, so the Dungeon-Quelle dropdown only ever offers options that are
    # non-empty, a real distinct dungeon, and currently confident/ready.
    result = {
        tag: dict(sorted(roots.items()))
        for tag, roots in result.items()
        if roots and tag not in EXCLUDED_FROM_OUTPUT and tag not in TEMPORARILY_HELD_BACK
    }

    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for tag, roots in result.items():
        print(f"{tag}: {len(roots)} sets")
    empty = [tag for tag in DUNGEON_SOURCE_TAGS if tag not in result and tag not in EXCLUDED_FROM_OUTPUT
             and tag not in TEMPORARILY_HELD_BACK]
    if empty:
        print("Omitted (0 sets):", ", ".join(empty))
    held_back_present = [tag for tag in TEMPORARILY_HELD_BACK if tag in DUNGEON_SOURCE_TAGS]
    if held_back_present:
        print("Temporarily held back:", ", ".join(held_back_present))
    excluded_present = [tag for tag in EXCLUDED_FROM_OUTPUT if tag in DUNGEON_SOURCE_TAGS]
    if excluded_present:
        print("Excluded (non-dungeon/redundant):", ", ".join(excluded_present))
    print("Wrote", OUT_PATH)


if __name__ == "__main__":
    main()
