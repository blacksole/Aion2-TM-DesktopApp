from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QScrollArea,
    QComboBox, QCheckBox, QButtonGroup, QCompleter, QMenu
)
from PySide6.QtCore import Signal, QRect, Qt
from PySide6.QtGui import QIntValidator, QPainter, QColor, QLinearGradient, QBrush, QActionGroup

from ui.widgets.empty_state import EmptyStateWidget

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

        self._done_val   = QLabel("0")
        self._open_val   = QLabel("0")
        self._missed_val = QLabel("0")
        self._total_val  = QLabel("0")
        self._pct_val    = QLabel("0%")
        self._extra_lbl = QLabel("")
        self._extra_lbl.setObjectName("ProgressExtra")

        self._sub_labels = []
        # Missed reuses the SAME "still-incomplete daily card at the last
        # reset" rule the exported Full View page's own "Missed (Yesterday)"
        # tile already tracks (MainWindow._record_missed_daily_activities)
        # (User-Wunsch, 2026-09-07: "Genauso die Regel dahinter bauen") --
        # just surfaced live in the app itself now too, not only on export.
        for val, icon, label, val_obj, icon_obj, sub_obj in [
            (self._done_val,   "✓", "done",      "ProgressDoneVal",   "ProgressDoneIcon",   "ProgressDoneSub"),
            (self._open_val,   "○", "remaining", "ProgressOpenVal",   "ProgressOpenIcon",   "ProgressOpenSub"),
            (self._missed_val, "!", "missed",    "ProgressMissedVal", "ProgressMissedIcon", "ProgressMissedSub"),
            (self._total_val,  "Σ", "total",     "ProgressTotalVal",  "ProgressTotalIcon",  "ProgressTotalSub"),
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

    def update_stats(self, total: int, done: int, open_count: int, missed_count: int = 0):
        self._done = done
        self._total = total
        pct = int(done / total * 100) if total > 0 else 0
        self._done_val.setText(str(done))
        self._open_val.setText(str(open_count))
        self._missed_val.setText(str(missed_count))
        self._total_val.setText(str(total))
        self._pct_val.setText(f"{pct}%")
        self.update()

    def update_language(self, language: str, tr_func):
        for sub, key in zip(self._sub_labels, ["done", "remaining", "missed", "total"]):
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
    # "+Add" while the Standards tab is active (User-Wunsch, 2026-09-09:
    # "Falls Templates bereits zugewiesen sind, sollen alle templates aus
    # dem Standard hinzugefügt werden, die nicht bereits zugewiesen sind")
    # -- carries just the target character; MainWindow owns the actual
    # "which titles does this character already have" check, since only it
    # can see the live task/shopping lists.
    standard_apply_requested = Signal(str)
    sort_requested = Signal(object)  # tab_key, sort_key
    filter_changed = Signal(str)
    char_filter_changed = Signal(str)
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
        self.active_char_filter = ""
        self._known_characters: list[str] = []
        self.active_sort = "priority"
        self.sort_direction = "desc"
        self._show_events = True
        self._rendered_count = 0

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

        # NOT added to self.tab_row -- moved up one more level, into
        # TodoTabsPage's own outer "ToDo | Timer" row instead (User-Wunsch,
        # 2026-09-05: first moved here from the Sort/Filter row where they
        # got crushed once the list had entries, then "wie wärs so" with a
        # screenshot showing them top-right next to "ToDo | Timer" --
        # TodoTabsPage reaches in for these two exactly like it already
        # does for title_label/subtitle_label, see its own docstring).
        # Built here (not in TodoTabsPage) since their signals belong to
        # THIS page -- full_view_requested/import_requested act on the
        # live task/shopping list, not the Timer page's own data.
        self._full_view_btn = QPushButton(self.tr(self.language, "full_view_btn"))
        self._full_view_btn.setObjectName("templateButton")
        self._full_view_btn.setCursor(Qt.PointingHandCursor)
        self._full_view_btn.clicked.connect(self.full_view_requested.emit)

        self._import_btn = QPushButton(self.tr(self.language, "full_view_import_btn"))
        self._import_btn.setObjectName("templateButton")
        self._import_btn.setCursor(Qt.PointingHandCursor)
        self._import_btn.clicked.connect(self.import_requested.emit)

        layout.addLayout(self.tab_row)

        self.progress_bar = TaskProgressBar()

        # "Templates" / "★ Standard Templates" source tabs, sitting flush on
        # top of the add-row (User-Wunsch, 2026-09-09, after iterating on a
        # preview: "gerne die Swap Buttons oberhalb des Feldes anbringen"
        # then converging on real folder-style tabs above the WHOLE row --
        # "wie wärs damit?"). Switching tabs only ever changes which list
        # the Template dropdown pulls from; the rest of the row keeps its
        # exact layout. Standard Template entries carry their own fixed
        # schedule/priority and never an amount at all (User-Wunsch: "dort
        # zählen die Prios nicht, sowie der Schedule" / "dürfen ... kein
        # amount haben"), so those three controls lock (disabled, shown for
        # reference only) whenever the Standards tab is active.
        self._template_source = "templates"
        self._standard_templates: dict = {"tasks": [], "shopping": []}

        self.source_tab_row = QHBoxLayout()
        self.source_tab_row.setSpacing(3)
        self.source_tab_row.setContentsMargins(18, 0, 0, 0)

        self.source_templates_btn = QPushButton(self.tr(self.language, "template_source_templates"))
        self.source_templates_btn.setObjectName("templateSourceTab")
        self.source_templates_btn.setCheckable(True)
        self.source_templates_btn.setChecked(True)
        self.source_templates_btn.setCursor(Qt.PointingHandCursor)
        self.source_templates_btn.clicked.connect(lambda: self._set_template_source("templates"))

        self.source_standards_btn = QPushButton(self.tr(self.language, "template_source_standards"))
        self.source_standards_btn.setObjectName("templateSourceTab")
        self.source_standards_btn.setCheckable(True)
        self.source_standards_btn.setCursor(Qt.PointingHandCursor)
        self.source_standards_btn.clicked.connect(lambda: self._set_template_source("standards"))

        self._source_btn_group = QButtonGroup(self)
        self._source_btn_group.setExclusive(True)
        self._source_btn_group.addButton(self.source_templates_btn)
        self._source_btn_group.addButton(self.source_standards_btn)

        self.source_tab_row.addWidget(self.source_templates_btn)
        self.source_tab_row.addWidget(self.source_standards_btn)
        self.source_tab_row.addStretch()

        add_panel = QFrame()
        add_panel.setObjectName("addPanel")

        # UX audit 2026-09-18, M1: this used to be ONE QHBoxLayout, whose
        # combined minimum (880px in EN, 931px in DE) was the single widest
        # thing on the page and forced the whole window's minimum width.
        # It is now two stacked rows: everything lives in the first one at
        # normal widths (pixel-identical to before), and the tail --
        # template / character / amount / Add -- drops to the second row
        # once one line no longer fits. See _update_add_row_wrap().
        add_panel_layout = QVBoxLayout(add_panel)
        add_panel_layout.setContentsMargins(18, 18, 18, 18)
        add_panel_layout.setSpacing(10)

        self._add_row_1 = QWidget()
        add_layout = QHBoxLayout(self._add_row_1)
        add_layout.setContentsMargins(0, 0, 0, 0)
        add_layout.setSpacing(12)

        self._add_row_2 = QWidget()
        add_row_2_layout = QHBoxLayout(self._add_row_2)
        add_row_2_layout.setContentsMargins(0, 0, 0, 0)
        add_row_2_layout.setSpacing(12)
        self._add_row_2.setVisible(False)

        add_panel_layout.addWidget(self._add_row_1)
        add_panel_layout.addWidget(self._add_row_2)

        self._add_row_primary = add_layout
        self._add_row_secondary = add_row_2_layout
        self._add_row_wrapped = False

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
        # UX audit 2026-09-18, M1: an 80px hard cap elided the placeholder
        # to "Amo…" at 1280px in EN already (DE "Anzahl"/RU
        # "Количество" are longer still). Keep it a narrow field --
        # it only ever holds up to 6 digits -- but never narrower than its
        # own placeholder.
        self.amount_input.setMinimumWidth(92)
        self.amount_input.setMaximumWidth(130)

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
        # User-Wunsch, 2026-09-17: "den Schedule anzeigen, der in den
        # Templates hinterlegt ist. Aktuell steht bei jedem Template
        # automatisch 'Daily'" -- the Daily/Weekly/Season toggle row below
        # never reflected the SELECTED template's own stored schedule, it
        # only ever kept whatever the user had last clicked (defaulting to
        # Daily), so adding e.g. a Weekly-tagged template silently added it
        # as Daily unless the user remembered to flip the toggle first.
        self.template_combo.currentIndexChanged.connect(self._on_template_selected)

        # Hint shown when template list is empty
        self.no_templates_hint = QLabel(self.tr(self.language, "no_templates_hint"))
        self.no_templates_hint.setObjectName("subtitle")

        # Character selector — shopping only
        self.char_input = QComboBox()
        self.char_input.setObjectName("priorityInput")
        self.char_input.setMinimumWidth(110)
        # UX audit 2026-09-18, M1: rendered "No charac…" at 1280px. The
        # widest entry this combo ever shows is its own "unassigned" row
        # ("No character" / "Kein Charakter" / "Без персонажа"), so size to
        # that and let a long character name grow the box instead of
        # eliding it.
        self.char_input.setMinimumContentsLength(14)
        self.char_input.setSizeAdjustPolicy(QComboBox.AdjustToContents)
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

        # (widget, stretch) in the order they must reappear -- moved as a
        # block between the two rows by _update_add_row_wrap().
        self._add_row_tail = [
            (self.template_combo, 3),
            (self.no_templates_hint, 0),
            (self.char_input, 2),
            (self.amount_input, 0),
            (self.add_btn, 0),
        ]

        # Tight spacing here (unlike the page's own 22px section spacing)
        # so the source tabs sit visually flush on top of add_panel, like a
        # real folder-tab flap, instead of floating a whole section above it.
        add_section = QWidget()
        add_section_layout = QVBoxLayout(add_section)
        add_section_layout.setContentsMargins(0, 0, 0, 0)
        add_section_layout.setSpacing(0)
        add_section_layout.addLayout(self.source_tab_row)
        add_section_layout.addWidget(add_panel)

        layout.addWidget(self.progress_bar)
        layout.addWidget(add_section)

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

        # Character filter (User-Wunsch, 2026-09-16: "beim ToDo wär es nice
        # wie im Overlay auch einen Char auswählen zu können, dass alle
        # ToDos zu einem Char nur angezeigt werden ... rechts vom Filter by")
        # -- same popover-menu pattern as OverlayWindow's own char filter
        # (_show_char_popover/_on_char_filter_selected), a single-choice
        # "selection filter" rather than another row of exclusive pill
        # buttons, since the character list is open-ended/variable-length.
        self.char_filter_btn = QPushButton()
        self.char_filter_btn.setObjectName("filterButton")
        self.char_filter_btn.clicked.connect(self._show_char_filter_popover)
        self._update_char_filter_btn_label()

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
        self.sort_row.addSpacing(8)
        self.sort_row.addWidget(self.char_filter_btn)

        self.sort_row.addStretch()

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

        self._list_scroll = scroll
        layout.addWidget(scroll, 1)

        # UX audit 2026-09-18, M2: a Tasks/Shopping tab with zero cards used
        # to render as a bare void. The placeholder replaces the (equally
        # empty) scroll area rather than sitting under it, so it can center
        # itself over the full remaining height.
        self.empty_state = EmptyStateWidget()
        layout.addWidget(self.empty_state, 1)

        self.update_input_mode()


    # add_panel's own left+right content margins, subtracted from the page
    # width to get what the add-row actually has to lay out in.
    _ADD_PANEL_CHROME = 36
    # Slack the row must regain before it un-wraps, so a width that lands
    # exactly on the one-line minimum cannot oscillate between the two
    # states on consecutive resize events.
    _ADD_ROW_WRAP_HYSTERESIS = 24

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_add_row_wrap()

    def _update_add_row_wrap(self):
        """Moves template/character/amount/Add between the add-panel's two
        rows (UX audit 2026-09-18, M1).

        The threshold is measured, not hardcoded: the width one line would
        need is the primary row's minimum plus -- while already wrapped --
        the secondary row's. That keeps it correct per language (DE/RU run
        20-35% wider) and per tab, since update_input_mode() hides a
        different set of controls on each.
        """
        available = self.width() - self._ADD_PANEL_CHROME
        one_line_needs = self._add_row_primary.minimumSize().width()
        if self._add_row_wrapped:
            one_line_needs += (
                self._add_row_primary.spacing()
                + self._add_row_secondary.minimumSize().width()
            )
            wrapped = available < one_line_needs + self._ADD_ROW_WRAP_HYSTERESIS
        else:
            wrapped = available < one_line_needs

        if wrapped == self._add_row_wrapped:
            return
        self._add_row_wrapped = wrapped

        if wrapped:
            src, dst = self._add_row_primary, self._add_row_secondary
        else:
            src, dst = self._add_row_secondary, self._add_row_primary

        for widget, stretch in self._add_row_tail:
            # addWidget() reparents, and Qt hides a reparented widget --
            # so each one's own explicit hidden/shown state (set by
            # update_input_mode() for this tab and template source) has to
            # be carried across by hand.
            was_hidden = widget.isHidden()
            src.removeWidget(widget)
            dst.addWidget(widget, stretch)
            widget.setVisible(not was_hidden)

        self._add_row_2.setVisible(wrapped)

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

    def _repopulate_combo(self, templates: list, placeholder: str):
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        for tmpl in templates:
            self.template_combo.addItem(tmpl.get("title", "?"), tmpl)
        self.template_combo.setCurrentIndex(-1)
        self.template_combo.blockSignals(False)
        self.template_combo.lineEdit().setPlaceholderText(placeholder)

    def _set_template_source(self, source: str):
        """Swaps the Template dropdown between the normal catalog and
        Standard Templates (User-Wunsch, 2026-09-09, after a preview
        iteration converged on real folder tabs above the add-row: "so
        bitte übernehmen"). See update_input_mode() for the locking of
        Schedule/Priority/Amount that goes along with the Standards side."""
        if source == self._template_source:
            return
        self._template_source = source
        self.update_input_mode()

    def update_input_mode(self):
        is_shopping = self.active_tab == "shopping"
        is_tasks = self.active_tab == "tasks"
        is_template_mode = is_shopping or is_tasks
        is_standards = self._template_source == "standards"

        # Repopulate combo for the active tab + source
        if is_tasks:
            source_list = self._standard_templates.get("tasks", []) if is_standards else self._task_templates
        elif is_shopping:
            source_list = self._standard_templates.get("shopping", []) if is_standards else self._templates
        else:
            source_list = []

        if is_template_mode:
            placeholder_key = "standard_template_placeholder" if is_standards else "template_placeholder"
            self._repopulate_combo(source_list, self.tr(self.language, placeholder_key))
        has_templates = bool(source_list) if is_template_mode else False

        self.title_input.setVisible(not is_template_mode)
        self.desc_input.setVisible(not is_template_mode)
        self.priority_input.setVisible(not (is_template_mode and is_standards))
        self.amount_input.setVisible(is_template_mode and has_templates and not is_standards)
        self.char_input.setVisible(is_template_mode and has_templates)
        self.template_combo.setVisible(is_template_mode and has_templates and not is_standards)

        # Standard Template entries carry their OWN fixed schedule/priority
        # and never an amount at all (User-Wunsch: "dort zählen die Prios
        # nicht, sowie der Schedule" / "dürfen ... kein amount haben"), and
        # "+Add" no longer needs a picked entry either (User-Wunsch: bulk-
        # add every not-yet-assigned Standard Template instead) -- so none
        # of Schedule/Priority/Amount/Template mean anything on this tab;
        # hide them outright rather than showing a locked, meaningless value.
        self.schedule_daily_btn.setVisible(is_template_mode and not is_standards)
        self.schedule_weekly_btn.setVisible(is_template_mode and not is_standards)
        self.schedule_season_btn.setVisible(is_template_mode and not is_standards)
        if is_standards:
            self.amount_input.clear()

        self.source_templates_btn.setVisible(is_template_mode)
        self.source_standards_btn.setVisible(is_template_mode)
        self.no_templates_hint.setVisible(is_template_mode and not has_templates)
        self.add_btn.setEnabled(not is_template_mode or has_templates)
        self.sort_price_btn.setVisible(is_shopping)
        self.sort_location_btn.setVisible(is_shopping)

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

        # This just changed how wide one line would have to be.
        self._update_add_row_wrap()

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

        self._update_char_filter_btn_label()

        # Re-pins the character combo's minimum width to the new locale's
        # "unassigned" label (see _rebuild_char_input) -- and translates
        # that row, which a plain text refresh cannot do since it is a
        # combo item, not a placeholder.
        self._rebuild_char_input(
            self._known_characters, select_data=self.char_input.currentData()
        )

        self.event_input.setText(
            self.tr(self.language, "filter_by_events")
        )

        self._template_btn.setText(self.tr(self.language, "templates_btn"))
        self._character_btn.setText(self.tr(self.language, "tab_character"))
        self._full_view_btn.setText(self.tr(self.language, "full_view_btn"))
        self._import_btn.setText(self.tr(self.language, "full_view_import_btn"))
        self.source_templates_btn.setText(self.tr(self.language, "template_source_templates"))
        self.source_standards_btn.setText(self.tr(self.language, "template_source_standards"))
        placeholder_key = "standard_template_placeholder" if self._template_source == "standards" else "template_placeholder"
        self.template_combo.lineEdit().setPlaceholderText(self.tr(self.language, placeholder_key))
        self.no_templates_hint.setText(self.tr(self.language, "no_templates_hint"))
        self._manual_reset_btn.setToolTip(self.tr(self.language, "manual_reset_tooltip"))

        self.progress_bar.update_language(language, self.tr)

        # isHidden(), not isVisible(): the page is a descendant of a
        # MainWindow that may not be shown yet when the language is applied.
        if not self.empty_state.isHidden():
            self._retranslate_empty_state()

    def update_stats(self, total: int, done: int, open_count: int, missed_count: int = 0):
        self.progress_bar.update_stats(total, done, open_count, missed_count)

    def emit_add_task(self):
        # Standards tab: no picker required at all -- "+Add" bulk-applies
        # every not-yet-assigned Standard Template to the selected character
        # in one go (User-Wunsch, 2026-09-09: "Falls Templates bereits
        # zugewiesen sind, sollen alle templates aus dem Standard
        # hinzugefügt werden, die nicht bereits zugewiesen sind"). MainWindow
        # does the actual per-title dedup since only it can see the live
        # task/shopping lists.
        if self._template_source == "standards":
            character = self.char_input.currentData() or ""
            self.standard_apply_requested.emit(character)
            self.char_input.setCurrentIndex(0)
            return

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

    def _on_template_selected(self, index: int):
        """Syncs the Daily/Weekly/Season toggle row and the Priority
        dropdown to whichever schedule/priority the just-picked template
        actually carries, instead of leaving them on whatever was last
        set (see the connection site's own comment for the full "always
        showed Daily" bug this fixes, extended the same way for Priority
        per user request)."""
        tmpl = self.template_combo.currentData()
        if tmpl is None:
            return
        schedule = tmpl.get("schedule", "daily")
        if schedule == "weekly":
            self.schedule_weekly_btn.setChecked(True)
        elif schedule == "season":
            self.schedule_season_btn.setChecked(True)
        else:
            self.schedule_daily_btn.setChecked(True)

        priority = tmpl.get("priority", "middle")
        prio_index = self.priority_input.findData(priority)
        if prio_index >= 0:
            self.priority_input.setCurrentIndex(prio_index)

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

    def update_standard_templates(self, standard_templates: dict):
        self._standard_templates = standard_templates or {"tasks": [], "shopping": []}
        if self._template_source == "standards":
            self.update_input_mode()

    def update_characters(self, char_names: list[str]):
        current = self.char_input.currentData()
        self._rebuild_char_input(char_names, select_data=current)
        self._known_characters = list(char_names)

    def _update_char_filter_btn_label(self):
        self.char_filter_btn.setText(
            self.active_char_filter or self.tr(self.language, "todo_char_filter_btn")
        )

    def _show_char_filter_popover(self):
        menu = QMenu(self)
        # QMenu is a real top-level popup, not a normal cascading child --
        # it does NOT reliably inherit MainWindow's setStyleSheet() the way
        # a plain child widget would (User-reported, 2026-09-16, screenshot:
        # rendered in the plain light native menu style instead of this
        # app's dark theme, even though a global unscoped "QMenu {...}" rule
        # already exists in styles.qss). Setting it explicitly here
        # guarantees it regardless of that cascade gap -- same colors as
        # that global rule.
        # Same palette as OverlayWindow's own character-filter menu (this
        # feature's own direct inspiration) instead of the plain square
        # global QMenu colors (User-Wunsch, 2026-09-16: "den Stil von dem
        # kantigen Dropdown anpassen") -- rounded corners, softer border,
        # rounded item highlight on hover/selection to match the rest of
        # this app's pill/rounded-card look instead of sharp edges.
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(14, 16, 24, 0.98);
                color: #e5e7eb;
                border: 1px solid rgba(100, 116, 139, 0.35);
                border-radius: 10px;
                padding: 6px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: rgba(255, 255, 255, 0.08);
            }
            QMenu::separator {
                height: 1px;
                background: rgba(100, 116, 139, 0.35);
                margin: 6px 8px;
            }
        """)
        group = QActionGroup(menu)
        group.setExclusive(True)

        all_action = menu.addAction(self.tr(self.language, "todo_char_filter_all"))
        all_action.setCheckable(True)
        all_action.setChecked(self.active_char_filter == "")
        all_action.triggered.connect(lambda: self._on_char_filter_selected(""))
        group.addAction(all_action)

        for name in self._known_characters:
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name == self.active_char_filter)
            action.triggered.connect(lambda _c=False, n=name: self._on_char_filter_selected(n))
            group.addAction(action)

        menu.exec(self.char_filter_btn.mapToGlobal(self.char_filter_btn.rect().bottomLeft()))

    def _on_char_filter_selected(self, name: str):
        self.set_char_filter_value(name)
        self.char_filter_changed.emit(name)

    def set_char_filter_value(self, name: str):
        """Also called by MainWindow right after a profile loads, to push
        the persisted filter back into this button without re-emitting
        char_filter_changed (which would otherwise immediately re-trigger
        MainWindow.set_task_char_filter and re-save the profile it just
        finished loading)."""
        self.active_char_filter = name
        self._update_char_filter_btn_label()

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

        # UX audit 2026-09-18, M1: setMinimumContentsLength alone only
        # feeds minimumSizeHint(), and QComboBox's default size policy
        # carries the Shrink flag -- so the add-row happily squeezed this
        # combo down to its explicit 110px minimum and Qt elided the label
        # to "No charac...". Pinning the explicit minimum to that hint is
        # what actually holds the width; re-done here rather than once in
        # __init__ because the hint moves with the language ("No character"
        # / "Kein Charakter" / "Bez personazha").
        self.char_input.setMinimumWidth(
            max(110, self.char_input.minimumSizeHint().width())
        )

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
        # Real bug found + fixed (User-reported, 2026-09-09, screenshots:
        # stray top-level "python3" windows appeared -- each showing a
        # single leftover card -- right when switching the Tasks/Shopping
        # tab). setParent(None) alone only detaches a widget from its
        # layout; it does NOT hide it. A widget that was already visible
        # right before losing its parent gets promoted by Qt into its own
        # real top-level window instead of just disappearing. NOT
        # deleteLater() here -- these TaskCard/ShoppingCard objects are the
        # SAME long-lived instances kept in MainWindow.task_lists and get
        # re-inserted (possibly this very same call, if `tasks` still
        # includes them) below; deleting them would break them on the very
        # next refresh() instead of just re-parenting them.
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)

        for task in tasks:
            self.list_layout.insertWidget(self.list_layout.count() - 1, task)
            task.show()

        self._rendered_count = len(tasks)
        self.update_empty_state()

    # ── Empty state (UX audit 2026-09-18, M2) ─────────────────────────────

    def update_empty_state(self):
        """Shows the placeholder whenever the ACTIVE tab rendered zero
        cards, and swaps the (then pointless) scroll area out for it.

        Public on purpose: ``render_tasks`` -- the one call MainWindow
        already makes on every ``refresh()`` -- drives it automatically, so
        MainWindow needs no change; any other owner that mutates the list
        outside a refresh can call this directly.
        """
        is_empty = self._rendered_count == 0 and self.active_tab in ("tasks", "shopping")
        if is_empty:
            self._retranslate_empty_state()
        self.empty_state.setVisible(is_empty)
        self._list_scroll.setVisible(not is_empty)

    def _retranslate_empty_state(self):
        """Feeds the placeholder the copy for whichever tab is active.

        The action is the one thing the user can actually do next: Shopping
        entries only ever come from a template (the add-row is a picker, not
        a free-text field), so its button opens the Templates dialog via the
        page's existing ``template_requested`` signal; Tasks focuses its own
        add-row picker instead -- unless there is no template to pick yet,
        in which case it falls back to the same Templates dialog.
        """
        if self.active_tab == "shopping":
            title_key, hint_key = "empty_shopping_title", "empty_shopping_hint"
            action_label = self.tr(self.language, "templates_btn")
            on_action = self.template_requested.emit
        else:
            title_key, hint_key = "empty_tasks_title", "empty_tasks_hint"
            if self._add_row_target() is None:
                # No template for this tab yet -- the add-row itself is
                # inert (it only shows "No templates ..."), so the only
                # move left is the same one Shopping offers.
                action_label = self.tr(self.language, "templates_btn")
                on_action = self.template_requested.emit
            else:
                action_label = self.tr(self.language, "add")
                on_action = self._focus_add_row

        # tr() falls back to the raw key for a key that does not exist yet
        # (core.translations.tr: ``.get(key, key)``), which would print
        # "empty_tasks_title" on screen -- so drop the hint and keep a
        # neutral title until the keys land.
        title = self.tr(self.language, title_key)
        hint = self.tr(self.language, hint_key)
        if title == title_key:
            title = self.tr(self.language, "no_templates_hint")
        if hint == hint_key:
            hint = ""

        self.empty_state.set_content(title, hint, action_label, on_action)

    def _add_row_target(self):
        """Where a new Tasks entry actually starts: the template picker in
        template mode, the free-text title on the legacy tabs -- whichever
        of the two update_input_mode() left on screen, or None when neither
        is (which is the "no templates at all" state)."""
        for candidate in (self.template_combo, self.title_input):
            if not candidate.isHidden():
                return candidate
        return None

    def _focus_add_row(self):
        target = self._add_row_target()
        if target is not None:
            target.setFocus()

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