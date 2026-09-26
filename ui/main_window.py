import json
import shutil
import os
import sys
from pathlib import Path
from uuid import uuid4
from .settings_dialog import SettingsDialog
from .update_dialog import UpdateDialog
from .custom_timer_manager_dialog import CustomTimerManagerDialog
from .widgets.header_widget import HeaderWidget
from .widgets.sidebar_widget import SidebarWidget
from .widgets.shopping_card import ShoppingCard
from .widgets.template_dialog import TemplateDialog
# _TemplateEditDialog is otherwise module-private to template_dialog.py --
# reused here (User-Wunsch, 2026-09-05) so the Item Database's "Add to
# Templates" context menu action gets the exact same Schedule/Location/
# Price form as manually adding a template, instead of a second
# hand-rolled copy of it.
from .widgets.template_dialog import _TemplateEditDialog
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
from core.platform import launch_external, tray_available
from core.sound import play_wav
from core.translations import tr
from core import theme
from . import motion
from core.update_checker import UpdateChecker
from core.news_checker import NewsChecker
from core.version import ARMORY_ENABLED
from ui.news_dialog import NewsDialog, NEWS_POPUP_ENABLED
from utils import paths
from ui.widgets import icons

logger = get_logger("main_window")
from PySide6.QtWidgets import QTimeEdit
from PySide6.QtGui import (
    QIcon, QPainter, Qt, QPixmap, QKeySequence, QShortcut,
)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMenu, QComboBox, QStackedWidget, QFileDialog, QMessageBox,
    QSystemTrayIcon, QInputDialog, QApplication, QLineEdit, QTextEdit, QAbstractSpinBox,
)
from datetime import datetime, timedelta
from PySide6.QtCore import QObject, QTimer, QEvent

#: ``(theme, asset_base)`` currently installed on the QApplication by
#: :meth:`MainWindow.load_styles` — see the note there.  Module level, not
#: per instance, because the stylesheet it tracks is process-wide.
_APPLIED_STYLE_KEY = None

#: Theme whose palette is currently installed on the QApplication.
#:
#: Tracked separately from ``MainWindow.current_theme`` because the two
#: answer different questions: ``current_theme`` is what the app WANTS,
#: this is what has actually been rendered.  Conflating them cost a real
#: bug (review F-1): both callers that matter -- ``__init__`` and
#: ``load_profile`` -- assign ``current_theme`` *before* calling
#: ``apply_theme(self.current_theme)``, so a "did the theme move?" test
#: against ``current_theme`` was always False and the palette silently
#: stayed on whatever ``main.py`` had set.  The sheet followed the theme,
#: the palette did not: exactly the "navy baseline under an Inferno sheet"
#: that ``core.theme.build_palette``'s docstring exists to prevent.
_APPLIED_PALETTE_THEME = None

THEME_LOGOS = {
    "abyss": "assets/logos/logo_abyss.png",
    "inferno": "assets/logos/logo_inferno.png",
    "emerald": "assets/logos/logo_emerald.png",
    "frostbite": "assets/logos/logo_frostbite.png",
    "obsidian": "assets/logos/logo_obsidian.png",
    "void": "assets/logos/logo_void.png",
}


#: priority -> the objectName MASTER §3 colours (ok / warn / danger).  Shared
#: with ui/widgets/shopping_card.py and mirrored by template_dialog's own map.
PRIORITY_OBJECT_NAMES = {
    "low": "priorityLow",
    "middle": "priorityMiddle",
    "medium": "priorityMiddle",
    "high": "priorityHigh",
}


class ThemedBackground(QWidget):
    """The window's ground: a flat ``bg.window`` fill from the active theme.

    Was ``GradientBackground``, a hand-rolled 4-stop diagonal gradient with
    its own per-theme hex table (24 literals that had to be kept in step
    with the QSS by hand, and were not: Frostbite's last stop was a bright
    ``#1e3a8a`` that no token anywhere used). MASTER's visual thesis is
    explicit — "zéro dégradé décoratif" — and §2 names ``bg.window`` as the
    fond of the main window and the overlay, so the ground is now one token,
    read live from ``core.theme``. Depth comes from the surface ladder
    (window → surface → elevated → overlay), not from a gradient.
    """

    def __init__(self):
        super().__init__()
        self.theme = theme.DEFAULT_THEME

    def set_theme(self, theme_name):
        self.theme = theme_name
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), theme.qcolor(self.theme, "bg.window"))

