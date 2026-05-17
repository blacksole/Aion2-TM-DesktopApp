from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtCore import Signal, QTime, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QStackedWidget, QComboBox, QTimeEdit,QButtonGroup, QGridLayout
)



class SettingsPage(QWidget):
    language_changed = Signal(str)
    theme_changed = Signal(str)
    daily_reset_changed = Signal(str)
    weekly_reset_day_changed = Signal(str)
    weekly_reset_time_changed = Signal(str)
    settings_save_requested = Signal(dict)

    def __init__(self):
        super().__init__()

        self.project_root = Path(__file__).resolve().parent.parent.parent

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
        self.btn_reset_timer = QPushButton()
        self.btn_advanced_timer = QPushButton()
        self.btn_layout = QPushButton()
        self.btn_language = QPushButton()

        self.setting_buttons = [
            self.btn_general,
            self.btn_reset_timer,
            self.btn_advanced_timer,
            self.btn_layout,
            self.btn_language,
        ]

        for button in self.setting_buttons:
            button.setObjectName("settingsNavButton")
            button.setMinimumHeight(44)
            sidebar_layout.addWidget(button)

        sidebar_layout.addStretch()

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("settingsContentStack")

        self.general_page = self._create_general_page()

        self.reset_timer_page = self._create_reset_timer_page()

        self.advanced_timer_page = self._create_advanced_timer_page()

        self.layout_page = self._create_layout_page()

        self.language_page = self._create_language_page()

        self.content_stack.addWidget(self.general_page)
        self.content_stack.addWidget(self.reset_timer_page)
        self.content_stack.addWidget(self.advanced_timer_page)
        self.content_stack.addWidget(self.layout_page)
        self.content_stack.addWidget(self.language_page)

        body_layout.addWidget(self.settings_sidebar)
        body_layout.addWidget(self.content_stack, 1)

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
        self.btn_reset_timer.clicked.connect(
            lambda: self._show_section(1, self.btn_reset_timer)
        )
        self.btn_advanced_timer.clicked.connect(
            lambda: self._show_section(2, self.btn_advanced_timer)
        )
        self.btn_layout.clicked.connect(
            lambda: self._show_section(3, self.btn_layout)
        )
        self.btn_language.clicked.connect(
            lambda: self._show_section(4, self.btn_language)
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

    def update_language(self, language: str, tr_func):
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
        self.btn_reset_timer.setText(tr_func(language, "reset_timer"))
        self.btn_advanced_timer.setText(tr_func(language, "advanced_timer"))
        self.btn_layout.setText(tr_func(language, "layout"))
        self.btn_language.setText(tr_func(language, "language"))

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

        # ===== RESET TIMER =====

        self.reset_timer_title.setText(
            tr_func(language, "reset_timer")
        )

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

        self.advanced_timer_title.setText(
            tr_func(language, "advanced_timer")
        )

        self.shugo_title.setText(
            tr_func(language, "shugo_timer")
        )

        self.shugo_desc.setText(
            tr_func(language, "shugo_timer_desc")
        )

        self.shugo_start_label.setText(
            tr_func(language, "start")
        )

        self.shugo_interval_label.setText(
            tr_func(language, "interval")
        )

        self.riss_title.setText(
            tr_func(language, "riss_timer")
        )

        self.riss_desc.setText(
            tr_func(language, "riss_timer_desc")
        )

        self.riss_anchor_label.setText(
            tr_func(language, "anchor")
        )

        self.riss_interval_label.setText(
            tr_func(language, "interval")
        )

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

    def _create_reset_timer_page(self):
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        self.reset_timer_title = QLabel()
        self.reset_timer_title.setObjectName("settingsSectionTitle")

        layout.addWidget(self.reset_timer_title)

        # ===== DAILY RESET ROW =====
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

        # ===== WEEKLY RESET ROW =====
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

        for day in ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]:
            btn = QPushButton(day)
            btn.setCheckable(True)
            btn.setObjectName("dayButton")
            btn.setFixedSize(34, 28)

            if day == "Mo":
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
        layout.addStretch()

        self.daily_reset_time.timeChanged.connect(
            self._emit_daily_reset_changed
        )

        for btn in self.weekly_day_buttons:
            btn.clicked.connect(self._emit_weekly_day_changed)

        self.weekly_reset_time.timeChanged.connect(
            self._emit_weekly_time_changed
        )

        return page
    
    def _emit_daily_reset_changed(self):
        value = self.daily_reset_time.time().toString("HH:mm")
        self.daily_reset_changed.emit(value)


    def _emit_weekly_day_changed(self):
        checked_button = self.weekly_day_group.checkedButton()
        if checked_button:
            self.weekly_reset_day_changed.emit(checked_button.text())


    def _emit_weekly_time_changed(self):
        value = self.weekly_reset_time.time().toString("HH:mm")
        self.weekly_reset_time_changed.emit(value)

    def _emit_save_requested(self):
        data = {
            "language": self.language_combo.currentData(),
            "theme": self.get_selected_theme(),
            "daily_reset_time": self.daily_reset_time.time().toString("HH:mm"),
            "weekly_reset_day": self.weekly_day_group.checkedButton().text(),
            "weekly_reset_time": self.weekly_reset_time.time().toString("HH:mm"),
            "shugo_enabled": self.shugo_enabled_btn.isChecked(),
            "shugo_start_minute": int(self.shugo_minute_combo.currentText()),
            "shugo_interval_text": self.shugo_interval_combo.currentText(),

            "riss_enabled": self.riss_enabled_btn.isChecked(),
            "riss_anchor_hour": int(self.riss_anchor_combo.currentText()),
            "riss_interval_text": self.riss_interval_combo.currentText(),

            "show_events": self.show_events_btn.isChecked(),
            "auto_save": self.auto_save_btn.isChecked(),
        }

        self.settings_save_requested.emit(data)

    def _create_advanced_timer_page(self):
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        self.advanced_timer_title = QLabel()
        self.advanced_timer_title.setObjectName("settingsSectionTitle")
        layout.addWidget(self.advanced_timer_title)

        # ===== SHUGO ROW =====
        shugo_row = QFrame()
        shugo_row.setObjectName("settingsRow")

        shugo_layout = QHBoxLayout(shugo_row)
        shugo_layout.setContentsMargins(14, 12, 14, 12)
        shugo_layout.setSpacing(12)

        shugo_text = QVBoxLayout()
        shugo_text.setSpacing(2)

        self.shugo_title = QLabel()
        self.shugo_title.setObjectName("settingsLabel")

        self.shugo_desc = QLabel()
        self.shugo_desc.setObjectName("settingsDescription")

        shugo_text.addWidget(self.shugo_title)
        shugo_text.addWidget(self.shugo_desc)

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
        self.shugo_interval_combo.addItems([
            "30 min", "1 Stunde", "2 Stunden", "3 Stunden"
        ])
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

        # ===== RISS ROW =====
        riss_row = QFrame()
        riss_row.setObjectName("settingsRow")

        riss_layout = QHBoxLayout(riss_row)
        riss_layout.setContentsMargins(14, 12, 14, 12)
        riss_layout.setSpacing(12)

        riss_text = QVBoxLayout()
        riss_text.setSpacing(2)

        self.riss_title = QLabel()
        self.riss_title.setObjectName("settingsLabel")

        self.riss_desc = QLabel()
        self.riss_desc.setObjectName("settingsDescription")

        riss_text.addWidget(self.riss_title)
        riss_text.addWidget(self.riss_desc)

        self.riss_enabled_btn = QPushButton("Off")
        self.riss_enabled_btn.setCheckable(True)
        self.riss_enabled_btn.setObjectName("toggleButton")
        self.riss_enabled_btn.setFixedWidth(70)

        self.riss_anchor_combo = QComboBox()
        self.riss_anchor_combo.setObjectName("settingsCombo")
        self.riss_anchor_combo.addItems([
            "00", "01", "02"
        ])
        self.riss_anchor_combo.setFixedWidth(80)

        self.riss_interval_combo = QComboBox()
        self.riss_interval_combo.setObjectName("settingsCombo")
        self.riss_interval_combo.addItems([
            "1 Stunde", "2 Stunden", "3 Stunden"
        ])
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

        self.shugo_enabled_btn.toggled.connect(
            lambda checked: self.shugo_enabled_btn.setText("On" if checked else "Off")
        )

        self.riss_enabled_btn.toggled.connect(
            lambda checked: self.riss_enabled_btn.setText("On" if checked else "Off")
        )

        return page
    
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
            lambda checked: self.auto_save_btn.setText("On" if checked else "Off")
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
            lambda checked: self.show_events_btn.setText("On" if checked else "Off")
        )

        row_layout.addLayout(text_layout, 1)
        row_layout.addWidget(self.show_events_btn)

        layout.addWidget(event_row)
        layout.addWidget(auto_save_row)
        layout.addStretch()

        return page
    
    def set_values(self, data: dict):
        # Allgemein
        if hasattr(self, "show_events_btn"):
            show_events = data.get("show_events", True)
            self.show_events_btn.setChecked(show_events)
            self.show_events_btn.setText("On" if show_events else "Off")

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
                btn.setChecked(btn.text() == weekly_day)

        if hasattr(self, "weekly_reset_time"):
            h, m = map(int, data.get("weekly_reset_time", "09:00").split(":"))
            self.weekly_reset_time.setTime(QTime(h, m))

        # Advanced Timer
        if hasattr(self, "shugo_enabled_btn"):
            enabled = data.get("shugo_enabled", False)
            self.shugo_enabled_btn.setChecked(enabled)
            self.shugo_enabled_btn.setText("On" if enabled else "Off")

        if hasattr(self, "shugo_minute_combo"):
            value = str(data.get("shugo_start_minute", 15)).zfill(2)
            index = self.shugo_minute_combo.findText(value)
            if index >= 0:
                self.shugo_minute_combo.setCurrentIndex(index)

        if hasattr(self, "shugo_interval_combo"):
            value = data.get("shugo_interval_text", "30 min")
            index = self.shugo_interval_combo.findText(value)
            if index >= 0:
                self.shugo_interval_combo.setCurrentIndex(index)

        if hasattr(self, "riss_enabled_btn"):
            enabled = data.get("riss_enabled", False)
            self.riss_enabled_btn.setChecked(enabled)
            self.riss_enabled_btn.setText("On" if enabled else "Off")

        if hasattr(self, "riss_anchor_combo"):
            value = str(data.get("riss_anchor_hour", 0)).zfill(2)
            index = self.riss_anchor_combo.findText(value)
            if index >= 0:
                self.riss_anchor_combo.setCurrentIndex(index)

        if hasattr(self, "riss_interval_combo"):
            value = data.get("riss_interval_text", "1 Stunde")
            index = self.riss_interval_combo.findText(value)
            if index >= 0:
                self.riss_interval_combo.setCurrentIndex(index)

        if hasattr(self, "auto_save_btn"):
            auto_save = data.get("auto_save", True)
            self.auto_save_btn.setChecked(auto_save)
            self.auto_save_btn.setText("On" if auto_save else "Off")

    def get_selected_theme(self):
        if not hasattr(self, "theme_buttons"):
            return "abyss"

        for theme_key, button in self.theme_buttons.items():
            if button.isChecked():
                return theme_key

        return "abyss"