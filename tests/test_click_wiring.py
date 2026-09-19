"""Whole-row and whole-card clicks, with nothing stored on the widget.

Four places in the UI made a plain widget clickable by assigning a function
onto the instance — ``row.mousePressEvent = lambda …``,
``card.mousePressEvent = on_press``, ``handle.mousePressEvent =
self._on_handle_press`` — which is review G's residual leak list L1–L4 and
the same pattern ``MainWindow._wire_card`` was already cured of:

* the function lives in the widget's own ``__dict__``;
* it captures the widget (as a default argument or a closure cell), and
  usually its owner too;
* so the widget references itself through Python, which is a reference
  cycle rooted on a **live Qt object**.  ``deleteLater()`` frees the C++
  side, but the Python wrapper — and everything it transitively holds —
  stays reachable until a full ``gc.collect()`` happens to run.

Frequency is what made these worth closing: the template rows are rebuilt on
every keystroke in the search box, the overlay's accordion sections on every
countdown tick, and a 40-node Flow Map orphaned 120 closures per rebuild.

Each site now uses the pattern the audit pointed at (``ArmoryCard`` /
``_CardPressFilter``): a class-level handler, a single event filter owned by
the dialog, or a signal — none of which captures anything.  This module
gates both halves of that change:

* **the click still works** — one test per site, driven with real
  ``QMouseEvent``s rather than by calling the handler;
* **the widget is released without a collection** — the census tests below
  disable the cyclic collector around the teardown, so they pass only while
  the reference graph is acyclic.  Verified to have teeth: with the old
  wiring re-introduced in a scratch copy, the Flow Map card census reports
  1/1 alive and the picker-row census 4/4, instead of 0.
"""

import gc
import re
import shutil
import weakref
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QCheckBox

from core.translations import tr
from tests.conftest import destroy_window

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PROFILE = Path(__file__).resolve().parent / "fixtures" / "reset_profile.json"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _send(widget, kind, *, button=Qt.LeftButton, buttons=Qt.LeftButton, at=(5.0, 5.0),
          globally=(100.0, 100.0), modifiers=Qt.NoModifier):
    """Deliver a real mouse event, the way Qt would."""
    event = QMouseEvent(
        kind, QPointF(*at), QPointF(*globally), button, buttons, modifiers
    )
    QApplication.sendEvent(widget, event)


def _click(widget, **kwargs):
    _send(widget, QEvent.MouseButtonPress, **kwargs)


def _flush():
    """Run the DeferredDelete queue without running the collector."""
    app = QApplication.instance()
    app.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def _alive(refs) -> int:
    return sum(1 for ref in refs if ref() is not None)


@pytest.fixture
def no_gc():
    """Disable the cyclic collector for the duration of a census.

    Without this the test proves nothing: CPython's generational collector
    fires on allocation counts, so a cycle the fix was supposed to remove
    would be swept up by whichever allocation happened next and the
    assertion would pass either way.
    """
    gc.collect()
    gc.disable()
    try:
        yield
    finally:
        gc.enable()
        gc.collect()


@pytest.fixture(scope="module")
def win(qapp, tmp_path_factory):
    """One real, offscreen MainWindow — for its overlay and its Flow Map.

    Both are parentless top-levels built by ``MainWindow.__init__``; neither
    can be constructed standalone (the overlay reads a dozen host methods,
    and a Flow Map without a host cannot save), so the honest subject is the
    real one.
    """
    import ui.main_window as mw

    profile_dir = tmp_path_factory.mktemp("click_wiring_profiles")
    shutil.copy2(FIXTURE_PROFILE, profile_dir / "QaProfile.json")

    patcher = pytest.MonkeyPatch()
    patcher.setattr(mw.MainWindow, "_resolve_profile_dir", lambda self: profile_dir)
    patcher.setattr(mw.MainWindow, "_save_app_config", lambda self: None)

    window = mw.MainWindow()
    window.countdown_timer.stop()
    yield window
    destroy_window(window)
    patcher.undo()


@pytest.fixture
def dialog(qapp):
    """A ``TemplateDialog`` with enough rows to tell one from another."""
    from ui.widgets.template_dialog import TemplateDialog

    shopping = [
        {"title": f"Item {i}", "location": "Shop", "is_general": False, "price": 1}
        for i in range(6)
    ]
    tasks = [
        {"title": f"Task {i}", "location": "Camp", "is_general": False,
         "schedule": "daily", "priority": "low"}
        for i in range(6)
    ]
    dlg = TemplateDialog(
        shopping, {}, task_templates=tasks, parent=None, language="en", tr_func=tr
    )
    yield dlg
    dlg.deleteLater()
    _flush()


