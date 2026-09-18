"""Characterization tests for the Build Planner persistence round-trip:
``LoadoutWindow.get_persistable_state`` <-> ``apply_persisted_state``, reached
through the host seam ``ItemDatabaseWindow.set_pending_loadout_state`` /
``get_loadout_state``.

Audit B-armory.md 1 flags this as MED risk: serialization is explicit-key, so
a key added to the build state but not to ``get_persistable_state`` is
silently dropped on the next save/load round-trip. These tests pin the CURRENT
key set and the round-trip fidelity of each key so the planned schema-driven
rewrite cannot quietly lose one.

Seams these tests depend on (KEEP THEM STABLE):
  * The module is loaded exactly like the host does it --
    ``importlib.util.spec_from_file_location("item_database_app",
    ItemDatabase/app.py)`` (see ``MainWindow._ensure_item_database_window``).
    A QApplication must exist first: importing app.py installs a global
    ``QComboBox.showPopup`` monkey-patch and builds Qt objects.
  * ``<module>.ICON_CACHE_DIR`` / ``<module>.DETAIL_CACHE_DIR`` -- rebound to
    a tmp dir BEFORE ``create_window`` so no cache directory is created under
    ItemDatabase/ (``ItemDetailCache.__init__`` mkdir's its cache dir).
  * ``IconCache.request`` / ``ItemDetailCache.request`` -- stubbed to record
    instead of hitting the wire. Building a LoadoutWindow on a cold cache
    really does fire icon GETs (synthetic Rune slot placeholders).
  * ``QNetworkAccessManager.get`` / ``.post`` -- replaced by a sentinel that
    raises, so any *other* code path reaching the network fails the test.
  * ``ItemDatabase/data`` is absent in this clone; the module degrades via its
    documented ``arm_no_cached_data`` path and the Build Planner still builds.
"""

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_PY = ROOT / "ItemDatabase" / "app.py"

# Every key get_persistable_state actually returns today. The audit lists 15
# of these; `current_genius_build_name` and `pantheon_slots` are in the code
# but missing from the audit table -- the code is the source of truth here.
EXPECTED_STATE_KEYS = {
    "character_class",
    "character_race",
    "current_build_name",
    "active_gear_types",
    "stat_priority_profiles",
    "monolith_level",
    "skill_levels",
    "skill_arcana_wish",
    "skill_active_specs",
    "current_skill_build_name",
    "skill_builds_data",
    "equip_builds_data",
    "daevanion_active",
    "daevanion_filter_checked",
    "genius_builds_data",
    "current_genius_build_name",
    "pantheon_slots",
}

QA_ITEM = {
    "id": 900123,
    "name": "QA Blade",
    "grade": "Unique",
    "categoryName": "Weapon",
    "image": "",
}


@pytest.fixture(scope="session")
def armory_module(qapp, tmp_path_factory):
    """ItemDatabase/app.py loaded the way the host loads it, fully offline."""
    from PySide6.QtNetwork import QNetworkAccessManager

    patcher = pytest.MonkeyPatch()

    def _no_network(self, *args, **kwargs):
        raise AssertionError("an Armory test tried to reach the network")

    patcher.setattr(QNetworkAccessManager, "get", _no_network)
    patcher.setattr(QNetworkAccessManager, "post", _no_network)

    module = sys.modules.get("item_database_app")
    if module is None:
        spec = importlib.util.spec_from_file_location("item_database_app", APP_PY)
        module = importlib.util.module_from_spec(spec)
        sys.modules["item_database_app"] = module
        spec.loader.exec_module(module)

    cache_root = tmp_path_factory.mktemp("armory_cache")
    patcher.setattr(module, "ICON_CACHE_DIR", cache_root / "icons")
    patcher.setattr(module, "DETAIL_CACHE_DIR", cache_root / "details")

    module._qa_icon_requests = []
    module._qa_detail_requests = []
    patcher.setattr(
        module.IconCache, "request",
        lambda self, url: module._qa_icon_requests.append(url),
    )
    patcher.setattr(
        module.ItemDetailCache, "request",
        lambda self, item_id: module._qa_detail_requests.append(item_id),
    )

    yield module

    patcher.undo()


@pytest.fixture(scope="module")
def armory_window(armory_module):
    """The ItemDatabaseWindow -- the object MainWindow actually holds."""
    window = armory_module.create_window(parent=None, language="en")
    yield window
    window.close()


