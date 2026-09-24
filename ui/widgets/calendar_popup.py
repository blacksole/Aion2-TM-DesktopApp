"""The popup calendar, pulled into the design system (MASTER §3).

``QDateEdit.setCalendarPopup(True)`` builds a ``QCalendarWidget`` in its own
``Qt::Popup`` top-level window.  That window is **not** a descendant of
MainWindow, so it never carries the ``aion2="true"`` property the app sheet
is scoped to -- it renders in default Fusion, with Qt's default font and
Qt's default cell metrics, inside an app where everything else is Barlow on
navy.  It was the last unthemed surface in the app.

The visible symptom was worse than "wrong colours".  A ``QCalendarWidget``
sizes its day grid from the *header* row, not from the widest day number,
and the columns then stay fixed: measured, every column is 18px wide no
matter how large the cell font gets.  The moment the effective font passes
~12pt -- which DPI scaling alone is enough to do -- ``"30"`` no longer fits
in 18px and Qt elides it to ``"..."``.  Single-digit days keep rendering,
so the grid looks half-empty rather than obviously broken.  Two earlier
fixes in ``styles.template.qss`` (an outer ``min-width``/``min-height``
floor, then ``padding`` on the item) each addressed a symptom: the outer
floor grows the popup without redistributing room into the columns, and
item padding grows row *height*, not column *width*.

So the sizing is done here, in code, where it can be measured against the
real font metrics, and the colours stay in the sheet.
"""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCalendarWidget,
    QDateEdit,
    QGraphicsDropShadowEffect,
)

from core import fonts, theme

#: Widest day label the grid must fit.  Measured rather than assumed,
#: because a condensed face and a mono face disagree by several pixels.
_WIDEST_DAY = "30"

#: Air around the widest label, per side, in `space` steps (MASTER §1).
#: `space.1` (4px) was the first attempt and produced a grid that read as
#: cramped: at `text.base` the cells came out 24px, so two-digit days sat
#: almost edge to edge and the selection rounding clipped their corners.
#: `space.3` (12px) gives a 40px cell -- a comfortable click target that
#: matches the density of the rest of the app rather than Qt's default.
_CELL_PAD_H = "space_3"
#: Vertically the line height already carries most of the rhythm, so the
#: padding is one step smaller; equal padding made the popup unnecessarily
#: tall without making a row easier to hit.
_CELL_PAD_V = "space_2"

#: Set on the popup so its own stylesheet can address it by id.  A type
#: selector cannot: inside a widget stylesheet Qt matches types against the
#: widget's children, not the widget.
_OBJECT_NAME = "Aion2CalendarPopup"


def _parse_shadow(value: str) -> tuple[int, int, QColor]:
    """Pull blur, y-offset and alpha out of the `shadow.popup` token.

    The token is a CSS shadow string -- offset, blur and a translucent
    black -- because that is the form the QSS template needs.  Reading it
    here keeps one definition instead of a second, silently diverging copy
    in code.  Falls back to the Abyss geometry if the token is reshaped.
    """
    numbers = re.findall(r"(\d+(?:\.\d+)?)", value)
    try:
        dy = int(float(numbers[1]))
        blur = int(float(numbers[2]))
        # The rgba() tail of the token: three channels and an alpha.  Taken
        # from the token rather than written out here, so the shadow has one
        # definition (MASTER §4-3) instead of a copy that can drift.
        red, green, blue = (int(float(n)) for n in numbers[3:6])
        colour = QColor(red, green, blue)
        colour.setAlphaF(float(numbers[6]))
    except (IndexError, ValueError):  # pragma: no cover - token reshaped
        fallback = QColor(theme.qcolor(theme.current_tokens(), "bg.window"))
        fallback.setAlphaF(0.35)
        return 18, 6, fallback
    return blur, dy, colour


