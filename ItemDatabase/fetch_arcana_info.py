"""Extracts all Arcana card data from the already-fetched data/items_all.json
(categoryName == "Arcana") into a clean structured file, and downloads each
card's real icon (already plain PNGs on assets.playnccdn.com, no webp
conversion needed unlike the skill icons) into assets/arcana_icons/.

Card data comes entirely from each item's own 'description' text, which
shugo.gg's catalog already includes verbatim, e.g.:
    "Empyrean Lord Stats: Time [Siel]\nSkill Effects: 4 Mastery Skill Levels"
    "Main Stats: Attack Bonus\nSub Stats: Random Stats"
No numeric stat values are exposed anywhere in the API for Arcana cards —
only this flavor-text summary — so this captures the full extent of what's
available.

Run after fetch_items.py (needs data/items_all.json to already exist).

Usage:
    python fetch_arcana_info.py
"""

import json
import re
import time
import urllib.request
from pathlib import Path

ITEMS_PATH = Path(__file__).parent / "data" / "items_all.json"
OUT_PATH = Path(__file__).parent / "data" / "arcana_info.json"
ICON_DIR = Path(__file__).parent / "assets" / "arcana_icons"
REQUEST_DELAY = 0.15

_LORD_RE = re.compile(r"Empyrean Lord Stats:\s*([^\[\n]+)\[([^\]]+)\]")
_SKILL_RE = re.compile(r"Skill Effects?:\s*(\d+)\s*(.+Skill Levels)")
_MAIN_STAT_RE = re.compile(r"Main Stats:\s*([^\n]+)")
_SUB_STAT_RE = re.compile(r"Sub Stats:\s*([^\n]+)")
_NAME_RE = re.compile(r"Arcana: (\w+) of (\w+)")
_SET_LABEL_RE = re.compile(r"_([A-Za-z]+Set\d+)\.png")


def parse_arcana_item(item: dict) -> dict:
    name_match = _NAME_RE.match(item["name"])
    card_type, theme = name_match.group(1), name_match.group(2)

    desc = item.get("description", "")
    lord_match = _LORD_RE.search(desc)
    skill_match = _SKILL_RE.search(desc)
    main_stat_match = _MAIN_STAT_RE.search(desc)
    sub_stat_match = _SUB_STAT_RE.search(desc)

    image = item.get("image", "")
    set_label_match = _SET_LABEL_RE.search(image)

    return {
        "id": item["id"],
        "name": item["name"],
        "cardType": card_type,
        "theme": theme,
        "grade": item.get("grade"),
        "image": image,
        "iconFile": image.rsplit("/", 1)[-1] if image else None,
        "setLabel": set_label_match.group(1) if set_label_match else None,
        "empyreanLord": lord_match.group(1).strip() if lord_match else None,
        "deity": lord_match.group(2).strip() if lord_match else None,
        "skillLevels": int(skill_match.group(1)) if skill_match else None,
        "skillCategory": skill_match.group(2).strip() if skill_match else None,
        "mainStat": main_stat_match.group(1).strip() if main_stat_match else None,
        "subStat": sub_stat_match.group(1).strip() if sub_stat_match else None,
    }


def main():
    data = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
    arcana_items = [it for it in data.get("items", []) if it.get("categoryName") == "Arcana"]
    print(f"Found {len(arcana_items)} Arcana items in {ITEMS_PATH.name}")

    parsed = [parse_arcana_item(it) for it in arcana_items]
    OUT_PATH.write_text(json.dumps({"arcana": parsed}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved structured data to {OUT_PATH}")

    ICON_DIR.mkdir(parents=True, exist_ok=True)
    distinct_icons = {p["image"]: p["iconFile"] for p in parsed if p["image"]}
    print(f"Downloading {len(distinct_icons)} distinct icons...")
    ok, failed = 0, []
    for i, (url, filename) in enumerate(distinct_icons.items(), 1):
        out_path = ICON_DIR / filename
        if out_path.exists():
            ok += 1
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=20).read()
            out_path.write_bytes(raw)
            ok += 1
            print(f"  [{i}/{len(distinct_icons)}] {filename}")
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            failed.append(filename)
            print(f"  [{i}/{len(distinct_icons)}] FAILED {filename}: {e}")

    print(f"\nDone: {ok} ok, {len(failed)} failed")
    if failed:
        print("Failed:", failed)


if __name__ == "__main__":
    main()
