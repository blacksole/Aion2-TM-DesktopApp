"""Armory landing page = live dashboard (audit §3 Phase 4c, D-ux M7/§3.2).

Two halves, deliberately separated:

1. ``summarize_build_planner`` — a pure function over the persisted
   ``profile["build_planner"]`` dict, tested without a widget: ``None``, an
   empty dict, a *real* profile section (``profiles/Claude.json``) and a
   synthetic state whose every number is known by hand.  Robustness matters
   more than the numbers here: six different Armory windows write into that
   dict, and this page only ever reads it.

2. The page itself — empty state vs cards, the CTA signals MainWindow is
   wired to, retranslation, and a rendered grab per theme (offscreen,
   ``QWidget.grab()``; no window ever appears on a real screen).

Seams these tests depend on (KEEP THEM STABLE):
  * ``summarize_build_planner`` / ``ArmorySummary`` / ``ARMORY_EQUIP_SLOTS``
  * ``ArmoryPage.set_build_planner_state`` — the ONE host hook, called by
    ``MainWindow._set_build_planner_state`` (the single writer of
    ``_build_planner_state``), plus ``MainWindow._refresh_armory_summary``
    and ``ArmoryPage.update_language``
  * objectNames ``armoryCard`` / ``armoryCardTitle`` / ``armoryCardValue`` /
    ``armoryCardHint`` / ``armoryCardCta``
"""

import json
import shutil
from array import array
from pathlib import Path

import pytest
from PySide6.QtCore import QDeadlineTimer, QEvent, QEventLoop, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from core import theme
from core.translations import TRANSLATIONS, tr
from tests.conftest import destroy_window
from ui.pages.armory_page import (
    ARMORY_EQUIP_SLOTS,
    ArmoryPage,
    ArmorySummary,
    summarize_build_planner,
)

REPO = Path(__file__).resolve().parent.parent
FIXTURE_PROFILE = REPO / "tests" / "fixtures" / "reset_profile.json"
REAL_PROFILE = REPO / "profiles" / "Claude.json"
SHOTS = REPO / "docs" / "audit-2026-09-18" / "shots" / "aether"

#: Every new key the dashboard reads, in all three language tables (the
#: key-existence pattern of tests/test_i18n_leaks.py: tr() falls back to
#: returning the key itself, so a typo ships as "armory_card_slots").
NEW_KEYS = (
    "armory_subtitle",
    "armory_card_build_title",
    "armory_card_build_empty",
    "armory_card_slots",
    "armory_card_enchant",
    "armory_card_daevanion_title",
    "armory_card_daevanion_value",
    "armory_card_skills_title",
    "armory_card_skills_value",
    "armory_card_open_build",
    "armory_card_open_items",
    "armory_card_open_crafting",
    "armory_empty_title",
    "armory_empty_hint",
)

#: Fusion's own default surfaces — the signature of a widget the stylesheet
#: never reached (same set and threshold as tests/test_render_gate.py).
FUSION_GREYS = (0xEFEFEF, 0xF0F0F0, 0xD4D0C8, 0xFFFFFF, 0xECECEC)
MAX_GREY_PIXELS = 200


def _settle(app, ms: int = 400) -> None:
    deadline = QDeadlineTimer(ms)
    while not deadline.hasExpired():
        app.processEvents(QEventLoop.AllEvents, 20)


def _grey_offenders(image: QImage) -> dict[str, int]:
    rgb32 = image.convertToFormat(QImage.Format_RGB32)
    words = array("I")
    words.frombytes(bytes(rgb32.constBits()))
    found = {}
    for grey in FUSION_GREYS:
        count = words.count(0xFF000000 | grey)
        if count > MAX_GREY_PIXELS:
            found[hex(grey)] = count
    return found


# ---------------------------------------------------------------------------
# 1. summarize_build_planner — no Qt
# ---------------------------------------------------------------------------


def test_summary_of_none_is_the_no_build_case():
    summary = summarize_build_planner(None)
    assert summary == ArmorySummary()
    assert summary.has_state is False
    assert summary.is_empty is True
    assert summary.total_slots == len(ARMORY_EQUIP_SLOTS) == 20
    assert summary.enchant_min is None and summary.enchant_max is None


