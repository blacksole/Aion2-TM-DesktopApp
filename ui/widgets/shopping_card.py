from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

_SCHEDULE_OBJECT_NAMES = {
    "daily":   "scheduleDaily",
    "weekly":  "scheduleWeekly",
    "season":  "scheduleSeason",
}


class ShoppingCard(QFrame):
    def __init__(
        self,
        priority,
        amount,
        title,
        location,
        price,
        schedule="daily",
        is_event=False,   # legacy — mapped to "season" on load
        currency="kinah",
        character="",
    ):
        super().__init__()

        # legacy migration: is_event=True → schedule="season"
        if is_event and schedule == "daily":
            schedule = "season"

        self.priority = priority
        self.amount = amount
        self.title = title
        self.location = location
        self.price = price
        self.schedule = schedule
        self.currency = currency
        self.character = character
        self.completed = False

        self.price_display = self.format_price(price, currency)

        self.setObjectName("taskCard")

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
        self.title_label = QLabel(title)
        self.title_label.setObjectName("taskTitle")
        title_row.addWidget(self.title_label)
        title_row.addStretch()

        self.info_label = QLabel(f"{location} • {self.price_display}")
        self.info_label.setObjectName("taskDescription")

        content_box.addLayout(title_row)
        content_box.addWidget(self.info_label)

        content_row.addWidget(self.amount_label)
        content_row.addLayout(content_box, 1)

        text_box.addLayout(content_row)

        self.priority_label = QLabel(priority.upper())
        self.priority_label.setObjectName("priorityMedium")

        # Schedule badge — styled like priority
        schedule_text = {"daily": "DAILY", "weekly": "WEEKLY", "season": "SEASON"}.get(schedule, schedule.upper())
        self.schedule_label = QLabel(schedule_text)
        self.schedule_label.setObjectName(_SCHEDULE_OBJECT_NAMES.get(schedule, "scheduleDaily"))

        self.delete_btn = QPushButton("×")
        self.delete_btn.setObjectName("deleteButton")
        self.delete_btn.setFixedWidth(28)
        self.delete_btn.clicked.connect(self.deleteLater)

        self.char_label = QLabel(character) if character else None
        if self.char_label:
            self.char_label.setObjectName("scheduleWeekly")

        layout.addWidget(self.check_btn)
        layout.addLayout(text_box, 1)
        if self.char_label:
            layout.addWidget(self.char_label)
        layout.addWidget(self.schedule_label)
        layout.addWidget(self.priority_label)
        layout.addWidget(self.delete_btn)

    def toggle(self):
        self.completed = not self.completed
        self._apply_completed_style()

    def set_completed(self, value):
        self.completed = value
        self._apply_completed_style()

    def _apply_completed_style(self):
        if self.completed:
            self.check_btn.setText("●")
            self.setProperty("completed", True)
            self.title_label.setStyleSheet("color: #64748b; text-decoration: line-through;")
        else:
            self.check_btn.setText("○")
            self.setProperty("completed", False)
            self.title_label.setStyleSheet("")
        self.style().unpolish(self)
        self.style().polish(self)

    def format_price(self, value, currency: str = "kinah") -> str:
        try:
            raw = float(str(value).replace(",", ".").strip())
        except ValueError:
            raw = 0

        if currency == "abyss":
            return f"{int(raw) if raw == int(raw) else raw} AP"

        kinah = raw * 1000
        if kinah >= 1_000_000:
            m = kinah / 1_000_000
            return f"{int(m)}m Kinah" if m == int(m) else f"{m:.1f}m Kinah"
        if kinah >= 1_000:
            k = kinah / 1_000
            return f"{int(k)}k Kinah" if k == int(k) else f"{k:.1f}k Kinah"
        return f"{int(kinah)} Kinah"

    def format_kinah_price(self, value):
        return self.format_price(value, "kinah")
