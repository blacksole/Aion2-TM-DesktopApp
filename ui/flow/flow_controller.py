class FlowController:
    def __init__(self, window):
        self.window = window

    def handle_node_click(self, node_id: str):
        if self.window.current_tool == "select":
            self.window.select_node(node_id)
            return

        if self.window.current_tool == "add_node":
            self.window.add_child_node(node_id)
            return

        if self.window.current_tool == "branch":
            self.window.add_branch_node(node_id)
            return

        if self.window.current_tool == "delete":
            self.window.select_node(node_id)
            return