@pytest.mark.parametrize("state", [{}, {"character_class": None}, {"equip_builds_data": "not a dict"}])
def test_summary_survives_missing_and_wrong_typed_keys(state):
    """A half-written or foreign-typed dict must summarize, not raise."""
    summary = summarize_build_planner(state)
    assert summary.has_state is True
    assert summary.is_empty is True
    assert summary.equipped_slots == 0
    assert summary.skill_count == 0
    assert summary.gear_types == ()


def test_summary_rejects_non_dict_state():
    assert summarize_build_planner([1, 2, 3]).is_empty is True
    assert summarize_build_planner("Chanter").has_state is False


def test_summary_of_the_real_profile_section():
    """profiles/Claude.json is a real, hand-built state (read-only here)."""
    state = json.loads(REAL_PROFILE.read_text(encoding="utf-8"))["build_planner"]
    summary = summarize_build_planner(state)

    assert summary.is_empty is False
    assert summary.character_class == "Chanter"
    assert summary.character_race == "Asmodae"
    assert summary.build_name == "Test Equip 1"

    equipped = state["equip_builds_data"]["chanter"]["Test Equip 1"]["equipped"]
    assert summary.equipped_slots == sum(1 for item in equipped.values() if item)
    assert 0 < summary.equipped_slots <= summary.total_slots

    # enchant is {"MainHand": 0} there -- "+0–+0" is noise, so no window.
    assert summary.enchant_min is None and summary.enchant_max is None

    assert summary.gear_types == ("Neutral", "PvE")
    assert summary.daevanion_nodes == 2          # s:11 + s:81, one node each
    assert summary.skill_build_name == "TestPvP"
    assert summary.skill_count == 6              # 4 active + 2 passive, stigma [null]
    assert summary.genius_build_name == "Default"
    assert summary.pantheon_total == len(state["pantheon_slots"])
    assert summary.pantheon_filled == 0


def _synthetic_state() -> dict:
    return {
        "character_class": "Gladiator",
        "character_race": "Elyos",
        "current_build_name": "PvE t1",
        "active_gear_types": ["PvE", "PvP", ""],
        "monolith_level": 3,
        "current_skill_build_name": "Cleave",
        "skill_builds_data": {
            "gladiator": {
                "Cleave": {
                    "priority": {
                        "active": ["1", "2", "3", None],
                        "passive": ["4", ""],
                        "stigma": [None],
                    }
                }
            }
        },
        "equip_builds_data": {
            "gladiator": {
                "PvE t1": {
                    "equipped": {
                        "MainHand": {"id": 1},
                        "Torso": {"id": 2},
                        "Helmet": None,
                        "Boots": {},
                    },
                    "enchant": {"MainHand": 15, "Torso": 12, "Helmet": 0, "Boots": True},
                }
            }
        },
        "daevanion_active": {"s:11": ["1", "2", "3"], "s:81": ["4"], "a:11": []},
        "genius_builds_data": {"Raid": {}},
        "current_genius_build_name": "Raid",
        "pantheon_slots": {"Artwork1": "77", "Artwork2": "", "Statue1": "88"},
    }


def test_summary_of_a_full_synthetic_state():
    summary = summarize_build_planner(_synthetic_state())

    assert summary.character_class == "Gladiator"
    assert summary.character_race == "Elyos"
    assert summary.build_name == "PvE t1"
    assert summary.equipped_slots == 2            # MainHand + Torso ({} and None are empty)
    assert summary.total_slots == len(ARMORY_EQUIP_SLOTS)
    assert (summary.enchant_min, summary.enchant_max) == (12, 15)  # 0 and True ignored
    assert summary.gear_types == ("PvE", "PvP")
    assert summary.daevanion_nodes == 4
    assert summary.skill_build_name == "Cleave"
    assert summary.skill_count == 4               # None and "" do not count
    assert summary.genius_build_name == "Raid"
    assert (summary.pantheon_filled, summary.pantheon_total) == (2, 3)
    assert summary.is_empty is False


def test_a_state_with_only_a_pantheon_piece_is_not_empty():
    """The class is the usual signal, but any real content beats it."""
    summary = summarize_build_planner({"pantheon_slots": {"Artwork1": "42"}})
    assert summary.is_empty is False


def test_build_name_is_blank_when_the_selected_build_does_not_exist():
    summary = summarize_build_planner(
        {"character_class": "Chanter", "current_build_name": "Gone", "equip_builds_data": {}}
    )
    assert summary.build_name == ""
    assert summary.is_empty is False
    assert summary.has_equip_build is False


