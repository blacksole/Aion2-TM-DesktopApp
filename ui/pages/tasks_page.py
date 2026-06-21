from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QScrollArea,
    QComboBox, QCheckBox, QButtonGroup
)
from PySide6.QtCore import Signal, QRect, Qt
from PySide6.QtGui import QIntValidator, QPainter, QColor, QLinearGradient, QBrush

class TaskProgressBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("TaskProgressBar")
        self.setFixedHeight(100)
        self._done = 0
        self._total = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 10)
        outer.setSpacing(8)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(0)

        self._done_val  = QLabel("0")
        self._open_val  = QLabel("0")
        self._total_val = QLabel("0")
        self._pct_val   = QLabel("0%")
        self._extra_lbl = QLabel("")
        self._extra_lbl.setObjectName("ProgressExtra")

        self._sub_labels = []
        for val, icon, label, val_obj, icon_obj, sub_obj in [
            (self._done_val,  "✓", "Erledigt", "ProgressDoneVal",  "ProgressDoneIcon",  "ProgressDoneSub"),
            (self._open_val,  "○", "Offen",    "ProgressOpenVal",  "ProgressOpenIcon",  "ProgressOpenSub"),
            (self._total_val, "Σ", "Gesamt",   "ProgressTotalVal", "ProgressTotalIcon", "ProgressTotalSub"),
        ]:
            icon_lbl = QLabel(icon)
            icon_lbl.setObjectName(icon_obj)
            val.setObjectName(val_obj)
            sub = QLabel(label)
            sub.setObjectName(sub_obj)
            self._sub_labels.append(sub)

            col = QVBoxLayout()
            col.setSpacing(1)
            col.setContentsMargins(0, 0, 0, 0)

            top_row = QHBoxLayout()
            top_row.setSpacing(5)
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.addWidget(icon_lbl)
            top_row.addWidget(val)
            top_row.addStretch()

            col.addLayout(top_row)
            col.addWidget(sub)

            stats_row.addLayout(col)
            stats_row.addSpacing(28)

        stats_row.addWidget(self._extra_lbl, 1)

        self._pct_val.setObjectName("ProgressPct")
        self._pct_sub = QLabel("Fortschritt")
        self._pct_sub.setObjectName("ProgressPctSub")
        pct_sub = self._pct_sub
        pct_sub.setAlignment(Qt.AlignRight)

        pct_col = QVBoxLayout()
        pct_col.setSpacing(1)
        pct_col.setContentsMargins(0, 0, 0, 0)
        pct_col.addWidget(self._pct_val)
        pct_col.addWidget(pct_sub)
        stats_row.addLayout(pct_col)

        outer.addLayout(stats_row)

        self._bar = QWidget()
        self._bar.setFixedHeight(8)
        outer.addWidget(self._bar)

    def update_stats(self, total: int, done: int, open_count: int):
        self._done = done
        self._total = total
        pct = int(done / total * 100) if total > 0 else 0
        self._done_val.setText(str(done))
        self._open_val.setText(str(open_count))
        self._total_val.setText(str(total))
        self._pct_val.setText(f"{pct}%")
        self.update()

    def update_language(self, language: str, tr_func):
        for sub, key in zip(self._sub_labels, ["done", "remaining", "total"]):
            sub.setText(tr_func(language, key))
        self._pct_sub.setText(tr_func(language, "progress"))

    def set_extra(self, text: str):
        self._extra_lbl.setText(text)

    def paintEvent(self, event):
        super().paintEvent(event)
        bar = self._bar.geometry()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # track
        p.setBrush(QBrush(QColor(15, 23, 42, 180)))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(bar, 4, 4)

        # fill
        if self._total > 0 and self._done > 0:
            fill_w = max(8, int(bar.width() * self._done / self._total))
            fill = QRect(bar.x(), bar.y(), fill_w, bar.height())
            grad = QLinearGradient(fill.left(), 0, fill.right(), 0)
            grad.setColorAt(0.0, QColor(6, 182, 212))
            grad.setColorAt(1.0, QColor(168, 85, 247))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fill, 4, 4)

        p.end()

