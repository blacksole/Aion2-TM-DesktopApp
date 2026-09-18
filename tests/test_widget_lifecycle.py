"""A MainWindow that is torn down must actually go away.

Not a style point: the stylesheet lives on the **QApplication** (MASTER
§4-1), so every ``setStyleSheet`` / ``setPalette`` re-resolves against every
live widget in the *process*, whoever created it.  A window that survives its
own teardown therefore taxes every later theme switch in every later test
module — measured, before this file existed: ~5 900 widgets alive by the end
of the suite, one theme switch at 9 s instead of 0.2 s, and a suite at 349 s
(review F-apex, "Re-verification 2").

Two independent causes, both pinned below:

  1. ``MainWindow._wire_card`` stored ``card.mousePressEvent = on_press`` — a
     closure capturing the card *and* the window, in the card's own instance
     dict.  That is a reference cycle whose root is a live Qt object, so
     ``deleteLater()`` could free the C++ widget while the Python wrapper (and
     through it the window, and every other card) stayed reachable.  It is an
     event filter owned by the window now, capturing neither.
  2. ``tests/conftest.py``'s ``destroy_window`` pumped the DeferredDelete
     queue once.  One pass frees the C++ trees; what is left is Python, and
     until the collector runs those wrappers hold their children.  It
     collects between two passes now.

The behaviour the new wiring has to keep is pinned in tests/test_soft_delete.py
("How the card is wired to all of the above").

The window is handed out by a *builder*, not as a fixture value: a fixture
value stays in pytest's cache for the whole test, and a MainWindow that is
still named keeps the cards in ``task_lists`` alive by design (a card on an
inactive tab has no Qt parent — the list is its only owner).  Holding the
only reference is what lets these tests ask the real question.
"""

import gc
import shutil
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from tests.conftest import destroy_window, live_widget_count

FIXTURE_PROFILE = Path(__file__).resolve().parent / "fixtures" / "reset_profile.json"

#: What a torn-down MainWindow may leave behind.  A window is ~650 widgets,
#: so this separates "released" from "still there" by two orders of
#: magnitude; it is not a fitted number.
MAX_SURVIVORS = 100


@pytest.fixture
def build_window(qapp, tmp_path_factory):
    """Returns a callable that builds one offscreen MainWindow per call."""
    import ui.main_window as mw

    profile_dir = tmp_path_factory.mktemp("lifecycle")
    shutil.copy2(FIXTURE_PROFILE, profile_dir / "QaProfile.json")

    patcher = pytest.MonkeyPatch()
    patcher.setattr(mw.MainWindow, "_resolve_profile_dir", lambda self: profile_dir)
    patcher.setattr(mw.MainWindow, "_save_app_config", lambda self: None)

    def build():
        window = mw.MainWindow()
        window.countdown_timer.stop()
        return window

    yield build
    patcher.undo()


def test_destroying_a_window_releases_its_widget_tree(build_window):
    gc.collect()
    empty = live_widget_count()

    window = build_window()
    built = live_widget_count()
    assert built - empty > 300, (
        f"a MainWindow only added {built - empty} widgets — the fixture "
        f"profile is probably not being loaded, so this test would prove "
        f"nothing about releasing a real tree"
    )

    destroy_window(window)
    del window
    gc.collect()

    after = live_widget_count()
    assert after - empty < MAX_SURVIVORS, (
        f"{after - empty} of {built - empty} widgets survived "
        f"destroy_window() — every later app-wide restyle pays for them"
    )


def test_neither_the_window_nor_a_card_outlives_its_teardown(build_window):
    """The cycle itself, by type rather than by count.

    Asked through ``QApplication.allWidgets()``, which is both the honest
    question and the expensive one: it is exactly the list a
    ``setStyleSheet`` on the application re-resolves against.
    """
    window = build_window()
    cards = [card for tab in window.task_lists.values() for card in tab]
    assert cards, "the fixture profile rendered no cards at all"
    kinds = {type(card).__name__ for card in cards}
    assert "TaskCard" in kinds, f"no task card in the fixture profile: {kinds}"

    destroy_window(window)
    del window, cards
    gc.collect()

    names = [type(widget).__name__ for widget in QApplication.allWidgets()]
    assert "MainWindow" not in names, "the MainWindow outlived destroy_window()"
    for kind in sorted(kinds):
        assert kind not in names, f"a {kind} outlived its window"


def test_one_event_filter_serves_every_card(build_window):
    """The shape of the fix, so it cannot regress into a per-card object.

    ``_wire_card`` used to give every card its own closure; the replacement
    is a single filter, parented to the window (a Qt parent, so no Python
    reference in either direction) and installed on all of them.  One filter
    per card would be cheaper than a closure and still wrong: N objects
    whose lifetime is the window's.
    """
    window = build_window()
    try:
        cards = [card for tab in window.task_lists.values() for card in tab]
        assert len(cards) > 1, "need at least two cards to tell one filter from N"

        filter_object = window._card_press_filter
        assert filter_object is not None, "no card was wired at all"
        assert filter_object.parent() is window, (
            "the filter is not owned by the window — nothing would free it"
        )
        assert sum(
            1 for child in window.children() if type(child) is type(filter_object)
        ) == 1, "more than one card-press filter per window"

        for card in cards:
            assert "mousePressEvent" not in vars(card), (
                f"{card.title!r} carries a per-instance mousePressEvent again"
            )
    finally:
        destroy_window(window)
