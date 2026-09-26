import os
from pathlib import Path
from PySide6.QtGui import (
    QIcon, QPainter, QPainterPath, QPen, QBrush, QFontDatabase,
)
from PySide6.QtCore import Signal, QTime, QDate, QSize, Qt, QRectF, QEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QStackedWidget, QComboBox, QTimeEdit, QDateEdit, QButtonGroup, QGridLayout,
    QFileDialog, QLineEdit, QScrollArea, QTabWidget, QDialog, QPlainTextEdit, QCompleter,
    QCheckBox,
)

from core import theme
from core.app_logger import get_log_path
from core.platform import open_path, platform_placeholder_exe_path, reveal_in_file_manager
from core.sound import list_system_wavs, play_wav
from ui.widgets import icons
from ui.widgets.calendar_popup import style_calendar_popup

#: Item data marking the "Browse..." row of a notification-sound picker.
SOUND_BROWSE_DATA = "__browse_wav__"


def populate_sound_combo(combo, selected: str = "", tr_func=None, language: str = "en") -> None:
    """Fill a notification-sound picker, shared by Settings and the custom-timer dialog.

    Rows: the "no sound" sentinel, every system .wav, any already-chosen
    custom file, and a "Browse..." entry.

    On Windows this is exactly the previous content and order (the sorted
    contents of C:\\Windows\\Media after the sentinel), with Browse appended
    last. Elsewhere the desktop sound themes ship .oga/.ogg -- which
    QSoundEffect cannot play -- so ``list_system_wavs()`` comes back empty and
    Browse is the only way in: it then LEADS the list instead of trailing it.
    """
    def _t(key: str, fallback: str) -> str:
        try:
            return tr_func(language, key) if tr_func else fallback
        except Exception:
            return fallback

    combo.blockSignals(True)
    try:
        combo.clear()
        combo.addItem(f"-- {_t('no_sound', 'No Sound')} --", "")
        wavs = list_system_wavs()
        browse_label = f"{_t('dps_meter_browse', 'Browse')}..."
        if not wavs:
            combo.addItem(browse_label, SOUND_BROWSE_DATA)
        for wav in wavs:
            combo.addItem(wav.stem, str(wav))
        # A sound picked through Browse (or carried over from another machine)
        # is not in the system list -- keep it visible instead of silently
        # resetting the user's choice to "no sound".
        if selected and combo.findData(selected) < 0:
            combo.addItem(Path(selected).stem, selected)
        if wavs:
            combo.addItem(browse_label, SOUND_BROWSE_DATA)
        combo.setCurrentIndex(max(0, combo.findData(selected)) if selected else 0)
    finally:
        combo.blockSignals(False)


def browse_for_wav(parent, combo, fallback_index: int = 0) -> str:
    """Handle the "Browse..." row: pick a .wav, insert it and select it.
    Cancelling restores ``fallback_index``. Returns the chosen path, or ""."""
    path, _ = QFileDialog.getOpenFileName(parent, "WAV", "", "WAV (*.wav)")
    combo.blockSignals(True)
    try:
        if not path:
            combo.setCurrentIndex(max(0, fallback_index))
            return ""
        index = combo.findData(path)
        if index < 0:
            combo.insertItem(1, Path(path).stem, path)
            index = 1
        combo.setCurrentIndex(index)
        return path
    finally:
        combo.blockSignals(False)


_PAYPAL_URL = "https://www.paypal.com/donate/?hosted_button_id=US4YUPTVHG87C"

def _apply_active_button_style(btn, active: bool, kind: str = "toggle"):
    """Flip #dayButton/#toggleButton's ``active`` state and repolish it.

    History worth keeping, because it is why this helper exists at all: a
    2026-09-16 report ("die Buttons an das jeweilige Layout anpassen", then
    "Buttons auf dem Inferno haben immernoch den gleichen Stil wie das
    abyss Stil") was worked around by building a per-theme
    ``qlineargradient`` inline stylesheet here, with its own duplicated
    table of six theme accent pairs -- because the equivalent
    ``QWidget[theme="…"] #dayButton[active="true"]`` rule in the old
    stylesheet never painted its background through the cascade.

    Both halves of that are gone: the stylesheet is applied to the
    QApplication (so there is no MainWindow-scoped cascade to lose a
    property in) and a theme is now token values, not a
    ``[theme="…"]``-scoped block, so ONE unscoped
    ``#toggleButton[active="true"]`` rule -- accent.soft fill, accent
    border, MASTER §3's pill -- serves all six themes. ``kind`` is kept in
    the signature for the ~20 call sites; the template's own #dayButton
    rule now owns the size difference it used to encode.
    """
    btn.setProperty("active", active)
    btn.style().unpolish(btn)
    btn.style().polish(btn)


class _ScreenAwareComboBox(QComboBox):
    """Works around a real Qt/Windows bug (User-reported, 2026-09-11: the
    Language and Notification Sound dropdown popups render detached/
    oddly positioned, overlapping other UI or extending off-screen; user
    confirmed a multi-monitor setup, though the app itself stays on one
    monitor) -- Qt's own QComboBox popup-positioning code can compute the
    popup's geometry against the WRONG screen's DPI/available-geometry
    the moment more than one QScreen exists, independently of whether the
    app window itself ever moves between monitors (a known Qt/Windows
    multi-screen quirk, still present even with
    Qt::HighDpiScaleFactorRoundingPolicy::PassThrough already set in
    main.py). Re-anchoring the popup here against THIS widget's own
    actual screen (self.screen(), not whichever screen Qt's internal
    logic guessed) after it's shown fixes that class of bug without
    touching anything else about the combo box."""

    def showPopup(self):
        super().showPopup()
        popup = self.view().window()
        screen = self.screen()
        if screen is None:
            return
        available = screen.availableGeometry()
        popup_geo = popup.geometry()
        below = self.mapToGlobal(self.rect().bottomLeft())
        x = min(max(below.x(), available.left()), max(available.left(), available.right() - popup_geo.width()))
        y = below.y()
        if y + popup_geo.height() > available.bottom():
            above = self.mapToGlobal(self.rect().topLeft())
            y = max(available.top(), above.y() - popup_geo.height())
        popup.move(x, y)


