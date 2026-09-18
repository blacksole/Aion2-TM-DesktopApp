"""MASTER §4-5 render gate: grab the real pages, per theme, and look.

Every other theme test pins a *name* — a token, a selector, a property.  None
of them can see what actually reaches the screen, and that is exactly how the
focus ring shipped broken (review F-4/F-7): the rendered QSS contained the
string the test looked for, and the ring still landed inside the control, on
top of the label.

So this module renders.  It builds ONE offscreen MainWindow for the whole
module, switches it through every theme, grabs the pages, and asserts three
things a name-based test cannot:

a. nothing raises while rendering;
b. no meaningful area of the page is Fusion's default grey — the signature of
   a widget the sheet never reached;
c. a focused control really shows the accent on its own edge.

Always offscreen (``tests/conftest.py`` pins ``QT_QPA_PLATFORM``), always via
``QWidget.grab()``, which renders through the raster engine and needs no
display: no window may ever appear on a real screen.
"""

import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import QDeadlineTimer, QEventLoop
from PySide6.QtWidgets import QApplication

from core import theme
from tests.conftest import destroy_window

FIXTURE_PROFILE = Path(__file__).resolve().parent / "fixtures" / "reset_profile.json"

#: Fusion's own default surfaces.  A patch of any of these on one of our
#: pages means a widget fell back to the platform style — i.e. the stylesheet
#: did not reach it.  Every one of the app's six themes is dark, so none of
#: these can be a legitimate colour anywhere on our pages.
FUSION_GREYS = {0xEFEFEF, 0xF0F0F0, 0xD4D0C8, 0xFFFFFF, 0xECECEC}

#: How much of one grey is "a widget", rather than an anti-aliased glyph edge
#: or a 1 px highlight.  A blank combo popup or an unstyled panel is
#: thousands of pixels; text anti-aliasing never is.
MAX_GREY_PIXELS = 200


def _settle(app, ms: int = 500) -> None:
    """Drain the loop so page-switch fades finish before the grab.

    Grabbing mid-fade yields a page at opacity 0 — which looks exactly like
    an unstyled page and would make (b) fire for the wrong reason.
    """
    deadline = QDeadlineTimer(ms)
    while not deadline.hasExpired():
        app.processEvents(QEventLoop.AllEvents, 20)


def _focus(app, widget, ms: int = 200) -> None:
    """Give ``widget`` real keyboard focus, then let the repaint land.

    ``setFocus()`` only arms a window's focus chain: ``hasFocus()`` -- and
    therefore the QSS ``:focus`` state the gate below photographs -- is false
    for every widget of an INACTIVE window, and the offscreen platform has no
    window manager to activate one.  Worse, activation here is delivered as
    an event and can be dropped again by a later top-level, so it is not a
    thing a fixture can set once.  Waiting on ``hasFocus()`` (and
    re-activating while waiting) replaces the fixed sleep that used to sit
    here and made the ring measurable at all.
    """
    window = widget.window()
    widget.setFocus()
    deadline = QDeadlineTimer(2000)
    while not widget.hasFocus() and not deadline.hasExpired():
        if not window.isActiveWindow():
            window.activateWindow()
        app.processEvents(QEventLoop.AllEvents, 20)
    assert widget.hasFocus(), (
        f"{type(widget).__name__}#{widget.objectName()} never took focus "
        f"(window active: {window.isActiveWindow()})"
    )
    _settle(app, ms)


def _edge_pixels(image) -> list[int]:
    edges = []
    for x in range(image.width()):
        edges.append(image.pixel(x, 0) & 0xFFFFFF)
        edges.append(image.pixel(x, image.height() - 1) & 0xFFFFFF)
    for y in range(image.height()):
        edges.append(image.pixel(0, y) & 0xFFFFFF)
        edges.append(image.pixel(image.width() - 1, y) & 0xFFFFFF)
    return edges


