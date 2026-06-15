from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Qt


class UnsavedChangesDialog(QDialog):
    SAVE = "save"
    DISCARD = "discard"
    CANCEL = "cancel"

    def __init__(self, node_title: str, parent=None):
        super().__init__(parent)

        self._action = self.CANCEL

        self.setWindowTitle("Ungespeicherte Änderungen")
        self.setObjectName("DeleteConfirmDialog")
        self.setModal(True)
        self.setMinimumWidth(360)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 22)
        layout.setSpacing(14)

        title_label = QLabel(f'„{node_title}" hat ungespeicherte Änderungen.')
        title_label.setObjectName("DeleteDialogTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        desc_label = QLabel("Was soll mit den Änderungen passieren?")
        desc_label.setObjectName("DeleteDialogDesc")
        layout.addWidget(desc_label)

        layout.addSpacing(6)

        save_btn = QPushButton("Speichern")
        save_btn.setObjectName("DeleteDialogOptionBtn")
        save_btn.clicked.connect(self._choose_save)
        layout.addWidget(save_btn)

        discard_btn = QPushButton("Verwerfen")
        discard_btn.setObjectName("DeleteDialogDangerBtn")
        discard_btn.clicked.connect(self._choose_discard)
        layout.addWidget(discard_btn)

        cancel_btn = QPushButton("Abbrechen")
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

    def __init__(self, node_title: str, has_children: bool, parent=None):
        super().__init__(parent)

        self._action = self.CANCEL

        self.setWindowTitle("Node löschen")
        self.setObjectName("DeleteConfirmDialog")
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 22)
        layout.setSpacing(14)

        title_label = QLabel(f'„{node_title}" löschen?')
        title_label.setObjectName("DeleteDialogTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        if has_children:
            desc_label = QLabel(
                "Dieser Node hat Children.\nWas soll mit ihnen passieren?"
            )
            desc_label.setObjectName("DeleteDialogDesc")
            layout.addWidget(desc_label)

            layout.addSpacing(6)

            intermediate_btn = QPushButton("Zwischenknoten löschen  —  Children an Parent hängen")
            intermediate_btn.setObjectName("DeleteDialogOptionBtn")
            intermediate_btn.clicked.connect(self._choose_intermediate)
            layout.addWidget(intermediate_btn)

            recursive_btn = QPushButton("Node + alle Children löschen")
            recursive_btn.setObjectName("DeleteDialogDangerBtn")
            recursive_btn.clicked.connect(self._choose_recursive)
            layout.addWidget(recursive_btn)

        else:
            layout.addSpacing(4)

            delete_btn = QPushButton("Löschen")
            delete_btn.setObjectName("DeleteDialogDangerBtn")
            delete_btn.clicked.connect(self._choose_recursive)
            layout.addWidget(delete_btn)

        cancel_btn = QPushButton("Abbrechen")
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