def _shop_rows(dialog):
    layout = dialog._shop_list_layout
    return [layout.itemAt(i).widget() for i in range(layout.count() - 1)]


def _task_rows(dialog):
    layout = dialog._task_list_layout
    return [layout.itemAt(i).widget() for i in range(layout.count() - 1)]


# ---------------------------------------------------------------------------
# L1 — TemplateDialog rows (rebuilt on every keystroke)
# ---------------------------------------------------------------------------


def test_clicking_a_shopping_row_selects_it(dialog):
    rows = _shop_rows(dialog)
    assert len(rows) == 6, "fixture built no rows to click"
    assert dialog._selected_shop_index is None

    _click(rows[3])
    assert dialog._selected_shop_index == 3, (
        "a left-click on the row body no longer selects it — the filter is "
        "not installed, or the row lost its rowIndex property"
    )


def test_clicking_the_selected_shopping_row_again_deselects_it(dialog):
    """The old lambda called the same toggle, so this must survive."""
    _click(_shop_rows(dialog)[2])
    assert dialog._selected_shop_index == 2
    _click(_shop_rows(dialog)[2])
    assert dialog._selected_shop_index is None


def test_clicking_a_task_row_selects_it(dialog):
    rows = _task_rows(dialog)
    assert len(rows) == 6
    _click(rows[4])
    assert dialog._selected_task_index == 4


def test_a_right_click_selects_nothing(dialog):
    """``button() == Qt.LeftButton`` guards the filter, as the old lambda
    did *not* — a right-press used to select the row too."""
    _click(_shop_rows(dialog)[1], button=Qt.RightButton, buttons=Qt.RightButton)
    assert dialog._selected_shop_index is None


def test_a_template_row_carries_no_handler_of_its_own(dialog):
    for row in _shop_rows(dialog) + _task_rows(dialog):
        assert "mousePressEvent" not in vars(row), (
            "a per-row mousePressEvent is back: it captures the dialog and "
            "lives in the row's own __dict__ (review G/L1)"
        )


def test_one_filter_serves_every_row(dialog):
    """One filter for both lists, owned by the dialog — not one per row."""
    from ui.widgets.template_dialog import _RowSelectFilter

    filter_object = dialog._row_select_filter
    assert filter_object is not None, "no row was wired at all"
    assert filter_object.parent() is dialog, (
        "the filter is not owned by the dialog — nothing would free it"
    )
    assert sum(1 for child in dialog.children() if isinstance(child, _RowSelectFilter)) == 1


def test_rebuilding_the_rows_frees_the_old_ones_without_a_collection(dialog, no_gc):
    """The frequency case: every keystroke in the search box rebuilds both
    lists, so a cycle here pinned one whole row subtree per keystroke."""
    refs = [weakref.ref(row) for row in _shop_rows(dialog) + _task_rows(dialog)]
    assert len(refs) == 12

    dialog._on_shop_search_changed("")
    dialog._on_task_search_changed("")
    _flush()

    assert _alive(refs) == 0, (
        f"{_alive(refs)}/{len(refs)} orphaned rows are still reachable with the "
        f"collector off — something on the row references the row again"
    )


# ---------------------------------------------------------------------------
# L4 — the two "whole row toggles its checkbox" dialogs
# ---------------------------------------------------------------------------


def _build_picker():
    from ui.widgets.template_dialog import _StandardTemplatePickerDialog

    entries = [
        {"title": f"Standard {i}", "schedule": "daily", "location": "Camp"}
        for i in range(4)
    ]
    return _StandardTemplatePickerDialog(entries, parent=None, language="en", tr_func=tr)


@pytest.fixture
def picker(qapp):
    dlg = _build_picker()
    yield dlg
    dlg.deleteLater()
    _flush()


def test_clicking_a_standard_row_toggles_its_checkbox(picker):
    """User-reported 2026-09-05: the checkbox's own hit area is narrower
    than the row, so the row has to own every pixel of the click."""
    row = picker._rows[1][0]
    check = row.findChild(QCheckBox)
    assert check is not None and not check.isChecked()

    _click(row)
    assert check.isChecked(), "the row body no longer toggles its checkbox"
    _click(row)
    assert not check.isChecked(), "a second click no longer untoggles it"