def _edge_hits(widget, colour) -> tuple[int, int]:
    """How many of ``widget``'s outermost pixels are exactly ``colour``."""
    edges = _edge_pixels(widget.grab().toImage())
    return sum(1 for pixel in edges if pixel == colour), len(edges)


def _settled_edge_hits(app, widget, colour, fraction=0.5, timeout_ms=1500):
    """``_edge_hits``, but wait for the repaint before believing a low count.

    A stylesheet swap and a focus change are both applied on POSTED events
    (unpolish/repolish, then the focus rect), so a fixed sleep measures
    whichever of the two happened to land inside it.  On a loaded machine
    one theme in six lost that race about once every three runs -- 0 accent
    pixels on a control that does show the ring.  This polls until the ring
    is there or the deadline passes, and returns the last measurement either
    way: the assertion at the call site is still the thing that decides.
    """
    hits, total = _edge_hits(widget, colour)
    deadline = QDeadlineTimer(timeout_ms)
    while hits <= total * fraction and not deadline.hasExpired():
        app.processEvents(QEventLoop.AllEvents, 20)
        hits, total = _edge_hits(widget, colour)
    return hits, total


def _grey_histogram(image) -> dict[int, int]:
    """Count Fusion-grey pixels, at C speed.

    A per-pixel ``image.pixel(x, y)`` loop is ~800 000 Python calls per grab
    and this module takes a dozen grabs per run.  ``array('I')`` over the raw
    RGB32 buffer counts pixel-ALIGNED 32-bit words, so it is both fast and
    free of the false matches a ``bytes.count`` on an unaligned byte pattern
    could produce.
    """
    from array import array

    from PySide6.QtGui import QImage

    rgb32 = image.convertToFormat(QImage.Format_RGB32)
    words = array("I")
    words.frombytes(bytes(rgb32.constBits()))
    counts = {}
    for grey in FUSION_GREYS:
        # Format_RGB32 is 0xffRRGGBB, so the alpha byte is always 0xff.
        found = words.count(0xFF000000 | grey)
        if found:
            counts[grey] = found
    return counts


@pytest.fixture(scope="module")
def win(qapp, tmp_path_factory):
    import ui.main_window as mw

    profile_dir = tmp_path_factory.mktemp("render_gate")
    shutil.copy2(FIXTURE_PROFILE, profile_dir / "QaProfile.json")

    patcher = pytest.MonkeyPatch()
    patcher.setattr(mw.MainWindow, "_resolve_profile_dir", lambda self: profile_dir)
    patcher.setattr(mw.MainWindow, "_save_app_config", lambda self: None)

    window = mw.MainWindow()
    window.countdown_timer.stop()
    window.show()
    _settle(qapp, 200)
    # Activation is NOT set up here: on the offscreen platform there is no
    # window manager, activation arrives as an event, and the app's own
    # ``Qt.Tool`` overlay is a second top-level that can take it away again
    # at any point in the module.  It is therefore acquired per measurement,
    # by ``_focus`` -- which is the reason the ring is visible in a grab at
    # all (``hasFocus()``, and so the QSS ``:focus`` state, is false for
    # every widget of an INACTIVE window: ``setFocus()`` alone armed the
    # focus chain and photographed a resting control).
    #
    # After show(), and only after the loop has run: the offscreen platform
    # has no window manager, so it answers the initial show with a resize to
    # the layout's own size hint (460x501 here) and any resize() made before
    # that is thrown away.  The gate asserts a real page-sized grab, so the
    # size has to be (re)applied on this side of the settle.
    window.resize(1100, 720)
    _settle(qapp, 120)
    assert window.width() > 500 and window.height() > 400, (
        f"the offscreen window is {window.width()}x{window.height()} -- the "
        f"grabs below would not be of a full page"
    )
    yield window
    destroy_window(window)
    patcher.undo()


@pytest.fixture(autouse=True)
def _abyss_after(win):
    yield
    win.apply_theme("abyss")


# ---------------------------------------------------------------------------
# (a) + (b): every page, every theme, renders and is fully styled
# ---------------------------------------------------------------------------


