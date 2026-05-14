from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QFrame
)


class TaskSection(QFrame):

    def __init__(self, title):
        super().__init__()

        self.setObjectName("taskSection")

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ===== TITLE =====
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")

        layout.addWidget(title_label)

        # ===== HEADER =====
        header = QHBoxLayout()

        acc = QLabel("A")
        acc.setFixedWidth(40)

        char = QLabel("C")
        char.setFixedWidth(40)

        task = QLabel("Tasks")

        header.addWidget(acc)
        header.addWidget(char)
        header.addWidget(task)

        layout.addLayout(header)

        # ===== CONTENT =====
        self.content = QVBoxLayout()
        self.content.setSpacing(4)

        layout.addLayout(self.content)