import os
import sys
import shutil
import zipfile
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextBrowser, QFrame,
)

from core.version import GITHUB_USER, GITHUB_REPO


class _InstallerThread(QThread):
    status = Signal(str)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, version: str, asset_url: str, app_root: Path, parent=None):
        super().__init__(parent)
        self.version = version
        self.asset_url = asset_url
        self.app_root = app_root
        self.bat_path: Path | None = None

    def run(self):
        try:
            is_frozen = getattr(sys, "frozen", False)

            # Persistent temp dir so files survive until bat runs
            tmp_dir = Path(os.environ.get("TEMP", "/tmp")) / "Aion2TM_update"
            shutil.rmtree(tmp_dir, ignore_errors=True)
            tmp_dir.mkdir(parents=True)

            zip_path = tmp_dir / "update.zip"

            # Prefer release asset; fall back to source archive for dev mode
            download_url = self.asset_url
            if not download_url:
                tag = f"v{self.version}" if not self.version.startswith("v") else self.version
                download_url = (
                    f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
                    f"/archive/refs/tags/{tag}.zip"
                )

            self.status.emit("Herunterladen...")
            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "Aion2-TM-Updater"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                zip_path.write_bytes(resp.read())

            self.status.emit("Entpacken...")
            extract_dir = tmp_dir / "extracted"
            extract_dir.mkdir()
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(extract_dir)

            if is_frozen and self.asset_url:
                # EXE-Modus: Batch-Skript schreibt Dateien nach dem Beenden
                self.status.emit("Updater vorbereiten...")
                app_dir = Path(sys.executable).parent
                exe_name = Path(sys.executable).name
                bat_path = tmp_dir / "aion2_updater.bat"
                bat_path.write_text(
                    f"@echo off\n"
                    f"timeout /t 2 /nobreak > nul\n"
                    f"robocopy \"{extract_dir}\" \"{app_dir}\" /E /IS /IT /IM /XD __pycache__ /NFL /NDL /NJH /NJS\n"
                    f"start \"\" \"{app_dir}\\{exe_name}\"\n"
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
    def __init__(self, version: str, body: str, asset_url: str, app_root: Path, parent=None):
        super().__init__(parent)
        self.version = version
        self.asset_url = asset_url
        self.app_root = app_root
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

        self._thread = _InstallerThread(self.version, self.asset_url, self.app_root, parent=self)
        self._thread.status.connect(self.status_label.setText)
        self._thread.finished.connect(self._on_done)
        self._thread.failed.connect(self._on_failed)
        self._thread.start()

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