# --- m2: a non-finite enchant level must not take the app down -------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (float("inf"), (None, None)),      # int(inf) raises OverflowError
        (float("-inf"), (None, None)),     # -inf > 0 is False, but guard it anyway
        (float("nan"), (None, None)),      # NaN > 0 is already False
        (12.0, (12, 12)),                  # a finite float still counts
    ],
)
def test_a_non_finite_enchant_level_cannot_raise(value, expected):
    """``json.loads`` accepts ``Infinity``, and ``int(inf)`` raises
    OverflowError — which would propagate through set_build_planner_state
    -> load_profile (try/finally, no except) into MainWindow.__init__, i.e.
    the app would not start (review G/m2)."""
    state = _synthetic_state()
    state["equip_builds_data"]["gladiator"]["PvE t1"]["enchant"] = {"MainHand": value}
    summary = summarize_build_planner(state)
    assert (summary.enchant_min, summary.enchant_max) == expected


def test_a_non_finite_level_does_not_hide_the_finite_ones():
    state = _synthetic_state()
    state["equip_builds_data"]["gladiator"]["PvE t1"]["enchant"] = {
        "MainHand": float("inf"),
        "Torso": 9,
    }
    summary = summarize_build_planner(state)
    assert (summary.enchant_min, summary.enchant_max) == (9, 9)


# --- m3: "0/20 slots" over a build that was never read ---------------------


def _state_with_an_unresolvable_class() -> dict:
    """A class the equip store has no key for, but real content elsewhere.

    ``daevanion_active`` and ``pantheon_slots`` are class-INDEPENDENT, so
    this state is not ``is_empty`` and the build card renders.
    """
    state = _synthetic_state()
    state["character_class"] = "Gladiatorr"  # misspelled: no equip_builds_data key
    return state


def test_an_unresolvable_class_reports_no_equip_build():
    summary = summarize_build_planner(_state_with_an_unresolvable_class())
    assert summary.is_empty is False
    assert summary.equipped_slots == 0
    assert summary.has_equip_build is False


def test_the_slots_line_is_hidden_when_the_build_was_never_found(page):
    """Review G/m3: the hint used to be unconditional, so a misspelled or
    not-yet-chosen class rendered "0/20 slots equipped" over a build the
    page had never read."""
    page.set_build_planner_state(_state_with_an_unresolvable_class())

    hints = [label.text() for label in page.build_card._hint_labels if not label.isHidden()]
    slots_line = tr("en", "armory_card_slots", equipped=0, total=len(ARMORY_EQUIP_SLOTS))
    assert slots_line not in hints, "the card still claims 0 of 20 slots"
    assert not any("0" in hint and "/" in hint for hint in hints), hints
    # What IS known still shows.
    assert not page.build_card.isHidden()
    assert page.daevanion_card.value_label.text() == tr(
        "en", "armory_card_daevanion_value", count=4
    )


def test_the_slots_line_is_shown_when_the_build_resolves(page):
    page.set_build_planner_state(_synthetic_state())
    hints = [label.text() for label in page.build_card._hint_labels if not label.isHidden()]
    assert hints[0] == tr(
        "en", "armory_card_slots", equipped=2, total=len(ARMORY_EQUIP_SLOTS)
    )


# --- m11 / m12: the display face and the card's own padding ----------------


def test_the_display_face_elides_and_keeps_the_whole_string(page):
    """MASTER-neutral fix for review G/m11: a value wider than its cell was
    clipped mid-glyph with no ellipsis and no tooltip."""
    long_value = "Gladiator · Elyos · " + "Eine sehr lange Buildbezeichnung " * 3
    page.build_card.set_value(long_value)
    label = page.build_card.value_label

    assert label.text() == long_value, "the logical text must stay whole"
    assert label.toolTip() == long_value, "no tooltip = the rest is unreadable"

    label.setFixedWidth(120)
    QApplication.instance().processEvents()
    painted = QLabel.text(label)
    assert painted != long_value and painted.endswith("…"), (
        f"the face is clipped rather than elided: {painted!r}"
    )
    assert label.text() == long_value


def test_a_short_value_is_not_elided(page):
    page.build_card.value_label.setFixedWidth(600)
    page.build_card.set_value("Gladiator")
    QApplication.instance().processEvents()
    assert QLabel.text(page.build_card.value_label) == "Gladiator"


