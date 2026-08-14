from core.version import APP_VERSION
from PySide6.QtCore import Signal, Qt, QByteArray, QBuffer
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog


class HeaderWidget(QWidget):
    settings_requested = Signal()
    main_menu_requested = Signal()
    update_btn_clicked = Signal()
    avatar_changed = Signal(str)  # emits base64 PNG string

    def __init__(self):
        super().__init__()
        self._has_avatar = False
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
        self.avatar_label.setCursor(Qt.PointingHandCursor)

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

    def mousePressEvent(self, event):
        child = self.childAt(event.pos())
        if child is self.avatar_label:
            self._pick_avatar()
        super().mousePressEvent(event)

    def _pick_avatar(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Avatar auswählen", "", "Bilder (*.png *.jpg *.jpeg *.webp)"
        )
        if not path:
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = (pixmap.width() - 128) // 2
        y = (pixmap.height() - 128) // 2
        pixmap = pixmap.copy(x, y, 128, 128)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        pixmap.save(buf, "PNG")
        b64 = bytes(ba.toBase64()).decode("ascii")
        self._apply_avatar_pixmap(pixmap)
        self.avatar_changed.emit(b64)

    def _apply_avatar_pixmap(self, pixmap: QPixmap):
        size = 42
        scaled = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        result = QPixmap(size, size)
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        ox = (scaled.width() - size) // 2
        oy = (scaled.height() - size) // 2
        painter.drawPixmap(-ox, -oy, scaled)
        painter.end()
        self.avatar_label.setPixmap(result)
        self.avatar_label.setText("")
        self.avatar_label.setStyleSheet("background: transparent; border-radius: 21px;")
        self._has_avatar = True

    def set_avatar(self, b64: str):
        if not b64:
            return
        ba = QByteArray.fromBase64(b64.encode("ascii"))
        pixmap = QPixmap()
        pixmap.loadFromData(ba)
        if not pixmap.isNull():
            self._apply_avatar_pixmap(pixmap)

    def set_profile(self, name: str):
        self.username_label.setText(name or "Profile")
        if not self._has_avatar:
            self.avatar_label.setText((name or "P")[:1].upper())

    def update_language(self, language, tr_func):
        pass

    def show_update(self, version: str):
        self.update_btn.setText(f"v{version} verfügbar — Changelog")
        self.update_btn.show()
