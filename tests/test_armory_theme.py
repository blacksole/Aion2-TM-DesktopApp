"""MASTER §4 for the Armory: the sheet is a template, its colours are tokens.

``ItemDatabase/`` was the one corner of this repo the design system did not
reach.  It carried its own 1,205-line hand-written stylesheet ("Abyss,
copied intentionally"), 201 colour literals and 96 ``setStyleSheet`` calls,
and MASTER listed it as a deferred decision with its debt frozen by a
counted baseline (``tests/fixtures/itemdatabase_literal_baseline.txt``).
This module gates the wave that closed it.

Five things, in the order they can fail:

1. the template renders, for all six themes, with nothing unresolved;
2. it still carries every selector the hand-written sheet had
   (``tests/fixtures/armory_legacy_selectors.txt``) -- the same
   snapshot-survives-deletion guarantee ``tests/test_theme.py`` makes for
   the app's own sheet;
3. the rules it must NOT have: no ``color`` on an item view (that would
   flatten every per-rarity ``setForeground``, the 2026-08-29 defect), and
   no ``font-family`` (MASTER's deferred "app.setFont() after the wave" is
   the host's call, and 22k lines of layout are tuned to the system font);
4. contrast: every rarity colour on every theme's own surfaces;
5. the pixels: all three Armory windows, per theme, grabbed offscreen --
   nothing raises, no Fusion grey patch, the accent really is in the
   sheet, a rarity foreground really survives it, and ``apply_theme()``
   really restyles a window that is already open.

Two of these (3) used to live in ``tests/test_app_sheet_isolation.py``,
asserted against ``ItemDatabase/styles.qss`` itself and guarded by
``skipif(not ARMORY_SHEET.is_file())``.  That file is gone now, so those
two went quietly to "skipped": they are re-asserted here against the
RENDERED template instead, which is the thing the windows actually get.
"""

import importlib.util
import re
import sys
from array import array
from pathlib import Path

import pytest
from PySide6.QtCore import QDeadlineTimer, QEventLoop
from PySide6.QtGui import QBrush, QColor, QImage, QStandardItem
from PySide6.QtWidgets import QWidget

from core import theme
from tests.conftest import destroy_window

ROOT = Path(__file__).resolve().parent.parent
APP_PY = ROOT / "ItemDatabase" / "app.py"
TEMPLATE = ROOT / "ItemDatabase" / "styles.template.qss"
LEGACY_SELECTORS = Path(__file__).resolve().parent / "fixtures" / "armory_legacy_selectors.txt"

#: Same set and same budget as the app's own render gate
#: (tests/test_render_gate.py): a patch of one of Fusion's default surfaces
#: on a page of an all-dark app is a widget the stylesheet never reached.
FUSION_GREYS = {0xEFEFEF, 0xF0F0F0, 0xD4D0C8, 0xFFFFFF, 0xECECEC}
MAX_GREY_PIXELS = 200


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _rendered(name: str) -> str:
    return theme.build_qss_from(TEMPLATE, name, asset_path="/QA_ASSETS")


def _without_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _rules(qss: str):
    """``(selector, declarations)`` per selector, as test_app_sheet_isolation
    parses them -- so the two modules agree on what "a selector" is.

    Always given a RENDERED sheet, never the template: a ``{{token}}``
    carries braces of its own, which is exactly what this parser splits
    on.  Rendering first is also the more honest subject -- it is the
    string the windows are handed.
    """
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", _without_comments(qss)):
        for selector in (" ".join(s.split()) for s in match.group(1).split(",")):
            if selector:
                yield selector, match.group(2)


def _declares(declarations: str, prop: str) -> bool:
    return bool(re.search(rf"(^|;|\s){re.escape(prop)}\s*:", declarations))