class TaskCard(QFrame):
    def __init__(self, title, description="", priority="low", is_event=False,
                 schedule="daily", character="", template_id="", location="",
                 card_id="", amount="1"):
        super().__init__()

        # Real bug found + fixed (User-reported, 2026-09-09: "man wählt
        # einen Eintrag an, aktualisiert den Amount ... und es passiert
        # nix" -- TaskCard never had an amount concept at all, unlike
        # ShoppingCard, so the Amount field's value was captured on the
        # form but silently dropped everywhere it reached a TaskCard).
        # `self.title` is the plain, undecorated title -- kept separate
        # from title_label's DISPLAYED text (which gets the "(Nx)" suffix
        # below) so serialize_card() and anything matching by title (e.g.
        # _delete_card's template lookup) still see the real title, not
        # the decorated display string.
        self.title = title
        self.amount = str(amount or "1")

        # Real gap found + fixed (User-reported, 2026-09-09: "missed" was
        # only ever matched by (title, character) text, no per-card
        # identity -- two cards that happen to share a title+character
        # could both get flagged, and a brand-new card with the same
        # title+character as an old missed one would wrongly inherit that
        # status). `template_id` doesn't help here either -- several
        # cards (one per character) can share the same template_id, so
        # it identifies "which template", not "which specific card".
        self.card_id = card_id or str(uuid4())
        self.completed = False
        self.is_event = is_event
        self.schedule = schedule
        self.character = character
        self.template_id = template_id
        self.location = location
        self.setProperty("event", self.is_event)
        self.setObjectName("taskCard")
        # Keyboard reachability (UX audit 2026-09-18, C1): a card has to
        # be able to HOLD focus before Delete can act on "the focused
        # card". Deliberately no focus styling here -- the QSS is owned
        # by a separate design pass.
        self.setFocusPolicy(Qt.StrongFocus)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        # MASTER §3: was "○"/"●" — two dingbats Barlow does not carry, so
        # the system fell back to another face for the single most-repeated
        # control in the app.  Converted together with ShoppingCard and the
        # three overlay rows: one of them alone would have made the ToDo
        # list mix a Lucide ring with a fallback dingbat, row by row.
        self.check_btn = QPushButton()
        self.check_btn.setObjectName("checkButton")
        self.check_btn.setFixedWidth(32)
        icons.set_icon(self.check_btn, "circle", 16, "fg.muted")
        # Icon-only: the "○" it replaced WAS the accessible name (review
        # H/15).  Not a tooltip -- this control is clicked, not hovered for
        # help, and an untranslated tooltip would be visible UI.
        self.check_btn.setAccessibleName("Toggle completed")
        self.check_btn.clicked.connect(self.toggle)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)

        self.title_label = QLabel()
        self.title_label.setObjectName("taskTitle")
        self._refresh_title_display()

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
        # User-reported, 2026-09-09: the new "Missed" stat tile had no
        # per-card equivalent -- you could see a total count but not WHICH
        # card it referred to. set_missed() (called from
        # MainWindow.refresh(), which already computes card_id membership
        # for the stat tile) toggles this same badge.
        # Hardcoded English, same as the DAILY/WEEKLY/SEASON badges right
        # above -- this whole row never goes through tr() at all.
        self.missed_badge = QLabel("MISSED")
        self.missed_badge.setObjectName("missedBadge")
        self.missed_badge.setVisible(False)
        badge_row.addWidget(self.missed_badge)
        badge_row.addStretch()
        text_box.addLayout(badge_row)

        self.priority_value = priority
        self.priority = QLabel(priority.upper())
        # Real bug, found while reviewing the wired-up render (2026-09-18):
        # this objectName was the LITERAL "priorityMedium" for every card, so
        # every priority came out warn-coloured -- a HIGH task looked exactly
        # like a MIDDLE one, and the ok/warn/danger mapping MASTER §3
        # specifies only ever worked in the Templates dialog (which has had
        # its own _PRIO_NAMES map all along).
        self._apply_priority_style()

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
        self._apply_completed_style()

    def set_completed(self, value):
        self.completed = value
        self._apply_completed_style()

    def _apply_completed_style(self):
        """Muted struck-through title + green check, entirely from the QSS.

        ``#taskCard[completed="true"] #taskTitle`` / ``#checkButton`` in
        ui/styles.template.qss own the look now (it used to be an inline
        ``color: #64748b`` literal here). A descendant rule keyed off an
        ANCESTOR's dynamic property is only re-evaluated when the child
        itself is repolished, hence the two extra passes.
        """
        icons.set_icon(
            self.check_btn,
            "circle-check" if self.completed else "circle",
            16,
            "ok" if self.completed else "fg.muted",
        )
        self.setProperty("completed", self.completed)
        for widget in (self, self.title_label, self.check_btn):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _apply_priority_style(self, text: str | None = None):
        """Label text + the objectName MASTER §3's ok/warn/danger rule needs.

        ``text`` is the already-translated label (the edit form and the
        language switch both have it); without it the plain English
        uppercase value is used, as at construction.
        """
        self.priority.setText(text if text is not None else str(self.priority_value or "").upper())
        self.priority.setObjectName(PRIORITY_OBJECT_NAMES.get(self.priority_value, "priorityMiddle"))
        self.priority.style().unpolish(self.priority)
        self.priority.style().polish(self.priority)

    def set_missed(self, value: bool):
        self.missed_badge.setVisible(value)

    def _refresh_title_display(self):
        """Shows "Title (Nx)" once amount is more than 1 (User-Wunsch,
        2026-09-09: "Titel (Anzahl)") -- title_label's TEXT is purely a
        display concern; self.title stays the plain, undecorated value
        everything else (serialization, template-title matching) uses."""
        if self.amount and self.amount not in ("1", "0", ""):
            self.title_label.setText(f"{self.title} ({self.amount}x)")
        else:
            self.title_label.setText(self.title)

    def set_title(self, title: str):
        self.title = title
        self._refresh_title_display()

    def set_amount(self, amount: str):
        self.amount = str(amount or "1")
        self._refresh_title_display()

    def update_from_template(self, tmpl: dict):
        """Refresh title/location/priority/schedule/description from an edited task template."""
        self.priority_value = tmpl.get("priority", self.priority_value)
        self.schedule = tmpl.get("schedule", self.schedule)
        self.location = tmpl.get("location", self.location)
        self.set_title(tmpl.get("title", self.title))
        self.location_label.setText(self.location)
        self.location_label.setVisible(bool(self.location))
        self._apply_priority_style()

        description = tmpl.get("description", self.desc_label.text())
        self.desc_label.setText(description)
        self.desc_label.setVisible(bool(description))

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
        # Structural guard for the 2.0.5 data-loss class: True while
        # load_profile is still restoring fields, so nothing can serialize
        # half-restored state over the file on disk (see load_profile/save_profile).
        self._profile_loading: bool = False
        # Set when the loaded profile (and its .bak) could not be parsed: the
        # guard above then stays on past load_profile, and only this flag --
        # not the re-entrancy one -- authorises a snapshot + warning.
        self._profile_unreadable: bool = False
        self._autosave_disabled_notified: bool = False
        self._pending_update = None
        self._checker = None


        self.tabs = {
            "tasks": "tasks",
            "shopping": "shopping",
        }

        self.language = "en"
        self.current_theme = "abyss"
        # MASTER §1 "motion.reduced" -- an accessibility switch, so it is a
        # per-profile setting, not a hidden constant. Pushed into
        # ui.motion (a module-level flag) on every load and on every toggle.
        self.reduce_motion = False

        self.active_tab = "tasks"
        self.active_filter = "all"
        self.show_events = True
        self.daily_reset_time = "09:00"
        self.weekly_reset_day = "Mo"
        self.weekly_reset_time = "09:00"
        self.season_reset_datetime = ""
        # On/Off gate for the Season timer (User-Wunsch, 2026-09-17: "beim
        # Season Timer noch ein 'On/Off' einrichten, similar zum Advanced
        # Timer") -- previously the Season countdown card/reset logic was
        # only ever gated by whether a date was SET at all, with no way to
        # turn it off independently, unlike Shugo/Riss's own explicit
        # enabled flags.
        self.season_enabled = False
        self.last_daily_reset_date = None
        self.last_weekly_reset_date = None
        # Which season_reset_datetime value the Season reset has already
        # fired for (User-Wunsch, 2026-09-17: "Season Einträge beim
        # Shopping und den Tasks mit dem Season Reset verknüpfen") -- a
        # plain value-equality marker rather than a date, since a season
        # end is a one-off, manually-set datetime, not a recurring
        # calendar boundary like Daily/Weekly. Comparing against the
        # CURRENT season_reset_datetime string directly means setting a
        # new date for the next season naturally allows the reset to fire
        # again once that new date passes.
        self.last_season_reset_datetime = None
        self.missed_daily_activities = []
        self._daily_countdown_text = "--:--:--"
        self._weekly_countdown_text = "--:--:--"
        self.profile_name = "Default"
        if getattr(sys, "frozen", False):
            self.project_root = Path(sys.executable).parent
        else:
            self.project_root = Path(__file__).resolve().parent.parent
        # Frozen: the per-user config location (%APPDATA%\Aion2 TM on Windows,
        # ~/.config/aion2-tm on Linux, ~/Library/Application Support on macOS
        # -- see utils/paths.py). From source: the repo root, so a dev run keeps
        # its config next to the code instead of polluting the user profile.
        if getattr(sys, "frozen", False):
            self.app_config_dir = paths.user_config_dir()
        else:
            self.app_config_dir = self.project_root
        self.app_config_path = self.app_config_dir / "config.json"
        self.app_config_dir.mkdir(parents=True, exist_ok=True)

        self.dps_meter_path = ""
        self.dps_meter_autostart = False
        self.minimize_to_tray = None  # None = not asked yet
        self._avatar_b64 = ""
        self._last_seen_news_id = 0
        self.characters: list = []

        self.profile_dir = self._resolve_profile_dir()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.last_profile_file = self.profile_dir / "last_profile.txt"
        self.profile_edit_mode = False
        self._refresh_default_profiles_backup()

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

        # Soft-delete state (UX audit 2026-09-18, C2). At most one card
        # is ever pending; the sequence number is what lets a fired undo
        # timer tell "still mine" from "already superseded".
        self._pending_delete = None
        self._pending_delete_seq = 0

        self.item_templates: list = []
        self.task_templates: list = []
        # Named Standard Template Sets -- {"tasks": {"SetName": [...]},
        # "shopping": {"SetName": [...]}}. See core.persistence.
        # migrate_standard_templates for the shape's history/migration.
        self.standard_templates: dict = {"tasks": {}, "shopping": {}}

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
        # Written here directly (the page does not exist yet); every LATER
        # write goes through _set_build_planner_state(), which is also what
        # keeps the Armory dashboard in step -- see its docstring.
        self._build_planner_state: dict | None = None

        # In-game overlay: which accordion sections are shown (User-Wunsch,
        # 2026-09-05: gear icon back in the overlay title bar, opening a
        # picker for this). Tasks/Guide/Timer/Custom Timer stay on by
        # default (matches the overlay's previous always-on behavior plus
        # the new Timer sections); Skill/Gear Priority default off since
        # they need the Armory beta set up first.
        self.overlay_visible_sections: dict = {
            "tasks": True, "guide": True, "timer": True, "custom_timer": True,
            "skill_priority": False, "gear_priority": False,
        }
        # "" = show every character's tasks (previous, only behavior) --
        # User-Wunsch, way back: "einen kleinen Button 'Char' einfügen ...
        # wenn man 4 oder mehr chars hat, ist das schnell überflutet".
        self.overlay_char_filter: str = ""
        # Same idea for the main ToDo list itself (User-Wunsch, 2026-09-16:
        # "beim ToDo wär es nice wie im Overlay auch einen Char auswählen zu
        # können") -- a separate filter, independent of the Overlay's own,
        # since the two are viewed at different times for different reasons.
        self.todo_char_filter: str = ""

        self.flow_map_window = FlowMapWindow(self, language=self.language, tr_func=tr)
        self.flow_map_window.map_switch_requested.connect(self._switch_flow_map)
        self.flow_map_window.map_add_requested.connect(self._add_flow_map)
        self.flow_map_window.map_delete_requested.connect(self._delete_flow_map)
        self.flow_map_window.map_reset_requested.connect(self._reset_flow_map)
        self.flow_map_window.root_renamed.connect(self._on_flow_map_root_renamed)
        self.flow_map_window.map_overlay_changed.connect(self._on_flow_map_overlay_changed)

        # The application stylesheet is scoped to `QWidget[aion2="true"]`
        # and its descendants (ui/styles.template.qss §0).  Set before
        # setup_ui() builds anything, so every child is polished with the
        # scope already in place -- and so that the sheet cannot reach the
        # Armory's parentless windows, whose 1,205-line sheet was tuned
        # against the default font and its own per-item colours.
        self.setProperty("aion2", True)

        self.setup_ui()
        # The tab pill highlight was only ever set by a click, so the app
        # opened with neither Tasks nor Shopping marked active.
        self.tasks_page.mark_active_tab(self.active_tab)
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

        # The startup theme belongs to the profile, which is only known once
        # the two branches above have run -- so the stylesheet AND the Fusion
        # fallback palette are (re)built here rather than guessed in main.py.
        # A profile that carries no theme leaves current_theme at its default
        # and this is simply a no-op re-render.
        self.apply_theme(self.current_theme)

        # Pre-create the native OS window handle so first show() has no flash
        if self.flow_map_window:
            self.flow_map_window.winId()

        self._launch_dps_meter_if_configured()

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdowns)
        self.countdown_timer.start(1000)

        self._editing_card = None
        self._setup_tray_icon()
        self._setup_shortcuts()
        self.update_countdowns()

    #: The one :class:`_CardPressFilter` this window installs on its cards,
    #: built on first use.  A class-level default rather than an ``__init__``
    #: assignment because ``refresh()`` (and therefore ``_wire_card``) already
    #: runs while ``__init__`` is still building the window.
    _card_press_filter = None

    class _CardPressFilter(QObject):
        """Turns a left-click on a card into "edit this card", for every card.

        This used to be ``card.mousePressEvent = on_press``: a closure that
        captured the card (as a default argument) and the window (as a free
        variable), stored in the *card's own* ``__dict__``.  That is a
        reference cycle rooted on a live Qt object -- card -> its instance
        dict -> the function -> the card again, and on to the MainWindow --
        so ``deleteLater()`` could free the C++ widget while the Python
        wrapper, the window and every other card stayed reachable until a
        full ``gc.collect()`` happened to run.  In the app that is a slow
        drip; in the test suite it is ~600 widgets per MainWindow that never
        left, and since the stylesheet lives on the QApplication (MASTER
        §4-1) every ``setStyleSheet`` had to re-resolve against all of them
        (F-apex "Re-verification 2": one theme switch, 9 s).

        An event filter needs neither capture: Qt hands it the event target,
        so the card comes in as ``obj``, and the owning window is reachable
        through the filter's Qt parent.  Both links are C++ -- nothing here
        holds a Python reference to a card or to the window.
        """

        def eventFilter(self, obj, event):
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                window = self.parent()
                child = obj.childAt(event.position().toPoint())
                if not isinstance(child, QPushButton):
                    if window._editing_card is obj:
                        window._cancel_edit()
                    else:
                        window._start_editing(obj)
            # False: the card's own mousePressEvent still runs, which is what
            # the old closure's trailing ``type(c).mousePressEvent(c, event)``
            # did by hand.
            return False

    def _wire_card(self, card):
        card.check_btn.clicked.connect(self._on_task_toggled)
        card.delete_btn.clicked.disconnect()
        # A bound method, not ``lambda c=card: ...``: PySide holds bound-method
        # slots weakly, so this connection adds no reference to the card or to
        # the window (the lambda did both, and outlived the card).
        card.delete_btn.clicked.connect(self._on_card_delete_clicked)
        card.setCursor(Qt.PointingHandCursor)

        if self._card_press_filter is None:
            self._card_press_filter = self._CardPressFilter(self)
        card.installEventFilter(self._card_press_filter)

    def _on_card_delete_clicked(self):
        """The "x" on a card. Resolves the card from the button, not a closure."""
        button = self.sender()
        if button is None:
            return
        card = button.parentWidget()
        while card is not None and getattr(card, "delete_btn", None) is not button:
            card = card.parentWidget()
        if card is not None:
            self._delete_card(card)

    def _on_task_toggled(self):
        self.refresh()
        if self.auto_save:
            self.save_profile(silent=True)

    # How long a deleted card stays undoable. Long enough to read the
    # toast and aim for the button (UX audit 2026-09-18, C2 asked for 5-8 s).
    UNDO_WINDOW_MS = 6000

    def _delete_card(self, card):
        """Soft delete: the card leaves the list (and therefore every
        serialization, count and refresh) immediately, but nothing is
        actually destroyed or saved until the undo window closes.

        Before this, the "x" was a single irreversible click: it dropped the
        card, flipped the matching template's ``is_general`` and auto-saved,
        with no confirmation and no way back (UX audit 2026-09-18, C2).

        The three effects that used to fire here are now split:
          * removing the card from ``task_lists`` happens NOW, so a pending
            card can never be serialized, counted, rendered or resurrected
            by a reset that runs while the toast is up;
          * the template mutation + ``deleteLater`` + save are deferred into
            ``_commit_pending_delete``;
          * ``_undo_pending_delete`` puts the card back at its exact index,
            which needs no save at all (nothing was written yet).
        """
        if self._editing_card is card:
            self._cancel_edit()

        # Only one card may be pending at a time: a second delete commits the
        # first (its undo chance is over the moment its toast is replaced).
        self._commit_pending_delete()

        tab = None
        index = None
        for key, cards in self.task_lists.items():
            if card in cards:
                tab = key
                index = cards.index(card)
                cards.remove(card)
                break

        if tab is None:
            # Not in any list (already deleted / never added) -- nothing to
            # undo, so fall back to the old destructive path for that card.
            card.deleteLater()
            return

        self._pending_delete_seq += 1
        seq = self._pending_delete_seq
        self._pending_delete = {
            "seq": seq,
            "tab": tab,
            "index": index,
            "card": card,
            "apply": self._template_delete_side_effects(card),
        }

        # refresh() re-renders from task_lists, which no longer holds the
        # card -- render_tasks hides and unparents it for us, which is why
        # the fade has to COMPLETE first: a card already unparented has
        # nothing left to fade. `task_lists` was mutated synchronously
        # above, so every count, serialization and reset already sees the
        # card as gone while it is still fading (MASTER §3, motion.base).
        # With reduced motion the duration is 0 and ui.motion applies the
        # end state and calls `then` inline, i.e. exactly the old behaviour.
        motion.fade_out(card, then=self.refresh, theme=self.current_theme)

        self.show_toast(
            tr(self.language, "toast_task_removed"),
            action_label=tr(self.language, "undo"),
            on_action=self._undo_pending_delete,
            duration_ms=self.UNDO_WINDOW_MS,
            action_key="undo",
        )
        # `self` as the context object: Qt drops the callback if the window
        # is destroyed before the timer fires, instead of running it against
        # already-deleted C++ widgets (a real RuntimeError, surfaced the
        # moment the test suite started destroying its windows for real).
        QTimer.singleShot(self.UNDO_WINDOW_MS, self, lambda: self._commit_pending_delete(seq))

    def _template_delete_side_effects(self, card):
        """The template mutation the old ``_delete_card`` did inline, frozen
        into a closure so it can run later (on commit) or never (on undo)."""
        if isinstance(card, ShoppingCard):
            templates = self.item_templates
        elif isinstance(card, TaskCard):
            templates = self.task_templates
        else:
            return lambda: None

        title_lower = card.title.lower()

        def _apply():
            for tmpl in templates:
                if tmpl.get("title", "").lower() == title_lower:
                    tmpl["is_general"] = False
                    break

        return _apply

    def _commit_pending_delete(self, seq=None):
        """Makes the pending delete real. Idempotent and safe to call from
        anywhere; ``seq`` lets a fired timer bow out when the delete it was
        scheduled for is already gone (undone, or committed by a newer one)."""
        pending = self._pending_delete
        if not pending:
            return
        if seq is not None and pending["seq"] != seq:
            return

        self._pending_delete = None
        pending["apply"]()
        card = pending["card"]
        card.setParent(None)
        card.deleteLater()
        if self.auto_save:
            self.save_profile(silent=True)

    def _undo_pending_delete(self):
        """Puts the card back exactly where it was. No save: the deletion was
        never written, so the file on disk is still the pre-delete state."""
        pending = self._pending_delete
        if not pending:
            return
        self._pending_delete = None

        cards = self.task_lists.setdefault(pending["tab"], [])
        index = min(pending["index"], len(cards))
        cards.insert(index, pending["card"])
        self._hide_toast()
        self.refresh()
        # refresh() has re-parented and shown the card; fade it back in so
        # the restore reads as the inverse of the delete.
        motion.fade_in(pending["card"], theme=self.current_theme)

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
        p.title_input.setText(card.title)
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
            # User-reported, 2026-09-09: this branch never populated the
            # Amount field at all for a Task, so it always showed
            # whatever was left over from a previous edit/add instead of
            # this card's own value.
            p.amount_input.setText(str(getattr(card, "amount", "1")))
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
            card._apply_priority_style(prio_text)
            card.set_title(title)
            card.set_amount(p.amount_input.text().strip() or "1")
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
            card._apply_priority_style(prio_text)
            card.set_title(title)
            card.set_amount(p.amount_input.text().strip() or "1")
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

    # ── Armory state: ONE writer (review G/M1) ───────────────────────────
    # `_build_planner_state` used to be assigned at four sites and only two
    # of them told the dashboard, so the Armory landing page went stale and
    # stayed stale: the Build Planner is a PARENTLESS, MODELESS top-level
    # (ItemDatabase/app.py, `create_window(parent=None)`), so the dashboard
    # sits *visible behind it* -- closing the planner fires neither hide nor
    # show on the page, and nothing re-read the dict.  Every write now goes
    # through the setter below, which is the only place that knows the page
    # has to be told.

    def _set_build_planner_state(self, state: dict | None):
        """The single writer of ``_build_planner_state``.

        Pushes to the Armory dashboard as well, so the page can never
        disagree with the dict.  ``getattr`` because ``__init__`` assigns the
        attribute (as None) before ``_setup_pages()`` builds the page.
        """
        self._build_planner_state = state
        page = getattr(self, "armory_page", None)
        if page is not None:
            page.set_build_planner_state(state)
            page.set_recommendations(self._armory_recommendations(state))

    # ── Armory recommendations (Stage 2, B-armory.md §3.4 #1/#2) ─────────
    # Computed HERE and pushed, not derived in the page: they need the
    # catalog under ItemDatabase/data and a DetailProvider over its detail
    # cache, and ui/pages/armory_page.py's first rule is that it imports
    # neither ItemDatabase nor the network.  The host already owns the one
    # writer of the state (above), so it is also the one place that knows
    # when a recommendation could have changed.

    def _armory_bundle_dir(self) -> Path:
        """``ItemDatabase/``, in both run modes.

        Mirrors ``ItemDatabase/app.py``'s ``_BUNDLE_DIR`` (read-only, not
        imported — importing app.py is the 23 000-line module load this
        page exists to avoid).  Same two branches as
        ``_ensure_item_database_window`` right below: bundled datas extract
        under ``_MEIPASS``, not next to the executable.

        Pure, and no engine import: :meth:`_armory_dirs` needs this to put
        the engine package on ``sys.path`` in the first place.
        """
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS) / "ItemDatabase"
        return self.project_root / "ItemDatabase"

    def _armory_dirs(self) -> tuple[Path, Path]:
        """``(catalog_dir, details_dir)`` — deliberately not one directory.

        This used to be a single ``_armory_data_dir()`` feeding both the
        catalog loader and ``DiskDetailProvider(data_dir / "details")``.
        From source that is correct, because app.py's ``_cache_root()``
        returns ``ItemDatabase/data`` there and the two trees coincide.
        **Frozen they do not**: ``_cache_root()`` returns
        ``user_cache_dir()/armory``, ``ItemDetailCache`` writes its
        ``{id}.json`` files there, and ``"Aion2 TM.spec"`` never ships a
        ``details/`` folder — so the provider was pointed at a directory
        that is empty for the life of the install, and two of the three
        recommendation features could never appear in a release build.
        Invisible from source, invisible to the suite.

        The arithmetic lives in
        :func:`armory_engine.providers.resolve_armory_dirs` so that the host
        and the Armory window cannot disagree about it, and so that a frozen
        layout is assertable from a source run.
        """
        bundle = self._armory_bundle_dir()
        self._ensure_armory_engine_importable(bundle)
        from armory_engine.providers import resolve_armory_dirs

        return resolve_armory_dirs(
            getattr(sys, "frozen", False), bundle, paths.user_cache_dir()
        )

    def _armory_data_dir(self) -> Path:
        """The **catalog** directory (``items_all.json`` & co.)."""
        return self._armory_dirs()[0]

    def _armory_details_dir(self) -> Path:
        """The **runtime detail cache** ``ItemDetailCache`` writes into."""
        return self._armory_dirs()[1]

    @staticmethod
    def _ensure_armory_engine_importable(bundle_dir: Path) -> None:
        """Put ``ItemDatabase/`` on ``sys.path`` for ``import armory_engine``.

        APPENDED, not inserted at 0 the way app.py does it: that directory
        also holds a dozen top-level modules (``app``, ``fetch_*``,
        ``compute_*``), and the host has no business letting any of them win
        a name against its own packages.
        """
        parent = str(bundle_dir)
        if parent not in sys.path:
            sys.path.append(parent)

    def _armory_engine(self):
        """``(recommend module, DetailProvider, DataBundle)``, or ``None``.

        Loaded once per session and memoized: the bundle parses
        ``items_all.json`` (a few MB) and the provider memoizes every detail
        it reads, while the caller below runs on every activation change.
        Re-reading the catalog on each focus change would be a file parse
        per Alt-Tab.

        ``ItemDatabase`` goes on ``sys.path`` for the same reason app.py
        puts it there itself: the engine is a package inside that directory
        (see :meth:`_ensure_armory_engine_importable`).

        The provider gets :meth:`_armory_details_dir`, the bundle gets
        :meth:`_armory_data_dir` — two different trees in a frozen build,
        see :meth:`_armory_dirs`.
        """
        cached = getattr(self, "_armory_engine_cache", None)
        if cached is not None:
            return cached or None
        try:
            catalog_dir, details_dir = self._armory_dirs()
            from armory_engine import providers, recommend

            cached = (
                recommend,
                providers.DiskDetailProvider(details_dir),
                providers.load_data_bundle(catalog_dir),
            )
        except Exception:  # pragma: no cover - a broken engine must not break the app
            logger.exception("Armory recommendations unavailable: engine could not be loaded")
            cached = ()
        self._armory_engine_cache = cached
        return cached or None

    def _armory_recommendations(self, state: dict | None) -> list:
        """The engine's next best actions for ``state`` — never raising.

        A dashboard card is not worth an unhandled exception on a window
        activation, so every failure degrades to "no recommendations", which
        the page renders as its own honest line.
        """
        engine = self._armory_engine()
        if engine is None:
            return []
        recommend, provider, bundle = engine
        try:
            return recommend.next_best_actions(state, provider, bundle)
        except Exception:  # pragma: no cover - same reasoning as above
            logger.exception("Armory recommendations failed for the current build")
            return []

    def _refresh_armory_summary(self):
        """Re-read the live Build Planner into the dict, then the page.

        Reads only: nothing is written to disk, so this is safe to call from
        an event handler and on a template profile alike.  Falls back to the
        persisted dict when the Armory was never opened this session
        (``get_loadout_state`` does that itself, ItemDatabase/app.py).
        Skipped while a profile is loading -- the live window still holds the
        PREVIOUS profile's state at that moment, and pulling it would
        clobber what load_profile just restored.
        """
        if getattr(self, "_profile_loading", False):
            return
        window = getattr(self, "item_database_window", None)
        if window is not None and hasattr(window, "get_loadout_state"):
            pulled = window.get_loadout_state()
            if pulled:
                self._set_build_planner_state(pulled)
                return
        self._set_build_planner_state(self._build_planner_state)

    def changeEvent(self, event):
        """Refresh the dashboard when the app regains focus (review G/M1).

        The user path the review named: dashboard on screen -> CTA -> edit
        gear in the parentless planner -> close it.  No Qt show/hide reaches
        this window, but its activation DOES change, and that is exactly the
        moment the numbers behind the planner became wrong.
        """
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            self._refresh_armory_summary()
        super().changeEvent(event)

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
            # Through the setter like every other path, so there is exactly
            # one line in this file that knows the page must be told.
            self._set_build_planner_state(self._build_planner_state)
            if hasattr(self.item_database_window, "add_to_templates_requested"):
                self.item_database_window.add_to_templates_requested.connect(
                    self._add_item_database_item_to_templates
                )

        return self.item_database_window

    def _add_item_database_item_to_templates(self, item_id: int, name: str):
        """Item Database's right-click "Add to Templates" (User-Wunsch,
        2026-09-05): the user first picks Task or Shopping, then gets the
        same Schedule/Location/Price form used everywhere else for adding a
        template (_TemplateEditDialog) -- pre-filled with Location (from
        the item's real "sources", if its detail happens to be cached
        already) and Price (if the catalog ever carries one; it currently
        never does, kept as a real lookup rather than a hardcoded "0" so it
        starts working the moment that data exists) "falls vorhanden",
        left blank otherwise. Title only ever comes from the picked item;
        everything else stays freely editable in that same dialog."""
        choice_box = QMessageBox(self)
        choice_box.setWindowTitle(tr(self.language, "arm_add_to_template_choice_title"))
        choice_box.setText(tr(self.language, "arm_add_to_template_choice_body", name=name))
        task_btn = choice_box.addButton(tr(self.language, "tab_tasks"), QMessageBox.ActionRole)
        shopping_btn = choice_box.addButton(tr(self.language, "tab_shopping"), QMessageBox.ActionRole)
        choice_box.addButton(QMessageBox.Cancel)
        choice_box.exec()
        clicked = choice_box.clickedButton()
        if clicked not in (task_btn, shopping_btn):
            return
        is_task = clicked is task_btn

        location = ""
        price = ""
        window = self.item_database_window
        if window is not None:
            cached_detail = window.detail_cache.get(item_id)
            sources = (cached_detail or {}).get("sources") or []
            location = ", ".join(sources)
            raw_item = next((it for it in window._raw_items if it.get("id") == item_id), None)
            price = str((raw_item or {}).get("price") or "")

        dlg = _TemplateEditDialog(
            {"title": name, "location": location, "price": price},
            known_locations=self._known_template_locations(is_task),
            parent=self, task_mode=is_task,
            language=self.language, tr_func=tr,
        )
        if not dlg.exec():
            return
        data = dlg.get_data()
        import uuid as _uuid
        data["id"] = str(_uuid.uuid4())
        if is_task:
            self.task_templates.append(data)
            self.tasks_page.update_task_templates(self.task_templates)
        else:
            self.item_templates.append(data)
            self.tasks_page.update_templates(self.item_templates)
        if self.auto_save:
            self.save_profile(silent=True)

    def _known_template_locations(self, is_task: bool) -> list[str]:
        templates = self.task_templates if is_task else self.item_templates
        seen, result = set(), []
        for tmpl in templates:
            loc = (tmpl.get("location") or "").strip()
            if loc and loc not in seen:
                seen.add(loc)
                result.append(loc)
        return result

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
        # KEPT deliberately, against review F-0e's "delete the line".
        #
        # This is an ItemDatabase widget: it renders the item catalog and
        # colours each row by rarity with QStandardItem.setForeground().  It
        # is the one Armory widget that lives INSIDE our widget tree
        # (parent=parent_widget), so unlike the Armory's own parentless
        # windows it does match the app sheet's `QWidget[aion2="true"]`
        # scope.  Its own sheet is the deeper one and wins every property it
        # declares, which is precisely what keeps its rarity colours, its
        # font metrics and its icon-column widths intact.  Dropping it would
        # hand this dialog to a sheet tuned for a different widget set --
        # the same class of regression as the BLOCKER (F-0), just delivered
        # from the other side.  It goes away with the Armory tokenization
        # wave, together with ItemDatabase/styles.qss itself.
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

    # LoadoutWindow.main_tabs index order (see ItemDatabase/app.py's
    # main_tabs.addTab calls in LoadoutWindow.__init__): Equipment=0,
    # Daevanion Board=1, Arcana=2, Skill Planner=3, Pantheon=4, Genius
    # Insight=5. Named here so the Armory dashboard's per-card launchers
    # below don't repeat bare index numbers.
    _DAEVANION_BOARD_TAB = 1
    _SKILL_PLANNER_TAB = 3

    def open_build_planner_window(self):
        logger.debug("Opening Build Planner window")
        window = self._ensure_item_database_window()
        window.open_loadout_window()

    def open_daevanion_board_window(self):
        logger.debug("Opening Build Planner window (Daevanion Board tab)")
        window = self._ensure_item_database_window()
        window.open_loadout_window(tab=self._DAEVANION_BOARD_TAB)

    def open_skill_planner_window(self):
        logger.debug("Opening Build Planner window (Skill Planner tab)")
        window = self._ensure_item_database_window()
        window.open_loadout_window(tab=self._SKILL_PLANNER_TAB)

    def open_crafting_calculator_window(self):
        logger.debug("Opening Crafting Calculator window")
        window = self._ensure_item_database_window()
        window.open_crafting_calculator()

    # ── Overlay: Skill/Gear Priority sections (User-Wunsch, 2026-09-05) ──
    # Read straight from the persisted Build Planner state (_build_planner_
    # state), not a live LoadoutWindow -- that dict is populated on profile
    # load regardless of whether Armory was ever opened this session (see
    # _build_planner_state's own comment). The one exception is skill-id ->
    # name resolution, which needs the ItemDatabase module loaded at least
    # once (ensure_loadout_window() below pays that cost, hidden, the first
    # time one of these sections is actually toggled on in the overlay).

    def get_skill_priority_rows(self) -> list[dict] | None:
        """Flat ranked list (active skills first, then passive -- same
        order as the Priority List itself) for the overlay's Skill Priority
        section. None if there's nothing to show (section stays hidden)."""
        state = self._build_planner_state or {}
        class_name = (state.get("character_class") or "").strip().lower()
        build_name = state.get("current_skill_build_name", "Default")
        build = state.get("skill_builds_data", {}).get(class_name, {}).get(build_name)
        if not class_name or not build:
            return None
        priority = build.get("priority", {})
        ids = [sid for sid in priority.get("active", []) if sid]
        ids += [sid for sid in priority.get("passive", []) if sid]
        if not ids:
            return None

        self._ensure_item_database_window()
        module = self._item_database_module
        skills_by_id = {}
        for skill in module._load_skills_by_class().get(class_name, []):
            skills_by_id[str(skill.get("id"))] = skill

        return [
            {"id": sid, "name": skills_by_id.get(str(sid), {}).get("name", str(sid))}
            for sid in ids
        ]

    def get_equip_priority_rows(self) -> list[tuple[str, dict]] | None:
        """One (section_key, item) pair per equip-priority slot-chain that
        still has a not-yet-checked-off item -- the overlay only ever shows
        the CURRENT item per chain (progressive reveal, User-Wunsch,
        2026-09-05), unlike Skill Priority's flat always-visible list. None
        if nothing qualifies (section stays hidden)."""
        state = self._build_planner_state or {}
        class_name = (state.get("character_class") or "").strip().lower()
        build_name = state.get("current_build_name", "Default")
        build = state.get("equip_builds_data", {}).get(class_name, {}).get(build_name)
        if not class_name or not build:
            return None
        priority = build.get("priority", {})
        progress = build.get("priority_progress", {})
        rows = []
        for section_key, chain in priority.items():
            idx = progress.get(section_key, 0)
            if idx < len(chain) and chain[idx]:
                rows.append((section_key, chain[idx]))
        return rows or None

    def advance_equip_priority(self, section_key: str):
        """Checks off the current item in one Gear Priority chain, called
        from the overlay's check button. Routes through the live Build
        Planner window if it's open AND currently showing the same class +
        build the overlay is reading from (keeps that window's own UI in
        sync); otherwise edits the persisted state dict directly."""
        state = self._build_planner_state or {}
        class_name = (state.get("character_class") or "").strip().lower()
        build_name = state.get("current_build_name", "Default")

        window = self.item_database_window
        live_loadout = window.get_loadout_window_if_open() if window else None
        live_matches = (
            live_loadout is not None
            and live_loadout.character_class_combo.currentText().strip().lower() == class_name
            and live_loadout._current_equip_build_name == build_name
        )
        if live_matches:
            live_loadout.advance_equip_priority(section_key)
            self._set_build_planner_state(window.get_loadout_state())
        else:
            build = state.get("equip_builds_data", {}).get(class_name, {}).get(build_name)
            if build is not None:
                progress = build.setdefault("priority_progress", {})
                chain = build.get("priority", {}).get(section_key, [])
                if progress.get(section_key, 0) < len(chain):
                    progress[section_key] = progress.get(section_key, 0) + 1
        self.save_profile(silent=True)

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
        # 820 exceeded the usable height of a 1366x768 laptop screen (and of
        # a 1920x1080 one with a top+bottom panel), which made the window
        # impossible to fit or resize down on those setups.
        self.setMinimumSize(1100, 700)
        icon_path = self.project_root / "assets" / "icons" / "aion2_tm_icon.ico"
        self.setWindowIcon(QIcon(str(icon_path)))

    def _setup_header(self):
        self.header = HeaderWidget()
        if self._avatar_b64:
            self.header.set_avatar(self._avatar_b64)


    def _setup_central_widget(self):
        self.background = ThemedBackground()
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

        # A row, not a bare label, so a toast can carry ONE action button
        # (UX audit 2026-09-18, C2 -- "Task removed / Undo"). The label keeps
        # its #toastLabel objectName so every existing QSS rule still
        # matches; the container and the button get their own names rather
        # than any inline colour (the design pass owns the styling).
        self.toast_widget = QWidget()
        self.toast_widget.setObjectName("toastBar")

        toast_row = QHBoxLayout(self.toast_widget)
        toast_row.setContentsMargins(0, 0, 0, 0)
        toast_row.setSpacing(10)

        # The "✓ " the toast used to prepend to every message was a
        # dingbat inside the *text*, so it was also inside everything that
        # read that text back (five assertions across two test modules).
        # It is a real icon beside the label now.
        self.toast_icon = icons.IconLabel("circle-check", 16, "ok")
        self.toast_icon.setObjectName("toastIcon")

        self.toast_label = QLabel()
        self.toast_label.setObjectName("toastLabel")

        self.toast_action_btn = QPushButton()
        self.toast_action_btn.setObjectName("toastActionButton")
        self.toast_action_btn.setCursor(Qt.PointingHandCursor)
        self.toast_action_btn.clicked.connect(self._on_toast_action)
        self.toast_action_btn.hide()

        toast_row.addWidget(self.toast_icon)
        toast_row.addWidget(self.toast_label)
        toast_row.addWidget(self.toast_action_btn)
        toast_row.addStretch()

        self.toast_widget.hide()
        self._toast_action = None
        self._toast_action_key = None
        self._toast_seq = 0
    
    def _setup_sidebar(self):
        self.sidebar = SidebarWidget()
        self._update_armory_visibility()

    def _update_armory_visibility(self):
        # Item Database / Crafting Calculator / Build Planner: fully
        # released now (ARMORY_ENABLED, see core/version.py -- the old
        # self-service "Beta Bereich freischalten" opt-in toggle in
        # Settings is gone, since it's no longer needed once this is
        # permanently True). Marked "(Expert)" in the sidebar rather than
        # a plain label, since it's still the app's more advanced area.
        self.sidebar.buttons["armory"].setVisible(ARMORY_ENABLED)
        self.sidebar.set_armory_expert_marked(ARMORY_ENABLED)
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
        # State is PUSHED in, by _set_build_planner_state() -- the page
        # pulls nothing and holds no callable of ours (review G/m10: the
        # `state_provider=lambda: self._build_planner_state` this replaces
        # re-created the MainWindow->page->lambda->MainWindow cycle the
        # same batch removed from the task cards).
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

        self.overlay_toggle_btn = QPushButton("Overlay")
        self.overlay_toggle_btn.setObjectName("overlayToggleBtn")
        icons.set_icon(self.overlay_toggle_btn, "eye", 16, clear_text=False)
        self.overlay_toggle_btn.setCheckable(True)
        self.overlay_toggle_btn.clicked.connect(self._toggle_overlay)
        self.left_layout.addWidget(self.overlay_toggle_btn)

        self.content_layout.addWidget(self.page_stack, 1)
        self.content_layout.addWidget(self.toast_widget)

        self.main_layout.addWidget(self.left_panel)
        self.main_layout.addWidget(self.content_container, 1)


    def _connect_signals(self):
        if hasattr(self.sidebar, "page_changed"):
            self.sidebar.page_changed.connect(self.handle_sidebar_page_changed)

        self.tasks_page.task_add_requested.connect(self.add_task_from_page)
        self.tasks_page.standard_apply_requested.connect(self._apply_standard_templates_to_existing)
        self.tasks_page.tab_changed.connect(self.select_tab)

        self.timers_page.manage_timers_requested.connect(self.open_custom_timer_manager)
        self.timers_page.timer_settings_requested.connect(self.open_timer_settings)

        self.armory_page.open_item_database_requested.connect(self.open_item_database_window)
        self.armory_page.open_crafting_calculator_requested.connect(self.open_crafting_calculator_window)
        self.armory_page.open_build_planner_requested.connect(self.open_build_planner_window)
        self.armory_page.open_daevanion_requested.connect(self.open_daevanion_board_window)
        self.armory_page.open_skill_planner_requested.connect(self.open_skill_planner_window)

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

        if hasattr(self.settings_page, "reduce_motion_changed"):
            self.settings_page.reduce_motion_changed.connect(
                self.set_reduce_motion
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
        self.tasks_page.char_filter_changed.connect(self.set_task_char_filter)
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

        if hasattr(self.settings_page, "restore_default_profiles_requested"):
            self.settings_page.restore_default_profiles_requested.connect(self._restore_default_profiles)

        if hasattr(self.settings_page, "season_reset_changed"):
            self.settings_page.season_reset_changed.connect(self._on_season_reset_changed_from_page)

        if hasattr(self.settings_page, "dps_start_requested"):
            self.settings_page.dps_start_requested.connect(self._start_dps_meter)

        # AION2TM_NO_UPDATE_CHECK=1 skips the startup update check (tests, CI,
        # packaged Linux builds where the distribution channel owns updates).
        # Without it, any event-loop pump 2 s after construction starts a real
        # network QThread that can still be running at interpreter exit.
        if not os.environ.get("AION2TM_NO_UPDATE_CHECK"):
            QTimer.singleShot(2000, self, self.run_update_check)

        # News popup (Teil 2, @koordinator 2026-09-26): same startup-timer
        # pattern as the update check above, gated behind NEWS_POPUP_ENABLED
        # (ui/news_dialog.py) until format/frequency/dismiss-behaviour/i18n
        # are settled with the real WordPress site. AION2TM_NO_UPDATE_CHECK
        # also skips this -- same "no network thread at interpreter exit in
        # tests/CI" reasoning as the update checker.
        if NEWS_POPUP_ENABLED and not os.environ.get("AION2TM_NO_UPDATE_CHECK"):
            QTimer.singleShot(2500, self, self.run_news_check)

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
            return f"{days}{tr(self.language, 'day_abbrev')} {hours:02}:{minutes:02}"

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

        season_text = self._get_season_countdown_text() if self.season_enabled else ""
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
                elif mode == "countdown":
                    dur = max(1, ct.get("countdown_duration_seconds", 7200))
                    if not ct.get("countdown_active"):
                        ct_text = self._format_custom_countdown(dur, "hh:mm:ss")
                        self._custom_notified[i] = False
                        seconds = None
                    else:
                        delay = max(0, min(60, ct.get("countdown_restart_delay_seconds", 0)))
                        phase, remaining = self._get_countdown_phase(
                            dur, delay, ct.get("countdown_started_at"), now
                        )
                        ct_text = self._format_custom_countdown(remaining, "hh:mm:ss")
                        if phase == "delay":
                            ct_text = f"⟳ {ct_text}"
                        # Only the "duration about to elapse" moment should
                        # notify -- not the auto-restart delay's own countdown.
                        seconds = remaining if phase == "running" else None
                else:  # hourly (default, backward compat)
                    next_ct = self._get_next_custom_timer_time_seconds(
                        max(60, ct.get("interval_minutes", 60) * 60),
                        ct.get("start_time", "00:00"),
                    )
                    seconds = (next_ct - now).total_seconds()
                    ct_text = self._format_custom_countdown(seconds, "hh:mm:ss")
                self.timers_page.set_custom_timer_countdown(i, ct_text)
                if seconds is None:
                    continue
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
        # MainWindow is the authority on which tab is active (it restores it
        # from the profile), so it has to move the highlight too -- see
        # TasksPage.mark_active_tab.
        self.tasks_page.mark_active_tab(tab)
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
                return f"{days}{tr(self.language, 'day_abbrev')} {hours:02d}:{minutes:02d}"
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

        if self.todo_char_filter:
            tasks = [
                task for task in tasks
                if getattr(task, "character", "") == self.todo_char_filter
            ]

        self.tasks_page.render_tasks(tasks)
        total = len(tasks)
        done = len([t for t in tasks if t.completed])

        open_count = total - done

        # Matches by the snapshotted card_id from _record_missed_daily_
        # activities (last daily reset) -- so this counts only cards from
        # THAT exact snapshot that are still in the currently visible tab/
        # filter, not a fresh live "still open" guess (User-Wunsch,
        # 2026-09-07: "Genauso die Regel dahinter bauen", after asking for
        # a live Missed stat here too -- previously this data only ever
        # reached the exported Full View page's own "Missed (Yesterday)"
        # tile). Switched from (title, character) text-matching to
        # card_id (User-Wunsch, 2026-09-09) -- text-matching couldn't
        # distinguish two same-named cards and wrongly flagged a brand-new
        # card sharing an old one's title+character.
        # Checking a missed card off clears its tag/count immediately
        # (User-Wunsch, 2026-09-09: "sobald eine Missed Karte abgehakt
        # wird, sollte der Tag verschwinden") -- `completed` is checked
        # here too, not just card_id membership, since the snapshot itself
        # only gets REPLACED at the next daily reset and has no way to
        # know you already handled one of its entries in the meantime.
        missed_ids = {m.get("card_id", "") for m in self.missed_daily_activities if m.get("card_id")}
        missed_count = len([t for t in tasks if getattr(t, "card_id", "") in missed_ids and not t.completed])

        # Tags the actual cards, not just the aggregate count above (User-
        # reported, 2026-09-09: "man sieht keinen Tag der Einträge ... als
        # missed markiert" -- the stat tile alone didn't say WHICH card).
        # Runs over BOTH lists, not just the current tab/filter's `tasks`,
        # so the tag stays correct immediately on switching tabs instead of
        # only updating on this tab's next refresh().
        for card_list in (self.task_lists.get("tasks", []), self.task_lists.get("shopping", [])):
            for card in card_list:
                if hasattr(card, "set_missed"):
                    card.set_missed(getattr(card, "card_id", "") in missed_ids and not card.completed)

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

        self.tasks_page.update_stats(total, done, open_count, missed_count)

        if self.active_tab == "shopping":
            parts = []
            if total_kinah_k > 0:
                parts.append(self.format_kinah_price(total_kinah_k))
            # AP/NP/SC all get the same thousands/k-m scaling as Kinah
            # (User-Wunsch, 2026-09-05: first just SC, then "jetzt noch die
            # gleiche Anpassung für NP und AP" -- matches the same fix
            # already applied to ShoppingCard.format_price for individual
            # item prices).
            if total_ap > 0:
                parts.append(self.format_scaled_price(total_ap, "AP"))
            if total_np > 0:
                parts.append(self.format_scaled_price(total_np, "NP"))
            if total_sc > 0:
                parts.append(self.format_scaled_price(total_sc, "Coins"))
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

    @staticmethod
    def _asset_base_path() -> Path:
        """Root the QSS's ``url(ASSET_PATH/...)`` references resolve against.

        ``sys._MEIPASS`` when frozen (PyInstaller extracts the bundled datas
        there), the repo root in a dev checkout.
        """
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        return Path(__file__).resolve().parent.parent

    def load_styles(self):
        """Render the token template for the active theme onto the *application*.

        One sheet for the whole process, not one per window: OverlayWindow,
        FlowMapWindow and the ItemDatabase window are all parentless
        top-levels, so a ``MainWindow.setStyleSheet`` never reached them
        through the widget-tree cascade and each needed its own hand-pushed
        copy (three delivery paths, three chances to drift).
        ``QApplication.setStyleSheet`` reaches every one of them, including
        windows created later (MASTER §4-1).
        """
        app = QApplication.instance()
        if app is None:  # a widget built without an app cannot be styled anyway
            logger.warning("load_styles(): no QApplication — stylesheet not applied")
            return ""

        theme.set_current(self.current_theme)
        base = self._asset_base_path().as_posix()

        # QApplication.setStyleSheet re-resolves the sheet against EVERY
        # widget of EVERY open window, so it is by far the most expensive
        # call in a theme switch -- and apply_theme() runs on every profile
        # load, which usually means "the same theme again".  Re-applying an
        # identical sheet is pure cost, so it is skipped; the key is global
        # because the sheet is (one QApplication per process).
        global _APPLIED_STYLE_KEY
        if _APPLIED_STYLE_KEY == (self.current_theme, base) and app.styleSheet():
            return app.styleSheet()

        styles = theme.build_qss(self.current_theme, base)
        app.setStyleSheet(styles)
        _APPLIED_STYLE_KEY = (self.current_theme, base)
        logger.debug(
            "Stylesheet rendered for theme %r (%d bytes)", self.current_theme, len(styles)
        )
        return styles

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


    def _tray_ready(self) -> bool:
        """True when a tray icon was actually created (see _setup_tray_icon)."""
        return hasattr(self, "tray_icon")

    def _notify(self, title: str, message: str, msecs: int = 5000):
        """Desktop balloon through the tray when there is one, in-app toast
        otherwise. On a bare Wayland session without a StatusNotifier host
        (Hyprland with no Waybar tray module, a minimal WM, a headless test)
        showMessage() is silently swallowed, which used to lose every
        notification the app produced."""
        if self._tray_ready():
            self.tray_icon.showMessage(
                title, message,
                QSystemTrayIcon.MessageIcon.Information,
                msecs,
            )
            return
        self.show_toast(message)

    def _setup_tray_icon(self):
        # Must run after QApplication exists -- QSystemTrayIcon.isSystemTrayAvailable()
        # segfaults when called before it (PySide6 6.11). Called from __init__,
        # which is only reached once main.py has constructed the app.
        if not tray_available():
            logger.info("No system tray available -- notifications fall back to in-app toasts")
            return
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

        # Same reasoning as in load_profile: the undo window cannot outlive
        # the session.  Committed on each path that actually CLOSES the app,
        # not here -- hiding into the tray does not end the session, and
        # committing before the tray branch silently ended the undo window
        # every time the user closed the window with tray mode on (review
        # F-8; the comment used to claim the behaviour this now has).
        if getattr(self, "_force_quit", False):
            self._commit_pending_delete()
            self.save_profile(silent=True)
            event.accept()
            QApplication.instance().quit()
            return

        # Hiding into a tray that does not exist would strand the window with
        # no way back, so the preference is honoured only when there IS a tray.
        # The stored setting is deliberately left untouched: the same profile
        # may well be used on a machine that has one.
        if self.minimize_to_tray is True and self._tray_ready():
            event.ignore()
            self.hide()
            self._notify("Aion 2 Companion", tr(self.language, "tray_running"), 3000)
            return

        if self.minimize_to_tray is None and self._tray_ready():
            box = QMessageBox(self)
            box.setWindowTitle(tr(self.language, "tray_minimize_title"))
            box.setText(tr(self.language, "tray_minimize_text"))
            tray_btn = box.addButton(
                tr(self.language, "tray_minimize_yes"), QMessageBox.AcceptRole
            )
            box.addButton(
                tr(self.language, "tray_minimize_no"), QMessageBox.RejectRole
            )
            box.exec()
            if box.clickedButton() is tray_btn:
                self.minimize_to_tray = True
                self._save_app_config()
                event.ignore()
                self.hide()
                self._notify("Aion 2 Companion", tr(self.language, "tray_running"), 3000)
            else:
                self.minimize_to_tray = False
                self._save_app_config()
                self._commit_pending_delete()
                self.save_profile(silent=True)
                event.accept()
                QApplication.instance().quit()
            return

        self._commit_pending_delete()
        self.save_profile(silent=True)
        event.accept()
        QApplication.instance().quit()

    def _launch_dps_meter_if_configured(self):
        if self.dps_meter_autostart and self.dps_meter_path:
            self._start_dps_meter(self.dps_meter_path)

    def _start_dps_meter(self, path: str):
        """Launches the user's configured external DPS Meter tool.

        On Windows this still goes through ShellExecuteEx with
        SEE_MASK_FLAG_NO_UI rather than the simpler os.startfile
        (core.platform.launch_windows_shellexecute holds the verbatim code and
        the full rationale): User-reported, 2026-08-30, declining the UAC
        elevation prompt for a DPS Meter that requires admin rights also popped
        up a SECOND "elevation failed" dialog carrying OUR app's taskbar icon,
        since we are the process that requested the launch. The UAC consent
        prompt itself is a Windows security boundary and is NOT suppressed --
        only the shell's follow-up error UI is, so a declined elevation comes
        back as an error code we log instead of a confusing second popup.

        Off Windows there is no UAC and no shell verb: a plain Popen from the
        program's own directory is the correct equivalent (a Windows .exe is
        routed through wine when it is installed).
        """
        if not path:
            return
        launch_external(Path(path), elevate_hint=True)

    def _fire_notification(self, title: str, message: str):
        self._notify(title, message)
        play_wav(self.notification_sound)

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
    def _get_countdown_phase(
        duration_seconds: int, delay_seconds: int, started_at_str: str | None, now: "datetime"
    ) -> tuple:
        """Returns (phase, remaining_seconds) for a running Countdown Timer.
        "running" while counting down the configured duration; "delay"
        while waiting out the configured auto-restart delay before the next
        cycle starts. Modulo-based (same idea as
        _get_next_custom_timer_time_seconds) so it stays correct however
        much wall-clock time passed while the app was closed, instead of
        needing to step through every missed cycle one at a time."""
        if not started_at_str:
            return "running", float(duration_seconds)
        try:
            started_at = datetime.fromisoformat(started_at_str)
        except ValueError:
            return "running", float(duration_seconds)
        cycle_length = duration_seconds + delay_seconds
        if cycle_length <= 0:
            return "running", float(duration_seconds)
        elapsed = (now - started_at).total_seconds()
        position = elapsed % cycle_length
        if position < duration_seconds:
            return "running", duration_seconds - position
        return "delay", cycle_length - position

    def toggle_countdown_timer(self, idx: int):
        """Starts/stops a Countdown Timer's Start/Stop button -- called from
        both the overlay row and the Timers page card. Stopping clears the
        anchor entirely (fully resets to the static configured duration)
        rather than pausing/resuming, matching the simple Start/Stop the
        feature was asked for."""
        if idx >= len(self.custom_timers):
            return
        ct = self.custom_timers[idx]
        if ct.get("timer_mode") != "countdown":
            return
        if ct.get("countdown_active"):
            ct["countdown_active"] = False
            ct.pop("countdown_started_at", None)
        else:
            ct["countdown_active"] = True
            ct["countdown_started_at"] = datetime.now().isoformat()
        self._custom_notified[idx] = False
        if self.auto_save:
            self.save_profile(silent=True)
        self.update_countdowns()
        if hasattr(self, "overlay") and self.overlay.isVisible():
            self.overlay.refresh()

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

    def _format_custom_countdown(self, seconds: float, fmt: str) -> str:
        s = max(0, int(seconds))
        if fmt == "mm:ss":
            total_minutes, secs = divmod(s, 60)
            return f"{total_minutes:02}:{secs:02}"
        if fmt == "dd:hh:mm":
            days, remainder = divmod(s, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, secs = divmod(remainder, 60)
            if days > 0:
                return f"{days}{tr(self.language, 'day_abbrev')} {hours:02}:{minutes:02}:{secs:02}"
            return f"{hours:02}:{minutes:02}:{secs:02}"
        # default: hh:mm:ss
        minutes, secs = divmod(s, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02}:{minutes:02}:{secs:02}"

    def _fire_custom_notification(self, name: str, sound_path: str, warn_minutes: int = 0):
        msg = f"{name} läuft jetzt ab!" if warn_minutes <= 0 else f"{name} läuft in {warn_minutes} Min ab!"
        self._notify(name, msg)
        play_wav(sound_path)

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
        dlg = CustomTimerManagerDialog(
            self.timer_categories, self.custom_timers,
            language=self.language, tr_func=tr, parent=self,
        )
        if dlg.exec():
            self.timer_categories = dlg.get_categories()
            self.custom_timers = dlg.get_custom_timers()
            self._custom_notified = [False] * 8
            self.timers_page.rebuild_custom_sections(self.timer_categories, self.custom_timers)
            if self.auto_save:
                self.save_profile(silent=True)

    def _ask_unreadable_profile_choice(self, profile_path: Path) -> str:
        """Modal asking what to do about a profile that could not be read.

        Returns "overwrite" or "keep". Split out from the handler below so a
        test can drive both answers without a real dialog.
        """
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(tr(self.language, "profile_unreadable_title"))
        box.setText(tr(self.language, "profile_unreadable_text", file=profile_path))
        save_btn = box.addButton(
            tr(self.language, "profile_unreadable_overwrite"), QMessageBox.AcceptRole
        )
        box.addButton(tr(self.language, "profile_unreadable_keep"), QMessageBox.RejectRole)
        box.setDefaultButton(box.buttons()[-1])
        box.exec()
        return "overwrite" if box.clickedButton() is save_btn else "keep"

    def _handle_unreadable_profile(self, profile_path: Path):
        """Tell the user the profile is unreadable and let them choose.

        A safety system that engages without saying so is indistinguishable,
        from the user's chair, from the app being broken: before this, a
        profile whose file AND .bak were both unparsable silently disabled
        auto-save for the whole session, with nothing but a line in app.log.

        "Save anyway" copies the unreadable file aside (so a manual rescue
        stays possible) and releases the guard; "Keep the file" leaves
        auto-save off, and says so once.
        """
        if self._ask_unreadable_profile_choice(profile_path) == "overwrite":
            from core.persistence import snapshot_corrupt

            snapshot = snapshot_corrupt(profile_path)
            self._profile_loading = False
            self._profile_unreadable = False
            self._autosave_disabled_notified = False
            self.show_toast(
                tr(self.language, "profile_unreadable_snapshot", file=snapshot.name)
                if snapshot else tr(self.language, "profile_saved")
            )
            return
        self._note_autosave_disabled()

    def _note_autosave_disabled(self):
        """Say once per session that auto-save is off. Called from the dialog
        above and from every skipped auto-save, so the message reappears if
        the user never saw the modal (a load that failed before the UI was
        up, for instance) -- but never turns into a toast storm."""
        if self._autosave_disabled_notified:
            return
        self._autosave_disabled_notified = True
        self.show_toast(tr(self.language, "profile_autosave_disabled"))

    def load_profile(self, profile_path):
        # Self-healing load (audit §2): a truncated/corrupt profile is no
        # longer silently turned into {} -- load_json_with_fallback tries the
        # <name>.json.bak copy atomic_write_json keeps, and tells us which
        # copy we actually got so the user can be warned (and so a file that
        # is beyond rescue never gets overwritten).
        from core.persistence import load_json_with_fallback

        # A card whose undo window is still open belongs to the profile we
        # are about to leave -- commit it against THAT profile (self.profile_
        # name is still the old one here) rather than let the switch quietly
        # resurrect or strand it (UX audit 2026-09-18, C2).
        self._commit_pending_delete()

        profile_path = Path(profile_path)
        data, status = load_json_with_fallback(profile_path)

        # Nothing may save while the fields below are still half-restored
        # (see save_profile's guard and the call-order note at the end).
        self._profile_loading = True

        # Both the profile AND its backup are unreadable: keep the guard on
        # past this method so no auto-save buries whatever is still on disk.
        # Only a deliberate "Save Profile" click writes from here on.
        unrecoverable = status == "empty" and profile_path.exists()
        # Why the guard is on matters: `_profile_loading` is also True during
        # a perfectly normal load, and only the unreadable-file case may
        # snapshot and warn.
        self._profile_unreadable = unrecoverable
        if unrecoverable:
            logger.error(
                "Profile %s and its backup are both unreadable -- loaded as empty; "
                "auto-save stays disabled so the file on disk is not overwritten.",
                profile_path,
            )

        try:
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
            self.season_enabled = settings.get("season_enabled", False)

            from datetime import date as _date
            _d = settings.get("last_daily_reset_date")
            self.last_daily_reset_date = _date.fromisoformat(_d) if _d else None
            _w = settings.get("last_weekly_reset_date")
            self.last_weekly_reset_date = _date.fromisoformat(_w) if _w else None
            self.last_season_reset_datetime = settings.get("last_season_reset_datetime")
            self.missed_daily_activities = settings.get("missed_daily_activities", [])

            self.show_events = settings.get("show_events", True)
            # Straight into ui.motion: the profile's own preference has to be
            # live before the first fade this load could trigger.
            self.set_reduce_motion(settings.get("reduce_motion", False), save=False)
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
            self.timers_page.set_season_visible(bool(self.season_enabled and self._get_season_countdown_text()))

            self.timer_categories = settings.get("timer_categories", ["Custom Timer"]) or ["Custom Timer"]
            self.custom_timers = settings.get("custom_timers", [])[:8]
            for ct in self.custom_timers:
                if "timer_mode" not in ct:
                    ct["timer_mode"] = "hourly"
            self._custom_notified = [False] * 8
            self.timers_page.rebuild_custom_sections(self.timer_categories, self.custom_timers)

            saved_overlay_sections = settings.get("overlay_visible_sections")
            if isinstance(saved_overlay_sections, dict):
                self.overlay_visible_sections.update(saved_overlay_sections)
            self.overlay_char_filter = settings.get("overlay_char_filter", "")
            self.todo_char_filter = settings.get("todo_char_filter", "")
            self.tasks_page.set_char_filter_value(self.todo_char_filter)

            self.toggle_events()

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
                            card_id=item.get("card_id", ""),
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
                            card_id=item.get("card_id", ""),
                            amount=item.get("amount", "1"),
                        )

                    if item.get("completed", False):
                        card.set_completed(True)

                    self._wire_card(card)
                    self.task_lists[tab].append(card)

            self.item_templates = data.get("item_templates", [])
            self.task_templates = data.get("task_templates", [])
            # Named Standard Template Sets (Planner: "Mehrere benennbare/
            # umbenennbare Standard-Template-Sets", freigegeben 2026-09-23)
            # -- migrate_standard_templates handles both an old profile's
            # flat list (wrapped into one set) and an already-migrated
            # named-dict profile (passed through unchanged) the same way,
            # so every load -- regardless of when the profile was last
            # saved -- ends up in the current {"tasks": {name: [...]}} shape.
            from core.persistence import migrate_standard_templates
            self.standard_templates = migrate_standard_templates(data.get("standard_templates"))
            self.tasks_page.update_templates(self.item_templates)
            self.tasks_page.update_task_templates(self.task_templates)
            self.tasks_page.update_standard_templates(self.standard_templates)

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
            # The setter pushes to the Armory dashboard itself.
            self._set_build_planner_state(data.get("build_planner"))
            if self.item_database_window and hasattr(self.item_database_window, "set_pending_loadout_state"):
                self.item_database_window.set_pending_loadout_state(self._build_planner_state)

            self._rebuild_characters()
            if hasattr(self.header, "set_profile"):
                self.header.set_profile(self.profile_name)
        finally:
            # Restore finished -- releasing the guard HERE, before
            # update_countdowns() below, deliberately keeps that call's
            # documented behaviour intact (a reset that is due at load time
            # still persists itself), while everything above it is now
            # structurally unable to save stale state. The guard stays on
            # only when the file on disk could not be read at all.
            self._profile_loading = unrecoverable

        if status == "bak":
            self.show_toast(tr(self.language, "profile_restored_from_backup"))
        elif unrecoverable:
            self._handle_unreadable_profile(profile_path)

        # Real, confirmed data-loss bug found + fixed (User-reported,
        # 2026-09-10, screenshot: a 122 KB profile got reduced to 23 KB just
        # from starting the packaged app; recurrence found + fixed 2026-09-14,
        # this time hitting build_planner specifically -- log evidence: a
        # "Profile saved" line landing BEFORE that same launch's "Profile
        # loaded" line): update_countdowns() ends by calling
        # check_auto_resets() -- which, whenever a daily/weekly reset is
        # actually due (a completely normal, frequent case: any time more
        # than a day/week has passed since the profile was last opened),
        # calls save_profile(silent=True) immediately. save_profile() reads
        # self._build_planner_state (among everything else restored above)
        # -- calling update_countdowns() from ANY point in this method
        # before every single field above has been restored from `data`
        # serializes that field's STALE pre-load value (here: whatever the
        # PREVIOUS profile/session left behind, or None on a fresh start)
        # straight over the real profile file on disk, permanently
        # destroying just that field while everything restored earlier
        # stays intact -- which is exactly why the first incident only ever
        # showed up as tasks/templates loss, and this one only ever showed
        # up as Build Planner/Armory loss. Fix: always call this LAST, only
        # once every single field this method restores is truly in place.
        self.update_countdowns()

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
                "card_id": getattr(card, "card_id", ""),
                "completed": card.completed,
            }

        return {
            "type": "task",
            "priority": getattr(card, "priority_value", "low"),
            "title": getattr(card, "title", card.title_label.text()),
            "description": card.desc_label.text(),
            "event": getattr(card, "is_event", False),
            "schedule": getattr(card, "schedule", "daily"),
            "character": getattr(card, "character", ""),
            "template_id": getattr(card, "template_id", ""),
            "location": getattr(card, "location", ""),
            "card_id": getattr(card, "card_id", ""),
            "amount": getattr(card, "amount", "1"),
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
        # Re-entrancy guard, the STRUCTURAL half of the 2.0.5 data-loss fix
        # (the other half is the call ORDER documented at the end of
        # load_profile). While load_profile is restoring, every attribute
        # read below may still hold the PREVIOUS profile's value (or None),
        # so any save triggered from inside that window -- most famously
        # update_countdowns() -> check_auto_resets() -> save_profile() when a
        # daily/weekly reset is due -- would write stale data straight over
        # the real file. The flag also stays True after a load that found
        # BOTH the profile and its .bak unreadable, so a corrupt file is
        # never overwritten by a background auto-save; a deliberate
        # "Save Profile" click (explicit=True) is the user's way out.
        if self._profile_loading and not explicit:
            logger.debug("save_profile skipped: profile load in progress / profile file unreadable")
            if self._profile_unreadable:
                self._note_autosave_disabled()
            return

        if explicit and self._profile_unreadable:
            # The guard is on because the file on disk could not be parsed.
            # This deliberate save is about to overwrite it, so preserve it
            # first -- the user may still want to hand-repair the original.
            from core.persistence import snapshot_corrupt

            snapshot_corrupt(self.profile_dir / f"{self.profile_name}.json")
            self._profile_unreadable = False

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
        # Pulled BEFORE the template guard below (review G/M2): the pull
        # only reads the live planner into memory and pushes it to the
        # dashboard -- it writes no file, so it must not be skipped for a
        # template profile.  It was, and the consequence was the first-run
        # path: a new user on "Default" equipped a full set and the Armory
        # page still said "No build yet" until they renamed the profile.
        if self.item_database_window and hasattr(self.item_database_window, "get_loadout_state"):
            self._set_build_planner_state(self.item_database_window.get_loadout_state())

        if not explicit and self._is_lang_default(self.profile_dir / f"{self.profile_name}.json"):
            return

        data = {
            "profile_name": self.profile_name,
            "theme": self.current_theme,
            "language": self.language,

            "settings": {
                "daily_reset_time": self.daily_reset_time,
                "weekly_reset_day": self.weekly_reset_day,
                "weekly_reset_time": self.weekly_reset_time,
                "season_reset_datetime": self.season_reset_datetime,
                "season_enabled": self.season_enabled,

                "show_events": self.show_events,
                "reduce_motion": self.reduce_motion,

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
                "last_season_reset_datetime": self.last_season_reset_datetime,
                "missed_daily_activities": self.missed_daily_activities,
                "overlay_visible_sections": self.overlay_visible_sections,
                "overlay_char_filter": self.overlay_char_filter,
                "todo_char_filter": self.todo_char_filter,
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

        # Local import, mirroring this file's existing in-method imports --
        # keeps the new dependency next to the only two places that use it.
        from core.persistence import atomic_write_json, stamp_schema

        # tmp + fsync + .bak rotation + os.replace: a crash mid-write can no
        # longer truncate the profile (audit §2, "non-atomic writes"), and the
        # previous good content always survives one write as <name>.json.bak.
        atomic_write_json(profile_path, stamp_schema(data))

        self.save_last_profile(profile_path)

        logger.debug("Profile saved: %s", profile_path)
        if not silent:
            self.show_toast(tr(self.language, "profile_saved"))

    def _resolve_profile_dir(self) -> Path:
        """Where this installation keeps its profiles, in strict precedence:

        1. ``config.json``'s ``profile_dir``, when that path still exists --
           the user's explicit choice always wins.
        2. Running from source: ``<repo>/profiles`` when present. That folder
           *is* the developer's profile directory; nothing to opt into.
        3. Frozen: ``<install>/profiles`` when it already holds ``*.json``
           (an existing install, including every portable one that predates
           the marker -- their profiles must not appear to vanish just
           because a stored absolute path stopped resolving), OR when
           ``portable.txt`` sits next to the executable (the documented way
           to CREATE a new portable installation).
        4. Otherwise the per-user data directory
           (``%APPDATA%\\Aion2 TM\\Profiles`` on Windows).

        The marker is looked up next to the EXECUTABLE (``paths.install_root()``
        == ``self.project_root``), never under ``sys._MEIPASS``: for this
        onedir build that is ``<install>/_internal``, a directory the user
        never sees and where the documentation never tells them to put it.
        A bare empty ``profiles/`` folder is deliberately not enough to flip a
        frozen install into portable mode -- a system-wide install must never
        write next to its own read-only files, and an installer that happened
        to create the folder would silently redirect every fresh install.
        """
        # 1. User hat explizit einen Pfad gesetzt → immer bevorzugen
        if self.app_config_path.exists():
            try:
                cfg = json.loads(self.app_config_path.read_text(encoding="utf-8"))
                self.dps_meter_path = cfg.get("dps_meter_path", "")
                self.dps_meter_autostart = cfg.get("dps_meter_autostart", False)
                raw_mtt = cfg.get("minimize_to_tray", None)
                self.minimize_to_tray = bool(raw_mtt) if raw_mtt is not None else None
                self._avatar_b64 = cfg.get("avatar", "")
                self._last_seen_news_id = cfg.get("last_seen_news_id", 0)
                custom = cfg.get("profile_dir", "")
                if custom:
                    p = Path(custom)
                    if p.exists():
                        return p
            except Exception:
                pass

        # 2./3. profiles/ next to the app (see the docstring above).
        local_dir = self.project_root / "profiles"
        frozen = getattr(sys, "frozen", False)
        if not frozen:
            if local_dir.exists():
                return local_dir
        else:
            if any(local_dir.glob("*.json")) or paths.is_portable(paths.install_root()):
                return local_dir

        # 4. Neue Installation → per-user data dir
        return paths.default_profiles_dir()

    def _save_app_config(self):
        cfg = {
            "profile_dir": str(self.profile_dir),
            "dps_meter_path": self.dps_meter_path,
            "dps_meter_autostart": self.dps_meter_autostart,
            "minimize_to_tray": self.minimize_to_tray,
            "avatar": self._avatar_b64,
            "last_seen_news_id": self._last_seen_news_id,
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
        self.show_toast(tr(self.language, "profile_path_saved"))

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

    def _bundled_default_profiles_dir(self) -> Path:
        """Where the 3 language Default profiles ship with THIS installed
        version (User-Wunsch, 2026-09-10, after discovering the packaged app
        never bundled profiles/ at all -- see Aion2 TM.spec's own comment on
        the "default_profiles" datas entries). Frozen: PyInstaller onedir
        extracts bundled datas under sys._MEIPASS (the _internal/ folder),
        never next to the exe. Dev: profiles/ IS the real, current source
        of truth already, no separate bundle needed."""
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS) / "default_profiles"
        return self.project_root / "profiles"

    def _refresh_default_profiles_backup(self) -> Path:
        """Mirrors this version's bundled Default profiles into profile_dir/
        Backup/ on every launch (User-Wunsch, 2026-09-10: "Dann machen wir in
        der App ein 'Backup Verzeichnis' - in dem liegen dann die
        Defaults"). Backup/ is purely internal/never user-edited, so
        silently overwriting it here every start is always safe -- unlike
        the user's own live Default.json etc., which only the "Restore
        Default Profile" button (with its own confirmation) ever touches.
        Returns the Backup directory path."""
        backup_dir = self.profile_dir / "Backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        src_dir = self._bundled_default_profiles_dir()
        for stem in ("Default", "Default_de", "Default_ru"):
            src = src_dir / f"{stem}.json"
            if src.exists():
                try:
                    shutil.copy2(src, backup_dir / f"{stem}.json")
                except OSError:
                    pass
        return backup_dir

    def _load_default_standard_templates(self) -> dict:
        """The language-matched Default profile's OWN Standard Template
        Sets -- read-only reference for TemplateDialog's "⟳ Sync" (User-
        Wunsch, 2026-09-10: let an existing profile pull in Standard
        Template entries a later update added to Default). Reads from
        profile_dir/Backup/ (this version's pristine bundled copy, refreshed
        every launch) rather than the user's own live Default.json -- that
        live file could itself be the user's heavily-customized profile,
        which would make Sync compare it against itself and always find
        nothing new. Tolerant of a missing/unreadable file since this is a
        non-critical convenience feature, not core profile data.

        Named-Set shape (Planner: "Mehrere benennbare/umbenennbare
        Standard-Template-Sets") via migrate_standard_templates, same as
        the profile's own standard_templates -- so TemplateDialog can
        compare the two using identical set names."""
        from core.persistence import migrate_standard_templates
        stem = self._LANG_DEFAULT_STEMS.get(self.language, "Default")
        path = self.profile_dir / "Backup" / f"{stem}.json"
        if not path.exists():
            return {"tasks": {}, "shopping": {}}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"tasks": {}, "shopping": {}}
        return migrate_standard_templates(data.get("standard_templates"))

    def _restore_default_profiles(self):
        """"Restore Default profile" button in Settings (User-Wunsch, 2026-
        09-10: "einen Button einfügen, der die Profile auf press in den
        Profilordner schiebt ... Popup Frage, ob das Default Profil
        überschrieben werden soll") -- pushes this version's bundled
        Default/Default_de/Default_ru.json from profile_dir/Backup/ into
        the live profile folder, confirming first whenever that would
        overwrite a file already there (same QMessageBox pattern as
        reset_profile/clear_event_entries above)."""
        backup_dir = self._refresh_default_profiles_backup()
        available = [s for s in ("Default", "Default_de", "Default_ru") if (backup_dir / f"{s}.json").exists()]
        if not available:
            return
        existing = [s for s in available if (self.profile_dir / f"{s}.json").exists()]
        if existing:
            box = QMessageBox(self)
            box.setWindowTitle(tr(self.language, "confirm_restore_default_title"))
            names = ", ".join(f"{s}.json" for s in existing)
            box.setText(tr(self.language, "confirm_restore_default_text", names=names))
            yes_btn = box.addButton(tr(self.language, "confirm_overwrite_yes"), QMessageBox.DestructiveRole)
            box.addButton(tr(self.language, "confirm_no"), QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is not yes_btn:
                return
        for stem in available:
            shutil.copy2(backup_dir / f"{stem}.json", self.profile_dir / f"{stem}.json")
        self.show_toast(tr(self.language, "toast_restore_default_done"))
        if self.profile_name in available:
            self.load_profile(self.profile_dir / f"{self.profile_name}.json")

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

        # Close the undo window BEFORE wiping the lists, exactly as
        # load_profile does. Without this the pending card survives the
        # reset in _pending_delete, and clicking Undo afterwards puts it
        # back into a list the user just emptied -- then persists it on the
        # next save (review F-2, reproduced offscreen).
        self._commit_pending_delete()

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

        # Same reason as reset_profile: a pending delete must not be
        # undoable across a destructive clear (review F-2).
        self._commit_pending_delete()

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
        # The pending soft-deleted card is deliberately NOT in task_lists
        # (that exclusion is the whole point of the design), so it has to be
        # retranslated explicitly -- otherwise Undo brings back a card still
        # labelled in the previous language, for the rest of the session,
        # since _apply_priority_style runs nowhere else (review F-10).
        pending = self._pending_delete
        card_groups = list(self.task_lists.values())
        if pending is not None:
            card_groups.append([pending["card"]])
        for cards in card_groups:
            for card in cards:
                if isinstance(card, ShoppingCard):
                    raw = card.priority
                    card._apply_priority_style(prio_display.get(raw, raw))
                else:
                    raw = card.priority_value
                    card._apply_priority_style(prio_display.get(raw, raw))
                    if getattr(card, "is_event", False) and hasattr(card, "event_badge"):
                        card.event_badge.setText(event_text)

        # A toast still on screen keeps its action button, so its label has
        # to follow the switch too (review F-10).
        if getattr(self, "_toast_action_key", None) and not self.toast_action_btn.isHidden():
            self.toast_action_btn.setText(tr(self.language, self._toast_action_key))

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

    def apply_theme(self, theme_name):
        global _APPLIED_PALETTE_THEME
        # Against the APPLIED theme, never against the desired one -- see
        # the note on _APPLIED_PALETTE_THEME.  The first application always
        # runs, whatever the profile asked for.
        unchanged = theme_name == _APPLIED_PALETTE_THEME
        self.current_theme = theme_name

        # A theme is now a different set of token VALUES, not a different
        # QSS block: re-rendering the sheet IS the theme switch (MASTER
        # §4-2).  This replaces the ~100 `QWidget[theme="…"] #selector`
        # rules and the three `setProperty("theme", …)` calls that used to
        # feed them -- nothing selects on that property any more, so a
        # dialog can no longer miss the switch by not descending from
        # whichever widget happened to carry it (the 2026-09-08 bug:
        # Templates buttons stayed cyan on Inferno).
        self.load_styles()
        app = QApplication.instance()
        # setPalette also walks every widget of every window, so it is
        # skipped when the theme did not actually move (apply_theme is
        # called on every profile load, usually with the same theme).
        if app is not None and not unchanged:
            app.setPalette(theme.build_palette(self.current_theme))
            _APPLIED_PALETTE_THEME = theme.tokens(self.current_theme).name

        if hasattr(self, "background"):
            self.background.set_theme(theme_name)
            if hasattr(self, "theme_logo_label"):
                self.update_theme_logo()

        if self.item_database_window is not None and hasattr(self.item_database_window, "set_theme"):
            self.item_database_window.set_theme(theme_name)

        if unchanged:
            # Nothing was re-rendered, so there is nothing to re-resolve.
            # This matters: the walk below touches every widget in the
            # window (thousands), and apply_theme() is called on every
            # profile load, almost always with the theme already active.
            self.update()
            return

        # A re-rendered stylesheet is not re-evaluated against widgets that
        # already computed their style, and property-based rules
        # (#taskCard[completed="true"], #settingsNavButton[active="true"]…)
        # need a repolish regardless.
        for widget in self.findChildren(QWidget):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

        # OverlayWindow has no Qt parent (standalone Qt.Tool window), so it
        # is invisible to self.findChildren() above.  It reads the app-wide
        # sheet now, but its own children still need the repolish, and its
        # painters need a repaint for the new token colors.
        if hasattr(self, "overlay"):
            self.overlay.style().unpolish(self.overlay)
            self.overlay.style().polish(self.overlay)
            for widget in self.overlay.findChildren(QWidget):
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            self.overlay.update()

        if self.flow_map_window is not None:
            self.flow_map_window.update()

        self.update()

    def show_toast(self, text, action_label=None, on_action=None, duration_ms=2200,
                   action_key=None):
        """Bottom-of-content status line. ``action_label``/``on_action`` add a
        single clickable action (Undo) for the lifetime of this toast.

        ``action_key`` is the translation key the label came from; keeping it
        lets ``apply_language`` retranslate a toast that is still on screen
        when the user switches language (review F-10).
        """
        self.toast_label.setText(text)

        if action_label and on_action is not None:
            self._toast_action = on_action
            self._toast_action_key = action_key
            self.toast_action_btn.setText(action_label)
            self.toast_action_btn.show()
        else:
            self._toast_action = None
            self._toast_action_key = None
            self.toast_action_btn.hide()

        self._toast_seq += 1
        seq = self._toast_seq
        # MASTER §3 "Toast": entrée/sortie motion.base. One of the exactly
        # three places in the app that animates.
        motion.fade_in(self.toast_widget, theme=self.current_theme)

        # See _delete_card: `self` as the context so a pending toast timer
        # cannot outlive the window it would touch.
        QTimer.singleShot(duration_ms, self, lambda: self._hide_toast(seq))

    def _on_toast_action(self):
        action = self._toast_action
        self._toast_action = None
        if action is not None:
            action()

    def _hide_toast(self, seq=None):
        """``seq`` makes an expiring toast's timer a no-op once a NEWER toast
        has taken the row over -- otherwise the first toast's timer would cut
        the second one short."""
        if seq is not None and seq != self._toast_seq:
            return
        self._toast_action = None
        self.toast_action_btn.hide()
        motion.fade_out(self.toast_widget, theme=self.current_theme)

    # ── Keyboard (UX audit 2026-09-18, C1) ────────────────────────────────

    def _setup_shortcuts(self):
        """The app had literally zero QShortcut/keyPressEvent before this
        (audit C1). Deliberately a small map of the five things a user does
        every session, plus Delete on a focused card.

        Delete is NOT a QShortcut: a window-context shortcut is resolved
        BEFORE the key ever reaches the focused widget, so binding it here
        would silently break Delete inside every QLineEdit/QTextEdit in the
        window. An application event filter sees the same key press but can
        decline it (return False) and let the editor have it.
        """
        self._shortcuts = {}

        def _bind(key, slot):
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(slot)
            self._shortcuts[key] = sc
            return sc

        _bind("Ctrl+N", self._focus_add_task_input)
        _bind("Ctrl+1", lambda: self._activate_todo_tab("todo"))
        _bind("Ctrl+2", lambda: self._activate_todo_tab("timer"))
        _bind("Ctrl+O", self._toggle_overlay)
        _bind("Ctrl+S", lambda: self.save_profile(explicit=True))

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    # The add-row's entry points, most-typed first. Ctrl+N has to pick the
    # first one that is actually on screen: TasksPage.update_input_mode()
    # shows a DIFFERENT set per tab and template source -- on the
    # Tasks/Shopping tabs the free-text title field is hidden entirely in
    # favour of the template picker, so hardcoding title_input would make
    # Ctrl+N a no-op exactly where it is used most.
    _ADD_ROW_FOCUS_ORDER = ("title_input", "template_combo", "char_input", "amount_input", "add_btn")

    def _focus_add_task_input(self):
        """Ctrl+N -- jump to the ToDo tab's add row. Returns the widget that
        took focus, or None when the row has nothing focusable (e.g. the
        Templates source is empty, which also disables "+ Add")."""
        self._activate_todo_tab("todo")

        for name in self._ADD_ROW_FOCUS_ORDER:
            widget = getattr(self.tasks_page, name, None)
            if widget is None or not widget.isEnabled():
                continue
            # isVisibleTo, not isVisible: "would be shown if the window is"
            # -- the answer must not depend on the window being mapped.
            if not widget.isVisibleTo(self.tasks_page):
                continue
            widget.setFocus(Qt.ShortcutFocusReason)
            if isinstance(widget, QLineEdit):
                widget.selectAll()
            return widget

        return None

    def _activate_todo_tab(self, key: str):
        """Ctrl+1 / Ctrl+2 -- show the ToDo page and select one of its tabs.
        Goes through the sidebar so its highlight never lies about which page
        is on screen."""
        self.sidebar.set_active_page("tasks")
        self.page_stack.setCurrentWidget(self.todo_page)
        self.todo_page.set_active_tab(key)

    @staticmethod
    def _card_for_widget(widget):
        """The TaskCard/ShoppingCard ``widget`` sits in, if any."""
        node = widget
        while node is not None:
            if isinstance(node, (TaskCard, ShoppingCard)):
                return node
            node = node.parentWidget()
        return None

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Delete:
            if self._delete_focused_card():
                return True
        return super().eventFilter(obj, event)

    def _delete_focused_card(self) -> bool:
        """Soft-deletes the focused card. Returns False -- key not consumed --
        whenever focus is in a text/selection editor or outside any card, so
        Delete keeps its normal meaning everywhere else."""
        focused = QApplication.focusWidget()
        if focused is None:
            return False
        # The filter is installed on the QApplication, so it sees key presses
        # meant for OTHER top-level windows too (the overlay, the Flow Map,
        # the Armory windows -- and, in the test suite, a second MainWindow).
        # Only this window's own cards are ours to delete.
        if focused is not self and not self.isAncestorOf(focused):
            return False
        if isinstance(focused, (QLineEdit, QTextEdit, QComboBox, QAbstractSpinBox)):
            return False

        card = self._card_for_widget(focused)
        if card is None:
            return False

        self._delete_card(card)
        return True

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
                             standard_templates=self.standard_templates,
                             default_standard_templates=self._load_default_standard_templates())
        if dlg.exec():
            old_shopping = {t.get("id"): t for t in self.item_templates}
            old_tasks = {t.get("id"): t for t in self.task_templates}
            self.item_templates = dlg.get_templates()
            self.task_templates = dlg.get_task_templates()
            self.standard_templates = dlg.get_standard_templates()
            self.tasks_page.update_templates(self.item_templates)
            self.tasks_page.update_task_templates(self.task_templates)
            self.tasks_page.update_standard_templates(self.standard_templates)
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
                    # Real bug found + fixed (User-reported, 2026-09-05:
                    # correcting a template's price didn't update the
                    # already-created "Abyss Command..." shopping entries)
                    # -- template_id only ever gets set on a card created
                    # THROUGH the "general" checkbox/Standard Templates
                    # flow; a card that started life some other way (e.g.
                    # a manually typed entry that happens to share a
                    # template's title) had template_id="" and this loop
                    # skipped it forever, with no way to ever link up.
                    # Falling back to a same-title match for any card
                    # that's not ALREADY linked to a different template,
                    # and backfilling its template_id once matched, so
                    # every future edit updates it directly from here on.
                    same_title = (
                        not card.template_id
                        and card.title.strip().lower() == title.lower()
                    )
                    if card.template_id == tid or same_title:
                        card.template_id = tid
                        card.update_from_template(tmpl)

    def _sync_tasks_from_templates(self, old_templates: dict):
        """Add / remove general TaskCards based on task_template is_general changes,
        and refresh already-added cards whose source template was edited."""
        task_cards = [
            card for card in self.task_lists.get("tasks", [])
            if isinstance(card, TaskCard)
        ]
        existing_titles = {card.title.lower() for card in task_cards}
        for tmpl in self.task_templates:
            title = tmpl.get("title", "").strip()
            tid = tmpl.get("id")
            was_general = old_templates.get(tid, {}).get("is_general", False) if tid else False
            is_general = tmpl.get("is_general", False)
            if is_general and title.lower() not in existing_titles:
                card = TaskCard(
                    title,
                    tmpl.get("description", ""),
                    tmpl.get("priority", "middle"),
                    schedule=tmpl.get("schedule", "daily"),
                    template_id=tid,
                    location=tmpl.get("location", ""),
                    character=tmpl.get("character", ""),
                    amount=tmpl.get("amount", "1"),
                )
                self._wire_card(card)
                self.task_lists.setdefault("tasks", []).append(card)
                existing_titles.add(title.lower())
            elif was_general and not is_general:
                self.task_lists["tasks"] = [
                    c for c in self.task_lists.get("tasks", [])
                    if not (isinstance(c, TaskCard) and c.title.lower() == title.lower())
                ]

            if tid:
                for card in task_cards:
                    # Same fallback as _sync_shopping_from_templates above.
                    same_title = (
                        not card.template_id
                        and card.title.strip().lower() == title.lower()
                    )
                    if card.template_id == tid or same_title:
                        card.template_id = tid
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
        ever-growing history).

        Carries each card's own `card_id` alongside title/character (User-
        Wunsch, 2026-09-09: "haben die Einträge keine IDs, über die diese
        referenziert werden können?") -- title+character alone couldn't
        tell two same-named cards apart, and wrongly kept flagging a BRAND
        NEW card as missed just because an old, unrelated card once shared
        its title+character. title/character stay too, purely for
        full_view_export.py's own display text (the exported page has no
        live card objects to look a title up from)."""
        missed = []
        for card in self.task_lists.get("tasks", []):
            if isinstance(card, TaskCard) and card.schedule == "daily" and not card.completed:
                missed.append({
                    "card_id": getattr(card, "card_id", ""),
                    "title": card.title,
                    "character": card.character or "",
                })
        for card in self.task_lists.get("shopping", []):
            if isinstance(card, ShoppingCard) and card.schedule == "daily" and not card.completed:
                missed.append({
                    "card_id": getattr(card, "card_id", ""),
                    "title": card.title,
                    "character": card.character or "",
                })
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
        # Same fix as TasksPage.render_tasks() (User-reported, 2026-09-09:
        # stray top-level "python3" windows) -- setParent(None) alone
        # doesn't hide an already-visible widget, so Qt promotes it into
        # its own real window instead of it just disappearing. Unlike
        # render_tasks()'s temporary detach (those cards get reused right
        # after), these ARE permanently dropped from task_lists here, so
        # deleteLater() is correct too, not just hide().
        for c in removed_shop:
            c.hide()
            c.setParent(None)
            c.deleteLater()

        removed_tasks = [
            c for c in self.task_lists.get("tasks", [])
            if isinstance(c, TaskCard) and c.character == char_name
        ]
        self.task_lists["tasks"] = [
            c for c in self.task_lists.get("tasks", [])
            if c not in removed_tasks
        ]
        for c in removed_tasks:
            c.hide()
            c.setParent(None)
            c.deleteLater()

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
                    amount=item.get("amount", "1"),
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
            create_character_callback=self._add_character,
        )
        dialog.exec()

    def _find_task_card(self, title: str, schedule: str, character: str):
        title_l = title.strip().lower()
        for card in self.task_lists.get("tasks", []):
            if not isinstance(card, TaskCard):
                continue
            if card.title.strip().lower() != title_l:
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
                     and c.title.strip().lower() == row["title"].strip().lower()
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

    def _pick_standard_set(self, kind: str, title_key: str, label_key: str) -> str | None:
        """Lets the user pick WHICH named Standard Template Set of `kind`
        to use, when there is more than one to choose from (Planner:
        "Mehrere benennbare/umbenennbare Standard-Template-Sets" -- User-
        Wunsch, 2026-09-23: assignment happens by free selection at
        APPLICATION time, no Main/Twink tag stored on the character).

        Zero-friction for the common case: 0 sets -> None (nothing to
        apply), exactly 1 set -> that one set, no dialog at all (matches
        the old single-starter-pack behaviour exactly). Only 2+ sets ever
        show the picker."""
        sets = self.standard_templates.get(kind, {})
        names = list(sets.keys())
        if not names:
            return None
        if len(names) == 1:
            return names[0]
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getItem(
            self, tr(self.language, title_key), tr(self.language, label_key),
            names, 0, False,
        )
        return name if ok else None

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
        list already; this one only fires once, at character creation).

        Named-Set aware (Planner: "Mehrere benennbare/umbenennbare
        Standard-Template-Sets", freigegeben 2026-09-23): Tasks and
        Shopping pick their OWN set independently -- there is no
        assumption that a shared name between the two means anything, and
        no Main/Twink tag is stored on the character; the set is chosen
        fresh, right here, at application time (0 sets -> skipped, exactly
        1 -> auto-picked, 2+ -> the user is asked which one)."""
        task_set = self._pick_standard_set("tasks", "standards_pick_set_title_tasks", "standards_pick_set_label")
        shop_set = self._pick_standard_set("shopping", "standards_pick_set_title_shopping", "standards_pick_set_label")
        task_templates = self.standard_templates.get("tasks", {}).get(task_set, []) if task_set else []
        shop_templates = self.standard_templates.get("shopping", {}).get(shop_set, []) if shop_set else []
        for tmpl in task_templates:
            card = TaskCard(
                tmpl.get("title", ""),
                tmpl.get("description", ""),
                priority=tmpl.get("priority", "middle"),
                schedule=tmpl.get("schedule", "daily"),
                character=character,
                location=tmpl.get("location", ""),
                amount=tmpl.get("amount", "1"),
                template_id=tmpl.get("source_id") or tmpl.get("id", ""),
            )
            self._wire_card(card)
            self.task_lists.setdefault("tasks", []).append(card)
        for tmpl in shop_templates:
            card = ShoppingCard(
                priority=tmpl.get("priority", "middle"),
                amount=str(tmpl.get("amount", "1")),
                title=tmpl.get("title", ""),
                location=tmpl.get("location", ""),
                price=tmpl.get("price", "0"),
                schedule=tmpl.get("schedule", "daily"),
                currency=tmpl.get("currency", "kinah"),
                character=character,
                template_id=tmpl.get("source_id") or tmpl.get("id", ""),
            )
            self._wire_card(card)
            self.task_lists.setdefault("shopping", []).append(card)
        if task_templates or shop_templates:
            self.refresh()
            if self.auto_save:
                self.save_profile(silent=True)

    def _apply_standard_templates_to_existing(self, character: str, set_name: str = ""):
        """"+Add" on the Standards tab of the Tasks/Shopping toolbar (User-
        Wunsch, 2026-09-09: "Falls Templates bereits zugewiesen sind, sollen
        alle templates aus dem Standard hinzugefügt werden, die nicht
        bereits zugewiesen sind") -- unlike _apply_standard_templates
        (character-CREATION only, unconditional), this targets an EXISTING
        character and is safe to click repeatedly: entries whose title that
        character already has (task OR shopping list, either kind matches
        this call's active tab) are skipped instead of duplicated. Also
        resolves the "nothing happens" report from picking one entry in the
        dropdown -- there is no picker requirement here at all, every
        not-yet-assigned Standard Template just gets added at once.

        Named-Set aware: `set_name` now comes straight from
        TasksPage.standard_apply_requested, i.e. whatever its OWN
        std_set_combo has selected (Planner Nachtrag 2026-09-23: tobia's
        screenshot showed that combo was missing from this main tab view
        entirely -- added right there, next to the Standards tab toggle).
        Falls back to _pick_standard_set's zero-friction rule (0 sets ->
        skipped, exactly 1 -> auto-picked, 2+ -> asks) only if the page
        didn't send one -- e.g. a stale connection during a hot-reload."""
        kind = self.active_tab
        if kind not in ("tasks", "shopping"):
            return
        if not set_name or set_name not in self.standard_templates.get(kind, {}):
            title_key = "standards_pick_set_title_tasks" if kind == "tasks" else "standards_pick_set_title_shopping"
            set_name = self._pick_standard_set(kind, title_key, "standards_pick_set_label")
        if not set_name:
            return
        existing_titles = {
            c.title.strip().lower()
            for c in self.task_lists.get(kind, [])
            if getattr(c, "character", "") == character
        }
        added_any = False
        for tmpl in self.standard_templates.get(kind, {}).get(set_name, []):
            title = tmpl.get("title", "").strip()
            if not title or title.lower() in existing_titles:
                continue
            template_id = tmpl.get("source_id") or tmpl.get("id", "")
            if kind == "tasks":
                card = TaskCard(
                    title,
                    tmpl.get("description", ""),
                    priority=tmpl.get("priority", "middle"),
                    schedule=tmpl.get("schedule", "daily"),
                    character=character,
                    location=tmpl.get("location", ""),
                    amount="1",
                    template_id=template_id,
                )
            else:
                card = ShoppingCard(
                    priority=tmpl.get("priority", "middle"),
                    amount="1",
                    title=title,
                    location=tmpl.get("location", ""),
                    price=tmpl.get("price", "0"),
                    schedule=tmpl.get("schedule", "daily"),
                    currency=tmpl.get("currency", "kinah"),
                    character=character,
                    template_id=template_id,
                )
            self._wire_card(card)
            self.task_lists.setdefault(kind, []).append(card)
            existing_titles.add(title.lower())
            added_any = True
        if added_any:
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

    def _remove_character(self, name: str, action: str = "recursive") -> tuple[bool, str]:
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
        deleted outright rather than asking a second dialog per map.

        Real bug found + fixed (User-reported, 2026-09-05, screenshot: the
        entire "Streamer Test" flow map reduced to one orphaned "New Node"
        after removing 2 characters) -- _add_flow_map/the "+" next to the
        map dropdown creates each NEW flow map with its OWN root node
        already carrying icon="character" (root = "the character this map
        is for"), so a character removed via THIS dialog can perfectly
        legitimately BE some map's root, not just an ordinary child node.
        flow_controller.delete_node() already refuses to ever delete
        root_node_id -- this function had no equivalent guard at all, so
        removing a character who happened to be their own map's root
        collected/popped every descendant of root, i.e. the ENTIRE map,
        with no error and no warning. Now skips (never touches) any
        target id that IS a root_node_id in any map, and reports it back
        via the same (ok, error_key) contract _add_character already
        uses, so the dialog can explain why nothing happened for that
        name instead of silently doing something catastrophic."""
        from ui.flow.flow_controller import FlowController

        removed_any = False
        blocked_as_root = False
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
                    if nid == window.root_node_id:
                        blocked_as_root = True
                        continue
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
                if removed_any:
                    window.render_flow()
                    window.mark_unsaved()
        for map_name, map_data in self.flow_maps.items():
            if map_name == active:
                continue
            nodes = map_data.get("nodes", {})
            root_id = map_data.get("root_node_id")
            target_ids = [
                nid for nid, nd in nodes.items()
                if nd.get("icon") == "character" and nd.get("title") == name
            ]
            for nid in target_ids:
                if nid == root_id:
                    blocked_as_root = True
                    continue
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
        if blocked_as_root and not removed_any:
            return False, "char_remove_is_flowmap_root"
        return removed_any, ""

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
            elif filter_key == "season":
                self.last_season_reset_datetime = self.season_reset_datetime
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

        # ===== SEASON RESET ===== (User-Wunsch, 2026-09-17: "Season
        # Einträge beim Shopping und den Tasks mit dem Season Reset
        # verknüpfen") -- a one-off manually-set target instead of a
        # recurring schedule, so "already reset" is tracked by comparing
        # against the exact season_reset_datetime value rather than a
        # calendar date; setting a new date for the next season is exactly
        # what makes this fire again once THAT date passes. Gated on
        # season_enabled to match Shugo/Riss's own on/off toggles.
        if self.season_enabled and self.season_reset_datetime:
            try:
                season_reset_dt = datetime.strptime(self.season_reset_datetime, "%Y-%m-%d %H:%M")
            except ValueError:
                season_reset_dt = None
            if season_reset_dt and now >= season_reset_dt:
                if self.last_season_reset_datetime != self.season_reset_datetime:
                    self._reset_tasks_by_schedule(["season"])
                    self._reset_shopping_by_schedule(["season"])
                    self.refresh()
                    self.save_profile(silent=True)
                    self.last_season_reset_datetime = self.season_reset_datetime

    def handle_sidebar_page_changed(self, page_key: str):
        logger.debug("Sidebar clicked: %s", page_key)

        if page_key in self.page_indexes:
            self.page_stack.setCurrentIndex(self.page_indexes[page_key])
            # MASTER §1: motion.slow, "changement de page (opacité seule)".
            # No slide -- a stacked page is layout-managed, and animating
            # its geometry fights the layout (see ui/motion.py).
            motion.fade_in(
                self.page_stack.currentWidget(), theme=self.current_theme, kind="slow"
            )

        # No "Tasks opened"/"Plan opened"/"Settings opened" toast here any
        # more (UX audit 2026-09-18, M4): confirming a navigation the sidebar
        # highlight already shows is chatter, and because About fired none the
        # previous page's toast used to sit under the About page. Toasts are
        # reserved for state changes now (saved / reset / imported / undo).
        # The translation keys stay in place -- harmless, and still used by
        # nothing else that would break.
        if page_key == "plan":
            # Deferred a tick (User-reported, 2026-09-13, screenshot: a
            # tiny ~3x4cm window with no content, just minimize/maximize/
            # close buttons, flashes every time) -- same real bug already
            # found + fixed for the EQ-Priority slot popup elsewhere in
            # this app: opening a real top-level window synchronously from
            # within the very sidebar click that triggered it can race
            # with that click's own pending mouse-release/repaint, and
            # Windows shows the new window's bare frame (no content
            # painted yet) for a moment before it either gets its real
            # size/content or gets misread as something to dismiss.
            QTimer.singleShot(0, self, self.open_flow_map_window)

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
                amount=data.get("amount", "1"),
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

        self.season_enabled = data.get(
            "season_enabled",
            self.season_enabled
        )

        self.show_events = data.get(
            "show_events",
            self.show_events
        )

        if "reduce_motion" in data:
            self.set_reduce_motion(data["reduce_motion"], save=False)

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
        self.timers_page.set_season_visible(bool(self.season_enabled and self._get_season_countdown_text()))

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

        old_path = self.dps_meter_path
        self.dps_meter_path = data.get("dps_meter_path", self.dps_meter_path)
        self.dps_meter_autostart = data.get("dps_meter_autostart", self.dps_meter_autostart)
        self._save_app_config()
        if self.dps_meter_autostart and self.dps_meter_path and self.dps_meter_path != old_path:
            self._start_dps_meter(self.dps_meter_path)

        self.save_profile(silent=True)

    def set_reduce_motion(self, enabled: bool, save: bool = True):
        """Store MASTER §1's ``motion.reduced`` preference and apply it now.

        ``ui.motion`` keeps the flag module-level (MASTER calls the setting
        "non négociable", so it has to reach every animation, and threading
        it through each call site would mean it could be forgotten in one).
        ``save=False`` is the profile-load path: the value came FROM the
        file, so writing it straight back would be a pointless write — and
        would happen while the profile is still half-restored.
        """
        self.reduce_motion = bool(enabled)
        motion.set_reduced_motion(self.reduce_motion)
        logger.debug("Reduced motion: %s", self.reduce_motion)
        if save and self.auto_save:
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
            "reduce_motion": self.reduce_motion,

            "daily_reset_time": self.daily_reset_time,
            "weekly_reset_day": self.weekly_reset_day,
            "weekly_reset_time": self.weekly_reset_time,
            "season_reset_datetime": self.season_reset_datetime,
            "season_enabled": self.season_enabled,

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
                return card.title.lower()

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
        return self.format_scaled_price(value, "Kinah")

    def format_scaled_price(self, value, unit: str):
        """Shared k/m scaling for every real currency total (Kinah, SC, AP,
        NP) -- User-Wunsch, 2026-09-05, applied incrementally: Kinah
        already had it, then SC, then "die gleiche Anpassung für NP und
        AP". Prices are entered/stored in THOUSANDS shorthand (see
        ShoppingCard.format_currency_price's own matching docstring for
        why the brief 2026-09-08 "no pre-scale" experiment was reverted)."""
        try:
            scaled = float(str(value).replace(",", ".").strip()) * 1000
        except ValueError:
            scaled = 0

        if scaled >= 1_000_000:
            millions = scaled / 1_000_000
            return f"{millions:g}m {unit}"

        if scaled >= 1_000:
            thousands = scaled / 1_000
            return f"{thousands:g}k {unit}"

        return f"{int(scaled)} {unit}"
    
    def set_task_filter(self, filter_key):
        self.active_filter = filter_key
        self.refresh()
        self._update_task_reset_hint()

    def set_task_char_filter(self, character: str):
        self.todo_char_filter = character
        self.save_profile(silent=True)
        self.refresh()

    def run_update_check(self):
        self._checker = UpdateChecker()
        self._checker.update_available.connect(self._on_update_available)
        self._checker.up_to_date.connect(lambda: None)
        self._checker.start()

    def run_news_check(self):
        self._news_checker = NewsChecker()
        self._news_checker.post_available.connect(self._on_news_post_available)
        self._news_checker.no_news.connect(lambda: None)
        self._news_checker.start()

    def _on_news_post_available(self, post_id: int, title: str, excerpt: str, link: str, date: str = ""):
        # Only ever show a post once -- persisted in config.json (not the
        # per-character profile) so it's remembered across restarts and
        # isn't duplicated per character. A lower/equal id (including a
        # post getting un-published and a different one taking the "latest"
        # spot) is treated as "nothing new", same as the update checker
        # treats "not newer" as up_to_date.
        if post_id <= self._last_seen_news_id:
            return
        self._last_seen_news_id = post_id
        self._save_app_config()
        dlg = NewsDialog(title, excerpt, link, date=date, language=self.language, parent=self)
        dlg.exec()

    def _on_update_available(self, version: str, body: str, asset_url: str, sha256_url: str = ""):
        # sha256_url is "" when the release published no checksum sidecar --
        # the installer needs that distinction (core.update_checker.
        # decide_checksum_policy), so it travels with the rest.
        self._pending_update = (version, body, asset_url, sha256_url)
        if hasattr(self.header, "show_update"):
            self.header.show_update(version)

    def _open_update_dialog(self):
        if not self._pending_update:
            return
        version, body, asset_url, sha256_url = self._pending_update

        if sys.platform != "win32":
            # UpdateDialog installs in place through a Windows .bat +
            # robocopy swap-on-restart (ui/update_dialog.py). There is no
            # equivalent off Windows, and there should not be: an AUR
            # package, an AppImage or a Flatpak is updated by its own
            # channel, and a self-updating app inside /opt or /usr would
            # either fail on permissions or fight the package manager.
            # Show the release page instead and let the user take it from
            # there.
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            from core.version import GITHUB_REPO, GITHUB_USER

            url = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
            logger.info("Update %s available; opening the release page (%s)", version, url)
            QDesktopServices.openUrl(QUrl(url))
            self.show_toast(f"Update {version} → {url}")
            return

        app_root = self.project_root
        dlg = UpdateDialog(version, body, asset_url, app_root, sha256_url, parent=self)
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
        data["settings"]["last_season_reset_datetime"] = None

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