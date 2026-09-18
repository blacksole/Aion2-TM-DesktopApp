"""Soft delete + undo for task/shopping cards (UX audit 2026-09-18, C2).

Before this, the card's "x" was one irreversible click: it dropped the card,
flipped the matching template's ``is_general`` and auto-saved. These tests pin
the replacement contract:

  * deleting removes the card from ``task_lists`` IMMEDIATELY -- so a pending
    card can never be serialized, counted, rendered, or resurrected by a reset
    that fires while the undo toast is up;
  * nothing is written and no template is touched until the delete COMMITS
    (toast expiry, a second delete, a profile switch, or app close);
  * undo puts the card back at its exact index with its completed state
    intact, and writes nothing (the deletion never reached disk).

Seams these tests depend on (KEEP THEM STABLE):
  * ``MainWindow._resolve_profile_dir`` / ``_save_app_config`` -- patched so no
    test touches the repo's own ``profiles/`` or ``config.json``.
  * ``core.persistence.atomic_write_json`` -- imported *inside* save_profile
    (late binding), so patching the module attribute intercepts every write.
  * ``MainWindow._pending_delete`` -- ``None`` or a dict with keys
    ``seq``/``tab``/``index``/``card``/``apply``.
  * ``MainWindow._commit_pending_delete(seq=None)`` /
    ``_undo_pending_delete()`` / ``UNDO_WINDOW_MS``.
  * ``show_toast(text, action_label=None, on_action=None, duration_ms=...)``
    and the ``toast_widget`` / ``toast_label`` / ``toast_action_btn`` trio.
"""

import shutil
from pathlib import Path

import pytest

from tests.conftest import destroy_window
from PySide6.QtCore import QDeadlineTimer, QEventLoop
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from core.translations import tr

FIXTURE_PROFILE = Path(__file__).resolve().parent / "fixtures" / "reset_profile.json"


def settled(predicate, timeout_ms: int = 2000):
    """Pump the event loop until ``predicate()`` or the deadline.

    Two of the transitions below now finish on an animation callback, not
    inline: MASTER §3 gives the toast and the soft-deleted card a
    ``motion.base`` (160 ms) fade, so ``toast_widget.hide()`` and the
    post-delete ``refresh()`` run when the fade ends.  Waiting on the
    OUTCOME rather than on a fixed sleep keeps these tests deterministic and
    independent of the duration token's value.
    """
    deadline = QDeadlineTimer(timeout_ms)
    while not predicate() and not deadline.hasExpired():
        QApplication.processEvents(QEventLoop.AllEvents, 20)
    assert predicate(), f"condition never held within {timeout_ms} ms"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def main_window(qapp, tmp_path_factory):
    """One real, offscreen MainWindow on a throwaway profile directory."""
    import ui.main_window as mw

    profile_dir = tmp_path_factory.mktemp("undo_profiles")
    shutil.copy2(FIXTURE_PROFILE, profile_dir / "QaProfile.json")

    patcher = pytest.MonkeyPatch()
    patcher.setattr(mw.MainWindow, "_resolve_profile_dir", lambda self: profile_dir)
    patcher.setattr(mw.MainWindow, "_save_app_config", lambda self: None)

    win = mw.MainWindow()
    # Nothing may run check_auto_resets behind the tests' back.
    win.countdown_timer.stop()
    assert win.profile_name == "QaProfile", "fixture profile was not the one loaded"

    yield win

    destroy_window(win)
    patcher.undo()


@pytest.fixture
def writes(monkeypatch):
    """Records (and suppresses) every profile write save_profile would make."""
    import core.persistence as persistence

    recorded: list[dict] = []

    def _spy(path, data, **kwargs):
        recorded.append(data)

    monkeypatch.setattr(persistence, "atomic_write_json", _spy)
    return recorded


