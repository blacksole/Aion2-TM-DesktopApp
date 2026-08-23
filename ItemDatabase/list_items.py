"""List/filter the locally cached AION 2 item data (run fetch_items.py first).

Examples:
    python list_items.py --stats
    python list_items.py --grade Legend --category Ring
    python list_items.py --search Dragon --class Gladiator
"""

import argparse
import json
from collections import Counter
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "items_all.json"


def load_items() -> list[dict]:
    if not DATA_PATH.exists():
        raise SystemExit(f"No cached data at {DATA_PATH} — run fetch_items.py first.")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return data.get("items", [])


def print_stats(items: list[dict]):
    print(f"Total items: {len(items)}")
    print("\nBy grade:")
    for grade, count in Counter(i.get("grade") for i in items).most_common():
        print(f"  {grade:10s} {count}")
    print(f"\nCategories ({len(set(i.get('categoryName') for i in items))}):")
    for cat, count in Counter(i.get("categoryName") for i in items).most_common(15):
        print(f"  {cat:30s} {count}")


def print_items(items: list[dict], limit: int):
    for item in items[:limit]:
        classes = ", ".join(item.get("classNames") or []) or "-"
        print(f"[{item.get('grade')}] {item.get('name')}  (id={item.get('id')})")
        print(f"    category: {item.get('categoryName')}  classes: {classes}  tradable: {item.get('tradable')}")
        for opt in item.get("options") or []:
            print(f"    - {opt}")
        print()
    if len(items) > limit:
        print(f"... {len(items) - limit} more (use --limit to see more)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grade", help="Filter by grade (e.g. Legend, Epic, Unique, Rare, Common)")
    parser.add_argument("--category", help="Filter by categoryName (e.g. Ring, Greatsword)")
    parser.add_argument("--class", dest="class_name", help="Filter by class (e.g. Gladiator)")
    parser.add_argument("--search", help="Substring match on item name")
    parser.add_argument("--limit", type=int, default=20, help="Max items to print (default 20)")
    parser.add_argument("--stats", action="store_true", help="Print summary stats instead of a list")
    args = parser.parse_args()

    items = load_items()

    if args.stats:
        print_stats(items)
        return

    if args.grade:
        items = [i for i in items if (i.get("grade") or "").lower() == args.grade.lower()]
    if args.category:
        items = [i for i in items if (i.get("categoryName") or "").lower() == args.category.lower()]
    if args.class_name:
        items = [i for i in items if args.class_name.lower() in [c.lower() for c in (i.get("classNames") or [])]]
    if args.search:
        items = [i for i in items if args.search.lower() in (i.get("name") or "").lower()]

    print(f"{len(items)} matching item(s)\n")
    print_items(items, args.limit)


if __name__ == "__main__":
    main()
