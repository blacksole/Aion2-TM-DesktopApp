"""Keyboard access for the main window (UX audit 2026-09-18, C1).

The app shipped with zero QShortcut/keyPressEvent: no way to add a task,
switch tabs, toggle the overlay, save, or delete without a mouse. These tests
pin the small map that replaced that:

    Ctrl+N  focus the ToDo tab's add-task title field
    Ctrl+1  ToDo tab          Ctrl+2  Timers tab
    Ctrl+O  toggle the overlay
    Ctrl+S  explicit profile save
    Delete  soft-delete the focused card -- and NOTHING else

Delete is deliberately not a QShortcut (a window-context shortcut resolves
BEFORE the focused widget sees the key, which would break Delete inside every
QLineEdit in the window); it is an application event filter that declines the
event whenever focus is not on a card. ``test_delete_inside_a_line_edit_*``
below is the regression guard for exactly that.

Seams these tests depend on (KEEP THEM STABLE):
  * ``MainWindow._shortcuts`` -- {"Ctrl+N": QShortcut, ...}.
  * ``MainWindow.eventFilter`` installed on the QApplication.
  * ``MainWindow._delete_focused_card()`` -> bool ("did I consume the key").
  * ``MainWindow._resolve_profile_dir`` / ``_save_app_config`` -- patched so no
    test touches the repo's own ``profiles/`` or ``config.json``.
"""

import shutil
from pathlib import Path

import pytest

from tests.conftest import destroy_window
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit

FIXTURE_PROFILE = Path(__file__).resolve().parent / "fixtures" / "reset_profile.json"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def main_window(qapp, tmp_path_factory):
    import ui.main_window as mw

    profile_dir = tmp_path_factory.mktemp("shortcut_profiles")
    shutil.copy2(FIXTURE_PROFILE, profile_dir / "QaProfile.json")

    patcher = pytest.MonkeyPatch()
    patcher.setattr(mw.MainWindow, "_resolve_profile_dir", lambda self: profile_dir)
    patcher.setattr(mw.MainWindow, "_save_app_config", lambda self: None)

    win = mw.MainWindow()
    win.countdown_timer.stop()
    # Focus only travels inside a shown window, even on the offscreen platform.
    win.show()
    # Deprecated in Qt 6.11 but still the only reliable way to give an
    # offscreen window the keyboard focus a real window manager would.
    QApplication.setActiveWindow(win)

    yield win

    win.overlay.hide()
    destroy_window(win)
    patcher.undo()


@pytest.fixture
def writes(monkeypatch):
    import core.persistence as persistence

    recorded: list[dict] = []
    monkeypatch.setattr(persistence, "atomic_write_json", lambda path, data, **kw: recorded.append(data))
    return recorded


@pytest.fixture
def win(main_window, writes):
    w = main_window
    w._pending_delete = None
    w._profile_loading = False
    w.auto_save = True
    w.load_profile(w.profile_dir / "QaProfile.json")
    w.language = "en"
    w.active_tab = "tasks"
    w.active_filter = "all"
    w.todo_char_filter = ""
    # A realistic add row: with at least one template the Tasks tab shows
    # its template picker (update_input_mode hides the free-text title field
    # on the template-driven tabs).
    w.task_templates = [{"id": "t1", "title": "QA Daily Task", "is_general": False}]
    w.item_templates = []
    w.tasks_page.update_task_templates(w.task_templates)
    w.overlay.hide()
    # Showing/hiding the overlay leaves the app with no active window, and
    # QApplication.focusWidget() only ever reports the ACTIVE window's focus.
    QApplication.setActiveWindow(w)
    w.refresh()
    writes.clear()
    return w


def _fire(win, key):
    """Triggers a bound shortcut without depending on the platform's real key
    delivery (offscreen has no window manager to route Ctrl+N through)."""
    win._shortcuts[key].activated.emit()
    QApplication.processEvents()


