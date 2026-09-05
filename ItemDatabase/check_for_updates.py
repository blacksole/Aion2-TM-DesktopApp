"""Weekly maintenance script (User-Wunsch, 2026-08-27): re-runs every data
fetch script, regenerates the derived compute_*.py outputs, and prints/logs
a summary of what actually changed so the recent skill-rebalance-patch
class of problem (our skills_all.json going stale after a live game patch,
e.g. the 2026-08-25/26 "Great Rebalance") gets caught automatically
instead of only when someone happens to notice.

Deliberately does NOT git-commit/push anything itself -- a data refresh can
occasionally pick up a scraping quirk (a page that half-rendered, a site
layout change breaking a parser), so a human should look at the diff below
before committing. This script's job ends at "here's exactly what changed,
review it before committing."

The diff itself is a real semantic comparison of the OLD vs NEW parsed JSON
for every data/*.json file (User-Wunsch, 2026-09-05: "prüfen, ob die Daten
bei der API sich geändert haben, wie diese sich geändert haben") -- NOT
`git diff`, since these files are stored as single-line compact JSON (see
the fetch scripts' own convention notes), where a line-based diff would
just show "the whole line changed" with zero readable detail. Lists of
objects are paired by their own "id" field (so reordering/insertion/
removal doesn't look like every entry changed), then every changed leaf
value is reported as "[Name].field: old -> new".

Run by hand:
    python check_for_updates.py
    python check_for_updates.py --if-due   # only runs if a Wednesday has
                                            # passed since the last run;
                                            # otherwise prints a one-line
                                            # "not due yet" and exits --
                                            # used by the VS Code task
                                            # below so opening the project
                                            # doesn't refetch every single
                                            # time, just once per week.

Or on a schedule -- see setup_weekly_check.bat in this same folder for a
Windows Task Scheduler entry that runs this every Wednesday (needs the PC
on and awake at that exact time, which is why the VS Code task above
exists as a catch-up path for whenever the project is actually opened).
"""

import datetime
import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
LOG_PATH = DATA_DIR / "check_for_updates.log"

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


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _snapshot_data_dir() -> dict[str, object]:
    return {f.name: _load_json(f) for f in DATA_DIR.glob("*.json") if f.name != "check_for_updates.log"}


def _index_by_id(items: list):
    """Pairs a list of dicts by their own "id" field across a re-fetch, so
    reordering/insertion/removal doesn't make every entry look changed --
    only real field-level differences within a matched pair do. Returns
    None if this list isn't "a list of dicts with an id" (falls back to a
    plain value-equality diff for those)."""
    if items and all(isinstance(x, dict) and "id" in x for x in items):
        return {str(x["id"]): x for x in items}
    return None


def _diff_values(old, new, path: str, out: list[str], max_items: int = 300):
    if len(out) >= max_items:
        return
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(set(old) | set(new)):
            sub_path = f"{path}.{key}" if path else key
            _diff_values(old.get(key), new.get(key), sub_path, out, max_items)
    elif isinstance(old, list) and isinstance(new, list):
        old_idx, new_idx = _index_by_id(old), _index_by_id(new)
        if old_idx is not None and new_idx is not None:
            for key in sorted(set(old_idx) | set(new_idx)):
                entry = new_idx.get(key) or old_idx.get(key)
                label = entry.get("name") or entry.get("title") if isinstance(entry, dict) else None
                _diff_values(old_idx.get(key), new_idx.get(key), f"{path}[{label or key}]", out, max_items)
        elif old != new:
            out.append(f"{path}: {old!r} -> {new!r}")
    elif old != new:
        out.append(f"{path}: {old!r} -> {new!r}")


def _diff_data_dir(before: dict, after: dict) -> dict[str, list[str]]:
    """{filename: [readable change lines]} for every data file whose
    parsed content actually differs -- see the module docstring for why
    this replaces the earlier `git diff --stat` approach entirely."""
    changes: dict[str, list[str]] = {}
    for name in sorted(set(before) | set(after)):
        old, new = before.get(name), after.get(name)
        if old == new:
            continue
        lines: list[str] = []
        _diff_values(old, new, "", lines)
        changes[name] = lines or ["(changed, but no readable leaf-level diff -- structure changed too much to pair up)"]
    return changes


