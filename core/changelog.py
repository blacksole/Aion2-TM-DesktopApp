"""Shared CHANGELOG.md parsing -- the single source of truth for release
notes/dates, used by both core/update_checker.py (a single version's notes
for the update-available dialog) and ui/update_dialog.py's
ChangelogHistoryDialog (the full local version history).

Split out (2026-09-26, companion.g-place.de migration): the update checker
now needs a version's release notes WITHOUT hitting GitHub's Releases API at
all (that host has no notes/changelog endpoint, just ".version"/".zip"), so
this had to stop being private to ui/update_dialog.py.
"""

import re
import sys
from datetime import datetime
from pathlib import Path


def changelog_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "CHANGELOG.md"


# "Release Date: 2026-09-17" on a line of its own.
RELEASE_DATE_RE = re.compile(r"(?mi)^\s*Release Date:\s*(\d{4}-\d{2}-\d{2})\s*$\n?")

# A hotfix is marked by a line that says only "Hotfix" (usually bold, see
# the 2.0.5 entry) -- NOT by the word turning up somewhere in the notes.
# The old substring check badged 2.0.6, whose notes merely mention that
# "Hotfix releases are marked with a badge" (User-reported, 2026-09-24).
_HOTFIX_MARK_RE = re.compile(r"(?mi)^\s*[*_]*\s*hotfix\s*[*_]*\s*$")


def is_hotfix(body: str) -> bool:
    return bool(_HOTFIX_MARK_RE.search(body or ""))


def parse_local_changelog() -> list[dict]:
    """Reads the bundled CHANGELOG.md directly (newest version first, same
    order it's written in) so every version that was ever written down
    shows up here -- not just the ones that happened to get published as
    an actual GitHub Release. In practice a release can lag behind its git
    tag (User-reported, 2026-09-17: v2.0.6/v2.0.4 were tagged and built but
    never separately published, so they silently never showed up here
    when this only read GitHub's /releases list).

    Returns a list of {"tag", "body", "release_date"} dicts, "release_date"
    being "" when the entry carries no "Release Date:" line.
    """
    path = changelog_path()
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    sections = re.split(r"(?m)^#\s+Version\s+", text)
    entries = []
    for section in sections[1:]:
        lines = section.strip().splitlines()
        if not lines:
            continue
        tag = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        # "Release Date: YYYY-MM-DD" (the format the 0.x/1.x entries already
        # use) is the local fallback date for a version that never became
        # its own GitHub Release (User-reported, 2026-09-24: v2.0.6/v2.0.4
        # showed no date at all).  Taken out of the body so the notes don't
        # repeat what the rail and header already show.
        release_date = ""
        date_match = RELEASE_DATE_RE.search(body)
        if date_match:
            release_date = date_match.group(1)
            body = RELEASE_DATE_RE.sub("", body, count=1).strip()
        entries.append({"tag": tag, "body": body, "release_date": release_date})
    return entries


def release_notes_for(version: str) -> str:
    """The CHANGELOG.md body for exactly this version, or "" if it isn't
    (yet) written down there -- e.g. the update check fires against a
    version that landed on companion.g-place.de moments before the local
    CHANGELOG.md entry was written, or the entry only lists a body-less
    placeholder pending a fuller write-up."""
    version = (version or "").lstrip("v")
    for entry in parse_local_changelog():
        if entry["tag"] == version:
            return entry["body"]
    return ""


# Lightweight month-name lookup (User-Wunsch, 2026-09-14: show each
# version's release date) -- no locale/babel dependency, matching this
# app's existing lightweight-translation style elsewhere (e.g. the plain
# "Mo"/"Di" weekday defaults). Only the 3 languages the app itself supports.
# Moved here from ui/update_dialog.py (2026-09-26) so the news popup can
# format a WordPress post date the exact same way as a changelog entry's
# date, instead of inventing a second date format in the same app.
_MONTH_NAMES = {
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
           "August", "September", "Oktober", "November", "Dezember"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
           "августа", "сентября", "октября", "ноября", "декабря"],
    "en": ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"],
}


def format_release_date(iso_str: str, language: str) -> str:
    """An ISO datetime (e.g. "2026-09-14T18:07:29Z", GitHub's/WordPress's
    format) into a human-readable date in the given UI language.
    Empty/unparsable input just returns "" -- an older or malformed date
    simply shows no date rather than a confusing placeholder."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        return ""
    months = _MONTH_NAMES.get(language, _MONTH_NAMES["en"])
    month = months[dt.month - 1]
    if language == "en":
        return f"{month} {dt.day}, {dt.year}"
    return f"{dt.day}. {month} {dt.year}"
