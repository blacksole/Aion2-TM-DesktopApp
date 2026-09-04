from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QCheckBox,
    QScrollArea,
    QTabWidget,
    QWidget,
    QDialog,
    QButtonGroup,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QIntValidator

_MAX_CHARACTERS = 8

_SCHED_NAMES = {"daily": "scheduleDaily", "weekly": "scheduleWeekly", "season": "scheduleSeason"}
_PRIO_NAMES  = {"low": "priorityToggleLow", "middle": "priorityToggleMiddle", "high": "priorityToggleHigh"}


# ── Item List Popup ───────────────────────────────────────────────────────────

class _NodeItemListDialog(QDialog):
    def __init__(self, items: list, shopping_templates: list,
                 task_templates: list = None, parent=None, item_picker_callback=None):
        super().__init__(parent)
        self.setWindowTitle("Liste bearbeiten")
        self.setModal(True)
        self.setFixedWidth(520)
        self.setMinimumHeight(540)
        self.resize(520, 680)

        # Separate items by type; old items without a type are shopping
        self._shopping_items = [dict(i) for i in items if i.get("type", "shopping") != "task"]
        self._task_items = [dict(i) for i in items if i.get("type") == "task"]
        self._shopping_templates = shopping_templates or []
        self._task_templates = task_templates or []
        # Opens the REAL Item Database catalog picker (icons, search,
        # shop-type sidebar) via MainWindow.open_template_item_picker --
        # same bridge Templates' own "Import from Database" link already
        # uses, since only the host app knows how to lazily load the
        # ItemDatabase module (User-Wunsch, 2026-09-04: "die Möglichkeit,
        # Items aus der Datenbank auszuwählen ... ein Toggle oder Button
        # zum switchen"). None if not supplied -> the toggle simply stays
        # hidden (e.g. if ever opened in a context without MainWindow).
        self._item_picker_callback = item_picker_callback
        # Each picked catalog item becomes a template-shaped dict (title
        # only, matching how "Import from Database" already only fills the
        # Title field elsewhere -- a catalog item has no location/price/
        # schedule/priority of its own) appended here, kept separate from
        # the real saved Shopping/Task templates.
        self._shop_db_picks: list[dict] = []
        self._task_db_picks: list[dict] = []
        self._shop_source = "templates"
        self._task_source = "templates"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(12)

        title_lbl = QLabel("Liste bearbeiten")
        title_lbl.setObjectName("PanelTitle")
        layout.addWidget(title_lbl)

        tab_widget = QTabWidget()
        tab_widget.addTab(self._make_shopping_tab(), "🛒 Einkauf")
        tab_widget.addTab(self._make_tasks_tab(), "📋 Aufgaben")
        layout.addWidget(tab_widget, 1)

        close_btn = QPushButton("Schließen")
        close_btn.setObjectName("FlowCancelButton")
        close_btn.setFixedHeight(40)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    # ── Tab builders ──────────────────────────────────────────────────────────

    def _make_shopping_tab(self) -> QWidget:
        widget = QWidget()
        vl = QVBoxLayout(widget)
        vl.setContentsMargins(0, 8, 0, 0)
        vl.setSpacing(8)

        add_frame = QFrame()
        add_frame.setObjectName("settingsRow")
        add_layout = QVBoxLayout(add_frame)
        add_layout.setContentsMargins(14, 12, 14, 12)
        add_layout.setSpacing(8)

        # Templates vs. real Item Database as the picker table's source
        # (User-Wunsch, 2026-09-04: "die Möglichkeit, Items aus der
        # Datenbank auszuwählen, hier gerne ein Toggle oder Button zum
        # switchen") -- hidden entirely if no bridge into the Item
        # Database was supplied (e.g. this dialog opened without a
        # MainWindow ancestor to reach the callback through).
        if self._item_picker_callback:
            source_row = QHBoxLayout()
            source_row.setSpacing(6)
            self._shop_source_group = QButtonGroup(self)
            self._shop_source_group.setExclusive(True)
            shop_tmpl_btn = self._make_toggle("Vorlagen", "priorityToggleLow", self._shop_source_group)
            shop_tmpl_btn.setChecked(True)
            shop_db_btn = self._make_toggle("Datenbank", "priorityToggleMiddle", self._shop_source_group)
            shop_tmpl_btn.clicked.connect(lambda: self._on_shop_source_changed("templates"))
            shop_db_btn.clicked.connect(lambda: self._on_shop_source_changed("database"))
            source_row.addWidget(shop_tmpl_btn)
            source_row.addWidget(shop_db_btn)
            source_row.addStretch()
            pick_btn = QPushButton("+ Aus Datenbank wählen")
            pick_btn.setObjectName("secondaryButton")
            pick_btn.setCursor(Qt.PointingHandCursor)
            pick_btn.clicked.connect(self._pick_shop_item_from_db)
            source_row.addWidget(pick_btn)
            add_layout.addLayout(source_row)

        # Searchable, checkbox-driven picker table instead of a single
        # flat dropdown (User-Wunsch, 2026-09-04: "einen ähnlichen Aufbau
        # wie die Database und dann eine extra Spalte, in der man Haken
        # setzen kann") -- several templates can be checked and added in
        # one go, each with its OWN Amount (confirmed via question:
        # per-row, since you rarely want the same quantity of everything),
        # while Priority/Schedule below stay one shared choice for the
        # whole batch (also confirmed).
        self._shop_picker_search = QLineEdit()
        self._shop_picker_search.setObjectName("FlowInput")
        self._shop_picker_search.setPlaceholderText("Suchen…")
        self._shop_picker_search.textChanged.connect(self._refresh_shop_picker_table)
        self._shop_picker_rows: list[tuple] = []
        self._shop_picker_table = self._make_picker_table(has_price=True)
        add_layout.addWidget(self._shop_picker_search)
        add_layout.addWidget(self._shop_picker_table)
        self._refresh_shop_picker_table()

        self._shop_prio_group = QButtonGroup(self)
        self._shop_prio_group.setExclusive(True)
        self._shop_prio_low  = self._make_toggle("Low",    "priorityToggleLow",    self._shop_prio_group)
        self._shop_prio_mid  = self._make_toggle("Middle", "priorityToggleMiddle", self._shop_prio_group)
        self._shop_prio_high = self._make_toggle("High",   "priorityToggleHigh",   self._shop_prio_group)
        self._shop_prio_low.setChecked(True)
        prio_row = QHBoxLayout()
        prio_row.addWidget(QLabel("Priorität:"))
        for b in (self._shop_prio_low, self._shop_prio_mid, self._shop_prio_high):
            prio_row.addWidget(b)
        prio_row.addStretch()

        self._shop_sched_group = QButtonGroup(self)
        self._shop_sched_group.setExclusive(True)
        self._shop_sched_daily  = self._make_toggle("Daily",  "scheduleToggleBtn", self._shop_sched_group)
        self._shop_sched_weekly = self._make_toggle("Weekly", "scheduleToggleBtn", self._shop_sched_group)
        self._shop_sched_season = self._make_toggle("Season", "scheduleToggleBtn", self._shop_sched_group)
        self._shop_sched_daily.setChecked(True)
        sched_row = QHBoxLayout()
        sched_row.addWidget(QLabel("Schedule:"))
        for b in (self._shop_sched_daily, self._shop_sched_weekly, self._shop_sched_season):
            sched_row.addWidget(b)
        sched_row.addStretch()

        shop_add_btn = QPushButton("+ Hinzufügen")
        shop_add_btn.setObjectName("primaryButton")
        shop_add_btn.setFixedHeight(34)
        shop_add_btn.setCursor(Qt.PointingHandCursor)
        shop_add_btn.clicked.connect(self._add_shopping_item)
        if not self._shopping_templates:
            shop_add_btn.setEnabled(False)

        add_layout.addLayout(prio_row)
        add_layout.addLayout(sched_row)
        add_layout.addWidget(shop_add_btn)
        vl.addWidget(add_frame)

        self._shop_list_container = QWidget()
        self._shop_list_layout = QVBoxLayout(self._shop_list_container)
        self._shop_list_layout.setContentsMargins(0, 0, 0, 0)
        self._shop_list_layout.setSpacing(4)
        self._shop_list_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self._shop_list_container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Viewport paints its own background separately from the outer
        # widget's QSS -- shows as a plain white/grey box when Windows
        # itself is set to dark mode (User-reported, 2026-08-29).
        scroll.viewport().setStyleSheet("background: transparent;")

        list_frame = QFrame()
        list_frame.setObjectName("settingsRow")
        list_frame.setMinimumHeight(100)
        lf_layout = QVBoxLayout(list_frame)
        lf_layout.setContentsMargins(0, 0, 0, 0)
        lf_layout.addWidget(scroll)
        vl.addWidget(list_frame, 1)

        for item in self._shopping_items:
            self._add_shop_row(item)
        return widget

    def _make_tasks_tab(self) -> QWidget:
        widget = QWidget()
        vl = QVBoxLayout(widget)
        vl.setContentsMargins(0, 8, 0, 0)
        vl.setSpacing(8)

        add_frame = QFrame()
        add_frame.setObjectName("settingsRow")
        add_layout = QVBoxLayout(add_frame)
        add_layout.setContentsMargins(14, 12, 14, 12)
        add_layout.setSpacing(8)

        if self._item_picker_callback:
            source_row = QHBoxLayout()
            source_row.setSpacing(6)
            self._task_source_group = QButtonGroup(self)
            self._task_source_group.setExclusive(True)
            task_tmpl_btn = self._make_toggle("Vorlagen", "priorityToggleLow", self._task_source_group)
            task_tmpl_btn.setChecked(True)
            task_db_btn = self._make_toggle("Datenbank", "priorityToggleMiddle", self._task_source_group)
            task_tmpl_btn.clicked.connect(lambda: self._on_task_source_changed("templates"))
            task_db_btn.clicked.connect(lambda: self._on_task_source_changed("database"))
            source_row.addWidget(task_tmpl_btn)
            source_row.addWidget(task_db_btn)
            source_row.addStretch()
            pick_btn = QPushButton("+ Aus Datenbank wählen")
            pick_btn.setObjectName("secondaryButton")
            pick_btn.setCursor(Qt.PointingHandCursor)
            pick_btn.clicked.connect(self._pick_task_item_from_db)
            source_row.addWidget(pick_btn)
            add_layout.addLayout(source_row)

        self._task_picker_search = QLineEdit()
        self._task_picker_search.setObjectName("FlowInput")
        self._task_picker_search.setPlaceholderText("Suchen…")
        self._task_picker_search.textChanged.connect(self._refresh_task_picker_table)
        self._task_picker_rows: list[tuple] = []
        self._task_picker_table = self._make_picker_table(has_price=False)
        add_layout.addWidget(self._task_picker_search)
        add_layout.addWidget(self._task_picker_table)
        self._refresh_task_picker_table()

        self._task_prio_group = QButtonGroup(self)
        self._task_prio_group.setExclusive(True)
        self._task_prio_low  = self._make_toggle("Low",    "priorityToggleLow",    self._task_prio_group)
        self._task_prio_mid  = self._make_toggle("Middle", "priorityToggleMiddle", self._task_prio_group)
        self._task_prio_high = self._make_toggle("High",   "priorityToggleHigh",   self._task_prio_group)
        self._task_prio_low.setChecked(True)
        prio_row = QHBoxLayout()
        prio_row.addWidget(QLabel("Priorität:"))
        for b in (self._task_prio_low, self._task_prio_mid, self._task_prio_high):
            prio_row.addWidget(b)
        prio_row.addStretch()

        self._task_sched_group = QButtonGroup(self)
        self._task_sched_group.setExclusive(True)
        self._task_sched_daily  = self._make_toggle("Daily",  "scheduleToggleBtn", self._task_sched_group)
        self._task_sched_weekly = self._make_toggle("Weekly", "scheduleToggleBtn", self._task_sched_group)
        self._task_sched_season = self._make_toggle("Season", "scheduleToggleBtn", self._task_sched_group)
        self._task_sched_daily.setChecked(True)
        sched_row = QHBoxLayout()
        sched_row.addWidget(QLabel("Schedule:"))
        for b in (self._task_sched_daily, self._task_sched_weekly, self._task_sched_season):
            sched_row.addWidget(b)
        sched_row.addStretch()

        task_add_btn = QPushButton("+ Hinzufügen")
        task_add_btn.setObjectName("primaryButton")
        task_add_btn.setFixedHeight(34)
        task_add_btn.setCursor(Qt.PointingHandCursor)
        task_add_btn.clicked.connect(self._add_task_item)
        if not self._task_templates:
            task_add_btn.setEnabled(False)

        add_layout.addLayout(prio_row)
        add_layout.addLayout(sched_row)
        add_layout.addWidget(task_add_btn)
        vl.addWidget(add_frame)

        self._task_list_container = QWidget()
        self._task_list_layout = QVBoxLayout(self._task_list_container)
        self._task_list_layout.setContentsMargins(0, 0, 0, 0)
        self._task_list_layout.setSpacing(4)
        self._task_list_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self._task_list_container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Same viewport-background fix as the shop-list scroll area above
        # (User-reported Windows-dark-mode white box, 2026-08-29).
        scroll.viewport().setStyleSheet("background: transparent;")

        list_frame = QFrame()
        list_frame.setObjectName("settingsRow")
        list_frame.setMinimumHeight(100)
        lf_layout = QVBoxLayout(list_frame)
        lf_layout.setContentsMargins(0, 0, 0, 0)
        lf_layout.addWidget(scroll)
        vl.addWidget(list_frame, 1)

        for item in self._task_items:
            self._add_task_row(item)
        return widget

    # ── Template picker table (checkbox + search, "wie die Database") ────────

    @staticmethod
    def _make_picker_table(has_price: bool) -> QTableWidget:
        columns = ["", "Name", "Ort", "Preis", "Anzahl"] if has_price else ["", "Name", "Ort", "Anzahl"]
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setMaximumHeight(180)
        table.setObjectName("FlowPickerTable")
        header = table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in range(len(columns)):
            if col != 1:
                header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        return table

    def _refresh_shop_picker_table(self, _text: str = ""):
        source = self._shopping_templates if self._shop_source == "templates" else self._shop_db_picks
        self._populate_picker_table(
            self._shop_picker_table, self._shop_picker_rows, source,
            self._shop_picker_search.text(), has_price=True,
        )

    def _refresh_task_picker_table(self, _text: str = ""):
        source = self._task_templates if self._task_source == "templates" else self._task_db_picks
        self._populate_picker_table(
            self._task_picker_table, self._task_picker_rows, source,
            self._task_picker_search.text(), has_price=False,
        )

    def _on_shop_source_changed(self, source: str):
        self._shop_source = source
        self._refresh_shop_picker_table()

    def _on_task_source_changed(self, source: str):
        self._task_source = source
        self._refresh_task_picker_table()

    def _pick_shop_item_from_db(self):
        item = self._item_picker_callback(self)
        if not item:
            return
        self._shop_db_picks.append({
            "title": item.get("name", ""), "location": "", "price": "0", "currency": "kinah",
        })
        if self._shop_source != "database":
            self._shop_source_group.buttons()[1].setChecked(True)
            self._shop_source = "database"
        self._refresh_shop_picker_table()

    def _pick_task_item_from_db(self):
        item = self._item_picker_callback(self)
        if not item:
            return
        self._task_db_picks.append({"title": item.get("name", ""), "location": ""})
        if self._task_source != "database":
            self._task_source_group.buttons()[1].setChecked(True)
            self._task_source = "database"
        self._refresh_task_picker_table()

    def _populate_picker_table(
        self, table: QTableWidget, rows: list, templates: list, filter_text: str, has_price: bool,
    ):
        """Rebuilds `table` (filtered by `filter_text`) and refills `rows`
        IN PLACE (never reassigned) with (checkbox, amount_edit, tmpl) per
        visible row, so _add_shopping_item/_add_task_item -- and this same
        method on the next keystroke -- always see the current rows
        through the one list object created once in _make_*_tab."""
        table.setRowCount(0)
        rows.clear()
        needle = filter_text.strip().lower()
        for tmpl in templates:
            title = tmpl.get("title", "")
            if needle and needle not in title.lower():
                continue
            row = table.rowCount()
            table.insertRow(row)

            check = QCheckBox()
            check_wrap = QWidget()
            check_layout = QHBoxLayout(check_wrap)
            check_layout.setContentsMargins(0, 0, 0, 0)
            check_layout.setAlignment(Qt.AlignCenter)
            check_layout.addWidget(check)
            table.setCellWidget(row, 0, check_wrap)

            table.setItem(row, 1, QTableWidgetItem(title))
            table.setItem(row, 2, QTableWidgetItem(tmpl.get("location", "")))

            col = 3
            if has_price:
                price = tmpl.get("price", "0")
                currency = tmpl.get("currency", "kinah")
                table.setItem(row, col, QTableWidgetItem(f"{price} {currency}"))
                col += 1

            amount = QLineEdit("1")
            amount.setObjectName("FlowInput")
            amount.setFixedWidth(48)
            amount.setValidator(QIntValidator(1, 9999, self))
            table.setCellWidget(row, col, amount)

            rows.append((check, amount, tmpl))
        if not templates:
            table.setRowCount(1)
            table.setSpan(0, 0, 1, table.columnCount())
            placeholder = "Keine Vorlagen vorhanden" if has_price else "Keine Aufgaben-Vorlagen vorhanden"
            table.setItem(0, 0, QTableWidgetItem(placeholder))

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _make_toggle(text: str, obj_name: str, group: QButtonGroup) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName(obj_name)
        btn.setCheckable(True)
        group.addButton(btn)
        return btn

    def _shop_priority(self) -> str:
        if self._shop_prio_high.isChecked():
            return "high"
        if self._shop_prio_mid.isChecked():
            return "middle"
        return "low"

    def _shop_schedule(self) -> str:
        if self._shop_sched_weekly.isChecked():
            return "weekly"
        if self._shop_sched_season.isChecked():
            return "season"
        return "daily"

    def _task_priority(self) -> str:
        if self._task_prio_high.isChecked():
            return "high"
        if self._task_prio_mid.isChecked():
            return "middle"
        return "low"

    def _task_schedule(self) -> str:
        if self._task_sched_weekly.isChecked():
            return "weekly"
        if self._task_sched_season.isChecked():
            return "season"
        return "daily"

    # ── Add actions ───────────────────────────────────────────────────────────

    def _add_shopping_item(self):
        # Adds every CHECKED row at once, each with its own Amount but the
        # one shared Priority/Schedule choice below the table (User-
        # confirmed via question, 2026-09-04) -- unchecks them afterward so
        # clicking "+ Hinzufügen" again doesn't silently re-add the same
        # templates.
        priority = self._shop_priority()
        schedule = self._shop_schedule()
        for check, amount_edit, tmpl in self._shop_picker_rows:
            if not check.isChecked():
                continue
            item = {
                "type":     "shopping",
                "title":    tmpl.get("title", ""),
                "location": tmpl.get("location", ""),
                "price":    tmpl.get("price", "0"),
                "currency": tmpl.get("currency", "kinah"),
                "amount":   amount_edit.text().strip() or "1",
                "priority": priority,
                "schedule": schedule,
            }
            self._shopping_items.append(item)
            self._add_shop_row(item)
            check.setChecked(False)

    def _add_task_item(self):
        priority = self._task_priority()
        schedule = self._task_schedule()
        for check, amount_edit, tmpl in self._task_picker_rows:
            if not check.isChecked():
                continue
            item = {
                "type":     "task",
                "title":    tmpl.get("title", ""),
                "location": tmpl.get("location", ""),
                "amount":   amount_edit.text().strip() or "1",
                "priority": priority,
                "schedule": schedule,
            }
            self._task_items.append(item)
            self._add_task_row(item)
            check.setChecked(False)

    # ── Row builders ──────────────────────────────────────────────────────────

    def _add_shop_row(self, item: dict):
        row = QWidget()
        row.setObjectName("taskCard")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(8, 4, 8, 4)
        rl.setSpacing(8)
        title = item.get("title", "")
        amount = item.get("amount", 1)
        schedule = item.get("schedule", "daily")
        lbl = QLabel(f"{title}  ×{amount}")
        lbl.setObjectName("NodeItemLabel")
        sched_badge = QLabel(schedule.upper()[:1])
        sched_badge.setObjectName(_SCHED_NAMES.get(schedule, "scheduleDaily"))
        del_btn = QPushButton("×")
        del_btn.setObjectName("PanelCloseButton")
        del_btn.setFixedSize(22, 22)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(lambda _c, i=item, r=row: self._delete_shop_item(i, r))
        rl.addWidget(lbl, 1)
        rl.addWidget(sched_badge)
        rl.addWidget(del_btn)
        self._shop_list_layout.insertWidget(self._shop_list_layout.count() - 1, row)
        row.show()

    def _add_task_row(self, item: dict):
        row = QWidget()
        row.setObjectName("taskCard")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(8, 4, 8, 4)
        rl.setSpacing(8)
        title = item.get("title", "")
        amount = item.get("amount", 1)
        schedule = item.get("schedule", "daily")
        lbl = QLabel(f"{title}  ×{amount}")
        lbl.setObjectName("NodeItemLabel")
        sched_badge = QLabel(schedule.upper()[:1])
        sched_badge.setObjectName(_SCHED_NAMES.get(schedule, "scheduleDaily"))
        del_btn = QPushButton("×")
        del_btn.setObjectName("PanelCloseButton")
        del_btn.setFixedSize(22, 22)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(lambda _c, i=item, r=row: self._delete_task_item(i, r))
        rl.addWidget(lbl, 1)
        rl.addWidget(sched_badge)
        rl.addWidget(del_btn)
        self._task_list_layout.insertWidget(self._task_list_layout.count() - 1, row)
        row.show()

    def _delete_shop_item(self, item, row):
        if item in self._shopping_items:
            self._shopping_items.remove(item)
        row.deleteLater()

    def _delete_task_item(self, item, row):
        if item in self._task_items:
            self._task_items.remove(item)
        row.deleteLater()

    def get_items(self) -> list:
        result = []
        for item in self._shopping_items:
            item["type"] = "shopping"
            result.append(item)
        for item in self._task_items:
            item["type"] = "task"
            result.append(item)
        return result


