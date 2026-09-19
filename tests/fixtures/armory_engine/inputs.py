"""Synthetic inputs for the armory_engine golden tests.

Small, hand-built and deliberately NOT scraped from the real catalog: the
goldens in ``golden.json`` are recorded by running the *pre-extraction*
``ItemDatabase/app.py`` against exactly these inputs (see
``tests/test_armory_engine_golden.py`` for the contract), so they have to be
readable, stable and free of anything that would make a diff unreviewable.

Kept as Python rather than JSON for the one thing JSON cannot express: the
Daevanion grid is keyed by an ``(r, c)`` tuple.  Everything here is plain
data -- no imports from the app, no Qt.
"""

# ---------------------------------------------------------------------------
# 6 items + their details (the DetailProvider's whole world)
# ---------------------------------------------------------------------------

#: ``{item_id: detail}`` -- the exact shape ``ItemDetailCache.get`` returns.
#: One per enchant family the estimators branch on: weapon (Unique curve),
#: weapon (Heroic linear), accessory, armor piece, belt, and a Rune (its own
#: hand-fitted curve, which bypasses the generic estimators entirely).
DETAILS = {
    900001: {
        "level": 120,
        "gradeName": "Unique",
        "categoryName": "Greatsword",
        "maxEnchantLevel": 15,
        "mainStats": [
            {"id": "WeaponFixingDamage", "name": "Attack", "value": "396 ~ 545"},
            {"id": "Accuracy", "name": "Accuracy", "value": "210"},
        ],
        "subStats": [
            {"id": "CriticalHit", "name": "Critical Hit", "value": "44"},
            {"id": "CombatSpeed", "name": "Combat Speed", "value": "3%"},
            {"id": "BackAttackDamage", "name": "Back Attack", "value": "12"},
            {"id": "Might", "name": "Might", "value": "18"},
        ],
    },
    900002: {
        "level": 140,
        "gradeName": "Heroic",
        "categoryName": "Guard",
        "maxEnchantLevel": 20,
        "mainStats": [
            {"id": "WeaponFixingDamage", "name": "Attack", "value": "136"},
            {"id": "Block", "name": "Block", "value": "88"},
        ],
        "subStats": [
            {"id": "Perfect", "name": "Perfect Chance", "value": "5"},
            {"id": "Defense", "name": "Defense increase", "value": "2%"},
            {"id": "Attack", "name": "Attack", "value": "30"},
        ],
    },
    900003: {
        "level": 95,
        "gradeName": "Unique",
        "categoryName": "Ring",
        "maxEnchantLevel": 15,
        "mainStats": [
            {"id": "WeaponFixingDamage", "name": "Attack", "value": "60"},
            {"id": "Time", "name": "Time", "value": "4"},
        ],
        "subStats": [
            {"id": "Accuracy", "name": "Accuracy", "value": "19"},
            {"id": "CriticalHit", "name": "Critical Hit", "value": "21"},
            {"id": "Attack", "name": "Attack", "value": "11"},
        ],
    },
    900004: {
        "level": 110,
        "gradeName": "Heroic",
        "categoryName": "Top",
        "maxEnchantLevel": 20,
        "mainStats": [
            {"id": "ArmorDefense", "name": "Defense", "value": "410"},
            {"id": "HPMax", "name": "Max HP", "value": "1800"},
        ],
        "subStats": [
            {"id": "DamageBoost", "name": "Damage Boost", "value": "1.5%"},
            {"id": "Endurance", "name": "Endurance", "value": "26"},
            {"id": "Accuracy", "name": "Accuracy", "value": "14"},
        ],
    },
    900005: {
        "level": 70,
        "gradeName": "Unique",
        "categoryName": "Belt",
        "maxEnchantLevel": 10,
        "mainStats": [
            {"id": "ArmorDefense", "name": "Defense", "value": "150"},
            {"id": "HPMax", "name": "Max HP", "value": "900"},
        ],
        "subStats": [
            {"id": "Evasion", "name": "Evasion", "value": "17"},
            {"id": "DecreaseDamage", "name": "Damage Tolerance", "value": "0.8%"},
        ],
    },
    # The real Clash Rune id -- _rune_enchant_bonus keys off the id itself.
    310900001: {
        "level": 40,
        "gradeName": "Unique",
        "categoryName": "Rune",
        "maxEnchantLevel": 10,
        "mainStats": [
            {"id": "CombatSpeed", "name": "Combat Speed", "value": "1%"},
            {"id": "DefensePierce", "name": "Penetration", "value": "100"},
        ],
        "subStats": [],
    },
}

