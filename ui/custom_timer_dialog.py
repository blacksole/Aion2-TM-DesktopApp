from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QButtonGroup, QGridLayout, QTimeEdit, QWidget,
)
from PySide6.QtCore import QTime

CUSTOM_TIMER_COLORS = [
    ("#22d3ee", "Cyan"),
    ("#a855f7", "Lila"),
    ("#22c55e", "Grün"),
    ("#ef4444", "Rot"),
    ("#f97316", "Orange"),
    ("#ec4899", "Pink"),
    ("#f59e0b", "Gelb"),
    ("#3b82f6", "Blau"),
]

_HOUR_PRESETS = [1, 2, 3, 4, 5, 6]
_DAY_KEYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


class CustomTimerDialog(QDialog):
    def __init__(self, name: str = "", color: str = "#22d3ee",
                 timer_mode: str = "hourly",
                 reset_time: str = "09:00", reset_day: str = "Mo",
                 interval_minutes: int = 60, interval_seconds: int = 3600,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Timer")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._selected_color = color
        self._timer_mode = timer_mode

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title_lbl = QLabel("Custom Timer konfigurieren")
        title_lbl.setObjectName("settingsSectionTitle")
        layout.addWidget(title_lbl)

        # ── Live-Vorschau ─────────────────────────────────────────────────
        preview_frame = QFrame()
        preview_frame.setObjectName("timerCard")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(16, 12, 16, 12)
        self.preview_title = QLabel((name or "NAME").upper())
        self.preview_title.setObjectName("statTitle")
        self.preview_value = QLabel(self._preview_text_for_mode(timer_mode))
        self.preview_value.setStyleSheet(
            f"color: {color}; font-size: 30px; font-weight: bold;"
        )
        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.preview_value)
        layout.addWidget(preview_frame)

        # ── Name ──────────────────────────────────────────────────────────
        name_row = QHBoxLayout()
        name_lbl = QLabel("Name (max. 10 Zeichen)")
        name_lbl.setObjectName("settingsLabel")
        self.name_input = QLineEdit(name)
        self.name_input.setMaxLength(10)
        self.name_input.setObjectName("settingsTimeInput")
        self.name_input.setPlaceholderText("z.B. Lager")
        self.name_input.textChanged.connect(self._update_preview)
        name_row.addWidget(name_lbl)
        name_row.addWidget(self.name_input)
        layout.addLayout(name_row)

        # ── Farb-Panel ────────────────────────────────────────────────────
        color_lbl = QLabel("Farbe")
        color_lbl.setObjectName("settingsLabel")
        layout.addWidget(color_lbl)

        color_panel = QFrame()
        color_panel.setObjectName("settingsRow")
        color_panel_layout = QGridLayout(color_panel)
        color_panel_layout.setContentsMargins(10, 10, 10, 10)
        color_panel_layout.setSpacing(8)
        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        for i, (hex_color, color_name) in enumerate(CUSTOM_TIMER_COLORS):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(44, 30)
            btn.setToolTip(color_name)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {hex_color}; border-radius: 6px;"
                f" border: 2px solid transparent; }}"
                f"QPushButton:checked {{ border: 2px solid #ffffff; }}"
                f"QPushButton:hover {{ border: 2px solid rgba(255,255,255,0.6); }}"
            )
            if hex_color == color:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked=False, c=hex_color: self._select_color(c))
            self.color_group.addButton(btn)
            color_panel_layout.addWidget(btn, i // 4, i % 4)
        layout.addWidget(color_panel)

        # ── Modus-Auswahl ─────────────────────────────────────────────────
        mode_lbl = QLabel("Timer-Modus")
        mode_lbl.setObjectName("settingsLabel")
        layout.addWidget(mode_lbl)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_buttons: dict[str, QPushButton] = {}
        for key, label in [
            ("daily",  "Daily"),
            ("weekly", "Weekly"),
            ("hourly", "Hourly"),
            ("custom", "Custom"),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("dayButton")
            btn.setFixedHeight(32)
            btn.setChecked(key == timer_mode)
            btn.clicked.connect(lambda checked=False, m=key: self._on_mode_changed(m))
            self._mode_group.addButton(btn)
            self._mode_buttons[key] = btn
            mode_row.addWidget(btn)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # ── Abschnittsbezeichnung ─────────────────────────────────────────
        self._section_lbl = QLabel()
        self._section_lbl.setObjectName("settingsLabel")
        layout.addWidget(self._section_lbl)

        # ── Daily-Abschnitt ───────────────────────────────────────────────
        self._daily_widget = QWidget()
        daily_layout = QHBoxLayout(self._daily_widget)
        daily_layout.setContentsMargins(0, 0, 0, 0)
        daily_layout.setSpacing(8)
        h_d, m_d = map(int, reset_time.split(":"))
        self.daily_time = QTimeEdit()
        self.daily_time.setObjectName("settingsTimeInput")
        self.daily_time.setDisplayFormat("HH:mm")
        self.daily_time.setTime(QTime(h_d, m_d))
        self.daily_time.setFixedWidth(110)
        daily_layout.addWidget(self.daily_time)
        daily_layout.addStretch()
        layout.addWidget(self._daily_widget)

        # ── Weekly-Abschnitt ──────────────────────────────────────────────
        self._weekly_widget = QWidget()
        weekly_layout = QVBoxLayout(self._weekly_widget)
        weekly_layout.setContentsMargins(0, 0, 0, 0)
        weekly_layout.setSpacing(6)

        day_btn_row = QHBoxLayout()
        day_btn_row.setSpacing(4)
        self._weekly_day_group = QButtonGroup(self)
        self._weekly_day_group.setExclusive(True)
        for day_key in _DAY_KEYS:
            btn = QPushButton(day_key)
            btn.setCheckable(True)
            btn.setObjectName("dayButton")
            btn.setFixedSize(38, 28)
            btn.setProperty("day_key", day_key)
            btn.setChecked(day_key == reset_day)
            self._weekly_day_group.addButton(btn)
            day_btn_row.addWidget(btn)
        day_btn_row.addStretch()
        weekly_layout.addLayout(day_btn_row)

        weekly_time_row = QHBoxLayout()
        h_w, m_w = map(int, reset_time.split(":"))
        self.weekly_time = QTimeEdit()
        self.weekly_time.setObjectName("settingsTimeInput")
        self.weekly_time.setDisplayFormat("HH:mm")
        self.weekly_time.setTime(QTime(h_w, m_w))
        self.weekly_time.setFixedWidth(110)
        weekly_time_row.addWidget(self.weekly_time)
        weekly_time_row.addStretch()
        weekly_layout.addLayout(weekly_time_row)
        layout.addWidget(self._weekly_widget)

        # ── Hourly-Abschnitt ──────────────────────────────────────────────
        self._hourly_widget = QWidget()
        hourly_outer = QVBoxLayout(self._hourly_widget)
        hourly_outer.setContentsMargins(0, 0, 0, 0)
        hourly_outer.setSpacing(6)

        presets_row = QHBoxLayout()
        presets_row.setSpacing(6)
        self._hourly_preset_group = QButtonGroup(self)
        self._hourly_preset_group.setExclusive(True)
        preset_match = False
        for h in _HOUR_PRESETS:
            btn = QPushButton(f"{h}h")
            btn.setCheckable(True)
            btn.setObjectName("dayButton")
            btn.setFixedSize(46, 32)
            if h * 60 == interval_minutes:
                btn.setChecked(True)
                preset_match = True
            self._hourly_preset_group.addButton(btn)
            presets_row.addWidget(btn)

        self._hourly_pencil_btn = QPushButton("✏")
        self._hourly_pencil_btn.setObjectName("secondaryButton")
        self._hourly_pencil_btn.setFixedSize(36, 32)
        self._hourly_pencil_btn.setCheckable(True)
        self._hourly_pencil_btn.setChecked(not preset_match and timer_mode == "hourly")
        self._hourly_pencil_btn.clicked.connect(self._on_hourly_pencil_clicked)
        presets_row.addWidget(self._hourly_pencil_btn)
        presets_row.addStretch()
        hourly_outer.addLayout(presets_row)

        self._hourly_manual_widget = QWidget()
        hourly_manual_layout = QHBoxLayout(self._hourly_manual_widget)
        hourly_manual_layout.setContentsMargins(0, 0, 0, 0)
        h_i, m_i = divmod(max(1, interval_minutes), 60)
        self.hourly_time = QTimeEdit()
        self.hourly_time.setObjectName("settingsTimeInput")
        self.hourly_time.setDisplayFormat("HH:mm")
        self.hourly_time.setTime(QTime(h_i, m_i))
        self.hourly_time.setFixedWidth(110)
        hourly_manual_layout.addWidget(self.hourly_time)
        hourly_manual_layout.addStretch()
        self._hourly_manual_widget.setVisible(self._hourly_pencil_btn.isChecked())
        hourly_outer.addWidget(self._hourly_manual_widget)
        layout.addWidget(self._hourly_widget)

        # ── Custom-Abschnitt ──────────────────────────────────────────────
        self._custom_widget = QWidget()
        custom_layout = QHBoxLayout(self._custom_widget)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        cs = max(1, interval_seconds)
        ch, rem = divmod(cs, 3600)
        cm, csec = divmod(rem, 60)
        self.custom_time = QTimeEdit()
        self.custom_time.setObjectName("settingsTimeInput")
        self.custom_time.setDisplayFormat("HH:mm:ss")
        self.custom_time.setTime(QTime(min(ch, 23), cm, csec))
        self.custom_time.setFixedWidth(130)
        custom_layout.addWidget(self.custom_time)
        custom_layout.addStretch()
        layout.addWidget(self._custom_widget)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton("Abbrechen")
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton("Speichern")
        self.ok_btn.setObjectName("primaryButton")
        self.ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.ok_btn)
        layout.addLayout(btn_row)

        self._apply_mode_ui(timer_mode, animate=False)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _select_color(self, color: str):
        self._selected_color = color
        self.preview_value.setStyleSheet(
            f"color: {color}; font-size: 30px; font-weight: bold;"
        )

    def _update_preview(self):
        text = self.name_input.text().strip().upper() or "NAME"
        self.preview_title.setText(text)

    def _on_mode_changed(self, mode: str):
        self._timer_mode = mode
        self.preview_value.setText(self._preview_text_for_mode(mode))
        self._apply_mode_ui(mode)

    def _on_hourly_pencil_clicked(self):
        self._hourly_manual_widget.setVisible(self._hourly_pencil_btn.isChecked())

    def _apply_mode_ui(self, mode: str, animate: bool = True):
        labels = {
            "daily":  "Tageszeit (Reset-Uhrzeit)",
            "weekly": "Wochentag & Uhrzeit",
            "hourly": "Intervall",
            "custom": "Intervall (hh:mm:ss)",
        }
        self._section_lbl.setText(labels.get(mode, ""))
        self._daily_widget.setVisible(mode == "daily")
        self._weekly_widget.setVisible(mode == "weekly")
        self._hourly_widget.setVisible(mode == "hourly")
        self._custom_widget.setVisible(mode == "custom")

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _preview_text_for_mode(mode: str) -> str:
        return {
            "daily":  "05:30:00",
            "weekly": "2T 14:30",
            "hourly": "01:30:00",
            "custom": "00:45:30",
        }.get(mode, "00:00:00")

    # ── Result ────────────────────────────────────────────────────────────

    def get_values(self) -> dict:
        mode = self._timer_mode
        result = {
            "name":       self.name_input.text().strip() or "Timer",
            "color":      self._selected_color,
            "timer_mode": mode,
        }
        if mode == "daily":
            t = self.daily_time.time()
            result["reset_time"] = t.toString("HH:mm")
        elif mode == "weekly":
            checked = self._weekly_day_group.checkedButton()
            result["reset_day"]  = checked.property("day_key") if checked else "Mo"
            t = self.weekly_time.time()
            result["reset_time"] = t.toString("HH:mm")
        elif mode == "hourly":
            checked = self._hourly_preset_group.checkedButton()
            if checked and not self._hourly_pencil_btn.isChecked():
                h = int(checked.text().replace("h", ""))
                result["interval_minutes"] = h * 60
            else:
                t = self.hourly_time.time()
                result["interval_minutes"] = max(1, t.hour() * 60 + t.minute())
        else:  # custom
            t = self.custom_time.time()
            secs = t.hour() * 3600 + t.minute() * 60 + t.second()
            result["interval_seconds"] = max(60, secs)
        return result