def _legacy_selectors() -> set[str]:
    """Read the snapshot.

    Comment lines start with ``"# "`` rather than ``"#"``: nearly every
    selector in this file starts with ``#`` too (it is a sheet of
    objectNames), so the usual "skip lines beginning with a hash" would
    quietly drop 150 of them and pass on an empty set.
    """
    lines = LEGACY_SELECTORS.read_text(encoding="utf-8").splitlines()
    return {
        line.strip()
        for line in lines
        if line.strip() and not line.startswith("# ") and line.strip() != "#"
    }


def _settle(app, ms: int = 300) -> None:
    deadline = QDeadlineTimer(ms)
    while not deadline.hasExpired():
        app.processEvents(QEventLoop.AllEvents, 20)


def _grey_histogram(image) -> dict[int, int]:
    """Fusion-grey pixel counts, counted as aligned 32-bit words (the same
    trick and the same reason as tests/test_render_gate.py)."""
    rgb32 = image.convertToFormat(QImage.Format_RGB32)
    words = array("I")
    words.frombytes(bytes(rgb32.constBits()))
    counts = {}
    for grey in FUSION_GREYS:
        found = words.count(0xFF000000 | grey)
        if found:
            counts[grey] = found
    return counts


def _exact_pixels(image, color: str) -> int:
    rgb32 = image.convertToFormat(QImage.Format_RGB32)
    words = array("I")
    words.frombytes(bytes(rgb32.constBits()))
    return words.count(0xFF000000 | (QColor(color).rgb() & 0xFFFFFF))


# ---------------------------------------------------------------------------
# fixtures -- one module load, three windows, reused across all six themes
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def armory_module(qapp, tmp_path_factory):
    """``ItemDatabase/app.py`` loaded the way the host loads it, offline.

    Same recipe as tests/test_build_planner_state.py (and the same reuse of
    ``sys.modules``, so a session that runs both pays for one load):
    importlib by path, caches redirected to a tmp dir before any window
    exists, and both network entry points replaced by a sentinel that
    raises -- a cold Armory really does fire icon GETs.
    """
    from PySide6.QtNetwork import QNetworkAccessManager

    patcher = pytest.MonkeyPatch()

    def _no_network(self, *args, **kwargs):
        raise AssertionError("an Armory test tried to reach the network")

    patcher.setattr(QNetworkAccessManager, "get", _no_network)
    patcher.setattr(QNetworkAccessManager, "post", _no_network)

    module = sys.modules.get("item_database_app")
    if module is None:
        spec = importlib.util.spec_from_file_location("item_database_app", APP_PY)
        module = importlib.util.module_from_spec(spec)
        sys.modules["item_database_app"] = module
        spec.loader.exec_module(module)

    cache_root = tmp_path_factory.mktemp("armory_theme_cache")
    patcher.setattr(module, "ICON_CACHE_DIR", cache_root / "icons")
    patcher.setattr(module, "DETAIL_CACHE_DIR", cache_root / "details")
    patcher.setattr(module.IconCache, "request", lambda self, url: None)
    patcher.setattr(module.ItemDetailCache, "request", lambda self, item_id: None)

    yield module

    module.apply_theme(theme.DEFAULT_THEME)
    patcher.undo()


@pytest.fixture(scope="module")
def windows(qapp, armory_module):
    """The three top-levels the Armory can put on screen, all open at once.

    Built once and reused for every theme: each one is a few thousand
    widgets, and a theme switch re-resolves the sheet against all of them
    (the expensive half of this module).  Torn down properly -- the
    pending ``QTimer.singleShot(0, _request_visible_icons)`` that
    ItemDatabaseWindow arms in ``__init__`` is drained by the settle below
    while the window is still alive, so it cannot fire into a deleted C++
    object during teardown.
    """
    database = armory_module.create_window(parent=None, language="en")
    database.resize(1400, 820)
    database.show()
    _settle(qapp)

    loadout = database.ensure_loadout_window()
    loadout.resize(1500, 900)
    loadout.show()
    _settle(qapp)

    database.open_crafting_calculator()
    crafting = database._crafting_window
    crafting.resize(1400, 860)
    crafting.show()
    _settle(qapp)

    yield {"item database": database, "build planner": loadout, "crafting": crafting}

    # Same teardown the rest of the suite uses (it pumps DeferredDelete
    # twice with a gc.collect() between, which is what actually frees a
    # PySide widget tree).  Three Armory windows are ~1,700 widgets, and
    # every later app-wide restyle would pay for them.
    for window in (crafting, loadout, database):
        destroy_window(window)
    _settle(qapp, 120)