def test_a_standard_row_carries_no_handler_of_its_own(picker):
    from ui.widgets.template_dialog import _CheckRow

    for row, _schedule, _location in picker._rows:
        assert isinstance(row, _CheckRow)
        assert "mousePressEvent" not in vars(row), (
            "on_row_press is back on the row, capturing the row and its "
            "checkbox as default arguments (review G/L4)"
        )


def test_the_check_rows_are_freed_without_a_collection(qapp, no_gc):
    # Its own dialog, not the fixture's: this test destroys the subject.
    dialog = _build_picker()
    refs = [weakref.ref(row) for row, _s, _l in dialog._rows]
    assert len(refs) == 4

    dialog._rows.clear()
    dialog._checks.clear()
    dialog.deleteLater()
    del dialog
    _flush()

    assert _alive(refs) == 0, (
        f"{_alive(refs)}/{len(refs)} rows outlived the dialog with the collector "
        f"off — the closure that captured `r=row` is back"
    )


def test_the_sync_dialog_rows_toggle_the_same_way(qapp):
    """``_StandardSyncDialog`` carried a second copy of the same closure."""
    from ui.widgets.template_dialog import _CheckRow, _StandardSyncDialog

    dlg = _StandardSyncDialog(
        [{"title": "New one", "schedule": "weekly", "location": "Camp"}],
        parent=None,
        language="en",
        tr_func=tr,
    )
    try:
        rows = dlg.findChildren(_CheckRow)
        assert rows, "the sync dialog built no rows"
        check = rows[0].findChild(QCheckBox)
        before = check.isChecked()
        _click(rows[0])
        assert check.isChecked() is not before
        assert "mousePressEvent" not in vars(rows[0])
    finally:
        dlg.deleteLater()
        _flush()


# ---------------------------------------------------------------------------
# L2 / L4 — the overlay HUD (rebuilt on every tick)
# ---------------------------------------------------------------------------


def test_clicking_a_section_header_collapses_it(qapp):
    from ui.overlay.overlay_window import _AccordionSection, _ClickableWidget

    section = _AccordionSection("Tasks", 3, True)
    try:
        assert isinstance(section._header, _ClickableWidget)
        assert section._open is True

        _click(section._header)
        assert section._open is False, "the header click no longer toggles the section"
        # The chevron was a "▸"/"▾" QLabel until the icons wave; it is a
        # Lucide IconLabel now, so the collapsed state is read off the icon
        # it paints rather than off its text (MASTER §3).
        assert section._chevron.icon_name == "chevron-right"

        _click(section._header)
        assert section._open is True
    finally:
        section.deleteLater()
        _flush()


def _first_section(overlay):
    """The first real ``_AccordionSection`` inside a live overlay."""
    from ui.overlay.overlay_window import _AccordionSection

    overlay.refresh()
    _flush()
    sections = overlay.findChildren(_AccordionSection)
    assert sections, "the overlay rendered no accordion section to click"
    return sections[0]


def test_the_header_press_never_reaches_the_overlays_drag_band(win):
    """The header is INSIDE the overlay here, and that is the whole point.

    ``OverlayWindow.mousePressEvent`` starts a window drag for any press
    with ``pos().y() <= 38``, and the first accordion header's top rows sit
    inside that band.  ``_ClickableWidget`` used to end in
    ``super().mousePressEvent(event)``; ``QWidget::mousePressEvent``
    *ignores* the event, so Qt walked the press up to the overlay and one
    click on the top pixel row both collapsed the section and grabbed the
    always-on HUD — the next mouse move dragged the whole window.

    The test that shipped with that change built a **parentless**
    ``_AccordionSection``, so the parent chain the bug needs did not exist
    under test.  This one uses the real overlay, and proves three things:
    the press is consumed, the coordinate really is inside the drag band
    (otherwise consuming it would prove nothing), and the window does not
    move afterwards.
    """
    overlay = win.overlay
    section = _first_section(overlay)
    header = section._header

    # The header's top-left in overlay coordinates -- inside the band.
    in_overlay = header.mapTo(overlay, QPoint(20, 0))
    assert in_overlay.y() <= 38, (
        "this header no longer overlaps the drag band; move the test to one "
        "that does, or the assertion below is vacuous"
    )

    overlay._drag_pos = None
    was_open = section._open
    before = overlay.pos()

    event = QMouseEvent(
        QEvent.MouseButtonPress, QPointF(20.0, 0.0), QPointF(500.0, 500.0),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
    )
    QApplication.sendEvent(header, event)

    assert section._open is not was_open, "the header click no longer toggles"
    assert event.isAccepted(), (
        "the header must CONSUME the press; an ignored one is propagated to "
        "the overlay by Qt and starts a window drag"
    )
    assert overlay._drag_pos is None, "the press started a window drag"

    _send(overlay, QEvent.MouseMove, at=(40.0, 60.0), globally=(540.0, 560.0))
    assert overlay.pos() == before, "the HUD moved after a header click"

    # And the band IS live at that coordinate: the same press delivered to
    # the overlay itself does start a drag.  Without this the assertion
    # above would pass on a header that simply sits below y=38.
    _send(overlay, QEvent.MouseButtonPress, at=(float(in_overlay.x()), 0.0))
    assert overlay._drag_pos is not None, (
        "the drag band no longer covers the header's top row — re-anchor "
        "this test rather than deleting it"
    )
    overlay._drag_pos = None
    section._toggle()  # leave the overlay as it was found


