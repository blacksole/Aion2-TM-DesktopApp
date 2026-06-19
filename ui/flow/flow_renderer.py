from ui.flow.flow_layout import compute_node_positions, NODE_WIDTH


class FlowRenderer:
    def __init__(self, window):
        self.window = window
        self._first_render = True

    def render_flow(self):
        self.window.clear_node_cards()
        self.window.connectors = []

        if not self.window.root_node_id:
            return

        root = self.window.nodes.get(self.window.root_node_id)
        if root and (root.x != 0 or root.y != 0):
            origin_x = root.x + NODE_WIDTH / 2
            origin_y = root.y
        else:
            origin_x = 4000.0
            origin_y = 4000.0

        auto = compute_node_positions(
            self.window.root_node_id, self.window.nodes, origin_x, origin_y
        )
        for node_id, (ax, ay) in auto.items():
            node = self.window.nodes.get(node_id)
            if node and node.x == 0 and node.y == 0:
                node.x = ax
                node.y = ay

        zoom = self.window.zoom_factor
        for node_id, node in self.window.nodes.items():
            card = self.window.create_node_card(node)
            card.setParent(self.window.map_area)
            card.move(int(node.x * zoom), int(node.y * zoom))
            card.show()
            self.window.node_cards[node_id] = card

        self.window.map_area.update()
        if self._first_render:
            self._first_render = False
            self.window.schedule_center_flow()
