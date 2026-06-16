from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QMenu, QSlider,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QBrush

PRIORITY_COLORS = {
    "high":   QColor(239, 68,  68),
    "middle": QColor(245, 158, 11),
    "low":    QColor(59,  130, 246),
}

STATUS_COLORS = {
    "active":    QColor(59,  130, 246),
    "locked":    QColor(71,  85,  105),
    "completed": QColor(34,  197, 94),
    "optional":  QColor(245, 158, 11),
}

TAB_BADGES = {
    "dailyTasks":     ("D",  QColor(59,  130, 246)),
    "weeklyTasks":    ("W",  QColor(139, 92,  246)),
    "dailyShopping":  ("DS", QColor(16,  185, 129)),
    "weeklyShopping": ("WS", QColor(6,   182, 212)),
}

_BG       = QColor(10, 12, 18, 225)
_TITLE_BG = QColor(14, 16, 24, 245)
_ROW_H    = 28
_BORDER_W = 3


class _ColoredRow(QWidget):
    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedHeight(_ROW_H)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), _BG)
        p.fillRect(0, 0, _BORDER_W, self.height(), self._color)
        grad = QLinearGradient(_BORDER_W, 0, int(self.width() * 0.62), 0)
        c0 = QColor(self._color); c0.setAlpha(60)
        c1 = QColor(self._color); c1.setAlpha(0)
        grad.setColorAt(0.0, c0)
        grad.setColorAt(1.0, c1)
        p.fillRect(_BORDER_W, 0, self.width() - _BORDER_W, self.height(), QBrush(grad))
        p.end()


class OverlayTaskRow(_ColoredRow):
    def __init__(self, tab_key: str, card_index: int, title: str, priority: str):
        color = PRIORITY_COLORS.get(priority, PRIORITY_COLORS["low"])
        super().__init__(color)
        self.tab_key = tab_key
        self.card_index = card_index

        layout = QHBoxLayout(self)
        layout.setContentsMargins(_BORDER_W + 6, 0, 8, 0)
        layout.setSpacing(6)

        self.check_btn = QPushButton("○")
        self.check_btn.setObjectName("OverlayCheckBtn")
        self.check_btn.setFixedSize(16, 16)
        self.check_btn.setCursor(Qt.PointingHandCursor)

        title_lbl = QLabel(title if len(title) <= 38 else title[:37] + "…")
        title_lbl.setObjectName("OverlayRowTitle")

        badge_text, badge_color = TAB_BADGES.get(tab_key, ("?", QColor(100, 116, 139)))
        badge = QLabel(badge_text)
        badge.setStyleSheet(
            f"background: rgba({badge_color.red()},{badge_color.green()},{badge_color.blue()},170);"
            "color: #f8fafc; border-radius: 3px; padding: 0px 4px;"
            "font-size: 9px; font-weight: bold;"
        )
        badge.setFixedHeight(14)

        layout.addWidget(self.check_btn)
        layout.addWidget(title_lbl, 1)
        layout.addWidget(badge)


class OverlayGuideRow(_ColoredRow):
    def __init__(self, node_id: str, title: str, status: str):
        color = STATUS_COLORS.get(status, STATUS_COLORS["locked"])
        super().__init__(color)
        self.node_id = node_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(_BORDER_W + 6, 0, 8, 0)
        layout.setSpacing(6)

        dot = QLabel("●")
        dot.setFixedWidth(12)
        dot.setStyleSheet(
            f"color: rgba({color.red()},{color.green()},{color.blue()},220); font-size: 10px;"
        )

        obj = "OverlayRowTitle" if status != "locked" else "OverlayRowTitleDim"
        title_lbl = QLabel(title if len(title) <= 36 else title[:35] + "…")
        title_lbl.setObjectName(obj)

        status_map = {"active": "ACTV", "locked": "LOCK", "completed": "DONE", "optional": "OPT"}
        status_lbl = QLabel(status_map.get(status, status[:4].upper()))
        status_lbl.setStyleSheet(
            f"color: rgba({color.red()},{color.green()},{color.blue()},180);"
            "font-size: 9px; font-weight: bold;"
        )
        status_lbl.setFixedWidth(34)
        status_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(dot)
        layout.addWidget(title_lbl, 1)
        layout.addWidget(status_lbl)