PAGES = (
    # Settings first, tasks last: the ground check and the focus check below
    # both want the tasks page, so ending on it lets all three reuse one
    # activation and one settle instead of three.
    ("settings", lambda w: w.sidebar.set_active_page("settings")),
    ("todo", lambda w: w.sidebar.set_active_page("tasks")),
)


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_every_theme_renders_grounded_styled_and_focus_ringed(qapp, win, name):
    """(a) + (b) + (c) for one theme, in one test.

    This was three parametrized tests -- pages/no-Fusion-grey, window
    ground, focus ring -- i.e. three app-wide theme switches and nine
    event-loop settles per theme, eighteen tests for six themes.  The
    stylesheet lives on the QApplication (MASTER §4-1), so a switch is the
    single most expensive thing this module does; doing it once per theme
    and then taking every measurement off that state is the same set of
    assertions for a third of the switches.  Every assertion below is the
    one it replaced, verbatim -- the only thing that went away is the
    repetition of ``win.apply_theme(name)``.
    """
    win.apply_theme(name)

    grabs = {}
    for page, activate in PAGES:
        activate(win)
        _settle(qapp)
        pixmap = win.grab()          # (a) -- raises if rendering fails
        grabs[page] = pixmap
        assert not pixmap.isNull(), f"{name}/{page}: grab produced nothing"
        assert pixmap.width() > 500 and pixmap.height() > 400

        greys = _grey_histogram(pixmap.toImage())
        offenders = {hex(c): n for c, n in greys.items() if n > MAX_GREY_PIXELS}
        assert not offenders, (
            f"{name}/{page}: Fusion default surfaces on the page "
            f"{offenders} -- a widget the stylesheet did not reach"
        )

    # ------------------------------------------------------------------
    # The window ground is the theme token.  The cheapest proof that the
    # grab is of a themed window at all -- and it would catch a page
    # grabbed mid-fade (all-black) too.  Read off the tasks-page grab
    # taken above, which is the same window state the old standalone test
    # built for itself.
    # ------------------------------------------------------------------
    image = grabs["todo"].toImage()
    expected = theme.qcolor(name, "bg.window").rgb() & 0xFFFFFF
    corner = image.pixel(2, image.height() - 3) & 0xFFFFFF
    assert corner == expected, (
        f"{name}: window ground is {hex(corner)}, expected {hex(expected)}"
    )

    # ------------------------------------------------------------------
    # (c) the focus ring is on the control's own edge.  Review F-4, the
    # part a string match could not see: ``outline`` on a QWidget only
    # recolours Fusion's PE_FrameFocusRect, drawn around the *label*
    # sub-rect INSIDE the control; the ring is a border now.  So: focus a
    # control, grab the control itself, and count accent pixels on its
    # outermost rows and columns.
    # ------------------------------------------------------------------
    button = win.tasks_page.tab_buttons["shopping"]
    accent = theme.qcolor(name, "accent").rgb() & 0xFFFFFF

    button.clearFocus()
    _settle(qapp, 120)
    resting_hits, _ = _edge_hits(button, accent)

    _focus(qapp, button)
    focused_hits, edge_total = _settled_edge_hits(qapp, button, accent)

    assert focused_hits > edge_total * 0.5, (
        f"{name}: only {focused_hits}/{edge_total} edge pixels carry the "
        f"accent -- the ring is not on the control's edge"
    )
    assert focused_hits > resting_hits + 20, (
        f"{name}: focusing changed the edge by {focused_hits - resting_hits} "
        f"pixels -- the ring is not distinguishable from the resting state"
    )
    button.clearFocus()


# ---------------------------------------------------------------------------
# (c) continued: the two focus properties that are not per-theme
# ---------------------------------------------------------------------------


