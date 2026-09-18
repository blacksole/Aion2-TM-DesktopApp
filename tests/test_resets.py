"""Characterization tests for MainWindow.check_auto_resets (daily / weekly /
season) and the _profile_loading save guard.

These pin CURRENT behaviour ahead of the planned refactor -- they are a
regression net, not a specification. Everything asserted here was read off
the running code, not off the docs.

Seams these tests depend on (KEEP THEM STABLE, or update this file with the
refactor):
  * ``ui.main_window.datetime``      -- module-level ``from datetime import
    datetime``; ``check_auto_resets`` calls ``datetime.now()`` through it.
    That module attribute is the ONLY clock seam; a refactor that switches
    to ``QDateTime.currentDateTime()`` or an injected clock must re-point
    ``_frozen_clock`` below.
  * ``MainWindow._resolve_profile_dir`` -- patched to a tmp dir so no test
    ever touches the repo's ``profiles/`` (incl. ``last_profile.txt``).
  * ``MainWindow._save_app_config``  -- patched to a no-op so the repo's
    tracked ``config.json`` is never rewritten.
  * ``core.persistence.atomic_write_json`` -- imported *inside*
    ``save_profile`` (late binding), so patching the module attribute
    intercepts every profile write. Used to count writes.
  * Reset state lives in plain MainWindow attributes: ``daily_reset_time``,
    ``weekly_reset_day``, ``weekly_reset_time``, ``season_enabled``,
    ``season_reset_datetime``, ``last_daily_reset_date``,
    ``last_weekly_reset_date``, ``last_season_reset_datetime``.
"""

import shutil
from datetime import date, datetime
from pathlib import Path

import pytest

from tests.conftest import destroy_window

FIXTURE_PROFILE = Path(__file__).resolve().parent / "fixtures" / "reset_profile.json"

# A Wednesday. Weekly boundary for "Mo" 09:00 is then 2026-09-14 09:00.
WEDNESDAY_NOON = datetime(2026, 9, 16, 12, 0)
MONDAY_BOUNDARY = date(2026, 9, 14)


def _frozen_clock(now: datetime):
    """A drop-in for ``ui.main_window.datetime`` whose ``now()`` is fixed."""

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: D102 - mirrors datetime.now
            return now

        @classmethod
        def today(cls):  # noqa: D102 - mirrors datetime.today
            return now

    return _FrozenDateTime


def _completed_by_schedule(win) -> dict:
    """{(list_name, schedule): completed} for every card in the window."""
    return {
        (list_name, card.schedule): card.completed
        for list_name, cards in win.task_lists.items()
        for card in cards
    }


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def main_window(qapp, tmp_path_factory):
    """One real, offscreen MainWindow on a throwaway profile directory.

    Module-scoped because a full construction costs ~0.8 s; every test
    re-seeds the handful of attributes check_auto_resets actually reads.
    """
    import ui.main_window as mw

    profile_dir = tmp_path_factory.mktemp("qa_profiles")
    shutil.copy2(FIXTURE_PROFILE, profile_dir / "QaProfile.json")

    patcher = pytest.MonkeyPatch()
    # Never let the app resolve the repo's own profiles/ directory.
    patcher.setattr(mw.MainWindow, "_resolve_profile_dir", lambda self: profile_dir)
    # Never rewrite the repo's tracked config.json.
    patcher.setattr(mw.MainWindow, "_save_app_config", lambda self: None)

    win = mw.MainWindow()
    # The 1 s countdown timer would call update_countdowns -> check_auto_resets
    # behind the tests' back if anything ever pumped the event loop.
    win.countdown_timer.stop()

    assert win.profile_name == "QaProfile", "fixture profile was not the one loaded"
    assert win.profile_dir == profile_dir

    yield win

    destroy_window(win)
    patcher.undo()


@pytest.fixture
def win(main_window):
    """Reset-relevant state re-seeded to a known baseline, all cards done."""
    w = main_window
    w._profile_loading = False
    w.auto_save = True
    w.daily_reset_time = "09:00"
    w.weekly_reset_day = "Mo"
    w.weekly_reset_time = "09:00"
    w.season_enabled = False
    w.season_reset_datetime = ""
    w.last_daily_reset_date = WEDNESDAY_NOON.date()
    w.last_weekly_reset_date = MONDAY_BOUNDARY
    w.last_season_reset_datetime = None
    w.missed_daily_activities = []
    for cards in w.task_lists.values():
        for card in cards:
            card.set_completed(True)
    return w


@pytest.fixture
def writes(monkeypatch):
    """Counts (and suppresses) every profile write save_profile would make."""
    import core.persistence as persistence

    recorded: list[Path] = []

    def _spy(path, data, **kwargs):
        recorded.append(Path(path))

    monkeypatch.setattr(persistence, "atomic_write_json", _spy)
    return recorded


