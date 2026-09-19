from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSlider, QMenu, QWidgetAction, QCheckBox,
)
from PySide6.QtCore import Qt, QPoint, QTimer, Signal
from PySide6.QtGui import QPainter, QColor, QActionGroup

from core import theme
from core.translations import tr

# --------------------------------------------------------------------------
# Colors (MASTER §4-3: a painter reads tokens, never a literal)
#
# Every table below used to be a QColor(r, g, b) literal.  Two kinds of
# colour live here and they are resolved differently:
#
#   * SEMANTIC — a priority, a status, a category.  These are theme tokens
#     (danger/warn/ok/accent/secondary/fg.muted) and follow the theme, so
#     they are resolved LAZILY, per build, against the current theme: the
#     overlay is rebuilt by refresh() and apply_theme() repaints it.
#   * DATA — the built-in reset timers and a user-picked custom timer colour.
#     Those are an identity the user recognises ("the purple one is
#     weekly"), not a theme decision, so they stay fixed and come from
#     core.theme.data_color (MASTER §4-4, the tolerated exception).
# --------------------------------------------------------------------------

#: priority -> semantic token.  Same mapping the task list's own
#: #priorityLow/#priorityMiddle/#priorityHigh badges use.
PRIORITY_TOKENS = {
    "high": "danger",
    "middle": "warn",
    "low": "ok",
}

#: Flow-node status -> semantic token.
STATUS_TOKENS = {
    "active": "accent",
    "locked": "fg.muted",
    "completed": "ok",
    "optional": "warn",
}

#: tab -> badge letter.  Both are categorisation badges, so both take
#: MASTER §3's badge colour (secondary); the letter is what distinguishes
#: them, exactly as in the list itself.
TAB_BADGE_LETTERS = {"tasks": "T", "shopping": "S"}

#: schedule -> badge letter (MASTER §3: "schedule → secondary").
#:
#: "Se" for season, not "S": the tab badges above already use "S" for
#: shopping, in the same colour, on rows of the same list -- one glyph for
#: two unrelated meanings (review F-18).  Two letters is the smaller change
#: than recolouring one of the two families, and the badge is sized by its
#: content.
SCHEDULE_BADGE_LETTERS = {"daily": "D", "weekly": "W", "season": "Se"}

#: Built-in reset timers, by ``core.theme.data_color("timer", …)`` key.
TIMER_COLOR_KEYS = {
    "daily": "daily",
    "weekly": "weekly",
    "shugo": "shugo",
    "rift": "rift",
}

#: Fallback for a custom timer with no colour stored.
DEFAULT_CUSTOM_TIMER_COLOR = theme.data_color("timer", "custom")


def token_color(name: str) -> QColor:
    """A semantic token of the theme the app is currently rendering."""
    return theme.qcolor(theme.current_tokens(), name)


def priority_color(priority: str) -> QColor:
    return token_color(PRIORITY_TOKENS.get(priority, PRIORITY_TOKENS["low"]))


def status_color(status: str) -> QColor:
    return token_color(STATUS_TOKENS.get(status, STATUS_TOKENS["locked"]))


def timer_color(key: str) -> QColor:
    return QColor(theme.data_color("timer", TIMER_COLOR_KEYS.get(key, key)))

# (key, display label, default-on) -- drives both the gear-icon popover and
# refresh()'s per-section visibility gate. Order here is the order sections
# appear in both the popover and the accordion.
OVERLAY_SECTIONS = [
    ("timer", "Timer", True),
    ("custom_timer", "Custom Timer", True),
    ("tasks", "Tasks", True),
    ("guide", "Guide", True),
    ("skill_priority", "Skill Priority", False),
    ("gear_priority", "Gear Priority", False),
]

_ROW_H    = 28
_BORDER_W = 3

# --------------------------------------------------------------------------
# Backdrop alpha (MASTER §3, "Overlay HUD": *fond bg.window avec alpha
# réglable par section, texte toujours opaque*)
#
# The slider used to drive setWindowOpacity(), which fades the WHOLE window
# — text included.  At the bottom of its range (20 %) the HUD was a ghost:
# unreadable, which defeats the point of a HUD you keep on top of the game.
# It now drives the alpha of the painted section backdrops only; every
# label keeps opacity 1.0, so the text stays crisp at any setting.
#
# Module-level because the rows are dozens of sibling widgets rebuilt on
# every refresh() and each paints its own backdrop; a single value they all
# read is one repaint away from being consistent, whereas a per-row copy
# would have to be pushed into each one on every slider tick.
# --------------------------------------------------------------------------

#: 0.0 (invisible) … 1.0 (opaque).  Default matches the slider's own 90 %.
_backdrop_alpha: float = 0.9


def set_backdrop_alpha(alpha: float) -> float:
    """Set the HUD backdrop opacity, clamped to the slider's own range."""
    global _backdrop_alpha
    _backdrop_alpha = max(0.0, min(1.0, float(alpha)))
    return _backdrop_alpha


