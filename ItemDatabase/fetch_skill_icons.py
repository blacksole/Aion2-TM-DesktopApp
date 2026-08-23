"""Downloads the skill icons referenced in data/skills_all.json from
questlog.gg's public asset mirror, converting WebP -> PNG (via Pillow), and
saves them under each skill's pre-computed 'iconFile' name (see
fetch_skills.py's compute_icon_filenames — icon_{class4}_{Skill}_{Type}_.png,
lengthened per-group whenever needed to avoid collisions). Several skills
share the exact same source image on questlog.gg (e.g. a cross-class
"Defiance") — the raw download is cached in memory so it's only fetched
once even when saved under multiple target names.

Run after fetch_skills.py, or again later if skills_all.json is refreshed.

Usage:
    python fetch_skill_icons.py
"""

import io
import json
import time
import urllib.request
from pathlib import Path

from PIL import Image

from fetch_skills import compute_icon_filenames

BASE_URL = "https://cdn.questlog.gg/aion-2/assets/Game/UI/Resource/Texture/Skill"
OUT_DIR = Path(__file__).parent / "assets" / "skill_icons"
SKILLS_PATH = Path(__file__).parent / "data" / "skills_all.json"
REQUEST_DELAY = 0.15


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(SKILLS_PATH.read_text(encoding="utf-8"))
    skills = data["skills"]

    if not all("iconFile" in s for s in skills):
        compute_icon_filenames(skills)
        SKILLS_PATH.write_text(json.dumps({"skills": skills}, ensure_ascii=False, indent=2), encoding="utf-8")

    targets = [s for s in skills if s.get("icon") and s.get("iconFile")]
    raw_cache: dict[str, bytes] = {}
    ok, failed = 0, []

    for i, s in enumerate(targets, 1):
        out_path = OUT_DIR / s["iconFile"]
        if out_path.exists():
            ok += 1
            continue

        raw_icon = s["icon"]
        try:
            if raw_icon not in raw_cache:
                url = f"{BASE_URL}/{raw_icon}.webp"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                raw_cache[raw_icon] = urllib.request.urlopen(req, timeout=20).read()
                time.sleep(REQUEST_DELAY)
            img = Image.open(io.BytesIO(raw_cache[raw_icon])).convert("RGBA")
            img.save(out_path, "PNG")
            ok += 1
            print(f"  [{i}/{len(targets)}] {raw_icon} -> {s['iconFile']}")
        except Exception as e:
            failed.append(s["iconFile"])
            print(f"  [{i}/{len(targets)}] FAILED {s['iconFile']} ({raw_icon}): {e}")

    print(f"\nDone: {ok} ok, {len(failed)} failed")
    if failed:
        print("Failed:", failed)


if __name__ == "__main__":
    main()