class TasksPage(QWidget):
    tab_changed = Signal(str)
    task_add_requested = Signal(dict)
    sort_requested = Signal(object)  # tab_key, sort_key
    filter_changed = Signal(str)

    def __init__(self, tabs: dict, language: str, tr_func):
        super().__init__()

        self.tabs = tabs
        self.language = language
        self.tr = tr_func
        self.active_tab = "dailyTasks"
        self.active_filter = "all"
        self.active_sort = "priority"
        self.sort_direction = "desc"

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

        self.progress_bar = TaskProgressBar()

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

        self.event_input = QCheckBox()
        self.event_input.setObjectName("eventCheckBox")
        self.event_input.setText("Event")

        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText(
            self.tr(self.language, "location")
        )

        self.amount_input = QLineEdit()
        self.amount_input.setValidator(
            QIntValidator(0, 999999)
        )
        self.amount_input.setPlaceholderText(
            self.tr(self.language, "amount")
        )

        self.price_input = QLineEdit()
        self.price_input.setValidator(
            QIntValidator(0, 999999999)
        )
        self.price_input.setPlaceholderText(
            f"{self.tr(self.language, 'price')} (K)"
        )

        self.add_btn = QPushButton(self.tr(self.language, "add"))
        self.add_btn.setObjectName("primaryButton")

        self.desc_input.returnPressed.connect(self.emit_add_task)
        self.add_btn.clicked.connect(self.emit_add_task)

        # Standardmäßig nur die für Aufgaben relevanten Inputs anzeigen
        add_layout.addWidget(self.event_input)
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
        
        layout.addWidget(self.progress_bar)
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
        self.sort_prio_btn.setCheckable(True)
        self.sort_prio_btn.clicked.connect(
            lambda: self.set_sort("priority")
        )

        self.sort_title_btn = QPushButton(
            self.tr(self.language, "sort_by_title")
        )
        self.sort_title_btn.setObjectName("sortButton")
        self.sort_title_btn.setCheckable(True)
        self.sort_title_btn.clicked.connect(lambda: self.set_sort("title"))

        self.sort_location_btn = QPushButton(
            self.tr(self.language, "sort_by_location")
        )
        self.sort_location_btn.setObjectName("sortButton")
        self.sort_location_btn.setCheckable(True)
        self.sort_location_btn.clicked.connect(lambda: self.set_sort("location"))

        self.sort_price_btn = QPushButton(
            self.tr(self.language, "sort_by_price")
        )
        self.sort_price_btn.setObjectName("sortButton")
        self.sort_price_btn.setCheckable(True)
        self.sort_price_btn.clicked.connect(lambda: self.set_sort("price"))

        self.sort_button_group = QButtonGroup(self)
        self.sort_button_group.setExclusive(True)

        for btn in [
            self.sort_prio_btn,
            self.sort_title_btn,
            self.sort_location_btn,
            self.sort_price_btn,
        ]:
            btn.setCheckable(True)
            self.sort_button_group.addButton(btn)

        self.filter_label = QLabel(
            self.tr(self.language, "filter_by")
        )
        self.filter_label.setObjectName("sortLabel")

        self.filter_all_btn = QPushButton("Alle")
        self.filter_all_btn.setObjectName("filterButton")
        self.filter_all_btn.clicked.connect(lambda: self.set_filter("all"))
        self.filter_all_btn.setProperty("active", True)

        self.filter_event_btn = QPushButton("Events")
        self.filter_event_btn.setObjectName("filterButton")
        self.filter_event_btn.clicked.connect(lambda: self.set_filter("event"))

        self.active_sort = "priority"
        self.update_sort_buttons()

        self.active_filter = "all"
        self.update_filter_buttons()

        separator = QLabel("|")
        separator.setObjectName("sortSeparator")

        self.sort_row.addWidget(self.sort_label)
        self.sort_row.addWidget(self.sort_prio_btn)
        self.sort_row.addWidget(self.sort_title_btn)
        self.sort_row.addWidget(self.sort_location_btn)
        self.sort_row.addWidget(self.sort_price_btn)

        self.sort_row.addSpacing(8)
        self.sort_row.addWidget(separator)
        self.sort_row.addSpacing(8)

        self.sort_row.addWidget(self.filter_label)
        self.sort_row.addWidget(self.filter_all_btn)
        self.sort_row.addWidget(self.filter_event_btn)

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
            f"{self.tr(self.language, 'price')} (K)"
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

        self.filter_label.setText(
            self.tr(self.language, "filter_by")
        )

        self.filter_all_btn.setText(
            self.tr(self.language, "filter_by_all")
        )

        self.filter_event_btn.setText(
            self.tr(self.language, "filter_by_events")
        )

        self.event_input.setText(
            self.tr(self.language, "filter_by_events")
        )

        self.progress_bar.update_language(language, self.tr)

    def update_stats(self, total: int, done: int, open_count: int):
        self.progress_bar.update_stats(total, done, open_count)

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
                "event": self.event_input.isChecked(),
                "priority": self.priority_input.currentData(),
                "amount": self.amount_input.text().strip() or "1",
                "title": title,
                "location": self.location_input.text().strip(),
                "price": self.price_input.text().strip() or "0",
            }
        else:
            data = {
                "event": self.event_input.isChecked(),
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
        self.event_input.setChecked(False)


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

    def set_event_features_visible(self, visible: bool):
        self.event_input.setVisible(visible)

        self.filter_label.setVisible(visible)
        self.filter_all_btn.setVisible(visible)
        self.filter_event_btn.setVisible(visible)

        if not visible:
            self.set_filter("all")

    def set_footer_text(self, text: str):
        if "|" in text:
            self.progress_bar.set_extra(text.split("|")[1].strip())
        else:
            self.progress_bar.set_extra("")

    def set_filter(self, filter_key: str):
        self.active_filter = filter_key
        self.filter_changed.emit(filter_key)
        self.update_filter_buttons()

    def update_filter_buttons(self):
        self.filter_all_btn.setProperty(
            "active",
            self.active_filter == "all"
        )

        self.filter_event_btn.setProperty(
            "active",
            self.active_filter == "event"
        )

        for btn in [
            self.filter_all_btn,
            self.filter_event_btn,
        ]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_sort(self, sort_key: str):
        if self.active_sort == sort_key:
            self.sort_direction = (
                "asc" if self.sort_direction == "desc" else "desc"
            )
        else:
            self.active_sort = sort_key
            self.sort_direction = "desc"

        self.update_sort_buttons()
        self.sort_requested.emit(
            {
                "key": self.active_sort,
                "direction": self.sort_direction,
            }
        )


    def update_sort_buttons(self):
        sort_buttons = {
            "priority": (
                self.sort_prio_btn,
                self.tr(self.language, "sort_by_priority")
            ),
            "title": (
                self.sort_title_btn,
                self.tr(self.language, "sort_by_title")
            ),
            "location": (
                self.sort_location_btn,
                self.tr(self.language, "sort_by_location")
            ),
            "price": (
                self.sort_price_btn,
                self.tr(self.language, "sort_by_price")
            ),
        }

        arrow = "↓" if self.sort_direction == "desc" else "↑"

        for key, (btn, label) in sort_buttons.items():
            is_active = self.active_sort == key

            btn.setChecked(is_active)

            if is_active:
                btn.setText(f"{label} {arrow}")
            else:
                btn.setText(label)

            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()