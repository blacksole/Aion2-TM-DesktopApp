from PySide6.QtCore import QTime, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QCheckBox, QTimeEdit, QPushButton, QComboBox,
    QButtonGroup, QStackedWidget, QWidget
)
from core.translations import tr

class SettingsDialog(QDialog):
    def __init__(
        self,
        parent=None,
        show_events=True,
        shugo_enabled=False,
        riss_enabled=False,
        shugo_start_minute="00",
        shugo_interval="30 min",
        riss_anchor_hour="00",
        riss_interval="1 Stunde",
        daily_reset_time="09:00",
        weekly_reset_time="09:00",
        weekly_day="Mo",
        language="de",
        current_theme="abyss"
    ):
        super().__init__(parent)

        self.language = language
        self.current_theme = current_theme
        self.setProperty("theme", self.current_theme)

        self.setWindowTitle("Settings")
        self.setMinimumSize(640, 420)
        self.resize(720, 460)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)

        title = QLabel("Settings")
        title.setObjectName("settingsTitle")
        main_layout.addWidget(title)

        self.system_time_label = QLabel()
        self.system_time_label.setObjectName("systemTimeLabel")
        main_layout.addWidget(self.system_time_label)

        self.system_clock = QTimer(self)
        self.system_clock.timeout.connect(self.update_system_time)
        self.system_clock.start(1000)
        self.update_system_time()

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # ===== SIDEBAR =====
        sidebar = QFrame()
        sidebar.setObjectName("settingsSidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(8)

        self.general_btn = self.create_sidebar_button("Allgemein", 0)
        self.reset_timer_btn = self.create_sidebar_button("Reset Timer", 1)
        self.advanced_timer_btn = self.create_sidebar_button("Advanced Timer", 2)
        self.layout_btn = self.create_sidebar_button(tr(self.language, "layout"), 3)
        self.language_btn = self.create_sidebar_button(tr(self.language, "language"), 4)

        sidebar_layout.addWidget(self.general_btn)
        sidebar_layout.addWidget(self.reset_timer_btn)
        sidebar_layout.addWidget(self.advanced_timer_btn)
        sidebar_layout.addWidget(self.layout_btn)
        sidebar_layout.addWidget(self.language_btn)
        sidebar_layout.addStretch()

        # ===== STACK =====
        self.pages = QStackedWidget()

        self.general_page = QWidget()
        self.reset_timer_page = QWidget()
        self.advanced_timer_page = QWidget()
        self.layout_page = QWidget()
        self.language_page = QWidget()

        self.build_general_page()

        self.build_reset_timer_page(
            daily_reset_time,
            weekly_reset_time,
            weekly_day
        )

        self.build_advanced_timer_page(
            shugo_enabled,
            riss_enabled,
            shugo_start_minute,
            shugo_interval,
            riss_anchor_hour,
            riss_interval
        )

        self.build_layout_page(show_events)
        self.build_language_page()


        self.pages.addWidget(self.general_page)
        self.pages.addWidget(self.reset_timer_page)
        self.pages.addWidget(self.advanced_timer_page)
        self.pages.addWidget(self.layout_page)
        self.pages.addWidget(self.language_page)

        content_layout.addWidget(sidebar)
        content_layout.addWidget(self.pages, 1)

        main_layout.addLayout(content_layout)

        # ===== BUTTONS =====
        button_row = QHBoxLayout()
        button_row.addStretch()

        cancel_btn = QPushButton(tr(self.language, "cancel"))
        cancel_btn.setMinimumHeight(38)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton(tr(self.language, "save"))
        save_btn.setObjectName("primaryButton")
        save_btn.setMinimumHeight(38)
        save_btn.clicked.connect(self.accept)

        button_row.addWidget(cancel_btn)
        button_row.addWidget(save_btn)

        main_layout.addLayout(button_row)

        self.set_active_sidebar_button(self.general_btn)
        self.pages.setCurrentIndex(0)
        self.resize(720, 460)

    def create_sidebar_button(self, text, index):
        btn = QPushButton(text)
        btn.setObjectName("settingsSidebarButton")
        btn.setCheckable(True)
        btn.setMinimumHeight(40)
        btn.clicked.connect(lambda: self.switch_page(index, btn))
        return btn

    def switch_page(self, index, button):
        self.pages.setCurrentIndex(index)
        self.set_active_sidebar_button(button)

    def set_active_sidebar_button(self, active_button):
        for btn in [
            self.general_btn,
            self.reset_timer_btn,
            self.advanced_timer_btn,
            self.layout_btn,
            self.language_btn
        ]:
            btn.setChecked(btn == active_button)

    def build_general_page(self):
        layout = QVBoxLayout(self.general_page)
        layout.setSpacing(14)

        layout.addWidget(self.create_section_title("Allgemein"))

        info = QLabel("Hier können später allgemeine Einstellungen ergänzt werden.")
        info.setObjectName("settingsLabel")
        info.setWordWrap(True)

        layout.addWidget(info)
        layout.addStretch()

    def build_layout_page(self, show_events):
        layout = QVBoxLayout(self.layout_page)
        layout.setSpacing(14)

        layout.addWidget(self.create_section_title(tr(self.language, "display")))

        self.show_events = QCheckBox(tr(self.language, "show_events"))
        self.show_events.setChecked(show_events)
        self.show_events.setObjectName("settingsCheckbox")
        layout.addWidget(self.show_events)

        layout.addWidget(self.create_section_title("Theme"))

        self.theme_selector = self.create_theme_button_row(
            "Farbstil",
            [
                ("Abyss Neon", "abyss", "🌌"),
                ("Inferno Crimson", "inferno", "🔥"),
                ("Emerald Night", "emerald", "🌲"),
                ("Frostbite", "frostbite", "❄️"),
                ("Obsidian Gold", "obsidian", "🌑"),
                ("Void Purple", "void", "🟣"),
            ]
        )

        layout.addWidget(self.theme_selector)
        layout.addStretch()

    def build_reset_timer_page(self, daily_reset_time, weekly_reset_time, weekly_day):
        layout = QVBoxLayout(self.reset_timer_page)
        layout.setSpacing(14)

        layout.addWidget(self.create_section_title("Reset Timer"))

        daily_time = QTime.fromString(daily_reset_time, "HH:mm")
        if not daily_time.isValid():
            daily_time = QTime(9, 0)

        weekly_time = QTime.fromString(weekly_reset_time, "HH:mm")
        if not weekly_time.isValid():
            weekly_time = QTime(9, 0)

        self.daily_reset = self.create_time_row("Daily Reset", daily_time)

        self.weekly_day = self.create_weekday_button_row(
            tr(self.language, "weekly_reset_day")
        )
        self.set_button_group_value(self.weekly_day, weekly_day)

        self.weekly_reset = self.create_time_row(
            tr(self.language, "weekly_reset_time"),
            weekly_time
        )

        layout.addWidget(self.daily_reset)
        layout.addWidget(self.weekly_day)
        layout.addWidget(self.weekly_reset)

        layout.addStretch()

    def build_advanced_timer_page(
        self,
        shugo_enabled,
        riss_enabled,
        shugo_start_minute,
        shugo_interval,
        riss_anchor_hour,
        riss_interval
    ):
        layout = QVBoxLayout(self.advanced_timer_page)
        layout.setSpacing(14)

        layout.addWidget(self.create_section_title("Advanced Timer"))

        self.shugo_timer_enabled = QCheckBox(tr(self.language, "show_shugo"))
        self.shugo_timer_enabled.setObjectName("settingsCheckbox")
        self.shugo_timer_enabled.setChecked(shugo_enabled)

        self.riss_timer_enabled = QCheckBox(tr(self.language, "show_riss"))
        self.riss_timer_enabled.setObjectName("settingsCheckbox")
        self.riss_timer_enabled.setChecked(riss_enabled)

        layout.addWidget(self.shugo_timer_enabled)
        layout.addWidget(self.riss_timer_enabled)

        self.shugo_minute = self.create_minute_button_row(
            tr(self.language, "shugo_start")
        )
        self.set_button_group_value(self.shugo_minute, shugo_start_minute)

        self.shugo_interval = self.create_combo_row(
            "Shugo Event Takt",
            ["30 min", "1 Stunde", "2 Stunden", "3 Stunden"]
        )
        self.shugo_interval.findChild(QComboBox).setCurrentText(shugo_interval)

        self.riss_anchor = self.create_hour_button_row(
            tr(self.language, "riss_anchor"),
            ["00", "01", "02"]
        )
        self.set_button_group_value(self.riss_anchor, riss_anchor_hour)

        self.riss_interval = self.create_combo_row(
            "Riss Takt",
            ["1 Stunde", "2 Stunden", "3 Stunden"]
        )
        self.riss_interval.findChild(QComboBox).setCurrentText(riss_interval)

        layout.addWidget(self.shugo_minute)
        layout.addWidget(self.shugo_interval)
        layout.addWidget(self.riss_anchor)
        layout.addWidget(self.riss_interval)

        layout.addStretch()

    def build_language_page(self):
        layout = QVBoxLayout(self.language_page)
        layout.setSpacing(14)

        layout.addWidget(self.create_section_title("Sprache"))

        self.language_combo = self.create_combo_row(
            tr(self.language, "select_language"),
            ["Deutsch", "English"]
        )

        combo = self.language_combo.findChild(QComboBox)
        combo.setCurrentText("Deutsch" if self.language == "de" else "English")

        layout.addWidget(self.language_combo)
        layout.addStretch()

    def create_section_title(self, text):
        label = QLabel(text)
        label.setObjectName("settingsSectionTitle")
        return label

    def create_time_row(self, label_text, default_time):
        frame = QFrame()
        frame.setObjectName("settingsRow")
        frame.setMinimumHeight(56)

        row = QHBoxLayout(frame)
        row.setContentsMargins(14, 10, 14, 10)

        label = QLabel(label_text)
        label.setObjectName("settingsLabel")

        time_edit = QTimeEdit()
        time_edit.setTime(default_time)
        time_edit.setDisplayFormat("HH:mm")
        time_edit.setObjectName("settingsTimeEdit")
        time_edit.setMinimumHeight(36)
        time_edit.setMinimumWidth(100)

        row.addWidget(label)
        row.addStretch()
        row.addWidget(time_edit)

        return frame

    def create_combo_row(self, label_text, options):
        frame = QFrame()
        frame.setObjectName("settingsRow")
        frame.setMinimumHeight(56)

        row = QHBoxLayout(frame)
        row.setContentsMargins(14, 10, 14, 10)

        label = QLabel(label_text)
        label.setObjectName("settingsLabel")

        combo = QComboBox()
        combo.addItems(options)
        combo.setObjectName("settingsComboBox")
        combo.setMinimumHeight(36)
        combo.setMinimumWidth(140)

        row.addWidget(label)
        row.addStretch()
        row.addWidget(combo)

        return frame

    def create_minute_button_row(self, label_text):
        return self.create_button_row(label_text, ["00", "15", "30", "45"])

    def create_hour_button_row(self, label_text, values):
        return self.create_button_row(label_text, values)

    def create_weekday_button_row(self, label_text):

        days = (
            ["Mo", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            if self.language == "en"
            else ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        )

        return self.create_button_row(
            label_text,
            days,
            button_width=46
        )

    def create_button_row(self, label_text, values, button_width=52):
        frame = QFrame()
        frame.setObjectName("settingsRow")
        frame.setMinimumHeight(56)

        row = QHBoxLayout(frame)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(8)

        label = QLabel(label_text)
        label.setObjectName("settingsLabel")

        button_group = QButtonGroup(frame)
        button_group.setExclusive(True)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)

        for value in values:
            btn = QPushButton(value)
            btn.setCheckable(True)
            btn.setObjectName("minuteToggleButton")
            btn.setMinimumHeight(34)
            btn.setMinimumWidth(button_width)

            if value == values[0]:
                btn.setChecked(True)

            button_group.addButton(btn)
            button_row.addWidget(btn)

        row.addWidget(label)
        row.addStretch()
        row.addLayout(button_row)

        frame.button_group = button_group

        return frame

    def set_button_group_value(self, row_frame, value):
        value = str(value)

        for button in row_frame.button_group.buttons():
            button.setChecked(button.text() == value)

    def update_system_time(self):
        current_time = QTime.currentTime().toString("HH:mm:ss")
        self.system_time_label.setText(f"Systemzeit: {current_time}")

    def get_selected_language(self):
        combo = self.language_combo.findChild(QComboBox)
        return "de" if combo.currentText() == "Deutsch" else "en"
    
    def create_theme_button_row(self, label_text, themes):
        frame = QFrame()
        frame.setObjectName("settingsThemeContainer")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        label = QLabel(label_text)
        label.setObjectName("settingsLabel")
        layout.addWidget(label)

        button_group = QButtonGroup(frame)
        button_group.setExclusive(True)

        for text, value, icon in themes:
            btn = QPushButton(f"{icon}  {text}")
            btn.setCheckable(True)
            btn.setObjectName("themeToggleButton")
            btn.setMinimumHeight(40)
            btn.setProperty("themeValue", value)
            def apply_selected_theme(_checked=False, theme=value):
                self.apply_dialog_theme(theme)

                if self.parent():
                    self.parent().apply_theme(theme)

            btn.clicked.connect(apply_selected_theme)

            if value == self.current_theme:
                btn.setChecked(True)

            button_group.addButton(btn)
            layout.addWidget(btn)

        frame.button_group = button_group

        return frame
    
    def get_selected_theme(self):
        for button in self.theme_selector.button_group.buttons():
            if button.isChecked():
                return button.property("themeValue")

        return "abyss"
    
    def apply_dialog_theme(self, theme):
        self.current_theme = theme
        self.setProperty("theme", theme)

        self.style().unpolish(self)
        self.style().polish(self)

        for widget in self.findChildren(QWidget):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

        self.update()

