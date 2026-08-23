from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import Signal


class SidebarWidget(QWidget):
    page_changed = Signal(str)

    def __init__(self):
        super().__init__()

        self.setObjectName("SidebarWidget")
        self.setFixedWidth(190)

        self.pages = {
            "tasks": "todo",
            "plan": "plan",
            "armory": "armory",
            "settings": "settings",
            "about": "about",
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.buttons = {}
        # Whether the "armory" nav entry should carry a "(Beta)" suffix --
        # set by MainWindow._update_armory_visibility(), which owns the
        # actual visibility/beta logic (this widget just renders labels).
        self._armory_beta_marked = False

        for key, translation_key in self.pages.items():
            button = QPushButton(translation_key)
            button.setCheckable(True)
            button.setObjectName("sidebarButton")
            button.clicked.connect(
                lambda checked=False, page_key=key: self.set_active_page(page_key)
            )

            layout.addWidget(button)
            self.buttons[key] = button

        layout.addStretch()

        self.set_active_page("tasks")

    def set_active_page(self, page_key: str):
        for key, button in self.buttons.items():
            button.setChecked(key == page_key)

        self.page_changed.emit(page_key)

    def set_armory_beta_marked(self, marked: bool):
        self._armory_beta_marked = marked

    def update_language(self, language: str, tr_func):
        for key, translation_key in self.pages.items():
            label = tr_func(language, translation_key)
            # Kept as a plain, untranslated "(Beta)" suffix rather than a
            # new translation key per language, since it's a temporary
            # marker, not permanent UI copy.
            if key == "armory" and self._armory_beta_marked:
                label = f"{label} (Beta)"
            self.buttons[key].setText(label)
