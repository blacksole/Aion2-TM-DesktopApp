from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class ShoppingCard(QFrame):
    def __init__(
        self,
        priority,
        amount,
        title,
        location,
        price
    ):
        super().__init__()

        self.priority = priority
        self.amount = amount
        self.title = title
        self.location = location
        self.price = price

        self.completed = False

        self.setObjectName("taskCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)

        # ===== LEFT =====

        left = QVBoxLayout()

        self.title_label = QLabel(
            f"{amount}x • {title}"
        )
        self.title_label.setObjectName("taskTitle")

        self.info_label = QLabel(
            f"{priority.upper()} • {location} • {price}"
        )
        self.info_label.setObjectName("taskDescription")

        left.addWidget(self.title_label)
        left.addWidget(self.info_label)

        # ===== RIGHT =====

        self.check_button = QPushButton("✓")
        self.check_button.setCheckable(True)
        self.check_button.setFixedSize(34, 34)
        self.check_button.clicked.connect(self.toggle)

        layout.addLayout(left)
        layout.addStretch()
        layout.addWidget(
            self.check_button,
            alignment=Qt.AlignCenter
        )

    def toggle(self):
        self.completed = not self.completed

        self.setProperty(
            "completed",
            self.completed
        )

        self.style().unpolish(self)
        self.style().polish(self)

        self.update()