import webbrowser
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QDialog, QApplication, QScrollArea,
)
from PySide6.QtGui import QPixmap, QIcon, QPainter
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtSvg import QSvgRenderer
from core.version import APP_VERSION, GITHUB_REPO, GITHUB_USER

_PAYPAL_URL = "https://www.paypal.com/donate/?hosted_button_id=US4YUPTVHG87C"
# Real bug found + fixed (2026-09-04, during a translation audit): this
# hardcoded "blacksole87" doesn't exist -- the real account is "blacksole"
# (core.version.GITHUB_USER, already used correctly by update_checker.py/
# update_dialog.py) -- the button silently 404'd. Built from the same
# shared constants those two already use instead of a second, driftable
# literal.
_GITHUB_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
# "Official Bug Report button" (User-Wunsch, 2026-09-04) -- straight to
# GitHub's own "new issue" composer rather than just the issues list, so
# it's one click from here to actually filing something.
_BUG_REPORT_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/issues/new"
_DISCORD_PROFILE_URL = "https://discord.com/users/294899670017114122"
_TWITCH_URL = "https://twitch.tv/soulflaresifu"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Official Twitch glyph (Simple Icons, CC0), used here purely to link out to
# the real Twitch channel -- matches Twitch's own brand guidelines for
# linking to their platform (User-Wunsch, 2026-08-29: "unter Support
# einfügen, bei den Discords mit einem Button mit Twitchlogo").
_TWITCH_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
<path fill="#9146FF" d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L21.857 12V0zm14.143 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.286z"/>
</svg>"""


def _twitch_icon(size: int = 20) -> QIcon:
    renderer = QSvgRenderer(QByteArray(_TWITCH_LOGO_SVG.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

# Official Discord "Clyde" logomark (Simple Icons, CC0), used here purely to
# link out to real Discord servers -- matches Discord's own brand guidelines
# for linking to their platform. Re-added (2026-08-29, User-Wunsch: "einfach
# 'App Support' mit einem Discord Icon dahinter, und bei Aion2 genauso") --
# both Cooperation-row Discord buttons now carry this icon instead of no
# icon at all, matching the Twitch button next to them.
_DISCORD_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
<path fill="#5865F2" d="M20.317 4.3728a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z"/>
</svg>"""