def test_a_section_header_carries_no_handler_of_its_own(qapp):
    from ui.overlay.overlay_window import _AccordionSection

    section = _AccordionSection("Guide", 1, False)
    try:
        assert "mousePressEvent" not in vars(section._header), (
            "the header lambda is back — it captures the section, which owns "
            "the header, so the pair can only be freed by the collector"
        )
    finally:
        section.deleteLater()
        _flush()


def test_the_section_toggle_callback_still_fires(qapp):
    """``on_toggle`` is how the overlay remembers open/closed across a
    refresh (User-reported, 2026-08-30) — the signal must carry it."""
    from ui.overlay.overlay_window import _AccordionSection

    seen = []
    section = _AccordionSection("Tasks", 2, True, on_toggle=seen.append)
    try:
        _click(section._header)
        assert seen == [False]
    finally:
        section.deleteLater()
        _flush()


def test_dragging_the_resize_handle_resizes_the_overlay(win):
    overlay = win.overlay
    handle = overlay._resize_handle
    start_height = overlay.height()

    _send(handle, QEvent.MouseButtonPress, globally=(0.0, 200.0))
    _send(handle, QEvent.MouseMove, button=Qt.NoButton, globally=(0.0, 260.0))
    assert overlay.height() == start_height + 60, (
        f"the grip no longer resizes: {start_height} -> {overlay.height()}"
    )

    _send(handle, QEvent.MouseButtonRelease, buttons=Qt.NoButton, globally=(0.0, 260.0))
    assert overlay._resize_pos is None, "the drag never ended"

    # A move with no drag in flight must do nothing.
    settled = overlay.height()
    _send(handle, QEvent.MouseMove, button=Qt.NoButton, globally=(0.0, 400.0))
    assert overlay.height() == settled

    overlay.resize(overlay.width(), start_height)


def test_the_resize_handle_stores_no_bound_method(win):
    """The worst of the four: bound methods on the handle made the handle's
    ``__dict__`` point at the overlay, which is parentless and holds
    ``main_window`` — one cycle pinning the entire MainWindow."""
    handle = win.overlay._resize_handle
    for name in ("mousePressEvent", "mouseMoveEvent", "mouseReleaseEvent"):
        assert name not in vars(handle), f"{name} is stored on the handle again"


# ---------------------------------------------------------------------------
# L3 — Flow Map node cards (three closures each)
# ---------------------------------------------------------------------------


@pytest.fixture
def flow(win):
    """The real Flow Map window, on a one-node demo map."""
    window = win.flow_map_window
    window.add_demo_flow()
    assert window.node_cards, "the demo map rendered no card"
    return window


def _first_card(window):
    node_id, card = next(iter(window.node_cards.items()))
    return window.nodes[node_id], card


def test_dragging_a_node_card_moves_the_node(flow):
    node, card = _first_card(flow)
    flow.current_tool = "select"
    start = (node.x, node.y)

    _send(card, QEvent.MouseButtonPress, globally=(100.0, 100.0))
    _send(card, QEvent.MouseMove, button=Qt.NoButton, globally=(160.0, 140.0))
    _send(card, QEvent.MouseButtonRelease, buttons=Qt.NoButton, globally=(160.0, 140.0))

    assert (node.x, node.y) == (start[0] + 60 / flow.zoom_factor,
                                start[1] + 40 / flow.zoom_factor), (
        f"the card no longer drags its node: {start} -> {(node.x, node.y)}"
    )


