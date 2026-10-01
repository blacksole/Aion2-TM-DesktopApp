"""Regression gates for the GitHub issues #11, #12 and #14 (and #13's spec).

* #11 -- Armory: the Pantheon tab was titled "Genius Insight" after every
  language switch, and a Build Planner built before the profile's language
  was applied stayed English for good.
* #12 -- Settings: the "Event Tasks" switch and the "Clear Events" button
  are gone; events cannot be created any more.
* #13 -- the Windows EXE carries version/company metadata.
* #14 -- a Flow Map's root node ("Create Character") is not a character.
"""

import re
import shutil
from pathlib import Path

import pytest

from core.translations import TRANSLATIONS
from tests.conftest import destroy_window

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PROFILE = Path(__file__).resolve().parent / "fixtures" / "reset_profile.json"


# ---------------------------------------------------------------------------
# #13 -- EXE metadata
# ---------------------------------------------------------------------------


def test_the_exe_spec_embeds_version_info():
    spec = (ROOT / "Aion2 TM.spec").read_text(encoding="utf-8")
    assert "version=_VERSION_INFO" in spec
    for field in ("CompanyName", "ProductName", "FileVersion", "ProductVersion"):
        assert field in spec, field


def test_every_project_module_the_armory_imports_is_bundled():
    """ItemDatabase/app.py is bundled as data and exec'd at runtime, so
    PyInstaller cannot see its imports.  A project module only it uses
    (core.shadows in v2.0.10) was left out and the Armory never opened
    (GitHub issue #11, point 4)."""
    app_src = (ROOT / "ItemDatabase" / "app.py").read_text(encoding="utf-8")
    needed = set()
    for pkg, names in re.findall(r"^\s*from ((?:core|utils)(?:\.\w+)?) import ([\w, ()]+)", app_src, re.M):
        if "." in pkg:
            needed.add(pkg)
        else:
            for name in re.findall(r"(\w+)(?:\s+as\s+\w+)?", names):
                if (ROOT / pkg / f"{name}.py").exists():
                    needed.add(f"{pkg}.{name}")
    spec = (ROOT / "Aion2 TM.spec").read_text(encoding="utf-8")
    block = re.search(r"hiddenimports=\[(.*?)\]", spec, re.S).group(1)
    listed = set(re.findall(r"'([\w.]+)'", block))
    assert "core.shadows" in needed
    assert needed <= listed, sorted(needed - listed)


# ---------------------------------------------------------------------------
# a real MainWindow
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def win(qapp, tmp_path_factory):
    import ui.main_window as mw

    profile_dir = tmp_path_factory.mktemp("issue_profiles")
    shutil.copy2(FIXTURE_PROFILE, profile_dir / "QaProfile.json")

    patcher = pytest.MonkeyPatch()
    patcher.setattr(mw.MainWindow, "_resolve_profile_dir", lambda self: profile_dir)
    patcher.setattr(mw.MainWindow, "_save_app_config", lambda self: None)

    window = mw.MainWindow()
    window.countdown_timer.stop()
    yield window
    destroy_window(window)
    patcher.undo()


# ---------------------------------------------------------------------------
# #12 -- no event settings left
# ---------------------------------------------------------------------------


def test_settings_offer_no_event_switch_and_no_clear_events(win):
    page = win.settings_page
    assert not hasattr(page, "show_events_btn")
    assert not hasattr(page, "clear_events_btn")
    captured = []
    page.settings_save_requested.connect(captured.append)
    try:
        page._emit_save_requested()
    finally:
        page.settings_save_requested.disconnect(captured.append)
    assert captured and "show_events" not in captured[0]


def test_a_profile_saved_with_events_hidden_shows_them_again(win):
    """With the switch gone, a stored ``show_events: false`` would hide the
    old event entries for good -- both load paths ignore it now."""
    import ui.main_window as mw

    src = Path(mw.__file__).read_text(encoding="utf-8")
    assert 'settings.get("show_events"' not in src
    assert not re.search(r'data\.get\(\s*"show_events"', src)
    assert win.show_events is True