def test_the_card_padding_is_space_3(page):
    """MASTER §3 "Carte": padding `3`.  It was (16, 12, 16, 12) — space_4
    horizontally — the only card in the app with its own padding (G/m12)."""
    from ui.pages.armory_page import CARD_PADDING

    assert CARD_PADDING == theme.THEMES["abyss"].space_3
    assert len({tokens.space_3 for tokens in theme.THEMES.values()}) == 1, (
        "space_3 now differs per theme — the card margin can no longer be a "
        "plain int here"
    )
    for card in (page.build_card, page.daevanion_card, page.items_card):
        margins = card.layout().contentsMargins()
        assert (
            margins.left(), margins.top(), margins.right(), margins.bottom()
        ) == (CARD_PADDING,) * 4


# ---------------------------------------------------------------------------
# 2. translations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", sorted(TRANSLATIONS))
@pytest.mark.parametrize("key", NEW_KEYS)
def test_every_new_key_exists_in_every_language(language, key):
    assert key in TRANSLATIONS[language], f"{language} is missing {key}"


@pytest.mark.parametrize("language", sorted(TRANSLATIONS))
def test_the_subtitle_no_longer_says_coming_soon(language):
    subtitle = TRANSLATIONS[language]["armory_subtitle"]
    for stale in ("coming soon", "in Vorbereitung", "скоро"):
        assert stale not in subtitle


def test_the_counted_keys_format_with_their_placeholders():
    assert tr("en", "armory_card_slots", equipped=11, total=20) == "11/20 slots equipped"
    assert tr("en", "armory_card_enchant", min=12, max=15) == "Enchant +12–+15"
    assert tr("en", "armory_card_daevanion_value", count=47) == "47 nodes active"


# ---------------------------------------------------------------------------
# 3. the page
# ---------------------------------------------------------------------------


@pytest.fixture
def page(qapp):
    widget = ArmoryPage()
    widget.update_language("en", tr)
    yield widget
    widget.deleteLater()


def test_page_shows_the_empty_state_when_there_is_no_build(page):
    page.set_build_planner_state(None)
    assert page.empty_state.isVisible() or not page.empty_state.isHidden()
    assert page.empty_state.title_label.text() == tr("en", "armory_empty_title")
    assert page.empty_state.hint_label.text() == tr("en", "armory_empty_hint")
    assert page.empty_state.action_button.text() == tr("en", "armory_card_open_build")
    # The two launchers keep working without a build; the summary cards go.
    for card in (page.build_card, page.daevanion_card, page.skill_card):
        assert card.isHidden()
    assert not page.items_card.isHidden()
    assert not page.crafting_card.isHidden()


def test_page_shows_the_cards_when_the_state_is_populated(page):
    page.set_build_planner_state(_synthetic_state())

    assert page.empty_state.isHidden()
    for card in (page.build_card, page.daevanion_card, page.skill_card):
        assert not card.isHidden()

    assert page.build_card.value_label.text() == "Gladiator · Elyos · PvE t1"
    hints = [label.text() for label in page.build_card._hint_labels if not label.isHidden()]
    assert hints == [
        tr("en", "armory_card_slots", equipped=2, total=len(ARMORY_EQUIP_SLOTS)),
        tr("en", "armory_card_enchant", min=12, max=15),
        "PvE · PvP",
    ]
    assert page.daevanion_card.value_label.text() == tr("en", "armory_card_daevanion_value", count=4)
    assert page.skill_card.value_label.text() == tr("en", "armory_card_skills_value", count=4)
    assert page.build_card.cta_button.text() == tr("en", "armory_card_open_build")


def test_the_launcher_cards_keep_their_description_and_no_figure(page):
    page.set_build_planner_state(_synthetic_state())
    assert page.items_card.value_label.isHidden()
    assert page.items_card.title_label.text() == tr("en", "armory_roadmap_items_title")
    assert page.items_card._hint_labels[0].text() == tr("en", "armory_roadmap_items_desc")
    assert page.crafting_card.cta_button.text() == tr("en", "armory_card_open_crafting")


def test_every_card_piece_carries_its_objectname(page):
    page.set_build_planner_state(_synthetic_state())
    card = page.build_card
    assert card.objectName() == "armoryCard"
    assert card.title_label.objectName() == "armoryCardTitle"
    assert card.value_label.objectName() == "armoryCardValue"
    assert card.cta_button.objectName() == "armoryCardCta"
    assert {label.objectName() for label in card._hint_labels} == {"armoryCardHint"}