class OverlayWindow(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._mode = "tasks"
        self._drag_pos = None
        self._resize_pos = None
        self._resize_start_h = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(360)
        self.setMinimumHeight(80)
        self.setMaximumHeight(700)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # title bar
        self._title_bar = QWidget()
        self._title_bar.setFixedHeight(38)
        self._title_bar.setCursor(Qt.SizeAllCursor)

        title_row = QHBoxLayout(self._title_bar)
        title_row.setContentsMargins(10, 0, 8, 0)
        title_row.setSpacing(4)

        dot = QLabel("●")
        dot.setStyleSheet("color: #3b82f6; font-size: 10px;")
        dot.setFixedWidth(12)

        self._profile_lbl = QLabel(main_window.profile_name)
        self._profile_lbl.setObjectName("OverlayProfileName")

        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setObjectName("OverlayOpacitySlider")
        self._opacity_slider.setRange(20, 100)
        self._opacity_slider.setValue(90)
        self._opacity_slider.setFixedWidth(72)
        self._opacity_slider.setFixedHeight(16)
        self._opacity_slider.setCursor(Qt.PointingHandCursor)
        self._opacity_slider.setToolTip("Opacity")
        self._opacity_slider.valueChanged.connect(
            lambda v: self.setWindowOpacity(v / 100.0)
        )
        self.setWindowOpacity(0.9)

        gear_btn = QPushButton("⚙")
        gear_btn.setObjectName("OverlayIconBtn")
        gear_btn.setFixedSize(26, 26)
        gear_btn.setCursor(Qt.PointingHandCursor)
        gear_btn.clicked.connect(self._show_settings)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("OverlayIconBtn")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.hide)

        title_row.addWidget(dot)
        title_row.addWidget(self._profile_lbl, 1)
        title_row.addWidget(self._opacity_slider)
        title_row.addWidget(gear_btn)
        title_row.addWidget(close_btn)

        outer.addWidget(self._title_bar)

        # scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setObjectName("OverlayScroll")

        self._content = QWidget()
        self._content.setObjectName("OverlayContent")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(1)
        self._content_layout.addStretch()

        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll)

        # resize handle
        self._resize_handle = QWidget()
        self._resize_handle.setFixedHeight(6)
        self._resize_handle.setCursor(Qt.SizeVerCursor)
        self._resize_handle.setObjectName("OverlayResizeHandle")
        self._resize_handle.mousePressEvent = self._on_handle_press
        self._resize_handle.mouseMoveEvent = self._on_handle_move
        self._resize_handle.mouseReleaseEvent = self._on_handle_release
        outer.addWidget(self._resize_handle)

        self.resize(360, 300)
        self.refresh()

    # painting

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(0, 0, self.width(), 38, _TITLE_BG)
        p.fillRect(0, 38, self.width(), self.height() - 44, _BG)
        # resize handle bar
        handle_y = self.height() - 6
        p.fillRect(0, handle_y, self.width(), 6, QColor(20, 24, 34, 200))
        grip_color = QColor(71, 85, 105, 180)
        grip_w = 30
        grip_x = (self.width() - grip_w) // 2
        p.fillRect(grip_x, handle_y + 2, grip_w, 2, grip_color)
        p.end()

    # public

    def refresh(self):
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._profile_lbl.setText(self.main_window.profile_name)

        if self._mode == "tasks":
            self._populate_tasks()
        else:
            self._populate_guide()

    # populate

    def _populate_tasks(self):
        count = 0
        for tab_key, cards in self.main_window.task_lists.items():
            for i, card in enumerate(cards):
                if card.completed:
                    continue
                priority = getattr(card, "priority_value", None) or getattr(card, "priority", "middle")
                title = card.title_label.text()
                row = OverlayTaskRow(tab_key, i, title, priority)
                row.check_btn.clicked.connect(
                    lambda _, tk=tab_key, idx=i: self._toggle_task(tk, idx)
                )
                self._content_layout.insertWidget(self._content_layout.count() - 1, row)
                count += 1

        if count == 0:
            self._add_empty("No active tasks ✓")

    def _populate_guide(self):
        fw = getattr(self.main_window, "flow_map_window", None)
        if not fw or not getattr(fw, "nodes", None):
            self._add_empty("No flow loaded")
            return
        count = 0
        for node in fw.nodes.values():
            if node.status in ("active", "locked"):
                row = OverlayGuideRow(node.id, node.title, node.status)
                self._content_layout.insertWidget(self._content_layout.count() - 1, row)
                count += 1
        if count == 0:
            self._add_empty("All steps completed ✓")

    def _add_empty(self, text: str):
        lbl = QLabel(text)
        lbl.setObjectName("OverlayEmpty")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFixedHeight(40)
        self._content_layout.insertWidget(0, lbl)

    # actions

    def _toggle_task(self, tab_key: str, index: int):
        cards = self.main_window.task_lists.get(tab_key, [])
        if 0 <= index < len(cards):
            cards[index].toggle()
            self.main_window.refresh()
            self.main_window.save_profile(silent=True)

    def _show_settings(self):
        menu = QMenu(self)
        menu.setObjectName("OverlayMenu")
        a_tasks = menu.addAction("Active Tasks")
        a_guide = menu.addAction("Guide Overview")
        a_tasks.setCheckable(True)
        a_guide.setCheckable(True)
        a_tasks.setChecked(self._mode == "tasks")
        a_guide.setChecked(self._mode == "guide")
        pos = self.sender().mapToGlobal(QPoint(0, self.sender().height()))
        action = menu.exec(pos)
        if action == a_tasks and self._mode != "tasks":
            self._mode = "tasks"
            self.refresh()
        elif action == a_guide and self._mode != "guide":
            self._mode = "guide"
            self.refresh()

    # drag & resize

    def _on_handle_press(self, event):
        if event.button() == Qt.LeftButton:
            self._resize_pos = event.globalPosition().toPoint()
            self._resize_start_h = self.height()

    def _on_handle_move(self, event):
        if self._resize_pos and event.buttons() & Qt.LeftButton:
            delta = event.globalPosition().toPoint().y() - self._resize_pos.y()
            new_h = max(80, self._resize_start_h + delta)
            self.resize(self.width(), new_h)

    def _on_handle_release(self, event):
        self._resize_pos = None
        self._resize_start_h = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() <= 38:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)
