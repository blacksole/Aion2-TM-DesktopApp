import json
import urllib.request

from PySide6.QtCore import QThread, Signal

from core.version import APP_VERSION, GITHUB_USER, GITHUB_REPO

_API_URL = (
    f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
)


class UpdateChecker(QThread):
    update_available = Signal(str, str)  # (version, body)
    up_to_date = Signal()

    def run(self):
        try:
            req = urllib.request.Request(
                _API_URL,
                headers={"User-Agent": "Aion2-TM-UpdateCheck"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())

            tag = (data.get("tag_name") or "").lstrip("v")
            body = data.get("body") or ""

            if tag and self._is_newer(tag, APP_VERSION):
                self.update_available.emit(tag, body)
            else:
                self.up_to_date.emit()
        except Exception:
            self.up_to_date.emit()

    @staticmethod
    def _is_newer(remote: str, local: str) -> bool:
        try:
            return tuple(int(x) for x in remote.split(".")) > tuple(
                int(x) for x in local.split(".")
            )
        except ValueError:
            return False
