import json
import urllib.request

from PySide6.QtCore import QThread, Signal

from core.version import APP_VERSION, GITHUB_USER, GITHUB_REPO

_LATEST_URL = (
    f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
)
_LIST_URL = (
    f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases"
)


class UpdateChecker(QThread):
    update_available = Signal(str, str, str)  # (version, body, asset_url)
    up_to_date = Signal()

    def __init__(self, include_prereleases: bool = False, parent=None):
        super().__init__(parent)
        # Separate, on-demand check (not a persisted setting) -- GitHub's
        # own /releases/latest endpoint never returns a prerelease, so a
        # normal check can't see test builds at all. This flag switches to
        # /releases (the full list, newest first) instead, so someone can
        # explicitly go looking for the newest test build when they want to.
        self.include_prereleases = include_prereleases

    def run(self):
        try:
            data = self._fetch_with_prereleases() if self.include_prereleases else self._fetch_latest_stable()
            if data is None:
                self.up_to_date.emit()
                return

            tag = (data.get("tag_name") or "").lstrip("v")
            body = data.get("body") or ""

            asset_url = ""
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if name.endswith(".zip") or name.endswith(".exe"):
                    asset_url = asset.get("browser_download_url", "")
                    break

            # Kein kompiliertes Asset → kein Update anbieten (Source-Archiv reicht nicht)
            if not tag or not asset_url:
                self.up_to_date.emit()
                return

            if self.include_prereleases:
                # Manuelle Test-Build-Suche: zeigt immer den neuesten
                # veröffentlichten Release (egal ob stable oder pre-release)
                # -- ein Beta-Tag wie "1.3.1-beta1" lässt sich mit der
                # einfachen numerischen _is_newer()-Prüfung unten ohnehin
                # nicht zuverlässig vergleichen, und wer aktiv nach einer
                # Testversion sucht, will sie sehen, nicht stillschweigend
                # per Versionsvergleich übersprungen bekommen.
                self.update_available.emit(tag, body, asset_url)
            elif self._is_newer(tag, APP_VERSION):
                self.update_available.emit(tag, body, asset_url)
            else:
                self.up_to_date.emit()
        except Exception:
            self.up_to_date.emit()

    def _fetch_latest_stable(self) -> dict | None:
        req = urllib.request.Request(_LATEST_URL, headers={"User-Agent": "Aion2-TM-UpdateCheck"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())

    def _fetch_with_prereleases(self) -> dict | None:
        req = urllib.request.Request(_LIST_URL, headers={"User-Agent": "Aion2-TM-UpdateCheck"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            releases = json.loads(resp.read())
        for release in releases:
            if release.get("draft"):
                continue
            return release  # GitHub lists newest first
        return None

    @staticmethod
    def _is_newer(remote: str, local: str) -> bool:
        try:
            return tuple(int(x) for x in remote.split(".")) > tuple(
                int(x) for x in local.split(".")
            )
        except ValueError:
            return False
