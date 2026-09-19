"""Stage 2 of the Armory engine: role weights, stat coverage, set completion.

The contract here is the OPPOSITE of ``tests/test_armory_engine_golden.py``'s
and the difference matters.  Those goldens were *recorded* from the
pre-extraction app.py, which is what makes them a one-way ratchet against a
behaviour change during a move.  Stage 2 is new behaviour, so there is
nothing to record: every number below is derived **by hand** from
``tests/fixtures/armory_engine/reco_inputs.py``, with the arithmetic written
into the assertion or the comment above it.  A recorded expectation would
only prove the code still does whatever it did the first time it ran.

Three groups:

1. ``score`` — the weight vector (a pure function of rank), the coverage
   ranking, and the substat alignment.
2. ``recommend`` — set completion, and ``next_best_actions``' orchestration
   and its four documented degradation paths.
3. ``providers`` — the disk provider and the bundle, against a temporary
   data pack built by the test, plus the absent-pack case that is this
   clone's actual state.

No Qt is imported anywhere in this module — that is the engine's whole
point, and ``tests/test_armory_engine_qt_free.py`` proves the modules could
not import it even if they tried.
"""

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "armory_engine"

# Same two inserts the golden module makes, and for the same reason: the
# engine is importable exactly the way app.py makes it importable.
if str(ROOT / "ItemDatabase") not in sys.path:
    sys.path.insert(0, str(ROOT / "ItemDatabase"))
if str(FIXTURES) not in sys.path:
    sys.path.insert(0, str(FIXTURES))

import reco_inputs as F  # noqa: E402  (needs the sys.path insert above)
from armory_engine import providers, recommend, score, stats  # noqa: E402
from armory_engine.explain import Reason, Recommendation  # noqa: E402

TOL = 1e-12


def _weights():
    """{'attack': 1.0, 'critical hit': .75, 'smite': .5625, 'move speed': .421875}"""
    return score.merge_role_weights(F.PROFILE_CATEGORIES)


def _names():
    return score.display_names(F.PROFILE_CATEGORIES)


def _totals():
    return stats.compute_stat_totals_detailed(
        F.EQUIPPED_AS_ITEMS,
        {slot: set(indices) for slot, indices in F.SUBSTATS.items()},
        {},
        F.DictProvider(),
    )


# ---------------------------------------------------------------------------
# 1. score — weights
# ---------------------------------------------------------------------------


def test_role_weights_decay_geometrically_from_one():
    weights = score.role_weights(["Attack", "Critical Hit", "Smite"])
    assert list(weights) == ["attack", "critical hit", "smite"]
    assert weights["attack"] == 1.0
    assert weights["critical hit"] == pytest.approx(0.75)
    assert weights["smite"] == pytest.approx(0.5625)  # 0.75 ** 2


def test_role_weights_normalize_through_the_substat_alias_table():
    """The auto-pick matches case-insensitively and rewrites "movement speed"
    (``substats._STAT_NAME_ALIASES``).  A weight vector that disagreed would
    explain a pick the app never made."""
    weights = score.role_weights(["MOVEMENT SPEED", "  Attack  "])
    assert set(weights) == {"move speed", "attack"}
    assert weights["move speed"] == 1.0


def test_a_repeated_name_keeps_its_best_rank_and_consumes_none():
    """A duplicate must not silently demote everything after it."""
    weights = score.role_weights(["Attack", "attack", "Critical Hit"])
    assert weights == {"attack": 1.0, "critical hit": pytest.approx(0.75)}


def test_role_weights_of_an_empty_profile_is_empty():
    assert score.role_weights([]) == {}
    assert score.role_weights(None) == {}


@pytest.mark.parametrize("decay", [0.0, -0.5, 1.5])
def test_an_impossible_decay_is_refused(decay):
    with pytest.raises(ValueError):
        score.role_weights(["Attack"], decay=decay)


def test_a_decay_of_one_makes_every_rank_equal():
    """The degenerate case is legal: it says "ranked, but I mean all of them"."""
    assert score.role_weights(["A", "B", "C"], decay=1.0) == {"a": 1.0, "b": 1.0, "c": 1.0}


