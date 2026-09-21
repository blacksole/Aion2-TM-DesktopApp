"""Golden tests for ``ItemDatabase/armory_engine`` — the Stage-1 extraction.

The contract, and the only reason these numbers are trustworthy: every value
in ``tests/fixtures/armory_engine/golden.json`` was RECORDED by running the
**pre-extraction** ``ItemDatabase/app.py`` — loaded exactly the way the host
loads it, ``spec_from_file_location("item_database_app", …)`` — against the
synthetic inputs in ``tests/fixtures/armory_engine/inputs.py``.  This module
then asserts the extracted pure functions reproduce them exactly.  So a
failure here does not mean "the golden is stale"; it means the move changed
behaviour, which Stage 1 forbids (audit B-armory.md §4.2: "pure code moves,
no behavior change").

Re-recording is therefore a deliberate act, never a fix for a red test.  The
recorder lives in the Stage-1 work notes; regenerating it requires the old
app.py, which is what makes these goldens a one-way ratchet.

No Qt anywhere in this module — that is the point of the extraction, and
``tests/test_armory_engine_qt_free.py`` proves the engine can be imported
without PySide6 even existing.  Here we simply never import it.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "armory_engine"

# The engine is importable the same way app.py makes it importable: its
# parent directory on sys.path.  Done here rather than in conftest so this
# module states its own dependency.
if str(ROOT / "ItemDatabase") not in sys.path:
    sys.path.insert(0, str(ROOT / "ItemDatabase"))
if str(FIXTURES) not in sys.path:
    sys.path.insert(0, str(FIXTURES))

import inputs as F  # noqa: E402  (needs the sys.path insert above)
from armory_engine import arcana, daevanion, enchant, sets, stats, substats, transfer  # noqa: E402

GOLDEN = json.loads((FIXTURES / "golden.json").read_text(encoding="utf-8"))

#: The Unique weapon curve is a power fit (k=5.733, p=1.355) and the totals
#: accumulate floats, so equality is asserted to float tolerance rather than
#: bit-for-bit.  Everything else in here is integers or exact linear rates.
TOL = 1e-9


class DictProvider:
    """A ``DetailProvider`` that is a dict lookup and nothing else.

    The whole value of ``armory_engine.model.DetailProvider`` in one class:
    the stat merge used to need a ``QObject`` holding a
    ``QNetworkAccessManager`` (audit §3.2 item 2), and now needs an object
    with a ``get``.
    """

    def __init__(self, details: dict):
        self._details = details

    def get(self, item_id):
        return self._details.get(item_id)


@pytest.fixture(scope="module")
def provider():
    return DictProvider(F.DETAILS)


# ---------------------------------------------------------------------------
# enchant / exceed / armor / GearScore push
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("row", GOLDEN["enchant"], ids=lambda r: f"{r['grade'] or 'none'}-{r['category'] or 'none'}-{r['cap']}-{r['level']}")
def test_every_estimator_reproduces_its_recorded_value(row):
    level, grade, cap, category = row["level"], row["grade"], row["cap"], row["category"]

    assert enchant.estimate_enchant_bonus(level, grade, cap, category) == pytest.approx(
        row["enchant"], abs=TOL
    )
    assert enchant.estimate_exceed_bonus(level, cap, category) == pytest.approx(row["exceed"], abs=TOL)
    assert list(enchant.estimate_armor_bonus(level, grade, cap, category)) == pytest.approx(
        row["armor"], abs=TOL
    )
    assert enchant.estimate_armor_exceed_bonus(level, cap) == pytest.approx(row["armor_exceed"], abs=TOL)
    assert enchant._gearscore_push(level, cap) == pytest.approx(row["gearscore_push"], abs=TOL)


@pytest.mark.parametrize("row", GOLDEN["rune"], ids=lambda r: f"{r['item_id']}-{r['level']}")
def test_the_rune_curve_reproduces_its_recorded_value(row):
    """The two Runes bypass the generic estimators entirely -- their own
    hand-fitted curve, thresholds and all."""
    assert enchant._rune_enchant_bonus(row["item_id"], row["level"]) == pytest.approx(
        row["bonus"], abs=TOL
    )


def test_the_gearscore_rates_are_the_confirmed_ones():
    """+1.0 per normal enchant level, +5.0 per Exceed step, grade- and
    category-independent -- measured against 4 real equipped items swept
    across enchant 0/5/10/15/20/25.  A constant, so pinned as a constant."""
    assert enchant._GEARSCORE_NORMAL_RATE == 1.0
    assert enchant._GEARSCORE_EXCEED_RATE == 5.0


# ---------------------------------------------------------------------------
# substat auto-pick + priority profiles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case,golden",
    list(zip(F.SUBSTAT_CASES, GOLDEN["substats"])),
    ids=[c["name"] for c in F.SUBSTAT_CASES],
)
def test_the_substat_pick_reproduces_its_recorded_indices(case, golden):
    assert case["name"] == golden["name"], "fixture and golden drifted out of order"
    picked = substats._pick_priority_substats(case["sub_stats"], case["count"], case["priority"])
    assert sorted(picked) == golden["picked"]


def test_the_default_profiles_are_unchanged():
    """Six (Gear-Typ x Rolle) profiles, each a full copy of the per-category
    defaults.  Five of the six are the same PvE/Angreifer guide data (audit
    §2.2) -- pinned as-is, because that is a data decision to revisit, not a
    bug to fix under a refactor."""
    assert substats._default_stat_priority_profiles() == GOLDEN["stat_priority_defaults"]


def test_merging_a_saved_profile_still_drops_junk_and_truncates():
    """An unknown gear_type/role is ignored, a known one is overlaid, and a
    list longer than _STAT_PRIORITY_MAX_ENTRIES is truncated."""
    merged = substats._merge_stat_priority_profiles({
        "PvE": {"Angreifer": {"weapon": ["QA One", "QA Two", "QA Three", "QA Four",
                                         "QA Five", "QA Six", "QA Seven", "QA Eight"]},
                "Nonsense": {"weapon": ["x"]}},
        "Nope": {"Angreifer": {"weapon": ["y"]}},
    })
    assert merged == GOLDEN["stat_priority_merge"]
    assert len(merged["PvE"]["Angreifer"]["weapon"]) == substats._STAT_PRIORITY_MAX_ENTRIES


@pytest.mark.parametrize("raw,expected", sorted(GOLDEN["normalize_stat_name"].items()))
def test_stat_name_normalization_is_unchanged(raw, expected):
    assert substats._normalize_stat_name(raw) == expected


# ---------------------------------------------------------------------------
# the stat merge + GearScore (the DetailProvider seam)
# ---------------------------------------------------------------------------


def test_the_stat_merge_reproduces_its_recorded_totals(provider):
    totals, by_slot = stats.compute_stat_totals_detailed(
        F.EQUIPPED, F.SUBSTATS, F.ENCHANT, provider
    )
    assert totals == pytest.approx(GOLDEN["stat_totals"], abs=TOL)
    assert set(by_slot) == set(GOLDEN["stat_by_slot"])
    for stat_id, slots in GOLDEN["stat_by_slot"].items():
        assert by_slot[stat_id] == pytest.approx(slots, abs=TOL)


def test_the_per_slot_breakdown_sums_to_the_totals(provider):
    """``by_slot`` is not a debugging extra -- it is the attribution the Stat
    Info tooltip renders and a future explanation attributes a delta with
    (see armory_engine.explain).  An attribution that does not add up to the
    number it explains is worse than none."""
    totals, by_slot = stats.compute_stat_totals_detailed(
        F.EQUIPPED, F.SUBSTATS, F.ENCHANT, provider
    )
    for stat_id, value in totals.items():
        assert sum(by_slot[stat_id].values()) == pytest.approx(value, abs=TOL)


def test_the_stat_merge_reproduces_its_recorded_totals_unenchanted(provider):
    totals, by_slot = stats.compute_stat_totals_detailed(F.EQUIPPED, F.SUBSTATS, {}, provider)
    assert totals == pytest.approx(GOLDEN["stat_totals_unenchanted"], abs=TOL)
    assert set(by_slot) == set(GOLDEN["stat_by_slot_unenchanted"])


def test_the_gearscore_reproduces_its_recorded_value(provider):
    assert stats.compute_gearscore(F.EQUIPPED, F.ENCHANT, provider) == pytest.approx(
        GOLDEN["gearscore"], abs=TOL
    )
    assert stats.compute_gearscore(F.EQUIPPED, {}, provider) == pytest.approx(
        GOLDEN["gearscore_unenchanted"], abs=TOL
    )


def test_an_unresolvable_slot_is_skipped_not_raised(provider):
    """A cold detail cache is the normal state on first paint: ``Cloak`` in
    the fixture points at an id the provider knows nothing about, and the
    merge must simply not contribute it."""
    _totals, by_slot = stats.compute_stat_totals_detailed(
        F.EQUIPPED, F.SUBSTATS, F.ENCHANT, provider
    )
    assert "Cloak" not in {slot for slots in by_slot.values() for slot in slots}


def test_an_empty_build_is_empty(provider):
    assert list(stats.compute_stat_totals_detailed({}, {}, {}, provider)) == [{}, {}]
    assert stats.compute_gearscore({}, {}, provider) == 0.0


@pytest.mark.parametrize("raw,expected", sorted(GOLDEN["parse_stat_value"].items()))
def test_stat_value_parsing_is_unchanged(raw, expected):
    assert stats._parse_stat_value(raw) == pytest.approx(expected, abs=TOL)


# ---------------------------------------------------------------------------
# the transfer graph + material trees
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def indexes():
    output_index = transfer._build_recipe_output_index(F.RECIPES)
    source_index = transfer._build_transfer_source_index(F.RECIPES, F.ITEMS_BY_ID, output_index)
    return output_index, source_index


def test_the_output_index_reproduces_its_recorded_mapping(indexes):
    output_index, _source = indexes
    assert {name: r["id"] for name, r in output_index.items()} == GOLDEN["output_index"]


def test_the_upgrade_hop_index_reproduces_its_recorded_mapping(indexes):
    """The Kinah-only hop (recipe 3, no Transfer Stone) must be in here, and
    the decoy (recipe 5, one qty-1 craftable input but a different type
    word) must not."""
    _output, source_index = indexes
    assert {s: [r["id"] for r in rs] for s, rs in source_index.items()} == GOLDEN["transfer_source_index"]
    assert 3 in source_index["Fine QA Boots"][0:1] or any(
        r["id"] == 3 for r in source_index["Fine QA Boots"]
    )
    assert all(r["id"] != 5 for rs in source_index.values() for r in rs)


@pytest.mark.parametrize("row", GOLDEN["transfer_source_names"].items(), ids=lambda kv: f"recipe{kv[0]}")
def test_upgrade_hop_detection_is_unchanged(indexes, row):
    output_index, _source = indexes
    recipe_id, expected = row
    recipe = next(r for r in F.RECIPES if str(r["id"]) == recipe_id)
    assert transfer._transfer_source_name(recipe, F.ITEMS_BY_ID, output_index) == expected


@pytest.mark.parametrize("row", GOLDEN["transfer_paths"], ids=lambda r: f"{r['start']}->{r['target']}")
def test_the_bfs_reproduces_its_recorded_path(indexes, row):
    _output, source_index = indexes
    path = transfer._find_transfer_path(row["start"], row["target"], source_index)
    assert (None if path is None else [r["id"] for r in path]) == row["path"]


def test_the_tier_chain_reproduces_its_recorded_order(indexes):
    _output, source_index = indexes
    assert transfer._ordered_tier_chain("Plain QA Boots", "Boots", source_index) == GOLDEN["tier_chain"]


@pytest.mark.parametrize("name", sorted(GOLDEN["material_trees"]))
def test_the_material_tree_reproduces_its_recorded_shape(indexes, name):
    output_index, _source = indexes
    tree = transfer._build_material_tree(output_index[name], output_index, F.ITEMS_BY_ID)
    assert tree == GOLDEN["material_trees"][name]


@pytest.mark.parametrize("key", sorted(GOLDEN["material_flat"]))
def test_flattening_and_the_kinah_rollup_are_unchanged(indexes, key):
    output_index, _source = indexes
    name, qty = key.rsplit("|", 1)
    tree = transfer._build_material_tree(output_index[name], output_index, F.ITEMS_BY_ID)
    totals = {}
    transfer._flatten_material_tree(tree, int(qty), totals)
    assert totals == GOLDEN["material_flat"][key]
    assert transfer._compute_tree_kinah(tree, int(qty)) == GOLDEN["tree_kinah"][key]


@pytest.mark.parametrize("raw,expected", sorted(GOLDEN["item_type_word"].items()))
def test_the_item_type_word_is_unchanged(raw, expected):
    assert transfer._item_type_word(raw) == expected


@pytest.mark.parametrize("raw,expected", sorted(GOLDEN["parse_gold_cost"].items()))
def test_gold_cost_parsing_is_unchanged(raw, expected):
    assert transfer._parse_gold_cost(None if raw == "None" else raw) == expected


# ---------------------------------------------------------------------------
# the Daevanion router
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def board():
    return F.daevanion_grid(), F.daevanion_node_by_id()


def test_the_board_cap_is_unchanged(board):
    grid, _by_id = board
    assert daevanion._daevanion_total_cost(grid) == GOLDEN["daevanion_total_cost"]
    assert daevanion._daevanion_spent_cost({"n00", "n01", "n22"}, _by_id) == GOLDEN["daevanion_spent_cost"]


@pytest.mark.parametrize("node_id,expected", sorted(GOLDEN["daevanion_mp_counts"].items()))
def test_the_max_mp_tiebreak_input_is_unchanged(board, node_id, expected):
    _grid, by_id = board
    assert daevanion._daevanion_node_mp_count(by_id[node_id]) == expected


@pytest.mark.parametrize("node_id,expected", sorted(GOLDEN["daevanion_reachable"].items()))
def test_reachability_is_unchanged(board, node_id, expected):
    """Only nodes with a real stat/skill value connect to each other -- an
    "empty" cell can never bridge two others."""
    grid, by_id = board
    assert daevanion._daevanion_is_reachable(by_id[node_id], grid, {"n00", "n21"}) is expected


def test_the_dijkstra_reproduces_its_recorded_distances_and_parents(board):
    """``dist`` AND ``prev``.  ``prev`` is the sensitive half: it decides
    which of several equal-cost paths is materialized, and therefore which
    nodes enter the tree.  It is why there is no heapq in this module -- see
    the module docstring of armory_engine.daevanion."""
    grid, by_id = board
    dist, prev = daevanion._daevanion_shortest_from_tree(grid, {F.DAEVANION_START_ID}, by_id)
    recorded = {
        nid: (None if d[0] == float("inf") else list(d)) for nid, d in dist.items()
    }
    assert recorded == GOLDEN["daevanion_dist_from_start"]
    assert prev == GOLDEN["daevanion_prev_from_start"]


@pytest.mark.parametrize("golden", GOLDEN["daevanion_routes"], ids=lambda g: g["name"])
def test_the_auto_route_reproduces_its_recorded_route(board, golden):
    grid, by_id = board
    case = next(c for c in F.DAEVANION_CASES if c["name"] == golden["name"])
    result = daevanion._daevanion_compute_auto_route(
        grid, by_id, set(case["wanted"]), F.DAEVANION_START_ID
    )
    assert sorted(result["tree"]) == golden["tree"]
    assert sorted(result["included"]) == golden["included"]
    assert sorted(result["skipped"]) == golden["skipped"]
    assert result["spent"] == golden["spent"]
    assert result["cap"] == golden["cap"]


def test_an_unreachable_target_makes_the_router_abandon_the_rest(board):
    """Documented behaviour, and a documented limitation (audit §2.4, LOW):
    when it cannot connect the next wanted node the router abandons ALL
    remaining ones at once instead of trying cheaper subsets.

    Worth stating precisely, because the audit calls this "when the cap is
    hit" and the cap can never actually be hit: ``cap`` is
    ``sum(cost for every node on the board)`` and the tree is a subset of the
    board, so ``spent <= cap`` always holds.  The branch is reached only by
    an UNREACHABLE target -- n44, walled off behind two "empty" cells in the
    fixture.  Pinned so that changing it is a decision, not a side effect.
    """
    grid, by_id = board
    case = next(c for c in F.DAEVANION_CASES if c["name"] == "unreachable")
    result = daevanion._daevanion_compute_auto_route(
        grid, by_id, set(case["wanted"]), F.DAEVANION_START_ID
    )
    assert result["skipped"] == {"n44"}
    assert result["included"] == {"n04", "n22"}
    assert result["spent"] <= result["cap"]


@pytest.mark.parametrize("golden", GOLDEN["daevanion_routes"], ids=lambda g: g["name"])
def test_the_router_never_spends_more_than_the_board_cap(golden):
    assert golden["spent"] <= golden["cap"]


@pytest.mark.parametrize("golden", GOLDEN["daevanion_random"], ids=lambda g: f"seed{g['seed']}")
def test_the_router_reproduces_its_recorded_route_on_a_random_board(golden):
    """Twelve seeded 6x6 boards with punched-out cells, varied costs and a
    random Max-MP spread -- breadth the hand-built board cannot give, and the
    regression net under the heapq question the module docstring settles."""
    grid = {(n["r"], n["c"]): n for n in golden["nodes"]}
    by_id = {n["id"]: n for n in golden["nodes"]}
    start = next(n["id"] for n in golden["nodes"] if n["g"] == "start")
    result = daevanion._daevanion_compute_auto_route(grid, by_id, set(golden["wanted"]), start)
    assert sorted(result["tree"]) == golden["tree"]
    assert sorted(result["included"]) == golden["included"]
    assert sorted(result["skipped"]) == golden["skipped"]
    assert result["spent"] == golden["spent"]


# ---------------------------------------------------------------------------
# the Arcana solver
# ---------------------------------------------------------------------------


def test_the_usable_lord_types_are_unchanged():
    """Scales has no Vigor/Magic entry, so Season 1's real usable total is 5
    of 6 -- data-driven from the theme map, not a hardcoded count."""
    usable = arcana._arcana_usable_lord_types(F.ARCANA_THEME_MAP, {"Vigor", "Magic"})
    assert usable == GOLDEN["arcana_usable_types"]
    assert "Scales" not in usable


@pytest.mark.parametrize("golden", GOLDEN["arcana"], ids=lambda g: g["name"])
def test_the_solver_reproduces_its_recorded_combinations(golden):
    usable = GOLDEN["arcana_usable_types"]
    wishes = next(c["wishes"] for c in F.ARCANA_CASES if c["name"] == golden["name"])
    combos = arcana._arcana_compute_combinations(
        usable, F.ARCANA_TYPE_TO_THEME, F.ARCANA_CLASS_SKILL_POOLS, wishes,
        F.ARCANA_SKILL_TYPE_BY_ID, F.ARCANA_PRIORITY_RANK,
    )
    assert len(combos) == len(golden["combinations"])
    for combo, expected in zip(combos, golden["combinations"]):
        assert combo["covered"] == expected["covered"]
        assert len(combo["assignments"]) == len(expected["assignments"])
        for assignment, expected_assignment in zip(combo["assignments"], expected["assignments"]):
            assert assignment["type"] == expected_assignment["type"]
            assert assignment["theme"] == expected_assignment["theme"]
            assert assignment["skill_ids"] == expected_assignment["skill_ids"]
            assert sorted(assignment["need_based_ids"]) == expected_assignment["need_based_ids"]
        assert arcana._arcana_result_coverage_percent(combo, wishes) == pytest.approx(
            expected["coverage_percent"], abs=TOL
        )


@pytest.mark.parametrize("golden", GOLDEN["arcana"], ids=lambda g: g["name"])
def test_every_card_spends_its_whole_budget_within_the_per_skill_cap(golden):
    """User-Wunsch, "Immer alle 5 verteilen": a card's 4 slots start at
    baseline 1 and the shared 5-point budget is spent down even once every
    wish is met -- unless every chosen skill has hit the per-skill cap of 4.
    Checked as an invariant over the recorded results rather than re-derived,
    so it also guards the goldens themselves."""
    for combo in golden["combinations"]:
        for assignment in combo["assignments"]:
            values = assignment["skill_ids"]
            assert len(values) <= arcana._ARCANA_SKILL_SLOTS_PER_CARD
            assert all(arcana._ARCANA_SKILL_BASELINE <= v <= arcana._ARCANA_PER_SKILL_CAP
                       for v in values.values())
            spent = sum(v - arcana._ARCANA_SKILL_BASELINE for v in values.values())
            capped_out = all(v == arcana._ARCANA_PER_SKILL_CAP for v in values.values())
            assert spent == arcana._ARCANA_CARD_EXTRA_BUDGET or capped_out, (
                f"{assignment['type']} spent {spent} of {arcana._ARCANA_CARD_EXTRA_BUDGET}"
            )


@pytest.mark.parametrize("golden", GOLDEN["arcana"], ids=lambda g: g["name"])
def test_the_ceilings_and_eligibility_are_unchanged(golden):
    usable = GOLDEN["arcana_usable_types"]
    for skill_id, expected in golden["ceilings"].items():
        category = F.ARCANA_SKILL_TYPE_BY_ID.get(skill_id)
        assert arcana._arcana_max_ceiling(
            skill_id, category, usable, F.ARCANA_CLASS_SKILL_POOLS
        ) == expected
    for skill_id, expected in golden["eligible_types"].items():
        category = F.ARCANA_SKILL_TYPE_BY_ID.get(skill_id)
        assert arcana._arcana_eligible_types(
            skill_id, category, usable, F.ARCANA_CLASS_SKILL_POOLS
        ) == expected


@pytest.mark.parametrize("golden", GOLDEN["arcana"], ids=lambda g: g["name"])
def test_the_uncovered_reason_tiers_are_unchanged(golden):
    """Three tiers: no eligible card at all / an eligible card exists but
    cannot reach the wish even dedicated to it / it could, just not in this
    combination.  Returned as a (translation key, kwargs) pair, never as
    display text."""
    usable = GOLDEN["arcana_usable_types"]
    wishes = next(c["wishes"] for c in F.ARCANA_CASES if c["name"] == golden["name"])
    combos = arcana._arcana_compute_combinations(
        usable, F.ARCANA_TYPE_TO_THEME, F.ARCANA_CLASS_SKILL_POOLS, wishes,
        F.ARCANA_SKILL_TYPE_BY_ID, F.ARCANA_PRIORITY_RANK,
    )
    for skill_id, wish in wishes.items():
        covered = combos[0]["covered"].get(skill_id, 0) if combos else 0
        key, kwargs = arcana._arcana_uncovered_reason(
            skill_id, wish, covered, usable, F.ARCANA_CLASS_SKILL_POOLS, F.ARCANA_SKILL_TYPE_BY_ID,
        )
        assert [key, kwargs] == golden["uncovered_reasons"][skill_id]
        assert key.startswith("arm_arcana_reason_"), "a reason must be a translation key"


def test_a_skill_no_usable_type_can_roll_reports_the_structural_reason():
    """``s_dash`` lives only in Compass and Scales; Scales is out of Season 1
    and Compass's pool does carry it -- so the "impossible" case is really
    about the wish COMPETING, and the structural tier needs a skill no
    usable pool has at all."""
    usable = GOLDEN["arcana_usable_types"]
    key, kwargs = arcana._arcana_uncovered_reason(
        "s_not_in_any_pool", 4, 0, usable, F.ARCANA_CLASS_SKILL_POOLS, F.ARCANA_SKILL_TYPE_BY_ID,
    )
    assert key == "arm_arcana_reason_no_card"
    assert kwargs == {}


@pytest.mark.parametrize("index", range(len(GOLDEN["arcana_card_slots"])))
def test_the_card_slot_migration_is_unchanged(index):
    """Always exactly 4 positional entries, and the older
    ``{"skill_ids": {...}}`` shape (still in any profile saved before
    per-slot editing existed) still migrates on the fly."""
    card_data = [
        None,
        {},
        {"skill_ids": {"s_dark": 4, "s_rush": 2}},
        {"slots": [{"skill_id": "s_dark", "level": 4}, None, None, None]},
        {"slots": [{"skill_id": "s_a", "level": 1}] * 6},
    ][index]
    slots = arcana._arcana_card_slot_list(card_data)
    assert slots == GOLDEN["arcana_card_slots"][index]
    assert len(slots) == arcana._ARCANA_SKILL_SLOTS_PER_CARD


def test_the_derived_card_level_is_unchanged():
    """A card's Level is derived from the points its slots sit above
    baseline, clamped at its grade's own max -- not stored separately."""
    card_data = [
        None,
        {"grade": "Unique", "slots": [{"skill_id": "s_dark", "level": 4},
                                      {"skill_id": "s_rush", "level": 2}, None, None]},
        {"grade": "Rare", "slots": [{"skill_id": "s_dark", "level": 4},
                                    {"skill_id": "s_rush", "level": 4}, None, None]},
        {"grade": "Legend", "slots": [{"skill_id": "s_dark", "level": 1}, None, None, None]},
    ]
    assert [arcana._arcana_card_level(c) for c in card_data] == GOLDEN["arcana_card_level"]
    assert [arcana._arcana_card_grade(c) for c in (None, {}, {"grade": "Rare"})] == (
        GOLDEN["arcana_card_grade"]
    )