def test_focusing_does_not_move_the_control(qapp, win):
    """The ring is 2 px where the resting border is 1 px, so each focus rule
    gives the pixel back as padding (`space_*_inset`).  If it did not, the
    control would grow and nudge its whole row on focus."""
    win.sidebar.set_active_page("tasks")
    _settle(qapp)
    button = win.tasks_page.tab_buttons["shopping"]
    neighbour = win.tasks_page.tab_buttons["tasks"]

    button.clearFocus()
    _settle(qapp, 120)
    before = (button.size(), neighbour.pos())

    _focus(qapp, button)
    after = (button.size(), neighbour.pos())

    assert before == after, f"focus moved geometry: {before} -> {after}"
    button.clearFocus()


def test_an_accent_filled_button_rings_in_on_accent(qapp, win):
    """Review F-9: an accent ring on an accent fill is invisible, and it was
    the Save button — the first control a keyboard user reaches."""
    win.sidebar.set_active_page("settings")
    _settle(qapp)
    save = win.settings_page.save_btn
    assert save.objectName() == "primaryButton"

    on_accent = theme.qcolor("abyss", "fg.on_accent").rgb() & 0xFFFFFF
    _focus(qapp, save)
    hits, edge_total = _settled_edge_hits(qapp, save, on_accent)
    assert hits > edge_total * 0.5, (
        f"only {hits}/{edge_total} edge pixels are fg.on-accent — the ring is "
        f"invisible on an accent-filled control"
    )
    save.clearFocus()


# ---------------------------------------------------------------------------
# The scope actually covers us (the other half of test_app_sheet_isolation)
# ---------------------------------------------------------------------------


def test_every_widget_of_ours_is_inside_the_app_sheet_scope(win):
    """The sheet is scoped to ``QWidget[aion2="true"]`` and its descendants.

    That is a guarantee about the widget TREE, so it is checked against a
    real tree rather than trusted: one widget whose ancestors all lack the
    flag is one unstyled widget, and the render gate above would only catch
    it if it happened to be large and grey.
    """
    from PySide6.QtWidgets import QWidget

    def in_scope(widget):
        node = widget
        while node is not None:
            if node.property("aion2"):
                return True
            node = node.parentWidget()
        return False

    roots = [win, win.overlay, win.flow_map_window]
    checked = 0
    outside = []
    for root in roots:
        if root is None:
            continue
        for widget in [root] + root.findChildren(QWidget):
            checked += 1
            if not in_scope(widget):
                outside.append(f"{type(widget).__name__}#{widget.objectName()}")

    assert checked > 300, f"only {checked} widgets walked — wrong tree?"
    assert not outside, f"widgets outside the app-sheet scope: {outside[:20]}"


def test_a_dialog_of_ours_inherits_the_scope(win):
    """Dialogs are created on demand, so the guarantee has to hold for a
    widget tree that did not exist when the property was set."""
    from core.translations import tr
    from ui.widgets.template_dialog import TemplateDialog

    dialog = TemplateDialog([], [], parent=win, language="en", tr_func=tr)
    try:
        node = dialog
        while node is not None and not node.property("aion2"):
            node = node.parentWidget()
        assert node is not None, "a dialog parented to MainWindow fell outside the scope"
    finally:
        dialog.deleteLater()


def test_the_armory_windows_are_parentless_so_the_scope_cannot_reach_them():
    """The isolation rests on the Armory's top-levels having no Qt parent.

    ``ui/main_window.py`` asks for ``create_window(parent=None)``; if that
    ever became ``parent=self`` the scope would start matching inside the
    Armory again and the leak would be back, silently.
    """
    source = (Path(__file__).resolve().parent.parent / "ui" / "main_window.py").read_text(
        encoding="utf-8"
    )
    assert "create_window(parent=None" in source, (
        "the Armory window is no longer created parentless — the app-sheet "
        "scope would now reach into it (see tests/test_app_sheet_isolation.py)"
    )


def test_qapplication_carries_the_sheet_and_no_window_has_a_copy(win):
    assert len(QApplication.instance().styleSheet()) > 5000
    assert win.styleSheet() == ""
    assert win.overlay.styleSheet() == ""