def _most_recent_wednesday_at(dt: datetime.datetime, hour: int = 9) -> datetime.datetime:
    """The most recent point in time that was a Wednesday at `hour`:00, at
    or before `dt` -- e.g. called with "now", this is this week's
    Wednesday check-in time if it's already passed, otherwise last week's."""
    days_since_wed = (dt.weekday() - 2) % 7  # Wednesday = weekday() 2 (Monday=0)
    wed = (dt - datetime.timedelta(days=days_since_wed)).replace(hour=hour, minute=0, second=0, microsecond=0)
    if wed > dt:
        wed -= datetime.timedelta(days=7)
    return wed


def _last_run_time() -> datetime.datetime | None:
    if not LOG_PATH.exists():
        return None
    first_line = LOG_PATH.read_text(encoding="utf-8").splitlines()[:1]
    if not first_line:
        return None
    try:
        return datetime.datetime.fromisoformat(first_line[0].split("run started ", 1)[1])
    except (IndexError, ValueError):
        return None


def _is_due() -> bool:
    """User-Wunsch, 2026-09-05: "automatisch ... ausführen, wenn ich nach
    einem Di/Mi VSC öffne" -- the Windows Scheduled Task only fires if the
    PC happens to be on at that exact Wednesday 09:00 moment; this is the
    catch-up path a VS Code task (see .vscode/tasks.json) calls on every
    project open with --if-due, so missing that moment just means it
    catches up the next time the project is opened instead of silently
    staying stale for a week."""
    last_run = _last_run_time()
    return last_run is None or last_run < _most_recent_wednesday_at(datetime.datetime.now())


def main():
    if "--if-due" in sys.argv and not _is_due():
        last_run = _last_run_time()
        print(f"check_for_updates.py: not due yet (last checked {last_run.isoformat() if last_run else 'never'}, next check due after this week's Wednesday).")
        return

    before = _snapshot_data_dir()

    started = datetime.datetime.now()
    log_lines = [f"check_for_updates.py run started {started.isoformat()}"]
    all_steps = FETCH_SCRIPTS + COMPUTE_SCRIPTS

    # Small local progress window (User-Wunsch, 2026-09-05: "kannst du
    # eventuell während des Fetches ein kleines Fortschrittsfenster
    # bauen?") -- purely a convenience layered on top of the exact same
    # _run/_snapshot_data_dir/_diff_data_dir this always used, so a
    # missing/broken PySide6 just falls back to the original plain-
    # terminal loop instead of failing the whole check.
    try:
        from _progress_window import run_with_progress_window
        log_lines, changes_or_none, failed = run_with_progress_window(
            all_steps, _run, _snapshot_data_dir, _diff_data_dir, before, log_lines,
        )
        changes = changes_or_none
    except Exception as exc:  # noqa: BLE001 -- any GUI failure just falls back
        print(f"(progress window unavailable: {exc} -- continuing without it)")
        failed = []
        for script in all_steps:
            if not _run(script, log_lines):
                failed.append(script)
        after = _snapshot_data_dir()
        changes = _diff_data_dir(before, after)

    print("\n=== Changed data files ===")
    log_lines.append("\n=== Changed data files ===")
    if not changes:
        print("(no changes)")
        log_lines.append("(no changes)")
    for filename, lines in changes.items():
        header = f"\n{filename} ({len(lines)} change{'s' if len(lines) != 1 else ''}):"
        print(header)
        log_lines.append(header)
        for line in lines:
            print(f"  {line}")
            log_lines.append(f"  {line}")

    if failed:
        print(f"\n{len(failed)} script(s) failed: {', '.join(failed)} -- check output above before trusting this run.")
        log_lines.append(f"\n{len(failed)} script(s) failed: {', '.join(failed)}")
    elif not changes:
        print("\nNo data changes this run.")
    else:
        print("\nData changed -- review the exact changes above, then `git diff`/commit by hand if it looks right.")

    LOG_PATH.write_text("\n".join(log_lines), encoding="utf-8")
    print(f"\nFull log written to {LOG_PATH}")


if __name__ == "__main__":
    main()
