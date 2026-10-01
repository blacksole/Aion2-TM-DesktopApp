"""Fetches AION 2 crafting recipe data (profession, mastery level, gold cost,
input materials, output item) from gamers4.life's public recipe database
pages, caching locally.

Same technique as fetch_skills.py: no dedicated JSON API was found for
recipes, so this scrapes the server-rendered Next.js RSC HTML of each page
listed in the site's own sitemap. Every quote in that RSC stream is
backslash-escaped (the whole chunk is itself a JS string literal) -- that's
normalized once up front so the rest of the parsing can use plain-looking
patterns.

Usage:
    python fetch_recipes.py [--limit N]
"""

import argparse
import html
import json
import re
import time
import urllib.request
from pathlib import Path

SITEMAP_URL = "https://gamers4.life/aion-2/database/sitemaps/en-recipe.xml"
RECIPE_PAGE_URL = "https://gamers4.life/aion-2/database/en/recipe/{id}/"
OUT_PATH = Path(__file__).parent / "data" / "recipes_all.json"
REQUEST_DELAY = 0.35  # seconds between requests -- be polite

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Aion2TM-RecipeFetch/1.0)"}

PROP_KEYS = [
    "id", "grade", "mainCategory", "subCategory", "qualificationRace", "subTab",
    "masteryGrade", "masteryLevel", "goldCost", "remoteGoldCost", "craftingFeeType",
    "craftGauge", "learnType", "isGuildCraft", "createdAt", "updatedAt",
]


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _recipe_ids_from_sitemap() -> list[str]:
    xml = _get(SITEMAP_URL)
    ids = []
    for line in xml.splitlines():
        line = line.strip()
        if "<loc>" in line and "/recipe/" in line:
            url = line.split("<loc>")[1].split("</loc>")[0]
            recipe_id = url.rstrip("/").split("/")[-1]
            ids.append(recipe_id)
    return ids


