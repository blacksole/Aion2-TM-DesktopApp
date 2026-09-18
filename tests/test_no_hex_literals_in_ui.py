"""MASTER §4-3/§4-4: no colour literal anywhere under ``ui/``.

The design system only holds if the UI cannot reach around it.  Before this
gate, ``ui/`` carried 124 hex/QColor literals -- a per-theme gradient table
in main_window, an Abyss-cyan progress bar that stayed cyan on Inferno, a
white-on-cyan overlay badge, a slate separator repeated in three files with
two different spellings.  Every one of them was invisible to
``tests/test_qss_contrast.py``, because none of them was a token.

So: scan the source, fail on a colour that is not a token lookup.  The only
tolerated exceptions live in ``tests/fixtures/hex_allowlist.txt``, which is
file-scoped and must justify every entry in prose.
"""

import re
from pathlib import Path

import pytest

UI_DIR = Path(__file__).resolve().parent.parent / "ui"
ALLOWLIST = Path(__file__).resolve().parent / "fixtures" / "hex_allowlist.txt"

#: ``#rgb`` / ``#rrggbb`` / ``#rrggbbaa``.  Word-boundary-anchored so a
#: ``#objectName`` inside a QSS string is not mistaken for a colour.
_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")

#: ``QColor(12, 34, 56)`` / ``QColor("#…")`` -- a QColor built from a
#: literal.  ``QColor(some_string)`` and ``QColor(other_qcolor)`` are fine:
#: that is how a token or a data colour is turned into a QColor.
_QCOLOR_RE = re.compile(r"QColor\(\s*(?:\d|[\"']\s*#)")

#: ``rgb(...)`` / ``rgba(...)`` written into an inline stylesheet.  An
#: f-string interpolating a token is not matched (it has no literal digits
#: in the first slot).
_RGB_FUNC_RE = re.compile(r"\brgba?\(\s*\d")


def _allowlist() -> dict[str, str]:
    """``{relative path: reason}`` from the fixture."""
    entries: dict[str, str] = {}
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        path, _, reason = line.partition("#")
        entries[path.strip()] = reason.strip()
    return entries


def _strip_comments(source: str) -> str:
    """Blank out ``#`` comments, keeping line count and column offsets.

    A comment may legitimately name the literal it replaced ("was
    ``#64748b``"), and that documentation must not trip the gate.  Done
    line-wise with a quote-awareness pass rather than by tokenising, so a
    ``"#rrggbb"`` inside a string still counts.
    """
    out = []
    for line in source.splitlines():
        quote = None
        cut = None
        index = 0
        while index < len(line):
            char = line[index]
            if quote:
                if char == "\\":
                    index += 2
                    continue
                if char == quote:
                    quote = None
            elif char in "\"'":
                quote = char
            elif char == "#":
                cut = index
                break
            index += 1
        out.append(line if cut is None else line[:cut] + " " * (len(line) - cut))
    return "\n".join(out)


