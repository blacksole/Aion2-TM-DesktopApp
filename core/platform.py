"""Platform-dispatched desktop integration: file manager, external launcher,
tray availability, session type.

One home for every construct that used to be spelled in Windows only:

* ``explorer /select,`` (``ui/pages/settings_page.py:227``) and
  ``explorer "<dir>"`` (``:2068``)
* ``ctypes.windll.shell32.ShellExecuteExW`` for the external DPS-meter
  (``ui/main_window.py:1843-1897``) -- kept verbatim behind
  :func:`launch_windows_shellexecute`, UAC semantics and all
* the unconditional ``QSystemTrayIcon`` (``ui/main_window.py:1727-1740``)
* the ``C:\\...\\dps_meter.exe`` placeholder (``ui/pages/settings_page.py:1624``)

Every function swallows its exceptions, logs, and reports success as a bool:
these are all "best effort, the app keeps running" operations.
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


def _log():
    return get_logger("platform")


def _plat(platform: str | None) -> str:
    return sys.platform if platform is None else platform


def _envmap(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _spawn(argv: list[str], cwd: str | None = None) -> bool:
    subprocess.Popen(argv, cwd=cwd)
    return True


# ── file manager ──────────────────────────────────────────────────────────

def reveal_in_file_manager(path: Path, platform: str | None = None) -> bool:
    """Show ``path`` in the desktop file manager, selected where supported.

    win32 ``explorer /select,<path>`` (byte-identical to the current call) ·
    darwin ``open -R <path>`` · else ``xdg-open <parent>``, since no portable
    Linux verb selects a file inside its folder.
    """
    try:
        target = Path(path)
        p = _plat(platform)
        if p == _WIN:
            return _spawn(["explorer", "/select,", str(target)])
        if p == _MAC:
            return _spawn(["open", "-R", str(target)])
        parent = target.parent if target.parent != target else target
        return _spawn(["xdg-open", str(parent)])
    except Exception as exc:
        _log().warning("could not reveal %s: %s", path, exc)
        return False


def open_path(path: Path | str, platform: str | None = None) -> bool:
    """Open a file or directory with the desktop's default handler."""
    try:
        target = Path(path)
        p = _plat(platform)
        if p == _WIN:
            startfile = getattr(os, "startfile", None)
            if startfile is None:
                return False
            startfile(str(target))
            return True
        if p == _MAC:
            return _spawn(["open", str(target)])
        return _spawn(["xdg-open", str(target)])
    except Exception as exc:
        _log().warning("could not open %s: %s", path, exc)
        return False


# ── external programs ─────────────────────────────────────────────────────

def launch_windows_shellexecute(path: Path | str) -> bool:
    """Launch ``path`` through ShellExecuteEx with ``SEE_MASK_FLAG_NO_UI``.

    Verbatim port of ``MainWindow._start_dps_meter``: ShellExecuteEx rather
    than the simpler ``os.startfile`` because ``SEE_MASK_FLAG_NO_UI``
    suppresses the SHELL's follow-up error dialog (missing file, access
    denied, *elevation cancelled*). User-reported 2026-08-30: declining the
    UAC prompt for a DPS meter that needs admin rights popped a SECOND
    "elevation failed" dialog carrying our own taskbar icon, since we are the
    process that requested the launch. The UAC consent prompt itself is a
    Windows security boundary and is NOT suppressed -- a declined elevation
    now just comes back as an error code we log.

    Returns False on any non-Windows host.
    """
    if sys.platform != _WIN:
        _log().debug("ShellExecuteEx requested off-Windows; ignored")
        return False

    import ctypes
    from ctypes import wintypes

    target = str(path)

    class _SHELLEXECUTEINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", ctypes.c_ulong),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hKeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIcon", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    SEE_MASK_NOCLOSEPROCESS = 0x00000040
    SEE_MASK_FLAG_NO_UI = 0x00000400
    SW_SHOWNORMAL = 1

    try:
        sei = _SHELLEXECUTEINFO()
        sei.cbSize = ctypes.sizeof(sei)
        sei.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_FLAG_NO_UI
        sei.hwnd = None
        sei.lpVerb = "open"
        sei.lpFile = target
        sei.lpParameters = None
        sei.lpDirectory = os.path.dirname(target) or None
        sei.nShow = SW_SHOWNORMAL
        sei.hInstApp = None

        ok = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
        if not ok:
            error = ctypes.get_last_error()
            _log().warning(
                "external program did not start (error=%s, e.g. UAC elevation was declined) -- "
                "no popup shown, see SEE_MASK_FLAG_NO_UI note above", error,
            )
            return False
        _log().info("external program started: %s", target)
        return True
    except Exception as exc:
        _log().error("external program failed to start: %s", exc)
        return False