def test_merge_takes_the_best_rank_a_stat_reaches_in_any_category():
    """Attack is rank 1 for the helmet and rank 2 for the boots -> 1.0."""
    merged = score.merge_role_weights(
        {"helmet": ["Attack", "Smite"], "boots": ["Move Speed", "Attack"]}
    )
    assert merged == {"attack": 1.0, "smite": pytest.approx(0.75), "move speed": 1.0}


def test_display_names_keep_the_spelling_the_profile_used():
    assert _names()["move speed"] == "Movement Speed"
    assert _names()["critical hit"] == "Critical Hit"


@pytest.mark.parametrize(
    ("stat_id", "expected"),
    [
        ("CriticalHit", "critical hit"),
        ("MoveSpeed", "move speed"),
        ("DamageRatio", "damage ratio"),
        ("HPRegen", "hp regen"),
        ("Attack", "attack"),
        ("", ""),
    ],
)
def test_a_stat_id_folds_onto_the_name_space(stat_id, expected):
    assert score.normalize_stat_id(stat_id) == expected


def test_the_name_index_uses_the_totals_spelling_not_the_pieces():
    """``compute_stat_totals_detailed`` rewrites "Defense" to "DefenseBonus"
    (``_GEAR_STAT_ID_ALIASES``).  An index keyed by the raw spelling would
    fail to join on exactly the stats the alias table exists for — and fail
    silently, as "the build carries none of it"."""
    index = score.stat_name_index([F.DETAILS[103]])
    assert index["DefenseBonus"] == "defense increase"
    assert "Defense" not in index


# ---------------------------------------------------------------------------
# 1b. score — the coverage ranking
# ---------------------------------------------------------------------------


def test_the_stat_gap_ranks_by_weight_times_missing_slot_coverage():
    """Hand-computed from reco_inputs, 4 equipped slots:

    Critical Hit  0.75     x (1 - 1/4) = 0.5625      (Helmet only)
    Smite         0.5625   x (1 - 1/4) = 0.421875    (Helmet only)
    Move Speed    0.421875 x (1 - 1/4) = 0.31640625  (Boots only)
    Attack        1.0      x (1 - 3/4) = 0.25        (Helmet, Gloves, Ring1)

    Attack last despite the top weight is the whole point: the build really
    does carry it everywhere, and a recommendation that led with the stat
    three of four pieces already provide would be noise.
    """
    totals, by_slot = _totals()
    ranked = score.stat_gap_ranked(
        totals,
        _weights(),
        by_slot=by_slot,
        slots=tuple(sorted(F.EQUIPPED)),
        index=score.stat_name_index(F.DETAILS.values()),
        names=_names(),
        top_k=4,
    )
    assert [reason.stat_id for _, reason in ranked] == [
        "CriticalHit", "Smite", "MoveSpeed", "Attack",
    ]
    assert [shortfall for shortfall, _ in ranked] == [
        pytest.approx(0.5625), pytest.approx(0.421875),
        pytest.approx(0.31640625), pytest.approx(0.25),
    ]


def test_each_gap_reason_carries_the_current_value_and_its_attribution():
    totals, by_slot = _totals()
    reasons = score.stat_gap(
        totals, _weights(), by_slot=by_slot, slots=tuple(sorted(F.EQUIPPED)),
        index=score.stat_name_index(F.DETAILS.values()), names=_names(), top_k=1,
    )
    (reason,) = reasons
    assert isinstance(reason, Reason)
    assert reason.delta == 10.0  # the Critical Hit the Helmet substat carries
    assert reason.weight == pytest.approx(0.75)
    assert reason.text_key == score.REASON_STAT_THIN
    assert reason.text_kwargs == {"stat": "Critical Hit", "slots": 1, "total": 4}


def test_a_stat_no_slot_carries_is_reported_as_absent_at_full_weight():
    """The unit-free finding: no combat model is needed to know that nothing
    equipped provides Block."""
    reasons = score.stat_gap(
        {"Attack": 100.0},
        {"attack": 1.0, "block": 0.75},
        by_slot={"Attack": {"Helmet": 100.0}},
        slots=("Helmet",),
        top_k=2,
    )
    assert [reason.text_key for reason in reasons] == [score.REASON_STAT_ABSENT]
    assert reasons[0].stat_id == "block"  # nothing to join onto yet
    assert reasons[0].delta == 0.0
    assert reasons[0].text_kwargs["slots"] == 0


