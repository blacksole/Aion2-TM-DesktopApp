from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton


class HeaderWidget(QWidget):
    settings_requested = Signal()
    main_menu_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("discordCard")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.avatar_label = QLabel("D")
        self.avatar_label.setObjectName("discordAvatar")
        self.avatar_label.setFixedSize(42, 42)
        self.avatar_label.setAlignment(Qt.AlignCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self.username_label = QLabel("Username")
        self.username_label.setObjectName("discordUsername")

        self.server_label = QLabel("Server / Status")
        self.server_label.setObjectName("discordServer")

        text_col.addWidget(self.username_label)
        text_col.addWidget(self.server_label)

        top_row.addWidget(self.avatar_label)
        top_row.addLayout(text_col, 1)

        root.addLayout(top_row)

    def update_language(self, language, tr_func):
        pass

    def set_discord_user(self, username: str, server: str = ""):
        self.username_label.setText(username or "Username")
        self.server_label.setText(server or "Discord")
        self.avatar_label.setText((username or "D")[:1].upper())