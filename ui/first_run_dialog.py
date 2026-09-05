from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QFileDialog,
)


class FirstRunDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.chosen_path: str | None = None
        self._setup_ui()

    def _setup_ui(self):
        # Always English, not translated via tr() (User-Wunsch, 2026-09-05:
        # "Die Standard Sprache von der App ist englisch - da kann das
        # Fenster gerne auf englisch sein") -- this dialog only ever shows
        # on a fresh install, BEFORE any profile (and therefore any real
        # language preference) has been loaded, so there's no language
        # signal to translate against anyway; English matches the app's
        # own actual default/fallback language for exactly that state.
        self.setWindowTitle("Welcome to Aion2 TM")
        self.setObjectName("UpdateDialog")
        self.setFixedSize(480, 280)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        title = QLabel("Welcome to Aion2 TM!")
        title.setObjectName("updateDialogTitle")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("updateDialogSep")
        layout.addWidget(sep)

        info = QLabel(
            "Profiles are stored locally on your PC.\n"
            "Do you already have profiles from a previous installation?"
        )
        info.setObjectName("updateDialogNotesLabel")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.existing_btn = QPushButton("Yes — specify path")
        self.existing_btn.setObjectName("primaryButton")
        self.existing_btn.setFixedHeight(40)
        self.existing_btn.clicked.connect(self._pick_existing)

        self.fresh_btn = QPushButton("No — start fresh")
        self.fresh_btn.setObjectName("updateDialogLaterBtn")
        self.fresh_btn.setFixedHeight(40)
        self.fresh_btn.clicked.connect(self.accept)

        btn_row.addWidget(self.fresh_btn)
        btn_row.addWidget(self.existing_btn)
        layout.addLayout(btn_row)

    def _pick_existing(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select profile folder", ""
        )
        if path:
            self.chosen_path = path
            self.accept()
        # Kein Pfad gewählt → Dialog bleibt offen