#: ``{slot_id: item}`` -- the catalog rows, as ``self._equipped`` holds them.
EQUIPPED = {
    "MainHand": {"id": 900001, "name": "QA Greatsword"},
    "SubHand": {"id": 900002, "name": "QA Guard"},
    "Ring1": {"id": 900003, "name": "QA Ring"},
    "Torso": {"id": 900004, "name": "QA Top"},
    "Belt": {"id": 900005, "name": "QA Belt"},
    "Rune": {"id": 310900001, "name": "Clash Rune"},
    # A slot the provider knows nothing about: the merge must skip it, not
    # raise (an item whose detail has not been fetched yet is the normal
    # cold-cache state).
    "Cloak": {"id": 900999, "name": "QA Unknown"},
}

#: ``{slot_id: {index into that detail's subStats}}`` -- what the player
#: ticked.  Index 9 on Ring1 is out of range on purpose: the merge bounds-
#: checks, and that guard is part of the behaviour being pinned.
SUBSTATS = {
    "MainHand": {0, 2},
    "SubHand": {1},
    "Ring1": {0, 9},
    "Torso": {0, 1},
    "Belt": set(),
}

#: ``{slot_id: enchant_level}`` -- normal range, exceed range, and zero.
ENCHANT = {
    "MainHand": 12,
    "SubHand": 23,
    "Ring1": 15,
    "Torso": 20,
    "Belt": 0,
    "Rune": 11,
}

# ---------------------------------------------------------------------------
# a 4-hop upgrade chain (transfer graph + material tree)
# ---------------------------------------------------------------------------

#: Normalized recipes, exactly as ``_load_recipes`` emits them.  Four of them
#: form one upgrade ladder (Plain -> Fine -> Pure -> Radiant QA Boots), of
#: which one hop is Kinah-only (no Transfer Stone) -- the case that broke a
#: real chain one hop before its end, per _build_transfer_source_index.
RECIPES = [
    {
        "id": 1, "profession": "Armorsmithing", "category": "boots", "grade": "Unique",
        "method": "Herstellung", "masteryLevel": 10, "goldCost": 4000,
        "inputs": [
            {"id": 800001, "name": "QA Iron Ore", "qty": 4},
            {"id": 800002, "name": "QA Leather", "qty": 2},
        ],
        "outputs": [{"id": 700001, "name": "Plain QA Boots"}],
    },
    {
        "id": 2, "profession": "Armorsmithing", "category": "boots", "grade": "Unique",
        "method": "Transfer", "masteryLevel": 20, "goldCost": 15000,
        "inputs": [
            {"id": 700001, "name": "Plain QA Boots", "qty": 1},
            {"id": 800003, "name": "Transfer Stone", "qty": 3},
        ],
        "outputs": [{"id": 700002, "name": "Fine QA Boots"}],
    },
    {
        # Kinah-only hop: no Transfer Stone anywhere in the inputs.
        "id": 3, "profession": "Armorsmithing", "category": "boots", "grade": "Unique",
        "method": "Herstellung", "masteryLevel": 30, "goldCost": 250000,
        "inputs": [{"id": 700002, "name": "Fine QA Boots", "qty": 1}],
        "outputs": [{"id": 700003, "name": "Pure QA Boots"}],
    },
    {
        "id": 4, "profession": "Armorsmithing", "category": "boots", "grade": "Unique",
        "method": "Transfer", "masteryLevel": 40, "goldCost": 900000,
        "inputs": [
            {"id": 700003, "name": "Pure QA Boots", "qty": 1},
            {"id": 800003, "name": "Transfer Stone", "qty": 5},
            {"id": 800004, "name": "QA Essence", "qty": 2},
        ],
        "outputs": [{"id": 700004, "name": "Radiant QA Boots"}],
    },
    {
        # A decoy: one qty-1 craftable input, but a DIFFERENT type word, so
        # it must never register as an upgrade hop (_transfer_source_name).
        "id": 5, "profession": "Handicrafting", "category": "ring", "grade": "Unique",
        "method": "Herstellung", "masteryLevel": 25, "goldCost": 7000,
        "inputs": [
            {"id": 700002, "name": "Fine QA Boots", "qty": 1},
            {"id": 800001, "name": "QA Iron Ore", "qty": 3},
        ],
        "outputs": [{"id": 700005, "name": "QA Ring"}],
    },
    {
        # A sub-recipe, so the material tree really has a second level.
        "id": 6, "profession": "Armorsmithing", "category": "materials", "grade": "Rare",
        "method": "Herstellung", "masteryLevel": 5, "goldCost": 300,
        "inputs": [{"id": 800005, "name": "QA Raw Hide", "qty": 3}],
        "outputs": [{"id": 800002, "name": "QA Leather"}],
    },
]