def test_the_per_type_pools_are_unchanged():
    usable = GOLDEN["arcana_usable_types"]
    wishes = F.ARCANA_CASES[1]["wishes"]
    eligible = {
        ct: arcana._arcana_eligible_skills_for_type(
            ct, wishes, F.ARCANA_CLASS_SKILL_POOLS, F.ARCANA_SKILL_TYPE_BY_ID
        )
        for ct in usable
    }
    assert eligible == GOLDEN["arcana_eligible_skills"]
    assert {ct: arcana._arcana_full_pool_for_type(ct, F.ARCANA_CLASS_SKILL_POOLS)
            for ct in usable} == GOLDEN["arcana_full_pools"]


def test_a_passive_only_card_never_offers_an_active_skill():
    """``_ARCANA_LORD_CATEGORY`` is a hard filter, not a preference: Bell and
    Mirror are passive-only, Parchment/Compass/Scales active-only, Chalice
    both.  Derived from the fixture rather than pinned, so it keeps holding
    if the pools change."""
    for card_type, category in arcana._ARCANA_LORD_CATEGORY.items():
        if category == "both" or card_type not in F.ARCANA_CLASS_SKILL_POOLS:
            continue
        wishes = {sid: 4 for sid in F.ARCANA_SKILL_TYPE_BY_ID}
        eligible = arcana._arcana_eligible_skills_for_type(
            card_type, wishes, F.ARCANA_CLASS_SKILL_POOLS, F.ARCANA_SKILL_TYPE_BY_ID
        )
        assert all(F.ARCANA_SKILL_TYPE_BY_ID[sid] == category for sid in eligible), card_type


