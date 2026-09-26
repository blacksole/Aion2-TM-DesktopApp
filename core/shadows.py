"""MASTER §1's single popup shadow — parsed from the token, painted by hand.

``shadow.popup`` -- an offset, a blur and a translucent black, spelled once
in :mod:`core.theme` and nowhere else -- is the *only* shadow the
design system defines, "reserved for popups/tooltips".  Qt has two ways to
honour it and both have a catch:

* ``QGraphicsDropShadowEffect`` makes Qt paint the widget into a bounding
  rect **expanded** by the blur radius plus the offset.  On a
  ``WA_TranslucentBackground`` top-level that is fatal on Windows: the dirty
  rect handed to ``UpdateLayeredWindowIndirect`` no longer matches the
  window's real size and the call fails on every paint (diagnosed on the
  Daevanion tooltip, 2026-09-23 — see ``_TranslucentCardTooltip``).
* A CSS ``box-shadow`` does not exist in Qt's stylesheet dialect at all.

So the shadow is painted by hand, and the widget reserves room for it *in
its own rect*: :func:`shadow_margins` says how much, the card is drawn
inset by exactly that, and :func:`paint_popup_shadow` fills the band between
the two.  Nothing ever wants to paint outside ``widget.rect()``, which is
what keeps Windows happy, and the shadow lands beside the card instead of
underneath it.

Qt-light like :mod:`core.theme`: ``QtGui``/``QtCore`` only, no widgets, no
``QApplication`` needed to import.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter

from core import theme

__all__ = [
    "SHADOW_STEPS",
    "paint_popup_shadow",
    "parse_shadow",
    "popup_shadow",
    "shadow_margins",
]

#: How many rounded rects approximate the blur.  Ten is what the Daevanion
#: tooltip already used and reads as a gradient rather than as bands at the
#: 18px blur the token asks for.
SHADOW_STEPS = 10

#: Fallback geometry if the token is ever reshaped -- the Abyss values.
_FALLBACK_BLUR = 18
_FALLBACK_DY = 6
_FALLBACK_ALPHA = 0.35


def parse_shadow(value: str) -> tuple[int, int, QColor]:
    """``(blur, y-offset, colour)`` out of a ``shadow.*`` token.

    The token is a CSS shadow string -- offset, blur and a translucent
    black -- because that is the form the QSS template needs.  Reading it
    here keeps one definition instead of a second, silently diverging copy
    in code (MASTER §4-3).
    """
    numbers = re.findall(r"(\d+(?:\.\d+)?)", value or "")
    try:
        dy = int(float(numbers[1]))
        blur = int(float(numbers[2]))
        red, green, blue = (int(float(n)) for n in numbers[3:6])
        colour = QColor(red, green, blue)
        colour.setAlphaF(float(numbers[6]))
    except (IndexError, ValueError):  # pragma: no cover - token reshaped
        fallback = QColor(theme.qcolor(theme.current_tokens(), "bg.window"))
        fallback.setAlphaF(_FALLBACK_ALPHA)
        return _FALLBACK_BLUR, _FALLBACK_DY, fallback
    return blur, dy, colour


def popup_shadow(tokens=None) -> tuple[int, int, QColor]:
    """:func:`parse_shadow` of the ACTIVE theme's ``shadow.popup``."""
    tokens = tokens if tokens is not None else theme.current_tokens()
    return parse_shadow(tokens.shadow_popup)


def shadow_margins(blur: int, dy: int) -> tuple[int, int, int, int]:
    """``(left, top, right, bottom)`` a card must keep free around itself.

    The shadow is the card's own rect moved down by ``dy`` and grown by
    ``blur`` on every side, so the band it needs is asymmetric: ``blur``
    left and right, ``blur - dy`` above (never negative) and ``blur + dy``
    below.
    """
    return blur, max(0, blur - dy), blur, blur + dy


def paint_popup_shadow(
    painter: QPainter,
    card_rect: QRect,
    blur: int,
    dy: int,
    colour: QColor,
    radius: int,
) -> None:
    """Fill the band around ``card_rect`` with the soft shadow.

    ``card_rect`` is where the opaque card will be drawn; every ring is
    larger than it, so the card fill that follows covers none of them --
    which is the whole difference from painting the rings under the card.
    """
    painter.setPen(Qt.NoPen)
    base_alpha = colour.alpha()
    for step in range(SHADOW_STEPS, 0, -1):
        grow = max(1, round(blur * step / SHADOW_STEPS))
        alpha = max(1, int(base_alpha * (1 - step / SHADOW_STEPS) * 0.5))
        ring = QColor(colour)
        ring.setAlpha(alpha)
        painter.setBrush(ring)
        rect = card_rect.translated(0, dy).adjusted(-grow, -grow, grow, grow)
        painter.drawRoundedRect(rect, radius + grow, radius + grow)