# ---------------------------------------------------------------------------
# #14 -- the root node is not a character
# ---------------------------------------------------------------------------


def test_the_flow_map_root_is_not_a_character(win):
    from core.flow_model import FlowNode

    window = win.flow_map_window
    assert window is not None
    root = window.nodes[window.root_node_id]
    root.icon = "character"
    root.title = "Create Character"
    child = FlowNode(title="Akasha", icon="character")
    window.nodes[child.id] = child
    root.children.append(child.id)

    # An inactive map whose root is seeded the same way ("+" next to the
    # map dropdown does exactly that).
    other_root = FlowNode(title="New Node", icon="character")
    other_child = FlowNode(title="MissMonique", icon="character")
    other_root.children.append(other_child.id)
    win.flow_maps["Issue14 Other"] = {
        "nodes": {other_root.id: other_root.to_dict(), other_child.id: other_child.to_dict()},
        "root_node_id": other_root.id,
    }
    try:
        win._rebuild_characters()
        assert "Akasha" in win.characters
        assert "MissMonique" in win.characters
        assert "Create Character" not in win.characters
        assert "New Node" not in win.characters
        assert win._character_has_children("Create Character") is False
    finally:
        win.flow_maps.pop("Issue14 Other", None)
        root.children.remove(child.id)
        window.nodes.pop(child.id, None)
        win._rebuild_characters()


# ---------------------------------------------------------------------------
# website bug #133 -- the same item from two shops in one Standard set
# ---------------------------------------------------------------------------


def test_adding_a_standard_set_later_keeps_the_same_item_from_two_shops(win):
    """"Soul Crystal (Bound)" from the Nightmare Store AND the Shugo Store:
    adding the set to an existing character dropped the Shugo one."""
    char = "Issue133Twink"
    set_name = "Issue133 Twink"
    kind_before = win.active_tab
    win.active_tab = "shopping"
    shops = win.standard_templates.setdefault("shopping", {})
    shops[set_name] = [
        {"title": "Soul Crystal (Bound)", "location": "Weekly Nightmare Store",
         "schedule": "weekly", "priority": "high", "price": "50", "currency": "nightmare",
         "id": "t133-a"},
        {"title": "Soul Crystal (Bound)", "location": "Shugo Store",
         "schedule": "weekly", "priority": "high", "price": "50", "currency": "kinah",
         "id": "t133-b"},
    ]
    auto_save = win.auto_save
    win.auto_save = False
    try:
        win._apply_standard_templates_to_existing(char, set_name)
        mine = [c for c in win.task_lists.get("shopping", []) if c.character == char]
        assert sorted(c.location for c in mine) == ["Shugo Store", "Weekly Nightmare Store"]
        # Still safe to click twice: nothing is duplicated.
        win._apply_standard_templates_to_existing(char, set_name)
        mine = [c for c in win.task_lists.get("shopping", []) if c.character == char]
        assert len(mine) == 2
    finally:
        win.task_lists["shopping"] = [
            c for c in win.task_lists.get("shopping", []) if c.character != char
        ]
        shops.pop(set_name, None)
        win.auto_save = auto_save
        win.active_tab = kind_before


# ---------------------------------------------------------------------------
# #11 -- Armory titles and language
# ---------------------------------------------------------------------------


def _settle(app, ms: int = 300) -> None:
    from PySide6.QtCore import QDeadlineTimer, QEventLoop

    deadline = QDeadlineTimer(ms)
    while not deadline.hasExpired():
        app.processEvents(QEventLoop.AllEvents, 20)