#: ``{item_id: item}`` for the grade check in ``_transfer_source_name``.
ITEMS_BY_ID = {
    700001: {"id": 700001, "name": "Plain QA Boots", "grade": "Unique"},
    700002: {"id": 700002, "name": "Fine QA Boots", "grade": "Unique"},
    700003: {"id": 700003, "name": "Pure QA Boots", "grade": "Unique"},
    700004: {"id": 700004, "name": "Radiant QA Boots", "grade": "Unique"},
    700005: {"id": 700005, "name": "QA Ring", "grade": "Unique"},
    800001: {"id": 800001, "name": "QA Iron Ore", "grade": "Common"},
    800002: {"id": 800002, "name": "QA Leather", "grade": "Rare"},
    800005: {"id": 800005, "name": "QA Raw Hide", "grade": "Common"},
}

# ---------------------------------------------------------------------------
# a 5x5 Daevanion board
# ---------------------------------------------------------------------------

#: Nodes as the raw data ships them (``{id, r, c, g, cost, e}``), laid out as
#: a 5x5 grid with four "empty" cells punched out.  Two of them (n03, n12)
#: make the router route AROUND something rather than walk a straight line.
#: The other two (n34, n43) wall n44 off completely, which is the ONLY way to
#: reach the router's "abandon every wanted node still left" branch: the
#: board cap is ``sum(cost for every node)``, and the tree is a subset of the
#: board, so ``spent`` can never exceed ``cap`` -- the branch fires on an
#: UNREACHABLE target, never on an exhausted point budget.
#: Costs vary so the cheapest-first greedy has a real choice to make, and
#: three nodes carry a Max MP stat so the (points, mpNodeCount) tie-break is
#: exercised.
DAEVANION_NODES = [
    {"id": "n00", "r": 0, "c": 0, "g": "start", "cost": 0, "e": [{"t": "s", "n": "Attack Bonus", "v": 5}]},
    {"id": "n01", "r": 0, "c": 1, "g": "normal", "cost": 2, "e": [{"t": "s", "n": "Max MP", "v": 40}]},
    {"id": "n02", "r": 0, "c": 2, "g": "normal", "cost": 1, "e": [{"t": "s", "n": "Accuracy", "v": 7}]},
    {"id": "n03", "r": 0, "c": 3, "g": "empty", "cost": 0, "e": []},
    {"id": "n04", "r": 0, "c": 4, "g": "normal", "cost": 3, "e": [{"t": "s", "n": "Critical", "v": 9}]},
    {"id": "n10", "r": 1, "c": 0, "g": "normal", "cost": 2, "e": [{"t": "s", "n": "Max MP", "v": 40}]},
    {"id": "n11", "r": 1, "c": 1, "g": "normal", "cost": 4, "e": [{"t": "s", "n": "Defense", "v": 30}]},
    {"id": "n12", "r": 1, "c": 2, "g": "empty", "cost": 0, "e": []},
    {"id": "n13", "r": 1, "c": 3, "g": "normal", "cost": 2, "e": [{"t": "s", "n": "Evasion", "v": 6}]},
    {"id": "n14", "r": 1, "c": 4, "g": "normal", "cost": 1, "e": [{"t": "k", "n": "skill", "v": 1, "skill_id": "9001"}]},
    {"id": "n20", "r": 2, "c": 0, "g": "normal", "cost": 1, "e": [{"t": "s", "n": "Block", "v": 12}]},
    {"id": "n21", "r": 2, "c": 1, "g": "normal", "cost": 1, "e": [{"t": "s", "n": "Max MP", "v": 40}]},
    {"id": "n22", "r": 2, "c": 2, "g": "normal", "cost": 5, "e": [{"t": "s", "n": "Attack Bonus", "v": 22}]},
    {"id": "n23", "r": 2, "c": 3, "g": "normal", "cost": 1, "e": [{"t": "s", "n": "Perfect", "v": 4}]},
    {"id": "n24", "r": 2, "c": 4, "g": "normal", "cost": 2, "e": [{"t": "s", "n": "Restoration", "v": 8}]},
    {"id": "n30", "r": 3, "c": 0, "g": "normal", "cost": 3, "e": [{"t": "s", "n": "Damage Boost", "v": 2}]},
    {"id": "n31", "r": 3, "c": 1, "g": "normal", "cost": 2, "e": [{"t": "s", "n": "Iron Wall", "v": 11}]},
    {"id": "n32", "r": 3, "c": 2, "g": "normal", "cost": 1, "e": [{"t": "s", "n": "Accuracy", "v": 7}]},
    {"id": "n33", "r": 3, "c": 3, "g": "normal", "cost": 4, "e": [{"t": "s", "n": "Critical", "v": 15}]},
    {"id": "n34", "r": 3, "c": 4, "g": "empty", "cost": 0, "e": []},
    {"id": "n40", "r": 4, "c": 0, "g": "normal", "cost": 2, "e": [{"t": "s", "n": "Defense", "v": 30}]},
    {"id": "n41", "r": 4, "c": 1, "g": "normal", "cost": 5, "e": [{"t": "s", "n": "Attack Bonus", "v": 22}]},
    {"id": "n42", "r": 4, "c": 2, "g": "normal", "cost": 3, "e": [{"t": "s", "n": "Block", "v": 12}]},
    {"id": "n43", "r": 4, "c": 3, "g": "empty", "cost": 0, "e": []},
    {"id": "n44", "r": 4, "c": 4, "g": "normal", "cost": 6, "e": [{"t": "s", "n": "Amplify All Damage", "v": 3}]},
]

