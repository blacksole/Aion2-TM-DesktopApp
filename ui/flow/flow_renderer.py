from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from ui.flow.widgets.flow_point_connector import FlowPointConnector

from ui.flow.flow_layout import (
    calculate_branch_layout,
    build_connections,
    calculate_connector_height,
)



class FlowRenderer:
    def __init__(self, window):
        self.window = window

    def render_flow(self):
        self.window.clear_map_layout()
        self.window.connectors = []

        if not self.window.root_node_id:
            return

        branch_widget = self.render_node_branch(
            self.window.root_node_id
        )

        self.window.map_layout.addWidget(
            branch_widget,
            alignment=self.window.qt_align_top_center()
        )

        self.window.map_area.adjustSize()
        self.window.schedule_center_flow()

    def render_node_branch(self, node_id: str):
        node = self.window.nodes.get(node_id)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        if not node:
            return container

        layout_data = calculate_branch_layout(
            node,
            self.window.nodes,
            self.window.zoom_factor
        )

        branch_spacing = layout_data["branch_spacing"]
        node_width = layout_data["node_width"]
        child_count = layout_data["child_count"]
        child_widths = layout_data["child_widths"]
        required_width = layout_data["required_width"]

        container.setMinimumWidth(required_width)

        card = self.window.create_node_card(node)
        card_wrapper = self.window.create_card_wrapper(card, required_width)

        layout.addWidget(card_wrapper, alignment=Qt.AlignCenter)

        if child_count == 0:
            return container

        connections = build_connections(
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

        branch_row = self.window.create_children_row(
            node=node,
            child_widths=child_widths,
            branch_spacing=branch_spacing,
        )

        layout.addLayout(branch_row)

        return container
    
    def create_connector(self, connections, child_count, required_width):
        connector_height = calculate_connector_height(
            child_count,
            self.window.zoom_factor
        )

        connector = FlowPointConnector(
            connections=connections,
            zoom=self.window.zoom_factor,
            height=connector_height,
            parent_window=self.window,
        )

        connector.setFixedWidth(required_width)

        return connector