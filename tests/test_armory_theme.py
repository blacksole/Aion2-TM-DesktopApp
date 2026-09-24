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

import ast
import importlib.util
import json
import re
import sys
from array import array
from pathlib import Path

import pytest
from PySide6.QtCore import QDeadlineTimer, QEventLoop
from PySide6.QtGui import QBrush, QColor, QCursor, QImage, QStandardItem
from PySide6.QtWidgets import QWidget

from core import theme
from tests.conftest import destroy_window

ROOT = Path(__file__).resolve().parent.parent
APP_PY = ROOT / "ItemDatabase" / "app.py"
TEMPLATE = ROOT / "ItemDatabase" / "styles.template.qss"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
LEGACY_SELECTORS = FIXTURES / "armory_legacy_selectors.txt"
DEAD_SELECTORS = FIXTURES / "armory_dead_selectors.txt"
ABYSS_DECLARATIONS = FIXTURES / "armory_abyss_declarations.json"

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


def test_every_objectname_rule_has_a_widget_that_sets_it():
    """A rule with no ``setObjectName`` behind it is an UNSTYLED WIDGET.

    Review G (B1/B2/M7): this test used to assert the opposite direction —
    it read the rendered sheet, checked a hand-written list of ids against
    *that same sheet*, and reported "set in app.py but never styled".  So
    it compared the author's rule to the author's rule, and passed while
    naming two of the three widgets that had shipped unstyled
    (``#TooltipStatusPill``, ``#EquipItemIconLabel``, and
    ``#SimGradeLabel``: each got a rule, none got its id).  Two of the
    three lost geometry, on a style-only brief.

    Derived from the template rather than hand-maintained, so a new rule
    cannot be added without its call site.  Matching on the bare quoted
    name, not on ``setObjectName("…")``: several ids are set through a
    lookup table or a variable (``_ROLE_BUTTON_OBJECT_NAMES``, the Pantheon
    slot styles, ``#SubstatRow``/``#SubstatRowCompact``,
    ``#CompareValueBetter``/``Worse``) and are not dead.
    """
    source = APP_PY.read_text(encoding="utf-8")
    ids = set()
    for selector, _ in _rules(_rendered("abyss")):
        for part in selector.split():
            if part.startswith("#"):
                ids.add(part.lstrip("#").split(":")[0].split("[")[0])
    assert len(ids) > 100, f"only {len(ids)} objectName rules found — wrong parse?"

    known_dead = {
        line.strip()
        for line in DEAD_SELECTORS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    dead = sorted(name for name in ids if f'"{name}"' not in source)
    assert not set(dead) - known_dead, (
        "template rules whose objectName is never set anywhere in app.py: "
        f"{sorted(set(dead) - known_dead)} — each one is a widget rendering "
        f"unstyled.  Wire it up, or add it to {DEAD_SELECTORS.name} with a reason."
    )
    assert not known_dead - set(dead), (
        f"{DEAD_SELECTORS.name} lists ids that are wired up now — delete the "
        f"stale entries: {sorted(known_dead - set(dead))}"
    )


def test_no_call_site_passes_a_colour_where_a_data_key_belongs():
    """Review G (M4): ``_set_data_color(head, "skill_type", skill_type)``
    read a parameter that two call sites still filled with
    ``_SKILL_TYPE_COLORS["active"]``, so the property landed as
    ``dataColor="skill_type:#22d3ee"`` and matched no rule in any theme.

    The test above enumerates *legitimate* keys out of
    ``theme.data_color_keys``, so it validates the rules and can never see
    a bogus key.  This one reads the call sites: any literal third argument
    must be a real key of that kind, and a non-literal (a variable) must
    not be a colour-shaped expression.
    """
    source = APP_PY.read_text(encoding="utf-8")
    calls = re.findall(r'_set_data_color\(\s*[^,]+,\s*"([a-z_]+)"\s*,\s*([^)]+)\)', source)
    assert len(calls) >= 15, f"only {len(calls)} _set_data_color call sites parsed"
    for kind, argument in calls:
        argument = argument.strip()
        assert kind in theme._DATA_COLORS, f"unknown data kind at a call site: {kind}"
        literal = re.fullmatch(r'"([^"]*)"', argument)
        if literal:
            assert literal.group(1) in theme.data_color_keys(kind), (
                f'_set_data_color(..., "{kind}", "{literal.group(1)}") — not a key of '
                f"that table; the rule it needs does not exist"
            )
            continue
        assert "COLORS[" not in argument and "#" not in argument, (
            f'_set_data_color(..., "{kind}", {argument}) looks like a COLOUR, and this '
            f"helper takes a data KEY (review G, M4)"
        )


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
# ---------------------------------------------------------------------------
# 2b. the VALUES, not just the selector names
# ---------------------------------------------------------------------------


def _declaration_map(qss: str) -> dict[str, dict[str, str]]:
    """``{selector: {property: value}}``, whitespace-normalised."""
    out: dict[str, dict[str, str]] = {}
    for selector, declarations in _rules(qss):
        props = {}
        for declaration in declarations.split(";"):
            if ":" not in declaration:
                continue
            name, _, value = declaration.partition(":")
            props[" ".join(name.split())] = " ".join(value.split())
        out.setdefault(selector, {}).update(props)
    return out


def test_the_abyss_render_matches_the_replayed_legacy_sheet():
    """Review G (M9): the port's central claim, made falsifiable.

    The template header claims that for Abyss, everything outside its
    nearest-token map renders byte-for-byte as the hand-written sheet did.
    That was true and *unfalsifiable in CI*, because the sheet it refers to
    was deleted in the same commit: the selector NAMES survived as a
    snapshot, the VALUES did not.

    ``armory_abyss_declarations.json``'s ``legacy`` half closes that: it is
    not a snapshot of this render, it is generated by replaying the
    documented substitution map onto ``git show
    eb53cd6:ItemDatabase/styles.qss``.  A failure here therefore means the
    render drifted from the deleted sheet, not merely from yesterday.
    """
    fixture = json.loads(ABYSS_DECLARATIONS.read_text(encoding="utf-8"))
    assert fixture["theme"] == "abyss" and fixture["source_revision"]
    rendered = _declaration_map(theme.build_qss_from(
        TEMPLATE, fixture["theme"], asset_path=fixture["asset_path"]
    ))
    expected = fixture["legacy"]
    assert len(expected) == 190, "the legacy half of the fixture looks truncated"

    for selector, properties in sorted(expected.items()):
        assert selector in rendered, f"legacy selector lost: {selector}"
        assert rendered[selector] == properties, (
            f"{selector} drifted from the sheet it replaced:\n"
            + "\n".join(
                f"  {prop}: was {properties.get(prop)!r}, now {rendered[selector].get(prop)!r}"
                for prop in sorted(set(properties) | set(rendered[selector]))
                if properties.get(prop) != rendered[selector].get(prop)
            )
        )


def test_the_rules_that_replaced_the_inline_sheets_are_pinned_too():
    """The other half of the fixture: the 228 rules with no pre-image.

    They cannot be checked against anything, so they are pinned as a change
    detector — an intentional edit updates the fixture and shows up in the
    diff, which is exactly what the pink→violet substat drift (review G,
    M10) needed and did not have.
    """
    fixture = json.loads(ABYSS_DECLARATIONS.read_text(encoding="utf-8"))
    rendered = _declaration_map(theme.build_qss_from(
        TEMPLATE, fixture["theme"], asset_path=fixture["asset_path"]
    ))
    added = {s: d for s, d in rendered.items() if s not in fixture["legacy"]}
    assert added == fixture["added"], (
        "the rules added by the tokenization wave changed:\n"
        + "\n".join(
            f"  {selector}: was {fixture['added'].get(selector)}, now {added.get(selector)}"
            for selector in sorted(set(added) | set(fixture["added"]))
            if added.get(selector) != fixture["added"].get(selector)
        )
    )


def test_the_fixture_covers_the_whole_sheet():
    """Neither half may quietly stop covering a rule."""
    fixture = json.loads(ABYSS_DECLARATIONS.read_text(encoding="utf-8"))
    rendered = _declaration_map(theme.build_qss_from(
        TEMPLATE, fixture["theme"], asset_path=fixture["asset_path"]
    ))
    assert set(rendered) == set(fixture["legacy"]) | set(fixture["added"])


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


def test_the_equipped_item_plate_really_wears_the_rarity_ring(qapp, armory_module, windows):
    """Review G (B2), measured where it broke.

    The plate is a 36x36 pixmap-only QLabel whose rarity signal is a 2 px
    ``border-color`` from the item's grade.  It shipped with the rule
    written and ``setObjectName("EquipItemIconLabel")`` missing, so the
    only rule still matching was the generic ``*[dataColor=…] { color: … }``
    — which does nothing at all to a label that holds no text.  A name
    check could not see that; the ring is a pixel fact, so this counts
    pixels on the plate's own edge.

    Driven through the same helper the equip panel uses rather than through
    the equip flow itself: ``ItemDatabase/data`` is absent in this clone, so
    no item can actually be equipped, and the property pair is exactly what
    ``_refresh_equip_item_panel`` sets.
    """
    loadout = windows["build planner"]
    plate = loadout.equip_item_icon_label
    assert plate.objectName() == "EquipItemIconLabel", (
        "the plate lost its objectName — every rule below it is dead again"
    )
    armory_module.apply_theme("abyss")
    _settle(qapp, 120)

    def edge_hits(colour: str) -> int:
        image = plate.grab().toImage()
        width, height = image.width(), image.height()
        edge = []
        for x in range(width):
            edge += [image.pixel(x, 0), image.pixel(x, 1),
                     image.pixel(x, height - 1), image.pixel(x, height - 2)]
        for y in range(height):
            edge += [image.pixel(0, y), image.pixel(1, y),
                     image.pixel(width - 1, y), image.pixel(width - 2, y)]
        target = QColor(colour).rgb() & 0xFFFFFF
        return sum(1 for pixel in edge if (pixel & 0xFFFFFF) == target)

    plate.setProperty("variant", "")
    armory_module._set_data_color(plate, "item_grade", "Legend")
    _settle(qapp, 150)
    legend_hits = edge_hits(theme.data_color("item_grade", "Legend"))
    assert legend_hits > 60, (
        f"only {legend_hits} edge pixels carry the Legend colour — the 2 px "
        f"rarity ring is not being drawn on the plate"
    )

    # ...and it is the GRADE that decides it, not a constant.
    armory_module._set_data_color(plate, "item_grade", "Rare")
    _settle(qapp, 150)
    assert edge_hits(theme.data_color("item_grade", "Rare")) > 60
    assert edge_hits(theme.data_color("item_grade", "Legend")) < 10

    # An empty slot drops the ring and the ground entirely (variant="empty").
    plate.setProperty("variant", "empty")
    armory_module._set_data_color(plate, "item_grade", None)
    _settle(qapp, 150)
    assert edge_hits(theme.data_color("item_grade", "Rare")) < 10


def test_the_daevanion_status_pill_is_styled(qapp, armory_module, windows):
    """Review G (B1): the five-state pill had its rule and no objectName,
    so it rendered as bare inherited text — no ground, no state colour, and
    no padding or radius, which is geometry lost on a style-only brief."""
    tooltip = armory_module.DaevanionNodeTooltip()
    try:
        assert tooltip._status_label.objectName() == "TooltipStatusPill"
        tooltip.setStyleSheet(_rendered("abyss"))
        for state, token in (
            ("start", "accent"), ("active", "accent"), ("available", "ok"),
            ("locked", "fg_muted"), ("no_points", "danger"),
        ):
            label = tooltip._status_label
            label.setText("QA")
            label.setProperty("status", state)
            label.style().unpolish(label)
            label.style().polish(label)
            _settle(qapp, 80)
            image = label.grab().toImage()
            expected = getattr(theme.THEMES["abyss"], token)
            # The pill's ground is that state's colour at a low alpha over
            # the tooltip, so look for the TEXT colour, which is solid.
            assert _exact_pixels(image, expected) > 5, (
                f"status={state}: no {token} pixels on the pill"
            )
    finally:
        tooltip.deleteLater()
        _settle(qapp, 80)


def test_daevanion_tooltip_content_updates_across_consecutive_hovers(qapp, armory_module, windows):
    """User-reported, 2026-09-23 (Screenshots): sweeping the mouse across
    several Daevanion nodes kept showing only the FIRST hovered node's
    content, even though the tooltip's on-screen POSITION correctly
    followed the mouse the whole time.

    That split (position right, content stuck) points straight at
    DaevanionBoardCanvas.mouseMoveEvent -> _daevanion_on_node_hovered ->
    _daevanion_show_tooltip, which calls set_node() + show_at() on the
    SAME already-visible tooltip instance for every new node -- there is
    no hide() between hovers. show_at() always calls move()+show(), which
    Qt/Windows always processes; set_node()'s setText() calls only
    scheduled the child QLabels for an update AT SOME POINT, on an
    already-visible, WA_TranslucentBackground top-level (Qt.ToolTip flag)
    window -- exactly the situation where Windows' DWM compositing can
    reuse an already-composited frame for the popup and never actually
    repaint the new label text into it, since nothing forced a synchronous
    redraw. Grabbing the widget's pixels (not just reading .text()) is the
    point: .text() reflects what setText() was TOLD, not what actually got
    painted onto that composited surface -- a stale-content bug like this
    would otherwise slip through checks that only assert on the Qt object
    model."""
    tooltip = armory_module.DaevanionNodeTooltip()
    try:
        tooltip.set_node("First Node", "Legend", "Legend", 3, 10, [], "available", "OK")
        tooltip.show_at(QCursor.pos())
        _settle(qapp, 80)
        first_image = tooltip._title_label.grab().toImage()

        tooltip.set_node("Second Node", "Legend", "Legend", 3, 10, [], "available", "OK")
        tooltip.show_at(QCursor.pos())
        _settle(qapp, 80)

        assert tooltip._title_label.text() == "Second Node"
        second_image = tooltip._title_label.grab().toImage()
        assert second_image != first_image, (
            "the title label's PAINTED pixels are unchanged across two "
            "consecutive hovers, even though .text() reports the new node "
            "-- the widget was told about the new content but never "
            "actually repainted it (the reported bug)"
        )
    finally:
        tooltip.hide()
        tooltip.deleteLater()
        _settle(qapp, 80)


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


def test_every_data_colour_a_real_widget_carries_is_a_real_key(qapp, armory_module, windows):
    """Review G (M4), caught where a static read cannot reach.

    ``_build_category_column``'s second parameter became a data KEY when
    its body became ``_set_data_color(head, "skill_type", skill_type)``, but
    its two call sites still passed ``_SKILL_TYPE_COLORS["active"]``.  The
    property landed as ``dataColor="skill_type:#22d3ee"`` — a value no rule
    in any theme matches — and neither the rule-side gate (which enumerates
    *legitimate* keys) nor a call-site regex on ``_set_data_color`` itself
    (the colour arrives through a parameter) could see it.

    Asking the widgets closes it: every ``dataColor`` a built widget
    actually carries must name a kind and a key this theme engine knows.
    The four card tooltips are built explicitly because they are created on
    demand and would otherwise be outside every window's child tree — and
    the Arcana one is exactly where M4 lived.
    """
    tooltips = [
        armory_module.DaevanionNodeTooltip(),
        armory_module.SkillInfoTooltip(),
        armory_module.ArcanaCardTooltip(),
        armory_module.ArcanaSetBonusTooltip(),
    ]
    try:
        roots = list(windows.values()) + tooltips
        seen = []
        for root in roots:
            for widget in [root] + root.findChildren(QWidget):
                value = widget.property("dataColor")
                if not value:
                    continue
                value = str(value)
                seen.append((widget.objectName(), value))
                assert ":" in value, f"malformed dataColor {value!r}"
                kind, _, key = value.partition(":")
                assert kind in theme._DATA_COLORS, (
                    f"#{widget.objectName()} carries dataColor={value!r} — "
                    f"{kind!r} is not a data-colour table"
                )
                assert key in theme.data_color_keys(kind), (
                    f"#{widget.objectName()} carries dataColor={value!r} — "
                    f"{key!r} is not a key of {kind!r}, so no rule matches it "
                    f"(a colour passed where a KEY belongs?)"
                )
        # Nine today: the rarity filter pills and the Arcana tooltip's two
        # column heads.  Most data-coloured widgets live in panels built on
        # demand (a selected item, a hovered node), so this floor is a
        # "did we walk a real tree at all" check, not a census.
        assert len(seen) >= 8, f"only {len(seen)} data-coloured widgets found — wrong tree?"
        assert any(kind.startswith("skill_type") for _name, kind in seen), (
            "no skill_type data colour was set by any widget — the Arcana card "
            "tooltip's ACTIVE/PASSIVE headings are where M4 lived"
        )
    finally:
        for tooltip in tooltips:
            tooltip.deleteLater()
        _settle(qapp, 80)


def test_the_standalone_spec_bundles_what_the_app_reads():
    """Review G (M6): a datas DESTINATION is part of the read path.

    ``_bundled_resource()`` is ``Path(sys._MEIPASS) / "ItemDatabase" /
    name``, so a file bundled to ``'.'`` lands one level too shallow and
    ``_load_qss_text()`` returns ``""`` — an unstyled window, logged as a
    warning, no error.  That is the 2026-08-27 regression this module's own
    docstring memorializes, and the standalone spec had re-laid it.

    Read as text rather than executed: a .spec is Python evaluated by
    PyInstaller with its own globals (``SPECPATH``), so ast is the honest
    way to inspect one from a test.
    """
    spec_text = (ROOT / "ItemDatabase" / "AION2_ItemDatabase.spec").read_text(encoding="utf-8")
    tree = ast.parse(spec_text)
    datas = None
    hidden = None
    pathex = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Analysis":
            for keyword in node.keywords:
                if keyword.arg == "datas":
                    datas = [tuple(ast.literal_eval(e)) for e in keyword.value.elts]
                elif keyword.arg == "hiddenimports":
                    hidden = ast.literal_eval(keyword.value)
                elif keyword.arg == "pathex":
                    pathex = keyword.value
    assert datas, "the standalone spec bundles nothing"

    for source, destination in datas:
        assert destination == "ItemDatabase" or destination.startswith("ItemDatabase/"), (
            f"({source!r}, {destination!r}): frozen, app.py reads its files from "
            f"_MEIPASS/ItemDatabase — this destination is unreachable"
        )
        assert (ROOT / "ItemDatabase" / source).exists(), f"{source} does not exist"

    destinations = {d for _s, d in datas}
    assert "ItemDatabase" in destinations, "the stylesheet template is not bundled"
    assert ("styles.template.qss", "ItemDatabase") in datas
    assert "ItemDatabase/assets" in destinations, (
        "assets/ is not bundled — the sheet's one url() (the combo dropdown "
        "arrow) cannot resolve"
    )

    assert hidden and "core.theme" in hidden, (
        "core.theme is the owner of every token this app renders; without it "
        "the exe runs on _FALLBACK_TOKENS and shows no rarity colours"
    )
    # pathex must not be a CWD-relative string: PyInstaller resolves it
    # against the build directory, not against the spec.
    assert pathex is not None
    literals = [n for n in ast.walk(pathex) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not any(value.value in ("..", ".") for value in literals), (
        "pathex is CWD-relative — build it from SPECPATH instead"
    )
    assert "SPECPATH" in spec_text


def test_the_shipping_spec_puts_the_armory_files_where_it_reads_them():
    """The spec that actually ships (``scripts/build_exe.bat`` and the
    release workflow build only this one).  Same invariant, and the reason
    M6 was capped at MAJOR: this one was already right."""
    spec_text = (ROOT / "Aion2 TM.spec").read_text(encoding="utf-8")
    tree = ast.parse(spec_text)
    datas = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Analysis":
            for keyword in node.keywords:
                if keyword.arg == "datas":
                    datas = [tuple(ast.literal_eval(e)) for e in keyword.value.elts]
    armory = [(s, d) for s, d in datas if s.startswith("ItemDatabase")]
    assert armory, "the shipping spec bundles no Armory files at all"
    for source, destination in armory:
        assert destination == "ItemDatabase" or destination.startswith("ItemDatabase/"), (
            f"({source!r}, {destination!r}) is outside _MEIPASS/ItemDatabase"
        )
    assert ("ItemDatabase/styles.template.qss", "ItemDatabase") in armory
    assert ("ItemDatabase/assets", "ItemDatabase/assets") in armory
    assert not any(source.endswith("styles.qss") for source, _d in armory), (
        "the deleted hand-written sheet is still named in the shipping spec"
    )


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
