"""Platform-abstraction tests: utils.paths, core.sound, core.platform.

Every OS branch is asserted from Linux by injecting ``platform=``/``env=``
instead of monkeypatching ``sys.platform`` -- the Windows layout in
particular must stay byte-identical to the pre-port hardcoded paths, and
that claim is worthless if it can only be checked on Windows.

Nothing here executes an external program: the launcher tests assert the
argv that *would* be spawned.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from core import platform as cplatform
from core import sound
from utils import paths

WIN_ENV = {
    "APPDATA": r"C:\Users\Tester\AppData\Roaming",
    "LOCALAPPDATA": r"C:\Users\Tester\AppData\Local",
    "USERPROFILE": r"C:\Users\Tester",
}
MAC_ENV = {"HOME": "/Users/tester"}
LINUX_ENV = {"HOME": "/home/tester"}


# ── utils.paths: Windows must not move ────────────────────────────────────

def test_windows_data_dir_is_appdata_app_name():
    assert paths.user_data_dir("win32", WIN_ENV) == Path(r"C:\Users\Tester\AppData\Roaming") / "Aion2 TM"


def test_windows_profiles_dir_matches_legacy_hardcoded_path():
    # Exactly what ui/main_window.py:2523 built: %APPDATA%\Aion2 TM\Profiles
    assert paths.default_profiles_dir("win32", WIN_ENV) == (
        Path(r"C:\Users\Tester\AppData\Roaming") / "Aion2 TM" / "Profiles"
    )


def test_windows_config_and_log_share_the_data_dir():
    # config.json and app.log have always sat next to each other in APPDATA.
    data = paths.user_data_dir("win32", WIN_ENV)
    assert paths.user_config_dir("win32", WIN_ENV) == data
    assert paths.user_log_dir("win32", WIN_ENV) == data


def test_windows_cache_dir_uses_localappdata():
    assert paths.user_cache_dir("win32", WIN_ENV) == Path(r"C:\Users\Tester\AppData\Local") / "Aion2 TM" / "Cache"


def test_windows_falls_back_to_userprofile_when_appdata_is_unset():
    # The old code raised KeyError here; we resolve the canonical location.
    # (Joined component-wise: on this Linux host a Windows string is a single
    # PosixPath component, so the comparison must be built the same way.)
    env = {"USERPROFILE": r"C:\Users\Tester"}
    expected = Path(r"C:\Users\Tester") / "AppData" / "Roaming" / "Aion2 TM"
    assert paths.user_data_dir("win32", env) == expected


# ── utils.paths: Linux honours XDG ────────────────────────────────────────

def test_linux_defaults_without_xdg_vars():
    assert paths.user_data_dir("linux", LINUX_ENV) == Path("/home/tester/.local/share/aion2-tm")
    assert paths.user_config_dir("linux", LINUX_ENV) == Path("/home/tester/.config/aion2-tm")
    assert paths.user_cache_dir("linux", LINUX_ENV) == Path("/home/tester/.cache/aion2-tm")
    assert paths.user_log_dir("linux", LINUX_ENV) == Path("/home/tester/.local/state/aion2-tm")


def test_linux_honours_xdg_overrides():
    env = {
        "HOME": "/home/tester",
        "XDG_DATA_HOME": "/xdg/data",
        "XDG_CONFIG_HOME": "/xdg/config",
        "XDG_CACHE_HOME": "/xdg/cache",
        "XDG_STATE_HOME": "/xdg/state",
    }
    assert paths.user_data_dir("linux", env) == Path("/xdg/data/aion2-tm")
    assert paths.user_config_dir("linux", env) == Path("/xdg/config/aion2-tm")
    assert paths.user_cache_dir("linux", env) == Path("/xdg/cache/aion2-tm")
    assert paths.user_log_dir("linux", env) == Path("/xdg/state/aion2-tm")


def test_relative_xdg_value_is_ignored_per_spec():
    env = {"HOME": "/home/tester", "XDG_DATA_HOME": "relative/path"}
    assert paths.user_data_dir("linux", env) == Path("/home/tester/.local/share/aion2-tm")


def test_linux_config_is_separate_from_data():
    assert paths.user_config_dir("linux", LINUX_ENV) != paths.user_data_dir("linux", LINUX_ENV)


# ── utils.paths: macOS ────────────────────────────────────────────────────

def test_macos_library_layout():
    assert paths.user_data_dir("darwin", MAC_ENV) == Path("/Users/tester/Library/Application Support/Aion2 TM")
    assert paths.user_config_dir("darwin", MAC_ENV) == paths.user_data_dir("darwin", MAC_ENV)
    assert paths.user_cache_dir("darwin", MAC_ENV) == Path("/Users/tester/Library/Caches/Aion2 TM")
    assert paths.user_log_dir("darwin", MAC_ENV) == Path("/Users/tester/Library/Logs/Aion2 TM")


# ── utils.paths: misc helpers ─────────────────────────────────────────────

def test_app_root_from_source_is_the_repo_root():
    root = paths.app_root()
    assert (root / "utils" / "paths.py").is_file()
    assert not paths.is_frozen()


def test_portable_marker_detection(tmp_path):
    assert paths.portable_marker(tmp_path) == tmp_path / "portable.txt"
    assert paths.is_portable(tmp_path) is False
    paths.portable_marker(tmp_path).write_text("", encoding="utf-8")
    assert paths.is_portable(tmp_path) is True


def test_portable_marker_must_be_a_file_not_a_directory(tmp_path):
    (tmp_path / "portable.txt").mkdir()
    assert paths.is_portable(tmp_path) is False


def test_ensure_dir_creates_nested_and_is_idempotent(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    assert paths.ensure_dir(target) == target
    assert target.is_dir()
    assert paths.ensure_dir(target) == target


# ── core.sound ────────────────────────────────────────────────────────────

def test_system_sound_dirs_windows_is_windows_media():
    assert sound.system_sound_dirs("win32") in ([Path(r"C:\Windows\Media")], [])


def test_system_sound_dirs_filters_to_existing(tmp_path):
    # A per-user sound dir under a fake HOME is picked up; the missing one is not.
    user_sounds = tmp_path / ".local" / "share" / "sounds"
    user_sounds.mkdir(parents=True)

    dirs = sound.system_sound_dirs("linux", {"HOME": str(tmp_path)})
    assert user_sounds in dirs
    assert all(d.is_dir() for d in dirs)

    empty_home = tmp_path / "nobody"
    assert user_sounds not in sound.system_sound_dirs("linux", {"HOME": str(empty_home)})


def test_system_sound_dirs_macos():
    assert sound.system_sound_dirs("darwin", MAC_ENV) in ([Path("/System/Library/Sounds")], [])


def test_list_system_wavs_globs_dedupes_and_sorts(tmp_path, monkeypatch):
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    (first / "Zeta.wav").write_bytes(b"")
    (first / "alpha.wav").write_bytes(b"")
    (first / "notes.txt").write_bytes(b"")
    (second / "Mid.wav").write_bytes(b"")

    monkeypatch.setattr(sound, "system_sound_dirs", lambda *a, **k: [first, second, first])

    found = sound.list_system_wavs()
    assert [w.stem for w in found] == ["alpha", "Mid", "Zeta"]
    assert len(found) == len(set(map(str, found)))


def test_list_system_wavs_survives_an_unreadable_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(sound, "system_sound_dirs", lambda *a, **k: [tmp_path / "gone"])
    assert sound.list_system_wavs() == []


def test_play_wav_none_returns_false_without_raising():
    assert sound.play_wav(None) is False
    assert sound.play_wav("") is False


def test_play_wav_missing_file_returns_false(tmp_path):
    assert sound.play_wav(tmp_path / "nope.wav") is False


def test_play_wav_falls_back_to_cli_player(tmp_path, monkeypatch):
    wav = tmp_path / "beep.wav"
    wav.write_bytes(b"")
    spawned: list[list[str]] = []

    def fake_qt(_path, _loop):
        raise RuntimeError("no QtMultimedia")

    monkeypatch.setattr(sound, "_play_qt", fake_qt)
    monkeypatch.setattr(sound.shutil, "which", lambda name: f"/usr/bin/{name}" if name == "paplay" else None)
    monkeypatch.setattr(sound.subprocess, "Popen", lambda argv, **kw: spawned.append(argv))

    assert sound.play_wav(wav) is True
    assert spawned == [["/usr/bin/paplay", str(wav)]]


def test_play_wav_returns_false_when_no_backend_exists(tmp_path, monkeypatch):
    wav = tmp_path / "beep.wav"
    wav.write_bytes(b"")
    monkeypatch.setattr(sound, "_play_qt", lambda *a: (_ for _ in ()).throw(RuntimeError("none")))
    monkeypatch.setattr(sound.shutil, "which", lambda name: None)
    assert sound.play_wav(wav) is False


def test_stop_never_raises():
    sound.stop()


# ── core.platform: file manager ───────────────────────────────────────────

@pytest.fixture
def spawned(monkeypatch):
    """Capture argv/cwd instead of starting anything."""
    calls: list[tuple[list[str], str | None]] = []
    monkeypatch.setattr(
        cplatform.subprocess, "Popen",
        lambda argv, cwd=None, **kw: calls.append((argv, cwd)),
    )
    return calls


def test_reveal_on_linux_opens_the_parent_directory(spawned, tmp_path):
    target = tmp_path / "profiles" / "Default.json"
    target.parent.mkdir()
    target.write_text("{}", encoding="utf-8")

    assert cplatform.reveal_in_file_manager(target, platform="linux") is True
    assert spawned == [(["xdg-open", str(target.parent)], None)]


def test_reveal_on_windows_builds_the_explorer_select_argv(spawned):
    target = Path(r"C:\Users\Tester\AppData\Roaming\Aion2 TM\app.log")

    assert cplatform.reveal_in_file_manager(target, platform="win32") is True
    assert spawned == [(["explorer", "/select,", str(target)], None)]


def test_reveal_on_macos_uses_open_dash_r(spawned, tmp_path):
    assert cplatform.reveal_in_file_manager(tmp_path / "x.json", platform="darwin") is True
    assert spawned[0][0] == ["open", "-R", str(tmp_path / "x.json")]


def test_reveal_reports_false_when_the_spawn_fails(monkeypatch, tmp_path):
    def boom(*a, **kw):
        raise OSError("xdg-open missing")

    monkeypatch.setattr(cplatform.subprocess, "Popen", boom)
    assert cplatform.reveal_in_file_manager(tmp_path, platform="linux") is False


def test_open_path_dispatch(spawned, tmp_path):
    assert cplatform.open_path(tmp_path, platform="linux") is True
    assert cplatform.open_path(tmp_path, platform="darwin") is True
    assert [argv[0] for argv, _ in spawned] == ["xdg-open", "open"]


# ── core.platform: external launcher ──────────────────────────────────────

def test_launch_external_runs_a_native_binary_in_its_own_directory(spawned, tmp_path):
    binary = tmp_path / "tools" / "dps-meter"
    binary.parent.mkdir()
    binary.write_text("#!/bin/sh\n", encoding="utf-8")

    assert cplatform.launch_external(binary, platform="linux") is True
    assert spawned == [([str(binary)], str(binary.parent))]


def test_launch_external_routes_an_exe_through_wine(spawned, tmp_path, monkeypatch):
    exe = tmp_path / "dps_meter.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(cplatform.shutil, "which", lambda name: "/usr/bin/wine" if name == "wine" else None)

    assert cplatform.launch_external(exe, platform="linux") is True
    assert spawned == [(["/usr/bin/wine", str(exe)], str(tmp_path))]


def test_launch_external_refuses_an_exe_without_wine(spawned, tmp_path, monkeypatch):
    exe = tmp_path / "dps_meter.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(cplatform.shutil, "which", lambda name: None)

    assert cplatform.launch_external(exe, platform="linux") is False
    assert spawned == []


def test_launch_external_missing_file_is_false(spawned, tmp_path):
    assert cplatform.launch_external(tmp_path / "absent", platform="linux") is False
    assert spawned == []


def test_shellexecute_is_a_no_op_off_windows(tmp_path):
    assert cplatform.launch_windows_shellexecute(tmp_path / "dps_meter.exe") is False


# ── core.platform: session ────────────────────────────────────────────────

def test_is_wayland_from_environment_when_no_qt_app_exists(monkeypatch):
    monkeypatch.setattr(cplatform, "_qt_platform_name", lambda: None)
    assert cplatform.is_wayland({"XDG_SESSION_TYPE": "wayland"}) is True
    assert cplatform.is_wayland({"WAYLAND_DISPLAY": "wayland-1"}) is True
    assert cplatform.is_wayland({"XDG_SESSION_TYPE": "X11"}) is False
    assert cplatform.is_wayland({}) is False


def test_is_wayland_prefers_qts_own_platform_name(monkeypatch):
    # A running Qt app is authoritative: XWayland reports "xcb" even though
    # WAYLAND_DISPLAY is set in the very same session.
    monkeypatch.setattr(cplatform, "_qt_platform_name", lambda: "xcb")
    assert cplatform.is_wayland({"WAYLAND_DISPLAY": "wayland-1"}) is False
    monkeypatch.setattr(cplatform, "_qt_platform_name", lambda: "wayland")
    assert cplatform.is_wayland({}) is True


def test_tray_available_is_false_without_a_qapplication():
    # Regression guard: isSystemTrayAvailable() segfaults when called before
    # QApplication exists, so the helper must short-circuit on the instance.
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        assert cplatform.tray_available() is False
    else:
        assert isinstance(cplatform.tray_available(), bool)


def test_tray_available_queries_qt_once_an_application_exists(qapp):
    assert isinstance(cplatform.tray_available(), bool)


def test_placeholder_exe_path_per_platform():
    assert cplatform.platform_placeholder_exe_path("win32") == "C:\\...\\dps_meter.exe"
    assert cplatform.platform_placeholder_exe_path("linux") == "/path/to/dps-meter"
    assert cplatform.platform_placeholder_exe_path("darwin") == "/path/to/dps-meter"


def test_no_module_imports_winsound_on_this_host():
    # Guards against a module-level `import winsound` creeping back in.
    import sys as _sys

    assert "winsound" not in _sys.modules or _sys.platform == "win32"
    assert subprocess  # module kept imported for the fixtures above


# ── the shared notification-sound picker (ui.pages.settings_page) ─────────

@pytest.fixture
def picker(qapp):
    from PySide6.QtWidgets import QComboBox

    return QComboBox()


def _rows(combo):
    return [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())]


def test_picker_leads_with_browse_when_no_system_wavs(picker, monkeypatch):
    from ui.pages import settings_page as sp

    monkeypatch.setattr(sp, "list_system_wavs", lambda *a, **k: [])
    sp.populate_sound_combo(picker)
    assert _rows(picker) == [("-- No Sound --", ""), ("Browse...", sp.SOUND_BROWSE_DATA)]


def test_picker_keeps_the_windows_order_and_trails_browse(picker, monkeypatch, tmp_path):
    # With system sounds present (Windows), the list must read exactly as it
    # always did -- sentinel, then the sorted sounds -- with Browse appended.
    from ui.pages import settings_page as sp

    wavs = [tmp_path / "Alarm.wav", tmp_path / "Chime.wav"]
    monkeypatch.setattr(sp, "list_system_wavs", lambda *a, **k: wavs)
    sp.populate_sound_combo(picker)
    assert [text for text, _ in _rows(picker)] == ["-- No Sound --", "Alarm", "Chime", "Browse..."]


def test_picker_keeps_an_unknown_saved_path_selected(picker, monkeypatch):
    from ui.pages import settings_page as sp

    monkeypatch.setattr(sp, "list_system_wavs", lambda *a, **k: [])
    sp.populate_sound_combo(picker, "/home/u/sounds/custom.wav")
    assert picker.currentData() == "/home/u/sounds/custom.wav"
    assert picker.currentText() == "custom"


def test_picker_translates_both_labels(picker, monkeypatch):
    from core.translations import tr
    from ui.pages import settings_page as sp

    monkeypatch.setattr(sp, "list_system_wavs", lambda *a, **k: [])
    sp.populate_sound_combo(picker, "", tr, "de")
    assert _rows(picker) == [("-- Kein Sound --", ""), ("Durchsuchen...", sp.SOUND_BROWSE_DATA)]


def test_browse_for_wav_inserts_and_selects(picker, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from ui.pages import settings_page as sp

    monkeypatch.setattr(sp, "list_system_wavs", lambda *a, **k: [])
    sp.populate_sound_combo(picker)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("/tmp/picked.wav", "")))

    assert sp.browse_for_wav(None, picker, 0) == "/tmp/picked.wav"
    assert picker.currentData() == "/tmp/picked.wav"


def test_browse_for_wav_cancel_restores_the_previous_row(picker, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from ui.pages import settings_page as sp

    monkeypatch.setattr(sp, "list_system_wavs", lambda *a, **k: [])
    sp.populate_sound_combo(picker)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))

    assert sp.browse_for_wav(None, picker, 0) == ""
    assert picker.currentIndex() == 0
    assert picker.currentData() == ""