class _CurrentPageStackedWidget(QStackedWidget):
    """QStackedWidget that only reserves space for its CURRENT page.

    Plain QStackedWidget's sizeHint()/minimumSizeHint() default to the
    LARGEST of all its pages (so the window doesn't jump when switching
    tabs) -- but this stack sits inside a QScrollArea, not a fixed-size
    window, so that "protect against resizing" behaviour instead means
    the shortest pages always show a scrollbar sized for the tallest one,
    even though nothing on screen needs scrolling (User-reported,
    2026-09-22: mystery scrollbar on the near-empty Appearance/Language
    pages). Overriding sizeHint()/minimumSizeHint() to report only
    currentWidget()'s is necessary but NOT sufficient: measured live
    (docs/audit-2026-09-18 era debugging session), QScrollArea's own
    updateScrollBars() does not reliably re-shrink an already-larger
    widget just because updateGeometry()/resize() ran -- General,
    Appearance and Language (the three pages with a word-wrapped QLabel)
    stayed stuck at General's own height even though sizeHint() was
    provably returning the right, smaller number on every call; Timers
    and Profiles (no word-wrap) happened to shrink fine on the same
    codepath. setFixedHeight() is the forceful fix -- an explicit
    min==max constraint QScrollArea cannot "expandedTo" its way around.

    A word-wrapped label's sizeHint() genuinely keeps growing across
    several early layout passes the first time a page with one is shown
    at all in the whole app session (546x561 -> ... -> 546x673 for
    General here) -- almost certainly first-use custom-font metric
    warmup, not something specific to this stack. Two earlier versions of
    this fix got this wrong in opposite ways, both measured live
    (User-reported, 2026-09-22):

    1. Reporting the CURRENT page's sizeHint()/minimumSizeHint()
       unconditionally, from the very first query, hands QScrollArea a
       small-but-still-growing number before a nested row's OWN
       title/description QVBoxLayout has seen the title's real, settled
       sizeHint -- QScrollArea's un-forced resize squeezes the page down
       early, freezing that nested layout's position for the description
       label at the wrong, premature offset (the two labels render on
       top of each other).
    2. Polling sizeHint() on a plain timer and declaring it "settled"
       once two consecutive ticks agree is not reliable either: General
       plateaus at an intermediate 561 for two whole ticks before a LATER
       pass grows it further to its true 673 -- a false "stable" reading
       that then gets locked in via setFixedHeight() forever (same
       overlap, just from the opposite direction: too confident, not too
       eager).

    The fix that actually holds: react to the page's OWN real Resize
    events instead of guessing when it is done. QStackedLayout calls
    setGeometry() on the current widget every time ITS layout completes a
    pass, which fires a genuine QEvent.Resize on it -- install an event
    filter on the current page and treat every one of ITS resizes as "my
    sizeHint may have changed too", re-syncing setFixedHeight() from
    THAT real completion signal instead of an arbitrary timer tick. This
    can never squeeze a page early (nothing runs before the page's own
    first real layout pass already happened) and can never lock in a
    false plateau (every further genuine layout pass -- however many it
    takes -- re-triggers the filter and corrects it again). Confirmed by
    feeding a plain, unfixed QStackedWidget through the same startup
    sequence: no override at all, no overlap -- because plain
    QStackedWidget's old "largest of all pages" height happens to always
    be tall enough that nothing is ever squeezed while still settling;
    this class now gets the same non-squeezing safety for free, since it
    only ever calls setFixedHeight() in response to a resize the page
    widget has ALREADY finished applying."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._watched_widget: QWidget | None = None
        self.currentChanged.connect(self._on_current_changed)

    def showEvent(self, event):
        """Qt does not reliably emit currentChanged for the page that was
        already current when the very first widget got added (no explicit
        setCurrentIndex() call ever happened for it) -- without this, the
        first-ever page (General) would never get watched at all."""
        super().showEvent(event)
        self._on_current_changed(self.currentIndex())

    def _on_current_changed(self, _index: int):
        if self._watched_widget is not None:
            self._watched_widget.removeEventFilter(self)
            self._watched_widget = None
        widget = self.currentWidget()
        if widget is None:
            return
        self._watched_widget = widget
        widget.installEventFilter(self)
        self._sync_height(widget)

    def eventFilter(self, watched, event):
        if watched is self._watched_widget and event.type() in (
            QEvent.Type.Resize, QEvent.Type.LayoutRequest,
        ):
            self._sync_height(watched)
        return super().eventFilter(watched, event)

    def _sync_height(self, widget):
        self.setFixedHeight(widget.sizeHint().height())
        self.updateGeometry()

    def sizeHint(self):
        widget = self.currentWidget()
        return widget.sizeHint() if widget is not None else super().sizeHint()

    def minimumSizeHint(self):
        widget = self.currentWidget()
        return widget.minimumSizeHint() if widget is not None else super().minimumSizeHint()


class _FlowingSettingsPanel(QFrame):
    """Content panel for the Settings page's "flowing tab" sidebar.

    What QSS cannot express is the SHAPE: three rounded corners plus a
    square top-left one, so the panel reads as continuous with the active
    nav button sitting flush against it. That is why the stroke is
    hand-painted here.

    What it no longer expresses is a gradient: the original stroke faded
    purple (#a855f7) to grey (#64748b), two literals belonging to no token,
    and MASTER's visual thesis rules out decorative gradients. It is now a
    flat ``border.strong`` — MASTER §1 reserves that exact token for "le
    séparateur actif", which is what this edge is. Fill still comes from
    #settingsContentPanel in the template.
    """

    _RADIUS = 10.0

    def paintEvent(self, event):
        super().paintEvent(event)  # lets the QSS background/fill render first

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pen_width = 1.0
        rect = QRectF(self.rect()).adjusted(pen_width / 2, pen_width / 2, -pen_width / 2, -pen_width / 2)
        r = self._RADIUS

        path = QPainterPath()
        path.moveTo(rect.left(), rect.top())
        path.lineTo(rect.right() - r, rect.top())
        path.arcTo(rect.right() - 2 * r, rect.top(), 2 * r, 2 * r, 90, -90)
        path.lineTo(rect.right(), rect.bottom() - r)
        path.arcTo(rect.right() - 2 * r, rect.bottom() - 2 * r, 2 * r, 2 * r, 0, -90)
        path.lineTo(rect.left() + r, rect.bottom())
        path.arcTo(rect.left(), rect.bottom() - 2 * r, 2 * r, 2 * r, -90, -90)
        path.lineTo(rect.left(), rect.top())

        painter.setPen(QPen(QBrush(theme.qcolor(theme.current_tokens(), "border.strong")), pen_width))
        painter.drawPath(path)



class _LogViewerDialog(QDialog):
    """Read-only viewer for app.log (User-Wunsch, 2026-08-27: "einen
    allgemeinen Log ... den man über die Settings abrufen kann") -- lets the
    user see what happened (which window opened when, which assets/colors
    loaded or failed to, etc.) without hunting for the file manually, which
    is exactly what made diagnosing a real packaged-build bug (rarity
    background silently falling back to grey) slow the first time around."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("App Log")
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._path_label = QLabel()
        self._path_label.setObjectName("settingsDescription")
        self._path_label.setWordWrap(True)
        layout.addWidget(self._path_label)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QPlainTextEdit.NoWrap)
        # The platform's own fixed-width font: Consolas exists on Windows only,
        # and naming it on Linux/macOS fell through to the proportional default,
        # which mangles the log's column alignment.
        self._text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self._text.setObjectName("logViewerText")
        layout.addWidget(self._text, 1)

        button_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._reload)
        button_row.addWidget(refresh_btn)
        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.clicked.connect(self._open_folder)
        button_row.addWidget(open_folder_btn)
        button_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

        self._reload()

    def _reload(self):
        path = get_log_path()
        self._path_label.setText(str(path))
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            text = f"(Log konnte nicht gelesen werden: {e})"
        self._text.setPlainText(text)
        # Scroll to the end -- the most recent entries are what you actually
        # want to see first, not the (possibly hours/days) oldest ones.
        scrollbar = self._text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _open_folder(self):
        reveal_in_file_manager(get_log_path())