def _ui_files() -> list[Path]:
    return sorted(p for p in UI_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def _offences(path: Path) -> list[str]:
    source = _strip_comments(path.read_text(encoding="utf-8"))
    found = []
    for number, line in enumerate(source.splitlines(), start=1):
        for label, pattern in (
            ("hex", _HEX_RE),
            ("QColor literal", _QCOLOR_RE),
            ("rgb()/rgba() literal", _RGB_FUNC_RE),
        ):
            if pattern.search(line):
                found.append(f"{path.name}:{number}: {label} — {line.strip()}")
    return found


def test_there_are_ui_files_to_scan():
    """A broken glob would make every assertion below vacuously true."""
    files = _ui_files()
    assert len(files) > 20, f"only found {len(files)} files under {UI_DIR}"


@pytest.mark.parametrize("path", _ui_files(), ids=lambda p: str(p.relative_to(UI_DIR)))
def test_no_colour_literal(path):
    relative = path.relative_to(UI_DIR.parent).as_posix()
    if relative in _allowlist():
        pytest.skip(f"allow-listed: {_allowlist()[relative]}")
    offences = _offences(path)
    assert not offences, (
        "colour literals must come from core.theme (MASTER §4-3/§4-4):\n  "
        + "\n  ".join(offences)
    )


def test_allowlist_entries_all_exist_and_are_justified():
    """A stale or unexplained exception is worse than none."""
    for relative, reason in _allowlist().items():
        assert (UI_DIR.parent / relative).is_file(), f"allow-list names a missing file: {relative}"
        assert len(reason) > 40, f"allow-list entry {relative} needs a real reason, got {reason!r}"


def test_allowlist_entries_are_actually_needed():
    """An entry whose file is now clean must be deleted, not left to rot."""
    for relative in _allowlist():
        path = UI_DIR.parent / relative
        assert _offences(path), f"{relative} has no colour literal left — remove its allow-list entry"


def test_the_gate_catches_a_literal(tmp_path):
    """The scanner itself, on each of the three shapes it rejects."""
    for snippet in (
        'label.setStyleSheet("color: #64748b;")\n',
        "color = QColor(15, 23, 42, 180)\n",
        'label.setStyleSheet("background: rgba(14, 16, 24, 0.98);")\n',
        'color = QColor("#38bdf8")\n',
    ):
        probe = tmp_path / "probe.py"
        probe.write_text(snippet, encoding="utf-8")
        assert _offences(probe), f"scanner missed: {snippet!r}"


def test_the_gate_accepts_a_token_lookup(tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text(
        "# was color: #64748b before the token system\n"
        'color = theme.qcolor(theme.current_tokens(), "fg.muted")\n'
        'fill = QColor(theme.data_color("timer", "daily"))\n'
        'label.setStyleSheet(f"color: {color.name()};")\n'
        'menu.setObjectName("charFilterMenu")\n',
        encoding="utf-8",
    )
    assert not _offences(probe)


# ---------------------------------------------------------------------------
# MASTER §4-4: setStyleSheet in a widget → objectName + a template rule
# ---------------------------------------------------------------------------

#: The complete inventory of ``setStyleSheet`` calls left under ``ui/``, each
#: with the reason it is allowed to stay.  There were 48 before this wave.
#:
#: Five of them set a DATA colour (the exception MASTER §4-4 names: a colour
#: the user or the catalog picked, not the theme) and nothing else — no size,
#: no radius, no font; the rest of each widget's look is an objectName rule
#: in ui/styles.template.qss.  The other two are delivery, not styling.
_ALLOWED_SETSTYLESHEET = {
    "custom_timer_dialog.py": 2,          # swatch fill + preview colour (per-timer data)
    "custom_timer_manager_dialog.py": 1,  # the row's timer-colour dot (per-timer data)
    "timers_page.py": 1,                  # the card's big number (per-timer data)
    "overlay_window.py": 1,               # Countdown Start/Stop fill (per-timer data)
    "main_window.py": 2,                  # the app-wide sheet + the Armory's own sheet
}

_SETSTYLESHEET_RE = re.compile(r"\.setStyleSheet\s*\(")


def _setstylesheet_calls(path: Path) -> list[str]:
    source = _strip_comments(path.read_text(encoding="utf-8"))
    return [
        f"{path.name}:{number}: {line.strip()}"
        for number, line in enumerate(source.splitlines(), start=1)
        if _SETSTYLESHEET_RE.search(line)
    ]


def test_no_new_inline_stylesheet_anywhere_in_ui():
    """A 49th call site has to be argued for, not slipped in.

    The count is asserted per file rather than as a total so a call moving
    between files still shows up.
    """
    found: dict[str, list[str]] = {}
    for path in _ui_files():
        calls = _setstylesheet_calls(path)
        if calls:
            found[path.name] = calls

    unexpected = {
        name: calls for name, calls in found.items() if name not in _ALLOWED_SETSTYLESHEET
    }
    assert not unexpected, (
        "setStyleSheet() in a widget must become an objectName + a rule in "
        f"ui/styles.template.qss (MASTER §4-4):\n  "
        + "\n  ".join(line for calls in unexpected.values() for line in calls)
    )

    for name, expected in _ALLOWED_SETSTYLESHEET.items():
        calls = found.get(name, [])
        assert len(calls) == expected, (
            f"{name}: expected {expected} setStyleSheet call(s), found {len(calls)}:\n  "
            + "\n  ".join(calls)
        )


def test_the_data_driven_exceptions_set_only_a_colour():
    """MASTER §4-4 tolerates a data COLOUR — not a size, radius or font.

    Anything else in one of those inline sheets belongs in the template,
    where a theme can move it.
    """
    allowed_properties = {"color", "background-color", "background"}
    for name in ("custom_timer_dialog.py", "custom_timer_manager_dialog.py",
                 "timers_page.py", "overlay_window.py"):
        path = next(p for p in _ui_files() if p.name == name)
        for call in _setstylesheet_calls(path):
            for prop in re.findall(r"([a-z-]+)\s*:", call.split(":", 2)[2]):
                assert prop in allowed_properties, f"{call}\n  -> '{prop}' is not a data colour"
