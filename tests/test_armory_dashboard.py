"""Armory landing page = live dashboard (audit §3 Phase 4c, D-ux M7/§3.2).

Two halves, deliberately separated:

1. ``summarize_build_planner`` — a pure function over the persisted
   ``profile["build_planner"]`` dict, tested without a widget: ``None``, an
   empty dict, a *real* profile section (``profiles/_fixtures/real_build_planner_profile.json``) and a
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
import sys
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
    _count_chosen_daevanion_nodes,
    summarize_build_planner,
)

REPO = Path(__file__).resolve().parent.parent

# The recommendation card renders ENGINE objects (duck-typed: text_key,
# text_kwargs, reasons).  Building the fakes out of the real dataclasses --
# rather than out of a local stub -- is what makes these tests fail if the
# explain contract changes shape, which is the whole point of having one.
if str(REPO / "ItemDatabase") not in sys.path:
    sys.path.insert(0, str(REPO / "ItemDatabase"))
from armory_engine.explain import Reason, Recommendation  # noqa: E402

FIXTURE_PROFILE = REPO / "tests" / "fixtures" / "reset_profile.json"
REAL_PROFILE = REPO / "profiles" / "_fixtures" / "real_build_planner_profile.json"
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
    "armory_card_open_daevanion",
    "armory_card_open_skills",
    "armory_card_open_items",
    "armory_card_open_crafting",
    "armory_empty_title",
    "armory_empty_hint",
)

#: The Stage-2 recommendation keys (B-armory.md §3.4 #1/#2).  Listed apart
#: from NEW_KEYS because half of them are never written in this repo's Python
#: at all: they arrive as ``text_key`` strings from
#: ``ItemDatabase/armory_engine``, so ``tests/test_i18n_leaks.py``'s literal
#: scan cannot see them and this is the only gate they have.
RECO_KEYS = (
    "armory_reco_title",
    "armory_reco_why",
    "armory_reco_needs_data",
    "armory_reco_empty",
    "armory_reco_set_incomplete",
    "armory_reason_set_missing_piece",
    "armory_reco_substat_alignment",
    "armory_reason_substat_missing",
    "armory_reason_slot_off_profile",
    "armory_reco_stat_gap",
    "armory_reason_stat_absent",
    "armory_reason_stat_thin",
    "armory_reason_stat_behind",
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
    """profiles/_fixtures/real_build_planner_profile.json is a real, hand-built state (read-only here)."""
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
    assert summary.daevanion_nodes == 0          # s:11 + s:81 each hold only their free start node
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
        # s:11 has 2 player-picked nodes plus its free start node ("1"),
        # s:81 has only its free start node ("4"), a:11 was never touched.
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
    assert summary.daevanion_nodes == 2  # start nodes excluded: (3-1) + (1-1) + (0-1 clamped to 0)
    assert summary.skill_build_name == "Cleave"
    assert summary.skill_count == 4               # None and "" do not count
    assert summary.genius_build_name == "Raid"
    assert (summary.pantheon_filled, summary.pantheon_total) == (2, 3)
    assert summary.is_empty is False


# ---------------------------------------------------------------------------
# The Daevanion start node: excluded by ID, not by subtracting one
# ---------------------------------------------------------------------------
# Apex review of PR #7, finding 8.  Every board carries one free, always-on
# "start" node that app.py seeds lazily and refuses to toggle, so it must not
# show up as "1 nodes active" on a board nobody clicked.  `len(nodes) - 1`
# gets the common case right and is wrong about everything else: a board
# saved WITHOUT its start node (a legacy profile, or one written before lazy
# seeding) silently under-reports.  The rule lives once, Qt-free, in
# armory_engine.daevanion; the host pushes the ids in.

def test_the_engine_knows_the_start_node_by_its_grade_not_its_position():
    from armory_engine.daevanion import daevanion_start_node_id

    grid = {
        (0, 0): {"id": "a", "g": "common"},
        (0, 1): {"id": "root", "g": "start"},
        (1, 0): {"id": "b", "g": "legend"},
    }
    assert daevanion_start_node_id(grid) == "root"
    assert daevanion_start_node_id({(0, 0): {"id": "a", "g": "common"}}) is None
    assert daevanion_start_node_id({}) is None


def test_the_engine_counts_the_nodes_the_player_picked():
    from armory_engine.daevanion import daevanion_chosen_node_count

    # The start node is NOT first -- the whole point of matching by id.
    assert daevanion_chosen_node_count(["a", "root", "b"], "root") == 2
    # Never seeded: nothing to subtract, and the old "-1" lost a real node.
    assert daevanion_chosen_node_count(["a", "b"], "root") == 2
    assert daevanion_chosen_node_count(["root"], "root") == 0
    assert daevanion_chosen_node_count([], "root") == 0
    assert daevanion_chosen_node_count(["a", "", None], "root") == 1


@pytest.mark.parametrize(
    ("ids", "start_id", "expected"),
    [
        (["a", "root", "b"], "root", 2),   # start in the middle of the list
        (["root", "a", "b"], "root", 2),   # start first (the common case)
        (["a", "b", "root"], "root", 2),   # start last
        (["a", "b"], "root", 2),           # never seeded -- "-1" would say 1
        (["root"], "root", 0),
        (["a", "root", "b"], None, 2),     # fallback: subtract one
        (["a", "b"], None, 1),             # fallback, and wrong -- knowingly
    ],
)
def test_the_page_excludes_the_start_node_by_id_when_it_knows_it(ids, start_id, expected):
    assert _count_chosen_daevanion_nodes(ids, start_id) == expected


def test_the_summary_uses_the_start_ids_the_host_pushes_in():
    """A board whose start node is not the first entry, and one that was
    never seeded at all -- the two cases the blind "-1" gets wrong."""
    state = {
        "daevanion_active": {
            "s:11": ["110201", "110113", "110202"],   # start node in the MIDDLE
            "s:81": ["810301", "810302"],             # never seeded: no start node
        }
    }
    start_ids = {"s:11": "110113", "s:81": "810113"}
    assert summarize_build_planner(state, start_ids).daevanion_nodes == 4

    # Without the mapping the page falls back and under-reports s:81 by one.
    assert summarize_build_planner(state).daevanion_nodes == 3


def test_the_summary_still_works_when_the_board_data_is_missing():
    """``{}`` is what the host pushes when the board files are unreadable --
    the dashboard must degrade, not raise."""
    state = _synthetic_state()
    assert summarize_build_planner(state, {}).daevanion_nodes == 2
    assert summarize_build_planner(state, None).daevanion_nodes == 2


def test_the_page_hook_ignores_anything_that_is_not_a_mapping(page):
    """The host computes the mapping behind a try/except, so it must be able
    to say "not known" without inventing a shape (same contract as
    ``set_recommendations``)."""
    page.set_daevanion_start_ids({"s:11": "110113"})
    page.set_daevanion_start_ids(None)
    page.set_build_planner_state(_synthetic_state())
    assert page.summary.daevanion_nodes == 2


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
        "en", "armory_card_daevanion_value", count=2
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
    assert page.daevanion_card.value_label.text() == tr("en", "armory_card_daevanion_value", count=2)
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


#: card, the signal it emits, and -- for the two cards that open the Build
#: Planner ON a particular tab -- the ``LoadoutWindow.TAB_*`` name that tab
#: is called by its owner (ItemDatabase/app.py).  The third column is what
#: was missing: these tests asserted the SIGNAL fires and nothing asserted
#: where it lands, so the two bare indices ui/main_window.py used to keep
#: could drift out of the Armory's addTab order unnoticed (Apex review of
#: PR #7, finding 7).  ``tests/test_armory_theme.py`` consumes the pairs
#: against a real LoadoutWindow; here they pin the host's own mapping.
CTA_CASES = (
    ("build_card", "open_build_planner_requested", None),
    ("daevanion_card", "open_daevanion_requested", "TAB_DAEVANION"),
    ("skill_card", "open_skill_planner_requested", "TAB_SKILLS"),
    ("items_card", "open_item_database_requested", None),
    ("crafting_card", "open_crafting_calculator_requested", None),
)

#: The MainWindow launcher each tab-opening card is wired to, and the
#: ``LoadoutWindow.TAB_*`` name it must ask for.
PLANNER_TAB_CASES = tuple(
    (signal, tab) for _card, signal, tab in CTA_CASES if tab is not None
)


@pytest.mark.parametrize("card_name,signal_name,tab_name", CTA_CASES)
def test_the_cta_button_emits_the_page_signal(page, card_name, signal_name, tab_name):
    page.set_build_planner_state(_synthetic_state())
    fired = []
    getattr(page, signal_name).connect(lambda: fired.append(card_name))
    getattr(page, card_name).cta_button.click()
    assert fired == [card_name]


@pytest.mark.parametrize("card_name,signal_name,tab_name", CTA_CASES)
def test_the_whole_card_is_clickable(page, card_name, signal_name, tab_name):
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


@pytest.mark.parametrize("card_name,signal_name,tab_name", CTA_CASES)
def test_the_card_is_activatable_by_keyboard(page, card_name, signal_name, tab_name):
    page.set_build_planner_state(_synthetic_state())
    card = getattr(page, card_name)
    fired = []
    getattr(page, signal_name).connect(lambda: fired.append(card_name))
    QTest.keyClick(card, Qt.Key_Space)
    assert fired == [card_name]


@pytest.mark.parametrize("signal_name,tab_name", PLANNER_TAB_CASES)
def test_the_host_asks_the_armory_for_the_tab_by_name(signal_name, tab_name):
    """MainWindow must resolve the index through ``LoadoutWindow.TAB_*``.

    A source-level gate rather than a live click, because a live click needs
    the whole 22k-line Armory module -- which
    ``tests/test_armory_theme.py::test_opening_the_planner_on_a_named_tab_lands_there``
    already pays for and asserts against. What this pins is the half that
    lives here: that the host does not go back to spelling the integer.
    """
    import ast

    source = (REPO / "ui" / "main_window.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    main_window = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
    )
    connects = {
        node.func.value.attr: node.args[0].attr
        for node in ast.walk(main_window)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "connect"
        and isinstance(node.func.value, ast.Attribute)
        and node.args
        and isinstance(node.args[0], ast.Attribute)
    }
    launcher_name = connects[signal_name]
    launcher = next(
        node for node in main_window.body
        if isinstance(node, ast.FunctionDef) and node.name == launcher_name
    )
    asked = [
        node.args[0].value
        for node in ast.walk(launcher)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_loadout_tab"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]
    assert asked == [tab_name], (
        f"{launcher_name} asks for {asked}, not LoadoutWindow.{tab_name}"
    )


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
    assert page.daevanion_card.value_label.text() == tr("de", "armory_card_daevanion_value", count=2)
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


# ---------------------------------------------------------------------------
# 6. the Recommendations card (Stage 2, B-armory.md §3.4 #1/#2)
#
# The engine itself is tested without Qt in
# tests/test_armory_engine_recommend.py.  What is tested HERE is the seam:
# that a Recommendation survives the trip to a widget as a translation KEY
# (so a language switch after the solve still renders), that "Why?" gates
# the reasons, and that the degradation line is the one the audit asked for.
# ---------------------------------------------------------------------------


def _reco(text_key, reasons=(), **kwargs):
    return Recommendation(
        pick={"kind": "test"}, score_delta=0.0, reasons=tuple(reasons),
        text_key=text_key, text_kwargs=kwargs,
    )


def _set_reco():
    """What ``missing_set_pieces`` produces for a set that is one piece
    short — the exact shape, built by hand."""
    return _reco(
        "armory_reco_set_incomplete",
        reasons=(
            Reason(
                stat_id="", delta=1.0, weight=0.25,
                text_key="armory_reason_set_missing_piece",
                text_kwargs={"slot": "Ring", "set": "Abyssal",
                             "source": "Expedition", "item": "Abyssal Ring"},
            ),
        ),
        set="Abyssal", owned=3, total=4, source="Expedition",
    )


@pytest.mark.parametrize("language", sorted(TRANSLATIONS))
@pytest.mark.parametrize("key", RECO_KEYS)
def test_every_recommendation_key_exists_in_every_language(language, key):
    assert key in TRANSLATIONS[language], f"{language} is missing {key}"
    assert TRANSLATIONS[language][key].strip(), f"{language}[{key}] is empty"


def test_every_engine_text_key_has_a_translation():
    """The keys the ENGINE emits, read off the engine's own constants rather
    than retyped here: a solver that invents a key nobody translated would
    ship the key itself rendered on screen (``tr`` falls back to it)."""
    from armory_engine import providers as engine_providers
    from armory_engine import recommend as engine_recommend
    from armory_engine import score as engine_score

    emitted = {
        engine_providers.DATA_MISSING_KEY,
        engine_recommend.RECO_SET_INCOMPLETE,
        engine_recommend.REASON_SET_MISSING_PIECE,
        engine_recommend.RECO_STAT_GAP,
        engine_score.REASON_STAT_ABSENT,
        engine_score.REASON_STAT_THIN,
        engine_score.REASON_STAT_BEHIND,
        engine_score.REASON_STAT_SUBSTAT_MISSING,
        engine_score.REASON_SLOT_OFF_PROFILE,
        engine_score.RECO_SUBSTAT_ALIGNMENT,
    }
    assert emitted <= set(RECO_KEYS)
    for language, table in TRANSLATIONS.items():
        assert emitted <= set(table), f"{language} is missing {sorted(emitted - set(table))}"


def test_the_recommendation_keys_format_with_the_kwargs_the_engine_sends():
    assert tr("en", "armory_reco_set_incomplete", set="Abyssal", owned=3, total=4,
              source="Expedition") == "Abyssal: 3/4 pieces — the rest from Expedition"
    assert tr("en", "armory_reason_stat_thin", stat="Critical Hit", slots=1,
              total=4) == "Critical Hit: only 1 of 4 slots provide any"
    assert tr("en", "armory_reason_stat_behind", stat="Attack", slots=1, total=4,
              value=650.0, reference=1000.0) == (
        "Attack: 650 against 1000 in the comparison build"
    )


def test_the_card_shows_the_degradation_line_when_there_is_no_data(page):
    """Audit §3.4's graceful degradation, as the user sees it: one line that
    says why, not an empty card that reads as "nothing to improve"."""
    page.set_build_planner_state(_synthetic_state())
    page.set_recommendations([_reco("armory_reco_needs_data")])

    rows = page.reco_card.visible_rows()
    assert [row.text_label.text() for row in rows] == [tr("en", "armory_reco_needs_data")]
    # Nothing to expand: a recommendation with no reasons explains itself.
    assert rows[0].why_button.isHidden()


def test_no_recommendation_at_all_reads_as_nothing_to_improve(page):
    page.set_build_planner_state(_synthetic_state())
    page.set_recommendations([])
    rows = page.reco_card.visible_rows()
    assert [row.text_label.text() for row in rows] == [tr("en", "armory_reco_empty")]


def test_a_recommendation_renders_its_line_and_hides_its_reasons(page):
    page.set_build_planner_state(_synthetic_state())
    page.set_recommendations([_set_reco()])

    (row,) = page.reco_card.visible_rows()
    assert row.text_label.text() == tr(
        "en", "armory_reco_set_incomplete", set="Abyssal", owned=3, total=4, source="Expedition"
    )
    assert not row.why_button.isHidden()
    assert row.why_button.text() == tr("en", "armory_reco_why")
    assert row.why_label.isHidden()


def test_why_reveals_the_reasons_and_hides_them_again(page):
    page.set_build_planner_state(_synthetic_state())
    page.set_recommendations([_set_reco()])
    (row,) = page.reco_card.visible_rows()

    row.why_button.setChecked(True)
    assert not row.why_label.isHidden()
    assert row.why_label.text() == tr(
        "en", "armory_reason_set_missing_piece", slot="Ring", set="Abyssal",
        source="Expedition", item="Abyssal Ring",
    )

    row.why_button.setChecked(False)
    assert row.why_label.isHidden()


def test_the_rows_are_reused_rather_than_rebuilt(page):
    """The page lives for the whole session and re-renders on every state
    push; churning widgets under it is what the hint labels already avoid."""
    page.set_build_planner_state(_synthetic_state())
    page.set_recommendations([_set_reco(), _reco("armory_reco_needs_data")])
    before = page.reco_card.rows
    assert len(before) == 2

    page.set_recommendations([_set_reco()])
    after = page.reco_card.rows
    assert after[0] is before[0] and after[1] is before[1]
    assert len(page.reco_card.visible_rows()) == 1


def test_a_language_switch_re_renders_a_recommendation_solved_earlier(page):
    """The reason ``text_key`` is a KEY and not a sentence: the solve happens
    on a state push, the render happens later, and the language can change in
    between."""
    page.set_build_planner_state(_synthetic_state())
    page.set_recommendations([_set_reco()])
    (row,) = page.reco_card.visible_rows()
    row.why_button.setChecked(True)
    english = row.text_label.text()

    page.update_language("de", tr)
    (row,) = page.reco_card.visible_rows()
    assert row.text_label.text() != english
    assert row.text_label.text() == tr(
        "de", "armory_reco_set_incomplete", set="Abyssal", owned=3, total=4, source="Expedition"
    )
    assert page.reco_card.title_label.text() == tr("de", "armory_reco_title")
    assert row.why_button.text() == tr("de", "armory_reco_why")


def test_a_key_whose_placeholders_disagree_falls_back_to_the_key(page):
    """Guarded because this runs inside a paint: a mismatch between an
    engine's kwargs and a translation's placeholders must show a visible
    typo, not stop the page from drawing."""
    page.set_build_planner_state(_synthetic_state())
    page.set_recommendations([_reco("armory_reco_set_incomplete")])  # no kwargs at all
    (row,) = page.reco_card.visible_rows()
    assert row.text_label.text() == "armory_reco_set_incomplete"


def test_the_card_carries_its_objectnames(page):
    page.set_build_planner_state(_synthetic_state())
    page.set_recommendations([_set_reco()])
    (row,) = page.reco_card.visible_rows()
    assert page.reco_card.objectName() == "armoryRecoCard"
    assert page.reco_card.title_label.objectName() == "armoryCardTitle"
    assert row.objectName() == "armoryRecoItem"
    assert row.why_button.objectName() == "armoryRecoWhyButton"
    assert row.why_label.objectName() == "armoryRecoWhy"


def test_the_card_is_hidden_with_the_rest_when_there_is_no_build(page):
    page.set_recommendations([_set_reco()])
    page.set_build_planner_state(None)
    assert page.reco_card.isHidden()
    page.set_build_planner_state(_synthetic_state())
    assert not page.reco_card.isHidden()


@pytest.mark.parametrize("value", [None, 7, "not a sequence"])
def test_a_non_sequence_push_is_the_same_as_none_yet(page, value):
    """The host computes these behind a try/except and must be able to say
    "nothing" without inventing a shape."""
    page.set_build_planner_state(_synthetic_state())
    page.set_recommendations(value)
    assert page.recommendations == ()


# ── the host seam ─────────────────────────────────────────────────────────


def test_the_single_writer_pushes_recommendations_too(host):
    """Same M1 reasoning as the summary: one writer, and it tells the page
    everything the page shows."""
    host._set_build_planner_state(_real_state())
    assert isinstance(host.armory_page.recommendations, tuple)


def test_this_clone_has_no_data_pack_so_the_card_says_so(host):
    """Not a hypothetical: ``ItemDatabase/data`` in this repo holds an empty
    ``details/`` and no ``items_all.json``, which is what every fresh clone
    looks like."""
    host._set_build_planner_state(_real_state())
    rows = host.armory_page.reco_card.visible_rows()
    assert len(rows) == 1
    assert rows[0].text_label.text() in (
        tr(host.language, "armory_reco_needs_data"),
        tr(host.language, "armory_reco_empty"),
    )


#: The top-level names of ``ItemDatabase/app.py`` that decide where the
#: Armory reads its catalog and writes its detail cache.  Lifted out of the
#: module by AST rather than imported (importing app.py is a 23 000-line
#: load that monkey-patches Qt) and rather than string-matched (a grep can
#: only prove a line is *present*, never what it computes).
#:
#: ``_migrate_legacy_cache`` and its call site are deliberately NOT lifted:
#: it moves directories on disk, and this test fakes a frozen layout.
_APP_PATH_NAMES = ("_BUNDLE_DIR", "BASE_DIR", "_cache_root", "CACHE_ROOT",
                   "DETAIL_CACHE_DIR")


def _app_py_path_constants(frozen: bool, meipass: Path, executable: Path,
                           cache_parent: Path) -> dict:
    """Run app.py's OWN path arithmetic under a synthetic layout.

    Executes the real statements out of the real file, so a change to
    ``_cache_root()`` or ``_BUNDLE_DIR`` lands here on the next run instead
    of silently diverging from the host.
    """
    import ast
    import types

    from utils import paths as real_paths

    tree = ast.parse((REPO / "ItemDatabase" / "app.py").read_text(encoding="utf-8"))
    wanted: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in _APP_PATH_NAMES:
            wanted.append(node)
        elif isinstance(node, ast.Assign):
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if names & set(_APP_PATH_NAMES):
                wanted.append(node)
        elif isinstance(node, ast.If):
            assigned = {
                t.id
                for inner in ast.walk(node)
                if isinstance(inner, ast.Assign)
                for t in inner.targets
                if isinstance(t, ast.Name)
            }
            if assigned & set(_APP_PATH_NAMES):
                wanted.append(node)
    lifted = [
        n.name if isinstance(n, ast.FunctionDef) else
        [t.id for t in n.targets if isinstance(t, ast.Name)] if isinstance(n, ast.Assign) else
        "if/else"
        for n in wanted
    ]
    assert len(wanted) >= 4, f"app.py's path statements moved — lifted only {lifted}"

    fake_sys = types.SimpleNamespace(executable=str(executable / "Aion2 TM"))
    if frozen:
        fake_sys.frozen = True
        fake_sys._MEIPASS = str(meipass)

    namespace = {"sys": fake_sys, "Path": Path, "__file__": str(
        REPO / "ItemDatabase" / "app.py")}
    original = real_paths.user_cache_dir
    real_paths.user_cache_dir = lambda *a, **k: cache_parent
    try:
        exec(compile(ast.Module(body=wanted, type_ignores=[]), "<app.py paths>", "exec"),
             namespace)
    finally:
        real_paths.user_cache_dir = original
    return namespace


def test_the_two_armory_dirs_mirror_the_armorys_own_constants(host, tmp_path):
    """Catalog **and** details, in source mode **and** frozen mode.

    The version of this test that shipped with the dashboard asserted only
    ``_armory_data_dir() == project_root/ItemDatabase/data`` and grepped for
    the two ``_BUNDLE_DIR`` lines.  It therefore encoded a bug as the
    intended invariant: the provider read ``_MEIPASS/ItemDatabase/data/
    details`` while ``ItemDetailCache`` wrote ``user_cache_dir()/armory/
    details``, so in the only build users install the detail cache the
    recommender reads is empty forever — and this test kept passing,
    because from source those two paths are the same directory.

    Both modes are pinned now, against app.py's own arithmetic rather than
    against a re-typed copy of it.
    """
    sys.path.append(str(REPO / "ItemDatabase"))
    from armory_engine.providers import resolve_armory_dirs

    # ── source mode: the host, and app.py, and the two trees coincide ──
    catalog, details = host._armory_dirs()
    assert catalog == host.project_root / "ItemDatabase" / "data"
    assert details == catalog / "details"
    assert (catalog, details) == (host._armory_data_dir(), host._armory_details_dir())

    from_app = _app_py_path_constants(
        frozen=False, meipass=tmp_path / "meipass",
        executable=tmp_path / "install", cache_parent=tmp_path / "cache")
    assert catalog == from_app["_BUNDLE_DIR"] / "data"
    assert details == from_app["DETAIL_CACHE_DIR"]

    # ── frozen mode: they do NOT coincide, and both sides must agree ──
    meipass = tmp_path / "meipass"
    cache_parent = tmp_path / "cache"
    frozen_app = _app_py_path_constants(
        frozen=True, meipass=meipass,
        executable=tmp_path / "install", cache_parent=cache_parent)
    frozen_catalog, frozen_details = resolve_armory_dirs(
        True, meipass / "ItemDatabase", cache_parent)

    assert frozen_catalog == frozen_app["_BUNDLE_DIR"] / "data"
    assert frozen_details == frozen_app["DETAIL_CACHE_DIR"]
    assert frozen_details != frozen_catalog / "details", (
        "the frozen layout is the whole point: the detail cache is NOT in "
        "the bundle, and a test that lets these be equal cannot see the bug"
    )


def test_the_spec_never_ships_a_details_folder(host):
    """Why the frozen split above is not theoretical.

    ``details/`` is a runtime HTTP cache (~278 MB on a played account) and
    the spec names each data file individually precisely so it can never be
    swept in.  If that ever changes, the frozen provider path becomes a
    judgement call again rather than a fact.
    """
    spec = (REPO / "Aion2 TM.spec").read_text(encoding="utf-8")
    assert "ItemDatabase/data/details" not in spec
    assert "('ItemDatabase/data'," not in spec, (
        "the whole data/ folder is bundled now — re-decide where the "
        "recommender's DiskDetailProvider should read from"
    )


def test_the_engine_is_loaded_once_per_session(host):
    """The recommender runs on every window activation; re-parsing the
    catalog per Alt-Tab is a file parse for a known answer."""
    host._armory_engine_cache = None
    first = host._armory_engine()
    assert host._armory_engine() is first
    host._armory_engine_cache = None


def test_a_failing_engine_degrades_instead_of_breaking_the_window(host, monkeypatch):
    """A dashboard card is not worth an unhandled exception on an
    activation change."""
    class Boom:
        def next_best_actions(self, *args, **kwargs):
            raise RuntimeError("solver exploded")

    monkeypatch.setattr(host, "_armory_engine_cache", (Boom(), None, None))
    assert host._armory_recommendations(_real_state()) == []
    host.armory_page.set_recommendations(host._armory_recommendations(_real_state()))
    assert host.armory_page.recommendations == ()


def test_the_recommendation_card_renders_with_no_fusion_grey(win, qapp):
    """The documented grab (MASTER §4-5 render gate), with a full card: two
    set recommendations, one expanded, one collapsed."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    state = json.loads(REAL_PROFILE.read_text(encoding="utf-8"))["build_planner"]

    win.apply_theme("abyss")
    win.sidebar.set_active_page("armory")
    win._set_build_planner_state(state)
    win.armory_page.set_recommendations([
        _set_reco(),
        _reco(
            "armory_reco_substat_alignment",
            reasons=(
                Reason(stat_id="attack", delta=0.0, weight=1.0,
                       text_key="armory_reason_substat_missing",
                       text_kwargs={"stat": "Attack"}),
                Reason(stat_id="combat speed", delta=0.0, weight=0.0,
                       text_key="armory_reason_slot_off_profile",
                       text_kwargs={"slot": "Gloves", "stat": "Combat Speed"}),
            ),
            aligned=2, total=5, top_n=3,
        ),
        _reco("armory_reco_stat_gap", reasons=(
            Reason(stat_id="CriticalHit", delta=10.0, weight=0.75,
                   text_key="armory_reason_stat_thin",
                   text_kwargs={"stat": "Critical Hit", "slots": 1, "total": 4}),
        ), count=3, gear_type="PvE", role="Angreifer"),
    ])
    win.armory_page.reco_card.visible_rows()[0].why_button.setChecked(True)
    _settle(qapp, 400)

    image = win.grab().toImage()
    destination = SHOTS / "armory_dashboard_reco.png"
    assert image.save(str(destination)), f"could not write {destination}"

    assert not _grey_offenders(image), "Fusion default surfaces on the Armory page"

    card_image = win.armory_page.reco_card.grab().toImage()
    expected = theme.qcolor("abyss", "bg.elevated").rgb() & 0xFFFFFF
    centre = card_image.pixel(card_image.width() // 2, 4) & 0xFFFFFF
    assert centre == expected, (
        f"the Recommendations card ground is {hex(centre)}, expected {hex(expected)}"
    )
    win.armory_page.set_recommendations([])