def _unescape(html_str: str) -> str:
    """No longer used by parse_recipe_page() (CI failure, 2026-10-01:
    gamers4.life switched this page from the backslash-escaped Next.js RSC
    stream this function used to decode to plain server-rendered HTML --
    see parse_recipe_page()'s docstring). Kept as a tiny public helper in
    case a future scrape of this same site needs it again."""
    out = []
    i = 0
    n = len(html_str)
    while i < n:
        ch = html_str[i]
        if ch == "\\" and i + 1 < n:
            nxt = html_str[i + 1]
            if nxt == '"':
                out.append('"'); i += 2; continue
            if nxt == "\\":
                out.append("\\"); i += 2; continue
            if nxt == "n":
                out.append("\n"); i += 2; continue
            if nxt == "t":
                out.append("\t"); i += 2; continue
            if nxt == "/":
                out.append("/"); i += 2; continue
            if nxt == "u" and i + 5 < n:
                try:
                    out.append(chr(int(html_str[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
        out.append(ch)
        i += 1
    return "".join(out)


_KV_RE = re.compile(r'<div class="k">([^<]*)</div><div class="v">([^<]*)</div>')
_H1_TITLE_RE = re.compile(r'<h1 class="title">([^<]*)</h1>')
_GRADE_PILL_RE = re.compile(r'<span class="pill">Grade (\d+)</span>')
_ID_PILL_RE = re.compile(r'<span class="pill id">ID (\d+)</span>')
# Both JSON blobs the page embeds verbatim inside <details><summary>KEY
# </summary><pre>...</pre></details> blocks, HTML-escaped (&quot; etc.).
_SECTION_PRE_RE = {
    "recipeInputItems": re.compile(
        r'<summary>recipeInputItems</summary><pre>(.*?)</pre>', re.DOTALL
    ),
    "recipeOutputItems": re.compile(
        r'<summary>recipeOutputItems</summary><pre>(.*?)</pre>', re.DOTALL
    ),
}


def _parse_record_fields(html_str: str) -> dict:
    """The "Record fields" card is a flat sequence of <div class="k">KEY</div>
    <div class="v">VALUE</div> pairs -- a key with no real value renders as
    the literal em-dash "—"."""
    result = {}
    for key, value in _KV_RE.findall(html_str):
        result[key] = None if value == "—" else value
    return result


def _parse_item_refs(raw_json: str) -> list[dict]:
    """recipeInputItems is a JSON array of item dicts; quantity -> qty to
    match this file's existing on-disk field name."""
    try:
        items = json.loads(raw_json)
    except json.JSONDecodeError:
        return []
    return [
        {"id": int(it["id"]), "name": it.get("name"), "qty": int(it.get("quantity") or 1)}
        for it in items
        if "id" in it
    ]


def _parse_output_refs(raw_json: str) -> list[dict]:
    """recipeOutputItems is a JSON OBJECT (not an array, unlike inputs):
    {"productItem": {...} | null, "comboProbability": ..., "comboProductItem": {...} | null}
    -- both productItem and a possible combo-craft alternate output."""
    try:
        obj = json.loads(raw_json)
    except json.JSONDecodeError:
        return []
    outputs = []
    for key in ("productItem", "comboProductItem"):
        item = obj.get(key)
        if isinstance(item, dict) and "id" in item:
            outputs.append({
                "id": int(item["id"]),
                "name": item.get("name"),
                "qty": int(item.get("quantity") or 1),
            })
    return outputs


def parse_recipe_page(raw_html: str) -> dict | None:
    """gamers4.life switched its recipe detail pages from a server-rendered
    Next.js RSC data stream (the old backslash-escaped `"div","mainCategory",
    {...}` shape this function used to decode) to plain server-rendered HTML
    with a key/value `.table` card plus two JSON blobs for recipe
    inputs/outputs (CI failure, 2026-10-01: 0/2442 recipes fetched, the old
    marker string no longer exists anywhere on the page at all).
    """
    if '<h1 class="title">' not in raw_html or 'class="k">mainCategory</div>' not in raw_html:
        return None  # 404 or unrecognized page shape

    name_match = _H1_TITLE_RE.search(raw_html)
    grade_match = _GRADE_PILL_RE.search(raw_html)
    id_match = _ID_PILL_RE.search(raw_html)
    fields = _parse_record_fields(raw_html)

    def _section_json(key: str) -> str | None:
        m = _SECTION_PRE_RE[key].search(raw_html)
        return html.unescape(m.group(1)) if m else None

    input_json = _section_json("recipeInputItems")
    output_json = _section_json("recipeOutputItems")

    def _int_or_none(value):
        return int(value) if value and value.isdigit() else None

    return {
        "id": int(id_match.group(1)) if id_match else _int_or_none(fields.get("id")),
        "grade": grade_match.group(1) if grade_match else fields.get("grade"),
        "masteryGradeNumeric": _int_or_none(fields.get("grade")),
        "mainCategory": fields.get("mainCategory"),
        "subCategory": fields.get("subCategory"),
        "qualificationRace": fields.get("qualificationRace"),
        "subTab": fields.get("subTab"),
        "masteryGrade": fields.get("masteryGrade"),
        "masteryLevel": _int_or_none(fields.get("masteryLevel")),
        "goldCost": fields.get("goldCost"),
        "remoteGoldCost": fields.get("remoteGoldCost"),
        "craftingFeeType": fields.get("craftingFeeType"),
        "craftGauge": fields.get("craftGauge"),
        "learnType": fields.get("learnType"),
        "isGuildCraft": fields.get("isGuildCraft") == "true",
        "createdAt": fields.get("createdAt"),
        "updatedAt": fields.get("updatedAt"),
        "name": name_match.group(1) if name_match else None,
        "inputs": _parse_item_refs(input_json) if input_json else [],
        "outputs": _parse_output_refs(output_json) if output_json else [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only fetch the first N recipes (testing)")
    args = parser.parse_args()

    print("Lade Recipe-Sitemap...")
    ids = _recipe_ids_from_sitemap()
    print(f"{len(ids)} Recipe-IDs gefunden.")
    if args.limit:
        ids = ids[:args.limit]

    recipes = []
    failed = []
    for i, recipe_id in enumerate(ids, 1):
        url = RECIPE_PAGE_URL.format(id=recipe_id)
        try:
            raw = _get(url)
            parsed = parse_recipe_page(raw)
            if parsed:
                recipes.append(parsed)
            else:
                failed.append(recipe_id)
        except Exception as e:
            print(f"  Fehler bei {recipe_id}: {e}")
            failed.append(recipe_id)

        if i % 50 == 0 or i == len(ids):
            print(f"  {i}/{len(ids)} verarbeitet ({len(recipes)} ok, {len(failed)} fehlgeschlagen)")

        time.sleep(REQUEST_DELAY)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({"recipes": recipes, "failed": failed}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fertig: {len(recipes)} Rezepte gespeichert nach {OUT_PATH} ({len(failed)} fehlgeschlagen)")


if __name__ == "__main__":
    main()
