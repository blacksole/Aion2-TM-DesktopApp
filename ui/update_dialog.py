import os
import sys
import shutil
import urllib.request
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextBrowser, QFrame, QScrollArea, QWidget, QButtonGroup,
    QSizePolicy,
)

from core.app_logger import get_logger
from core.changelog import (
    is_hotfix as _is_hotfix, parse_local_changelog,
    format_release_date as _format_release_date,
)
from core.update_checker import (
    decide_checksum_policy, parse_sha256_sidecar, safe_extract, verify_sha256,
)
from core.version import GITHUB_USER, GITHUB_REPO, APP_VERSION
from core.translations import tr

logger = get_logger("update_dialog")


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
    """Builds the full version history for the dialog below by reading the
    bundled CHANGELOG.md -- the single source of truth, always present and
    always complete, and (since the companion.g-place.de migration,
    2026-09-26) the ONLY source: there is no longer a GitHub Releases API
    call here to overlay a real "published_at" date on top of it. That
    overlay is gone, not degraded -- every version's date already came from
    CHANGELOG.md's own "Release Date:" line whenever GitHub had nothing for
    it (a version tagged/built but never separately published there), so
    dropping GitHub entirely just means every version now takes the path
    that was already the normal fallback.
    """
    fetched = Signal(list)   # list of {"tag", "body", "published_at"} dicts
    failed = Signal()

    def run(self):
        # EVERY version ever written down, oldest included. The split into
        # "the current major line, shown right away" and "older lines,
        # behind Load more" is the DIALOG's job (see
        # ChangelogHistoryDialog._on_fetched) -- filtering by major version
        # HERE (as an earlier revision of this thread did) made
        # _on_fetched's `older` list permanently empty and the
        # User-requested "Load more" button (User-Wunsch, 2026-09-17:
        # "darunter dann einen 'load more' einbauen, der dann den Rest
        # anzeigt") structurally unreachable, along with the whole
        # 1.9.x/0.x history in CHANGELOG.md.
        local_entries = parse_local_changelog()

        entries = [
            {
                "tag": e["tag"],
                "body": e["body"],
                "published_at": e.get("release_date", ""),
            }
            for e in local_entries
        ]

        if entries:
            self.fetched.emit(entries)
        else:
            self.failed.emit()