@pytest.fixture
def at():
    """``at(datetime)`` freezes ui.main_window's clock for the test."""
    patcher = pytest.MonkeyPatch()

    def _freeze(now: datetime):
        import ui.main_window as mw

        patcher.setattr(mw, "datetime", _frozen_clock(now))
        return now

    yield _freeze
    patcher.undo()


# ---------------------------------------------------------------------------
# nothing due
# ---------------------------------------------------------------------------

def test_no_reset_due_changes_nothing_and_saves_nothing(win, writes, at):
    at(WEDNESDAY_NOON)
    before = _completed_by_schedule(win)

    win.check_auto_resets()

    assert _completed_by_schedule(win) == before
    assert all(before.values()), "baseline should have every card completed"
    assert win.last_daily_reset_date == WEDNESDAY_NOON.date()
    assert win.last_weekly_reset_date == MONDAY_BOUNDARY
    assert win.last_season_reset_datetime is None
    assert writes == []


# ---------------------------------------------------------------------------
# daily
# ---------------------------------------------------------------------------

def test_daily_due_unchecks_only_daily_entries_and_stamps_the_date(win, writes, at):
    at(WEDNESDAY_NOON)
    win.last_daily_reset_date = date(2026, 9, 15)

    win.check_auto_resets()

    state = _completed_by_schedule(win)
    assert state[("tasks", "daily")] is False
    assert state[("shopping", "daily")] is False
    # Weekly and season are untouched by a daily reset.
    assert state[("tasks", "weekly")] is True
    assert state[("shopping", "weekly")] is True
    assert state[("tasks", "season")] is True
    assert state[("shopping", "season")] is True

    assert win.last_daily_reset_date == WEDNESDAY_NOON.date()
    assert win.last_weekly_reset_date == MONDAY_BOUNDARY, "weekly marker must not move"
    assert len(writes) == 1, "a due daily reset persists itself exactly once"


def test_daily_not_due_before_todays_reset_time(win, writes, at):
    at(datetime(2026, 9, 16, 8, 0))  # 08:00, reset time is 09:00
    win.last_daily_reset_date = date(2026, 9, 15)

    win.check_auto_resets()

    state = _completed_by_schedule(win)
    assert state[("tasks", "daily")] is True
    assert win.last_daily_reset_date == date(2026, 9, 15), "marker stays on yesterday"
    assert writes == []


def test_daily_reset_records_the_still_open_daily_entries_as_missed(win, writes, at):
    at(WEDNESDAY_NOON)
    win.last_daily_reset_date = date(2026, 9, 15)
    for cards in win.task_lists.values():
        for card in cards:
            if card.schedule == "daily":
                card.set_completed(False)

    win.check_auto_resets()

    missed_ids = {entry["card_id"] for entry in win.missed_daily_activities}
    assert missed_ids == {"qa-task-daily", "qa-shop-daily"}
    assert all(entry["character"] == "QA Char" for entry in win.missed_daily_activities)


def test_daily_reset_time_is_read_from_the_configured_hhmm(win, writes, at):
    at(datetime(2026, 9, 16, 5, 30))
    win.daily_reset_time = "05:00"
    win.last_daily_reset_date = date(2026, 9, 15)

    win.check_auto_resets()

    assert win.last_daily_reset_date == WEDNESDAY_NOON.date()
    assert _completed_by_schedule(win)[("tasks", "daily")] is False


# ---------------------------------------------------------------------------
# weekly
# ---------------------------------------------------------------------------

def test_weekly_due_unchecks_only_weekly_entries(win, writes, at):
    at(WEDNESDAY_NOON)
    win.last_weekly_reset_date = date(2026, 9, 7)  # the previous Monday

    win.check_auto_resets()

    state = _completed_by_schedule(win)
    assert state[("tasks", "weekly")] is False
    assert state[("shopping", "weekly")] is False
    assert state[("tasks", "daily")] is True
    assert state[("shopping", "daily")] is True
    assert state[("tasks", "season")] is True

    # The marker is the LAST PASSED boundary, not "today".
    assert win.last_weekly_reset_date == MONDAY_BOUNDARY
    assert len(writes) == 1


def test_weekly_boundary_is_the_last_passed_configured_weekday(win, writes, at):
    at(datetime(2026, 9, 18, 12, 0))  # a Friday
    win.weekly_reset_day = "Do"  # Thursday
    win.last_weekly_reset_date = date(2026, 9, 1)

    win.check_auto_resets()

    assert win.last_weekly_reset_date == date(2026, 9, 17)


