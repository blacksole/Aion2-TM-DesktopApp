"""Characterization tests for the enchant / GearScore estimators in
ItemDatabase/app.py (``estimate_enchant_bonus``, ``estimate_exceed_bonus``,
``estimate_armor_bonus``, ``estimate_armor_exceed_bonus``, ``_gearscore_push``).

The calibration data lives in TWO places: the hardcoded constants in app.py
and the documentation pair ``ENCHANT_RATES.md`` / ``ENCHANT_RATES.json`` --
which, per the audit (B-armory.md 1, LOW), no Python file reads. These tests
close that loop: every documented (grade, level -> bonus) row in the JSON is
asserted against the live estimators, so the two sources of truth can no
longer drift apart silently, and the planned move of this block into
``armory_engine/enchant.py`` cannot change a number unnoticed.

Tolerances come from the docs themselves: linear rates are exact; the Unique
weapon curve is a power fit (k=5.733, p=1.355) that ENCHANT_RATES.md states
may miss intermediate points by "~5 Einheiten".

Seams these tests depend on (KEEP THEM STABLE):
  * ``importlib.util.spec_from_file_location("item_database_app",
    ItemDatabase/app.py)`` with a QApplication already alive (module import
    installs a global QComboBox.showPopup monkey-patch).
  * Public-ish names: ``estimate_enchant_bonus``, ``estimate_exceed_bonus``,
    ``estimate_armor_bonus``, ``estimate_armor_exceed_bonus``,
    ``_gearscore_push``, ``_GEARSCORE_NORMAL_RATE``, ``_GEARSCORE_EXCEED_RATE``,
    ``_ACCESSORY_CATEGORIES``, ``_ARMOR_CATEGORIES``, ``_BELT_CATEGORY``.
    If the refactor renames these, update this file in the SAME commit.
  * ``ItemDatabase/ENCHANT_RATES.json`` -- the table these tests read.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_PY = ROOT / "ItemDatabase" / "app.py"
RATES_JSON = ROOT / "ItemDatabase" / "ENCHANT_RATES.json"

# ENCHANT_RATES.md, "Offene Punkte": the Unique weapon curve is a fit whose
# intermediate values may deviate by about 5 units.
UNIQUE_CURVE_TOLERANCE = 5.0
# Linear rates are documented as exact.
EXACT = 1e-9

RATES = json.loads(RATES_JSON.read_text(encoding="utf-8"))

# Real API categoryName values, NOT the German display names used in the docs
# (ENCHANT_RATES.json says "Helmet/Torso/Shoulder/Pants/Boots/Cape"; the code
# keys off "Helm/Top/Pauldrons/Legs/Shoes/Cloak"). Documented drift, pinned
# here so the refactor keeps the code-side names.
A_WEAPON = "Weapon"
AN_ACCESSORY = "Ring"
AN_ARMOR_PIECE = "Top"
A_BELT = "Belt"


@pytest.fixture(scope="module")
def armory(qapp, monkeypatch_module_network):
    module = sys.modules.get("item_database_app")
    if module is None:
        spec = importlib.util.spec_from_file_location("item_database_app", APP_PY)
        module = importlib.util.module_from_spec(spec)
        sys.modules["item_database_app"] = module
        spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def monkeypatch_module_network():
    """No estimator may touch the network; any attempt raises loudly."""
    from PySide6.QtNetwork import QNetworkAccessManager

    patcher = pytest.MonkeyPatch()

    def _no_network(self, *args, **kwargs):
        raise AssertionError("an enchant-model test tried to reach the network")

    patcher.setattr(QNetworkAccessManager, "get", _no_network)
    patcher.setattr(QNetworkAccessManager, "post", _no_network)
    yield
    patcher.undo()


# ---------------------------------------------------------------------------
# weapons / guard -- ENCHANT_RATES.json weapons_and_guard
# ---------------------------------------------------------------------------

WEAPON_LINEAR_GRADES = [
    (grade, spec["rate_per_level"], spec["cap_level"], spec["bonus_at_cap"])
    for grade, spec in RATES["weapons_and_guard"]["by_grade"].items()
    if spec.get("rate_per_level") is not None
]

# The four real calibration samples behind the Unique power fit
# (app.py's own comment block + ENCHANT_RATES.md's "bestätigt (4 Punkte)").
UNIQUE_WEAPON_SAMPLES = [(6, 65), (10, 125), (12, 165), (15, 225)]


@pytest.mark.parametrize("grade,rate,cap,bonus_at_cap", WEAPON_LINEAR_GRADES)
@pytest.mark.parametrize("level", range(1, 21))
def test_linear_weapon_grades_match_the_documented_rate(
    armory, grade, rate, cap, bonus_at_cap, level
):
    expected = rate * min(level, cap)
    assert armory.estimate_enchant_bonus(level, grade, cap, A_WEAPON) == pytest.approx(
        expected, abs=EXACT
    )


@pytest.mark.parametrize("grade,rate,cap,bonus_at_cap", WEAPON_LINEAR_GRADES)
def test_linear_weapon_grades_hit_the_documented_cap_bonus(
    armory, grade, rate, cap, bonus_at_cap
):
    assert armory.estimate_enchant_bonus(cap, grade, cap, A_WEAPON) == pytest.approx(
        bonus_at_cap, abs=EXACT
    )


@pytest.mark.parametrize("level,documented", UNIQUE_WEAPON_SAMPLES)
def test_unique_weapon_curve_reproduces_its_calibration_samples(
    armory, level, documented
):
    cap = RATES["weapons_and_guard"]["by_grade"]["Unique"]["cap_level"]
    actual = armory.estimate_enchant_bonus(level, "Unique", cap, A_WEAPON)
    assert actual == pytest.approx(documented, abs=UNIQUE_CURVE_TOLERANCE)


def test_unique_weapon_cap_bonus_matches_the_table(armory):
    spec = RATES["weapons_and_guard"]["by_grade"]["Unique"]
    actual = armory.estimate_enchant_bonus(
        spec["cap_level"], "Unique", spec["cap_level"], A_WEAPON
    )
    assert actual == pytest.approx(spec["bonus_at_cap"], abs=UNIQUE_CURVE_TOLERANCE)


def test_untested_grades_fall_back_to_the_legend_placeholder(armory):
    """ENCHANT_RATES.md: Common/Rare has no samples; the app uses the Legend
    formula as a placeholder. Unknown grade strings take the same path."""
    legend_rate = RATES["weapons_and_guard"]["by_grade"]["Legend"]["rate_per_level"]
    for grade in ("Common", "Rare", "", "SomethingNew"):
        assert armory.estimate_enchant_bonus(10, grade, 15, A_WEAPON) == pytest.approx(
            legend_rate * 10, abs=EXACT
        )


# ---------------------------------------------------------------------------
# accessories -- ENCHANT_RATES.json accessories
# ---------------------------------------------------------------------------

ACCESSORY_GRADES = [
    (grade, spec["cap_level"], spec["bonus_at_cap"])
    for grade, spec in RATES["accessories"]["by_grade"].items()
]


@pytest.mark.parametrize("grade,cap,bonus_at_cap", ACCESSORY_GRADES)
def test_accessories_scale_at_the_grade_independent_rate(
    armory, grade, cap, bonus_at_cap
):
    rate = RATES["accessories"]["rate_per_level"]
    for level in range(1, cap + 1):
        assert armory.estimate_enchant_bonus(
            level, grade, cap, AN_ACCESSORY
        ) == pytest.approx(rate * level, abs=EXACT)
    assert armory.estimate_enchant_bonus(
        cap, grade, cap, AN_ACCESSORY
    ) == pytest.approx(bonus_at_cap, abs=EXACT)


def test_every_documented_accessory_category_uses_the_accessory_rate(armory):
    documented = set(RATES["accessories"]["categories"])
    assert armory._ACCESSORY_CATEGORIES == documented
    for category in documented:
        assert armory.estimate_enchant_bonus(3, "Heroic", 20, category) == pytest.approx(
            15.0, abs=EXACT
        ), "accessories must not take the Heroic weapon rate"


# ---------------------------------------------------------------------------
# armor + belt -- ENCHANT_RATES.json armor / belt
# ---------------------------------------------------------------------------

ARMOR_GRADES = [
    (grade, spec["cap_level"], spec["defense"], spec["hp"])
    for grade, spec in RATES["armor"]["by_grade"].items()
]
BELT_GRADES = [
    (grade, spec["cap_level"], spec["defense"], spec["hp"])
    for grade, spec in RATES["belt"]["by_grade"].items()
]


@pytest.mark.parametrize("grade,cap,defense,hp", ARMOR_GRADES)
def test_armor_scales_defense_and_hp_at_the_documented_rates(
    armory, grade, cap, defense, hp
):
    for level in range(1, cap + 1):
        got_def, got_hp = armory.estimate_armor_bonus(level, grade, cap, AN_ARMOR_PIECE)
        assert got_def == pytest.approx(defense["rate_per_level"] * level, abs=EXACT)
        assert got_hp == pytest.approx(hp["rate_per_level"] * level, abs=EXACT)

    capped = armory.estimate_armor_bonus(cap, grade, cap, AN_ARMOR_PIECE)
    assert capped == (defense["bonus_at_cap"], hp["bonus_at_cap"])


@pytest.mark.parametrize("grade,cap,defense,hp", BELT_GRADES)
def test_belt_is_grade_independent_with_its_own_cap(armory, grade, cap, defense, hp):
    assert cap == 10
    for level in range(1, cap + 1):
        got_def, got_hp = armory.estimate_armor_bonus(level, grade, cap, A_BELT)
        assert got_def == pytest.approx(defense["rate_per_level"] * level, abs=EXACT)
        assert got_hp == pytest.approx(hp["rate_per_level"] * level, abs=EXACT)

    assert armory.estimate_armor_bonus(cap, grade, cap, A_BELT) == (
        defense["bonus_at_cap"],
        hp["bonus_at_cap"],
    )


def test_armor_category_set_is_the_code_side_api_names(armory):
    """Pinned deliberately: the code keys off shugo.gg categoryName values,
    which are NOT the display names the docs table uses."""
    assert armory._ARMOR_CATEGORIES == {
        "Helm", "Top", "Pauldrons", "Gloves", "Legs", "Shoes", "Cloak",
    }
    assert armory._BELT_CATEGORY == "Belt"


# ---------------------------------------------------------------------------
# invariants: zero, freeze, monotonicity
# ---------------------------------------------------------------------------

EVERY_SHAPE = [
    ("Legend", 15, A_WEAPON),
    ("Unique", 15, A_WEAPON),
    ("Heroic", 20, A_WEAPON),
    ("Legend", 15, AN_ACCESSORY),
    ("Heroic", 20, AN_ACCESSORY),
]


@pytest.mark.parametrize("grade,cap,category", EVERY_SHAPE)
@pytest.mark.parametrize("level", [0, -1, -20])
def test_no_enchant_bonus_at_or_below_level_zero(armory, grade, cap, category, level):
    assert armory.estimate_enchant_bonus(level, grade, cap, category) == 0.0
    assert armory.estimate_armor_bonus(level, grade, cap, AN_ARMOR_PIECE) == (0.0, 0.0)


@pytest.mark.parametrize("grade,cap,category", EVERY_SHAPE)
def test_enchant_bonus_is_non_decreasing_in_level(armory, grade, cap, category):
    values = [
        armory.estimate_enchant_bonus(level, grade, cap, category)
        for level in range(0, 31)
    ]
    assert values == sorted(values)


@pytest.mark.parametrize("grade,cap,category", EVERY_SHAPE)
def test_enchant_bonus_freezes_at_the_items_own_cap(armory, grade, cap, category):
    at_cap = armory.estimate_enchant_bonus(cap, grade, cap, category)
    for level in (cap + 1, cap + 5, cap + 25):
        assert armory.estimate_enchant_bonus(level, grade, cap, category) == at_cap


def test_an_unknown_cap_means_no_freeze_at_all(armory):
    """normal_max_level == 0 is the 'detail data has no maxEnchantLevel' case:
    the curve keeps growing rather than clamping."""
    assert armory.estimate_enchant_bonus(30, "Legend", 0, A_WEAPON) == pytest.approx(
        300.0, abs=EXACT
    )
    assert armory.estimate_armor_bonus(30, "Unique", 0, AN_ARMOR_PIECE) == (900, 600)


def test_armor_bonus_is_non_decreasing_in_level(armory):
    for grade, cap, _, _ in ARMOR_GRADES:
        defenses = []
        hps = []
        for level in range(0, cap + 6):
            got_def, got_hp = armory.estimate_armor_bonus(
                level, grade, cap, AN_ARMOR_PIECE
            )
            defenses.append(got_def)
            hps.append(got_hp)
        assert defenses == sorted(defenses)
        assert hps == sorted(hps)


# ---------------------------------------------------------------------------
# exceed range
# ---------------------------------------------------------------------------

def test_weapon_exceed_lines_match_the_documented_per_step_rates(armory):
    exceed = RATES["weapons_and_guard"]["exceed"]
    for steps in range(1, 6):
        got = armory.estimate_exceed_bonus(15 + steps, 15, A_WEAPON)
        assert got["attack"] == pytest.approx(exceed["Attack"]["per_level"] * steps)
        assert got["attack_pct"] == pytest.approx(
            exceed["Attack increase"]["per_level"] * steps
        )
        assert got["defense"] == 0.0, "weapons gain no Defense line in Exceed"


def test_accessory_exceed_lines_match_the_documented_per_step_rates(armory):
    exceed = RATES["accessories"]["exceed"]
    for steps in range(1, 6):
        got = armory.estimate_exceed_bonus(15 + steps, 15, AN_ACCESSORY)
        assert got["attack"] == pytest.approx(exceed["Attack"]["per_level"] * steps)
        assert got["defense"] == pytest.approx(exceed["Defense"]["per_level"] * steps)
        assert got["attack_pct"] == pytest.approx(
            exceed["Attack increase"]["per_level"] * steps
        )


def test_armor_exceed_lines_match_the_documented_per_step_rates(armory):
    exceed = RATES["armor"]["exceed"]
    for steps in range(1, 6):
        got = armory.estimate_armor_exceed_bonus(20 + steps, 20)
        assert got["defense"] == pytest.approx(exceed["Defense"]["per_level"] * steps)
        assert got["hp"] == pytest.approx(exceed["HP"]["per_level"] * steps)
        assert got["defense_pct"] == pytest.approx(
            exceed["Defense increase"]["per_level"] * steps
        )
        assert got["hp_pct"] == pytest.approx(exceed["HP increase"]["per_level"] * steps)


@pytest.mark.parametrize("level", [0, 1, 14, 15])
def test_no_exceed_bonus_at_or_below_the_cap(armory, level):
    assert armory.estimate_exceed_bonus(level, 15, A_WEAPON) == {
        "attack": 0.0, "attack_pct": 0.0, "defense": 0.0,
    }
    assert armory.estimate_armor_exceed_bonus(level, 15) == {
        "defense": 0.0, "defense_pct": 0.0, "hp": 0.0, "hp_pct": 0.0,
    }


def test_no_exceed_bonus_when_the_cap_is_unknown(armory):
    assert armory.estimate_exceed_bonus(30, 0, A_WEAPON)["attack"] == 0.0
    assert armory.estimate_armor_exceed_bonus(30, 0)["defense"] == 0.0


# ---------------------------------------------------------------------------
# GearScore push
# ---------------------------------------------------------------------------

def test_gearscore_rates_are_the_calibrated_constants(armory):
    assert armory._GEARSCORE_NORMAL_RATE == 1.0
    assert armory._GEARSCORE_EXCEED_RATE == 5.0


@pytest.mark.parametrize("level", [0, -1, -10])
def test_gearscore_push_is_zero_without_enchant(armory, level):
    assert armory._gearscore_push(level, 15) == 0.0


@pytest.mark.parametrize("level", range(1, 16))
def test_gearscore_push_is_one_per_normal_enchant_level(armory, level):
    assert armory._gearscore_push(level, 15) == pytest.approx(float(level), abs=EXACT)


@pytest.mark.parametrize("steps", range(1, 11))
def test_gearscore_push_is_five_per_exceed_step(armory, steps):
    assert armory._gearscore_push(15 + steps, 15) == pytest.approx(
        15.0 + 5.0 * steps, abs=EXACT
    )


def test_gearscore_push_is_grade_and_category_independent(armory):
    """All four real calibration samples (Staff / Guard / Shoulder / Necklace)
    gave the identical rate -- the function takes no grade/category at all."""
    assert armory._gearscore_push(20, 15) == 40.0
    assert armory._gearscore_push(25, 20) == 45.0
    assert armory._gearscore_push(30, 0) == 30.0, "unknown cap = all normal steps"


def test_gearscore_push_is_non_decreasing_in_level(armory):
    values = [armory._gearscore_push(level, 15) for level in range(0, 31)]
    assert values == sorted(values)
