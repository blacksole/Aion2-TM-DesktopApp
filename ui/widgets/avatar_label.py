import requests

from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtCore import Qt


class AvatarLabel(QLabel):
    def __init__(self, size: int = 54):
        super().__init__()

        self.avatar_size = size
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        # Styled by #profileAvatar in ui/styles.template.qss (accent fill,
        # fg.on-accent text, radius.full) -- the same rule HeaderWidget's own
        # avatar uses, instead of the Discord-blurple literal + hardcoded
        # 18 px this carried (MASTER §4-4: no hex in ui/).
        self.setObjectName("profileAvatar")

    def set_initials(self, username: str):
        initials = username[:2].upper() if username else "?"
        self.setText(initials)
        self.setPixmap(QPixmap())

    def load_from_url(self, url: str):
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()

            pixmap = QPixmap()
            pixmap.loadFromData(response.content)

            rounded = self._make_round_pixmap(pixmap)
            self.setPixmap(rounded)
            self.setText("")

        except Exception:
            self.set_initials("?")

    def _make_round_pixmap(self, pixmap: QPixmap) -> QPixmap:
        pixmap = pixmap.scaled(
            self.avatar_size,
            self.avatar_size,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
        )

        rounded = QPixmap(self.avatar_size, self.avatar_size)
        rounded.fill(Qt.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addEllipse(0, 0, self.avatar_size, self.avatar_size)
        painter.setClipPath(path)

        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        return rounded