def style_calendar_popup(date_edit: QDateEdit) -> QCalendarWidget | None:
    """Give ``date_edit``'s popup calendar the app's font and honest metrics.

    Returns the calendar so a caller can keep styling it; ``None`` when the
    popup is disabled (nothing to do).

    Safe to call more than once: every step is idempotent.
    """
    if not date_edit.calendarPopup():
        return None
    calendar = date_edit.calendarWidget()
    if calendar is None:
        return None

    calendar.setObjectName(_OBJECT_NAME)
    tokens = theme.current_tokens()
    families = fonts.load_fonts()

    # --- font: the popup inherits nothing, so set it explicitly ---------
    # Medium, not regular: a bare digit has none of the redundancy a word
    # has -- there is no surrounding shape to read "17" from if the strokes
    # thin out -- and the grid is scanned, not read.  MASTER §1 lists 500 as
    # a body weight, so this stays inside the type scale instead of
    # inventing a calendar-only weight.
    body = QFont(families["body"])
    body.setPixelSize(tokens.text_base)
    body.setWeight(QFont.Weight.Medium)
    calendar.setFont(body)

    # Child views carry their own font resolution; the grid stays Qt's
    # default unless it is set on the view too.
    for widget in calendar.findChildren(QAbstractItemView):
        widget.setFont(body)

    # --- sizing: measure, never guess -----------------------------------
    metrics = calendar.fontMetrics()
    cell_w = metrics.horizontalAdvance(_WIDEST_DAY) + getattr(tokens, _CELL_PAD_H) * 2
    cell_h = metrics.height() + getattr(tokens, _CELL_PAD_V) * 2

    view = calendar.findChild(QAbstractItemView)
    if view is not None:
        # Elision is the visible bug; switch it off so a cell that is still
        # too narrow shows a clipped digit (obvious) instead of "..."
        # (looks like missing data).
        view.setTextElideMode(Qt.TextElideMode.ElideNone)

    # The grid columns are `Stretch`: they divide the calendar's width
    # among themselves.  Measured -- setting `Fixed` +
    # `setDefaultSectionSize()` on the header is silently ignored, the
    # columns still came out 18px.  So the lever is the calendar's own
    # minimum width, and the per-cell size is what that width must supply.
    #
    # 7 day columns + `space.2` of frame on each side; 7 rows (1 weekday
    # header + 6 week rows) + `space.8` for the navigation bar, which does
    # not report a usable height until it has been laid out once.
    grid_w = cell_w * 7 + tokens.space_2 * 2
    grid_h = cell_h * 7 + tokens.space_8 + tokens.space_2 * 2
    calendar.setMinimumSize(grid_w, grid_h)

    # --- week numbers off: they add an 8th column nobody reads ----------
    calendar.setVerticalHeaderFormat(
        QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
    )
    calendar.setHorizontalHeaderFormat(
        QCalendarWidget.HorizontalHeaderFormat.ShortDayNames
    )
    calendar.setGridVisible(False)

    # --- colours: weekdays and weekend in tokens, not Qt's red ----------
    # Qt paints Saturday/Sunday in a hardcoded red that belongs to no theme
    # and reads as `danger` ("something is wrong with this day").  MASTER §2
    # keeps `danger` for errors, so the weekend uses `fg.muted` instead --
    # de-emphasis, which is what a weekend actually is here.
    weekday = QTextCharFormat()
    weekday.setForeground(theme.qcolor(tokens, "fg"))
    weekend = QTextCharFormat()
    weekend.setForeground(theme.qcolor(tokens, "fg.muted"))
    for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
        calendar.setWeekdayTextFormat(day, weekend)
    for day in (
        Qt.DayOfWeek.Monday,
        Qt.DayOfWeek.Tuesday,
        Qt.DayOfWeek.Wednesday,
        Qt.DayOfWeek.Thursday,
        Qt.DayOfWeek.Friday,
    ):
        calendar.setWeekdayTextFormat(day, weekday)

    header = QTextCharFormat()
    header.setForeground(theme.qcolor(tokens, "fg.muted"))
    header.setFontCapitalization(QFont.Capitalization.AllUppercase)
    calendar.setHeaderTextFormat(header)

    # --- lift the popup off the page ------------------------------------
    # MASTER §1 defines exactly one shadow, "reserved for popups/tooltips",
    # and `shadow.popup` existed as a token that nothing ever applied.  This
    # is the case it was written for: measured, `bg.overlay` on the card
    # below it is 1.08-1.13:1 across the six themes -- a surface step that
    # small cannot carry "this floats above the page" on its own, and the
    # popup read as a hole punched in the settings card.
    #
    # Qt cannot put a CSS box-shadow on a Qt::Popup (it has no compositing
    # parent to draw into), so the depth is built from what a popup does
    # have: a full-strength border in `border.strong` instead of `border`,
    # plus a QGraphicsDropShadowEffect carrying the token's own geometry.
    #
    # The navigation bar is styled here too, not in the sheet: Qt builds its
    # month/year labels as QToolButtons that it paints through the *disabled*
    # palette group, so they came out #a19b9d against `fg`'s #e5e7eb --
    # measured, the month name read as greyed-out on an otherwise crisp
    # popup.  A rule on the button's own `color` is what overrides it.
    accent_soft = theme.qcolor(tokens, "accent.soft").name(QColor.NameFormat.HexArgb)
    # A widget's own stylesheet REPLACES the app sheet for that widget
    # rather than merging with it, so everything the calendar itself needs
    # is restated here.  Two ways of writing that do NOT work, both
    # measured rather than assumed:
    #
    #   * `QCalendarWidget {...}` -- Qt matches a widget stylesheet's type
    #     selectors against the widget's *children*, so this never paints
    #     the calendar itself and the border fell back to bg.overlay.
    #   * bare declarations followed by rule blocks -- a stylesheet is
    #     either a declaration list or a rule list, never both; Qt parsed
    #     the leading declarations and dropped every block after them, so
    #     the border appeared and the navigation bar went grey again.
    #
    # An objectName selector is unambiguous in both directions.
    calendar.setStyleSheet(
        f"#{_OBJECT_NAME} {{"
        f"  background-color: {theme.qcolor(tokens, 'bg.overlay').name()};"
        f"}}"
        f"QCalendarWidget QToolButton {{"
        f"  color: {theme.qcolor(tokens, 'fg').name()};"
        f"  font-weight: {tokens.font_weight_semibold};"
        f"  background-color: transparent;"
        f"  border: none;"
        f"  border-radius: {tokens.radius_sm}px;"
        f"  padding: {tokens.space_1}px {tokens.space_2}px;"
        f"}}"
        f"QCalendarWidget QToolButton:hover {{"
        f"  background-color: {accent_soft};"
        f"}}"
        f"QCalendarWidget QSpinBox {{"
        f"  color: {theme.qcolor(tokens, 'fg').name()};"
        f"  background-color: {theme.qcolor(tokens, 'bg.input').name()};"
        f"  border: {tokens.border_width}px solid "
        f"{theme.qcolor(tokens, 'border').name()};"
        f"  border-radius: {tokens.radius_sm}px;"
        f"}}"
    )

    # The calendar is not the popup: QDateEdit puts it inside a container
    # window named `qt_datetimedit_calendar` (confirmed live -- the calendar
    # itself reports isWindow() == False).  The edge and the shadow belong
    # on that container, otherwise they are drawn inside a window whose own
    # background still meets the page flush.
    container = calendar.parentWidget()
    if container is not None and container.isWindow():
        # A plain QWidget ignores a stylesheet background/border unless it
        # is told to paint one; QFrame and friends set this themselves.
        # Without it the container's rule parsed fine and drew nothing --
        # measured, the edge pixel stayed bg.overlay through three earlier
        # attempts at moving the border around.
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        container.setStyleSheet(
            f"#{container.objectName()} {{"
            f"  background-color: {theme.qcolor(tokens, 'bg.overlay').name()};"
            f"  border: {tokens.border_width}px solid "
            f"{theme.qcolor(tokens, 'border.strong').name()};"
            f"  border-radius: {tokens.radius_md}px;"
            f"}}"
        )
        # The container's layout runs at zero margins, so the calendar sat
        # on all four edges and painted straight over the border (measured:
        # the edge pixel read bg.overlay, not border.strong).  One
        # border-width of margin is the room the frame needs to be seen.
        layout = container.layout()
        if layout is not None:
            inset = tokens.border_width
            layout.setContentsMargins(inset, inset, inset, inset)
        shadow_target = container
    else:  # pragma: no cover - Qt changed the popup's shape
        shadow_target = calendar

    shadow = QGraphicsDropShadowEffect(shadow_target)
    # Parsed from `shadow.popup` rather than retyped, so a change to the
    # token moves the real shadow with it.
    blur, dy, shadow_colour = _parse_shadow(tokens.shadow_popup)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, dy)
    shadow.setColor(shadow_colour)
    shadow_target.setGraphicsEffect(shadow)

    # --- days of the neighbouring months --------------------------------
    # Nothing to do here, and that is worth stating: Qt paints out-of-month
    # cells from QPalette's *Disabled* group, which core.theme.build_palette
    # already fills with `fg.muted` for every theme.  Writing a
    # setDateTextFormat() for those dates looks like it works but is dead
    # code -- measured, the palette wins and the format is never seen.  The
    # blue those cells used to show (#4472b8 in an Inferno screenshot) was
    # not Qt being stubborn, it was the app sheet's `color` on the day grid
    # flattening the palette; removing that (MASTER §4-8) is what fixed it.

    return calendar


def calendar_needs_restyle() -> bool:
    """Whether a theme change requires re-running :func:`style_calendar_popup`.

    Colours come from ``QTextCharFormat`` objects captured at call time, so
    unlike the stylesheet they do not follow a live theme switch on their
    own.  Kept as a named predicate so the call site reads as intent.
    """
    return True


__all__ = ["style_calendar_popup", "calendar_needs_restyle"]
