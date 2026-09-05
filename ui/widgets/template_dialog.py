from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtGui import QRegularExpressionValidator, QIntValidator
from PySide6.QtCore import QRegularExpression
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
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
                 language: str = "en", tr_func=None, item_picker_callback=None,
                 characters: list = None, standard_templates: dict = None):
        super().__init__(parent)
        # For the post-CSV-import "which character does this apply to"
        # question -- same names MainWindow's own Shopping "Add" form
        # already offers via its Character dropdown. Character CREATION/
        # management itself lives in its own dialog now, opened by its own
        # "Character" button next to the ToDo screen's "Templates" button
        # (User-correction, 2026-09-04, after first trying it as a tab
        # here: "Character sollte direkt im ToDo Fenster neben Templates
        # stehen") -- see ui/widgets/character_dialog.py.
        self._characters = list(characters or [])
        self._language = language
        self._tr = tr_func or (lambda _l, k, **kw: k)
        # Opens the REAL Item Database catalog picker (icons, shop-type
        # sidebar, real filters) for "Import from Database" -- provided by
        # MainWindow.open_template_item_picker, since only the host app
        # knows how to lazily load the ItemDatabase module (see
        # MainWindow._ensure_item_database_window). None in any other
        # embedding context just hides the import link entirely.
        self._item_picker_callback = item_picker_callback

        self.setWindowTitle(self._t("templates_title"))
        self.setMinimumSize(660, 540)
        self.resize(720, 580)

        self.templates = [dict(t) for t in templates]
        self.task_templates = [dict(t) for t in (task_templates or [])]
        # Small, directly-editable starter pack applied once to every NEW
        # character (User-Wunsch, 2026-09-05: "Man soll 2-3 Standard
        # Templates definieren und anpassen können") -- replaces the old
        # per-tab CSV Import/Export buttons at the same spot (earlier
        # User-Wunsch: "den Import und Export kann man durch die neue
        # Funktion dann entfernen"). Independent of the existing
        # is_general flag on regular templates (that one auto-adds to
        # EVERY character already; this only fires once, at creation --
        # see MainWindow._apply_standard_templates).
        standard_templates = standard_templates or {}
        self.standard_templates = {
            "tasks": [dict(t) for t in standard_templates.get("tasks", [])],
            "shopping": [dict(t) for t in standard_templates.get("shopping", [])],
        }
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

    def reject(self):
        # Real bug found + fixed (User-reported, 2026-09-05: templates/
        # Standard Templates added here showed up empty again later) --
        # this dialog has no actual "cancel and discard" semantics (every
        # add/edit/delete already applies straight to self.templates/
        # self.task_templates/self.standard_templates as you go, there's
        # no separate pending draft), so its "Close" button intentionally
        # calls accept(). But Qt's OWN native window X button and the
        # Escape key both call reject() by default, which this class never
        # overrode -- _open_template_dialog's entire "pull the edited
        # lists back into MainWindow" block only runs `if dlg.exec():`,
        # so closing via the X/Escape silently discarded the whole
        # session's edits instead of keeping them, with no error and no
        # visible sign anything was lost until the user reopened the
        # dialog later and found it back to how it was before.
        self.accept()

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
        standards_btn = QPushButton(self._t("standards_manage_btn"))
        standards_btn.setObjectName("secondaryButton")
        standards_btn.setCursor(Qt.PointingHandCursor)
        standards_btn.clicked.connect(lambda: self._open_standards_manager(is_shop=True))
        self._shop_add_btn = QPushButton(self._t("template_add_btn"))
        self._shop_add_btn.setObjectName("primaryButton")
        self._shop_add_btn.clicked.connect(self._handle_shop_add_btn)
        header.addWidget(info)
        header.addStretch()
        header.addWidget(standards_btn)
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
        # Viewport paints its own background separately from #scrollArea's
        # own QSS rule -- can show up as a plain white box when Windows
        # itself is set to dark mode (User-reported, 2026-08-29).
        scroll.viewport().setStyleSheet("background: transparent;")
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
        standards_btn = QPushButton(self._t("standards_manage_btn"))
        standards_btn.setObjectName("secondaryButton")
        standards_btn.setCursor(Qt.PointingHandCursor)
        standards_btn.clicked.connect(lambda: self._open_standards_manager(is_shop=False))
        self._task_add_btn = QPushButton(self._t("task_add_btn"))
        self._task_add_btn.setObjectName("primaryButton")
        self._task_add_btn.clicked.connect(self._handle_task_add_btn)
        header.addWidget(info)
        header.addStretch()
        header.addWidget(standards_btn)
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
        # Same viewport-background fix as the shop-list scroll area above
        # (User-reported Windows-dark-mode white box, 2026-08-29).
        scroll.viewport().setStyleSheet("background: transparent;")
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
                                  language=self._language, tr_func=self._tr,
                                  item_picker_callback=self._item_picker_callback)
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
                item_picker_callback=self._item_picker_callback,
            )
            if dlg.exec():
                data = dlg.get_data()
                data["id"] = self.templates[index].get("id", str(uuid4()))
                data["is_general"] = self.templates[index].get("is_general", False)
                data["amount"] = self.templates[index].get("amount", "1")
                data["character"] = self.templates[index].get("character", "")
                data["_from_import"] = self.templates[index].get("_from_import", False)
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
                data["character"] = self.task_templates[index].get("character", "")
                data["_from_import"] = self.task_templates[index].get("_from_import", False)
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

    # ── Standard Templates ("Standards verwalten") ──────────────────────────
    # Replaced the old per-tab CSV Import/Export at this exact spot (User-
    # Wunsch, 2026-09-05: "den Import und Export kann man durch die neue
    # Funktion dann entfernen"). A small, directly-editable starter pack
    # ("Man soll 2-3 Standard Templates definieren und anpassen können"),
    # applied once to every brand-new character -- see MainWindow.
    # _apply_standard_templates. Reuses _TemplateEditDialog for add/edit
    # (same form Shopping/Task templates already use) rather than a new
    # bespoke one.

    def get_standard_templates(self) -> dict:
        return self.standard_templates

    def _open_standards_manager(self, is_shop: bool):
        dlg = _StandardTemplatesDialog(
            self.standard_templates["shopping" if is_shop else "tasks"],
            is_shop=is_shop, known_locations=self._known_shop_locations() if is_shop else self._known_task_locations(),
            available_templates=self.templates if is_shop else self.task_templates,
            parent=self, language=self._language, tr_func=self._tr,
            item_picker_callback=self._item_picker_callback if is_shop else None,
        )
        if dlg.exec():
            self.standard_templates["shopping" if is_shop else "tasks"] = dlg.get_items()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_templates(self) -> list:
        return self.templates

    def get_task_templates(self) -> list:
        return self.task_templates


