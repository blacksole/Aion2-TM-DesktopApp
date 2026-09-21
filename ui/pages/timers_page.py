from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
from PySide6.QtCore import Signal

from core import theme
from ui.widgets import icons

#: The built-in timers' identity colours (MASTER §4-4 data colours, owned by
#: core/theme.py).  These used to be five hex literals passed in at the call
#: site; Season had no entry in the shared table at all and carried its own
#: #10b981, so it and the overlay's Season badge disagreed.
_DAILY = theme.data_color("timer", "daily")
_WEEKLY = theme.data_color("timer", "weekly")
_SHUGO = theme.data_color("timer", "shugo")
_RIFT = theme.data_color("timer", "rift")
_CUSTOM = theme.data_color("timer", "custom")


class TimerInfoCard(QFrame):
    def __init__(self, title: str, value: str = "--:--", color: str = ""):
        super().__init__()

        self.setObjectName("timerCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("statTitle")

        self.value_label = QLabel(value)
        # #bigValue owns the type (font.mono, text.display, bold -- MASTER
        # §3 "gros chiffres"); the colour is this timer's own data colour,
        # the one exception MASTER §4-4 allows to stay in code.
        self.value_label.setObjectName("bigValue")
        self.value_label.setStyleSheet(f"color: {color or _DAILY};")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)


class TimersPage(QWidget):
    manage_timers_requested = Signal()
    timer_settings_requested = Signal()

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        self.title_label = QLabel("Timer")
        self.title_label.setObjectName("mainTitle")

        self.subtitle_label = QLabel("Reset Timer und Advanced Timer")
        self.subtitle_label.setObjectName("subtitle")

        title_col.addWidget(self.title_label)
        title_col.addWidget(self.subtitle_label)
        header_row.addLayout(title_col, 1)

        # User-reported, 2026-09-07: the plain "+" icon read as "add a
        # timer" when it actually opens the whole Custom Timer manager
        # (add/edit/remove/categories) -- a labeled button says what it
        # does instead of implying just one of its several actions.
        self.manage_timers_btn = QPushButton("Verwalten")
        self.manage_timers_btn.setObjectName("secondaryButton")
        self.manage_timers_btn.setFixedHeight(40)
        self.manage_timers_btn.setToolTip("Custom Timer verwalten")
        self.manage_timers_btn.clicked.connect(self.manage_timers_requested.emit)

        self.timer_settings_btn = QPushButton()
        self.timer_settings_btn.setObjectName("pageIconButton")
        self.timer_settings_btn.setToolTip("")
        icons.set_icon(self.timer_settings_btn, "settings", 16)
        self.timer_settings_btn.clicked.connect(self.timer_settings_requested.emit)

        header_row.addWidget(self.manage_timers_btn)
        header_row.addWidget(self.timer_settings_btn)

        layout.addLayout(header_row)

        # ── Haupt-Timer Reihe (Daily, Weekly, Shugo, Riss) ───────────────
        main_row = QHBoxLayout()
        main_row.setSpacing(12)

        self.daily_reset_card = TimerInfoCard("Daily Reset", "--:--", _DAILY)
        self.weekly_reset_card = TimerInfoCard("Weekly Reset", "--:--", _WEEKLY)
        self.season_timer_card = TimerInfoCard("Season", "--:--", _CUSTOM)
        self.shugo_timer_card = TimerInfoCard("Shugo", "--:--", _SHUGO)
        self.riss_timer_card = TimerInfoCard("Riss", "--:--", _RIFT)

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
                    timer_cfg.get("color") or _CUSTOM,
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
        self.manage_timers_btn.setText(tr_func(language, "timers_manage"))
        self.timer_settings_btn.setToolTip(tr_func(language, "timers_open_settings_tooltip"))
        self.daily_reset_card.title_label.setText(tr_func(language, "daily_reset").upper())
        self.weekly_reset_card.title_label.setText(tr_func(language, "weekly_reset").upper())
        self.season_timer_card.title_label.setText("SEASON")
        self.shugo_timer_card.title_label.setText(tr_func(language, "shugo").upper())
        self.riss_timer_card.title_label.setText(tr_func(language, "riss").upper())
