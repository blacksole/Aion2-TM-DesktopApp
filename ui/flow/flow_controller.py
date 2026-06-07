from core.flow_model import FlowNode

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
        
    def add_child_node(self, parent_id: str):
        parent_node = self.window.nodes.get(parent_id)

        if not parent_node:
            return

        old_children = parent_node.children.copy()

        new_node = FlowNode(
            title="Neue Kachel",
            description="Beschreibung hinzufügen.",
            icon="level",
            status="locked",
        )

        parent_node.children = [new_node.id]
        new_node.children = old_children

        self.window.nodes[new_node.id] = new_node
        self.window.selected_node_id = new_node.id

        self.window.render_flow()
        self.window.expand_editor_panel()
        self.window.load_node_into_editor(new_node.id)
        self.window.mark_unsaved()

    def add_branch_node(self, parent_id: str):
        parent_node = self.window.nodes.get(parent_id)

        if not parent_node:
            return

        new_node = FlowNode(
            title="Neuer Branch",
            description="Beschreibung hinzufügen.",
            icon="level",
            status="locked",
        )

        parent_node.children.append(new_node.id)

        self.window.nodes[new_node.id] = new_node
        self.window.selected_node_id = new_node.id

        self.window.render_flow()
        self.window.expand_editor_panel()
        self.window.load_node_into_editor(new_node.id)
        self.window.mark_unsaved()

    def select_node(self, node_id: str):
        self.window.selected_node_id = node_id

        self.window.expand_editor_panel()
        self.window.load_node_into_editor(node_id)