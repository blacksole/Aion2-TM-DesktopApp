from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)

DEBUG_MODE = False

# Panels
SHOW_STATUS_PANEL = True

# Text
SHOW_MOUSE_DEBUG = True
SHOW_NODE_CENTER = True
SHOW_VIEWPORT_INFO = True
SHOW_MAP_AREA_INFO = True

# Visual Debug
SHOW_PARENT_ANCHORS = False
SHOW_CHILD_ANCHORS = False
SHOW_CONNECTOR_PATHS = False
SHOW_LAYOUT_BOXES = False
SHOW_SUBTREE_WIDTH = False
SHOW_CARD_BOUNDS = False

def debug_enabled(flag):
    return DEBUG_MODE and flag


def format_mouse_debug_text(
    content_pos,
    map_pos,
    viewport_center,
    map_area_pos,
    node_center_text,
):
    parts = []

    if SHOW_MOUSE_DEBUG:
        parts.append(
            f"Mouse | Content: {content_pos.x()}, {content_pos.y()} "
            f"| Map: {map_pos.x()}, {map_pos.y()}"
        )

    if SHOW_VIEWPORT_INFO:
        parts.append(
            f"Viewport Center: {viewport_center.x()}, {viewport_center.y()}"
        )

    if SHOW_MAP_AREA_INFO:
        parts.append(
            f"MapArea Pos: {map_area_pos.x()}, {map_area_pos.y()}"
        )

    if SHOW_NODE_CENTER:
        parts.append(node_center_text)

    return " | ".join(parts)

def update_mouse_position_debug_label(window, pos, source_widget):
    if not DEBUG_MODE:
        window.mouse_debug_label.setText("")
        return

    global_pos = source_widget.mapToGlobal(pos)
    content_pos = window.content.mapFromGlobal(global_pos)
    map_pos = window.map_area.mapFromGlobal(global_pos)

    viewport_center = window.map_viewport.rect().center()
    map_area_pos = window.map_area.pos()

    node_center_text = "Nodes Center: -"

    if window.map_layout.count() > 0:
        flow_widget = window.map_layout.itemAt(0).widget()

        if flow_widget:
            flow_center = flow_widget.geometry().center()

            node_center_global = window.map_area.mapToGlobal(flow_center)
            node_center_viewport = window.map_viewport.mapFromGlobal(
                node_center_global
            )

            node_center_text = (
                f"Nodes Center Map: {flow_center.x()}, {flow_center.y()} "
                f"| Nodes Center Viewport: "
                f"{node_center_viewport.x()}, {node_center_viewport.y()}"
            )

    window.mouse_debug_label.setText(
        format_mouse_debug_text(
            content_pos,
            map_pos,
            viewport_center,
            map_area_pos,
            node_center_text,
        )
    )

class StatusPanel(QFrame):
    def __init__(self, language="en", tr_func=None):
        super().__init__()

        self.setObjectName("StatusPanel")
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(12)

        self.title = QLabel()
        self.title.setObjectName("PanelTitle")
        self.setFixedWidth(390)

        layout.addWidget(self.title)

        items = [
            ("green", "status_completed"),
            ("blue", "status_active"),
            ("yellow", "status_optional"),
            ("gray", "status_locked"),
        ]

        self.rows = []

        for color, key in items:
            row = QHBoxLayout()

            dot = QLabel("●")
            dot.setObjectName(f"StatusDot_{color}")

            text = QLabel()
            text.setObjectName("StatusText")

            row.addWidget(dot)
            row.addWidget(text)
            row.addStretch()

            layout.addLayout(row)
            self.rows.append((text, key))

        self.update_language(language, tr_func)

    def update_language(self, language, tr_func):
        self.title.setText(tr_func(language, "flow_status_colors"))

        for text, key in self.rows:
            text.setText(tr_func(language, key))