@pytest.fixture(autouse=True)
def _abyss_after(armory_module):
    yield
    armory_module.apply_theme(theme.DEFAULT_THEME)


# ---------------------------------------------------------------------------
# 1. the template renders
# ---------------------------------------------------------------------------


def test_the_hand_written_sheet_is_gone():
    """MASTER §4-2, applied to the Armory: one sheet, generated.  A
    reappearing styles.qss is a second source of truth for 190 selectors."""
    assert not (ROOT / "ItemDatabase" / "styles.qss").exists()
    assert TEMPLATE.is_file()


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_every_theme_renders_the_armory_template(name):
    qss = _rendered(name)
    assert len(qss) > 20000, "the Armory sheet rendered suspiciously small"
    assert "{{" not in _without_comments(qss), "unsubstituted placeholder left in the output"
    assert "}}" not in _without_comments(qss)
    assert "ASSET_PATH" not in qss
    assert "/QA_ASSETS/assets/ui/dropdown_arrow.png" in qss, "the one url() lost its asset path"
    assert theme.THEMES[name].accent in qss, f"{name}: the accent never appears in the sheet"


def test_the_template_is_not_scoped_to_the_app_sheets_property():
    """The inverse of tests/test_app_sheet_isolation.

    The application sheet prefixes every rule with the ``aion2`` property
    selector so it cannot reach the Armory's parentless windows.  This
    sheet is applied TO those windows, so the same prefix here would match
    nothing at all.
    """
    for selector, _ in _rules(_rendered("abyss")):
        assert "aion2" not in selector, f"the Armory sheet scoped a rule: {selector}"


# ---------------------------------------------------------------------------
# 2. nothing lost in the port
# ---------------------------------------------------------------------------


def test_the_legacy_selector_snapshot_looks_real():
    legacy = _legacy_selectors()
    assert len(legacy) > 150, f"the snapshot itself looks truncated ({len(legacy)})"
    assert "#PantheonColossusSlot" in legacy
    assert "QComboBox QAbstractItemView" in legacy


def test_the_template_keeps_every_legacy_selector():
    """Porting must not silently drop a widget's styling."""
    ported = {selector for selector, _ in _rules(_rendered("abyss"))}
    missing = sorted(_legacy_selectors() - ported)
    assert not missing, f"selectors lost in the port: {missing}"


def test_the_template_styles_the_object_names_this_wave_added():
    """The other direction: the 93 inline sheets became rules, and a rule
    with no objectName behind it is an unstyled widget."""
    ported = {selector for selector, _ in _rules(_rendered("abyss"))}
    for selector in (
        "#TransparentPane", "#GradeTileName", "#SubstatSectionHeader",
        "#TooltipTitle", "#TooltipStatusPill", "#ArcanaSeasonButton",
        "#ArcanaThemeOption", "#EquipItemIconLabel", "#CompareValueBetter",
        "#SkillTypeBadge", "#TierComboPopup", "#CraftMenuRow",
    ):
        assert selector in ported, f"{selector} is set in app.py but never styled"