def test_top_k_bounds_the_report():
    totals, by_slot = _totals()
    assert len(score.stat_gap(totals, _weights(), by_slot=by_slot, top_k=2)) == 2
    assert score.stat_gap(totals, _weights(), by_slot=by_slot, top_k=0) == []


def test_a_reference_build_switches_the_gap_to_the_one_legal_magnitude():
    """Same stat, same units -> a ratio that means something.  650 against a
    baseline of 1000 is 35 % short, weighted 1.0."""
    reasons = score.stat_gap(
        {"Attack": 650.0}, {"attack": 1.0}, {"Attack": 1000.0}, top_k=3
    )
    (reason,) = reasons
    assert reason.text_key == score.REASON_STAT_BEHIND
    assert reason.text_kwargs["value"] == 650.0
    assert reason.text_kwargs["reference"] == 1000.0


def test_a_build_ahead_of_its_reference_reports_nothing():
    assert score.stat_gap({"Attack": 1200.0}, {"attack": 1.0}, {"Attack": 1000.0}) == []


def test_two_stat_ids_that_share_a_name_are_summed_not_double_counted():
    """The catalog really does this: "Attack" is a main-stat id on one piece
    and a substat id on another."""
    reasons = score.stat_gap(
        {"Attack": 100.0, "WeaponFixingDamage": 50.0},
        {"attack": 1.0},
        by_slot={"Attack": {"Ring1": 100.0}, "WeaponFixingDamage": {"MainHand": 50.0}},
        slots=("Ring1", "MainHand", "Helmet"),
        index={"Attack": "attack", "WeaponFixingDamage": "attack"},
        top_k=1,
    )
    assert reasons[0].delta == 150.0
    assert reasons[0].text_kwargs["slots"] == 2


# ---------------------------------------------------------------------------
# 1c. score — substat alignment
# ---------------------------------------------------------------------------


def _alignment():
    return score.substat_alignment(
        {
            "Helmet": ["Critical Hit", "Smite"],
            "Gloves": ["Combat Speed"],
            "Boots": ["Move Speed"],
            "Ring1": ["Accuracy"],
        },
        _weights(),
        names=_names(),
    )


def test_substat_alignment_counts_the_share_inside_the_profile_top_n():
    """5 picks, of which Critical Hit and Smite are in the top 3
    (attack > critical hit > smite) -> 2/5 = 0.4 aligned, 0.6 on the table."""
    alignment = _alignment()
    assert isinstance(alignment, Recommendation)
    assert alignment.pick["aligned"] == 2
    assert alignment.pick["total"] == 5
    assert alignment.pick["share"] == pytest.approx(0.4)
    assert alignment.score_delta == pytest.approx(0.6)
    assert alignment.text_key == score.RECO_SUBSTAT_ALIGNMENT


def test_substat_alignment_names_the_slots_that_are_entirely_off_profile():
    """Gloves (Combat Speed) and Ring1 (Accuracy) pick nothing the profile
    ranks at all; Boots picks Move Speed, which is ranked 4th — in the
    profile, just not in its top 3 — so Boots is NOT off-profile."""
    alignment = _alignment()
    assert alignment.pick["off_profile_slots"] == ("Gloves", "Ring1")
    assert alignment.pick["missing"] == ("attack",)


def test_every_alignment_reason_is_renderable():
    alignment = _alignment()
    assert [reason.text_key for reason in alignment.reasons] == [
        score.REASON_STAT_SUBSTAT_MISSING,
        score.REASON_SLOT_OFF_PROFILE,
        score.REASON_SLOT_OFF_PROFILE,
    ]
    # The catalog spelling, not the normalized key, for a stat the profile
    # never mentions and therefore has no player spelling for.
    assert alignment.reasons[1].text_kwargs == {"slot": "Gloves", "stat": "Combat Speed"}


