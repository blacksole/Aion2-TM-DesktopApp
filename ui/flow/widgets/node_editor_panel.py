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
)

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QIntValidator

_MAX_CHARACTERS = 8

_SCHED_NAMES = {"daily": "scheduleDaily", "weekly": "scheduleWeekly", "season": "scheduleSeason"}
_PRIO_NAMES  = {"low": "priorityToggleLow", "middle": "priorityToggleMiddle", "high": "priorityToggleHigh"}


# ── Item List Popup ───────────────────────────────────────────────────────────

class _NodeItemListDialog(QDialog):
    def __init__(self, items: list, shopping_templates: list,
                 task_templates: list = None, parent=None):
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

        self._shop_combo = QComboBox()
        self._shop_combo.setObjectName("FlowSymbolCombo")
        self._shop_combo.setMinimumHeight(36)
        if self._shopping_templates:
            for tmpl in self._shopping_templates:
                self._shop_combo.addItem(tmpl.get("title", ""), tmpl)
        else:
            self._shop_combo.addItem("Keine Vorlagen vorhanden")

        self._shop_amount = QLineEdit("1")
        self._shop_amount.setObjectName("FlowInput")
        self._shop_amount.setFixedWidth(70)
        self._shop_amount.setValidator(QIntValidator(1, 9999, self))
        amount_row = QHBoxLayout()
        amount_row.addWidget(QLabel("Anzahl:"))
        amount_row.addWidget(self._shop_amount)
        amount_row.addStretch()

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

        add_layout.addWidget(self._shop_combo)
        add_layout.addLayout(amount_row)
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

        self._task_combo = QComboBox()
        self._task_combo.setObjectName("FlowSymbolCombo")
        self._task_combo.setMinimumHeight(36)
        if self._task_templates:
            for tmpl in self._task_templates:
                self._task_combo.addItem(tmpl.get("title", ""), tmpl)
        else:
            self._task_combo.addItem("Keine Aufgaben-Vorlagen vorhanden")

        self._task_amount = QLineEdit("1")
        self._task_amount.setObjectName("FlowInput")
        self._task_amount.setFixedWidth(70)
        self._task_amount.setValidator(QIntValidator(1, 9999, self))
        amount_row = QHBoxLayout()
        amount_row.addWidget(QLabel("Anzahl:"))
        amount_row.addWidget(self._task_amount)
        amount_row.addStretch()

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

        add_layout.addWidget(self._task_combo)
        add_layout.addLayout(amount_row)
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
        tmpl = self._shop_combo.currentData()
        if not tmpl:
            return
        item = {
            "type":     "shopping",
            "title":    tmpl.get("title", ""),
            "location": tmpl.get("location", ""),
            "price":    tmpl.get("price", "0"),
            "currency": tmpl.get("currency", "kinah"),
            "amount":   self._shop_amount.text().strip() or "1",
            "priority": self._shop_priority(),
            "schedule": self._shop_schedule(),
        }
        self._shopping_items.append(item)
        self._add_shop_row(item)

    def _add_task_item(self):
        tmpl = self._task_combo.currentData()
        if not tmpl:
            return
        item = {
            "type":     "task",
            "title":    tmpl.get("title", ""),
            "location": tmpl.get("location", ""),
            "amount":   self._task_amount.text().strip() or "1",
            "priority": self._task_priority(),
            "schedule": self._task_schedule(),
        }
        self._task_items.append(item)
        self._add_task_row(item)

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
        dialog = _NodeItemListDialog(
            self._character_items, self._shopping_options,
            task_templates=self._task_options, parent=self
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
