from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import Signal


class SidebarWidget(QWidget):
    page_changed = Signal(str)

    def __init__(self):
        super().__init__()

        self.setObjectName("SidebarWidget")
        self.setFixedWidth(190)

        self.pages = {
            "tasks": "tasks",
            "timers": "timers",
            "plan": "plan",
            "profile": "profile",
            "settings": "settings",
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.buttons = {}

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

    def update_language(self, language: str, tr_func):
        for key, translation_key in self.pages.items():
            self.buttons[key].setText(
                tr_func(language, translation_key)
            )