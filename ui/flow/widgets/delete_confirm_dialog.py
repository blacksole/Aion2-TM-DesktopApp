from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Qt

_T = {
    "unsaved_title":     {"de": "Ungespeicherte Änderungen", "ru": "Несохранённые изменения",  "en": "Unsaved Changes"},
    "unsaved_body":      {"de": '„{t}" hat ungespeicherte Änderungen.',      "ru": '«{t}» содержит несохранённые изменения.',    "en": '"{t}" has unsaved changes.'},
    "unsaved_question":  {"de": "Was soll mit den Änderungen passieren?",     "ru": "Что сделать с изменениями?",                 "en": "What should happen to the changes?"},
    "save":              {"de": "Speichern",   "ru": "Сохранить",  "en": "Save"},
    "discard":           {"de": "Verwerfen",   "ru": "Отменить",   "en": "Discard"},
    "cancel":            {"de": "Abbrechen",   "ru": "Отмена",     "en": "Cancel"},
    "delete_title":      {"de": "Node löschen",                               "ru": "Удалить узел",                               "en": "Delete Node"},
    "delete_body":       {"de": '„{t}" löschen?',                             "ru": 'Удалить «{t}»?',                             "en": 'Delete "{t}"?'},
    "children_question": {"de": "Dieser Node hat Children.\nWas soll mit ihnen passieren?", "ru": "У этого узла есть дочерние узлы.\nЧто с ними сделать?", "en": "This node has children.\nWhat should happen to them?"},
    "intermediate":      {"de": "Zwischenknoten löschen  —  Children an Parent hängen",     "ru": "Удалить промежуточный — перенести дочерние к родителю",  "en": "Delete intermediate  —  attach children to parent"},
    "recursive":         {"de": "Node + alle Children löschen",               "ru": "Удалить узел + все дочерние",                "en": "Delete node + all children"},
    "delete":            {"de": "Löschen",     "ru": "Удалить",    "en": "Delete"},
}

def _t(key, lang, **kwargs):
    text = _T[key].get(lang, _T[key]["en"])
    return text.format(**kwargs) if kwargs else text


class UnsavedChangesDialog(QDialog):
    SAVE = "save"
    DISCARD = "discard"
    CANCEL = "cancel"

    def __init__(self, node_title: str, language: str = "en", tr_func=None, parent=None):
        super().__init__(parent)

        self._action = self.CANCEL
        lang = language

        self.setWindowTitle(_t("unsaved_title", lang))
        self.setObjectName("DeleteConfirmDialog")
        self.setModal(True)
        self.setMinimumWidth(360)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 22)
        layout.setSpacing(14)

        title_label = QLabel(_t("unsaved_body", lang, t=node_title))
        title_label.setObjectName("DeleteDialogTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        desc_label = QLabel(_t("unsaved_question", lang))
        desc_label.setObjectName("DeleteDialogDesc")
        layout.addWidget(desc_label)

        layout.addSpacing(6)

        save_btn = QPushButton(_t("save", lang))
        save_btn.setObjectName("DeleteDialogOptionBtn")
        save_btn.clicked.connect(self._choose_save)
        layout.addWidget(save_btn)

        discard_btn = QPushButton(_t("discard", lang))
        discard_btn.setObjectName("DeleteDialogDangerBtn")
        discard_btn.clicked.connect(self._choose_discard)
        layout.addWidget(discard_btn)

        cancel_btn = QPushButton(_t("cancel", lang))
        cancel_btn.setObjectName("DeleteDialogCancelBtn")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def _choose_save(self):
        self._action = self.SAVE
        self.accept()

    def _choose_discard(self):
        self._action = self.DISCARD
        self.accept()

    def get_action(self) -> str:
        return self._action


class DeleteConfirmDialog(QDialog):
    RECURSIVE = "recursive"
    INTERMEDIATE = "intermediate"
    CANCEL = "cancel"

    def __init__(self, node_title: str, has_children: bool, language: str = "en", tr_func=None, parent=None):
        super().__init__(parent)

        self._action = self.CANCEL
        lang = language

        self.setWindowTitle(_t("delete_title", lang))
        self.setObjectName("DeleteConfirmDialog")
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 22)
        layout.setSpacing(14)

        title_label = QLabel(_t("delete_body", lang, t=node_title))
        title_label.setObjectName("DeleteDialogTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        if has_children:
            desc_label = QLabel(_t("children_question", lang))
            desc_label.setObjectName("DeleteDialogDesc")
            layout.addWidget(desc_label)

            layout.addSpacing(6)

            intermediate_btn = QPushButton(_t("intermediate", lang))
            intermediate_btn.setObjectName("DeleteDialogOptionBtn")
            intermediate_btn.clicked.connect(self._choose_intermediate)
            layout.addWidget(intermediate_btn)

            recursive_btn = QPushButton(_t("recursive", lang))
            recursive_btn.setObjectName("DeleteDialogDangerBtn")
            recursive_btn.clicked.connect(self._choose_recursive)
            layout.addWidget(recursive_btn)

        else:
            layout.addSpacing(4)

            delete_btn = QPushButton(_t("delete", lang))
            delete_btn.setObjectName("DeleteDialogDangerBtn")
            delete_btn.clicked.connect(self._choose_recursive)
            layout.addWidget(delete_btn)

        cancel_btn = QPushButton(_t("cancel", lang))
        cancel_btn.setObjectName("DeleteDialogCancelBtn")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def _choose_intermediate(self):
        self._action = self.INTERMEDIATE
        self.accept()

    def _choose_recursive(self):
        self._action = self.RECURSIVE
        self.accept()

    def get_action(self) -> str:
        return self._action
