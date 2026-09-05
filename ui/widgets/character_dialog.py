from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.flow.widgets.delete_confirm_dialog import DeleteConfirmDialog


class CharacterManagerDialog(QDialog):
    """Standalone "Character" popup, opened from its own button next to
    "Templates" on the ToDo screen (User-Wunsch, 2026-09-04: "Character
    sollte direkt im ToDo Fenster neben Templates stehen" -- a first pass
    put this inside the Templates dialog as a third tab, which the user
    then corrected: this row's future belongs to a "Standard Templates"
    picker, not character management, so it needed its own dedicated
    surface instead).

    Characters have no separate registry anywhere in the app -- they ARE
    Flow Map nodes with icon="character" under the hood (see MainWindow.
    _rebuild_characters/_add_character/_remove_character), which is
    exactly the gap GitHub issue #2 flagged: "There is no obvious way to
    add a character in Templates, Profile, or Settings." This dialog is
    just a thin UI over those two MainWindow methods, passed in as
    callbacks (same pattern as TemplateDialog's item_picker_callback) so
    it stays the one single Flow-Map-node model, not a second parallel one.
    """

    def __init__(self, characters: list, add_character_callback, remove_character_callback,
                 has_children_callback=None,
                 language: str = "en", tr_func=None, parent=None):
        super().__init__(parent)
        self._characters = list(characters or [])
        self._add_character_callback = add_character_callback
        # remove_character_callback(name, action) -- action is "recursive"
        # or "intermediate", the same choice flow_controller.delete_node()
        # already offers for any Flow Map node with children (User-Wunsch,
        # 2026-09-04: "Bei remove Charakter sollte eine Abfrage in Bezug
        # auf die Flow Chart kommen - siehe Kind von Vater entfernen") --
        # has_children_callback(name) decides whether _on_remove_clicked
        # even needs to ask, via the very same DeleteConfirmDialog the
        # Flow Map editor itself uses.
        self._remove_character_callback = remove_character_callback
        self._has_children_callback = has_children_callback
        self._language = language
        self._tr = tr_func or (lambda _l, k, **kw: k)

        self.setWindowTitle(self._t("tab_character"))
        self.setMinimumSize(420, 480)
        self.resize(460, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        info = QLabel(self._t("character_tab_info"))
        info.setObjectName("subtitle")
        info.setWordWrap(True)
        layout.addWidget(info)

        add_row = QHBoxLayout()
        self._name_input = QLineEdit()
        self._name_input.setObjectName("FlowInput")
        self._name_input.setPlaceholderText(self._t("char_add_new_label"))
        self._name_input.returnPressed.connect(self._on_add_clicked)
        add_btn = QPushButton(self._t("char_add_new"))
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._on_add_clicked)
        add_row.addWidget(self._name_input, 1)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self._list_container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("scrollArea")
        # Viewport paints its own background separately from #scrollArea's
        # own QSS rule -- can show up as a plain white box when Windows
        # itself is set to dark mode (same fix already applied elsewhere,
        # e.g. TemplateDialog's own lists).
        scroll.viewport().setStyleSheet("background: transparent;")
        layout.addWidget(scroll, 1)

        close_btn = QPushButton(self._t("close"))
        close_btn.setObjectName("primaryButton")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignRight)

        self._rebuild_list()

    def _t(self, key: str, **kwargs) -> str:
        return self._tr(self._language, key, **kwargs)

    def _rebuild_list(self):
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for name in self._characters:
            row = self._make_row(name)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def _make_row(self, name: str) -> QWidget:
        row = QFrame()
        row.setObjectName("taskCard")
        hl = QHBoxLayout(row)
        hl.setContentsMargins(12, 8, 12, 8)
        hl.setSpacing(10)

        name_lbl = QLabel(name)
        name_lbl.setObjectName("taskTitle")
        hl.addWidget(name_lbl, 1)

        remove_btn = QPushButton(self._t("remove"))
        remove_btn.setObjectName("secondaryButton")
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.clicked.connect(lambda _c=False, n=name: self._on_remove_clicked(n))
        hl.addWidget(remove_btn)
        return row

    def _on_add_clicked(self):
        name = self._name_input.text().strip()
        if not name:
            return
        ok, error_key = self._add_character_callback(name)
        if ok:
            self._characters.append(name)
            self._characters.sort()
            self._name_input.clear()
            self._rebuild_list()
        elif error_key:
            QMessageBox.warning(self, self._t("char_add_new_title"), self._t(error_key))

    def _on_remove_clicked(self, name: str):
        has_children = bool(self._has_children_callback and self._has_children_callback(name))
        dialog = DeleteConfirmDialog(name, has_children, language=self._language, parent=self)
        if not dialog.exec():
            return
        action = dialog.get_action()  # "recursive" or "intermediate"
        ok, error_key = self._remove_character_callback(name, action)
        if ok:
            if name in self._characters:
                self._characters.remove(name)
            self._rebuild_list()
        elif error_key:
            QMessageBox.warning(self, self._t("tab_character"), self._t(error_key))
