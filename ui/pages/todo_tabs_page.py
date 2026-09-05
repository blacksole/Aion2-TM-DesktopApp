from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget


class TodoTabsPage(QWidget):
    """Thin top-level wrapper combining the existing Tasks/Shopping page and
    the Timers page under two top tabs ('ToDo' / 'Timer') — replaces the
    separate 'Tasks' and 'Timers' sidebar entries with one merged one.
    Doesn't touch TasksPage/TimersPage internals; just hides their own
    title/subtitle labels since this wrapper's tab row takes over that role."""

    def __init__(self, todo_widget: QWidget, timer_widget: QWidget):
        super().__init__()

        if hasattr(todo_widget, "title_label"):
            todo_widget.title_label.setVisible(False)
        if hasattr(todo_widget, "subtitle_label"):
            todo_widget.subtitle_label.setVisible(False)
        if hasattr(timer_widget, "title_label"):
            timer_widget.title_label.setVisible(False)
        if hasattr(timer_widget, "subtitle_label"):
            timer_widget.subtitle_label.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.tab_row = QHBoxLayout()
        self.tab_row.setSpacing(8)

        self.todo_tab_btn = QPushButton("ToDo")
        self.todo_tab_btn.setObjectName("topTabButton")

        self.timer_tab_btn = QPushButton("Timer")
        self.timer_tab_btn.setObjectName("topTabButton")

        self.todo_tab_btn.clicked.connect(lambda: self.set_active_tab("todo"))
        self.timer_tab_btn.clicked.connect(lambda: self.set_active_tab("timer"))

        self.tab_row.addWidget(self.todo_tab_btn)
        self.tab_row.addWidget(self.timer_tab_btn)
        self.tab_row.addStretch()

        # Reaches into todo_widget (TasksPage) for these two exact same way
        # as title_label/subtitle_label above (User-Wunsch, 2026-09-05:
        # "wie wärs so", screenshot showing Full View/Import top-right next
        # to "ToDo | Timer" instead of sharing TasksPage's own crowded
        # rows). Hidden while the Timer tab is active in set_active_tab
        # below -- they only ever act on Tasks/Shopping data.
        self._full_view_btn = getattr(todo_widget, "_full_view_btn", None)
        self._import_btn = getattr(todo_widget, "_import_btn", None)
        if self._full_view_btn is not None:
            self.tab_row.addWidget(self._full_view_btn)
        if self._import_btn is not None:
            self.tab_row.addWidget(self._import_btn)

        layout.addLayout(self.tab_row)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(todo_widget)
        self.content_stack.addWidget(timer_widget)
        layout.addWidget(self.content_stack, 1)

        self.set_active_tab("todo")

    def set_active_tab(self, key: str):
        self.todo_tab_btn.setProperty("active", key == "todo")
        self.timer_tab_btn.setProperty("active", key == "timer")
        for btn in (self.todo_tab_btn, self.timer_tab_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.content_stack.setCurrentIndex(0 if key == "todo" else 1)
        is_todo = key == "todo"
        if self._full_view_btn is not None:
            self._full_view_btn.setVisible(is_todo)
        if self._import_btn is not None:
            self._import_btn.setVisible(is_todo)

    def update_language(self, language: str, tr_func):
        self.todo_tab_btn.setText(tr_func(language, "todo"))
        self.timer_tab_btn.setText(tr_func(language, "timers"))
