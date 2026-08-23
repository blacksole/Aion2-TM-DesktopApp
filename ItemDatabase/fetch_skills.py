"""Fetches AION2 skill data (name, icon, class, description, specializations)
from gamers4.life's public skill database pages, caching locally.

Each skill detail page embeds a JSON blob (Next.js RSC payload) with the
real data — no dedicated JSON API was found, so this scrapes the rendered
HTML of each page listed in the site's own sitemap. Stdlib-only, no new
dependency, polite pacing between requests.

Usage:
    python fetch_skills.py
"""

import json
import time
import urllib.request
from pathlib import Path

SITEMAP_URL = "https://gamers4.life/aion-2/database/sitemaps/en-skill.xml"
SKILL_PAGE_URL = "https://gamers4.life/aion-2/database/en/skill/{id}/"
OUT_PATH = Path(__file__).parent / "data" / "skills_all.json"
REQUEST_DELAY = 0.35  # seconds between requests — be polite

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Aion2TM-SkillFetch/1.0)"}


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


def _extract_skill_json(html: str) -> dict | None:
    marker = '{\\"id\\":\\"'
    start = html.find(marker)
    if start == -1:
        return None
    depth = 0
    end = None
    for i in range(start, len(html)):
        ch = html[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return None
    raw = html[start:end]
    unescaped = raw.replace('\\"', '"').replace("\\\\", "\\")
    try:
        return json.loads(unescaped)
    except json.JSONDecodeError:
        return None


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
            html = _get(url)
            data = _extract_skill_json(html)
            if not data:
                errors.append(skill_id)
                continue
            entry = {
                "id": data.get("id"),
                "name": data.get("name", ""),
                "icon": _icon_filename(data.get("icon")),
                "mainCategory": data.get("mainCategory", ""),
                "subCategory": data.get("subCategory", ""),
                "type": data.get("type", ""),
                "damageType": data.get("damageType", ""),
                "isBasicSkill": data.get("isBasicSkill", False),
                "description": data.get("description", ""),
                "consumed": data.get("consumed") or {},
                "cooldown": data.get("cooldown"),
                "range": data.get("range") or {},
                "requiredWeapons": data.get("requiredWeapons") or [],
                "levels": [
                    {
                        "level": lvl.get("level"),
                        "minValue": lvl.get("minValue"),
                        "maxValue": lvl.get("maxValue"),
                    }
                    for lvl in (data.get("levels") or [])
                ],
                "specializations": [
                    {
                        "id": s.get("id"),
                        "name": s.get("name", ""),
                        "spec": s.get("spec", ""),
                        "description": s.get("description", ""),
                        "specialized": s.get("specialized", ""),
                        "parentSkillLvl": s.get("parentSkillLvl"),
                    }
                    for s in (data.get("specializations") or [])
                ],
            }
            results.append(entry)
        except Exception as e:
            errors.append(skill_id)
            print(f"  [{i}/{len(ids)}] FEHLER bei {skill_id}: {e}")
        else:
            print(f"  [{i}/{len(ids)}] {entry['mainCategory']:12s} {entry['name']}")
        time.sleep(REQUEST_DELAY)

    compute_icon_filenames(results)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({"skills": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nFertig: {len(results)} Skills gespeichert nach {OUT_PATH}")
    if errors:
        print(f"Fehlgeschlagen: {len(errors)} IDs: {errors}")


if __name__ == "__main__":
    main()
