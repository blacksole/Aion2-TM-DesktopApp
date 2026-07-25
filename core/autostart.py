import sys
import winreg

_REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "Aion2 TM"


def _exe_path() -> str:
    """Returns the path to register — the frozen EXE or empty string in dev mode."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return ""


def set_autostart(enabled: bool) -> bool:
    """Enable or disable Windows autostart for this app. Returns success."""
    path = _exe_path()
    if not path:
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_KEY,
            0, winreg.KEY_SET_VALUE,
        )
        if enabled:
            winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, path)
        else:
            try:
                winreg.DeleteValue(key, _APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


def get_autostart() -> bool:
    """Returns True if the autostart registry entry exists for this app."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_KEY,
            0, winreg.KEY_READ,
        )
        winreg.QueryValueEx(key, _APP_NAME)
        winreg.CloseKey(key)
        return True
    except (OSError, FileNotFoundError):
        return False
