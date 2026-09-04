"""Fetches the Pantheon item catalog (Artwork/Statue/Colossus) -- these grant
Empyrean Lord points (same 10 lords/keys as Arcana cards, see
_ARCANA_LORD_STAT_IDS in app.py: life/wisdom/illusion/destiny/death/freedom/
justice/space/time/destruction) but aren't part of shugo.gg's item catalog at
all (checked: shugo.gg's own item-details API returns these items with no
mainStats/options whatsoever -- Pantheon point values are a separate game
system it doesn't model).

Source: questlog.gg's own Character Builder tool needs this data for its
Pantheon panel (12 Artwork slots + 4 Statue slots + 1 Colossus slot = 17,
confirmed by cross-referencing a real saved build's "pantheon" section
against this catalog, 2026-09-04) and fetches it from its own backend's
tRPC endpoint `characterBuilder.getEquipmentItems` -- a ~30MB response
covering EVERY equipment item, not just Pantheon, so this script pulls that
whole payload but only keeps the `mainCategory == "pantheon"` subset.

28 of 236 items (mostly "(Bound)" reward items and unreleased "[Season 2]"
previews) have no stat data even on questlog's own side -- a genuine
upstream gap, not something this script can fill in. Kept in the output
with an empty stats dict rather than dropped, so the app can decide how to
surface "no data yet" itself.

Usage:
    python fetch_pantheon_items.py
"""

import json
import urllib.request
from pathlib import Path

URL = "https://questlog.gg/aion-2/api/trpc/characterBuilder.getEquipmentItems?input=%7B%22language%22%3A%22en%22%7D"
OUTPUT_PATH = Path(__file__).parent / "data" / "pantheon_items.json"

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def main():
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.load(r)
    items = payload["result"]["data"]
    print(f"Fetched {len(items)} total equipment items from questlog.gg")

    pantheon = [it for it in items if it.get("mainCategory") == "pantheon"]
    out = []
    missing = 0
    for it in pantheon:
        stats = (it.get("itemStats") or {}).get("pantheon") or {}
        if not stats:
            missing += 1
        out.append({
            "id": it["id"], "name": it["name"], "subCategory": it["subCategory"],
            "grade": it.get("grade"), "icon": it.get("icon"), "stats": stats,
        })

    by_sub = {}
    for it in out:
        by_sub[it["subCategory"]] = by_sub.get(it["subCategory"], 0) + 1

    OUTPUT_PATH.write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(f"{len(out)} Pantheon items ({by_sub}), {missing} without stat data -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
