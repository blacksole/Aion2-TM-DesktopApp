"""Integration tests for where the app decides to keep user data.

`MainWindow._resolve_profile_dir` is the highest-blast-radius function in the
port -- it decides where every profile lives -- and the helpers underneath it
(`utils.paths.install_root` / `is_portable`) are only correct in combination.
These tests therefore drive the CALLER with a faked frozen layout rather than
the helpers in isolation: the bug they guard against (a marker looked up in
`sys._MEIPASS` while the folder it unlocks sits next to the executable) is
invisible to any test of either side alone.

MainWindow is instantiated via `__new__` with just the two attributes the
method reads: constructing a real window costs ~0.8 s and pulls in the entire
UI for a decision that touches none of it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import ui.main_window as mw
from utils import paths


@pytest.fixture
def frozen_install(tmp_path, monkeypatch):
    """A PyInstaller onedir layout: <install>/Aion2 TM.exe + <install>/_internal."""
    install = tmp_path / "install"
    internal = install / "_internal"
    internal.mkdir(parents=True)
    exe = install / "Aion2 TM.exe"
    exe.write_bytes(b"")

    monkeypatch.setattr(mw.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(exe))
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(internal), raising=False)
    return install


def _resolver(project_root: Path, config_path: Path | None = None):
    """A MainWindow carrying only what _resolve_profile_dir reads."""
    win = mw.MainWindow.__new__(mw.MainWindow)
    win.project_root = project_root
    win.app_config_path = config_path or (project_root / "does-not-exist.json")
    return win


# ── B1: the marker must be looked up next to the EXECUTABLE ──────────────

def test_install_root_is_the_exe_dir_not_meipass(frozen_install):
    # The whole defect in one assertion: these two are different directories
    # for a onedir build, and the portable marker belongs to the first.
    assert paths.install_root() == frozen_install
    assert paths.app_root() == frozen_install / "_internal"
    assert paths.install_root() != paths.app_root()


def test_marker_next_to_the_exe_enables_portable_mode(frozen_install):
    (frozen_install / "profiles").mkdir()
    paths.portable_marker(paths.install_root()).write_text("", encoding="utf-8")

    win = _resolver(frozen_install)
    resolved = win._resolve_profile_dir()

    assert resolved == frozen_install / "profiles"
    # The marker directory and the directory being unlocked are the same one.
    assert paths.portable_marker(paths.install_root()).parent == resolved.parent


def test_marker_inside_meipass_does_not_enable_portable_mode(frozen_install):
    # Regression guard for the shipped-but-unreachable feature: a marker in
    # <install>/_internal is NOT where the documentation puts it, and an empty
    # profiles/ folder alone must not flip an install into portable mode.
    (frozen_install / "profiles").mkdir()
    paths.portable_marker(paths.app_root()).write_text("", encoding="utf-8")

    assert _resolver(frozen_install)._resolve_profile_dir() == paths.default_profiles_dir()


# ── M1: an existing frozen profiles/ keeps working without a marker ──────

def test_existing_profiles_folder_with_json_is_kept(frozen_install):
    local = frozen_install / "profiles"
    local.mkdir()
    (local / "Default.json").write_text("{}", encoding="utf-8")

    assert _resolver(frozen_install)._resolve_profile_dir() == local


def test_empty_profiles_folder_without_marker_is_refused(frozen_install):
    # An installer that merely creates the folder must not redirect a fresh
    # install away from %APPDATA%.
    (frozen_install / "profiles").mkdir()

    assert _resolver(frozen_install)._resolve_profile_dir() == paths.default_profiles_dir()


def test_no_profiles_folder_falls_back_to_the_user_data_dir(frozen_install):
    assert _resolver(frozen_install)._resolve_profile_dir() == paths.default_profiles_dir()


def test_stale_config_path_falls_back_to_the_existing_profiles_folder(frozen_install, tmp_path):
    # The exact scenario that used to look like data loss: config.json points
    # at a path that no longer resolves (moved folder, changed drive letter)
    # and the install has its own profiles/ next to the exe.
    local = frozen_install / "profiles"
    local.mkdir()
    (local / "Main.json").write_text("{}", encoding="utf-8")
    config = frozen_install / "config.json"
    config.write_text('{"profile_dir": "%s"}' % (tmp_path / "gone" / "Profiles"), encoding="utf-8")

    win = _resolver(frozen_install, config)
    assert win._resolve_profile_dir() == local


def test_valid_config_path_wins_over_everything(frozen_install, tmp_path):
    chosen = tmp_path / "elsewhere"
    chosen.mkdir()
    local = frozen_install / "profiles"
    local.mkdir()
    (local / "Main.json").write_text("{}", encoding="utf-8")
    paths.portable_marker(paths.install_root()).write_text("", encoding="utf-8")
    config = frozen_install / "config.json"
    config.write_text('{"profile_dir": "%s"}' % chosen, encoding="utf-8")

    win = _resolver(frozen_install, config)
    assert win._resolve_profile_dir() == chosen


# ── running from source is unchanged ─────────────────────────────────────

def test_from_source_a_bare_profiles_folder_is_enough(tmp_path, monkeypatch):
    monkeypatch.setattr(mw.sys, "frozen", False, raising=False)
    monkeypatch.setattr(paths.sys, "frozen", False, raising=False)
    local = tmp_path / "profiles"
    local.mkdir()

    assert _resolver(tmp_path)._resolve_profile_dir() == local


def test_from_source_without_a_profiles_folder_uses_the_user_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(mw.sys, "frozen", False, raising=False)
    monkeypatch.setattr(paths.sys, "frozen", False, raising=False)

    assert _resolver(tmp_path)._resolve_profile_dir() == paths.default_profiles_dir()
