import glob
import os
import subprocess
import webbrowser
import winsound
from pathlib import Path
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Signal, QTime, QSize, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QStackedWidget, QComboBox, QTimeEdit, QButtonGroup, QGridLayout,
    QDialog, QFileDialog, QLineEdit, QScrollArea, QInputDialog, QTabWidget,
)
from ui.custom_timer_dialog import CustomTimerDialog

_PAYPAL_URL = "https://www.paypal.com/donate/?hosted_button_id=US4YUPTVHG87C"



class SettingsPage(QWidget):
    language_changed = Signal(str)
    theme_changed = Signal(str)
    daily_reset_changed = Signal(str)
    weekly_reset_day_changed = Signal(str)
    weekly_reset_time_changed = Signal(str)
    settings_save_requested = Signal(dict)
    check_update_requested = Signal()
    profile_dir_changed = Signal(str)
    dps_start_requested = Signal(str)  # emits path

    def __init__(self):
        super().__init__()

        self.project_root = Path(__file__).resolve().parent.parent.parent
        self._cur_lang = "de"
        self._cur_tr = None

        self._custom_timer_configs = []
        self._timer_categories = ["Custom Timer"]

        self.setup_ui()

    def setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(16)

        self.title_label = QLabel("Settings")
        self.title_label.setObjectName("mainTitle")

        self.subtitle_label = QLabel("App, layout and timer settings")
        self.subtitle_label.setObjectName("subtitle")

        root_layout.addWidget(self.title_label)
        root_layout.addWidget(self.subtitle_label)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(16)

        self.settings_sidebar = QFrame()
        self.settings_sidebar.setObjectName("settingsSidebar")
        self.settings_sidebar.setFixedWidth(220)

        sidebar_layout = QVBoxLayout(self.settings_sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(8)

        self.btn_general = QPushButton()
        self.btn_timer = QPushButton()
        self.btn_notifications = QPushButton()
        self.btn_layout = QPushButton()
        self.btn_language = QPushButton()
        self.btn_profiles = QPushButton()

        self.setting_buttons = [
            self.btn_general,
            self.btn_timer,
            self.btn_notifications,
            self.btn_layout,
            self.btn_language,
            self.btn_profiles,
        ]

        for button in self.setting_buttons:
            button.setObjectName("settingsNavButton")
            button.setMinimumHeight(44)
            sidebar_layout.addWidget(button)

        sidebar_layout.addStretch()

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("settingsContentStack")

        self.general_page = self._create_general_page()

        self.timer_page = self._create_timer_page()

        self.notifications_page = self._create_notifications_page()

        self.layout_page = self._create_layout_page()

        self.language_page = self._create_language_page()

        self.profiles_page = self._create_profiles_page()

        self.content_stack.addWidget(self.general_page)       # 0
        self.content_stack.addWidget(self.timer_page)          # 1
        self.content_stack.addWidget(self.notifications_page)  # 2
        self.content_stack.addWidget(self.layout_page)         # 3
        self.content_stack.addWidget(self.language_page)       # 4
        self.content_stack.addWidget(self.profiles_page)       # 5

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setWidget(self.content_stack)

        body_layout.addWidget(self.settings_sidebar)
        body_layout.addWidget(scroll_area, 1)

        root_layout.addLayout(body_layout, 1)

        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("primaryButton")
        root_layout.addWidget(self.save_btn)

        self._connect_signals()
        self.save_btn.clicked.connect(self._emit_save_requested)
        self._set_active_button(self.btn_general)

    def _create_placeholder_page(self, title, description):
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("settingsSectionTitle")

        description_label = QLabel(description)
        description_label.setObjectName("settingsSectionDescription")
        description_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addStretch()

        return page

    def _connect_signals(self):
        self.btn_general.clicked.connect(
            lambda: self._show_section(0, self.btn_general)
        )
        self.btn_timer.clicked.connect(
            lambda: self._show_section(1, self.btn_timer)
        )
        self.btn_notifications.clicked.connect(
            lambda: self._show_section(2, self.btn_notifications)
        )
        self.btn_layout.clicked.connect(
            lambda: self._show_section(3, self.btn_layout)
        )
        self.btn_language.clicked.connect(
            lambda: self._show_section(4, self.btn_language)
        )
        self.btn_profiles.clicked.connect(
            lambda: self._show_section(5, self.btn_profiles)
        )

    def _show_section(self, index, active_button):
        self.content_stack.setCurrentIndex(index)
        self._set_active_button(active_button)

    def _set_active_button(self, active_button):
        for button in self.setting_buttons:
            button.setProperty("active", button == active_button)
            button.style().unpolish(button)
            button.style().polish(button)

    def _update_toggle_text(self, button, checked, language, tr_func):
        button.setText(
            tr_func(language, "on")
            if checked else
            tr_func(language, "off")
        )

    def _set_toggle(self, btn, checked):
        if self._cur_tr:
            self._update_toggle_text(btn, checked, self._cur_lang, self._cur_tr)
        else:
            btn.setText("On" if checked else "Off")

    def update_language(self, language: str, tr_func):
        self._cur_lang = language
        self._cur_tr = tr_func

        self.title_label.setText(
            tr_func(language, "settings_title")
        )

        self.subtitle_label.setText(
            tr_func(language, "settings_subtitle")
        )

        self.save_btn.setText(
            tr_func(language, "save")
        )

        self.btn_general.setText(tr_func(language, "general"))
        self.btn_timer.setText(tr_func(language, "timers"))
        self.btn_notifications.setText(tr_func(language, "notifications"))
        self.btn_layout.setText(tr_func(language, "layout"))
        self.btn_language.setText(tr_func(language, "language"))
        _profiles_label = {"en": "Profiles", "de": "Profile", "ru": "Профили"}
        self.btn_profiles.setText(_profiles_label.get(language, "Profiles"))
        self.profiles_title.setText(_profiles_label.get(language, "Profiles"))
        self.profiles_path_title.setText(
            {"en": "Profile folder", "de": "Profilordner", "ru": "Папка профилей"}.get(language, "Profile folder")
        )
        self.profiles_change_btn.setText(
            {"en": "Change...", "de": "Ändern...", "ru": "Изменить..."}.get(language, "Change...")
        )
        self.profiles_open_btn.setText(
            {"en": "Open folder", "de": "Ordner öffnen", "ru": "Открыть папку"}.get(language, "Open folder")
        )

        # ===== GENERAL =====

        self.general_title.setText(
            tr_func(language, "general")
        )

        self.event_title.setText(
            tr_func(language, "event_tasks")
        )

        self.event_desc.setText(
            tr_func(language, "show_events_desc")
        )

        self.auto_save_title.setText(
            tr_func(language, "auto_save")
        )

        self.auto_save_desc.setText(
            tr_func(language, "auto_save_desc")
        )

        self.tray_title.setText(tr_func(language, "tray_setting"))
        self.tray_desc.setText(tr_func(language, "tray_setting_desc"))
        self._update_toggle_text(self.tray_minimize_btn, self.tray_minimize_btn.isChecked(), language, tr_func)

        self.dps_title.setText(tr_func(language, "dps_meter"))
        self.dps_desc.setText(tr_func(language, "dps_meter_desc"))
        self.dps_browse_btn.setText(tr_func(language, "dps_meter_browse"))
        self._update_toggle_text(self.dps_autostart_btn, self.dps_autostart_btn.isChecked(), language, tr_func)

        self.update_check_title.setText(tr_func(language, "check_updates"))
        self.update_check_desc.setText(tr_func(language, "check_updates_desc"))
        self.check_update_btn.setText(tr_func(language, "check_updates_btn"))

        # ===== RESET TIMER =====

        self.reset_timer_title.setText(
            tr_func(language, "reset_timer")
        )
        self._reset_help_btn.setToolTip(tr_func(language, "reset_timer_help"))

        self.daily_reset_label.setText(
            tr_func(language, "daily_reset")
        )

        self.weekly_reset_label.setText(
            tr_func(language, "weekly_reset")
        )

        # ===== ADVANCED TIMER =====

        self._update_toggle_text(
            self.shugo_enabled_btn,
            self.shugo_enabled_btn.isChecked(),
            language,
            tr_func
        )

        self._update_toggle_text(
            self.riss_enabled_btn,
            self.riss_enabled_btn.isChecked(),
            language,
            tr_func
        )

        self._update_toggle_text(
            self.notif_enabled_btn,
            self.notif_enabled_btn.isChecked(),
            language,
            tr_func
        )

        self.advanced_timer_title.setText(
            tr_func(language, "advanced_timer")
        )
        self._advanced_help_btn.setToolTip(tr_func(language, "advanced_timer_help"))

        self.custom_timer_title.setText(
            {"de": "Kategorien", "en": "Categories", "ru": "Категории"}.get(language, "Kategorien")
        )
        self._timer_section_lbl.setText(
            {"de": "Timer", "en": "Timer", "ru": "Таймеры"}.get(language, "Timer")
        )
        self._ct_help_btn.setToolTip(tr_func(language, "custom_timer_help"))

        self.notifications_title.setText(tr_func(language, "notifications"))

        self.shugo_title.setText(
            tr_func(language, "shugo_timer")
        )
        self.shugo_help_btn.setToolTip(tr_func(language, "shugo_help"))

        self.shugo_start_label.setText(
            tr_func(language, "start")
        )

        self.shugo_interval_label.setText(
            tr_func(language, "interval")
        )

        self.riss_title.setText(
            tr_func(language, "riss_timer")
        )
        self.riss_help_btn.setToolTip(tr_func(language, "riss_help"))

        self.riss_anchor_label.setText(
            tr_func(language, "anchor")
        )

        self.riss_interval_label.setText(
            tr_func(language, "interval")
        )

        self.notif_desc.setText(
            {"de": "Benachrichtigung vor Shugo & Riss Spawn", "ru": "Уведомление перед появлением Shugo и Riss"}.get(
                language, "Notification before Shugo & Rift spawn"
            )
        )
        self.notif_warn_label.setText(tr_func(language, "notif_warn_label"))
        self.notif_sound_title.setText(
            {"de": "Benachrichtigungston", "ru": "Звук уведомления"}.get(language, "Notification Sound")
        )
        self.notif_title.setText(tr_func(language, "win_notif_title"))
        self.notif_test_btn.setText(tr_func(language, "test_sound"))

        if hasattr(self, "notif_shugo_warn_label"):
            self.notif_shugo_warn_label.setText(tr_func(language, "notif_shugo_warn"))
        if hasattr(self, "notif_riss_warn_label"):
            self.notif_riss_warn_label.setText(tr_func(language, "notif_riss_warn"))

        if hasattr(self, "notif_sync_btn"):
            synced = self.notif_sync_btn.isChecked()
            key = "notif_sync" if synced else "notif_nosync"
            self.notif_sync_btn.setText(tr_func(language, key))

        self._update_toggle_text(
            self.notif_shugo_enabled_btn,
            self.notif_shugo_enabled_btn.isChecked(),
            language, tr_func
        )
        self._update_toggle_text(
            self.notif_riss_enabled_btn,
            self.notif_riss_enabled_btn.isChecked(),
            language, tr_func
        )

        # ===== WARN COMBOS =====
        m = tr_func(language, "min_abbr")
        if hasattr(self, "notif_warn_combo"):
            cur_warn = self.notif_warn_combo.currentData()
            self.notif_warn_combo.blockSignals(True)
            self.notif_warn_combo.clear()
            for v in [0, 1, 5, 10]:
                self.notif_warn_combo.addItem(f"{v} {m}", v)
            idx = self.notif_warn_combo.findData(cur_warn)
            self.notif_warn_combo.setCurrentIndex(max(0, idx))
            self.notif_warn_combo.blockSignals(False)

        if hasattr(self, "notif_shugo_warn_combo"):
            cur = self.notif_shugo_warn_combo.currentData()
            self.notif_shugo_warn_combo.blockSignals(True)
            self.notif_shugo_warn_combo.clear()
            for v in [0, 1, 3, 5]:
                self.notif_shugo_warn_combo.addItem(f"{v} {m}", v)
            idx = self.notif_shugo_warn_combo.findData(cur)
            self.notif_shugo_warn_combo.setCurrentIndex(max(0, idx))
            self.notif_shugo_warn_combo.blockSignals(False)

        if hasattr(self, "notif_riss_warn_combo"):
            cur = self.notif_riss_warn_combo.currentData()
            self.notif_riss_warn_combo.blockSignals(True)
            self.notif_riss_warn_combo.clear()
            for v in [0, 1, 5, 10]:
                self.notif_riss_warn_combo.addItem(f"{v} {m}", v)
            idx = self.notif_riss_warn_combo.findData(cur)
            self.notif_riss_warn_combo.setCurrentIndex(max(0, idx))
            self.notif_riss_warn_combo.blockSignals(False)

        # ===== INTERVAL COMBOS =====
        _shugo_keys = ["30min", "1h", "2h", "3h"]
        _riss_keys = ["1h", "2h", "3h"]

        if hasattr(self, "shugo_interval_combo"):
            cur = self.shugo_interval_combo.currentData()
            self.shugo_interval_combo.blockSignals(True)
            self.shugo_interval_combo.clear()
            for k in _shugo_keys:
                self.shugo_interval_combo.addItem(tr_func(language, f"timer_{k}"), k)
            idx = self.shugo_interval_combo.findData(cur)
            self.shugo_interval_combo.setCurrentIndex(max(0, idx))
            self.shugo_interval_combo.blockSignals(False)

        if hasattr(self, "riss_interval_combo"):
            cur = self.riss_interval_combo.currentData()
            self.riss_interval_combo.blockSignals(True)
            self.riss_interval_combo.clear()
            for k in _riss_keys:
                self.riss_interval_combo.addItem(tr_func(language, f"timer_{k}"), k)
            idx = self.riss_interval_combo.findData(cur)
            self.riss_interval_combo.setCurrentIndex(max(0, idx))
            self.riss_interval_combo.blockSignals(False)

        # ===== WEEKDAY BUTTONS =====
        if hasattr(self, "weekly_day_buttons") and hasattr(self, "_day_tr_keys"):
            for btn, tr_key in zip(self.weekly_day_buttons, self._day_tr_keys):
                btn.setText(tr_func(language, tr_key))

        # ===== NO-SOUND LABEL =====
        if hasattr(self, "notif_sound_combo") and self.notif_sound_combo.count() > 0:
            self.notif_sound_combo.setItemText(0, f"-- {tr_func(language, 'no_sound')} --")

        # ===== CUSTOM TIMER SOUNDS =====
        if hasattr(self, "_custom_sound_combos"):
            for i, combo in enumerate(self._custom_sound_combos):
                if combo.count() > 0:
                    combo.setItemText(0, f"-- {tr_func(language, 'no_sound')} --")

        # ===== LANGUAGE =====

        self.language_title.setText(
            tr_func(language, "language")
        )

        self.language_desc.setText(
            tr_func(language, "language_desc")
        )

        self.language_label.setText(
            tr_func(language, "application_language")
        )

        # ==== LAYOUT =====

        self.layout_title.setText(
            tr_func(language, "layout")
        )




        self._update_toggle_text(
            self.show_events_btn,
            self.show_events_btn.isChecked(),
            language,
            tr_func
        )

        self._update_toggle_text(
            self.auto_save_btn,
            self.auto_save_btn.isChecked(),
            language,
            tr_func
        )

    def _create_language_page(self):
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.language_title = QLabel()
        self.language_title.setObjectName("settingsSectionTitle")

        self.language_desc = QLabel()
        self.language_desc.setObjectName("settingsSectionDescription")
        self.language_desc.setWordWrap(True)

        self.language_combo = QComboBox()
        self.language_combo.setObjectName("settingsCombo")
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Deutsch", "de")
        self.language_combo.addItem("Русский", "ru")

        layout.addWidget(self.language_title)
        layout.addWidget(self.language_desc)
        language_row = QFrame()
        language_row.setObjectName("settingsRow")

        row_layout = QHBoxLayout(language_row)
        row_layout.setContentsMargins(14, 12, 14, 12)

        self.language_label = QLabel()
        self.language_label.setObjectName("settingsLabel")

        self.language_combo.setFixedWidth(180)

        row_layout.addWidget(self.language_label)
        row_layout.addStretch()
        row_layout.addWidget(self.language_combo)

        layout.addWidget(language_row)
        layout.addStretch()

        self.language_combo.currentIndexChanged.connect(
            self._emit_language_changed
        )

        return page

    def _emit_language_changed(self):
        language = self.language_combo.currentData()

        if language:
            self.language_changed.emit(language)

    def _create_layout_page(self):
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        self.layout_title = QLabel()
        self.layout_title.setObjectName("settingsSectionTitle")

        layout.addWidget(self.layout_title)

        self.theme_button_group = QButtonGroup(self)
        self.theme_button_group.setExclusive(True)

        theme_grid = QGridLayout()
        theme_grid.setSpacing(12)

        themes = [
            ("abyss", "Abyss"),
            ("inferno", "Inferno"),
            ("emerald", "Emerald"),
            ("frostbite", "Frostbite"),
            ("obsidian", "Obsidian"),
            ("void", "Void"),
        ]

        self.theme_buttons = {}

        for index, (theme_key, theme_name) in enumerate(themes):

            btn = QPushButton(theme_name)
            btn.setCheckable(True)
            btn.setObjectName("themeButton")
            btn.setMinimumHeight(70)

            logo_path = (
                self.project_root /
                f"assets/logos/logo_{theme_key}.png"
            )

            if logo_path.exists():
                btn.setIcon(QIcon(str(logo_path)))
                btn.setIconSize(QSize(48, 48))

            btn.clicked.connect(
                lambda checked=False, t=theme_key:
                self.theme_changed.emit(t)
            )

            self.theme_button_group.addButton(btn)
            self.theme_buttons[theme_key] = btn

            row = index // 2
            col = index % 2

            theme_grid.addWidget(btn, row, col)

        if "abyss" in self.theme_buttons:
            self.theme_buttons["abyss"].setChecked(True)

        layout.addLayout(theme_grid)
        layout.addStretch()

        return page
    
    def _emit_theme_changed(self):
        theme = self.theme_combo.currentData()

        if theme:
            self.theme_changed.emit(theme)

    def _create_timer_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 24)
        page_layout.setSpacing(0)

        self._timer_tab_widget = QTabWidget()
        self._timer_tab_widget.setObjectName("settingsTabWidget")
        page_layout.addWidget(self._timer_tab_widget, 1)

        # ━━━━━━━━━━━━━━━━━━━━━━ TAB 1: Standard ━━━━━━━━━━━━━━━━━━━━━━━━
        standard_tab = QWidget()
        layout = QVBoxLayout(standard_tab)
        layout.setContentsMargins(4, 20, 4, 8)
        layout.setSpacing(18)

        # ── Reset Timer ──────────────────────────────────────────────────
        self.reset_timer_title = QLabel()
        self.reset_timer_title.setObjectName("settingsSectionTitle")
        _reset_hdr = QHBoxLayout()
        _reset_hdr.addWidget(self.reset_timer_title)
        _reset_hdr.addStretch()
        self._reset_help_btn = QPushButton("?")
        self._reset_help_btn.setObjectName("helpButton")
        self._reset_help_btn.setFixedSize(22, 22)
        self._reset_help_btn.setToolTip(
            "Zeigt die verbleibende Zeit bis zum täglichen und wöchentlichen Server-Reset an."
        )
        _reset_hdr.addWidget(self._reset_help_btn)
        layout.addLayout(_reset_hdr)

        # Daily reset
        daily_row = QFrame()
        daily_row.setObjectName("settingsRow")
        daily_layout = QHBoxLayout(daily_row)
        daily_layout.setContentsMargins(14, 12, 14, 12)
        daily_layout.setSpacing(12)
        self.daily_reset_label = QLabel()
        self.daily_reset_label.setObjectName("settingsLabel")
        self.daily_reset_time = QTimeEdit()
        self.daily_reset_time.setObjectName("settingsTimeInput")
        self.daily_reset_time.setDisplayFormat("HH:mm")
        self.daily_reset_time.setTime(QTime(9, 0))
        self.daily_reset_time.setFixedWidth(130)
        daily_layout.addWidget(self.daily_reset_label)
        daily_layout.addStretch()
        daily_layout.addWidget(self.daily_reset_time)

        # Weekly reset
        weekly_row = QFrame()
        weekly_row.setObjectName("settingsRow")
        weekly_layout = QHBoxLayout(weekly_row)
        weekly_layout.setContentsMargins(14, 12, 14, 12)
        weekly_layout.setSpacing(12)
        self.weekly_reset_label = QLabel()
        self.weekly_reset_label.setObjectName("settingsLabel")
        self.weekly_day_group = QButtonGroup(self)
        day_widget = QWidget()
        day_layout = QHBoxLayout(day_widget)
        day_layout.setContentsMargins(0, 0, 0, 0)
        day_layout.setSpacing(4)
        self.weekly_day_buttons = []
        _day_keys = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        self._day_tr_keys = ["day_Mo", "day_Di", "day_Mi", "day_Do", "day_Fr", "day_Sa", "day_So"]
        for day_key in _day_keys:
            btn = QPushButton(day_key)
            btn.setProperty("day_key", day_key)
            btn.setCheckable(True)
            btn.setObjectName("dayButton")
            btn.setFixedSize(34, 28)
            if day_key == "Mo":
                btn.setChecked(True)
            self.weekly_day_group.addButton(btn)
            self.weekly_day_buttons.append(btn)
            day_layout.addWidget(btn)
        self.weekly_reset_time = QTimeEdit()
        self.weekly_reset_time.setObjectName("settingsTimeInput")
        self.weekly_reset_time.setDisplayFormat("HH:mm")
        self.weekly_reset_time.setTime(QTime(9, 0))
        self.weekly_reset_time.setFixedWidth(130)
        weekly_layout.addWidget(self.weekly_reset_label)
        weekly_layout.addStretch()
        weekly_layout.addWidget(day_widget)
        weekly_layout.addWidget(self.weekly_reset_time)

        layout.addWidget(daily_row)
        layout.addWidget(weekly_row)

        # ── Advanced Timer ───────────────────────────────────────────────
        self.advanced_timer_title = QLabel()
        self.advanced_timer_title.setObjectName("settingsSectionTitle")
        _adv_hdr = QHBoxLayout()
        _adv_hdr.addWidget(self.advanced_timer_title)
        _adv_hdr.addStretch()
        self._advanced_help_btn = QPushButton("?")
        self._advanced_help_btn.setObjectName("helpButton")
        self._advanced_help_btn.setFixedSize(22, 22)
        self._advanced_help_btn.setToolTip(
            "Konfigurierbare Timer für Shugo- und Riss-Spawn-Zeiten mit individuellem Intervall."
        )
        _adv_hdr.addWidget(self._advanced_help_btn)
        layout.addLayout(_adv_hdr)

        # Shugo row
        shugo_row = QFrame()
        shugo_row.setObjectName("settingsRow")
        shugo_layout = QHBoxLayout(shugo_row)
        shugo_layout.setContentsMargins(14, 12, 14, 12)
        shugo_layout.setSpacing(12)
        shugo_text = QHBoxLayout()
        shugo_text.setSpacing(6)
        self.shugo_title = QLabel()
        self.shugo_title.setObjectName("settingsLabel")
        self.shugo_help_btn = QPushButton("?")
        self.shugo_help_btn.setObjectName("helpButton")
        self.shugo_help_btn.setFixedSize(22, 22)
        shugo_text.addWidget(self.shugo_title)
        shugo_text.addWidget(self.shugo_help_btn)
        shugo_text.addStretch()
        self.shugo_enabled_btn = QPushButton("Off")
        self.shugo_enabled_btn.setCheckable(True)
        self.shugo_enabled_btn.setObjectName("toggleButton")
        self.shugo_enabled_btn.setFixedWidth(70)
        self.shugo_minute_combo = QComboBox()
        self.shugo_minute_combo.setObjectName("settingsCombo")
        self.shugo_minute_combo.addItems(["00", "15", "30", "45"])
        self.shugo_minute_combo.setFixedWidth(80)
        self.shugo_interval_combo = QComboBox()
        self.shugo_interval_combo.setObjectName("settingsCombo")
        self.shugo_interval_combo.addItem("30 min", "30min")
        self.shugo_interval_combo.addItem("1 Stunde", "1h")
        self.shugo_interval_combo.addItem("2 Stunden", "2h")
        self.shugo_interval_combo.addItem("3 Stunden", "3h")
        self.shugo_interval_combo.setFixedWidth(120)
        shugo_layout.addLayout(shugo_text, 1)
        self.shugo_start_label = QLabel()
        self.shugo_start_label.setObjectName("settingsInlineLabel")
        shugo_layout.addWidget(self.shugo_start_label)
        shugo_layout.addWidget(self.shugo_minute_combo)
        self.shugo_interval_label = QLabel()
        self.shugo_interval_label.setObjectName("settingsInlineLabel")
        shugo_layout.addWidget(self.shugo_interval_label)
        shugo_layout.addWidget(self.shugo_interval_combo)
        shugo_layout.addWidget(self.shugo_enabled_btn)

        # Riss row
        riss_row = QFrame()
        riss_row.setObjectName("settingsRow")
        riss_layout = QHBoxLayout(riss_row)
        riss_layout.setContentsMargins(14, 12, 14, 12)
        riss_layout.setSpacing(12)
        riss_text = QHBoxLayout()
        riss_text.setSpacing(6)
        self.riss_title = QLabel()
        self.riss_title.setObjectName("settingsLabel")
        self.riss_help_btn = QPushButton("?")
        self.riss_help_btn.setObjectName("helpButton")
        self.riss_help_btn.setFixedSize(22, 22)
        riss_text.addWidget(self.riss_title)
        riss_text.addWidget(self.riss_help_btn)
        riss_text.addStretch()
        self.riss_enabled_btn = QPushButton("Off")
        self.riss_enabled_btn.setCheckable(True)
        self.riss_enabled_btn.setObjectName("toggleButton")
        self.riss_enabled_btn.setFixedWidth(70)
        self.riss_anchor_combo = QComboBox()
        self.riss_anchor_combo.setObjectName("settingsCombo")
        self.riss_anchor_combo.addItems(["00", "01", "02"])
        self.riss_anchor_combo.setFixedWidth(80)
        self.riss_interval_combo = QComboBox()
        self.riss_interval_combo.setObjectName("settingsCombo")
        self.riss_interval_combo.addItem("1 Stunde", "1h")
        self.riss_interval_combo.addItem("2 Stunden", "2h")
        self.riss_interval_combo.addItem("3 Stunden", "3h")
        self.riss_interval_combo.setFixedWidth(120)
        riss_layout.addLayout(riss_text, 1)
        self.riss_anchor_label = QLabel()
        self.riss_anchor_label.setObjectName("settingsInlineLabel")
        riss_layout.addWidget(self.riss_anchor_label)
        riss_layout.addWidget(self.riss_anchor_combo)
        self.riss_interval_label = QLabel()
        self.riss_interval_label.setObjectName("settingsInlineLabel")
        riss_layout.addWidget(self.riss_interval_label)
        riss_layout.addWidget(self.riss_interval_combo)
        riss_layout.addWidget(self.riss_enabled_btn)

        layout.addWidget(shugo_row)
        layout.addWidget(riss_row)
        layout.addStretch()

        self._timer_tab_widget.addTab(standard_tab, "Standard")

        # ━━━━━━━━━━━━━━━━━━━━━━ TAB 2: Custom ━━━━━━━━━━━━━━━━━━━━━━━━━━
        custom_tab = QWidget()
        layout = QVBoxLayout(custom_tab)
        layout.setContentsMargins(4, 20, 4, 8)
        layout.setSpacing(12)

        # ── Kategorien Header ────────────────────────────────────────────
        cat_hdr = QHBoxLayout()
        self.custom_timer_title = QLabel("Kategorien")
        self.custom_timer_title.setObjectName("settingsSectionTitle")
        self._ct_help_btn = QPushButton("?")
        self._ct_help_btn.setObjectName("helpButton")
        self._ct_help_btn.setFixedSize(22, 22)
        self._ct_help_btn.setToolTip(
            "Erstelle bis zu 4 Gruppen, um Timer auf der Timer-Seite unter eigenen Überschriften anzuzeigen."
        )
        cat_hdr.addWidget(self.custom_timer_title)
        cat_hdr.addWidget(self._ct_help_btn)
        cat_hdr.addStretch()
        layout.addLayout(cat_hdr)

        # ── Kategorien-Verwaltung ────────────────────────────────────────
        self._cat_rows_container = QWidget()
        self._cat_rows_layout = QVBoxLayout(self._cat_rows_container)
        self._cat_rows_layout.setContentsMargins(0, 0, 0, 4)
        self._cat_rows_layout.setSpacing(4)
        layout.addWidget(self._cat_rows_container)
        self._rebuild_category_rows()

        # ── Timer Header ─────────────────────────────────────────────────
        timer_hdr = QHBoxLayout()
        self._timer_section_lbl = QLabel("Timer")
        self._timer_section_lbl.setObjectName("settingsSectionTitle")
        self._add_ct_btn = QPushButton("＋")
        self._add_ct_btn.setObjectName("secondaryButton")
        self._add_ct_btn.setFixedWidth(44)
        self._add_ct_btn.setFixedHeight(32)
        self._add_ct_btn.clicked.connect(self._add_custom_timer)
        timer_hdr.addWidget(self._timer_section_lbl)
        timer_hdr.addStretch()
        timer_hdr.addWidget(self._add_ct_btn)
        layout.addLayout(timer_hdr)

        # ── Timer Liste ──────────────────────────────────────────────────
        self._custom_ct_container = QWidget()
        self._custom_ct_layout = QVBoxLayout(self._custom_ct_container)
        self._custom_ct_layout.setContentsMargins(0, 0, 0, 0)
        self._custom_ct_layout.setSpacing(8)
        layout.addWidget(self._custom_ct_container)

        self._custom_rows = []
        layout.addStretch()

        self._timer_tab_widget.addTab(custom_tab, "Custom")

        # ── Signals ──────────────────────────────────────────────────────
        self.daily_reset_time.timeChanged.connect(self._emit_daily_reset_changed)
        for btn in self.weekly_day_buttons:
            btn.clicked.connect(self._emit_weekly_day_changed)
        self.weekly_reset_time.timeChanged.connect(self._emit_weekly_time_changed)

        self.shugo_enabled_btn.toggled.connect(
            lambda checked: self._set_toggle(self.shugo_enabled_btn, checked)
        )
        self.riss_enabled_btn.toggled.connect(
            lambda checked: self._set_toggle(self.riss_enabled_btn, checked)
        )

        return page
    
    def _emit_daily_reset_changed(self):
        value = self.daily_reset_time.time().toString("HH:mm")
        self.daily_reset_changed.emit(value)


    def _emit_weekly_day_changed(self):
        checked_button = self.weekly_day_group.checkedButton()
        if checked_button:
            self.weekly_reset_day_changed.emit(checked_button.property("day_key"))


    def _emit_weekly_time_changed(self):
        value = self.weekly_reset_time.time().toString("HH:mm")
        self.weekly_reset_time_changed.emit(value)

    def _emit_save_requested(self):
        data = {
            "language": self.language_combo.currentData(),
            "theme": self.get_selected_theme(),
            "daily_reset_time": self.daily_reset_time.time().toString("HH:mm"),
            "weekly_reset_day": self.weekly_day_group.checkedButton().property("day_key"),
            "weekly_reset_time": self.weekly_reset_time.time().toString("HH:mm"),
            "shugo_enabled": self.shugo_enabled_btn.isChecked(),
            "shugo_start_minute": int(self.shugo_minute_combo.currentText()),
            "shugo_interval_text": self.shugo_interval_combo.currentData(),

            "riss_enabled": self.riss_enabled_btn.isChecked(),
            "riss_anchor_hour": int(self.riss_anchor_combo.currentText()),
            "riss_interval_text": self.riss_interval_combo.currentData(),

            "show_events": self.show_events_btn.isChecked(),
            "auto_save": self.auto_save_btn.isChecked(),
            "minimize_to_tray": self.tray_minimize_btn.isChecked(),
            "dps_meter_path": self.dps_path_input.text().strip(),
            "dps_meter_autostart": self.dps_autostart_btn.isChecked(),

            "notification_enabled": self.notif_enabled_btn.isChecked(),
            "notification_warn_minutes": self.notif_warn_combo.currentData(),
            "notification_sync": self.notif_sync_btn.isChecked(),
            "notification_shugo_enabled": self.notif_shugo_enabled_btn.isChecked(),
            "notification_shugo_warn_minutes": self.notif_shugo_warn_combo.currentData(),
            "notification_riss_enabled": self.notif_riss_enabled_btn.isChecked(),
            "notification_riss_warn_minutes": self.notif_riss_warn_combo.currentData(),
            "notification_sound": self.notif_sound_combo.currentData() or "",

            "timer_categories": self._timer_categories,
            "custom_timers": [
                {
                    "enabled":          cfg.get("enabled", False),
                    "name":             cfg.get("name", ""),
                    "color":            cfg.get("color", "#22d3ee"),
                    "timer_mode":       cfg.get("timer_mode", "hourly"),
                    "reset_time":       cfg.get("reset_time", "09:00"),
                    "reset_day":        cfg.get("reset_day", "Mo"),
                    "interval_minutes": cfg.get("interval_minutes", 60),
                    "interval_seconds": cfg.get("interval_seconds", 3600),
                    "start_time":       cfg.get("start_time", "00:00"),
                    "category":         cfg.get("category", self._timer_categories[0] if self._timer_categories else "Custom Timer"),
                    "notification_sound": (
                        self._custom_sound_combos[i].currentData() or ""
                        if hasattr(self, "_custom_sound_combos") and i < len(self._custom_sound_combos)
                        else ""
                    ),
                }
                for i, cfg in enumerate(self._custom_timer_configs)
            ],
        }

        self.settings_save_requested.emit(data)



    def _create_notifications_page(self):
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        self.notifications_title = QLabel()
        self.notifications_title.setObjectName("settingsSectionTitle")
        layout.addWidget(self.notifications_title)

        # ===== NOTIFICATION ROW =====
        notif_row = QFrame()
        notif_row.setObjectName("settingsRow")

        notif_outer = QVBoxLayout(notif_row)
        notif_outer.setContentsMargins(14, 12, 14, 12)
        notif_outer.setSpacing(8)

        notif_header = QHBoxLayout()
        notif_header.setSpacing(12)

        notif_text = QVBoxLayout()
        notif_text.setSpacing(2)

        self.notif_title = QLabel()
        self.notif_title.setObjectName("settingsLabel")

        self.notif_desc = QLabel()
        self.notif_desc.setObjectName("settingsDescription")

        notif_text.addWidget(self.notif_title)
        notif_text.addWidget(self.notif_desc)

        self.notif_sync_btn = QPushButton("Synchron")
        self.notif_sync_btn.setCheckable(True)
        self.notif_sync_btn.setChecked(True)
        self.notif_sync_btn.setObjectName("toggleButton")
        self.notif_sync_btn.setFixedWidth(140)

        notif_header.addLayout(notif_text, 1)
        notif_header.addWidget(self.notif_sync_btn)
        notif_outer.addLayout(notif_header)

        # ── Synchronized sub-row ──────────────────────────────────────────
        self._notif_sync_row = QWidget()
        sync_row_layout = QHBoxLayout(self._notif_sync_row)
        sync_row_layout.setContentsMargins(0, 0, 0, 0)
        sync_row_layout.setSpacing(10)

        self.notif_warn_label = QLabel()
        self.notif_warn_label.setObjectName("settingsInlineLabel")

        self.notif_warn_combo = QComboBox()
        self.notif_warn_combo.setObjectName("settingsCombo")
        self.notif_warn_combo.setFixedWidth(100)
        self.notif_warn_combo.addItem("0 min", 0)
        self.notif_warn_combo.addItem("1 min", 1)
        self.notif_warn_combo.addItem("5 min", 5)
        self.notif_warn_combo.addItem("10 min", 10)
        self.notif_warn_combo.setCurrentIndex(1)

        self.notif_enabled_btn = QPushButton("Off")
        self.notif_enabled_btn.setCheckable(True)
        self.notif_enabled_btn.setObjectName("toggleButton")
        self.notif_enabled_btn.setFixedWidth(70)

        sync_row_layout.addStretch()
        sync_row_layout.addWidget(self.notif_warn_label)
        sync_row_layout.addWidget(self.notif_warn_combo)
        sync_row_layout.addWidget(self.notif_enabled_btn)

        notif_outer.addWidget(self._notif_sync_row)

        # ── Not-Synchronized sub-rows ─────────────────────────────────────
        self._notif_nosync_widget = QWidget()
        nosync_layout = QVBoxLayout(self._notif_nosync_widget)
        nosync_layout.setContentsMargins(0, 0, 0, 0)
        nosync_layout.setSpacing(4)

        # Shugo sub-row
        nosync_shugo = QHBoxLayout()
        nosync_shugo.setSpacing(10)
        self.notif_shugo_warn_label = QLabel()
        self.notif_shugo_warn_label.setObjectName("settingsInlineLabel")
        self.notif_shugo_warn_combo = QComboBox()
        self.notif_shugo_warn_combo.setObjectName("settingsCombo")
        self.notif_shugo_warn_combo.setFixedWidth(100)
        self.notif_shugo_warn_combo.addItem("0 min", 0)
        self.notif_shugo_warn_combo.addItem("1 min", 1)
        self.notif_shugo_warn_combo.addItem("3 min", 3)
        self.notif_shugo_warn_combo.addItem("5 min", 5)
        self.notif_shugo_warn_combo.setCurrentIndex(1)
        self.notif_shugo_enabled_btn = QPushButton("Off")
        self.notif_shugo_enabled_btn.setCheckable(True)
        self.notif_shugo_enabled_btn.setObjectName("toggleButton")
        self.notif_shugo_enabled_btn.setFixedWidth(70)
        nosync_shugo.addStretch()
        nosync_shugo.addWidget(self.notif_shugo_warn_label)
        nosync_shugo.addWidget(self.notif_shugo_warn_combo)
        nosync_shugo.addWidget(self.notif_shugo_enabled_btn)
        nosync_layout.addLayout(nosync_shugo)

        # Riss sub-row
        nosync_riss = QHBoxLayout()
        nosync_riss.setSpacing(10)
        self.notif_riss_warn_label = QLabel()
        self.notif_riss_warn_label.setObjectName("settingsInlineLabel")
        self.notif_riss_warn_combo = QComboBox()
        self.notif_riss_warn_combo.setObjectName("settingsCombo")
        self.notif_riss_warn_combo.setFixedWidth(100)
        self.notif_riss_warn_combo.addItem("0 min", 0)
        self.notif_riss_warn_combo.addItem("1 min", 1)
        self.notif_riss_warn_combo.addItem("5 min", 5)
        self.notif_riss_warn_combo.addItem("10 min", 10)
        self.notif_riss_warn_combo.setCurrentIndex(1)
        self.notif_riss_enabled_btn = QPushButton("Off")
        self.notif_riss_enabled_btn.setCheckable(True)
        self.notif_riss_enabled_btn.setObjectName("toggleButton")
        self.notif_riss_enabled_btn.setFixedWidth(70)
        nosync_riss.addStretch()
        nosync_riss.addWidget(self.notif_riss_warn_label)
        nosync_riss.addWidget(self.notif_riss_warn_combo)
        nosync_riss.addWidget(self.notif_riss_enabled_btn)
        nosync_layout.addLayout(nosync_riss)

        self._notif_nosync_widget.setVisible(False)
        notif_outer.addWidget(self._notif_nosync_widget)

        # ===== SOUND ROW =====
        sound_row = QFrame()
        sound_row.setObjectName("settingsRow")

        sound_layout = QHBoxLayout(sound_row)
        sound_layout.setContentsMargins(14, 12, 14, 12)
        sound_layout.setSpacing(12)

        sound_text = QVBoxLayout()
        sound_text.setSpacing(2)

        self.notif_sound_title = QLabel("Notification Sound")
        self.notif_sound_title.setObjectName("settingsLabel")

        sound_text.addWidget(self.notif_sound_title)

        self.notif_sound_combo = QComboBox()
        self.notif_sound_combo.setObjectName("settingsCombo")
        self.notif_sound_combo.setFixedWidth(260)
        self._populate_sound_combo()

        self.notif_test_btn = QPushButton("▶ Test")
        self.notif_test_btn.setObjectName("secondaryButton")
        self.notif_test_btn.setFixedWidth(70)
        self.notif_test_btn.clicked.connect(self._preview_sound)

        sound_layout.addLayout(sound_text, 1)
        sound_layout.addWidget(self.notif_sound_combo)
        sound_layout.addWidget(self.notif_test_btn)

        layout.addWidget(notif_row)
        layout.addWidget(sound_row)

        # ── Custom Timer Sounds ───────────────────────────────────────────
        self.custom_notif_section_title = QLabel("Custom Timer")
        self.custom_notif_section_title.setObjectName("settingsSectionTitle")
        self.custom_notif_section_title.setVisible(False)
        layout.addWidget(self.custom_notif_section_title)

        self._custom_notif_rows = []
        self._custom_notif_labels = []
        self._custom_sound_combos = []

        for i in range(8):
            ct_sound_row = QFrame()
            ct_sound_row.setObjectName("settingsRow")
            ct_sound_row.setVisible(False)
            ct_sound_layout = QHBoxLayout(ct_sound_row)
            ct_sound_layout.setContentsMargins(14, 12, 14, 12)
            ct_sound_layout.setSpacing(12)

            ct_name_lbl = QLabel(f"Timer {i + 1}")
            ct_name_lbl.setObjectName("settingsLabel")
            ct_name_lbl.setFixedWidth(100)

            ct_combo = QComboBox()
            ct_combo.setObjectName("settingsCombo")
            ct_combo.setFixedWidth(240)
            ct_combo.addItem("-- No Sound --", "")
            for path in sorted(glob.glob(r"C:\Windows\Media\*.wav")):
                name = os.path.splitext(os.path.basename(path))[0]
                ct_combo.addItem(name, path)

            ct_test_btn = QPushButton("▶ Test")
            ct_test_btn.setObjectName("secondaryButton")
            ct_test_btn.setFixedWidth(70)
            ct_test_btn.clicked.connect(
                lambda checked=False, combo=ct_combo: self._preview_custom_sound(combo)
            )

            ct_sound_layout.addWidget(ct_name_lbl)
            ct_sound_layout.addWidget(ct_combo, 1)
            ct_sound_layout.addWidget(ct_test_btn)

            layout.addWidget(ct_sound_row)
            self._custom_notif_rows.append(ct_sound_row)
            self._custom_notif_labels.append(ct_name_lbl)
            self._custom_sound_combos.append(ct_combo)

        layout.addStretch()

        self.notif_enabled_btn.toggled.connect(
            lambda checked: self._set_toggle(self.notif_enabled_btn, checked)
        )

        self.notif_shugo_enabled_btn.toggled.connect(
            lambda checked: self._set_toggle(self.notif_shugo_enabled_btn, checked)
        )

        self.notif_riss_enabled_btn.toggled.connect(
            lambda checked: self._set_toggle(self.notif_riss_enabled_btn, checked)
        )

        self.notif_sync_btn.toggled.connect(self._on_notif_sync_toggled)

        return page

    def _browse_dps_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "DPS Meter auswählen", "", "Anwendung (*.exe)"
        )
        if path:
            self.dps_path_input.setText(path)

    def _on_notif_sync_toggled(self, checked: bool):
        lang = self._cur_lang
        tr = self._cur_tr
        if checked:
            self.notif_sync_btn.setText(tr(lang, "notif_sync") if tr else "Synchron")
        else:
            self.notif_sync_btn.setText(tr(lang, "notif_nosync") if tr else "Nicht-Synchron")
        self._notif_sync_row.setVisible(checked)
        self._notif_nosync_widget.setVisible(not checked)

    def _populate_sound_combo(self):
        self.notif_sound_combo.clear()
        self.notif_sound_combo.addItem("-- No Sound --", "")
        for path in sorted(glob.glob(r"C:\Windows\Media\*.wav")):
            name = os.path.splitext(os.path.basename(path))[0]
            self.notif_sound_combo.addItem(name, path)

    def _preview_sound(self):
        path = self.notif_sound_combo.currentData() or ""
        if path and os.path.isfile(path):
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    
    def _create_general_page(self):
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        self.general_title = QLabel()
        self.general_title.setObjectName("settingsSectionTitle")

        layout.addWidget(self.general_title)

        event_row = QFrame()
        event_row.setObjectName("settingsRow")

        auto_save_row = QFrame()
        auto_save_row.setObjectName("settingsRow")

        auto_save_layout = QHBoxLayout(auto_save_row)
        auto_save_layout.setContentsMargins(14, 12, 14, 12)
        auto_save_layout.setSpacing(12)

        auto_save_text = QVBoxLayout()
        auto_save_text.setSpacing(2)

        self.auto_save_title = QLabel()
        self.auto_save_title.setObjectName("settingsLabel")

        self.auto_save_desc = QLabel()
        self.auto_save_desc.setObjectName("settingsDescription")

        auto_save_text.addWidget(self.auto_save_title)
        auto_save_text.addWidget(self.auto_save_desc)

        self.auto_save_btn = QPushButton("On")
        self.auto_save_btn.setCheckable(True)
        self.auto_save_btn.setChecked(True)
        self.auto_save_btn.setObjectName("toggleButton")
        self.auto_save_btn.setFixedWidth(70)

        self.auto_save_btn.toggled.connect(
            lambda checked: self._set_toggle(self.auto_save_btn, checked)
        )

        auto_save_layout.addLayout(auto_save_text, 1)
        auto_save_layout.addWidget(self.auto_save_btn)

        row_layout = QHBoxLayout(event_row)
        row_layout.setContentsMargins(14, 12, 14, 12)
        row_layout.setSpacing(12)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.event_title = QLabel()
        self.event_title.setObjectName("settingsLabel")

        self.event_desc = QLabel()
        self.event_desc.setObjectName("settingsDescription")


        text_layout.addWidget(self.event_title)
        text_layout.addWidget(self.event_desc)

        self.show_events_btn = QPushButton("On")
        self.show_events_btn.setCheckable(True)
        self.show_events_btn.setChecked(True)
        self.show_events_btn.setObjectName("toggleButton")
        self.show_events_btn.setFixedWidth(70)

        self.show_events_btn.toggled.connect(
            lambda checked: self._set_toggle(self.show_events_btn, checked)
        )

        row_layout.addLayout(text_layout, 1)
        row_layout.addWidget(self.show_events_btn)

        update_row = QFrame()
        update_row.setObjectName("settingsRow")
        update_layout = QHBoxLayout(update_row)
        update_layout.setContentsMargins(14, 12, 14, 12)
        update_layout.setSpacing(12)
        update_text = QVBoxLayout()
        update_text.setSpacing(2)
        self.update_check_title = QLabel()
        self.update_check_title.setObjectName("settingsLabel")
        self.update_check_desc = QLabel()
        self.update_check_desc.setObjectName("settingsDescription")
        update_text.addWidget(self.update_check_title)
        update_text.addWidget(self.update_check_desc)
        self.check_update_btn = QPushButton()
        self.check_update_btn.setObjectName("secondaryButton")
        self.check_update_btn.setFixedWidth(110)
        self.check_update_btn.clicked.connect(self.check_update_requested.emit)
        update_layout.addLayout(update_text, 1)
        update_layout.addWidget(self.check_update_btn)

        # ===== DPS METER ROW =====
        dps_row = QFrame()
        dps_row.setObjectName("settingsRow")
        dps_outer = QVBoxLayout(dps_row)
        dps_outer.setContentsMargins(14, 12, 14, 12)
        dps_outer.setSpacing(8)

        dps_header = QHBoxLayout()
        dps_header.setSpacing(12)
        dps_text = QVBoxLayout()
        dps_text.setSpacing(2)
        self.dps_title = QLabel()
        self.dps_title.setObjectName("settingsLabel")
        self.dps_desc = QLabel()
        self.dps_desc.setObjectName("settingsDescription")
        dps_text.addWidget(self.dps_title)
        dps_text.addWidget(self.dps_desc)
        self.dps_autostart_btn = QPushButton("Off")
        self.dps_autostart_btn.setCheckable(True)
        self.dps_autostart_btn.setObjectName("toggleButton")
        self.dps_autostart_btn.setFixedWidth(110)
        self.dps_autostart_btn.toggled.connect(
            lambda checked: self._set_toggle(self.dps_autostart_btn, checked)
        )
        dps_header.addLayout(dps_text, 1)
        dps_header.addWidget(self.dps_autostart_btn)
        dps_outer.addLayout(dps_header)

        dps_path_row = QHBoxLayout()
        dps_path_row.setSpacing(8)
        self.dps_path_input = QLineEdit()
        self.dps_path_input.setObjectName("settingsLineEditReadOnly")
        self.dps_path_input.setPlaceholderText("C:\\...\\dps_meter.exe")
        self.dps_path_input.setReadOnly(True)
        self.dps_browse_btn = QPushButton()
        self.dps_browse_btn.setObjectName("secondaryButton")
        self.dps_browse_btn.setFixedWidth(100)
        self.dps_browse_btn.clicked.connect(self._browse_dps_exe)
        self.dps_start_btn = QPushButton("▶ Start")
        self.dps_start_btn.setObjectName("secondaryButton")
        self.dps_start_btn.setFixedWidth(80)
        self.dps_start_btn.clicked.connect(
            lambda: self.dps_start_requested.emit(self.dps_path_input.text().strip())
        )
        dps_path_row.addWidget(self.dps_path_input, 1)
        dps_path_row.addWidget(self.dps_browse_btn)
        dps_path_row.addWidget(self.dps_start_btn)
        dps_outer.addLayout(dps_path_row)

        # ===== TRAY ROW =====
        tray_row = QFrame()
        tray_row.setObjectName("settingsRow")
        tray_layout = QHBoxLayout(tray_row)
        tray_layout.setContentsMargins(14, 12, 14, 12)
        tray_layout.setSpacing(12)
        tray_text = QVBoxLayout()
        tray_text.setSpacing(2)
        self.tray_title = QLabel()
        self.tray_title.setObjectName("settingsLabel")
        self.tray_desc = QLabel()
        self.tray_desc.setObjectName("settingsDescription")
        tray_text.addWidget(self.tray_title)
        tray_text.addWidget(self.tray_desc)
        self.tray_minimize_btn = QPushButton("Off")
        self.tray_minimize_btn.setCheckable(True)
        self.tray_minimize_btn.setChecked(False)
        self.tray_minimize_btn.setObjectName("toggleButton")
        self.tray_minimize_btn.setFixedWidth(70)
        self.tray_minimize_btn.toggled.connect(
            lambda checked: self._set_toggle(self.tray_minimize_btn, checked)
        )
        tray_layout.addLayout(tray_text, 1)
        tray_layout.addWidget(self.tray_minimize_btn)

        layout.addWidget(event_row)
        layout.addWidget(auto_save_row)
        layout.addWidget(tray_row)
        layout.addWidget(dps_row)
        layout.addWidget(update_row)
        layout.addStretch()

        return page

    def set_values(self, data: dict):
        # Allgemein
        if hasattr(self, "show_events_btn"):
            show_events = data.get("show_events", True)
            self.show_events_btn.setChecked(show_events)
            self._set_toggle(self.show_events_btn, show_events)

        if hasattr(self, "dps_path_input"):
            self.dps_path_input.setText(data.get("dps_meter_path", ""))

        if hasattr(self, "dps_autostart_btn"):
            v = data.get("dps_meter_autostart", False)
            self.dps_autostart_btn.setChecked(v)
            self._set_toggle(self.dps_autostart_btn, v)

        if hasattr(self, "tray_minimize_btn"):
            v = bool(data.get("minimize_to_tray", False))
            self.tray_minimize_btn.setChecked(v)
            self._set_toggle(self.tray_minimize_btn, v)

        # Language
        if hasattr(self, "language_combo"):
            language = data.get("language", "en")
            index = self.language_combo.findData(language)
            if index >= 0:
                self.language_combo.setCurrentIndex(index)

        # Theme Buttons
        if hasattr(self, "theme_buttons"):
            theme = data.get("theme", "abyss")
            if theme in self.theme_buttons:
                self.theme_buttons[theme].setChecked(True)

        # Reset Timer
        if hasattr(self, "daily_reset_time"):
            h, m = map(int, data.get("daily_reset_time", "09:00").split(":"))
            self.daily_reset_time.setTime(QTime(h, m))

        if hasattr(self, "weekly_day_buttons"):
            weekly_day = data.get("weekly_reset_day", "Mo")
            for btn in self.weekly_day_buttons:
                btn.setChecked(btn.property("day_key") == weekly_day)

        if hasattr(self, "weekly_reset_time"):
            h, m = map(int, data.get("weekly_reset_time", "09:00").split(":"))
            self.weekly_reset_time.setTime(QTime(h, m))

        # Advanced Timer
        if hasattr(self, "shugo_enabled_btn"):
            enabled = data.get("shugo_enabled", False)
            self.shugo_enabled_btn.setChecked(enabled)
            self._set_toggle(self.shugo_enabled_btn, enabled)

        if hasattr(self, "shugo_minute_combo"):
            value = str(data.get("shugo_start_minute", 15)).zfill(2)
            index = self.shugo_minute_combo.findText(value)
            if index >= 0:
                self.shugo_minute_combo.setCurrentIndex(index)

        if hasattr(self, "shugo_interval_combo"):
            value = data.get("shugo_interval_text", "30min")
            _compat = {"30 min": "30min", "1 Stunde": "1h", "2 Stunden": "2h", "3 Stunden": "3h"}
            key = _compat.get(value, value)
            index = self.shugo_interval_combo.findData(key)
            if index >= 0:
                self.shugo_interval_combo.setCurrentIndex(index)

        if hasattr(self, "riss_enabled_btn"):
            enabled = data.get("riss_enabled", False)
            self.riss_enabled_btn.setChecked(enabled)
            self._set_toggle(self.riss_enabled_btn, enabled)

        if hasattr(self, "riss_anchor_combo"):
            value = str(data.get("riss_anchor_hour", 0)).zfill(2)
            index = self.riss_anchor_combo.findText(value)
            if index >= 0:
                self.riss_anchor_combo.setCurrentIndex(index)

        if hasattr(self, "riss_interval_combo"):
            value = data.get("riss_interval_text", "1h")
            _compat = {"1 Stunde": "1h", "2 Stunden": "2h", "3 Stunden": "3h"}
            key = _compat.get(value, value)
            index = self.riss_interval_combo.findData(key)
            if index >= 0:
                self.riss_interval_combo.setCurrentIndex(index)

        if hasattr(self, "auto_save_btn"):
            auto_save = data.get("auto_save", True)
            self.auto_save_btn.setChecked(auto_save)
            self._set_toggle(self.auto_save_btn, auto_save)

        if hasattr(self, "notif_enabled_btn"):
            enabled = data.get("notification_enabled", False)
            self.notif_enabled_btn.setChecked(enabled)
            self._set_toggle(self.notif_enabled_btn, enabled)

        if hasattr(self, "notif_warn_combo"):
            warn = data.get("notification_warn_minutes", 1)
            idx = self.notif_warn_combo.findData(warn)
            if idx >= 0:
                self.notif_warn_combo.setCurrentIndex(idx)

        if hasattr(self, "notif_sync_btn"):
            synced = data.get("notification_sync", True)
            self.notif_sync_btn.blockSignals(True)
            self.notif_sync_btn.setChecked(synced)
            self.notif_sync_btn.blockSignals(False)
            lang = self._cur_lang
            tr = self._cur_tr
            key = "notif_sync" if synced else "notif_nosync"
            self.notif_sync_btn.setText(tr(lang, key) if tr else ("Synchron" if synced else "Nicht-Synchron"))
            self._notif_sync_row.setVisible(synced)
            self._notif_nosync_widget.setVisible(not synced)

        if hasattr(self, "notif_shugo_enabled_btn"):
            v = data.get("notification_shugo_enabled", False)
            self.notif_shugo_enabled_btn.setChecked(v)
            self._set_toggle(self.notif_shugo_enabled_btn, v)

        if hasattr(self, "notif_shugo_warn_combo"):
            w = data.get("notification_shugo_warn_minutes", 1)
            idx = self.notif_shugo_warn_combo.findData(w)
            if idx >= 0:
                self.notif_shugo_warn_combo.setCurrentIndex(idx)

        if hasattr(self, "notif_riss_enabled_btn"):
            v = data.get("notification_riss_enabled", False)
            self.notif_riss_enabled_btn.setChecked(v)
            self._set_toggle(self.notif_riss_enabled_btn, v)

        if hasattr(self, "notif_riss_warn_combo"):
            w = data.get("notification_riss_warn_minutes", 1)
            idx = self.notif_riss_warn_combo.findData(w)
            if idx >= 0:
                self.notif_riss_warn_combo.setCurrentIndex(idx)

        if hasattr(self, "notif_sound_combo"):
            sound_path = data.get("notification_sound", "")
            index = self.notif_sound_combo.findData(sound_path)
            if index >= 0:
                self.notif_sound_combo.setCurrentIndex(index)

        if hasattr(self, "profiles_path_label"):
            self.profiles_path_label.setText(data.get("profile_dir", ""))

        if "timer_categories" in data:
            cats = data["timer_categories"]
            if isinstance(cats, list) and cats:
                self._timer_categories = [str(c) for c in cats]
            else:
                self._timer_categories = ["Custom Timer"]

        if "custom_timers" in data:
            self._custom_timer_configs = []
            for ct in data["custom_timers"][:8]:
                cfg = {
                    "enabled":          ct.get("enabled", False),
                    "name":             ct.get("name", ""),
                    "color":            ct.get("color", "#22d3ee"),
                    "timer_mode":       ct.get("timer_mode", "hourly"),
                    "reset_time":       ct.get("reset_time", "09:00"),
                    "reset_day":        ct.get("reset_day", "Mo"),
                    "interval_minutes": ct.get("interval_minutes", 60),
                    "interval_seconds": ct.get("interval_seconds", 3600),
                    "start_time":       ct.get("start_time", "00:00"),
                    "category":         ct.get("category", self._timer_categories[0] if self._timer_categories else "Custom Timer"),
                    "notification_sound": ct.get("notification_sound", ""),
                }
                self._custom_timer_configs.append(cfg)
            if hasattr(self, "_custom_ct_layout"):
                self._rebuild_custom_timer_rows()
            if hasattr(self, "_cat_rows_layout"):
                self._rebuild_category_rows()
            for i, ct in enumerate(self._custom_timer_configs):
                if hasattr(self, "_custom_sound_combos") and i < len(self._custom_sound_combos):
                    sound = ct.get("notification_sound", "")
                    idx = self._custom_sound_combos[i].findData(sound)
                    if idx >= 0:
                        self._custom_sound_combos[i].setCurrentIndex(idx)

    def get_selected_theme(self):
        if not hasattr(self, "theme_buttons"):
            return "abyss"

        for theme_key, button in self.theme_buttons.items():
            if button.isChecked():
                return theme_key

        return "abyss"

    def _create_profiles_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        self.profiles_title = QLabel("Profiles")
        self.profiles_title.setObjectName("settingsSectionTitle")
        layout.addWidget(self.profiles_title)

        # ===== CURRENT PATH ROW =====
        path_row = QFrame()
        path_row.setObjectName("settingsRow")
        path_layout = QVBoxLayout(path_row)
        path_layout.setContentsMargins(14, 14, 14, 14)
        path_layout.setSpacing(8)

        self.profiles_path_title = QLabel("Profilordner")
        self.profiles_path_title.setObjectName("settingsLabel")

        self.profiles_path_label = QLineEdit()
        self.profiles_path_label.setObjectName("settingsPathLabel")
        self.profiles_path_label.setReadOnly(True)
        self.profiles_path_label.setMinimumHeight(34)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.profiles_change_btn = QPushButton()
        self.profiles_change_btn.setObjectName("secondaryButton")
        self.profiles_change_btn.setFixedHeight(36)
        self.profiles_change_btn.clicked.connect(self._pick_profile_dir)

        self.profiles_open_btn = QPushButton()
        self.profiles_open_btn.setObjectName("secondaryButton")
        self.profiles_open_btn.setFixedHeight(36)
        self.profiles_open_btn.clicked.connect(self._open_profile_dir)

        btn_row.addWidget(self.profiles_change_btn)
        btn_row.addWidget(self.profiles_open_btn)
        btn_row.addStretch()

        path_layout.addWidget(self.profiles_path_title)
        path_layout.addWidget(self.profiles_path_label)
        path_layout.addLayout(btn_row)

        layout.addWidget(path_row)
        layout.addStretch()

        return page

    def _pick_profile_dir(self):
        current = self.profiles_path_label.text()
        new_path = QFileDialog.getExistingDirectory(
            self, "Profilordner wählen", current
        )
        if new_path:
            self.profiles_path_label.setText(new_path)
            self.profile_dir_changed.emit(new_path)

    def _open_profile_dir(self):
        path = self.profiles_path_label.text()
        if path and os.path.isdir(path):
            subprocess.Popen(f'explorer "{path}"')

    def _rebuild_category_rows(self):
        while self._cat_rows_layout.count():
            item = self._cat_rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for cat in self._timer_categories:
            self._cat_rows_layout.addWidget(self._build_category_row(cat))
        if len(self._timer_categories) < 4:
            add_btn = QPushButton("＋ Kategorie hinzufügen")
            add_btn.setObjectName("secondaryButton")
            add_btn.clicked.connect(self._add_category)
            self._cat_rows_layout.addWidget(add_btn)

    def _build_category_row(self, cat_name: str) -> QFrame:
        row = QFrame()
        row.setObjectName("settingsRow")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 6, 14, 6)
        rl.setSpacing(8)
        dot = QLabel("●")
        dot.setFixedWidth(16)
        dot.setStyleSheet("color: #22d3ee; font-size: 14px;")
        name_lbl = QLabel(cat_name)
        name_lbl.setObjectName("settingsLabel")
        rename_btn = QPushButton("Umbenennen")
        rename_btn.setObjectName("secondaryButton")
        rename_btn.setFixedWidth(110)
        rename_btn.clicked.connect(lambda checked=False, cn=cat_name: self._rename_category(cn))
        rl.addWidget(dot)
        rl.addWidget(name_lbl, 1)
        rl.addWidget(rename_btn)
        has_timers = any(
            cfg.get("category", self._timer_categories[0]) == cat_name
            for cfg in self._custom_timer_configs
        )
        if len(self._timer_categories) > 1 and not has_timers:
            del_btn = QPushButton("✕")
            del_btn.setObjectName("secondaryButton")
            del_btn.setFixedWidth(36)
            del_btn.clicked.connect(lambda checked=False, cn=cat_name: self._remove_category(cn))
            rl.addWidget(del_btn)
        return row

    def _add_category(self):
        if len(self._timer_categories) >= 4:
            return
        name, ok = QInputDialog.getText(self, "Kategorie hinzufügen", "Name:")
        if ok and name.strip():
            name = name.strip()[:20]
            if name not in self._timer_categories:
                self._timer_categories.append(name)
                self._rebuild_category_rows()

    def _remove_category(self, cat_name: str):
        if cat_name in self._timer_categories and len(self._timer_categories) > 1:
            self._timer_categories.remove(cat_name)
            self._rebuild_category_rows()

    def _rename_category(self, old_name: str):
        new_name, ok = QInputDialog.getText(
            self, "Kategorie umbenennen", "Neuer Name:", text=old_name
        )
        if ok and new_name.strip():
            new_name = new_name.strip()[:20]
            if new_name != old_name and new_name not in self._timer_categories:
                idx = self._timer_categories.index(old_name)
                self._timer_categories[idx] = new_name
                for cfg in self._custom_timer_configs:
                    if cfg.get("category", "") == old_name:
                        cfg["category"] = new_name
                self._rebuild_category_rows()
                self._rebuild_custom_timer_rows()

    def _add_custom_timer(self):
        if len(self._custom_timer_configs) >= 8:
            return
        dlg = CustomTimerDialog(
            categories=self._timer_categories,
            category=self._timer_categories[0],
            parent=self,
        )
        if dlg.exec():
            values = dlg.get_values()
            self._custom_timer_configs.append({
                "enabled": False,
                "notification_sound": "",
                **values,
            })
            self._rebuild_custom_timer_rows()
            self._rebuild_category_rows()

    def _edit_custom_timer(self, idx: int):
        if idx >= len(self._custom_timer_configs):
            return
        cfg = self._custom_timer_configs[idx]
        dlg = CustomTimerDialog(
            name=cfg.get("name", ""),
            color=cfg.get("color", "#22d3ee"),
            timer_mode=cfg.get("timer_mode", "hourly"),
            reset_time=cfg.get("reset_time", "09:00"),
            reset_day=cfg.get("reset_day", "Mo"),
            interval_minutes=cfg.get("interval_minutes", 60),
            interval_seconds=cfg.get("interval_seconds", 3600),
            start_time=cfg.get("start_time", ""),
            categories=self._timer_categories,
            category=cfg.get("category", self._timer_categories[0]),
            parent=self,
        )
        if dlg.exec():
            values = dlg.get_values()
            for field in ("name", "color", "timer_mode", "reset_time",
                          "reset_day", "interval_minutes", "interval_seconds",
                          "start_time", "category"):
                if field in values:
                    cfg[field] = values[field]
                else:
                    cfg.pop(field, None)
            self._rebuild_custom_timer_rows()
            self._rebuild_category_rows()

    def _remove_custom_timer(self, idx: int):
        if idx < len(self._custom_timer_configs):
            del self._custom_timer_configs[idx]
            self._rebuild_custom_timer_rows()
            self._rebuild_category_rows()

    def _rebuild_custom_timer_rows(self):
        while self._custom_ct_layout.count():
            item = self._custom_ct_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._custom_rows = []

        for i, cfg in enumerate(self._custom_timer_configs):
            row = self._build_custom_timer_row(i, cfg)
            self._custom_ct_layout.addWidget(row)

        self._add_ct_btn.setVisible(len(self._custom_timer_configs) < 8)
        self._update_custom_notif_visibility()

    def _build_custom_timer_row(self, idx: int, cfg: dict) -> QFrame:
        row = QFrame()
        row.setObjectName("settingsRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(14, 12, 14, 12)
        row_layout.setSpacing(10)

        color_dot = QLabel("●")
        color_dot.setFixedWidth(18)
        color_dot.setStyleSheet(f"color: {cfg['color']}; font-size: 18px;")

        name_lbl = QLabel(cfg["name"])
        name_lbl.setObjectName("settingsLabel")

        interval_lbl = QLabel(self._format_timer_summary(cfg))
        interval_lbl.setObjectName("settingsDescription")

        default_cat = self._timer_categories[0] if self._timer_categories else "Custom Timer"
        cat_lbl = QLabel(f"[{cfg.get('category', default_cat)}]")
        cat_lbl.setObjectName("settingsDescription")

        edit_btn = QPushButton("Bearbeiten")
        edit_btn.setObjectName("secondaryButton")
        edit_btn.setFixedWidth(110)
        edit_btn.clicked.connect(lambda checked=False, i=idx: self._edit_custom_timer(i))

        remove_btn = QPushButton("✕")
        remove_btn.setObjectName("secondaryButton")
        remove_btn.setFixedWidth(36)
        remove_btn.clicked.connect(lambda checked=False, i=idx: self._remove_custom_timer(i))

        toggle_btn = QPushButton()
        toggle_btn.setCheckable(True)
        toggle_btn.setChecked(cfg.get("enabled", False))
        toggle_btn.setObjectName("toggleButton")
        toggle_btn.setFixedWidth(70)
        self._set_toggle(toggle_btn, cfg.get("enabled", False))
        toggle_btn.toggled.connect(
            lambda checked, i=idx, btn=toggle_btn: self._on_custom_timer_toggled(i, checked, btn)
        )

        row_layout.addWidget(color_dot)
        row_layout.addWidget(name_lbl)
        row_layout.addWidget(interval_lbl)
        row_layout.addWidget(cat_lbl)
        row_layout.addStretch()
        row_layout.addWidget(edit_btn)
        row_layout.addWidget(remove_btn)
        row_layout.addWidget(toggle_btn)

        self._custom_rows.append((toggle_btn, color_dot, name_lbl))
        return row

    def _on_custom_timer_toggled(self, idx: int, checked: bool, btn=None):
        if idx < len(self._custom_timer_configs):
            self._custom_timer_configs[idx]["enabled"] = checked
        if btn:
            self._set_toggle(btn, checked)

    def _update_custom_notif_visibility(self):
        count = len(self._custom_timer_configs)
        has_any = count > 0
        if hasattr(self, "custom_notif_section_title"):
            self.custom_notif_section_title.setVisible(has_any)
        rows = getattr(self, "_custom_notif_rows", [])
        for i in range(len(rows)):
            rows[i].setVisible(i < count)
            if i < count:
                self._custom_notif_labels[i].setText(self._custom_timer_configs[i]["name"])

    @staticmethod
    def _format_timer_summary(cfg: dict) -> str:
        mode = cfg.get("timer_mode", "hourly")
        if mode == "daily":
            return f"Täglich {cfg.get('reset_time', '09:00')}"
        if mode == "weekly":
            day = cfg.get("reset_day", "Mo")
            t = cfg.get("reset_time", "09:00")
            return f"Wöchentlich {day} {t}"
        if mode == "hourly":
            mins = cfg.get("interval_minutes", 60)
            h, m = divmod(mins, 60)
            if m == 0:
                return f"Alle {h}h"
            return f"Alle {h}h {m}min"
        # custom
        secs = cfg.get("interval_seconds", 3600)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02}:{m:02}:{s:02}"

    def _preview_custom_sound(self, combo):
        path = combo.currentData() or ""
        if path and os.path.isfile(path):
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)

    def update_profile_dir_label(self, path: str):
        if hasattr(self, "profiles_path_label"):
            self.profiles_path_label.setText(path)