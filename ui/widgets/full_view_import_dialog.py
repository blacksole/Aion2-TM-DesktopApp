from pathlib import Path

from core import theme
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui.full_view_import import ParsedImport, parse_full_view_csv, parse_full_view_xlsx

_TYPE_LABEL = {"daily": "Daily", "weekly": "Weekly", "season": "Season"}
_ACTION_ORDER = {"new": 0, "done": 1, "open": 2, "unchanged": 3}
#: Import-plan action -> semantic token (MASTER §2).  Was four QColor hex
#: literals; "new" was a sky blue that matched no token at all.
_ACTION_TOKENS = {
    "new": "accent",
    "done": "ok",
    "open": "danger",
    "unchanged": "fg.muted",
}


class FullViewImportDialog(QDialog):
    """Native counterpart to Full View's CSV/Excel export (User-Wunsch,
    2026-09-05: "Kann man hier auch ein Import Button einfügen mit
    Vorschau?"). The exported browser page itself can't write back into
    this running app (a static file:// page has no channel into a
    separate process, see full_view_export.py's own module docstring) --
    this dialog is the real thing instead: pick the file, review a
    preview of exactly what will change, then Sync commits it via the two
    callbacks passed in.

    plan_callback(entries: list[ImportEntry]) -> list[dict]: classifies
    each entry against the CURRENT profile (new/done/open/unchanged)
    WITHOUT mutating anything -- MainWindow._plan_full_view_import.
    apply_callback(plan: list[dict]) -> dict: actually applies that exact
    plan and returns {"new":, "done":, "open":, "unchanged":} counts --
    MainWindow.apply_full_view_import_plan. Same callback-passed-in
    pattern as CharacterManagerDialog, so this dialog has zero direct
    knowledge of task_lists/TaskCard/profile saving."""

    def __init__(self, characters: list, plan_callback, apply_callback,
                 language: str = "en", tr_func=None, parent=None,
                 create_character_callback=None):
        super().__init__(parent)
        self._characters = list(characters or [])
        self._plan_callback = plan_callback
        self._apply_callback = apply_callback
        # User-Wunsch, 2026-09-08: "bei jedem Charakter, der nicht
        # existiert, den Benutzer fragen, ob dieser Charakter erstellt
        # werden soll" -- optional so this dialog still works (just
        # without the offer) if a caller doesn't pass one.
        self._create_character_callback = create_character_callback
        self._language = language
        self._tr = tr_func or (lambda _l, k, **kw: k)
        self._parsed: ParsedImport | None = None
        self._plan: list[dict] = []
        self._last_path: str | None = None

        self.setWindowTitle(self._t("full_view_import_title"))
        self.setMinimumSize(640, 520)
        self.resize(720, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        desc = QLabel(self._t("full_view_import_desc"))
        desc.setObjectName("subtitle")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        file_row = QHBoxLayout()
        choose_btn = QPushButton(self._t("full_view_import_choose_file_btn"))
        choose_btn.setObjectName("primaryButton")
        choose_btn.clicked.connect(self._on_choose_file)
        file_row.addWidget(choose_btn)
        self._file_label = QLabel(self._t("full_view_import_no_file_hint"))
        self._file_label.setObjectName("subtitle")
        file_row.addWidget(self._file_label, 1)
        layout.addLayout(file_row)

        self._warning_label = QLabel("")
        self._warning_label.setObjectName("DetailDisclaimer")
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        layout.addWidget(self._warning_label)

        self._summary_label = QLabel("")
        self._summary_label.setObjectName("subtitle")
        layout.addWidget(self._summary_label)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels([
            self._t("full_view_import_col_character"),
            self._t("full_view_import_col_type"),
            self._t("full_view_import_col_activity"),
            self._t("full_view_import_col_action"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self._table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._t("cancel"))
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self._sync_btn = QPushButton(self._t("full_view_import_sync_btn"))
        self._sync_btn.setObjectName("primaryButton")
        self._sync_btn.setEnabled(False)
        self._sync_btn.clicked.connect(self._on_sync_clicked)
        btn_row.addWidget(self._sync_btn)
        layout.addLayout(btn_row)

    def _t(self, key: str, **kwargs) -> str:
        return self._tr(self._language, key, **kwargs)

    def _on_choose_file(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, self._t("full_view_import_choose_file_btn"), "",
            "CSV / Excel (*.csv *.xlsx)",
        )
        if not path:
            return
        self._last_path = path
        parsed = self._parse_file(path)
        if parsed is None:
            return

        self._parsed = parsed
        self._file_label.setText(Path(path).name)
        self._offer_create_missing_characters()
        self._rebuild_preview()

    def _parse_file(self, path: str) -> ParsedImport | None:
        try:
            if path.lower().endswith(".xlsx"):
                return parse_full_view_xlsx(path, self._characters)
            text = Path(path).read_text(encoding="utf-8-sig")
            return parse_full_view_csv(text, self._characters)
        except Exception as exc:  # noqa: BLE001 -- surfaced to the user, not swallowed
            QMessageBox.warning(self, self._t("full_view_import_title"),
                                 self._t("full_view_import_parse_error", error=str(exc)))
            return None

    def _offer_create_missing_characters(self):
        """Asks, per unmatched character name, whether to create it (User-
        Wunsch, 2026-09-08) -- previously such rows were just silently
        skipped and reported in the passive warning label below. Any name
        the user confirms gets created via the same callback
        CharacterManagerDialog uses (MainWindow._add_character), then the
        file is RE-PARSED (self._characters now includes it) so those
        rows go from skipped to matched instead of staying dropped for
        the rest of this dialog's lifetime."""
        if not self._create_character_callback or self._parsed is None:
            return
        if not self._parsed.unmatched_characters:
            return

        any_created = False
        for name in list(self._parsed.unmatched_characters):
            answer = QMessageBox.question(
                self, self._t("char_add_new_title"),
                self._t("full_view_import_create_character_text", name=name),
            )
            if answer != QMessageBox.Yes:
                continue
            ok, error_key = self._create_character_callback(name)
            if ok:
                self._characters.append(name)
                any_created = True
            elif error_key:
                QMessageBox.warning(self, self._t("char_add_new_title"), self._t(error_key))

        if any_created and self._last_path:
            reparsed = self._parse_file(self._last_path)
            if reparsed is not None:
                self._parsed = reparsed

    def _rebuild_preview(self):
        if self._parsed is None:
            return
        if self._parsed.unmatched_characters:
            names = ", ".join(self._parsed.unmatched_characters)
            self._warning_label.setText(
                self._t("full_view_import_unmatched_warning", n=len(self._parsed.unmatched_characters), names=names)
            )
            self._warning_label.setVisible(True)
        else:
            self._warning_label.setVisible(False)

        self._plan = self._plan_callback(self._parsed.entries)
        self._plan.sort(key=lambda r: (_ACTION_ORDER.get(r["action"], 9), r["character"] or "", r["title"]))

        counts = {"new": 0, "done": 0, "open": 0, "unchanged": 0}
        for row in self._plan:
            counts[row["action"]] = counts.get(row["action"], 0) + 1
        self._summary_label.setText(self._t("full_view_import_summary", **counts))

        self._table.setRowCount(len(self._plan))
        for r, row in enumerate(self._plan):
            char_display = row["character"] or self._t("char_unassigned")
            action_key = f"full_view_import_action_{row['action']}"
            values = [char_display, _TYPE_LABEL.get(row["schedule"], row["schedule"]), row["title"], self._t(action_key)]
            token = _ACTION_TOKENS.get(row["action"])
            color = theme.qcolor(theme.current_tokens(), token) if token else None
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                if c == 3 and color is not None:
                    item.setForeground(color)
                self._table.setItem(r, c, item)

        self._sync_btn.setEnabled(bool(self._plan))

    def _on_sync_clicked(self):
        result = self._apply_callback(self._plan)
        QMessageBox.information(
            self, self._t("full_view_import_result_title"),
            self._t("full_view_import_result_text", new=result.get("new", 0), done=result.get("done", 0), open=result.get("open", 0)),
        )
        self.accept()
