import hashlib
import ntpath
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from PySide6.QtCore import QThread, Signal

from core.changelog import release_notes_for
from core.version import APP_VERSION

# companion.g-place.de replaces the GitHub Releases API as of 2026-10 (tobia,
# @koordinator 2026-09-26): the repo goes PRIVATE on 2026-10-02 to stop
# cloning, which would turn api.github.com/repos/.../releases/latest into a
# silent 404 for every already-installed copy of the app. This host serves
# just the two things an update check needs -- a bare version string and the
# build ZIP -- no release-notes/changelog endpoint and (so far) no checksum
# sidecar, unlike the old GitHub asset list. Release notes come from the
# CHANGELOG.md already bundled with the app (local_release_notes() below);
# sha256_url is always "" for now, which decide_checksum_policy() already
# treats as "release published no sidecar -- install unverified", the exact
# same path every pre-checksum GitHub release already went through.
_VERSION_URL = "https://companion.g-place.de/download/Aion2_TM-latest.version"
_ZIP_URL = "https://companion.g-place.de/download/Aion2_TM-latest.zip"

# The release workflow publishes "<asset>.sha256" next to every build asset
# (coreutils format: "<hex>  Aion2_TM.zip") -- kept for when/if
# companion.g-place.de grows a matching "<zip>.sha256" sidecar; unused by
# UpdateChecker.run() today (see _VERSION_URL/_ZIP_URL comment above).
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


class UpdateChecker(QThread):
    update_available = Signal(str, str, str, str)  # (version, body, asset_url, sha256_url)
    up_to_date = Signal()

    def __init__(self, include_prereleases: bool = False, parent=None):
        super().__init__(parent)
        # No longer meaningful (companion.g-place.de serves exactly one
        # "latest" version, no separate pre-release channel like GitHub's
        # full /releases list did) -- kept as a constructor arg purely so
        # existing callers (ui/main_window.py's UpdateChecker() calls, any
        # future "check for a test build" menu action) don't need updating
        # too; it is simply ignored.
        self.include_prereleases = include_prereleases
        # Always "" -- companion.g-place.de publishes no checksum sidecar
        # (see the module docstring above). decide_checksum_policy() already
        # treats an empty sidecar_url as "release published none -- install
        # unverified", the same path every pre-checksum GitHub release went
        # through, so nothing downstream needed to change for this.
        self.sha256_url = ""

    def run(self):
        try:
            remote_version = self._fetch_latest_version()
            if not remote_version:
                self.up_to_date.emit()
                return

            if self._is_newer(remote_version, APP_VERSION):
                body = release_notes_for(remote_version)
                self.update_available.emit(remote_version, body, _ZIP_URL, self.sha256_url)
            else:
                self.up_to_date.emit()
        except Exception:
            self.up_to_date.emit()

    def _fetch_latest_version(self) -> str:
        """The bare version string companion.g-place.de serves, e.g.
        "2.0.9" -- stripped of whitespace/a stray leading "v" in case the
        file ever gets hand-edited to match the CHANGELOG.md/tag style."""
        req = urllib.request.Request(_VERSION_URL, headers={"User-Agent": "Aion2-TM-UpdateCheck"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read().decode("utf-8", "replace").strip().lstrip("v")

    @staticmethod
    def _is_newer(remote: str, local: str) -> bool:
        try:
            return tuple(int(x) for x in remote.split(".")) > tuple(
                int(x) for x in local.split(".")
            )
        except ValueError:
            return False
