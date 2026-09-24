from uuid import uuid4

from core.persistence import LEGACY_STANDARD_SET_NAME, migrate_standard_templates
from ui.widgets.shopping_card import format_currency_price
from ui.widgets import icons
from PySide6.QtCore import Qt, QEvent, QObject, QSize
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
    QInputDialog,
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


class _CheckRow(QFrame):
    """A row whose whole surface toggles the one checkbox it contains.

    Replaces ``row.mousePressEvent = on_row_press`` (review G/L4), a closure
    that captured the row *and* its checkbox as default arguments and was
    stored in the row's own ``__dict__`` — a reference cycle rooted on a
    live Qt object, which ``deleteLater()`` cannot break: the C++ widget is
    freed while the Python wrapper keeps the whole dialog subtree reachable
    until a full ``gc.collect()`` happens to run.

    The checkbox is found through the Qt parent/child tree rather than
    captured, so this class holds no Python reference to anything: exactly
    the ``ui/main_window.py::_CardPressFilter`` / ``ArmoryCard`` pattern,
    in the one shape that fits here (the rows are built inline, one
    checkbox each, and the behaviour belongs to the row itself).

    The children are ``WA_TransparentForMouseEvents`` (User-reported,
    2026-09-05: QCheckBox's own hitButton region is narrower than the
    widget once QSS is applied, and a QLabel swallows the press), so this
    one handler really does own every pixel of the row.
    """

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            check = self.findChild(QCheckBox)
            if check is not None:
                check.setChecked(not check.isChecked())
        # The old closure ended in ``QFrame.mousePressEvent(r, event)``.
        super().mousePressEvent(event)


class _RowSelectFilter(QObject):
    """Turns a left-click on a template row into "select that row".

    Replaces ``row.mousePressEvent = lambda _e, i=index: self._select_*(i)``
    (review G/L1) — the same cycle as above and the highest-frequency one in
    the app: the rows are rebuilt on **every keystroke** in the search box
    (``_on_shop_search_changed`` / ``_on_task_search_changed``), so each
    keystroke orphaned a pinned copy of the row subtree.

    An event filter needs no capture at all: Qt hands it the event target,
    so the row arrives as ``obj``, its index comes off the row as a Qt
    *property* (C++ side), and the dialog is reachable through the filter's
    Qt parent.  One filter serves every row of both lists.
    """

    #: Row property -> the ``TemplateDialog`` method that selects it.
    _SELECTORS = {"shop": "_select_shop_row", "task": "_select_task_row"}

    def eventFilter(self, obj, event):
        if event.type() != QEvent.MouseButtonPress or event.button() != Qt.LeftButton:
            return False
        dialog = self.parent()
        index = obj.property("rowIndex")
        selector = self._SELECTORS.get(obj.property("rowKind"))
        if dialog is None or index is None or selector is None:
            return False
        getattr(dialog, selector)(int(index))
        # True, not False: the old closure REPLACED the row's
        # mousePressEvent, so the row's own handler never ran and the press
        # never propagated to the list container behind it.
        return True


def _h_separator() -> QFrame:
    # A 1 px rule, coloured by #dialogSeparator in the template.  Was an
    # inline rgba(100, 116, 139, 0.3) -- slate.500 at 30 %, a value in no
    # token table, repeated in three places in this file with two different
    # spellings.  The other two call sites now come here instead.
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setObjectName("dialogSeparator")
    return line