DAEVANION_START_ID = "n00"

#: Four routing problems: one reachable target, a spread-out set, a set that
#: includes the walled-off n44 (the "skip what is left" branch), and nearly
#: the whole board at once.
DAEVANION_CASES = [
    {"name": "single_target", "wanted": ["n22"]},
    {"name": "spread", "wanted": ["n04", "n22", "n40"]},
    {"name": "unreachable", "wanted": ["n04", "n22", "n44"]},
    {"name": "many", "wanted": ["n04", "n14", "n22", "n24", "n33", "n41", "n42"]},
]


def daevanion_grid() -> dict:
    """``{(r, c): node}`` -- the structure the router actually walks."""
    return {(n["r"], n["c"]): n for n in DAEVANION_NODES}


def daevanion_node_by_id() -> dict:
    return {n["id"]: n for n in DAEVANION_NODES}


# ---------------------------------------------------------------------------
# an Arcana wishlist
# ---------------------------------------------------------------------------

#: ``{lord_type: [skill rows]}`` -- the pools a class really offers per Lord
#: card type.  Chalice is "both", Parchment/Compass/Scales "active",
#: Bell/Mirror "passive" (``_ARCANA_LORD_CATEGORY``); the pools below respect
#: that so the eligibility filter has something real to reject.
ARCANA_CLASS_SKILL_POOLS = {
    "Chalice": [
        {"id": "s_rush", "name": "Rushing Smash"},
        {"id": "s_spin", "name": "Spinning Strike"},
        {"id": "s_dark", "name": "Dark Crush"},
        {"id": "s_guard", "name": "Iron Guard"},
        {"id": "s_focus", "name": "Focus"},
    ],
    "Parchment": [
        {"id": "s_rush", "name": "Rushing Smash"},
        {"id": "s_onslaught", "name": "Onslaught"},
        {"id": "s_spin", "name": "Spinning Strike"},
        {"id": "s_cleave", "name": "Cleave"},
        {"id": "s_impact", "name": "Impactful Crush"},
    ],
    "Compass": [
        {"id": "s_onslaught", "name": "Onslaught"},
        {"id": "s_impact", "name": "Impactful Crush"},
        {"id": "s_dash", "name": "Dash"},
        {"id": "s_cleave", "name": "Cleave"},
    ],
    "Bell": [
        {"id": "s_guard", "name": "Iron Guard"},
        {"id": "s_focus", "name": "Focus"},
        {"id": "s_endure", "name": "Endure"},
        {"id": "s_vigor", "name": "Vigor Mastery"},
    ],
    "Mirror": [
        {"id": "s_focus", "name": "Focus"},
        {"id": "s_endure", "name": "Endure"},
        {"id": "s_reflect", "name": "Reflect"},
    ],
    # Scales exists in the pool data but has no Vigor/Magic theme entry, so
    # _arcana_usable_lord_types drops it -- the real Season-1 shape.
    "Scales": [
        {"id": "s_dash", "name": "Dash"},
        {"id": "s_cleave", "name": "Cleave"},
    ],
}