CTA_CASES = (
    ("build_card", "open_build_planner_requested"),
    ("daevanion_card", "open_build_planner_requested"),
    ("skill_card", "open_build_planner_requested"),
    ("items_card", "open_item_database_requested"),
    ("crafting_card", "open_crafting_calculator_requested"),
)


@pytest.mark.parametrize("card_name,signal_name", CTA_CASES)
def test_the_cta_button_emits_the_page_signal(page, card_name, signal_name):
    page.set_build_planner_state(_synthetic_state())
    fired = []
    getattr(page, signal_name).connect(lambda: fired.append(card_name))
    getattr(page, card_name).cta_button.click()
    assert fired == [card_name]


@pytest.mark.parametrize("card_name,signal_name", CTA_CASES)
def test_the_whole_card_is_clickable(page, card_name, signal_name):
    """The card is a button, via a real Signal -- not the
    ``row.mousePressEvent = closure`` monkey-patch this page used to carry
    (which kept the widget alive inside a default argument)."""
    page.set_build_planner_state(_synthetic_state())
    card = getattr(page, card_name)
    assert card.mousePressEvent.__self__ is card   # bound method, not a patched attribute
    fired = []
    getattr(page, signal_name).connect(lambda: fired.append(card_name))
    QTest.mouseClick(card, Qt.LeftButton)
    assert fired == [card_name]


@pytest.mark.parametrize("card_name,signal_name", CTA_CASES)
def test_the_card_is_activatable_by_keyboard(page, card_name, signal_name):
    page.set_build_planner_state(_synthetic_state())
    card = getattr(page, card_name)
    fired = []
    getattr(page, signal_name).connect(lambda: fired.append(card_name))
    QTest.keyClick(card, Qt.Key_Space)
    assert fired == [card_name]


def test_the_empty_state_cta_opens_the_build_planner(page):
    page.set_build_planner_state(None)
    fired = []
    page.open_build_planner_requested.connect(lambda: fired.append("open"))
    page.empty_state.action_button.click()
    assert fired == ["open"]


def test_a_language_switch_retranslates_every_text(page):
    page.set_build_planner_state(_synthetic_state())
    page.update_language("de", tr)

    assert page.subtitle_label.text() == tr("de", "armory_subtitle")
    assert page.build_card.title_label.text() == tr("de", "armory_card_build_title")
    assert page.build_card.cta_button.text() == tr("de", "armory_card_open_build")
    assert page.daevanion_card.value_label.text() == tr("de", "armory_card_daevanion_value", count=4)
    assert page.items_card.cta_button.text() == tr("de", "armory_card_open_items")

    page.update_language("ru", tr)
    assert page.skill_card.value_label.text() == tr("ru", "armory_card_skills_value", count=4)
    # Data (class, race, build name) is never translated.
    assert page.build_card.value_label.text() == "Gladiator · Elyos · PvE t1"

    page.update_language("en", tr)
    assert page.subtitle_label.text() == tr("en", "armory_subtitle")


def test_a_language_switch_retranslates_the_empty_state(page):
    page.set_build_planner_state(None)
    page.update_language("de", tr)
    assert page.empty_state.title_label.text() == tr("de", "armory_empty_title")
    assert page.empty_state.action_button.text() == tr("de", "armory_card_open_build")
    assert page.empty_state.hint_label.text() == tr("de", "armory_empty_hint")
    assert not page.empty_state.isHidden()


# ---------------------------------------------------------------------------
# 4. rendered, per theme (offscreen grabs -- MASTER §4-5 render gate)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def win(qapp, tmp_path_factory):
    import ui.main_window as mw

    profile_dir = tmp_path_factory.mktemp("armory_dashboard")
    shutil.copy2(FIXTURE_PROFILE, profile_dir / "QaProfile.json")

    patcher = pytest.MonkeyPatch()
    patcher.setattr(mw.MainWindow, "_resolve_profile_dir", lambda self: profile_dir)
    patcher.setattr(mw.MainWindow, "_save_app_config", lambda self: None)

    window = mw.MainWindow()
    window.countdown_timer.stop()
    window.resize(1100, 720)
    window.show()
    yield window
    destroy_window(window)
    patcher.undo()


