"""Fetches the class-specific skill pool for each Arcana card type + grade
from questlog.gg's own character-builder API (a different site than
shugo.gg — a Nuxt/Vue SPA whose data comes from tRPC calls, found by
grepping its JS chunks for the `characterBuilder` procedures actually
used by the page).

Endpoint: https://questlog.gg/aion-2/api/trpc/characterBuilder.getItemSubStatSkills
Returns ~5000 entries total; the ones relevant here have a `group` like
"Arcana_Skill_Random_Grail_Unique_1" — CardType_Grade, no theme, since the
skill pool only depends on card type + grade, not which of the 7 themes
(confirmed: same pattern as shugo.gg's skillCategory, which is also only
cardType+grade-dependent). Each entry's `id` is a real skill id that
matches our own data/skills_all.json 1:1.

questlog.gg's card-type names differ from shugo.gg's for two of the six
"Lord card" types: Grail = our Chalice, Libra = our Scales. The other 4
"Stat card" types (Key/Hourglass/Dice/Lantern) don't appear at all here —
consistent with them granting stats, not skill levels.

Run after fetch_skills.py (needs data/skills_all.json for name lookup).

Usage:
    python fetch_arcana_class_skills.py
"""

import json
import urllib.request
from pathlib import Path

API_URL = "https://questlog.gg/aion-2/api/trpc/characterBuilder.getItemSubStatSkills"
SKILLS_PATH = Path(__file__).parent / "data" / "skills_all.json"
OUT_PATH = Path(__file__).parent / "data" / "arcana_class_skills.json"

# questlog.gg internal name -> our cardType name (see fetch_arcana_info.py)
CARD_TYPE_MAP = {
    "Grail": "Chalice",
    "Libra": "Scales",
    "Bell": "Bell",
    "Compass": "Compass",
    "Mirror": "Mirror",
    "Parchment": "Parchment",
}


def main():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    entries = data["result"]["data"]
    print(f"Fetched {len(entries)} total substat/skill entries from questlog.gg")

    skills = json.loads(SKILLS_PATH.read_text(encoding="utf-8"))["skills"]
    skills_by_id = {s["id"]: s for s in skills}

    # group -> "Arcana_Skill_Random_{QLCardType}_{Grade}_1"
    result: dict[str, dict[str, dict[str, list]]] = {}
    unresolved = 0
    for e in entries:
        group = e["group"]
        if not group.startswith("Arcana_Skill_Random_"):
            continue
        rest = group[len("Arcana_Skill_Random_"):]
        parts = rest.split("_")
        ql_card_type, grade = parts[0], parts[1]
        card_type = CARD_TYPE_MAP.get(ql_card_type)
        if not card_type:
            continue

        skill = skills_by_id.get(e["id"])
        if not skill:
            unresolved += 1
            continue

        result.setdefault(card_type, {}).setdefault(grade, {}).setdefault(e["class"], []).append({
            "id": e["id"],
            "name": skill["name"],
            "type": skill.get("type"),
            "levelBase": e["levelBaseValue"],
            "levelMax": e["levelMaxValue"],
        })

    print(f"Resolved into {sum(len(g) for g in result.values())} cardType/grade groups, {unresolved} unresolved skill ids")
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved to {OUT_PATH}")


if __name__ == "__main__":
    main()
