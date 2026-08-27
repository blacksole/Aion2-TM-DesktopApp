from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSlider,
)
from PySide6.QtCore import Qt
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
    "tasks":    ("T",  QColor(59,  130, 246)),
    "shopping": ("S",  QColor(6,   182, 212)),
}

SCHEDULE_BADGES = {
    "daily":  ("D", QColor(59,  130, 246)),
    "weekly": ("W", QColor(139, 92,  246)),
    "season": ("S", QColor(245, 158, 11)),
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
    def __init__(self, tab_key: str, card_index: int, title: str, priority: str,
                 badge: tuple | None = None):
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

        title_lbl = QLabel(title if len(title) <= 44 else title[:43] + "…")
        title_lbl.setObjectName("OverlayRowTitle")

        badge_text, badge_color = badge if badge else TAB_BADGES.get(tab_key, ("?", QColor(100, 116, 139)))
        badge_lbl = QLabel(badge_text)
        badge_lbl.setStyleSheet(
            f"background: rgba({badge_color.red()},{badge_color.green()},{badge_color.blue()},170);"
            "color: #f8fafc; border-radius: 3px; padding: 0px 4px;"
            "font-size: 9px; font-weight: bold;"
        )
        badge_lbl.setFixedHeight(14)

        layout.addWidget(self.check_btn)
        layout.addWidget(title_lbl, 1)
        layout.addWidget(badge_lbl)


class OverlayGuideRow(_ColoredRow):
    def __init__(self, node_id: str, title: str, status: str):
        color = STATUS_COLORS.get(status, STATUS_COLORS["locked"])
        super().__init__(color)
        self.node_id = node_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(_BORDER_W + 6, 0, 8, 0)
        layout.setSpacing(6)

        can_toggle = status in ("active", "completed")

        self.check_btn = QPushButton("✓" if status == "completed" else "○")
        self.check_btn.setObjectName("OverlayCheckBtn")
        self.check_btn.setFixedSize(16, 16)
        self.check_btn.setEnabled(can_toggle)
        self.check_btn.setCursor(Qt.PointingHandCursor if can_toggle else Qt.ArrowCursor)

        obj = "OverlayRowTitle" if status != "locked" else "OverlayRowTitleDim"
        title_lbl = QLabel(title if len(title) <= 34 else title[:33] + "…")
        title_lbl.setObjectName(obj)

        status_map = {"active": "ACTV", "locked": "LOCK", "completed": "DONE", "optional": "OPT"}
        status_lbl = QLabel(status_map.get(status, status[:4].upper()))
        status_lbl.setStyleSheet(
            f"color: rgba({color.red()},{color.green()},{color.blue()},180);"
            "font-size: 9px; font-weight: bold;"
        )
        status_lbl.setFixedWidth(34)
        status_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(self.check_btn)
        layout.addWidget(title_lbl, 1)
        layout.addWidget(status_lbl)


class _AccordionSection(QWidget):
    """A collapsible section: clickable header (chevron/title/count) + body.

    Sections are only ever added to the overlay when they actually have rows
    -- there is no "empty section" state, unlike the rows inside a section
    (Tasks/Guide keep their own "all done" placeholder row).
    """

    def __init__(self, title: str, count: int, open_by_default: bool, parent=None):
        super().__init__(parent)
        self._open = open_by_default

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._header = QWidget()
        self._header.setObjectName("OverlaySectionHead")
        self._header.setCursor(Qt.PointingHandCursor)
        # A plain QWidget doesn't paint its stylesheet background/border by
        # default (unlike QLabel/QPushButton) -- without this, #OverlaySectionHead's
        # background tint and border lines silently don't render at all.
        self._header.setAttribute(Qt.WA_StyledBackground, True)
        header_row = QHBoxLayout(self._header)
        header_row.setContentsMargins(10, 6, 10, 6)
        header_row.setSpacing(8)

        self._chevron = QLabel()
        self._chevron.setObjectName("OverlayChevron")
        self._chevron.setFixedWidth(10)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("OverlaySectionTitle")

        self._count_lbl = QLabel(str(count))
        self._count_lbl.setObjectName("OverlaySectionCount")

        header_row.addWidget(self._chevron)
        header_row.addWidget(title_lbl, 1)
        header_row.addWidget(self._count_lbl)

        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(1)

        outer.addWidget(self._header)
        outer.addWidget(self._body)

        self._header.mousePressEvent = lambda _event: self._toggle()
        self._apply_open_state()

    def add_row(self, widget: QWidget):
        self._body_layout.addWidget(widget)

    def _toggle(self):
        self._open = not self._open
        self._apply_open_state()

    def _apply_open_state(self):
        self._chevron.setText("▾" if self._open else "▸")
        self._body.setVisible(self._open)


class OverlayWindow(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
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

        close_btn = QPushButton("✕")
        close_btn.setObjectName("OverlayIconBtn")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.hide)

        title_row.addWidget(dot)
        title_row.addWidget(self._profile_lbl, 1)
        title_row.addWidget(self._opacity_slider)
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

        sections = [self._build_tasks_section(), self._build_guide_section()]

        # Skills/Equipment become sections here once their priority lists are
        # actually persisted somewhere the overlay can read -- right now
        # both live only in the Build Planner's in-memory session state, so
        # there is nothing to show yet. Sections only ever appear when they
        # have real content (see _AccordionSection docstring).
        skill_data = self._skill_priority_data()
        if skill_data:
            sections.append(self._build_skill_section(skill_data))
        equip_data = self._equip_priority_data()
        if equip_data:
            sections.append(self._build_equip_section(equip_data))

        for section in sections:
            self._content_layout.insertWidget(self._content_layout.count() - 1, section)

    def _skill_priority_data(self):
        return None

    def _equip_priority_data(self):
        return None

    # populate

    def _build_tasks_section(self) -> _AccordionSection:
        rows = []
        for tab_key, cards in self.main_window.task_lists.items():
            for i, card in enumerate(cards):
                if card.completed:
                    continue
                priority = getattr(card, "priority_value", None) or getattr(card, "priority", "middle")
                title = card.title_label.text()
                amount = getattr(card, "amount", None)
                if amount and str(amount) not in ("0", "1", ""):
                    title = f"{amount}x {title}"
                character = getattr(card, "character", "")
                if character:
                    title = f"{title} · {character}"
                schedule = getattr(card, "schedule", "daily")
                badge = SCHEDULE_BADGES.get(schedule, SCHEDULE_BADGES["daily"])
                title = f"[Shop] {title}" if tab_key == "shopping" else f"[Task] {title}"
                row = OverlayTaskRow(tab_key, i, title, priority, badge=badge)
                row.check_btn.clicked.connect(
                    lambda _, tk=tab_key, idx=i: self._toggle_task(tk, idx)
                )
                rows.append(row)

        section = _AccordionSection("Tasks", len(rows), open_by_default=True)
        for row in rows:
            section.add_row(row)
        if not rows:
            section.add_row(self._empty_row("No active tasks ✓"))
        return section

    def _build_guide_section(self) -> _AccordionSection:
        mw = self.main_window
        fw = getattr(mw, "flow_map_window", None)
        rows = []

        if fw:
            from core.flow_model import FlowNode

            # Collect all maps marked for overlay; use live data for the active map
            all_maps = dict(getattr(mw, "flow_maps", {}))
            active_name = getattr(mw, "active_flow_map_name", None)
            if active_name:
                all_maps[active_name] = fw.get_flow_data()

            for map_name, map_data in all_maps.items():
                if not map_data.get("show_in_overlay", False):
                    continue
                nodes = {
                    nid: FlowNode.from_dict(nd)
                    for nid, nd in map_data.get("nodes", {}).items()
                }
                for node in nodes.values():
                    if node.status in ("active", "locked", "completed"):
                        row = OverlayGuideRow(node.id, node.title, node.status)
                        if node.status in ("active", "completed"):
                            row.check_btn.clicked.connect(
                                lambda _, nid=node.id, mn=map_name: self._toggle_node(nid, mn)
                            )
                        rows.append(row)

        section = _AccordionSection("Guide", len(rows), open_by_default=False)
        for row in rows:
            section.add_row(row)
        if not rows:
            section.add_row(self._empty_row("No flow loaded" if not fw else "All steps completed ✓"))
        return section

    def _toggle_node(self, node_id: str, map_name: str = None):
        mw = self.main_window
        fw = getattr(mw, "flow_map_window", None)
        active_name = getattr(mw, "active_flow_map_name", None)

        if map_name is None or map_name == active_name:
            if fw:
                fw.toggle_node_completed(node_id)
        else:
            from core.flow_model import FlowNode
            map_data = getattr(mw, "flow_maps", {}).get(map_name, {})
            node_data = map_data.get("nodes", {}).get(node_id)
            if node_data:
                node = FlowNode.from_dict(node_data)
                if node.status == "completed":
                    node.status = "active"
                    node.completed = False
                else:
                    node.status = "completed"
                    node.completed = True
                node_data["status"] = node.status
                node_data["completed"] = node.completed

        mw.save_profile(silent=True)
        self.refresh()

    def _empty_row(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("OverlayEmpty")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFixedHeight(40)
        return lbl

    # actions

    def _toggle_task(self, tab_key: str, index: int):
        cards = self.main_window.task_lists.get(tab_key, [])
        if 0 <= index < len(cards):
            cards[index].toggle()
            self.main_window.refresh()
            self.main_window.save_profile(silent=True)

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