def backdrop_alpha() -> float:
    return _backdrop_alpha


def backdrop_color(token: str = "bg.window") -> QColor:
    """A surface token of the current theme at the HUD's backdrop alpha."""
    color = token_color(token)
    color.setAlphaF(_backdrop_alpha)
    return color


class _ColoredRow(QWidget):
    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedHeight(_ROW_H)

    def paintEvent(self, event):
        p = QPainter(self)
        # Backdrop only — the row's own translucency. Its 3 px identity bar
        # stays fully opaque, like the text: MASTER makes only the *fond*
        # adjustable.  The horizontal colour-to-transparent gradient that
        # used to wash across 62 % of every row is gone (MASTER thesis:
        # "zéro dégradé décoratif"); the bar alone carries the colour.
        p.fillRect(self.rect(), backdrop_color("bg.window"))
        p.fillRect(0, 0, _BORDER_W, self.height(), self._color)
        p.end()


class OverlayTaskRow(_ColoredRow):
    def __init__(self, tab_key: str, card_index: int, title: str, priority: str,
                 badge: str | None = None):
        super().__init__(priority_color(priority))
        self.tab_key = tab_key
        self.card_index = card_index

        layout = QHBoxLayout(self)
        layout.setContentsMargins(_BORDER_W + 6, 0, 8, 0)
        layout.setSpacing(6)

        self.check_btn = QPushButton("○")
        self.check_btn.setObjectName("OverlayCheckBtn")
        self.check_btn.setFixedSize(16, 16)
        self.check_btn.setCursor(Qt.PointingHandCursor)

        title_lbl = QLabel(title if len(title) <= 44 else title[:43] + "…")
        title_lbl.setObjectName("OverlayRowTitle")

        badge_lbl = QLabel(badge or TAB_BADGE_LETTERS.get(tab_key, "?"))
        # Styled by #OverlayBadge in the template (secondary on
        # secondary.soft, MASTER §3) -- was an inline rgba() fill built from
        # a per-tab QColor literal plus a hardcoded near-white text.
        badge_lbl.setObjectName("OverlayBadge")
        badge_lbl.setFixedHeight(14)

        layout.addWidget(self.check_btn)
        layout.addWidget(title_lbl, 1)
        layout.addWidget(badge_lbl)


class OverlayGuideRow(_ColoredRow):
    def __init__(self, node_id: str, title: str, status: str):
        super().__init__(status_color(status))
        self.node_id = node_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(_BORDER_W + 6, 0, 8, 0)
        layout.setSpacing(6)

        can_toggle = status in ("active", "completed")

        self.check_btn = QPushButton("✓" if status == "completed" else "○")
        self.check_btn.setObjectName("OverlayCheckBtn")
        self.check_btn.setFixedSize(16, 16)
        self.check_btn.setEnabled(can_toggle)
        self.check_btn.setCursor(Qt.PointingHandCursor if can_toggle else Qt.ArrowCursor)

        obj = "OverlayRowTitle" if status != "locked" else "OverlayRowTitleDim"
        title_lbl = QLabel(title if len(title) <= 34 else title[:33] + "…")
        title_lbl.setObjectName(obj)

        status_map = {"active": "ACTV", "locked": "LOCK", "completed": "DONE", "optional": "OPT"}
        status_lbl = QLabel(status_map.get(status, status[:4].upper()))
        # #OverlayStatusLabel[status="…"] in the template carries the colour
        # (accent / ok / warn / fg.muted -- the same semantic tokens
        # STATUS_TOKENS maps above), so a theme switch moves it too.
        status_lbl.setObjectName("OverlayStatusLabel")
        status_lbl.setProperty("status", status)
        status_lbl.setFixedWidth(34)
        status_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(self.check_btn)
        layout.addWidget(title_lbl, 1)
        layout.addWidget(status_lbl)


class OverlayInfoRow(_ColoredRow):
    """Read-only labeled row (Timer / Custom Timer / Skill Priority): a
    colored left border, a title, and a right-aligned value label. The
    value label is swapped in place by OverlayWindow._tick_timers() for
    rows that carry a live countdown, instead of rebuilding the row."""

    def __init__(self, color: QColor, title: str, value: str, badge: str | None = None):
        super().__init__(color)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(_BORDER_W + 6, 0, 8, 0)
        layout.setSpacing(6)

        if badge:
            badge_lbl = QLabel(badge)
            badge_lbl.setObjectName("OverlayBadge")
            badge_lbl.setFixedHeight(14)
            layout.addWidget(badge_lbl)

        title_lbl = QLabel(title if len(title) <= 34 else title[:33] + "…")
        title_lbl.setObjectName("OverlayRowTitle")
        layout.addWidget(title_lbl, 1)

        self.value_lbl = QLabel(value)
        self.value_lbl.setObjectName("OverlayRowValue")
        layout.addWidget(self.value_lbl)


