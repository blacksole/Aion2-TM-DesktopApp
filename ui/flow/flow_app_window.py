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
    QPixmap, 
    QIcon,
    QCursor,
)
from pathlib import Path
from core.flow_model import FlowNode

from ui.flow.flow_layout import NODE_WIDTH
from ui.flow.widgets.flow_canvas import FlowCanvas
from ui.flow.widgets.flow_viewport import FlowMapViewport
from ui.flow.widgets.flow_node_card import FlowNodeCard
from ui.flow.widgets.flow_point_connector import FlowPointConnector
from ui.flow.widgets.node_editor_panel import NodeEditorPanel

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

        self.zoom_hint_label = QLabel("Ctrl + Wheel | Zoom 100%")
        self.zoom_hint_label.setObjectName("FlowZoomHintLabel")

        

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
        top_layout.addWidget(self.zoom_hint_label)
        top_layout.setSpacing(10)
        top_layout.addWidget(self.save_status_label)

        self.content = QWidget()
        self.content.setObjectName("FlowContentOverlay")
        content_overlay_layout = QVBoxLayout(self.content)
        content_overlay_layout.setContentsMargins(0, 0, 0, 0)
        content_overlay_layout.setSpacing(0)

        # ====== TOOLBAR & MAP AREA ======= #

        self.tool_bar = QFrame()
        self.tool_bar.setObjectName("FlowToolBar")
        self.tool_bar.setFixedWidth(64)
        self.tool_bar.setParent(self.content)

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
        self.map_viewport.setMouseTracking(True)
        
        self.map_viewport.setParent(self.content)

        self.map_area = QWidget(self.map_viewport)
        self.map_area.resize(3000, 3000)
        self.map_area.move(20, 0)

        self.map_area.setMouseTracking(True)

        self.map_viewport.set_pan_target(self.map_area)

        self.map_layout = QVBoxLayout(self.map_area)
        self.map_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.map_layout.setSpacing(0)



        self.add_demo_flow()

        self.side_panel_wrapper = QWidget()
        self.side_panel_wrapper.setParent(self.content)
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

        self.mouse_debug_label = QLabel("Mouse: -")
        self.mouse_debug_label.setObjectName("FlowMouseDebugLabel")

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
        info_layout.addWidget(self.mouse_debug_label)
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

        self.content.installEventFilter(self)
        QTimer.singleShot(0, self.position_flow_overlays)

        self.update_active_tool_label()

        self.update_language(language, tr_func)
        self.set_current_tool("select")

        self.position_flow_overlays()

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
        self.zoom_hint_label.setText(
            f"Ctrl + Wheel | Zoom {int(self.zoom_factor * 100)}%"
        )
        self.render_flow()

    def adjust_zoom(self, delta: float):
        new_zoom = self.zoom_factor + delta
        new_zoom = max(0.4, min(1.4, new_zoom))

        self.zoom_factor = new_zoom

        self.zoom_hint_label.setText(
            f"Ctrl + Wheel | Zoom {int(self.zoom_factor * 100)}%"
        )

        self.render_flow()


    def toggle_editor_panel(self):
        visible = self.toggle_editor_btn.isChecked()

        self.side_panel.setVisible(visible)

        if visible:
            self.toggle_editor_btn.setText(">>")
        else:
            self.toggle_editor_btn.setText("<<")
        self.side_panel_wrapper.setFixedWidth(390)

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
        self.connectors = []

        if not self.root_node_id:
            return

        branch_widget = self.render_node_branch(self.root_node_id)

        self.map_layout.addWidget(
            branch_widget,
            alignment=Qt.AlignTop | Qt.AlignHCenter
        )

        self.map_area.adjustSize()
        QTimer.singleShot(0, self.center_flow_in_viewport)

    def center_flow_in_viewport(self):
        if self.map_layout.count() == 0:
            return

        flow_widget = self.map_layout.itemAt(0).widget()

        if not flow_widget:
            return

        self.map_area.adjustSize()
        flow_widget.adjustSize()

        flow_center = flow_widget.geometry().center()
        viewport_center = self.map_viewport.rect().center()

        new_x = viewport_center.x() - flow_center.x()
        new_y = viewport_center.y() - flow_center.y()

        self.map_area.move(new_x, new_y)

    def render_node_branch(self, node_id: str):
        node = self.nodes.get(node_id)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        if not node:
            return container

        
        
        layout_data = self.calculate_branch_layout(node)

        branch_spacing = layout_data["branch_spacing"]
        node_width = layout_data["node_width"]
        child_count = layout_data["child_count"]
        child_widths = layout_data["child_widths"]
        required_width = layout_data["required_width"]

        container.setMinimumWidth(required_width)

        card = self.create_node_card(node)
        card_wrapper = self.create_card_wrapper(card, required_width)
        layout.addWidget(card_wrapper, alignment=Qt.AlignCenter)

        if child_count == 0:
            return container

        connections = self.build_connections(
            child_count=child_count,
            child_widths=child_widths,
            branch_spacing=branch_spacing,
            node_width=node_width,
            required_width=required_width,
        )

        connector = self.create_connector(
            connections=connections,
            child_count=child_count,
            required_width=required_width,
        )

        layout.addWidget(connector, alignment=Qt.AlignCenter)

        branch_row = self.create_children_row(
            node=node,
            child_widths=child_widths,
            branch_spacing=branch_spacing,
        )

        layout.addLayout(branch_row)

        return container

    def handle_node_click(self, node_id: str):
        if self.current_tool == "select":
            self.select_node(node_id)
            return

        if self.current_tool == "add_node":
            self.add_child_node(node_id)
            return

        if self.current_tool == "branch":
            self.add_branch_node(node_id)
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

        old_children = parent_node.children.copy()

        new_node = FlowNode(
            title="Neue Kachel",
            description="Beschreibung hinzufügen.",
            icon="level",
            status="locked",
        )

        # Neue Node wird direkt nach Parent eingefügt
        parent_node.children = [new_node.id]

        # Alte Nachfolger hängen nun an der neuen Node
        new_node.children = old_children

        self.nodes[new_node.id] = new_node
        self.selected_node_id = new_node.id

        self.render_flow()
        self.expand_editor_panel()
        self.load_node_into_editor(new_node.id)
        self.mark_unsaved()

    def add_branch_node(self, parent_id: str):
        parent_node = self.nodes.get(parent_id)

        if not parent_node:
            return

        new_node = FlowNode(
            title="Neuer Branch",
            description="Beschreibung hinzufügen.",
            icon="level",
            status="locked",
        )

        parent_node.children.append(new_node.id)
        print(f"Branch added to {parent_node.title}")
        print(f"Children now: {parent_node.children}")

        self.nodes[new_node.id] = new_node
        self.selected_node_id = new_node.id

        self.render_flow()
        self.expand_editor_panel()
        self.load_node_into_editor(new_node.id)
        self.mark_unsaved()



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

        index = self.editor_panel.symbol_combo.findData(node.icon)

        if index >= 0:
            self.editor_panel.symbol_combo.setCurrentIndex(index)

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_flow_overlays()

    def eventFilter(self, obj, event):
        if obj == self.content and event.type() == event.Type.Resize:
            QTimer.singleShot(0, self.position_flow_overlays)

        return super().eventFilter(obj, event)

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


    def handle_connector_click(self, parent_id: str):
        if self.current_tool == "add_node":
            self.add_child_node(parent_id)
            return

        if self.current_tool == "branch":
            # später: Beschreibung am Connector bearbeiten
            return

        if self.current_tool == "delete":
            # Branches / Connectoren werden nicht gelöscht
            return
        
    def position_flow_overlays(self):
        if not hasattr(self, "content"):
            return

        content_size = self.content.size()

        if content_size.width() <= 0 or content_size.height() <= 0:
            return

        self.map_viewport.setGeometry(
            0,
            0,
            content_size.width(),
            content_size.height()
        )

        self.map_viewport.lower()

        self.map_area.resize(
            max(5000, content_size.width() * 3),
            max(5000, content_size.height() * 3)
        )

        margin = 18

        self.tool_bar.move(margin, margin)
        self.tool_bar.setFixedHeight(content_size.height() - margin * 2)

        panel_width = 390
        self.side_panel_wrapper.setFixedWidth(panel_width)

        self.side_panel_wrapper.move(
            content_size.width() - panel_width - margin,
            margin
        )

        self.side_panel_wrapper.setFixedHeight(
            content_size.height() - margin * 2
        )

        self.tool_bar.raise_()
        self.side_panel_wrapper.raise_()



    # ========== DEBUG Funktionen ========== #
    def update_mouse_position_debug(self, pos, source_widget):
        global_pos = source_widget.mapToGlobal(pos)
        content_pos = self.content.mapFromGlobal(global_pos)
        map_pos = self.map_area.mapFromGlobal(global_pos)

        viewport_center = self.map_viewport.rect().center()
        map_area_pos = self.map_area.pos()

        node_center_text = "Nodes Center: -"

        if self.map_layout.count() > 0:
            flow_widget = self.map_layout.itemAt(0).widget()

            if flow_widget:
                flow_center = flow_widget.geometry().center()

                node_center_global = self.map_area.mapToGlobal(flow_center)
                node_center_viewport = self.map_viewport.mapFromGlobal(node_center_global)

                node_center_text = (
                    f"Nodes Center Map: {flow_center.x()}, {flow_center.y()} "
                    f"| Nodes Center Viewport: {node_center_viewport.x()}, {node_center_viewport.y()}"
                )

        self.mouse_debug_label.setText(
            f"Mouse | Content: {content_pos.x()}, {content_pos.y()} "
            f"| Map: {map_pos.x()}, {map_pos.y()} "
            f"| Viewport Center: {viewport_center.x()}, {viewport_center.y()} "
            f"| MapArea Pos: {map_area_pos.x()}, {map_area_pos.y()} "
            f"| {node_center_text}"
        )

    def calculate_parent_anchor_x(self, index: int, count: int, width: int) -> float:
        center = width / 2

        if count <= 1:
            return center

        # kleiner Wert = Punkte enger zusammen
        anchor_spread = width * 0.18

        start_x = center - anchor_spread / 2
        step = anchor_spread / (count - 1)

        return start_x + step * index
    
    def calculate_subtree_width(self, node_id: str) -> int:
        node = self.nodes.get(node_id)

        if not node or not node.children:
            return int(NODE_WIDTH * self.zoom_factor)

        child_count = len(node.children)
        branch_spacing = 90

        child_widths = [
            self.calculate_subtree_width(child_id)
            for child_id in node.children
        ]

        children_total_width = (
            sum(child_widths)
            + (child_count - 1) * branch_spacing
        )

        return max(
            int(NODE_WIDTH * self.zoom_factor),
            children_total_width
        )
    
    def calculate_branch_layout(self, node):
        branch_spacing = 90
        node_width = int(NODE_WIDTH * self.zoom_factor)
        child_count = len(node.children)

        if child_count > 0:
            child_widths = [
                self.calculate_subtree_width(child_id)
                for child_id in node.children
            ]

            required_width = (
                sum(child_widths)
                + (child_count - 1) * branch_spacing
            )

            required_width = max(required_width, node_width)
        else:
            child_widths = []
            required_width = node_width

        return {
            "branch_spacing": branch_spacing,
            "node_width": node_width,
            "child_count": child_count,
            "child_widths": child_widths,
            "required_width": required_width,
        }
    
    def create_node_card(self, node):
        card = FlowNodeCard(
            node.id,
            node.title,
            node.description,
            icon=self.get_icon_symbol(node.icon),
            status=node.status,
            zoom=self.zoom_factor,
            parent_window=self,
        )

        card.add_node_hint_btn.clicked.connect(
            lambda checked=False, parent_id=node.id: self.add_child_node(parent_id)
        )

        card.done_btn.clicked.connect(
            lambda checked=False, node_id=node.id: self.toggle_node_completed(node_id)
        )

        card.mousePressEvent = (
            lambda event, node_id=node.id: self.handle_node_click(node_id)
        )

        return card
    
    def create_card_wrapper(self, card, required_width):
        card_wrapper = QWidget()
        card_wrapper.setFixedWidth(required_width)

        card_layout = QHBoxLayout(card_wrapper)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        card_layout.addWidget(card, alignment=Qt.AlignHCenter)

        return card_wrapper
    
    def build_connections(
        self,
        child_count,
        child_widths,
        branch_spacing,
        node_width,
        required_width,
    ):
        connections = []

        for index in range(child_count):
            parent_anchor_x = self.calculate_parent_anchor_x(
                index=index,
                count=child_count,
                width=node_width,
            )

            parent_offset_x = (required_width - node_width) / 2
            start_x = parent_offset_x + parent_anchor_x

            child_x = sum(child_widths[:index]) + index * branch_spacing
            child_top_center_x = child_x + child_widths[index] / 2

            connections.append((start_x, child_top_center_x))

        return connections
    
    def create_connector(self, connections, child_count, required_width):
        base_connector_height = 70
        extra_per_child = 14

        connector_height = (
            base_connector_height
            + int(self.zoom_factor * child_count * extra_per_child)
        )

        connector = FlowPointConnector(
            connections=connections,
            zoom=self.zoom_factor,
            height=connector_height,
            parent_window=self,
        )

        connector.setFixedWidth(required_width)

        return connector
    
    def create_children_row(self, node, child_widths, branch_spacing):
        branch_row = QHBoxLayout()
        branch_row.setContentsMargins(0, 0, 0, 0)
        branch_row.setSpacing(branch_spacing)
        branch_row.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        for index, child_id in enumerate(node.children):
            child_widget = self.render_node_branch(child_id)
            child_widget.setFixedWidth(child_widths[index])

            branch_row.addWidget(
                child_widget,
                alignment=Qt.AlignTop | Qt.AlignHCenter
            )

        return branch_row