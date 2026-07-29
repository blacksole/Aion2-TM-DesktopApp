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

        # ── Haupt-Timer Reihe (Daily, Weekly, Shugo, Riss) ───────────────
        main_row = QHBoxLayout()
        main_row.setSpacing(12)

        self.daily_reset_card = TimerInfoCard("Daily Reset", "--:--", "#22d3ee")
        self.weekly_reset_card = TimerInfoCard("Weekly Reset", "--:--", "#a855f7")
        self.shugo_timer_card = TimerInfoCard("Shugo", "--:--", "#f59e0b")
        self.riss_timer_card = TimerInfoCard("Riss", "--:--", "#f59e0b")

        self.shugo_timer_card.setVisible(False)
        self.riss_timer_card.setVisible(False)

        main_row.addWidget(self.daily_reset_card)
        main_row.addWidget(self.weekly_reset_card)
        main_row.addWidget(self.shugo_timer_card)
        main_row.addWidget(self.riss_timer_card)
        main_row.addStretch()
        layout.addLayout(main_row)

        # ── Custom Timer Abschnitt ────────────────────────────────────────
        self.custom_section_label = QLabel("Custom Timers")
        self.custom_section_label.setObjectName("subtitle")
        self.custom_section_label.setVisible(False)
        layout.addWidget(self.custom_section_label)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(12)

        self.custom_timer_cards = []
        for i in range(2):
            card = TimerInfoCard(f"Timer {i + 1}", "--:--", "#22d3ee")
            card.setVisible(False)
            self.custom_timer_cards.append(card)
            custom_row.addWidget(card)

        custom_row.addStretch()
        layout.addLayout(custom_row)

        layout.addStretch()

    # ── Setter Haupt-Timer ────────────────────────────────────────────────

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

    # ── Setter Custom Timer ───────────────────────────────────────────────

    def set_custom_timer_visible(self, idx: int, visible: bool):
        if 0 <= idx < len(self.custom_timer_cards):
            self.custom_timer_cards[idx].setVisible(visible)
            self._update_custom_section()

    def set_custom_timer_countdown(self, idx: int, text: str):
        if 0 <= idx < len(self.custom_timer_cards):
            self.custom_timer_cards[idx].value_label.setText(text)

    def set_custom_timer_style(self, idx: int, name: str, color: str,
                               display_format: str = "hh:mm:ss"):
        if 0 <= idx < len(self.custom_timer_cards):
            card = self.custom_timer_cards[idx]
            card.title_label.setText(name.upper())
            card.value_label.setStyleSheet(
                f"color: {color}; font-size: 30px; font-weight: bold;"
            )

    def _update_custom_section(self):
        any_visible = any(c.isVisible() for c in self.custom_timer_cards)
        self.custom_section_label.setVisible(any_visible)

    # ── Sprache ───────────────────────────────────────────────────────────

    def update_language(self, language: str, tr_func):
        self.title_label.setText(tr_func(language, "timers"))
        self.subtitle_label.setText(tr_func(language, "timers_subtitle"))
        self.daily_reset_card.title_label.setText(tr_func(language, "daily_reset").upper())
        self.weekly_reset_card.title_label.setText(tr_func(language, "weekly_reset").upper())
        self.shugo_timer_card.title_label.setText(tr_func(language, "shugo").upper())
        self.riss_timer_card.title_label.setText(tr_func(language, "riss").upper())
        _ct = {"de": "Custom Timer", "ru": "Custom Timer", "en": "Custom Timers"}
        self.custom_section_label.setText(_ct.get(language, "Custom Timers"))
