"""Shared test setup: headless Qt so the suite runs on CI and on Linux without a display."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Never let a test MainWindow start the real startup update-check QThread.
os.environ.setdefault("AION2TM_NO_UPDATE_CHECK", "1")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Deliberately NOT forcing reduced motion globally here: a MainWindow calls
# set_reduce_motion() from its own profile on every load, so a global switch
# would be overwritten by the app under test.  The two places that assert a
# state a fade now reaches asynchronously pump the event loop instead (see
# tests/test_soft_delete.py's `settled` helper).


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
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    for attribute in ("overlay", "flow_map_window", "item_database_window"):
        child = getattr(window, attribute, None)
        if child is not None:
            child.close()
            child.deleteLater()

    for timer_attribute in ("countdown_timer", "_tick_timer"):
        timer = getattr(window, timer_attribute, None)
        if timer is not None:
            timer.stop()

    window.close()
    window.deleteLater()

    app = QApplication.instance()
    if app is not None:
        app.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
