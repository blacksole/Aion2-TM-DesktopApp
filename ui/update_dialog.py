import os
import sys
import shutil
import urllib.request
from datetime import datetime
from pathlib import Path

import json

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextBrowser, QFrame, QScrollArea, QWidget, QButtonGroup,
)

from core.app_logger import get_logger
from core.update_checker import (
    decide_checksum_policy, parse_sha256_sidecar, safe_extract, verify_sha256,
)
from core.version import GITHUB_USER, GITHUB_REPO

logger = get_logger("update_dialog")

_RELEASES_LIST_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases"

# Lightweight month-name lookup (User-Wunsch, 2026-09-14: show each
# version's release date) -- no locale/babel dependency, matching this
# app's existing lightweight-translation style elsewhere (e.g. the plain
# "Mo"/"Di" weekday defaults). Only the 3 languages the app itself supports.
_MONTH_NAMES = {
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
           "August", "September", "Oktober", "November", "Dezember"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
           "августа", "сентября", "октября", "ноября", "декабря"],
    "en": ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"],
}


def _format_release_date(iso_str: str, language: str) -> str:
    """GitHub's "published_at" (e.g. "2026-09-14T18:07:29Z") into a
    human-readable date in the given UI language. Empty/unparsable input
    just returns "" -- an older or malformed release simply shows no date
    rather than a confusing placeholder."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        return ""
    months = _MONTH_NAMES.get(language, _MONTH_NAMES["en"])
    month = months[dt.month - 1]
    if language == "en":
        return f"{month} {dt.day}, {dt.year}"
    return f"{dt.day}. {month} {dt.year}"


class _InstallerThread(QThread):
    status = Signal(str)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, version: str, asset_url: str, app_root: Path, sha256_url: str = "", parent=None):
        super().__init__(parent)
        self.version = version
        self.asset_url = asset_url
        self.app_root = app_root
        # "" means the release published no checksum sidecar (see
        # decide_checksum_policy) -- NOT that we failed to fetch one.
        self.sha256_url = sha256_url
        self.bat_path: Path | None = None

    def run(self):
        try:
            is_frozen = getattr(sys, "frozen", False)

            if is_frozen and not self.asset_url:
                self.failed.emit(
                    "Kein Download-Asset für diese Version gefunden.\n"
                    "Bitte die neue Version manuell von GitHub herunterladen."
                )
                return

            # Persistent temp dir so files survive until bat runs
            tmp_dir = Path(os.environ.get("TEMP", "/tmp")) / "Aion2TM_update"
            shutil.rmtree(tmp_dir, ignore_errors=True)
            tmp_dir.mkdir(parents=True)

            zip_path = tmp_dir / "update.zip"

            download_url = self.asset_url or (
                f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
                f"/archive/refs/tags/v{self.version.lstrip('v')}.zip"
            )

            self.status.emit("Herunterladen...")
            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "Aion2-TM-Updater"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                zip_path.write_bytes(resp.read())

            # Integrity check before anything from this archive touches the
            # installed app (audit §5): the release publishes a
            # "<asset>.sha256" sidecar, so a swapped/truncated/MITM'd
            # download is caught here instead of being robocopy'd over the
            # user's installation. Releases predating the sidecar have none
            # -- those still install, with a warning in app.log.
            self.status.emit("Download prüfen...")
            sidecar_url = self.sha256_url
            expected = self._fetch_expected_sha256(sidecar_url) if sidecar_url else ""
            policy = decide_checksum_policy(sidecar_url, expected)

            if policy == "abort":
                # The release publishes a checksum; we could not read it. A
                # network failure and a tampered mirror look identical from
                # here, and the next step overwrites the user's install.
                zip_path.unlink(missing_ok=True)
                logger.error(
                    "Checksum sidecar %s published but unreadable -- update aborted", sidecar_url
                )
                self.failed.emit(
                    "Die Prüfsumme des Downloads konnte nicht geladen werden.\n"
                    "Das Update wurde aus Sicherheitsgründen abgebrochen und die "
                    "Datei gelöscht.\n"
                    "Bitte später erneut versuchen."
                )
                return

            if policy == "verify":
                if not verify_sha256(zip_path, expected):
                    zip_path.unlink(missing_ok=True)
                    logger.error("SHA-256 mismatch for %s -- download deleted", download_url)
                    self.failed.emit(
                        "Prüfsumme des Downloads stimmt nicht überein.\n"
                        "Das Update wurde abgebrochen und die Datei gelöscht.\n"
                        "Bitte später erneut versuchen."
                    )
                    return
                logger.info("Update archive SHA-256 verified: %s", download_url)
            else:
                logger.warning(
                    "Release published no SHA-256 sidecar for %s -- installing unverified",
                    download_url,
                )

            self.status.emit("Entpacken...")
            extract_dir = tmp_dir / "extracted"
            extract_dir.mkdir()
            # Zip-Slip guard: reject any member resolving outside extract_dir
            # before a single byte is written.
            safe_extract(zip_path, extract_dir)

            if is_frozen:
                # EXE-Modus: prüfen ob ZIP einen Unterordner hat (z.B. "Aion2 TM v0.8.4/")
                entries = list(extract_dir.iterdir())
                if len(entries) == 1 and entries[0].is_dir():
                    source_dir = entries[0]
                else:
                    source_dir = extract_dir

                self.status.emit("Updater vorbereiten...")
                app_dir = Path(sys.executable).parent
                bat_path = tmp_dir / "aion2_updater.bat"
                bat_path.write_text(
                    f"@echo off\n"
                    f"timeout /t 2 /nobreak > nul\n"
                    f"robocopy \"{source_dir}\" \"{app_dir}\" /E /IS /IT /IM /XD __pycache__ /NFL /NDL /NJH /NJS\n"
                    f"start \"\" \"{app_dir}\\Aion2 TM.exe\"\n"
                    f"rd /s /q \"{tmp_dir}\"\n",
                    encoding="utf-8",
                )
                self.bat_path = bat_path
            else:
                # Dev-Modus: Quellcode direkt kopieren
                extracted_root = next(extract_dir.iterdir())
                self.status.emit("Installieren...")
                self._copy_dir(extracted_root, self.app_root)
                for pycache in self.app_root.rglob("__pycache__"):
                    shutil.rmtree(pycache, ignore_errors=True)

            self.finished.emit()
        except Exception as e:
            self.failed.emit(str(e))

    def _fetch_expected_sha256(self, sidecar_url: str) -> str:
        """Digest published at ``sidecar_url``, or "" when it could not be
        fetched or parsed. The CALLER decides what "" means -- see
        decide_checksum_policy."""
        if not sidecar_url:
            return ""
        try:
            req = urllib.request.Request(
                sidecar_url, headers={"User-Agent": "Aion2-TM-Updater"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8", "replace")
        except Exception as e:
            logger.warning("Could not fetch checksum sidecar %s: %s", sidecar_url, e)
            return ""
        return parse_sha256_sidecar(text)

    def _copy_dir(self, src: Path, dest: Path):
        dest.mkdir(exist_ok=True)
        for item in src.iterdir():
            if item.name == "profiles":
                continue
            item_dest = dest / item.name
            if item.is_dir():
                shutil.copytree(
                    item, item_dest,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )
            else:
                shutil.copy(item, item_dest)


class UpdateDialog(QDialog):
    def __init__(self, version: str, body: str, asset_url: str, app_root: Path,
                 sha256_url: str = "", parent=None):
        super().__init__(parent)
        self.version = version
        self.asset_url = asset_url
        self.app_root = app_root
        self.sha256_url = sha256_url
        self._thread = None
        self._setup_ui(body)

    def _setup_ui(self, body: str):
        self.setWindowTitle(f"Update verfügbar — v{self.version}")
        self.setObjectName("UpdateDialog")
        self.setMinimumSize(560, 460)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel(f"Version {self.version} ist verfügbar")
        title.setObjectName("updateDialogTitle")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("updateDialogSep")
        layout.addWidget(sep)

        notes_label = QLabel("Was ist neu:")
        notes_label.setObjectName("updateDialogNotesLabel")
        layout.addWidget(notes_label)

        self.notes = QTextBrowser()
        self.notes.setObjectName("updateDialogNotes")
        self.notes.setMarkdown(body or "_Keine Release Notes vorhanden._")
        self.notes.setOpenExternalLinks(True)
        layout.addWidget(self.notes, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("updateDialogStatus")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.hide()
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.later_btn = QPushButton("Später")
        self.later_btn.setObjectName("updateDialogLaterBtn")
        self.later_btn.setFixedWidth(100)
        self.later_btn.clicked.connect(self.reject)

        self.action_btn = QPushButton("Jetzt aktualisieren")
        self.action_btn.setObjectName("primaryButton")
        self.action_btn.setFixedWidth(180)
        self.action_btn.clicked.connect(self._start_install)

        btn_row.addWidget(self.later_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.action_btn)

        layout.addLayout(btn_row)

    def _start_install(self):
        self.action_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.action_btn.setText("Installiere...")
        self.status_label.show()
        self.status_label.setText("Vorbereitung...")

        self._thread = self._build_installer_thread()
        self._thread.status.connect(self.status_label.setText)
        self._thread.finished.connect(self._on_done)
        self._thread.failed.connect(self._on_failed)
        self._thread.start()

    def _build_installer_thread(self) -> _InstallerThread:
        """The installer thread, fully wired. Split from _start_install so the
        checksum plumbing can be asserted without starting a download."""
        return _InstallerThread(
            self.version, self.asset_url, self.app_root, self.sha256_url, parent=self
        )

    def _on_done(self):
        self.status_label.setText("Fertig! App wird beim Neustart aktualisiert.")
        self.action_btn.setText("App neu starten")
        self.action_btn.setEnabled(True)
        self.later_btn.setText("Später neu starten")
        self.later_btn.setEnabled(True)
        self.action_btn.clicked.disconnect()
        self.action_btn.clicked.connect(self._restart)

    def _on_failed(self, error: str):
        self.status_label.setText(f"Fehler: {error}")
        self.action_btn.setText("Erneut versuchen")
        self.action_btn.setEnabled(True)
        self.later_btn.setEnabled(True)

    def _restart(self):
        import subprocess
        if self._thread and self._thread.bat_path and self._thread.bat_path.exists():
            # EXE-Modus: Batch-Skript übernimmt Neustart
            subprocess.Popen(
                ["cmd.exe", "/c", str(self._thread.bat_path)],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            # Dev-Modus: direkt neu starten
            subprocess.Popen([sys.executable] + sys.argv)
        self.accept()
        QApplication.instance().quit()


class _ChangelogFetcher(QThread):
    """Fetches the last 3 non-draft releases (newest first) for the History
    dialog below -- same GitHub /releases list endpoint UpdateChecker's own
    include_prereleases path already uses, just keeping the first 3 entries
    instead of only the first."""
    fetched = Signal(list)   # list of {"tag", "body"} dicts
    failed = Signal()

    def run(self):
        try:
            req = urllib.request.Request(
                _RELEASES_LIST_URL, headers={"User-Agent": "Aion2-TM-UpdateCheck"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                releases = json.loads(resp.read())
            entries = [
                {
                    "tag": (r.get("tag_name") or "").lstrip("v"),
                    "body": r.get("body") or "",
                    "published_at": r.get("published_at") or "",
                }
                for r in releases if not r.get("draft")
            ][:3]
            if entries:
                self.fetched.emit(entries)
            else:
                self.failed.emit()
        except Exception:
            self.failed.emit()


class ChangelogHistoryDialog(QDialog):
    """"Update-Verlauf" (User-Wunsch, 2026-09-14): shows the last 3 GitHub
    releases' notes at once, same visual language as UpdateDialog above (the
    #UpdateDialog/#updateDialogTitle/#updateDialogNotes/#updateDialogSep/
    #updateDialogLaterBtn styles are all reused as-is -- see styles.qss's
    "UPDATE DIALOG" section) plus one small new left-rail control
    (#changelogVersionBtn) for picking which version to jump to. Clicking a
    version scrolls its section into view; scrolling manually keeps the
    left rail's active version in sync via the scroll area's own
    scrollbar, mirroring the browser mockup the user approved."""

    def __init__(self, parent=None, language: str = "en"):
        super().__init__(parent)
        self._language = language
        self.setWindowTitle("Update-Verlauf")
        self.setObjectName("UpdateDialog")
        # Wide enough that the left rail (fixed at 190px below, matching the
        # approved mockup's ~176px rail) never has to fight the markdown
        # content area for space (User-reported, 2026-09-14, screenshot:
        # too narrow overall, clipping the rail's own version/date/badge).
        self.setMinimumSize(820, 560)
        self.resize(820, 620)
        # Explicit close-button hint + a closeEvent override (User-reported,
        # 2026-09-14: the native titlebar "X" was visible but didn't
        # actually close the dialog) -- belt-and-suspenders since a plain
        # QDialog's close button already maps to reject() by default; this
        # guarantees it regardless of whatever combination of inherited/
        # removed window flags caused that.
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.WindowContextHelpButtonHint) | Qt.WindowCloseButtonHint
        )

        self._sections: list[tuple[QPushButton, QWidget]] = []
        self._suppress_scroll_sync = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("Update-Verlauf")
        title.setObjectName("updateDialogTitle")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("updateDialogSep")
        layout.addWidget(sep)

        body_row = QHBoxLayout()
        body_row.setSpacing(16)
        layout.addLayout(body_row, 1)

        # Fixed-width container, not just a bare layout (User-reported,
        # 2026-09-14, screenshot: version/date/HOTFIX badge clipping inside
        # a too-narrow rail) -- a QVBoxLayout alone has no width of its own
        # to constrain, so the whole rail column is wrapped in a QWidget
        # with a real fixed width, matching the approved mockup's ~176px
        # rail plus a little breathing room for the HOTFIX badge.
        rail_container = QWidget()
        rail_container.setFixedWidth(190)
        rail_label_col = QVBoxLayout(rail_container)
        rail_label_col.setContentsMargins(0, 0, 0, 0)
        rail_label_col.setSpacing(8)
        rail_title = QLabel("Versionen")
        rail_title.setObjectName("updateDialogNotesLabel")
        rail_label_col.addWidget(rail_title)

        self._rail_group = QButtonGroup(self)
        self._rail_group.setExclusive(True)
        self._rail_col = rail_label_col
        body_row.addWidget(rail_container)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("updateDialogNotes")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(4, 4, 4, 4)
        self._content_layout.setSpacing(18)
        self._scroll.setWidget(self._content)
        self._scroll.verticalScrollBar().valueChanged.connect(self._on_scrolled)
        body_row.addWidget(self._scroll, 1)

        self.status_label = QLabel("Lade Update-Verlauf …")
        self.status_label.setObjectName("updateDialogStatus")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("Schließen")
        close_btn.setObjectName("updateDialogLaterBtn")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._fetcher = _ChangelogFetcher(self)
        self._fetcher.fetched.connect(self._on_fetched)
        self._fetcher.failed.connect(self._on_failed)
        self._fetcher.start()

    def closeEvent(self, event):
        self.reject()
        event.accept()

    def _on_failed(self):
        self.status_label.setText("Update-Verlauf konnte nicht geladen werden.")

    def _on_fetched(self, entries: list[dict]):
        self.status_label.hide()
        for i, entry in enumerate(entries):
            tag, body = entry["tag"], entry["body"]
            is_hotfix = "hotfix" in body.lower()
            date_str = _format_release_date(entry.get("published_at", ""), self._language)

            # Composite button content (User-Wunsch, 2026-09-14: version
            # number big/bold like a title, date small/muted underneath,
            # matching the approved browser mockup 1:1) -- a plain
            # QPushButton can't mix two font sizes in its own text, so its
            # own text stays empty and two QLabels are laid out inside it
            # instead. WA_TransparentForMouseEvents on both so clicks land
            # on the button underneath rather than being swallowed by the
            # labels sitting on top of it.
            btn = QPushButton()
            btn.setObjectName("changelogVersionBtn")
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            if is_hotfix:
                btn.setToolTip("Hotfix")
            # A QPushButton with an embedded layout (needed for the two
            # differently-sized labels below) doesn't reliably grow to fit
            # that layout's own size hint the way a real button's text
            # normally would -- explicit minimum height (User-reported,
            # 2026-09-14, screenshot: title/date cramped on top of each
            # other) so there's always real breathing room for both lines
            # plus their margins, matching the mockup's padding.
            btn.setMinimumHeight(58)
            btn_inner = QVBoxLayout(btn)
            btn_inner.setContentsMargins(12, 10, 12, 10)
            btn_inner.setSpacing(3)
            btn_top_row = QHBoxLayout()
            btn_top_row.setSpacing(6)
            version_lbl = QLabel(f"v{tag}")
            version_lbl.setObjectName("changelogVersionBtnTitle")
            version_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            btn_top_row.addWidget(version_lbl)
            if is_hotfix:
                small_tag = QLabel("HOTFIX")
                small_tag.setObjectName("changelogHotfixBadge")
                small_tag.setAttribute(Qt.WA_TransparentForMouseEvents)
                btn_top_row.addWidget(small_tag)
            btn_top_row.addStretch(1)
            btn_inner.addLayout(btn_top_row)
            if date_str:
                btn_date_lbl = QLabel(date_str)
                btn_date_lbl.setObjectName("changelogVersionBtnDate")
                btn_date_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
                btn_inner.addWidget(btn_date_lbl)
            self._rail_group.addButton(btn)
            self._rail_col.addWidget(btn)

            header_row = QHBoxLayout()
            header_row.setSpacing(8)
            header = QLabel(f"Version {tag}")
            header.setObjectName("changelogVersionHeader")
            header_row.addWidget(header)
            # "Hotfix" badge (User-Wunsch, 2026-09-14) -- CHANGELOG.md marks
            # a real hotfix release by literally writing "Hotfix" into its
            # entry (see e.g. the 2.0.5 section), which flows straight
            # through into this release's GitHub body untouched -- no
            # separate GitHub API field for this, so a plain case-
            # insensitive substring check is the only signal available.
            if is_hotfix:
                hotfix_badge = QLabel("Hotfix")
                hotfix_badge.setObjectName("changelogHotfixBadge")
                header_row.addWidget(hotfix_badge)
            header_row.addStretch(1)

            # Plain QLabel, not QTextBrowser (User-reported, 2026-09-14:
            # even with its scrollbar hidden, a QTextBrowser is still a
            # QAbstractScrollArea and silently swallows mouse-wheel input
            # over it instead of letting it bubble up to self._scroll --
            # "kein jeweiliges Scrolldown, auch wenn kein Balken da ist").
            # QLabel has no scrolling capability at all, so the outer
            # self._scroll is the ONLY thing that ever reacts to wheel
            # input, and it sizes itself to its content naturally via
            # word-wrap instead of needing a manual document-height hack.
            # QTextDocument here is used purely as a markdown->HTML
            # converter (QLabel itself has no setMarkdown), matching what
            # QTextBrowser.setMarkdown does internally.
            doc = QTextDocument()
            doc.setMarkdown(body or "_Keine Release Notes vorhanden._")
            notes = QLabel()
            notes.setTextFormat(Qt.RichText)
            notes.setWordWrap(True)
            notes.setOpenExternalLinks(True)
            notes.setText(doc.toHtml())

            section = QWidget()
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(6)
            section_layout.addLayout(header_row)
            if date_str:
                date_lbl = QLabel(date_str)
                date_lbl.setObjectName("updateDialogStatus")
                date_lbl.setAlignment(Qt.AlignLeft)
                section_layout.addWidget(date_lbl)
            section_layout.addWidget(notes)
            if i > 0:
                divider = QFrame()
                divider.setFrameShape(QFrame.HLine)
                divider.setObjectName("updateDialogSep")
                self._content_layout.addWidget(divider)
            self._content_layout.addWidget(section)

            btn.clicked.connect(lambda _c=False, s=section, b=btn: self._jump_to(s, b))
            self._sections.append((btn, section))

        self._rail_col.addStretch(1)

    def _jump_to(self, section: QWidget, btn: QPushButton):
        self._suppress_scroll_sync = True
        self._scroll.verticalScrollBar().setValue(section.y())
        btn.setChecked(True)
        self._suppress_scroll_sync = False

    def _on_scrolled(self, value: int):
        # Highlights whichever section's top edge is closest above the
        # current scroll position, without fighting a click's own jump
        # (see _jump_to's suppress flag) -- mirrors the mockup's
        # IntersectionObserver scroll-spy using plain scrollbar math
        # instead, since QTextBrowser/QScrollArea has no observer API.
        if self._suppress_scroll_sync or not self._sections:
            return
        current = self._sections[0]
        for btn, section in self._sections:
            if section.y() <= value + 12:
                current = (btn, section)
        current[0].setChecked(True)
