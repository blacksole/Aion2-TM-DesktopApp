"""News popup (Teil 2, @koordinator 2026-09-26): shows the latest
companion.g-place.de WordPress post at app start.

Same visual language as the changelog/update dialogs (#updateDialogTitle,
#updateDialogSep, #updateDialogStatus, #updateDialogNotes, #primaryButton,
#updateDialogLaterBtn) instead of a bare unstyled QDialog -- tobia,
2026-09-27: "gefaellt mir noch nicht so gut... richtung changelog oder
noch besser" -- so this reuses exactly the changelog dialog's existing
QSS objectNames rather than inventing a third look for the same app.

Each post is shown at most once -- MainWindow persists the highest post
id already shown in config.json (`_last_seen_news_id`) and skips anything
at or below it, the same "remembered across restarts, not per profile"
place dps_meter_path etc. already live in.

Live as of 2026-09-26 (tobia: "Das News update soll auf jedenfall jetzt
schon mit rein - damit ich Nachrichten ueber die Webseite an die App user
schicken kann") -- kept behind NEWS_POPUP_ENABLED anyway, the same on/off
switch other features use (core/version.py's ARMORY_ENABLED / app.py's
_COMPARE_MENU_ENABLED), purely so a future problem with the WordPress side
can be killed with one flag flip instead of a code change.
"""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QTextDocument
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)

from core.changelog import format_release_date
from core.translations import tr

# Live (2026-09-26, tobia). Kept as a kill-switch, same pattern as other
# features that shipped behind a flag (ARMORY_ENABLED, _COMPARE_MENU_ENABLED).
NEWS_POPUP_ENABLED = True


class NewsDialog(QDialog):
    """A single popup showing one WordPress post's title + excerpt, styled
    like the changelog dialog (title/date/badge header, boxed notes,
    accent "Open" button) instead of a plain default QDialog."""

    def __init__(self, title: str, excerpt: str, link: str, date: str = "",
                 language: str = "en", parent=None):
        super().__init__(parent)
        self.setObjectName("newsDialog")
        self.setWindowTitle(tr(language, "news_dialog_window_title"))
        self.setMinimumSize(480, 320)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._link = link

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("updateDialogTitle")
        title_label.setWordWrap(True)
        header_row.addWidget(title_label, 1)

        badge = QLabel(tr(language, "news_dialog_badge"))
        badge.setObjectName("changelogHotfixBadge")
        header_row.addWidget(badge, 0, Qt.AlignTop)
        layout.addLayout(header_row)

        date_str = format_release_date(date, language) if date else ""
        if date_str:
            date_label = QLabel(date_str)
            date_label.setObjectName("updateDialogStatus")
            layout.addWidget(date_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("updateDialogSep")
        layout.addWidget(sep)

        if excerpt:
            body = QLabel()
            body.setObjectName("updateDialogNotes")
            body.setWordWrap(True)
            body.setTextFormat(Qt.RichText)
            doc = QTextDocument()
            doc.setPlainText(excerpt)
            body.setText(doc.toHtml())
            layout.addWidget(body, 1)
        else:
            layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)

        close_btn = QPushButton(tr(language, "news_dialog_close_btn"))
        close_btn.setObjectName("updateDialogLaterBtn")
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(close_btn)
        buttons.addStretch(1)

        if link:
            open_btn = QPushButton(tr(language, "news_dialog_open_btn"))
            open_btn.setObjectName("primaryButton")
            open_btn.setFixedWidth(160)
            open_btn.setDefault(True)
            open_btn.clicked.connect(self._open_link)
            buttons.addWidget(open_btn)

        layout.addLayout(buttons)

    def _open_link(self):
        if self._link:
            QDesktopServices.openUrl(QUrl(self._link))
        self.accept()