class TemplateDialog(QDialog):
    """Popup for managing item and task template catalogs."""

    def __init__(self, templates: list, flow_maps: dict, task_templates: list = None,
                 initial_tab: str = "shopping", parent=None,
                 language: str = "en", tr_func=None, item_picker_callback=None,
                 characters: list = None, standard_templates: dict = None,
                 default_standard_templates: dict = None):
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
        #
        # Shape as of the "Mehrere benennbare/umbenennbare Standard-
        # Template-Sets" Planner task (freigegeben 2026-09-23):
        # {"tasks": {"SetName": [...], ...}, "shopping": {"SetName": [...]}}
        # -- multiple NAMED sets per kind instead of one un-named pack,
        # so a user can e.g. keep a "Daily Grind" Tasks set and a
        # "Weekly Crafting" Tasks set side by side. Tasks and Shopping stay
        # fully independent collections of sets, same as they were already
        # independent single lists (User-Wunsch, 2026-09-23: no assumption
        # that a same-named Tasks/Shopping set pair means anything).
        # Assignment to a character happens by NAME PICK at apply time --
        # no Main/Twink tag is ever stored on the character itself (tobia,
        # 2026-09-23, explicit clarification).
        standard_templates = migrate_standard_templates(standard_templates)
        self.standard_templates = {
            "tasks": {name: [dict(t) for t in entries]
                      for name, entries in standard_templates["tasks"].items()},
            "shopping": {name: [dict(t) for t in entries]
                         for name, entries in standard_templates["shopping"].items()},
        }
        # Which named set each tab's "standards" view is currently showing
        # -- lazily created on first "standards" view (see _current_set_name
        # / _ensure_std_set) rather than up front, so a profile with zero
        # Standard Template Sets doesn't spuriously grow an empty "Default"
        # set just from opening this dialog.
        self._shop_std_set: str | None = next(iter(self.standard_templates["shopping"]), None)
        self._task_std_set: str | None = next(iter(self.standard_templates["tasks"]), None)
        # The language-matched Default profile's OWN Standard Template Sets
        # -- read-only reference for "⟳ Sync" (User-Wunsch, 2026-09-10),
        # never written back to. MainWindow resolves which Default file this
        # is (same language-fallback logic as _preferred_default()) since
        # only it knows the profiles directory / frozen-app path. Same
        # named-set shape as self.standard_templates; Sync now matches the
        # CURRENTLY SELECTED set in THIS profile against the SAME-NAMED set
        # in the Default profile (User-Wunsch, 2026-09-23: Sync needs to
        # know which of the now-multiple sets it's comparing against).
        default_standard_templates = migrate_standard_templates(default_standard_templates)
        self._default_standard_templates = default_standard_templates
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
        # "Templates" / "★ Standard Templates" mode per tab (User-Wunsch,
        # 2026-09-10: "Manage Standards" popup replaced by a segmented
        # toggle -- same visual pattern as the Tasks/Shopping add-row
        # toolbar's own Templates/Standards switch, "Option B" from the
        # preview -- so Standards now renders INLINE in this same list
        # instead of a separate dialog. Independent per tab since Shopping
        # and Tasks each have their own separate Standard Templates list.
        self._shop_view_mode: str = "templates"
        self._task_view_mode: str = "templates"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        # ── Tab widget ────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.addTab(self._make_shop_tab(), self._t("tab_shopping"))
        self._tabs.addTab(self._make_tasks_tab(), self._t("tab_tasks"))
        # The two labels used to start with "🛒"/"📋" — tofu on a stock
        # Linux font stack.  A QTabWidget takes a real QIcon instead.
        self._tabs.setTabIcon(0, icons.icon("shopping-cart", 16))
        self._tabs.setTabIcon(1, icons.icon("list-todo", 16))
        self._tabs.setIconSize(QSize(16, 16))
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
        header.setSpacing(6)
        self._shop_source_tmpl_btn = QPushButton(self._t("template_source_templates"))
        self._shop_source_tmpl_btn.setObjectName("filterButton")
        self._shop_source_tmpl_btn.setCursor(Qt.PointingHandCursor)
        self._shop_source_tmpl_btn.setProperty("active", True)
        self._shop_source_tmpl_btn.clicked.connect(lambda: self._set_shop_view_mode("templates"))
        self._shop_source_std_btn = QPushButton(self._t("template_source_standards"))
        self._shop_source_std_btn.setObjectName("filterButton")
        self._shop_source_std_btn.setCursor(Qt.PointingHandCursor)
        self._shop_source_std_btn.clicked.connect(lambda: self._set_shop_view_mode("standards"))
        self._shop_info_label = QLabel(self._t("shop_tab_info"))
        self._shop_info_label.setObjectName("subtitle")
        self._shop_sync_btn = QPushButton()
        icons.set_icon(self._shop_sync_btn, "refresh-cw", 16, clear_text=False)
        self._shop_sync_btn.setObjectName("secondaryButton")
        self._shop_sync_btn.setCursor(Qt.PointingHandCursor)
        self._shop_sync_btn.clicked.connect(lambda: self._open_sync_dialog("shopping"))
        self._shop_sync_btn.setVisible(False)
        self._shop_add_btn = QPushButton(self._t("template_add_btn"))
        self._shop_add_btn.setObjectName("primaryButton")
        self._shop_add_btn.clicked.connect(self._handle_shop_add_btn)
        header.addWidget(self._shop_source_tmpl_btn)
        header.addWidget(self._shop_source_std_btn)
        header.addStretch()
        header.addWidget(self._shop_sync_btn)
        header.addWidget(self._shop_add_btn)
        vl.addLayout(header)

        self._shop_set_row = self._make_set_switcher_row("shopping")
        vl.addLayout(self._shop_set_row)
        self._refresh_set_row("shopping")

        # UX audit 2026-09-18, M1: sitting inside the header row, this
        # legend got squeezed between the source tabs and the "Add" button
        # and rendered clipped ("☑ = quest appears automatically in the
        # task…"). It reads as a caption for the list below anyway, so it
        # gets its own full-width row under the controls.
        self._shop_info_label.setWordWrap(True)
        vl.addWidget(self._shop_info_label)

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
        scroll.viewport().setObjectName("transparentViewport")
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
        header.setSpacing(6)
        self._task_source_tmpl_btn = QPushButton(self._t("template_source_templates"))
        self._task_source_tmpl_btn.setObjectName("filterButton")
        self._task_source_tmpl_btn.setCursor(Qt.PointingHandCursor)
        self._task_source_tmpl_btn.setProperty("active", True)
        self._task_source_tmpl_btn.clicked.connect(lambda: self._set_task_view_mode("templates"))
        self._task_source_std_btn = QPushButton(self._t("template_source_standards"))
        self._task_source_std_btn.setObjectName("filterButton")
        self._task_source_std_btn.setCursor(Qt.PointingHandCursor)
        self._task_source_std_btn.clicked.connect(lambda: self._set_task_view_mode("standards"))
        self._task_info_label = QLabel(self._t("task_tab_info"))
        self._task_info_label.setObjectName("subtitle")
        self._task_sync_btn = QPushButton()
        icons.set_icon(self._task_sync_btn, "refresh-cw", 16, clear_text=False)
        self._task_sync_btn.setObjectName("secondaryButton")
        self._task_sync_btn.setCursor(Qt.PointingHandCursor)
        self._task_sync_btn.clicked.connect(lambda: self._open_sync_dialog("tasks"))
        self._task_sync_btn.setVisible(False)
        self._task_add_btn = QPushButton(self._t("task_add_btn"))
        self._task_add_btn.setObjectName("primaryButton")
        self._task_add_btn.clicked.connect(self._handle_task_add_btn)
        header.addWidget(self._task_source_tmpl_btn)
        header.addWidget(self._task_source_std_btn)
        header.addStretch()
        header.addWidget(self._task_sync_btn)
        header.addWidget(self._task_add_btn)
        vl.addLayout(header)

        self._task_set_row = self._make_set_switcher_row("tasks")
        vl.addLayout(self._task_set_row)
        self._refresh_set_row("tasks")

        # Own row under the controls -- see the Shopping tab's twin comment
        # (UX audit 2026-09-18, M1: clipped by the Add Task button).
        self._task_info_label.setWordWrap(True)
        vl.addWidget(self._task_info_label)

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
        scroll.viewport().setObjectName("transparentViewport")
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

    # ── Standard Template Set switcher (shared by Shopping + Tasks) ────────────
    # Same combo + icon-button-row pattern as Equip Sets/Skill Builds in the
    # Build Planner (ItemDatabase/app.py::_rebuild_equip_build_tabs) --
    # Planner task "Mehrere benennbare/umbenennbare Standard-Template-Sets"
    # asked for exactly that visual reuse. Shopping and Tasks each keep
    # their OWN independent named sets (self._shop_std_set /
    # self._task_std_set track which one each tab is showing), same
    # independence the two tabs already had as separate flat lists before
    # this change.

    def _set_kind_state(self, kind: str):
        """(sets dict, current-name attr name, view-mode attr, combo attr)
        for `kind` -- keeps every set-management method kind-agnostic
        instead of duplicating it once per Shopping/Tasks."""
        if kind == "shopping":
            return self.standard_templates["shopping"], "_shop_std_set", self._shop_view_mode
        return self.standard_templates["tasks"], "_task_std_set", self._task_view_mode

    def _current_set_name(self, kind: str) -> str | None:
        sets, attr, _ = self._set_kind_state(kind)
        name = getattr(self, attr)
        if name not in sets:
            name = next(iter(sets), None)
            setattr(self, attr, name)
        return name

    def _current_set_list(self, kind: str) -> list[dict]:
        """The live list for `kind`'s currently selected set -- creating
        the set on first write would be surprising, so this returns a
        throwaway empty list (never stored) when there is no set yet;
        callers that ADD an entry go through _ensure_set_for_add instead."""
        sets, _, _ = self._set_kind_state(kind)
        name = self._current_set_name(kind)
        return sets.get(name, [])

    def _ensure_set_for_add(self, kind: str) -> str:
        """The set name new entries should be added to -- creates one
        named set (LEGACY_STANDARD_SET_NAME) the first time a user adds a
        Standard Template entry to a profile that has none yet, so the
        "+Add" button on the Standards view always has somewhere to put
        the new entry without forcing an explicit "create a set first"
        step for the common single-set case."""
        sets, attr, _ = self._set_kind_state(kind)
        name = self._current_set_name(kind)
        if name is None:
            name = LEGACY_STANDARD_SET_NAME
            sets[name] = []
            setattr(self, attr, name)
        return name

    def _make_set_switcher_row(self, kind: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)

        combo = QComboBox()
        combo.setObjectName("BuildSwitcherCombo")
        combo.setMinimumWidth(160)
        combo.currentTextChanged.connect(lambda name, k=kind: self._on_switch_set(k, name))
        row.addWidget(combo)

        add_btn = QPushButton()
        icons.set_icon(add_btn, "plus", 16, clear_text=False)
        add_btn.setToolTip(self._t("standards_set_add"))
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(lambda _c=False, k=kind: self._on_add_set(k))
        row.addWidget(add_btn)

        duplicate_btn = QPushButton()
        icons.set_icon(duplicate_btn, "copy", 16, clear_text=False)
        duplicate_btn.setToolTip(self._t("standards_set_duplicate"))
        duplicate_btn.setCursor(Qt.PointingHandCursor)
        duplicate_btn.clicked.connect(lambda _c=False, k=kind: self._on_duplicate_set(k))
        row.addWidget(duplicate_btn)

        rename_btn = QPushButton()
        icons.set_icon(rename_btn, "pencil", 16, clear_text=False)
        rename_btn.setToolTip(self._t("standards_set_rename"))
        rename_btn.setCursor(Qt.PointingHandCursor)
        rename_btn.clicked.connect(lambda _c=False, k=kind: self._on_rename_set(k))
        row.addWidget(rename_btn)

        delete_btn = QPushButton()
        icons.set_icon(delete_btn, "trash", 16, clear_text=False)
        delete_btn.setToolTip(self._t("standards_set_delete"))
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(lambda _c=False, k=kind: self._on_delete_set(k))
        row.addWidget(delete_btn)

        row.addStretch()

        if kind == "shopping":
            self._shop_set_combo = combo
            self._shop_set_add_btn = add_btn
            self._shop_set_duplicate_btn = duplicate_btn
            self._shop_set_rename_btn = rename_btn
            self._shop_set_delete_btn = delete_btn
        else:
            self._task_set_combo = combo
            self._task_set_add_btn = add_btn
            self._task_set_duplicate_btn = duplicate_btn
            self._task_set_rename_btn = rename_btn
            self._task_set_delete_btn = delete_btn
        # NOT self._refresh_set_row(kind) here -- the caller hasn't stored
        # this row on self._shop_set_row/_task_set_row yet (it does that
        # with THIS method's return value), and _refresh_set_row needs
        # that attribute through _set_row_widgets(). Callers refresh right
        # after assigning the row.
        return row

    def _set_row_widgets(self, kind: str):
        if kind == "shopping":
            return (self._shop_set_row, self._shop_set_combo, self._shop_set_add_btn,
                    self._shop_set_duplicate_btn, self._shop_set_rename_btn, self._shop_set_delete_btn)
        return (self._task_set_row, self._task_set_combo, self._task_set_add_btn,
                self._task_set_duplicate_btn, self._task_set_rename_btn, self._task_set_delete_btn)

    def _refresh_set_row(self, kind: str):
        """Repopulates `kind`'s set combo and shows/hides the whole row --
        only relevant on the "standards" view, exactly like the Equip Sets
        switcher only exists inside its own page."""
        sets, _, view_mode = self._set_kind_state(kind)
        row_layout, combo, add_btn, dup_btn, rename_btn, del_btn = self._set_row_widgets(kind)
        is_std = view_mode == "standards"
        for i in range(row_layout.count()):
            w = row_layout.itemAt(i).widget()
            if w is not None:
                w.setVisible(is_std)
        if not is_std:
            return
        current = self._current_set_name(kind)
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(list(sets.keys()))
        if current is not None:
            combo.setCurrentText(current)
        combo.blockSignals(False)
        has_sets = bool(sets)
        combo.setEnabled(has_sets)
        # Duplicate/rename/delete need an existing set to act on; a
        # brand-new profile with zero sets only offers "+".
        for btn in (dup_btn, rename_btn, del_btn):
            btn.setEnabled(has_sets)

    def _on_switch_set(self, kind: str, name: str):
        if not name:
            return
        _, attr, _ = self._set_kind_state(kind)
        if getattr(self, attr) == name:
            return
        setattr(self, attr, name)
        if kind == "shopping":
            self._selected_shop_index = None
            self._update_shop_add_btn()
            self._update_shop_sync_btn()
            self._rebuild_shop_list()
        else:
            self._selected_task_index = None
            self._update_task_add_btn()
            self._update_task_sync_btn()
            self._rebuild_task_list()

    def _on_add_set(self, kind: str):
        sets, attr, _ = self._set_kind_state(kind)
        name, ok = QInputDialog.getText(self, self._t("standards_set_add_title"), self._t("standards_set_name_colon"))
        name = name.strip()
        if not ok or not name or name in sets:
            return
        sets[name] = []
        setattr(self, attr, name)
        self._refresh_set_row(kind)
        if kind == "shopping":
            self._rebuild_shop_list()
            self._update_shop_sync_btn()
        else:
            self._rebuild_task_list()
            self._update_task_sync_btn()

    def _on_duplicate_set(self, kind: str):
        sets, attr, _ = self._set_kind_state(kind)
        source_name = self._current_set_name(kind)
        if source_name is None:
            return
        default_name = self._t("standards_set_duplicate_default_name", name=source_name)
        name, ok = QInputDialog.getText(self, self._t("standards_set_duplicate_title"),
                                        self._t("standards_set_name_colon"), text=default_name)
        name = name.strip()
        if not ok or not name or name in sets:
            return
        sets[name] = [dict(t) for t in sets[source_name]]
        setattr(self, attr, name)
        self._refresh_set_row(kind)
        if kind == "shopping":
            self._rebuild_shop_list()
        else:
            self._rebuild_task_list()

    def _on_rename_set(self, kind: str):
        sets, attr, _ = self._set_kind_state(kind)
        old_name = self._current_set_name(kind)
        if old_name is None:
            return
        new_name, ok = QInputDialog.getText(self, self._t("standards_set_rename_title"),
                                            self._t("standards_set_name_colon"), text=old_name)
        new_name = new_name.strip()
        if not ok or not new_name or new_name == old_name or new_name in sets:
            return
        # dict preserves insertion order in Python 3.7+, so building a new
        # dict in the same order (renaming in place) keeps the combo's
        # item order stable instead of moving the renamed set to the end.
        sets[new_name] = sets.pop(old_name)
        renamed = {}
        for key, value in sets.items():
            renamed[new_name if key == new_name else key] = value
        sets.clear()
        sets.update(renamed)
        setattr(self, attr, new_name)
        self._refresh_set_row(kind)

    def _on_delete_set(self, kind: str):
        sets, attr, _ = self._set_kind_state(kind)
        name = self._current_set_name(kind)
        if name is None:
            return
        reply = QMessageBox.question(
            self, self._t("standards_set_delete_confirm_title"),
            self._t("standards_set_delete_confirm_text", name=name),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        sets.pop(name, None)
        setattr(self, attr, next(iter(sets), None))
        self._refresh_set_row(kind)
        if kind == "shopping":
            self._selected_shop_index = None
            self._update_shop_add_btn()
            self._rebuild_shop_list()
        else:
            self._selected_task_index = None
            self._update_task_add_btn()
            self._rebuild_task_list()

    # ── Shopping list rendering ───────────────────────────────────────────────

    def _set_shop_view_mode(self, mode: str):
        if mode == self._shop_view_mode:
            return
        self._shop_view_mode = mode
        self._selected_shop_index = None
        is_std = mode == "standards"
        self._shop_source_tmpl_btn.setProperty("active", not is_std)
        self._shop_source_std_btn.setProperty("active", is_std)
        for b in (self._shop_source_tmpl_btn, self._shop_source_std_btn):
            b.style().unpolish(b)
            b.style().polish(b)
        self._shop_info_label.setVisible(not is_std)
        self._shop_sync_btn.setVisible(is_std)
        if is_std:
            self._update_shop_sync_btn()
        self._update_shop_add_btn()
        self._refresh_set_row("shopping")
        self._rebuild_shop_list()

    def _current_shop_list(self) -> list[dict]:
        return self._current_set_list("shopping") if self._shop_view_mode == "standards" else self.templates

    def _rebuild_shop_list(self):
        while self._shop_list_layout.count() > 1:
            item = self._shop_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        query = self._shop_search.strip().lower()
        for i, tmpl in enumerate(self._current_shop_list()):
            if query and query not in tmpl.get("title", "").lower() and query not in tmpl.get("location", "").lower():
                continue
            row = self._make_shop_row(i, tmpl)
            self._shop_list_layout.insertWidget(self._shop_list_layout.count() - 1, row)

    def _on_shop_search_changed(self, text: str):
        self._shop_search = text
        self._rebuild_shop_list()

    def _make_shop_row(self, index: int, tmpl: dict) -> QWidget:
        is_std = self._shop_view_mode == "standards"
        row = QFrame()
        row.setObjectName("taskCard")
        row.setProperty("selected", (not is_std) and index == self._selected_shop_index)
        if not is_std:
            row.setCursor(Qt.PointingHandCursor)
            self._wire_row(row, "shop", index)

        hl = QHBoxLayout(row)
        hl.setContentsMargins(12, 10, 12, 10)
        hl.setSpacing(10)

        if not is_std:
            check = QCheckBox()
            check.setChecked(bool(tmpl.get("is_general", False)))
            check.setToolTip(self._t("shop_check_tooltip"))
            check.setCursor(Qt.PointingHandCursor)
            check.stateChanged.connect(lambda state, i=index: self._set_shop_general(i, bool(state)))
            hl.addWidget(check)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)

        title_row = QHBoxLayout()
        title_lbl = QLabel(tmpl.get("title", "—"))
        title_lbl.setObjectName("taskTitle")
        currency = tmpl.get("currency", "kinah")
        price_raw = tmpl.get("price", "0")
        price_lbl = QLabel(format_currency_price(price_raw, currency))
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
        if not is_std:
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
        if is_std:
            edit_btn.clicked.connect(lambda _c=False, i=index: self._edit_standard_entry("shopping", i))
        else:
            edit_btn.clicked.connect(lambda _c=False, i=index: self._edit_shop_template(i))

        del_btn = QPushButton("×")
        del_btn.setObjectName("deleteButton")
        del_btn.setFixedSize(32, 30)
        del_btn.setCursor(Qt.PointingHandCursor)
        if is_std:
            del_btn.clicked.connect(lambda _c=False, i=index: self._delete_standard_entry("shopping", i))
        else:
            del_btn.clicked.connect(lambda _c=False, i=index: self._delete_shop_template(i))

        hl.addLayout(text_col, 1)
        hl.addWidget(edit_btn)
        hl.addWidget(del_btn)
        return row

    # ── Task list rendering ───────────────────────────────────────────────────

    def _set_task_view_mode(self, mode: str):
        if mode == self._task_view_mode:
            return
        self._task_view_mode = mode
        self._selected_task_index = None
        is_std = mode == "standards"
        self._task_source_tmpl_btn.setProperty("active", not is_std)
        self._task_source_std_btn.setProperty("active", is_std)
        for b in (self._task_source_tmpl_btn, self._task_source_std_btn):
            b.style().unpolish(b)
            b.style().polish(b)
        self._task_info_label.setVisible(not is_std)
        self._task_sync_btn.setVisible(is_std)
        if is_std:
            self._update_task_sync_btn()
        self._update_task_add_btn()
        self._refresh_set_row("tasks")
        self._rebuild_task_list()

    def _current_task_list(self) -> list[dict]:
        return self._current_set_list("tasks") if self._task_view_mode == "standards" else self.task_templates

    def _rebuild_task_list(self):
        while self._task_list_layout.count() > 1:
            item = self._task_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        query = self._task_search.strip().lower()
        for i, tmpl in enumerate(self._current_task_list()):
            if query and query not in tmpl.get("title", "").lower() and query not in tmpl.get("location", "").lower():
                continue
            row = self._make_task_row(i, tmpl)
            self._task_list_layout.insertWidget(self._task_list_layout.count() - 1, row)

    def _on_task_search_changed(self, text: str):
        self._task_search = text
        self._rebuild_task_list()

    def _make_task_row(self, index: int, tmpl: dict) -> QWidget:
        is_std = self._task_view_mode == "standards"
        row = QFrame()
        row.setObjectName("taskCard")
        row.setProperty("selected", (not is_std) and index == self._selected_task_index)
        if not is_std:
            row.setCursor(Qt.PointingHandCursor)
            self._wire_row(row, "task", index)

        hl = QHBoxLayout(row)
        hl.setContentsMargins(12, 10, 12, 10)
        hl.setSpacing(10)

        if not is_std:
            check = QCheckBox()
            check.setChecked(bool(tmpl.get("is_general", False)))
            check.setToolTip(self._t("task_check_tooltip"))
            check.setCursor(Qt.PointingHandCursor)
            check.stateChanged.connect(lambda state, i=index: self._set_task_general(i, bool(state)))
            hl.addWidget(check)

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
        if is_std:
            edit_btn.clicked.connect(lambda _c=False, i=index: self._edit_standard_entry("tasks", i))
        else:
            edit_btn.clicked.connect(lambda _c=False, i=index: self._edit_task_template(i))

        del_btn = QPushButton("×")
        del_btn.setObjectName("deleteButton")
        del_btn.setFixedSize(32, 30)
        del_btn.setCursor(Qt.PointingHandCursor)
        if is_std:
            del_btn.clicked.connect(lambda _c=False, i=index: self._delete_standard_entry("tasks", i))
        else:
            del_btn.clicked.connect(lambda _c=False, i=index: self._delete_task_template(i))

        hl.addLayout(text_col, 1)
        hl.addWidget(edit_btn)
        hl.addWidget(del_btn)
        return row

    # ── Row wiring ────────────────────────────────────────────────────────────

    #: The one :class:`_RowSelectFilter` this dialog installs on its rows,
    #: built on first use.  A class-level default rather than an ``__init__``
    #: assignment because the first ``_rebuild_shop_list()`` already runs
    #: while ``__init__`` is still building the dialog.
    _row_select_filter = None

    def _wire_row(self, row, kind: str, index: int):
        """Make ``row`` selectable without storing anything on it.

        The index goes on the row as a Qt property (C++ side, freed with
        the widget) and the behaviour comes from a single filter owned by
        the dialog — see :class:`_RowSelectFilter` for why not a closure.
        """
        row.setProperty("rowKind", kind)
        row.setProperty("rowIndex", index)
        if self._row_select_filter is None:
            self._row_select_filter = _RowSelectFilter(self)
        row.installEventFilter(self._row_select_filter)

    # ── Shopping actions ──────────────────────────────────────────────────────

    def _select_shop_row(self, index: int):
        self._selected_shop_index = None if self._selected_shop_index == index else index
        self._update_shop_add_btn()
        self._rebuild_shop_list()

    def _update_shop_add_btn(self):
        if self._shop_view_mode != "standards" and self._selected_shop_index is not None:
            self._shop_add_btn.setText(self._t("template_update_btn"))
        else:
            self._shop_add_btn.setText(self._t("template_add_btn"))

    def _handle_shop_add_btn(self):
        if self._shop_view_mode == "standards":
            self._add_standard_entry("shopping")
        elif self._selected_shop_index is not None:
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
        source = self._current_shop_list()
        if self._shop_sort_key == "name":
            source.sort(key=lambda t: t.get("title", "").lower(), reverse=reverse)
        elif self._shop_sort_key == "priority":
            _order = {"high": 0, "middle": 1, "low": 2}
            source.sort(key=lambda t: _order.get(t.get("priority", "middle"), 1), reverse=reverse)
        elif self._shop_sort_key == "schedule":
            _order = {"daily": 0, "weekly": 1, "season": 2}
            source.sort(key=lambda t: _order.get(t.get("schedule", "daily"), 3), reverse=reverse)
        elif self._shop_sort_key == "location":
            source.sort(key=lambda t: t.get("location", "").lower(), reverse=reverse)
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
                self._sync_standard_template("shopping", data)
                self._selected_shop_index = None
                self._update_shop_add_btn()
                self._rebuild_shop_list()

    def _delete_shop_template(self, index: int):
        if 0 <= index < len(self.templates):
            removed = self.templates.pop(index)
            self._remove_from_standard_templates("shopping", removed.get("id"))
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
        if self._task_view_mode != "standards" and self._selected_task_index is not None:
            self._task_add_btn.setText(self._t("template_update_btn"))
        else:
            self._task_add_btn.setText(self._t("task_add_btn"))

    def _handle_task_add_btn(self):
        if self._task_view_mode == "standards":
            self._add_standard_entry("tasks")
        elif self._selected_task_index is not None:
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
        source = self._current_task_list()
        if self._task_sort_key == "name":
            source.sort(key=lambda t: t.get("title", "").lower(), reverse=reverse)
        elif self._task_sort_key == "priority":
            _order = {"high": 0, "middle": 1, "low": 2}
            source.sort(key=lambda t: _order.get(t.get("priority", "middle"), 1), reverse=reverse)
        elif self._task_sort_key == "schedule":
            _order = {"daily": 0, "weekly": 1, "season": 2}
            source.sort(key=lambda t: _order.get(t.get("schedule", "daily"), 3), reverse=reverse)
        elif self._task_sort_key == "location":
            source.sort(key=lambda t: t.get("location", "").lower(), reverse=reverse)
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
                self._sync_standard_template("tasks", data)
                self._selected_task_index = None
                self._update_task_add_btn()
                self._rebuild_task_list()

    def _sync_standard_template(self, kind: str, updated: dict):
        """Keeps a Standard Template entry in sync when its SOURCE template
        gets edited (User-reported, 2026-09-09: "wenn in den Templates ein
        Eintrag geändert wird, ist dieser in den Standard Templates noch
        unverändert") -- Standard Templates are stored as independent
        snapshot copies (see __init__'s `[dict(t) for t in ...]`), so
        editing the real template never touched them on its own. Matched
        by "source_id" (NOT "id" -- a Standard Template entry always gets
        its OWN fresh id when added via the picker, see
        _add_standard_entry, so matching on "id" silently never fired for
        any real, picker-added entry) -- a no-op if this
        template was never added to Standard Templates in the first place.
        Keeps the Standard entry's own "id"/"source_id" intact across the
        overwrite so it stays findable next time.

        Named-Set aware: the match could be sitting in ANY of the kind's
        sets, not just the one currently shown, so this scans every set --
        an edited real template must stay in sync everywhere it was ever
        added, not just in the set the user happens to be looking at."""
        tid = updated.get("id")
        if not tid:
            return
        for std_list in self.standard_templates.get(kind, {}).values():
            for i, std in enumerate(std_list):
                if std.get("source_id") == tid:
                    data = dict(updated)
                    data["id"] = std.get("id", data.get("id"))
                    data["source_id"] = tid
                    std_list[i] = data
                    break

    def _remove_from_standard_templates(self, kind: str, tid: str):
        """Companion to _sync_standard_template above -- removes a Standard
        Template entry when its SOURCE template is deleted from the normal
        Shopping/Tasks list (User-reported, 2026-09-09: "Falls Templates aus
        der normalen Templates Liste entfernt werden, sollten diese auch aus
        den Standards entfernt werden"). Same "source_id" matching, scanned
        across every set of this kind (see _sync_standard_template) -- a
        no-op if this template was never added to any Standard Template Set."""
        if not tid:
            return
        for name, std_list in self.standard_templates.get(kind, {}).items():
            self.standard_templates[kind][name] = [
                std for std in std_list if std.get("source_id") != tid
            ]

    def _delete_task_template(self, index: int):
        if 0 <= index < len(self.task_templates):
            removed = self.task_templates.pop(index)
            self._remove_from_standard_templates("tasks", removed.get("id"))
            if self._selected_task_index == index:
                self._selected_task_index = None
                self._update_task_add_btn()
            elif self._selected_task_index is not None and self._selected_task_index > index:
                self._selected_task_index -= 1
            self._rebuild_task_list()

    # ── Standard Templates ───────────────────────────────────────────────────
    # A small, directly-editable starter pack ("Man soll 2-3 Standard
    # Templates definieren und anpassen können", 2026-09-05), applied once to
    # every brand-new character -- see MainWindow._apply_standard_templates.
    # Originally its own "Manage Standards" popup; now rendered INLINE in
    # this same Shopping/Tasks list via the "Templates / ★ Standard
    # Templates" toggle above (User-Wunsch, 2026-09-10: "kann man hier bei
    # Manage Standard Templates statt einem Popup ein Reiter draus machen?
    # ... ja" -- Option B, the same segmented-toggle pattern already used on
    # the Tasks/Shopping add-row toolbar). _make_shop_row/_make_task_row
    # route Edit/Delete here when their tab's view mode is "standards";
    # _handle_shop_add_btn/_handle_task_add_btn route "+Add" to
    # _add_standard_entry the same way. Reuses _TemplateEditDialog for the
    # edit form and _StandardTemplatePickerDialog for "+Add" (same picker
    # popup, unaffected by the "manage" dialog itself going away).
    #
    # Every method below acts on the CURRENTLY SELECTED named set for its
    # kind (see _current_set_name/_current_set_list/_ensure_set_for_add
    # above) -- Planner task "Mehrere benennbare/umbenennbare Standard-
    # Template-Sets".

    def get_standard_templates(self) -> dict:
        return self.standard_templates

    def _add_standard_entry(self, kind: str):
        is_shop = kind == "shopping"
        available = self.templates if is_shop else self.task_templates
        set_name = self._ensure_set_for_add(kind)
        target = self.standard_templates[kind][set_name]
        already = {t.get("title", "").strip().lower() for t in target if t.get("title")}
        pickable = [t for t in available if t.get("title", "").strip().lower() not in already]
        dlg = _StandardTemplatePickerDialog(pickable, parent=self, language=self._language, tr_func=self._tr)
        if not dlg.exec():
            return
        for tmpl in dlg.get_selected():
            # A COPY with its own new id, not a reference -- editing it
            # afterward via _edit_standard_entry must never touch the
            # source template in the main Shopping/Tasks list. source_id
            # keeps a separate link back to that source template's OWN id
            # (see _sync_standard_template/_remove_from_standard_templates
            # above, which match on it).
            item = dict(tmpl)
            item["source_id"] = tmpl.get("id", "")
            item["id"] = str(uuid4())
            item["is_general"] = False
            if is_shop:
                item.setdefault("amount", "1")
            target.append(item)
        self._refresh_set_row(kind)
        if is_shop:
            self._rebuild_shop_list()
        else:
            self._rebuild_task_list()

    def _edit_standard_entry(self, kind: str, index: int):
        is_shop = kind == "shopping"
        items = self._current_set_list(kind)
        if not (0 <= index < len(items)):
            return
        dlg = _TemplateEditDialog(
            items[index],
            known_locations=self._known_shop_locations() if is_shop else self._known_task_locations(),
            parent=self, task_mode=not is_shop, language=self._language, tr_func=self._tr,
            item_picker_callback=self._item_picker_callback if is_shop else None,
        )
        if dlg.exec():
            data = dlg.get_data()
            data["id"] = items[index].get("id", str(uuid4()))
            data["source_id"] = items[index].get("source_id", "")
            if is_shop:
                data["amount"] = items[index].get("amount", "1")
            items[index] = data
            if is_shop:
                self._rebuild_shop_list()
            else:
                self._rebuild_task_list()

    def _delete_standard_entry(self, kind: str, index: int):
        items = self._current_set_list(kind)
        if 0 <= index < len(items):
            items.pop(index)
            if kind == "shopping":
                self._rebuild_shop_list()
            else:
                self._rebuild_task_list()

    def _default_new_entries(self, kind: str) -> list[dict]:
        """Entries in the SAME-NAMED set of the language-matched Default
        profile's Standard Template Sets that THIS profile's currently
        selected set doesn't have yet, matched by title (case-insensitive)
        -- ids never match across different profiles (established this
        session), so title is the only reliable key.

        Named-Set aware (User-Wunsch, 2026-09-23: Sync needs to know which
        of the now-multiple sets it's comparing against) -- Sync compares
        the CURRENTLY SELECTED set here against the identically-named set
        over in the Default profile; if this profile has no set of that
        name selected yet (empty profile, first set), there's nothing to
        sync against and this returns empty rather than guessing a target."""
        set_name = self._current_set_name(kind)
        if set_name is None:
            return []
        existing = {t.get("title", "").strip().lower() for t in self._current_set_list(kind) if t.get("title")}
        default_set = self._default_standard_templates.get(kind, {}).get(set_name, [])
        return [
            t for t in default_set
            if t.get("title", "").strip().lower() not in existing
        ]

    def _update_shop_sync_btn(self):
        count = len(self._default_new_entries("shopping"))
        self._shop_sync_btn.setText(f'{self._t("standards_sync_btn")} ({count})')
        self._shop_sync_btn.setEnabled(count > 0)

    def _update_task_sync_btn(self):
        count = len(self._default_new_entries("tasks"))
        self._task_sync_btn.setText(f'{self._t("standards_sync_btn")} ({count})')
        self._task_sync_btn.setEnabled(count > 0)

    def _open_sync_dialog(self, kind: str):
        """"⟳ Sync" (User-Wunsch, 2026-09-10) -- merge-only: never touches or
        removes anything already in this profile's own Standard Templates,
        only ever adds picked entries. If the underlying template a picked
        entry is based on doesn't exist in THIS profile's own Shopping/Tasks
        catalog either (different profile, so ids never carried over), a
        copy of it is added there too, so the new Standard entry has a real
        source to link back to via source_id -- same as every other entry.
        Targets the CURRENTLY SELECTED named set (see _default_new_entries)."""
        new_entries = self._default_new_entries(kind)
        if not new_entries:
            return
        set_name = self._ensure_set_for_add(kind)
        dlg = _StandardSyncDialog(new_entries, parent=self, language=self._language, tr_func=self._tr)
        if not dlg.exec():
            return
        picked = dlg.get_selected()
        if not picked:
            return
        is_shop = kind == "shopping"
        catalog = self.templates if is_shop else self.task_templates
        catalog_by_key = {
            (t.get("title", "").strip().lower(), t.get("location", "").strip().lower()): t
            for t in catalog
        }
        target = self.standard_templates[kind][set_name]
        for entry in picked:
            key = (entry.get("title", "").strip().lower(), entry.get("location", "").strip().lower())
            match = catalog_by_key.get(key)
            if match is None:
                new_tmpl = {
                    "id": str(uuid4()),
                    "title": entry.get("title", ""),
                    "location": entry.get("location", ""),
                    "schedule": entry.get("schedule", "daily"),
                    "priority": entry.get("priority", "middle"),
                    "is_general": False,
                }
                if is_shop:
                    new_tmpl["price"] = entry.get("price", "0")
                    new_tmpl["currency"] = entry.get("currency", "kinah")
                catalog.append(new_tmpl)
                catalog_by_key[key] = new_tmpl
                match = new_tmpl
            std_item = dict(entry)
            std_item["id"] = str(uuid4())
            std_item["source_id"] = match.get("id", "")
            std_item["is_general"] = False
            target.append(std_item)
        self._refresh_set_row(kind)
        if is_shop:
            self._rebuild_shop_list()
            self._update_shop_sync_btn()
        else:
            self._rebuild_task_list()
            self._update_task_sync_btn()

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
                # _CheckRow, not QFrame: the whole row toggles its checkbox
                # from a class-level handler instead of a per-row closure
                # stored on the widget (review G/L4).
                row = _CheckRow()
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

                self._rows.append((row, sched, tmpl.get("location", "").strip()))
                list_layout.addWidget(row)
            list_layout.addStretch()

            scroll = QScrollArea()
            scroll.setWidget(list_container)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setObjectName("scrollArea")
            scroll.viewport().setObjectName("transparentViewport")
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