@pytest.fixture
def win(main_window, writes):
    """A window whose card lists are freshly rebuilt from the fixture file.

    ``load_profile`` is the cheapest way back to a known set of live cards
    after a test has deleted some; the ``writes`` spy above is already in
    place, so the reload cannot persist a previous test's deletion.
    """
    w = main_window
    w._pending_delete = None
    w._profile_loading = False
    w.auto_save = True
    w.load_profile(w.profile_dir / "QaProfile.json")
    w.language = "en"
    w.active_tab = "tasks"
    w.active_filter = "all"
    w.todo_char_filter = ""
    # The fixture carries no templates; these give the commit path something
    # to flip (the side effect the old _delete_card did inline).
    w.task_templates = [
        {"id": "t-daily", "title": "QA Daily Task", "is_general": True},
        {"id": "t-weekly", "title": "QA Weekly Task", "is_general": True},
    ]
    w.item_templates = [
        {"id": "i-daily", "title": "QA Daily Item", "is_general": True},
    ]
    w.refresh()
    writes.clear()
    return w


def _titles(win, tab="tasks"):
    return [c.title for c in win.task_lists[tab]]


def _serialized_titles(win, tab="tasks"):
    """Exactly what save_profile would persist for ``tab``."""
    return [win.serialize_card(c)["title"] for c in win.task_lists[tab]]


# ---------------------------------------------------------------------------
# the delete itself
# ---------------------------------------------------------------------------

def test_delete_removes_the_card_but_commits_nothing_yet(win, writes):
    card = win.task_lists["tasks"][0]

    win._delete_card(card)

    assert card not in win.task_lists["tasks"]
    assert win._pending_delete is not None
    assert win._pending_delete["card"] is card
    assert win._pending_delete["tab"] == "tasks"
    assert win._pending_delete["index"] == 0
    # Nothing persisted and no template touched while undo is still possible.
    assert writes == []
    assert win.task_templates[0]["is_general"] is True


def test_pending_card_is_excluded_from_serialization(win, writes):
    card = win.task_lists["tasks"][1]
    title = card.title

    win._delete_card(card)
    win.save_profile(silent=True)

    assert len(writes) == 1
    saved = [entry["title"] for entry in writes[0]["tasks"]["tasks"]]
    assert title not in saved
    assert _serialized_titles(win) == saved


def test_pending_card_is_excluded_from_counts_and_rendering(win):
    before = win.tasks_page._rendered_count
    card = win.task_lists["tasks"][0]

    win._delete_card(card)

    # The card is out of task_lists the instant _delete_card returns (that is
    # the invariant this module exists for, see the header) -- the re-RENDER
    # waits for its fade to finish.
    assert card not in win.task_lists["tasks"]
    settled(lambda: win.tasks_page._rendered_count == before - 1)
    # render_tasks hides and unparents everything it no longer renders.
    assert card.isHidden()
    assert card.parentWidget() is None


def test_shopping_cards_take_the_same_path(win, writes):
    card = win.task_lists["shopping"][0]

    win._delete_card(card)

    assert card not in win.task_lists["shopping"]
    assert win._pending_delete["tab"] == "shopping"
    assert writes == []


# ---------------------------------------------------------------------------
# undo
# ---------------------------------------------------------------------------

def test_undo_restores_exact_index_and_completed_state(win, writes):
    card = win.task_lists["tasks"][1]
    card.set_completed(True)
    before = _titles(win)

    win._delete_card(card)
    win._undo_pending_delete()

    assert _titles(win) == before
    assert win.task_lists["tasks"][1] is card
    assert card.completed is True
    assert win._pending_delete is None
    # An undone delete never reached disk, so it needs no save to unwind.
    assert writes == []


def test_undo_leaves_the_template_untouched(win):
    card = win.task_lists["tasks"][0]
    assert card.title == "QA Daily Task"

    win._delete_card(card)
    win._undo_pending_delete()

    assert win.task_templates[0]["is_general"] is True


def test_undo_without_a_pending_delete_is_a_no_op(win, writes):
    before = _titles(win)

    win._undo_pending_delete()

    assert _titles(win) == before
    assert writes == []