def test_a_press_under_the_drag_threshold_is_a_click(flow):
    """Under 5 px the gesture is a selection, not a move (unchanged)."""
    node, card = _first_card(flow)
    flow.current_tool = "select"
    start = (node.x, node.y)

    _send(card, QEvent.MouseButtonPress, globally=(100.0, 100.0))
    _send(card, QEvent.MouseMove, button=Qt.NoButton, globally=(102.0, 101.0))
    _send(card, QEvent.MouseButtonRelease, buttons=Qt.NoButton, globally=(102.0, 101.0))

    assert (node.x, node.y) == start, "a 2 px wobble moved the node"
    assert flow.selected_node_id == node.id, "the click no longer selects the node"


def test_the_done_button_toggles_its_own_node(flow):
    """The ✓ used to be wired with ``lambda node_id=node.id: …``; it resolves
    the card from the sender now, so the wrong node must not move."""
    node, card = _first_card(flow)
    before = node.status
    card.done_btn.click()
    assert flow.nodes[node.id].status != before, "the ✓ no longer toggles the node"
    card.done_btn.click()
    assert flow.nodes[node.id].status == before


def test_a_node_card_carries_no_handler_of_its_own(flow):
    for card in flow.node_cards.values():
        for name in ("mousePressEvent", "mouseMoveEvent", "mouseReleaseEvent"):
            assert name not in vars(card), (
                f"{name} is stored on the card again — three closures per "
                f"card, each capturing the card, the node and the window "
                f"(review G/L3)"
            )


def test_one_drag_state_for_the_window_not_one_per_card(flow):
    """The dict the three closures shared is the window's now: only one card
    can be mid-drag, because the mouse is grabbed by the one that was
    pressed."""
    node, card = _first_card(flow)
    _send(card, QEvent.MouseButtonPress, globally=(100.0, 100.0))
    assert flow._node_drag_state is not None
    assert flow._node_drag_state["start_node"] == (node.x, node.y)
    _send(card, QEvent.MouseButtonRelease, buttons=Qt.NoButton, globally=(100.0, 100.0))


def test_clearing_the_cards_frees_them_without_a_collection(flow, no_gc):
    """Teeth verified: with the three closures put back, this reports 1/1."""
    refs = [weakref.ref(card) for card in flow.node_cards.values()]
    assert refs

    flow.clear_node_cards()
    _flush()

    assert _alive(refs) == 0, (
        f"{_alive(refs)}/{len(refs)} node cards are still reachable with the "
        f"collector off — a closure on the card references the card again"
    )


# ---------------------------------------------------------------------------
# m4 — every singleShot carries a context object
# ---------------------------------------------------------------------------


_SINGLE_SHOT = re.compile(r"QTimer\.singleShot\(")


def _singleshot_arity(source: str, open_paren: int) -> int:
    """How many top-level arguments the call starting at ``open_paren`` has.

    Counted by walking the text rather than by regex: an argument can be a
    lambda or a call with commas of its own, and ``[^,)]+`` would stop at
    the first of them.
    """
    depth = 0
    arguments = 1
    for index in range(open_paren, len(source)):
        char = source[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                return arguments
        elif char == "," and depth == 1:
            arguments += 1
    return arguments


def test_every_singleshot_in_our_own_code_passes_a_context_object():
    """``QTimer.singleShot(ms, callable)`` has no owner.

    PySide holds the callable strongly and nothing disconnects it, so the
    slot still runs after its widget's C++ side is gone — "Internal C++
    object already deleted", raised inside the Qt event loop and reported
    against whichever test happened to pump next.  The three-argument
    overload ``singleShot(ms, context, callable)`` ties the timer to a
    QObject and Qt drops it with that object (review G/m4; PySide6 6.11
    accepts it — every call site below is already on it).
    """
    offenders = []
    checked = 0
    for path in sorted(list((ROOT / "ui").rglob("*.py")) + list((ROOT / "core").rglob("*.py"))):
        source = path.read_text(encoding="utf-8")
        for match in _SINGLE_SHOT.finditer(source):
            checked += 1
            # ``singleShot(ms, callable)`` is the unowned overload;
            # ``singleShot(ms, context, callable)`` is the one we want.
            if _singleshot_arity(source, match.end() - 1) < 3:
                line = source.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(ROOT)}:{line}")
    assert checked >= 7, f"only {checked} singleShot call sites found — wrong tree?"
    assert not offenders, (
        "QTimer.singleShot without a context object — pass the owning widget "
        "as the second argument:\n  " + "\n  ".join(offenders)
    )
