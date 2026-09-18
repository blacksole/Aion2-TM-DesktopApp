"""No test may ever open a window on a real screen.

This is the one guarantee the whole Qt half of the suite rests on, and it
failed silently on 2026-09-18: ``tests/conftest.py`` asked for the offscreen
platform with ``os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")``, and
a desktop session exports its own value (Omarchy: ``"wayland;xcb"``), so
setdefault did nothing.  Every MainWindow, overlay, dialog and Armory window
the suite builds was therefore a real window on the developer's compositor,
and the grab-heavy render gate froze his desktop.

An env-var read would not have caught it either -- the variable was set, just
not to what the suite needs.  So this asks the only authority that cannot be
wrong: the QApplication that is actually running.
"""

import os

from PySide6.QtGui import QGuiApplication


def test_the_running_qapplication_is_offscreen(qapp):
    """The live platform plugin, not the request that produced it."""
    assert QGuiApplication.platformName() == "offscreen", (
        f"the suite is running on the {QGuiApplication.platformName()!r} "
        f"platform plugin: every test window is a REAL window on a real "
        f"screen. tests/conftest.py must ASSIGN QT_QPA_PLATFORM, not "
        f"setdefault it -- a desktop session exports its own value."
    )


def test_the_environment_the_plugin_was_chosen_from_says_offscreen():
    """The request as well, so a subprocess a test spawns inherits it."""
    assert os.environ.get("QT_QPA_PLATFORM") == "offscreen", (
        f"QT_QPA_PLATFORM is {os.environ.get('QT_QPA_PLATFORM')!r}; a child "
        f"process started by a test would open real windows"
    )


def test_no_test_window_is_visible_on_a_screen(qapp):
    """Belt and braces: nothing left showing, whatever the platform.

    ``QWidget.grab()`` renders through the raster engine and needs no
    mapped window, so a test never has a reason to leave one visible.
    """
    from PySide6.QtWidgets import QApplication

    visible = [
        f"{type(widget).__name__}#{widget.objectName()}"
        for widget in QApplication.topLevelWidgets()
        if widget.isVisible()
    ]
    assert not visible, f"top-level widgets still shown: {visible}"