def test_undo_re_renders_the_card(win):
    before = win.tasks_page._rendered_count
    card = win.task_lists["tasks"][0]

    win._delete_card(card)
    win._undo_pending_delete()

    assert win.tasks_page._rendered_count == before
    assert not card.isHidden()


# ---------------------------------------------------------------------------
# commit
# ---------------------------------------------------------------------------

def test_commit_flips_the_task_template_and_saves_once(win, writes):
    card = win.task_lists["tasks"][0]
    assert card.title == "QA Daily Task"

    win._delete_card(card)
    win._commit_pending_delete()

    assert win.task_templates[0]["is_general"] is False
    assert win.task_templates[1]["is_general"] is True, "only the matching template flips"
    assert win._pending_delete is None
    assert len(writes) == 1


def test_commit_flips_the_item_template_for_shopping_cards(win):
    card = win.task_lists["shopping"][0]
    assert card.title == "QA Daily Item"

    win._delete_card(card)
    win._commit_pending_delete()

    assert win.item_templates[0]["is_general"] is False


def test_commit_does_not_save_when_auto_save_is_off(win, writes):
    win.auto_save = False
    card = win.task_lists["tasks"][0]

    win._delete_card(card)
    win._commit_pending_delete()

    assert win._pending_delete is None
    assert writes == []


def test_commit_without_a_pending_delete_is_a_no_op(win, writes):
    win._commit_pending_delete()

    assert win._pending_delete is None
    assert writes == []


def test_two_rapid_deletes_commit_the_first(win, writes):
    first = win.task_lists["tasks"][0]
    second = win.task_lists["tasks"][1]

    win._delete_card(first)
    win._delete_card(second)

    assert win._pending_delete["card"] is second
    # The first one is gone for good: template flipped and persisted.
    assert win.task_templates[0]["is_general"] is False
    assert len(writes) == 1
    # ...while the second is still undoable and untouched.
    assert win.task_templates[1]["is_general"] is True


def test_undo_after_two_deletes_only_restores_the_second(win):
    first = win.task_lists["tasks"][0]
    second = win.task_lists["tasks"][1]

    win._delete_card(first)
    win._delete_card(second)
    win._undo_pending_delete()

    titles = _titles(win)
    assert second.title in titles
    assert first.title not in titles


# ---------------------------------------------------------------------------
# the expiry timer's sequence guard
# ---------------------------------------------------------------------------

def test_expiring_timer_commits_its_own_delete(win, writes):
    card = win.task_lists["tasks"][0]
    win._delete_card(card)
    seq = win._pending_delete["seq"]

    win._commit_pending_delete(seq)

    assert win._pending_delete is None
    assert win.task_templates[0]["is_general"] is False
    assert len(writes) == 1


def test_a_stale_timer_cannot_commit_a_newer_delete(win, writes):
    first = win.task_lists["tasks"][0]
    win._delete_card(first)
    stale_seq = win._pending_delete["seq"]
    win._undo_pending_delete()
    writes.clear()

    second = win.task_lists["tasks"][1]
    win._delete_card(second)

    win._commit_pending_delete(stale_seq)

    assert win._pending_delete is not None, "the newer delete is still undoable"
    assert win._pending_delete["card"] is second
    assert writes == []


def test_undo_window_is_long_enough_to_be_usable(win):
    # The audit asked for 5-8 s; anything shorter is not an undo affordance.
    assert 5000 <= win.UNDO_WINDOW_MS <= 8000


# ---------------------------------------------------------------------------
# a reset must not resurrect a pending card
# ---------------------------------------------------------------------------

def test_reset_while_pending_does_not_resurrect_the_card(win):
    card = win.task_lists["tasks"][0]
    card.set_completed(True)

    win._delete_card(card)
    win.reset_tasks_for_tabs(["tasks", "shopping"])

    assert card not in win.task_lists["tasks"]
    assert card.completed is True, "a pending card is outside the reset's reach"
    assert win._pending_delete is not None, "the reset must not consume the undo window"


