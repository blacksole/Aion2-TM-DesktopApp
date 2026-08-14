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
from .widgets.template_dialog import TemplateDialog
from .pages.tasks_page import TasksPage
from .pages.timers_page import TimersPage
from .pages.profile_page import ProfilePage
from .pages.settings_page import SettingsPage
from .pages.dashboard_page import DashboardPage
from .pages.about_page import AboutPage
from .flow.flow_app_window import FlowMapWindow
from .overlay.overlay_window import OverlayWindow
from core.translations import tr
from core.update_checker import UpdateChecker
from PySide6.QtWidgets import QTimeEdit
from PySide6.QtGui import QIcon, QPainter, QLinearGradient, QColor, Qt, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMenu, QComboBox, QStackedWidget, QFileDialog, QMessageBox,
    QSystemTrayIcon, QInputDialog,
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
    def __init__(self, title, description="", priority="low", is_event=False,
                 schedule="daily", character=""):
        super().__init__()

        self.completed = False
        self.is_event = is_event
        self.schedule = schedule
        self.character = character
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
        text_box.setSpacing(2)

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
        text_box.addWidget(self.desc_label)
        if not description:
            self.desc_label.hide()

        # Schedule badge row
        _sched_texts = {"daily": "DAILY", "weekly": "WEEKLY", "season": "SEASON"}
        _sched_names = {"daily": "scheduleDaily", "weekly": "scheduleWeekly", "season": "scheduleSeason"}
        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
        self.schedule_label = QLabel(_sched_texts.get(schedule, schedule.upper()))
        self.schedule_label.setObjectName(_sched_names.get(schedule, "scheduleDaily"))
        badge_row.addWidget(self.schedule_label)
        if character:
            self.char_label = QLabel(character)
            self.char_label.setObjectName("scheduleWeekly")
            badge_row.addWidget(self.char_label)
        badge_row.addStretch()
        text_box.addLayout(badge_row)

        self.priority_value = priority
        self.priority = QLabel(priority.upper())
        self.priority.setObjectName("priorityMedium")

        self.delete_btn = QPushButton("×")
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
    def __init__(self):
        super().__init__()

        self.auto_save = True
        self._pending_update = None
        self._checker = None


        self.tabs = {
            "tasks": "tasks",
            "shopping": "shopping",
        }

        self.language = "en"
        self.current_theme = "abyss"

        self.active_tab = "tasks"
        self.active_filter = "all"
        self.show_events = True
        self.daily_reset_time = "09:00"
        self.weekly_reset_day = "Mo"
        self.weekly_reset_time = "09:00"
        self.season_reset_datetime = ""
        self.last_daily_reset_date = None
        self.last_weekly_reset_date = None
        self._daily_countdown_text = "--:--:--"
        self._weekly_countdown_text = "--:--:--"
        self.profile_name = "Default"
        if getattr(sys, "frozen", False):
            self.project_root = Path(sys.executable).parent
        else:
            self.project_root = Path(__file__).resolve().parent.parent
        if getattr(sys, "frozen", False):
            self.app_config_dir = Path(os.environ["APPDATA"]) / "Aion2 TM"
        else:
            self.app_config_dir = self.project_root
        self.app_config_path = self.app_config_dir / "config.json"
        self.app_config_dir.mkdir(parents=True, exist_ok=True)

        self.dps_meter_path = ""
        self.dps_meter_autostart = False
        self.minimize_to_tray = None  # None = not asked yet
        self._avatar_b64 = ""
        self.characters: list = []

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
        self.notification_sync = True
        self.notification_shugo_enabled = False
        self.notification_shugo_warn_minutes = 1
        self.notification_riss_enabled = False
        self.notification_riss_warn_minutes = 1
        self.notification_sound = ""
        self._shugo_notified = False
        self._riss_notified = False

        self.custom_timers = []
        self.timer_categories = ["Custom Timer"]
        self._custom_notified = [False] * 8

        self.weekly_reset_day = "Mo"

        self.task_lists = {
            key: [] for key in self.tabs
        }

        self.item_templates: list = []
        self.task_templates: list = []

        self.flow_maps: dict = {}
        self.active_flow_map_name: str = "Map 1"

        self.flow_map_window = FlowMapWindow(self, language=self.language, tr_func=tr)
        self.flow_map_window.map_switch_requested.connect(self._switch_flow_map)
        self.flow_map_window.map_add_requested.connect(self._add_flow_map)
        self.flow_map_window.map_delete_requested.connect(self._delete_flow_map)
        self.flow_map_window.map_reset_requested.connect(self._reset_flow_map)
        self.flow_map_window.root_renamed.connect(self._on_flow_map_root_renamed)
        self.flow_map_window.map_overlay_changed.connect(self._on_flow_map_overlay_changed)

        self.setup_ui()
        self.overlay = OverlayWindow(self)
        self.load_styles()
        self.apply_language()
        self.sync_settings_page()
        self.refresh()
        self.sort_current_list("priority")

        if not self.app_config_path.exists() and getattr(sys, "frozen", False):
            self._show_first_run_dialog()
        else:
            self.load_last_profile()

        # Pre-create the native OS window handle so first show() has no flash
        if self.flow_map_window:
            self.flow_map_window.winId()

        self._launch_dps_meter_if_configured()

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdowns)
        self.countdown_timer.start(1000)

        self._editing_card = None
        self._setup_tray_icon()
        self.update_countdowns()

    def _wire_card(self, card):
        card.check_btn.clicked.connect(self._on_task_toggled)
        card.delete_btn.clicked.disconnect()
        card.delete_btn.clicked.connect(lambda checked=False, c=card: self._delete_card(c))
        card.setCursor(Qt.PointingHandCursor)

        def on_press(event, c=card):
            if event.button() == Qt.LeftButton:
                child = c.childAt(event.pos())
                if not isinstance(child, QPushButton):
                    if self._editing_card is c:
                        self._cancel_edit()
                    else:
                        self._start_editing(c)
            type(c).mousePressEvent(c, event)

        card.mousePressEvent = on_press

    def _on_task_toggled(self):
        self.refresh()
        if self.auto_save:
            self.save_profile(silent=True)

    def _delete_card(self, card):
        if self._editing_card is card:
            self._cancel_edit()
        for cards in self.task_lists.values():
            if card in cards:
                cards.remove(card)
                break
        if isinstance(card, ShoppingCard):
            title_lower = card.title.lower()
            for tmpl in self.item_templates:
                if tmpl.get("title", "").lower() == title_lower:
                    tmpl["is_general"] = False
                    break
        elif isinstance(card, TaskCard):
            title_lower = card.title_label.text().lower()
            for tmpl in self.task_templates:
                if tmpl.get("title", "").lower() == title_lower:
                    tmpl["is_general"] = False
                    break
        card.deleteLater()
        self.refresh()
        if self.auto_save:
            self.save_profile(silent=True)

    def _set_card_selected(self, card, selected: bool):
        card.setProperty("selected", selected)
        card.style().unpolish(card)
        card.style().polish(card)

    def _start_editing(self, card):
        if self._editing_card is not None:
            self._set_card_selected(self._editing_card, False)
        self._editing_card = card
        self._set_card_selected(card, True)
        p = self.tasks_page
        priority_val = card.priority if isinstance(card, ShoppingCard) else card.priority_value
        idx = p.priority_input.findData(priority_val)
        p.priority_input.setCurrentIndex(idx if idx >= 0 else 0)
        p.title_input.setText(card.title if isinstance(card, ShoppingCard) else card.title_label.text())
        if isinstance(card, ShoppingCard):
            p.amount_input.setText(str(card.amount))
            p.location_input.setText(card.location)
            p.price_input.setText(str(card.price))
            sched = getattr(card, "schedule", "daily")
            p.schedule_daily_btn.setChecked(sched == "daily")
            p.schedule_weekly_btn.setChecked(sched == "weekly")
            p.schedule_season_btn.setChecked(sched == "season")
            cur = getattr(card, "currency", "kinah")
            p.currency_kinah_btn.setChecked(cur == "kinah")
            p.currency_abyss_btn.setChecked(cur == "abyss")
        else:
            p.desc_input.setText(card.desc_label.text())
            sched = getattr(card, "schedule", "daily")
            p.schedule_daily_btn.setChecked(sched == "daily")
            p.schedule_weekly_btn.setChecked(sched == "weekly")
            p.schedule_season_btn.setChecked(sched == "season")
            char = getattr(card, "character", "")
            idx = p.char_input.findData(char)
            p.char_input.setCurrentIndex(-1 if idx <= 0 else idx)
        p.add_btn.setText("Aktualisieren")
        try:
            p.add_btn.clicked.disconnect()
        except RuntimeError:
            pass
        p.add_btn.clicked.connect(self._apply_card_edit)
        try:
            p.desc_input.returnPressed.disconnect(p.emit_add_task)
        except (RuntimeError, TypeError):
            pass
        p.title_input.setFocus()

    def _apply_card_edit(self):
        card = self._editing_card
        if card is None:
            return
        p = self.tasks_page
        priority = p.priority_input.currentData()
        title = p.title_input.text().strip()
        if not title:
            return
        prio_map = {"low": "priority_low", "medium": "priority_middle", "high": "priority_high"}
        prio_text = tr(self.language, prio_map.get(priority, priority))
        if isinstance(card, ShoppingCard):
            card.priority = priority
            card.priority_label.setText(prio_text)
            card.title = title
            card.title_label.setText(title)
            card.amount = p.amount_input.text().strip() or "1"
            card.amount_label.setText(f"{card.amount}x")
            card.location = p.location_input.text().strip()
            card.price = p.price_input.text().strip() or "0"
            card.currency = p.get_selected_currency()
            card.price_display = card.format_price(card.price, card.currency)
            card.info_label.setText(f"{card.location} • {card.price_display}")
            new_schedule = p.get_selected_schedule()
            if new_schedule != card.schedule:
                card.schedule = new_schedule
                _sched_names = {"daily": "scheduleDaily", "weekly": "scheduleWeekly", "season": "scheduleSeason"}
                _sched_texts = {"daily": "DAILY", "weekly": "WEEKLY", "season": "SEASON"}
                card.schedule_label.setText(_sched_texts.get(new_schedule, new_schedule.upper()))
                card.schedule_label.setObjectName(_sched_names.get(new_schedule, "scheduleDaily"))
                card.schedule_label.style().unpolish(card.schedule_label)
                card.schedule_label.style().polish(card.schedule_label)
        else:
            card.priority_value = priority
            card.priority.setText(prio_text)
            card.title_label.setText(title)
            desc = p.desc_input.text().strip()
            card.desc_label.setText(desc)
            card.desc_label.setVisible(bool(desc))
            new_schedule = p.get_selected_schedule()
            if new_schedule != card.schedule:
                card.schedule = new_schedule
                _sched_names = {"daily": "scheduleDaily", "weekly": "scheduleWeekly", "season": "scheduleSeason"}
                _sched_texts = {"daily": "DAILY", "weekly": "WEEKLY", "season": "SEASON"}
                card.schedule_label.setText(_sched_texts.get(new_schedule, new_schedule.upper()))
                card.schedule_label.setObjectName(_sched_names.get(new_schedule, "scheduleDaily"))
                card.schedule_label.style().unpolish(card.schedule_label)
                card.schedule_label.style().polish(card.schedule_label)
            new_char = p.char_input.currentData() or ""
            card.character = new_char
            if hasattr(card, "char_label"):
                card.char_label.setText(new_char)
                card.char_label.setVisible(bool(new_char))
        self._cancel_edit()
        if self.auto_save:
            self.save_profile(silent=True)

    def _cancel_edit(self):
        if self._editing_card is not None:
            self._set_card_selected(self._editing_card, False)
        self._editing_card = None
        p = self.tasks_page
        p.add_btn.setText(tr(self.language, "add"))
        try:
            p.add_btn.clicked.disconnect()
        except RuntimeError:
            pass
        p.add_btn.clicked.connect(p.emit_add_task)
        try:
            p.desc_input.returnPressed.disconnect()
        except RuntimeError:
            pass
        p.desc_input.returnPressed.connect(p.emit_add_task)
        p.title_input.clear()
        p.desc_input.clear()
        p.amount_input.clear()
        p.location_input.clear()
        p.price_input.clear()
        p.priority_input.setCurrentIndex(1)

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
            self.flow_map_window = FlowMapWindow(self, language=self.language, tr_func=tr)
            self.flow_map_window.map_switch_requested.connect(self._switch_flow_map)
            self.flow_map_window.map_add_requested.connect(self._add_flow_map)
            self.flow_map_window.map_delete_requested.connect(self._delete_flow_map)
            self.flow_map_window.map_reset_requested.connect(self._reset_flow_map)

        self.flow_map_window.set_map_list(list(self.flow_maps.keys()) or ["Map 1"], self.active_flow_map_name)
        self.flow_map_window.render_flow()  # build cards while still hidden
        self.flow_map_window.show()
        self.flow_map_window.raise_()
        self.flow_map_window.activateWindow()

    def _switch_flow_map(self, name: str):
        if name == self.active_flow_map_name or not name:
            return
        if self.flow_map_window:
            self.flow_maps[self.active_flow_map_name] = self.flow_map_window.get_flow_data()
        self.active_flow_map_name = name
        if self.flow_map_window:
            self.flow_map_window.load_flow_data(self.flow_maps.get(name, {}))
        if self.auto_save:
            self.save_profile(silent=True)

    def _add_flow_map(self):
        i = 2
        while f"Map {i}" in self.flow_maps:
            i += 1
        name = f"Map {i}"
        if self.flow_map_window:
            self.flow_maps[self.active_flow_map_name] = self.flow_map_window.get_flow_data()
        from core.flow_model import FlowNode
        root = FlowNode(title="New Node", description="", icon="character", status="active")
        self.flow_maps[name] = {"nodes": {root.id: root.to_dict()}, "root_node_id": root.id}
        self.active_flow_map_name = name
        if self.flow_map_window:
            self.flow_map_window.load_flow_data(self.flow_maps[name])
            self.flow_map_window.set_map_list(list(self.flow_maps.keys()), name)
        if self.auto_save:
            self.save_profile(silent=True)

    def _delete_flow_map(self):
        if len(self.flow_maps) <= 1:
            QMessageBox.information(
                self.flow_map_window,
                "Map löschen",
                "Mindestens eine Map muss vorhanden bleiben.",
            )
            return
        name = self.active_flow_map_name
        reply = QMessageBox.question(
            self.flow_map_window,
            "Map löschen",
            f'Die Map "{name}" wird gelöscht. Fortfahren?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        names = list(self.flow_maps.keys())
        idx = names.index(name)
        del self.flow_maps[name]
        remaining = list(self.flow_maps.keys())
        new_active = remaining[max(0, idx - 1)]
        self.active_flow_map_name = new_active
        if self.flow_map_window:
            self.flow_map_window.load_flow_data(self.flow_maps[new_active])
            self.flow_map_window.set_map_list(remaining, new_active)
        if self.auto_save:
            self.save_profile(silent=True)

    def _reset_flow_map(self):
        reply = QMessageBox.question(
            self.flow_map_window,
            "Map zurücksetzen",
            f'Die Map "{self.active_flow_map_name}" wird geleert. Fortfahren?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        from core.flow_model import FlowNode
        root = FlowNode(title="New Node", description="", icon="character", status="active")
        empty = {"nodes": {root.id: root.to_dict()}, "root_node_id": root.id}
        self.flow_maps[self.active_flow_map_name] = empty
        if self.flow_map_window:
            self.flow_map_window.load_flow_data(empty)
        if self.auto_save:
            self.save_profile(silent=True)


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
        self.setMinimumSize(1100, 820)
        icon_path = self.project_root / "assets" / "icons" / "aion2_tm_icon.ico"
        self.setWindowIcon(QIcon(str(icon_path)))

    def _setup_header(self):
        self.header = HeaderWidget()
        if self._avatar_b64:
            self.header.set_avatar(self._avatar_b64)


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
        self.about_page = AboutPage()

        self.page_indexes = {
            "dashboard": 0,
            "tasks": 1,
            "timers": 2,
            "profile": 3,
            "settings": 4,
            "about": 5,
        }

        self.page_stack.addWidget(self.dashboard_page)
        self.page_stack.addWidget(self.tasks_page)
        self.page_stack.addWidget(self.timers_page)
        self.page_stack.addWidget(self.profile_page)
        self.page_stack.addWidget(self.settings_page)
        self.page_stack.addWidget(self.about_page)

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

        if hasattr(self.profile_page, "duplicate_requested"):
            self.profile_page.duplicate_requested.connect(self.duplicate_profile)

        self.tasks_page.sort_requested.connect(self.sort_current_list)
        self.tasks_page.filter_changed.connect(self.set_task_filter)
        self.tasks_page.manual_reset_requested.connect(self._on_manual_reset)
        self.tasks_page.template_requested.connect(self._open_template_dialog)

        if hasattr(self.header, "update_btn_clicked"):
            self.header.update_btn_clicked.connect(self._open_update_dialog)

        if hasattr(self.header, "avatar_changed"):
            self.header.avatar_changed.connect(self._on_avatar_changed)

        if hasattr(self.settings_page, "check_update_requested"):
            self.settings_page.check_update_requested.connect(self._on_manual_update_check)

        if hasattr(self.settings_page, "profile_dir_changed"):
            self.settings_page.profile_dir_changed.connect(self.change_profile_dir)

        if hasattr(self.settings_page, "season_reset_changed"):
            self.settings_page.season_reset_changed.connect(self._on_season_reset_changed_from_page)

        if hasattr(self.settings_page, "dps_start_requested"):
            self.settings_page.dps_start_requested.connect(self._start_dps_meter)

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
        self._daily_countdown_text = daily_text
        self.timers_page.set_daily_countdown(daily_text)

        weekly_next = self.get_next_weekly_reset()
        weekly_seconds = (weekly_next - now).total_seconds()
        weekly_text = self.format_reset_countdown(weekly_seconds)
        self._weekly_countdown_text = weekly_text
        self.timers_page.set_weekly_countdown(weekly_text)

        season_text = self._get_season_countdown_text()
        if season_text:
            self.timers_page.set_season_countdown(season_text)
            self.timers_page.set_season_visible(True)
        else:
            self.timers_page.set_season_visible(False)

        self._update_task_reset_hint()

        if self.shugo_enabled:
            next_shugo = self.get_next_shugo_time()
            seconds = (next_shugo - now).total_seconds()
            shugo_text = self.format_countdown(seconds)
            self.timers_page.set_shugo_countdown(shugo_text)
            if self.notification_sync:
                shugo_notif_on = self.notification_enabled
                shugo_warn_min = self.notification_warn_minutes
            else:
                shugo_notif_on = self.notification_shugo_enabled
                shugo_warn_min = self.notification_shugo_warn_minutes
            if shugo_notif_on:
                warn_secs = shugo_warn_min * 60
                check_secs = warn_secs if warn_secs > 0 else 10
                if not self._shugo_notified and 0 <= seconds <= check_secs:
                    self._shugo_notified = True
                    msg = "Shugo spawnt jetzt!" if shugo_warn_min == 0 else f"Shugo spawnt in {shugo_warn_min} Min!"
                    self._fire_notification("Shugo", msg)
                elif seconds > check_secs:
                    self._shugo_notified = False

        if self.riss_enabled:
            next_riss = self.get_next_riss_time()
            seconds = (next_riss - now).total_seconds()
            riss_text = self.format_countdown(seconds)
            self.timers_page.set_riss_countdown(riss_text)
            if self.notification_sync:
                riss_notif_on = self.notification_enabled
                riss_warn_min = self.notification_warn_minutes
            else:
                riss_notif_on = self.notification_riss_enabled
                riss_warn_min = self.notification_riss_warn_minutes
            if riss_notif_on:
                warn_secs = riss_warn_min * 60
                check_secs = warn_secs if warn_secs > 0 else 10
                if not self._riss_notified and 0 <= seconds <= check_secs:
                    self._riss_notified = True
                    msg = "Riss öffnet sich jetzt!" if riss_warn_min == 0 else f"Riss öffnet sich in {riss_warn_min} Min!"
                    self._fire_notification("Riss", msg)
                elif seconds > check_secs:
                    self._riss_notified = False

        for i, ct in enumerate(self.custom_timers[:8]):
            if ct.get("enabled") and ct.get("name"):
                mode = ct.get("timer_mode", "hourly")
                if mode == "daily":
                    next_ct = self._get_next_daily_custom_time(ct.get("reset_time", "09:00"))
                    seconds = (next_ct - now).total_seconds()
                    ct_text = self.format_reset_countdown(seconds)
                elif mode == "weekly":
                    next_ct = self._get_next_weekly_custom_time(
                        ct.get("reset_day", "Mo"), ct.get("reset_time", "09:00")
                    )
                    seconds = (next_ct - now).total_seconds()
                    ct_text = self.format_reset_countdown(seconds)
                elif mode == "custom":
                    next_ct = self._get_next_custom_timer_time_seconds(
                        max(60, ct.get("interval_seconds", 3600)),
                        ct.get("start_time", "00:00"),
                    )
                    seconds = (next_ct - now).total_seconds()
                    ct_text = self.format_reset_countdown(seconds)
                else:  # hourly (default, backward compat)
                    next_ct = self._get_next_custom_timer_time(ct.get("interval_minutes", 60))
                    seconds = (next_ct - now).total_seconds()
                    ct_text = self._format_custom_countdown(seconds, "hh:mm:ss")
                self.timers_page.set_custom_timer_countdown(i, ct_text)
                if not self._custom_notified[i] and 0 <= seconds <= 10:
                    self._custom_notified[i] = True
                    self._fire_custom_notification(ct["name"], ct.get("notification_sound", ""))
                elif seconds > 10:
                    self._custom_notified[i] = False

        self.check_auto_resets()

    def select_tab(self, tab):
        self.active_tab = tab
        self._update_task_reset_hint()
        self.refresh()

    def _get_season_countdown_text(self) -> str:
        if not self.season_reset_datetime:
            return ""
        try:
            from datetime import datetime as _dt
            target = _dt.strptime(self.season_reset_datetime, "%Y-%m-%d %H:%M")
            diff = (target - _dt.now()).total_seconds()
            if diff <= 0:
                return "Abgelaufen"
            days = int(diff // 86400)
            hours = int((diff % 86400) // 3600)
            minutes = int((diff % 3600) // 60)
            if days > 0:
                return f"{days}T {hours:02d}:{minutes:02d}"
            return f"{hours:02d}:{minutes:02d}"
        except (ValueError, TypeError):
            return ""

    def _update_task_reset_hint(self):
        tab = self.tasks_page.active_tab
        prefix = tr(self.language, "reset_at")
        if tab in ("tasks", "shopping"):
            f = self.active_filter
            if f == "weekly":
                self.tasks_page.set_reset_hint(prefix, self._weekly_countdown_text, True)
            elif f == "season":
                season_text = self._get_season_countdown_text()
                if season_text:
                    self.tasks_page.set_reset_hint("Season-Ende: ", season_text, True)
                else:
                    self.tasks_page.set_reset_hint("", "", False)
            elif f == "daily":
                self.tasks_page.set_reset_hint(prefix, self._daily_countdown_text, True)
            else:
                self.tasks_page.set_reset_hint("", "", False)
        else:
            self.tasks_page.set_reset_hint("", "", False)

    def refresh(self):

        tasks = self.task_lists[self.active_tab]

        if self.active_filter == "event":
            tasks = [
                task for task in tasks
                if getattr(task, "is_event", False)
            ]
        elif self.active_filter in ("daily", "weekly", "season"):
            tasks = [
                task for task in tasks
                if getattr(task, "schedule", None) == self.active_filter
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

        total_kinah_k = 0

        if self.active_tab == "shopping":
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

        if self.active_tab == "shopping":
            self.tasks_page.set_footer_text(
                f"● {tr(self.language, 'progress')}: {progress}%   |   "
                f"{tr(self.language, 'total_price')}: "
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
        if hasattr(sys, "_MEIPASS"):
            base_path = Path(sys._MEIPASS)
            style_path = base_path / "ui" / "styles.qss"
        else:
            style_path = Path(__file__).resolve().parent / "styles.qss"
            base_path = Path(__file__).resolve().parent.parent

        with open(style_path, "r", encoding="utf-8") as f:
            styles = f.read()

        styles = styles.replace("ASSET_PATH", base_path.as_posix())
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

        tray_menu = QMenu(self)
        self._tray_open_action = tray_menu.addAction(tr(self.language, "tray_open"))
        self._tray_open_action.triggered.connect(self._restore_from_tray)
        tray_menu.addSeparator()
        self._tray_exit_action = tray_menu.addAction(tr(self.language, "tray_exit"))
        self._tray_exit_action.triggered.connect(self._quit_app)
        self.tray_icon.setContextMenu(tray_menu)

        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore_from_tray()

    def _restore_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _quit_app(self):
        self._force_quit = True
        self.close()

    def closeEvent(self, event):
        if getattr(self, "_force_quit", False):
            event.accept()
            return

        if self.minimize_to_tray is True:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "Aion2 TM",
                tr(self.language, "tray_running"),
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
            return

        if self.minimize_to_tray is None:
            box = QMessageBox(self)
            box.setWindowTitle(tr(self.language, "tray_minimize_title"))
            box.setText(tr(self.language, "tray_minimize_text"))
            tray_btn = box.addButton(
                tr(self.language, "tray_minimize_yes"), QMessageBox.AcceptRole
            )
            close_btn = box.addButton(
                tr(self.language, "tray_minimize_no"), QMessageBox.RejectRole
            )
            box.exec()
            if box.clickedButton() is tray_btn:
                self.minimize_to_tray = True
                self._save_app_config()
                event.ignore()
                self.hide()
                self.tray_icon.showMessage(
                    "Aion2 TM",
                    tr(self.language, "tray_running"),
                    QSystemTrayIcon.MessageIcon.Information,
                    3000,
                )
            else:
                self.minimize_to_tray = False
                self._save_app_config()
                event.accept()
            return

        event.accept()

    def _launch_dps_meter_if_configured(self):
        if self.dps_meter_autostart and self.dps_meter_path:
            self._start_dps_meter(self.dps_meter_path)

    def _start_dps_meter(self, path: str):
        import os
        if not path:
            return
        if not os.path.isfile(path):
            print(f"[DPS Meter] Datei nicht gefunden: {path}")
            return
        try:
            os.startfile(path)
            print(f"[DPS Meter] Gestartet: {path}")
        except Exception as e:
            print(f"[DPS Meter] Fehler beim Starten: {e}")

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
            
    def _get_next_custom_timer_time(self, interval_minutes: int) -> "datetime":
        now = datetime.now()
        interval = timedelta(minutes=interval_minutes)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elapsed_secs = (now - midnight).total_seconds()
        intervals_passed = int(elapsed_secs / interval.total_seconds())
        return midnight + interval * (intervals_passed + 1)

    def _get_next_custom_timer_time_seconds(self, interval_seconds: int, start_time: str = "00:00") -> "datetime":
        now = datetime.now()
        h, m = map(int, start_time.split(":"))
        anchor = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if anchor > now:
            anchor -= timedelta(days=1)
        elapsed = (now - anchor).total_seconds()
        intervals_passed = int(elapsed / interval_seconds)
        return anchor + timedelta(seconds=interval_seconds * (intervals_passed + 1))

    @staticmethod
    def _get_next_daily_custom_time(reset_time_str: str) -> "datetime":
        now = datetime.now()
        h, m = map(int, reset_time_str.split(":"))
        reset = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if reset <= now:
            reset += timedelta(days=1)
        return reset

    @staticmethod
    def _get_next_weekly_custom_time(day_str: str, reset_time_str: str) -> "datetime":
        now = datetime.now()
        day_map = {"Mo": 0, "Di": 1, "Mi": 2, "Do": 3, "Fr": 4, "Sa": 5, "So": 6}
        target_weekday = day_map.get(day_str, 0)
        h, m = map(int, reset_time_str.split(":"))
        days_ahead = target_weekday - now.weekday()
        if days_ahead < 0:
            days_ahead += 7
        reset = (now + timedelta(days=days_ahead)).replace(
            hour=h, minute=m, second=0, microsecond=0
        )
        if reset <= now:
            reset += timedelta(days=7)
        return reset

    @staticmethod
    def _format_custom_countdown(seconds: float, fmt: str) -> str:
        s = max(0, int(seconds))
        if fmt == "mm:ss":
            total_minutes, secs = divmod(s, 60)
            return f"{total_minutes:02}:{secs:02}"
        if fmt == "dd:hh:mm":
            days, remainder = divmod(s, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, secs = divmod(remainder, 60)
            if days > 0:
                return f"{days}T {hours:02}:{minutes:02}:{secs:02}"
            return f"{hours:02}:{minutes:02}:{secs:02}"
        # default: hh:mm:ss
        minutes, secs = divmod(s, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02}:{minutes:02}:{secs:02}"

    def _fire_custom_notification(self, name: str, sound_path: str):
        if hasattr(self, "tray_icon"):
            self.tray_icon.showMessage(
                name, f"{name} Timer abgelaufen!",
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )
        if sound_path and os.path.isfile(sound_path):
            winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)

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
        self.season_reset_datetime = settings.get("season_reset_datetime", "")

        from datetime import date as _date
        _d = settings.get("last_daily_reset_date")
        self.last_daily_reset_date = _date.fromisoformat(_d) if _d else None
        _w = settings.get("last_weekly_reset_date")
        self.last_weekly_reset_date = _date.fromisoformat(_w) if _w else None

        self.show_events = settings.get("show_events", True)
        self.auto_save = settings.get("auto_save", True)
        self.notification_enabled = settings.get("notification_enabled", False)
        self.notification_warn_minutes = settings.get("notification_warn_minutes", 1)
        self.notification_sync = settings.get("notification_sync", True)
        self.notification_shugo_enabled = settings.get("notification_shugo_enabled", False)
        self.notification_shugo_warn_minutes = settings.get("notification_shugo_warn_minutes", 1)
        self.notification_riss_enabled = settings.get("notification_riss_enabled", False)
        self.notification_riss_warn_minutes = settings.get("notification_riss_warn_minutes", 1)
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

        self.timer_categories = settings.get("timer_categories", ["Custom Timer"]) or ["Custom Timer"]
        self.custom_timers = settings.get("custom_timers", [])[:8]
        for ct in self.custom_timers:
            if "timer_mode" not in ct:
                ct["timer_mode"] = "hourly"
        self._custom_notified = [False] * 8
        self.timers_page.rebuild_custom_sections(self.timer_categories, self.custom_timers)

        self.toggle_events()
        self.update_countdowns()

        self.profile_page.set_profile_name(self.profile_name)
        self.sync_settings_page()

        # Aktuelle Listen immer leeren
        self.task_lists = {key: [] for key in self.tabs}

        if isinstance(data, dict):
            saved_tasks = data.get("tasks", {})

        # ===== MIGRATION: old event tabs → tasks =====
        old_event_tasks = saved_tasks.get("eventTasks", [])
        old_event_shopping = saved_tasks.get("eventShopping", [])

        if old_event_tasks:
            for item in old_event_tasks:
                item["event"] = True
                item.setdefault("schedule", "daily")
            saved_tasks.setdefault("tasks", []).extend(old_event_tasks)

        if old_event_shopping:
            for item in old_event_shopping:
                item.setdefault("schedule", "season")
                item["type"] = "shopping"
            saved_tasks.setdefault("shopping", []).extend(old_event_shopping)

        # ===== MIGRATION: dailyTasks / weeklyTasks → tasks =====
        for old_tab, default_schedule in (("dailyTasks", "daily"), ("weeklyTasks", "weekly")):
            for item in saved_tasks.get(old_tab, []):
                if item.get("type") != "shopping":
                    item.setdefault("schedule", default_schedule)
                    saved_tasks.setdefault("tasks", []).append(item)

        # ===== MIGRATION: dailyShopping + weeklyShopping → shopping =====
        for old_tab, default_schedule in (("dailyShopping", "daily"), ("weeklyShopping", "weekly")):
            for item in saved_tasks.get(old_tab, []):
                item.setdefault("schedule", default_schedule)
                item["type"] = "shopping"
                saved_tasks.setdefault("shopping", []).append(item)

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
                        schedule=item.get("schedule", "daily"),
                        is_event=item.get("event", False),
                        currency=item.get("currency", "kinah"),
                        character=item.get("character", ""),
                    )
                else:
                    card = TaskCard(
                        item.get("title", ""),
                        item.get("description", ""),
                        item.get("priority", "middle"),
                        item.get("event", False),
                        schedule=item.get("schedule", "daily"),
                        character=item.get("character", ""),
                    )

                if item.get("completed", False):
                    card.set_completed(True)

                self._wire_card(card)
                self.task_lists[tab].append(card)

        self.item_templates = data.get("item_templates", [])
        self.task_templates = data.get("task_templates", [])
        self.tasks_page.update_templates(self.item_templates)
        self.tasks_page.update_task_templates(self.task_templates)

        # Reconcile: add missing cards for templates that are still is_general=True
        self._sync_shopping_from_templates({})
        self._sync_tasks_from_templates({})

        self.refresh()
        raw_maps = data.get("flow_maps")
        old_map = data.get("flow_map", {})
        if raw_maps:
            self.flow_maps = raw_maps
            self.active_flow_map_name = data.get("active_flow_map", next(iter(raw_maps)))
        elif old_map:
            self.flow_maps = {"Map 1": old_map}
            self.active_flow_map_name = "Map 1"
        else:
            self.flow_maps = {}
            self.active_flow_map_name = "Map 1"
        if self.flow_map_window:
            self.flow_map_window.load_flow_data(self.flow_maps.get(self.active_flow_map_name, {}))
            self.flow_map_window.set_map_list(list(self.flow_maps.keys()) or ["Map 1"], self.active_flow_map_name)
            for node in self.flow_map_window.nodes.values():
                if node.icon == "character" and node.character_items:
                    self._sync_character_items_to_shopping(node.title, node.character_items)
        self._rebuild_characters()
        if self.characters:
            self.save_profile(silent=True)
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
                "schedule": card.schedule,
                "currency": card.currency,
                "character": card.character,
                "completed": card.completed,
            }

        return {
            "type": "task",
            "priority": getattr(card, "priority_value", "low"),
            "title": card.title_label.text(),
            "description": card.desc_label.text(),
            "event": getattr(card, "is_event", False),
            "schedule": getattr(card, "schedule", "daily"),
            "character": getattr(card, "character", ""),
            "completed": card.completed,
        }
    
    def _get_all_flow_maps(self) -> dict:
        if self.flow_map_window:
            self.flow_maps[self.active_flow_map_name] = self.flow_map_window.get_flow_data()
        return self.flow_maps

    def _on_flow_map_root_renamed(self, old_name: str, new_name: str):
        if old_name not in self.flow_maps or old_name == new_name:
            return
        if new_name in self.flow_maps:
            return  # Name already taken — don't rename
        data = self.flow_map_window.get_flow_data()
        self.flow_maps[new_name] = data
        del self.flow_maps[old_name]
        self.active_flow_map_name = new_name
        self.flow_map_window.set_map_list(list(self.flow_maps.keys()), new_name)
        if self.auto_save:
            self.save_profile(silent=True)

    def _on_flow_map_overlay_changed(self, checked: bool):
        data = self.flow_map_window.get_flow_data()
        self.flow_maps[self.active_flow_map_name] = data
        if self.auto_save:
            self.save_profile(silent=True)

    def save_profile(self, silent=False):
        data = {
            "profile_name": self.profile_name,
            "theme": self.current_theme,
            "language": self.language,

            "settings": {
                "daily_reset_time": self.daily_reset_time,
                "weekly_reset_day": self.weekly_reset_day,
                "weekly_reset_time": self.weekly_reset_time,
                "season_reset_datetime": self.season_reset_datetime,

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
                "notification_sync": self.notification_sync,
                "notification_shugo_enabled": self.notification_shugo_enabled,
                "notification_shugo_warn_minutes": self.notification_shugo_warn_minutes,
                "notification_riss_enabled": self.notification_riss_enabled,
                "notification_riss_warn_minutes": self.notification_riss_warn_minutes,
                "notification_sound": self.notification_sound,
                "timer_categories": self.timer_categories,
                "custom_timers": self.custom_timers,
                "last_daily_reset_date": (
                    self.last_daily_reset_date.isoformat()
                    if self.last_daily_reset_date else None
                ),
                "last_weekly_reset_date": (
                    self.last_weekly_reset_date.isoformat()
                    if self.last_weekly_reset_date else None
                ),
            },

            "tasks": {
                tab: [
                    self.serialize_card(card)
                    for card in cards
                ]
                for tab, cards in self.task_lists.items()
            },

            "flow_maps": self._get_all_flow_maps(),
            "active_flow_map": self.active_flow_map_name,
            "item_templates": self.item_templates,
            "task_templates": self.task_templates,
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
                self.dps_meter_path = cfg.get("dps_meter_path", "")
                self.dps_meter_autostart = cfg.get("dps_meter_autostart", False)
                raw_mtt = cfg.get("minimize_to_tray", None)
                self.minimize_to_tray = bool(raw_mtt) if raw_mtt is not None else None
                self._avatar_b64 = cfg.get("avatar", "")
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
        cfg = {
            "profile_dir": str(self.profile_dir),
            "dps_meter_path": self.dps_meter_path,
            "dps_meter_autostart": self.dps_meter_autostart,
            "minimize_to_tray": self.minimize_to_tray,
            "avatar": self._avatar_b64,
        }
        self.app_config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    def _show_first_run_dialog(self):
        from ui.first_run_dialog import FirstRunDialog
        dlg = FirstRunDialog(self)
        dlg.exec()
        if dlg.chosen_path:
            self.change_profile_dir(dlg.chosen_path)
        else:
            self.load_last_profile()

    def change_profile_dir(self, new_path: str):
        new_dir = Path(new_path)
        new_dir.mkdir(parents=True, exist_ok=True)

        # Nur kopieren wenn der Zielordner noch keine Profile enthält
        target_has_profiles = any(new_dir.glob("*.json"))
        if not target_has_profiles:
            for f in self.profile_dir.glob("*.json"):
                shutil.copy2(f, new_dir / f.name)

        self.profile_dir = new_dir
        self.last_profile_file = self.profile_dir / "last_profile.txt"
        self._save_app_config()
        if hasattr(self, "settings_page"):
            self.settings_page.update_profile_dir_label(str(self.profile_dir))

        # Immer aus dem neuen Ordner laden – last_profile.txt könnte auf alten Ordner zeigen
        self._load_best_profile_from_dir(new_dir)
        self.show_toast("Profilpfad gespeichert")

    def _load_best_profile_from_dir(self, folder: Path):
        """Lädt das beste verfügbare Profil aus einem Ordner: erstes Nicht-Default, sonst Default."""
        profiles = sorted(folder.glob("*.json"))
        if not profiles:
            return
        non_default = [p for p in profiles if p.stem.lower() != "default"]
        to_load = non_default[0] if non_default else profiles[0]
        self.load_profile(to_load)

    def save_last_profile(self, profile_path):
        with open(self.last_profile_file, "w", encoding="utf-8") as f:
            f.write(str(profile_path))


    def load_last_profile(self):
        if self.last_profile_file.exists():
            try:
                profile_path = Path(self.last_profile_file.read_text(encoding="utf-8").strip())
                if profile_path.exists():
                    self.load_profile(profile_path)
                    return
            except Exception:
                pass

        # Fallback: erstes verfügbares Profil laden
        profiles = sorted(self.profile_dir.glob("*.json"))
        if profiles:
            self.load_profile(profiles[0])

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

        if self.flow_map_window:
            self.flow_map_window.update_language(self.language, tr)

        # Update priority labels + event badges on all existing cards
        prio_display = {
            "low":    tr(self.language, "priority_low"),
            "medium": tr(self.language, "priority_middle"),
            "high":   tr(self.language, "priority_high"),
        }
        event_text = tr(self.language, "event_badge")
        for cards in self.task_lists.values():
            for card in cards:
                if isinstance(card, ShoppingCard):
                    raw = card.priority
                    card.priority_label.setText(prio_display.get(raw, raw))
                else:
                    raw = card.priority_value
                    card.priority.setText(prio_display.get(raw, raw))
                    if getattr(card, "is_event", False) and hasattr(card, "event_badge"):
                        card.event_badge.setText(event_text)

        self.sidebar.update_language(self.language, tr)
        self.header.update_language(self.language, tr)

        if hasattr(self, "_tray_open_action"):
            self._tray_open_action.setText(tr(self.language, "tray_open"))
            self._tray_exit_action.setText(tr(self.language, "tray_exit"))

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

    def reset_tasks_for_tabs(self, tabs, do_refresh=True):
        for tab in tabs:
            for card in self.task_lists.get(tab, []):
                card.set_completed(False)

        if do_refresh:
            self.refresh()
            self.save_profile(silent=True)

    def _reset_shopping_by_schedule(self, schedules: list):
        """Reset completed state for shopping items matching the given schedule types (data only)."""
        for card in self.task_lists.get("shopping", []):
            if isinstance(card, ShoppingCard) and card.schedule in schedules:
                card.set_completed(False)

    def _open_template_dialog(self):
        flow_maps = self._get_all_flow_maps()
        dlg = TemplateDialog(self.item_templates, flow_maps,
                             task_templates=self.task_templates,
                             initial_tab=self.active_tab,
                             parent=self)
        if dlg.exec():
            old_shopping = {t.get("id"): t for t in self.item_templates}
            old_tasks = {t.get("id"): t for t in self.task_templates}
            self.item_templates = dlg.get_templates()
            self.task_templates = dlg.get_task_templates()
            self.tasks_page.update_templates(self.item_templates)
            self.tasks_page.update_task_templates(self.task_templates)
            self._sync_shopping_from_templates(old_shopping)
            self._sync_tasks_from_templates(old_tasks)
            self.refresh()
            if self.auto_save:
                self.save_profile(silent=True)

    def _sync_shopping_from_templates(self, old_templates: dict):
        """Add / remove general ShoppingCards based on template is_general changes."""
        existing_titles = {
            card.title.lower()
            for card in self.task_lists.get("shopping", [])
            if isinstance(card, ShoppingCard)
        }

        for tmpl in self.item_templates:
            title = tmpl.get("title", "").strip()
            tid = tmpl.get("id")
            was_general = old_templates.get(tid, {}).get("is_general", False) if tid else False
            is_general = tmpl.get("is_general", False)

            if is_general and title.lower() not in existing_titles:
                # Add a new ShoppingCard to the shopping tab
                card = ShoppingCard(
                    priority=tmpl.get("priority", "middle"),
                    amount=str(tmpl.get("amount", "1")),
                    title=title,
                    location=tmpl.get("location", ""),
                    price=tmpl.get("price", "0"),
                    schedule=tmpl.get("schedule", "daily"),
                    currency=tmpl.get("currency", "kinah"),
                )
                self._wire_card(card)
                self.task_lists.setdefault("shopping", []).append(card)
                existing_titles.add(title.lower())
            elif was_general and not is_general:
                # Remove matching ShoppingCard (by title)
                self.task_lists["shopping"] = [
                    c for c in self.task_lists.get("shopping", [])
                    if not (isinstance(c, ShoppingCard) and c.title.lower() == title.lower())
                ]

    def _sync_tasks_from_templates(self, old_templates: dict):
        """Add / remove general TaskCards based on task_template is_general changes."""
        existing_titles = {
            card.title_label.text().lower()
            for card in self.task_lists.get("tasks", [])
            if isinstance(card, TaskCard)
        }
        for tmpl in self.task_templates:
            title = tmpl.get("title", "").strip()
            tid = tmpl.get("id")
            was_general = old_templates.get(tid, {}).get("is_general", False) if tid else False
            is_general = tmpl.get("is_general", False)
            if is_general and title.lower() not in existing_titles:
                card = TaskCard(
                    title,
                    "",
                    tmpl.get("priority", "middle"),
                    schedule=tmpl.get("schedule", "daily"),
                )
                self._wire_card(card)
                self.task_lists.setdefault("tasks", []).append(card)
                existing_titles.add(title.lower())
            elif was_general and not is_general:
                self.task_lists["tasks"] = [
                    c for c in self.task_lists.get("tasks", [])
                    if not (isinstance(c, TaskCard) and c.title_label.text().lower() == title.lower())
                ]

    def _reset_tasks_by_schedule(self, schedules: list):
        """Reset completed state for task cards matching the given schedule types."""
        for card in self.task_lists.get("tasks", []):
            if isinstance(card, TaskCard) and card.schedule in schedules:
                card.set_completed(False)

    def _sync_character_items_to_shopping(self, char_name: str, items: list):
        """Sync shopping and task items from a character node into the respective lists."""
        removed_shop = [
            c for c in self.task_lists.get("shopping", [])
            if isinstance(c, ShoppingCard) and c.character == char_name
        ]
        self.task_lists["shopping"] = [
            c for c in self.task_lists.get("shopping", [])
            if c not in removed_shop
        ]
        for c in removed_shop:
            c.setParent(None)

        removed_tasks = [
            c for c in self.task_lists.get("tasks", [])
            if isinstance(c, TaskCard) and c.character == char_name
        ]
        self.task_lists["tasks"] = [
            c for c in self.task_lists.get("tasks", [])
            if c not in removed_tasks
        ]
        for c in removed_tasks:
            c.setParent(None)

        for item in items:
            if item.get("type") == "task":
                card = TaskCard(
                    item.get("title", ""),
                    item.get("description", ""),
                    item.get("priority", "middle"),
                    False,
                    schedule=item.get("schedule", "daily"),
                    character=char_name,
                )
                self._wire_card(card)
                self.task_lists.setdefault("tasks", []).append(card)
            else:
                card = ShoppingCard(
                    priority=item.get("priority", "middle"),
                    amount=str(item.get("amount", "1")),
                    title=item.get("title", ""),
                    location=item.get("location", ""),
                    price=item.get("price", "0"),
                    schedule=item.get("schedule", "daily"),
                    currency=item.get("currency", "kinah"),
                    character=char_name,
                )
                self._wire_card(card)
                self.task_lists.setdefault("shopping", []).append(card)

        if self.active_tab in ("shopping", "tasks"):
            self.refresh()

    def _rebuild_characters(self):
        """Collect all character node titles from every flow map and update the dropdown."""
        chars: set[str] = set()
        active = self.active_flow_map_name
        if self.flow_map_window:
            for node in self.flow_map_window.nodes.values():
                if node.icon == "character" and node.title:
                    chars.add(node.title)
        for map_name, map_data in self.flow_maps.items():
            if map_name == active:
                continue
            for nd in map_data.get("nodes", {}).values():
                if nd.get("icon") == "character" and nd.get("title"):
                    chars.add(nd["title"])
        self.characters = sorted(chars)
        self.tasks_page.update_characters(self.characters)

    def _on_manual_reset(self):
        from datetime import date
        tab = self.active_tab
        filter_key = self.active_filter
        if tab == "tasks":
            schedules = [filter_key] if filter_key in ("daily", "weekly", "season") else ["daily", "weekly", "season"]
            self._reset_tasks_by_schedule(schedules)
            if filter_key == "daily":
                self.last_daily_reset_date = date.today()
            elif filter_key == "weekly":
                self.last_weekly_reset_date = date.today()
        elif tab == "shopping":
            if filter_key in ("daily", "weekly", "season"):
                self._reset_shopping_by_schedule([filter_key])
            else:
                self._reset_shopping_by_schedule(["daily", "weekly", "season"])
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
                self._reset_tasks_by_schedule(["daily"])
                self._reset_shopping_by_schedule(["daily"])
                self.refresh()
                self.save_profile(silent=True)
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

        # Berechne den letzten vergangenen Reset-Zeitpunkt (unabhängig vom heutigen Wochentag)
        days_ago = (now.weekday() - target_weekday) % 7
        last_weekly_reset_dt = (
            now.replace(hour=weekly_hour, minute=weekly_minute, second=0, microsecond=0)
            - timedelta(days=days_ago)
        )
        if last_weekly_reset_dt > now:
            last_weekly_reset_dt -= timedelta(days=7)
        last_weekly_reset_date = last_weekly_reset_dt.date()

        if self.last_weekly_reset_date is None or self.last_weekly_reset_date < last_weekly_reset_date:
            self._reset_tasks_by_schedule(["weekly"])
            self._reset_shopping_by_schedule(["weekly"])
            self.refresh()
            self.save_profile(silent=True)
            self.last_weekly_reset_date = last_weekly_reset_date

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

        elif page_key == "about":
            self.about_page.update_language(self.language, tr)

    def add_task_from_page(self, data):
        if self.active_tab == "shopping":
            card = ShoppingCard(
                priority=data.get("priority", "middle"),
                amount=str(data.get("amount", "1")),
                title=data.get("title", ""),
                location=data.get("location", ""),
                price=data.get("price", "0"),
                schedule=data.get("schedule", "daily"),
                currency=data.get("currency", "kinah"),
                character=data.get("character", ""),
            )
        elif self.active_tab == "tasks":
            card = TaskCard(
                data.get("title", ""),
                data.get("description", ""),
                data.get("priority", "middle"),
                data.get("event", False),
                schedule=data.get("schedule", "daily"),
                character=data.get("character", ""),
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
            import uuid as _uuid
            _json.dump(
                {"profile_name": "Default", "theme": self.current_theme,
                 "language": self.language, "tasks": {
                     "tasks": [], "shopping": []},
                 "item_templates": [
                     {
                         "id": str(_uuid.uuid4()),
                         "title": "Odyle-Extrakt",
                         "location": "Neuer Branch",
                         "price": "100",
                         "currency": "kinah",
                         "schedule": "weekly",
                         "priority": "middle",
                         "amount": "1",
                         "is_general": False,
                     }
                 ],
                 "task_templates": [],
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

    def _on_season_reset_changed_from_page(self, value: str):
        self.season_reset_datetime = value
        self._update_task_reset_hint()
        self.save_profile(silent=True)

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

        self.season_reset_datetime = data.get(
            "season_reset_datetime",
            self.season_reset_datetime
        )

        self.show_events = data.get(
            "show_events",
            self.show_events
        )

        self.toggle_events()

        self.update_countdowns()

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
        self.notification_sync = data.get("notification_sync", self.notification_sync)
        self.notification_shugo_enabled = data.get("notification_shugo_enabled", self.notification_shugo_enabled)
        self.notification_shugo_warn_minutes = data.get("notification_shugo_warn_minutes", self.notification_shugo_warn_minutes)
        self.notification_riss_enabled = data.get("notification_riss_enabled", self.notification_riss_enabled)
        self.notification_riss_warn_minutes = data.get("notification_riss_warn_minutes", self.notification_riss_warn_minutes)
        self.notification_sound = data.get("notification_sound", self.notification_sound)
        if "timer_categories" in data:
            self.timer_categories = data["timer_categories"] or ["Custom Timer"]
        if "custom_timers" in data:
            self.custom_timers = data["custom_timers"][:8]
            for ct in self.custom_timers:
                if "timer_mode" not in ct:
                    ct["timer_mode"] = "hourly"
            self._custom_notified = [False] * 8
            self.timers_page.rebuild_custom_sections(self.timer_categories, self.custom_timers)

        if "minimize_to_tray" in data:
            self.minimize_to_tray = data["minimize_to_tray"]

        old_path = self.dps_meter_path
        self.dps_meter_path = data.get("dps_meter_path", self.dps_meter_path)
        self.dps_meter_autostart = data.get("dps_meter_autostart", self.dps_meter_autostart)
        self._save_app_config()
        if self.dps_meter_autostart and self.dps_meter_path and self.dps_meter_path != old_path:
            self._start_dps_meter(self.dps_meter_path)

        self.save_profile(silent=True)

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
            "season_reset_datetime": self.season_reset_datetime,

            "shugo_enabled": self.shugo_enabled,
            "shugo_start_minute": self.shugo_start_minute,
            "shugo_interval_text": self.shugo_interval_text,

            "riss_enabled": self.riss_enabled,
            "riss_anchor_hour": self.riss_anchor_hour,
            "riss_interval_text": self.riss_interval_text,

            "auto_save": self.auto_save,

            "notification_enabled": self.notification_enabled,
            "notification_warn_minutes": self.notification_warn_minutes,
            "notification_sync": self.notification_sync,
            "notification_shugo_enabled": self.notification_shugo_enabled,
            "notification_shugo_warn_minutes": self.notification_shugo_warn_minutes,
            "notification_riss_enabled": self.notification_riss_enabled,
            "notification_riss_warn_minutes": self.notification_riss_warn_minutes,
            "notification_sound": self.notification_sound,
            "dps_meter_path": self.dps_meter_path,
            "dps_meter_autostart": self.dps_meter_autostart,
            "minimize_to_tray": bool(self.minimize_to_tray),

            "profile_dir": str(self.profile_dir),

            "timer_categories": self.timer_categories,
            "custom_timers": self.custom_timers,
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
        self._update_task_reset_hint()

    def run_update_check(self):
        self._checker = UpdateChecker()
        self._checker.update_available.connect(self._on_update_available)
        self._checker.up_to_date.connect(lambda: None)
        self._checker.start()

    def _on_update_available(self, version: str, body: str, asset_url: str):
        self._pending_update = (version, body, asset_url)
        if hasattr(self.header, "show_update"):
            self.header.show_update(version)

    def _open_update_dialog(self):
        if not self._pending_update:
            return
        version, body, asset_url = self._pending_update
        app_root = self.project_root
        dlg = UpdateDialog(version, body, asset_url, app_root, parent=self)
        dlg.exec()

    def _on_avatar_changed(self, b64: str):
        self._avatar_b64 = b64
        self._save_app_config()

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

    def duplicate_profile(self):
        self.save_profile(silent=True)

        default_name = f"{self.profile_name} (2)"
        new_name, ok = QInputDialog.getText(
            self,
            tr(self.language, "duplicate_profile_title"),
            tr(self.language, "duplicate_profile_label"),
            text=default_name,
        )
        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()
        dest_path = self.profile_dir / f"{new_name}.json"

        if dest_path.exists():
            QMessageBox.warning(
                self,
                tr(self.language, "duplicate_profile_title"),
                f'"{new_name}" existiert bereits.',
            )
            return

        src_path = self.profile_dir / f"{self.profile_name}.json"
        with open(src_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["profile_name"] = new_name
        data.setdefault("settings", {})["last_daily_reset_date"] = None
        data["settings"]["last_weekly_reset_date"] = None

        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        self.show_toast(
            tr(self.language, "duplicate_profile_success", name=new_name)
        )

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