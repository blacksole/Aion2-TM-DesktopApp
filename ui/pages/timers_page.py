from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame


class TimerInfoCard(QFrame):
    def __init__(self, title: str, value: str = "--:--", color: str = "#22d3ee"):
        super().__init__()

        self.setObjectName("timerCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("statTitle")

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 30px; font-weight: bold;"
        )

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)


class TimersPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.title_label = QLabel("Timer")
        self.title_label.setObjectName("mainTitle")

        self.subtitle_label = QLabel("Reset Timer und Advanced Timer")
        self.subtitle_label.setObjectName("subtitle")

        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)

        timer_row = QHBoxLayout()
        timer_row.setSpacing(12)

        self.daily_reset_card = TimerInfoCard("Daily Reset", "--:--", "#22d3ee")
        self.weekly_reset_card = TimerInfoCard("Weekly Reset", "--:--", "#a855f7")
        self.shugo_timer_card = TimerInfoCard("Shugo", "--:--", "#f59e0b")
        self.riss_timer_card = TimerInfoCard("Riss", "--:--", "#f59e0b")

        self.shugo_timer_card.setVisible(False)
        self.riss_timer_card.setVisible(False)

        timer_row.addWidget(self.daily_reset_card)
        timer_row.addWidget(self.weekly_reset_card)
        timer_row.addWidget(self.shugo_timer_card)
        timer_row.addWidget(self.riss_timer_card)
        timer_row.addStretch()
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addLayout(timer_row)
        layout.addStretch()

    def set_daily_countdown(self, text: str):
        self.daily_reset_card.value_label.setText(text)

    def set_weekly_countdown(self, text: str):
        self.weekly_reset_card.value_label.setText(text)

    def set_shugo_countdown(self, text: str):
        self.shugo_timer_card.value_label.setText(text)

    def set_riss_countdown(self, text: str):
        self.riss_timer_card.value_label.setText(text)

    def set_shugo_visible(self, visible: bool):
        self.shugo_timer_card.setVisible(visible)

    def set_riss_visible(self, visible: bool):
        self.riss_timer_card.setVisible(visible)

    def update_language(self, language: str, tr_func):
        self.daily_reset_card.title_label.setText(
            tr_func(language, "daily_reset").upper()
        )

        self.weekly_reset_card.title_label.setText(
            tr_func(language, "weekly_reset").upper()
        )

        self.shugo_timer_card.title_label.setText(
            tr_func(language, "shugo").upper()
        )
        self.riss_timer_card.title_label.setText(
            tr_func(language, "riss").upper()
        )

        self.title_label.setText(
            tr_func(language, "timers")
        )

        self.subtitle_label.setText(
            tr_func(language, "timers_subtitle")
        )