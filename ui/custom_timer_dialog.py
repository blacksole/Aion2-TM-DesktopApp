from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QButtonGroup, QGridLayout, QTimeEdit, QWidget, QSpinBox, QComboBox,
    QTabWidget, QCompleter,
)
from PySide6.QtCore import QTime, Qt

from core import theme
from core.sound import play_wav
from ui.pages.settings_page import (
    SOUND_BROWSE_DATA, _ScreenAwareComboBox, browse_for_wav, populate_sound_combo,
)

#: The eight swatches a user can pick for a custom timer, as
#: ``(hex, translation key)``.  The hexes used to be literals here; the
#: table now comes from ``core.theme``'s ``timer_swatch`` data colours, which
#: makes core/theme.py the single owner (MASTER §4-4) and this list a
#: rendering of it.  The order is the table's declaration order.
CUSTOM_TIMER_COLORS = [
    (theme.data_color("timer_swatch", key), f"ct_color_{key}")
    for key in theme.data_color_keys("timer_swatch")
]

#: Colour a brand-new timer starts on (the first swatch).
DEFAULT_TIMER_COLOR = CUSTOM_TIMER_COLORS[0][0]

_HOUR_PRESETS = [1, 2, 3, 4, 5, 6]
_DAY_KEYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
_MODE_ORDER = ["daily", "weekly", "hourly", "custom", "countdown"]


