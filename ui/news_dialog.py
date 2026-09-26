"""News popup (Teil 2, @koordinator 2026-09-26): shows the latest
companion.g-place.de WordPress post at app start.

A plain, non-blocking QDialog: title + excerpt + an "Open" button that
opens the post's own link in the browser, plus "Close". Each post is shown
at most once -- MainWindow persists the highest post id already shown in
config.json (`_last_seen_news_id`) and skips anything at or below it, the
same "remembered across restarts, not per profile" place dps_meter_path
etc. already live in.

Live as of 2026-09-26 (tobia: "Das News update soll auf jedenfall jetzt
schon mit rein - damit ich Nachrichten ueber die Webseite an die App user
schicken kann") -- kept behind NEWS_POPUP_ENABLED anyway, the same on/off
switch other features use (core/version.py's ARMORY_ENABLED / app.py's
_COMPARE_MENU_ENABLED), purely so a future problem with the WordPress side
can be killed with one flag flip instead of a code change.
"""

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextBrowser,
)

from core.translations import tr

# Live (2026-09-26, tobia). Kept as a kill-switch, same pattern as other
# features that shipped behind a flag (ARMORY_ENABLED, _COMPARE_MENU_ENABLED).
NEWS_POPUP_ENABLED = True


class NewsDialog(QDialog):
    """A single popup showing one WordPress post's title + excerpt."""

    def __init__(self, title: str, excerpt: str, link: str, language: str = "en", parent=None):
        super().__init__(parent)
        self.setObjectName("newsDialog")
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self._link = link

        layout = QVBoxLayout(self)

        title_label = QLabel(title)
        title_label.setObjectName("newsDialogTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        if excerpt:
            body = QTextBrowser()
            body.setObjectName("newsDialogBody")
            body.setOpenExternalLinks(False)
            body.setReadOnly(True)
            body.setPlainText(excerpt)
            layout.addWidget(body)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        close_btn = QPushButton(tr(language, "news_dialog_close_btn"))
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(close_btn)

        if link:
            open_btn = QPushButton(tr(language, "news_dialog_open_btn"))
            open_btn.setDefault(True)
            open_btn.clicked.connect(self._open_link)
            buttons.addWidget(open_btn)

        layout.addLayout(buttons)

    def _open_link(self):
        if self._link:
            QDesktopServices.openUrl(QUrl(self._link))
        self.accept()
