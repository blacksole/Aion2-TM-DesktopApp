from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QGridLayout
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QIcon

from ui.flow.flow_layout import (
    NODE_WIDTH,
    NODE_HEIGHT,
    ICON_BOX_SIZE,
    ICON_SIZE,
)


#: Zoom buckets the Flow Map's three discrete label sizes used to be
#: expressed as inline ``font-size:`` literals.  There were only ever three,
#: so they are a *state*, not a continuous scale: the value goes on the
#: labels as a ``zoomStep`` property and ui/styles.template.qss holds the
#: sizes (``#FlowNodeTitle[zoomStep="mid"]`` &c.), which is what MASTER §4-4
#: asks for — no setStyleSheet in a widget.
_ZOOM_STEPS = (
    (1.0, "full"),
    (0.8, "mid"),
    (0.0, "small"),
)


def _zoom_step(zoom: float) -> str:
    """Name of the zoom bucket ``zoom`` falls in."""
    for threshold, name in _ZOOM_STEPS:
        if zoom >= threshold:
            return name
    return _ZOOM_STEPS[-1][1]


class FlowNodeCard(QFrame):
    def __init__(
        self,
        node_id,
        title,
        description,
        icon="☆",
        status="active",
        zoom=1.0,
        parent_window=None,
        parent=None,
    ):
        super().__init__(parent)

        self.setObjectName("FlowNodeCard")
        self.setProperty("status", status)
        self.setFixedSize(int(NODE_WIDTH * zoom), int(NODE_HEIGHT * zoom))

        self.node_id = node_id
        self.parent_window = parent_window

        self.icon_box = QLabel()
        self.icon_box.setObjectName("FlowNodeIcon")
        self.icon_box.setAlignment(Qt.AlignCenter)
        self.icon_box.setFixedSize(
            int(ICON_BOX_SIZE * zoom),
            int(ICON_BOX_SIZE * zoom),
        )

        pixmap = QPixmap(icon)
        self._original_pixmap = pixmap if not pixmap.isNull() else None

        if self._original_pixmap:
            self.icon_box.setPixmap(
                self._original_pixmap.scaled(
                    int(ICON_SIZE * zoom),
                    int(ICON_SIZE * zoom),
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation,
                )
            )
        else:
            self.icon_box.setText("☆")

        self.title_label = QLabel(title)
        self.title_label.setObjectName("FlowNodeTitle")
        self._apply_zoom_step(zoom)

        if zoom >= 1.0:
            visible_description = description
        elif zoom >= 0.8:
            visible_description = (
                description[:45] + "..."
                if len(description) > 45
                else description
            )
        else:
            visible_description = ""

        self.desc_label = QLabel(visible_description)
        self.desc_label.setObjectName("FlowNodeDescription")
        self.desc_label.setWordWrap(True)
        self._apply_zoom_step(zoom)
        self.desc_label.setVisible(zoom >= 0.8)

        self.add_node_hint_btn = QPushButton()
        self.add_node_hint_btn.setObjectName("FlowNodeAddHintButton")
        self.add_node_hint_btn.setFixedSize(int(72 * zoom), int(64 * zoom))
        self.add_node_hint_btn.setCursor(Qt.PointingHandCursor)
        self.add_node_hint_btn.setEnabled(False)
        self.add_node_hint_btn.setProperty("visibleState", "false")

        if self.parent_window:
            plus_icon = self.parent_window.flow_tool_icon_dir / "cursor_addNode.png"
            self.add_node_hint_btn.setIcon(QIcon(str(plus_icon)))
            self.add_node_hint_btn.setIconSize(QSize(int(50 * zoom), int(50 * zoom)))
        else:
            self.add_node_hint_btn.setText("+")

        self.done_btn = QPushButton("✓")
        self.done_btn.setObjectName("FlowDoneButton")
        self.done_btn.setFixedSize(34, 34)
        self.done_btn.setCursor(Qt.PointingHandCursor)

        grid = QGridLayout(self)
        grid.setContentsMargins(
            int(22 * zoom), int(18 * zoom), int(18 * zoom), int(14 * zoom)
        )
        grid.setHorizontalSpacing(int(18 * zoom))
        grid.setVerticalSpacing(int(2 * zoom))

        grid.addWidget(self.icon_box, 0, 0, 3, 1, Qt.AlignTop)
        grid.addWidget(self.title_label, 0, 1, Qt.AlignLeft | Qt.AlignTop)
        grid.addWidget(self.desc_label, 1, 1, Qt.AlignLeft | Qt.AlignTop)
        grid.addWidget(self.add_node_hint_btn, 2, 0, 1, 3, Qt.AlignHCenter | Qt.AlignTop)
        grid.addWidget(self.done_btn, 0, 2, Qt.AlignRight | Qt.AlignTop)

        grid.setColumnStretch(1, 1)

        # Let mouse events pass through to the card frame
        for w in (self.icon_box, self.title_label, self.desc_label, self.add_node_hint_btn):
            w.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def _apply_zoom_step(self, zoom: float):
        """Tag both labels with the zoom bucket so the QSS can size them."""
        step = _zoom_step(zoom)
        for label in (getattr(self, "title_label", None), getattr(self, "desc_label", None)):
            if label is None:  # __init__ builds the title before the description
                continue
            label.setProperty("zoomStep", step)
            label.style().unpolish(label)
            label.style().polish(label)

    def enterEvent(self, event):
        if self.parent_window:
            if self.parent_window.current_tool == "add_node":
                self.add_node_hint_btn.setEnabled(True)
                self.add_node_hint_btn.setProperty("visibleState", "true")
                self.add_node_hint_btn.style().unpolish(self.add_node_hint_btn)
                self.add_node_hint_btn.style().polish(self.add_node_hint_btn)

        super().enterEvent(event)

    def leaveEvent(self, event):
        self.add_node_hint_btn.setEnabled(False)
        self.add_node_hint_btn.setProperty("visibleState", "false")
        self.add_node_hint_btn.style().unpolish(self.add_node_hint_btn)
        self.add_node_hint_btn.style().polish(self.add_node_hint_btn)

        super().leaveEvent(event)

    def apply_zoom(self, zoom: float, description: str = ""):
        self.setFixedSize(int(NODE_WIDTH * zoom), int(NODE_HEIGHT * zoom))
        box_px = int(ICON_BOX_SIZE * zoom)
        self.icon_box.setFixedSize(box_px, box_px)

        grid = self.layout()
        grid.setContentsMargins(
            int(22 * zoom), int(18 * zoom), int(18 * zoom), int(14 * zoom)
        )
        grid.setHorizontalSpacing(int(18 * zoom))
        grid.setVerticalSpacing(int(2 * zoom))
        self.add_node_hint_btn.setFixedSize(int(72 * zoom), int(64 * zoom))
        self.add_node_hint_btn.setIconSize(QSize(int(50 * zoom), int(50 * zoom)))
        if self._original_pixmap:
            icon_px = int(ICON_SIZE * zoom)
            self.icon_box.setPixmap(
                self._original_pixmap.scaled(
                    icon_px, icon_px,
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation,
                )
            )

        self._apply_zoom_step(zoom)
        self.desc_label.setVisible(zoom >= 0.8)

        if zoom >= 1.0:
            self.desc_label.setText(description)
        elif zoom >= 0.8:
            self.desc_label.setText(
                description[:45] + "..." if len(description) > 45 else description
            )
        else:
            self.desc_label.setText("")