"""The "Sync" button on Standard Templates, once a set has been renamed.

User-Wunsch 2026-09-10 built Sync as "add what the Default profile has and
you don't".  The named-set migration (2026-09-23) then made it match the
selected set against the **identically named** set in the Default profile --
and ``profiles/Default*.json`` ship the flat legacy list, so after migration
Default holds exactly ONE set, ``LEGACY_STANDARD_SET_NAME``.  Rename your set
to "Daily Grind" and Sync returned ``[]`` forever: count 0, button
permanently disabled, no message (Apex review of PR #7, finding 6).  No test
covered it, which is why it shipped.

The rule now: same name wins; failing that, Default's SOLE set (there is no
ambiguity about what "the standard templates" are when there is only one);
and a real ambiguity says so on the tooltip instead of going quiet.
"""
from __future__ import annotations

import gc
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from core.translations import tr  # noqa: E402
from ui.widgets.template_dialog import TemplateDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _entry(title: str) -> dict:
    return {"id": title.lower(), "title": title, "location": "", "price": ""}


DEFAULT_ONE_SET = {"tasks": {"Default": [_entry("Coin Quest"), _entry("Fortress")]}, "shopping": {}}


def _dialog(qapp, standard_templates, default_standard_templates):
    dlg = TemplateDialog(
        templates=[],
        flow_maps={},
        task_templates=[],
        initial_tab="tasks",
        language="en",
        tr_func=tr,
        standard_templates=standard_templates,
        default_standard_templates=default_standard_templates,
    )
    return dlg


def _drop(qapp, dlg):
    from PySide6.QtCore import QEvent

    dlg.deleteLater()
    for _ in range(2):
        qapp.sendPostedEvents(None, QEvent.DeferredDelete)
        qapp.processEvents()
        gc.collect()


def test_a_renamed_set_still_syncs_against_defaults_only_set(qapp):
    """The exact regression: the user's set is called anything but
    "Default", and Default has exactly one set."""
    dlg = _dialog(qapp, {"tasks": {"Daily Grind": [_entry("Coin Quest")]}, "shopping": {}}, DEFAULT_ONE_SET)
    try:
        assert dlg._task_std_set == "Daily Grind"
        new = dlg._default_new_entries("tasks")
        assert [t["title"] for t in new] == ["Fortress"]

        dlg._update_task_sync_btn()
        assert dlg._task_sync_btn.isEnabled()
        assert dlg._task_sync_btn.text().endswith("(1)")
    finally:
        _drop(qapp, dlg)


def test_a_same_named_set_still_wins_over_the_sole_set_fallback(qapp):
    """The fallback must not override an exact match."""
    default = {
        "tasks": {"Default": [_entry("Coin Quest")], "Weekly": [_entry("Fortress")]},
        "shopping": {},
    }
    dlg = _dialog(qapp, {"tasks": {"Weekly": []}, "shopping": {}}, default)
    try:
        assert [t["title"] for t in dlg._default_new_entries("tasks")] == ["Fortress"]
    finally:
        _drop(qapp, dlg)


def test_a_real_ambiguity_disables_sync_and_says_why(qapp):
    """Default grew a second set and none matches by name -- there is no
    honest target, so the button stays off WITH a reason on it."""
    default = {
        "tasks": {"Default": [_entry("Coin Quest")], "Weekly": [_entry("Fortress")]},
        "shopping": {},
    }
    dlg = _dialog(qapp, {"tasks": {"Daily Grind": []}, "shopping": {}}, default)
    try:
        assert dlg._default_new_entries("tasks") == []
        dlg._update_task_sync_btn()
        assert not dlg._task_sync_btn.isEnabled()
        assert dlg._task_sync_btn.toolTip() == tr("en", "standards_sync_hint_ambiguous")
        assert dlg._task_sync_btn.toolTip() != "standards_sync_hint_ambiguous"
    finally:
        _drop(qapp, dlg)


def test_nothing_to_sync_is_not_the_same_message_as_nothing_to_sync_against(qapp):
    """"You already have everything" and "there is nothing to compare with"
    are different states; both used to render as the same dead button."""
    up_to_date = _dialog(
        qapp,
        {"tasks": {"Default": [_entry("Coin Quest"), _entry("Fortress")]}, "shopping": {}},
        DEFAULT_ONE_SET,
    )
    try:
        up_to_date._update_task_sync_btn()
        assert not up_to_date._task_sync_btn.isEnabled()
        assert up_to_date._task_sync_btn.toolTip() == tr("en", "standards_sync_hint_up_to_date")
    finally:
        _drop(qapp, up_to_date)

    empty_default = _dialog(
        qapp, {"tasks": {"Daily Grind": []}, "shopping": {}}, {"tasks": {}, "shopping": {}}
    )
    try:
        empty_default._update_task_sync_btn()
        assert not empty_default._task_sync_btn.isEnabled()
        assert empty_default._task_sync_btn.toolTip() == tr("en", "standards_sync_hint_no_default")
    finally:
        _drop(qapp, empty_default)


@pytest.mark.parametrize(
    "key",
    [
        "standards_sync_hint_no_set",
        "standards_sync_hint_no_default",
        "standards_sync_hint_ambiguous",
        "standards_sync_hint_up_to_date",
    ],
)
@pytest.mark.parametrize("language", ["de", "ru", "en"])
def test_every_hint_exists_in_every_language(language, key):
    from core.translations import TRANSLATIONS

    assert key in TRANSLATIONS[language], f"{key} missing from {language}"
    assert TRANSLATIONS[language][key].strip()
