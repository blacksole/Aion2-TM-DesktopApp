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

# Same 4 groups the editor's category tabs use -- matches _STAT_PRIORITY_
# CATEGORIES in app.py (kept independent here since this script has no
# import from app.py, same isolation as compute_dungeon_sets.py).
CATEGORY_NAMES = {
    "weapon": {"Greatsword", "Longsword", "Dagger", "Bow", "Spellbook", "Orb", "Mace", "Staff", "Fist", "Guard"},
    "armor": {"Helm", "Pauldrons", "Top", "Gloves", "Legs", "Shoes"},
    "jewelry": {"Earrings", "Necklace", "Ring", "Amulet"},
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
