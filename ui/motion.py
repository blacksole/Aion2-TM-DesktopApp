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
#: half-faded.  Entries remove themselves when the animation finishes — and
#: also when they are SUPERSEDED, which is the part that was missing:
#:
#: Qt stops a competing animation on the same ``(target, propertyName)``
#: pair when a second one starts, and a *stopped* animation never emits
#: ``finished``.  Everything this module hangs on ``finished`` — the `then`
#: callback, the effect teardown, the removal from this set — was therefore
#: silently dropped for every superseded animation, so the set grew without
#: bound and each stale entry held an armed callback (and a reference to a
#: MainWindow) that could fire inside some arbitrary later moment when the
#: event loop next ran.  Measured at 46 armed callbacks at the end of one
#: test module (review F-3); that timing dependence was the reported flake.
#:
#: :func:`_animate` now retires the previous animation for a pair itself,
#: *before* starting the new one, so this set holds only live animations.
_running: dict[tuple[int, bytes], "QPropertyAnimation"] = {}

#: What happens to a superseded animation's ``then`` callback.  For the two
#: things this module animates — a fade in and a fade out of the same widget
#: — the newer animation is the one that expresses the user's latest intent,
#: so the older one's post-condition is DROPPED rather than run: running it
#: would hide a widget the newer fade has just shown, or re-render a list the
#: newer state has already rendered.  Callers that need a guaranteed
#: post-condition must not express it as a fade's `then`.
SUPERSEDED_POLICY = "drop"

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


def _drop_effect(widget: QWidget) -> None:
    """Uninstall the opacity effect once the fade is over.

    Not tidiness — cost.  A QGraphicsOpacityEffect makes Qt render the whole
    widget subtree into an offscreen buffer on EVERY repaint, for as long as
    it is installed.  Leaving one on a page of the QStackedWidget (or on the
    toast row) after a 220 ms fade therefore taxes every later paint of that
    page forever; measured on the test suite, which fades the same pages
    repeatedly, it was the difference between ~30 s and several minutes.

    Guarded: the widget may already be deleted by the time a queued
    ``finished`` handler runs (a soft-deleted card commits and calls
    ``deleteLater``), and touching a dead QWidget raises.
    """
    try:
        if isinstance(widget.graphicsEffect(), QGraphicsOpacityEffect):
            widget.setGraphicsEffect(None)
    except RuntimeError:  # the C++ object is gone; nothing left to clean up
        pass


def _key(target: QObject, prop: bytes) -> tuple[int, bytes]:
    """Identity of an animation slot: one property of one object."""
    return (id(target), prop)


def _retire(key: tuple[int, bytes]) -> None:
    """Stop and forget the animation occupying ``key``, if any.

    Called before starting a new animation on the same slot, so that the
    stop is *ours* — with the bookkeeping done — rather than Qt's silent one.
    """
    previous = _running.pop(key, None)
    if previous is None:
        return
    try:
        previous.stop()
    except RuntimeError:  # C++ side already gone
        return
    logger.debug("motion: superseded %s (policy=%s)", key, SUPERSEDED_POLICY)


def _keep(animation: QPropertyAnimation, key: tuple[int, bytes]) -> None:
    _running[key] = animation

    def _release() -> None:
        if _running.get(key) is animation:
            del _running[key]

    animation.finished.connect(_release)


def running_count() -> int:
    """How many animations are live.  Used by tests to pin the bound."""
    return len(_running)


def drain() -> None:
    """Stop and forget every live animation (test teardown)."""
    for animation in list(_running.values()):
        try:
            animation.stop()
        except RuntimeError:
            pass
    _running.clear()


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

    # Retire the slot's previous occupant FIRST: Qt would stop it anyway
    # when the new animation starts, but silently and without releasing its
    # callback (see the note on _running).  `then` is dropped per
    # SUPERSEDED_POLICY.
    key = _key(target, prop)
    _retire(key)

    animation = QPropertyAnimation(target, prop)
    animation.setDuration(ms)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(_curve(theme))
    if then is not None:
        animation.finished.connect(then)
    _keep(animation, key)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


#: Dynamic property holding a widget's fade generation.  Every fade bumps
#: it; a fade's completion handler compares against the value it captured,
#: so a fade that has been superseded cannot act on the widget any more.
_GENERATION = "_aion2_motion_gen"


def _next_generation(widget: QWidget) -> int:
    generation = int(widget.property(_GENERATION) or 0) + 1
    widget.setProperty(_GENERATION, generation)
    return generation


def _is_current(widget: QWidget, generation: int) -> bool:
    try:
        return int(widget.property(_GENERATION) or 0) == generation
    except RuntimeError:  # widget destroyed
        return False


def fade_in(widget: QWidget, theme: str | None = None, kind: str = "base") -> QPropertyAnimation | None:
    """Show ``widget`` by fading its opacity 0 → 1 (``motion.base``)."""
    generation = _next_generation(widget)
    effect = _opacity_effect(widget)
    effect.setOpacity(0.0)
    widget.show()

    def finish() -> None:
        # Only the newest fade may tear the effect down; an older one
        # completing here would strip the effect a newer fade is animating.
        if _is_current(widget, generation):
            _drop_effect(widget)

    return _animate(effect, b"opacity", 0.0, 1.0, duration(kind, theme), theme, then=finish)


def fade_out(
    widget: QWidget,
    then=None,
    theme: str | None = None,
    kind: str = "base",
) -> QPropertyAnimation | None:
    """Fade ``widget`` 1 → 0, hide it, then call ``then`` if given.

    ``then`` runs only if this fade is still the widget's newest one.  A
    superseded fade must not act: the case that matters is a toast that is
    replaced inside its own 160 ms fade-out — the old fade's ``hide()``
    would hide the row the new toast just showed, leaving a toast with text
    and no widget (review F-3). Dropping the stale post-condition is the
    documented policy (:data:`SUPERSEDED_POLICY`).
    """
    generation = _next_generation(widget)
    effect = _opacity_effect(widget)
    effect.setOpacity(1.0)

    def finish() -> None:
        if not _is_current(widget, generation):
            logger.debug("fade_out: superseded before completion, not hiding")
            return
        # The widget can legitimately be gone by the time this queued
        # callback runs: a soft-deleted card whose undo window closed is
        # setParent(None) + deleteLater()'d, and hide() on a dead QWidget
        # raises from inside a Qt slot (where it becomes an unhandled
        # traceback, not an exception a caller can see).
        try:
            widget.hide()
        except RuntimeError:
            logger.debug("fade_out: widget was destroyed mid-fade")
        else:
            _drop_effect(widget)
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
