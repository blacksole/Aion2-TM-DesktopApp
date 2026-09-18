"""Atomic, self-healing JSON persistence for profile files.

Qt-free on purpose: this is the safety net under `MainWindow.save_profile` /
`MainWindow.load_profile`, and it has to be unit-testable without a
QApplication.

Two failure modes from the audit (docs/audit-2026-09-18/A-core-architecture.md
§2) are addressed here:

1. **Non-atomic writes.** `save_profile` used to write straight over the
   profile with `open(path, "w")` + `json.dump`, from 49 different call sites
   (one per click). A crash or power loss anywhere in that window truncates
   the file. `atomic_write_json` writes a sibling `.tmp`, fsyncs it, rotates
   the previous good file to `.bak`, and only then `os.replace()`s it into
   place -- `os.replace` is atomic on both POSIX and Windows, so the profile
   on disk is always either the complete old content or the complete new one.
2. **Corrupt file -> empty dict -> overwritten.** `load_profile` swallowed
   `JSONDecodeError` into `data = {}`, and the next auto-save then wrote that
   empty profile over the corpse -- silent total loss.
   `load_json_with_fallback` never hides that: it falls back to the `.bak`
   and reports which copy the caller actually got ("ok" / "bak" / "empty"),
   so the UI can warn and, in the worst case, refuse to save over the file.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from core.app_logger import get_logger

logger = get_logger("persistence")

# Bumped only when the on-disk profile shape changes in a way that needs a
# migration. Nothing migrates yet -- this release just starts stamping the
# field so a future migration has something to branch on (files written by
# <= 2.0.7 have no key at all and are treated as version 0).
SCHEMA_VERSION = 1


def _tmp_path(path: Path) -> Path:
    return path.with_suffix(".json.tmp")


def backup_path(path: Path) -> Path:
    """The `.bak` sibling `atomic_write_json` rotates to and
    `load_json_with_fallback` falls back to."""
    return Path(path).with_suffix(".json.bak")


def atomic_write_json(path, data: dict, *, backup: bool = True) -> None:
    """Write `data` to `path` so that `path` is never left partially written.

    tmp -> flush + fsync -> rotate previous content to `.bak` -> os.replace.
    If anything raises, the temp file is removed and the exception propagates
    with the original `path` still untouched.
    """
    path = Path(path)
    tmp = _tmp_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        if backup and path.exists():
            # copy2, not rename: between the rotation and the os.replace below
            # there must never be a moment where `path` does not exist.
            shutil.copy2(path, backup_path(path))

        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove temp file after a failed write: %s", tmp)
        raise


def _read_json_dict(path: Path) -> dict | None:
    """Read one JSON object, or None if the file is missing, unreadable,
    empty, malformed, or simply not an object."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None

    if not raw.strip():
        logger.warning("File is empty: %s", path)
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Malformed JSON in %s: %s", path, exc)
        return None

    if not isinstance(data, dict):
        logger.warning("Expected a JSON object in %s, got %s", path, type(data).__name__)
        return None

    return data


def load_json_with_fallback(path) -> tuple[dict, str]:
    """Load `path`, falling back to its `.bak` copy.

    Returns `(data, status)` where status is:
      * "ok"    -- `path` itself was read successfully
      * "bak"   -- `path` was unusable, the backup was used (warn the user!)
      * "empty" -- neither copy was usable; `data` is `{}`

    A corrupt file is NEVER silently turned into `{}`: "empty" together with
    an existing `path` means the caller must refuse to save over it.
    """
    path = Path(path)

    data = _read_json_dict(path)
    if data is not None:
        return data, "ok"

    bak = backup_path(path)
    if path.exists():
        logger.warning("%s is unusable -- trying backup %s", path, bak)

    data = _read_json_dict(bak)
    if data is not None:
        logger.warning("Recovered %s from its backup %s", path, bak)
        return data, "bak"

    if path.exists():
        logger.error(
            "Neither %s nor its backup %s could be read -- returning an empty "
            "profile; the file must NOT be overwritten.", path, bak,
        )
    else:
        logger.debug("No file at %s (and no backup) -- starting empty", path)

    return {}, "empty"


def snapshot_corrupt(path) -> Path | None:
    """Copy an unreadable profile aside as ``<name>.json.corrupt-<YYYYmmdd-HHMMSS>``.

    Called before anything deliberately overwrites a file that could not be
    parsed (neither it nor its ``.bak``), so a manual rescue -- a missing
    closing brace, a truncated tail -- stays possible after the user chooses
    to carry on. Copies rather than renames: the profile the app is about to
    write must keep its own name, and a rename would briefly leave none.

    Returns the snapshot path, or None when there was nothing to copy or the
    copy failed (never raises: this runs on the way to saving the user's work,
    and must not be what stops it).
    """
    path = Path(path)
    try:
        if not path.is_file():
            return None
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = path.with_name(f"{path.name}.corrupt-{stamp}")
        shutil.copy2(path, target)
        logger.warning("Unreadable profile %s copied aside to %s", path, target)
        return target
    except OSError as exc:
        logger.error("Could not snapshot the unreadable profile %s: %s", path, exc)
        return None


def stamp_schema(data: dict) -> dict:
    """Set the schema version on `data` (idempotent) and return it."""
    data["schema_version"] = SCHEMA_VERSION
    return data


def schema_version_of(data: dict) -> int:
    """Version of a loaded payload. Files written before schema stamping
    existed have no key at all and count as 0."""
    try:
        return int(data.get("schema_version", 0))
    except (TypeError, ValueError):
        return 0