#: ``{skill_id: "active"|"passive"}``
ARCANA_SKILL_TYPE_BY_ID = {
    "s_rush": "active",
    "s_spin": "active",
    "s_dark": "active",
    "s_onslaught": "active",
    "s_cleave": "active",
    "s_impact": "active",
    "s_dash": "active",
    "s_guard": "passive",
    "s_focus": "passive",
    "s_endure": "passive",
    "s_vigor": "passive",
    "s_reflect": "passive",
}

#: ``{theme: {lord_type: entry}}`` -- only the two Season-1 themes, and
#: Scales in neither of them.
ARCANA_THEME_MAP = {
    "Vigor": {"Chalice": {}, "Parchment": {}, "Bell": {}},
    "Magic": {"Chalice": {}, "Compass": {}, "Mirror": {}},
    "Frenzy": {"Scales": {}},
}

ARCANA_TYPE_TO_THEME = {
    "Chalice": "Vigor",
    "Parchment": "Vigor",
    "Bell": "Vigor",
    "Compass": "Magic",
    "Mirror": "Magic",
}

#: Priority-list rank, lower is better -- the solver's documented tie-break.
ARCANA_PRIORITY_RANK = {
    "s_dark": 0,
    "s_onslaught": 1,
    "s_rush": 2,
    "s_spin": 3,
    "s_impact": 4,
    "s_focus": 5,
    "s_guard": 6,
    "s_cleave": 7,
    "s_endure": 8,
    "s_dash": 9,
}

#: Three wishlists: one comfortably satisfiable, one that forces competition
#: for the same card's 4 slots, and one asking for a skill no usable type can
#: ever roll (the "no eligible card" uncovered reason).
ARCANA_CASES = [
    {"name": "easy", "wishes": {"s_dark": 4, "s_rush": 2}},
    {"name": "competing", "wishes": {"s_dark": 4, "s_rush": 4, "s_spin": 4, "s_onslaught": 4, "s_impact": 3}},
    {"name": "impossible", "wishes": {"s_dash": 4, "s_focus": 2}},
]

# ---------------------------------------------------------------------------
# substat auto-pick
# ---------------------------------------------------------------------------

#: ``(name, sub_stats, count, priority_names)`` -- covers an exact walk, a
#: case-insensitive match, the documented alias, a count larger than the
#: matches available, and a priority list that matches nothing.
SUBSTAT_CASES = [
    {
        "name": "exact_order",
        "sub_stats": [{"name": "Critical Hit"}, {"name": "Attack"}, {"name": "Accuracy"}],
        "count": 2,
        "priority": ["Attack", "Accuracy", "Critical Hit"],
    },
    {
        "name": "case_insensitive",
        "sub_stats": [{"name": "defense INCREASE"}, {"name": "Attack"}],
        "count": 1,
        "priority": ["Defense Increase"],
    },
    {
        "name": "alias_movement_speed",
        "sub_stats": [{"name": "Move Speed"}, {"name": "Attack"}],
        "count": 1,
        "priority": ["Movement Speed"],
    },
    {
        "name": "falls_through_whole_list",
        "sub_stats": [{"name": "Endurance"}, {"name": "Block"}],
        "count": 3,
        "priority": ["Attack", "Accuracy", "Block", "Endurance"],
    },
    {
        "name": "no_match",
        "sub_stats": [{"name": "Endurance"}],
        "count": 2,
        "priority": ["Attack"],
    },
    {
        "name": "duplicate_names",
        "sub_stats": [{"name": "Attack"}, {"name": "Attack"}, {"name": "Accuracy"}],
        "count": 2,
        "priority": ["Attack", "Accuracy"],
    },
]
