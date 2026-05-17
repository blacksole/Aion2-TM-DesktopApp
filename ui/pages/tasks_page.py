from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QScrollArea, 
    QComboBox
)
from PySide6.QtCore import Signal

class TaskStatCard(QFrame):
    def __init__(self, title, value, color):
        super().__init__()

        self.setObjectName("statCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("statTitle")

        self.value_label = QLabel(str(value))
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 30px; font-weight: bold;"
        )

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

class TasksPage(QWidget):
    tab_changed = Signal(str)
    task_add_requested = Signal(dict)
    sort_requested = Signal(str)  # tab_key, sort_key

    def __init__(self, tabs: dict, language: str, tr_func):
        super().__init__()

        self.tabs = tabs
        self.language = language
        self.tr = tr_func
        self.active_tab = "dailyTasks"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(22)

        self.title_label = QLabel(self.tr(self.language, "tasks"))
        self.title_label.setObjectName("mainTitle")

        self.subtitle_label = QLabel(self.tr(self.language, "tasks_subtitle"))
        self.subtitle_label.setObjectName("subtitle")

        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)

        self.tab_row = QHBoxLayout()
        self.tab_row.setSpacing(8)

        self.tab_buttons = {}

        for key, label in self.tabs.items():
            btn = QPushButton(self.tr(self.language, label))
            btn.setObjectName("tabButton")
            btn.clicked.connect(
                lambda checked=False, k=key: self.set_active_tab(k)
            )

            self.tab_buttons[key] = btn
            self.tab_row.addWidget(btn)

        self.tab_row.addStretch()
        layout.addLayout(self.tab_row)
        stats_row = QHBoxLayout()

        self.total_card = TaskStatCard(
            self.tr(self.language, "total"),
            0,
            "#22d3ee"
        )

        self.done_card = TaskStatCard(
            self.tr(self.language, "done"),
            0,
            "#34d399"
        )

        self.open_card = TaskStatCard(
            self.tr(self.language, "remaining"),
            0,
            "#fbbf24"
        )

        stats_row.addWidget(self.total_card)
        stats_row.addWidget(self.done_card)
        stats_row.addWidget(self.open_card)

        add_panel = QFrame()
        add_panel.setObjectName("addPanel")

        add_layout = QHBoxLayout(add_panel)
        add_layout.setContentsMargins(18, 18, 18, 18)
        add_layout.setSpacing(12)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Titel")

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText(
            self.tr(self.language, "description")
        )

        self.priority_input = QComboBox()
        self.priority_input.setObjectName("priorityInput")
        self.priority_input.addItem(
            self.tr(self.language, "priority_low"),
            "low"
        )
        self.priority_input.addItem(
            self.tr(self.language, "priority_middle"),
            "middle"
        )
        self.priority_input.addItem(
            self.tr(self.language, "priority_high"),
            "high"
        )

        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText(
            self.tr(self.language, "location")
        )

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText(
            self.tr(self.language, "amount")
        )

        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText(
            self.tr(self.language, "price")
        )

        self.add_btn = QPushButton(self.tr(self.language, "add"))
        self.add_btn.setObjectName("primaryButton")

        self.desc_input.returnPressed.connect(self.emit_add_task)
        self.add_btn.clicked.connect(self.emit_add_task)

        # Standardmäßig nur die für Aufgaben relevanten Inputs anzeigen
        add_layout.addWidget(self.priority_input, 2)
        add_layout.addWidget(self.title_input, 3)

        add_layout.addWidget(self.desc_input, 4)

        # Shopping-spezifische Inputs
        add_layout.addWidget(self.location_input, 3)
        add_layout.addWidget(self.amount_input, 2)
        add_layout.addWidget(self.price_input, 2)

        self.location_input.hide()
        self.amount_input.hide()
        self.price_input.hide()

        add_layout.addWidget(self.add_btn)
        
        layout.addLayout(stats_row)
        layout.addWidget(add_panel)

        self.sort_row = QHBoxLayout()
        self.sort_row.setSpacing(8)

        self.sort_label = QLabel(
            self.tr(self.language, "sort_by")
        )
        self.sort_label.setObjectName("sortLabel")

        self.sort_prio_btn = QPushButton(
            self.tr(self.language, "sort_by_priority")
        )
        self.sort_prio_btn.setObjectName("sortButton")
        self.sort_prio_btn.clicked.connect(lambda: self.sort_requested.emit("priority"))

        self.sort_title_btn = QPushButton(
            self.tr(self.language, "sort_by_title")
        )
        self.sort_title_btn.setObjectName("sortButton")
        self.sort_title_btn.clicked.connect(lambda: self.sort_requested.emit("title"))

        self.sort_location_btn = QPushButton(
            self.tr(self.language, "sort_by_location")
        )
        self.sort_location_btn.setObjectName("sortButton")
        self.sort_location_btn.clicked.connect(lambda: self.sort_requested.emit("location"))

        self.sort_price_btn = QPushButton(
            self.tr(self.language, "sort_by_price")
        )
        self.sort_price_btn.setObjectName("sortButton")
        self.sort_price_btn.clicked.connect(lambda: self.sort_requested.emit("price"))

        self.sort_row.addWidget(self.sort_label)
        self.sort_row.addWidget(self.sort_prio_btn)
        self.sort_row.addWidget(self.sort_title_btn)
        self.sort_row.addWidget(self.sort_location_btn)
        self.sort_row.addWidget(self.sort_price_btn)
        self.sort_row.addStretch()

        layout.addLayout(self.sort_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("scrollArea")

        self.list_container = QWidget()

        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch()

        scroll.setWidget(self.list_container)

        layout.addWidget(scroll, 1)

        self.footer = QLabel("● Fortschritt: 0%")
        self.footer.setObjectName("footer")

        layout.addWidget(self.footer)
        self.update_input_mode()


    def set_active_tab(self, tab_key: str):
        self.active_tab = tab_key
        self.update_input_mode()

        for key, btn in self.tab_buttons.items():
            btn.setProperty("active", key == self.active_tab)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.tab_changed.emit(tab_key)

    def set_events_visible(self, visible: bool):
        if "eventTasks" in self.tab_buttons:
            self.tab_buttons["eventTasks"].setVisible(visible)

        if "eventShopping" in self.tab_buttons:
            self.tab_buttons["eventShopping"].setVisible(visible)

    def update_input_mode(self):
        shopping_tabs = [
            "dailyShopping",
            "weeklyShopping",
            "eventShopping",
        ]

        is_shopping = self.active_tab in shopping_tabs

        self.desc_input.setVisible(not is_shopping)

        self.priority_input.setVisible(True)
        self.amount_input.setVisible(is_shopping)
        self.location_input.setVisible(is_shopping)
        self.price_input.setVisible(is_shopping)
        self.sort_price_btn.setVisible(is_shopping)

    def update_language(self, language: str):
        self.language = language

        for key, btn in self.tab_buttons.items():
            btn.setText(self.tr(self.language, self.tabs[key]))

        self.total_card.title_label.setText(
            self.tr(self.language, "total").upper()
        )

        self.done_card.title_label.setText(
            self.tr(self.language, "done").upper()
        )

        self.open_card.title_label.setText(
            self.tr(self.language, "remaining").upper()
        )

        self.add_btn.setText(
            self.tr(self.language, "add")
        )

        self.desc_input.setPlaceholderText(
            self.tr(self.language, "description")
        )

        self.set_title_placeholder(
            self.tr(self.language, "title")
        )

        self.title_label.setText(
            self.tr(self.language, "tasks")
        )

        self.subtitle_label.setText(
            self.tr(self.language, "tasks_subtitle")
        )

        current_priority = self.priority_input.currentData()

        self.priority_input.clear()

        self.priority_input.addItem(
            self.tr(self.language, "priority_low"),
            "low"
        )

        self.priority_input.addItem(
            self.tr(self.language, "priority_middle"),
            "middle"
        )

        self.priority_input.addItem(
            self.tr(self.language, "priority_high"),
            "high"
        )

        index = self.priority_input.findData(current_priority)

        self.priority_input.setCurrentIndex(
            index if index >= 0 else 1
        )

        self.location_input.setPlaceholderText(
            self.tr(self.language, "location")
        )

        self.amount_input.setPlaceholderText(
            self.tr(self.language, "amount")
        )

        self.price_input.setPlaceholderText(
            self.tr(self.language, "price")
        )

        self.sort_label.setText(
            self.tr(self.language, "sort_by")
        )

        self.sort_prio_btn.setText(
            self.tr(self.language, "sort_by_priority")
        )

        self.sort_title_btn.setText(
            self.tr(self.language, "sort_by_title")
        )

        self.sort_location_btn.setText(
            self.tr(self.language, "sort_by_location")
        )

        self.sort_price_btn.setText(
            self.tr(self.language, "sort_by_price")
        )

    def update_stats(self, total: int, done: int, open_count: int):
        self.total_card.value_label.setText(str(total))
        self.done_card.value_label.setText(str(done))
        self.open_card.value_label.setText(str(open_count))

    def emit_add_task(self):
        title = self.title_input.text().strip()

        if not title:
            return

        shopping_tabs = [
            "dailyShopping",
            "weeklyShopping",
            "eventShopping",
        ]

        if self.active_tab in shopping_tabs:
            data = {
                "priority": self.priority_input.currentData(),
                "amount": self.amount_input.text().strip() or "1",
                "title": title,
                "location": self.location_input.text().strip(),
                "price": f"{float(self.price_input.text().strip() or 0):.2f} €",
            }
        else:
            data = {
                "priority": self.priority_input.currentData(),
                "title": title,
                "description": self.desc_input.text().strip(),
            }

        self.task_add_requested.emit(data)

        self.title_input.clear()
        self.desc_input.clear()
        self.location_input.clear()
        self.amount_input.clear()
        self.price_input.clear()
        self.priority_input.setCurrentIndex(1)


    def set_title_placeholder(self, text: str):
        self.title_input.setPlaceholderText(text)

    def render_tasks(self, tasks: list):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.setParent(None)

        for task in tasks:
            self.list_layout.insertWidget(
                self.list_layout.count() - 1,
                task
            )

    def set_footer_text(self, text: str):
        self.footer.setText(text)

    