class _StandardSyncDialog(QDialog):
    """Checkbox picker for "⟳ Sync" (User-Wunsch, 2026-09-10: "Wie wärs,
    wenn wir eine Liste an den User weitergeben von den Einträgen, die
    nicht doppelt sind? mit einer Auswahl 'alles markieren' und
    checkboxen?") -- pulls in Standard Template entries the language-
    matched Default profile has that this profile doesn't yet. Merge-only:
    the caller (TemplateDialog._open_sync_dialog) already filters to
    non-duplicate entries, and accepting here never touches or removes
    anything already in the profile's own list. Same click-anywhere-on-row
    checkbox pattern as _StandardTemplatePickerDialog, and each row gets a
    "NEW" tag (User-Wunsch: "die neuen mit 'new' markieren")."""

    def __init__(self, new_entries: list[dict], parent=None, language: str = "en", tr_func=None):
        super().__init__(parent)
        self._entries = new_entries
        self._checks: list[QCheckBox] = []
        self._language = language
        self._tr = tr_func or (lambda _l, k, **kw: k)

        self.setWindowTitle(self._t("standards_sync_title"))
        self.setMinimumSize(400, 460)
        self.resize(440, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        desc = QLabel(self._t("standards_sync_desc"))
        desc.setObjectName("subtitle")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        top_row = QHBoxLayout()
        self._select_all_check = QCheckBox(self._t("standards_pick_select_all"))
        self._select_all_check.setCursor(Qt.PointingHandCursor)
        self._select_all_check.stateChanged.connect(self._on_select_all)
        self._count_label = QLabel()
        self._count_label.setObjectName("subtitle")
        top_row.addWidget(self._select_all_check)
        top_row.addStretch()
        top_row.addWidget(self._count_label)
        layout.addLayout(top_row)

        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(6)
        for entry in self._entries:
            # _CheckRow: see _StandardTemplatePickerDialog above (G/L4).
            row = _CheckRow()
            row.setObjectName("taskCard")
            row.setCursor(Qt.PointingHandCursor)
            hl = QHBoxLayout(row)
            hl.setContentsMargins(10, 8, 10, 8)
            hl.setSpacing(10)

            check = QCheckBox(entry.get("title", "—"))
            check.setCursor(Qt.PointingHandCursor)
            # Same fix as _StandardTemplatePickerDialog's own rows (User-
            # reported, 2026-09-05): WA_TransparentForMouseEvents makes the
            # checkbox/badges pass every click through to the row underneath,
            # so ONE handler reliably owns the whole row instead of a dead
            # zone silently eating clicks.
            check.setAttribute(Qt.WA_TransparentForMouseEvents)
            check.stateChanged.connect(self._update_count)
            self._checks.append(check)
            hl.addWidget(check, 1)

            sched = entry.get("schedule", "daily")
            sched_badge = QLabel(_SCHEDULE_TEXTS.get(sched, sched.upper()))
            sched_badge.setObjectName(_SCHEDULE_NAMES.get(sched, "scheduleDaily"))
            sched_badge.setAttribute(Qt.WA_TransparentForMouseEvents)
            hl.addWidget(sched_badge)

            new_badge = QLabel(self._t("standards_sync_new_tag"))
            new_badge.setObjectName("newBadge")
            new_badge.setAttribute(Qt.WA_TransparentForMouseEvents)
            hl.addWidget(new_badge)

            list_layout.addWidget(row)
        list_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(list_container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("scrollArea")
        scroll.viewport().setObjectName("transparentViewport")
        layout.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._t("cancel"))
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        self._apply_btn = QPushButton(self._t("standards_sync_apply_btn"))
        self._apply_btn.setObjectName("primaryButton")
        self._apply_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._apply_btn)
        layout.addLayout(btn_row)

        self._update_count()

    def _t(self, key: str, **kwargs) -> str:
        return self._tr(self._language, key, **kwargs)

    def _on_select_all(self, state):
        checked = bool(state)
        for c in self._checks:
            c.blockSignals(True)
            c.setChecked(checked)
            c.blockSignals(False)
        self._update_count()

    def _update_count(self):
        n = sum(1 for c in self._checks if c.isChecked())
        total = len(self._checks)
        self._count_label.setText(self._t("standards_sync_selected_count", n=n, total=total))
        self._apply_btn.setEnabled(n > 0)
        self._select_all_check.blockSignals(True)
        self._select_all_check.setChecked(n == total and total > 0)
        self._select_all_check.blockSignals(False)

    def get_selected(self) -> list[dict]:
        return [e for e, c in zip(self._entries, self._checks) if c.isChecked()]


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
            icons.set_icon(import_link, "database", 16, clear_text=False)
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

        # ── Description accordion, tasks only, collapsed by default ──────────
        # (User-Wunsch, 2026-09-09: "hier bitte noch ein accordion Button
        # einfügen, der ein Beschreibungsfeld zeigt, Standard ist dies aber
        # zugeklappt") -- ShoppingCard has no description concept to show it
        # in (unlike TaskCard's own desc_label), so this stays task-only
        # rather than adding write-only dead data to shop templates.
        self._description = None
        if task_mode:
            self._desc_toggle_btn = QPushButton(self._t("task_description_toggle"))
            self._desc_toggle_btn.setObjectName("linkButton")
            icons.set_icon(self._desc_toggle_btn, "chevron-right", 16,
                           "accent", clear_text=False)
            self._desc_toggle_btn.setFlat(True)
            self._desc_toggle_btn.setCursor(Qt.PointingHandCursor)
            self._desc_toggle_btn.setCheckable(True)
            self._desc_toggle_btn.clicked.connect(self._toggle_description)
            layout.addWidget(self._desc_toggle_btn, 0, Qt.AlignLeft)

            self._description = QLineEdit(data.get("description", ""))
            self._description.setPlaceholderText(self._t("placeholder_task_description"))
            self._description.setVisible(False)
            layout.addWidget(self._description)

            # Already has a description (editing an existing entry) -> start
            # expanded so it's not silently hidden from view.
            if data.get("description", "").strip():
                self._desc_toggle_btn.setChecked(True)
                self._toggle_description()

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

    def _toggle_description(self):
        expanded = self._desc_toggle_btn.isChecked()
        self._description.setVisible(expanded)
        icons.set_icon(self._desc_toggle_btn,
                       "chevron-down" if expanded else "chevron-right",
                       16, "accent", clear_text=False)
        self._desc_toggle_btn.setText(self._t("task_description_toggle"))

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
        if self._description is not None:
            d["description"] = self._description.text().strip()
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

        layout.addWidget(_h_separator())

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

        layout.addWidget(_h_separator())

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
