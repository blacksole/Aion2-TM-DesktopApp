from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QButtonGroup,
    QComboBox,
)
from PySide6.QtCore import Qt, QSize, QTimer, Signal
from PySide6.QtGui import QPixmap, QIcon, QCursor

from core.flow_model import FlowNode


from ui.flow.flow_debug import (
    update_mouse_position_debug_label
)

from ui.flow.widgets.flow_canvas import FlowCanvas
from ui.flow.widgets.flow_viewport import FlowMapViewport
from ui.flow.widgets.flow_node_card import FlowNodeCard
from ui.flow.widgets.flow_map_area import FlowMapArea
from ui.flow.widgets.node_editor_panel import NodeEditorPanel
from ui.flow.widgets.flow_guide_view import FlowGuideView
from ui.flow.flow_layout import NODE_WIDTH, NODE_HEIGHT
from ui.flow.flow_renderer import FlowRenderer
from ui.flow.flow_controller import FlowController

class FlowMapWindow(QMainWindow):
    map_switch_requested = Signal(str)
    map_add_requested = Signal()
    map_delete_requested = Signal()
    map_reset_requested = Signal()

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

        self.nodes: dict[str, FlowNode] = {}
        self.root_node_id = None
        self.selected_node_id = None
        self.zoom_factor = 1.0
        self.current_tool = "select"
        self.current_mode = "edit"

        self.renderer = FlowRenderer(self)
        self.controller = FlowController(self)

        self.map_name_combo = QComboBox()
        self.map_name_combo.setObjectName("FlowMapCombo")
        self.map_name_combo.setMinimumWidth(160)
        self.map_name_combo.addItem("Map 1")
        self.map_name_combo.currentTextChanged.connect(self._on_map_combo_changed)

        self.new_map_btn = QPushButton("+")
        self.new_map_btn.setObjectName("FlowNewMapBtn")
        self.new_map_btn.setFixedSize(34, 34)
        self.new_map_btn.setToolTip("Neue Map erstellen")
        self.new_map_btn.clicked.connect(self.map_add_requested.emit)

        self.delete_map_btn = QPushButton("🗑")
        self.delete_map_btn.setObjectName("FlowDeleteMapBtn")
        self.delete_map_btn.setFixedSize(34, 34)
        self.delete_map_btn.setToolTip("Aktuelle Map löschen")
        self.delete_map_btn.clicked.connect(lambda: self.map_delete_requested.emit())

        self.edit_mode_btn = QPushButton()
        self.edit_mode_btn.setObjectName("FlowModeButton")
        self.edit_mode_btn.setCheckable(True)
        self.edit_mode_btn.setChecked(True)

        self.guide_mode_btn = QPushButton()
        self.guide_mode_btn.setObjectName("FlowModeButton")
        self.guide_mode_btn.setCheckable(True)

        self.zoom_hint_label = QLabel("Scroll | Zoom 100%")
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

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.edit_mode_btn)
        self.mode_group.addButton(self.guide_mode_btn)

        self.edit_mode_btn.clicked.connect(lambda: self.set_mode("edit"))
        self.guide_mode_btn.clicked.connect(lambda: self.set_mode("guide"))

        map_selector_row = QHBoxLayout()
        map_selector_row.setSpacing(6)
        map_selector_row.addWidget(self.map_name_combo)
        map_selector_row.addWidget(self.new_map_btn)
        map_selector_row.addWidget(self.delete_map_btn)
        top_layout.addLayout(map_selector_row)

        top_layout.addStretch()
        top_layout.addWidget(self.mode_tabs)
        top_layout.addStretch()

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

        self.home_btn = QPushButton()
        self.home_btn.setIcon(QIcon(str(self.flow_icon_dir / "home_icon.png")))
        self.home_btn.setIconSize(QSize(28, 28))
        self.home_btn.setObjectName("FlowHomeBtn")
        self.home_btn.setToolTip("Go to Root")
        tool_layout.addWidget(self.home_btn)
        self.home_btn.clicked.connect(self.center_flow_in_viewport)

        separator = QFrame()
        separator.setObjectName("FlowToolSeparator")
        separator.setFrameShape(QFrame.HLine)
        separator.setFixedHeight(1)
        tool_layout.addWidget(separator)

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

        sep_bottom = QFrame()
        sep_bottom.setObjectName("FlowToolSeparator")
        sep_bottom.setFrameShape(QFrame.HLine)
        sep_bottom.setFixedHeight(1)
        tool_layout.addWidget(sep_bottom)

        self.reset_map_btn = QPushButton("↺")
        self.reset_map_btn.setObjectName("FlowResetMapBtn")
        self.reset_map_btn.setFixedSize(44, 44)
        self.reset_map_btn.setToolTip("Map zurücksetzen")
        self.reset_map_btn.clicked.connect(self.map_reset_requested.emit)
        tool_layout.addWidget(self.reset_map_btn)

        self.map_viewport = FlowMapViewport(self)
        self.map_viewport.setMouseTracking(True)
        
        self.map_viewport.setParent(self.content)

        self.map_area = FlowMapArea(self, self.map_viewport)
        self.map_area.move(20, 0)
        self.map_viewport.set_pan_target(self.map_area)
        self.node_cards: dict = {}



        self.add_demo_flow()

        self.current_mode = "edit"

        self.guide_view = FlowGuideView(self)
        self.guide_view.setParent(self.content)
        self.guide_view.hide()

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

        self.editor_panel.node_cancel_btn.clicked.connect(
            self.cancel_selected_node
        )

        self.editor_panel.close_btn.clicked.connect(
            self.cancel_selected_node
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

        self.side_panel_wrapper.setVisible(False)

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

        # Tooltips
        self.new_map_btn.setToolTip(tr_func(language, "flow_tooltip_new_map"))
        self.delete_map_btn.setToolTip(tr_func(language, "flow_tooltip_delete_map"))
        self.reset_map_btn.setToolTip(tr_func(language, "flow_tooltip_reset_map"))
        self.home_btn.setToolTip(tr_func(language, "flow_tooltip_home"))
        self.select_tool_btn.setToolTip(tr_func(language, "flow_tooltip_select"))
        self.add_node_tool_btn.setToolTip(tr_func(language, "flow_tooltip_add_node"))
        self.branch_tool_btn.setToolTip(tr_func(language, "flow_tooltip_branch"))
        self.delete_tool_btn.setToolTip(tr_func(language, "flow_tooltip_delete"))

        # Save status + zoom
        self.save_status_label.setText(tr_func(language, "flow_saved"))
        self.zoom_hint_label.setText(
            tr_func(language, "flow_zoom_hint", pct=int(self.zoom_factor * 100))
        )

        self.update_active_tool_label()

    def adjust_zoom(self, delta: float, mouse_pos=None):
        old_zoom = self.zoom_factor
        new_zoom = max(0.6, min(1.0, old_zoom + delta))

        if new_zoom == old_zoom:
            return

        old_map_x = self.map_area.x()
        old_map_y = self.map_area.y()

        self.zoom_factor = new_zoom
        self.zoom_hint_label.setText(
            self.tr_func(self.language, "flow_zoom_hint", pct=int(self.zoom_factor * 100))
        )
        self.render_flow()

        if mouse_pos is not None:
            mx = mouse_pos.x()
            my = mouse_pos.y()
            content_x = (mx - old_map_x) / old_zoom
            content_y = (my - old_map_y) / old_zoom
            self.map_area.move(
                int(mx - content_x * new_zoom),
                int(my - content_y * new_zoom),
            )

    def get_flow_data(self) -> dict:
        return {
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "root_node_id": self.root_node_id,
        }

    def load_flow_data(self, data: dict):
        if not data:
            return
        from core.flow_model import FlowNode
        raw_nodes = data.get("nodes", {})
        self.nodes = {nid: FlowNode.from_dict(nd) for nid, nd in raw_nodes.items()}
        self.root_node_id = data.get("root_node_id")
        self.selected_node_id = None
        self.renderer._first_render = True
        if self.isVisible():
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

    def close_editor_panel(self):
        self.side_panel_wrapper.setVisible(False)

    def expand_editor_panel(self):
        self.side_panel_wrapper.setVisible(True)
        self.toggle_editor_btn.setChecked(True)
        self.toggle_editor_panel()

    def add_demo_flow(self):
        node1 = FlowNode(
            title="Char erstellen",
            description="Erstelle einen neuen\nCharakter.",
            icon="character",
            status="active",
        )

        self.nodes = {
            node1.id: node1,
        }

        self.root_node_id = node1.id
        self.render_flow()


    def clear_node_cards(self):
        for card in self.node_cards.values():
            card.deleteLater()
        self.node_cards = {}


    def set_mode(self, mode: str):
        if mode == self.current_mode:
            return

        if not self.controller.confirm_dirty_before_action():
            self._revert_mode_buttons()
            return

        self.current_mode = mode

        is_edit = mode == "edit"

        self.tool_bar.setVisible(is_edit)
        self.side_panel_wrapper.setVisible(is_edit and self.selected_node_id is not None)
        self.map_viewport.setVisible(is_edit)
        self.guide_view.setVisible(not is_edit)

        if not is_edit:
            self.current_tool = "select"
            self.select_tool_btn.setChecked(True)
            self.guide_view.refresh()
        else:
            self.render_flow()

        self.position_flow_overlays()

    def _revert_mode_buttons(self):
        for btn in (self.edit_mode_btn, self.guide_mode_btn):
            btn.blockSignals(True)
        self.edit_mode_btn.setChecked(self.current_mode == "edit")
        self.guide_mode_btn.setChecked(self.current_mode == "guide")
        for btn in (self.edit_mode_btn, self.guide_mode_btn):
            btn.blockSignals(False)

    def render_flow(self):
        if self.current_mode == "guide":
            if hasattr(self, "guide_view"):
                self.guide_view.refresh()
            return
        self.renderer.render_flow()

    def center_flow_in_viewport(self):
        if not self.root_node_id or not self.nodes:
            return

        root = self.nodes.get(self.root_node_id)
        if not root:
            return

        zoom = self.zoom_factor
        card_center_x = root.x * zoom + NODE_WIDTH * zoom / 2
        card_center_y = root.y * zoom + NODE_HEIGHT * zoom / 2

        viewport_center = self.map_viewport.rect().center()

        new_x = viewport_center.x() - card_center_x
        new_y = viewport_center.y() - card_center_y

        self.map_area.move(int(new_x), int(new_y))

    def render_node_branch(self, node_id: str):
        pass

    def handle_node_click(self, node_id: str):
        self.controller.handle_node_click(node_id)

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
        self.controller.add_child_node(parent_id)

    def add_branch_node(self, parent_id: str):
        self.controller.add_branch_node(parent_id)

    def delete_node(self, node_id: str):
        self.controller.delete_node(node_id)

    def cancel_selected_node(self):
        self.controller.cancel_selected_node()

    def select_node(self, node_id: str):
        self.controller.select_node(node_id)


    def load_node_into_editor(self, node_id: str):
        self.controller.load_node_into_editor(node_id)

    def save_selected_node(self):
        self.controller.save_selected_node()

    def mark_unsaved(self):
        self.save_status_label.setText(self.tr_func(self.language, "flow_saving"))
        self.save_status_label.setProperty("state", "saving")
        self.save_status_label.style().unpolish(self.save_status_label)
        self.save_status_label.style().polish(self.save_status_label)

        main = self.parent()
        if main and hasattr(main, "save_profile"):
            main.save_profile(silent=True)

        QTimer.singleShot(2000, self.mark_saved)


    def mark_saved(self):
        self.save_status_label.setText(self.tr_func(self.language, "flow_saved"))
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
        self.controller.toggle_node_completed(node_id)

    def set_current_tool(self, tool_name: str):
        self.current_tool = tool_name

        self.apply_current_tool_cursor()
        self.update_active_tool_label()

        self.render_flow()

    def update_active_tool_label(self):
        if not self.tr_func:
            return
        tool_key_map = {
            "select":   "flow_tooltip_select",
            "add_node": "flow_tooltip_add_node",
            "branch":   "flow_tooltip_branch",
            "delete":   "flow_tooltip_delete",
        }
        tr_key = tool_key_map.get(self.current_tool, "flow_tooltip_select")
        prefix = self.tr_func(self.language, "flow_tool_prefix")
        name   = self.tr_func(self.language, tr_key)
        self.active_tool_label.setText(f"{prefix} {name}")

    
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
        self.controller.handle_connector_click(parent_id)
        
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
            max(8000, content_size.width() * 5),
            max(8000, content_size.height() * 8)
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

        if hasattr(self, "guide_view"):
            self.guide_view.setGeometry(
                0, 0,
                content_size.width(),
                content_size.height(),
            )

        self.tool_bar.raise_()
        self.side_panel_wrapper.raise_()



    # ========== DEBUG Funktionen ========== #
    def update_mouse_position_debug(self, pos, source_widget):
        update_mouse_position_debug_label(self, pos, source_widget)
        


    
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

        drag_state = {"dragging": False, "start_global": None, "start_node": (0.0, 0.0)}

        def on_press(event, n=node, c=card):
            if event.button() != Qt.LeftButton:
                return
            drag_state["dragging"] = False
            drag_state["start_global"] = event.globalPosition().toPoint()
            drag_state["start_node"] = (n.x, n.y)
            if self.current_tool != "select":
                self.handle_node_click(n.id)

        def on_move(event, n=node, c=card):
            if not (event.buttons() & Qt.LeftButton):
                return
            if self.current_tool != "select" or drag_state["start_global"] is None:
                return
            delta = event.globalPosition().toPoint() - drag_state["start_global"]
            if not drag_state["dragging"]:
                if abs(delta.x()) > 5 or abs(delta.y()) > 5:
                    drag_state["dragging"] = True
            if drag_state["dragging"]:
                sx, sy = drag_state["start_node"]
                n.x = sx + delta.x() / self.zoom_factor
                n.y = sy + delta.y() / self.zoom_factor
                c.move(int(n.x * self.zoom_factor), int(n.y * self.zoom_factor))
                self.map_area.update()

        def on_release(event, n=node):
            if event.button() != Qt.LeftButton:
                return
            if self.current_tool == "select" and not drag_state["dragging"]:
                self.handle_node_click(n.id)
            if drag_state["dragging"]:
                self.mark_unsaved()
            drag_state["dragging"] = False
            drag_state["start_global"] = None

        card.mousePressEvent = on_press
        card.mouseMoveEvent = on_move
        card.mouseReleaseEvent = on_release

        return card
    
    def qt_align_top_center(self):
        return Qt.AlignTop | Qt.AlignHCenter


    def schedule_center_flow(self):
        QTimer.singleShot(0, self.center_flow_in_viewport)

    def set_map_list(self, names: list, active_name: str):
        self.map_name_combo.blockSignals(True)
        self.map_name_combo.clear()
        for name in names:
            self.map_name_combo.addItem(name)
        idx = self.map_name_combo.findText(active_name)
        self.map_name_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.map_name_combo.blockSignals(False)

    def _on_map_combo_changed(self, text: str):
        if text:
            self.map_switch_requested.emit(text)