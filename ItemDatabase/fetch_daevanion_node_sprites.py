"""Fetches the Daevanion Board's real per-grade node frame sprites (5 tiers
x enabled/disabled state, Start has no disabled state) -- User-found CDN
path, 2026-08-28: `cdn.questlog.gg/aion-2/assets/images-test/`, NOT
`questlog.gg/assets/` (that path returns an identical SPA-fallback image
for every filename, verified via matching MD5 across all 5 -- a dead end
found earlier the same day, before this real path was found).

These are generic per-TIER frame art (a distinct engraved medallion design
per grade -- Common/Rare/Legend/Unique/Start), not per-stat-specific --
confirmed exhaustively against all 16,200 real questlog.gg nodes that the
node's own `icon` field is always exactly one of these 5 URLs, identical
for every stat_name/skill_id within a grade. The actual stat/skill-specific
content shown per node in the app is a separate overlay (a resolved skill
icon, or a drawn abbreviation badge for stats -- see app.py's
_daevanion_build_node_icons), composited on top of whichever of these two
sprites the node's current state calls for.

Usage:
    python fetch_daevanion_node_sprites.py
"""

import urllib.request
from pathlib import Path

BASE_URL = "https://cdn.questlog.gg/aion-2/assets/images-test"
OUT_DIR = Path(__file__).parent / "assets" / "daevanion_nodes"

GRADES = ["Common", "Rare", "Legend", "Unique"]


def _fetch(name: str) -> bytes | None:
    url = f"{BASE_URL}/{name}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError:
        return None


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fetched = 0
    for grade in GRADES:
        for suffix in ("Sprite", "Disabled_Sprite"):
            filename = f"UT_FWindow_Daevanion_Node_{grade}_{suffix}.webp"
            data = _fetch(filename)
            if data is None:
                print(f"MISSING: {filename}")
                continue
            (OUT_DIR / filename).write_bytes(data)
            fetched += 1
    # Start has no disabled state -- always auto-active.
    data = _fetch("UT_FWindow_Daevanion_Node_Start_Sprite.webp")
    if data is not None:
        (OUT_DIR / "UT_FWindow_Daevanion_Node_Start_Sprite.webp").write_bytes(data)
        fetched += 1

    print(f"Fetched {fetched} sprites -> {OUT_DIR}")


if __name__ == "__main__":
    main()
