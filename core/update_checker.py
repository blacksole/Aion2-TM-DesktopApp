import hashlib
import json
import ntpath
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from PySide6.QtCore import QThread, Signal

from core.version import APP_VERSION, GITHUB_USER, GITHUB_REPO

_LATEST_URL = (
    f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
)
_LIST_URL = (
    f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases"
)

# The release workflow publishes "<asset>.sha256" next to every build asset
# (coreutils format: "<hex>  Aion2_TM.zip").
SHA256_SUFFIX = ".sha256"
_HEX_DIGITS = frozenset("0123456789abcdef")
_CHUNK_SIZE = 1024 * 1024


# --------------------------------------------------------------------------
# Download integrity (audit §5: the updater replaced the whole app from an
# unverified ZIP). All Qt-free and side-effect-free so they can be unit
# tested without a QApplication -- ui/update_dialog.py's installer thread
# is the only caller.
# --------------------------------------------------------------------------

def sha256_sidecar_url(asset_url: str) -> str:
    """URL of the checksum file belonging to a release asset.

    GitHub serves every asset of a release from the same
    .../releases/download/<tag>/ prefix, so the sidecar is simply the asset
    URL plus ".sha256" -- which keeps the checker's existing
    `update_available(version, body, asset_url)` signal (and therefore all
    of its consumers) unchanged.
    """
    return f"{asset_url}{SHA256_SUFFIX}" if asset_url else ""


def is_sha256_hex(value: str) -> bool:
    value = (value or "").strip().lower()
    return len(value) == 64 and set(value) <= _HEX_DIGITS


def parse_sha256_sidecar(text: str) -> str:
    """Pull the digest out of a checksum file.

    Accepts the coreutils layouts ("<hex>  name", "<hex> *name") as well as
    a bare "<hex>"; returns the lowercase digest, or "" if the text holds
    none (an unparsable sidecar is treated exactly like a missing one).
    """
    for line in (text or "").replace("\ufeff", "").splitlines():
        parts = line.strip().split()
        if parts and is_sha256_hex(parts[0]):
            return parts[0].strip().lower()
    return ""


def verify_sha256(zip_path, expected_hex: str) -> bool:
    """True when the file at `zip_path` hashes to `expected_hex`.

    Read in chunks -- the release ZIP is tens of megabytes and this runs on
    the updater thread. A malformed or empty expectation is never a pass.
    """
    if not is_sha256_hex(expected_hex):
        return False

    digest = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected_hex.strip().lower()


def _is_unsafe_member(name: str, target: Path) -> bool:
    """Zip-Slip check for one archive member name."""
    if not name:
        return True

    # Zip entries use forward slashes by spec, but a hostile archive can
    # write whatever it likes -- normalize both separators before judging.
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or ntpath.splitdrive(name)[0]:
        return True  # absolute ("/etc/passwd", "C:\\Windows\\...")
    if ".." in PurePosixPath(normalized).parts:
        return True  # traversal ("../evil.txt", "a/../../evil.txt")

    resolved = (target / normalized).resolve()
    return not resolved.is_relative_to(target)


def safe_extract(zip_path, target_dir) -> None:
    """Extract `zip_path` into `target_dir`, refusing to write outside it.

    Every member is validated before a single byte is written, so a
    poisoned archive cannot drop half of itself on disk before being
    caught. Raises ValueError naming the offending entry.
    """
    target = Path(target_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if _is_unsafe_member(info.filename, target):
                raise ValueError(f"Unsafe path in update archive: {info.filename!r}")
        zf.extractall(target)


def decide_checksum_policy(sidecar_url: str | None, fetched: str | None) -> str:
    """What to do with a downloaded update, given what we know about its checksum.

    Three genuinely different situations that the old code collapsed into one
    ("no digest in hand -> install anyway"):

    * ``"skip"``   -- the release published no ``.sha256`` asset at all. Every
      release before the checksum step is like this, so refusing them would
      brick the updater for anyone still on an old version. Install, and say
      so in the log.
    * ``"abort"``  -- the release DOES publish a sidecar, but we could not read
      it (404, timeout, captive portal, proxy, truncated body). We cannot tell
      a network failure from tampering, and we are about to overwrite the
      user's installation: refuse.
    * ``"verify"`` -- we have the published digest; compare it.

    The distinction is only possible because the checker sees the release's
    asset LIST; the installer thread, which only sees a URL, cannot make it.
    """
    if not sidecar_url:
        return "skip"
    if not fetched:
        return "abort"
    return "verify"


def select_assets(assets: list) -> tuple[str, str]:
    """Pick (download_url, sha256_url) out of a release's asset list.

    Same choice as before for the payload -- first .zip/.exe -- plus that
    asset's checksum sidecar when the release publishes one (releases built
    before the sidecar step simply return "" for it).
    """
    asset_url = ""
    asset_name = ""
    for asset in assets or []:
        name = asset.get("name", "")
        if name.endswith(".zip") or name.endswith(".exe"):
            asset_url = asset.get("browser_download_url", "")
            asset_name = name
            break

    sha256_url = ""
    if asset_name:
        wanted = asset_name + SHA256_SUFFIX
        for asset in assets or []:
            if asset.get("name", "") == wanted:
                sha256_url = asset.get("browser_download_url", "")
                break

    return asset_url, sha256_url


class UpdateChecker(QThread):
    update_available = Signal(str, str, str, str)  # (version, body, asset_url, sha256_url)
    up_to_date = Signal()

    def __init__(self, include_prereleases: bool = False, parent=None):
        super().__init__(parent)
        # Separate, on-demand check (not a persisted setting) -- GitHub's
        # own /releases/latest endpoint never returns a prerelease, so a
        # normal check can't see test builds at all. This flag switches to
        # /releases (the full list, newest first) instead, so someone can
        # explicitly go looking for the newest test build when they want to.
        self.include_prereleases = include_prereleases
        # Checksum sidecar of the asset the last run picked, or "" when the
        # release published none. Also emitted with `update_available`: the
        # installer thread cannot re-derive the DIFFERENCE between "no sidecar
        # was published" and "the sidecar could not be fetched" from a URL
        # alone, and that difference decides whether a failed fetch installs
        # or aborts (see decide_checksum_policy).
        self.sha256_url = ""

    def run(self):
        try:
            data = self._fetch_with_prereleases() if self.include_prereleases else self._fetch_latest_stable()
            if data is None:
                self.up_to_date.emit()
                return

            tag = (data.get("tag_name") or "").lstrip("v")
            body = data.get("body") or ""

            asset_url, self.sha256_url = select_assets(data.get("assets", []))

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
                self.update_available.emit(tag, body, asset_url, self.sha256_url)
            elif self._is_newer(tag, APP_VERSION):
                self.update_available.emit(tag, body, asset_url, self.sha256_url)
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