def test_german_and_english_weekday_keys_are_equivalent(win, writes, at):
    at(datetime(2026, 9, 18, 12, 0))
    win.weekly_reset_day = "Do"
    win.last_weekly_reset_date = date(2026, 9, 1)
    win.check_auto_resets()
    german_marker = win.last_weekly_reset_date

    win.weekly_reset_day = "Thu"
    win.last_weekly_reset_date = date(2026, 9, 1)
    win.check_auto_resets()

    assert win.last_weekly_reset_date == german_marker == date(2026, 9, 17)


def test_unknown_weekday_key_falls_back_to_monday(win, writes, at):
    at(WEDNESDAY_NOON)
    win.weekly_reset_day = "Sonntag"  # in neither half of day_map
    win.last_weekly_reset_date = date(2026, 9, 7)

    win.check_auto_resets()

    assert win.last_weekly_reset_date == MONDAY_BOUNDARY


def test_weekly_fires_once_when_the_marker_is_missing(win, writes, at):
    at(WEDNESDAY_NOON)
    win.last_weekly_reset_date = None

    win.check_auto_resets()

    assert _completed_by_schedule(win)[("tasks", "weekly")] is False
    assert win.last_weekly_reset_date == MONDAY_BOUNDARY


# ---------------------------------------------------------------------------
# season (2.0.7)
# ---------------------------------------------------------------------------

def test_season_past_end_datetime_resets_only_season_entries(win, writes, at):
    at(WEDNESDAY_NOON)
    win.season_enabled = True
    win.season_reset_datetime = "2026-09-01 09:00"

    win.check_auto_resets()

    state = _completed_by_schedule(win)
    assert state[("tasks", "season")] is False
    assert state[("shopping", "season")] is False
    assert state[("tasks", "daily")] is True
    assert state[("tasks", "weekly")] is True

    assert win.last_season_reset_datetime == "2026-09-01 09:00"
    assert len(writes) == 1


def test_season_does_not_fire_twice_for_the_same_end_datetime(win, writes, at):
    at(WEDNESDAY_NOON)
    win.season_enabled = True
    win.season_reset_datetime = "2026-09-01 09:00"
    win.last_season_reset_datetime = "2026-09-01 09:00"

    win.check_auto_resets()

    assert _completed_by_schedule(win)[("tasks", "season")] is True
    assert writes == []


def test_setting_a_new_season_end_lets_the_reset_fire_again(win, writes, at):
    at(WEDNESDAY_NOON)
    win.season_enabled = True
    win.last_season_reset_datetime = "2026-09-01 09:00"
    win.season_reset_datetime = "2026-09-10 09:00"

    win.check_auto_resets()

    assert _completed_by_schedule(win)[("tasks", "season")] is False
    assert win.last_season_reset_datetime == "2026-09-10 09:00"


def test_season_disabled_never_resets_even_when_the_date_has_passed(win, writes, at):
    at(WEDNESDAY_NOON)
    win.season_enabled = False
    win.season_reset_datetime = "2026-09-01 09:00"

    win.check_auto_resets()

    assert _completed_by_schedule(win)[("tasks", "season")] is True
    assert win.last_season_reset_datetime is None
    assert writes == []


def test_future_season_end_datetime_does_not_reset(win, writes, at):
    at(WEDNESDAY_NOON)
    win.season_enabled = True
    win.season_reset_datetime = "2026-11-04 09:00"

    win.check_auto_resets()

    assert _completed_by_schedule(win)[("tasks", "season")] is True
    assert win.last_season_reset_datetime is None


def test_malformed_season_end_datetime_is_ignored_without_raising(win, writes, at):
    at(WEDNESDAY_NOON)
    win.season_enabled = True
    win.season_reset_datetime = "not-a-datetime"

    win.check_auto_resets()  # must not raise

    assert _completed_by_schedule(win)[("tasks", "season")] is True
    assert win.last_season_reset_datetime is None


# ---------------------------------------------------------------------------
# the 7cab132 load guard
# ---------------------------------------------------------------------------

def test_reset_during_load_resets_state_but_writes_nothing(win, writes, at):
    """The structural half of the 2.0.5 data-loss fix.

    While ``_profile_loading`` is True a due reset still mutates in-memory
    state -- only the *write* is suppressed, so half-restored fields can
    never be serialized over the real profile on disk.
    """
    at(WEDNESDAY_NOON)
    win.last_daily_reset_date = date(2026, 9, 15)
    win._profile_loading = True

    win.check_auto_resets()

    assert _completed_by_schedule(win)[("tasks", "daily")] is False
    assert win.last_daily_reset_date == WEDNESDAY_NOON.date()
    assert writes == [], "no profile write may happen while a load is in flight"


def test_explicit_save_is_the_way_out_of_the_load_guard(win, writes):
    win._profile_loading = True

    win.save_profile(silent=True)
    assert writes == []

    win.save_profile(explicit=True)
    assert len(writes) == 1
    assert writes[0].name == "QaProfile.json"
