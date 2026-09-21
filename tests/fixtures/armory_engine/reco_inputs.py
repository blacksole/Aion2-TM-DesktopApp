"""Synthetic inputs for the Stage-2 recommendation tests.

Different contract from ``inputs.py`` next door, and deliberately so.  Those
feed the GOLDEN tests, whose expected values were *recorded* from the
pre-extraction app.py — a one-way ratchet against behaviour change.  Stage 2
is new behaviour, so there is nothing to record from: every expectation in
``tests/test_armory_engine_recommend.py`` is computed **by hand** from the
numbers below, in the test, with the arithmetic written out.  A recorded
expectation would only prove the code still does what it did.

Everything here is chosen to be hand-computable:

* two sets, sizes 4 and 3, so completeness is 3/4 and 1/3 and the ordering
  between them is unambiguous;
* a duplicate item name (the bound/unbound twin the real catalog has), so
  the "lowest id wins" rule is exercised rather than asserted;
* flat stat values (100 / 50 / 40 / 20), no enchant levels, so totals are
  sums a reader can check in their head;
* one stat that travels under an ALIASED id (``"Defense"`` on the piece,
  ``"DefenseBonus"`` in the totals), because that join is the one place the
  name index can silently fail.

No imports, no Qt, no reading of anything.
"""

# ---------------------------------------------------------------------------
# catalog
# ---------------------------------------------------------------------------

#: ``{item_id: item}`` as ``items_all.json`` ships rows.
#: 105 is 104's bound twin: same name, higher id (see ``build_set_index``).
#: 300 belongs to no set — it must not appear in any recommendation.
ITEMS = {
    101: {"id": 101, "name": "Abyssal Helm", "grade": "Unique"},
    102: {"id": 102, "name": "Abyssal Gloves", "grade": "Unique"},
    103: {"id": 103, "name": "Abyssal Boots", "grade": "Unique"},
    104: {"id": 104, "name": "Abyssal Ring", "grade": "Unique"},
    105: {"id": 105, "name": "Abyssal Ring", "grade": "Unique"},
    201: {"id": 201, "name": "Corrupted Helm", "grade": "Legend"},
    202: {"id": 202, "name": "Corrupted Boots", "grade": "Legend"},
    203: {"id": 203, "name": "Corrupted Ring", "grade": "Legend"},
    300: {"id": 300, "name": "Fierce Battle Amulet", "grade": "Unique"},
}

#: ``{source_tag: {root: {...}}}`` exactly as ``compute_dungeon_sets.py``
#: writes it.  "Abyssal" is listed under two tags on purpose: the index
#: takes the alphabetically first ("Expedition"), which is what makes the
#: rendered source line stable across refreshes.
DUNGEON_SETS = {
    "Expedition": {"Abyssal": {"grade": "Unique", "gearscore": 120}},
    "Sanctuary": {
        "Abyssal": {"grade": "Unique", "gearscore": 120},
        "Corrupted": {"grade": "Legend", "gearscore": 95},
    },
}

#: The older ``{root: grade}`` spelling ``sets.py``'s docstring describes.
#: Both are accepted; this proves it rather than trusting the docstring.
DUNGEON_SETS_FLAT = {"Expedition": {"Abyssal": "Unique"}}

# ---------------------------------------------------------------------------
# details (the DetailProvider's whole world)
# ---------------------------------------------------------------------------

#: Flat values, no ranges, no percents, no enchant: the totals a test
#: asserts are sums of what is written here.
DETAILS = {
    101: {
        "level": 100,
        "gradeName": "Unique",
        "categoryName": "Helmet",
        "maxEnchantLevel": 15,
        "mainStats": [{"id": "Attack", "name": "Attack", "value": "100"}],
        "subStats": [
            {"id": "CriticalHit", "name": "Critical Hit", "value": "10"},
            {"id": "Smite", "name": "Smite", "value": "5"},
            {"id": "Block", "name": "Block", "value": "7"},
        ],
    },
    102: {
        "level": 90,
        "gradeName": "Unique",
        "categoryName": "Gloves",
        "maxEnchantLevel": 15,
        "mainStats": [{"id": "Attack", "name": "Attack", "value": "50"}],
        "subStats": [{"id": "CombatSpeed", "name": "Combat Speed", "value": "2"}],
    },
    103: {
        "level": 80,
        "gradeName": "Unique",
        "categoryName": "Boots",
        "maxEnchantLevel": 15,
        # "Defense" is aliased to "DefenseBonus" by the totals merge.
        "mainStats": [{"id": "Defense", "name": "Defense increase", "value": "40"}],
        "subStats": [{"id": "MoveSpeed", "name": "Move Speed", "value": "3"}],
    },
    203: {
        "level": 70,
        "gradeName": "Legend",
        "categoryName": "Ring",
        "maxEnchantLevel": 15,
        "mainStats": [{"id": "Attack", "name": "Attack", "value": "20"}],
        "subStats": [{"id": "Accuracy", "name": "Accuracy", "value": "8"}],
    },
}

# ---------------------------------------------------------------------------
# the build
# ---------------------------------------------------------------------------

#: Three quarters of "Abyssal" (Ring missing) and one third of "Corrupted"
#: (Helm and Boots missing) — two sets whose completeness ordering is 0.75
#: before 0.333.
EQUIPPED = {"Helmet": 101, "Gloves": 102, "Boots": 103, "Ring1": 203}

#: The same slots as the persisted state holds them: whole item dicts, not
#: ids (``_item_id`` accepts both, and the app only ever produces this one).
EQUIPPED_AS_ITEMS = {slot: dict(ITEMS[item_id]) for slot, item_id in EQUIPPED.items()}

#: Indices into each item's own ``subStats``.  Helmet takes Critical Hit and
#: Smite (0, 1) and leaves Block; Gloves takes Combat Speed; Boots takes
#: Move Speed; the Ring takes Accuracy.
SUBSTATS = {"Helmet": [0, 1], "Gloves": [0], "Boots": [0], "Ring1": [0]}

#: One category only, so the merged weight vector is hand-checkable:
#: rank 0 Attack = 1.0, rank 1 Critical Hit = 0.75, rank 2 Smite = 0.5625,
#: rank 3 Move Speed = 0.421875 (0.75 ** 3).
PROFILE_CATEGORIES = {
    "helmet": ["Attack", "Critical Hit", "Smite", "Movement Speed"],
}


def state(**overrides) -> dict:
    """A ``build_planner`` dict carrying the build above.

    Shaped exactly like the persisted one (``model.BuildState``): the class
    key is lower-cased, the build lives under ``current_build_name``, and
    the substats are lists.
    """
    base = {
        "character_class": "Gladiator",
        "current_build_name": "PvE t1",
        "active_gear_types": ["PvE", "Neutral"],
        "equip_builds_data": {
            "gladiator": {
                "PvE t1": {
                    "equipped": EQUIPPED_AS_ITEMS,
                    "substats": SUBSTATS,
                    "enchant": {},
                }
            }
        },
    }
    base.update(overrides)
    return base


class DictProvider:
    """``DetailProvider`` over a plain dict — the same stub the golden tests
    use, restated here so this fixture module has no import of its own."""

    def __init__(self, details=None):
        self.details = DETAILS if details is None else details

    def get(self, item_id):
        return self.details.get(item_id)
