from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Signal, Qt


class ArmoryPage(QWidget):
    """Sidebar page reserving the future item/build tools (item database
    with faction filter, crafting calculator, build planner). Opens the
    ItemDatabase window either way -- the Crafting Guide itself isn't built
    yet (its own tab/button lives there, currently disabled)."""

    open_item_database_requested = Signal()
    open_crafting_calculator_requested = Signal()
    open_build_planner_requested = Signal()

    # (title_key, desc_key, signal_name)
    _ROADMAP_ROWS = [
        ("armory_roadmap_items_title", "armory_roadmap_items_desc", "open_item_database_requested"),
        ("armory_roadmap_crafting_title", "armory_roadmap_crafting_desc", "open_crafting_calculator_requested"),
        ("armory_roadmap_builds_title", "armory_roadmap_builds_desc", "open_build_planner_requested"),
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

        for title_key, desc_key, signal_name in self._ROADMAP_ROWS:
            # Whole card is clickable (User-Wunsch, 2026-09-10/11: "Die
            # Buttons rechts entfernen und die Karten selbst als Buttons
            # machen, sodass man überall drauf klicken kann") -- own
            # objectName instead of the shared "settingsRow" so the hover
            # affordance below doesn't leak onto every other Settings row
            # that still isn't clickable. Same mousePressEvent-monkeypatch
            # pattern already used for Task/Shopping cards (MainWindow.
            # _wire_card) and the Templates picker rows.
            row = QFrame()
            row.setObjectName("armoryCardRow")
            row.setCursor(Qt.PointingHandCursor)
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

            bound_signal = getattr(self, signal_name)

            def on_press(event, signal=bound_signal, r=row):
                if event.button() == Qt.LeftButton:
                    signal.emit()
                type(r).mousePressEvent(r, event)

            row.mousePressEvent = on_press

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
