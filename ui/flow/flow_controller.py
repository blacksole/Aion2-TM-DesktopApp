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

    def toggle_node_completed(self, node_id: str):
        node = self.window.nodes.get(node_id)

        if not node:
            return

        if node.status == "completed":
            node.completed = False
            node.status = "active"

            for child_id in node.children:
                child = self.window.nodes.get(child_id)

                if child and child.status == "active":
                    child.status = "locked"

        else:
            node.completed = True
            node.status = "completed"

            if node.children:
                next_node = self.window.nodes.get(node.children[0])

                if next_node and next_node.status != "completed":
                    next_node.status = "active"

        self.window.render_flow()
        self.window.mark_unsaved()

    def save_selected_node(self):
        if not self.window.selected_node_id:
            return

        node = self.window.nodes.get(self.window.selected_node_id)

        if not node:
            return

        node.title = self.window.editor_panel.title_input.text().strip()
        node.description = self.window.editor_panel.desc_input.toPlainText().strip()
        node.icon = self.window.editor_panel.symbol_combo.currentData()

        self.window.render_flow()
        self.window.mark_unsaved()

    def handle_connector_click(self, parent_id: str):
        if self.window.current_tool == "add_node":
            self.add_child_node(parent_id)
            return

        if self.window.current_tool == "branch":
            return

        if self.window.current_tool == "delete":
            return