"""Shared test setup: headless Qt so the suite runs on CI and on Linux without a display."""
import gc
import os
import sys
import warnings
from pathlib import Path

# FORCED, not setdefault.  A desktop session exports its own value -- Omarchy
# sets ``QT_QPA_PLATFORM="wayland;xcb"`` -- and ``setdefault`` then does
# nothing, so the suite ran on the developer's real compositor: every test
# MainWindow, overlay and dialog opened an actual window on his screen and a
# grab-heavy module could lock the desktop up.  There is no case in which a
# test wants the session's platform, so this is an assignment.
# ``tests/test_headless.py`` asserts the result on the live QApplication.
os.environ["QT_QPA_PLATFORM"] = "offscreen"
# Never let a test MainWindow start the real startup update-check QThread.
os.environ.setdefault("AION2TM_NO_UPDATE_CHECK", "1")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402  (must follow the sys.path insert above)


@pytest.fixture(autouse=True)
def _no_animation_crosses_a_test():
    """Stop and forget every live animation at the end of each test.

    An armed ``finished`` callback is a reference to a MainWindow plus a
    post-condition (``refresh()``, ``hide()``) waiting for the event loop.
    Tests rarely pump the loop for the full 160 ms of a fade, so without
    this the callbacks pile up and fire inside *whichever later test happens
    to pump* — a wall-clock dependency, and the reported 1-in-3 flake
    (review F-3).  Draining here makes each test's animation state its own.
    """
    yield
    from ui import motion

    motion.drain()


# Deliberately NOT forcing reduced motion globally here: a MainWindow calls
# set_reduce_motion() from its own profile on every load, so a global switch
# would be overwritten by the app under test.  The two places that assert a
# state a fade now reaches asynchronously pump the event loop instead (see
# tests/test_soft_delete.py's `settled` helper).


#: The windows a MainWindow owns in Python but NOT as a Qt parent: the
#: overlay is a parentless ``Qt.Tool``, the Flow Map and the Armory's
#: ItemDatabase window are parentless top-levels.  ``findChildren`` cannot
#: reach any of them, so ``destroy_window`` has to name them -- and
#: ``tests/test_widget_lifecycle.py`` fails the day a fourth appears
#: (review G/m5).
HOST_WINDOW_ATTRIBUTES = ("overlay", "flow_map_window", "item_database_window")


def destroy_window(window) -> None:
    """Tear a test MainWindow down for real, not just visually.

    ``close()`` alone only hides a window: the widget tree stays alive for
    the rest of the session, because the module-scoped fixture's reference
    goes away without Qt ever processing a deletion.  With five test modules
    each building a MainWindow, the process ends up holding ~15 000 live
    widgets — and since the stylesheet now lives on the **QApplication**
    (MASTER §4-1), every single ``setStyleSheet`` / ``setPalette`` has to
    re-resolve against all of them.  Measured: one theme switch cost 9 s
    with five windows alive versus ~0.2 s with one.

    So: close it, drop it, and pump the DeferredDelete queue so Qt frees the
    tree before the next module starts.  The overlay and the Flow Map window
    are handled explicitly — the overlay is a parentless ``Qt.Tool`` window
    (it takes MainWindow as a plain argument, not as a Qt parent), so
    nothing would ever collect it otherwise.
    """
    from PySide6.QtCore import QEvent, QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()

    named_children = [
        child
        for child in (
            getattr(window, attribute, None) for attribute in HOST_WINDOW_ATTRIBUTES
        )
        if child is not None
    ]

    # Timers FIRST, on the window AND on each parentless child, before
    # anything is closed (review G/m5).  The sweep used to run only on
    # ``window`` and only after the close loop above had already
    # ``deleteLater``'d those three -- so the two window trees whose timers
    # actually matter (the overlay's 1 s ``_tick_timer``, the Armory's icon
    # request timer) were never reached by it: ``findChildren`` sees Qt
    # children, and a parentless top-level is not one.
    #
    # A slot that runs after its C++ side is gone raises inside the Qt event
    # loop ("Internal C++ object already deleted"), which pytest-qt reports
    # against whichever test happened to pump next.  So: stop every timer
    # while the objects its slot touches are still alive, then drain what
    # was already queued.
    for root in [window, *named_children]:
        for timer_attribute in ("countdown_timer", "_tick_timer"):
            timer = getattr(root, timer_attribute, None)
            if timer is not None:
                timer.stop()
        for timer in root.findChildren(QTimer):
            timer.stop()
    if app is not None:
        app.processEvents()

    for child in named_children:
        child.close()
        child.deleteLater()

    window.close()
    window.deleteLater()

    if app is not None:
        # Two passes, and a gc.collect() between them.  One pass is not
        # enough: the first DeferredDelete flush destroys the C++ trees, but
        # what is left over is *Python* -- wrapper objects still reachable
        # from a cycle (a widget's own ``__dict__`` pointing back at itself
        # through a closure or a lambda slot, review F "Re-verification 2").
        # Until the collector breaks those, the wrappers keep their children
        # alive and any deleteLater they themselves posted never runs.
        app.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
        gc.collect()
        app.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
    else:
        gc.collect()


def live_widget_count() -> int:
    """How many QWidgets the process is still holding.

    The number the suite's cost is proportional to: the stylesheet lives on
    the QApplication (MASTER §4-1), so every ``setStyleSheet`` /
    ``setPalette`` re-resolves against every live widget in the process, no
    matter which module created it.
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return len(app.allWidgets()) if app is not None else 0


#: How many widgets a single test module may leave behind before the census
#: below says so.  A module that builds one MainWindow and tears it down with
#: ``destroy_window`` settles at a couple of dozen; a module that forgets the
#: teardown leaves several hundred.  Deliberately a WARNING, not a failure:
#: this is a budget on a global resource, and a test module should not fail
#: because of what an earlier one left in the QApplication.
WIDGET_LEAK_BUDGET = 150

#: ``[(module, before, after)]`` -- filled by the census fixture, printed by
#: ``pytest_terminal_summary``.
_WIDGET_CENSUS: list[tuple[str, int, int]] = []


@pytest.fixture(scope="module", autouse=True)
def _widget_census(request):
    """Report (never enforce) how many widgets each module leaves behind.

    Autouse and module-scoped, so it brackets every module's own window
    fixtures: autouse fixtures of a scope are set up before the non-autouse
    ones of that same scope, which puts ``before`` ahead of the MainWindow
    build and ``after`` behind its teardown.
    """
    before = live_widget_count()
    yield
    gc.collect()
    after = live_widget_count()
    _WIDGET_CENSUS.append((request.node.name, before, after))
    leaked = after - before
    if leaked > WIDGET_LEAK_BUDGET:
        warnings.warn(
            f"{request.node.name} left {leaked} widgets alive "
            f"({before} -> {after}); budget is {WIDGET_LEAK_BUDGET}. "
            f"Every later app-wide restyle now pays for them.",
            stacklevel=1,
        )


def pytest_terminal_summary(terminalreporter):
    """One line per module: widgets before -> after, and what leaked."""
    if not _WIDGET_CENSUS:
        return
    worst = sorted(_WIDGET_CENSUS, key=lambda row: row[2] - row[1], reverse=True)
    terminalreporter.write_sep("=", "live widget census (top 10 by leak)")
    for name, before, after in worst[:10]:
        terminalreporter.write_line(f"{after - before:+6d}  {before:5d} -> {after:5d}  {name}")
    terminalreporter.write_line(f"final live widgets: {live_widget_count()}")
