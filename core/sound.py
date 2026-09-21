"""Notification-sound playback, one choke point for every platform.

Replaces the three module-level ``import winsound`` + four ``PlaySound`` call
sites (``ui/main_window.py:6,1907,2077``, ``ui/custom_timer_dialog.py:3,480``,
``ui/pages/settings_page.py:5,1459``) and the ``C:\\Windows\\Media\\*.wav`` glob
used to populate the sound pickers.

Backend selection:

* **win32** -- ``winsound.PlaySound`` with exactly the flags the call sites
  use today (``SND_FILENAME | SND_ASYNC``, plus ``SND_LOOP`` when looping).
  Kept rather than replaced: it is zero-latency, has no Qt dependency and is
  what the existing Windows builds shipped.
* **elsewhere** -- ``QSoundEffect`` (QtMultimedia): async, WAV, no new pip
  dependency. A single module-level instance is kept alive, because a
  garbage-collected QSoundEffect stops mid-sound.
* **fallback** -- ``paplay``/``aplay``/``afplay`` if QtMultimedia is missing
  (it is excluded from some builds) or no QApplication exists yet.

Nothing in here raises: a notification sound that fails must never take down
the notification, let alone the app. Every entry point returns a bool.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from core.app_logger import get_logger

_WIN = "win32"
_MAC = "darwin"

#: Kept alive at module scope -- a collected QSoundEffect cuts its own sound off.
_effect = None
#: Handle on the external player started by the CLI fallback, so stop() can kill it.
_proc: subprocess.Popen | None = None

_CLI_PLAYERS = ("paplay", "aplay", "afplay")


def _log():
    return get_logger("sound")


def _plat(platform: str | None) -> str:
    return sys.platform if platform is None else platform


def _envmap(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


# ── playback ──────────────────────────────────────────────────────────────

def _play_winsound(path: Path, loop: bool) -> bool:
    import winsound

    flags = winsound.SND_FILENAME | winsound.SND_ASYNC
    if loop:
        flags |= winsound.SND_LOOP
    winsound.PlaySound(str(path), flags)
    return True


def _play_qt(path: Path, loop: bool) -> bool:
    global _effect

    from PySide6.QtCore import QCoreApplication, QUrl
    from PySide6.QtMultimedia import QSoundEffect

    if QCoreApplication.instance() is None:
        # QSoundEffect needs a running Qt application; without one it would
        # silently never play. Let the caller fall through to the CLI player.
        raise RuntimeError("no QCoreApplication instance")

    if _effect is None:
        _effect = QSoundEffect()
    _effect.setSource(QUrl.fromLocalFile(str(path)))
    _effect.setLoopCount(QSoundEffect.Loop.Infinite.value if loop else 1)
    _effect.play()
    return True


def _play_cli(path: Path, loop: bool) -> bool:
    global _proc

    for name in _CLI_PLAYERS:
        binary = shutil.which(name)
        if not binary:
            continue
        argv = [binary, str(path)]
        _proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if loop:
            _log().debug("looping not supported by the %s fallback; played once", name)
        return True
    _log().warning("no sound backend available for %s", path)
    return False


def play_wav(path: str | Path | None, *, loop: bool = False) -> bool:
    """Play a .wav asynchronously. Returns True if a backend accepted it.

    A falsy path, a missing file or a dead backend is a quiet False -- never
    an exception, and never a dialog.
    """
    if not path:
        return False
    try:
        target = Path(path)
        if not target.is_file():
            _log().debug("sound file not found: %s", target)
            return False

        if _plat(None) == _WIN:
            return _play_winsound(target, loop)

        try:
            return _play_qt(target, loop)
        except Exception as exc:  # QtMultimedia absent, or no QApplication yet
            _log().debug("QSoundEffect unavailable (%s); falling back to a CLI player", exc)
            return _play_cli(target, loop)
    except Exception as exc:
        _log().warning("could not play %s: %s", path, exc)
        return False


def stop() -> None:
    """Stop whatever this module is currently playing. Never raises."""
    global _proc

    try:
        if _plat(None) == _WIN:
            import winsound

            winsound.PlaySound(None, winsound.SND_PURGE)
            return
        if _effect is not None:
            _effect.stop()
        if _proc is not None and _proc.poll() is None:
            _proc.terminate()
        _proc = None
    except Exception as exc:
        _log().debug("stop() failed: %s", exc)


# ── system sound discovery ────────────────────────────────────────────────

def system_sound_dirs(platform: str | None = None, env: Mapping[str, str] | None = None) -> list[Path]:
    """Directories to scan for ready-made notification sounds, existing ones only."""
    p = _plat(platform)
    if p == _WIN:
        candidates = [Path(r"C:\Windows\Media")]
    elif p == _MAC:
        candidates = [Path("/System/Library/Sounds")]
    else:
        e = _envmap(env)
        home = Path(e.get("HOME") or Path.home())
        candidates = [
            Path("/usr/share/sounds"),
            Path("/usr/share/sounds/freedesktop/stereo"),
            home / ".local" / "share" / "sounds",
        ]
    out: list[Path] = []
    for directory in candidates:
        try:
            if directory.is_dir():
                out.append(directory)
        except OSError:
            continue
    return out


def list_system_wavs(platform: str | None = None, env: Mapping[str, str] | None = None) -> list[Path]:
    """Every .wav found in :func:`system_sound_dirs`, de-duplicated -- the
    cross-platform drop-in for ``get_windows_sounds()`` and
    ``SettingsPage._populate_sound_combo``'s hardcoded glob.

    Sorted by full path, case-sensitively, which is exactly what the
    ``sorted(glob.glob(r"C:\\Windows\\Media\\*.wav"))`` it replaces produced:
    on Windows that puts ``Ring01`` before ``chimes`` (uppercase first), and
    the notification-sound combo keeps the order users know. A case-insensitive
    sort would read better but would silently reorder the Windows picker.
    """
    seen: set[str] = set()
    found: list[Path] = []
    for directory in system_sound_dirs(platform, env):
        try:
            entries = sorted(directory.glob("*.wav"))
        except OSError as exc:
            _log().debug("cannot list %s: %s", directory, exc)
            continue
        for wav in entries:
            try:
                key = str(wav.resolve())
            except OSError:
                key = str(wav)
            if key in seen:
                continue
            seen.add(key)
            found.append(wav)
    return sorted(found, key=str)
