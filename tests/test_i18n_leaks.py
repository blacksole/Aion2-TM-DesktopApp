"""Guards against the language mixing the UX audit found (2026-09-18, M3).

Every locale leaked German: "Discord öffnen" on the English About page, a
hardcoded "Profilpfad gespeichert" toast, "Synchron" defaults in Settings, a
German-only "T" day abbreviation in every countdown. Those are fixed; these
tests are the ratchet that keeps them fixed.

Two independent checks:

1. **No German literal goes straight into a widget.** The scan is AST-based,
   not textual, so comments, docstrings and dict tables are invisible to it by
   construction, and a ``tr(...) if tr else "fallback"`` expression is not a
   string literal either -- exactly the two allow-lists the audit asked for.
   Only a bare ``str`` constant handed to a text-setting call is a finding.

2. **Every literal tr() key used by the touched files really exists**, in all
   three language dicts. ``tr()`` falls back to returning the key itself, so a
   typo ships as "toast_task_removd" on screen instead of raising.

``ItemDatabase/`` is out of scope (it is a vendored sub-app with its own
strings, and ruff already excludes it).
"""

import ast
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.translations import TRANSLATIONS

UI_ROOT = Path(__file__).resolve().parent.parent / "ui"

# Files this change set touched -- the ones whose tr() keys are pinned below.
TOUCHED = [
    "main_window.py",
    "pages/about_page.py",
    "pages/timers_page.py",
    "pages/settings_page.py",
    "widgets/shopping_card.py",
]

# Substrings that can only be German. Deliberately short and specific: this is
# a leak detector, not a language classifier.
GERMAN_MARKERS = ("öffnen", "gespeichert", "Kein ", "Synchron")

# Calls whose string argument lands on screen.
TEXT_SETTERS = {
    "setText",
    "setToolTip",
    "setPlaceholderText",
    "setWindowTitle",
    "setTitle",
    "setStatusTip",
    "addItem",
}

# Widget constructors that take their visible label as the first argument.
TEXT_CONSTRUCTORS = {"QPushButton", "QLabel", "QCheckBox", "QRadioButton", "QAction", "QGroupBox"}

# Names a translation lookup goes by in this codebase.
TR_CALLEES = {"tr", "tr_func", "_tr", "_cur_tr", "_default_tr"}


def _ui_files():
    return sorted(p for p in UI_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def _literal_ui_strings(tree):
    """(lineno, call name, string) for every bare str constant handed to a
    text-setting call or a label-taking widget constructor."""
    found = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Attribute) and node.func.attr in TEXT_SETTERS:
            name = node.func.attr
        elif isinstance(node.func, ast.Name) and node.func.id in TEXT_CONSTRUCTORS:
            name = node.func.id
        else:
            continue

        for arg in node.args:
            # An IfExp ("tr(...) if tr else '...'"), an f-string, a Name or a
            # dict lookup is not a literal -- only a bare constant counts.
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found.append((arg.lineno, name, arg.value))

    return found


def _literal_tr_keys(tree):
    """(lineno, key) for every ``tr(<lang>, "literal")`` call."""
    keys = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        if isinstance(func, ast.Attribute):
            callee = func.attr
        elif isinstance(func, ast.Name):
            callee = func.id
        else:
            continue

        if callee not in TR_CALLEES or len(node.args) < 2:
            continue

        key_arg = node.args[1]
        if isinstance(key_arg, ast.Constant) and isinstance(key_arg.value, str):
            keys.append((key_arg.lineno, key_arg.value))

    return keys


def _parse(path: Path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


# ---------------------------------------------------------------------------
# 1. no German literal reaches a widget
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _ui_files(), ids=lambda p: str(p.relative_to(UI_ROOT)))
def test_no_german_literal_is_set_on_a_widget(path):
    leaks = [
        f"{path.relative_to(UI_ROOT)}:{lineno} {call}({string!r})"
        for lineno, call, string in _literal_ui_strings(_parse(path))
        if any(marker in string for marker in GERMAN_MARKERS)
    ]

    assert leaks == [], (
        "German-only copy is going straight onto a widget. Route it through "
        "tr() with a key defined in all three languages:\n  " + "\n  ".join(leaks)
    )


def test_the_scanner_actually_catches_a_leak():
    """The detector above is only worth having if it fires -- this is its own
    regression test, in case a refactor quietly narrows TEXT_SETTERS."""
    tree = ast.parse(
        'btn = QPushButton("Discord öffnen")\n'
        'btn.setToolTip("Timer-Einstellungen öffnen")\n'
    )

    leaks = [s for _, _, s in _literal_ui_strings(tree) if any(m in s for m in GERMAN_MARKERS)]

    assert leaks == ["Discord öffnen", "Timer-Einstellungen öffnen"]


def test_the_scanner_ignores_a_translated_call_with_a_fallback():
    """``tr(lang, "k") if tr else "Synchron"`` is the allow-listed shape."""
    tree = ast.parse('btn.setText(tr(lang, "notif_sync") if tr else "Synchron")\n')

    assert _literal_ui_strings(tree) == []


