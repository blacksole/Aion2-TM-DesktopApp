from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QRadialGradient

from core.flow_model import FlowNode
from ui.flow.widgets.delete_confirm_dialog import UnsavedChangesDialog


NODE_RADIUS = 14
NODE_SPACING_H = 160
BRANCH_OFFSET_Y = 85
LABEL_MAX_CHARS = 14

STATUS_COLORS = {
    "completed": QColor(34, 197, 94),
    "active":    QColor(59, 130, 246),
    "optional":  QColor(245, 158, 11),
    "locked":    QColor(71, 85, 105),
}

GLOW_COLORS = {
    "completed": QColor(34, 197, 94, 45),
    "active":    QColor(59, 130, 246, 55),
    "optional":  QColor(245, 158, 11, 45),
    "locked":    QColor(71, 85, 105, 20),
}


class FlowGuideCanvas(QWidget):
    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view
        self._node_positions: dict[str, QPoint] = {}
        self._hovered_id: str | None = None
        self.setMouseTracking(True)
        self.setMinimumHeight(220)

    def set_node_positions(self, positions: dict[str, QPoint]):
        self._node_positions = positions
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        nodes = self.parent_view.nodes
        if not nodes or not self.parent_view.root_node_id:
            return

        self._draw_all_lines(painter, self.parent_view.root_node_id, nodes)

        for node_id, pos in self._node_positions.items():
            node = nodes.get(node_id)
            if node:
                self._draw_node(painter, node, pos)

        for node_id, pos in self._node_positions.items():
            node = nodes.get(node_id)
            if node:
                self._draw_label(painter, node, pos)

    def _draw_all_lines(self, painter, node_id: str, nodes: dict):
        node = nodes.get(node_id)
        if not node:
            return
        pos = self._node_positions.get(node_id)
        if not pos:
            return
        painter.setPen(QPen(QColor(71, 85, 105, 160), 2, Qt.SolidLine))
        for child_id in node.children:
            child_pos = self._node_positions.get(child_id)
            if child_pos:
                painter.drawLine(pos, child_pos)
            self._draw_all_lines(painter, child_id, nodes)

    def _draw_node(self, painter, node: FlowNode, pos: QPoint):
        status = node.status
        color = STATUS_COLORS.get(status, STATUS_COLORS["locked"])
        glow_color = GLOW_COLORS.get(status, GLOW_COLORS["locked"])
        is_hovered = node.id == self._hovered_id
        is_selected = node.id == self.parent_view._selected_node_id

        r = NODE_RADIUS
        glow_r = r + 12 if (is_hovered or is_selected) else r + 6

        gradient = QRadialGradient(pos.x(), pos.y(), glow_r)
        gradient.setColorAt(0.0, glow_color)
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(pos, glow_r, glow_r)

        if is_selected:
            ring = QColor(color)
            ring.setAlpha(210)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(ring, 2.5))
            painter.drawEllipse(pos, r + 6, r + 6)

        fill = color.lighter(135) if is_hovered else color
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(color.lighter(170), 1.5))
        painter.drawEllipse(pos, r, r)

        if node.status == "completed":
            font = QFont()
            font.setPixelSize(13)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
            painter.drawText(
                QRect(pos.x() - r, pos.y() - r, r * 2, r * 2),
                Qt.AlignCenter,
                "✓",
            )

    def _draw_label(self, painter, node: FlowNode, pos: QPoint):
        text = (
            node.title
            if len(node.title) <= LABEL_MAX_CHARS
            else node.title[:LABEL_MAX_CHARS - 1] + "…"
        )

        font = QFont()
        font.setPixelSize(11)
        font.setBold(node.id == self.parent_view._selected_node_id)
        painter.setFont(font)

        if node.id == self.parent_view._selected_node_id:
            color = QColor(248, 250, 252)
        elif node.status == "locked":
            color = QColor(100, 116, 139)
        else:
            color = QColor(148, 163, 184)

        painter.setPen(QPen(color))
        label_y = pos.y() + NODE_RADIUS + 6
        painter.drawText(
            QRect(pos.x() - 72, label_y, 144, 20),
            Qt.AlignCenter,
            text,
        )

    def _node_at(self, pos: QPoint) -> str | None:
        for node_id, node_pos in self._node_positions.items():
            dx = pos.x() - node_pos.x()
            dy = pos.y() - node_pos.y()
            if dx * dx + dy * dy <= (NODE_RADIUS + 8) ** 2:
                return node_id
        return None

    def mouseMoveEvent(self, event):
        hit = self._node_at(event.pos())
        if hit != self._hovered_id:
            self._hovered_id = hit
            self.update()
            if hit:
                node = self.parent_view.nodes.get(hit)
                if node:
                    self.parent_view.show_node_info(node, hover=True)
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.parent_view.revert_to_selected_info()
                self.setCursor(Qt.ArrowCursor)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            hit = self._node_at(event.pos())
            if hit:
                self.parent_view.select_node(hit)
            else:
                self.parent_view.deselect_node()
        super().mousePressEvent(event)

    def leaveEvent(self, event):
        self._hovered_id = None
        self.parent_view.revert_to_selected_info()
        self.update()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.parent_view.refresh()


