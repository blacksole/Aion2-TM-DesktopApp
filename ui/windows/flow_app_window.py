from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QFrame,
    QComboBox,
    QButtonGroup,
)
from PySide6.QtCore import  Qt, QSize, QTimer
from PySide6.QtGui import (
    QPainter, 
    QColor, 
    QPen, 
    QPixmap, 
    QIcon,
    QCursor,
)
from pathlib import Path
from core.flow_model import FlowNode


class FlowCanvas(QWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("FlowCanvas")

    def set_pan_target(self, widget):
        self.pan_target = widget

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

class FlowMapViewport(QWidget):
    def __init__(self, parent_window=None):
        super().__init__()

        self.parent_window = parent_window

        self.setObjectName("FlowMapViewport")
        self.setCursor(Qt.OpenHandCursor)

        self.is_panning = False
        self.pan_start_pos = None
        self.pan_target = None

    def set_pan_target(self, widget):
        self.pan_target = widget

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_panning = True
            self.pan_start_pos = event.position().toPoint()
            if self.parent_window:
                self.parent_window.set_tool_cursor(
                    "cursor_hold.png"
                )

    def mouseMoveEvent(self, event):
        if not self.is_panning or not self.pan_target:
            return

        current_pos = event.position().toPoint()
        delta = current_pos - self.pan_start_pos
        self.pan_start_pos = current_pos

        self.pan_target.move(
            self.pan_target.x() + delta.x(),
            self.pan_target.y() + delta.y()
        )

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_panning = False

            if self.parent_window:
                self.parent_window.apply_current_tool_cursor()


class FlowNodeCard(QFrame):
    def __init__(self, node_id, title, description, icon="☆", status="active",  zoom=1.0):
        super().__init__()

        self.setObjectName("FlowNodeCard")
        self.setProperty("status", status)
        self.setFixedSize(int(440 * zoom), int(136 * zoom))
        self.node_id = node_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 18, 18, 18)
        layout.setSpacing(18)

        self.icon_box = QLabel()
        self.icon_box.setObjectName("FlowNodeIcon")
        self.icon_box.setAlignment(Qt.AlignCenter)
        self.icon_box.setFixedSize(int(72 * zoom), int(72 * zoom))

        pixmap = QPixmap(icon)

        if not pixmap.isNull():
            self.icon_box.setPixmap(
                pixmap.scaled(
                    int(54 * zoom), int(54 * zoom),
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

        if zoom >= 1.0:
            title_size = 18
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

        # ======= DESC EDITOR PANEL ZOOM LOGIC ======= #


        if zoom >= 1.0:
            visible_description = description
        elif zoom >= 0.8:
            visible_description = description[:45] + "..." if len(description) > 45 else description
        else:
            visible_description = ""


        self.desc_label = QLabel(visible_description)
        self.desc_label.setObjectName("FlowNodeDescription")
        self.desc_label.setWordWrap(True)

        if zoom >= 1.0:
            desc_size = 13
        elif zoom >= 0.8:
            desc_size = 12
        else:
            desc_size = 0

        self.desc_label.setStyleSheet(
            f"""
            font-size: {desc_size}px;
            """
        )

        self.desc_label.setVisible(zoom >= 0.8)

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
    def __init__(self, zoom=1.0):
        super().__init__()
        self.setFixedHeight(int(82 * zoom))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignCenter)

        line_top = QLabel("│")
        line_top.setObjectName("FlowConnectorLine")
        line_top.setAlignment(Qt.AlignCenter)

        arrow = QLabel("▼")
        arrow.setObjectName("FlowConnectorArrow")
        arrow.setAlignment(Qt.AlignCenter)

        line_top.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        arrow.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        layout.addWidget(line_top)
        layout.addWidget(arrow)

        self.setToolTip("")


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

        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("PanelCloseButton")
        self.close_btn.setFixedSize(34, 34)
        self.close_btn.setCursor(Qt.PointingHandCursor)

        header.addWidget(self.panel_title)
        header.addStretch()
        header.addWidget(self.close_btn)

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

        self.node_cancel_btn = QPushButton()
        self.node_cancel_btn.setObjectName("FlowCancelButton")

        self.node_save_btn = QPushButton()
        self.node_save_btn.setObjectName("FlowSaveButton")

        button_row.addWidget(self.node_cancel_btn)
        button_row.addWidget(self.node_save_btn)

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
        self.node_cancel_btn.setText(tr_func(language, "cancel"))
        self.node_save_btn.setText(tr_func(language, "flow_save"))

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
        self.flow_icon_dir = (
            self.project_root / "assets" / "icons" / "flow"
        )

        self.flow_tool_icon_dir = (
            self.flow_icon_dir / "tools"
        )

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
        self.zoom_factor = 1.0
        self.current_tool = "select"

        self.plan_title = QLabel("Aion Classic Progress")
        self.plan_title.setObjectName("FlowPlanTitle")

        self.edit_mode_btn = QPushButton()
        self.edit_mode_btn.setObjectName("FlowModeButton")
        self.edit_mode_btn.setCheckable(True)
        self.edit_mode_btn.setChecked(True)

        self.guide_mode_btn = QPushButton()
        self.guide_mode_btn.setObjectName("FlowModeButton")
        self.guide_mode_btn.setCheckable(True)

        self.zoom_combo = QComboBox()
        self.zoom_combo.setObjectName("FlowZoomCombo")
        self.zoom_combo.addItem("100%", 1.0)
        self.zoom_combo.addItem("80%", 0.8)
        self.zoom_combo.addItem("60%", 0.6)
        self.zoom_combo.setCurrentIndex(0)
        self.zoom_combo.setFixedHeight(42)
        self.zoom_combo.setMinimumHeight(42)
        self.zoom_combo.setMaximumHeight(42)
        self.zoom_combo.currentIndexChanged.connect(self.change_zoom)

        self.save_status_label = QLabel("✓ Saved")
        self.save_status_label.setObjectName("FlowSaveStatusLabel")

        self.mode_tabs = QFrame()
        self.mode_tabs.setObjectName("FlowModeTabs")

        mode_layout = QHBoxLayout(self.mode_tabs)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(0)

        mode_layout.addWidget(self.edit_mode_btn)
        mode_layout.addWidget(self.guide_mode_btn)

        top_layout.addWidget(self.back_btn)
        top_layout.addWidget(self.plan_title)

        top_layout.addStretch()
        top_layout.addWidget(self.mode_tabs)
        top_layout.addStretch()

        top_layout.addWidget(self.zoom_combo)
        top_layout.setSpacing(10)
        top_layout.addWidget(self.save_status_label)

        self.content = QWidget()
        content_layout = QHBoxLayout(self.content)
        content_layout.setContentsMargins(28, 24, 28, 18)
        content_layout.setSpacing(34)

        # ====== TOOLBAR & MAP AREA ======= #

        self.tool_bar = QFrame()
        self.tool_bar.setObjectName("FlowToolBar")
        self.tool_bar.setFixedWidth(64)

        tool_layout = QVBoxLayout(self.tool_bar)
        tool_layout.setContentsMargins(8, 8, 8, 8)
        tool_layout.setSpacing(10)

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)

        self.select_tool_btn = QPushButton()
        self.select_tool_btn.setIcon(
            QIcon(str(self.flow_tool_icon_dir / "select_node.png"))
        )
        self.select_tool_btn.setObjectName("FlowToolButton")
        self.select_tool_btn.setCheckable(True)
        self.select_tool_btn.setChecked(True)
        self.select_tool_btn.setToolTip("Select")

        self.add_node_tool_btn = QPushButton()
        self.add_node_tool_btn.setIcon(
            QIcon(str(self.flow_tool_icon_dir / "tool_addNode.png"))
        )
        self.add_node_tool_btn.setObjectName("FlowToolButton")
        self.add_node_tool_btn.setCheckable(True)
        self.add_node_tool_btn.setToolTip("Add Node")

        self.branch_tool_btn = QPushButton()
        self.branch_tool_btn.setIcon(
            QIcon(str(self.flow_tool_icon_dir / "add_branch.png"))
        )

        self.branch_tool_btn.setObjectName("FlowToolButton")
        self.branch_tool_btn.setCheckable(True)
        self.branch_tool_btn.setToolTip("Branch")

        self.delete_tool_btn = QPushButton()
        self.delete_tool_btn.setIcon(
            QIcon(str(self.flow_tool_icon_dir / "delete_node.png"))
        )
        self.delete_tool_btn.setObjectName("FlowToolButton")
        self.delete_tool_btn.setCheckable(True)
        self.delete_tool_btn.setToolTip("Delete")

        for btn in [
            self.select_tool_btn,
            self.add_node_tool_btn,
            self.branch_tool_btn,
            self.delete_tool_btn,
        ]:
            btn.setIconSize(QSize(28, 28))

        tools = [
            (self.select_tool_btn, "select"),
            (self.add_node_tool_btn, "add_node"),
            (self.branch_tool_btn, "branch"),
            (self.delete_tool_btn, "delete"),
        ]

        for button, tool_name in tools:
            self.tool_group.addButton(button)
            button.clicked.connect(
                lambda checked=False, tool=tool_name: self.set_current_tool(tool)
            )
            tool_layout.addWidget(button)

        tool_layout.addStretch()

        self.map_viewport = FlowMapViewport(self)

        self.map_area = QWidget(self.map_viewport)
        self.map_area.resize(900, 2000)
        self.map_area.move(0, 0)

        self.map_viewport.set_pan_target(self.map_area)

        self.map_layout = QVBoxLayout(self.map_area)
        self.map_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.map_layout.setSpacing(0)



        self.add_demo_flow()

        self.side_panel_wrapper = QWidget()
        side_wrapper_layout = QVBoxLayout(self.side_panel_wrapper)
        side_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        side_wrapper_layout.setSpacing(8)

        self.side_panel = QWidget()
        side_layout = QVBoxLayout(self.side_panel)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(16)

        self.editor_panel = NodeEditorPanel(
            language,
            tr_func,
            icon_dir=self.flow_icon_dir
        )

        self.editor_panel.node_save_btn.clicked.connect(
            self.save_selected_node
        )

        self.editor_panel.close_btn.clicked.connect(
            self.collapse_editor_panel
        )

        side_layout.addWidget(self.editor_panel)
        side_layout.addStretch()

        self.toggle_editor_btn = QPushButton(">>")
        self.toggle_editor_btn.setObjectName("FlowEditorBottomToggle")
        self.toggle_editor_btn.setFixedSize(82, 34)
        self.toggle_editor_btn.setCheckable(True)
        self.toggle_editor_btn.setChecked(True)
        self.toggle_editor_btn.clicked.connect(self.toggle_editor_panel)

        side_wrapper_layout.addWidget(self.side_panel)
        side_wrapper_layout.addWidget(
            self.toggle_editor_btn,
            alignment=Qt.AlignRight
        )
        side_wrapper_layout.addStretch()

        content_layout.addWidget(self.tool_bar)
        content_layout.addWidget(self.map_viewport, 1)
        content_layout.addWidget(self.side_panel_wrapper)

        self.map_viewport.setMinimumWidth(800)

        # ======= INFO BAR FOOTER ======= #

        self.info_bar = QFrame()
        self.info_bar.setObjectName("FlowInfoBar")
        self.info_bar.setFixedHeight(76)

        info_layout = QHBoxLayout(self.info_bar)
        info_layout.setContentsMargins(28, 10, 28, 10)
        info_layout.setSpacing(22)

        self.active_tool_label = QLabel()
        self.active_tool_label.setObjectName("FlowActiveToolLabel")

        self.info_icon = QLabel("i")
        self.info_icon.setObjectName("FlowInfoIcon")
        self.info_icon.setAlignment(Qt.AlignCenter)
        self.info_icon.setFixedSize(34, 34)

        self.info_text = QLabel()
        self.info_text.setObjectName("FlowInfoText")

        self.footer_status_title = QLabel()
        self.footer_status_title.setObjectName("FooterStatusTitle")

        self.footer_completed = QLabel()
        self.footer_completed.setObjectName("FooterStatusCompleted")

        self.footer_active = QLabel()
        self.footer_active.setObjectName("FooterStatusActive")

        self.footer_optional = QLabel()
        self.footer_optional.setObjectName("FooterStatusOptional")

        self.footer_locked = QLabel()
        self.footer_locked.setObjectName("FooterStatusLocked")

        info_layout.addWidget(self.active_tool_label)
        info_layout.addSpacing(18)

        info_layout.addWidget(self.info_icon)
        info_layout.addWidget(self.info_text)
        info_layout.addStretch()
        info_layout.addWidget(self.footer_status_title)
        info_layout.addWidget(self.footer_completed)
        info_layout.addWidget(self.footer_active)
        info_layout.addWidget(self.footer_optional)
        info_layout.addWidget(self.footer_locked)

        root.addWidget(self.topbar)
        root.addWidget(self.content, 1)
        root.addWidget(self.info_bar)

        self.update_active_tool_label()

        self.update_language(language, tr_func)
        self.set_current_tool("select")

    def update_language(self, language, tr_func):
        self.language = language
        self.tr_func = tr_func

        self.setWindowTitle(tr_func(language, "flow_window_title"))
        self.edit_mode_btn.setText(tr_func(language, "flow_edit_mode"))
        self.guide_mode_btn.setText(tr_func(language, "flow_guide_mode"))

        self.info_text.setText(tr_func(language, "flow_info_text"))

        self.editor_panel.update_language(language, tr_func)
        self.footer_status_title.setText(
            tr_func(language, "flow_status_colors") + ":"
        )

        self.footer_completed.setText(
            "● " + tr_func(language, "status_completed_short")
        )

        self.footer_active.setText(
            "● " + tr_func(language, "status_active_short")
        )

        self.footer_optional.setText(
            "● " + tr_func(language, "status_optional_short")
        )

        self.footer_locked.setText(
            "● " + tr_func(language, "status_locked_short")
        )

    def change_zoom(self):
        self.zoom_factor = self.zoom_combo.currentData()
        self.render_flow()


    def toggle_editor_panel(self):
        visible = self.toggle_editor_btn.isChecked()

        self.side_panel.setVisible(visible)

        if visible:
            self.toggle_editor_btn.setText(">>")
            self.side_panel_wrapper.setFixedWidth(390)
        else:
            self.toggle_editor_btn.setText("<<")
            self.side_panel_wrapper.setFixedWidth(82)

    def collapse_editor_panel(self):
        self.toggle_editor_btn.setChecked(False)
        self.toggle_editor_panel()


    def expand_editor_panel(self):
        self.toggle_editor_btn.setChecked(True)
        self.toggle_editor_panel()

    def add_demo_flow(self):
        node1 = FlowNode(
            title="Char erstellen",
            description="Erstelle einen neuen\nCharakter.",
            icon="character",
            status="active",
        )

        node2 = FlowNode(
            title="Level 26 erreichen",
            description="Erreiche mindestens\nLevel 26.",
            icon="level",
            status="locked",
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
                node.id,
                node.title,
                node.description,
                icon=self.get_icon_symbol(node.icon),
                status=node.status,
                zoom=self.zoom_factor,
            )

            card.done_btn.clicked.connect(
                lambda checked=False, node_id=node.id: self.toggle_node_completed(node_id)
            )

            card.mousePressEvent = (
                lambda event, node_id=node.id: self.handle_node_click(node_id)
            )

            connector = FlowConnector(self.zoom_factor)

            if self.current_tool == "add_node":
                connector.setToolTip("Neue Node hinzufügen")

            elif self.current_tool == "branch":
                connector.setToolTip("Beschreibung hinzufügen")

            elif self.current_tool == "delete":
                connector.setToolTip("Branches können nicht gelöscht werden")

            self.map_layout.addWidget(card, alignment=Qt.AlignCenter)



            self.map_layout.addWidget(connector, alignment=Qt.AlignCenter)

            current_id = node.children[0] if node.children else None

    def handle_node_click(self, node_id: str):
        if self.current_tool == "select":
            self.select_node(node_id)
            return

        if self.current_tool == "branch":
            # später: Branch hinzufügen
            self.select_node(node_id)
            return

        if self.current_tool == "delete":
            # später: Delete Dialog
            self.select_node(node_id)
            return

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

        self.expand_editor_panel()
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
        self.mark_unsaved()

    def mark_unsaved(self):
        self.save_status_label.setText("Saving...")
        self.save_status_label.setProperty("state", "saving")
        self.save_status_label.style().unpolish(self.save_status_label)
        self.save_status_label.style().polish(self.save_status_label)

        QTimer.singleShot(2000, self.mark_saved)


    def mark_saved(self):
        self.save_status_label.setText("✓ Saved")
        self.save_status_label.setProperty("state", "saved")
        self.save_status_label.style().unpolish(self.save_status_label)
        self.save_status_label.style().polish(self.save_status_label)

    def closeEvent(self, event):
        self.mark_saved()
        super().closeEvent(event)

    def toggle_node_completed(self, node_id: str):
        node = self.nodes.get(node_id)

        if not node:
            return

        if node.status == "completed":
            node.completed = False
            node.status = "active"

            for child_id in node.children:
                child = self.nodes.get(child_id)
                if child and child.status == "active":
                    child.status = "locked"

        else:
            node.completed = True
            node.status = "completed"

            if node.children:
                next_node = self.nodes.get(node.children[0])

                if next_node and next_node.status != "completed":
                    next_node.status = "active"

        self.render_flow()
        self.mark_unsaved()

    def set_current_tool(self, tool_name: str):
        self.current_tool = tool_name

        self.apply_current_tool_cursor()

        self.update_active_tool_label()

        self.render_flow()

    def update_active_tool_label(self):
        names = {
            "select": "Select",
            "add_node": "Add Node",
            "branch": "Branch",
            "delete": "Delete",
        }

        self.active_tool_label.setText(
            f"Tool: {names.get(self.current_tool, 'Select')}"
        )

    
    def set_tool_cursor(self, filename: str):
        cursor_path = self.flow_tool_icon_dir / filename

        pixmap = QPixmap(str(cursor_path))

        if pixmap.isNull():
            return

        cursor = QCursor(
            pixmap.scaled(
                32,
                32,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            ),
            4,
            4,
        )

        self.map_viewport.setCursor(cursor)

    def apply_current_tool_cursor(self):
        if self.current_tool == "select":
            self.set_tool_cursor("cursor_select.png")

        elif self.current_tool == "add_node":
            self.set_tool_cursor("cursor_addNode.png")

        elif self.current_tool == "branch":
            self.set_tool_cursor("cursor_branch.png")

        elif self.current_tool == "delete":
            self.set_tool_cursor("cursor_delete.png")