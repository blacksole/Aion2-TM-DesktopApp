from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QButtonGroup, QGridLayout, QTimeEdit, QWidget, QSpinBox, QComboBox,
    QTabWidget,
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
_MODE_ORDER = ["daily", "weekly", "hourly", "custom"]


class CustomTimerDialog(QDialog):
    def __init__(self, name: str = "", color: str = "#22d3ee",
                 timer_mode: str = "hourly",
                 reset_time: str = "09:00", reset_day: str = "Mo",
                 interval_minutes: int = 60, interval_seconds: int = 3600,
                 start_time: str = "",
                 categories: list = None, category: str = "",
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Timer")
        self.setModal(True)
        self.setMinimumWidth(500)
        self._selected_color = color
        self._timer_mode = timer_mode
        self._categories = categories or ["Custom Timer"]
        if not start_time:
            from datetime import datetime
            start_time = datetime.now().strftime("%H:%M")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title_lbl = QLabel("Custom Timer konfigurieren")
        title_lbl.setObjectName("settingsSectionTitle")
        layout.addWidget(title_lbl)

        # ── 1. Anzeige (Preview) ──────────────────────────────────────────
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

        # ── Name + Kategorie ──────────────────────────────────────────────
        meta_row = QHBoxLayout()
        meta_row.setSpacing(16)

        name_col = QVBoxLayout()
        name_col.setSpacing(4)
        name_lbl = QLabel("Name (max. 10 Zeichen)")
        name_lbl.setObjectName("settingsLabel")
        self.name_input = QLineEdit(name)
        self.name_input.setMaxLength(10)
        self.name_input.setObjectName("settingsTimeInput")
        self.name_input.setPlaceholderText("z.B. Lager")
        self.name_input.textChanged.connect(self._update_preview)
        name_col.addWidget(name_lbl)
        name_col.addWidget(self.name_input)

        cat_col = QVBoxLayout()
        cat_col.setSpacing(4)
        cat_lbl = QLabel("Kategorie")
        cat_lbl.setObjectName("settingsLabel")
        self.category_combo = QComboBox()
        self.category_combo.setObjectName("settingsCombo")
        for cat in self._categories:
            self.category_combo.addItem(cat)
        cur_cat = category or (self._categories[0] if self._categories else "Custom Timer")
        idx = self.category_combo.findText(cur_cat)
        self.category_combo.setCurrentIndex(max(0, idx))
        cat_col.addWidget(cat_lbl)
        cat_col.addWidget(self.category_combo)

        meta_row.addLayout(name_col, 2)
        meta_row.addLayout(cat_col, 1)
        layout.addLayout(meta_row)

        # ── 2. Timer-Modus als Tabs ───────────────────────────────────────
        self._mode_tabs = QTabWidget()
        self._mode_tabs.setObjectName("timerModeTabWidget")

        # Daily
        daily_tab = QWidget()
        dtl = QVBoxLayout(daily_tab)
        dtl.setContentsMargins(8, 16, 8, 8)
        dtl.setSpacing(10)
        h_d, m_d = map(int, reset_time.split(":"))
        daily_row = QHBoxLayout()
        reset_lbl = QLabel("Reset-Uhrzeit")
        reset_lbl.setObjectName("settingsInlineLabel")
        reset_lbl.setFixedWidth(110)
        self.daily_time = QTimeEdit()
        self.daily_time.setObjectName("settingsTimeInput")
        self.daily_time.setDisplayFormat("HH:mm")
        self.daily_time.setTime(QTime(h_d, m_d))
        self.daily_time.setFixedWidth(110)
        daily_row.addWidget(reset_lbl)
        daily_row.addWidget(self.daily_time)
        daily_row.addStretch()
        dtl.addLayout(daily_row)
        dtl.addStretch()
        self._mode_tabs.addTab(daily_tab, "Daily")

        # Weekly
        weekly_tab = QWidget()
        wtl = QVBoxLayout(weekly_tab)
        wtl.setContentsMargins(8, 16, 8, 8)
        wtl.setSpacing(10)
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
        h_w, m_w = map(int, reset_time.split(":"))
        weekly_time_row = QHBoxLayout()
        wtime_lbl = QLabel("Uhrzeit")
        wtime_lbl.setObjectName("settingsInlineLabel")
        wtime_lbl.setFixedWidth(110)
        self.weekly_time = QTimeEdit()
        self.weekly_time.setObjectName("settingsTimeInput")
        self.weekly_time.setDisplayFormat("HH:mm")
        self.weekly_time.setTime(QTime(h_w, m_w))
        self.weekly_time.setFixedWidth(110)
        weekly_time_row.addWidget(wtime_lbl)
        weekly_time_row.addWidget(self.weekly_time)
        weekly_time_row.addStretch()
        wtl.addLayout(day_btn_row)
        wtl.addLayout(weekly_time_row)
        wtl.addStretch()
        self._mode_tabs.addTab(weekly_tab, "Weekly")

        # Hourly
        hourly_tab = QWidget()
        htl = QVBoxLayout(hourly_tab)
        htl.setContentsMargins(8, 16, 8, 8)
        htl.setSpacing(8)
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
        self._hourly_pencil_btn = QPushButton("Custom")
        self._hourly_pencil_btn.setObjectName("secondaryButton")
        self._hourly_pencil_btn.setFixedSize(64, 32)
        self._hourly_pencil_btn.setCheckable(True)
        self._hourly_pencil_btn.setChecked(not preset_match and timer_mode == "hourly")
        self._hourly_pencil_btn.clicked.connect(self._on_hourly_pencil_clicked)
        presets_row.addWidget(self._hourly_pencil_btn)
        presets_row.addStretch()
        htl.addLayout(presets_row)
        self._hourly_manual_widget = QWidget()
        hmanual_row = QHBoxLayout(self._hourly_manual_widget)
        hmanual_row.setContentsMargins(0, 0, 0, 0)
        h_i, m_i = divmod(max(1, interval_minutes), 60)
        self.hourly_time = QTimeEdit()
        self.hourly_time.setObjectName("settingsTimeInput")
        self.hourly_time.setDisplayFormat("HH:mm")
        self.hourly_time.setTime(QTime(h_i, m_i))
        self.hourly_time.setFixedWidth(110)
        hmanual_row.addWidget(self.hourly_time)
        hmanual_row.addStretch()
        self._hourly_manual_widget.setVisible(self._hourly_pencil_btn.isChecked())
        htl.addWidget(self._hourly_manual_widget)
        htl.addStretch()
        self._mode_tabs.addTab(hourly_tab, "Hourly")

        # Custom
        custom_tab = QWidget()
        ctl = QVBoxLayout(custom_tab)
        ctl.setContentsMargins(8, 16, 8, 8)
        ctl.setSpacing(10)
        cs = max(60, interval_seconds)
        cs_h, cs_m = divmod(cs // 60, 60)
        # Start
        custom_start_row = QHBoxLayout()
        custom_start_row.setSpacing(8)
        start_lbl = QLabel("Start")
        start_lbl.setObjectName("settingsInlineLabel")
        start_lbl.setFixedWidth(70)
        h_st, m_st = map(int, start_time.split(":"))
        self.custom_start_time = QTimeEdit()
        self.custom_start_time.setObjectName("settingsTimeInput")
        self.custom_start_time.setDisplayFormat("HH:mm")
        self.custom_start_time.setTime(QTime(h_st, m_st))
        self.custom_start_time.setFixedWidth(110)
        custom_start_row.addWidget(start_lbl)
        custom_start_row.addWidget(self.custom_start_time)
        custom_start_row.addStretch()
        ctl.addLayout(custom_start_row)
        # Intervall
        custom_interval_row = QHBoxLayout()
        custom_interval_row.setSpacing(6)
        ivl_lbl = QLabel("Intervall")
        ivl_lbl.setObjectName("settingsInlineLabel")
        ivl_lbl.setFixedWidth(70)
        self.custom_hours = QSpinBox()
        self.custom_hours.setObjectName("settingsTimeInput")
        self.custom_hours.setRange(0, 99)
        self.custom_hours.setValue(min(cs_h, 99))
        self.custom_hours.setFixedWidth(90)
        h_unit = QLabel("h")
        h_unit.setObjectName("settingsInlineLabel")
        self.custom_minutes = QSpinBox()
        self.custom_minutes.setObjectName("settingsTimeInput")
        self.custom_minutes.setRange(0, 59)
        self.custom_minutes.setValue(cs_m)
        self.custom_minutes.setFixedWidth(90)
        m_unit = QLabel("min")
        m_unit.setObjectName("settingsInlineLabel")
        custom_interval_row.addWidget(ivl_lbl)
        custom_interval_row.addWidget(self.custom_hours)
        custom_interval_row.addWidget(h_unit)
        custom_interval_row.addSpacing(6)
        custom_interval_row.addWidget(self.custom_minutes)
        custom_interval_row.addWidget(m_unit)
        custom_interval_row.addStretch()
        ctl.addLayout(custom_interval_row)
        ctl.addStretch()
        self._mode_tabs.addTab(custom_tab, "Custom")

        tab_idx = _MODE_ORDER.index(timer_mode) if timer_mode in _MODE_ORDER else 2
        self._mode_tabs.setCurrentIndex(tab_idx)
        self._mode_tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._mode_tabs)

        # ── 3. Farbe ──────────────────────────────────────────────────────
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

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_tab_changed(self, idx: int):
        self._timer_mode = _MODE_ORDER[idx] if idx < len(_MODE_ORDER) else "hourly"
        self.preview_value.setText(self._preview_text_for_mode(self._timer_mode))

    def _select_color(self, color: str):
        self._selected_color = color
        self.preview_value.setStyleSheet(
            f"color: {color}; font-size: 30px; font-weight: bold;"
        )

    def _update_preview(self):
        self.preview_title.setText(self.name_input.text().strip().upper() or "NAME")

    def _on_hourly_pencil_clicked(self):
        self._hourly_manual_widget.setVisible(self._hourly_pencil_btn.isChecked())

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _preview_text_for_mode(mode: str) -> str:
        return {
            "daily":  "05:30:00",
            "weekly": "2T 14:30",
            "hourly": "01:30:00",
            "custom": "2T 23:00",
        }.get(mode, "00:00:00")

    # ── Result ────────────────────────────────────────────────────────────

    def get_values(self) -> dict:
        mode = self._timer_mode
        result = {
            "name":     self.name_input.text().strip() or "Timer",
            "color":    self._selected_color,
            "timer_mode": mode,
            "category": self.category_combo.currentText(),
        }
        if mode == "daily":
            result["reset_time"] = self.daily_time.time().toString("HH:mm")
        elif mode == "weekly":
            checked = self._weekly_day_group.checkedButton()
            result["reset_day"]  = checked.property("day_key") if checked else "Mo"
            result["reset_time"] = self.weekly_time.time().toString("HH:mm")
        elif mode == "hourly":
            checked = self._hourly_preset_group.checkedButton()
            if checked and not self._hourly_pencil_btn.isChecked():
                result["interval_minutes"] = int(checked.text().replace("h", "")) * 60
            else:
                t = self.hourly_time.time()
                result["interval_minutes"] = max(1, t.hour() * 60 + t.minute())
        else:  # custom
            total_min = self.custom_hours.value() * 60 + self.custom_minutes.value()
            result["interval_seconds"] = max(60, total_min * 60)
            result["start_time"] = self.custom_start_time.time().toString("HH:mm")
        return result