def _real_state() -> dict:
    return json.loads(REAL_PROFILE.read_text(encoding="utf-8"))["build_planner"]


class _FakeArmoryWindow:
    """The two methods MainWindow calls across the Armory seam.

    Standing in for the real ItemDatabase window so the writer paths can be
    driven without loading the 23k-line module (and without a second
    top-level window, parentless and modeless, in the test process).
    """

    def __init__(self, state, loadout=None):
        self.state = state
        self.pending = None
        self._loadout = loadout

    def get_loadout_state(self):
        return self.state

    def set_pending_loadout_state(self, state):
        self.pending = state

    def get_loadout_window_if_open(self):
        return self._loadout


@pytest.fixture
def host(win):
    """``win`` with its Armory seam reset after the test.

    The fixture is function-scoped over the module-scoped window: each
    writer-path test installs its own fake Armory window and its own
    profile name, and hands both back.
    """
    original_window = win.item_database_window
    original_state = win._build_planner_state
    original_name = win.profile_name
    win.item_database_window = None
    win._set_build_planner_state(None)
    yield win
    win.item_database_window = original_window
    win.profile_name = original_name
    win._set_build_planner_state(original_state)


def test_the_single_writer_pushes_to_the_page(host):
    """M1: ``_build_planner_state`` has exactly one writer, and it tells the
    page.  Every other path below goes through this one."""
    host._set_build_planner_state(_real_state())
    assert host._build_planner_state is not None
    assert host.armory_page.summary.character_class == "Chanter"

    host._set_build_planner_state(None)
    assert host.armory_page.summary.is_empty is True


def test_writer_path_load_profile_refreshes_the_dashboard(host, tmp_path):
    """Writer 1/4: ``load_profile``."""
    profile = tmp_path / "LoadedProfile.json"
    profile.write_text(
        json.dumps({"profile_name": "LoadedProfile", "build_planner": _real_state()}),
        encoding="utf-8",
    )
    host.load_profile(profile)
    assert host.armory_page.summary.character_class == "Chanter"

    blank = tmp_path / "BlankProfile.json"
    blank.write_text(json.dumps({"profile_name": "BlankProfile"}), encoding="utf-8")
    host.load_profile(blank)
    assert host.armory_page.summary.is_empty is True


def test_writer_path_save_profile_refreshes_the_dashboard(host):
    """Writer 2/4: the ``get_loadout_state()`` pull inside ``save_profile``."""
    host.item_database_window = _FakeArmoryWindow(_real_state())
    host.save_profile(silent=True)
    assert host.armory_page.summary.character_class == "Chanter"


def test_writer_path_advance_equip_priority_refreshes_the_dashboard(host):
    """Writer 3/4: the overlay's Gear-Priority check button, live-window
    branch — it re-pulls the state, so the page must follow."""
    state = _real_state()
    edited = json.loads(json.dumps(state))
    edited["character_class"] = "Gladiator"

    class _FakeLoadout:
        _current_equip_build_name = state["current_build_name"]

        class character_class_combo:  # noqa: N801 - mirrors the real widget name
            @staticmethod
            def currentText():
                return state["character_class"]

        def advance_equip_priority(self, section_key):
            self.advanced = section_key

    loadout = _FakeLoadout()
    host.item_database_window = _FakeArmoryWindow(edited, loadout=loadout)
    host._set_build_planner_state(state)
    assert host.armory_page.summary.character_class == "Chanter"

    host.advance_equip_priority("weapon")
    assert loadout.advanced == "weapon"
    assert host.armory_page.summary.character_class == "Gladiator"


def test_the_dashboard_refreshes_when_the_app_regains_focus(host):
    """M1's own user path: the Build Planner is parentless and modeless, so
    closing it fires no show/hide on the page — only an activation change on
    the window."""
    host.item_database_window = _FakeArmoryWindow(_real_state())
    assert host.armory_page.summary.is_empty is True

    # isActiveWindow() is False for an offscreen window, so shadow it: the
    # gate under test is "activation changed AND we are the active window".
    host.isActiveWindow = lambda: True
    try:
        host.changeEvent(QEvent(QEvent.ActivationChange))
    finally:
        del host.isActiveWindow
    assert host.armory_page.summary.character_class == "Chanter"