class ChangelogHistoryDialog(QDialog):
    """"Update-Verlauf" (User-Wunsch, 2026-09-14): shows the last 3 GitHub
    releases' notes at once, same visual language as UpdateDialog above (the
    #UpdateDialog/#updateDialogTitle/#updateDialogNotes/#updateDialogSep/
    #updateDialogLaterBtn styles are all reused as-is -- see
    "UPDATE DIALOG" section) plus one small new left-rail control
    (#changelogVersionBtn) for picking which version to jump to. Clicking a
    version scrolls its section into view; scrolling manually keeps the
    left rail's active version in sync via the scroll area's own
    scrollbar, mirroring the browser mockup the user approved."""

    def __init__(self, parent=None, language: str = "en"):
        super().__init__(parent)
        self._language = language
        self.setWindowTitle(tr(language, "changelog_dialog_title"))
        self.setObjectName("UpdateDialog")
        # Wide enough that the left rail (fixed at 212px below, matching the
        # approved mockup's ~176px rail) never has to fight the markdown
        # content area for space (User-reported, 2026-09-14, screenshot:
        # too narrow overall, clipping the rail's own version/date/badge).
        # Rail bumped from 190->212 (User-reported, 2026-09-17: a horizontal
        # scrollbar appeared under the version buttons) -- once the rail
        # became its own scrollable area (to fit the full version history),
        # its slim 10px vertical scrollbar started eating into the same
        # ~186px a #changelogVersionBtn needs (min-width 160px + padding +
        # border), so 190px was no longer quite enough; +22px covers that
        # with real breathing room. Dialog width grows by the same amount
        # so the notes area on the right keeps its original width.
        # Rail bumped again 212->232 (2026-09-26, v2.0.10's extra digit --
        # see rail_outer.setFixedWidth() below); dialog width grows by the
        # same +20px for the same reason.
        self.setMinimumSize(862, 560)
        self.resize(862, 620)
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
        self._load_more_btn: QPushButton | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel(tr(language, "changelog_dialog_title"))
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
        # rail plus a little breathing room for the HOTFIX badge. The
        # button list itself now lives in its own nested scroll area
        # (User-Wunsch, 2026-09-17: show every version, not just the last
        # 3), since a full local-changelog history can run well past what
        # fits in the fixed dialog height; the "Versionen" title stays put
        # outside that inner scroll so it never scrolls away.
        # Widened 212->232 (2026-09-26): v2.0.10 was the first double-digit
        # patch version released. Measured directly: the top row needs
        # title sizeHint (98px) + spacing (6px) + badge sizeHint (99px) +
        # left/right content margins (24px) = 227px minimum to lay out
        # without compressing either label below its sizeHint -- 212px
        # (barely enough for v2.0.9's narrower "v2.0.9" title) started
        # shrinking both below their real size on any two-digit patch
        # version. +20px (227 rounded up with a few px of breathing room)
        # keeps every patch version up to v2.0.99 exactly as roomy as
        # one-digit ones were.
        rail_outer = QWidget()
        rail_outer.setFixedWidth(232)
        rail_outer_layout = QVBoxLayout(rail_outer)
        rail_outer_layout.setContentsMargins(0, 0, 0, 0)
        rail_outer_layout.setSpacing(8)
        rail_title = QLabel(tr(language, "changelog_versions_label"))
        rail_title.setObjectName("updateDialogNotesLabel")
        rail_outer_layout.addWidget(rail_title)

        rail_scroll = QScrollArea()
        rail_scroll.setWidgetResizable(True)
        rail_scroll.setFrameShape(QFrame.NoFrame)
        rail_container = QWidget()
        rail_label_col = QVBoxLayout(rail_container)
        rail_label_col.setContentsMargins(0, 0, 0, 0)
        rail_label_col.setSpacing(8)
        rail_scroll.setWidget(rail_container)
        rail_outer_layout.addWidget(rail_scroll, 1)

        self._rail_group = QButtonGroup(self)
        self._rail_group.setExclusive(True)
        self._rail_col = rail_label_col
        body_row.addWidget(rail_outer)

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

        self.status_label = QLabel(tr(language, "changelog_loading"))
        self.status_label.setObjectName("updateDialogStatus")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton(tr(language, "close"))
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
        self.status_label.setText(tr(self._language, "changelog_load_failed"))

    def _on_fetched(self, entries: list[dict]):
        self.status_label.hide()
        # Only the current major line shows right away (User-Wunsch,
        # 2026-09-17: "immer bis zur letzten vollen Zahl", e.g. 2.0.0
        # upward while the app sits on 2.0.x) -- older major lines sit
        # behind a "Load more" button appended below the visible list
        # instead of being dropped entirely (User-Wunsch, same message:
        # "darunter dann einen 'load more' einbauen, der dann den Rest
        # anzeigt").
        current_major = APP_VERSION.split(".")[0]
        primary = [e for e in entries if e["tag"].split(".")[0] == current_major]
        older = [e for e in entries if e["tag"].split(".")[0] != current_major]

        for entry in primary:
            self._add_entry(entry)

        if older:
            # No trailing stretch yet -- adding one now and another one
            # after "Load more" reveals the rest would leave a dead
            # expanding gap sitting between the two button groups (a
            # QVBoxLayout stretch item stays wherever it was inserted).
            # The stretch only ever gets added once, in whichever branch
            # turns out to be the final state.
            # A plain QPushButton(text) has no built-in word-wrap, so a
            # longer translation (User-reported, 2026-09-17: a horizontal
            # scrollbar reappeared) forces Qt's own single-line sizeHint
            # calculation, which came out far wider than the rail (up to
            # ~360px for the German text, measured directly -- nowhere
            # close to what the padding/font CSS values alone would
            # suggest). Built the same composite way #changelogVersionBtn
            # already is elsewhere in this dialog: a fixed-width button
            # with an embedded, word-wrapping QLabel, so its width is
            # deterministic regardless of language/text length.
            self._load_more_btn = QPushButton()
            self._load_more_btn.setObjectName("changelogLoadMoreBtn")
            self._load_more_btn.setFixedWidth(188)
            load_more_layout = QVBoxLayout(self._load_more_btn)
            load_more_layout.setContentsMargins(10, 8, 10, 8)
            load_more_label = QLabel(tr(self._language, "changelog_load_more"))
            load_more_label.setObjectName("changelogLoadMoreLabel")
            load_more_label.setWordWrap(True)
            load_more_label.setAlignment(Qt.AlignCenter)
            load_more_label.setAttribute(Qt.WA_TransparentForMouseEvents)
            load_more_layout.addWidget(load_more_label)
            self._load_more_btn.clicked.connect(lambda: self._on_load_more_clicked(older))
            self._rail_col.addWidget(self._load_more_btn)
        else:
            self._rail_col.addStretch(1)

    def _on_load_more_clicked(self, older: list[dict]):
        self._rail_col.removeWidget(self._load_more_btn)
        self._load_more_btn.deleteLater()
        self._load_more_btn = None
        for entry in older:
            self._add_entry(entry)
        self._rail_col.addStretch(1)

    def _add_entry(self, entry: dict):
            tag, body = entry["tag"], entry["body"]
            is_hotfix = _is_hotfix(body)
            date_str = _format_release_date(entry.get("published_at", ""), self._language)
            is_first = not self._sections

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
            btn.setChecked(is_first)
            if is_hotfix:
                btn.setToolTip(tr(self._language, "changelog_hotfix_badge"))
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
            # Fixed vertically, centred in the row (User-reported,
            # 2026-09-24): without a date line underneath, the button's
            # spare height used to be handed to this row, stretching the
            # title and the HOTFIX badge to 38px -- the badge looked like a
            # different, bigger control on 2.0.6 than on 2.0.5.
            version_lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btn_top_row.addWidget(version_lbl, 0, Qt.AlignVCenter)
            # The badge exists in EVERY row, hidden-but-sized where there is
            # no hotfix: the top row is then always exactly as tall as it is
            # with a badge, so every date line sits at the same y in every
            # button (measured before: 6px lower on 2.0.5 than elsewhere).
            small_tag = QLabel(tr(self._language, "changelog_hotfix_badge").upper())
            small_tag.setObjectName("changelogHotfixBadge")
            small_tag.setAttribute(Qt.WA_TransparentForMouseEvents)
            badge_policy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            badge_policy.setRetainSizeWhenHidden(True)
            small_tag.setSizePolicy(badge_policy)
            small_tag.setVisible(is_hotfix)
            btn_top_row.addWidget(small_tag, 0, Qt.AlignVCenter)
            btn_top_row.addStretch(1)
            btn_inner.addLayout(btn_top_row)
            # The date line is ALWAYS there, even empty (tobia, 2026-09-24:
            # "die Groesse wie mit dem Datum ist richtig") -- a version
            # without a date keeps the same two-line layout instead of
            # collapsing into a different, one-line button.
            btn_date_lbl = QLabel(date_str or "\u00a0")
            btn_date_lbl.setObjectName("changelogVersionBtnDate")
            btn_date_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            btn_date_lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btn_inner.addWidget(btn_date_lbl)
            btn_inner.addStretch(1)
            self._rail_group.addButton(btn)
            self._rail_col.addWidget(btn)
            self._equalize_rail_buttons(btn)

            header_row = QHBoxLayout()
            header_row.setSpacing(8)
            header = QLabel(f"{tr(self._language, 'changelog_version_word')} {tag}")
            header.setObjectName("changelogVersionHeader")
            header_row.addWidget(header)
            # "Hotfix" badge (User-Wunsch, 2026-09-14) -- CHANGELOG.md marks
            # a real hotfix release by literally writing "Hotfix" into its
            # entry (see e.g. the 2.0.5 section), which flows straight
            # through into this release's GitHub body untouched -- no
            # separate GitHub API field for this, so a plain case-
            # insensitive substring check is the only signal available.
            if is_hotfix:
                hotfix_badge = QLabel(tr(self._language, "changelog_hotfix_badge"))
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
            doc.setMarkdown(body or tr(self._language, "changelog_no_notes"))
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
            if not is_first:
                divider = QFrame()
                divider.setFrameShape(QFrame.HLine)
                divider.setObjectName("updateDialogSep")
                self._content_layout.addWidget(divider)
            self._content_layout.addWidget(section)

            btn.clicked.connect(lambda _c=False, s=section, b=btn: self._jump_to(s, b))
            self._sections.append((btn, section))

    def _equalize_rail_buttons(self, new_btn: QPushButton):
        """Every version button gets the height of the tallest one.

        A HOTFIX badge makes its row a few px taller than a bare version
        number; with the old fixed 58px that squeezed the date underneath
        (14px instead of 17px, measured).  Sizing all buttons to the tallest
        content keeps the whole rail one height and nothing gets squeezed
        (tobia, 2026-09-24: the layout WITH date is the reference)."""
        buttons = [btn for btn, _section in self._sections] + [new_btn]
        height = 58
        for btn in buttons:
            for child in btn.findChildren(QLabel):
                child.ensurePolished()
            btn.ensurePolished()
            layout = btn.layout()
            if layout is not None:
                layout.invalidate()
                height = max(height, layout.sizeHint().height())
        for btn in buttons:
            btn.setMinimumHeight(height)

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
