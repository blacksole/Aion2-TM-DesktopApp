import webbrowser
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QDialog, QApplication,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from core.version import APP_VERSION

_PAYPAL_URL = "https://www.paypal.com/donate/?hosted_button_id=US4YUPTVHG87C"
_GITHUB_URL = "https://github.com/blacksole87/Aion2-TM-DesktopApp"
_DISCORD_PROFILE_URL = "https://discord.com/users/294899670017114122"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Add more entries here to list additional tools on the About page.
# Each entry: (name, url, description)
_USEFUL_LINKS = [
    ("Guildnest", "https://guildnest.app", "Kostenloses Gilden-Management-Tool, direkt nutzbar im Discord. Für Aion2 besonders interessant: Build-Editor für Charakter-Builds und Item-Datenbank. Dazu Loot-Verwaltung, Event-Planung und Anwesenheits-Tracking für die Gilde."),
]


class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        self.page_title = QLabel()
        self.page_title.setObjectName("aboutH1")
        layout.addWidget(self.page_title)

        # ===== ABOUT ROW =====
        about_row = QFrame()
        about_row.setObjectName("settingsRow")
        about_layout = QHBoxLayout(about_row)
        about_layout.setContentsMargins(24, 20, 24, 20)
        about_layout.setSpacing(20)

        # Icon — grösser und vertikal zentriert
        about_icon = QLabel()
        icon_path = _PROJECT_ROOT / "assets" / "icons" / "AION2_TM_Icon.png"
        icon_pix = QPixmap(str(icon_path))
        if not icon_pix.isNull():
            about_icon.setPixmap(icon_pix.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        about_icon.setFixedSize(84, 84)
        about_icon.setAlignment(Qt.AlignCenter)

        # Text-Spalte
        about_text = QVBoxLayout()
        about_text.setSpacing(2)

        self.about_title_lbl = QLabel()
        self.about_title_lbl.setObjectName("aboutH2")

        self.about_version_lbl = QLabel()
        self.about_version_lbl.setObjectName("settingsDescription")

        # Trennlinie zwischen Version und Beschreibung
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("aboutSeparator")
        sep.setFixedHeight(1)

        self.about_desc_lbl = QLabel()
        self.about_desc_lbl.setObjectName("settingsDescription")
        self.about_desc_lbl.setWordWrap(True)

        self.about_discord_lbl = QLabel()
        self.about_discord_lbl.setObjectName("settingsDescription")

        about_text.addWidget(self.about_title_lbl)
        about_text.addSpacing(4)
        about_text.addWidget(self.about_version_lbl)
        about_text.addSpacing(6)
        about_text.addWidget(sep)
        about_text.addSpacing(6)
        about_text.addWidget(self.about_desc_lbl)
        about_text.addSpacing(4)
        about_text.addWidget(self.about_discord_lbl)

        # Button-Spalte
        about_btn_col = QVBoxLayout()
        about_btn_col.setSpacing(8)

        self.github_btn = QPushButton()
        self.github_btn.setObjectName("secondaryButton")
        self.github_btn.setFixedWidth(140)
        self.github_btn.clicked.connect(lambda: webbrowser.open(_GITHUB_URL))

        self.copy_ver_btn = QPushButton()
        self.copy_ver_btn.setObjectName("secondaryButton")
        self.copy_ver_btn.setFixedWidth(140)
        self.copy_ver_btn.clicked.connect(self._copy_version)

        self.discord_btn = QPushButton("Discord öffnen ↗")
        self.discord_btn.setObjectName("secondaryButton")
        self.discord_btn.setFixedWidth(140)
        self.discord_btn.clicked.connect(lambda: webbrowser.open(_DISCORD_PROFILE_URL))

        about_btn_col.addWidget(self.github_btn)
        about_btn_col.addWidget(self.copy_ver_btn)
        about_btn_col.addWidget(self.discord_btn)
        about_btn_col.addStretch()

        about_layout.addWidget(about_icon, 0, Qt.AlignTop)
        about_layout.addLayout(about_text, 1)
        about_layout.addLayout(about_btn_col)

        # ===== SUPPORT ROW =====
        donate_row = QFrame()
        donate_row.setObjectName("settingsRow")
        donate_layout = QHBoxLayout(donate_row)
        donate_layout.setContentsMargins(24, 16, 24, 16)
        donate_layout.setSpacing(12)

        donate_text = QVBoxLayout()
        donate_text.setSpacing(4)
        self.donate_title_lbl = QLabel()
        self.donate_title_lbl.setObjectName("aboutH2")
        self.donate_desc_lbl = QLabel()
        self.donate_desc_lbl.setObjectName("settingsDescription")
        donate_text.addWidget(self.donate_title_lbl)
        donate_text.addWidget(self.donate_desc_lbl)

        self.donate_btn = QPushButton()
        self.donate_btn.setObjectName("donateButton")
        self.donate_btn.setFixedWidth(110)
        self.donate_btn.clicked.connect(lambda: webbrowser.open(_PAYPAL_URL))

        self.donate_qr_btn = QPushButton("QR")
        self.donate_qr_btn.setObjectName("donateQrButton")
        self.donate_qr_btn.setFixedSize(36, 36)
        self.donate_qr_btn.clicked.connect(self._show_qr_dialog)

        donate_layout.addLayout(donate_text, 1)
        donate_layout.addWidget(self.donate_qr_btn)
        donate_layout.addWidget(self.donate_btn)

        # ===== USEFUL LINKS ROW =====
        links_row = QFrame()
        links_row.setObjectName("settingsRow")
        links_layout = QVBoxLayout(links_row)
        links_layout.setContentsMargins(24, 16, 24, 16)
        links_layout.setSpacing(10)

        links_header = QVBoxLayout()
        links_header.setSpacing(4)
        self.links_title_lbl = QLabel()
        self.links_title_lbl.setObjectName("aboutH2")
        self.links_desc_lbl = QLabel()
        self.links_desc_lbl.setObjectName("settingsDescription")
        links_header.addWidget(self.links_title_lbl)
        links_header.addWidget(self.links_desc_lbl)
        links_layout.addLayout(links_header)

        self._link_open_btns = []
        for name, url, description in _USEFUL_LINKS:
            entry_row = QHBoxLayout()
            entry_row.setSpacing(12)

            entry_text = QVBoxLayout()
            entry_text.setSpacing(2)
            name_lbl = QLabel(name)
            name_lbl.setObjectName("aboutH3")
            desc_lbl = QLabel(description)
            desc_lbl.setObjectName("taskDescription")
            desc_lbl.setWordWrap(True)
            entry_text.addWidget(name_lbl)
            entry_text.addWidget(desc_lbl)

            open_btn = QPushButton()
            open_btn.setObjectName("secondaryButton")
            open_btn.setFixedWidth(140)
            open_btn.clicked.connect(lambda _c=False, u=url: webbrowser.open(u))
            self._link_open_btns.append(open_btn)

            entry_row.addLayout(entry_text, 1)
            entry_row.addWidget(open_btn, 0, Qt.AlignVCenter)
            links_layout.addLayout(entry_row)

        layout.addWidget(about_row)
        layout.addWidget(donate_row)
        layout.addWidget(links_row)
        layout.addStretch()

    def update_language(self, language: str, tr_func):
        _nav_labels = {"de": "Über Aion2 TM", "ru": "Об Aion2 TM"}
        self.page_title.setText(_nav_labels.get(language, "About Aion2 TM"))
        self.about_title_lbl.setText(tr_func(language, "about"))
        self.about_version_lbl.setText(f"v{APP_VERSION}  ·  Python + PySide6  ·  by blacksole")
        self.about_desc_lbl.setText(tr_func(language, "about_desc"))
        self.about_discord_lbl.setText("Discord: .tasse")
        self.github_btn.setText(tr_func(language, "about_github"))
        self.copy_ver_btn.setText(tr_func(language, "about_copy_ver"))
        self.donate_title_lbl.setText(tr_func(language, "donate"))
        self.donate_desc_lbl.setText(tr_func(language, "donate_desc"))
        self.donate_btn.setText(tr_func(language, "donate_btn"))
        self.links_title_lbl.setText(tr_func(language, "useful_links_title"))
        self.links_desc_lbl.setText(tr_func(language, "useful_links_desc"))
        for btn in self._link_open_btns:
            btn.setText(tr_func(language, "useful_links_open"))

    def _copy_version(self):
        QApplication.clipboard().setText(f"Aion2 TM v{APP_VERSION}")

    def _show_qr_dialog(self):
        qr_path = _PROJECT_ROOT / "assets" / "images" / "QR-Code.png"
        dialog = QDialog(self)
        dialog.setWindowTitle("Donate via PayPal")
        dialog.setFixedSize(260, 300)
        dialog.setObjectName("DonateQrDialog")
        v_layout = QVBoxLayout(dialog)
        v_layout.setContentsMargins(20, 20, 20, 20)
        v_layout.setSpacing(12)
        v_layout.setAlignment(Qt.AlignCenter)
        qr_label = QLabel()
        qr_label.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(str(qr_path))
        if not pixmap.isNull():
            qr_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            qr_label.setText("QR Code nicht gefunden.")
            qr_label.setAlignment(Qt.AlignCenter)
        hint = QLabel("Mit PayPal-App scannen")
        hint.setObjectName("donateQrHint")
        hint.setAlignment(Qt.AlignCenter)
        open_btn = QPushButton("Im Browser öffnen")
        open_btn.setObjectName("donateButton")
        open_btn.clicked.connect(lambda: webbrowser.open(_PAYPAL_URL))
        v_layout.addWidget(qr_label)
        v_layout.addWidget(hint)
        v_layout.addWidget(open_btn)
        dialog.exec()