def test_the_scan_covers_the_files_this_change_touched():
    scanned = {str(p.relative_to(UI_ROOT)) for p in _ui_files()}

    assert set(TOUCHED) <= scanned


# ---------------------------------------------------------------------------
# 2. every tr() key used really exists, in every language
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("relpath", TOUCHED)
def test_every_literal_tr_key_exists_in_all_languages(relpath):
    path = UI_ROOT / relpath
    missing = []

    for lineno, key in _literal_tr_keys(_parse(path)):
        absent = sorted(lang for lang, table in TRANSLATIONS.items() if key not in table)
        if absent:
            missing.append(f"{relpath}:{lineno} {key!r} missing from {absent}")

    assert missing == [], "\n  ".join(["unknown translation keys:"] + missing)


def test_the_keys_added_for_this_change_exist_everywhere():
    added = {
        "day_abbrev",
        "toast_task_removed",
        "undo",
        "about_open_discord",
        "open_in_browser",
        "timers_open_settings_tooltip",
        "open_folder",
        "profile_path_saved",
        "empty_tasks_title",
        "empty_tasks_hint",
        "empty_shopping_title",
        "empty_shopping_hint",
        "empty_timers_title",
        "empty_timers_hint",
        "empty_overlay_tasks",
    }

    for lang, table in TRANSLATIONS.items():
        assert added <= set(table), f"{lang} is missing {sorted(added - set(table))}"
        for key in sorted(added):
            assert table[key].strip(), f"{lang}[{key}] is empty"


def test_all_three_languages_carry_exactly_the_same_keys():
    tables = {lang: set(table) for lang, table in TRANSLATIONS.items()}
    reference = tables["en"]

    for lang, keys in tables.items():
        assert keys == reference, f"{lang} differs by {sorted(keys ^ reference)}"


def test_the_day_abbreviation_is_language_specific():
    assert TRANSLATIONS["en"]["day_abbrev"] == "d"
    assert TRANSLATIONS["de"]["day_abbrev"] == "T"
    assert TRANSLATIONS["ru"]["day_abbrev"] == "д"


def test_the_appearance_section_is_no_longer_called_layout():
    assert TRANSLATIONS["en"]["layout"] == "Appearance"
    assert TRANSLATIONS["de"]["layout"] == "Darstellung"
    assert TRANSLATIONS["ru"]["layout"] == "Оформление"
    # The subtitle used to advertise the old "Layout" name in every language.
    assert "layout" not in TRANSLATIONS["en"]["settings_subtitle"].lower()
    assert "Layout" not in TRANSLATIONS["de"]["settings_subtitle"]


# ---------------------------------------------------------------------------
# 3. the three countdown formatters (M3: the hardcoded German "T")
# ---------------------------------------------------------------------------

def _stub(language, **extra):
    """Just enough of a MainWindow for the formatters, which read nothing but
    ``self.language`` (and ``self.season_reset_datetime``). Keeps these cases
    free of a ~1 s window construction."""
    return SimpleNamespace(language=language, **extra)


@pytest.mark.parametrize(
    ("language", "abbrev"),
    [("en", "d"), ("de", "T"), ("ru", "д")],
)
def test_reset_countdown_uses_the_translated_day_abbreviation(language, abbrev):
    from ui.main_window import MainWindow

    seconds = 2 * 86400 + 18 * 3600 + 27 * 60

    text = MainWindow.format_reset_countdown(_stub(language), seconds)

    assert text == f"2{abbrev} 18:27"


@pytest.mark.parametrize(
    ("language", "abbrev"),
    [("en", "d"), ("de", "T"), ("ru", "д")],
)
def test_custom_countdown_uses_the_translated_day_abbreviation(language, abbrev):
    from ui.main_window import MainWindow

    seconds = 2 * 86400 + 18 * 3600 + 27 * 60 + 5

    text = MainWindow._format_custom_countdown(_stub(language), seconds, "dd:hh:mm")

    assert text == f"2{abbrev} 18:27:05"


@pytest.mark.parametrize(
    ("language", "abbrev"),
    [("en", "d"), ("de", "T"), ("ru", "д")],
)
def test_season_countdown_uses_the_translated_day_abbreviation(language, abbrev):
    from ui.main_window import MainWindow

    target = datetime.now() + timedelta(days=2, hours=18, minutes=27, seconds=30)
    stub = _stub(language, season_reset_datetime=target.strftime("%Y-%m-%d %H:%M"))

    text = MainWindow._get_season_countdown_text(stub)

    assert text.startswith(f"2{abbrev} ") or text.startswith(f"1{abbrev} 23:5"), text


def test_countdowns_below_a_day_carry_no_day_abbreviation():
    from ui.main_window import MainWindow

    assert MainWindow.format_reset_countdown(_stub("de"), 3661) == "01:01:01"
    assert MainWindow._format_custom_countdown(_stub("de"), 3661, "dd:hh:mm") == "01:01:01"
