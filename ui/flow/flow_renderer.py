class FlowRenderer:
    def __init__(self, window):
        self.window = window

    def render_flow(self):
        self.window.clear_map_layout()
        self.window.connectors = []

        if not self.window.root_node_id:
            return

        branch_widget = self.window.render_node_branch(
            self.window.root_node_id
        )

        self.window.map_layout.addWidget(
            branch_widget,
            alignment=self.window.qt_align_top_center()
        )

        self.window.map_area.adjustSize()
        self.window.schedule_center_flow()