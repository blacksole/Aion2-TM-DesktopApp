from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtGui import QRegularExpressionValidator, QIntValidator
from PySide6.QtCore import QRegularExpression
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QCompleter,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

_SCHEDULE_NAMES = {"daily": "scheduleDaily", "weekly": "scheduleWeekly", "season": "scheduleSeason"}
_SCHEDULE_TEXTS = {"daily": "DAILY", "weekly": "WEEKLY", "season": "SEASON"}
_PRIO_NAMES = {"low": "priorityLow", "middle": "priorityMiddle", "high": "priorityHigh"}
_PRIO_TEXTS = {"low": "LOW", "middle": "MID", "high": "HIGH"}
_SORT_LABELS = {"name": "Name", "priority": "Prio", "schedule": "Schedule", "location": "Location"}


def _h_separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: rgba(100, 116, 139, 0.3);")
    return line


class TemplateDialog(QDialog):
    """Popup for managing item and task template catalogs."""

    def __init__(self, templates: list, flow_maps: dict, task_templates: list = None,
                 initial_tab: str = "shopping", parent=None,
                 language: str = "en", tr_func=None):
        super().__init__(parent)
        self._language = language
        self._tr = tr_func or (lambda _l, k, **kw: k)

        self.setWindowTitle(self._t("templates_title"))
        self.setMinimumSize(660, 540)
        self.resize(720, 580)

        self.templates = [dict(t) for t in templates]
        self.task_templates = [dict(t) for t in (task_templates or [])]
        self.flow_maps = flow_maps
        self._selected_shop_index: int | None = None
        self._selected_task_index: int | None = None
        self._shop_sort_key: str = "none"
        self._shop_sort_dir: str = "asc"
        self._shop_sort_btns: dict = {}
        self._shop_search: str = ""
        self._task_sort_key: str = "none"
        self._task_sort_dir: str = "asc"
        self._task_sort_btns: dict = {}
        self._task_search: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        # ── Tab widget ────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.addTab(self._make_shop_tab(), self._t("tab_shopping"))
        self._tabs.addTab(self._make_tasks_tab(), self._t("tab_tasks"))
        if initial_tab == "tasks":
            self._tabs.setCurrentIndex(1)
        layout.addWidget(self._tabs, 1)

        # ── Footer ────────────────────────────────────────────────────────────
        close_btn = QPushButton(self._t("close"))
        close_btn.setObjectName("primaryButton")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignRight)

    def _t(self, key: str, **kwargs) -> str:
        return self._tr(self._language, key, **kwargs)

    # ── Shopping tab ──────────────────────────────────────────────────────────

    def _make_shop_tab(self) -> QWidget:
        widget = QWidget()
        vl = QVBoxLayout(widget)
        vl.setContentsMargins(12, 12, 12, 12)
        vl.setSpacing(8)

        header = QHBoxLayout()
        info = QLabel(self._t("shop_tab_info"))
        info.setObjectName("subtitle")
        self._shop_add_btn = QPushButton(self._t("template_add_btn"))
        self._shop_add_btn.setObjectName("primaryButton")
        self._shop_add_btn.clicked.connect(self._handle_shop_add_btn)
        header.addWidget(info)
        header.addStretch()
        header.addWidget(self._shop_add_btn)
        vl.addLayout(header)

        self._shop_search_input = QLineEdit()
        self._shop_search_input.setObjectName("FlowInput")
        self._shop_search_input.setPlaceholderText(self._t("template_search_placeholder"))
        self._shop_search_input.textChanged.connect(self._on_shop_search_changed)
        vl.addWidget(self._shop_search_input)

        sort_row = QHBoxLayout()
        sort_lbl = QLabel(self._t("sort_label"))
        sort_lbl.setObjectName("subtitle")
        sort_row.addWidget(sort_lbl)
        for label, key in (("Name", "name"), ("Prio", "priority"), ("Schedule", "schedule"), ("Location", "location")):
            btn = QPushButton(label)
            btn.setObjectName("filterButton")
            btn.clicked.connect(lambda _c=False, k=key: self._sort_shop_by(k))
            sort_row.addWidget(btn)
            self._shop_sort_btns[key] = btn
        sort_row.addStretch()
        vl.addLayout(sort_row)

        self._shop_list_container = QWidget()
        self._shop_list_layout = QVBoxLayout(self._shop_list_container)
        self._shop_list_layout.setContentsMargins(0, 0, 0, 0)
        self._shop_list_layout.setSpacing(6)
        self._shop_list_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self._shop_list_container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("scrollArea")
        vl.addWidget(scroll, 1)

        self._rebuild_shop_list()
        return widget

    # ── Tasks tab ─────────────────────────────────────────────────────────────

    def _make_tasks_tab(self) -> QWidget:
        widget = QWidget()
        vl = QVBoxLayout(widget)
        vl.setContentsMargins(12, 12, 12, 12)
        vl.setSpacing(8)

        header = QHBoxLayout()
        info = QLabel(self._t("task_tab_info"))
        info.setObjectName("subtitle")
        self._task_add_btn = QPushButton(self._t("task_add_btn"))
        self._task_add_btn.setObjectName("primaryButton")
        self._task_add_btn.clicked.connect(self._handle_task_add_btn)
        header.addWidget(info)
        header.addStretch()
        header.addWidget(self._task_add_btn)
        vl.addLayout(header)

        self._task_search_input = QLineEdit()
        self._task_search_input.setObjectName("FlowInput")
        self._task_search_input.setPlaceholderText(self._t("template_search_placeholder"))
        self._task_search_input.textChanged.connect(self._on_task_search_changed)
        vl.addWidget(self._task_search_input)

        sort_row = QHBoxLayout()
        sort_lbl = QLabel(self._t("sort_label"))
        sort_lbl.setObjectName("subtitle")
        sort_row.addWidget(sort_lbl)
        for label, key in (("Name", "name"), ("Prio", "priority"), ("Schedule", "schedule"), ("Location", "location")):
            btn = QPushButton(label)
            btn.setObjectName("filterButton")
            btn.clicked.connect(lambda _c=False, k=key: self._sort_tasks_by(k))
            sort_row.addWidget(btn)
            self._task_sort_btns[key] = btn
        sort_row.addStretch()
        vl.addLayout(sort_row)

        self._task_list_container = QWidget()
        self._task_list_layout = QVBoxLayout(self._task_list_container)
        self._task_list_layout.setContentsMargins(0, 0, 0, 0)
        self._task_list_layout.setSpacing(6)
        self._task_list_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self._task_list_container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("scrollArea")
        vl.addWidget(scroll, 1)

        self._rebuild_task_list()
        return widget

    # ── Character assignment detection ────────────────────────────────────────

    def _get_char_assignments(self, title: str) -> list[str]:
        chars = []
        seen: set[str] = set()
        for map_data in self.flow_maps.values():
            if not isinstance(map_data, dict):
                continue
            for node_data in map_data.get("nodes", {}).values():
                if not isinstance(node_data, dict):
                    continue
                if node_data.get("icon") != "character":
                    continue
                for ci in node_data.get("character_items", []):
                    if ci.get("title", "").lower() == title.lower():
                        char_name = node_data.get("title", "?")
                        if char_name not in seen:
                            chars.append(char_name)
                            seen.add(char_name)
        return chars

    # ── Shopping list rendering ───────────────────────────────────────────────

    def _rebuild_shop_list(self):
        while self._shop_list_layout.count() > 1:
            item = self._shop_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        query = self._shop_search.strip().lower()
        for i, tmpl in enumerate(self.templates):
            if query and query not in tmpl.get("title", "").lower() and query not in tmpl.get("location", "").lower():
                continue
            row = self._make_shop_row(i, tmpl)
            self._shop_list_layout.insertWidget(self._shop_list_layout.count() - 1, row)

    def _on_shop_search_changed(self, text: str):
        self._shop_search = text
        self._rebuild_shop_list()

    def _make_shop_row(self, index: int, tmpl: dict) -> QWidget:
        row = QFrame()
        row.setObjectName("taskCard")
        row.setProperty("selected", index == self._selected_shop_index)
        row.setCursor(Qt.PointingHandCursor)
        row.mousePressEvent = lambda _e, i=index: self._select_shop_row(i)

        hl = QHBoxLayout(row)
        hl.setContentsMargins(12, 10, 12, 10)
        hl.setSpacing(10)

        check = QCheckBox()
        check.setChecked(bool(tmpl.get("is_general", False)))
        check.setToolTip(self._t("shop_check_tooltip"))
        check.setCursor(Qt.PointingHandCursor)
        check.stateChanged.connect(lambda state, i=index: self._set_shop_general(i, bool(state)))

        text_col = QVBoxLayout()
        text_col.setSpacing(3)

        title_row = QHBoxLayout()
        title_lbl = QLabel(tmpl.get("title", "—"))
        title_lbl.setObjectName("taskTitle")
        currency = tmpl.get("currency", "kinah")
        price_raw = tmpl.get("price", "0")
        price_display = f"{price_raw} AP" if currency == "abyss" else f"{price_raw}K"
        price_lbl = QLabel(price_display)
        price_lbl.setObjectName("taskDescription")
        title_row.addWidget(title_lbl)
        title_row.addSpacing(8)
        title_row.addWidget(price_lbl)
        title_row.addStretch()
        text_col.addLayout(title_row)

        location = tmpl.get("location", "").strip()
        if location:
            loc_lbl = QLabel(location)
            loc_lbl.setObjectName("taskDescription")
            text_col.addWidget(loc_lbl)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
        sched = tmpl.get("schedule", "daily")
        sched_badge = QLabel(_SCHEDULE_TEXTS.get(sched, sched.upper()))
        sched_badge.setObjectName(_SCHEDULE_NAMES.get(sched, "scheduleDaily"))
        badge_row.addWidget(sched_badge)
        prio = tmpl.get("priority", "middle")
        prio_badge = QLabel(_PRIO_TEXTS.get(prio, prio.upper()))
        prio_badge.setObjectName(_PRIO_NAMES.get(prio, "priorityMiddle"))
        badge_row.addWidget(prio_badge)
        chars = self._get_char_assignments(tmpl.get("title", ""))
        for char_name in chars:
            char_badge = QLabel(char_name)
            char_badge.setObjectName("scheduleWeekly")
            badge_row.addWidget(char_badge)
        badge_row.addStretch()
        text_col.addLayout(badge_row)

        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("secondaryButton")
        edit_btn.setFixedSize(52, 30)
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.clicked.connect(lambda _c=False, i=index: self._edit_shop_template(i))

        del_btn = QPushButton("×")
        del_btn.setObjectName("deleteButton")
        del_btn.setFixedSize(32, 30)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(lambda _c=False, i=index: self._delete_shop_template(i))

        hl.addWidget(check)
        hl.addLayout(text_col, 1)
        hl.addWidget(edit_btn)
        hl.addWidget(del_btn)
        return row

    # ── Task list rendering ───────────────────────────────────────────────────

    def _rebuild_task_list(self):
        while self._task_list_layout.count() > 1:
            item = self._task_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        query = self._task_search.strip().lower()
        for i, tmpl in enumerate(self.task_templates):
            if query and query not in tmpl.get("title", "").lower() and query not in tmpl.get("location", "").lower():
                continue
            row = self._make_task_row(i, tmpl)
            self._task_list_layout.insertWidget(self._task_list_layout.count() - 1, row)

    def _on_task_search_changed(self, text: str):
        self._task_search = text
        self._rebuild_task_list()

    def _make_task_row(self, index: int, tmpl: dict) -> QWidget:
        row = QFrame()
        row.setObjectName("taskCard")
        row.setProperty("selected", index == self._selected_task_index)
        row.setCursor(Qt.PointingHandCursor)
        row.mousePressEvent = lambda _e, i=index: self._select_task_row(i)

        hl = QHBoxLayout(row)
        hl.setContentsMargins(12, 10, 12, 10)
        hl.setSpacing(10)

        check = QCheckBox()
        check.setChecked(bool(tmpl.get("is_general", False)))
        check.setToolTip(self._t("task_check_tooltip"))
        check.setCursor(Qt.PointingHandCursor)
        check.stateChanged.connect(lambda state, i=index: self._set_task_general(i, bool(state)))

        text_col = QVBoxLayout()
        text_col.setSpacing(3)

        title_lbl = QLabel(tmpl.get("title", "—"))
        title_lbl.setObjectName("taskTitle")
        text_col.addWidget(title_lbl)

        location = tmpl.get("location", "").strip()
        if location:
            loc_lbl = QLabel(location)
            loc_lbl.setObjectName("taskDescription")
            text_col.addWidget(loc_lbl)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
        sched = tmpl.get("schedule", "daily")
        sched_badge = QLabel(_SCHEDULE_TEXTS.get(sched, sched.upper()))
        sched_badge.setObjectName(_SCHEDULE_NAMES.get(sched, "scheduleDaily"))
        badge_row.addWidget(sched_badge)
        prio = tmpl.get("priority", "middle")
        prio_badge = QLabel(_PRIO_TEXTS.get(prio, prio.upper()))
        prio_badge.setObjectName(_PRIO_NAMES.get(prio, "priorityMiddle"))
        badge_row.addWidget(prio_badge)
        badge_row.addStretch()
        text_col.addLayout(badge_row)

        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("secondaryButton")
        edit_btn.setFixedSize(52, 30)
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.clicked.connect(lambda _c=False, i=index: self._edit_task_template(i))

        del_btn = QPushButton("×")
        del_btn.setObjectName("deleteButton")
        del_btn.setFixedSize(32, 30)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(lambda _c=False, i=index: self._delete_task_template(i))

        hl.addWidget(check)
        hl.addLayout(text_col, 1)
        hl.addWidget(edit_btn)
        hl.addWidget(del_btn)
        return row

    # ── Shopping actions ──────────────────────────────────────────────────────

    def _select_shop_row(self, index: int):
        self._selected_shop_index = None if self._selected_shop_index == index else index
        self._update_shop_add_btn()
        self._rebuild_shop_list()

    def _update_shop_add_btn(self):
        if self._selected_shop_index is not None:
            self._shop_add_btn.setText(self._t("template_update_btn"))
        else:
            self._shop_add_btn.setText(self._t("template_add_btn"))

    def _handle_shop_add_btn(self):
        if self._selected_shop_index is not None:
            self._edit_shop_template(self._selected_shop_index)
        else:
            self._add_shop_template()

    def _sort_shop_by(self, key: str):
        if self._shop_sort_key == key:
            self._shop_sort_dir = "desc" if self._shop_sort_dir == "asc" else "asc"
        else:
            self._shop_sort_key = key
            self._shop_sort_dir = "asc"
        self._update_shop_sort_buttons()
        reverse = self._shop_sort_dir == "desc"
        if self._shop_sort_key == "name":
            self.templates.sort(key=lambda t: t.get("title", "").lower(), reverse=reverse)
        elif self._shop_sort_key == "priority":
            _order = {"high": 0, "middle": 1, "low": 2}
            self.templates.sort(key=lambda t: _order.get(t.get("priority", "middle"), 1), reverse=reverse)
        elif self._shop_sort_key == "schedule":
            _order = {"daily": 0, "weekly": 1, "season": 2}
            self.templates.sort(key=lambda t: _order.get(t.get("schedule", "daily"), 3), reverse=reverse)
        elif self._shop_sort_key == "location":
            self.templates.sort(key=lambda t: t.get("location", "").lower(), reverse=reverse)
        self._selected_shop_index = None
        self._update_shop_add_btn()
        self._rebuild_shop_list()

    def _update_shop_sort_buttons(self):
        arrow = " ↑" if self._shop_sort_dir == "asc" else " ↓"
        for k, btn in self._shop_sort_btns.items():
            is_active = k == self._shop_sort_key
            btn.setText(_SORT_LABELS[k] + (arrow if is_active else ""))
            btn.setProperty("active", is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _set_shop_general(self, index: int, value: bool):
        if not (0 <= index < len(self.templates)):
            return
        if value:
            dlg = _AmountDialog(self.templates[index], parent=self,
                                language=self._language, tr_func=self._tr)
            if not dlg.exec():
                self._rebuild_shop_list()
                return
            self.templates[index]["amount"] = dlg.get_amount()
            self.templates[index]["priority"] = dlg.get_priority()
            self.templates[index]["schedule"] = dlg.get_schedule()
        self.templates[index]["is_general"] = value
        self._rebuild_shop_list()

    def _known_shop_locations(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for t in self.templates:
            loc = t.get("location", "").strip()
            if loc and loc not in seen:
                seen.add(loc)
                result.append(loc)
        return result

    def _add_shop_template(self):
        dlg = _TemplateEditDialog(known_locations=self._known_shop_locations(), parent=self,
                                  language=self._language, tr_func=self._tr)
        if dlg.exec():
            item = dlg.get_data()
            item["id"] = str(uuid4())
            self.templates.append(item)
            self._rebuild_shop_list()

    def _edit_shop_template(self, index: int):
        if 0 <= index < len(self.templates):
            dlg = _TemplateEditDialog(
                self.templates[index],
                known_locations=self._known_shop_locations(),
                parent=self,
                language=self._language,
                tr_func=self._tr,
            )
            if dlg.exec():
                data = dlg.get_data()
                data["id"] = self.templates[index].get("id", str(uuid4()))
                data["is_general"] = self.templates[index].get("is_general", False)
                data["amount"] = self.templates[index].get("amount", "1")
                self.templates[index] = data
                self._selected_shop_index = None
                self._update_shop_add_btn()
                self._rebuild_shop_list()

    def _delete_shop_template(self, index: int):
        if 0 <= index < len(self.templates):
            self.templates.pop(index)
            if self._selected_shop_index == index:
                self._selected_shop_index = None
                self._update_shop_add_btn()
            elif self._selected_shop_index is not None and self._selected_shop_index > index:
                self._selected_shop_index -= 1
            self._rebuild_shop_list()

    # ── Task actions ──────────────────────────────────────────────────────────

    def _select_task_row(self, index: int):
        self._selected_task_index = None if self._selected_task_index == index else index
        self._update_task_add_btn()
        self._rebuild_task_list()

    def _update_task_add_btn(self):
        if self._selected_task_index is not None:
            self._task_add_btn.setText(self._t("template_update_btn"))
        else:
            self._task_add_btn.setText(self._t("task_add_btn"))

    def _handle_task_add_btn(self):
        if self._selected_task_index is not None:
            self._edit_task_template(self._selected_task_index)
        else:
            self._add_task_template()

    def _sort_tasks_by(self, key: str):
        if self._task_sort_key == key:
            self._task_sort_dir = "desc" if self._task_sort_dir == "asc" else "asc"
        else:
            self._task_sort_key = key
            self._task_sort_dir = "asc"
        self._update_task_sort_buttons()
        reverse = self._task_sort_dir == "desc"
        if self._task_sort_key == "name":
            self.task_templates.sort(key=lambda t: t.get("title", "").lower(), reverse=reverse)
        elif self._task_sort_key == "priority":
            _order = {"high": 0, "middle": 1, "low": 2}
            self.task_templates.sort(key=lambda t: _order.get(t.get("priority", "middle"), 1), reverse=reverse)
        elif self._task_sort_key == "schedule":
            _order = {"daily": 0, "weekly": 1, "season": 2}
            self.task_templates.sort(key=lambda t: _order.get(t.get("schedule", "daily"), 3), reverse=reverse)
        elif self._task_sort_key == "location":
            self.task_templates.sort(key=lambda t: t.get("location", "").lower(), reverse=reverse)
        self._selected_task_index = None
        self._update_task_add_btn()
        self._rebuild_task_list()

    def _update_task_sort_buttons(self):
        arrow = " ↑" if self._task_sort_dir == "asc" else " ↓"
        for k, btn in self._task_sort_btns.items():
            is_active = k == self._task_sort_key
            btn.setText(_SORT_LABELS[k] + (arrow if is_active else ""))
            btn.setProperty("active", is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _set_task_general(self, index: int, value: bool):
        if not (0 <= index < len(self.task_templates)):
            return
        self.task_templates[index]["is_general"] = value
        self._rebuild_task_list()

    def _known_task_locations(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for t in self.task_templates:
            loc = t.get("location", "").strip()
            if loc and loc not in seen:
                seen.add(loc)
                result.append(loc)
        return result

    def _add_task_template(self):
        dlg = _TemplateEditDialog(
            known_locations=self._known_task_locations(),
            parent=self,
            task_mode=True,
            language=self._language,
            tr_func=self._tr,
        )
        if dlg.exec():
            item = dlg.get_data()
            item["id"] = str(uuid4())
            self.task_templates.append(item)
            self._rebuild_task_list()

    def _edit_task_template(self, index: int):
        if 0 <= index < len(self.task_templates):
            dlg = _TemplateEditDialog(
                self.task_templates[index],
                known_locations=self._known_task_locations(),
                parent=self,
                task_mode=True,
                language=self._language,
                tr_func=self._tr,
            )
            if dlg.exec():
                data = dlg.get_data()
                data["id"] = self.task_templates[index].get("id", str(uuid4()))
                data["is_general"] = self.task_templates[index].get("is_general", False)
                self.task_templates[index] = data
                self._selected_task_index = None
                self._update_task_add_btn()
                self._rebuild_task_list()

    def _delete_task_template(self, index: int):
        if 0 <= index < len(self.task_templates):
            self.task_templates.pop(index)
            if self._selected_task_index == index:
                self._selected_task_index = None
                self._update_task_add_btn()
            elif self._selected_task_index is not None and self._selected_task_index > index:
                self._selected_task_index -= 1
            self._rebuild_task_list()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_templates(self) -> list:
        return self.templates

    def get_task_templates(self) -> list:
        return self.task_templates


class _TemplateEditDialog(QDialog):
    """Edit form for shopping and task templates. Pass task_mode=True to hide currency/price."""

    def __init__(self, data: dict = None, known_locations: list[str] = None, parent=None,
                 task_mode: bool = False, language: str = "en", tr_func=None):
        super().__init__(parent)
        data = data or {}
        known_locations = known_locations or []
        self._task_mode = task_mode
        self._tr = tr_func or (lambda _l, k, **kw: k)
        self._language = language

        if task_mode:
            title_key = "task_edit_title" if data.get("title") else "task_add_title"
        else:
            title_key = "template_edit_title" if data.get("title") else "template_add_title"
        self.setWindowTitle(self._t(title_key))
        self.setFixedWidth(500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # ── Row 1: Schedule (left) ··· Priority (right) ───────────────────────
        self._daily_btn  = self._toggle("Daily",  "scheduleToggleBtn")
        self._weekly_btn = self._toggle("Weekly", "scheduleToggleBtn")
        self._season_btn = self._toggle("Season", "scheduleToggleBtn")
        sched_grp = QButtonGroup(self)
        sched_grp.setExclusive(True)
        for b in (self._daily_btn, self._weekly_btn, self._season_btn):
            sched_grp.addButton(b)
        {"daily": self._daily_btn, "weekly": self._weekly_btn, "season": self._season_btn}.get(
            data.get("schedule", "daily"), self._daily_btn
        ).setChecked(True)

        self._low_btn    = self._toggle("Low",    "priorityToggleLow")
        self._middle_btn = self._toggle("Middle", "priorityToggleMiddle")
        self._high_btn   = self._toggle("High",   "priorityToggleHigh")
        prio_grp = QButtonGroup(self)
        prio_grp.setExclusive(True)
        for b in (self._low_btn, self._middle_btn, self._high_btn):
            prio_grp.addButton(b)
        {"low": self._low_btn, "middle": self._middle_btn, "high": self._high_btn}.get(
            data.get("priority", "middle"), self._middle_btn
        ).setChecked(True)

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(6)
        for b in (self._daily_btn, self._weekly_btn, self._season_btn):
            toggle_row.addWidget(b)
        toggle_row.addSpacing(14)
        for b in (self._low_btn, self._middle_btn, self._high_btn):
            toggle_row.addWidget(b)
        layout.addLayout(toggle_row)

        layout.addWidget(_h_separator())

        # ── Row 2: Title + Location ────────────────────────────────────────────
        self._title = QLineEdit(data.get("title", ""))
        placeholder_key = "placeholder_taskname" if task_mode else "placeholder_itemname"
        self._title.setPlaceholderText(self._t(placeholder_key))

        self._location = QLineEdit(data.get("location", ""))
        self._location.setPlaceholderText(self._t("placeholder_location_short"))
        if known_locations:
            cpl = QCompleter(known_locations, self._location)
            cpl.setCaseSensitivity(Qt.CaseInsensitive)
            cpl.setFilterMode(Qt.MatchContains)
            self._location.setCompleter(cpl)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_row.addWidget(self._title, 1)
        name_row.addWidget(self._location, 1)
        layout.addLayout(name_row)

        # ── Row 3: Currency + Price (shopping only) ───────────────────────────
        if not task_mode:
            self._kinah_btn = self._toggle("Kinah", "currencyToggleKinah")
            self._abyss_btn = self._toggle("AP",    "currencyToggleAbyss")
            self._np_btn    = self._toggle("NP",    "currencyToggleAbyss")
            self._sc_btn    = self._toggle("SC",    "currencyToggleAbyss")
            cur_grp = QButtonGroup(self)
            cur_grp.setExclusive(True)
            for b in (self._kinah_btn, self._abyss_btn, self._np_btn, self._sc_btn):
                cur_grp.addButton(b)
            cur = data.get("currency", "kinah")
            {"abyss": self._abyss_btn, "nightmare": self._np_btn,
             "shugo": self._sc_btn}.get(cur, self._kinah_btn).setChecked(True)

            self._price = QLineEdit(str(data.get("price", "")))
            self._price.setPlaceholderText(self._t("placeholder_price_k"))
            self._price.setValidator(
                QRegularExpressionValidator(QRegularExpression(r"^\d{0,9}([.,]\d{0,3})?[kK]?$"))
            )
            self._price.setMaximumWidth(120)

            price_row = QHBoxLayout()
            price_row.setSpacing(8)
            for b in (self._kinah_btn, self._abyss_btn, self._np_btn, self._sc_btn):
                price_row.addWidget(b)
            price_row.addSpacing(8)
            price_row.addWidget(self._price, 1)
            layout.addLayout(price_row)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._t("cancel"))
        cancel_btn.setObjectName("FlowCancelButton")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton(self._t("save"))
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _t(self, key: str, **kwargs) -> str:
        return self._tr(self._language, key, **kwargs)

    @staticmethod
    def _toggle(text: str, obj_name: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName(obj_name)
        btn.setCheckable(True)
        return btn

    def _get_schedule(self) -> str:
        if self._weekly_btn.isChecked():
            return "weekly"
        if self._season_btn.isChecked():
            return "season"
        return "daily"

    def _get_priority(self) -> str:
        if self._low_btn.isChecked():
            return "low"
        if self._high_btn.isChecked():
            return "high"
        return "middle"

    def _save(self):
        if self._title.text().strip():
            self.accept()

    def _get_currency(self) -> str:
        if self._abyss_btn.isChecked():
            return "abyss"
        if self._np_btn.isChecked():
            return "nightmare"
        if self._sc_btn.isChecked():
            return "shugo"
        return "kinah"

    def get_data(self) -> dict:
        d = {
            "title": self._title.text().strip(),
            "location": self._location.text().strip(),
            "schedule": self._get_schedule(),
            "priority": self._get_priority(),
            "is_general": False,
        }
        if not self._task_mode:
            d["price"] = self._price.text().strip() or "0"
            d["currency"] = self._get_currency()
        return d


class _AmountDialog(QDialog):
    """Popup shown when the user checks a shopping template item to add it to the shopping list."""

    @staticmethod
    def _toggle(text: str, obj_name: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName(obj_name)
        btn.setCheckable(True)
        return btn

    def __init__(self, tmpl: dict, parent=None, language: str = "en", tr_func=None):
        super().__init__(parent)
        self._tr = tr_func or (lambda _l, k, **kw: k)
        self._language = language

        self.setWindowTitle(self._t("add_to_shop_title"))
        self.setFixedWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        info = QLabel(self._t("add_to_shop_info", title=tmpl.get("title", "")))
        info.setObjectName("taskDescription")
        info.setWordWrap(True)
        layout.addWidget(info)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: rgba(100,116,139,0.3);")
        layout.addWidget(sep)

        amount_row = QHBoxLayout()
        amount_lbl = QLabel(self._t("amount_label"))
        amount_lbl.setObjectName("settingsLabel")
        self._amount = QLineEdit(str(tmpl.get("amount", "1")))
        self._amount.setObjectName("FlowInput")
        self._amount.setFixedWidth(80)
        self._amount.setValidator(QIntValidator(1, 9999, self))
        self._amount.returnPressed.connect(self.accept)
        amount_row.addWidget(amount_lbl)
        amount_row.addWidget(self._amount)
        amount_row.addStretch()
        layout.addLayout(amount_row)

        prio_row = QHBoxLayout()
        prio_lbl = QLabel(self._t("priority_label"))
        prio_lbl.setObjectName("settingsLabel")
        self._prio_group = QButtonGroup(self)
        self._prio_group.setExclusive(True)
        self._prio_low  = self._toggle("Low",    "priorityToggleLow")
        self._prio_mid  = self._toggle("Middle", "priorityToggleMiddle")
        self._prio_high = self._toggle("High",   "priorityToggleHigh")
        for btn in (self._prio_low, self._prio_mid, self._prio_high):
            self._prio_group.addButton(btn)
            prio_row.addWidget(btn)
        prio_row.insertWidget(0, prio_lbl)
        prio_row.addStretch()
        cur_prio = tmpl.get("priority", "middle")
        {"low": self._prio_low, "middle": self._prio_mid, "high": self._prio_high}.get(
            cur_prio, self._prio_mid
        ).setChecked(True)
        layout.addLayout(prio_row)

        sched_row = QHBoxLayout()
        sched_lbl = QLabel("Schedule:")
        sched_lbl.setObjectName("settingsLabel")
        self._sched_group = QButtonGroup(self)
        self._sched_group.setExclusive(True)
        self._sched_daily  = self._toggle("Daily",  "scheduleToggleBtn")
        self._sched_weekly = self._toggle("Weekly", "scheduleToggleBtn")
        self._sched_season = self._toggle("Season", "scheduleToggleBtn")
        for btn in (self._sched_daily, self._sched_weekly, self._sched_season):
            self._sched_group.addButton(btn)
            sched_row.addWidget(btn)
        sched_row.insertWidget(0, sched_lbl)
        sched_row.addStretch()
        cur_sched = tmpl.get("schedule", "daily")
        {"daily": self._sched_daily, "weekly": self._sched_weekly, "season": self._sched_season}.get(
            cur_sched, self._sched_daily
        ).setChecked(True)
        layout.addLayout(sched_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: rgba(100,116,139,0.3);")
        layout.addWidget(sep2)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._t("cancel"))
        cancel_btn.setObjectName("FlowCancelButton")
        cancel_btn.clicked.connect(self.reject)
        confirm_btn = QPushButton(self._t("add_btn_short"))
        confirm_btn.setObjectName("primaryButton")
        confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

    def _t(self, key: str, **kwargs) -> str:
        return self._tr(self._language, key, **kwargs)

    def get_amount(self) -> str:
        return self._amount.text().strip() or "1"

    def get_priority(self) -> str:
        if self._prio_low.isChecked():
            return "low"
        if self._prio_high.isChecked():
            return "high"
        return "middle"

    def get_schedule(self) -> str:
        if self._sched_weekly.isChecked():
            return "weekly"
        if self._sched_season.isChecked():
            return "season"
        return "daily"