def _focus(win, widget):
    """Gives ``widget`` the real keyboard focus and proves it took.

    QApplication.focusWidget() only ever reports the ACTIVE window's focus
    widget, and on the offscreen platform nothing re-activates a window on
    its own -- so every test that reads focus has to claim it first, or it
    silently depends on whatever the previous test left behind."""
    from PySide6.QtCore import QDeadlineTimer, QEventLoop

    widget.setFocus(Qt.OtherFocusReason)
    # Activation is delivered as an EVENT, not applied inline, and the app's
    # own ``Qt.Tool`` overlay is a second top-level that can take it back --
    # so one setActiveWindow() + one processEvents() was a race (it failed
    # ~1 run in 3 with `focusWidget() is None`).  Wait for the outcome.
    deadline = QDeadlineTimer(2000)
    while QApplication.focusWidget() is not widget and not deadline.hasExpired():
        if not win.isActiveWindow():
            win.activateWindow()
        widget.setFocus(Qt.OtherFocusReason)
        QApplication.processEvents(QEventLoop.AllEvents, 20)
    assert QApplication.focusWidget() is widget, (
        f"could not give focus to {widget!r}; got {QApplication.focusWidget()!r}"
    )
    return widget


# ---------------------------------------------------------------------------
# the map exists and is bound to this window
# ---------------------------------------------------------------------------

def test_every_documented_shortcut_is_bound(win):
    assert set(win._shortcuts) == {"Ctrl+N", "Ctrl+1", "Ctrl+2", "Ctrl+O", "Ctrl+S"}
    for sc in win._shortcuts.values():
        assert sc.parent() is win


# ---------------------------------------------------------------------------
# Ctrl+1 / Ctrl+2 -- ToDo / Timers
# ---------------------------------------------------------------------------

def test_ctrl_2_shows_the_timers_tab(win):
    _fire(win, "Ctrl+2")

    assert win.page_stack.currentWidget() is win.todo_page
    assert win.todo_page.content_stack.currentIndex() == 1
    assert win.todo_page.timer_tab_btn.property("active") is True


def test_ctrl_1_shows_the_todo_tab(win):
    _fire(win, "Ctrl+2")
    _fire(win, "Ctrl+1")

    assert win.page_stack.currentWidget() is win.todo_page
    assert win.todo_page.content_stack.currentIndex() == 0
    assert win.todo_page.todo_tab_btn.property("active") is True


def test_ctrl_1_comes_back_from_another_page(win):
    win.sidebar.set_active_page("settings")
    assert win.page_stack.currentWidget() is win.settings_page

    _fire(win, "Ctrl+1")

    assert win.page_stack.currentWidget() is win.todo_page
    # The sidebar highlight must not keep pointing at Settings.
    assert win.sidebar.buttons["tasks"].isChecked()
    assert not win.sidebar.buttons["settings"].isChecked()


# ---------------------------------------------------------------------------
# Ctrl+N -- add a task
# ---------------------------------------------------------------------------

def test_ctrl_n_focuses_the_add_rows_entry_point(win):
    _focus(win, win.overlay_toggle_btn)

    focused = win._focus_add_task_input()
    QApplication.processEvents()

    # The Tasks tab is template-driven, so the entry point is the template
    # picker rather than the (hidden) free-text title field.
    assert focused is win.tasks_page.template_combo
    assert focused.hasFocus()


def test_ctrl_n_focuses_the_title_field_when_it_is_the_visible_one(win):
    # Whatever TasksPage decides to show, Ctrl+N follows it: force the
    # free-text field on and the title input must win again.
    win.tasks_page.title_input.setVisible(True)

    focused = win._focus_add_task_input()

    assert focused is win.tasks_page.title_input
    assert focused.hasFocus()
    win.tasks_page.update_input_mode()


def test_ctrl_n_returns_none_when_the_add_row_has_no_entry_point(win):
    win.tasks_page.update_task_templates([])

    assert win._focus_add_task_input() is None


def test_ctrl_n_switches_to_the_todo_tab_first(win):
    _fire(win, "Ctrl+2")

    _fire(win, "Ctrl+N")

    assert win.todo_page.content_stack.currentIndex() == 0
    assert win.page_stack.currentWidget() is win.todo_page


