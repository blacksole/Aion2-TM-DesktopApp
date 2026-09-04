"""Fetches the real per-enchant-level Wings stat tables (fpmax/decreasedamage/
amplifyweapondamage/etc per level, from Wing_Unique_Enchant "level 0" base up
to its max) -- shugo.gg's item catalog lists Wings as items but (like
Pantheon, see fetch_pantheon_items.py) doesn't expose usable stat data for
them; the Item Database's existing Wings filters only cover Equip/Owned
Effect labels, not real numbers.

Source: questlog.gg's own Character Builder backend, tRPC endpoint
`characterBuilder.getWings` -- 134 entries (67 named wings x 2 race variants,
"light"=Elyos/"dark"=Asmodian, same stats per name just a different item id/
icon per race, confirmed 2026-09-04). Numeric `grade` codes cross-checked
against shugo.gg's own grade strings for the same item ids where a Pantheon
item happened to share one (11=Common/21=Rare/31=Legend/41=Unique/51=Epic);
grade 71 (real values, sample checked against a Pantheon id: consistently
absent from shugo's 5-grade catalog) only ever appears on clearly cosmetic/
cash-shop wing skins (e.g. "Maid Ribbon Wings", "Sunshine Wings") -- almost
certainly a "Cosmetic" tier above Epic with no shugo.gg equivalent to
confirm the exact label against; stored as-is (raw numeric code), not
guessed into a name.

Usage:
    python fetch_wings_items.py
"""

import json
import urllib.request
from pathlib import Path

URL = "https://questlog.gg/aion-2/api/trpc/characterBuilder.getWings?input=%7B%22language%22%3A%22en%22%7D"
OUTPUT_PATH = Path(__file__).parent / "data" / "wings_items.json"

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def main():
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.load(r)
    wings = payload["result"]["data"]
    print(f"Fetched {len(wings)} wing entries from questlog.gg")

    out = []
    for w in wings:
        # Real per-level stat values live under equipStats.enchants -- NOT
        # enchantInfo (that's just enchant-attempt success-rate/cost-item
        # data, a first-pass mistake caught by an empty-stats sanity check
        # after the initial fetch, 2026-09-04).
        levels = [
            {"level": e["level"], "stats": e.get("stats") or {}}
            for e in ((w.get("equipStats") or {}).get("enchants") or [])
        ]
        out.append({
            "id": w["id"], "name": w["name"], "race": w.get("race"),
            "grade": w.get("grade"), "icon": w.get("icon"), "levels": levels,
        })

    by_race = {}
    for w in out:
        by_race[w["race"]] = by_race.get(w["race"], 0) + 1

    OUTPUT_PATH.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8",
    )
    print(f"{len(out)} wings ({by_race}) -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
