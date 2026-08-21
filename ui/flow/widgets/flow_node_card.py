from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QGridLayout
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QIcon

from ui.flow.flow_layout import (
    NODE_WIDTH,
    NODE_HEIGHT,
    ICON_BOX_SIZE,
    ICON_SIZE,
    TITLE_SIZE,
    DESCRIPTION_SIZE,
)


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

        if zoom >= 1.0:
            title_size = TITLE_SIZE
        elif zoom >= 0.8:
            title_size = 16
        else:
            title_size = 15

        self.title_label.setStyleSheet(
            f"""
            font-size: {title_size}px;
            font-weight: 700;
            """
        )

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

        if zoom >= 1.0:
            desc_size = DESCRIPTION_SIZE
        elif zoom >= 0.8:
            desc_size = 12
        else:
            desc_size = 1

        self.desc_label.setStyleSheet(
            f"""
            font-size: {desc_size}px;
            """
        )
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

        title_size = TITLE_SIZE if zoom >= 1.0 else (16 if zoom >= 0.8 else 15)
        self.title_label.setStyleSheet(f"font-size: {title_size}px; font-weight: 700;")

        desc_size = DESCRIPTION_SIZE if zoom >= 1.0 else (12 if zoom >= 0.8 else 1)
        self.desc_label.setStyleSheet(f"font-size: {desc_size}px;")
        self.desc_label.setVisible(zoom >= 0.8)

        if zoom >= 1.0:
            self.desc_label.setText(description)
        elif zoom >= 0.8:
            self.desc_label.setText(
                description[:45] + "..." if len(description) > 45 else description
            )
        else:
            self.desc_label.setText("")