def test_a_refresh_is_skipped_while_a_profile_is_loading(host):
    """The live window still holds the PREVIOUS profile at that moment."""
    host.item_database_window = _FakeArmoryWindow(_real_state())
    host._profile_loading = True
    try:
        host._refresh_armory_summary()
    finally:
        host._profile_loading = False
    assert host.armory_page.summary.is_empty is True


def test_a_template_profile_populates_the_dashboard_without_writing(host, tmp_path):
    """M2: ``save_profile`` returns early on a template profile — the pull
    now happens BEFORE that return, so the first-run path populates.  And it
    still writes nothing: that guard exists for a real data-loss reason."""
    host.profile_name = "Default"
    template = host.profile_dir / "Default.json"
    assert not template.exists()

    host.item_database_window = _FakeArmoryWindow(_real_state())
    host.save_profile(silent=True)

    assert host.armory_page.summary.character_class == "Chanter"
    assert not template.exists(), "a template profile must not be written to"


# ---------------------------------------------------------------------------
# 5. the slot mirror (M3) -- drift against the real Armory fails loudly
# ---------------------------------------------------------------------------


def test_the_active_slot_mirror_matches_the_armory():
    """``ARMORY_EQUIP_SLOTS`` is the ACTIVE paperdoll, recomputed here from
    ItemDatabase's own section tables.

    The page mirrors the slot ids instead of importing the 23k-line module
    (module docstring), so this is the test that makes the mirror safe: add
    Brooch back to the paperdoll over there and this fails, instead of the
    dashboard quietly reading "20/22 slots equipped" forever (review G/M3).
    """
    import ItemDatabase.app as ida

    active = [
        slot
        for _label, slots in (*ida._LEFT_EQUIP_SECTIONS, *ida._RIGHT_EQUIP_SECTIONS)
        for slot in slots
    ]
    assert tuple(active) == ARMORY_EQUIP_SLOTS
    assert len(active) == 20

    # The definition table is longer -- that difference is the whole finding.
    defined = {slot for slot, _key, _cats in ida.SLOT_LAYOUT}
    assert defined - set(active) == {"Brooch1", "Brooch2"}


def test_a_filled_unknown_slot_grows_the_denominator():
    """So the ratio can never exceed 1 if the Armory gains a slot first."""
    state = _synthetic_state()
    equipped = state["equip_builds_data"]["gladiator"]["PvE t1"]["equipped"]
    equipped.update({f"Extra{index}": {"id": index} for index in range(len(ARMORY_EQUIP_SLOTS))})
    summary = summarize_build_planner(state)
    assert summary.equipped_slots == len(ARMORY_EQUIP_SLOTS) + 2
    assert summary.total_slots == summary.equipped_slots


def test_an_empty_unknown_slot_does_not_grow_the_denominator():
    """A profile written by an older build can hold an empty Brooch entry."""
    state = _synthetic_state()
    state["equip_builds_data"]["gladiator"]["PvE t1"]["equipped"].update(
        {"Brooch1": None, "Brooch2": {}}
    )
    summary = summarize_build_planner(state)
    assert summary.equipped_slots == 2
    assert summary.total_slots == len(ARMORY_EQUIP_SLOTS)


@pytest.mark.parametrize("name", ("abyss", "inferno"))
def test_the_armory_dashboard_renders_with_no_fusion_grey(win, qapp, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    state = json.loads(REAL_PROFILE.read_text(encoding="utf-8"))["build_planner"]

    win.apply_theme(name)
    win.sidebar.set_active_page("armory")
    win._build_planner_state = state
    win.armory_page.set_build_planner_state(state)
    _settle(qapp, 400)

    pixmap = win.grab()
    assert not pixmap.isNull()
    image = pixmap.toImage()

    destination = SHOTS / f"armory_dashboard_{name}.png"
    assert image.save(str(destination)), f"could not write {destination}"

    offenders = _grey_offenders(image)
    assert not offenders, f"{name}: Fusion default surfaces on the Armory page {offenders}"

    # The card surface really is the theme's elevated token, i.e. the sheet
    # reached the new objectNames (a name-based test cannot see this).
    card_image = win.armory_page.build_card.grab().toImage()
    expected = theme.qcolor(name, "bg.elevated").rgb() & 0xFFFFFF
    centre = card_image.pixel(card_image.width() // 2, 4) & 0xFFFFFF
    assert centre == expected, (
        f"{name}: the Armory card ground is {hex(centre)}, expected {hex(expected)}"
    )
    win.apply_theme("abyss")