class FlowGuideView(QWidget):
    def __init__(self, window):
        super().__init__()

        self.window = window
        self.setObjectName("FlowGuideView")
        self._selected_node_id: str | None = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.canvas = FlowGuideCanvas(self)
        root_layout.addWidget(self.canvas, 1)

        self.info_bar = QFrame()
        self.info_bar.setObjectName("GuideInfoBar")
        self.info_bar.setFixedHeight(90)

        info_layout = QHBoxLayout(self.info_bar)
        info_layout.setContentsMargins(28, 12, 28, 12)
        info_layout.setSpacing(18)

        self.info_icon_label = QLabel("●")
        self.info_icon_label.setObjectName("GuideInfoIcon")
        self.info_icon_label.setFixedWidth(28)
        self.info_icon_label.setAlignment(Qt.AlignCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self.info_title = QLabel("—")
        self.info_title.setObjectName("GuideInfoTitle")

        self.info_desc = QLabel("")
        self.info_desc.setObjectName("GuideInfoDesc")
        self.info_desc.setWordWrap(True)

        text_col.addWidget(self.info_title)
        text_col.addWidget(self.info_desc)

        self.done_btn = QPushButton("✓  Als erledigt markieren")
        self.done_btn.setObjectName("GuideDoneButton")
        self.done_btn.setFixedSize(220, 44)
        self.done_btn.setVisible(False)
        self.done_btn.setCursor(Qt.PointingHandCursor)
        self.done_btn.clicked.connect(self._on_done_clicked)

        self.edit_btn = QPushButton("✏  Edit")
        self.edit_btn.setObjectName("GuideEditButton")
        self.edit_btn.setFixedSize(88, 44)
        self.edit_btn.setVisible(False)
        self.edit_btn.setCursor(Qt.PointingHandCursor)
        self.edit_btn.clicked.connect(self._on_edit_clicked)

        info_layout.addWidget(self.info_icon_label)
        info_layout.addLayout(text_col, 1)
        info_layout.addWidget(self.done_btn)
        info_layout.addWidget(self.edit_btn)

        root_layout.addWidget(self.info_bar)

    @property
    def nodes(self) -> dict:
        return self.window.nodes

    @property
    def root_node_id(self) -> str | None:
        return self.window.root_node_id

    def refresh(self):
        positions = self._calculate_positions()
        self.canvas.set_node_positions(positions)

    def _calculate_positions(self) -> dict[str, QPoint]:
        positions: dict[str, QPoint] = {}
        if not self.root_node_id:
            return positions
        canvas_h = max(self.canvas.height(), 200)
        main_y = canvas_h // 2
        self._place_node(self.root_node_id, 60, main_y, positions)
        return positions

    def _place_node(self, node_id: str, x: int, y: int, positions: dict):
        node = self.nodes.get(node_id)
        if not node:
            return
        positions[node_id] = QPoint(x, y)
        next_x = x + NODE_SPACING_H
        for i, child_id in enumerate(node.children):
            child_y = y + i * BRANCH_OFFSET_Y
            self._place_node(child_id, next_x, child_y, positions)

    def select_node(self, node_id: str):
        editor_open = self.window.side_panel_wrapper.isVisible()
        if editor_open and self.window.editor_panel.is_dirty:
            if not self.window.controller.confirm_dirty_before_action():
                return

        self._selected_node_id = node_id
        self.window.selected_node_id = node_id

        if editor_open:
            self.window.load_node_into_editor(node_id)

        node = self.nodes.get(node_id)
        if node:
            self.show_node_info(node, hover=False)
        self.canvas.update()

    def deselect_node(self):
        self._selected_node_id = None
        self.canvas._hovered_id = None
        self.clear_node_info()
        self.canvas.update()

    def revert_to_selected_info(self):
        if self._selected_node_id:
            node = self.nodes.get(self._selected_node_id)
            if node:
                self.show_node_info(node, hover=False)
        else:
            self.clear_node_info()

    def show_node_info(self, node: FlowNode, hover: bool = False):
        color = STATUS_COLORS.get(node.status, STATUS_COLORS["locked"])
        self.info_icon_label.setText("●")
        self.info_icon_label.setStyleSheet(
            f"color: {color.name()}; font-size: 22px;"
        )
        self.info_title.setText(node.title)
        self.info_desc.setText(node.description)

        is_selected = node.id == self._selected_node_id
        can_act = node.status in ("active", "completed")

        self.done_btn.setVisible(can_act and is_selected)
        self.edit_btn.setVisible(is_selected)

        if node.status == "completed":
            self.done_btn.setText("↩  Als offen markieren")
        else:
            self.done_btn.setText("✓  Als erledigt markieren")

    def clear_node_info(self):
        self.info_icon_label.setStyleSheet("color: #334155; font-size: 22px;")
        self.info_title.setText("—")
        self.info_desc.setText("")
        self.done_btn.setVisible(False)
        self.edit_btn.setVisible(False)

    def _on_done_clicked(self):
        if not self._selected_node_id:
            return
        self.window.toggle_node_completed(self._selected_node_id)
        node = self.nodes.get(self._selected_node_id)
        if node:
            self.show_node_info(node, hover=False)
        self.refresh()

    def _on_edit_clicked(self):
        if not self._selected_node_id:
            return
        self.window.selected_node_id = self._selected_node_id
        self.window.expand_editor_panel()
        self.window.load_node_into_editor(self._selected_node_id)
        self.window.side_panel_wrapper.setVisible(True)
        self.window.side_panel_wrapper.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh()
