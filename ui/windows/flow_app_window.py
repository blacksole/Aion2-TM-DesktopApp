from PySide6.QtWidgets import (
    QComboBox,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QFrame,
)
from PySide6.QtCore import  Qt, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QPixmap, QIcon
from pathlib import Path
from core.flow_model import FlowNode


class FlowCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("FlowCanvas")

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        spacing = 72
        color = QColor(255, 255, 255, 12)
        pen = QPen(color)
        pen.setWidth(1)
        painter.setPen(pen)

        for x in range(0, self.width(), spacing):
            for y in range(0, self.height(), spacing):
                painter.drawLine(x - 4, y, x + 4, y)
                painter.drawLine(x, y - 4, x, y + 4)


class FlowNodeCard(QFrame):
    def __init__(self, title, description, icon="☆", status="active"):
        super().__init__()

        self.setObjectName("FlowNodeCard")
        self.setProperty("status", status)
        self.setFixedSize(440, 136)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 18, 18, 18)
        layout.setSpacing(18)

        self.icon_box = QLabel()
        self.icon_box.setObjectName("FlowNodeIcon")
        self.icon_box.setAlignment(Qt.AlignCenter)
        self.icon_box.setFixedSize(72, 72)

        pixmap = QPixmap(icon)

        if not pixmap.isNull():
            self.icon_box.setPixmap(
                pixmap.scaled(
                    54,
                    54,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            )
        else:
            self.icon_box.setText("☆")

        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("FlowNodeTitle")

        self.desc_label = QLabel(description)
        self.desc_label.setObjectName("FlowNodeDescription")
        self.desc_label.setWordWrap(True)

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.desc_label)
        text_layout.addStretch()

        self.done_btn = QPushButton("✓")
        self.done_btn.setObjectName("FlowDoneButton")
        self.done_btn.setFixedSize(34, 34)
        self.done_btn.setCursor(Qt.PointingHandCursor)

        layout.addWidget(self.icon_box)
        layout.addLayout(text_layout, 1)
        layout.addWidget(self.done_btn, alignment=Qt.AlignTop)


class FlowConnector(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(82)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignCenter)

        self.plus_btn = QPushButton("+")
        self.plus_btn.setObjectName("FlowConnectorPlus")
        self.plus_btn.setFixedSize(42, 42)
        self.plus_btn.setCursor(Qt.PointingHandCursor)

        line_top = QLabel("│")
        line_top.setObjectName("FlowConnectorLine")
        line_top.setAlignment(Qt.AlignCenter)

        arrow = QLabel("▼")
        arrow.setObjectName("FlowConnectorArrow")
        arrow.setAlignment(Qt.AlignCenter)

        layout.addWidget(line_top)
        layout.addWidget(self.plus_btn, alignment=Qt.AlignCenter)
        layout.addWidget(arrow)


class NodeEditorPanel(QFrame):
    def __init__(self, language="en", tr_func=None, icon_dir=None):
        super().__init__()

        self.language = language
        self.tr_func = tr_func
        self.icon_dir = icon_dir

        self.setObjectName("NodeEditorPanel")
        self.setFixedWidth(420)
        self.setFixedWidth(390)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()

        self.panel_title = QLabel()
        self.panel_title.setObjectName("PanelTitle")

        close_btn = QPushButton("×")
        close_btn.setObjectName("PanelCloseButton")
        close_btn.setFixedSize(34, 34)

        header.addWidget(self.panel_title)
        header.addStretch()
        header.addWidget(close_btn)

        self.title_label = QLabel()
        self.title_label.setObjectName("FieldLabel")

        self.title_input = QLineEdit()
        self.title_input.setObjectName("FlowInput")

        self.desc_label = QLabel()
        self.desc_label.setObjectName("FieldLabel")

        self.desc_input = QTextEdit()
        self.desc_input.setObjectName("FlowTextEdit")
        self.desc_input.setFixedHeight(150)

        self.symbol_label = QLabel()
        self.symbol_label.setObjectName("FieldLabel")

        self.symbol_combo = QComboBox()
        self.symbol_combo.setObjectName("FlowSymbolCombo")
        self.symbol_combo.setIconSize(QSize(42, 42))
        self.symbol_combo.setMinimumHeight(58)
        self.symbol_combo.view().setIconSize(QSize(42, 42))
        self.symbol_combo.view().setMinimumHeight(260)

        self.symbol_options = [
            ("character", "Character"),
            ("level", "Level"),
            ("expedition", "Expedition"),
            ("daily_dungeon", "Daily Dungeon"),
            ("sanctuary", "Sanctuary"),
            ("pets", "Pets"),
            ("closet", "Closet"),
            ("enhancement", "Enhancement"),
            ("crafting", "Crafting"),
            ("supply_request", "Supply Request"),
        ]

        for key, label in self.symbol_options:
            icon_path = self.icon_dir / f"{key}.png"

            self.symbol_combo.addItem(
                QIcon(str(icon_path)),
                label,
                key
            )

        button_row = QHBoxLayout()
        button_row.setSpacing(14)

        self.cancel_btn = QPushButton()
        self.cancel_btn.setObjectName("FlowCancelButton")

        self.save_btn = QPushButton()
        self.save_btn.setObjectName("FlowSaveButton")

        button_row.addWidget(self.cancel_btn)
        button_row.addWidget(self.save_btn)

        layout.addLayout(header)
        layout.addWidget(self.title_label)
        layout.addWidget(self.title_input)
        layout.addWidget(self.desc_label)
        layout.addWidget(self.desc_input)
        layout.addWidget(self.symbol_label)
        layout.addWidget(self.symbol_combo)
        layout.addSpacing(14)
        layout.addLayout(button_row)

        self.update_language(language, tr_func)

    def update_language(self, language, tr_func):
        self.language = language
        self.tr_func = tr_func

        self.panel_title.setText(tr_func(language, "flow_node_edit"))
        self.title_label.setText(tr_func(language, "flow_title_placeholder"))
        self.desc_label.setText(tr_func(language, "flow_description_placeholder"))
        self.symbol_label.setText(tr_func(language, "flow_symbol"))
        self.cancel_btn.setText(tr_func(language, "cancel"))
        self.save_btn.setText(tr_func(language, "flow_save"))

    def select_node(self, node_id: str):
        self.selected_node_id = node_id
        self.load_node_into_editor(node_id)


    def load_node_into_editor(self, node_id: str):
        node = self.nodes.get(node_id)

        if not node:
            return

        self.editor_panel.title_input.setText(node.title)
        self.editor_panel.desc_input.setPlainText(node.description)

        index = self.editor_panel.symbol_combo.findData(node.icon)

        if index >= 0:
            self.editor_panel.symbol_combo.setCurrentIndex(index)


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