class OverlayCheckRow(_ColoredRow):
    """Actionable labeled row (Gear Priority): a check button that fires a
    callback when clicked -- used to advance a slot-chain's progress to its
    next item, rather than toggling a simple done/undone flag."""

    def __init__(self, color: QColor, title: str, on_check):
        super().__init__(color)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(_BORDER_W + 6, 0, 8, 0)
        layout.setSpacing(6)

        self.check_btn = QPushButton("○")
        self.check_btn.setObjectName("OverlayCheckBtn")
        self.check_btn.setFixedSize(16, 16)
        self.check_btn.setCursor(Qt.PointingHandCursor)
        self.check_btn.clicked.connect(on_check)

        title_lbl = QLabel(title if len(title) <= 40 else title[:39] + "…")
        title_lbl.setObjectName("OverlayRowTitle")

        layout.addWidget(self.check_btn)
        layout.addWidget(title_lbl, 1)


class OverlayCountdownRow(_ColoredRow):
    """Countdown Timer row (User-Wunsch, 2026-09-07: "ein Countdown Button
    für das Overlay"): unlike the other Custom Timer modes, which always
    run purely from wall-clock, this one is only running while manually
    started -- so it needs an actual Start/Stop control here instead of a
    plain read-only value like OverlayInfoRow."""

    def __init__(self, color: QColor, title: str, value: str, running: bool, on_toggle):
        super().__init__(color)
        # User-reported, 2026-09-07: the Start/Stop button was barely
        # legible at the plain row height -- this row gets a bit more room
        # than the standard _ROW_H so a real button actually fits.
        self.setFixedHeight(_ROW_H + 6)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(_BORDER_W + 6, 0, 8, 0)
        layout.setSpacing(8)

        # Button - Title - Time (User-Wunsch, 2026-09-07: "den button nach
        # links machen, danach den Titel und rechts weiterhin die Zeit").
        self.toggle_btn = QPushButton()
        self.toggle_btn.setObjectName("OverlayCountdownToggleBtn")
        self.toggle_btn.setFixedSize(62, 26)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setProperty("running", running)
        self.toggle_btn.setText("Stop" if running else "Start")
        self.toggle_btn.clicked.connect(on_toggle)
        # User-Wunsch, 2026-09-07: "die Farbe, die man in den Settings des
        # Counters einstellt, [soll] die Farbe des Buttons darstellen".
        # The fill is genuinely per-timer DATA -- the colour the user picked
        # for this one timer -- so it stays in code, which is the exception
        # MASTER §4-4 allows. Everything else (radius, size, text colour,
        # hover) comes from #OverlayCountdownToggleBtn in the template, and
        # the two-stop lighter/darker gradient is gone with it (MASTER:
        # "zéro dégradé décoratif"); a flat fill also keeps the Start/Stop
        # label at a predictable contrast instead of a per-timer accident.
        self.toggle_btn.setStyleSheet(self._button_style_for(color))
        layout.addWidget(self.toggle_btn)

        title_lbl = QLabel(title if len(title) <= 26 else title[:25] + "…")
        title_lbl.setObjectName("OverlayRowTitle")
        layout.addWidget(title_lbl, 1)

        self.value_lbl = QLabel(value)
        self.value_lbl.setObjectName("OverlayRowValue")
        layout.addWidget(self.value_lbl)

    def set_running(self, running: bool):
        self.toggle_btn.setText("Stop" if running else "Start")
        self.toggle_btn.setProperty("running", running)
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)

    @staticmethod
    def _button_style_for(color: QColor) -> str:
        """The ONLY property this button takes from code: its data fill."""
        return (
            f"QPushButton {{ background-color: {color.name()}; }}"
            f"QPushButton:hover {{ background-color: {color.lighter(115).name()}; }}"
        )


