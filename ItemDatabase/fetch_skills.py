"""Fetches AION2 skill data (name, icon, class, description, specializations)
from gamers4.life's public skill database pages, caching locally.

Each skill detail page embeds a JSON blob (Next.js RSC payload) with the
real data — no dedicated JSON API was found, so this scrapes the rendered
HTML of each page listed in the site's own sitemap. Stdlib-only, no new
dependency, polite pacing between requests.

Usage:
    python fetch_skills.py
"""

import html
import json
import re
import time
import urllib.request
from pathlib import Path

SITEMAP_URL = "https://gamers4.life/aion-2/database/sitemaps/en-skill.xml"
SKILL_PAGE_URL = "https://gamers4.life/aion-2/database/en/skill/{id}/"
OUT_PATH = Path(__file__).parent / "data" / "skills_all.json"
REQUEST_DELAY = 0.35  # seconds between requests — be polite

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Aion2TM-SkillFetch/1.0)"}

_KV_RE = re.compile(r'<div class="k">([^<]*)</div><div class="v">([^<]*)</div>')
_H1_TITLE_RE = re.compile(r'<h1 class="title">([^<]*)</h1>')
_ID_PILL_RE = re.compile(r'<span class="pill id">ID (\d+)</span>')
_ICON_SRC_RE = re.compile(r'<div class="icon"><img src="([^"]*)"')
_SECTION_PRE_RE = {
    key: re.compile(
        r'<summary>' + re.escape(key) + r'</summary><pre>(.*?)</pre></details>',
        re.S,
    )
    for key in ("levels", "specializations", "range", "requiredWeapons", "consumed")
}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _skill_ids_from_sitemap() -> list[str]:
    xml = _get(SITEMAP_URL)
    ids = []
    for line in xml.splitlines():
        line = line.strip()
        if "<loc>" in line and "/skill/" in line:
            url = line.split("<loc>")[1].split("</loc>")[0]
            skill_id = url.rstrip("/").split("/")[-1]
            ids.append(skill_id)
    return ids


def _parse_record_fields(raw_html: str) -> dict:
    """The "Record fields" <div class="table"> block: a flat run of
    <div class="k">key</div><div class="v">value</div> pairs, HTML-escaped,
    "—" meaning None."""
    fields = {}
    for key, value in _KV_RE.findall(raw_html):
        value = html.unescape(value)
        fields[html.unescape(key)] = None if value == "—" else value
    return fields


def _section_json(raw_html: str, key: str):
    match = _SECTION_PRE_RE[key].search(raw_html)
    if not match:
        return None
    try:
        return json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError:
        return None


def parse_skill_page(raw_html: str, skill_id: str) -> dict | None:
    """Parses a gamers4.life skill detail page (current plain-HTML shape,
    see fetch_dungeons.py's parse_dungeon_page() docstring for the sibling
    fix on the same 2026-10-01 site redesign). Returns None only if even
    the title is missing (page genuinely has no skill, e.g. a stale
    sitemap entry) -- every other field degrades to a sensible default so
    one odd skill doesn't abort the whole run."""
    name_match = _H1_TITLE_RE.search(raw_html)
    if not name_match:
        return None
    id_match = _ID_PILL_RE.search(raw_html)
    icon_match = _ICON_SRC_RE.search(raw_html)
    fields = _parse_record_fields(raw_html)

    levels = [
        {
            "level": lvl.get("level"),
            "minValue": lvl.get("minValue"),
            "maxValue": lvl.get("maxValue"),
        }
        for lvl in (_section_json(raw_html, "levels") or [])
    ]
    specializations = [
        {
            "id": s.get("id"),
            "name": s.get("name", ""),
            "spec": s.get("spec", ""),
            "description": s.get("description", ""),
            "specialized": s.get("specialized", ""),
            "parentSkillLvl": s.get("parentSkillLvl"),
        }
        for s in (_section_json(raw_html, "specializations") or [])
    ]

    return {
        "id": int(id_match.group(1)) if id_match else int(skill_id),
        "name": html.unescape(name_match.group(1)),
        "icon": _icon_filename(icon_match.group(1) if icon_match else None),
        "mainCategory": fields.get("mainCategory", "") or "",
        "subCategory": fields.get("subCategory", "") or "",
        "type": fields.get("type", "") or "",
        "damageType": fields.get("damageType", "") or "",
        "isBasicSkill": fields.get("isBasicSkill") == "true",
        "description": _skill_description(raw_html),
        "consumed": _section_json(raw_html, "consumed") or {},
        "cooldown": _int_or_none(fields.get("cooldown")),
        "range": _section_json(raw_html, "range") or {},
        "requiredWeapons": _section_json(raw_html, "requiredWeapons") or [],
        "levels": levels,
        "specializations": specializations,
    }