class FlowMapWindow(QMainWindow):
    def __init__(self, parent=None, language="en", tr_func=None):
        super().__init__(parent)

        self.language = language
        self.tr_func = tr_func

        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.flow_icon_dir = self.project_root / "assets" / "icons" / "flow"

        self.resize(1700, 950)
        self.setMinimumSize(1400, 850)

        self.canvas = FlowCanvas()
        self.setCentralWidget(self.canvas)

        root = QVBoxLayout(self.canvas)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.topbar = QFrame()
        self.topbar.setObjectName("FlowTopbar")
        self.topbar.setFixedHeight(76)

        top_layout = QHBoxLayout(self.topbar)
        top_layout.setContentsMargins(28, 12, 28, 12)

        self.back_btn = QPushButton("‹")
        self.back_btn.setObjectName("FlowBackButton")
        self.back_btn.setFixedSize(46, 46)

        self.nodes: dict[str, FlowNode] = {}
        self.root_node_id = None
        self.selected_node_id = None

        self.plan_title = QLabel("Aion Classic Progress")
        self.plan_title.setObjectName("FlowPlanTitle")

        self.edit_mode_btn = QPushButton()
        self.edit_mode_btn.setObjectName("FlowModeButton")
        self.edit_mode_btn.setCheckable(True)
        self.edit_mode_btn.setChecked(True)

        self.guide_mode_btn = QPushButton()
        self.guide_mode_btn.setObjectName("FlowModeButton")
        self.guide_mode_btn.setCheckable(True)

        self.save_btn = QPushButton()
        self.save_btn.setObjectName("FlowTopSaveButton")

        top_layout.addWidget(self.back_btn)
        top_layout.addWidget(self.plan_title)
        top_layout.addStretch()
        top_layout.addWidget(self.edit_mode_btn)
        top_layout.addWidget(self.guide_mode_btn)
        top_layout.addStretch()
        top_layout.addWidget(self.save_btn)

        self.content = QWidget()
        content_layout = QHBoxLayout(self.content)
        content_layout.setContentsMargins(28, 24, 28, 18)
        content_layout.setSpacing(34)

        self.map_area = QWidget()
        self.map_layout = QVBoxLayout(self.map_area)
        self.map_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.map_layout.setSpacing(0)

        self.add_demo_flow()

        self.side_panel = QWidget()
        side_layout = QVBoxLayout(self.side_panel)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(16)

        self.editor_panel = NodeEditorPanel(language, tr_func, icon_dir=self.flow_icon_dir)
        self.status_panel = StatusPanel(language, tr_func)
        self.editor_panel.save_btn.clicked.connect(
            self.save_selected_node
        )

        side_layout.addWidget(self.editor_panel)
        side_layout.addWidget(self.status_panel)
        side_layout.addStretch()

        content_layout.addWidget(self.map_area, 1)
        content_layout.addWidget(self.side_panel)

        self.map_area.setMinimumWidth(800)

        

        self.info_bar = QFrame()
        self.info_bar.setObjectName("FlowInfoBar")
        self.info_bar.setFixedHeight(84)

        info_layout = QHBoxLayout(self.info_bar)
        info_layout.setContentsMargins(28, 12, 28, 12)

        self.info_icon = QLabel("i")
        self.info_icon.setObjectName("FlowInfoIcon")
        self.info_icon.setAlignment(Qt.AlignCenter)
        self.info_icon.setFixedSize(38, 38)

        self.info_text = QLabel()
        self.info_text.setObjectName("FlowInfoText")

        self.progress_hint = QLabel("✓  →  ○  →  ○")
        self.progress_hint.setObjectName("FlowProgressHint")

        info_layout.addWidget(self.info_icon)
        info_layout.addWidget(self.info_text)
        info_layout.addStretch()
        info_layout.addWidget(self.progress_hint)

        root.addWidget(self.topbar)
        root.addWidget(self.content, 1)
        root.addWidget(self.info_bar)

        self.update_language(language, tr_func)

    def update_language(self, language, tr_func):
        self.language = language
        self.tr_func = tr_func

        self.setWindowTitle(tr_func(language, "flow_window_title"))
        self.edit_mode_btn.setText(tr_func(language, "flow_edit_mode"))
        self.guide_mode_btn.setText(tr_func(language, "flow_guide_mode"))
        self.save_btn.setText("💾 " + tr_func(language, "flow_save"))

        self.info_text.setText(tr_func(language, "flow_info_text"))

        self.editor_panel.update_language(language, tr_func)
        self.status_panel.update_language(language, tr_func)

    def add_demo_flow(self):
        node1 = FlowNode(
            title="Char erstellen",
            description="Erstelle einen neuen\nCharakter.",
            icon="character",
            status="completed",
        )

        node2 = FlowNode(
            title="Level 26 erreichen",
            description="Erreiche mindestens\nLevel 26.",
            icon="level",
            status="active",
        )

        node3 = FlowNode(
            title="Dungeons erkunden",
            description="Absolviere erste Dungeons\nfür bessere Ausrüstung.",
            icon="daily_dungeon",
            status="locked",
        )

        node4 = FlowNode(
            title="Ausrüstung verbessern",
            description="Verbessere deine Ausrüstung\ndurch Crafting.",
            icon="crafting",
            status="locked",
        )

        node1.children.append(node2.id)
        node2.children.append(node3.id)
        node3.children.append(node4.id)

        self.nodes = {
            node1.id: node1,
            node2.id: node2,
            node3.id: node3,
            node4.id: node4,
        }

        self.root_node_id = node1.id
        self.render_flow()


    def clear_map_layout(self):
        while self.map_layout.count():
            item = self.map_layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()


    def render_flow(self):
        self.clear_map_layout()

        if not self.root_node_id:
            return

        current_id = self.root_node_id

        while current_id:
            node = self.nodes.get(current_id)

            if not node:
                break

            card = FlowNodeCard(
                node.title,
                node.description,
                icon=self.get_icon_symbol(node.icon),
                status=node.status,
            )

            card.mousePressEvent = (
                lambda event, node_id=node.id: self.select_node(node_id)
            )

            self.map_layout.addWidget(card, alignment=Qt.AlignCenter)

            connector = FlowConnector()
            connector.plus_btn.clicked.connect(
                lambda checked=False, parent_id=node.id: self.add_child_node(parent_id)
            )

            self.map_layout.addWidget(connector, alignment=Qt.AlignCenter)

            current_id = node.children[0] if node.children else None


    def get_icon_symbol(self, icon_key: str):
        icon_map = {
            "character": "character.png",
            "level": "level.png",
            "expedition": "expedition.png",
            "daily_dungeon": "daily_dungeon.png",
            "sanctuary": "sanctuary.png",
            "pets": "pets.png",
            "closet": "closet.png",
            "enhancement": "enhancement.png",
            "crafting": "crafting.png",
            "supply_request": "supply_request.png",
        }

        filename = icon_map.get(icon_key, "level.png")
        return str(self.flow_icon_dir / filename)


    def add_child_node(self, parent_id: str):
        parent_node = self.nodes.get(parent_id)

        if not parent_node:
            return

        new_node = FlowNode(
            title="Neue Kachel",
            description="Beschreibung hinzufügen.",
            icon="level",
            status="locked",
        )

        if not parent_node.children:
            parent_node.children.append(new_node.id)

        self.nodes[new_node.id] = new_node
        self.selected_node_id = new_node.id

        self.render_flow()
        self.load_node_into_editor(new_node.id)

    def select_node(self, node_id: str):
        self.selected_node_id = node_id
        self.load_node_into_editor(node_id)


    def load_node_into_editor(self, node_id: str):
        node = self.nodes.get(node_id)

        if not node:
            return

        self.editor_panel.title_input.setText(node.title)
        self.editor_panel.desc_input.setPlainText(node.description)

    def save_selected_node(self):
        if not self.selected_node_id:
            return

        node = self.nodes.get(self.selected_node_id)

        if not node:
            return

        node.title = self.editor_panel.title_input.text().strip()
        node.description = self.editor_panel.desc_input.toPlainText().strip()
        node.icon = self.editor_panel.symbol_combo.currentData()

        self.render_flow()