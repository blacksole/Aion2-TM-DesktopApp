"""Fetches AION 2 dungeon data (type, recommended level, reward items) from
gamers4.life's public dungeon database pages, caching locally.

Same scraping technique as fetch_recipes.py/fetch_skills.py -- this is the
link between "which dungeons are live this season" and "which crafting
materials/recipes are actually obtainable": a dungeon's Reward Items list
cross-referenced against recipe input-item IDs tells us which recipes need
a material that only drops from a given dungeon.

Usage:
    python fetch_dungeons.py [--limit N]
"""

import argparse
import html
import json
import re
import time
import urllib.request
from pathlib import Path

SITEMAP_URL = "https://gamers4.life/aion-2/database/sitemaps/en-dungeon.xml"
DUNGEON_PAGE_URL = "https://gamers4.life/aion-2/database/en/dungeon/{id}/"
OUT_PATH = Path(__file__).parent / "data" / "dungeons_all.json"
REQUEST_DELAY = 0.35  # seconds between requests -- be polite

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Aion2TM-DungeonFetch/1.0)"}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _dungeon_ids_from_sitemap() -> list[str]:
    xml = _get(SITEMAP_URL)
    ids = []
    for line in xml.splitlines():
        line = line.strip()
        if "<loc>" in line and "/dungeon/" in line:
            url = line.split("<loc>")[1].split("</loc>")[0]
            dungeon_id = url.rstrip("/").split("/")[-1]
            ids.append(dungeon_id)
    return ids


def _unescape(html_str: str) -> str:
    """No longer used by parse_dungeon_page() (see its docstring: the
    current page shape has nothing left to backslash-unescape) -- kept
    as a tiny public helper in case a future scrape of this same site
    needs it again, same as fetch_recipes.py's own copy."""
    return html_str.replace('\\"', '"')


_KV_RE = re.compile(r'<div class="k">([^<]*)</div><div class="v">([^<]*)</div>')
_H1_TITLE_RE = re.compile(r'<h1 class="title">([^<]*)</h1>')
# The one JSON blob the page embeds verbatim, inside a <details><summary>
# dungeonRewardsItems</summary><pre>...</pre></details> block, HTML-escaped
# (&quot; etc.) -- much simpler to pull out than the "Record fields"
# key/value table above, which has no such structured sibling for lists.
_REWARDS_PRE_RE = re.compile(
    r'<summary>dungeonRewardsItems</summary><pre>(.*?)</pre>', re.DOTALL
)


def _parse_record_fields(html: str) -> dict:
    """The "Record fields" card is a flat sequence of <div class="k">KEY</div>
    <div class="v">VALUE</div> pairs (no nesting, no quoting to worry about)
    -- a key with no real value renders as the literal em-dash "—"."""
    result = {}
    for key, value in _KV_RE.findall(html):
        result[key] = None if value == "—" else value
    return result


def parse_dungeon_page(raw_html: str) -> dict | None:
    """gamers4.life switched its dungeon detail pages from a server-rendered
    React/JSON data blob (the old `"div","mainCategory",{...}` shape this
    function used to look for) to plain server-rendered HTML with a
    key/value `.table` card plus one JSON blob for item rewards (CI
    failure, 2026-10-01: 0/548 dungeons fetched, the old marker string no
    longer exists anywhere on the page at all). Re-reads the SAME page
    shape every other field already comes from, just via the new markup.
    """
    if '<h1 class="title">' not in raw_html or 'class="k">mainCategory</div>' not in raw_html:
        return None  # 404 or unrecognized page shape

    name_match = _H1_TITLE_RE.search(raw_html)
    fields = _parse_record_fields(raw_html)

    reward_items = []
    rewards_match = _REWARDS_PRE_RE.search(raw_html)
    if rewards_match:
        raw_json = html.unescape(rewards_match.group(1))
        try:
            reward_items = [
                {"id": int(it["id"]), "name": it.get("name")}
                for it in json.loads(raw_json)
            ]
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            reward_items = []

    def _bool(key: str) -> bool:
        return fields.get(key) == "true"

    map_id = fields.get("mapId")
    return {
        "id": int(map_id) if map_id and map_id.isdigit() else None,
        "name": name_match.group(1) if name_match else None,
        "mainCategory": fields.get("mainCategory"),
        "description": fields.get("description"),
        "dungeonType": fields.get("dungeonType"),
        "recommendLevel": fields.get("recommendLevel"),
        "usesDungeonUi": _bool("usesDungeonUi"),
        "isInstanceLayer": _bool("isInstanceLayer"),
        "mapId": map_id,
        "createdAt": fields.get("createdAt"),
        "updatedAt": fields.get("updatedAt"),
        "rewardItems": reward_items,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only fetch the first N dungeons (testing)")
    args = parser.parse_args()

    print("Lade Dungeon-Sitemap...")
    ids = _dungeon_ids_from_sitemap()
    print(f"{len(ids)} Dungeon-IDs gefunden.")
    if args.limit:
        ids = ids[:args.limit]

    dungeons = []
    failed = []
    for i, dungeon_id in enumerate(ids, 1):
        url = DUNGEON_PAGE_URL.format(id=dungeon_id)
        try:
            raw = _get(url)
            parsed = parse_dungeon_page(raw)
            if parsed:
                dungeons.append(parsed)
            else:
                failed.append(dungeon_id)
        except Exception as e:
            print(f"  Fehler bei {dungeon_id}: {e}")
            failed.append(dungeon_id)

        if i % 50 == 0 or i == len(ids):
            print(f"  {i}/{len(ids)} verarbeitet ({len(dungeons)} ok, {len(failed)} fehlgeschlagen)")

        time.sleep(REQUEST_DELAY)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({"dungeons": dungeons, "failed": failed}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fertig: {len(dungeons)} Dungeons gespeichert nach {OUT_PATH} ({len(failed)} fehlgeschlagen)")


if __name__ == "__main__":
    main()
