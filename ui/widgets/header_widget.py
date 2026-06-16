from core.version import APP_VERSION
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton


class HeaderWidget(QWidget):
    settings_requested = Signal()
    main_menu_requested = Signal()
    update_btn_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("profileCard")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.avatar_label = QLabel("P")
        self.avatar_label.setObjectName("profileAvatar")
        self.avatar_label.setFixedSize(42, 42)
        self.avatar_label.setAlignment(Qt.AlignCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self.username_label = QLabel("Profile")
        self.username_label.setObjectName("profileUsername")

        self.version_label = QLabel(f"v{APP_VERSION}")
        self.version_label.setObjectName("profileVersion")

        text_col.addWidget(self.username_label)
        text_col.addWidget(self.version_label)

        top_row.addWidget(self.avatar_label)
        top_row.addLayout(text_col, 1)

        self.update_btn = QPushButton()
        self.update_btn.setObjectName("updateAvailableButton")
        self.update_btn.hide()
        self.update_btn.clicked.connect(self.update_btn_clicked.emit)

        root.addLayout(top_row)
        root.addWidget(self.update_btn)

    def update_language(self, language, tr_func):
        pass

    def set_profile(self, name: str):
        self.username_label.setText(name or "Profile")
        self.avatar_label.setText((name or "P")[:1].upper())

    def show_update(self, version: str):
        self.update_btn.setText(f"v{version} verfügbar — Changelog")
        self.update_btn.show()