# ---------------------------------------------------------------------------
# dungeon sets
# ---------------------------------------------------------------------------


def test_a_missing_dungeon_sets_file_degrades_to_empty(tmp_path):
    """A dev checkout that has not run ``compute_dungeon_sets.py`` must get
    an empty dropdown and a warning -- never the ~17 s live scan this
    replaced, and never an exception."""
    missing = tmp_path / "nope" / "dungeon_sets.json"
    assert sets._build_dungeon_sets({}, None, path=missing) == {}


def test_the_dungeon_sets_file_is_read_and_passed_through(tmp_path):
    written = {"Expedition": {"Abyssal": "Unique"}, "Sanctuary": {"Radiant": "Legend"}}
    path = tmp_path / "dungeon_sets.json"
    path.write_text(json.dumps(written), encoding="utf-8")
    assert sets._build_dungeon_sets({}, None, path=path) == written


def test_a_corrupt_dungeon_sets_file_degrades_to_empty(tmp_path):
    path = tmp_path / "dungeon_sets.json"
    path.write_text("{not json", encoding="utf-8")
    assert sets._build_dungeon_sets({}, None, path=path) == {}


def test_the_dungeon_sets_path_points_beside_app_py():
    """The path is resolved from the PACKAGE's location, so it has to land on
    the same ``ItemDatabase/data/`` app.py's own ``Path(__file__).parent``
    gave -- in a checkout and under ``_MEIPASS/ItemDatabase/`` alike."""
    assert sets.DUNGEON_SETS_PATH == ROOT / "ItemDatabase" / "data" / "dungeon_sets.json"


def test_the_detail_provider_protocol_accepts_the_dict_stub(provider):
    """``DetailProvider`` is structural: satisfying it is having a ``get``.
    That is what lets ItemDetailCache stay a QObject and the engine stay
    Qt-free."""
    from armory_engine.model import DetailProvider

    assert isinstance(provider, DetailProvider)