# ---------------------------------------------------------------------------
# Ctrl+O -- overlay
# ---------------------------------------------------------------------------

def test_ctrl_o_toggles_the_overlay_both_ways(win):
    assert not win.overlay.isVisible()

    _fire(win, "Ctrl+O")
    assert win.overlay.isVisible()
    assert win.overlay_toggle_btn.isChecked()

    _fire(win, "Ctrl+O")
    assert not win.overlay.isVisible()
    assert not win.overlay_toggle_btn.isChecked()


# ---------------------------------------------------------------------------
# Ctrl+S -- save
# ---------------------------------------------------------------------------

def test_ctrl_s_saves_explicitly(win, monkeypatch):
    calls = []
    monkeypatch.setattr(win, "save_profile", lambda **kw: calls.append(kw))

    _fire(win, "Ctrl+S")

    assert calls == [{"explicit": True}]


def test_ctrl_s_writes_the_profile_even_while_auto_save_is_off(win, writes):
    win.auto_save = False

    _fire(win, "Ctrl+S")

    assert len(writes) == 1


# ---------------------------------------------------------------------------
# Delete -- only ever on a focused card
# ---------------------------------------------------------------------------

def test_cards_can_take_focus(win):
    card = win.task_lists["tasks"][0]

    assert card.focusPolicy() == Qt.StrongFocus


def test_delete_soft_deletes_the_focused_card(win):
    card = win.task_lists["tasks"][0]
    _focus(win, card)

    consumed = win._delete_focused_card()

    assert consumed is True
    assert card not in win.task_lists["tasks"]
    assert win._pending_delete["card"] is card


def test_delete_works_from_a_child_of_the_card(win):
    card = win.task_lists["tasks"][0]
    _focus(win, card.check_btn)

    consumed = win._delete_focused_card()

    assert consumed is True
    assert card not in win.task_lists["tasks"]


def test_delete_key_event_reaches_the_focused_card(win):
    card = win.task_lists["tasks"][0]
    _focus(win, card)

    QTest.keyClick(card, Qt.Key_Delete)

    assert card not in win.task_lists["tasks"]


def test_delete_inside_a_line_edit_does_nothing_to_cards(win):
    # A real in-app editor on the add row (the free-text title field is
    # hidden on the template-driven Tasks tab -- see update_input_mode).
    edit = win.tasks_page.amount_input
    edit.setText("12")
    _focus(win, edit)
    before = list(win.task_lists["tasks"])

    consumed = win._delete_focused_card()

    assert consumed is False, "the key must fall through to the editor"
    assert win.task_lists["tasks"] == before
    assert win._pending_delete is None
    edit.setText("1")


def test_delete_key_inside_a_line_edit_still_edits_the_text(win):
    edit = win.tasks_page.amount_input
    edit.setText("123")
    edit.setCursorPosition(0)
    _focus(win, edit)
    before = list(win.task_lists["tasks"])

    QTest.keyClick(edit, Qt.Key_Delete)

    assert edit.text() == "23", "Delete must keep its normal meaning in an editor"
    assert win.task_lists["tasks"] == before
    edit.setText("1")


def test_delete_in_an_unrelated_line_edit_is_also_ignored(win, qapp):
    stray = QLineEdit(win)
    stray.setText("x")
    stray.show()
    _focus(win, stray)

    assert win._delete_focused_card() is False
    assert win._pending_delete is None

    stray.setParent(None)
    stray.deleteLater()


def test_delete_with_focus_outside_any_card_is_ignored(win):
    _focus(win, win.overlay_toggle_btn)
    before = list(win.task_lists["tasks"])

    assert win._delete_focused_card() is False
    assert win.task_lists["tasks"] == before


def test_deleting_by_keyboard_is_undoable_like_the_x_button(win, writes):
    card = win.task_lists["tasks"][0]
    before = [c.title for c in win.task_lists["tasks"]]
    _focus(win, card)

    win._delete_focused_card()
    win._undo_pending_delete()

    assert [c.title for c in win.task_lists["tasks"]] == before
    assert writes == []
