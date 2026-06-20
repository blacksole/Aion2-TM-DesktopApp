import glob
import json
import os
import shutil
import sys
import winsound
from pathlib import Path
from .settings_dialog import SettingsDialog
from .update_dialog import UpdateDialog
from .widgets.header_widget import HeaderWidget
from .widgets.sidebar_widget import SidebarWidget
from .widgets.shopping_card import ShoppingCard
from .pages.tasks_page import TasksPage
from .pages.timers_page import TimersPage
from .pages.profile_page import ProfilePage
from .pages.settings_page import SettingsPage
from .pages.dashboard_page import DashboardPage
from .flow.flow_app_window import FlowMapWindow
from .overlay.overlay_window import OverlayWindow
from core.translations import tr
from core.update_checker import UpdateChecker
from PySide6.QtWidgets import QTimeEdit
from PySide6.QtGui import QIcon, QPainter, QLinearGradient, QColor, Qt, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMenu, QComboBox, QStackedWidget, QFileDialog, QMessageBox,
    QSystemTrayIcon,
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
    def __init__(self, title, description="", priority="low", is_event=False):
        super().__init__()

        self.completed = False
        self.is_event = is_event
        self.setProperty("event", self.is_event)
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

        title_row = QHBoxLayout()

        if self.is_event:
            self.event_badge = QLabel("EVENT")
            self.event_badge.setObjectName("eventBadge")
            title_row.addWidget(self.event_badge)

        title_row.addWidget(self.title_label)
        title_row.addStretch()

        text_box.addLayout(title_row)

        if description:
            text_box.addWidget(self.desc_label)

        self.priority_value = priority
        self.priority = QLabel(priority.upper())
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
        self._pending_update = None
        self._checker = None


        self.tabs = {
            "dailyTasks": "daily_tasks",
            "weeklyTasks": "weekly_tasks",
            "dailyShopping": "daily_shopping",
            "weeklyShopping": "weekly_shopping",
        }

        self.language = "en"
        self.current_theme = "abyss"

        self.active_tab = "dailyTasks"
        self.active_filter = "all"
        self.show_events = True
        self.daily_reset_time = "09:00"
        self.weekly_reset_day = "Mo"
        self.weekly_reset_time = "09:00"
        self.last_daily_reset_date = None
        self.last_weekly_reset_date = None
        self.profile_name = "Default"
        if getattr(sys, "frozen", False):
            self.project_root = Path(sys.executable).parent
        else:
            self.project_root = Path(__file__).resolve().parent.parent
        self.app_config_dir = Path(os.environ["APPDATA"]) / "Aion2 TM"
        self.app_config_path = self.app_config_dir / "config.json"
        self.app_config_dir.mkdir(parents=True, exist_ok=True)

        self.profile_dir = self._resolve_profile_dir()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
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

        self.notification_enabled = False
        self.notification_warn_minutes = 1
        self.notification_sound = ""
        self._shugo_notified = False
        self._riss_notified = False

        self.weekly_reset_day = "Mo"

        self.task_lists = {
            key: [] for key in self.tabs
        }

        self.flow_map_window = FlowMapWindow(self, language=self.language, tr_func=tr)

        self.setup_ui()
        self.overlay = OverlayWindow(self)
        self.load_styles()
        self.apply_language()
        self.sync_settings_page()
        self.refresh()
        self.sort_current_list("priority")

        self.load_last_profile()

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdowns)
        self.countdown_timer.start(1000)

        self._setup_tray_icon()
        self.update_countdowns()

    def _wire_card(self, card):
        card.check_btn.clicked.connect(self._on_task_toggled)

    def _on_task_toggled(self):
        self.refresh()
        if self.auto_save:
            self.save_profile(silent=True)

    def _toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide()
            self.overlay_toggle_btn.setChecked(False)
        else:
            self.overlay.refresh()
            self.overlay.show()
            self.overlay.raise_()
            self.overlay_toggle_btn.setChecked(True)

    def open_flow_map_window(self):
        if self.flow_map_window is None:
            self.flow_map_window = FlowMapWindow(self)

        self.flow_map_window.show()
        self.flow_map_window.raise_()
        self.flow_map_window.activateWindow()
        self.flow_map_window.render_flow()


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
        icon_path = self.project_root / "assets" / "icons" / "aion2_tm_icon.ico"
        self.setWindowIcon(QIcon(str(icon_path)))

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

        self.overlay_toggle_btn = QPushButton("⬛  Overlay")
        self.overlay_toggle_btn.setObjectName("overlayToggleBtn")
        self.overlay_toggle_btn.setCheckable(True)
        self.overlay_toggle_btn.clicked.connect(self._toggle_overlay)
        self.left_layout.addWidget(self.overlay_toggle_btn)

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

        if hasattr(self.profile_page, "profile_name_changed"):
            self.profile_page.profile_name_changed.connect(
                self.set_profile_name
            )

        if hasattr(self.header, "settings_requested"):
            self.header.settings_requested.connect(self.open_settings)

        if hasattr(self.header, "main_menu_requested"):
            self.header.main_menu_requested.connect(self.open_main_menu)

        if hasattr(self.settings_page, "settings_save_requested"):
            self.settings_page.settings_save_requested.connect(
                self.apply_settings_from_page
            )

        if hasattr(self.profile_page, "save_profile_btn"):
            self.profile_page.save_profile_btn.clicked.connect(
                self.save_profile_from_profile_page
            )

        if hasattr(self.profile_page, "reset_profile_btn"):
            self.profile_page.reset_profile_btn.clicked.connect(
                self.reset_profile
            )

        if hasattr(self.profile_page, "load_profile_btn"):
            self.profile_page.load_profile_btn.clicked.connect(
                self.open_profile_menu
            )

        if hasattr(self.profile_page, "clear_events_btn"):
            self.profile_page.clear_events_btn.clicked.connect(
                self.clear_event_entries
            )

        if hasattr(self.profile_page, "export_requested"):
            self.profile_page.export_requested.connect(self.export_profile)

        if hasattr(self.profile_page, "import_requested"):
            self.profile_page.import_requested.connect(self.import_profile)
            
        
        self.tasks_page.sort_requested.connect(self.sort_current_list)
        self.tasks_page.filter_changed.connect(self.set_task_filter)

        if hasattr(self.header, "update_btn_clicked"):
            self.header.update_btn_clicked.connect(self._open_update_dialog)

        if hasattr(self.settings_page, "check_update_requested"):
            self.settings_page.check_update_requested.connect(self._on_manual_update_check)

        if hasattr(self.settings_page, "profile_dir_changed"):
            self.settings_page.profile_dir_changed.connect(self.change_profile_dir)

        QTimer.singleShot(2000, self.run_update_check)

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
            if self.notification_enabled:
                warn_secs = self.notification_warn_minutes * 60
                if not self._shugo_notified and 0 < seconds <= warn_secs:
                    self._shugo_notified = True
                    self._fire_notification(
                        "Shugo",
                        f"Shugo spawnt in {self.notification_warn_minutes} Min!"
                    )
                elif seconds > warn_secs:
                    self._shugo_notified = False

        if self.riss_enabled:
            next_riss = self.get_next_riss_time()
            seconds = (next_riss - now).total_seconds()
            riss_text = self.format_countdown(seconds)
            self.timers_page.set_riss_countdown(riss_text)
            if self.notification_enabled:
                warn_secs = self.notification_warn_minutes * 60
                if not self._riss_notified and 0 < seconds <= warn_secs:
                    self._riss_notified = True
                    self._fire_notification(
                        "Riss",
                        f"Riss öffnet sich in {self.notification_warn_minutes} Min!"
                    )
                elif seconds > warn_secs:
                    self._riss_notified = False

        self.check_auto_resets()

    def select_tab(self, tab):
        self.active_tab = tab

        self.refresh()

    def refresh(self):

        tasks = self.task_lists[self.active_tab]

        if self.active_filter == "event":
            tasks = [
                task for task in tasks
                if getattr(task, "is_event", False)
            ]

        if not self.show_events:
            tasks = [
                task for task in tasks
                if not getattr(task, "is_event", False)
            ]

        self.tasks_page.render_tasks(tasks)
        total = len(tasks)
        done = len([t for t in tasks if t.completed])

        open_count = total - done

        progress = round(
            (done / total) * 100
        ) if total else 0

        shopping_tabs = [
            "dailyShopping",
            "weeklyShopping",
        ]

        total_kinah_k = 0

        if self.active_tab in shopping_tabs:
            for card in tasks:
                if isinstance(card, ShoppingCard):
                    try:
                        amount = int(
                            str(card.amount).strip() or 1
                        )

                        price_k = float(
                            str(card.price).replace(",", ".").strip() or 0
                        )

                        total_kinah_k += amount * price_k

                    except ValueError:
                        pass

        self.tasks_page.update_stats(total, done, open_count)

        self.tasks_page.set_footer_text(
            f"● {tr(self.language, 'progress')}: {progress}%"
        )

        shopping_total_labels = {
            "dailyShopping": "daily_total_price",
            "weeklyShopping": "weekly_total_price",
            "eventShopping": "event_total_price",
        }

        if self.active_tab in shopping_total_labels:
            self.tasks_page.set_footer_text(
                f"● {tr(self.language, 'progress')}: {progress}%   |   "
                f"{tr(self.language, shopping_total_labels[self.active_tab])}: "
                f"{self.format_kinah_price(total_kinah_k)}"
            )
        else:
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

        if hasattr(self, "overlay") and self.overlay.isVisible():
            self.overlay.refresh()

    def load_styles(self):
        style_path = (
            Path(__file__).resolve().parent / "styles.qss"
        )

        with open(style_path, "r", encoding="utf-8") as f:
            styles = f.read()

        base_path = Path(__file__).resolve().parent.parent

        styles = styles.replace(
            "ASSET_PATH",
            base_path.as_posix()
        )

        self.setStyleSheet(styles)

    def toggle_events(self):
        self.tasks_page.set_event_features_visible(
            self.show_events
        )

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


    def _setup_tray_icon(self):
        icon = self.windowIcon()
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.show()

    def _fire_notification(self, title: str, message: str):
        if hasattr(self, "tray_icon"):
            self.tray_icon.showMessage(
                title, message,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )
        if self.notification_sound and os.path.isfile(self.notification_sound):
            winsound.PlaySound(
                self.notification_sound,
                winsound.SND_FILENAME | winsound.SND_ASYNC,
            )

    @staticmethod
    def get_windows_sounds() -> dict:
        sounds = {"-- Kein Sound --": ""}
        for path in sorted(glob.glob(r"C:\Windows\Media\*.wav")):
            name = os.path.splitext(os.path.basename(path))[0]
            sounds[name] = path
        return sounds

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
        self.notification_enabled = settings.get("notification_enabled", False)
        self.notification_warn_minutes = settings.get("notification_warn_minutes", 1)
        self.notification_sound = settings.get("notification_sound", "")
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

        if isinstance(data, dict):
            saved_tasks = data.get("tasks", {})

        # ===== MIGRATION OLD EVENT TABS =====

        old_event_tasks = saved_tasks.get("eventTasks", [])
        old_event_shopping = saved_tasks.get("eventShopping", [])

        if old_event_tasks:
            saved_tasks.setdefault("dailyTasks", [])

            for item in old_event_tasks:
                item["event"] = True

            saved_tasks["dailyTasks"].extend(
                old_event_tasks
            )

        if old_event_shopping:
            saved_tasks.setdefault("dailyShopping", [])

            for item in old_event_shopping:
                item["event"] = True

            saved_tasks["dailyShopping"].extend(
                old_event_shopping
            )

        for tab, items in saved_tasks.items():

            if tab not in self.task_lists:
                continue

            for item in items:

                if item.get("type") == "shopping":

                    card = ShoppingCard(
                        priority=item.get("priority", "middle"),
                        amount=str(item.get("amount", "1")),
                        title=item.get("title", ""),
                        location=item.get("location", ""),
                        price=item.get("price", "0"),
                        is_event=item.get("event", False),
                    )

                else:
                    card = TaskCard(
                        item.get("title", ""),
                        item.get("description", ""),
                        item.get("priority", "middle"),
                        item.get("event", False),
                    )

                if item.get("completed", False):
                    card.set_completed(True)

                self._wire_card(card)
                self.task_lists[tab].append(card)

        self.refresh()
        if self.flow_map_window:
            self.flow_map_window.load_flow_data(data.get("flow_map", {}))
        if hasattr(self.header, "set_profile"):
            self.header.set_profile(self.profile_name)
        self.save_last_profile(profile_path)
        print("Profil geladen:", self.profile_name)

    def serialize_card(self, card):
        if isinstance(card, ShoppingCard):
            return {
                "type": "shopping",
                "priority": card.priority,
                "amount": card.amount,
                "title": card.title,
                "location": card.location,
                "price": card.price,
                "event": getattr(card, "is_event", False),
                "completed": card.completed,
            }

        return {
            "type": "task",
            "priority": getattr(card, "priority_value", "low"),
            "title": card.title_label.text(),
            "description": card.desc_label.text(),
            "event": getattr(card, "is_event", False),
            "completed": card.completed,
        }
    
    def save_profile(self, silent=False):
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

                "notification_enabled": self.notification_enabled,
                "notification_warn_minutes": self.notification_warn_minutes,
                "notification_sound": self.notification_sound,
            },

            "tasks": {
                tab: [
                    self.serialize_card(card)
                    for card in cards
                ]
                for tab, cards in self.task_lists.items()
            },

            "flow_map": self.flow_map_window.get_flow_data() if self.flow_map_window else {},
        }

        profile_path = self.profile_dir / f"{self.profile_name}.json"

        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        self.save_last_profile(profile_path)

        print("Profil gespeichert:", profile_path)
        if not silent:
            self.show_toast(tr(self.language, "profile_saved"))

    def _resolve_profile_dir(self) -> Path:
        # 1. User hat explizit einen Pfad gesetzt → immer bevorzugen
        if self.app_config_path.exists():
            try:
                cfg = json.loads(self.app_config_path.read_text(encoding="utf-8"))
                custom = cfg.get("profile_dir", "")
                if custom:
                    p = Path(custom)
                    if p.exists():
                        return p
            except Exception:
                pass

        # 2. Bestehender profiles-Ordner neben der App / EXE
        local_dir = self.project_root / "profiles"
        if local_dir.exists():
            return local_dir

        # 3. Neue Installation → AppData
        return Path(os.environ["APPDATA"]) / "Aion2 TM" / "Profiles"

    def _save_app_config(self):
        cfg = {"profile_dir": str(self.profile_dir)}
        self.app_config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    def change_profile_dir(self, new_path: str):
        new_dir = Path(new_path)
        new_dir.mkdir(parents=True, exist_ok=True)
        for f in self.profile_dir.glob("*.json"):
            dest = new_dir / f.name
            if not dest.exists():
                shutil.copy2(f, dest)
        self.profile_dir = new_dir
        self.last_profile_file = self.profile_dir / "last_profile.txt"
        self._save_app_config()
        if hasattr(self, "settings_page"):
            self.settings_page.update_profile_dir_label(str(self.profile_dir))
        self.show_toast("Profilpfad gespeichert")

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
        box = QMessageBox(self)
        box.setWindowTitle(tr(self.language, "confirm_reset_title"))
        box.setText(tr(self.language, "confirm_reset_text"))
        yes_btn = box.addButton(tr(self.language, "confirm_yes"), QMessageBox.DestructiveRole)
        box.addButton(tr(self.language, "confirm_no"), QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is not yes_btn:
            return

        self.task_lists = {key: [] for key in self.tabs}
        self.refresh()
        self.save_profile(silent=True)

    def clear_event_entries(self):
        box = QMessageBox(self)
        box.setWindowTitle(tr(self.language, "confirm_clear_events_title"))
        box.setText(tr(self.language, "confirm_clear_events_text"))
        yes_btn = box.addButton(tr(self.language, "confirm_yes"), QMessageBox.DestructiveRole)
        box.addButton(tr(self.language, "confirm_no"), QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is not yes_btn:
            return

        for tab in self.task_lists:
            self.task_lists[tab] = [
                card for card in self.task_lists[tab]
                if not getattr(card, "is_event", False)
            ]

        self.refresh()

        if self.auto_save:
            self.save_profile(silent=True)

        self.show_toast(tr(self.language, "event_entries_removed"))

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

        elif page_key == "plan":
            self.open_flow_map_window()
            self.show_toast(tr(self.language, "toast_plan_opened"))

        elif page_key == "settings":
            self.show_toast(tr(self.language, "toast_settings_opened"))

        elif page_key == "profile":
            self.profile_page.set_profile_name(self.profile_name)
            self.show_toast(
                tr(self.language, "toast_profile_opened", name=self.profile_name)
            )

    def add_task_from_page(self, data):
        shopping_tabs = [
            "dailyShopping",
            "weeklyShopping",
        ]

        if self.active_tab in shopping_tabs:
            card = ShoppingCard(
                priority=data.get("priority", "middle"),
                amount=str(data.get("amount", "1")),
                title=data.get("title", ""),
                location=data.get("location", ""),
                price=data.get("price", "0"),
                is_event=data.get("event", False),
            )
        else:
            card = TaskCard(
                data.get("title", ""),
                data.get("description", ""),
                data.get("priority", "middle"),
                data.get("event", False),
            )

        self._wire_card(card)
        self.task_lists[self.active_tab].insert(0, card)
        self.refresh()

        if self.auto_save:
            self.save_profile(silent=True)

    def set_profile_name(self, profile_name: str):
        if not profile_name or profile_name == self.profile_name:
            return
        old_name = self.profile_name
        old_path = self.profile_dir / f"{old_name}.json"
        self.profile_name = profile_name
        self.profile_page.set_profile_name(profile_name)
        if hasattr(self.header, "set_profile"):
            self.header.set_profile(profile_name)
        self.save_profile(silent=True)
        if old_name == "Default":
            self._create_default_profile()
        elif old_path.exists():
            old_path.unlink(missing_ok=True)

    def _create_default_profile(self):
        default_path = self.profile_dir / "Default.json"
        if not default_path.exists():
            import json as _json
            _json.dump(
                {"profile_name": "Default", "theme": self.current_theme,
                 "language": self.language, "tasks": {
                     "dailyTasks": [], "weeklyTasks": [],
                     "dailyShopping": [], "weeklyShopping": []},
                 "flow_map": {}},
                open(default_path, "w", encoding="utf-8"),
                indent=4, ensure_ascii=False,
            )

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
        self.save_profile(silent=True)

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

        self.notification_enabled = data.get("notification_enabled", self.notification_enabled)
        self.notification_warn_minutes = data.get("notification_warn_minutes", self.notification_warn_minutes)
        self.notification_sound = data.get("notification_sound", self.notification_sound)

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

            "notification_enabled": self.notification_enabled,
            "notification_warn_minutes": self.notification_warn_minutes,
            "notification_sound": self.notification_sound,

            "profile_dir": str(self.profile_dir),
        })


    def sort_current_list(self, sort_data):
        if isinstance(sort_data, dict):
            sort_key = sort_data.get("key", "priority")
            direction = sort_data.get("direction", "desc")
        else:
            sort_key = sort_data
            direction = "desc"

        reverse = direction == "desc"
        priority_order = {
            "high": 0,
            "middle": 1,
            "low": 2,
        }

        def get_card_value(card):
            if sort_key == "priority":
                if isinstance(card, ShoppingCard):
                    return priority_order.get(card.priority, 99)

                return priority_order.get(
                    getattr(card, "priority_value", "middle"),
                    99
                )

            if sort_key == "title":
                if isinstance(card, ShoppingCard):
                    return card.title.lower()

                return card.title_label.text().lower()

            if sort_key == "location":
                if isinstance(card, ShoppingCard):
                    return card.location.lower()

                return card.desc_label.text().lower()

            if sort_key == "price":
                if isinstance(card, ShoppingCard):
                    try:
                        return float(
                            str(card.price)
                            .replace("€", "")
                            .replace(",", ".")
                            .strip()
                        )
                    except ValueError:
                        return 0

                return 0

            return ""

        self.task_lists[self.active_tab].sort(
            key=get_card_value,
            reverse=reverse
        )

        self.refresh()

    def save_profile_from_profile_page(self):
        if hasattr(self.profile_page, "get_profile_name"):
            profile_name = self.profile_page.get_profile_name()

            if profile_name:
                self.set_profile_name(profile_name)

        self.save_profile()

    def format_kinah_price(self, value):
        try:
            kinah = float(str(value).replace(",", ".").strip()) * 1000
        except ValueError:
            kinah = 0

        if kinah >= 1_000_000:
            millions = kinah / 1_000_000
            return f"{millions:g}m Kinah"

        if kinah >= 1_000:
            thousands = kinah / 1_000
            return f"{thousands:g}k Kinah"

        return f"{int(kinah)} Kinah"
    
    def set_task_filter(self, filter_key):
        self.active_filter = filter_key
        self.refresh()

    def run_update_check(self):
        self._checker = UpdateChecker()
        self._checker.update_available.connect(self._on_update_available)
        self._checker.up_to_date.connect(lambda: None)
        self._checker.start()

    def _on_update_available(self, version: str, body: str):
        self._pending_update = (version, body)
        if hasattr(self.header, "show_update"):
            self.header.show_update(version)

    def _open_update_dialog(self):
        if not self._pending_update:
            return
        version, body = self._pending_update
        app_root = self.project_root
        dlg = UpdateDialog(version, body, app_root, parent=self)
        dlg.exec()

    def _on_manual_update_check(self):
        self._checker = UpdateChecker()
        self._checker.update_available.connect(self._on_update_available)
        self._checker.up_to_date.connect(
            lambda: self.show_toast(tr(self.language, "up_to_date_toast"))
        )
        self._checker.start()

    def closeEvent(self, event):
        self.save_profile(silent=True)
        event.accept()

    def export_profile(self):
        self.save_profile(silent=True)
        src = self.profile_dir / f"{self.profile_name}.json"
        dest, _ = QFileDialog.getSaveFileName(
            self,
            tr(self.language, "export_profile"),
            str(Path.home() / f"{self.profile_name}.json"),
            "JSON Profile (*.json)",
        )
        if not dest:
            return
        import shutil
        shutil.copy2(src, dest)
        self.show_toast(tr(self.language, "profile_exported"))

    def import_profile(self):
        src, _ = QFileDialog.getOpenFileName(
            self,
            tr(self.language, "import_profile"),
            str(Path.home()),
            "JSON Profile (*.json)",
        )
        if not src:
            return
        try:
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError
        except Exception:
            self.show_toast(tr(self.language, "profile_import_error"))
            return
        import shutil
        dest = self.profile_dir / Path(src).name
        shutil.copy2(src, dest)
        self.load_profile(dest)
        self.show_toast(tr(self.language, "profile_imported"))