class SettingsPage(QWidget):
    language_changed = Signal(str)
    theme_changed = Signal(str)
    #: MASTER §1 "motion.reduced": emitted the moment the checkbox flips, so
    #: the next fade is already suppressed.
    reduce_motion_changed = Signal(bool)
    daily_reset_changed = Signal(str)
    weekly_reset_day_changed = Signal(str)
    weekly_reset_time_changed = Signal(str)
    season_reset_changed = Signal(str)
    settings_save_requested = Signal(dict)
    check_update_requested = Signal()
    profile_dir_changed = Signal(str)
    restore_default_profiles_requested = Signal()
    dps_start_requested = Signal(str)  # emits path

    profile_name_changed = Signal(str)
    export_requested = Signal()
    import_requested = Signal()
    duplicate_requested = Signal()

    def __init__(self):
        super().__init__()

        self.project_root = Path(__file__).resolve().parent.parent.parent
        self._cur_lang = "de"
        self._cur_tr = None

        self.profile_name = "Default"
        self.profile_edit_mode = False

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

        # No spacing here (User-Wunsch: "flowing tab") -- the active nav
        # button's right edge needs to sit flush against the content
        # panel's left edge with nothing in between for the fill/border to
        # visually merge; see #settingsPageSidebar/#settingsContentPanel.
        body_layout = QHBoxLayout()
        # A real gutter (review F-19): at spacing 0 the active nav item's
        # accent.soft fill ran straight into the content panel's
        # border.strong edge, so the highlight read as truncated rather than
        # as a tab joined to the panel.  _FlowingSettingsPanel still paints
        # its square top-left corner, which is what carries the "joined"
        # reading -- it does not need the two fills to touch.
        body_layout.setSpacing(12)  # MASTER §1 space.3

        self.settings_sidebar = QFrame()
        self.settings_sidebar.setObjectName("settingsPageSidebar")
        self.settings_sidebar.setFixedWidth(220)

        sidebar_layout = QVBoxLayout(self.settings_sidebar)
        # No right margin -- same "flush against the panel" reason as the
        # spacing above; left/top/bottom keep breathing room.
        sidebar_layout.setContentsMargins(12, 12, 0, 12)
        sidebar_layout.setSpacing(8)

        self.btn_general = QPushButton()
        self.btn_timer = QPushButton()
        self.btn_layout = QPushButton()
        self.btn_language = QPushButton()
        self.btn_profiles = QPushButton()

        self.setting_buttons = [
            self.btn_general,
            self.btn_timer,
            self.btn_layout,
            self.btn_language,
            self.btn_profiles,
        ]

        for button in self.setting_buttons:
            button.setObjectName("settingsNavButton")
            button.setMinimumHeight(44)
            sidebar_layout.addWidget(button)

        sidebar_layout.addStretch()

        self.content_stack = _CurrentPageStackedWidget()
        self.content_stack.setObjectName("settingsContentStack")

        self.general_page = self._create_general_page()

        self.timer_page = self._create_timer_page()

        self.layout_page = self._create_layout_page()

        self.language_page = self._create_language_page()

        self.profiles_page = self._create_profiles_page()

        self.content_stack.addWidget(self.general_page)  # 0
        self.content_stack.addWidget(self.timer_page)     # 1
        self.content_stack.addWidget(self.layout_page)    # 2
        self.content_stack.addWidget(self.language_page)  # 3
        self.content_stack.addWidget(self.profiles_page)  # 4

        scroll_area = QScrollArea()
        scroll_area.setObjectName("scrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setWidget(self.content_stack)
        # QAbstractScrollArea's viewport paints its own QPalette::Base
        # background regardless of the outer widget's "#scrollArea { background:
        # transparent }" rule (that only reaches the QScrollArea itself, not its
        # internal viewport child) -- under Fusion that palette role defaults to
        # a light grey/white, which showed as a solid grey box instead of the
        # real window gradient behind #settingsContentPanel. Scoped to just
        # this instance rather than editing the shared "#scrollArea" QSS rule
        # (also used by tasks_page.py/template_dialog.py).
        scroll_area.viewport().setObjectName("transparentViewport")

        # Bordered panel around the content (User-Wunsch: the active nav
        # button's "flowing tab" fill/border needs a real panel to join
        # into -- the scroll area itself stays transparent/borderless as
        # before, this just wraps it). Own objectName, not the shared
        # "#scrollArea" one (used by Tasks/Template dialog too), so the
        # panel styling stays scoped to Settings. _FlowingSettingsPanel
        # hand-paints the fading border (see its docstring); QSS still
        # owns the transparent fill via the same objectName.
        content_panel = _FlowingSettingsPanel()
        content_panel.setObjectName("settingsContentPanel")
        content_panel_layout = QVBoxLayout(content_panel)
        content_panel_layout.setContentsMargins(4, 4, 4, 4)
        content_panel_layout.addWidget(scroll_area)

        body_layout.addWidget(self.settings_sidebar)
        body_layout.addWidget(content_panel, 1)

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
        self.btn_layout.clicked.connect(
            lambda: self._show_section(2, self.btn_layout)
        )
        self.btn_language.clicked.connect(
            lambda: self._show_section(3, self.btn_language)
        )
        self.btn_profiles.clicked.connect(
            lambda: self._show_section(4, self.btn_profiles)
        )

    def _show_section(self, index, active_button):
        self.content_stack.setCurrentIndex(index)
        self._set_active_button(active_button)

    def show_timer_section(self):
        self._show_section(1, self.btn_timer)
        self._timer_tab_widget.setCurrentIndex(0)

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
        _apply_active_button_style(btn, checked, "toggle")

    def _show_changelog_history(self):
        from ui.update_dialog import ChangelogHistoryDialog
        dialog = ChangelogHistoryDialog(self, language=self._cur_lang)
        dialog.exec()

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
        self.profiles_open_btn.setText(tr_func(language, "open_folder"))
        self.profiles_restore_btn.setText(
            {"en": "Restore Default profile", "de": "Standardprofil wiederherstellen",
             "ru": "Восстановить профиль по умолчанию"}.get(language, "Restore Default profile")
        )

        self.profiles_name_label.setText(
            tr_func(language, "current_profile", name=self.profile_name)
        )
        self.save_profile_btn.setText(tr_func(language, "save_profile"))
        self.load_profile_btn.setText(tr_func(language, "load_profile"))
        self.reset_profile_btn.setText(tr_func(language, "reset_profile"))
        self.reset_profile_btn.setToolTip(tr_func(language, "reset_profile_tooltip"))
        self.clear_events_btn.setText(tr_func(language, "clear_events"))
        self.clear_events_btn.setToolTip(tr_func(language, "clear_events_tooltip"))
        self.duplicate_profile_btn.setText(tr_func(language, "duplicate_profile"))
        self.export_profile_btn.setText(tr_func(language, "export_profile"))
        self.import_profile_btn.setText(tr_func(language, "import_profile"))

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
        self.changelog_history_btn.setText(tr_func(language, "about_changelog_history"))


        self.log_title.setText(tr_func(language, "view_log_title"))
        self.log_desc.setText(tr_func(language, "view_log_desc"))
        self.view_log_btn.setText(tr_func(language, "view_log_btn"))

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

        if hasattr(self, "season_reset_label"):
            self.season_reset_label.setText(tr_func(language, "season_reset_label"))

        # ===== ADVANCED TIMER =====

        self._update_toggle_text(
            self.season_enabled_btn,
            self.season_enabled_btn.isChecked(),
            language,
            tr_func
        )

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

        # ===== NO-SOUND / BROWSE LABELS =====
        # Rebuilt rather than setItemText(0, ...): the picker now also carries
        # a translated "Browse..." row, and the current selection survives.
        if hasattr(self, "notif_sound_combo") and self.notif_sound_combo.count() > 0:
            self._populate_sound_combo()

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

        if hasattr(self, "reduce_motion_check"):
            self.reduce_motion_check.setText(tr_func(language, "reduce_motion"))
            self.reduce_motion_hint.setText(tr_func(language, "reduce_motion_hint"))




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

        self.language_combo = _ScreenAwareComboBox()
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
            ("frostbite", "Elyos"),
            ("obsidian", "Obsidian"),
            ("void", "Asmodae"),
        ]

        self.theme_buttons = {}

        for index, (theme_key, theme_name) in enumerate(themes):

            btn = QPushButton(theme_name)
            btn.setCheckable(True)
            btn.setObjectName("themeButton")

            logo_path = (
                self.project_root /
                f"assets/logos/logo_{theme_key}.png"
            )

            if logo_path.exists():
                btn.setIcon(QIcon(str(logo_path)))
                btn.setIconSize(QSize(48, 48))

            btn.clicked.connect(
                lambda checked=False, t=theme_key:
                self._on_theme_button_clicked(t)
            )

            self.theme_button_group.addButton(btn)
            self.theme_buttons[theme_key] = btn

            row = index // 2
            col = index % 2

            theme_grid.addWidget(btn, row, col)

        if "abyss" in self.theme_buttons:
            self.theme_buttons["abyss"].setChecked(True)

        layout.addLayout(theme_grid)

        # ── Reduce animations (MASTER §1 "motion.reduced", non négociable) ──
        # A QCheckBox rather than the page's usual On/Off #toggleButton: this
        # is an accessibility preference, and a checkbox is what a screen
        # reader and a keyboard user expect for one. Emitted immediately
        # (not on Save) so the effect is visible while the user is looking
        # at the setting -- MainWindow persists it from the signal.
        motion_row = QFrame()
        motion_row.setObjectName("settingsRow")
        motion_layout = QVBoxLayout(motion_row)
        motion_layout.setContentsMargins(14, 12, 14, 12)
        motion_layout.setSpacing(4)

        self.reduce_motion_check = QCheckBox()
        self.reduce_motion_check.setObjectName("eventCheckBox")
        self.reduce_motion_check.toggled.connect(self.reduce_motion_changed.emit)
        motion_layout.addWidget(self.reduce_motion_check)

        self.reduce_motion_hint = QLabel()
        self.reduce_motion_hint.setObjectName("settingsDescription")
        self.reduce_motion_hint.setWordWrap(True)
        motion_layout.addWidget(self.reduce_motion_hint)

        layout.addWidget(motion_row)
        layout.addStretch()

        return page

    def _emit_theme_changed(self):
        theme = self.theme_combo.currentData()

        if theme:
            self.theme_changed.emit(theme)
            self._refresh_active_button_styles()

    def _on_theme_button_clicked(self, theme: str):
        self.theme_changed.emit(theme)
        self._refresh_active_button_styles()

    def _refresh_active_button_styles(self):
        """#dayButton/#toggleButton's "active" look is baked into an inline
        stylesheet per-widget at the moment it's clicked (see
        _apply_active_button_style's docstring for why) -- which means it
        only ever reads the CURRENT theme at THAT moment, and never
        refreshes again on its own. A plain theme switch (no button
        re-clicked) would otherwise leave whichever day/toggle happens to
        already be checked showing the PREVIOUS theme's colors forever,
        exactly as reported (User, 2026-09-16: "Buttons auf dem Inferno
        haben immernoch den gleichen Stil wie das abyss Stil"). Called
        right after emitting theme_changed, since MainWindow's
        apply_theme() (connected to that signal) runs synchronously first
        and updates self.window()'s "theme" property before this runs."""
        for btn in getattr(self, "weekly_day_buttons", []):
            if btn.isChecked():
                _apply_active_button_style(btn, True, "day")
        for btn in (
            getattr(self, "season_enabled_btn", None),
            getattr(self, "shugo_enabled_btn", None),
            getattr(self, "riss_enabled_btn", None),
            getattr(self, "notif_sync_btn", None),
            getattr(self, "notif_enabled_btn", None),
            getattr(self, "notif_shugo_enabled_btn", None),
            getattr(self, "notif_riss_enabled_btn", None),
            getattr(self, "auto_save_btn", None),
            getattr(self, "show_events_btn", None),
            getattr(self, "dps_autostart_btn", None),
            getattr(self, "tray_minimize_btn", None),
        ):
            if btn is not None and btn.isChecked():
                _apply_active_button_style(btn, True, "toggle")

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
            btn.setAttribute(Qt.WA_StyledBackground, True)
            btn.setFixedSize(34, 28)
            if day_key == "Mo":
                btn.setChecked(True)
                _apply_active_button_style(btn, True, "day")
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

        # Season end
        season_row = QFrame()
        season_row.setObjectName("settingsRow")
        season_layout = QHBoxLayout(season_row)
        season_layout.setContentsMargins(14, 12, 14, 12)
        season_layout.setSpacing(12)
        self.season_reset_label = QLabel("Season-Ende")
        self.season_reset_label.setObjectName("settingsLabel")
        self.season_reset_date = QDateEdit()
        self.season_reset_date.setObjectName("settingsTimeInput")
        self.season_reset_date.setDisplayFormat("dd.MM.yyyy")
        self.season_reset_date.setCalendarPopup(True)
        self.season_reset_date.setDate(QDate.currentDate())
        self.season_reset_date.setMinimumWidth(130)
        # The popup is its own top-level window and inherits neither the app
        # sheet nor the app font; it is themed explicitly.  See
        # ui/widgets/calendar_popup.py for why the sizing lives in code.
        style_calendar_popup(self.season_reset_date)
        self.season_reset_time = QTimeEdit()
        self.season_reset_time.setObjectName("settingsTimeInput")
        self.season_reset_time.setDisplayFormat("HH:mm")
        self.season_reset_time.setTime(QTime(9, 0))
        self.season_reset_time.setMinimumWidth(90)
        self.season_reset_date.dateChanged.connect(self._on_season_reset_changed)
        self.season_reset_time.timeChanged.connect(self._on_season_reset_changed)
        season_layout.addWidget(self.season_reset_label)
        season_layout.addStretch()
        season_layout.addWidget(self.season_reset_date)
        season_layout.addWidget(self.season_reset_time)

        # On/Off toggle (User-Wunsch, 2026-09-17: "beim Season Timer noch
        # ein 'On/Off' einrichten, similar zum Advanced Timer") -- same
        # widget setup as shugo_enabled_btn/riss_enabled_btn below, just
        # gating whether the Season countdown card/reset logic is active
        # at all (independent of whether a date is even set).
        self.season_enabled_btn = QPushButton("Off")
        self.season_enabled_btn.setCheckable(True)
        self.season_enabled_btn.setObjectName("toggleButton")
        self.season_enabled_btn.setAttribute(Qt.WA_StyledBackground, True)
        self.season_enabled_btn.setFixedWidth(70)
        season_layout.addWidget(self.season_enabled_btn)
        layout.addWidget(season_row)

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
        self.shugo_enabled_btn.setAttribute(Qt.WA_StyledBackground, True)
        self.shugo_enabled_btn.setFixedWidth(70)
        self.shugo_minute_combo = QComboBox()
        self.shugo_minute_combo.setObjectName("settingsTimerCombo")
        self.shugo_minute_combo.addItems(["00", "15", "30", "45"])
        self.shugo_minute_combo.setFixedWidth(80)
        self.shugo_interval_combo = QComboBox()
        self.shugo_interval_combo.setObjectName("settingsTimerCombo")
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
        self.riss_enabled_btn.setAttribute(Qt.WA_StyledBackground, True)
        self.riss_enabled_btn.setFixedWidth(70)
        self.riss_anchor_combo = QComboBox()
        self.riss_anchor_combo.setObjectName("settingsTimerCombo")
        self.riss_anchor_combo.addItems(["00", "01", "02"])
        self.riss_anchor_combo.setFixedWidth(80)
        self.riss_interval_combo = QComboBox()
        self.riss_interval_combo.setObjectName("settingsTimerCombo")
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

        # ━━━━━━━━━━━━━━━━━━━━━━ TAB 2: Notifications ━━━━━━━━━━━━━━━━━━━━
        self.notifications_page = self._create_notifications_page()
        self._timer_tab_widget.addTab(self.notifications_page, "Notifications")

        # ── Signals ──────────────────────────────────────────────────────
        self.daily_reset_time.timeChanged.connect(self._emit_daily_reset_changed)
        for btn in self.weekly_day_buttons:
            btn.clicked.connect(self._emit_weekly_day_changed)
        self.weekly_reset_time.timeChanged.connect(self._emit_weekly_time_changed)

        self.season_enabled_btn.toggled.connect(
            lambda checked: self._set_toggle(self.season_enabled_btn, checked)
        )
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
        for btn in self.weekly_day_buttons:
            _apply_active_button_style(btn, btn.isChecked(), "day")
        checked_button = self.weekly_day_group.checkedButton()
        if checked_button:
            self.weekly_reset_day_changed.emit(checked_button.property("day_key"))

    def _emit_weekly_time_changed(self):
        value = self.weekly_reset_time.time().toString("HH:mm")
        self.weekly_reset_time_changed.emit(value)

    def _on_season_reset_changed(self):
        value = self._get_season_reset_str()
        self.season_reset_changed.emit(value)

    def _get_season_reset_str(self) -> str:
        d = self.season_reset_date.date().toString("yyyy-MM-dd")
        t = self.season_reset_time.time().toString("HH:mm")
        return f"{d} {t}"

    def _emit_save_requested(self):
        data = {
            "language": self.language_combo.currentData(),
            "theme": self.get_selected_theme(),
            "daily_reset_time": self.daily_reset_time.time().toString("HH:mm"),
            "weekly_reset_day": self.weekly_day_group.checkedButton().property("day_key"),
            "weekly_reset_time": self.weekly_reset_time.time().toString("HH:mm"),
            "season_reset_datetime": self._get_season_reset_str(),
            "season_enabled": self.season_enabled_btn.isChecked(),
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
            "reduce_motion": self.reduce_motion_check.isChecked(),
        }

        self.settings_save_requested.emit(data)



    def _create_notifications_page(self):
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

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

        self.notif_sync_btn = QPushButton()
        self.notif_sync_btn.setCheckable(True)
        self.notif_sync_btn.setChecked(True)
        self.notif_sync_btn.setObjectName("toggleButton")
        self.notif_sync_btn.setAttribute(Qt.WA_StyledBackground, True)
        _apply_active_button_style(self.notif_sync_btn, True, "toggle")
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
        self.notif_enabled_btn.setAttribute(Qt.WA_StyledBackground, True)
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
        self.notif_shugo_enabled_btn.setAttribute(Qt.WA_StyledBackground, True)
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
        self.notif_riss_enabled_btn.setAttribute(Qt.WA_StyledBackground, True)
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

        self.notif_sound_combo = _ScreenAwareComboBox()
        self.notif_sound_combo.setObjectName("settingsCombo")
        self.notif_sound_combo.setFixedWidth(260)
        # Real bug found + fixed (User-reported, 2026-09-11, screenshot: the
        # popup listed every single one of Windows' ~70 built-in .wav
        # sounds at once, scrolling for ages and extending well past the
        # screen -- almost certainly also the actual cause of the earlier-
        # reported "detached/off-screen dropdown" complaint, not just the
        # multi-monitor screen-geometry issue _ScreenAwareComboBox works
        # around). Capped to the same 9-visible-rows convention already
        # used for the Wings picker's similarly long list (User-Wunsch
        # there, 2026-09-06), plus made searchable -- typing filters the
        # list instead of scrolling through it blind.
        self.notif_sound_combo.setMaxVisibleItems(9)
        self.notif_sound_combo.setEditable(True)
        self.notif_sound_combo.setInsertPolicy(QComboBox.NoInsert)
        sound_completer = self.notif_sound_combo.completer()
        if sound_completer is not None:
            sound_completer.setCaseSensitivity(Qt.CaseInsensitive)
            sound_completer.setFilterMode(Qt.MatchContains)
            sound_completer.setCompletionMode(QCompleter.PopupCompletion)
        self._populate_sound_combo("")
        self.notif_sound_combo.currentIndexChanged.connect(self._on_sound_combo_changed)

        self.notif_test_btn = QPushButton("Test")
        self.notif_test_btn.setObjectName("secondaryButton")
        icons.set_icon(self.notif_test_btn, "play", 16, clear_text=False)
        self.notif_test_btn.setFixedWidth(70)
        self.notif_test_btn.clicked.connect(self._preview_sound)

        sound_layout.addLayout(sound_text, 1)
        sound_layout.addWidget(self.notif_sound_combo)
        sound_layout.addWidget(self.notif_test_btn)

        layout.addWidget(notif_row)
        layout.addWidget(sound_row)
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
            self.notif_sync_btn.setText(tr(lang, "notif_sync") if tr else "Synchronized")
        else:
            self.notif_sync_btn.setText(tr(lang, "notif_nosync") if tr else "Separate")
        self._notif_sync_row.setVisible(checked)
        self._notif_nosync_widget.setVisible(not checked)
        # notif_sync_btn doesn't go through _set_toggle (it swaps text to
        # "Synchron"/"Nicht-Synchron" instead of On/Off) -- same inline
        # active-style override still needed for its #toggleButton background.
        _apply_active_button_style(self.notif_sync_btn, checked, "toggle")

    def _populate_sound_combo(self, selected: str | None = None):
        if selected is None:
            selected = self.notif_sound_combo.currentData() or ""
        populate_sound_combo(self.notif_sound_combo, selected, self._cur_tr, self._cur_lang)
        self._last_sound_index = self.notif_sound_combo.currentIndex()

    def _on_sound_combo_changed(self, index: int):
        if self.notif_sound_combo.itemData(index) == SOUND_BROWSE_DATA:
            browse_for_wav(self, self.notif_sound_combo, getattr(self, "_last_sound_index", 0))
        self._last_sound_index = self.notif_sound_combo.currentIndex()

    def _preview_sound(self):
        play_wav(self.notif_sound_combo.currentData() or "")
    
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
        self.auto_save_btn.setAttribute(Qt.WA_StyledBackground, True)
        _apply_active_button_style(self.auto_save_btn, True, "toggle")
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
        self.show_events_btn.setAttribute(Qt.WA_StyledBackground, True)
        _apply_active_button_style(self.show_events_btn, True, "toggle")
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
        self.changelog_history_btn = QPushButton()
        self.changelog_history_btn.setObjectName("secondaryButton")
        self.changelog_history_btn.setFixedWidth(110)
        self.changelog_history_btn.clicked.connect(self._show_changelog_history)

        self.check_update_btn = QPushButton()
        self.check_update_btn.setObjectName("secondaryButton")
        self.check_update_btn.setFixedWidth(110)
        self.check_update_btn.clicked.connect(self.check_update_requested.emit)
        update_layout.addLayout(update_text, 1)
        update_layout.addWidget(self.changelog_history_btn)
        update_layout.addWidget(self.check_update_btn)

        # ===== LOG ROW ===== (User-Wunsch, 2026-08-27: "einen allgemeinen
        # Log ... den man über die Settings abrufen kann, mit Zeitstempel")
        log_row = QFrame()
        log_row.setObjectName("settingsRow")
        log_layout = QHBoxLayout(log_row)
        log_layout.setContentsMargins(14, 12, 14, 12)
        log_layout.setSpacing(12)
        log_text = QVBoxLayout()
        log_text.setSpacing(2)
        self.log_title = QLabel()
        self.log_title.setObjectName("settingsLabel")
        self.log_desc = QLabel()
        self.log_desc.setObjectName("settingsDescription")
        self.log_desc.setWordWrap(True)
        log_text.addWidget(self.log_title)
        log_text.addWidget(self.log_desc)
        self.view_log_btn = QPushButton()
        self.view_log_btn.setObjectName("secondaryButton")
        self.view_log_btn.setFixedWidth(110)
        self.view_log_btn.clicked.connect(self._open_log_viewer)
        log_layout.addLayout(log_text, 1)
        log_layout.addWidget(self.view_log_btn)

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
        self.dps_autostart_btn.setAttribute(Qt.WA_StyledBackground, True)
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
        self.dps_path_input.setPlaceholderText(platform_placeholder_exe_path())
        self.dps_path_input.setReadOnly(True)
        self.dps_browse_btn = QPushButton()
        self.dps_browse_btn.setObjectName("secondaryButton")
        self.dps_browse_btn.setFixedWidth(100)
        self.dps_browse_btn.clicked.connect(self._browse_dps_exe)
        self.dps_start_btn = QPushButton("Start")
        icons.set_icon(self.dps_start_btn, "play", 16, clear_text=False)
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
        self.tray_minimize_btn.setAttribute(Qt.WA_StyledBackground, True)
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
        layout.addWidget(log_row)
        layout.addStretch()

        return page

    def _open_log_viewer(self):
        dialog = _LogViewerDialog(self)
        dialog.exec()

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

        if hasattr(self, "reduce_motion_check"):
            reduce_motion = bool(data.get("reduce_motion", False))
            # blockSignals: set_values() is a pure "show me the stored
            # state" call. Without this it would emit, and MainWindow would
            # save the profile back while it is still being loaded.
            self.reduce_motion_check.blockSignals(True)
            self.reduce_motion_check.setChecked(reduce_motion)
            self.reduce_motion_check.blockSignals(False)

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
                is_active = btn.property("day_key") == weekly_day
                btn.setChecked(is_active)
                _apply_active_button_style(btn, is_active, "day")

        if hasattr(self, "weekly_reset_time"):
            h, m = map(int, data.get("weekly_reset_time", "09:00").split(":"))
            self.weekly_reset_time.setTime(QTime(h, m))

        if hasattr(self, "season_reset_date"):
            raw = data.get("season_reset_datetime", "")
            if raw and " " in raw:
                date_part, time_part = raw.split(" ", 1)
                try:
                    y, mo, d = map(int, date_part.split("-"))
                    self.season_reset_date.blockSignals(True)
                    self.season_reset_date.setDate(QDate(y, mo, d))
                    self.season_reset_date.blockSignals(False)
                except ValueError:
                    pass
                try:
                    th, tm = map(int, time_part.split(":"))
                    self.season_reset_time.blockSignals(True)
                    self.season_reset_time.setTime(QTime(th, tm))
                    self.season_reset_time.blockSignals(False)
                except ValueError:
                    pass

        if hasattr(self, "season_enabled_btn"):
            enabled = data.get("season_enabled", False)
            self.season_enabled_btn.setChecked(enabled)
            self._set_toggle(self.season_enabled_btn, enabled)

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
            self.notif_sync_btn.setText(tr(lang, key) if tr else ("Synchronized" if synced else "Separate"))
            _apply_active_button_style(self.notif_sync_btn, synced, "toggle")
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
            # Repopulate around the saved path: a custom .wav picked through
            # Browse is not in the system list, and findData() alone would
            # silently fall back to "no sound".
            self._populate_sound_combo(data.get("notification_sound", ""))

        if hasattr(self, "profiles_path_label"):
            self.profiles_path_label.setText(data.get("profile_dir", ""))

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

        # ===== CURRENT PROFILE / RENAME ROW =====
        name_row = QFrame()
        name_row.setObjectName("settingsRow")
        name_layout = QHBoxLayout(name_row)
        name_layout.setContentsMargins(14, 12, 14, 12)
        name_layout.setSpacing(10)

        self.profiles_name_label = QLabel('Aktuelles Profil: "Default"')
        self.profiles_name_label.setObjectName("settingsLabel")

        self.profiles_name_input = QLineEdit()
        self.profiles_name_input.setObjectName("profileInput")
        self.profiles_name_input.setText(self.profile_name)
        self.profiles_name_input.setVisible(False)

        self.profiles_name_edit_btn = QPushButton()
        self.profiles_name_edit_btn.setObjectName("smallIconButton")
        self.profiles_name_edit_btn.setFixedSize(34, 34)
        # "✎" / "💾" before the icons wave.  The 💾 in particular was a full
        # colour emoji on most Linux font stacks -- the one glyph in the app
        # that ignored the theme entirely.
        icons.set_icon(self.profiles_name_edit_btn, "pencil", 16)
        self.profiles_name_edit_btn.setToolTip("Profilnamen bearbeiten")
        self.profiles_name_edit_btn.setAccessibleName("Profilnamen bearbeiten")
        self.profiles_name_edit_btn.clicked.connect(self._toggle_profile_edit)

        name_layout.addWidget(self.profiles_name_label)
        name_layout.addWidget(self.profiles_name_input)
        name_layout.addStretch()
        name_layout.addWidget(self.profiles_name_edit_btn)

        layout.addWidget(name_row)

        # ===== PROFILE ACTION BUTTONS =====
        action_row = QFrame()
        action_row.setObjectName("settingsRow")
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(14, 12, 14, 12)
        action_layout.setSpacing(8)

        self.save_profile_btn = QPushButton("Save Profile")
        self.save_profile_btn.setObjectName("secondaryButton")

        self.load_profile_btn = QPushButton("Load Profile")
        icons.set_icon(self.load_profile_btn, "chevron-down", 16, clear_text=False)
        self.load_profile_btn.setObjectName("secondaryButton")

        self.reset_profile_btn = QPushButton("Reset Profile")
        self.reset_profile_btn.setObjectName("secondaryButton")
        self.reset_profile_btn.setToolTip(
            "Removes all current Tasks and Shopping entries from this profile."
        )

        self.clear_events_btn = QPushButton("Clear Events")
        self.clear_events_btn.setObjectName("secondaryButton")
        self.clear_events_btn.setToolTip(
            "Removes all Event entries from Tasks and Shopping lists."
        )

        self.duplicate_profile_btn = QPushButton("Duplicate Profile")
        self.duplicate_profile_btn.setObjectName("secondaryButton")

        action_layout.addWidget(self.save_profile_btn)
        action_layout.addWidget(self.load_profile_btn)
        action_layout.addWidget(self.reset_profile_btn)
        action_layout.addWidget(self.clear_events_btn)
        action_layout.addWidget(self.duplicate_profile_btn)
        action_layout.addStretch()

        layout.addWidget(action_row)

        # ===== EXPORT / IMPORT ROW =====
        transfer_row = QFrame()
        transfer_row.setObjectName("settingsRow")
        transfer_layout = QHBoxLayout(transfer_row)
        transfer_layout.setContentsMargins(14, 12, 14, 12)
        transfer_layout.setSpacing(8)

        self.export_profile_btn = QPushButton("Export Profile")
        self.export_profile_btn.setObjectName("secondaryButton")

        self.import_profile_btn = QPushButton("Import Profile")
        self.import_profile_btn.setObjectName("secondaryButton")

        transfer_layout.addWidget(self.export_profile_btn)
        transfer_layout.addWidget(self.import_profile_btn)
        transfer_layout.addStretch()

        layout.addWidget(transfer_row)

        self.export_profile_btn.clicked.connect(self.export_requested.emit)
        self.import_profile_btn.clicked.connect(self.import_requested.emit)
        self.duplicate_profile_btn.clicked.connect(self.duplicate_requested.emit)

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

        # "Restore Default Profile" (User-Wunsch, 2026-09-10, after
        # discovering the packaged app never actually shipped/refreshed the
        # Default profiles at all: "einen Button einfügen, der die Profile
        # auf press in den Profilordner schiebt ... Popup Frage, ob das
        # Default Profil überschrieben werden soll") -- pushes this
        # version's bundled Default/Default_de/Default_ru.json (mirrored
        # into profile_dir/Backup/ on every launch, see MainWindow.
        # _refresh_default_profiles_backup) into the live profile folder.
        # MainWindow owns the actual copy + overwrite confirmation, same
        # as every other destructive action in this app.
        self.profiles_restore_btn = QPushButton()
        self.profiles_restore_btn.setObjectName("secondaryButton")
        self.profiles_restore_btn.setFixedHeight(36)
        self.profiles_restore_btn.clicked.connect(self.restore_default_profiles_requested.emit)

        btn_row.addWidget(self.profiles_change_btn)
        btn_row.addWidget(self.profiles_open_btn)
        btn_row.addWidget(self.profiles_restore_btn)
        btn_row.addStretch()

        path_layout.addWidget(self.profiles_path_title)
        path_layout.addWidget(self.profiles_path_label)
        path_layout.addLayout(btn_row)

        layout.addWidget(path_row)
        layout.addStretch()

        return page

    def set_profile_name(self, profile_name: str):
        self.profile_name = profile_name

        if self._cur_tr:
            self.profiles_name_label.setText(
                self._cur_tr(self._cur_lang, "current_profile", name=profile_name)
            )
        else:
            self.profiles_name_label.setText(f'Aktuelles Profil: "{profile_name}"')

        self.profiles_name_input.setText(profile_name)

    def get_profile_name(self):
        return self.profiles_name_input.text().strip()

    def _toggle_profile_edit(self):
        if not self.profile_edit_mode:
            self.profile_edit_mode = True
            self.profiles_name_input.setText(self.profile_name)
            self.profiles_name_label.setVisible(False)
            self.profiles_name_input.setVisible(True)
            icons.set_icon(self.profiles_name_edit_btn, "save", 16)
            self.profiles_name_edit_btn.setToolTip("Profilnamen speichern")
            self.profiles_name_edit_btn.setAccessibleName("Profilnamen speichern")
            self.profiles_name_input.setFocus()
            self.profiles_name_input.selectAll()
            return

        new_name = self.profiles_name_input.text().strip()

        if new_name:
            self.profile_name = new_name
            self.profile_name_changed.emit(new_name)

        self.profiles_name_label.setText(f'Aktuelles Profil: "{self.profile_name}"')
        self.profile_edit_mode = False
        self.profiles_name_input.setVisible(False)
        self.profiles_name_label.setVisible(True)
        icons.set_icon(self.profiles_name_edit_btn, "pencil", 16)
        self.profiles_name_edit_btn.setToolTip("Profilnamen bearbeiten")
        self.profiles_name_edit_btn.setAccessibleName("Profilnamen bearbeiten")

    def _pick_profile_dir(self):
        current = self.profiles_path_label.text()
        new_path = QFileDialog.getExistingDirectory(
            self, "Profilordner wählen", current
        )
        if new_path:
            self.profiles_path_label.setText(new_path)
            self.profile_dir_changed.emit(new_path)

    def _open_profile_dir(self):
        # Opens the folder itself -- this never was a "reveal and select".
        path = self.profiles_path_label.text()
        if path and os.path.isdir(path):
            open_path(path)

    def update_profile_dir_label(self, path: str):
        if hasattr(self, "profiles_path_label"):
            self.profiles_path_label.setText(path)