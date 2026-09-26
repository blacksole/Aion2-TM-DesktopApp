"""Cross-platform application directories for Aion2 TM.

Stdlib only, Qt-free, no third-party dependency (deliberately *not*
``platformdirs``): this module is imported by ``core.app_logger`` and by the
frozen build's earliest start-up path, where an extra wheel would cost both
launch time and packaging surface.

Every resolver accepts an optional ``platform`` (defaults to ``sys.platform``)
and ``env`` (defaults to ``os.environ``) mapping, so all three OS branches are
exercisable from any host -- the test-suite runs on Linux and still asserts the
exact Windows layout.

The Windows layout is byte-identical to the pre-port hardcoded paths it
replaces (``ui/main_window.py:337,2523``, ``core/app_logger.py:21``)::

    %APPDATA%\\Aion2 TM              config.json, app.log
    %APPDATA%\\Aion2 TM\\Profiles     profile .json files

The only behavioural difference: when ``%APPDATA%`` is unset the old code
raised ``KeyError``; here it falls back to ``%USERPROFILE%\\AppData\\Roaming``,
which is what the variable points at on every sane Windows install anyway.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

APP_NAME = "Aion2 TM"
APP_SLUG = "aion2-tm"

PORTABLE_MARKER_NAME = "portable.txt"

_WIN = "win32"
_MAC = "darwin"


def _plat(platform: str | None) -> str:
    return sys.platform if platform is None else platform


def _envmap(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _home(env: Mapping[str, str] | None = None) -> Path:
    """Home directory, honouring the supplied environment mapping first.

    ``Path.home()`` reads the *process* environment, which would defeat the
    ``env=`` injection used by the tests, so HOME/USERPROFILE win when present.
    """
    e = _envmap(env)
    for key in ("HOME", "USERPROFILE"):
        value = e.get(key)
        if value:
            return Path(value)
    return Path.home()


def _xdg(env: Mapping[str, str] | None, var: str, fallback: str) -> Path:
    """An XDG base directory: the variable when set to an *absolute* path,
    else the spec-mandated fallback relative to home (the XDG basedir spec
    requires relative values to be ignored).

    The absolute check is a plain string ``startswith("/")``, not
    ``Path(value).is_absolute()``: on a Windows *host*,
    ``Path("/xdg/data").is_absolute()`` is False (no drive letter), which
    would silently take the "relative value, ignore it" branch below even
    for a genuinely absolute POSIX override -- this branch is exercised from
    Windows dev machines via the ``platform=`` injection (see
    test_platform.py's module docstring), not just real Linux hosts. Still
    returns a plain ``Path`` (unlike a ``PurePosixPath`` attempt at this same
    fix): callers ``mkdir()`` these on a real Linux host, e.g.
    ``ensure_dir(user_cache_dir() / "armory")`` in ItemDatabase/app.py.
    """
    value = _envmap(env).get(var, "")
    if value.startswith("/"):
        return Path(value)
    return _home(env) / fallback


def _windows_roaming(env: Mapping[str, str] | None) -> Path:
    value = _envmap(env).get("APPDATA", "")
    if value:
        return Path(value)
    return _home(env) / "AppData" / "Roaming"


def _windows_local(env: Mapping[str, str] | None) -> Path:
    value = _envmap(env).get("LOCALAPPDATA", "")
    if value:
        return Path(value)
    return _home(env) / "AppData" / "Local"


def is_frozen() -> bool:
    """True inside a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Directory the application's own read-only files live in.

    Frozen: ``sys._MEIPASS`` when present (onedir/onefile bundle payload),
    else the directory holding the executable. From source: the repository
    root (this file is ``<root>/utils/paths.py``).
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def install_root() -> Path:
    """Directory the application is INSTALLED in -- where the executable sits.

    Deliberately NOT the same as :func:`app_root`. For the PyInstaller onedir
    build this project ships, ``sys._MEIPASS`` points at ``<install>/_internal``
    while the executable lives in ``<install>``. Everything the USER is told to
    put "next to the app" is addressed from here -- the ``portable.txt`` marker
    and the ``profiles/`` folder it unlocks -- whereas read-only bundled payload
    (data files, default profiles) is addressed from :func:`app_root`.

    Not ``resolve()``d: it must stay byte-identical to
    ``MainWindow.project_root`` (``Path(sys.executable).parent``), which is what
    builds the ``profiles/`` path the marker unlocks.
    """
    if is_frozen():
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[1]


def user_data_dir(platform: str | None = None, env: Mapping[str, str] | None = None) -> Path:
    """Per-user writable data directory.

    win32 ``%APPDATA%/Aion2 TM`` · darwin ``~/Library/Application Support/Aion2 TM``
    · else ``$XDG_DATA_HOME|~/.local/share/aion2-tm``.
    """
    p = _plat(platform)
    if p == _WIN:
        return _windows_roaming(env) / APP_NAME
    if p == _MAC:
        return _home(env) / "Library" / "Application Support" / APP_NAME
    return _xdg(env, "XDG_DATA_HOME", ".local/share") / APP_SLUG


def user_config_dir(platform: str | None = None, env: Mapping[str, str] | None = None) -> Path:
    """Per-user configuration directory.

    On Windows (and macOS) this is deliberately the *same* directory as
    :func:`user_data_dir` -- ``config.json`` has always lived in
    ``%APPDATA%\\Aion2 TM`` next to the profiles, and moving it would orphan
    every existing install. Only Linux splits config from data, per XDG.
    """
    p = _plat(platform)
    if p in (_WIN, _MAC):
        return user_data_dir(p, env)
    return _xdg(env, "XDG_CONFIG_HOME", ".config") / APP_SLUG


def user_cache_dir(platform: str | None = None, env: Mapping[str, str] | None = None) -> Path:
    """Per-user cache directory (Armory icon/detail caches).

    win32 ``%LOCALAPPDATA%/Aion2 TM/Cache`` · darwin ``~/Library/Caches/Aion2 TM``
    · else ``$XDG_CACHE_HOME|~/.cache/aion2-tm``.
    """
    p = _plat(platform)
    if p == _WIN:
        return _windows_local(env) / APP_NAME / "Cache"
    if p == _MAC:
        return _home(env) / "Library" / "Caches" / APP_NAME
    return _xdg(env, "XDG_CACHE_HOME", ".cache") / APP_SLUG


def user_log_dir(platform: str | None = None, env: Mapping[str, str] | None = None) -> Path:
    """Where ``app.log`` belongs.

    win32 = the data dir, matching ``core.app_logger``'s current behaviour
    (one log next to config.json) · darwin ``~/Library/Logs/Aion2 TM``
    · else ``$XDG_STATE_HOME|~/.local/state/aion2-tm``.
    """
    p = _plat(platform)
    if p == _WIN:
        return user_data_dir(p, env)
    if p == _MAC:
        return _home(env) / "Library" / "Logs" / APP_NAME
    return _xdg(env, "XDG_STATE_HOME", ".local/state") / APP_SLUG


def default_profiles_dir(platform: str | None = None, env: Mapping[str, str] | None = None) -> Path:
    """Fallback profile directory for a fresh install -- the third and last
    branch of ``MainWindow._resolve_profile_dir()``. On Windows this is
    exactly ``%APPDATA%\\Aion2 TM\\Profiles``, as before."""
    return user_data_dir(platform, env) / "Profiles"


def portable_marker(root: Path) -> Path:
    """Path of the sentinel file that opts an installation into portable mode."""
    return Path(root) / PORTABLE_MARKER_NAME


def is_portable(root: Path) -> bool:
    """True when ``root`` carries the portable sentinel file.

    Pass :func:`install_root` (not :func:`app_root`): the marker belongs next
    to the executable, in the same directory as the ``profiles/`` folder it
    unlocks. Looking for it under ``sys._MEIPASS`` would search
    ``<install>/_internal`` and never find a marker the user placed where the
    documentation tells them to.
    """
    try:
        return portable_marker(root).is_file()
    except OSError:
        return False


def ensure_dir(p: Path) -> Path:
    """``mkdir -p`` the directory and return it, for use inline."""
    path = Path(p)
    path.mkdir(parents=True, exist_ok=True)
    return path
