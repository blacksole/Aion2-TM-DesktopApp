"""Offline maintenance script (same convention as compute_stat_priority_
options.py / compute_dungeon_sets.py) -- scans every per-item detail file's
real `sources` field to find which items are actually purchasable from a
real in-game shop/vendor, so the Template dialog's "Import from Database"
picker can pre-filter to just those instead of the full ~10k-item catalog.
Run whenever the catalog is refreshed:

    python compute_shop_items.py

Writes data/shop_items.json: {shop_name: [item_id, ...]}.

Only 4 shop types are actually tagged anywhere in the scraped `sources`
data (verified 2026-08-29 by scanning every detail file for every distinct
`sources` value): Merchant NPC, Trade Shop, Black Cloud Merchants, Shugo
Festival. Windbreeze Shop/Season Shop/Nightmare Shop/Abyss Store do NOT
appear under any `sources` tag (or item name) anywhere in the catalog --
User-decision (2026-08-29): those 4 stay hand-curated Template entries in
the "Default" profile instead (no picker/DB filtering for them), revisited
once real Global screenshots are available (see project_todo.md memory,
tied to the Sept 17/30 Global test-phase checkpoint).
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DETAILS_DIR = DATA_DIR / "details"
OUTPUT_PATH = DATA_DIR / "shop_items.json"

# The only 4 `sources` values that represent a real, buyable shop/vendor --
# everything else (Quest, Crafting, Looted from monsters, Reward Chest,
# Achievements, Sanctuary, Rank, Substance Morph, Sealed Dungeon, Hidden
# Cube, Subscribe, Stronghold, Gathering, Ascension, Monolith, Attendance,
# Expedition) is a drop/reward/craft source, not something you shop for.
SHOP_SOURCES = {"Merchant NPC", "Trade Shop", "Black Cloud Merchants", "Shugo Festival"}


def main():
    shops: dict[str, list[int]] = {name: [] for name in SHOP_SOURCES}
    scanned = 0
    for path in DETAILS_DIR.glob("*.json"):
        try:
            detail = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        scanned += 1
        item_id = detail.get("id")
        if not item_id:
            continue
        for source in detail.get("sources") or []:
            if source in SHOP_SOURCES:
                shops[source].append(item_id)

    OUTPUT_PATH.write_text(json.dumps(shops, indent=2), encoding="utf-8")
    print(f"Scanned {scanned} detail files.")
    for name, ids in shops.items():
        print(f"  {name}: {len(ids)} items")
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