def test_every_data_colour_the_armory_sets_has_a_rule():
    """``_set_data_color(w, kind, key)`` is only as good as the rule behind
    it: a kind the sheet has no ``*[dataColor="kind:key"]`` rule for is a
    widget that silently keeps its inherited colour."""
    source = APP_PY.read_text(encoding="utf-8")
    kinds = set(re.findall(r'_set_data_color\([^,]+,\s*"([a-z_]+)"', source))
    assert kinds, "no _set_data_color call sites found — did the helper get renamed?"
    template = TEMPLATE.read_text(encoding="utf-8")
    for kind in sorted(kinds):
        for key in theme.data_color_keys(kind):
            needle = f'[dataColor="{kind}:{key}"]'
            assert needle in template, f"nothing in the sheet colours {needle}"


# ---------------------------------------------------------------------------
# 3. the two rules this sheet must never have
# ---------------------------------------------------------------------------

#: The item views where a QSS ``color`` really does beat each item's own
#: ``setForeground()`` -- a combo popup.  That is the case the 2026-08-29
#: user report was about, and the case the hand-written sheet had a comment
#: about; this sheet still declares ``color`` on ``QTableView`` and
#: ``QListWidget`` (it always has), and there the item's own brush wins --
#: which is not taken on trust either, it is measured in pixels by
#: ``test_a_rarity_foreground_survives_the_sheet`` below.
_ITEM_VIEW_SELECTORS = (
    "QComboBox QAbstractItemView",
    "QComboBox QAbstractItemView::item",
    "QAbstractItemView",
    "QTreeView",
    "QListView::item", "QListWidget::item", "QTableView::item", "QTreeView::item",
)


@pytest.mark.parametrize("name", sorted(theme.THEMES))
@pytest.mark.parametrize("bare", _ITEM_VIEW_SELECTORS)
def test_no_colour_on_an_item_view(name, bare):
    """The 2026-08-29 fix, re-gated on this side of the deletion.

    ``ItemDatabase/styles.qss`` removed exactly this declaration with the
    user report attached ("Grade/Rarity dropdown items showed plain white
    instead of their per-rarity color").  It was pinned by
    tests/test_app_sheet_isolation.py against that file; the file is a
    template now, so the assertion moved here.
    """
    for selector, declarations in _rules(_rendered(name)):
        if selector != bare:
            continue
        assert not _declares(declarations, "color"), (
            f"{name}: 'color' on '{selector}' flattens every item's own "
            f"setForeground() — put it on an objectName-scoped rule instead"
        )