def _discord_icon(size: int = 20) -> QIcon:
    renderer = QSvgRenderer(QByteArray(_DISCORD_LOGO_SVG.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

# Community Discords that actively cooperate with us -- helping publish and
# promote the app (User, 2026-08-27: "Die Discords sind die Communities, die
# mit mir zusammen arbeiten, Helfen die App zu publishen und Werbung
# machen") -- shown in the "Cooperation" row, same per-entry layout as
# Useful Links below (name/description/Open button) instead of the old
# single collapsed row with a dropdown menu.
# Each entry: (display name, invite URL, description translation key).
# "App Support" (not the community's real name) is deliberate (User-Wunsch,
# 2026-08-29: the button previously misspelled it as "ZasseZer0" -- rather
# than get the exact real name right, just label the button by what it's
# FOR instead).
_DISCORD_SERVERS = [
    ("Aion 2 Discord", "https://discord.gg/aion2global", "coop_aion2_discord_desc"),
    ("App Support", "https://discord.gg/EJAJpDFDeq", "coop_zassezero_desc"),
]

# Add more entries here to list additional tools on the About page.
# Each entry: (name, url, description translation key).
_USEFUL_LINKS = [
    ("Guildnest", "https://guildnest.app", "useful_link_guildnest_desc"),
    (
        "Kanon's Aion 2 Bible",
        "https://docs.google.com/document/d/11u4wLCG1WfL-xSka2Aze0rI9vYRa7mq3N3Gp1bt0AWY/edit?tab=t.0",
        "useful_link_bible_desc",
    ),
]


class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        # AboutPage used to put everything directly on `self` with no
        # scroll wrapper -- added straight to MainWindow's page_stack (see
        # main_window.py), so on any window/screen too short to fit every
        # row (About/Coop/Support/Links/Sources), Qt squeezed each row
        # BELOW its own sizeHint instead of scrolling, most visibly
        # mangling the Support row's two-line text into an overlapping
        # mess (User-reported, 2026-09-03, screenshot). Same scroll-wrapper
        # pattern as settings_page.py.
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("scrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.viewport().setStyleSheet("background: transparent;")
        root_layout.addWidget(scroll_area)

        content = QWidget()
        scroll_area.setWidget(content)

        layout = QVBoxLayout(content)
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

        self.bugreport_btn = QPushButton()
        self.bugreport_btn.setObjectName("secondaryButton")
        self.bugreport_btn.setFixedWidth(140)
        self.bugreport_btn.clicked.connect(lambda: webbrowser.open(_BUG_REPORT_URL))

        about_btn_col.addWidget(self.github_btn)
        about_btn_col.addWidget(self.bugreport_btn)
        about_btn_col.addWidget(self.copy_ver_btn)
        about_btn_col.addWidget(self.discord_btn)
        about_btn_col.addStretch()

        about_layout.addWidget(about_icon, 0, Qt.AlignTop)
        about_layout.addLayout(about_text, 1)
        about_layout.addLayout(about_btn_col)

        # ===== COOPERATION ROW =====
        # Communities that actively cooperate with us on publishing/promoting
        # the app (see _DISCORD_SERVERS) -- one shared title+description on
        # the left (About row's own text+button-column layout, reused here),
        # one named button per community on the right instead of the old
        # single dropdown-menu button, so the button itself already says
        # which community it opens.
        coop_row = QFrame()
        coop_row.setObjectName("settingsRow")
        coop_layout = QHBoxLayout(coop_row)
        coop_layout.setContentsMargins(24, 16, 24, 16)
        coop_layout.setSpacing(12)

        coop_text = QVBoxLayout()
        coop_text.setSpacing(4)
        self.coop_title_lbl = QLabel()
        self.coop_title_lbl.setObjectName("aboutH2")
        self.coop_desc_lbl = QLabel()
        self.coop_desc_lbl.setObjectName("settingsDescription")
        self.coop_desc_lbl.setWordWrap(True)
        coop_text.addWidget(self.coop_title_lbl)
        coop_text.addWidget(self.coop_desc_lbl)

        coop_btn_col = QVBoxLayout()
        coop_btn_col.setSpacing(8)
        for name, url, _desc_key in _DISCORD_SERVERS:
            btn = QPushButton(f" {name}")
            btn.setObjectName("secondaryButton")
            btn.setFixedWidth(180)
            btn.setIcon(_discord_icon())
            btn.clicked.connect(lambda _c=False, u=url: webbrowser.open(u))
            coop_btn_col.addWidget(btn)

        self.twitch_btn = QPushButton(" soulflaresifu")
        self.twitch_btn.setObjectName("secondaryButton")
        self.twitch_btn.setFixedWidth(180)
        self.twitch_btn.setIcon(_twitch_icon())
        self.twitch_btn.clicked.connect(lambda: webbrowser.open(_TWITCH_URL))
        coop_btn_col.addWidget(self.twitch_btn)

        coop_layout.addLayout(coop_text, 1)
        coop_layout.addLayout(coop_btn_col)

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
        self.donate_desc_lbl.setWordWrap(True)
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
        self._link_desc_lbls = []
        for name, url, desc_key in _USEFUL_LINKS:
            entry_row = QHBoxLayout()
            entry_row.setSpacing(12)

            entry_text = QVBoxLayout()
            entry_text.setSpacing(2)
            name_lbl = QLabel(name)
            name_lbl.setObjectName("aboutH3")
            desc_lbl = QLabel()
            desc_lbl.setObjectName("taskDescription")
            desc_lbl.setWordWrap(True)
            self._link_desc_lbls.append((desc_lbl, desc_key))
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

        # ===== SOURCES ROW =====
        # Plain reference listing, no buttons (User-Wunsch, 2026-08-29:
        # "Hier brauchen wir keinen Button. Wir machen eine Auflistung in
        # 2-3 Zeilen mit Komma-Auflistung, welche Seiten oder Quellen wir
        # als Referenz genommen haben") -- every real external data/
        # research source the app's own item/skill/recipe/board/formula
        # data was scraped or researched from, credited here once instead
        # of scattered only in code comments.
        sources_row = QFrame()
        sources_row.setObjectName("settingsRow")
        sources_layout = QVBoxLayout(sources_row)
        sources_layout.setContentsMargins(24, 16, 24, 16)
        sources_layout.setSpacing(4)
        self.sources_title_lbl = QLabel()
        self.sources_title_lbl.setObjectName("aboutH2")
        self.sources_desc_lbl = QLabel()
        self.sources_desc_lbl.setObjectName("settingsDescription")
        self.sources_desc_lbl.setWordWrap(True)
        sources_layout.addWidget(self.sources_title_lbl)
        sources_layout.addWidget(self.sources_desc_lbl)

        layout.addWidget(about_row)
        layout.addWidget(coop_row)
        layout.addWidget(donate_row)
        layout.addWidget(links_row)
        layout.addWidget(sources_row)
        layout.addStretch()

    def update_language(self, language: str, tr_func):
        _nav_labels = {"de": "Über Aion2 TM", "ru": "Об Aion2 TM"}
        self.page_title.setText(_nav_labels.get(language, "About Aion2 TM"))
        self.about_title_lbl.setText(tr_func(language, "about"))
        self.about_version_lbl.setText(f"v{APP_VERSION}  ·  Python + PySide6  ·  by blacksole")
        self.about_desc_lbl.setText(tr_func(language, "about_desc"))
        self.about_discord_lbl.setText("Discord: .tasse")
        self.github_btn.setText(tr_func(language, "about_github"))
        self.bugreport_btn.setText(tr_func(language, "bug_report_btn"))
        self.copy_ver_btn.setText(tr_func(language, "about_copy_ver"))
        self.coop_title_lbl.setText(tr_func(language, "coop_title"))
        self.coop_desc_lbl.setText(tr_func(language, "coop_desc"))
        self.twitch_btn.setToolTip(tr_func(language, "coop_twitch_desc"))
        self.donate_title_lbl.setText(tr_func(language, "donate"))
        self.donate_desc_lbl.setText(tr_func(language, "donate_desc"))
        self.donate_btn.setText(tr_func(language, "donate_btn"))
        self.links_title_lbl.setText(tr_func(language, "useful_links_title"))
        self.links_desc_lbl.setText(tr_func(language, "useful_links_desc"))
        for btn in self._link_open_btns:
            btn.setText(tr_func(language, "useful_links_open"))
        for desc_lbl, desc_key in self._link_desc_lbls:
            desc_lbl.setText(tr_func(language, desc_key))
        self.sources_title_lbl.setText(tr_func(language, "sources_title"))
        self.sources_desc_lbl.setText(tr_func(language, "sources_desc"))

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
