"""The app's only animation helpers (MASTER §1 "Motion", §4-6).

Thesis, from MASTER: *motion confirms a state change*.  120–180 ms, opacity
and a 4–8 px translation, nothing else.  Concretely that means:

* **never** animate ``width``/``height``/``geometry`` of a layout-managed
  widget — the layout owns that geometry and fights back, which is why
  :func:`slide_hint` moves ``pos`` and is documented for *floating* widgets
  only (a toast, a popover, an overlay panel: anything with no parent layout,
  or parented but explicitly positioned).  Calling it on a layout-managed
  widget is a no-op-with-a-warning rather than a jitter bug;
* durations come from the tokens, never from a literal;
* :func:`set_reduced_motion` collapses every duration to 0 — MASTER calls
  this "non négociable", so it is a module-level switch the settings page
  can flip once instead of a flag threaded through every call site.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QEasingCurve, QObject, QPoint, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from core.theme import DEFAULT_THEME, tokens

logger = logging.getLogger(__name__)

_reduced_motion = False

#: Keeps running animations alive: a QPropertyAnimation that nobody holds a
#: reference to is garbage-collected mid-flight and the widget freezes
#: half-faded.  Entries remove themselves when the animation finishes.
_running: set[QPropertyAnimation] = set()

_EASING = {
    "OutCubic": QEasingCurve.Type.OutCubic,
    "InCubic": QEasingCurve.Type.InCubic,
    "InOutCubic": QEasingCurve.Type.InOutCubic,
    "Linear": QEasingCurve.Type.Linear,
}


def set_reduced_motion(enabled: bool) -> None:
    """Turn every animation into an instant state change (accessibility)."""
    global _reduced_motion
    _reduced_motion = bool(enabled)


def reduced_motion() -> bool:
    """Whether reduced motion is currently on."""
    return _reduced_motion


def _tokens(theme: str | None):
    return tokens(theme or DEFAULT_THEME)


def duration(kind: str = "base", theme: str | None = None) -> int:
    """Duration in ms for ``fast`` / ``base`` / ``slow``; 0 if reduced."""
    if _reduced_motion:
        return 0
    attr = f"motion_{kind}"
    theme_tokens = _tokens(theme)
    if not hasattr(theme_tokens, attr):
        raise KeyError(f"Unknown motion token: {kind!r}")
    return int(getattr(theme_tokens, attr))


def _curve(theme: str | None) -> QEasingCurve.Type:
    name = _tokens(theme).motion_ease
    curve = _EASING.get(name)
    if curve is None:
        logger.warning("Unknown easing %r — using OutCubic", name)
        return QEasingCurve.Type.OutCubic
    return curve


def _opacity_effect(widget: QWidget) -> QGraphicsOpacityEffect:
    """Reuse the widget's opacity effect, or install one."""
    effect = widget.graphicsEffect()
    if isinstance(effect, QGraphicsOpacityEffect):
        return effect
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    return effect


def _keep(animation: QPropertyAnimation) -> None:
    _running.add(animation)
    animation.finished.connect(lambda: _running.discard(animation))


def _animate(
    target: QObject,
    prop: bytes,
    start,
    end,
    ms: int,
    theme: str | None,
    then=None,
) -> QPropertyAnimation | None:
    """Run one property animation, or apply the end value instantly at 0 ms."""
    if ms <= 0:
        target.setProperty(prop.decode(), end)
        if then is not None:
            then()
        return None

    animation = QPropertyAnimation(target, prop)
    animation.setDuration(ms)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(_curve(theme))
    if then is not None:
        animation.finished.connect(then)
    _keep(animation)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


def fade_in(widget: QWidget, theme: str | None = None, kind: str = "base") -> QPropertyAnimation | None:
    """Show ``widget`` by fading its opacity 0 → 1 (``motion.base``)."""
    effect = _opacity_effect(widget)
    effect.setOpacity(0.0)
    widget.show()
    return _animate(effect, b"opacity", 0.0, 1.0, duration(kind, theme), theme)


def fade_out(
    widget: QWidget,
    then=None,
    theme: str | None = None,
    kind: str = "base",
) -> QPropertyAnimation | None:
    """Fade ``widget`` 1 → 0, hide it, then call ``then`` if given."""
    effect = _opacity_effect(widget)
    effect.setOpacity(1.0)

    def finish() -> None:
        widget.hide()
        if then is not None:
            then()

    return _animate(effect, b"opacity", 1.0, 0.0, duration(kind, theme), theme, then=finish)


def slide_hint(
    widget: QWidget,
    theme: str | None = None,
    kind: str = "fast",
    direction: str = "up",
) -> QPropertyAnimation | None:
    """Nudge a **floating** widget ``motion.offset`` px into place.

    Only ``pos`` is animated, never geometry: a widget owned by a layout has
    its position recomputed on every layout pass, so animating it would
    fight the layout.  Such a widget is left alone (with a debug line) — use
    :func:`fade_in` for it instead.
    """
    if widget.parentWidget() is not None and widget.parentWidget().layout() is not None:
        layout = widget.parentWidget().layout()
        if layout.indexOf(widget) != -1:
            logger.debug("slide_hint skipped: %s is layout-managed", widget.objectName() or widget)
            return None

    offset = int(_tokens(theme).motion_offset)
    deltas = {
        "up": QPoint(0, offset),
        "down": QPoint(0, -offset),
        "left": QPoint(offset, 0),
        "right": QPoint(-offset, 0),
    }
    if direction not in deltas:
        raise ValueError(f"Unknown direction: {direction!r} (known: {sorted(deltas)})")

    end = widget.pos()
    start = end + deltas[direction]
    widget.move(start)
    return _animate(widget, b"pos", start, end, duration(kind, theme), theme)
