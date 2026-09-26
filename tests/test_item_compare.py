"""Item Compare: the contract, and the window that shows it.

Planner "Item-Vergleich", 2026-09-24.  Design: Obsidian vault,
``Design/Konzept - Item-Vergleich.md``.

Two halves, split the way the work is split:

* ``armory_engine.compare`` -- Qt-free.  The formatter both sides share,
  and ``ItemComparison.swapped()``.  (``build_item_comparison`` is
  @developer's and is exercised here only as far as the window needs it.)
* ``ItemCompareDialog`` -- the window.  It must paint what the comparison
  says and decide nothing: these tests hand it a comparison whose winners
  CONTRADICT the numbers, and check that the window follows the winners.
  That is the property that keeps the window and the logic from ever
  disagreeing about a rounded tie.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ItemDatabase"))

from armory_engine.compare import (  # noqa: E402
    ItemComparison,
    StatComparison,
    StatValue,
    format_signed,
    format_stat_value,
)

from core import theme  # noqa: E402
from tests.conftest import destroy_window  # noqa: E402

APP_PY = ROOT / "ItemDatabase" / "app.py"


# ---------------------------------------------------------------------------
# 1. the shared formatter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("value", "percent", "expected"),
    [
        (742, False, "742"),
        (742.0, False, "742"),
        (3.5, True, "3.5%"),
        (12.25, True, "12.25%"),
        (3.50, True, "3.5%"),
        (0, True, "0%"),
    ],
)
def test_values_keep_their_fractions_but_not_trailing_zeros(value, percent, expected):
    # _format_number would round 3.5% to "4%" -- the cached details really
    # carry 3.5% / 12.25% values (AbnormalResistance, DefenseRatio, ...).
    assert format_stat_value(value, percent) == expected


def test_deltas_always_carry_a_sign_and_a_real_minus():
    assert format_signed(85) == "+85"
    assert format_signed(-85) == "−85"  # U+2212, as wide as the plus
    assert format_signed(0) == "±0"
    assert format_signed(0.001, percent=True) == "±0%"  # rounds to nothing


# ---------------------------------------------------------------------------
# 2. swapping mirrors, never recomputes
# ---------------------------------------------------------------------------

def _row(stat_id, a, b, winner, percent=False, low_a=None, low_b=None):
    return StatComparison(
        stat_id=stat_id, name=stat_id,
        a=None if a is None else StatValue(high=a, low=low_a),
        b=None if b is None else StatValue(high=b, low=low_b),
        percent=percent, winner=winner,
    )


def _comparison(**overrides):
    base = dict(
        item_a={"id": 1, "name": "Alpha Blade", "grade": "Epic", "categoryName": "Sword", "level": 40},
        item_b={"id": 2, "name": "Beta Blade", "grade": "Unique", "categoryName": "Sword", "level": 45},
        main=[
            _row("Attack", 661, 776, "b", low_a=489, low_b=574),
            _row("Accuracy", 100, 100, "tie"),
            _row("Block", 150, None, "none"),
        ],
        sub_pool=[_row("Might", 100, 111, "none")],
        meta=[StatComparison("tradable", "Tradable", None, None, text_a="Yes", text_b="No")],
    )
    base.update(overrides)
    return ItemComparison(**base)


def test_swap_mirrors_sides_winners_and_texts():
    swapped = _comparison().swapped()
    assert swapped.item_a["name"] == "Beta Blade"
    attack = swapped.main[0]
    assert (attack.a.high, attack.b.high, attack.winner) == (776, 661, "a")
    assert swapped.main[1].winner == "tie"
    block = swapped.main[2]
    assert block.a is None and block.b.high == 150 and block.winner == "none"
    assert (swapped.meta[0].text_a, swapped.meta[0].text_b) == ("No", "Yes")
    assert swapped.wins == (1, 0, 1)


def test_a_range_delta_moves_at_both_ends():
    attack = _comparison().main[0]
    assert (attack.delta_low, attack.delta_high) == (85, 115)


# ---------------------------------------------------------------------------
# 3. the window paints what it is told
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def armory(qapp, tmp_path_factory):
    from PySide6.QtNetwork import QNetworkAccessManager

    patcher = pytest.MonkeyPatch()

    def _no_network(self, *args, **kwargs):
        raise AssertionError("a compare test tried to reach the network")

    patcher.setattr(QNetworkAccessManager, "get", _no_network)
    module = sys.modules.get("item_database_app")
    if module is None:
        spec = importlib.util.spec_from_file_location("item_database_app", APP_PY)
        module = importlib.util.module_from_spec(spec)
        sys.modules["item_database_app"] = module
        spec.loader.exec_module(module)
    cache = tmp_path_factory.mktemp("compare_cache")
    patcher.setattr(module, "ICON_CACHE_DIR", cache / "icons")
    patcher.setattr(module.IconCache, "request", lambda self, url: None)
    yield module
    module.apply_theme(theme.DEFAULT_THEME)
    patcher.undo()


@pytest.fixture
def dialog(qapp, armory):
    icons = armory.IconCache(armory.ICON_CACHE_DIR)
    window = armory.ItemCompareDialog(icons, None)
    armory._style_window(window)
    window.resize(780, 600)
    window.show()
    qapp.processEvents()
    yield window
    destroy_window(window)


def _cells(dialog, armory):
    return {
        label.text(): label
        for label in dialog.findChildren(armory.QLabel)
        if label.objectName() in ("CompareCell", "CompareDelta")
    }


def _fg(label):
    return label.palette().color(label.foregroundRole()).name()


def test_the_window_follows_the_winner_it_is_given_not_the_numbers(dialog, armory, qapp):
    # 100 vs 200, and the comparison says A won.  A window that re-derived
    # winners would crown B; this one must crown A.
    dialog.show_comparison(_comparison(main=[_row("Attack", 100, 200, "a")]))
    qapp.processEvents()
    cells = _cells(dialog, armory)
    assert "▲ 100" in cells and "▼ 200" in cells
    assert cells["▲ 100"].property("state") == "win"
    assert cells["▼ 200"].property("state") == "lose"


@pytest.mark.parametrize("theme_name", ["abyss", "inferno", "void"])
def test_winner_is_ok_and_loser_is_danger_in_every_theme(dialog, armory, qapp, theme_name):
    """tobia, 2026-09-24: winner green, loser red, like Build Compare."""
    armory.apply_theme(theme_name)
    dialog.show_comparison(_comparison())
    qapp.processEvents()
    tokens = theme.tokens(theme_name)
    cells = _cells(dialog, armory)
    assert _fg(cells["▲ 574 ~ 776"]) == tokens.ok
    assert _fg(cells["▼ 489 ~ 661"]) == tokens.danger
    assert _fg(cells["+85 ~ +115"]) == tokens.ok
    # A tie is neither -- plain foreground, no arrow.  Selected by state,
    # not by text: "100" is also a sub-stat pool value in this fixture.
    ties = [
        label for label in dialog.findChildren(armory.QLabel)
        if label.objectName() == "CompareCell" and label.property("state") == "tie"
    ]
    assert ties and all(_fg(label) == tokens.fg for label in ties)
    assert not any(label.text().startswith(("▲", "▼")) for label in ties)


def test_a_missing_stat_is_no_win(dialog, armory, qapp):
    dialog.show_comparison(_comparison())
    qapp.processEvents()
    cells = _cells(dialog, armory)
    assert cells["150"].property("state") == "tie"  # the side that has it: no ▲
    assert cells["—"].property("state") == "absent"
    assert cells[armory._t("arm_cmp_only_a")].property("state") == "flat"


def test_the_sub_stat_pool_never_shows_a_winner(dialog, armory, qapp):
    dialog.show_comparison(_comparison())
    qapp.processEvents()
    cells = _cells(dialog, armory)
    assert cells["111"].property("state") == "pool"
    pool_states = {
        label.property("state") for label in dialog.findChildren(armory.QLabel)
        if label.objectName() == "CompareCell" and label.text() in ("100", "111")
    }
    assert "win" not in pool_states and "lose" not in pool_states


def test_a_long_sub_stat_pool_starts_collapsed(dialog, armory, qapp):
    pool = [_row(f"Stat{i}", i, i + 1, "none") for i in range(23)]
    dialog.show_comparison(_comparison(sub_pool=pool))
    qapp.processEvents()
    shown = {label.text() for label in dialog.findChildren(armory.QLabel)}
    assert "Stat5" in shown and "Stat6" not in shown
    toggle = next(
        button for button in dialog.findChildren(armory.QPushButton)
        if button.objectName() == "CompareToggle"
    )
    assert toggle.text() == armory._t("arm_cmp_show_more", n=17)
    toggle.click()
    qapp.processEvents()
    shown = {label.text() for label in dialog.findChildren(armory.QLabel)}
    assert "Stat22" in shown


def test_properties_are_named_and_valued_in_the_ui_language(dialog, armory, qapp):
    dialog.show_comparison(_comparison())
    qapp.processEvents()
    shown = {label.text() for label in dialog.findChildren(armory.QLabel)}
    assert armory._t("arm_cmp_tradable") in shown
    assert {armory._t("arm_yes"), armory._t("arm_no")} <= shown


def test_the_swap_button_mirrors_the_window(dialog, armory, qapp):
    dialog.show_comparison(_comparison())
    qapp.processEvents()
    swap = next(
        button for button in dialog.findChildren(armory.QPushButton)
        if button.objectName() == "CompareSwap"
    )
    swap.click()
    qapp.processEvents()
    assert dialog.comparison.item_a["name"] == "Beta Blade"
    assert "▲ 574 ~ 776" in _cells(dialog, armory)


# ---------------------------------------------------------------------------
# 4. the menu entry stays hidden until the logic is wired (tobia, 2026-09-24)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def database(qapp, armory):
    """The real Item Database window -- the menu under test is its own."""
    window = armory.create_window(parent=None, language="en")
    window.resize(1200, 700)
    window.show()
    for _ in range(40):
        qapp.processEvents()
    yield window
    destroy_window(window)


def _menu_texts(armory, database, monkeypatch, enabled: bool, anchor=None) -> list[str]:
    """The item table's context menu on its first row, captured instead of
    executed (a real exec() would block the test on a modal menu)."""
    captured: list[str] = []

    # A QMenu whose exec() records the entries and returns at once.  Patched
    # as the module's QMenu NAME -- setting `exec` on the PySide type itself
    # does not take (the real, modal exec still ran and hung this test).
    class _CapturingMenu(armory.QMenu):
        def exec(self, *args, **kwargs):
            captured.extend(action.text() for action in self.actions() if action.text())
            return None

    monkeypatch.setattr(armory, "QMenu", _CapturingMenu)
    monkeypatch.setattr(armory.ItemDatabaseWindow, "_COMPARE_MENU_ENABLED", enabled)
    monkeypatch.setattr(database, "_compare_anchor", anchor)

    index = database.proxy.index(0, 0)
    if not index.isValid():
        pytest.skip("no item rows in this clone -- no data pack")
    rect = database.table.visualRect(index)
    database._show_item_context_menu(rect.center())
    return captured


def test_compare_is_hidden_from_the_context_menu_for_now(armory, database, monkeypatch):
    texts = _menu_texts(armory, database, monkeypatch, enabled=False, anchor=(-1, "Alpha Blade", "Sword"))
    assert armory._t("arm_ctx_show_details") in texts  # the menu did build
    assert armory._t("arm_ctx_compare_with") not in texts
    assert not any("Alpha Blade" in text for text in texts)


def test_flipping_the_switch_brings_both_entries_back(armory, database, monkeypatch):
    texts = _menu_texts(armory, database, monkeypatch, enabled=True, anchor=(-1, "Alpha Blade", "Sword"))
    assert armory._t("arm_ctx_compare_with") in texts
    assert armory._t("arm_ctx_compare_with_item", name="Alpha Blade") in texts


def test_the_shipped_default_is_on():
    """Read from the source, so no fixture or monkeypatch can mask it.

    Reactivated 2026-09-25 (tobia): compare window + logic were already
    finished uncommitted, only the menu was gated off -- flipped back on
    now that both halves are verified working together.
    """
    source = APP_PY.read_text(encoding="utf-8")
    assert "_COMPARE_MENU_ENABLED = True" in source


# ---------------------------------------------------------------------------
# 5. one detail popup at a time (tobia, 2026-09-26 -- "das können wir jetzt
#    durchziehen, da wir nun den item vergleich drin haben": compare_dialog()
#    already reuses a single window; _open_detail_popup() got the same fix)
# ---------------------------------------------------------------------------

def test_double_clicking_two_rows_reuses_one_detail_window(armory, database, qapp):
    proxy = database.proxy
    if proxy.rowCount() < 2:
        pytest.skip("fewer than 2 item rows in this clone -- no data pack")

    database._open_detail_popup(proxy.index(0, 0))
    qapp.processEvents()
    first = database._detail_dialog
    assert first is not None
    assert first.isVisible()

    database._open_detail_popup(proxy.index(1, 0))
    qapp.processEvents()

    # Same window instance, still just one -- not a second one stacked on
    # top of the first.
    assert database._detail_dialog is first
    assert sum(
        1 for w in armory.QApplication.topLevelWidgets()
        if isinstance(w, armory.ItemDetailDialog)
    ) == 1

