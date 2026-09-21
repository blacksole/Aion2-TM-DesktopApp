"""Stage 1's two structural invariants: no drift, and it still ships.

**No drift.** The engine was extracted by MOVING code, and app.py imports it
back under the same names so its ~700 internal call sites did not change.
That leaves one specific way to break it quietly: re-add a definition to
app.py.  The module would still import, every call site would still resolve —
to the copy — and the engine's golden tests would keep passing against code
nothing runs.  ``tests/test_theme.py`` guards the token tables the same way;
this is that pattern pointed at the engine.

**It still ships.** app.py is bundled as a DATA file, not compiled into the
PYZ (the host loads it with ``spec_from_file_location``), so PyInstaller
never follows its imports.  Audit B-armory.md §4.1 names this as one of the
two hard constraints of the whole refactor: "a package split silently breaks
the frozen build unless each new file/folder gets a datas entry" — and notes
the spec had already fallen five files behind once, which shipped a release
where the Pantheon filter always returned nothing.  The failure mode here is
worse than a missing colour: no ``armory_engine`` means ModuleNotFoundError
the moment the Armory opens.  Nothing in the test suite runs PyInstaller, so
the spec is read as data instead — which is exactly what
``tests/test_armory_theme.py`` already does for the stylesheet entries.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_PY = ROOT / "ItemDatabase" / "app.py"
ENGINE = ROOT / "ItemDatabase" / "armory_engine"

#: ``{module: [names that moved out of app.py into it]}``.
#:
#: The map is the point of the test, so it is spelled out rather than derived
#: from ``__all__``: a name dropped from an engine ``__all__`` AND from this
#: list would make the drift check pass by shrinking, which is the one thing
#: a guard must not allow.
MOVED = {
    "enchant": [
        "_GEAR_STAT_ID_ALIASES", "_SCALING_STAT_ID", "_ACCESSORY_CATEGORIES",
        "_ACCESSORY_RATE_PER_LEVEL", "_WEAPON_CURVE_PARAMS", "_HEROIC_RATE_PER_LEVEL",
        "_DEFAULT_WEAPON_CURVE", "_RUNE_PVE_ITEM_ID", "_RUNE_PVP_ITEM_ID",
        "_RUNE_COMBAT_SPEED_THRESHOLD", "_RUNE_MULTI_HIT_THRESHOLD",
        "_rune_enchant_bonus", "estimate_enchant_bonus", "estimate_exceed_bonus",
        "_ARMOR_CATEGORIES", "_BELT_CATEGORY", "_DEFENSE_STAT_ID", "_HP_STAT_ID",
        "_ARMOR_DEFENSE_RATE", "_DEFAULT_ARMOR_DEFENSE_RATE", "_ARMOR_HP_RATE_PER_LEVEL",
        "_BELT_DEFENSE_RATE_PER_LEVEL", "_BELT_HP_RATE_PER_LEVEL",
        "estimate_armor_bonus", "estimate_armor_exceed_bonus",
        "_GEARSCORE_NORMAL_RATE", "_GEARSCORE_EXCEED_RATE", "_gearscore_push",
    ],
    "substats": [
        "_STAT_PRIORITY_GEAR_TYPES", "_STAT_PRIORITY_ROLES", "_STAT_PRIORITY_MAX_ENTRIES",
        "_DEFAULT_STAT_PRIORITY_BY_CATEGORY", "_default_stat_priority_profiles",
        "_merge_stat_priority_profiles", "_STAT_NAME_ALIASES", "_normalize_stat_name",
        "_pick_priority_substats",
    ],
    "arcana": [
        "_ARCANA_LORD_TYPES", "_ARCANA_LORD_CATEGORY", "_ARCANA_GRADE_MAX_LEVEL",
        "_ARCANA_MAX_CARD_LEVEL", "_ARCANA_ACTIVE_THEMES", "_arcana_usable_lord_types",
        "_ARCANA_SKILL_BASELINE", "_ARCANA_CARD_EXTRA_BUDGET", "_ARCANA_PER_SKILL_CAP",
        "_ARCANA_SKILL_SLOTS_PER_CARD", "_ARCANA_DEFAULT_GRADE",
        "_arcana_card_slot_list", "_arcana_card_grade", "_arcana_card_level",
        "_arcana_eligible_skills_for_type", "_arcana_full_pool_for_type",
        "_arcana_best_card_contribution", "_arcana_best_combination",
        "_arcana_compute_combinations", "_arcana_result_coverage_percent",
        "_arcana_eligible_types", "_arcana_max_ceiling", "_arcana_uncovered_reason",
    ],
    "daevanion": [
        "_daevanion_neighbors", "_daevanion_is_reachable", "_daevanion_total_cost",
        "_daevanion_spent_cost", "_DAEVANION_MP_NAMES", "_daevanion_node_mp_count",
        "_daevanion_shortest_from_tree", "_daevanion_path_nodes_to_add",
        "_daevanion_compute_auto_route",
    ],
    "transfer": [
        "_item_type_word", "_item_grade", "_transfer_source_name",
        "_build_transfer_source_index", "_find_transfer_path", "_ordered_tier_chain",
        "_parse_gold_cost", "_build_recipe_output_index", "_resolve_material_name",
        "_build_material_node", "_build_material_tree", "_flatten_material_tree",
        "_compute_tree_kinah",
    ],
    "sets": ["_build_dungeon_sets"],
    "stats": ["_parse_stat_value"],
}

#: Every name above, flattened -- what app.py must resolve and must not define.
ALL_MOVED = sorted({name for names in MOVED.values() for name in names})

#: Names the Armory's own characterization tests read straight off the loaded
#: ``item_database_app`` module (tests/test_enchant_model.py's "Seams these
#: tests depend on" block).  They must stay importable from app.py so BOTH
#: paths -- engine-direct and through-app.py -- keep being exercised.
RE_EXPORTED_FOR_TESTS = [
    "estimate_enchant_bonus", "estimate_exceed_bonus", "estimate_armor_bonus",
    "estimate_armor_exceed_bonus", "_gearscore_push",
    "_GEARSCORE_NORMAL_RATE", "_GEARSCORE_EXCEED_RATE",
    "_ACCESSORY_CATEGORIES", "_ARMOR_CATEGORIES", "_BELT_CATEGORY",
]

#: The two LoadoutWindow methods that stayed as METHODS, wrapping the pure
#: functions.  They are still defined in app.py by design (they are the seam
#: the live panel and Build Compare both call), so the drift check below is
#: about module-level definitions only and these are named here to say so.
WRAPPED_METHODS = ["_compute_stat_totals_detailed", "_compute_gearscore"]


@pytest.fixture(scope="module")
def app_tree():
    """app.py parsed, never executed -- this module must not need a Qt app."""
    return ast.parse(APP_PY.read_text(encoding="utf-8"), filename=str(APP_PY))


@pytest.fixture(scope="module")
def module_level_definitions(app_tree):
    """Names bound at app.py's TOP LEVEL: defs, classes and plain assignments.

    Deliberately not recursive.  A moved name reappearing as a module-level
    definition is the drift this guards; a local variable that happens to
    share a name is not.
    """
    defined = set()
    for node in app_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined.add(node.target.id)
    return defined


@pytest.fixture(scope="module")
def engine_imports(app_tree):
    """``{imported name: engine module}`` for every ``from armory_engine.x``."""
    imported = {}
    for node in ast.walk(app_tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("armory_engine"):
            for alias in node.names:
                imported[alias.asname or alias.name] = node.module
    return imported


# ---------------------------------------------------------------------------
# no drift
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ALL_MOVED)
def test_no_moved_name_is_still_defined_in_app_py(name, module_level_definitions):
    """The whole point of a MOVE: there is one copy, and it is in the engine.

    A re-added definition in app.py would shadow the import silently -- the
    call sites would resolve to the copy, and the engine's golden tests would
    go on passing against code nothing runs.
    """
    assert name not in module_level_definitions, (
        f"{name} is defined in app.py again; it lives in armory_engine now. "
        f"If app.py really needs its own, it needs a different name."
    )


@pytest.mark.parametrize("name", ALL_MOVED)
def test_app_py_imports_back_every_moved_name_it_still_uses(name, engine_imports, app_tree):
    """The move kept app.py's ~700 call sites working by importing the names
    back under exactly the names they had.  So: every moved name app.py still
    REFERENCES has to be imported.

    Derived from the reference rather than from a list, because the two halves
    are genuinely different.  Most of what moved is still used here (the
    estimators, the solvers, the category sets the UI branches on); a handful
    of pure calibration constants -- the curve parameters, the per-level rates
    -- are only ever read by the estimators themselves, so re-importing them
    would be dead weight.  This test does not care which is which; it only
    insists the two agree.
    """
    referenced = {
        node.id for node in ast.walk(app_tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    if name not in referenced:
        pytest.skip(f"{name} is internal to the engine -- app.py never reads it")
    assert name in engine_imports, f"app.py uses {name} but does not import it"


@pytest.mark.parametrize("name", RE_EXPORTED_FOR_TESTS)
def test_the_names_the_characterization_tests_read_are_re_exported(name, engine_imports):
    """tests/test_enchant_model.py loads app.py the way the host does and
    reads these off the module.  Keeping them importable here is what makes
    that suite test the SHIPPING path (app.py's namespace) while
    tests/test_armory_engine_golden.py tests the engine directly."""
    assert name in engine_imports, (
        f"{name} is no longer re-exported from app.py; tests/test_enchant_model.py "
        f"reads it off the loaded module"
    )


@pytest.mark.parametrize("module_name,names", sorted(MOVED.items()))
def test_every_moved_name_really_exists_in_its_engine_module(module_name, names):
    """Reads the engine module as source too, so this file needs no imports of
    its own and cannot be fooled by something already in ``sys.modules``."""
    tree = ast.parse((ENGINE / f"{module_name}.py").read_text(encoding="utf-8"))
    defined = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            defined.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined.add(node.target.id)
    missing = sorted(set(names) - defined)
    assert not missing, f"armory_engine.{module_name} is missing {missing}"


@pytest.mark.parametrize("name", WRAPPED_METHODS)
def test_the_two_wrapped_methods_are_methods_and_delegate(name, app_tree):
    """``_compute_stat_totals_detailed`` and ``_compute_gearscore`` stayed on
    LoadoutWindow as thin wrappers -- so they ARE still defined, and the check
    on them is the opposite one: that the body is a delegation and not a
    second implementation.

    A wrapper is one ``return`` of one call.  If one of these grows a loop
    again, the arithmetic has drifted back out of the engine.
    """
    loadout = next(
        node for node in ast.walk(app_tree)
        if isinstance(node, ast.ClassDef) and node.name == "LoadoutWindow"
    )
    method = next(
        node for node in loadout.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    statements = [s for s in method.body if not isinstance(s, ast.Expr)]
    assert len(statements) == 1 and isinstance(statements[0], ast.Return), (
        f"{name} is no longer a thin wrapper -- it has {len(statements)} statements"
    )
    call = statements[0].value
    assert isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    assert call.func.id in ("compute_stat_totals_detailed", "compute_gearscore")


def test_app_py_puts_the_engine_on_sys_path_before_importing_it(app_tree):
    """Order matters, and is invisible at a glance.

    app.py is loaded BY FILE PATH, which does not put its own directory on
    ``sys.path``.  So the insert has to execute before the first
    ``from armory_engine...`` -- otherwise the host app dies at startup while
    a bare ``python ItemDatabase/app.py`` keeps working, the worst possible
    split between the two entry points.
    """
    first_engine_import = min(
        node.lineno for node in ast.walk(app_tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("armory_engine")
    )
    inserts = [
        node.lineno for node in ast.walk(app_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "insert"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "path"
    ]
    assert any(line < first_engine_import for line in inserts), (
        "no sys.path.insert runs before the first armory_engine import"
    )


# ---------------------------------------------------------------------------
# it still ships
# ---------------------------------------------------------------------------


def _spec_datas(spec_path: Path) -> list[tuple[str, str]]:
    """The ``datas`` list of a .spec's ``Analysis(...)``, read as data.

    A .spec is Python that PyInstaller evaluates with its own globals
    (``SPECPATH``), so ast is the honest way to inspect one from a test --
    the same approach ``tests/test_armory_theme.py`` takes.
    """
    tree = ast.parse(spec_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Analysis":
            for keyword in node.keywords:
                if keyword.arg == "datas":
                    return [tuple(ast.literal_eval(element)) for element in keyword.value.elts]
    raise AssertionError(f"{spec_path.name} has no Analysis(datas=...)")


@pytest.mark.parametrize(
    "spec_name,source",
    [
        ("Aion2 TM.spec", "ItemDatabase/armory_engine"),
        ("ItemDatabase/AION2_ItemDatabase.spec", "armory_engine"),
    ],
)
def test_both_specs_bundle_the_engine_package(spec_name, source):
    """One entry per spec, and the DESTINATION is part of the read path.

    It has to be ``ItemDatabase/armory_engine`` in both, because app.py
    resolves the package through its own directory -- frozen, that is
    ``_MEIPASS/ItemDatabase``.  A destination of ``armory_engine`` would land
    it one level too shallow and the Armory would not open at all.

    A directory source, not a file list: PyInstaller copies a directory
    recursively, so a module added to the package later ships without anyone
    touching either spec.  (Contrast ``ItemDatabase/data/`` in the shipping
    spec, which needs a line per file -- that folder also holds ~278 MB of
    runtime caches that must never ship.)
    """
    datas = _spec_datas(ROOT / spec_name)
    assert (source, "ItemDatabase/armory_engine") in datas, (
        f"{spec_name} does not bundle {source} to ItemDatabase/armory_engine; "
        f"the frozen Armory would raise ModuleNotFoundError on open"
    )


@pytest.mark.parametrize(
    "spec_name,source",
    [
        ("Aion2 TM.spec", "ItemDatabase/armory_engine"),
        ("ItemDatabase/AION2_ItemDatabase.spec", "armory_engine"),
    ],
)
def test_the_bundled_engine_source_exists_where_the_spec_says(spec_name, source):
    base = ROOT if spec_name == "Aion2 TM.spec" else ROOT / "ItemDatabase"
    assert (base / source).is_dir()


def test_the_shipping_spec_still_bundles_app_py_as_data():
    """The constraint the engine entry exists BECAUSE of: app.py is data, so
    PyInstaller never follows its imports.  If this ever becomes a real
    module in the PYZ, the engine entry can go -- and until then it cannot."""
    datas = _spec_datas(ROOT / "Aion2 TM.spec")
    assert ("ItemDatabase/app.py", "ItemDatabase") in datas