class _StandardTemplatePickerDialog(QDialog):
    """Multi-select over the already-existing Shopping/Task template
    catalog (User-Wunsch, 2026-09-05: "hier sollte man aus der bereits
    vorhandenen Template Liste wählen") -- the caller (_StandardTemplates
    Dialog._on_add) already filters out templates whose title is already
    in the Standard list, so everything shown here is a real, pickable
    option."""

    def __init__(self, templates: list[dict], parent=None, language: str = "en", tr_func=None):
        super().__init__(parent)
        self._templates = templates
        self._checks: list[QCheckBox] = []
        # (row widget, schedule, location) per template, in the same order
        # as self._templates/self._checks -- drives both the schedule/
        # location filters below (User-Wunsch, 2026-09-05: "hier wären
        # dann Filter nice, wie Schedule und location") and Select/
        # Deselect All, which only ever touches currently VISIBLE rows so
        # bulk-checking after narrowing down never silently checks
        # something hidden the user hasn't actually looked at.
        self._rows: list[tuple[QFrame, str, str]] = []
        self._schedule_filter = "all"
        self._location_filter = "all"
        self._language = language
        self._tr = tr_func or (lambda _l, k, **kw: k)

        self.setWindowTitle(self._t("standards_pick_title"))
        self.setMinimumSize(380, 460)
        self.resize(420, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        if not templates:
            empty = QLabel(self._t("standards_pick_empty"))
            empty.setObjectName("subtitle")
            empty.setWordWrap(True)
            layout.addWidget(empty)
        else:
            filter_row = QHBoxLayout()
            filter_row.setSpacing(6)
            sched_group = QButtonGroup(self)
            sched_group.setExclusive(True)
            for key, label in (("all", self._t("standards_pick_filter_all_schedules")), ("daily", "DAILY"), ("weekly", "WEEKLY"), ("season", "SEASON")):
                btn = QPushButton(label)
                btn.setObjectName("filterButton")
                btn.setCheckable(True)
                btn.setChecked(key == "all")
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda _c=False, k=key: self._on_schedule_filter_changed(k))
                sched_group.addButton(btn)
                filter_row.addWidget(btn)

            locations = sorted({t.get("location", "").strip() for t in templates if t.get("location", "").strip()})
            if locations:
                self._location_combo = QComboBox()
                self._location_combo.addItem(self._t("standards_pick_filter_all_locations"), "all")
                for loc in locations:
                    self._location_combo.addItem(loc, loc)
                self._location_combo.currentIndexChanged.connect(self._on_location_filter_changed)
                filter_row.addWidget(self._location_combo, 1)
            else:
                filter_row.addStretch()
            layout.addLayout(filter_row)

            select_row = QHBoxLayout()
            select_all_btn = QPushButton(self._t("standards_pick_select_all"))
            select_all_btn.setObjectName("secondaryButton")
            select_all_btn.setCursor(Qt.PointingHandCursor)
            select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
            deselect_all_btn = QPushButton(self._t("standards_pick_deselect_all"))
            deselect_all_btn.setObjectName("secondaryButton")
            deselect_all_btn.setCursor(Qt.PointingHandCursor)
            deselect_all_btn.clicked.connect(lambda: self._set_all_checked(False))
            select_row.addWidget(select_all_btn)
            select_row.addWidget(deselect_all_btn)
            select_row.addStretch()
            layout.addLayout(select_row)

            list_container = QWidget()
            list_layout = QVBoxLayout(list_container)
            list_layout.setContentsMargins(0, 0, 0, 0)
            list_layout.setSpacing(4)
            for tmpl in templates:
                row = QFrame()
                row.setObjectName("taskCard")
                row.setCursor(Qt.PointingHandCursor)
                hl = QHBoxLayout(row)
                hl.setContentsMargins(10, 8, 10, 8)
                hl.setSpacing(10)
                check = QCheckBox(tmpl.get("title", "—"))
                check.setCursor(Qt.PointingHandCursor)
                # Real bug found + fixed (User-reported, 2026-09-05:
                # "das Haken setzen geht teilweise noch nicht oder [nur]
                # durch mehrfaches klicken") -- QCheckBox's own clickable
                # ("hitButton") region can be narrower than its full
                # widget rect once custom QSS is applied, and a plain
                # QLabel (sched_badge) swallows the mouse press it
                # receives without forwarding it to its parent either way
                # -- either dead zone silently ate the click, delivering
                # it to a widget that never calls row.mousePressEvent at
                # all. WA_TransparentForMouseEvents makes both widgets
                # pass every click straight through to the row underneath,
                # so ONE handler (below) reliably owns every pixel of the
                # card, with no ambiguous double-handling to get wrong.
                check.setAttribute(Qt.WA_TransparentForMouseEvents)
                self._checks.append(check)
                hl.addWidget(check, 1)
                sched = tmpl.get("schedule", "daily")
                sched_badge = QLabel(_SCHEDULE_TEXTS.get(sched, sched.upper()))
                sched_badge.setObjectName(_SCHEDULE_NAMES.get(sched, "scheduleDaily"))
                sched_badge.setAttribute(Qt.WA_TransparentForMouseEvents)
                hl.addWidget(sched_badge)

                def on_row_press(event, c=check, r=row):
                    c.setChecked(not c.isChecked())
                    QFrame.mousePressEvent(r, event)
                row.mousePressEvent = on_row_press

                self._rows.append((row, sched, tmpl.get("location", "").strip()))
                list_layout.addWidget(row)
            list_layout.addStretch()

            scroll = QScrollArea()
            scroll.setWidget(list_container)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setObjectName("scrollArea")
            scroll.viewport().setStyleSheet("background: transparent;")
            layout.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._t("cancel"))
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        apply_btn = QPushButton(self._t("standards_pick_apply_btn"))
        apply_btn.setObjectName("primaryButton")
        apply_btn.clicked.connect(self.accept)
        apply_btn.setEnabled(bool(templates))
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

    def _t(self, key: str, **kwargs) -> str:
        return self._tr(self._language, key, **kwargs)

    def get_selected(self) -> list[dict]:
        return [t for t, c in zip(self._templates, self._checks) if c.isChecked()]

    def _set_all_checked(self, checked: bool):
        # Only currently VISIBLE rows -- narrowing down with a filter then
        # hitting Select All shouldn't silently check items the filter is
        # hiding, which the user hasn't actually looked at.
        for row, check in zip((r for r, _s, _l in self._rows), self._checks):
            if row.isVisible():
                check.setChecked(checked)

    def _on_schedule_filter_changed(self, key: str):
        self._schedule_filter = key
        self._apply_filters()

    def _on_location_filter_changed(self, _index: int):
        self._location_filter = self._location_combo.currentData()
        self._apply_filters()

    def _apply_filters(self):
        for row, schedule, location in self._rows:
            sched_ok = self._schedule_filter == "all" or schedule == self._schedule_filter
            loc_ok = self._location_filter == "all" or location == self._location_filter
            row.setVisible(sched_ok and loc_ok)