# ── Node Editor Panel ─────────────────────────────────────────────────────────

class NodeEditorPanel(QFrame):
    def __init__(self, language="en", tr_func=None, icon_dir=None, parent=None):
        super().__init__(parent)

        self.language = language
        self.tr_func = tr_func
        self.icon_dir = icon_dir
        self._character_items: list[dict] = []
        self._shopping_options: list[dict] = []
        self._task_options: list[dict] = []

        self.setObjectName("NodeEditorPanel")
        self.setFixedWidth(390)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()

        self.panel_title = QLabel()
        self.panel_title.setObjectName("PanelTitle")

        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("PanelCloseButton")
        self.close_btn.setFixedSize(34, 34)
        self.close_btn.setCursor(Qt.PointingHandCursor)

        header.addWidget(self.panel_title)
        header.addStretch()
        header.addWidget(self.close_btn)

        self.title_label = QLabel()
        self.title_label.setObjectName("FieldLabel")

        self.title_input = QLineEdit()
        self.title_input.setObjectName("FlowInput")
        self.title_input.setMaxLength(25)

        self.desc_label = QLabel()
        self.desc_label.setObjectName("FieldLabel")

        self.desc_input = QTextEdit()
        self.desc_input.setObjectName("FlowTextEdit")
        self.desc_input.setFixedHeight(100)

        self.symbol_label = QLabel()
        self.symbol_label.setObjectName("FieldLabel")

        self.symbol_combo = QComboBox()
        self.symbol_combo.setObjectName("FlowSymbolCombo")
        self.symbol_combo.setIconSize(QSize(42, 42))
        self.symbol_combo.setMinimumHeight(58)
        self.symbol_combo.view().setIconSize(QSize(42, 42))
        self.symbol_combo.view().setMinimumHeight(260)

        self.symbol_options = [
            ("character", "Character"),
            ("level", "Level"),
            ("expedition", "Expedition"),
            ("daily_dungeon", "Daily Dungeon"),
            ("dungeon", "Dungeon"),
            ("sanctuary", "Sanctuary"),
            ("pets", "Pets"),
            ("closet", "Closet"),
            ("enhancement", "Enhancement"),
            ("crafting", "Crafting"),
            ("supply_request", "Supply Request"),
            ("broker_market", "Broker Market"),
            ("money", "Money"),
        ]

        if self.icon_dir:
            for key, label in self.symbol_options:
                icon_path = self.icon_dir / f"{key}.png"
                self.symbol_combo.addItem(QIcon(str(icon_path)), label, key)
        else:
            for key, label in self.symbol_options:
                self.symbol_combo.addItem(label, key)

        self.optional_check = QCheckBox()
        self.optional_check.setObjectName("FlowOptionalCheck")
        self.optional_check.setCursor(Qt.PointingHandCursor)

        # ── Character Items Section ───────────────────────────────────────────
        self.character_section = QFrame()
        self.character_section.setObjectName("CharacterSection")
        char_layout = QVBoxLayout(self.character_section)
        char_layout.setContentsMargins(0, 0, 0, 0)
        char_layout.setSpacing(6)

        char_header_row = QHBoxLayout()
        self.char_items_label = QLabel("Einkaufsliste")
        self.char_items_label.setObjectName("FieldLabel")
        self._items_count_label = QLabel("")
        self._items_count_label.setObjectName("subtitle")
        char_header_row.addWidget(self.char_items_label)
        char_header_row.addStretch()
        char_header_row.addWidget(self._items_count_label)
        char_layout.addLayout(char_header_row)

        self._edit_items_btn = QPushButton("Liste bearbeiten")
        self._edit_items_btn.setObjectName("secondaryButton")
        self._edit_items_btn.setFixedHeight(34)
        self._edit_items_btn.setCursor(Qt.PointingHandCursor)
        self._edit_items_btn.clicked.connect(self._open_item_list_dialog)
        char_layout.addWidget(self._edit_items_btn)

        self.character_section.setVisible(False)
        # ─────────────────────────────────────────────────────────────────────

        self.is_dirty = False

        self.title_input.textChanged.connect(self._mark_dirty)
        self.desc_input.textChanged.connect(self._mark_dirty)
        self.symbol_combo.currentIndexChanged.connect(self._mark_dirty)
        self.symbol_combo.currentIndexChanged.connect(self._on_icon_changed)
        self.optional_check.stateChanged.connect(self._mark_dirty)

        button_row = QHBoxLayout()
        button_row.setSpacing(14)

        self.node_cancel_btn = QPushButton()
        self.node_cancel_btn.setObjectName("FlowCancelButton")

        self.node_save_btn = QPushButton()
        self.node_save_btn.setObjectName("FlowSaveButton")

        button_row.addWidget(self.node_cancel_btn)
        button_row.addWidget(self.node_save_btn)

        layout.addLayout(header)
        layout.addWidget(self.title_label)
        layout.addWidget(self.title_input)
        layout.addWidget(self.desc_label)
        layout.addWidget(self.desc_input)
        layout.addWidget(self.symbol_label)
        layout.addWidget(self.symbol_combo)
        layout.addSpacing(4)
        layout.addWidget(self.character_section)
        layout.addWidget(self.optional_check)
        layout.addSpacing(6)
        layout.addLayout(button_row)

        self.update_language(language, tr_func)

    # ── Item list popup ───────────────────────────────────────────────────────

    def _open_item_list_dialog(self):
        # Same ancestor-walk MainWindow-lookup already used a few lines
        # below (FlowMapWindow -> its own parent is MainWindow) -- reused
        # here to reach MainWindow.open_template_item_picker, the same
        # bridge Templates' "Import from Database" link already uses
        # (User-Wunsch, 2026-09-04: pick items straight from the real Item
        # Database here too).
        item_picker_callback = None
        w = self.parent()
        while w is not None:
            main = w.parent() if hasattr(w, "nodes") and hasattr(w, "selected_node_id") else None
            if main is not None and hasattr(main, "open_template_item_picker"):
                item_picker_callback = main.open_template_item_picker
                break
            w = w.parent()
        dialog = _NodeItemListDialog(
            self._character_items, self._shopping_options,
            task_templates=self._task_options, parent=self,
            item_picker_callback=item_picker_callback,
        )
        dialog.exec()
        self._character_items = dialog.get_items()
        self._update_items_count()
        self._mark_dirty()
        # Update node.character_items and sync lists immediately,
        # without triggering render_flow or closing the editor panel.
        w = self.parent()
        while w is not None:
            if hasattr(w, "nodes") and hasattr(w, "selected_node_id"):
                node = w.nodes.get(w.selected_node_id)
                if node and node.icon == "character":
                    node.character_items = list(self._character_items)
                    main = w.parent()
                    if main and hasattr(main, "_sync_character_items_to_shopping"):
                        main._sync_character_items_to_shopping(node.title, node.character_items)
                    if hasattr(w, "mark_unsaved"):
                        w.mark_unsaved()
                break
            w = w.parent()

    def _update_items_count(self):
        shop_n = sum(1 for i in self._character_items if i.get("type", "shopping") != "task")
        task_n = sum(1 for i in self._character_items if i.get("type") == "task")
        parts = []
        if shop_n:
            parts.append(f"{shop_n} Einkauf")
        if task_n:
            parts.append(f"{task_n} Aufgabe{'n' if task_n != 1 else ''}")
        self._items_count_label.setText(", ".join(parts) if parts else "Keine Einträge")

    # ── Shopping options (templates passed from controller) ───────────────────

    def set_shopping_options(self, options: list[dict]):
        self._shopping_options = options

    def set_task_options(self, options: list[dict]):
        self._task_options = options

    # ── Character Items ───────────────────────────────────────────────────────

    def _on_icon_changed(self):
        is_char = self.symbol_combo.currentData() == "character"
        self.character_section.setVisible(is_char)

    def load_character_items(self, items: list):
        self._character_items = [dict(i) for i in items] if items else []
        self._update_items_count()

    def get_character_items(self) -> list:
        return list(self._character_items)

    # ── General ───────────────────────────────────────────────────────────────

    def _mark_dirty(self):
        self.is_dirty = True

    def mark_clean(self):
        self.is_dirty = False

    def update_language(self, language, tr_func):
        self.language = language
        self.tr_func = tr_func

        if not tr_func:
            return

        self.panel_title.setText(tr_func(language, "flow_node_edit"))
        self.title_label.setText(tr_func(language, "flow_title_placeholder"))
        self.desc_label.setText(tr_func(language, "flow_description_placeholder"))
        self.symbol_label.setText(tr_func(language, "flow_symbol"))
        self.optional_check.setText(tr_func(language, "flow_optional_node"))
        self.node_cancel_btn.setText(tr_func(language, "cancel"))
        self.node_save_btn.setText(tr_func(language, "flow_save"))
