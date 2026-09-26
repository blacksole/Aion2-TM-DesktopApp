"""MASTER §1's one shadow: one definition, and it actually renders.

``shadow.popup`` ("0 6px 18px rgba(0, 0, 0, 0.35)") is the only shadow the
design system defines.  Before the Apex review of PR #7 it was applied in
two places and worked in neither: the Daevanion/Skill tooltips painted it
UNDER their own opaque card (finding 4), and the calendar popup handed it to
a ``QGraphicsDropShadowEffect`` on an opaque ``Qt::Popup`` (finding 9) --
the same construct whose expanded bounding rect had just been diagnosed as
the cause of Windows' ``UpdateLayeredWindowIndirect`` failures.

The pixel-level proof for the tooltip lives in ``tests/test_armory_theme.py``
(it needs the Armory module).  This module pins the arithmetic and the
calendar popup, both of which need neither.
"""
from __future__ import annotations

import ast
import gc
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication, QDateEdit  # noqa: E402

from core import shadows, theme  # noqa: E402
from ui.widgets import calendar_popup  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# 1. the token, read once
# ---------------------------------------------------------------------------

def test_the_token_parses_into_its_three_parts():
    blur, dy, colour = shadows.parse_shadow("0 6px 18px rgba(0, 0, 0, 0.35)")
    assert (blur, dy) == (18, 6)
    assert (colour.red(), colour.green(), colour.blue()) == (0, 0, 0)
    assert colour.alpha() == pytest.approx(89, abs=1)


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_every_theme_agrees_on_the_popup_shadow(name):
    """MASTER §2 lets a theme redefine only accent*/secondary*/bg.* -- which
    is what makes it safe for a widget to size its shadow band ONCE."""
    blur, dy, _colour = shadows.popup_shadow(theme.THEMES[name])
    assert (blur, dy) == shadows.popup_shadow(theme.THEMES["abyss"])[:2]


def test_a_reshaped_token_falls_back_instead_of_raising(qapp):
    theme.apply(qapp, "Abyss")
    blur, dy, colour = shadows.parse_shadow("inset none")
    assert (blur, dy) == (18, 6)
    assert isinstance(colour, QColor)


def test_the_margins_are_the_band_the_blur_actually_needs():
    """Down and out: ``blur`` each side, ``blur - dy`` above, ``blur + dy``
    below -- never negative, so an offset larger than the blur cannot ask
    for a negative top margin."""
    assert shadows.shadow_margins(18, 6) == (18, 12, 18, 24)
    assert shadows.shadow_margins(10, 40) == (10, 0, 10, 50)
    assert shadows.shadow_margins(0, 0) == (0, 0, 0, 0)


# ---------------------------------------------------------------------------
# 2. the calendar popup
# ---------------------------------------------------------------------------

def _date_edit(qapp) -> QDateEdit:
    theme.apply(qapp, "Abyss")
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    return edit


def _drop(qapp, widget) -> None:
    """Free the popup tree for real -- ``deleteLater`` alone posts an event
    a plain ``processEvents()`` never delivers (see conftest's
    ``destroy_window``)."""
    from PySide6.QtCore import QEvent

    widget.deleteLater()
    for _ in range(2):
        qapp.sendPostedEvents(None, QEvent.DeferredDelete)
        qapp.processEvents()
        gc.collect()


def test_the_calendar_popup_installs_no_graphics_effect(qapp):
    """Finding 9: an effect on an opaque Qt::Popup is the bug class the
    tooltip fix had just removed, and it clipped the shadow anyway."""
    edit = _date_edit(qapp)
    try:
        calendar = calendar_popup.style_calendar_popup(edit)
        assert calendar is not None
        assert calendar.graphicsEffect() is None
        container = calendar.parentWidget()
        if container is not None:
            assert container.graphicsEffect() is None
    finally:
        _drop(qapp, edit)


def test_restyling_follows_a_theme_switch(qapp):
    """The QTextCharFormat colours are captured at call time, so the popup
    only follows a theme switch if something calls it again."""
    edit = _date_edit(qapp)
    try:
        calendar = calendar_popup.style_calendar_popup(edit)
        from PySide6.QtCore import Qt

        abyss = calendar.weekdayTextFormat(Qt.DayOfWeek.Monday).foreground().color()

        theme.apply(qapp, "Inferno")
        assert calendar_popup.calendar_needs_restyle()
        calendar_popup.style_calendar_popup(edit)
        inferno = calendar.weekdayTextFormat(Qt.DayOfWeek.Monday).foreground().color()

        assert inferno == theme.qcolor(theme.current_tokens(), "fg")
        assert abyss == theme.qcolor(theme.THEMES["abyss"], "fg")
    finally:
        theme.apply(qapp, "Abyss")
        _drop(qapp, edit)


def test_the_restyle_predicate_is_wired_to_a_real_call_site():
    """It was dead: always True, called from nowhere (finding 10).  Pinned
    as a source fact so it cannot quietly go dead again."""
    source = (ROOT / "ui" / "pages" / "settings_page.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "calendar_needs_restyle" in called
    assert "style_calendar_popup" in called
