"""Offline maintenance script (same convention as compute_dungeon_sets.py /
fetch_item_details.py) -- scans the real per-item subStats data to build the
"Verfügbare Werte" reference list the Eigenschaften-Priorität editor shows
per equipment category (Waffe/Guard, Rüstung, Schmuck, Bracelets), so the
player picks from real, catalog-verified stat names instead of typing them
freehand. Run whenever the catalog is refreshed:

    python compute_stat_priority_options.py

Writes data/stat_priority_options.json: {category: [stat names, most
common on real items first]}.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
ITEMS_PATH = DATA_DIR / "items_all.json"
DETAILS_DIR = DATA_DIR / "details"
OUTPUT_PATH = DATA_DIR / "stat_priority_options.json"

# Same groups the editor's category tabs use -- matches _STAT_PRIORITY_
# CATEGORIES in app.py (kept independent here since this script has no
# import from app.py, same isolation as compute_dungeon_sets.py). "ring"
# split out from "jewelry" (2026-08-27, User-Wunsch: Rings need a
# fundamentally different priority -- Active Skill 1-6 > Attack -- from
# Earring/Necklace's Attack > Accuracy > Critical Hit; Amulet dropped
# entirely, its subStats are never random). Armor further split into one
# bucket per real piece (2026-08-27, User-Wunsch: "Jedes Rüstungsteil hat
# eine eigene Prio Liste") -- every piece happens to share the exact same
# underlying subStat pool in practice, but each has its own dropdown to
# keep the split visible/independent in the UI.
CATEGORY_NAMES = {
    "weapon": {"Greatsword", "Longsword", "Dagger", "Bow", "Spellbook", "Orb", "Mace", "Staff", "Fist", "Guard"},
    "helmet": {"Helm"},
    "shoulder": {"Pauldrons"},
    "torso": {"Top"},
    "gloves": {"Gloves"},
    "pants": {"Legs"},
    "boots": {"Shoes"},
    "ring": {"Ring"},
    "jewelry": {"Earrings", "Necklace"},
    "bracelet": {"Bracelet"},
}


def main():
    items = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
    if isinstance(items, dict):
        items = items.get("items", items)

    group_ids: dict[str, list[int]] = {g: [] for g in CATEGORY_NAMES}
    for item in items:
        cat = item.get("categoryName")
        for group, names in CATEGORY_NAMES.items():
            if cat in names:
                group_ids[group].append(item["id"])

    result: dict[str, list[str]] = {}
    for group, ids in group_ids.items():
        counts: dict[str, int] = {}
        for item_id in ids:
            detail_path = DETAILS_DIR / f"{item_id}.json"
            if not detail_path.exists():
                continue
            try:
                detail = json.loads(detail_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            # subStatRandom=False means every listed subStat is always
            # active on that item -- no roll, nothing to prioritize between
            # them. Only items that actually roll N-of-M substats
            # (subStatRandom=True) represent a real choice worth listing
            # here. Found via a real user report (2026-08-27, "Bei den
            # bracelets sind mehr Werte, als eigentlich möglich sind"):
            # ~10 fixed non-Bracelet items (Ascension/Drifter/Facade/...)
            # were leaking their always-on stats (Attack/HP/Critical Hit/...)
            # into the same pool as the real random Deity-stat Bracelets
            # (Justice [Nezekan] etc, subStatRandom=True) -- verified
            # weapon/armor/jewelry have zero such contamination already,
            # this only ever affected Bracelet.
            if not detail.get("subStatRandom"):
                continue
            for sub_stat in detail.get("subStats") or []:
                name = sub_stat.get("name")
                if name:
                    counts[name] = counts.get(name, 0) + 1
        result[group] = [name for name, _ in sorted(counts.items(), key=lambda kv: -kv[1])]

    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    for group, names in result.items():
        print(f"{group}: {len(names)} stat names")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
