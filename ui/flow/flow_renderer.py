class FlowRenderer:
    def __init__(self, window):
        self.window = window

    def render_flow(self):
        return self.window.render_flow()

    def render_node_branch(self, node_id: str):
        return self.window.render_node_branch(node_id)