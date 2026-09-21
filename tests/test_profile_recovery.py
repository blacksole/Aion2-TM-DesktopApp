"""What the user sees when a profile cannot be read at all.

The guard that keeps auto-save away from an unparsable profile is correct and
well tested; what was missing is the other half -- telling the user it engaged.
These tests drive the real `MainWindow.load_profile` against a corrupt file
with no `.bak` (the migration case: `.bak` only starts existing after this
branch's first successful write) and assert the whole chain: modal shown,
either answer honoured, corrupt file preserved before any overwrite.

The modal is driven by monkeypatching `QMessageBox.exec` to click a button,
which is what a real click does -- `clickedButton()` is set by the click, not
by the event loop.
"""

from __future__ import annotations

import json

import pytest

from tests.conftest import destroy_window
from PySide6.QtWidgets import QMessageBox

from core.translations import tr

CORRUPT = '{"theme": "abyss", "tasks": [  '  # truncated mid-object


@pytest.fixture(scope="module")
def window(qapp, tmp_path_factory):
    """A real offscreen MainWindow on a throwaway profile directory."""
    import ui.main_window as mw

    profile_dir = tmp_path_factory.mktemp("recovery_profiles")
    (profile_dir / "Seed.json").write_text(json.dumps({"theme": "abyss"}), encoding="utf-8")

    patcher = pytest.MonkeyPatch()
    patcher.setattr(mw.MainWindow, "_resolve_profile_dir", lambda self: profile_dir)
    patcher.setattr(mw.MainWindow, "_save_app_config", lambda self: None)
    # NB: do NOT patch run_update_check. __init__ arms
    # QTimer.singleShot(2000, self.run_update_check), so Qt holds a bound
    # reference to whatever that attribute was at construction time; replacing
    # it and then restoring it at teardown leaves PySide6 cleaning up a
    # connection to a dead function object -- a segfault in func_dealloc at
    # interpreter shutdown, after every test has already passed. The timer
    # never fires here anyway: nothing in these tests runs the event loop for
    # two seconds.

    win = mw.MainWindow()
    win.countdown_timer.stop()
    yield win
    destroy_window(win)
    patcher.undo()


@pytest.fixture
def corrupt_profile(window):
    """A profile whose file is unparsable and which has no .bak at all."""
    path = window.profile_dir / "Broken.json"
    path.write_text(CORRUPT, encoding="utf-8")
    for leftover in window.profile_dir.glob("Broken.json.*"):
        leftover.unlink()
    window._profile_loading = False
    window._profile_unreadable = False
    window._autosave_disabled_notified = False
    return path


def _answer_with(monkeypatch, index: int):
    """Make the next QMessageBox.exec() click button `index` (0 = overwrite)."""
    monkeypatch.setattr(QMessageBox, "exec", lambda self: self.buttons()[index].click())


def test_unreadable_profile_asks_the_user(window, corrupt_profile, monkeypatch):
    shown = {}

    def capture(self):
        shown["title"] = self.windowTitle()
        shown["text"] = self.text()
        shown["buttons"] = [b.text() for b in self.buttons()]
        return self.buttons()[1].click()

    monkeypatch.setattr(QMessageBox, "exec", capture)
    window.load_profile(corrupt_profile)

    assert shown["title"] == tr(window.language, "profile_unreadable_title")
    assert str(corrupt_profile) in shown["text"]
    assert shown["buttons"] == [
        tr(window.language, "profile_unreadable_overwrite"),
        tr(window.language, "profile_unreadable_keep"),
    ]


