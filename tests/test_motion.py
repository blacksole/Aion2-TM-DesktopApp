"""ui/motion.py — durations come from tokens, and reduced motion means 0."""

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget

from core.theme import ABYSS
from ui import motion


@pytest.fixture(scope="module")
def app():
    yield QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _motion_on():
    """Every test starts from motion enabled, whatever the previous one did."""
    motion.set_reduced_motion(False)
    yield
    motion.set_reduced_motion(False)


def test_durations_come_from_the_tokens():
    assert motion.duration("fast") == ABYSS.motion_fast == 120
    assert motion.duration("base") == ABYSS.motion_base == 160
    assert motion.duration("slow") == ABYSS.motion_slow == 220


def test_unknown_duration_kind_raises():
    with pytest.raises(KeyError):
        motion.duration("glacial")


def test_reduced_motion_zeroes_every_duration():
    motion.set_reduced_motion(True)
    assert motion.reduced_motion() is True
    assert [motion.duration(kind) for kind in ("fast", "base", "slow")] == [0, 0, 0]


def test_reduced_motion_is_reversible():
    motion.set_reduced_motion(True)
    motion.set_reduced_motion(False)
    assert motion.reduced_motion() is False
    assert motion.duration("base") == ABYSS.motion_base


def test_fade_in_animates_and_ends_visible(app):
    widget = QLabel("x")
    animation = motion.fade_in(widget)
    assert animation is not None
    assert animation.duration() == ABYSS.motion_base
    assert isinstance(widget.graphicsEffect(), QGraphicsOpacityEffect)
    assert animation.endValue() == 1.0


def test_fade_in_reduced_motion_applies_the_end_state_instantly(app):
    motion.set_reduced_motion(True)
    widget = QLabel("x")
    assert motion.fade_in(widget) is None
    assert not widget.isHidden()
    # The effect is uninstalled the moment the fade is over -- instantly,
    # here -- because an installed QGraphicsOpacityEffect makes Qt re-render
    # the widget through an offscreen buffer on every later repaint. Fully
    # opaque and no effect is the same thing on screen, and cheaper.
    assert widget.graphicsEffect() is None


def test_fade_out_reduced_motion_hides_and_calls_back(app):
    motion.set_reduced_motion(True)
    widget = QLabel("x")
    widget.show()
    calls = []
    assert motion.fade_out(widget, then=lambda: calls.append(1)) is None
    assert widget.isHidden()
    assert widget.graphicsEffect() is None
    assert calls == [1]


def test_fade_out_animates_when_motion_is_on(app):
    widget = QLabel("x")
    widget.show()
    animation = motion.fade_out(widget)
    assert animation is not None
    assert animation.startValue() == 1.0 and animation.endValue() == 0.0


def test_slide_hint_moves_a_floating_widget_only(app):
    floating = QWidget()
    floating.move(QPoint(40, 40))
    animation = motion.slide_hint(floating)
    assert animation is not None
    assert animation.duration() == ABYSS.motion_fast
    assert animation.endValue() == QPoint(40, 40)
    assert animation.startValue() == QPoint(40, 40 + ABYSS.motion_offset)


def test_slide_hint_refuses_layout_managed_widgets(app):
    """MASTER: never animate the geometry a layout owns."""
    parent = QWidget()
    layout = QVBoxLayout(parent)
    child = QLabel("x")
    layout.addWidget(child)
    assert motion.slide_hint(child) is None


def test_slide_hint_direction_is_validated(app):
    floating = QWidget()
    with pytest.raises(ValueError):
        motion.slide_hint(floating, direction="sideways")


@pytest.mark.parametrize("direction", ["up", "down", "left", "right"])
def test_slide_hint_offsets_by_the_motion_token(app, direction):
    floating = QWidget()
    floating.move(QPoint(100, 100))
    animation = motion.slide_hint(floating, direction=direction)
    start = animation.startValue()
    delta = max(abs(start.x() - 100), abs(start.y() - 100))
    assert delta == ABYSS.motion_offset


def test_fade_in_reuses_an_existing_opacity_effect(app):
    widget = QLabel("x")
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    motion.fade_in(widget)
    assert widget.graphicsEffect() is effect


def test_the_opacity_effect_does_not_outlive_the_fade(app):
    """A QGraphicsOpacityEffect left installed taxes every later repaint of
    the widget's whole subtree, forever.  Both fades must clean up."""
    widget = QLabel("x")

    animation = motion.fade_in(widget)
    assert animation is not None
    assert isinstance(widget.graphicsEffect(), QGraphicsOpacityEffect), "no effect mid-fade"
    _drain_until(app, lambda: widget.graphicsEffect() is None)

    widget.show()
    animation = motion.fade_out(widget)
    assert animation is not None
    _drain_until(app, lambda: widget.graphicsEffect() is None)
    assert widget.isHidden()


def _drain_until(app, predicate, timeout_ms: int = 2000):
    from PySide6.QtCore import QDeadlineTimer, QEventLoop

    deadline = QDeadlineTimer(timeout_ms)
    while not predicate() and not deadline.hasExpired():
        app.processEvents(QEventLoop.AllEvents, 20)
    assert predicate(), f"condition never held within {timeout_ms} ms"