def launch_external(path: Path | str, *, elevate_hint: bool = False, platform: str | None = None) -> bool:
    """Launch a user-configured external program (today: the DPS meter).

    win32 goes through :func:`launch_windows_shellexecute` so the UAC
    behaviour above is preserved. Elsewhere a plain ``Popen`` with the
    program's own directory as cwd is the correct equivalent; a Windows
    ``.exe`` handed to us on Linux is routed through ``wine`` when it is on
    PATH, and refused (logged, no dialog) when it is not.

    ``elevate_hint`` records that the caller expects the target to request
    elevation. It is informational -- no platform here escalates on its own.
    """
    try:
        target = Path(path)
        if not str(target):
            return False
        p = _plat(platform)
        if p == _WIN:
            if not target.is_file():
                _log().warning("external program not found: %s", target)
                return False
            return launch_windows_shellexecute(target)

        if not target.is_file():
            _log().warning("external program not found: %s", target)
            return False
        cwd = str(target.parent) or None
        if target.suffix.lower() == ".exe":
            wine = shutil.which("wine")
            if not wine:
                _log().warning("cannot run the Windows executable %s: wine is not installed", target)
                return False
            if elevate_hint:
                _log().debug("elevation hint ignored under wine for %s", target)
            return _spawn([wine, str(target)], cwd=cwd)
        return _spawn([str(target)], cwd=cwd)
    except Exception as exc:
        _log().error("external program failed to start: %s", exc)
        return False


# ── desktop session ───────────────────────────────────────────────────────

def _qt_platform_name() -> str | None:
    """Qt's own platform plugin name, lowercased, or None when no Qt
    application is running yet (the authoritative answer only exists once
    QGuiApplication has picked a plugin). Separate from :func:`is_wayland`
    so the environment fallback stays testable."""
    try:
        from PySide6.QtGui import QGuiApplication

        if QGuiApplication.instance() is None:
            return None
        return QGuiApplication.platformName().lower()
    except Exception as exc:
        _log().debug("Qt platform name unavailable (%s); reading the environment", exc)
        return None



def tray_available() -> bool:
    """True when a system tray / StatusNotifier host is actually present.

    Never assume: on a bare Wayland session without a StatusNotifier host the
    tray icon silently does nothing, taking minimize-to-tray and every toast
    with it.

    ``QSystemTrayIcon.isSystemTrayAvailable()`` **segfaults** when no
    QApplication exists yet (verified on PySide6 6.11 -- it touches the
    platform theme through a null app pointer), so the instance check is a
    hard requirement, not a nicety: this must never be called from module
    import time or before ``QApplication(...)`` is constructed.
    """
    try:
        from PySide6.QtWidgets import QApplication, QSystemTrayIcon

        if QApplication.instance() is None:
            _log().debug("tray checked before the QApplication exists; assuming none")
            return False
        return bool(QSystemTrayIcon.isSystemTrayAvailable())
    except Exception as exc:
        _log().debug("tray availability unknown (%s); assuming none", exc)
        return False


def is_wayland(env: Mapping[str, str] | None = None) -> bool:
    """True on a native Wayland session (not XWayland).

    Qt's own platform name is authoritative once an application exists; before
    that, fall back to the session environment. Callers need this because
    ``WindowStaysOnTopHint`` and explicit geometry are not honoured for
    xdg-shell clients -- the overlay window's hard constraint.
    """
    name = _qt_platform_name()
    if name is not None:
        return name == "wayland"

    e = _envmap(env)
    if (e.get("XDG_SESSION_TYPE") or "").lower() == "wayland":
        return True
    return bool(e.get("WAYLAND_DISPLAY"))


def platform_placeholder_exe_path(platform: str | None = None) -> str:
    """Placeholder text for the "external program" path field."""
    return "C:\\...\\dps_meter.exe" if _plat(platform) == _WIN else "/path/to/dps-meter"