def test_the_armory_sheet_still_declares_no_font_family():
    """Review F-0b, re-gated the same way.

    The app sheet's own gate asserts every ``font-family`` it declares is
    scoped so it cannot reach here; that only holds while the Armory does
    not retype itself either.  MASTER's deferred decision ("app.setFont()
    as the base-font vehicle, after the Armory wave") is the host's to
    make -- this wave moved colours, not metrics.
    """
    assert "font-family" not in _without_comments(TEMPLATE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 4. contrast, on the pairs this sheet actually produces
# ---------------------------------------------------------------------------

#: Rarity text lands on cards, table rows and popups -- three surfaces.
_TEXT_GROUNDS = ("bg_elevated", "bg_surface", "bg_overlay")

#: MASTER §2 gives 3:1 for non-body text (badges, pills, single words).
#: A grade colour is game DATA: if one ever failed here the fix is a softer
#: chip behind it, never a different rarity colour.
_DATA_TEXT_MIN = 3.0


@pytest.mark.parametrize("name", sorted(theme.THEMES))
@pytest.mark.parametrize("grade", theme.data_color_keys("item_grade"))
@pytest.mark.parametrize("ground", _TEXT_GROUNDS)
def test_every_rarity_reads_on_every_surface(name, grade, ground):
    tokens = theme.THEMES[name]
    ratio = theme.contrast_ratio(theme.data_color("item_grade", grade), getattr(tokens, ground))
    assert ratio >= _DATA_TEXT_MIN, (
        f"{name}: {grade} on {ground} is {ratio:.2f}:1 — a rarity colour is "
        f"game data, so give it a *.soft chip background rather than a new hue"
    )


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_every_other_data_colour_reads_too(name):
    """The rest of the tables the Armory colours text with."""
    tokens = theme.THEMES[name]
    worst = []
    for kind in ("skill_type", "craft_method", "arcana_theme", "arcana_category",
                 "genius_board", "role", "damage_type", "gear_type"):
        for key in theme.data_color_keys(kind):
            ratio = theme.contrast_ratio(theme.data_color(kind, key), tokens.bg_elevated)
            if ratio < _DATA_TEXT_MIN:
                worst.append(f"{kind}:{key} = {ratio:.2f}:1")
    assert not worst, f"{name}: data colours below {_DATA_TEXT_MIN}:1 on bg.elevated: {worst}"


# ---------------------------------------------------------------------------
# 5. the pixels
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_every_theme_renders_all_three_windows(qapp, armory_module, windows, name):
    """MASTER §4-5's render gate, pointed at the Armory.

    One theme switch, three grabs, and the same three questions the app's
    own gate asks: does it raise, is any of it Fusion grey, and is the
    sheet that produced it really this theme's.
    """
    restyled = armory_module.apply_theme(name)
    assert restyled >= 3, f"apply_theme restyled {restyled} windows, expected 3"
    _settle(qapp, 250)

    accent = theme.THEMES[name].accent
    for label, window in windows.items():
        assert accent in window.styleSheet(), (
            f"{name}/{label}: the window's sheet does not carry the theme accent"
        )
        pixmap = window.grab()            # raises if rendering fails
        assert not pixmap.isNull(), f"{name}/{label}: grab produced nothing"
        assert pixmap.width() > 500 and pixmap.height() > 400

        offenders = {hex(c): n for c, n in _grey_histogram(pixmap.toImage()).items()
                     if n > MAX_GREY_PIXELS}
        assert not offenders, (
            f"{name}/{label}: Fusion default surfaces {offenders} — a widget "
            f"the stylesheet did not reach"
        )


def test_the_window_ground_is_the_theme_token(qapp, armory_module, windows):
    """The cheapest proof a grab is of a themed window at all.

    The Item Database window's ground used to be a 4-stop diagonal gradient
    from a 24-hex per-theme table; it is one token now
    (GradientBackground.paintEvent).
    """
    database = windows["item database"]
    for name in sorted(theme.THEMES):
        armory_module.apply_theme(name)
        _settle(qapp, 200)
        image = database.grab().toImage()
        expected = theme.qcolor(name, "bg.window").rgb() & 0xFFFFFF
        corner = image.pixel(3, image.height() - 4) & 0xFFFFFF
        assert corner == expected, (
            f"{name}: the Armory ground is {hex(corner)}, expected {hex(expected)}"
        )


def test_a_rarity_foreground_survives_the_sheet(qapp, armory_module, windows):
    """MASTER §4-8, measured in pixels rather than in selectors.

    A ``color`` anywhere on an item view would repaint this row in the
    view's text colour, and the string-level gate above would still pass if
    the declaration arrived through some *other* selector (a
    ``QWidget``-level rule, a sub-control, a future edit).  So: put a real
    row in the real model with a Legend foreground, grab the viewport, and
    look for that exact colour.
    """
    database = windows["item database"]
    armory_module.apply_theme("abyss")
    legend = theme.data_color("item_grade", "Legend")

    # Every filter to "off" first: this window shares a process with the
    # other Armory tests, and a single active filter pill would hide the
    # row and turn this into a mystery about pixels.
    database.proxy.set_search("")
    database.proxy.set_grade("All")
    database.proxy.set_shop("All")
    database.proxy.set_gear_types(set())
    database.proxy.set_group_categories(None)
    database.proxy.set_subcategory_categories(None)

    row = [QStandardItem("") for _ in range(database.model.columnCount())]
    row[2].setText("QA Legend Blade")
    row[2].setForeground(QBrush(QColor(legend)))
    database.model.appendRow(row)
    try:
        _settle(qapp, 400)
        assert database.proxy.rowCount() > 0, "the QA row was filtered out of the view"
        database.table.scrollToTop()
        _settle(qapp, 120)
        image = database.table.viewport().grab().toImage()
        hits = _exact_pixels(image, legend)
        assert hits > 20, (
            f"only {hits} pixels of the Legend colour in the table — a QSS "
            f"`color` on the item view has flattened setForeground() again "
            f"(User-reported 2026-08-29)"
        )
        assert database.model.item(0, 2).foreground().color().name() == legend
    finally:
        database.model.removeRow(0)


def test_apply_theme_restyles_a_window_that_is_already_open(qapp, armory_module, windows):
    """The seam the host uses.

    The Armory's windows are parentless, so they are outside both Qt's
    stylesheet cascade and the app sheet's scope: a theme switch has to
    re-render and re-SET the sheet on each of them, which is what
    ``module.apply_theme(name)`` does and why the host has to call it.
    """
    loadout = windows["build planner"]
    armory_module.apply_theme("abyss")
    _settle(qapp, 120)
    assert theme.THEMES["abyss"].accent in loadout.styleSheet()

    assert armory_module.apply_theme("inferno") >= 3
    _settle(qapp, 120)
    assert theme.THEMES["inferno"].accent in loadout.styleSheet()
    assert theme.current() == "inferno"

    # Not "the old accent is absent": Abyss's cyan is also the `active`
    # skill-type DATA colour, which every theme's sheet carries by design.
    # So the check is on a rule that takes the accent TOKEN.
    gearscore = next(
        declarations for selector, declarations in _rules(loadout.styleSheet())
        if selector == "#GearScoreHeaderLabel"
    )
    assert theme.THEMES["inferno"].accent in gearscore
    assert theme.THEMES["abyss"].accent not in gearscore


def test_the_host_seam_also_restyles_every_window(qapp, armory_module, windows):
    """``ItemDatabaseWindow.set_theme`` is the seam MainWindow already calls
    (main_window.py's ``apply_theme``), so it must reach the other two
    windows too -- not just the one it is called on."""
    database = windows["item database"]
    database.set_theme("void")
    _settle(qapp, 120)
    for label, window in windows.items():
        assert theme.THEMES["void"].accent in window.styleSheet(), label


def test_property_driven_rules_are_repolished_on_a_theme_switch(qapp, armory_module, windows):
    """Qt does not re-evaluate ``[dataColor=…]`` against a widget that has
    already computed its style, so apply_theme() repolishes.  Checked
    through a widget that really carries the property."""
    loadout = windows["build planner"]
    armory_module.apply_theme("emerald")
    _settle(qapp, 120)
    tagged = [
        widget for widget in loadout.findChildren(QWidget)
        if widget.property("dataColor")
    ]
    assert tagged, "no widget in the Build Planner carries a dataColor property"
    assert all(":" in str(widget.property("dataColor")) for widget in tagged)


def test_the_fallback_renderer_understands_the_same_template(armory_module, monkeypatch):
    """Step 3 of app.py's optional ``core.theme`` import.

    Without core.theme there is no token engine, so app.py renders the
    template itself from ``_FALLBACK_TOKENS``.  That stand-in duplicates
    two placeholder forms, and a template that outgrew it would ship a
    standalone build full of literal ``{{...}}`` strings.
    """
    monkeypatch.setattr(armory_module, "_theme", None)
    rendered = armory_module._render_qss(
        TEMPLATE.read_text(encoding="utf-8"), "/QA_ASSETS"
    )
    assert "{{" not in _without_comments(rendered)
    assert "ASSET_PATH" not in rendered
    assert armory_module._FALLBACK_TOKENS["accent"] in rendered
    # and a data colour resolves to the readable grey, not to a crash
    assert armory_module._FALLBACK_TOKENS["fg_muted"] in rendered
