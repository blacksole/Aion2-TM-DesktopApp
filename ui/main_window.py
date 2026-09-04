import glob
import json
import os
import shutil
import sys
import winsound
from pathlib import Path
from .settings_dialog import SettingsDialog
from .update_dialog import UpdateDialog
from .custom_timer_manager_dialog import CustomTimerManagerDialog
from .widgets.header_widget import HeaderWidget
from .widgets.sidebar_widget import SidebarWidget
from .widgets.shopping_card import ShoppingCard
from .widgets.template_dialog import TemplateDialog
from .pages.tasks_page import TasksPage
from .pages.timers_page import TimersPage
from .pages.todo_tabs_page import TodoTabsPage
from .pages.armory_page import ArmoryPage
from .pages.settings_page import SettingsPage
from .pages.dashboard_page import DashboardPage
from .pages.about_page import AboutPage
from .flow.flow_app_window import FlowMapWindow
from .overlay.overlay_window import OverlayWindow
from core.app_logger import get_logger
from core.translations import tr
from core.update_checker import UpdateChecker
from core.version import ARMORY_ENABLED

logger = get_logger("main_window")
from PySide6.QtWidgets import QTimeEdit
from PySide6.QtGui import QIcon, QPainter, QLinearGradient, QColor, Qt, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMenu, QComboBox, QStackedWidget, QFileDialog, QMessageBox,
    QSystemTrayIcon, QInputDialog, QApplication,
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
                 schedule="daily", character="", template_id="", location=""):
        super().__init__()

        self.completed = False
        self.is_event = is_event
        self.schedule = schedule
        self.character = character
        self.template_id = template_id
        self.location = location
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

        self.location_label = QLabel(location)
        self.location_label.setObjectName("taskDescription")

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
        text_box.addWidget(self.location_label)
        if not location:
            self.location_label.hide()

        # Schedule badge row
        _sched_texts = {"daily": "DAILY", "weekly": "WEEKLY", "season": "SEASON"}
        _sched_names = {"daily": "scheduleDaily", "weekly": "scheduleWeekly", "season": "scheduleSeason"}
        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
        self.schedule_label = QLabel(_sched_texts.get(schedule, schedule.upper()))
        self.schedule_label.setObjectName(_sched_names.get(schedule, "scheduleDaily"))
        badge_row.addWidget(self.schedule_label)
        self.char_label = QLabel(character)
        self.char_label.setObjectName("scheduleWeekly")
        badge_row.addWidget(self.char_label)
        if not character:
            self.char_label.hide()
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

    def update_from_template(self, tmpl: dict):
        """Refresh title/location/priority/schedule from an edited task template."""
        self.priority_value = tmpl.get("priority", self.priority_value)
        self.schedule = tmpl.get("schedule", self.schedule)
        self.location = tmpl.get("location", self.location)
        self.title_label.setText(tmpl.get("title", self.title_label.text()))
        self.location_label.setText(self.location)
        self.location_label.setVisible(bool(self.location))
        self.priority.setText(self.priority_value.upper())

        _sched_texts = {"daily": "DAILY", "weekly": "WEEKLY", "season": "SEASON"}
        _sched_names = {"daily": "scheduleDaily", "weekly": "scheduleWeekly", "season": "scheduleSeason"}
        self.schedule_label.setText(_sched_texts.get(self.schedule, self.schedule.upper()))
        self.schedule_label.setObjectName(_sched_names.get(self.schedule, "scheduleDaily"))
        self.style().unpolish(self.schedule_label)
        self.style().polish(self.schedule_label)


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
        self.missed_daily_activities = []
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
        self.armory_beta_enabled = False  # self-service opt-in, see _update_armory_visibility
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
        self.standard_templates: dict = {"tasks": [], "shopping": []}

        self.flow_maps: dict = {}
        self.active_flow_map_name: str = "Map 1"

        self.item_database_window = None
        # Build Planner state (User-Wunsch, 2026-08-25: "die Informationen
        # vom Buildplanner im Profil gespeichert werden" -- first step,
        # scoped to equipment + class/race). ItemDatabase/LoadoutWindow are
        # both lazily created (see _ensure_item_database_window /
        # ItemDatabaseWindow.open_loadout_window), so this holds whatever
        # was last loaded/saved even while neither window exists yet this
        # session -- handed off to the LoadoutWindow the moment it's
        # actually created, and refreshed from it (if open) on every save.
        self._build_planner_state: dict | None = None

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
            logger.debug("Overlay hidden")
        else:
            self.overlay.refresh()
            self.overlay.show()
            self.overlay.raise_()
            self.overlay_toggle_btn.setChecked(True)
            logger.debug("Overlay shown")

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

    def _ensure_item_database_window(self):
        if self.item_database_window is None:
            import importlib.util

            if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                # Bundled datas extract under _MEIPASS (onedir: the _internal/ folder), not next to the exe.
                db_dir = Path(sys._MEIPASS) / "ItemDatabase"
            else:
                db_dir = self.project_root / "ItemDatabase"
            logger.info("Loading ItemDatabase module from: %s", db_dir)
            spec = importlib.util.spec_from_file_location("item_database_app", db_dir / "app.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Kept (not just a local var) so other callers can reach classes
            # from this same lazily-loaded module later without importing
            # it a second time -- see open_template_item_picker.
            self._item_database_module = module

            # No Qt parent on purpose: an owned top-level window on Windows
            # shares the owner's taskbar entry, and closing it can leave the
            # whole app looking "minimized" until something restores focus.
            # This window's lifetime is already managed explicitly via this
            # singleton attribute, not by Qt parent-child ownership.
            self.item_database_window = module.create_window(parent=None, language=self.language)
            if hasattr(self.item_database_window, "set_theme"):
                self.item_database_window.set_theme(self.current_theme)
            if self._build_planner_state and hasattr(self.item_database_window, "set_pending_loadout_state"):
                self.item_database_window.set_pending_loadout_state(self._build_planner_state)

        return self.item_database_window

    def open_template_item_picker(self, parent_widget=None) -> dict | None:
        """Lazily loads the ItemDatabase module (same singleton pattern as
        _ensure_item_database_window, and this call alone does NOT show
        the full Item Database window -- just constructs/reuses it in the
        background for its already-loaded item list + caches) and opens
        the real catalog picker for the Templates dialog's "Import from
        Database" link (User-Wunsch, 2026-08-29: "die Database mit allen
        Filtern und Ansicht übergeben ... das Modell ist ja bereits
        gebaut"). Returns the chosen item dict, or None if cancelled."""
        window = self._ensure_item_database_window()
        module = self._item_database_module
        dlg = module.TemplateItemPickerDialog(
            window._raw_items, window.icon_cache, window.detail_cache, parent=parent_widget,
        )
        dlg.setStyleSheet(module._load_qss_text())
        if dlg.exec() and dlg.selected_item:
            return dlg.selected_item
        return None

    def open_item_database_window(self):
        logger.debug("Opening Item Database window")
        window = self._ensure_item_database_window()
        window.show()
        window.raise_()
        window.activateWindow()

    def open_build_planner_window(self):
        logger.debug("Opening Build Planner window")
        window = self._ensure_item_database_window()
        window.open_loadout_window()

    def open_crafting_calculator_window(self):
        logger.debug("Opening Crafting Calculator window")
        window = self._ensure_item_database_window()
        window.open_crafting_calculator()

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
        self._update_armory_visibility()

    def _update_armory_visibility(self):
        # Item Database / Crafting Calculator / Build Planner: either
        # fully released (ARMORY_ENABLED, see core/version.py) or reached
        # early via the self-service "Beta Bereich freischalten" toggle in
        # Settings (armory_beta_enabled, opt-in at the user's own risk).
        # Called both at startup and whenever that setting changes, so the
        # nav entry updates live without needing a restart.
        show = ARMORY_ENABLED or self.armory_beta_enabled
        self.sidebar.buttons["armory"].setVisible(show)
        self.sidebar.set_armory_beta_marked(show and not ARMORY_ENABLED)
        logger.debug(
            "Armory visibility updated: show=%s (ARMORY_ENABLED=%s, armory_beta_enabled=%s)",
            show, ARMORY_ENABLED, self.armory_beta_enabled,
        )
        self.sidebar.update_language(self.language, tr)


    def _setup_pages(self):
        self.dashboard_page = DashboardPage()

        self.tasks_page = TasksPage(
            tabs=self.tabs,
            language=self.language,
            tr_func=tr
        )

        self.timers_page = TimersPage()
        self.todo_page = TodoTabsPage(self.tasks_page, self.timers_page)
        self.armory_page = ArmoryPage()
        self.settings_page = SettingsPage()
        self.about_page = AboutPage()

        self.page_indexes = {
            "dashboard": 0,
            "tasks": 1,
            "armory": 2,
            "settings": 3,
            "about": 4,
        }

        self.page_stack.addWidget(self.dashboard_page)
        self.page_stack.addWidget(self.todo_page)
        self.page_stack.addWidget(self.armory_page)
        self.page_stack.addWidget(self.settings_page)
        self.page_stack.addWidget(self.about_page)

        self.page_stack.setCurrentWidget(self.todo_page)


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

        self.timers_page.manage_timers_requested.connect(self.open_custom_timer_manager)
        self.timers_page.timer_settings_requested.connect(self.open_timer_settings)

        self.armory_page.open_item_database_requested.connect(self.open_item_database_window)
        self.armory_page.open_crafting_calculator_requested.connect(self.open_crafting_calculator_window)
        self.armory_page.open_build_planner_requested.connect(self.open_build_planner_window)

        if hasattr(self.settings_page, "theme_changed"):
            self.settings_page.theme_changed.connect(
                self.change_theme_from_page
            )

        if hasattr(self.settings_page, "profile_name_changed"):
            self.settings_page.profile_name_changed.connect(
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

        if hasattr(self.settings_page, "save_profile_btn"):
            self.settings_page.save_profile_btn.clicked.connect(
                self.save_profile_from_profile_page
            )

        if hasattr(self.settings_page, "reset_profile_btn"):
            self.settings_page.reset_profile_btn.clicked.connect(
                self.reset_profile
            )

        if hasattr(self.settings_page, "load_profile_btn"):
            self.settings_page.load_profile_btn.clicked.connect(
                self.open_profile_menu
            )

        if hasattr(self.settings_page, "clear_events_btn"):
            self.settings_page.clear_events_btn.clicked.connect(
                self.clear_event_entries
            )

        if hasattr(self.settings_page, "export_requested"):
            self.settings_page.export_requested.connect(self.export_profile)

        if hasattr(self.settings_page, "import_requested"):
            self.settings_page.import_requested.connect(self.import_profile)

        if hasattr(self.settings_page, "duplicate_requested"):
            self.settings_page.duplicate_requested.connect(self.duplicate_profile)

        self.tasks_page.sort_requested.connect(self.sort_current_list)
        self.tasks_page.filter_changed.connect(self.set_task_filter)
        self.tasks_page.manual_reset_requested.connect(self._on_manual_reset)
        self.tasks_page.template_requested.connect(self._open_template_dialog)
        self.tasks_page.character_requested.connect(self._open_character_dialog)
        self.tasks_page.full_view_requested.connect(self._on_full_view_requested)
        self.tasks_page.import_requested.connect(self._open_full_view_import)

        if hasattr(self.header, "update_btn_clicked"):
            self.header.update_btn_clicked.connect(self._open_update_dialog)

        if hasattr(self.header, "avatar_changed"):
            self.header.avatar_changed.connect(self._on_avatar_changed)

        if hasattr(self.header, "profile_menu_requested"):
            self.header.profile_menu_requested.connect(
                lambda: self.open_profile_menu(anchor=self.header.profile_switch_btn)
            )

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
                warn_minutes = ct.get("notification_warn_minutes", 1)
                warn_secs = warn_minutes * 60
                check_secs = warn_secs if warn_secs > 0 else 10
                if not self._custom_notified[i] and 0 <= seconds <= check_secs:
                    self._custom_notified[i] = True
                    self._fire_custom_notification(ct["name"], ct.get("notification_sound", ""), warn_minutes)
                elif seconds > check_secs:
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
        total_ap = 0
        total_np = 0
        total_sc = 0

        if self.active_tab == "shopping":
            for card in tasks:
                if isinstance(card, ShoppingCard):
                    try:
                        amount = int(str(card.amount).strip() or 1)
                        price = float(str(card.price).replace(",", ".").strip() or 0)
                        currency = getattr(card, "currency", "kinah")
                        if currency == "abyss":
                            total_ap += amount * price
                        elif currency == "nightmare":
                            total_np += amount * price
                        elif currency == "shugo":
                            total_sc += amount * price
                        else:
                            total_kinah_k += amount * price
                    except ValueError:
                        pass

        self.tasks_page.update_stats(total, done, open_count)

        if self.active_tab == "shopping":
            parts = []
            if total_kinah_k > 0:
                parts.append(self.format_kinah_price(total_kinah_k))
            if total_ap > 0:
                ap_int = int(total_ap) if total_ap == int(total_ap) else total_ap
                parts.append(f"{ap_int} AP")
            if total_np > 0:
                np_int = int(total_np) if total_np == int(total_np) else total_np
                parts.append(f"{np_int} NP")
            if total_sc > 0:
                sc_int = int(total_sc) if total_sc == int(total_sc) else total_sc
                parts.append(f"{sc_int} SC")
            price_str = " + ".join(parts) if parts else "—"
            self.tasks_page.set_footer_text(
                f"● {tr(self.language, 'progress')}: {progress}%   |   "
                f"{tr(self.language, 'total_price')}: {price_str}"
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
        # OverlayWindow has no Qt parent (it's a standalone Qt.Tool window, see
        # its __init__), so it never receives this stylesheet through normal
        # widget-tree cascade -- it needs its own copy applied directly.
        if hasattr(self, "overlay"):
            self.overlay.setStyleSheet(styles)
        logger.debug("Stylesheet loaded: %s (%d bytes)", style_path, len(styles))

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
        # Real, silent data-loss risk (User-Wunsch, 2026-09-04: "beim
        # Beenden durch das X einmal prüfen, ob Daten noch ungesichert
        # sind und den User darauf hinweisen, sicherheitshalber"):
        # save_profile() below only ever persists what's already
        # COMMITTED into a node (title/description typed into the Flow
        # Map's node editor panel but not yet clicked "Save" on that node
        # is never part of self.flow_maps/self.characters at all) --
        # closing straight through would silently discard that in-progress
        # edit. Reuses the exact same Save/Discard/Cancel prompt the Flow
        # Map editor itself already shows before switching nodes/maps
        # while dirty (FlowController.confirm_dirty_before_action) instead
        # of a second, differently-worded warning.
        if self.flow_map_window and not self.flow_map_window.controller.confirm_dirty_before_action():
            event.ignore()
            return

        if getattr(self, "_force_quit", False):
            self.save_profile(silent=True)
            event.accept()
            QApplication.instance().quit()
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
                self.save_profile(silent=True)
                event.accept()
                QApplication.instance().quit()
            return

        self.save_profile(silent=True)
        event.accept()
        QApplication.instance().quit()

    def _launch_dps_meter_if_configured(self):
        if self.dps_meter_autostart and self.dps_meter_path:
            self._start_dps_meter(self.dps_meter_path)

    def _start_dps_meter(self, path: str):
        """Launches the user's configured external DPS Meter tool. Uses
        ShellExecuteEx directly (not the simpler os.startfile) with
        SEE_MASK_FLAG_NO_UI (User-reported, 2026-08-30: declining the UAC
        elevation prompt for a DPS Meter that requires admin rights also
        popped up a SECOND "elevation failed" error dialog, carrying OUR
        app's own taskbar icon since we're the process that requested the
        launch). SEE_MASK_FLAG_NO_UI only suppresses the SHELL's own
        follow-up error UI (missing file, access denied, elevation
        cancelled, ...) -- it does NOT and cannot suppress the actual UAC
        consent prompt itself (that's a Windows security boundary no
        application can bypass, by design, and shouldn't want to). The
        user still sees the normal "Do you want to allow..." prompt every
        time; declining it just no longer also throws up a confusing
        second popup -- a failure is instead reported back to us as a
        plain error code, which we log instead of displaying."""
        import ctypes
        from ctypes import wintypes

        if not path:
            return
        if not os.path.isfile(path):
            logger.warning("DPS Meter file not found: %s", path)
            return

        class _SHELLEXECUTEINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("fMask", ctypes.c_ulong),
                ("hwnd", wintypes.HWND),
                ("lpVerb", wintypes.LPCWSTR),
                ("lpFile", wintypes.LPCWSTR),
                ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR),
                ("nShow", ctypes.c_int),
                ("hInstApp", wintypes.HINSTANCE),
                ("lpIDList", ctypes.c_void_p),
                ("lpClass", wintypes.LPCWSTR),
                ("hKeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD),
                ("hIcon", wintypes.HANDLE),
                ("hProcess", wintypes.HANDLE),
            ]

        SEE_MASK_NOCLOSEPROCESS = 0x00000040
        SEE_MASK_FLAG_NO_UI = 0x00000400
        SW_SHOWNORMAL = 1

        sei = _SHELLEXECUTEINFO()
        sei.cbSize = ctypes.sizeof(sei)
        sei.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_FLAG_NO_UI
        sei.hwnd = None
        sei.lpVerb = "open"
        sei.lpFile = path
        sei.lpParameters = None
        sei.lpDirectory = os.path.dirname(path) or None
        sei.nShow = SW_SHOWNORMAL
        sei.hInstApp = None

        try:
            ok = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
            if not ok:
                error = ctypes.get_last_error()
                logger.warning(
                    "DPS Meter did not start (error=%s, e.g. UAC elevation was declined) -- "
                    "no popup shown, see SEE_MASK_FLAG_NO_UI note above", error,
                )
            else:
                logger.info("DPS Meter started: %s", path)
        except Exception as e:
            logger.error("DPS Meter failed to start: %s", e)

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

    def _fire_custom_notification(self, name: str, sound_path: str, warn_minutes: int = 0):
        msg = f"{name} läuft jetzt ab!" if warn_minutes <= 0 else f"{name} läuft in {warn_minutes} Min ab!"
        if hasattr(self, "tray_icon"):
            self.tray_icon.showMessage(
                name, msg,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )
        if sound_path and os.path.isfile(sound_path):
            winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)

    def open_profile_menu(self, checked=False, anchor=None):
        menu = QMenu(self)

        profiles = sorted(self.profile_dir.glob("*.json"))

        if profiles:
            user_profiles = [p for p in profiles if not self._is_lang_default(p)]
            default_profiles = [p for p in profiles if self._is_lang_default(p)]

            for profile_path in user_profiles:
                action = menu.addAction(profile_path.stem)
                action.triggered.connect(
                    lambda checked=False, path=profile_path: self.load_profile(path)
                )

            if user_profiles and default_profiles:
                menu.addSeparator()

            for profile_path in default_profiles:
                label = self._DEFAULT_LANG_LABELS.get(profile_path.stem.lower(), profile_path.stem)
                action = menu.addAction(label)
                action.triggered.connect(
                    lambda checked=False, path=profile_path: self.load_profile(path)
                )
        else:
            menu.addAction("No profiles").setEnabled(False)

        anchor = anchor or self.settings_page.load_profile_btn
        menu.setMinimumWidth(anchor.width())
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def open_timer_settings(self):
        self.sidebar.set_active_page("settings")
        self.settings_page.show_timer_section()

    def open_custom_timer_manager(self):
        dlg = CustomTimerManagerDialog(self.timer_categories, self.custom_timers, parent=self)
        if dlg.exec():
            self.timer_categories = dlg.get_categories()
            self.custom_timers = dlg.get_custom_timers()
            self._custom_notified = [False] * 8
            self.timers_page.rebuild_custom_sections(self.timer_categories, self.custom_timers)
            if self.auto_save:
                self.save_profile(silent=True)

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
        self.missed_daily_activities = settings.get("missed_daily_activities", [])

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

        self.settings_page.set_profile_name(self.profile_name)
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
                        template_id=item.get("template_id", ""),
                    )
                else:
                    card = TaskCard(
                        item.get("title", ""),
                        item.get("description", ""),
                        item.get("priority", "middle"),
                        item.get("event", False),
                        schedule=item.get("schedule", "daily"),
                        character=item.get("character", ""),
                        template_id=item.get("template_id", ""),
                        location=item.get("location", ""),
                    )

                if item.get("completed", False):
                    card.set_completed(True)

                self._wire_card(card)
                self.task_lists[tab].append(card)

        self.item_templates = data.get("item_templates", [])
        self.task_templates = data.get("task_templates", [])
        self.standard_templates = data.get("standard_templates", {"tasks": [], "shopping": []})
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
        self._build_planner_state = data.get("build_planner")
        if self.item_database_window and hasattr(self.item_database_window, "set_pending_loadout_state"):
            self.item_database_window.set_pending_loadout_state(self._build_planner_state)

        self._rebuild_characters()
        if hasattr(self.header, "set_profile"):
            self.header.set_profile(self.profile_name)
        self.save_last_profile(profile_path)
        logger.info("Profile loaded: %s", self.profile_name)

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
                "template_id": getattr(card, "template_id", ""),
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
            "template_id": getattr(card, "template_id", ""),
            "location": getattr(card, "location", ""),
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

    def save_profile(self, silent=False, explicit=False):
        # "Default"/"Default_de"/"Default_ru" are the language-picker starter
        # templates (see _is_lang_default), not a real ongoing profile --
        # renaming away from "Default" already re-creates a fresh template
        # (_create_default_profile, called from set_profile_name), but until
        # a new user/tester actually renames it, every single interaction
        # used to silently re-save over that same template file (User-
        # Report, 2026-08-29: browsing the Daevanion Board while still on
        # "Default" got saved into it). `explicit` marks a real, deliberate
        # "Save Profile" button click (see save_profile_from_profile_page) --
        # every other call site keeps working exactly as before for any
        # real (non-template) profile, since this guard only ever applies
        # while the CURRENT profile is still one of the three templates.
        if not explicit and self._is_lang_default(self.profile_dir / f"{self.profile_name}.json"):
            return

        if self.item_database_window and hasattr(self.item_database_window, "get_loadout_state"):
            self._build_planner_state = self.item_database_window.get_loadout_state()

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
                "missed_daily_activities": self.missed_daily_activities,
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
            "standard_templates": self.standard_templates,
            "build_planner": self._build_planner_state,
        }

        profile_path = self.profile_dir / f"{self.profile_name}.json"

        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        self.save_last_profile(profile_path)

        logger.debug("Profile saved: %s", profile_path)
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
                self.armory_beta_enabled = bool(cfg.get("armory_beta_enabled", False))
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
            "armory_beta_enabled": self.armory_beta_enabled,
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

    # ── Language-default helpers ──────────────────────────────────────────────
    _LANG_DEFAULT_STEMS = {"en": "Default", "de": "Default_de", "ru": "Default_ru"}
    _DEFAULT_LANG_LABELS = {
        "default":    "Default [EN]",
        "default_de": "Default [DE]",
        "default_ru": "Default [RU]",
    }

    def _is_lang_default(self, path: Path) -> bool:
        return path.stem.lower() in self._DEFAULT_LANG_LABELS

    def _preferred_default(self) -> "Path | None":
        stem = self._LANG_DEFAULT_STEMS.get(self.language, "Default")
        p = self.profile_dir / f"{stem}.json"
        if p.exists():
            return p
        for s in ("Default", "Default_de", "Default_ru"):
            p = self.profile_dir / f"{s}.json"
            if p.exists():
                return p
        return None

    # ─────────────────────────────────────────────────────────────────────────

    def _load_best_profile_from_dir(self, folder: Path):
        """Lädt das beste verfügbare Profil: erstes Nicht-Default, sonst sprachpassendes Default."""
        profiles = sorted(folder.glob("*.json"))
        if not profiles:
            return
        non_default = [p for p in profiles if not self._is_lang_default(p)]
        if non_default:
            self.load_profile(non_default[0])
        else:
            preferred = self._preferred_default()
            self.load_profile(preferred or profiles[0])

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

        # Fallback: sprachpassendes Default, dann erstes Profil
        preferred = self._preferred_default()
        if preferred:
            self.load_profile(preferred)
            return
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
        self.setWindowTitle("Aion 2 Companion")

        self.timers_page.update_language(self.language, tr)
        self.settings_page.update_language(self.language, tr)
        self.tasks_page.update_language(self.language)
        self.todo_page.update_language(self.language, tr)
        self.armory_page.update_language(self.language, tr)

        if self.flow_map_window:
            self.flow_map_window.update_language(self.language, tr)

        if self.item_database_window and hasattr(self.item_database_window, "update_language"):
            self.item_database_window.update_language(self.language)

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
        # Falls aktuell ein Default-Profil aktiv ist → zu sprachpassendem Default wechseln
        current_path = self.profile_dir / f"{self.profile_name}.json"
        if self._is_lang_default(current_path):
            preferred = self._preferred_default()
            if preferred and preferred != current_path:
                self.load_profile(preferred)
                return
        self.save_profile()

    def apply_theme(self, theme):
        self.current_theme = theme

        if hasattr(self, "background"):
            self.background.set_theme(theme)
            if hasattr(self, "theme_logo_label"):
                self.update_theme_logo()
            self.background.setProperty("theme", theme)

        if self.item_database_window is not None and hasattr(self.item_database_window, "set_theme"):
            self.item_database_window.set_theme(theme)

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
                             parent=self,
                             language=self.language,
                             tr_func=tr,
                             item_picker_callback=self.open_template_item_picker,
                             characters=self.characters,
                             standard_templates=self.standard_templates)
        if dlg.exec():
            old_shopping = {t.get("id"): t for t in self.item_templates}
            old_tasks = {t.get("id"): t for t in self.task_templates}
            self.item_templates = dlg.get_templates()
            self.task_templates = dlg.get_task_templates()
            self.standard_templates = dlg.get_standard_templates()
            self.tasks_page.update_templates(self.item_templates)
            self.tasks_page.update_task_templates(self.task_templates)
            self._sync_shopping_from_templates(old_shopping)
            self._sync_tasks_from_templates(old_tasks)
            self.refresh()
            if self.auto_save:
                self.save_profile(silent=True)

    def _sync_shopping_from_templates(self, old_templates: dict):
        """Add / remove general ShoppingCards based on template is_general changes,
        and refresh already-added cards whose source template was edited."""
        shopping_cards = [
            card for card in self.task_lists.get("shopping", [])
            if isinstance(card, ShoppingCard)
        ]
        existing_titles = {card.title.lower() for card in shopping_cards}

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
                    character=tmpl.get("character", ""),
                    template_id=tid,
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

            if tid:
                for card in shopping_cards:
                    if card.template_id == tid:
                        card.update_from_template(tmpl)

    def _sync_tasks_from_templates(self, old_templates: dict):
        """Add / remove general TaskCards based on task_template is_general changes,
        and refresh already-added cards whose source template was edited."""
        task_cards = [
            card for card in self.task_lists.get("tasks", [])
            if isinstance(card, TaskCard)
        ]
        existing_titles = {card.title_label.text().lower() for card in task_cards}
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
                    template_id=tid,
                    location=tmpl.get("location", ""),
                    character=tmpl.get("character", ""),
                )
                self._wire_card(card)
                self.task_lists.setdefault("tasks", []).append(card)
                existing_titles.add(title.lower())
            elif was_general and not is_general:
                self.task_lists["tasks"] = [
                    c for c in self.task_lists.get("tasks", [])
                    if not (isinstance(c, TaskCard) and c.title_label.text().lower() == title.lower())
                ]

            if tid:
                for card in task_cards:
                    if card.template_id == tid:
                        card.update_from_template(tmpl)

    def _reset_tasks_by_schedule(self, schedules: list):
        """Reset completed state for task cards matching the given schedule types."""
        for card in self.task_lists.get("tasks", []):
            if isinstance(card, TaskCard) and card.schedule in schedules:
                card.set_completed(False)

    def _record_missed_daily_activities(self):
        """Snapshots which DAILY task/shopping cards are still incomplete
        right before a daily reset clears them (User-Wunsch, 2026-09-05:
        "die verpassten Missionen fehlen noch in dem Roster Grid") -- real
        tracking, not the fabricated stat the earlier browser mockup used
        (see full_view_export.py's own docstring on why that was left out
        originally: the reset itself never recorded which cards were left
        undone before wiping them, so there was no real data to show).
        Called from BOTH the automatic overnight reset (check_auto_resets)
        and a manual daily reset (_on_manual_reset) -- either one crosses
        the same "yesterday -> today" boundary this is meant to capture,
        so both get identical treatment. Replaces the previous snapshot
        entirely (always reflects "since the LAST daily reset", not an
        ever-growing history)."""
        missed = []
        for card in self.task_lists.get("tasks", []):
            if isinstance(card, TaskCard) and card.schedule == "daily" and not card.completed:
                missed.append({"title": card.title_label.text(), "character": card.character or ""})
        for card in self.task_lists.get("shopping", []):
            if isinstance(card, ShoppingCard) and card.schedule == "daily" and not card.completed:
                missed.append({"title": card.title, "character": card.character or ""})
        self.missed_daily_activities = missed

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
                    location=item.get("location", ""),
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

    def _on_full_view_requested(self):
        """"🌐 Full View" button in the ToDo screen's sort/filter row
        (User-Wunsch, 2026-09-04, concrete follow-up to the Roster-Grid
        browser mockup discussed earlier). Exports the REAL current tasks/
        shopping state as a self-contained HTML snapshot and opens it in
        the system's default browser -- a snapshot, not a live view (see
        that earlier discussion: real two-way sync would need a small
        local HTTP server, not built here since a read-only overview
        already covers what was asked for)."""
        import tempfile
        from datetime import datetime
        from pathlib import Path
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from .full_view_export import build_full_view_csv, build_full_view_html, build_full_view_xlsx

        cards = self.task_lists.get("tasks", []) + self.task_lists.get("shopping", [])
        rows = [self.serialize_card(c) for c in cards]

        export_dir = Path(tempfile.gettempdir()) / "aion2_tm_full_view"
        export_dir.mkdir(parents=True, exist_ok=True)

        # Real bug found + fixed (User-reported, 2026-09-04: "wird immer
        # noch nicht angezeigt" after a fresh export -- a fixed
        # "roster_grid.html" name meant some browsers just refocused an
        # already-open tab from a PREVIOUS export instead of loading the
        # freshly-written one, showing stale data forever). Every export
        # now gets its own timestamped basename, so each click opens a
        # genuinely new URL the browser has never seen -- old exports in
        # this folder are cleared first so they don't pile up indefinitely.
        for old in export_dir.glob("roster_grid_*.*"):
            old.unlink(missing_ok=True)
        basename = f"roster_grid_{datetime.now():%Y%m%d_%H%M%S}"

        # Written as siblings of the HTML page (User-Wunsch, 2026-09-04:
        # "Vielleicht eine Option, aus dieser Ansicht als Excel-Tabelle
        # exportieren" -> "Können wir dem User die Wahl ... geben?") -- the
        # page's own "⬇ CSV"/"⬇ Excel" links are plain relative hrefs to
        # these, so the browser handles the actual download/open itself,
        # no JS-side file generation needed.
        (export_dir / f"{basename}.csv").write_text(
            build_full_view_csv(rows, self.characters, self.language), encoding="utf-8-sig", newline="",
        )
        build_full_view_xlsx(rows, self.characters, export_dir / f"{basename}.xlsx", self.language)

        page = build_full_view_html(
            rows, self.characters, self.language, basename=basename,
            missed_daily=self.missed_daily_activities,
        )
        path = export_dir / f"{basename}.html"
        path.write_text(page, encoding="utf-8")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_full_view_import(self):
        """Native counterpart to "Full View" (User-Wunsch, 2026-09-05:
        "Kann man hier auch ein Import Button einfügen mit Vorschau?").
        Sync can't happen from the exported browser page itself -- see
        ui/full_view_import.py's own module docstring -- so this opens a
        real in-app dialog: pick the (possibly Excel-edited) CSV/XLSX file,
        preview exactly what will change, Sync writes it into the real
        profile via _plan_full_view_import/apply_full_view_import_plan."""
        from ui.widgets.full_view_import_dialog import FullViewImportDialog

        dialog = FullViewImportDialog(
            self.characters, self._plan_full_view_import, self.apply_full_view_import_plan,
            language=self.language, tr_func=tr, parent=self,
        )
        dialog.exec()

    def _find_task_card(self, title: str, schedule: str, character: str):
        title_l = title.strip().lower()
        for card in self.task_lists.get("tasks", []):
            if not isinstance(card, TaskCard):
                continue
            if card.title_label.text().strip().lower() != title_l:
                continue
            if getattr(card, "schedule", "daily") != schedule:
                continue
            if (getattr(card, "character", "") or "") != character:
                continue
            return card
        return None

    def _plan_full_view_import(self, entries: list) -> list[dict]:
        """Classifies each parsed import entry against the CURRENT profile
        state without mutating anything -- shared by the preview dialog
        AND apply_full_view_import_plan (which executes this exact plan
        unchanged), so preview and apply can never drift apart."""
        plan = []
        for entry in entries:
            character = entry.character or ""
            card = self._find_task_card(entry.title, entry.schedule, character)
            if card is None:
                action = "new"
            elif card.completed != entry.done:
                action = "done" if entry.done else "open"
            else:
                action = "unchanged"
            plan.append({
                "character": entry.character, "schedule": entry.schedule,
                "title": entry.title, "done": entry.done, "action": action,
            })
        return plan

    def apply_full_view_import_plan(self, plan: list[dict]) -> dict:
        """Applies a plan from _plan_full_view_import to the real profile
        (User-Wunsch, 2026-09-05: a missing (character, title, schedule)
        combo gets a brand-new card -- "Neue Karte anlegen" -- and Sync can
        flip an existing card's completion state in EITHER direction --
        "Beide Richtungen", the imported file is the source of truth for
        done/open, not a one-way catch-up)."""
        counts = {"new": 0, "done": 0, "open": 0, "unchanged": 0}
        for row in plan:
            counts[row["action"]] = counts.get(row["action"], 0) + 1
            if row["action"] == "unchanged":
                continue
            character = row["character"] or ""
            if row["action"] == "new":
                # A new per-character instance of an already-known
                # recurring task inherits ITS priority (any character,
                # same title+schedule) instead of always defaulting --
                # keeps a real task's priority consistent across characters.
                sibling = next(
                    (c for c in self.task_lists.get("tasks", [])
                     if isinstance(c, TaskCard)
                     and c.title_label.text().strip().lower() == row["title"].strip().lower()
                     and getattr(c, "schedule", "daily") == row["schedule"]),
                    None,
                )
                priority = getattr(sibling, "priority_value", "middle") if sibling else "middle"
                card = TaskCard(row["title"], schedule=row["schedule"], character=character, priority=priority)
                card.set_completed(row["done"])
                self._wire_card(card)
                self.task_lists.setdefault("tasks", []).append(card)
            else:
                card = self._find_task_card(row["title"], row["schedule"], character)
                if card is not None:
                    card.set_completed(row["done"])

        self.refresh()
        if self.auto_save:
            self.save_profile(silent=True)
        return counts

    def _open_character_dialog(self):
        """"Character" button, right next to "Templates" on the ToDo screen
        (User-Wunsch, 2026-09-04). Thin wrapper -- _add_character/
        _remove_character below do the real work."""
        from .widgets.character_dialog import CharacterManagerDialog

        dlg = CharacterManagerDialog(
            self.characters, self._add_character, self._remove_character,
            self._character_has_children,
            language=self.language, tr_func=tr, parent=self,
        )
        dlg.exec()

    def _add_character(self, name: str) -> tuple[bool, str]:
        """Creates a real Flow Map "character"-icon node as a direct child
        of the ACTIVE flow map's root -- characters have no separate
        registry, they ARE Flow Map nodes (see _rebuild_characters below).
        Shared by the Templates dialog's "Character" tab (User-Wunsch,
        2026-09-04: "hier können Chars erstellt und schnell verwaltet
        werden") -- "am Root" per that same request, exactly what a user
        manually adding a node under root and setting its icon to
        "character" via the editor panel would produce, same root-child-
        only/8-max rules flow_controller.save_selected_node() enforces for
        that manual path, just without needing the full editor panel for a
        name-only creation. Returns (ok, error_key); error_key is "" on
        success or when there's simply nothing to do (empty name/already
        exists), else a translation key the caller can show describing why
        it failed."""
        from core.flow_model import FlowNode
        from ui.flow.flow_layout import find_free_child_position

        name = (name or "").strip()
        if not name or name in self.characters:
            return False, ""

        window = self.flow_map_window
        root = window.nodes.get(window.root_node_id) if window else None
        if not root:
            return False, ""
        char_count = sum(
            1 for cid in root.children
            if window.nodes.get(cid) and window.nodes[cid].icon == "character"
        )
        if char_count >= 8:
            return False, "char_limit_reached"

        new_node = FlowNode(title=name, icon="character")
        root.children.append(new_node.id)
        window.nodes[new_node.id] = new_node
        pos = find_free_child_position(window.root_node_id, window.nodes)
        if pos:
            new_node.x, new_node.y = pos

        window.render_flow()
        window.mark_unsaved()
        self._rebuild_characters()
        self._apply_standard_templates(name)
        self.tasks_page.select_character(name)
        return True, ""

    def _apply_standard_templates(self, character: str):
        """Seeds a brand-new character with the small "Standard Templates"
        starter pack (User-Wunsch, 2026-09-05: "Man soll 2-3 Standard
        Templates definieren und anpassen können") -- its own small,
        directly-editable list (see TemplateDialog's "Standards verwalten"
        button, which replaced the old CSV Import/Export at the same spot,
        per the user's own earlier decision), independent of the existing
        is_general flag (that one auto-adds to EVERY character's live
        list already; this one only fires once, at character creation)."""
        for tmpl in self.standard_templates.get("tasks", []):
            card = TaskCard(
                tmpl.get("title", ""),
                priority=tmpl.get("priority", "middle"),
                schedule=tmpl.get("schedule", "daily"),
                character=character,
                location=tmpl.get("location", ""),
            )
            self._wire_card(card)
            self.task_lists.setdefault("tasks", []).append(card)
        for tmpl in self.standard_templates.get("shopping", []):
            card = ShoppingCard(
                priority=tmpl.get("priority", "middle"),
                amount=str(tmpl.get("amount", "1")),
                title=tmpl.get("title", ""),
                location=tmpl.get("location", ""),
                price=tmpl.get("price", "0"),
                schedule=tmpl.get("schedule", "daily"),
                currency=tmpl.get("currency", "kinah"),
                character=character,
            )
            self._wire_card(card)
            self.task_lists.setdefault("shopping", []).append(card)
        if self.standard_templates.get("tasks") or self.standard_templates.get("shopping"):
            self.refresh()
            if self.auto_save:
                self.save_profile(silent=True)

    def _character_has_children(self, name: str) -> bool:
        """Whether the ACTIVE flow map's version of this character node has
        any children -- decides which confirmation CharacterManagerDialog
        shows before calling _remove_character below (User-Wunsch,
        2026-09-04: "Bei remove Charakter sollte eine Abfrage in Bezug auf
        die Flow Chart kommen - siehe Kind von Vater entfernen" -- a
        character node can have its own sub-nodes in the Flow Map just
        like any other node, and blindly deleting it would silently orphan
        them, same risk flow_controller.delete_node() already guards
        against for every other node)."""
        window = self.flow_map_window
        if not window:
            return False
        for node in window.nodes.values():
            if node.icon == "character" and node.title == name and node.children:
                return True
        return False

    def _remove_character(self, name: str, action: str = "recursive") -> bool:
        """Removes every Flow Map "character"-icon node with this exact
        title -- across every flow map, not just the active one, in case
        the same character name exists as a node in more than one map.
        Companion to _add_character above, same "no separate registry"
        model.

        `action` ("recursive" or "intermediate") mirrors the exact same
        choice flow_controller.delete_node() already offers for any node
        with children, via the same DeleteConfirmDialog (see
        CharacterManagerDialog._on_remove_clicked) -- "recursive" removes
        the character and its whole subtree, "intermediate" removes just
        the character node and re-parents its children up to whatever it
        was attached to (root, for a character). Reuses FlowController's
        own _find_parent_id/_collect_descendants rather than duplicating
        that traversal logic a second time. Only the ACTIVE map's node
        gets this full treatment with a real parent/children graph to
        walk -- a same-named node in an INACTIVE map (raw serialized dict,
        no live FlowController) is the rare edge case of one character
        existing in more than one map, and just gets its own subtree
        deleted outright rather than asking a second dialog per map."""
        from ui.flow.flow_controller import FlowController

        removed_any = False
        active = self.active_flow_map_name
        window = self.flow_map_window
        if window:
            target_ids = [
                nid for nid, node in window.nodes.items()
                if node.icon == "character" and node.title == name
            ]
            if target_ids:
                controller = FlowController(window)
                for nid in target_ids:
                    node = window.nodes.get(nid)
                    if not node:
                        continue
                    parent_id = controller._find_parent_id(nid)
                    if action == "intermediate":
                        if parent_id:
                            parent = window.nodes.get(parent_id)
                            if parent and nid in parent.children:
                                idx = parent.children.index(nid)
                                parent.children.remove(nid)
                                for i, child_id in enumerate(node.children):
                                    parent.children.insert(idx + i, child_id)
                        window.nodes.pop(nid, None)
                    else:
                        for desc_id in controller._collect_descendants(nid):
                            window.nodes.pop(desc_id, None)
                        if parent_id:
                            parent = window.nodes.get(parent_id)
                            if parent and nid in parent.children:
                                parent.children.remove(nid)
                    removed_any = True
                window.render_flow()
                window.mark_unsaved()
        for map_name, map_data in self.flow_maps.items():
            if map_name == active:
                continue
            nodes = map_data.get("nodes", {})
            target_ids = [
                nid for nid, nd in nodes.items()
                if nd.get("icon") == "character" and nd.get("title") == name
            ]
            for nid in target_ids:
                stack = [nid]
                while stack:
                    cur_id = stack.pop()
                    cur_node = nodes.pop(cur_id, None)
                    if cur_node:
                        stack.extend(cur_node.get("children", []))
                for nd in nodes.values():
                    if nid in nd.get("children", []):
                        nd["children"].remove(nid)
                removed_any = True
        if removed_any:
            self._rebuild_characters()
        return removed_any

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
            if "daily" in schedules:
                self._record_missed_daily_activities()
            self._reset_tasks_by_schedule(schedules)
            if filter_key == "daily":
                self.last_daily_reset_date = date.today()
            elif filter_key == "weekly":
                self.last_weekly_reset_date = date.today()
        elif tab == "shopping":
            schedules = [filter_key] if filter_key in ("daily", "weekly", "season") else ["daily", "weekly", "season"]
            if "daily" in schedules:
                self._record_missed_daily_activities()
            self._reset_shopping_by_schedule(schedules)
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
                self._record_missed_daily_activities()
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
        logger.debug("Sidebar clicked: %s", page_key)

        if page_key in self.page_indexes:
            self.page_stack.setCurrentIndex(self.page_indexes[page_key])

        if page_key == "tasks":
            self.show_toast(tr(self.language, "toast_tasks_opened"))

        elif page_key == "plan":
            self.open_flow_map_window()
            self.show_toast(tr(self.language, "toast_plan_opened"))

        elif page_key == "settings":
            self.show_toast(tr(self.language, "toast_settings_opened"))

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
                template_id=data.get("template_id", ""),
            )
        elif self.active_tab == "tasks":
            card = TaskCard(
                data.get("title", ""),
                data.get("description", ""),
                data.get("priority", "middle"),
                data.get("event", False),
                schedule=data.get("schedule", "daily"),
                character=data.get("character", ""),
                template_id=data.get("template_id", ""),
                location=data.get("location", ""),
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
        self.settings_page.set_profile_name(profile_name)
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

        if "minimize_to_tray" in data:
            self.minimize_to_tray = data["minimize_to_tray"]

        self.armory_beta_enabled = data.get("armory_beta_enabled", self.armory_beta_enabled)
        self._update_armory_visibility()

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
            "armory_beta_enabled": self.armory_beta_enabled,

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
        if hasattr(self.settings_page, "get_profile_name"):
            profile_name = self.settings_page.get_profile_name()

            if profile_name:
                self.set_profile_name(profile_name)

        self.save_profile(explicit=True)

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