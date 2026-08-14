from PySide6.QtWidgets import QMessageBox

from core.flow_model import FlowNode
from ui.flow.flow_layout import find_free_child_position
from ui.flow.widgets.delete_confirm_dialog import DeleteConfirmDialog, UnsavedChangesDialog


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
            self.delete_node(node_id)
            return
        
    def _tr(self, key: str) -> str:
        if self.window.tr_func:
            return self.window.tr_func(self.window.language, key)
        return key

    def add_child_node(self, parent_id: str):
        parent_node = self.window.nodes.get(parent_id)

        if not parent_node:
            return

        old_children = parent_node.children.copy()

        new_node = FlowNode(
            title=self._tr("flow_new_node_title"),
            description=self._tr("flow_new_node_desc"),
            icon="level",
            status="locked",
        )

        parent_node.children = [new_node.id]
        new_node.children = old_children

        self.window.nodes[new_node.id] = new_node

        pos = find_free_child_position(parent_id, self.window.nodes)
        if pos:
            new_node.x, new_node.y = pos

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
            title=self._tr("flow_new_branch_title"),
            description=self._tr("flow_new_node_desc"),
            icon="level",
            status="locked",
        )

        parent_node.children.append(new_node.id)

        self.window.nodes[new_node.id] = new_node

        pos = find_free_child_position(parent_id, self.window.nodes)
        if pos:
            new_node.x, new_node.y = pos

        self.window.selected_node_id = new_node.id

        self.window.render_flow()
        self.window.expand_editor_panel()
        self.window.load_node_into_editor(new_node.id)
        self.window.mark_unsaved()

    def select_node(self, node_id: str):
        if node_id == self.window.selected_node_id:
            return

        if not self.confirm_dirty_before_action():
            return

        self.window.selected_node_id = node_id
        self.window.expand_editor_panel()
        self.window.load_node_into_editor(node_id)

    def _editor_is_dirty(self) -> bool:
        return (
            self.window.side_panel_wrapper.isVisible()
            and self.window.editor_panel.is_dirty
        )

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

            for child_id in node.children:
                child = self.window.nodes.get(child_id)
                if child and child.status not in ("completed", "optional"):
                    child.status = "active"

        self.window.render_flow()
        self.window.mark_unsaved()

    def save_selected_node(self):
        if not self.window.selected_node_id:
            return

        node = self.window.nodes.get(self.window.selected_node_id)

        if not node:
            return

        panel = self.window.editor_panel
        new_icon = panel.symbol_combo.currentData()

        # Validate character icon placement
        if new_icon == "character" and self.window.selected_node_id != self.window.root_node_id:
            parent_id = self._find_parent_id(self.window.selected_node_id)
            if parent_id != self.window.root_node_id:
                _msg = {
                    "de": ("Nicht erlaubt", "Charakter-Nodes können nur direkt unter dem Root-Node erstellt werden."),
                    "ru": ("Запрещено", "Узлы персонажа можно размещать только сразу под корневым узлом."),
                }.get(self.window.language, ("Not allowed", "Character nodes can only be placed directly under the root node."))
                QMessageBox.warning(self.window, _msg[0], _msg[1])
                return

            root = self.window.nodes.get(self.window.root_node_id)
            if root:
                char_count = sum(
                    1 for cid in root.children
                    if cid != self.window.selected_node_id
                    and self.window.nodes.get(cid) and self.window.nodes[cid].icon == "character"
                )
                if char_count >= 8:
                    _msg = {
                        "de": ("Limit erreicht", "Maximal 8 Charakter-Nodes erlaubt."),
                        "ru": ("Лимит достигнут", "Допускается не более 8 узлов персонажа."),
                    }.get(self.window.language, ("Limit reached", "Maximum 8 character nodes allowed."))
                    QMessageBox.warning(self.window, _msg[0], _msg[1])
                    return

        old_title = node.title
        node.title = panel.title_input.text().strip() or old_title
        node.description = panel.desc_input.toPlainText().strip()
        node.icon = new_icon

        if node.icon == "character":
            node.character_items = panel.get_character_items()
            main = self.window.parent()
            if main and hasattr(main, "_sync_character_items_to_shopping"):
                main._sync_character_items_to_shopping(node.title, node.character_items)
        else:
            node.character_items = []

        if panel.optional_check.isChecked():
            node.status = "optional"
        elif node.status == "optional":
            node.status = "locked"

        is_root = self.window.selected_node_id == self.window.root_node_id
        if is_root and node.title != old_title:
            mw_name = self.window.map_name_combo.currentText()
            self.window.root_renamed.emit(mw_name, node.title)

        panel.mark_clean()
        self.window.update_node_card(self.window.selected_node_id)
        self.window.mark_unsaved()
        self.window.close_editor_panel()
        main = self.window.parent()
        if main and hasattr(main, "_rebuild_characters"):
            main._rebuild_characters()

    def cancel_selected_node(self):
        if self._editor_is_dirty():
            current_node = self.window.nodes.get(self.window.selected_node_id)
            title = current_node.title if current_node else "Node"
            dialog = UnsavedChangesDialog(title, language=self.window.language, parent=self.window)
            if not dialog.exec():
                return
            action = dialog.get_action()
            if action == UnsavedChangesDialog.CANCEL:
                return
            if action == UnsavedChangesDialog.SAVE:
                self.save_selected_node()

        self.window.editor_panel.mark_clean()
        self.window.close_editor_panel()

    def delete_node(self, node_id: str):
        if node_id == self.window.root_node_id:
            _msg = {
                "de": ("Nicht möglich", "Der Root-Node kann nicht gelöscht werden."),
                "ru": ("Невозможно", "Корневой узел не может быть удалён."),
            }.get(self.window.language, ("Not possible", "The root node cannot be deleted."))
            QMessageBox.information(self.window, _msg[0], _msg[1])
            return

        node = self.window.nodes.get(node_id)
        if not node:
            return

        parent_id = self._find_parent_id(node_id)
        has_children = bool(node.children)

        dialog = DeleteConfirmDialog(node.title, has_children, language=self.window.language, parent=self.window)
        if not dialog.exec():
            return

        action = dialog.get_action()

        if action == DeleteConfirmDialog.RECURSIVE:
            for desc_id in self._collect_descendants(node_id):
                self.window.nodes.pop(desc_id, None)
            if parent_id:
                parent = self.window.nodes.get(parent_id)
                if parent and node_id in parent.children:
                    parent.children.remove(node_id)

        elif action == DeleteConfirmDialog.INTERMEDIATE:
            if parent_id:
                parent = self.window.nodes.get(parent_id)
                if parent and node_id in parent.children:
                    idx = parent.children.index(node_id)
                    parent.children.remove(node_id)
                    for i, child_id in enumerate(node.children):
                        parent.children.insert(idx + i, child_id)
            self.window.nodes.pop(node_id, None)

        if self.window.selected_node_id == node_id:
            self.window.selected_node_id = None
            self.window.close_editor_panel()

        self.window.render_flow()
        self.window.mark_unsaved()
        main = self.window.parent()
        if main and hasattr(main, "_rebuild_characters"):
            main._rebuild_characters()

    @staticmethod
    def _parse_int(val) -> int:
        try:
            return max(1, int(str(val or 1).strip()))
        except (ValueError, TypeError):
            return 1

    @staticmethod
    def _parse_kinah(val) -> int:
        s = str(val or "0").strip().lower().replace(" ", "")
        if s.endswith("k"):
            num = s[:-1].replace(",", ".")
            try:
                return int(float(num) * 1000)
            except ValueError:
                return 0
        s = s.replace(".", "").replace(",", "")
        try:
            return int(s)
        except (ValueError, TypeError):
            return 0

    def _populate_shopping_dropdown(self, panel):
        """Pass item/task templates from main window to panel."""
        main = self.window.parent()
        if not main:
            return
        if hasattr(main, "item_templates"):
            panel.set_shopping_options(list(main.item_templates))
        if hasattr(main, "task_templates"):
            panel.set_task_options(list(main.task_templates))

    def _find_parent_id(self, node_id: str) -> str | None:
        for parent_id, parent_node in self.window.nodes.items():
            if node_id in parent_node.children:
                return parent_id
        return None

    def _collect_descendants(self, node_id: str) -> list[str]:
        ids = [node_id]
        node = self.window.nodes.get(node_id)
        if node:
            for child_id in node.children:
                ids.extend(self._collect_descendants(child_id))
        return ids

    def confirm_dirty_before_action(self) -> bool:
        """Show Save/Discard/Cancel dialog if editor is dirty.
        Returns True if the pending action should proceed, False if cancelled."""
        if not self._editor_is_dirty():
            return True
        current_node = self.window.nodes.get(self.window.selected_node_id)
        title = current_node.title if current_node else "Node"
        dialog = UnsavedChangesDialog(title, language=self.window.language, parent=self.window)
        if not dialog.exec():
            return False
        action = dialog.get_action()
        if action == UnsavedChangesDialog.CANCEL:
            return False
        if action == UnsavedChangesDialog.SAVE:
            self.save_selected_node()
        return True

    def handle_connector_click(self, parent_id: str):
        if self.window.current_tool == "add_node":
            self.add_child_node(parent_id)
            return

        if self.window.current_tool == "branch":
            return

        if self.window.current_tool == "delete":
            return
        
    def load_node_into_editor(self, node_id: str):
        node = self.window.nodes.get(node_id)

        if not node:
            return

        panel = self.window.editor_panel

        panel.title_input.blockSignals(True)
        panel.desc_input.blockSignals(True)
        panel.symbol_combo.blockSignals(True)
        panel.optional_check.blockSignals(True)

        panel.title_input.setText(node.title)
        panel.desc_input.setPlainText(node.description)

        index = panel.symbol_combo.findData(node.icon)
        if index >= 0:
            panel.symbol_combo.setCurrentIndex(index)

        panel.optional_check.setChecked(node.status == "optional")

        panel.title_input.blockSignals(False)
        panel.desc_input.blockSignals(False)
        panel.symbol_combo.blockSignals(False)
        panel.optional_check.blockSignals(False)

        # "character" icon only allowed for direct children of the root node
        is_root = (node_id == self.window.root_node_id)
        root_node = self.window.nodes.get(self.window.root_node_id)
        is_root_child = (root_node is not None) and (node_id in root_node.children)
        char_allowed = not is_root and is_root_child
        char_idx = panel.symbol_combo.findData("character")
        if char_idx >= 0:
            panel.symbol_combo.model().item(char_idx).setEnabled(char_allowed)

        # Character section
        is_char = node.icon == "character"
        panel.character_section.setVisible(is_char)
        if is_char:
            self._populate_shopping_dropdown(panel)
            panel.load_character_items(node.character_items)
        else:
            panel.load_character_items([])

        panel.mark_clean()