_DESC_RE = re.compile(r'<p class="desc">(.*?)</p>', re.S)


def _skill_description(raw_html: str) -> str:
    match = _DESC_RE.search(raw_html)
    return html.unescape(match.group(1)).strip() if match else ""


def _int_or_none(value):
    return int(value) if value and value.lstrip("-").isdigit() else None


def _icon_filename(icon_field: str | None) -> str:
    if not icon_field:
        return ""
    last = icon_field.rstrip("/").split("/")[-1]
    return last.split(".")[0]


def _alnum(text: str) -> str:
    return "".join(c for c in text if c.isalnum())


def _common_prefix_len(strings: list[str]) -> int:
    if not strings:
        return 0
    shortest = min(len(s) for s in strings)
    for i in range(shortest):
        ch = strings[0][i]
        if any(s[i] != ch for s in strings):
            return i
    return shortest


def compute_icon_filenames(skills: list[dict]) -> None:
    """Assigns each skill an 'iconFile' name: icon_{class4}_{Skill}_{Type}_.png
    (first 4 letters of the class, capitalized type). The skill-name portion
    is normally the first 8 alnum letters, but for any group that collides
    at that length (same class+type+name8), it's extended just enough that
    every member's truncated name differs from every other member's by at
    least 3 trailing characters (never shorter than 8)."""
    groups: dict[tuple, list[dict]] = {}
    for s in skills:
        cls = (s.get("mainCategory") or "none")[:4]
        typ = (s.get("type") or "unknown").capitalize()
        key = (cls, typ, _alnum(s.get("name", ""))[:8])
        groups.setdefault(key, []).append(s)

    for (cls, typ, _name8), group in groups.items():
        if len(group) == 1:
            length = 8
        else:
            names = [_alnum(s.get("name", "")) for s in group]
            length = max(8, _common_prefix_len(names) + 3)
        for s in group:
            name_part = _alnum(s.get("name", ""))[:length]
            s["iconFile"] = f"icon_{cls}_{name_part}_{typ}_.png"


def main():
    print("Lade Skill-Sitemap...")
    ids = _skill_ids_from_sitemap()
    print(f"  {len(ids)} Skill-IDs gefunden")

    results = []
    errors = []
    for i, skill_id in enumerate(ids, 1):
        url = SKILL_PAGE_URL.format(id=skill_id)
        try:
            raw_html = _get(url)
            entry = parse_skill_page(raw_html, skill_id)
            if not entry:
                errors.append(skill_id)
                continue
            results.append(entry)
        except Exception as e:
            errors.append(skill_id)
            print(f"  [{i}/{len(ids)}] FEHLER bei {skill_id}: {e}")
        else:
            print(f"  [{i}/{len(ids)}] {entry['mainCategory']:12s} {entry['name']}")
        time.sleep(REQUEST_DELAY)

    # The site's own "type" field is unreliable for Stigma skills (it comes
    # back as "active" for many of them), while "subCategory" consistently
    # says "stigma" -- trust subCategory here so icon filenames/app logic
    # that key off "type" don't silently mislabel Stigma skills as Active.
    for entry in results:
        if entry.get("subCategory") == "stigma":
            entry["type"] = "stigma"

    compute_icon_filenames(results)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({"skills": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nFertig: {len(results)} Skills gespeichert nach {OUT_PATH}")
    if errors:
        print(f"Fehlgeschlagen: {len(errors)} IDs: {errors}")


if __name__ == "__main__":
    main()