class CustomTimerDialog(QDialog):
    def __init__(self, name: str = "", color: str = "",
                 timer_mode: str = "hourly",
                 reset_time: str = "09:00", reset_day: str = "Mo",
                 interval_minutes: int = 60, interval_seconds: int = 3600,
                 start_time: str = "",
                 countdown_duration_seconds: int = 7200,
                 countdown_restart_delay_seconds: int = 0,
                 categories: list = None, category: str = "",
                 notification_sound: str = "",
                 notification_warn_minutes: int = 1,
                 language: str = "en", tr_func=None,
                 parent=None):
        super().__init__(parent)
        self._language = language
        self._tr = tr_func or (lambda _l, k, **kw: k)
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

        title_lbl = QLabel(self._tr(self._language, "ct_dialog_title"))
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
        # #bigValue in the template owns the type (font.mono, text.display,
        # bold -- MASTER §3 "gros chiffres"); only the COLOUR is set here,
        # because it is the per-timer colour the user picked, i.e. data
        # (MASTER §4-4's tolerated exception).
        self.preview_value.setObjectName("bigValue")
        self._paint_preview_color(color)
        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.preview_value)
        layout.addWidget(preview_frame)

        # ── Name + Kategorie ──────────────────────────────────────────────
        meta_row = QHBoxLayout()
        meta_row.setSpacing(16)

        name_col = QVBoxLayout()
        name_col.setSpacing(4)
        name_lbl = QLabel(self._tr(self._language, "ct_dialog_name_label"))
        name_lbl.setObjectName("settingsLabel")
        self.name_input = QLineEdit(name)
        self.name_input.setMaxLength(10)
        self.name_input.setObjectName("settingsTimeInput")
        self.name_input.setPlaceholderText(self._tr(self._language, "ct_dialog_name_placeholder"))
        self.name_input.textChanged.connect(self._update_preview)
        name_col.addWidget(name_lbl)
        name_col.addWidget(self.name_input)

        cat_col = QVBoxLayout()
        cat_col.setSpacing(4)
        cat_lbl = QLabel(self._tr(self._language, "ct_dialog_category_label"))
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
        reset_lbl = QLabel(self._tr(self._language, "ct_dialog_reset_time_label"))
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
        self._mode_tabs.addTab(daily_tab, self._tr(self._language, "schedule_daily"))

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
        wtime_lbl = QLabel(self._tr(self._language, "ct_dialog_time_label"))
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
        self._mode_tabs.addTab(weekly_tab, self._tr(self._language, "schedule_weekly"))

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
        self._hourly_pencil_btn = QPushButton(self._tr(self._language, "ct_dialog_tab_custom"))
        self._hourly_pencil_btn.setObjectName("secondaryButton")
        self._hourly_pencil_btn.setFixedSize(112, 32)
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
        hourly_start_row = QHBoxLayout()
        hourly_start_row.setSpacing(8)
        hourly_start_lbl = QLabel(self._tr(self._language, "ct_dialog_start_label"))
        hourly_start_lbl.setObjectName("settingsInlineLabel")
        hourly_start_lbl.setFixedWidth(70)
        h_hst, m_hst = map(int, start_time.split(":"))
        self.hourly_start_time = QTimeEdit()
        self.hourly_start_time.setObjectName("settingsTimeInput")
        self.hourly_start_time.setDisplayFormat("HH:mm")
        self.hourly_start_time.setTime(QTime(h_hst, m_hst))
        self.hourly_start_time.setFixedWidth(110)
        hourly_start_row.addWidget(hourly_start_lbl)
        hourly_start_row.addWidget(self.hourly_start_time)
        hourly_start_row.addStretch()
        htl.addLayout(hourly_start_row)
        htl.addStretch()
        self._mode_tabs.addTab(hourly_tab, self._tr(self._language, "ct_dialog_tab_hourly"))

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
        start_lbl = QLabel(self._tr(self._language, "ct_dialog_start_label"))
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
        ivl_lbl = QLabel(self._tr(self._language, "ct_dialog_interval_label"))
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
        self._mode_tabs.addTab(custom_tab, self._tr(self._language, "ct_dialog_tab_custom"))

        # Countdown -- manually started/stopped from the overlay (User-
        # Wunsch, 2026-09-07: "einen Countdown Button für das Overlay ...
        # stellt diesen Countdown Timer auf eine Zeit ein"), unlike the
        # other modes which always run from wall-clock alone. Only the
        # static config (duration + optional auto-restart delay) lives
        # here -- the running/started-at state is runtime-only, toggled
        # from the overlay's Start/Stop button (see main_window.py).
        countdown_tab = QWidget()
        cdtl = QVBoxLayout(countdown_tab)
        cdtl.setContentsMargins(8, 16, 8, 8)
        cdtl.setSpacing(10)
        cd_dur = max(1, countdown_duration_seconds)
        cd_h, cd_m = divmod(cd_dur // 60, 60)
        cd_duration_row = QHBoxLayout()
        cd_duration_row.setSpacing(6)
        cd_dur_lbl = QLabel(self._tr(self._language, "ct_dialog_duration_label"))
        cd_dur_lbl.setObjectName("settingsInlineLabel")
        cd_dur_lbl.setFixedWidth(70)
        self.countdown_hours = QSpinBox()
        self.countdown_hours.setObjectName("settingsTimeInput")
        self.countdown_hours.setRange(0, 99)
        self.countdown_hours.setValue(min(cd_h, 99))
        self.countdown_hours.setFixedWidth(90)
        cd_h_unit = QLabel("h")
        cd_h_unit.setObjectName("settingsInlineLabel")
        self.countdown_minutes = QSpinBox()
        self.countdown_minutes.setObjectName("settingsTimeInput")
        self.countdown_minutes.setRange(0, 59)
        self.countdown_minutes.setValue(cd_m)
        self.countdown_minutes.setFixedWidth(90)
        cd_m_unit = QLabel("min")
        cd_m_unit.setObjectName("settingsInlineLabel")
        cd_duration_row.addWidget(cd_dur_lbl)
        cd_duration_row.addWidget(self.countdown_hours)
        cd_duration_row.addWidget(cd_h_unit)
        cd_duration_row.addSpacing(6)
        cd_duration_row.addWidget(self.countdown_minutes)
        cd_duration_row.addWidget(cd_m_unit)
        cd_duration_row.addStretch()
        cdtl.addLayout(cd_duration_row)
        # Auto-restart delay
        cd_delay_row = QHBoxLayout()
        cd_delay_row.setSpacing(6)
        cd_delay_lbl = QLabel(self._tr(self._language, "ct_dialog_restart_after_label"))
        cd_delay_lbl.setObjectName("settingsInlineLabel")
        cd_delay_lbl.setFixedWidth(90)
        self.countdown_restart_delay = QSpinBox()
        self.countdown_restart_delay.setObjectName("settingsTimeInput")
        self.countdown_restart_delay.setRange(0, 60)
        self.countdown_restart_delay.setValue(
            max(0, min(60, countdown_restart_delay_seconds))
        )
        self.countdown_restart_delay.setFixedWidth(90)
        cd_delay_unit = QLabel(self._tr(self._language, "ct_dialog_seconds_unit"))
        cd_delay_unit.setObjectName("settingsInlineLabel")
        cd_delay_row.addWidget(cd_delay_lbl)
        cd_delay_row.addWidget(self.countdown_restart_delay)
        cd_delay_row.addWidget(cd_delay_unit)
        cd_delay_row.addStretch()
        cdtl.addLayout(cd_delay_row)
        cd_hint = QLabel(self._tr(self._language, "ct_dialog_countdown_hint"))
        cd_hint.setObjectName("settingsDescription")
        cdtl.addWidget(cd_hint)
        cdtl.addStretch()
        self._mode_tabs.addTab(countdown_tab, self._tr(self._language, "ct_dialog_tab_countdown"))

        tab_idx = _MODE_ORDER.index(timer_mode) if timer_mode in _MODE_ORDER else 2
        self._mode_tabs.setCurrentIndex(tab_idx)
        self._mode_tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._mode_tabs)

        # ── 3. Farbe ──────────────────────────────────────────────────────
        color_lbl = QLabel(self._tr(self._language, "ct_dialog_color_label"))
        color_lbl.setObjectName("settingsLabel")
        layout.addWidget(color_lbl)

        color_panel = QFrame()
        color_panel.setObjectName("settingsRow")
        color_panel_layout = QGridLayout(color_panel)
        color_panel_layout.setContentsMargins(10, 10, 10, 10)
        color_panel_layout.setSpacing(8)
        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        for i, (hex_color, color_name_key) in enumerate(CUSTOM_TIMER_COLORS):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(44, 30)
            btn.setToolTip(self._tr(self._language, color_name_key))
            # Swatch = the colour itself, so the FILL is data. Radius and
            # the checked/hover ring come from #ctColorSwatch in the
            # template (the ring used to be a hardcoded white).
            btn.setObjectName("ctColorSwatch")
            btn.setStyleSheet(f"QPushButton {{ background-color: {hex_color}; }}")
            if hex_color == color:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked=False, c=hex_color: self._select_color(c))
            self.color_group.addButton(btn)
            color_panel_layout.addWidget(btn, i // 4, i % 4)
        layout.addWidget(color_panel)

        # ── 4. Benachrichtigungston ───────────────────────────────────────
        sound_lbl = QLabel(self._tr(self._language, "ct_dialog_notification_sound_label"))
        sound_lbl.setObjectName("settingsLabel")
        layout.addWidget(sound_lbl)

        sound_row = QFrame()
        sound_row.setObjectName("settingsRow")
        sound_row_layout = QHBoxLayout(sound_row)
        sound_row_layout.setContentsMargins(14, 12, 14, 12)
        sound_row_layout.setSpacing(12)

        # Real bug found + fixed (User-reported, 2026-09-11, screenshot:
        # same giant unclamped ~70-sound popup as the general Settings
        # page's Notification Sound dropdown, "bei den Custom Timer
        # genauso") -- same fix applied here: capped popup height + a
        # search-as-you-type completer, plus the same screen-aware popup
        # positioning fix (multi-monitor setup, see _ScreenAwareComboBox).
        self.sound_combo = _ScreenAwareComboBox()
        self.sound_combo.setObjectName("settingsCombo")
        self.sound_combo.setMaxVisibleItems(9)
        self.sound_combo.setEditable(True)
        self.sound_combo.setInsertPolicy(QComboBox.NoInsert)
        sound_completer = self.sound_combo.completer()
        if sound_completer is not None:
            sound_completer.setCaseSensitivity(Qt.CaseInsensitive)
            sound_completer.setFilterMode(Qt.MatchContains)
            sound_completer.setCompletionMode(QCompleter.PopupCompletion)
        populate_sound_combo(self.sound_combo, notification_sound, self._tr, self._language)
        # The sentinel keeps this dialog's own wording ("-- Kein Sound --"),
        # which differs from Settings' "-- No Sound --" key.
        self.sound_combo.setItemText(0, self._tr(self._language, "ct_dialog_no_sound"))
        self._last_sound_index = self.sound_combo.currentIndex()
        self.sound_combo.currentIndexChanged.connect(self._on_sound_combo_changed)

        self.sound_test_btn = QPushButton(self._tr(self._language, "ct_dialog_test_button"))
        self.sound_test_btn.setObjectName("secondaryButton")
        self.sound_test_btn.setFixedWidth(70)
        self.sound_test_btn.clicked.connect(self._preview_sound)

        warn_lbl = QLabel(self._tr(self._language, "ct_dialog_warn_label"))
        warn_lbl.setObjectName("settingsInlineLabel")

        self.warn_combo = QComboBox()
        self.warn_combo.setObjectName("settingsCombo")
        self.warn_combo.setFixedWidth(90)
        for v in (0, 1, 3, 5, 10):
            self.warn_combo.addItem(f"{v} min", v)
        warn_idx = self.warn_combo.findData(notification_warn_minutes)
        self.warn_combo.setCurrentIndex(max(0, warn_idx))

        sound_row_layout.addWidget(self.sound_combo, 1)
        sound_row_layout.addWidget(warn_lbl)
        sound_row_layout.addWidget(self.warn_combo)
        sound_row_layout.addWidget(self.sound_test_btn)
        layout.addWidget(sound_row)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton(self._tr(self._language, "cancel"))
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton(self._tr(self._language, "save"))
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
        self._paint_preview_color(color)

    def _paint_preview_color(self, color: str):
        """The one inline property left here: the timer's own data colour."""
        self.preview_value.setStyleSheet(f"color: {color or DEFAULT_TIMER_COLOR};")

    def _update_preview(self):
        self.preview_title.setText(self.name_input.text().strip().upper() or "NAME")

    def _on_hourly_pencil_clicked(self):
        self._hourly_manual_widget.setVisible(self._hourly_pencil_btn.isChecked())

    def _on_sound_combo_changed(self, index: int):
        if self.sound_combo.itemData(index) == SOUND_BROWSE_DATA:
            browse_for_wav(self, self.sound_combo, getattr(self, "_last_sound_index", 0))
        self._last_sound_index = self.sound_combo.currentIndex()

    def _preview_sound(self):
        play_wav(self.sound_combo.currentData() or "")

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _preview_text_for_mode(mode: str) -> str:
        return {
            "daily":  "05:30:00",
            "weekly": "2T 14:30",
            "hourly": "01:30:00",
            "custom": "2T 23:00",
            "countdown": "02:00:00",
        }.get(mode, "00:00:00")

    # ── Result ────────────────────────────────────────────────────────────

    def get_values(self) -> dict:
        mode = self._timer_mode
        result = {
            "name":     self.name_input.text().strip() or "Timer",
            "color":    self._selected_color,
            "timer_mode": mode,
            "category": self.category_combo.currentText(),
            "notification_sound": self.sound_combo.currentData() or "",
            "notification_warn_minutes": self.warn_combo.currentData(),
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
            result["start_time"] = self.hourly_start_time.time().toString("HH:mm")
        elif mode == "countdown":
            total_min = self.countdown_hours.value() * 60 + self.countdown_minutes.value()
            result["countdown_duration_seconds"] = max(60, total_min * 60)
            result["countdown_restart_delay_seconds"] = self.countdown_restart_delay.value()
        else:  # custom
            total_min = self.custom_hours.value() * 60 + self.custom_minutes.value()
            result["interval_seconds"] = max(60, total_min * 60)
            result["start_time"] = self.custom_start_time.time().toString("HH:mm")
        return result
