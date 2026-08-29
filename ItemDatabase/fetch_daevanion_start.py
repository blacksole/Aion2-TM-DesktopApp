"""Fetches the Daevanion Board "_s" (Start) variant -- the smaller content
Global actually has right now, before the Eltnen/Morheim update KR/TW
already received (see fetch_daevanion_advanced.py for that larger "_a"
variant). Source: talentbuilds.com's own Daevanion Planner page embeds the
full board dataset as a UTF-16-encoded JS file (`const boardsData = [...]`)
at daevanionplanner/boards_embedded.js -- no API needed, just decode + eval
as JSON.

48 boards (6 deities: Nezekan/Zikel/Vaizel/Triniel/Ariel/Azphel -- Marchutan
and Yustiel don't exist yet in this dataset -- x 8 classes, no Fighter),
still a 225-node/15x15 grid per board (grid size never changed, only which
cells carry a real stat/skill value did -- verified 2026-08-28 against
fetch_daevanion_advanced.py's output: ~150 of 225 cells differ per board for
the 4 affected deities, Ariel/Azphel are byte-identical between variants).

Talentbuilds' raw effect data is richer than questlog.gg's: skill nodes
carry skill_name/skill_description directly (no skill_id lookup against
skills_all.json needed), stat nodes carry a human-readable stat name
directly (not a lowercase code). Kept as close to the raw shape as
practical in the output so the app-side loader (app.py's daevanion loading,
once built) can special-case as little as possible.

Usage:
    python fetch_daevanion_start.py
"""

import json
import re
import urllib.request
from pathlib import Path

URL = "https://talentbuilds.com/aion2/daevanionplanner/boards_embedded.js"
OUTPUT_PATH = Path(__file__).parent / "data" / "daevanion_boards_s.json"

CLASS_MAP = {
    "Assassin": "assassin", "Chanter": "chanter", "Cleric": "cleric",
    "Elementalist": "elementalist", "Gladiator": "gladiator", "Ranger": "ranger",
    "Sorcerer": "sorcerer", "Templar": "templar",
}
GRADE_MAP = {"None": "empty", "Common": "common", "Rare": "rare", "Legend": "legend", "Unique": "unique"}


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    text = raw.decode("utf-16")
    match = re.search(r"const boardsData\s*=\s*(\[.*\]);?\s*$", text, re.S)
    if not match:
        raise RuntimeError("boardsData array not found in boards_embedded.js -- site format may have changed")
    boards_raw = json.loads(match.group(1))
    print(f"Fetched {len(boards_raw)} boards from talentbuilds.com")

    out_boards = []
    out_nodes = []
    for b in boards_raw:
        board_id = str(b["id"])
        out_boards.append({"id": board_id, "name": b["title"], "classId": CLASS_MAP[b["class"]], "order": b["order"]})
        for n in b["nodes"]:
            effect = n.get("effect") or {}
            kind = effect.get("kind")
            eff_out = []
            grade = "start" if n["type"] == "Start" else GRADE_MAP.get(n["grade"], "common")
            if kind == "Stat":
                eff_out.append({"t": "s", "n": effect["stat"], "v": effect["amount"]})
            elif kind == "SkillLevel":
                eff_out.append({
                    "t": "k", "n": effect.get("skill_name"), "v": effect.get("levels"),
                    "skill_id": effect.get("skill_id"), "desc": effect.get("skill_description"),
                })
            out_nodes.append({
                "id": str(n["id"]), "b": board_id, "r": n["row"], "c": n["col"], "name": n.get("title", ""),
                "g": grade, "lvl": n["required_level"], "cost": n["cost_points"],
                "refund_gold": n.get("refund_gold", 0), "e": eff_out,
            })

    OUTPUT_PATH.write_text(
        json.dumps({"boards": out_boards, "nodes": out_nodes}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"{len(out_boards)} boards, {len(out_nodes)} nodes -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
