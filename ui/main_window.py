from asyncio import tasks
import json
from pathlib import Path
from .settings_dialog import SettingsDialog
from .widgets.header_widget import HeaderWidget
from .widgets.sidebar_widget import SidebarWidget
from .pages.tasks_page import TasksPage
from .pages.timers_page import TimersPage
from .pages.profile_page import ProfilePage
from .pages.settings_page import SettingsPage
from .pages.dashboard_page import DashboardPage
from core.translations import tr
from PySide6.QtWidgets import QTimeEdit
from PySide6.QtGui import QPainter, QLinearGradient, QColor, Qt, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMenu, QComboBox, 
    QStackedWidget
)
from datetime import datetime, timedelta
from PySide6.QtCore import QTimer

THEME_LOGOS = {
    "abyss": "assets/logos/logo_abyss.png",
    "inferno": "assets/logos/logo_inferno.png",
    "emerald": "assets/logos/logo_emerald.png",
    "frostbite": "assets/logos/logo_frostbite.png",
    "obsidian": "assets/logos/logo_obsidian.png",
    "void": "assets/logos/logo_void.png",
}


class GradientBackground(QWidget):
    THEMES = {
        "abyss": ["#0f172a", "#111827", "#121212", "#2e0f28"],
        "inferno": ["#140f0f", "#1f1111", "#281212", "#3b0f0f"],
        "emerald": ["#07130f", "#0b1f17", "#10261f", "#132d26"],
        "frostbite": ["#0b1120", "#111827", "#172554", "#1e3a8a"],
        "obsidian": ["#111111", "#171717", "#1f1f1f", "#262626"],
        "void": ["#120c1c", "#1b1028", "#231236", "#2f1547"],
    }

    def __init__(self):
        super().__init__()
        self.theme = "abyss"

    def set_theme(self, theme):
        self.theme = theme
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        colors = self.THEMES.get(self.theme, self.THEMES["abyss"])

        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor(colors[0]))
        gradient.setColorAt(0.35, QColor(colors[1]))
        gradient.setColorAt(0.75, QColor(colors[2]))
        gradient.setColorAt(1.0, QColor(colors[3]))

        painter.fillRect(self.rect(), gradient)

