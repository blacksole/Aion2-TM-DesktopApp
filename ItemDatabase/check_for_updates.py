"""Weekly maintenance script (User-Wunsch, 2026-08-27): re-runs every data
fetch script, regenerates the derived compute_*.py outputs, and prints/logs
a summary of what actually changed (via `git diff --stat`) so the recent
skill-rebalance-patch class of problem (our skills_all.json going stale
after a live game patch, e.g. the 2026-08-25/26 "Great Rebalance") gets
caught automatically instead of only when someone happens to notice.

Deliberately does NOT git-commit/push anything itself -- a data refresh can
occasionally pick up a scraping quirk (a page that half-rendered, a site
layout change breaking a parser), so a human should look at `git diff`
before it ships. This script's job ends at "here's what changed, review
data/*.json/details/ before committing."

Run by hand:
    python check_for_updates.py

Or on a schedule -- see setup_weekly_check.bat in this same folder for a
Windows Task Scheduler entry that runs this every Wednesday.
"""

import datetime
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent
LOG_PATH = BASE / "data" / "check_for_updates.log"

# Run in this order -- items/skills/recipes/dungeons/arcana are independent
# fetches, but the compute_*.py scripts at the end READ items_all.json's
# fresh output, so they must run after it.
FETCH_SCRIPTS = [
    "fetch_items.py",
    "fetch_item_details.py",
    "fetch_skills.py",
    "fetch_skill_icons.py",
    "fetch_recipes.py",
    "fetch_dungeons.py",
    "fetch_arcana_info.py",
    "fetch_arcana_class_skills.py",
]
COMPUTE_SCRIPTS = [
    "compute_dungeon_sets.py",
    "compute_stat_priority_options.py",
]


def _run(script: str, log_lines: list[str]) -> bool:
    print(f"\n=== {script} ===")
    log_lines.append(f"\n=== {script} ===")
    result = subprocess.run(
        [sys.executable, script], cwd=BASE, capture_output=True, text=True,
    )
    print(result.stdout)
    log_lines.append(result.stdout)
    if result.returncode != 0:
        print(f"!! {script} FAILED (exit {result.returncode}):\n{result.stderr}")
        log_lines.append(f"!! FAILED (exit {result.returncode}):\n{result.stderr}")
        return False
    return True


def _git_diff_stat() -> str:
    # Git repo root is cont_ToDo_app (BASE.parent), not the outer mono-repo
    # folder -- confirmed by running `git` commands from there directly.
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", "--", "ItemDatabase/data"],
            cwd=BASE.parent, capture_output=True, text=True,
        )
        return result.stdout.strip() or "(no changes)"
    except FileNotFoundError:
        return "(git not available -- can't show a diff summary)"


def main():
    started = datetime.datetime.now()
    log_lines = [f"check_for_updates.py run started {started.isoformat()}"]

    failed = []
    for script in FETCH_SCRIPTS:
        if not _run(script, log_lines):
            failed.append(script)
    for script in COMPUTE_SCRIPTS:
        if not _run(script, log_lines):
            failed.append(script)

    diff_summary = _git_diff_stat()
    print("\n=== Changed data files (git diff --stat) ===")
    print(diff_summary)
    log_lines.append("\n=== Changed data files (git diff --stat) ===")
    log_lines.append(diff_summary)

    if failed:
        print(f"\n{len(failed)} script(s) failed: {', '.join(failed)} -- check output above before trusting this run.")
        log_lines.append(f"\n{len(failed)} script(s) failed: {', '.join(failed)}")
    elif diff_summary == "(no changes)":
        print("\nNo data changes this run.")
    else:
        print("\nData changed -- review the diff above (or `git diff` directly), then commit by hand if it looks right.")

    LOG_PATH.write_text("\n".join(log_lines), encoding="utf-8")
    print(f"\nFull log written to {LOG_PATH}")


if __name__ == "__main__":
    main()