@pytest.fixture(scope="module")
def loadout(armory_window):
    """The real LoadoutWindow, built through the host's own entry point."""
    loadout_window = armory_window.ensure_loadout_window()
    yield loadout_window
    loadout_window.close()


@pytest.fixture(scope="module")
def default_state(loadout):
    return copy.deepcopy(loadout.get_persistable_state())


@pytest.fixture(scope="module")
def dummy_state(armory_module, default_state):
    """A state dict with a distinctive value under every single key."""
    slots = list(default_state["equip_builds_data"]["gladiator"]["Default"]["priority"])

    genius = copy.deepcopy(armory_module._genius_default_state())
    genius["Cogni"]["1"] = {"stat": "AttackBonus", "value": 99, "locked": True}

    priorities = copy.deepcopy(default_state["stat_priority_profiles"])
    priorities["PvE"]["Angreifer"]["weapon"] = ["QA Only Stat"]

    return {
        "character_class": "Ranger",
        "character_race": "Asmodae",
        "current_build_name": "QA Equip Build",
        "active_gear_types": ["PvP"],
        "stat_priority_profiles": priorities,
        "monolith_level": 7,
        "skill_levels": {"90001": 4},
        "skill_arcana_wish": {"90001": 2},
        "skill_active_specs": {"90001": [11, 22]},
        "current_skill_build_name": "QA Skill Build",
        "skill_builds_data": {
            "ranger": {
                "QA Skill Build": {
                    "priority": {
                        "active": ["90001"],
                        "passive": ["90002"],
                        "stigma": ["90003"],
                    },
                    "arcana_cards": {
                        "Key": {
                            "grade": "Unique",
                            "slots": [{"skill_id": "90001", "level": 3}, None, None, None],
                        }
                    },
                }
            }
        },
        "equip_builds_data": {
            "ranger": {
                "QA Equip Build": {
                    "equipped": {"weapon": copy.deepcopy(QA_ITEM)},
                    "substats": {"weapon": [0, 2]},
                    "enchant": {"weapon": 12},
                    "philosopher_stone": {"weapon": {"stat": "Attack", "value": 5}},
                    "priority": {slot: [None] for slot in slots}
                    | {"weapon": [copy.deepcopy(QA_ITEM), None]},
                    "priority_progress": {"weapon": 1},
                    "linked_skill_build": "QA Skill Build",
                    "linked_genius_build": "QA Genius",
                }
            }
        },
        "daevanion_active": {"s:qa-board": [1, 2, 3]},
        "daevanion_filter_checked": {"s:ranger": ["Attack"]},
        "genius_builds_data": {"QA Genius": genius},
        "current_genius_build_name": "QA Genius",
        "pantheon_slots": {
            slot: (900999 if slot == "Artwork1" else "")
            for slot in default_state["pantheon_slots"]
        },
    }


@pytest.fixture(scope="module")
def round_tripped(loadout, dummy_state):
    """apply_persisted_state(dummy) -> get_persistable_state()."""
    loadout.apply_persisted_state(copy.deepcopy(dummy_state))
    return copy.deepcopy(loadout.get_persistable_state())


# ---------------------------------------------------------------------------
# the key registry
# ---------------------------------------------------------------------------

def test_persistable_state_key_set_is_exactly_the_known_registry(default_state):
    assert set(default_state) == EXPECTED_STATE_KEYS


def test_host_push_pull_seam_round_trips_through_the_live_window(
    armory_window, loadout, dummy_state
):
    """The exact pair MainWindow uses: set_pending_loadout_state on load,
    get_loadout_state on save. With the Build Planner open, the pull reads the
    LIVE window, not the dict that was pushed."""
    armory_window.set_pending_loadout_state(copy.deepcopy(dummy_state))

    pulled = armory_window.get_loadout_state()

    assert set(pulled) == EXPECTED_STATE_KEYS
    assert pulled["current_build_name"] == "QA Equip Build"
    assert pulled["monolith_level"] == 7
    assert armory_window.get_loadout_window_if_open() is loadout


def test_host_pull_without_an_open_planner_returns_the_pushed_dict(armory_module):
    """A save must never wipe Build Planner data just because the user never
    opened the Armory this session (get_loadout_state's own docstring)."""
    window = armory_module.create_window(parent=None, language="en")
    try:
        assert window.get_loadout_window_if_open() is None
        window.set_pending_loadout_state({"character_class": "Cleric"})
        assert window.get_loadout_state() == {"character_class": "Cleric"}
    finally:
        window.close()