@pytest.fixture(scope="module")
def armory(win, qapp, tmp_path_factory):
    """The host's own Armory window, offline, fully loaded before the tests
    and torn down while still alive -- its chunked item load
    (``QTimer.singleShot(0, _load_items_chunk)``) must not fire into a
    deleted model (same recipe as tests/test_armory_theme.py)."""
    from PySide6.QtNetwork import QNetworkAccessManager

    patcher = pytest.MonkeyPatch()

    def _no_network(self, *args, **kwargs):
        raise AssertionError("an Armory test tried to reach the network")

    patcher.setattr(QNetworkAccessManager, "get", _no_network)
    patcher.setattr(QNetworkAccessManager, "post", _no_network)
    window = win._ensure_item_database_window()
    module = win._item_database_module
    cache_root = tmp_path_factory.mktemp("issue_armory_cache")
    patcher.setattr(module, "ICON_CACHE_DIR", cache_root / "icons")
    patcher.setattr(module, "DETAIL_CACHE_DIR", cache_root / "details")
    patcher.setattr(module.IconCache, "request", lambda self, url: None)
    patcher.setattr(module.ItemDetailCache, "request", lambda self, item_id: None)
    _settle(qapp, 1500)
    yield window
    _settle(qapp, 300)
    loadout = window.get_loadout_window_if_open()
    if loadout is not None:
        destroy_window(loadout)
    destroy_window(window)
    win.item_database_window = None
    _settle(qapp, 120)
    patcher.undo()


def _tab_titles(loadout):
    return [loadout.main_tabs.tabText(i) for i in range(loadout.main_tabs.count())]


def test_every_build_planner_tab_keeps_its_own_title_after_a_language_switch(armory):
    from core.translations import tr

    loadout = armory.ensure_loadout_window()
    for lang in ("de", "ru", "en"):
        armory.update_language(lang)
        loadout = armory.get_loadout_window_if_open()
        titles = _tab_titles(loadout)
        assert len(titles) == len(set(titles)), (lang, titles)
        pantheon = getattr(loadout, "TAB_PANTHEON", None)
        if pantheon is not None:
            assert titles[pantheon] == tr(lang, "arm_pantheon_tab"), (lang, titles)


def test_a_build_planner_built_in_english_turns_german(armory, qapp):
    """The overlay can build the planner before the profile's language is
    applied; switching to German afterwards must reach every text."""
    from PySide6.QtWidgets import QLabel

    de = TRANSLATIONS["de"]
    armory.update_language("en")
    loadout = armory.ensure_loadout_window()
    state_before = loadout.get_persistable_state()
    armory.update_language("de")
    qapp.processEvents()
    loadout = armory.get_loadout_window_if_open()

    labels = {w.text() for w in loadout.findChildren(QLabel)}
    for key in ("arm_pantheon_hint", "arm_pantheon_lord_points_title",
                "arm_pantheon_inventory_title", "arm_genius_owned_effects_title"):
        assert de[key] in labels, key
    for key in ("arm_pantheon_hint", "arm_pantheon_lord_points_title"):
        assert TRANSLATIONS["en"][key] not in labels, key
    assert loadout.get_persistable_state() == state_before
    armory.update_language("en")


# Proper nouns of the game stay English on purpose (no official German
# client); every other Armory chrome key needs a real German value.
_GAME_TERMS = re.compile(
    r"Arcana|Pantheon|Genius|Daevanion|Kinah|PvP|PvE|Cogni|Fera|Natura|Varian|"
    r"Build [AB]|GearScore|VS|ID|Name|Rune|Ring|Set|Shop|Details|Material|Support|"
    r"\{\w+\}[: +/]*\{?\w*\}?$|^PVP / PVE$|^Guard$"
)


def test_no_armory_chrome_key_is_left_english_in_german():
    en, de = TRANSLATIONS["en"], TRANSLATIONS["de"]
    left = sorted(
        k for k in en
        if k.startswith("arm_") and de.get(k) == en[k]
        and any(c.isalpha() for c in en[k]) and not _GAME_TERMS.search(en[k])
    )
    assert left == [], left
