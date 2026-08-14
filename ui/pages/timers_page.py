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
        self.season_timer_card = TimerInfoCard("Season", "--:--", "#10b981")
        self.shugo_timer_card = TimerInfoCard("Shugo", "--:--", "#f59e0b")
        self.riss_timer_card = TimerInfoCard("Riss", "--:--", "#f59e0b")

        self.season_timer_card.setVisible(False)
        self.shugo_timer_card.setVisible(False)
        self.riss_timer_card.setVisible(False)

        main_row.addWidget(self.daily_reset_card)
        main_row.addWidget(self.weekly_reset_card)
        main_row.addWidget(self.season_timer_card)
        main_row.addWidget(self.shugo_timer_card)
        main_row.addWidget(self.riss_timer_card)
        main_row.addStretch()
        layout.addLayout(main_row)

        # ── Custom Timer Abschnitt (dynamisch nach Kategorie) ─────────────
        self._custom_area = QWidget()
        self._custom_area_layout = QVBoxLayout(self._custom_area)
        self._custom_area_layout.setContentsMargins(0, 0, 0, 0)
        self._custom_area_layout.setSpacing(12)
        self._custom_area.setVisible(False)
        layout.addWidget(self._custom_area)

        self._custom_timer_cards: dict[int, TimerInfoCard] = {}

        layout.addStretch()

    # ── Setter Haupt-Timer ────────────────────────────────────────────────

    def set_daily_countdown(self, text: str):
        self.daily_reset_card.value_label.setText(text)

    def set_weekly_countdown(self, text: str):
        self.weekly_reset_card.value_label.setText(text)

    def set_season_countdown(self, text: str):
        self.season_timer_card.value_label.setText(text if text else "--:--")

    def set_season_visible(self, visible: bool):
        self.season_timer_card.setVisible(visible)

    def set_shugo_countdown(self, text: str):
        self.shugo_timer_card.value_label.setText(text)

    def set_riss_countdown(self, text: str):
        self.riss_timer_card.value_label.setText(text)

    def set_shugo_visible(self, visible: bool):
        self.shugo_timer_card.setVisible(visible)

    def set_riss_visible(self, visible: bool):
        self.riss_timer_card.setVisible(visible)

    # ── Custom Timer Abschnitte (dynamisch) ───────────────────────────────

    def rebuild_custom_sections(self, categories: list, timers: list):
        """Rebuild dynamic custom timer sections grouped by category."""
        while self._custom_area_layout.count():
            item = self._custom_area_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._custom_timer_cards.clear()

        default_cat = categories[0] if categories else "Custom Timer"
        any_visible = False

        for cat_name in categories:
            cat_timers = [
                (i, t) for i, t in enumerate(timers)
                if t.get("category", default_cat) == cat_name
                and t.get("enabled") and t.get("name")
            ]
            if not cat_timers:
                continue

            any_visible = True

            header = QLabel(cat_name)
            header.setObjectName("subtitle")
            self._custom_area_layout.addWidget(header)

            cards_widget = QWidget()
            cards_row = QHBoxLayout(cards_widget)
            cards_row.setContentsMargins(0, 0, 0, 0)
            cards_row.setSpacing(12)

            for idx, timer_cfg in cat_timers:
                card = TimerInfoCard(
                    timer_cfg.get("name", f"Timer {idx + 1}"),
                    "--:--",
                    timer_cfg.get("color", "#22d3ee"),
                )
                cards_row.addWidget(card)
                self._custom_timer_cards[idx] = card

            cards_row.addStretch()
            self._custom_area_layout.addWidget(cards_widget)

        self._custom_area.setVisible(any_visible)

    def set_custom_timer_countdown(self, idx: int, text: str):
        if idx in self._custom_timer_cards:
            self._custom_timer_cards[idx].value_label.setText(text)

    # ── Sprache ───────────────────────────────────────────────────────────

    def update_language(self, language: str, tr_func):
        self.title_label.setText(tr_func(language, "timers"))
        self.subtitle_label.setText(tr_func(language, "timers_subtitle"))
        self.daily_reset_card.title_label.setText(tr_func(language, "daily_reset").upper())
        self.weekly_reset_card.title_label.setText(tr_func(language, "weekly_reset").upper())
        self.season_timer_card.title_label.setText("SEASON")
        self.shugo_timer_card.title_label.setText(tr_func(language, "shugo").upper())
        self.riss_timer_card.title_label.setText(tr_func(language, "riss").upper())