def test_an_empty_substat_sheet_is_a_zero_recommendation_with_no_headline():
    """No detail resolvable -> nothing to say, and ``next_best_actions``
    drops it rather than showing a card about nothing."""
    alignment = score.substat_alignment({}, _weights())
    assert alignment.score_delta == 0.0
    assert alignment.reasons == ()
    assert alignment.text_key == ""


# ---------------------------------------------------------------------------
# 2. recommend — set completion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Abyssal Helm", ("Abyssal", "Helm")),
        ("Corrupted Judicator Boots", ("Corrupted Judicator", "Boots")),
        ("Fierce Battle Amulet", ("Fierce Battle", "Amulet")),
        ("Helm", None),          # the word alone is not "<root> <word>"
        ("Abyssal Helmet", None),  # "Helmet" is not a set slot word
        ("", None),
    ],
)
def test_the_set_root_is_the_name_minus_its_trailing_slot_word(name, expected):
    assert recommend.set_root(name) == expected


def test_the_slot_word_mirror_matches_the_script_that_writes_the_file():
    """``dungeon_sets.json``'s roots were derived by stripping exactly
    ``compute_dungeon_sets.DUNGEON_SET_SLOT_WORDS``; re-deriving them here
    with a different list would silently fail to match.  Parsed rather than
    imported — the script reads ``data/*.json`` at import time."""
    source = (ROOT / "ItemDatabase" / "compute_dungeon_sets.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    found = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "DUNGEON_SET_SLOT_WORDS"
            for target in node.targets
        ):
            found = [element.value for element in node.value.elts]
    assert found is not None, "compute_dungeon_sets.py no longer defines the list"
    assert list(recommend.SET_SLOT_WORDS) == found


def test_the_set_index_keeps_the_lowest_id_of_a_duplicated_name():
    """Bound and unbound copies share a name (a confirmed catalog quirk).
    The piece a player is told to go and get must be the same one on every
    refresh."""
    index = recommend.build_set_index(F.ITEMS, F.DUNGEON_SETS)
    assert index["Abyssal"]["pieces"]["Ring"]["id"] == 104


def test_the_set_index_takes_the_alphabetically_first_source_tag():
    """"Abyssal" is listed under Expedition and Sanctuary; a dashboard that
    renamed the source between two refreshes would be broken."""
    index = recommend.build_set_index(F.ITEMS, F.DUNGEON_SETS)
    assert index["Abyssal"]["tag"] == "Expedition"
    assert index["Corrupted"]["tag"] == "Sanctuary"


def test_an_item_belonging_to_no_listed_set_is_ignored():
    index = recommend.build_set_index(F.ITEMS, F.DUNGEON_SETS)
    assert set(index) == {"Abyssal", "Corrupted"}
    assert "Fierce Battle" not in index


def test_the_older_flat_grade_shape_is_read_too():
    index = recommend.build_set_index(F.ITEMS, F.DUNGEON_SETS_FLAT)
    assert index["Abyssal"]["grade"] == "Unique"
    assert index["Abyssal"]["gearscore"] is None


def test_missing_pieces_are_sorted_by_completeness_descending():
    """Abyssal 3/4 = 0.75 before Corrupted 1/3 = 0.333: the set that is one
    piece short is the one worth acting on."""
    picks = recommend.missing_set_pieces(F.EQUIPPED_AS_ITEMS, F.ITEMS, F.DUNGEON_SETS)
    assert [pick.pick["root"] for pick in picks] == ["Abyssal", "Corrupted"]
    assert picks[0].pick["owned"] == 3 and picks[0].pick["total"] == 4
    assert picks[1].pick["owned"] == 1 and picks[1].pick["total"] == 3


def test_a_set_recommendation_names_every_missing_piece_and_its_source():
    picks = recommend.missing_set_pieces(F.EQUIPPED_AS_ITEMS, F.ITEMS, F.DUNGEON_SETS)
    assert picks[0].text_key == recommend.RECO_SET_INCOMPLETE
    assert picks[0].text_kwargs == {
        "set": "Abyssal", "owned": 3, "total": 4, "source": "Expedition",
    }
    assert [reason.text_kwargs["slot"] for reason in picks[1].reasons] == ["Boots", "Helm"]
    assert picks[1].reasons[0].text_kwargs["item"] == "Corrupted Boots"
    assert picks[1].reasons[0].text_kwargs["source"] == "Sanctuary"


