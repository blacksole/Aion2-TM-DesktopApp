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

PROP_KEYS = [
    "id", "mainCategory", "description", "dungeonType", "recommendLevel",
    "usesDungeonUi", "isInstanceLayer", "mapId", "createdAt", "updatedAt",
]


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


def _unescape(html: str) -> str:
    return html.replace('\\"', '"')


def _extract_balanced(html: str, start: int, open_ch="{", close_ch="}") -> str | None:
    depth = 0
    i = start
    in_string = False
    n = len(html)
    while i < n:
        ch = html[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return html[start:i + 1]
        i += 1
    return None


def _parse_properties(html: str) -> dict:
    result = {}
    for key in PROP_KEYS:
        marker = f'"div","{key}",{{'
        idx = html.find(marker)
        if idx == -1:
            continue
        obj_start = html.find("{", idx)
        block = _extract_balanced(html, obj_start, "{", "}")
        if not block:
            continue
        strings = re.findall(r'"children":"([^"]*)"', block)
        if len(strings) >= 2:
            result[key] = strings[-1]
        elif len(strings) == 1:
            result[key] = None
    return result


def _parse_name(html: str) -> str | None:
    m = re.search(r'"mt-0\.5 text-xs text-faint","children":\["id ","(\d+)"\]', html)
    m2 = re.search(r'"font-display text-2xl font-bold leading-tight sm:text-3xl","children":"([^"]+)"', html)
    return m2.group(1) if m2 else None


def _parse_item_refs(block: str) -> list[dict]:
    items = []
    for m in re.finditer(r'"href":"/en/item/(\d+)/"', block):
        item_id = int(m.group(1))
        tail = block[m.end():m.end() + 800]
        name_m = re.search(r'"children":"([^"]+)"', tail)
        items.append({"id": item_id, "name": name_m.group(1) if name_m else None})
    return items


def _parse_section(html: str, section_key: str) -> str | None:
    marker = f'"section","{section_key}",{{'
    idx = html.find(marker)
    if idx == -1:
        return None
    obj_start = html.find("{", idx)
    return _extract_balanced(html, obj_start, "{", "}")


def parse_dungeon_page(raw_html: str) -> dict | None:
    html = _unescape(raw_html)
    if '"div","mainCategory",{' not in html:
        return None  # 404 or unrecognized page shape

    props = _parse_properties(html)
    name = _parse_name(html)
    rewards_section = _parse_section(html, "dungeonRewardsItems")

    return {
        "id": int(props.get("id")) if props.get("id") else None,
        "name": name,
        "mainCategory": props.get("mainCategory"),
        "description": props.get("description"),
        "dungeonType": props.get("dungeonType"),
        "recommendLevel": props.get("recommendLevel"),
        "usesDungeonUi": props.get("usesDungeonUi") == "yes",
        "isInstanceLayer": props.get("isInstanceLayer") == "yes",
        "mapId": props.get("mapId"),
        "createdAt": props.get("createdAt"),
        "updatedAt": props.get("updatedAt"),
        "rewardItems": _parse_item_refs(rewards_section) if rewards_section else [],
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
