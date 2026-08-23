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


def _unescape(html: str) -> str:
    """Properly unescapes the JS string literal each RSC chunk is embedded
    as (\\" -> ", \\n -> real newline, \\uXXXX -> the real character) --
    a naive \\"->\" replace (the original approach) leaves literal \\n
    sequences in place, which breaks the chunk-reference resolution below
    (real newlines are what separate "ID:VALUE" definitions within one
    push() call)."""
    out = []
    i = 0
    n = len(html)
    while i < n:
        ch = html[i]
        if ch == "\\" and i + 1 < n:
            nxt = html[i + 1]
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
                    out.append(chr(int(html[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
        out.append(ch)
        i += 1
    return "".join(out)


_CHUNK_DEF_RE = re.compile(r"(?m)^([0-9a-fA-F]+):")
_CHUNK_REF_RE = re.compile(r'"\$L([0-9a-fA-F]+)"')


def _collect_chunk_definitions(html: str) -> dict[str, str]:
    """Each self.__next_f.push([1,"...")]) call's content is one or more
    'ID:VALUE' definitions concatenated with real newlines (after
    _unescape) -- e.g. "1f:[...]\\n20:[...]\\n21:[...]". Splits every push
    call in the page into that flat id -> raw-value map."""
    chunks: dict[str, str] = {}
    for body in re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.DOTALL):
        text = _unescape(body)
        matches = list(_CHUNK_DEF_RE.finditer(text))
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunks[m.group(1)] = text[start:end].rstrip("\n")
    return chunks


def _resolve_refs(html: str) -> str:
    """Some fields (seen on recipes where the same label/value text repeats
    elsewhere on the page, e.g. Mastery Grade / subCategory) are streamed as
    a "$Lxx" back-reference to a chunk defined elsewhere on the same page,
    instead of being inlined directly -- the naive parser silently returned
    None for those. Substitutes every "$Lxx" token with that chunk's own
    raw content so the existing field-extraction regexes see real text
    either way. A few passes handle a reference pointing to another
    reference."""
    chunks = _collect_chunk_definitions(html)
    for _ in range(4):
        new_html = _CHUNK_REF_RE.sub(lambda m: chunks.get(m.group(1), '""'), html)
        if new_html == html:
            break
        html = new_html
    return html


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


def _parse_grade_badge(html: str) -> str | None:
    m = re.search(r'"background":"#[0-9a-fA-F]{6,8}","color":"#[0-9a-fA-F]{6,8}"\},"children":"([^"]+)"', html)
    return m.group(1) if m else None


def _parse_item_refs(block: str) -> list[dict]:
    items = []
    for m in re.finditer(r'"href":"/en/item/(\d+)/"', block):
        item_id = int(m.group(1))
        tail = block[m.end():m.end() + 800]
        name_m = re.search(r'"children":"([^"]+)"', tail)
        qty_m = re.search(r'"children":\["[×xX]","([\d,]+)"\]', tail)
        name = name_m.group(1) if name_m else None
        qty = int(qty_m.group(1).replace(",", "")) if qty_m else 1
        items.append({"id": item_id, "name": name, "qty": qty})
    return items


def _parse_section(html: str, section_key: str) -> str | None:
    marker = f'"section","{section_key}",{{'
    idx = html.find(marker)
    if idx == -1:
        return None
    obj_start = html.find("{", idx)
    return _extract_balanced(html, obj_start, "{", "}")


def parse_recipe_page(raw_html: str) -> dict | None:
    html = _unescape(raw_html)
    if '"div","mainCategory",{' not in html:
        return None  # 404 or unrecognized page shape
    html = _resolve_refs(html)

    props = _parse_properties(html)
    grade_badge = _parse_grade_badge(html)
    input_section = _parse_section(html, "recipeInputItems")
    output_section = _parse_section(html, "recipeOutputItems")

    return {
        "id": int(props.get("id")) if props.get("id") else None,
        "grade": grade_badge,
        "masteryGradeNumeric": int(props["grade"]) if props.get("grade", "").isdigit() else None,
        "mainCategory": props.get("mainCategory"),
        "subCategory": props.get("subCategory"),
        "qualificationRace": props.get("qualificationRace"),
        "subTab": props.get("subTab"),
        "masteryGrade": props.get("masteryGrade"),
        "masteryLevel": int(props["masteryLevel"]) if props.get("masteryLevel", "").isdigit() else None,
        "goldCost": props.get("goldCost"),
        "remoteGoldCost": props.get("remoteGoldCost"),
        "craftingFeeType": props.get("craftingFeeType"),
        "craftGauge": props.get("craftGauge"),
        "learnType": props.get("learnType"),
        "isGuildCraft": props.get("isGuildCraft") == "yes",
        "createdAt": props.get("createdAt"),
        "updatedAt": props.get("updatedAt"),
        "inputs": _parse_item_refs(input_section) if input_section else [],
        "outputs": _parse_item_refs(output_section) if output_section else [],
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
