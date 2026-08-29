"""Fetches the Daevanion Board "_a" (Advanced) variant -- KR/TW's current,
post-Eltnen/Morheim content (see fetch_daevanion_start.py for the smaller
"_s" variant Global actually has right now). Source: questlog.gg's own
character-builder tRPC API, same convention as fetch_arcana_class_skills.py
(a different site, its own procedures -- found the same way, by grepping
its JS chunks for the tRPC router calls the Daevanion Planner page itself
makes).

Endpoints (plain JSON GET, NOT superjson-wrapped -- confirmed 2026-08-28,
`?input={"language":"en"}` works directly, wrapping in `{"json":...}`
does not):
    https://questlog.gg/aion-2/api/trpc/daevanionPlanner.getDaevanionBoards
    https://questlog.gg/aion-2/api/trpc/daevanionPlanner.getDaevanionNodes

72 boards (8 deities: Nezekan/Zikel/Vaizel/Triniel/Ariel/Azphel/Marchutan/
Yustiel x 9 classes, including Fighter) x 225 nodes (15x15 grid, start
always at row/col 8/8). Kept close to the raw shape -- skill nodes only
carry skill_id (questlog doesn't expose skill_name/description directly,
unlike talentbuilds.com), resolved against skills_all.json at app runtime
via the SAME _skills_by_class lookup the rest of the app already uses (not
baked in here) -- Fighter has zero entries in skills_all.json currently (a
real, pre-existing gap independent of Daevanion, see
[[project_daevanion_board_port]]), so Fighter's skill-level nodes won't
resolve a real name/type until that's fixed.

Usage:
    python fetch_daevanion_advanced.py
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = "https://questlog.gg/aion-2/api/trpc/daevanionPlanner"
OUTPUT_PATH = Path(__file__).parent / "data" / "daevanion_boards_a.json"

GRADE_MAP = {0: "start", 11: "common", 21: "rare", 31: "legend", 41: "unique"}


def _fetch(procedure: str, payload: dict) -> dict:
    query = urllib.parse.urlencode({"input": json.dumps(payload)})
    url = f"{API_BASE}.{procedure}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    boards_raw = _fetch("getDaevanionBoards", {"language": "en"})["result"]["data"]
    nodes_raw = _fetch("getDaevanionNodes", {"language": "en"})["result"]["data"]
    print(f"Fetched {len(boards_raw)} boards, {len(nodes_raw)} nodes from questlog.gg")

    out_boards = [{"id": b["id"], "name": b["name"], "classId": b["classId"], "order": b["order"]} for b in boards_raw]

    out_nodes = []
    for n in nodes_raw:
        effect = n.get("effect") or []
        eff_out = []
        for e in effect:
            if e.get("type") == "stat":
                eff_out.append({"t": "s", "n": e.get("stat_name"), "v": e.get("stat_value")})
            elif e.get("type") == "skill_level":
                eff_out.append({"t": "k", "skill_id": e.get("skill_id"), "v": e.get("level_increase")})
        grade = "start" if n.get("mainCategory") == "start" else GRADE_MAP.get(n.get("grade"), "common")
        out_nodes.append({
            "id": str(n["id"]), "b": n["boardId"], "r": n["row"], "c": n["col"], "name": n.get("name", ""),
            "g": grade, "lvl": n.get("needLevel"), "cost": n.get("costDaevanionPoint") or 0,
            "refund_gold": n.get("resetGold", 0), "e": eff_out,
        })

    OUTPUT_PATH.write_text(
        json.dumps({"boards": out_boards, "nodes": out_nodes}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"{len(out_boards)} boards, {len(out_nodes)} nodes -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
