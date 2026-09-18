"""Tests for the empty-state placeholders and the add-row truncation fixes
(UX audit 2026-09-18, findings M1 "text truncation" and M2 "empty states are
blank").

Seams these tests depend on (KEEP THEM STABLE):
  * ``ui.widgets.empty_state.EmptyStateWidget`` -- ``set_content`` /
    ``retranslate``, objectNames ``emptyState`` / ``emptyStateTitle`` /
    ``emptyStateHint`` / ``emptyStateAction``.
  * ``TasksPage.render_tasks`` -- the single call MainWindow already makes on
    every ``refresh()``; it drives ``TasksPage.update_empty_state()``, so
    MainWindow itself needs no change. ``update_empty_state`` is public for
    any owner that mutates the list outside a refresh.
  * ``TasksPage.empty_state`` / ``TasksPage._list_scroll`` -- the two widgets
    that swap places when a tab renders zero cards.
  * ``CustomTimerManagerDialog._ct_empty_state`` -- toggled from
    ``_rebuild_custom_timer_rows``.
  * The MainWindow construction recipe (patched ``_resolve_profile_dir`` /
    ``_save_app_config``) is the one from ``tests/test_resets.py``.
"""

import shutil
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from core.translations import tr
from ui.custom_timer_manager_dialog import CustomTimerManagerDialog
from ui.pages.tasks_page import TasksPage
from ui.widgets.empty_state import EmptyStateWidget

FIXTURE_PROFILE = Path(__file__).resolve().parent / "fixtures" / "reset_profile.json"

TABS = {"tasks": "tasks", "shopping": "shopping"}


# ---------------------------------------------------------------------------
# EmptyStateWidget
# ---------------------------------------------------------------------------

def test_empty_state_is_hidden_until_shown(qapp):
    widget = EmptyStateWidget()
    assert widget.objectName() == "emptyState"
    assert widget.isHidden()
    assert widget.title_label.objectName() == "emptyStateTitle"
    assert widget.hint_label.objectName() == "emptyStateHint"
    assert widget.action_button.objectName() == "emptyStateAction"


def test_empty_state_wraps_long_text(qapp):
    widget = EmptyStateWidget()
    assert widget.title_label.wordWrap()
    assert widget.hint_label.wordWrap()


def test_set_content_fills_title_hint_and_action(qapp):
    calls = []
    widget = EmptyStateWidget()
    widget.set_content("Nothing here", "Add one above", "Templates",
                       lambda *_: calls.append(True))

    assert widget.title_label.text() == "Nothing here"
    assert widget.hint_label.text() == "Add one above"
    assert not widget.hint_label.isHidden()
    assert widget.action_button.text() == "Templates"
    assert not widget.action_button.isHidden()

    widget.action_button.click()
    assert len(calls) == 1


def test_set_content_hides_hint_and_action_when_omitted(qapp):
    widget = EmptyStateWidget()
    widget.set_content("Nothing here")

    assert widget.hint_label.isHidden()
    assert widget.action_button.isHidden()


def test_set_content_replaces_the_previous_action(qapp):
    first, second = [], []
    widget = EmptyStateWidget()
    widget.set_content("t", "", "A", lambda *_: first.append(True))
    widget.set_content("t", "", "B", lambda *_: second.append(True))

    widget.action_button.click()

    assert first == [], "the first callback must be disconnected, not stacked"
    assert len(second) == 1


def test_retranslate_keeps_the_action_wired(qapp):
    calls = []
    widget = EmptyStateWidget()
    widget.set_content("No tasks yet", "Add one above", "+ Add",
                       lambda *_: calls.append(True))
    widget.setVisible(True)

    widget.retranslate("Noch keine Aufgaben", "Oben eine hinzufügen", "+ Hinzufügen")

    assert widget.title_label.text() == "Noch keine Aufgaben"
    assert widget.hint_label.text() == "Oben eine hinzufügen"
    assert widget.action_button.text() == "+ Hinzufügen"
    assert not widget.isHidden()

    widget.action_button.click()
    assert len(calls) == 1


def test_retranslate_to_an_empty_hint_hides_it(qapp):
    widget = EmptyStateWidget()
    widget.set_content("Title", "Hint")
    widget.retranslate("Title", "")
    assert widget.hint_label.isHidden()


# ---------------------------------------------------------------------------
# TasksPage empty state (standalone page -- no MainWindow needed)
# ---------------------------------------------------------------------------

@pytest.fixture
def page(qapp):
    p = TasksPage(TABS, "en", tr)
    p.show()
    yield p
    p.close()
    p.deleteLater()
    QApplication.processEvents()


def test_page_starts_with_the_list_visible_and_no_placeholder(page):
    assert page.empty_state.isHidden()
    assert not page._list_scroll.isHidden()


def test_rendering_zero_task_cards_swaps_in_the_placeholder(page):
    page.set_active_tab("tasks")
    page.render_tasks([])

    assert not page.empty_state.isHidden()
    assert page._list_scroll.isHidden()
    assert page.empty_state.title_label.text() == tr("en", "empty_tasks_title")
    assert page.empty_state.hint_label.text() == tr("en", "empty_tasks_hint")