def test_reset_while_pending_does_not_persist_the_card(win, writes):
    card = win.task_lists["tasks"][0]
    title = card.title

    win._delete_card(card)
    win.reset_tasks_for_tabs(["tasks", "shopping"])

    assert writes, "the reset saves"
    saved = [entry["title"] for entry in writes[-1]["tasks"]["tasks"]]
    assert title not in saved


def test_undo_after_a_reset_still_restores_the_card(win):
    card = win.task_lists["tasks"][1]
    before = _titles(win)

    win._delete_card(card)
    win.reset_tasks_for_tabs(["tasks", "shopping"])
    win._undo_pending_delete()

    assert _titles(win) == before


# ---------------------------------------------------------------------------
# lifecycle commits: profile switch and app close
# ---------------------------------------------------------------------------

def test_switching_profiles_commits_the_pending_delete(win):
    card = win.task_lists["tasks"][0]
    win._delete_card(card)

    win.load_profile(win.profile_dir / "QaProfile.json")

    assert win._pending_delete is None


def test_closing_the_app_commits_the_pending_delete(win, writes):
    card = win.task_lists["tasks"][0]
    win._delete_card(card)
    win.minimize_to_tray = False
    win._force_quit = True

    win.closeEvent(QCloseEvent())

    assert win._pending_delete is None
    assert win.task_templates[0]["is_general"] is False
    assert writes, "closing persists the committed delete"


# ---------------------------------------------------------------------------
# the toast row (label + optional action button)
# ---------------------------------------------------------------------------

def test_plain_toast_has_no_action_button(win):
    win.show_toast("saved")

    assert win.toast_label.text() == "✓ saved"
    assert win.toast_action_btn.isHidden()


def test_delete_shows_an_undo_action_toast(win):
    card = win.task_lists["tasks"][0]

    win._delete_card(card)

    assert win.toast_label.text() == f"✓ {tr('en', 'toast_task_removed')}"
    assert not win.toast_action_btn.isHidden()
    assert win.toast_action_btn.text() == tr("en", "undo")


def test_clicking_the_toast_action_undoes_the_delete(win, writes):
    card = win.task_lists["tasks"][0]
    before = _titles(win)

    win._delete_card(card)
    win.toast_action_btn.click()

    assert _titles(win) == before
    assert win._pending_delete is None
    assert win.toast_action_btn.isHidden()
    assert writes == []


def test_the_action_fires_only_once(win):
    card = win.task_lists["tasks"][0]
    win._delete_card(card)

    win.toast_action_btn.click()
    win.toast_action_btn.click()

    assert _titles(win).count(card.title) == 1


def test_a_later_plain_toast_drops_the_action_button(win):
    win._delete_card(win.task_lists["tasks"][0])

    win.show_toast("saved")

    assert win.toast_action_btn.isHidden()


def test_an_expired_toasts_timer_does_not_close_a_newer_toast(win):
    win.show_toast("first")
    stale_seq = win._toast_seq
    win.show_toast("second")

    win._hide_toast(stale_seq)

    assert win.toast_label.text() == "✓ second"
    assert not win.toast_widget.isHidden()

    win._hide_toast(win._toast_seq)
    settled(win.toast_widget.isHidden)


# ---------------------------------------------------------------------------
# a DESTRUCTIVE reset must close the undo window (review F-2)
# ---------------------------------------------------------------------------
#
# The three tests above cover `reset_tasks_for_tabs` -- the completed-FLAG
# reset, which deliberately leaves the undo window open because it destroys
# nothing.  `reset_profile` and `clear_event_entries` DO destroy: they empty
# the lists.  Neither committed the pending delete, so Undo afterwards put a
# card back into a list the user had just emptied, and the next save
# persisted it.