# ---------------------------------------------------------------------------
# round-trip, key by key
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(EXPECTED_STATE_KEYS))
def test_round_trip_preserves_key(key, dummy_state, round_tripped):
    assert round_tripped[key] == dummy_state[key]


def test_round_trip_adds_no_keys_and_loses_no_keys(dummy_state, round_tripped):
    assert set(round_tripped) == set(dummy_state)


# ---------------------------------------------------------------------------
# the documented drop trap (audit B-armory.md 1)
# ---------------------------------------------------------------------------

def test_unknown_extra_key_is_silently_dropped_today(loadout, dummy_state):
    """Current behaviour, pinned: explicit-key serialization loses anything
    get_persistable_state does not name. This is the trap the audit calls out;
    when it is fixed, this test is the one to delete (and the xfail below
    starts passing)."""
    state = copy.deepcopy(dummy_state)
    state["qa_future_key"] = "keep-me"

    loadout.apply_persisted_state(state)
    read_back = loadout.get_persistable_state()

    assert "qa_future_key" not in read_back


@pytest.mark.xfail(
    strict=False,
    reason="Desired behaviour after the schema-driven serialization fix "
           "(audit B-armory.md 1, MED/S): unknown keys should survive a "
           "round-trip instead of being dropped.",
)
def test_unknown_extra_key_should_survive_round_trip(loadout, dummy_state):
    state = copy.deepcopy(dummy_state)
    state["qa_future_key"] = "keep-me"

    loadout.apply_persisted_state(state)

    assert loadout.get_persistable_state().get("qa_future_key") == "keep-me"


# ---------------------------------------------------------------------------
# normalizations the round-trip performs (all load-bearing, all current)
# ---------------------------------------------------------------------------

def test_genius_lines_gain_an_explicit_locked_flag(loadout, dummy_state):
    """A Genius line saved by an older build (no `locked` key) reads back with
    locked=False -- _merge_genius_build rebuilds every entry onto a default."""
    state = copy.deepcopy(dummy_state)
    line = state["genius_builds_data"]["QA Genius"]["Cogni"]["2"]
    line.pop("locked", None)

    loadout.apply_persisted_state(state)
    read_back = loadout.get_persistable_state()

    assert read_back["genius_builds_data"]["QA Genius"]["Cogni"]["2"]["locked"] is False


def test_missing_stat_priority_profiles_are_filled_with_the_defaults(
    loadout, dummy_state, default_state
):
    state = copy.deepcopy(dummy_state)
    state["stat_priority_profiles"] = {}

    loadout.apply_persisted_state(state)
    read_back = loadout.get_persistable_state()

    assert read_back["stat_priority_profiles"] == default_state["stat_priority_profiles"]


def test_unknown_class_or_race_leaves_the_current_selection_alone(loadout, dummy_state):
    loadout.apply_persisted_state(copy.deepcopy(dummy_state))
    state = copy.deepcopy(dummy_state)
    state["character_class"] = "NotAClass"
    state["character_race"] = "NotARace"

    loadout.apply_persisted_state(state)
    read_back = loadout.get_persistable_state()

    assert read_back["character_class"] == "Ranger"
    assert read_back["character_race"] == "Asmodae"


def test_pantheon_empty_slots_round_trip_as_empty_strings(loadout, dummy_state):
    loadout.apply_persisted_state(copy.deepcopy(dummy_state))
    read_back = loadout.get_persistable_state()

    slots = read_back["pantheon_slots"]
    assert slots["Artwork1"] == 900999
    assert all(value == "" for key, value in slots.items() if key != "Artwork1")


# ---------------------------------------------------------------------------
# offline guarantee
# ---------------------------------------------------------------------------

def test_no_network_request_escapes_the_armory_under_test(armory_module, round_tripped):
    """QNetworkAccessManager.get/post raise in this suite, so reaching this
    line at all proves nothing hit the wire. What the Build Planner *would*
    have fetched on a cold cache is recorded instead -- it is non-zero, which
    is exactly the cold-start cost the audit flags (B-armory.md 6)."""
    assert armory_module._qa_detail_requests == []
    assert len(armory_module._qa_icon_requests) > 0