def test_rendering_zero_shopping_cards_uses_the_shopping_copy(page):
    page.set_active_tab("shopping")
    page.render_tasks([])

    assert not page.empty_state.isHidden()
    assert page.empty_state.title_label.text() == tr("en", "empty_shopping_title")
    assert page.empty_state.hint_label.text() == tr("en", "empty_shopping_hint")


def test_shopping_placeholder_action_opens_the_templates_dialog(page):
    seen = []
    page.template_requested.connect(lambda: seen.append(True))
    page.set_active_tab("shopping")
    page.render_tasks([])

    page.empty_state.action_button.click()

    assert seen == [True]


def test_tasks_placeholder_action_focuses_the_add_row(page):
    page.update_task_templates([{"id": "t1", "title": "Daevanion Quest",
                                 "schedule": "daily", "priority": "high"}])
    page.set_active_tab("tasks")
    page.render_tasks([])

    page.empty_state.action_button.click()

    # hasFocus() also requires an ACTIVE window, which an offscreen test
    # window never is -- focusWidget() is the window-local answer.
    assert page.focusWidget() is page.template_combo


def test_placeholder_goes_away_once_a_card_is_rendered(page):
    page.set_active_tab("tasks")
    page.render_tasks([])
    assert not page.empty_state.isHidden()

    page.render_tasks([QPushButton("a card")])

    assert page.empty_state.isHidden()
    assert not page._list_scroll.isHidden()


def test_placeholder_follows_the_language(page):
    page.set_active_tab("tasks")
    page.render_tasks([])

    page.update_language("de")

    assert page.empty_state.title_label.text() == tr("de", "empty_tasks_title")
    assert page.empty_state.hint_label.text() == tr("de", "empty_tasks_hint")


def test_tasks_placeholder_falls_back_to_templates_with_no_templates(page):
    """With no template for the tab the add-row is inert, so the action has
    to open the Templates dialog instead of focusing a hidden field."""
    seen = []
    page.template_requested.connect(lambda: seen.append(True))
    page.set_active_tab("tasks")
    page.render_tasks([])

    page.empty_state.action_button.click()

    assert seen == [True]


def test_placeholder_tolerates_a_missing_translation_key(page, monkeypatch):
    """``core.translations.tr`` returns the RAW KEY for one it does not know
    (``.get(key, key)``), which would print "empty_tasks_title" on screen."""
    monkeypatch.setattr(page, "tr", lambda lang, key, **kw: key)
    page.set_active_tab("tasks")
    page.render_tasks([])

    assert page.empty_state.title_label.text() != "empty_tasks_title"
    assert page.empty_state.hint_label.text() == ""
    assert page.empty_state.hint_label.isHidden()


# ---------------------------------------------------------------------------
# M1 -- add-row truncation
# ---------------------------------------------------------------------------

def test_character_combo_is_wide_enough_for_its_unassigned_row(page):
    """M1: rendered "No charac…" at 1280px."""
    assert page.char_input.minimumContentsLength() >= len(tr("en", "char_unassigned"))


def test_character_combo_minimum_width_holds_against_shrinking(page):
    """minimumContentsLength only feeds minimumSizeHint(), and QComboBox's
    default size policy may shrink past it -- the explicit minimum is what
    the layout actually honours."""
    page.update_characters([])
    assert page.char_input.minimumWidth() >= page.char_input.minimumSizeHint().width()


def test_amount_field_fits_its_own_placeholder(page):
    metrics = page.amount_input.fontMetrics()
    assert page.amount_input.minimumWidth() > metrics.horizontalAdvance(tr("en", "amount"))


@pytest.fixture
def unshown_page(qapp):
    """A page that is never shown: resize() then lands exactly, instead of
    being clamped to a top-level window's layout minimum."""
    p = TasksPage(TABS, "en", tr)
    p.update_task_templates([{"id": "t1", "title": "Daevanion Quest",
                              "schedule": "daily", "priority": "high",
                              "location": "Sanctum"}])
    p.update_characters(["QA Char"])
    p.set_active_tab("tasks")
    yield p
    p.close()


def test_add_row_wraps_to_a_second_line_when_narrow(unshown_page):
    page = unshown_page

    # Qt defers the QResizeEvent of a never-shown widget until it is shown,
    # so call the hook resizeEvent() would call.
    page.resize(1400, 700)
    page._update_add_row_wrap()
    assert not page._add_row_wrapped
    assert page._add_row_2.isHidden()

    page.resize(700, 700)
    page._update_add_row_wrap()
    assert page._add_row_wrapped
    assert not page._add_row_2.isHidden()
    # The tail stays usable -- Qt hides a widget on reparent, so the wrap
    # has to carry each control's own hidden/shown state across.
    assert not page.add_btn.isHidden()
    assert not page.template_combo.isHidden()
    assert not page.char_input.isHidden()


