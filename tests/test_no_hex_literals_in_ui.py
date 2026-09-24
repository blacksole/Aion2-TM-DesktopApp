"""MASTER §4-3/§4-4: no colour literal outside ``core/theme.py``.

The design system only holds if the UI cannot reach around it.  Before this
gate, ``ui/`` carried 124 hex/QColor literals -- a per-theme gradient table
in main_window, an Abyss-cyan progress bar that stayed cyan on Inferno, a
white-on-cyan overlay badge, a slate separator repeated in three files with
two different spellings.  None of them was visible to
``tests/test_qss_contrast.py``, because none of them was a token.

Three things this file gates, each added for a reason the review named:

* ``ui/`` **and ``core/``** are scanned (review F-5).  MASTER line 3 promises
  no magic hex in either, and ``core/translations.py`` had already frozen the
  ``ok`` and ``fg.muted`` tokens inside three language tables.
* exemptions are **entry-granular** (review F-6).  A per-file exemption let a
  new literal hide behind an old one.
* ``ItemDatabase/`` is **baseline-counted** rather than scanned clean: its
  tokenization is a later wave, but the counts must not grow in the meantime.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
ALLOWLIST = FIXTURES / "hex_allowlist.txt"
BASELINE = FIXTURES / "itemdatabase_literal_baseline.txt"

#: Directories whose Python must contain no colour literal.
SCAN_DIRS = ("ui", "core")

#: The single owner of the token values.  Not an exception to "no magic hex"
#: -- it is where the hexes are supposed to be, and every scanned file reads
#: from it.  Listed here rather than in the allow-list because exempting the
#: owner is structural, not a tolerated debt.
OWNER_FILES = {"core/theme.py"}

#: ``#rgb`` / ``#rrggbb`` / ``#rrggbbaa``.  Word-boundary-anchored so a
#: ``#objectName`` inside a QSS string is not mistaken for a colour.
_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")

#: ``QColor(12, 34, 56)`` / ``QColor("#…")`` -- a QColor built from a
#: literal.  ``QColor(some_string)`` and ``QColor(other_qcolor)`` are fine:
#: that is how a token or a data colour is turned into a QColor.
_QCOLOR_RE = re.compile(r"QColor\(\s*(?:\d|[\"']\s*#)")

#: ``rgb(...)`` / ``rgba(...)`` written into an inline stylesheet.  An
#: f-string interpolating a token is not matched (no literal digit first).
_RGB_FUNC_RE = re.compile(r"\brgba?\(\s*\d")

_SETSTYLESHEET_RE = re.compile(r"\.setStyleSheet\s*\(")


# ---------------------------------------------------------------------------
# scanning
# ---------------------------------------------------------------------------


def _strip_comments(source: str) -> str:
    """Blank out ``#`` comments, keeping line numbering intact.

    A comment may legitimately name the literal it replaced ("was
    ``#64748b``"), and that documentation must not trip the gate.  Quote-aware
    so a ``"#rrggbb"`` inside a string still counts.
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
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


def _scanned_files() -> list[Path]:
    files = []
    for directory in SCAN_DIRS:
        files.extend(
            p for p in (REPO / directory).rglob("*.py") if "__pycache__" not in p.parts
        )
    return sorted(files)


def _relative(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def _offences(path: Path) -> set[tuple[str, int, str]]:
    """``{(relative path, line, literal)}`` — keyed by PATH, not basename.

    Basename keying (review F-12) silently merged same-named files under
    different directories.
    """
    source = _strip_comments(path.read_text(encoding="utf-8"))
    relative = _relative(path) if path.is_relative_to(REPO) else path.name
    found = set()
    for number, line in enumerate(source.splitlines(), start=1):
        for literal in _HEX_RE.findall(line):
            found.add((relative, number, literal))
        for pattern, label in ((_QCOLOR_RE, "QColor-literal"), (_RGB_FUNC_RE, "rgb-literal")):
            if pattern.search(line):
                found.add((relative, number, label))
    return found


# ---------------------------------------------------------------------------
# allow-list
# ---------------------------------------------------------------------------


def _allowlist() -> dict[tuple[str, int, str], str]:
    entries: dict[tuple[str, int, str], str] = {}
    for raw in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        spec, _, reason = line.partition("#  ")
        if not reason:
            spec, _, reason = line.partition("  #")
        path, _, rest = spec.strip().partition(":")
        number, _, literal = rest.partition(":")
        entries[(path, int(number), literal.strip())] = reason.strip().lstrip("#").strip()
    return entries


def test_the_allowlist_parses_and_every_entry_is_justified():
    entries = _allowlist()
    assert entries, "the allow-list parsed empty — wrong format?"
    for key, reason in entries.items():
        assert len(reason) > 30, f"{key} needs a real reason, got {reason!r}"
        assert (REPO / key[0]).is_file(), f"allow-list names a missing file: {key[0]}"


def test_the_allowlist_cannot_exempt_a_whole_file():
    """Review F-6: the format must not admit a bare path."""
    for raw in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        spec = line.split("#")[0].strip()
        assert spec.count(":") >= 2, f"not entry-granular: {line!r}"
        _path, number, _literal = spec.split(":", 2)
        assert number.isdigit(), f"second field must be a line number: {line!r}"


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------


def test_there_are_files_to_scan():
    """A broken glob would make every assertion below vacuously true."""
    files = _scanned_files()
    assert len(files) > 25, f"only found {len(files)} files under {SCAN_DIRS}"
    names = {_relative(p) for p in files}
    assert "core/translations.py" in names
    assert "ui/main_window.py" in names


@pytest.mark.parametrize("path", _scanned_files(), ids=_relative)
def test_no_colour_literal(path):
    relative = _relative(path)
    if relative in OWNER_FILES:
        pytest.skip("core/theme.py owns the token values")
    found = _offences(path)
    allowed = {key for key in _allowlist() if key[0] == relative}
    unexpected = sorted(found - allowed)
    assert not unexpected, (
        "colour literals must come from core.theme (MASTER §4-3/§4-4):\n  "
        + "\n  ".join(f"{p}:{n}: {lit}" for p, n, lit in unexpected)
    )
    stale = sorted(allowed - found)
    assert not stale, (
        "allow-list entries that no longer match anything — delete them:\n  "
        + "\n  ".join(f"{p}:{n}: {lit}" for p, n, lit in stale)
    )


def test_the_gate_catches_a_literal(tmp_path):
    """The scanner itself, on each shape it rejects."""
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


def test_translations_no_longer_freeze_a_token(qapp):
    """Review F-5: two rich-text strings had the `ok` and `fg.muted` hexes
    baked into all three language tables.  They are placeholders now, so the
    span follows the theme."""
    from core import theme
    from core.translations import tr

    for language in ("en", "de", "ru"):
        for name in sorted(theme.THEMES):
            theme.set_current(name)
            text = tr(language, "arm_all_substats_selected_html", selected=1, cap=2, stone_note="")
            assert theme.THEMES[name].ok in text, (language, name)
            assert "{color_" not in text
    theme.set_current(theme.DEFAULT_THEME)


# ---------------------------------------------------------------------------
# MASTER §4-4: setStyleSheet in a widget → objectName + a template rule
# ---------------------------------------------------------------------------

#: The complete inventory of ``setStyleSheet`` calls left under the scanned
#: directories, keyed by RELATIVE PATH (review F-12).  There were 48 under
#: ``ui/`` before this wave.
#:
#: Five set a DATA colour (the exception MASTER §4-4 names: a colour the user
#: or the catalog picked, not the theme) and nothing else — no size, no
#: radius, no font.  The rest of each widget's look is an objectName rule in
#: ui/styles.template.qss.  The other three are delivery, not styling.
_ALLOWED_SETSTYLESHEET = {
    "ui/custom_timer_dialog.py": 2,          # swatch fill + preview colour (per-timer data)
    "ui/custom_timer_manager_dialog.py": 1,  # the row's timer-colour dot (per-timer data)
    "ui/pages/timers_page.py": 1,            # the card's big number (per-timer data)
    "ui/overlay/overlay_window.py": 1,       # Countdown Start/Stop fill (per-timer data)
    "ui/main_window.py": 2,                  # the app-wide sheet + the Armory's own sheet
    "core/theme.py": 1,                      # theme.apply(): the app-wide sheet
    # The QDateEdit popup: the calendar and the `qt_datetimedit_calendar`
    # container Qt wraps it in.  Neither can be reached from the app sheet
    # -- the container is a parentless Qt::Popup, so the scoped prefix never
    # matches it, and a widget's own stylesheet REPLACES the app sheet for
    # that widget rather than merging, so the rules have to be restated
    # where they are set.  Every value still comes from core.theme.
    "ui/widgets/calendar_popup.py": 2,
}


def _setstylesheet_calls(path: Path) -> list[str]:
    source = _strip_comments(path.read_text(encoding="utf-8"))
    relative = _relative(path)
    return [
        f"{relative}:{number}: {line.strip()}"
        for number, line in enumerate(source.splitlines(), start=1)
        if _SETSTYLESHEET_RE.search(line)
    ]


def test_no_new_inline_stylesheet():
    """A 49th call site has to be argued for, not slipped in."""
    found = {}
    for path in _scanned_files():
        calls = _setstylesheet_calls(path)
        if calls:
            found[_relative(path)] = calls

    unexpected = {name: calls for name, calls in found.items() if name not in _ALLOWED_SETSTYLESHEET}
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
    """MASTER §4-4 tolerates a data COLOUR — not a size, radius or font."""
    allowed_properties = {"color", "background-color", "background"}
    data_driven = (
        "ui/custom_timer_dialog.py",
        "ui/custom_timer_manager_dialog.py",
        "ui/pages/timers_page.py",
        "ui/overlay/overlay_window.py",
    )
    by_path = {_relative(p): p for p in _scanned_files()}
    for name in data_driven:
        for call in _setstylesheet_calls(by_path[name]):
            for prop in re.findall(r"([a-z-]+)\s*:", call.split(":", 2)[2]):
                assert prop in allowed_properties, f"{call}\n  -> '{prop}' is not a data colour"


# ---------------------------------------------------------------------------
# ItemDatabase/: baseline-counted, not scanned clean (review F-5)
# ---------------------------------------------------------------------------


def _baseline() -> dict[str, int]:
    values = {}
    for raw in BASELINE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = int(value.split("#")[0].strip())
    return values


def _itemdatabase_counts() -> dict[str, int]:
    counts = {"hex": 0, "qcolor": 0, "rgb": 0, "setstylesheet": 0}
    for path in sorted((REPO / "ItemDatabase").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        source = _strip_comments(path.read_text(encoding="utf-8"))
        counts["hex"] += len(_HEX_RE.findall(source))
        counts["qcolor"] += len(_QCOLOR_RE.findall(source))
        counts["rgb"] += len(_RGB_FUNC_RE.findall(source))
        counts["setstylesheet"] += len(_SETSTYLESHEET_RE.findall(source))
    return counts


@pytest.mark.skipif(not (REPO / "ItemDatabase").is_dir(), reason="ItemDatabase not present")
def test_itemdatabase_literal_count_does_not_grow():
    """The Armory is not tokenized yet, and that is a scheduled wave — but
    its debt must not grow while it waits.

    MASTER line 3 promises no magic hex in ``ItemDatabase/`` either; until
    that wave lands, this is the honest version of the promise: a recorded
    baseline that may only ever go DOWN.  Lower it when you remove some.
    """
    baseline = _baseline()
    counts = _itemdatabase_counts()
    grew = {k: (counts[k], baseline[k]) for k in counts if counts[k] > baseline[k]}
    assert not grew, (
        "ItemDatabase colour-literal debt increased (now, baseline): "
        f"{grew} — tokenize instead of adding, or lower the baseline if you removed some"
    )
    shrank = {k: (counts[k], baseline[k]) for k in counts if counts[k] < baseline[k]}
    assert not shrank, (
        "ItemDatabase debt went DOWN — update tests/fixtures/"
        f"itemdatabase_literal_baseline.txt to the new floor: {shrank}"
    )