class _StandardTemplatesDialog(QDialog):
    """Small, focused list for "Standards verwalten" (User-Wunsch, 2026-
    09-05: "Man soll 2-3 Standard Templates definieren und anpassen
    können") -- add/edit/delete a handful of template entries applied
    once to every brand-new character. Deliberately its own tiny list
    (no search/sort, unlike the main Shopping/Tasks tabs) since it's
    meant to stay small; reuses _TemplateEditDialog for the actual add/
    edit form, same as the main tabs do."""

    def __init__(self, items: list[dict], is_shop: bool, known_locations: list[str],
                 available_templates: list[dict] | None = None,
                 parent=None, language: str = "en", tr_func=None, item_picker_callback=None):
        super().__init__(parent)
        self._items = [dict(t) for t in items]
        self._is_shop = is_shop
        self._known_locations = known_locations
        # The already-existing Shopping/Task template catalog (User-Wunsch,
        # 2026-09-05: "hier sollte man aus der bereits vorhandenen Template
        # Liste wählen") -- "+ Add Template" below picks FROM this instead
        # of opening a blank creation form, so nothing gets typed twice.
        self._available_templates = list(available_templates or [])
        self._language = language
        self._tr = tr_func or (lambda _l, k, **kw: k)
        self._item_picker_callback = item_picker_callback

        self.setWindowTitle(self._t("standards_manage_title"))
        self.setMinimumSize(420, 420)
        self.resize(460, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        info = QLabel(self._t("standards_manage_desc"))
        info.setObjectName("subtitle")
        info.setWordWrap(True)
        layout.addWidget(info)

        add_btn = QPushButton(self._t("template_add_btn"))
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._on_add)
        layout.addWidget(add_btn, 0, Qt.AlignRight)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self._list_container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("scrollArea")
        # Same dark-mode viewport fix already applied to every other list
        # in this file (User-reported, 2026-08-29).
        scroll.viewport().setStyleSheet("background: transparent;")
        layout.addWidget(scroll, 1)

        close_btn = QPushButton(self._t("close"))
        close_btn.setObjectName("primaryButton")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignRight)

        self._rebuild_list()

    def reject(self):
        # Same fix as TemplateDialog.reject -- no real cancel semantics
        # (add/edit/delete already apply straight to self._items), so the
        # native window X / Escape must commit too, not silently discard
        # the whole session like Qt's default reject() would.
        self.accept()

    def _t(self, key: str, **kwargs) -> str:
        return self._tr(self._language, key, **kwargs)

    def get_items(self) -> list[dict]:
        return self._items

    def _rebuild_list(self):
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, tmpl in enumerate(self._items):
            row = self._make_row(i, tmpl)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def _make_row(self, index: int, tmpl: dict) -> QWidget:
        row = QFrame()
        row.setObjectName("taskCard")

        hl = QHBoxLayout(row)
        hl.setContentsMargins(12, 10, 12, 10)
        hl.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        title_lbl = QLabel(tmpl.get("title", "—"))
        title_lbl.setObjectName("taskTitle")
        text_col.addWidget(title_lbl)

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
        edit_btn.clicked.connect(lambda _c=False, i=index: self._on_edit(i))

        del_btn = QPushButton("×")
        del_btn.setObjectName("deleteButton")
        del_btn.setFixedSize(32, 30)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(lambda _c=False, i=index: self._on_delete(i))

        hl.addLayout(text_col, 1)
        hl.addWidget(edit_btn)
        hl.addWidget(del_btn)
        return row

    def _on_add(self):
        already = {t.get("title", "").strip().lower() for t in self._items if t.get("title")}
        pickable = [t for t in self._available_templates if t.get("title", "").strip().lower() not in already]
        dlg = _StandardTemplatePickerDialog(pickable, parent=self, language=self._language, tr_func=self._tr)
        if not dlg.exec():
            return
        for tmpl in dlg.get_selected():
            # A COPY with its own new id, not a reference -- editing it
            # afterward via _on_edit must never touch the source template
            # in the main Shopping/Tasks list ("...und anpassen können").
            item = dict(tmpl)
            item["id"] = str(uuid4())
            item["is_general"] = False
            if self._is_shop:
                item.setdefault("amount", "1")
            self._items.append(item)
        self._rebuild_list()

    def _on_edit(self, index: int):
        if not (0 <= index < len(self._items)):
            return
        dlg = _TemplateEditDialog(
            self._items[index], known_locations=self._known_locations, parent=self,
            task_mode=not self._is_shop, language=self._language, tr_func=self._tr,
            item_picker_callback=self._item_picker_callback,
        )
        if dlg.exec():
            data = dlg.get_data()
            data["id"] = self._items[index].get("id", str(uuid4()))
            if self._is_shop:
                data["amount"] = self._items[index].get("amount", "1")
            self._items[index] = data
            self._rebuild_list()

    def _on_delete(self, index: int):
        if 0 <= index < len(self._items):
            self._items.pop(index)
            self._rebuild_list()