def test_add_row_unwraps_again_when_the_space_comes_back(unshown_page):
    page = unshown_page
    page.resize(700, 700)
    page._update_add_row_wrap()
    assert page._add_row_wrapped

    page.resize(1400, 700)
    page._update_add_row_wrap()

    assert not page._add_row_wrapped
    assert page._add_row_2.isHidden()
    assert not page.add_btn.isHidden()


def test_wrapping_lowers_the_add_row_minimum_width(unshown_page):
    """The point of the wrap (UX audit M1): on one line the add-row's own
    minimum was the widest thing on the page, and so set the whole window's
    minimum width. Measured on the two row layouts, which recompute on
    demand -- the enclosing widgets' minimumSizeHint() is cached."""
    page = unshown_page

    page.resize(1400, 700)
    page._update_add_row_wrap()
    one_line_minimum = page._add_row_primary.minimumSize().width()
    assert page._add_row_secondary.count() == 0

    page.resize(700, 700)
    page._update_add_row_wrap()

    assert page._add_row_primary.minimumSize().width() < one_line_minimum
    # ... and the tail really moved, rather than just being hidden.
    assert page._add_row_secondary.indexOf(page.add_btn) >= 0
    assert page._add_row_primary.indexOf(page.add_btn) == -1


# ---------------------------------------------------------------------------
# Custom timer manager
# ---------------------------------------------------------------------------

def test_timer_manager_shows_the_placeholder_with_no_timers(qapp):
    # Never show() this one: it is setModal(True), and a modal widget left
    # in QApplication's stack breaks the focus-sensitive tests elsewhere in
    # the suite. isHidden() is the flag under test and needs no window.
    dlg = CustomTimerManagerDialog([], [], language="en", tr_func=tr)
    assert not dlg._ct_empty_state.isHidden()
    assert dlg._ct_empty_state.title_label.text() == tr("en", "empty_timers_title")
    assert dlg._ct_empty_state.hint_label.text() == tr("en", "empty_timers_hint")


def test_timer_manager_hides_the_placeholder_once_a_timer_exists(qapp):
    timer = {"name": "Deva", "color": "#22d3ee", "timer_mode": "hourly",
             "interval_minutes": 60, "enabled": True}
    dlg = CustomTimerManagerDialog([], [timer], language="en", tr_func=tr)
    assert dlg._ct_empty_state.isHidden()


def test_timer_manager_placeholder_toggles_when_the_last_timer_goes(qapp):
    timer = {"name": "Deva", "color": "#22d3ee", "timer_mode": "hourly",
             "interval_minutes": 60, "enabled": True}
    dlg = CustomTimerManagerDialog([], [timer], language="en", tr_func=tr)
    assert dlg._ct_empty_state.isHidden()

    dlg._remove_custom_timer(0)

    assert not dlg._ct_empty_state.isHidden()


def test_timer_manager_tolerates_a_missing_translation_key(qapp):
    dlg = CustomTimerManagerDialog([], [], language="en",
                                   tr_func=lambda lang, key, **kw: key)
    assert dlg._ct_empty_state.title_label.text() != "empty_timers_title"
    assert dlg._ct_empty_state.hint_label.isHidden()


# ---------------------------------------------------------------------------
# End-to-end through MainWindow.refresh -- the seam MainWindow already uses
# ---------------------------------------------------------------------------

@pytest.fixture
def main_window(qapp, tmp_path_factory):
    """Same recipe as tests/test_resets.py: a real offscreen MainWindow on a
    throwaway profile dir, with the repo's config.json left alone."""
    import ui.main_window as mw

    profile_dir = tmp_path_factory.mktemp("empty_state_profiles")
    shutil.copy2(FIXTURE_PROFILE, profile_dir / "QaProfile.json")

    patcher = pytest.MonkeyPatch()
    patcher.setattr(mw.MainWindow, "_resolve_profile_dir", lambda self: profile_dir)
    patcher.setattr(mw.MainWindow, "_save_app_config", lambda self: None)

    win = mw.MainWindow()
    win.countdown_timer.stop()
    yield win
    win.close()
    patcher.undo()


def test_refresh_shows_the_placeholder_when_shopping_is_empty(main_window):
    win = main_window
    win.task_lists["shopping"] = []
    win.tasks_page.set_active_tab("shopping")

    # MainWindow is never show()n here, so isVisible() is False throughout
    # -- isHidden() is the explicit flag the page actually sets.
    assert not win.tasks_page.empty_state.isHidden()
    assert win.tasks_page._list_scroll.isHidden()
    assert win.tasks_page.empty_state.title_label.text() == tr(
        win.language, "empty_shopping_title"
    )


def test_refresh_hides_the_placeholder_again_once_a_card_is_back(main_window):
    win = main_window
    kept = list(win.task_lists["shopping"])
    win.task_lists["shopping"] = []
    win.tasks_page.set_active_tab("shopping")
    assert not win.tasks_page.empty_state.isHidden()

    win.task_lists["shopping"] = kept
    win.refresh()

    assert win.tasks_page.empty_state.isHidden()
    assert not win.tasks_page._list_scroll.isHidden()
