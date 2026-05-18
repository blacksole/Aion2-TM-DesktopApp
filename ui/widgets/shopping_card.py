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
        price,
        is_event=False
    ):
        super().__init__()

        self.priority = priority
        self.amount = amount
        self.title = title
        self.location = location
        self.price = price
        self.is_event = is_event
        self.completed = False

        self.price_display = self.format_kinah_price(price)

        self.setObjectName("taskCard")
        self.setProperty("event", self.is_event)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        self.check_btn = QPushButton("○")
        self.check_btn.setObjectName("checkButton")
        self.check_btn.setFixedWidth(32)
        self.check_btn.clicked.connect(self.toggle)

        text_box = QVBoxLayout()

        content_row = QHBoxLayout()
        content_row.setSpacing(12)

        self.amount_label = QLabel(f"{amount}x")
        self.amount_label.setObjectName("shoppingAmount")

        content_box = QVBoxLayout()
        content_box.setSpacing(4)

        title_row = QHBoxLayout()

        if self.is_event:
            self.event_badge = QLabel("EVENT")
            self.event_badge.setObjectName("eventBadge")
            title_row.addWidget(self.event_badge)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("taskTitle")

        title_row.addWidget(self.title_label)
        title_row.addStretch()

        self.info_label = QLabel(
            f"{location} • {self.price_display}"
        )
        self.info_label.setObjectName("taskDescription")

        content_box.addLayout(title_row)
        content_box.addWidget(self.info_label)

        content_row.addWidget(self.amount_label)
        content_row.addLayout(content_box, 1)

        text_box.addLayout(content_row)

        self.priority_label = QLabel(priority.upper())
        self.priority_label.setObjectName("priorityMedium")

        self.delete_btn = QPushButton("🗑")
        self.delete_btn.setObjectName("deleteButton")
        self.delete_btn.setFixedWidth(36)
        self.delete_btn.clicked.connect(self.deleteLater)

        layout.addWidget(self.check_btn)
        layout.addLayout(text_box, 1)
        layout.addWidget(self.priority_label)
        layout.addWidget(self.delete_btn)

    def toggle(self):
        self.completed = not self.completed

        if self.completed:
            self.check_btn.setText("●")
            self.setProperty("completed", True)

            self.title_label.setStyleSheet(
                "color: #64748b; text-decoration: line-through;"
            )
        else:
            self.check_btn.setText("○")
            self.setProperty("completed", False)
            self.title_label.setStyleSheet("")

        self.style().unpolish(self)
        self.style().polish(self)

    def set_completed(self, value):
        self.completed = value

        if self.completed:
            self.check_btn.setText("●")
            self.setProperty("completed", True)

            self.title_label.setStyleSheet(
                "color: #64748b; text-decoration: line-through;"
            )
        else:
            self.check_btn.setText("○")
            self.setProperty("completed", False)
            self.title_label.setStyleSheet("")

        self.style().unpolish(self)
        self.style().polish(self)

    def format_kinah_price(self, value):
        try:
            k_value = float(str(value).replace(",", ".").strip())
        except ValueError:
            k_value = 0

        kinah = k_value * 1000

        if kinah >= 1_000_000:
            millions = kinah / 1_000_000

            if millions.is_integer():
                return f"{int(millions)}m Kinah"

            return f"{millions:.1f}m Kinah"

        if kinah >= 1_000:
            thousands = kinah / 1_000

            if thousands.is_integer():
                return f"{int(thousands)}k Kinah"

            return f"{thousands:.1f}k Kinah"

        return f"{int(kinah)} Kinah"