class _TemplateEditDialog(QDialog):
    """Edit form for shopping and task templates. Pass task_mode=True to hide currency/price."""

    def __init__(self, data: dict = None, known_locations: list[str] = None, parent=None,
                 task_mode: bool = False, language: str = "en", tr_func=None,
                 item_picker_callback=None):
        super().__init__(parent)
        data = data or {}
        known_locations = known_locations or []
        self._task_mode = task_mode
        self._tr = tr_func or (lambda _l, k, **kw: k)
        self._language = language
        self._item_picker_callback = item_picker_callback

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

        # "Import from Database" (User-Wunsch, 2026-08-29): picks a real item
        # name from the catalog straight into the Title field -- shopping
        # entries only, a Task isn't necessarily a real game item. Still
        # freely editable afterward, this just pre-fills the field.
        if not task_mode and self._item_picker_callback:
            import_link = QPushButton(self._t("template_import_from_db"))
            import_link.setObjectName("linkButton")
            import_link.setCursor(Qt.PointingHandCursor)
            import_link.setFlat(True)
            import_link.clicked.connect(self._open_import_from_db)
            layout.addWidget(import_link, 0, Qt.AlignLeft)

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
            self._np_btn    = self._toggle("NC",    "currencyToggleAbyss")
            self._sc_btn    = self._toggle("SC",    "currencyToggleAbyss")
            self._abyss_btn.setToolTip("Abyss Points")
            self._np_btn.setToolTip("Nightmare Coins")
            self._sc_btn.setToolTip("Season Coins")
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

    def _open_import_from_db(self):
        if not self._item_picker_callback:
            return
        item = self._item_picker_callback(self)
        if item:
            self._title.setText(item.get("name", ""))

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