def _answer_confirmation(monkeypatch, role):
    """Answer the confirmation QMessageBox by clicking the button with ``role``.

    Both destructive paths build a box, ``exec()`` it, and compare
    ``clickedButton()`` with the button they added for "yes".  Clicking a
    real button inside the faked ``exec`` is what makes ``clickedButton()``
    return that same object -- ``buttons()`` is ordered by ROLE, not by the
    order they were added, so indexing it picks the wrong one.
    """
    from PySide6.QtWidgets import QMessageBox

    def fake_exec(self):
        for button in self.buttons():
            if self.buttonRole(button) == role:
                button.click()
                return 0
        raise AssertionError(f"no button with role {role} in the confirmation box")

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)


def _accept_confirmation(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    _answer_confirmation(monkeypatch, QMessageBox.DestructiveRole)


def _decline_confirmation(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    _answer_confirmation(monkeypatch, QMessageBox.RejectRole)


def test_reset_profile_closes_the_undo_window(win, writes, monkeypatch):
    _accept_confirmation(monkeypatch)
    card = win.task_lists["tasks"][0]

    win._delete_card(card)
    win.reset_profile()

    assert win._pending_delete is None, "the undo window survived a destructive reset"
    assert _titles(win) == []

    win._undo_pending_delete()
    assert _titles(win) == [], "Undo resurrected a card the reset destroyed"
    # The commit's own save (pre-reset list minus the deleted card) comes
    # first, the reset's save last -- what must never hold the card is the
    # state the app is left in.
    assert writes, "the reset saves"
    assert not writes[-1]["tasks"]["tasks"], "the reset persisted a task list"


def test_clear_event_entries_closes_the_undo_window(win, writes, monkeypatch):
    _accept_confirmation(monkeypatch)
    card = win.task_lists["tasks"][0]

    win._delete_card(card)
    win.clear_event_entries()

    assert win._pending_delete is None, "the undo window survived clear_event_entries"
    before = _titles(win)

    win._undo_pending_delete()
    assert _titles(win) == before, "Undo resurrected a card after a destructive clear"


def test_declining_the_reset_leaves_the_undo_window_open(win, monkeypatch):
    """Committing must happen after the confirmation, not before it."""
    _decline_confirmation(monkeypatch)

    card = win.task_lists["tasks"][0]
    title = card.title
    win._delete_card(card)
    win.reset_profile()

    assert win._pending_delete is not None, "a declined reset consumed the undo window"
    win._undo_pending_delete()
    assert title in _titles(win)


# ---------------------------------------------------------------------------
# closing to the tray is not closing (review F-8)
# ---------------------------------------------------------------------------


def test_hiding_to_the_tray_keeps_the_undo_window_open(win, monkeypatch):
    """`closeEvent` committed the pending delete before the tray branch, so
    minimising to the tray silently ended the undo window even though the
    app had not closed."""
    from PySide6.QtGui import QCloseEvent

    card = win.task_lists["tasks"][0]
    title = card.title
    win._delete_card(card)

    monkeypatch.setattr(win, "minimize_to_tray", True)
    monkeypatch.setattr(win, "_tray_ready", lambda: True)
    monkeypatch.setattr(win, "_notify", lambda *a, **k: None)
    # _quit_app() sets this on the shared window, and it short-circuits
    # straight to "accept and quit".
    monkeypatch.setattr(win, "_force_quit", False)

    event = QCloseEvent()
    win.closeEvent(event)

    assert not event.isAccepted(), "the window closed instead of hiding to the tray"
    assert win._pending_delete is not None, "the tray hide ended the undo window"

    win._undo_pending_delete()
    assert title in _titles(win)
    win.show()


def test_a_real_close_still_commits(win, monkeypatch):
    from PySide6.QtGui import QCloseEvent

    card = win.task_lists["tasks"][0]
    win._delete_card(card)

    monkeypatch.setattr(win, "minimize_to_tray", False)
    monkeypatch.setattr(win, "_tray_ready", lambda: False)
    monkeypatch.setattr(win, "_force_quit", False)
    event = QCloseEvent()
    win.closeEvent(event)

    assert win._pending_delete is None, "a real close left the undo window open"
