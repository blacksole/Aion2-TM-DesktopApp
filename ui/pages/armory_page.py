from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
from PySide6.QtCore import Signal


class ArmoryPage(QWidget):
    """Sidebar page reserving the future item/build tools (item database
    with faction filter, crafting calculator, build planner). Opens the
    ItemDatabase window either way -- the Crafting Guide itself isn't built
    yet (its own tab/button lives there, currently disabled)."""

    open_item_database_requested = Signal()
    open_crafting_calculator_requested = Signal()
    open_build_planner_requested = Signal()

    # (title_key, desc_key, signal_name or None, button_text_key or None)
    _ROADMAP_ROWS = [
        ("armory_roadmap_items_title", "armory_roadmap_items_desc", "open_item_database_requested", "armory_open_btn"),
        ("armory_roadmap_crafting_title", "armory_roadmap_crafting_desc", "open_crafting_calculator_requested", "armory_open_btn"),
        ("armory_roadmap_builds_title", "armory_roadmap_builds_desc", "open_build_planner_requested", "armory_open_btn"),
    ]

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.title_label = QLabel("Armory")
        self.title_label.setObjectName("mainTitle")

        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("subtitle")

        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)

        self._roadmap_title_labels = []
        self._roadmap_desc_labels = []
        self._open_buttons = []

        for title_key, desc_key, signal_name, btn_text_key in self._ROADMAP_ROWS:
            row = QFrame()
            row.setObjectName("settingsRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 12, 14, 12)
            row_layout.setSpacing(12)

            text_col = QVBoxLayout()
            text_col.setSpacing(4)
            title_label = QLabel()
            title_label.setObjectName("settingsSectionTitle")
            desc_label = QLabel()
            desc_label.setObjectName("settingsSectionDescription")
            desc_label.setWordWrap(True)
            text_col.addWidget(title_label)
            text_col.addWidget(desc_label)

            row_layout.addLayout(text_col, 1)

            if signal_name:
                open_btn = QPushButton()
                open_btn.setObjectName("secondaryButton")
                open_btn.clicked.connect(getattr(self, signal_name).emit)
                row_layout.addWidget(open_btn)
                self._open_buttons.append((open_btn, btn_text_key))

            layout.addWidget(row)

            self._roadmap_title_labels.append((title_label, title_key))
            self._roadmap_desc_labels.append((desc_label, desc_key))

        layout.addStretch()

    def update_language(self, language: str, tr_func):
        self.title_label.setText(tr_func(language, "armory"))
        self.subtitle_label.setText(tr_func(language, "armory_subtitle"))
        for label, key in self._roadmap_title_labels:
            label.setText(tr_func(language, key))
        for label, key in self._roadmap_desc_labels:
            label.setText(tr_func(language, key))
        for btn, btn_text_key in self._open_buttons:
            btn.setText(tr_func(language, btn_text_key))