def test_keep_the_file_leaves_autosave_off_and_says_so(window, corrupt_profile, monkeypatch):
    _answer_with(monkeypatch, 1)
    window.load_profile(corrupt_profile)

    assert window._profile_loading is True
    assert window._profile_unreadable is True
    assert window.toast_label.text() == tr(window.language, "profile_autosave_disabled")
    # The file is untouched and no snapshot was taken -- nothing overwrote it.
    assert corrupt_profile.read_text(encoding="utf-8") == CORRUPT
    assert list(window.profile_dir.glob("Broken.json.corrupt-*")) == []

    # And an auto-save really is a no-op from here on.
    window.save_profile(silent=True)
    assert corrupt_profile.read_text(encoding="utf-8") == CORRUPT


def test_save_anyway_snapshots_the_file_and_releases_the_guard(window, corrupt_profile, monkeypatch):
    _answer_with(monkeypatch, 0)
    window.load_profile(corrupt_profile)

    snapshots = list(window.profile_dir.glob("Broken.json.corrupt-*"))
    assert len(snapshots) == 1
    assert snapshots[0].read_text(encoding="utf-8") == CORRUPT
    assert window._profile_loading is False
    assert window._profile_unreadable is False

    # Auto-save works again, and now really writes.
    window.save_profile(silent=True)
    assert json.loads(corrupt_profile.read_text(encoding="utf-8"))


def test_explicit_save_snapshots_before_overwriting(window, corrupt_profile, monkeypatch):
    _answer_with(monkeypatch, 1)
    window.load_profile(corrupt_profile)
    assert window._profile_unreadable is True

    # The escape hatch: a deliberate "Save Profile" click. It must preserve
    # the unreadable original before writing over it.
    window.save_profile(explicit=True)

    snapshots = list(window.profile_dir.glob("Broken.json.corrupt-*"))
    assert len(snapshots) == 1
    assert snapshots[0].read_text(encoding="utf-8") == CORRUPT
    assert json.loads(corrupt_profile.read_text(encoding="utf-8"))
    assert window._profile_unreadable is False


def test_readable_profile_shows_no_dialog(window, monkeypatch):
    path = window.profile_dir / "Fine.json"
    path.write_text(json.dumps({"theme": "abyss", "language": "en"}), encoding="utf-8")
    monkeypatch.setattr(QMessageBox, "exec", lambda self: pytest.fail("no dialog expected"))

    window.load_profile(path)

    assert window._profile_loading is False
    assert window._profile_unreadable is False


def test_backup_recovery_toast_is_translated(window, monkeypatch):
    from core import persistence

    path = window.profile_dir / "FromBak.json"
    path.write_text(CORRUPT, encoding="utf-8")
    persistence.backup_path(path).write_text(
        json.dumps({"theme": "abyss", "language": "de"}), encoding="utf-8"
    )

    window.load_profile(path)

    assert window.toast_label.text() == tr(window.language, "profile_restored_from_backup")
    assert "Profile restored from backup" not in window.toast_label.text() or window.language == "en"


def test_a_corrupt_profile_at_STARTUP_does_not_crash_the_app(qapp, tmp_path, monkeypatch):
    """The migration case, end to end: the app starts, finds the profile it is
    told to open unreadable, and must survive -- the warning path runs during
    __init__, before anything in the UI can be assumed to exist."""
    import ui.main_window as mw

    profile_dir = tmp_path / "startup_profiles"
    profile_dir.mkdir()
    (profile_dir / "Rescue.json").write_text(CORRUPT, encoding="utf-8")
    (profile_dir / "last_profile.txt").write_text(str(profile_dir / "Rescue.json"), encoding="utf-8")

    monkeypatch.setattr(mw.MainWindow, "_resolve_profile_dir", lambda self: profile_dir)
    monkeypatch.setattr(mw.MainWindow, "_save_app_config", lambda self: None)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: self.buttons()[1].click())

    win = mw.MainWindow()
    try:
        win.countdown_timer.stop()
        assert win._profile_unreadable is True
        assert win._profile_loading is True          # auto-save stays disabled
        assert (profile_dir / "Rescue.json").read_text(encoding="utf-8") == CORRUPT
    finally:
        destroy_window(win)
