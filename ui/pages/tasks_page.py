from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QScrollArea,
    QComboBox, QCheckBox, QButtonGroup, QCompleter
)
from PySide6.QtCore import Signal, QRect, Qt, QRegularExpression
from PySide6.QtGui import QIntValidator, QRegularExpressionValidator, QPainter, QColor, QLinearGradient, QBrush

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
            (self._done_val,  "✓", "done",      "ProgressDoneVal",  "ProgressDoneIcon",  "ProgressDoneSub"),
            (self._open_val,  "○", "remaining", "ProgressOpenVal",  "ProgressOpenIcon",  "ProgressOpenSub"),
            (self._total_val, "Σ", "total",     "ProgressTotalVal", "ProgressTotalIcon", "ProgressTotalSub"),
        ]:
            icon_lbl = QLabel(icon)
            icon_lbl.setObjectName(icon_obj)
            val.setObjectName(val_obj)
            sub = QLabel("")
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
        self._pct_sub = QLabel("")
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
    manual_reset_requested = Signal()
    template_requested = Signal()
    character_requested = Signal()
    full_view_requested = Signal()
    import_requested = Signal()

    def __init__(self, tabs: dict, language: str, tr_func):
        super().__init__()

        self.tabs = tabs
        self.language = language
        self.tr = tr_func
        self.active_tab = "tasks"
        self.active_filter = "all"
        self.active_sort = "priority"
        self.sort_direction = "desc"
        self._show_events = True

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

        self._template_btn = QPushButton(self.tr(self.language, "templates_btn"))
        self._template_btn.setObjectName("templateButton")
        self._template_btn.setCursor(Qt.PointingHandCursor)
        self._template_btn.setVisible(False)
        self._template_btn.clicked.connect(self.template_requested.emit)
        self.tab_row.addWidget(self._template_btn)

        # Directly next to "Templates", not buried inside it (User-
        # correction, 2026-09-04, after a first pass put this inside the
        # Templates popup as a tab: "Character sollte direkt im ToDo
        # Fenster neben Templates stehen").
        self._character_btn = QPushButton(self.tr(self.language, "tab_character"))
        self._character_btn.setObjectName("templateButton")
        self._character_btn.setCursor(Qt.PointingHandCursor)
        self._character_btn.setVisible(False)
        self._character_btn.clicked.connect(self.character_requested.emit)
        self.tab_row.addWidget(self._character_btn)

        layout.addLayout(self.tab_row)

        self.progress_bar = TaskProgressBar()

        add_panel = QFrame()
        add_panel.setObjectName("addPanel")

        add_layout = QHBoxLayout(add_panel)
        add_layout.setContentsMargins(18, 18, 18, 18)
        add_layout.setSpacing(12)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText(self.tr(self.language, "title"))

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

        # Schedule selector — mutually exclusive, only visible in shopping mode
        self.schedule_daily_btn = QPushButton("Daily")
        self.schedule_daily_btn.setObjectName("scheduleToggleBtn")
        self.schedule_daily_btn.setCheckable(True)
        self.schedule_daily_btn.setChecked(True)

        self.schedule_weekly_btn = QPushButton("Weekly")
        self.schedule_weekly_btn.setObjectName("scheduleToggleBtn")
        self.schedule_weekly_btn.setCheckable(True)

        self.schedule_season_btn = QPushButton("Season")
        self.schedule_season_btn.setObjectName("scheduleToggleBtn")
        self.schedule_season_btn.setCheckable(True)

        self._schedule_btn_group = QButtonGroup(self)
        self._schedule_btn_group.setExclusive(True)
        self._schedule_btn_group.addButton(self.schedule_daily_btn)
        self._schedule_btn_group.addButton(self.schedule_weekly_btn)
        self._schedule_btn_group.addButton(self.schedule_season_btn)

        self.amount_input = QLineEdit()
        self.amount_input.setValidator(QIntValidator(0, 999999))
        self.amount_input.setPlaceholderText(self.tr(self.language, "amount"))
        self.amount_input.setMaximumWidth(80)

        # Template selector — replaces free-text title in shopping / tasks mode
        self._templates: list[dict] = []
        self._task_templates: list[dict] = []
        self.template_combo = QComboBox()
        self.template_combo.setObjectName("priorityInput")
        self.template_combo.setMinimumWidth(160)
        self.template_combo.setCurrentIndex(-1)
        self.template_combo.setEditable(True)
        self.template_combo.setInsertPolicy(QComboBox.NoInsert)
        self.template_combo.lineEdit().setPlaceholderText(self.tr(self.language, "template_placeholder"))

        template_completer = QCompleter(self.template_combo.model(), self.template_combo)
        template_completer.setCompletionMode(QCompleter.PopupCompletion)
        template_completer.setFilterMode(Qt.MatchContains)
        template_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.template_combo.setCompleter(template_completer)

        # Hint shown when template list is empty
        self.no_templates_hint = QLabel(self.tr(self.language, "no_templates_hint"))
        self.no_templates_hint.setObjectName("subtitle")

        # Character selector — shopping only
        self.char_input = QComboBox()
        self.char_input.setObjectName("priorityInput")
        self.char_input.setMinimumWidth(110)
        # Real bug found + fixed (GitHub issue #2, 2026-09-04: the "leer"
        # placeholder was untranslated German even in English, and relying
        # on setPlaceholderText()+currentIndex(-1) instead of a real,
        # selectable first row rendered a stray half-height blank row above
        # the real character list). "Unassigned" is now item 0, always
        # present and selectable (no setPlaceholderText/-1 index needed at
        # all) -- see _rebuild_char_input(). Character CREATION itself
        # doesn't live here (User-correction, 2026-09-04: this row is
        # earmarked to become the "Standard Templates" picker later, per
        # GitHub issue #2 -- adding a character doesn't belong on it) --
        # that now happens via a dedicated "Character" tab in the Templates
        # dialog instead (TemplateDialog._make_character_tab).
        self._rebuild_char_input([])

        # Legacy fields kept for serialize/deserialize compatibility but hidden
        self.location_input = QLineEdit()
        self.price_input = QLineEdit()
        self.currency_kinah_btn = QPushButton("Kinah")
        self.currency_kinah_btn.setObjectName("currencyToggleKinah")
        self.currency_kinah_btn.setCheckable(True)
        self.currency_kinah_btn.setChecked(True)
        self.currency_abyss_btn = QPushButton("AP")
        self.currency_abyss_btn.setObjectName("currencyToggleAbyss")
        self.currency_abyss_btn.setCheckable(True)
        self.currency_nightmare_btn = QPushButton("NP")
        self.currency_nightmare_btn.setObjectName("currencyToggleAbyss")
        self.currency_nightmare_btn.setCheckable(True)
        self.currency_shugo_btn = QPushButton("SC")
        self.currency_shugo_btn.setObjectName("currencyToggleAbyss")
        self.currency_shugo_btn.setCheckable(True)
        self._currency_btn_group = QButtonGroup(self)
        self._currency_btn_group.setExclusive(True)
        self._currency_btn_group.addButton(self.currency_kinah_btn)
        self._currency_btn_group.addButton(self.currency_abyss_btn)
        self._currency_btn_group.addButton(self.currency_nightmare_btn)
        self._currency_btn_group.addButton(self.currency_shugo_btn)

        self.add_btn = QPushButton(self.tr(self.language, "add"))
        self.add_btn.setObjectName("primaryButton")

        self.desc_input.returnPressed.connect(self.emit_add_task)
        self.add_btn.clicked.connect(self.emit_add_task)

        # Layout order
        add_layout.addWidget(self.event_input)
        add_layout.addWidget(self.schedule_daily_btn)
        add_layout.addWidget(self.schedule_weekly_btn)
        add_layout.addWidget(self.schedule_season_btn)
        add_layout.addWidget(self.priority_input, 2)
        add_layout.addWidget(self.title_input, 3)
        add_layout.addWidget(self.desc_input, 4)
        add_layout.addWidget(self.template_combo, 3)
        add_layout.addWidget(self.no_templates_hint)
        add_layout.addWidget(self.char_input, 2)
        add_layout.addWidget(self.amount_input)

        # Hidden by default
        self.location_input.hide()
        self.price_input.hide()
        self.currency_kinah_btn.hide()
        self.currency_abyss_btn.hide()
        self.currency_nightmare_btn.hide()
        self.currency_shugo_btn.hide()
        self.template_combo.hide()
        self.no_templates_hint.hide()
        self.amount_input.hide()
        self.char_input.hide()
        self.schedule_daily_btn.hide()
        self.schedule_weekly_btn.hide()
        self.schedule_season_btn.hide()

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

        self.filter_all_btn = QPushButton(self.tr(self.language, "filter_by_all"))
        self.filter_all_btn.setObjectName("filterButton")
        self.filter_all_btn.clicked.connect(lambda: self.set_filter("all"))
        self.filter_all_btn.setProperty("active", True)

        self.filter_event_btn = QPushButton(self.tr(self.language, "filter_by_events"))
        self.filter_event_btn.setObjectName("filterButton")
        self.filter_event_btn.clicked.connect(lambda: self.set_filter("event"))

        self.filter_daily_btn = QPushButton("Daily")
        self.filter_daily_btn.setObjectName("filterButton")
        self.filter_daily_btn.clicked.connect(lambda: self.set_filter("daily"))

        self.filter_weekly_btn = QPushButton("Weekly")
        self.filter_weekly_btn.setObjectName("filterButton")
        self.filter_weekly_btn.clicked.connect(lambda: self.set_filter("weekly"))

        self.filter_season_btn = QPushButton("Season")
        self.filter_season_btn.setObjectName("filterButton")
        self.filter_season_btn.clicked.connect(lambda: self.set_filter("season"))

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
        self.sort_row.addWidget(self.filter_daily_btn)
        self.sort_row.addWidget(self.filter_weekly_btn)
        self.sort_row.addWidget(self.filter_season_btn)

        self.sort_row.addStretch()

        # User-Wunsch, 2026-09-04: opens the same Roster-Grid layout
        # discussed as a browser mockup, now over the real current tasks/
        # shopping data (MainWindow._on_full_view_requested). Placed here,
        # in the empty space right of the filter pills -- "nimm bitte
        # diesen Platz" (screenshot pointed at exactly this spot).
        self._full_view_btn = QPushButton(self.tr(self.language, "full_view_btn"))
        self._full_view_btn.setObjectName("templateButton")
        self._full_view_btn.setCursor(Qt.PointingHandCursor)
        self._full_view_btn.clicked.connect(self.full_view_requested.emit)
        self.sort_row.addWidget(self._full_view_btn)

        # Native counterpart to Full View's CSV/Excel export (User-Wunsch,
        # 2026-09-05: "Kann man hier auch ein Import Button einfügen mit
        # Vorschau?") -- Sync can't happen from the exported browser page
        # itself (a static file:// page has no channel back into this
        # running app), so this opens a real in-app dialog instead: pick
        # the (possibly Excel-edited) CSV/XLSX file, preview it, Sync
        # writes straight into the real profile. See
        # MainWindow._open_full_view_import.
        self._import_btn = QPushButton(self.tr(self.language, "full_view_import_btn"))
        self._import_btn.setObjectName("templateButton")
        self._import_btn.setCursor(Qt.PointingHandCursor)
        self._import_btn.clicked.connect(self.import_requested.emit)
        self.sort_row.addWidget(self._import_btn)

        self._reset_hint_label = QLabel()
        self._reset_hint_label.setObjectName("resetHintLabel")
        self._reset_hint_label.setVisible(False)
        self.sort_row.addWidget(self._reset_hint_label)

        self._manual_reset_btn = QPushButton("↺")
        self._manual_reset_btn.setObjectName("ManualResetBtn")
        self._manual_reset_btn.setFixedSize(26, 26)
        self._manual_reset_btn.setToolTip(self.tr(self.language, "manual_reset_tooltip"))
        self._manual_reset_btn.setVisible(False)
        self._manual_reset_btn.clicked.connect(self.manual_reset_requested.emit)
        self.sort_row.addWidget(self._manual_reset_btn)

        layout.addLayout(self.sort_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("scrollArea")
        # #scrollArea's own QSS rule (background: transparent) doesn't
        # reach the viewport -- QAbstractScrollArea's viewport paints its
        # own QPalette::Base background separately, which on a system with
        # Windows set to dark mode can show up as a plain white box (User-
        # reported, 2026-08-29) instead of picking up the app's dark theme.
        # Same fix already applied throughout ItemDatabase/app.py and
        # settings_page.py.
        scroll.viewport().setStyleSheet("background: transparent;")

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

    def _repopulate_combo(self, templates: list):
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        for tmpl in templates:
            self.template_combo.addItem(tmpl.get("title", "?"), tmpl)
        self.template_combo.setCurrentIndex(-1)
        self.template_combo.blockSignals(False)

    def update_input_mode(self):
        is_shopping = self.active_tab == "shopping"
        is_tasks = self.active_tab == "tasks"
        is_template_mode = is_shopping or is_tasks

        # Repopulate combo for the active tab
        if is_tasks:
            self._repopulate_combo(self._task_templates)
            has_templates = bool(self._task_templates)
        elif is_shopping:
            self._repopulate_combo(self._templates)
            has_templates = bool(self._templates)
        else:
            has_templates = False

        self.title_input.setVisible(not is_template_mode)
        self.desc_input.setVisible(not is_template_mode)
        self.priority_input.setVisible(True)
        self.amount_input.setVisible(is_template_mode and has_templates)
        self.char_input.setVisible(is_template_mode and has_templates)
        self.template_combo.setVisible(is_template_mode and has_templates)
        self.no_templates_hint.setVisible(is_template_mode and not has_templates)
        self.add_btn.setEnabled(not is_template_mode or has_templates)
        self.sort_price_btn.setVisible(is_shopping)
        self.sort_location_btn.setVisible(is_shopping)

        # Schedule toggle buttons in all template modes
        self.schedule_daily_btn.setVisible(is_template_mode)
        self.schedule_weekly_btn.setVisible(is_template_mode)
        self.schedule_season_btn.setVisible(is_template_mode)

        # Event checkbox only for legacy non-template tabs
        self.event_input.setVisible(not is_template_mode and self._show_events)

        # Filter buttons: schedule for template modes, event for legacy tabs
        self.filter_event_btn.setVisible(not is_template_mode and self._show_events)
        self.filter_daily_btn.setVisible(is_template_mode)
        self.filter_weekly_btn.setVisible(is_template_mode)
        self.filter_season_btn.setVisible(is_template_mode)

        # Template/Character buttons for both shopping and tasks
        self._template_btn.setVisible(is_template_mode)
        self._character_btn.setVisible(is_template_mode)

    def set_reset_hint(self, prefix: str, countdown: str, visible: bool):
        if visible:
            self._reset_hint_label.setText(
                f'<span style="color:#64748b;font-weight:500;">{prefix}</span>'
                f' <span style="color:#22d3ee;font-weight:700;">{countdown}</span>'
            )
        self._reset_hint_label.setVisible(visible)
        self._manual_reset_btn.setVisible(visible)

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

        self._template_btn.setText(self.tr(self.language, "templates_btn"))
        self._character_btn.setText(self.tr(self.language, "tab_character"))
        self._full_view_btn.setText(self.tr(self.language, "full_view_btn"))
        self._import_btn.setText(self.tr(self.language, "full_view_import_btn"))
        self.template_combo.lineEdit().setPlaceholderText(self.tr(self.language, "template_placeholder"))
        self.no_templates_hint.setText(self.tr(self.language, "no_templates_hint"))
        self._manual_reset_btn.setToolTip(self.tr(self.language, "manual_reset_tooltip"))

        self.progress_bar.update_language(language, self.tr)

    def update_stats(self, total: int, done: int, open_count: int):
        self.progress_bar.update_stats(total, done, open_count)

    def emit_add_task(self):
        if self.active_tab == "shopping":
            tmpl = self.template_combo.currentData()
            if tmpl is None:
                return
            data = {
                "schedule": self.get_selected_schedule(),
                "priority": self.priority_input.currentData(),
                "amount": self.amount_input.text().strip() or "1",
                "title": tmpl.get("title", ""),
                "location": tmpl.get("location", ""),
                "price": tmpl.get("price", "0"),
                "currency": tmpl.get("currency", "kinah"),
                "character": self.char_input.currentData() or "",
                "template_id": tmpl.get("id", ""),
            }
        elif self.active_tab == "tasks":
            tmpl = self.template_combo.currentData()
            if tmpl is None:
                return
            data = {
                "schedule": self.get_selected_schedule(),
                "priority": self.priority_input.currentData(),
                "amount": self.amount_input.text().strip() or "1",
                "title": tmpl.get("title", ""),
                "location": tmpl.get("location", ""),
                "character": self.char_input.currentData() or "",
                "template_id": tmpl.get("id", ""),
            }
        else:
            title = self.title_input.text().strip()
            if not title:
                return
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
        self.template_combo.setCurrentIndex(-1)
        self.amount_input.clear()
        self.char_input.setCurrentIndex(-1)
        self.priority_input.setCurrentIndex(1)
        self.event_input.setChecked(False)

    def get_selected_schedule(self) -> str:
        if self.schedule_weekly_btn.isChecked():
            return "weekly"
        if self.schedule_season_btn.isChecked():
            return "season"
        return "daily"

    def get_selected_currency(self) -> str:
        if self.currency_abyss_btn.isChecked():
            return "abyss"
        if self.currency_nightmare_btn.isChecked():
            return "nightmare"
        if self.currency_shugo_btn.isChecked():
            return "shugo"
        return "kinah"

    def update_templates(self, templates: list[dict]):
        self._templates = list(templates)
        if self.active_tab == "shopping":
            self.update_input_mode()

    def update_task_templates(self, templates: list[dict]):
        self._task_templates = list(templates)
        if self.active_tab == "tasks":
            self.update_input_mode()

    def update_characters(self, char_names: list[str]):
        current = self.char_input.currentData()
        self._rebuild_char_input(char_names, select_data=current)

    def _rebuild_char_input(self, char_names: list[str], select_data: str | None = None):
        """Always has a real, selectable "Unassigned" row (index 0) -- see
        the char_input setup comment in __init__ for why (fixes both the
        untranslated "leer" text and the stray blank-row rendering bug)."""
        self.char_input.blockSignals(True)
        self.char_input.clear()
        self.char_input.addItem(self.tr(self.language, "char_unassigned"), "")
        for name in char_names:
            self.char_input.addItem(name, name)
        idx = self.char_input.findData(select_data) if select_data else -1
        self.char_input.setCurrentIndex(idx if idx >= 0 else 0)
        self.char_input.blockSignals(False)

    def select_character(self, name: str):
        """Called by MainWindow right after a character was created via the
        Templates dialog's "Character" tab (GitHub issue #2: "automatically
        select that character for the task being added") -- update_characters()
        has already refreshed the item list with the new name by then."""
        idx = self.char_input.findData(name)
        if idx >= 0:
            self.char_input.setCurrentIndex(idx)


    def set_title_placeholder(self, text: str):
        self.title_input.setPlaceholderText(text)

    def render_tasks(self, tasks: list):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        for task in tasks:
            self.list_layout.insertWidget(self.list_layout.count() - 1, task)
            task.show()

    def set_event_features_visible(self, visible: bool):
        self._show_events = visible
        self.update_input_mode()
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
        filter_map = {
            "all": self.filter_all_btn,
            "event": self.filter_event_btn,
            "daily": self.filter_daily_btn,
            "weekly": self.filter_weekly_btn,
            "season": self.filter_season_btn,
        }
        for key, btn in filter_map.items():
            btn.setProperty("active", self.active_filter == key)
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