def test_the_set_reasons_sum_exactly_to_the_score_delta():
    """The one Stage-2 feature where ``explain.Recommendation``'s "reasons
    sum to the whole" really holds: one reason per missing piece, each worth
    1/total.  Abyssal: 1 x 0.25.  Corrupted: 2 x 1/3."""
    picks = recommend.missing_set_pieces(F.EQUIPPED_AS_ITEMS, F.ITEMS, F.DUNGEON_SETS)
    for pick in picks:
        assert sum(reason.score_contribution for reason in pick.reasons) == pytest.approx(
            pick.score_delta, abs=TOL
        )
    assert picks[0].score_delta == pytest.approx(0.25)
    assert picks[1].score_delta == pytest.approx(2 / 3)


def test_a_complete_set_produces_no_recommendation():
    equipped = {
        "Helmet": 101, "Gloves": 102, "Boots": 103, "Ring1": 104,
    }
    assert recommend.missing_set_pieces(equipped, F.ITEMS, F.DUNGEON_SETS) == []


def test_equipped_slots_are_accepted_as_ids_or_as_whole_item_dicts():
    """The persisted state holds item dicts; §3.4's sketch thinks in ids."""
    by_id = recommend.missing_set_pieces(F.EQUIPPED, F.ITEMS, F.DUNGEON_SETS)
    by_dict = recommend.missing_set_pieces(F.EQUIPPED_AS_ITEMS, F.ITEMS, F.DUNGEON_SETS)
    assert [pick.pick for pick in by_id] == [pick.pick for pick in by_dict]


def test_an_item_missing_from_the_catalog_falls_back_to_its_own_name():
    """A build saved before a catalog refresh can hold an item the current
    ``items_all.json`` no longer lists."""
    picks = recommend.missing_set_pieces(
        {"Helmet": {"id": 999, "name": "Abyssal Helm"}}, F.ITEMS, F.DUNGEON_SETS
    )
    assert picks[0].pick["root"] == "Abyssal"
    assert picks[0].pick["owned"] == 1


def test_no_dungeon_set_table_means_no_set_recommendations():
    assert recommend.missing_set_pieces(F.EQUIPPED_AS_ITEMS, F.ITEMS, {}) == []


def test_the_limit_bounds_the_list():
    picks = recommend.missing_set_pieces(F.EQUIPPED_AS_ITEMS, F.ITEMS, F.DUNGEON_SETS, limit=1)
    assert [pick.pick["root"] for pick in picks] == ["Abyssal"]


# ---------------------------------------------------------------------------
# 2b. recommend — orchestration and degradation
# ---------------------------------------------------------------------------


def _bundle(**overrides) -> providers.DataBundle:
    kwargs = {"items_by_id": F.ITEMS, "dungeon_sets": F.DUNGEON_SETS}
    kwargs.update(overrides)
    return providers.DataBundle(**kwargs)


def test_next_best_actions_orders_sets_then_alignment_then_the_gap():
    """Actionability, not score: a set one piece short names an item to go
    and get, the alignment names slots to re-pick, the gap is a diagnosis."""
    picks = recommend.next_best_actions(F.state(), F.DictProvider(), _bundle())
    assert [pick.pick["kind"] for pick in picks] == [
        "set_completion", "set_completion", "substat_alignment", "stat_gap",
    ]
    assert [pick.pick.get("root") for pick in picks[:2]] == ["Abyssal", "Corrupted"]


def test_every_recommendation_carries_a_text_key_and_its_reasons():
    """Audit §3.3: solvers never return bare picks."""
    for pick in recommend.next_best_actions(F.state(), F.DictProvider(), _bundle()):
        assert pick.text_key, pick.pick
        assert pick.reasons, pick.pick
        for reason in pick.reasons:
            assert reason.text_key