class TaskCard(QFrame):
    def __init__(self, title, description=""):
        super().__init__()

        self.completed = False

        self.setObjectName("taskCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        self.check_btn = QPushButton("○")
        self.check_btn.setObjectName("checkButton")
        self.check_btn.setFixedWidth(32)
        self.check_btn.clicked.connect(self.toggle)

        text_box = QVBoxLayout()

        self.title_label = QLabel(title)
        self.title_label.setObjectName("taskTitle")

        self.desc_label = QLabel(description)
        self.desc_label.setObjectName("taskDescription")

        text_box.addWidget(self.title_label)

        if description:
            text_box.addWidget(self.desc_label)

        self.priority = QLabel("Mittel")
        self.priority.setObjectName("priorityMedium")

        self.delete_btn = QPushButton("🗑")
        self.delete_btn.setObjectName("deleteButton")
        self.delete_btn.setFixedWidth(36)
        self.delete_btn.clicked.connect(self.deleteLater)

        layout.addWidget(self.check_btn)
        layout.addLayout(text_box, 1)
        layout.addWidget(self.priority)
        layout.addWidget(self.delete_btn)

    def toggle(self):
        self.completed = not self.completed

        if self.completed:
            self.check_btn.setText("●")
            self.setProperty("completed", True)

            self.title_label.setStyleSheet(
                "color: #64748b; text-decoration: line-through;"
            )

        else:
            self.check_btn.setText("○")
            self.setProperty("completed", False)
            self.title_label.setStyleSheet("")

        self.style().unpolish(self)
        self.style().polish(self)

    def set_completed(self, value):
        self.completed = value

        if self.completed:
            self.check_btn.setText("●")
            self.setProperty("completed", True)
            self.title_label.setStyleSheet(
                "color: #64748b; text-decoration: line-through;"
            )
        else:
            self.check_btn.setText("○")
            self.setProperty("completed", False)
            self.title_label.setStyleSheet("")

        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QMainWindow):
    def __init__(self, auth_manager=None):
        super().__init__()

        self.auth_manager = auth_manager
        self.auto_save = True

        self.tabs = {
            "dailyTasks": "daily_tasks",
            "weeklyTasks": "weekly_tasks",
            "eventTasks": "event_tasks",
            "dailyShopping": "daily_shopping",
            "weeklyShopping": "weekly_shopping",
            "eventShopping": "event_shopping",
        }

        self.language = "en"
        self.current_theme = "abyss"

        self.active_tab = "dailyTasks"
        self.show_events = True
        self.daily_reset_time = "09:00"
        self.weekly_reset_day = "Mo"
        self.weekly_reset_time = "09:00"
        self.last_daily_reset_date = None
        self.last_weekly_reset_date = None
        self.profile_name = "Default"
        self.project_root = Path(__file__).resolve().parent.parent
        self.profile_dir = self.project_root / "profiles"
        self.profile_dir.mkdir(exist_ok=True)
        self.last_profile_file = self.profile_dir / "last_profile.txt"
        self.profile_edit_mode = False

        self.shugo_enabled = False
        self.shugo_start_minute = 15
        self.shugo_interval_minutes = 30
        self.shugo_interval_text = "30 min"


        self.riss_enabled = False
        self.riss_anchor_hour = 0
        self.riss_interval_hours = 1
        self.riss_interval_text = "1 Stunde"

        self.weekly_reset_day = "Mo"

        self.task_lists = {
            key: [] for key in self.tabs
        }

        self.setup_ui()
        self.load_styles()
        self.apply_language()
        self.sync_settings_page()
        self.refresh()

        self.load_last_profile()

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdowns)
        self.countdown_timer.start(1000)

        self.update_countdowns()



    def setup_ui(self):
        self._setup_window()
        self._setup_central_widget()
        self._setup_header()
        self._setup_theme_logo()
        self._setup_sidebar()
        self._setup_pages()
        self._setup_layout()
        self._connect_signals()
        

    def _setup_window(self):
        self.setWindowTitle(self.tr("app.title"))
        self.resize(1200, 800)
        self.setMinimumSize(1000, 700)

    def _setup_header(self):
        self.header = HeaderWidget()


    def _setup_central_widget(self):
        self.background = GradientBackground()
        self.background.set_theme(self.current_theme)
        self.setCentralWidget(self.background)

        self.main_layout = QHBoxLayout(self.background)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.left_panel = QWidget()
        self.left_panel.setObjectName("leftPanel")
        self.left_panel.setFixedWidth(260)

        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(14, 14, 14, 14)
        self.left_layout.setSpacing(16)

        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(18, 18, 18, 18)
        self.content_layout.setSpacing(14)

        self.page_stack = QStackedWidget()

        self.toast_label = QLabel()
        self.toast_label.setObjectName("toastLabel")
        self.toast_label.hide()
    
    def _setup_sidebar(self):
        self.sidebar = SidebarWidget()


    def _setup_pages(self):
        self.dashboard_page = DashboardPage()

        self.tasks_page = TasksPage(
            tabs=self.tabs,
            language=self.language,
            tr_func=tr
        )

        self.timers_page = TimersPage()
        self.profile_page = ProfilePage()
        self.settings_page = SettingsPage()

        self.page_indexes = {
            "dashboard": 0,
            "tasks": 1,
            "timers": 2,
            "profile": 3,
            "settings": 4,
        }

        self.page_stack.addWidget(self.dashboard_page)
        self.page_stack.addWidget(self.tasks_page)
        self.page_stack.addWidget(self.timers_page)
        self.page_stack.addWidget(self.profile_page)
        self.page_stack.addWidget(self.settings_page)

        self.page_stack.setCurrentWidget(self.tasks_page)


    def _setup_layout(self):
        self.left_layout.addWidget(self.header)
        self.left_layout.addWidget(self.theme_logo_label)
        self.left_layout.addWidget(self.sidebar)
        self.left_layout.addStretch()

        self.content_layout.addWidget(self.page_stack, 1)
        self.content_layout.addWidget(self.toast_label)

        self.main_layout.addWidget(self.left_panel)
        self.main_layout.addWidget(self.content_container, 1)


    def _connect_signals(self):
        if hasattr(self.sidebar, "page_changed"):
            self.sidebar.page_changed.connect(self.handle_sidebar_page_changed)

        self.tasks_page.task_add_requested.connect(self.add_task_from_page)
        self.tasks_page.tab_changed.connect(self.select_tab)

        if hasattr(self.settings_page, "theme_changed"):
            self.settings_page.theme_changed.connect(
                self.change_theme_from_page
            )

        if hasattr(self.header, "settings_requested"):
            self.header.settings_requested.connect(self.open_settings)

        if hasattr(self.header, "main_menu_requested"):
            self.header.main_menu_requested.connect(self.open_main_menu)

        if hasattr(self.settings_page, "settings_save_requested"):
            self.settings_page.settings_save_requested.connect(
                self.apply_settings_from_page
            )

    def open_main_menu(self):
        menu = QMenu(self)

        menu.addAction("New Profile")
        menu.addAction("Save Profile")

        load_menu = menu.addMenu("Load Profile")

        load_menu.addAction("No profiles").setEnabled(False)

        menu.exec(
            self.sender().mapToGlobal(
                self.sender().rect().bottomLeft()
            )
        )

    def open_settings(self):
        dialog = SettingsDialog(
            self,
            show_events=self.show_events,
            shugo_enabled=self.shugo_enabled,
            riss_enabled=self.riss_enabled,
            shugo_start_minute=str(self.shugo_start_minute).zfill(2),
            shugo_interval=self.shugo_interval_text,
            riss_anchor_hour=str(self.riss_anchor_hour).zfill(2),
            riss_interval=self.riss_interval_text,
            weekly_day=self.weekly_reset_day,
            daily_reset_time=self.daily_reset_time,
            weekly_reset_time=self.weekly_reset_time,
            language=self.language,
            current_theme=self.current_theme
        )

        if dialog.exec():

            self.language = dialog.get_selected_language()
            self.apply_language()

            self.apply_theme(dialog.get_selected_theme())

            self.show_events = dialog.show_events.isChecked()

            self.toggle_events()

            # ===== RESET TIMER =====

            daily_time = dialog.daily_reset.findChild(
                QTimeEdit
            ).time().toString("HH:mm")

            weekly_time = dialog.weekly_reset.findChild(
                QTimeEdit
            ).time().toString("HH:mm")

            self.daily_reset_time = daily_time
            self.weekly_reset_time = weekly_time

            self.weekly_reset_day = self.get_selected_minute(
                dialog.weekly_day
            )

            self.update_countdowns()

            # ===== SHUGO =====

            if dialog.shugo_timer_enabled.isChecked():

                self.shugo_enabled = True

                self.shugo_start_minute = int(
                    self.get_selected_minute(dialog.shugo_minute)
                )

                self.shugo_interval_minutes = self.interval_text_to_minutes(
                    dialog.shugo_interval.findChild(QComboBox).currentText()
                )

                self.timers_page.set_shugo_visible(True)

            else:
                self.shugo_enabled = False
                self.timers_page.set_shugo_visible(False)

            self.shugo_interval_text = dialog.shugo_interval.findChild(QComboBox).currentText()
            self.shugo_interval_minutes = self.interval_text_to_minutes(self.shugo_interval_text)

            # ===== RISS =====

            if dialog.riss_timer_enabled.isChecked():

                self.riss_enabled = True

                self.riss_anchor_hour = int(
                    self.get_selected_minute(dialog.riss_anchor)
                )

                self.riss_interval_hours = self.interval_text_to_hours(
                    dialog.riss_interval.findChild(QComboBox).currentText()
                )

                self.timers_page.set_riss_visible(True)
            else:
                self.riss_enabled = False
                self.timers_page.set_riss_visible(False)

            self.riss_interval_text = dialog.riss_interval.findChild(QComboBox).currentText()
            self.riss_interval_hours = self.interval_text_to_hours(self.riss_interval_text)

            self.update_countdowns()

            self.save_profile()

            self.show_toast(
                tr(self.language, "settings_saved")
            )

    def get_selected_minute(self, minute_row):
        for button in minute_row.button_group.buttons():

            if button.isChecked():
                return button.text()

        return "00"
    
    def get_next_daily_reset(self):
        now = datetime.now()

        hour, minute = map(int, self.daily_reset_time.split(":"))

        reset_time = now.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0
        )

        if reset_time <= now:
            reset_time += timedelta(days=1)

        return reset_time


    def get_next_weekly_reset(self):
        now = datetime.now()

        day_map = {
            "Mo": 0,
            "Di": 1,
            "Mi": 2,
            "Do": 3,
            "Fr": 4,
            "Sa": 5,
            "So": 6,

            "Tue": 1,
            "Wed": 2,
            "Thu": 3,
            "Fri": 4,
            "Sat": 5,
            "Sun": 6,
        }

        target_weekday = day_map.get(self.weekly_reset_day, 0)

        hour, minute = map(int, self.weekly_reset_time.split(":"))

        days_ahead = target_weekday - now.weekday()

        if days_ahead < 0:
            days_ahead += 7

        reset_date = now + timedelta(days=days_ahead)

        reset_time = reset_date.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0
        )

        if reset_time <= now:
            reset_time += timedelta(days=7)

        return reset_time


    def format_reset_countdown(self, seconds):
        seconds = max(0, int(seconds))

        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, secs = divmod(remainder, 60)

        if days > 0:
            return f"{days}T {hours:02}:{minutes:02}"

        return f"{hours:02}:{minutes:02}:{secs:02}"


    def update_countdowns(self):
        now = datetime.now()

        daily_next = self.get_next_daily_reset()
        daily_seconds = (daily_next - now).total_seconds()
        daily_text = self.format_reset_countdown(daily_seconds)
        self.timers_page.set_daily_countdown(daily_text)

        weekly_next = self.get_next_weekly_reset()
        weekly_seconds = (weekly_next - now).total_seconds()
        weekly_text = self.format_reset_countdown(weekly_seconds)
        self.timers_page.set_weekly_countdown(weekly_text)

        if self.shugo_enabled:
            next_shugo = self.get_next_shugo_time()
            seconds = (next_shugo - now).total_seconds()
            shugo_text = self.format_countdown(seconds)
            self.timers_page.set_shugo_countdown(shugo_text)

        if self.riss_enabled:
            next_riss = self.get_next_riss_time()
            seconds = (next_riss - now).total_seconds()
            riss_text = self.format_countdown(seconds)
            self.timers_page.set_riss_countdown(riss_text)

        self.check_auto_resets()

    def select_tab(self, tab):
        self.active_tab = tab

        self.refresh()

    def add_task(self):
        title = self.title_input.text().strip()
        description = self.desc_input.text().strip()

        if not title:
            return

        card = TaskCard(title, description)

        self.task_lists[self.active_tab].insert(0, card)

        self.title_input.clear()
        self.desc_input.clear()

        self.refresh()

    def refresh(self):

        tasks = self.task_lists[self.active_tab]
        self.tasks_page.render_tasks(tasks)

        total = len(tasks)

        done = len([
            t for t in tasks if t.completed
        ])

        open_count = total - done

        progress = round(
            (done / total) * 100
        ) if total else 0

        self.tasks_page.update_stats(total, done, open_count)

        self.tasks_page.set_footer_text(
            f"● {tr(self.language, 'progress')}: {progress}%"
        )

        tab_key = self.tabs[self.active_tab]

        self.tasks_page.set_title_placeholder(
            tr(
                self.language,
                f"placeholder_{tab_key}"
            )
        )

    def load_styles(self):
        style_path = (
            Path(__file__).resolve().parent / "styles.qss"
        )

        with open(style_path, "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

    def toggle_events(self):
        self.tasks_page.set_events_visible(self.show_events)

        if (
            not self.show_events and
            self.active_tab in [
                "eventTasks",
                "eventShopping"
            ]
        ):
            self.active_tab = "dailyTasks"
            self.tasks_page.set_active_tab("dailyTasks")

        self.refresh()

    def interval_text_to_minutes(self, text):
        if "30" in text:
            return 30
        if "1" in text:
            return 60
        if "2" in text:
            return 120
        if "3" in text:
            return 180
        return 30


    def interval_text_to_hours(self, text):
        if "1" in text:
            return 1
        if "2" in text:
            return 2
        if "3" in text:
            return 3
        return 1


    def format_countdown(self, seconds):
        seconds = max(0, int(seconds))
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            return f"{hours:02}:{minutes:02}:{sec:02}"

        return f"{minutes:02}:{sec:02}"


    def get_next_shugo_time(self):
        now = datetime.now()

        anchor = now.replace(
            minute=self.shugo_start_minute,
            second=0,
            microsecond=0
        )

        interval = timedelta(minutes=self.shugo_interval_minutes)

        while anchor <= now:
            anchor += interval

        return anchor


    def get_next_riss_time(self):
        now = datetime.now()

        anchor = now.replace(
            hour=self.riss_anchor_hour,
            minute=0,
            second=0,
            microsecond=0
        )

        interval = timedelta(hours=self.riss_interval_hours)

        while anchor <= now:
            anchor += interval

        return anchor
            
    def open_profile_menu(self):
        menu = QMenu(self)

        profiles = sorted(self.profile_dir.glob("*.json"))

        if profiles:
            for profile_path in profiles:
                profile_name = profile_path.stem

                action = menu.addAction(profile_name)
                action.triggered.connect(
                    lambda checked=False, path=profile_path: self.load_profile(path)
                )
        else:
            menu.addAction("No profiles").setEnabled(False)

        menu.exec(
            self.profile_page.load_profile_btn.mapToGlobal(
                self.profile_page.load_profile_btn.rect().bottomLeft()
            )
        )

    def load_profile(self, profile_path):
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = {}
        except FileNotFoundError:
            data = {}

        self.profile_name = profile_path.stem
        if not isinstance(data, dict):
            data = {}

        self.current_theme = data.get("theme", "abyss")
        self.apply_theme(self.current_theme)

        self.language = data.get("language", "en")
        self.apply_language()

        settings = data.get("settings", {})

        self.daily_reset_time = settings.get("daily_reset_time", "09:00")
        self.weekly_reset_day = settings.get("weekly_reset_day", "Mo")
        self.weekly_reset_time = settings.get("weekly_reset_time", "09:00")

        self.show_events = settings.get("show_events", True)
        self.auto_save = settings.get("auto_save", True)
        self.shugo_enabled = settings.get("shugo_enabled", False)
        self.shugo_start_minute = settings.get("shugo_start_minute", 15)
        self.shugo_interval_text = settings.get("shugo_interval_text", "30 min")
        self.shugo_interval_minutes = self.interval_text_to_minutes(
            self.shugo_interval_text
        )

        self.riss_enabled = settings.get("riss_enabled", False)
        self.riss_anchor_hour = settings.get("riss_anchor_hour", 0)
        self.riss_interval_text = settings.get("riss_interval_text", "1 Stunde")
        self.riss_interval_hours = self.interval_text_to_hours(
            self.riss_interval_text
        )

        self.timers_page.set_shugo_visible(self.shugo_enabled)
        self.timers_page.set_riss_visible(self.riss_enabled)

        self.toggle_events()
        self.update_countdowns()

        self.profile_page.set_profile_name(self.profile_name)
        self.sync_settings_page()

        # Aktuelle Listen immer leeren
        self.task_lists = {key: [] for key in self.tabs}

        # Neues Format:
        # {
        #   "profile_name": "...",
        #   "tasks": {
        #       "dailyTasks": [...]
        #   }
        # }
        if isinstance(data, dict):
            saved_tasks = data.get("tasks", {})

        # Altes Format oder leeres Profil
        else:
            saved_tasks = {}

        if isinstance(saved_tasks, dict):
            for tab, cards in saved_tasks.items():
                if tab not in self.task_lists:
                    continue

                if not isinstance(cards, list):
                    continue

                for item in cards:
                    if not isinstance(item, dict):
                        continue

                    card = TaskCard(
                        item.get("title", ""),
                        item.get("description", "")
                    )
                    if item.get("completed", False):
                        card.toggle()
                    self.task_lists[tab].append(card)

        self.refresh()
        self.save_last_profile(profile_path)
        print("Profil geladen:", self.profile_name)
    
    def save_profile(self):
        data = {
            "profile_name": self.profile_name,
            "theme": self.current_theme,
            "language": self.language,

            "settings": {
                "daily_reset_time": self.daily_reset_time,
                "weekly_reset_day": self.weekly_reset_day,
                "weekly_reset_time": self.weekly_reset_time,

                "show_events": self.show_events,

                "shugo_enabled": self.shugo_enabled,
                "shugo_start_minute": self.shugo_start_minute,
                "shugo_interval_text": self.shugo_interval_text,

                "riss_enabled": self.riss_enabled,
                "riss_anchor_hour": self.riss_anchor_hour,
                "riss_interval_text": self.riss_interval_text,

                "auto_save": self.auto_save,
            },

            "tasks": {
                tab: [
                    {
                        "title": card.title_label.text(),
                        "description": card.desc_label.text(),
                        "completed": card.completed,
                    }
                    for card in cards
                ]
                for tab, cards in self.task_lists.items()
            }
        }

        profile_path = self.profile_dir / f"{self.profile_name}.json"

        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        self.save_last_profile(profile_path)

        print("Profil gespeichert:", profile_path)
        self.show_toast(
            tr(self.language, "profile_saved")
        )

    def save_last_profile(self, profile_path):
        with open(self.last_profile_file, "w", encoding="utf-8") as f:
            f.write(str(profile_path))


    def load_last_profile(self):
        if not self.last_profile_file.exists():
            return

        with open(self.last_profile_file, "r", encoding="utf-8") as f:
            profile_path = Path(f.read().strip())

        if profile_path.exists():
            self.load_profile(profile_path)

    def reset_profile(self):
        self.task_lists = {key: [] for key in self.tabs}
        self.refresh()

        print("Profil zurückgesetzt:", self.profile_name)

    def apply_language(self):
        self.setWindowTitle("Aion Companion")

        self.timers_page.update_language(self.language, tr)
        self.settings_page.update_language(self.language, tr)
        self.profile_page.update_language(self.language, tr)
        self.tasks_page.update_language(self.language)

        self.sidebar.update_language(self.language, tr)
        self.header.update_language(self.language, tr)

        self.refresh()

    def change_language_from_page(self, language: str):
        self.language = language
        self.apply_language()
        self.save_profile()

    def apply_theme(self, theme):
        self.current_theme = theme

        if hasattr(self, "background"):
            self.background.set_theme(theme)
            if hasattr(self, "theme_logo_label"):
                self.update_theme_logo()
            self.background.setProperty("theme", theme)

        for widget in self.findChildren(QWidget):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

        self.update()

    def show_toast(self, text):
        self.toast_label.setText(f"✓ {text}")
        self.toast_label.show()

        QTimer.singleShot(
            2200,
            self.toast_label.hide
        )

    def reset_tasks_for_tabs(self, tabs):
        for tab in tabs:
            for card in self.task_lists.get(tab, []):
                card.set_completed(False)

        self.refresh()
        self.save_profile()


    def check_auto_resets(self):
        now = datetime.now()

        # ===== DAILY RESET =====
        daily_hour, daily_minute = map(int, self.daily_reset_time.split(":"))

        daily_reset_time_today = now.replace(
            hour=daily_hour,
            minute=daily_minute,
            second=0,
            microsecond=0
        )

        if now >= daily_reset_time_today:
            if self.last_daily_reset_date != now.date():
                self.reset_tasks_for_tabs([
                    "dailyTasks",
                    "dailyShopping"
                ])

                self.last_daily_reset_date = now.date()

        # ===== WEEKLY RESET =====
        day_map = {
            "Mo": 0,
            "Di": 1,
            "Mi": 2,
            "Do": 3,
            "Fr": 4,
            "Sa": 5,
            "So": 6,

            "Tue": 1,
            "Wed": 2,
            "Thu": 3,
            "Fri": 4,
            "Sat": 5,
            "Sun": 6,
        }

        weekly_hour, weekly_minute = map(int, self.weekly_reset_time.split(":"))
        target_weekday = day_map.get(self.weekly_reset_day, 0)

        weekly_reset_time_today = now.replace(
            hour=weekly_hour,
            minute=weekly_minute,
            second=0,
            microsecond=0
        )

        if now.weekday() == target_weekday and now >= weekly_reset_time_today:
            if self.last_weekly_reset_date != now.date():
                self.reset_tasks_for_tabs([
                    "weeklyTasks",
                    "weeklyShopping"
                ])

                self.last_weekly_reset_date = now.date()

    def handle_sidebar_page_changed(self, page_key: str):
        print("Sidebar clicked:", page_key)

        if page_key in self.page_indexes:
            self.page_stack.setCurrentIndex(self.page_indexes[page_key])

        if page_key == "tasks":
            self.show_toast(tr(self.language, "toast_tasks_opened"))

        elif page_key == "timers":
            self.show_toast(tr(self.language, "toast_timers_opened"))

        elif page_key == "settings":
            self.show_toast(tr(self.language, "toast_settings_opened"))

        elif page_key == "profile":
            self.profile_page.set_profile_name(self.profile_name)
            self.show_toast(
                tr(self.language, "toast_profile_opened", name=self.profile_name)
            )

    def add_task_from_page(self, title: str, description: str):
        card = TaskCard(title, description)
        self.task_lists[self.active_tab].insert(0, card)
        self.refresh()

    def set_profile_name(self, profile_name: str):
        if profile_name:
            self.profile_name = profile_name
            self.profile_page.set_profile_name(profile_name)

    def change_theme_from_page(self, theme: str):
        self.apply_theme(theme)
        self.save_profile()

    def _setup_theme_logo(self):
        self.theme_logo_label = QLabel()
        self.theme_logo_label.setObjectName("themeLogo")
        self.theme_logo_label.setFixedSize(210, 170)
        self.theme_logo_label.setAlignment(Qt.AlignCenter)

        self.update_theme_logo()

    def update_theme_logo(self):
        logo_path = self.project_root / THEME_LOGOS.get(
            self.current_theme,
            THEME_LOGOS["abyss"]
        )

        pixmap = QPixmap(str(logo_path))

        if pixmap.isNull():
            self.theme_logo_label.clear()
            return

        scaled = pixmap.scaled(
            170,
            170,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.theme_logo_label.setPixmap(scaled)
        self.theme_logo_label.setAlignment(Qt.AlignCenter)

    def change_daily_reset_from_page(self, value: str):
        self.daily_reset_time = value
        self.update_countdowns()
        self.save_profile()


    def change_weekly_reset_day_from_page(self, value: str):
        self.weekly_reset_day = value
        self.update_countdowns()
        self.save_profile()


    def change_weekly_reset_time_from_page(self, value: str):
        self.weekly_reset_time = value
        self.update_countdowns()
        self.save_profile()

    def apply_settings_from_page(self, data: dict):
        self.language = data.get("language", self.language)
        self.apply_language()

        self.auto_save = data.get("auto_save", self.auto_save)

        theme = data.get("theme", self.current_theme)
        self.apply_theme(theme)

        self.daily_reset_time = data.get(
            "daily_reset_time",
            self.daily_reset_time
        )

        self.weekly_reset_day = data.get(
            "weekly_reset_day",
            self.weekly_reset_day
        )

        self.weekly_reset_time = data.get(
            "weekly_reset_time",
            self.weekly_reset_time
        )

        self.show_events = data.get(
            "show_events",
            self.show_events
        )

        self.toggle_events()

        self.update_countdowns()
        self.save_profile()

        self.show_toast(
            tr(self.language, "settings_saved")
        )

        self.shugo_enabled = data.get(
            "shugo_enabled",
            self.shugo_enabled
        )

        self.shugo_start_minute = data.get(
            "shugo_start_minute",
            self.shugo_start_minute
        )

        self.shugo_interval_text = data.get(
            "shugo_interval_text",
            self.shugo_interval_text
        )

        self.shugo_interval_minutes = self.interval_text_to_minutes(
            self.shugo_interval_text
        )

        self.riss_enabled = data.get(
            "riss_enabled",
            self.riss_enabled
        )

        self.riss_anchor_hour = data.get(
            "riss_anchor_hour",
            self.riss_anchor_hour
        )

        self.riss_interval_text = data.get(
            "riss_interval_text",
            self.riss_interval_text
        )

        self.riss_interval_hours = self.interval_text_to_hours(
            self.riss_interval_text
        )

        self.timers_page.set_shugo_visible(self.shugo_enabled)
        self.timers_page.set_riss_visible(self.riss_enabled)

    def change_theme_from_page(self, theme: str):
        self.apply_theme(theme)
        self.save_profile()

    def sync_settings_page(self):
        if not hasattr(self, "settings_page"):
            return

        self.settings_page.set_values({
            "language": self.language,
            "theme": self.current_theme,

            "show_events": self.show_events,

            "daily_reset_time": self.daily_reset_time,
            "weekly_reset_day": self.weekly_reset_day,
            "weekly_reset_time": self.weekly_reset_time,

            "shugo_enabled": self.shugo_enabled,
            "shugo_start_minute": self.shugo_start_minute,
            "shugo_interval_text": self.shugo_interval_text,

            "riss_enabled": self.riss_enabled,
            "riss_anchor_hour": self.riss_anchor_hour,
            "riss_interval_text": self.riss_interval_text,

            "auto_save": self.auto_save,
        })