class _ClickableWidget(QWidget):
    """A bare widget that reports a left-click as a signal.

    The accordion header used to be wired with
    ``self._header.mousePressEvent = lambda _event: self._toggle()``
    (review G/L2): a closure capturing the section, stored in the header's
    own ``__dict__``.  That is a reference cycle rooted on a live Qt object
    — header -> its instance dict -> the lambda -> the section -> the
    header — and it mattered here more than anywhere: the overlay is the
    always-on HUD and ``refresh()`` rebuilds every section from scratch on
    every task toggle and every countdown tick, so each rebuild orphaned a
    pinned section subtree.

    A signal costs neither capture: PySide holds a bound-method slot
    weakly, so ``clicked.connect(section._toggle)`` adds no reference in
    either direction (same reasoning as ``MainWindow._wire_card``).
    """

    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class _ResizeHandle(QWidget):
    """The overlay's bottom grip: drag state as signals, not stored methods.

    ``self._resize_handle.mousePressEvent = self._on_handle_press`` and its
    two siblings (review G/L4) stored **bound methods** on the handle, so
    the handle's instance dict pointed at the OverlayWindow.  The overlay is
    parentless *and* holds ``self.main_window``, so that single cycle
    transitively pinned the entire MainWindow — structurally the reason
    ``tests/conftest.py::destroy_window`` needs a ``gc.collect()`` at all.

    The handle reports positions instead; the window keeps the arithmetic.
    """

    pressed = Signal(QPoint)
    moved = Signal(QPoint)
    released = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pressed.emit(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.moved.emit(event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.released.emit()
        super().mouseReleaseEvent(event)


class _AccordionSection(QWidget):
    """A collapsible section: clickable header (chevron/title/count) + body.

    Sections are only ever added to the overlay when they actually have rows
    -- there is no "empty section" state, unlike the rows inside a section
    (Tasks/Guide keep their own "all done" placeholder row).
    """

    def __init__(self, title: str, count: int, open_by_default: bool, parent=None, on_toggle=None):
        super().__init__(parent)
        self._open = open_by_default
        self._on_toggle = on_toggle

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._header = _ClickableWidget()
        self._header.setObjectName("OverlaySectionHead")
        self._header.setCursor(Qt.PointingHandCursor)
        # A plain QWidget doesn't paint its stylesheet background/border by
        # default (unlike QLabel/QPushButton) -- without this, #OverlaySectionHead's
        # background tint and border lines silently don't render at all.
        self._header.setAttribute(Qt.WA_StyledBackground, True)
        header_row = QHBoxLayout(self._header)
        header_row.setContentsMargins(10, 6, 10, 6)
        header_row.setSpacing(8)

        self._chevron = QLabel()
        self._chevron.setObjectName("OverlayChevron")
        self._chevron.setFixedWidth(10)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("OverlaySectionTitle")

        self._count_lbl = QLabel(str(count))
        self._count_lbl.setObjectName("OverlaySectionCount")

        header_row.addWidget(self._chevron)
        header_row.addWidget(title_lbl, 1)
        header_row.addWidget(self._count_lbl)

        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(1)

        outer.addWidget(self._header)
        outer.addWidget(self._body)

        # A bound method, not a lambda stored on the header: PySide holds it
        # weakly, so the connection adds no reference (review G/L2).
        self._header.clicked.connect(self._toggle)
        self._apply_open_state()

    def add_row(self, widget: QWidget):
        self._body_layout.addWidget(widget)

    def _toggle(self):
        self._open = not self._open
        self._apply_open_state()
        if self._on_toggle:
            self._on_toggle(self._open)

    def _apply_open_state(self):
        self._chevron.setText("▾" if self._open else "▸")
        self._body.setVisible(self._open)


class OverlayWindow(QWidget):
    def __init__(self, main_window):
        super().__init__()
        # Parentless Qt.Tool window, so it carries the app-sheet scope
        # itself (see MainWindow.__init__ and the template's §0 comment).
        self.setProperty("aion2", True)
        self.main_window = main_window
        self._drag_pos = None
        self._resize_pos = None
        self._resize_start_h = None
        # Accordion open/closed state survives refresh() (each refresh
        # rebuilds the sections from scratch, e.g. after checking off a
        # Guide step) -- without this it always snapped back to
        # open_by_default (User-reported, 2026-08-30: checking a Guide item
        # closed the section again every time).
        self._section_open = {"Tasks": True, "Guide": False}
        self._tick_callbacks = []

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(360)
        self.setMinimumHeight(80)
        self.setMaximumHeight(700)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # title bar
        self._title_bar = QWidget()
        self._title_bar.setFixedHeight(38)
        self._title_bar.setCursor(Qt.SizeAllCursor)

        title_row = QHBoxLayout(self._title_bar)
        title_row.setContentsMargins(10, 0, 8, 0)
        title_row.setSpacing(4)

        dot = QLabel("●")
        dot.setObjectName("OverlayLiveDot")
        dot.setFixedWidth(12)

        self._profile_lbl = QLabel(main_window.profile_name)
        self._profile_lbl.setObjectName("OverlayProfileName")

        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setObjectName("OverlayOpacitySlider")
        self._opacity_slider.setRange(20, 100)
        self._opacity_slider.setValue(90)
        self._opacity_slider.setFixedWidth(72)
        self._opacity_slider.setFixedHeight(16)
        self._opacity_slider.setCursor(Qt.PointingHandCursor)
        self._opacity_slider.setToolTip("Opacity")
        # Same range, same handle, same meaning to the user -- but it now
        # fades only the section backdrops, never the text (MASTER §3).
        # setWindowOpacity() faded the whole window, which made the HUD
        # unreadable at the low end of its own slider.
        self._opacity_slider.valueChanged.connect(self._on_backdrop_alpha_changed)
        set_backdrop_alpha(self._opacity_slider.value() / 100.0)

        # "Char" switch button (User-Wunsch, way back: "einen kleinen
        # Button 'Char' einfügen, über den man zwischen den einzelnen
        # Chars wechseln kann - denke, wenn man 4 oder mehr chars hat und
        # gleichzeitig alle Tasks anzeigen lässt, ist das schnell
        # überflutet"). Filters the Tasks section down to one character
        # instead of always mixing every character's tasks together;
        # shows that character's own name once a filter is active instead
        # of the generic "Char" label, so the active filter is visible at
        # a glance without opening the popover.
        self._char_btn = QPushButton("Char")
        self._char_btn.setObjectName("OverlayCharBtn")
        self._char_btn.setFixedHeight(24)
        self._char_btn.setCursor(Qt.PointingHandCursor)
        self._char_btn.setToolTip("Filter Tasks by character")
        self._char_btn.clicked.connect(self._show_char_popover)
        self._update_char_btn_label()

        # Gear icon (User-Wunsch, 2026-09-05: bring it back, this time as a
        # section-visibility picker rather than its original Tasks/Guide
        # mode-switch role -- see OverlayWindow._show_section_popover).
        self._gear_btn = QPushButton("⚙")
        self._gear_btn.setObjectName("OverlayIconBtn")
        self._gear_btn.setFixedSize(26, 26)
        self._gear_btn.setCursor(Qt.PointingHandCursor)
        self._gear_btn.setToolTip("Overlay sections")
        self._gear_btn.clicked.connect(self._show_section_popover)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("OverlayIconBtn")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.hide)

        title_row.addWidget(dot)
        title_row.addWidget(self._profile_lbl, 1)
        title_row.addWidget(self._char_btn)
        title_row.addWidget(self._gear_btn)
        title_row.addWidget(self._opacity_slider)
        title_row.addWidget(close_btn)

        outer.addWidget(self._title_bar)

        # scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setObjectName("OverlayScroll")
        # Viewport paints its own background separately from
        # #OverlayScroll's own QSS rule -- shows as a plain white box when
        # Windows itself is set to dark mode (User-reported, 2026-08-29).
        self._scroll.viewport().setObjectName("transparentViewport")

        self._content = QWidget()
        self._content.setObjectName("OverlayContent")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(1)
        self._content_layout.addStretch()

        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll)

        # resize handle
        self._resize_handle = _ResizeHandle()
        self._resize_handle.setFixedHeight(6)
        self._resize_handle.setCursor(Qt.SizeVerCursor)
        self._resize_handle.setObjectName("OverlayResizeHandle")
        # Three bound-method slots instead of three bound methods stored in
        # the handle's __dict__ (review G/L4).
        self._resize_handle.pressed.connect(self._on_handle_press)
        self._resize_handle.moved.connect(self._on_handle_move)
        self._resize_handle.released.connect(self._on_handle_release)
        outer.addWidget(self._resize_handle)

        self.resize(360, 300)
        self.refresh()

        # Drives just the Timer/Custom Timer row value labels in place (see
        # OverlayInfoRow / _tick_timers) -- a full refresh() every second
        # would rebuild/flicker the whole accordion instead.
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick_timers)
        self._tick_timer.start(1000)

    # painting

    def paintEvent(self, event):
        p = QPainter(self)
        # Three backdrops, all at the slider's alpha (MASTER §3): the title
        # bar one step up the surface ladder so it still reads as a bar, the
        # body on bg.window, the resize strip on bg.elevated. Text and the
        # rows' identity bars are painted opaque, independently of this.
        p.fillRect(0, 0, self.width(), 38, backdrop_color("bg.surface"))
        p.fillRect(0, 38, self.width(), self.height() - 44, backdrop_color("bg.window"))
        handle_y = self.height() - 6
        p.fillRect(0, handle_y, self.width(), 6, backdrop_color("bg.elevated"))
        grip_w = 30
        grip_x = (self.width() - grip_w) // 2
        p.fillRect(grip_x, handle_y + 2, grip_w, 2, token_color("border.strong"))
        p.end()

    def _on_backdrop_alpha_changed(self, value: int):
        """Slider -> backdrop alpha, then repaint every painted surface.

        The rows paint their own backdrop, so they each need the update();
        a single repaint of the window would leave them at the old alpha.
        """
        set_backdrop_alpha(value / 100.0)
        self.update()
        for child in self.findChildren(_ColoredRow):
            child.update()

    # public

    def refresh(self):
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._profile_lbl.setText(self.main_window.profile_name)
        self._update_char_btn_label()
        # Rebuilt from scratch each refresh -- rows register their own tick
        # callback (see OverlayInfoRow usage below) so _tick_timers() can
        # update just the value labels every second without a full rebuild.
        self._tick_callbacks = []

        visible = getattr(self.main_window, "overlay_visible_sections", {})
        sections = []
        # Timer/Custom Timer lead (User-Wunsch, 2026-09-05: "ganz oben
        # stehen") -- a countdown you might be watching for is more
        # time-sensitive at a glance than the Tasks/Guide lists below it.
        if visible.get("timer", True):
            sections.append(self._build_timer_section())
        if visible.get("custom_timer", True):
            section = self._build_custom_timer_section()
            if section:
                sections.append(section)
        if visible.get("tasks", True):
            sections.append(self._build_tasks_section())
        if visible.get("guide", True):
            sections.append(self._build_guide_section())
        if visible.get("skill_priority", False):
            section = self._build_skill_priority_section()
            if section:
                sections.append(section)
        if visible.get("gear_priority", False):
            section = self._build_equip_priority_section()
            if section:
                sections.append(section)

        for section in sections:
            self._content_layout.insertWidget(self._content_layout.count() - 1, section)

    def _tick_timers(self):
        for callback in self._tick_callbacks:
            callback()

    # gear icon / section picker

    def _show_section_popover(self):
        mw = self.main_window
        visible = mw.overlay_visible_sections
        menu = QMenu(self)
        menu.setObjectName("OverlayMenu")
        for key, label, _default in OVERLAY_SECTIONS:
            check = QCheckBox(label)
            check.setChecked(bool(visible.get(key, False)))
            check.toggled.connect(lambda checked, k=key: self._on_section_toggled(k, checked))
            action = QWidgetAction(menu)
            action.setDefaultWidget(check)
            menu.addAction(action)
        menu.exec(self._gear_btn.mapToGlobal(self._gear_btn.rect().bottomLeft()))

    def _on_section_toggled(self, key: str, checked: bool):
        self.main_window.overlay_visible_sections[key] = checked
        self.main_window.save_profile(silent=True)
        self.refresh()

    # character filter (Tasks section)

    def _update_char_btn_label(self):
        current = getattr(self.main_window, "overlay_char_filter", "") or ""
        self._char_btn.setText(current if current else "Char")

    def _show_char_popover(self):
        mw = self.main_window
        current = getattr(mw, "overlay_char_filter", "") or ""
        menu = QMenu(self)
        menu.setObjectName("OverlayMenu")
        group = QActionGroup(menu)
        group.setExclusive(True)

        all_action = menu.addAction("All Characters")
        all_action.setCheckable(True)
        all_action.setChecked(current == "")
        all_action.triggered.connect(lambda: self._on_char_filter_selected(""))
        group.addAction(all_action)

        for name in getattr(mw, "characters", []):
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name == current)
            action.triggered.connect(lambda _c=False, n=name: self._on_char_filter_selected(n))
            group.addAction(action)

        menu.exec(self._char_btn.mapToGlobal(self._char_btn.rect().bottomLeft()))

    def _on_char_filter_selected(self, name: str):
        self.main_window.overlay_char_filter = name
        self.main_window.save_profile(silent=True)
        self._update_char_btn_label()
        self.refresh()

    # section builders

    def _build_timer_section(self) -> "_AccordionSection":
        mw = self.main_window
        rows = []

        def add_row(color, title, badge, get_seconds, formatter):
            row = OverlayInfoRow(color, title, formatter(get_seconds()), badge=badge)
            row_tick = lambda r=row: r.value_lbl.setText(formatter(get_seconds()))
            self._tick_callbacks.append(row_tick)
            rows.append(row)

        add_row(
            timer_color("daily"), "Daily Reset", "D",
            lambda: (mw.get_next_daily_reset() - datetime.now()).total_seconds(),
            mw.format_reset_countdown,
        )
        add_row(
            timer_color("weekly"), "Weekly Reset", "W",
            lambda: (mw.get_next_weekly_reset() - datetime.now()).total_seconds(),
            mw.format_reset_countdown,
        )
        if getattr(mw, "shugo_enabled", False):
            add_row(
                timer_color("shugo"), "Shugo Event", "Sh",
                lambda: (mw.get_next_shugo_time() - datetime.now()).total_seconds(),
                mw.format_countdown,
            )
        if getattr(mw, "riss_enabled", False):
            add_row(
                timer_color("rift"), "Rift Timer", "Rf",
                lambda: (mw.get_next_riss_time() - datetime.now()).total_seconds(),
                mw.format_countdown,
            )

        section = _AccordionSection(
            "Timer", len(rows),
            open_by_default=self._section_open.setdefault("Timer", True),
            on_toggle=lambda is_open: self._section_open.__setitem__("Timer", is_open),
        )
        for row in rows:
            section.add_row(row)
        return section

    def _build_custom_timer_section(self):
        mw = self.main_window
        qualifying = [ct for ct in mw.custom_timers[:8] if ct.get("enabled") and ct.get("name")]
        if not qualifying:
            return None

        rows = []
        # Countdown Timers listed first (User-Wunsch, 2026-09-07) -- they're
        # the ones needing interaction (Start/Stop), the rest are read-only.
        # Stable sort keeps everything else in its original relative order.
        ordered = sorted(
            enumerate(mw.custom_timers[:8]),
            key=lambda pair: 0 if pair[1].get("timer_mode") == "countdown" else 1,
        )
        for idx, ct in ordered:
            if not (ct.get("enabled") and ct.get("name")):
                continue
            if ct.get("timer_mode") == "countdown":
                def compute_countdown(ct=ct) -> str:
                    dur = max(1, ct.get("countdown_duration_seconds", 7200))
                    if not ct.get("countdown_active"):
                        return mw._format_custom_countdown(dur, "hh:mm:ss")
                    delay = max(0, min(60, ct.get("countdown_restart_delay_seconds", 0)))
                    phase, remaining = mw._get_countdown_phase(
                        dur, delay, ct.get("countdown_started_at"), datetime.now()
                    )
                    text = mw._format_custom_countdown(remaining, "hh:mm:ss")
                    return f"⟳ {text}" if phase == "delay" else text

                row = OverlayCountdownRow(
                    QColor(ct.get("color") or DEFAULT_CUSTOM_TIMER_COLOR), ct.get("name", "Timer"), compute_countdown(),
                    running=bool(ct.get("countdown_active")),
                    on_toggle=lambda _=False, i=idx: self._on_countdown_toggled(i),
                )
                self._tick_callbacks.append(
                    lambda r=row, c=compute_countdown: r.value_lbl.setText(c())
                )
                rows.append(row)
                continue

            def compute(ct=ct) -> str:
                now = datetime.now()
                mode = ct.get("timer_mode", "hourly")
                if mode == "daily":
                    next_t = mw._get_next_daily_custom_time(ct.get("reset_time", "09:00"))
                    return mw.format_reset_countdown((next_t - now).total_seconds())
                if mode == "weekly":
                    next_t = mw._get_next_weekly_custom_time(
                        ct.get("reset_day", "Mo"), ct.get("reset_time", "09:00")
                    )
                    return mw.format_reset_countdown((next_t - now).total_seconds())
                if mode == "custom":
                    next_t = mw._get_next_custom_timer_time_seconds(
                        max(60, ct.get("interval_seconds", 3600)), ct.get("start_time", "00:00"),
                    )
                    return mw.format_reset_countdown((next_t - now).total_seconds())
                next_t = mw._get_next_custom_timer_time_seconds(
                    max(60, ct.get("interval_minutes", 60) * 60), ct.get("start_time", "00:00"),
                )
                return mw._format_custom_countdown((next_t - now).total_seconds(), "hh:mm:ss")

            row = OverlayInfoRow(QColor(ct.get("color") or DEFAULT_CUSTOM_TIMER_COLOR), ct.get("name", "Timer"), compute())
            self._tick_callbacks.append(lambda r=row, c=compute: r.value_lbl.setText(c()))
            rows.append(row)

        section = _AccordionSection(
            "Custom Timer", len(rows),
            open_by_default=self._section_open.setdefault("Custom Timer", True),
            on_toggle=lambda is_open: self._section_open.__setitem__("Custom Timer", is_open),
        )
        for row in rows:
            section.add_row(row)
        return section

    def _build_skill_priority_section(self):
        rows_data = self.main_window.get_skill_priority_rows()
        if not rows_data:
            return None

        rows = [
            OverlayInfoRow(token_color("secondary"), entry["name"], f"#{i + 1}")
            for i, entry in enumerate(rows_data)
        ]
        section = _AccordionSection(
            "Skill Priority", len(rows),
            open_by_default=self._section_open.setdefault("Skill Priority", True),
            on_toggle=lambda is_open: self._section_open.__setitem__("Skill Priority", is_open),
        )
        for row in rows:
            section.add_row(row)
        return section

    def _build_equip_priority_section(self):
        rows_data = self.main_window.get_equip_priority_rows()
        if not rows_data:
            return None

        rows = []
        for section_key, item in rows_data:
            title = item.get("name", section_key)
            row = OverlayCheckRow(
                token_color("ok"), title,
                on_check=lambda _, sk=section_key: self._on_equip_priority_checked(sk),
            )
            rows.append(row)

        section = _AccordionSection(
            "Gear Priority", len(rows),
            open_by_default=self._section_open.setdefault("Gear Priority", True),
            on_toggle=lambda is_open: self._section_open.__setitem__("Gear Priority", is_open),
        )
        for row in rows:
            section.add_row(row)
        return section

    def _on_equip_priority_checked(self, section_key: str):
        self.main_window.advance_equip_priority(section_key)
        self.refresh()

    def _on_countdown_toggled(self, idx: int):
        # toggle_countdown_timer() already refreshes the overlay itself
        # (also needed for callers other than this button, e.g. a future
        # Start/Stop control on the Timers page), so no self.refresh() here.
        self.main_window.toggle_countdown_timer(idx)

    # populate

    def _build_tasks_section(self) -> _AccordionSection:
        # Real bug found + fixed (2026-09-09): this used to read
        # card.title_label.text() and then prepend "Nx " again itself --
        # once TaskCard/ShoppingCard started showing "Title (Nx)" in that
        # same label (see MainWindow.TaskCard._refresh_title_display), the
        # amount was shown twice ("5x Nightmare (5x)"). card.title is the
        # plain, undecorated value both classes now expose for exactly
        # this kind of reuse.
        char_filter = getattr(self.main_window, "overlay_char_filter", "") or ""
        rows = []
        for tab_key, cards in self.main_window.task_lists.items():
            for i, card in enumerate(cards):
                if card.completed:
                    continue
                character = getattr(card, "character", "")
                if char_filter and character != char_filter:
                    continue
                priority = getattr(card, "priority_value", None) or getattr(card, "priority", "middle")
                title = card.title
                amount = getattr(card, "amount", None)
                if amount and str(amount) not in ("0", "1", ""):
                    title = f"{amount}x {title}"
                if character:
                    title = f"{title} · {character}"
                schedule = getattr(card, "schedule", "daily")
                badge = SCHEDULE_BADGE_LETTERS.get(schedule, SCHEDULE_BADGE_LETTERS["daily"])
                title = f"[Shop] {title}" if tab_key == "shopping" else f"[Task] {title}"
                row = OverlayTaskRow(tab_key, i, title, priority, badge=badge)
                row.check_btn.clicked.connect(
                    lambda _, tk=tab_key, idx=i: self._toggle_task(tk, idx)
                )
                rows.append(row)

        section = _AccordionSection(
            "Tasks", len(rows),
            open_by_default=self._section_open["Tasks"],
            on_toggle=lambda is_open: self._section_open.__setitem__("Tasks", is_open),
        )
        for row in rows:
            section.add_row(row)
        if not rows:
            section.add_row(
                self._empty_row(tr(getattr(self.main_window, "language", "en"), "empty_overlay_tasks"))
            )
        return section

    def _build_guide_section(self) -> _AccordionSection:
        mw = self.main_window
        fw = getattr(mw, "flow_map_window", None)
        rows = []

        if fw:
            from core.flow_model import FlowNode

            # Collect all maps marked for overlay; use live data for the active map
            all_maps = dict(getattr(mw, "flow_maps", {}))
            active_name = getattr(mw, "active_flow_map_name", None)
            if active_name:
                all_maps[active_name] = fw.get_flow_data()

            for map_name, map_data in all_maps.items():
                if not map_data.get("show_in_overlay", False):
                    continue
                nodes = {
                    nid: FlowNode.from_dict(nd)
                    for nid, nd in map_data.get("nodes", {}).items()
                }
                for node in nodes.values():
                    if node.status in ("active", "locked", "completed"):
                        row = OverlayGuideRow(node.id, node.title, node.status)
                        if node.status in ("active", "completed"):
                            row.check_btn.clicked.connect(
                                lambda _, nid=node.id, mn=map_name: self._toggle_node(nid, mn)
                            )
                        rows.append(row)

        section = _AccordionSection(
            "Guide", len(rows),
            open_by_default=self._section_open["Guide"],
            on_toggle=lambda is_open: self._section_open.__setitem__("Guide", is_open),
        )
        for row in rows:
            section.add_row(row)
        if not rows:
            section.add_row(self._empty_row("No flow loaded" if not fw else "All steps completed ✓"))
        return section

    def _toggle_node(self, node_id: str, map_name: str = None):
        mw = self.main_window
        fw = getattr(mw, "flow_map_window", None)
        active_name = getattr(mw, "active_flow_map_name", None)

        if map_name is None or map_name == active_name:
            if fw:
                fw.toggle_node_completed(node_id)
        else:
            from core.flow_model import FlowNode
            map_data = getattr(mw, "flow_maps", {}).get(map_name, {})
            node_data = map_data.get("nodes", {}).get(node_id)
            if node_data:
                node = FlowNode.from_dict(node_data)
                if node.status == "completed":
                    node.status = "active"
                    node.completed = False
                else:
                    node.status = "completed"
                    node.completed = True
                node_data["status"] = node.status
                node_data["completed"] = node.completed

        mw.save_profile(silent=True)
        self.refresh()

    def _empty_row(self, text: str) -> QLabel:
        """The HUD's own empty state: one hint line, no icon, no action.

        Carries BOTH #OverlayEmpty (its own compact 11 px size, since it
        sits inside a 40 px accordion row, not a whole page) and
        #emptyStateHint, so the colour comes from the one place every other
        empty state in the app reads it (MASTER §3, "État vide").
        """
        lbl = QLabel(text)
        lbl.setObjectName("OverlayEmpty")
        lbl.setProperty("class", "emptyStateHint")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFixedHeight(40)
        return lbl

    # actions

    def _toggle_task(self, tab_key: str, index: int):
        cards = self.main_window.task_lists.get(tab_key, [])
        if 0 <= index < len(cards):
            cards[index].toggle()
            self.main_window.refresh()
            self.main_window.save_profile(silent=True)

    # drag & resize

    def _on_handle_press(self, global_pos):
        """``_ResizeHandle.pressed`` — remember where the drag started."""
        self._resize_pos = global_pos
        self._resize_start_h = self.height()

    def _on_handle_move(self, global_pos):
        """``_ResizeHandle.moved`` — resize by the delta since the press."""
        if self._resize_pos is None:
            return
        delta = global_pos.y() - self._resize_pos.y()
        new_h = max(80, self._resize_start_h + delta)
        self.resize(self.width(), new_h)

    def _on_handle_release(self):
        """``_ResizeHandle.released`` — the drag is over."""
        self._resize_pos = None
        self._resize_start_h = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() <= 38:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)