def test_the_stat_gap_recommendation_names_the_profile_it_used():
    """The state persists no role (it is a per-dialog choice in the Build
    Planner), so the sentence has to say which one the engine assumed."""
    (gap,) = [
        pick for pick in recommend.next_best_actions(F.state(), F.DictProvider(), _bundle())
        if pick.pick["kind"] == "stat_gap"
    ]
    assert gap.text_kwargs["role"] == recommend.DEFAULT_ROLE == "Angreifer"
    assert gap.text_kwargs["gear_type"] == "PvE"
    assert gap.score_delta == pytest.approx(sum(gap.pick["shortfalls"]))


def test_the_pvp_toggle_selects_the_pvp_profile():
    """Same test app.py's Quick Select makes: ``"PvP" in active_gear_types``."""
    state = F.state(active_gear_types=["PvP"])
    (gap,) = [
        pick for pick in recommend.next_best_actions(state, F.DictProvider(), _bundle())
        if pick.pick["kind"] == "stat_gap"
    ]
    assert gap.text_kwargs["gear_type"] == "PvP"


def test_no_data_pack_returns_exactly_the_line_that_says_so():
    """The degradation is a return value, not an empty list: a dashboard
    cannot tell "nothing to improve" from "no data" on its own."""
    picks = recommend.next_best_actions(F.state(), F.DictProvider(), providers.DataBundle())
    assert len(picks) == 1
    assert picks[0].text_key == providers.DATA_MISSING_KEY
    assert picks[0].pick["kind"] == "unavailable"
    assert picks[0].reasons == ()


def test_no_dungeon_set_table_still_runs_the_stat_features():
    picks = recommend.next_best_actions(F.state(), F.DictProvider(), _bundle(dungeon_sets={}))
    assert [pick.pick["kind"] for pick in picks] == ["substat_alignment", "stat_gap"]


def test_no_provider_still_runs_the_set_features():
    """Set completion needs names, not details."""
    picks = recommend.next_best_actions(F.state(), None, _bundle())
    assert {pick.pick["kind"] for pick in picks} == {"set_completion"}


def test_a_provider_that_resolves_nothing_drops_the_stat_features():
    """The cold-cache state: the catalog is there, the details are not."""
    picks = recommend.next_best_actions(F.state(), F.DictProvider({}), _bundle())
    assert {pick.pick["kind"] for pick in picks} == {"set_completion"}


@pytest.mark.parametrize(
    "state",
    [
        None,
        {},
        {"character_class": "Gladiator"},
        {"character_class": "Unknown", "equip_builds_data": {"gladiator": {}}},
        {"equip_builds_data": "not a dict"},
    ],
)
def test_a_state_with_no_resolvable_build_recommends_nothing(state):
    assert recommend.next_best_actions(state, F.DictProvider(), _bundle()) == []


def test_the_build_name_defaults_the_way_every_other_reader_defaults_it():
    """MainWindow and the dashboard both default the selected name to
    "Default"; a third rule here would make the engine read a different
    build than the page summarizes."""
    state = F.state(current_build_name="")
    state["equip_builds_data"]["gladiator"] = {
        "Default": state["equip_builds_data"]["gladiator"]["PvE t1"]
    }
    assert recommend.next_best_actions(state, F.DictProvider(), _bundle())


def test_the_set_index_is_computed_once_and_cached_on_the_bundle():
    """``next_best_actions`` runs on every window activation; a pass over
    the whole catalog per Alt-Tab is a cost with no matching benefit."""
    bundle = _bundle()
    assert bundle.set_index is None
    recommend.next_best_actions(F.state(), F.DictProvider(), bundle)
    first = bundle.set_index
    assert first is not None
    recommend.next_best_actions(F.state(), F.DictProvider(), bundle)
    assert bundle.set_index is first


def test_the_limit_bounds_the_whole_list():
    picks = recommend.next_best_actions(F.state(), F.DictProvider(), _bundle(), limit=2)
    assert len(picks) == 2


# ---------------------------------------------------------------------------
# 3. providers
# ---------------------------------------------------------------------------


@pytest.fixture
def data_pack(tmp_path):
    """A temporary ``ItemDatabase/data`` holding the synthetic catalog."""
    data_dir = tmp_path / "data"
    (data_dir / "details").mkdir(parents=True)
    (data_dir / "items_all.json").write_text(
        json.dumps({"items": list(F.ITEMS.values())}), encoding="utf-8"
    )
    (data_dir / "dungeon_sets.json").write_text(json.dumps(F.DUNGEON_SETS), encoding="utf-8")
    for item_id, detail in F.DETAILS.items():
        (data_dir / "details" / f"{item_id}.json").write_text(
            json.dumps(detail), encoding="utf-8"
        )
    return data_dir


def test_the_disk_provider_reads_one_detail_file_per_id(data_pack):
    provider = providers.DiskDetailProvider(data_pack / "details")
    assert provider.get(101)["mainStats"][0]["value"] == "100"
    assert provider.get(999) is None


def test_the_disk_provider_memoizes_hits_and_misses(data_pack, monkeypatch):
    """A miss is the common case without the pack, and the dashboard asks
    again on every focus change."""
    provider = providers.DiskDetailProvider(data_pack / "details")
    provider.get(101)
    provider.get(999)
    assert provider.cached_ids == (101, 999)

    monkeypatch.setattr(
        providers, "load_json_or_none",
        lambda path: pytest.fail(f"re-read {path} for a memoized id"),
    )
    assert provider.get(101)["level"] == 100
    assert provider.get(999) is None


@pytest.mark.parametrize("item_id", [None, "not an id", object()])
def test_the_disk_provider_answers_none_for_an_unusable_id(data_pack, item_id):
    assert providers.DiskDetailProvider(data_pack / "details").get(item_id) is None


def test_the_disk_provider_satisfies_the_protocol_structurally():
    """The point of ``model.DetailProvider``: no inheritance anywhere."""
    from armory_engine.model import DetailProvider

    assert isinstance(providers.DiskDetailProvider(Path(".")), DetailProvider)


def test_a_missing_directory_is_not_an_error(tmp_path):
    provider = providers.DiskDetailProvider(tmp_path / "nope" / "details")
    assert provider.get(101) is None


def test_load_json_or_none_collapses_every_failure(tmp_path):
    assert providers.load_json_or_none(tmp_path / "absent.json") is None
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert providers.load_json_or_none(broken) is None
    good = tmp_path / "good.json"
    good.write_text('{"a": 1}', encoding="utf-8")
    assert providers.load_json_or_none(good) == {"a": 1}


def test_the_bundle_reads_the_three_catalog_files(data_pack):
    bundle = providers.load_data_bundle(data_pack)
    assert bundle.available is True
    assert bundle.reason_key == ""
    assert bundle.items_by_id[101]["name"] == "Abyssal Helm"
    assert bundle.dungeon_sets == F.DUNGEON_SETS
    # Not written by the fixture: a file that is absent is named, not fatal.
    assert bundle.stat_priority_options == {}
    assert providers.STAT_PRIORITY_OPTIONS_FILE in bundle.missing


def test_an_absent_data_dir_is_the_unavailable_bundle(tmp_path):
    """This clone's actual state: ``ItemDatabase/data`` holds no catalog."""
    bundle = providers.load_data_bundle(tmp_path / "data")
    assert bundle.available is False
    assert bundle.reason_key == providers.DATA_MISSING_KEY
    assert len(bundle.missing) == 3


def test_a_bare_list_of_items_is_read_too(tmp_path):
    """``compute_dungeon_sets.py`` already guards for it, so this reader
    does not get to be the one that does not."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "items_all.json").write_text(
        json.dumps([{"id": 1, "name": "Abyssal Helm"}, {"name": "no id"}, "junk"]),
        encoding="utf-8",
    )
    bundle = providers.load_data_bundle(data_dir)
    assert set(bundle.items_by_id) == {1}


def test_the_whole_chain_runs_off_disk(data_pack):
    """Bundle + disk provider + orchestrator, with nothing in memory: the
    exact configuration ``MainWindow._armory_recommendations`` builds."""
    picks = recommend.next_best_actions(
        F.state(),
        providers.DiskDetailProvider(data_pack / "details"),
        providers.load_data_bundle(data_pack),
    )
    assert [pick.pick["kind"] for pick in picks] == [
        "set_completion", "set_completion", "substat_alignment", "stat_gap",
    ]
