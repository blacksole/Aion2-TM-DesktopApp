"""Enchant, Exceed and GearScore estimators — the Armory's calibrated numbers.

Moved verbatim out of ``ItemDatabase/app.py`` (audit B-armory.md §3.1/§4.2,
old app.py:1187–1440): same constants, same curves, same comments recording
what each number was fitted against.  Nothing here was re-derived — the point
of the move is that the arithmetic becomes testable without Qt, not that it
changes.

Names keep their leading underscore where app.py had one.  That underscore is
app.py's own "module-private" convention, and app.py imports these back under
exactly these names so none of its ~700 internal call sites had to change;
renaming them is a separate decision from moving them.

``ENCHANT_RATES.json`` / ``ENCHANT_RATES.md`` remain documentation of the
117-sample calibration and are read by no Python file (audit §1, LOW: two
sources of truth).  ``tests/test_enchant_model.py`` closes that loop by
asserting every documented row against these functions.
"""

from __future__ import annotations

__all__ = [
    "estimate_armor_bonus",
    "estimate_armor_exceed_bonus",
    "estimate_enchant_bonus",
    "estimate_exceed_bonus",
    "_ACCESSORY_CATEGORIES",
    "_ARMOR_CATEGORIES",
    "_BELT_CATEGORY",
    "_DEFENSE_STAT_ID",
    "_GEARSCORE_EXCEED_RATE",
    "_GEARSCORE_NORMAL_RATE",
    "_GEAR_STAT_ID_ALIASES",
    "_HP_STAT_ID",
    "_RUNE_PVE_ITEM_ID",
    "_RUNE_PVP_ITEM_ID",
    "_SCALING_STAT_ID",
    "_gearscore_push",
    "_rune_enchant_bonus",
]

# Real per-item substat ids that don't match the id this file otherwise
# uses for the SAME real stat (confirmed 2026-08-30 via an audit of every
# distinct stat id across ~2200 cached item detail responses against
# _STAT_ID_DISPLAY_NAME/_MAIN_STAT_ROWS etc. -- User-Wunsch: "prüfen, ob
# alle Werte des gesamten Gears in die Stats mit einfließen"). Without
# this, gear rolling any of these ids was silently summed under the raw
# id and never shown anywhere or counted toward the row it clearly means
# (e.g. real gear uses "BackAttackDamage", but the "Back Attack" row
# expects "BackAttack" -- same stat, so any gear piece rolling it was
# invisible). Normalized here, at gear-collection time, rather than
# renaming the established row ids themselves, since those same ids are
# also targeted by Genius/Daevanion/Arcana/Attribute mappings elsewhere.
_GEAR_STAT_ID_ALIASES = {
    "Accuracy": "AccuracyBonus",
    "Evasion": "EvasionBonus",
    "Perfect": "PerfectChance",
    "Defense": "DefenseBonus",
    "FixingDamage": "AttackBonus",
    "WeaponDamage": "MaxAttack",
    "CriticalAddDamage": "CriticalAttack",
    "BackAttackDamage": "BackAttack",
    "FrontAttackDamage": "FrontAttack",
    "BackAttackCritical": "BackAttackCriticalHit",
    "FrontAttackCritical": "FrontAttackCriticalHit",
    "BackAttackDefense": "BackDefense",
    "FrontAttackDefense": "FrontDefense",
    "BackAttackCriticalResist": "BackAttackCriticalHitResist",
    "FrontAttackCriticalResist": "FrontAttackCriticalHitResist",
    "DecreaseBackAttack": "BackAttackDamageTolerance",
    "DecreaseFrontAttack": "FrontAttackDamageTolerance",
    "DecreaseWeaponDamage": "WeaponDamageTolerance",
    "DecreaseDamage": "DamageTolerance",
    "DecreaseCriticalDamage": "CriticalDamageTolerance",
    "IgnoreIronWall": "EndurancePenetration",
    "IgnoreRestoration": "RegenerationPenetration",
    "PvEAddDamage": "PvEAttack",
    "PvEDamageDefense": "PvEDefense",
    "BossNpcAddDamage": "BossAttack",
    # Real Bracelets ("Ludra's Bracelet", "Abyssal Bracelet", etc.) can
    # roll a raw Empyrean Lord stat directly as a substat -- completely
    # independent of Arcana cards (User-reported, 2026-08-30). Aliased
    # straight to the same "XxxLordPoints" id Arcana card contributions
    # use, so both sources land in the same total/tooltip automatically;
    # see _arcana_lord_stat_totals_detailed for how the derived %-stats
    # (Combat Speed etc.) then combine both sources' points.
    "Time": "TimeLordPoints", "Space": "SpaceLordPoints", "Justice": "JusticeLordPoints",
    "Freedom": "FreedomLordPoints", "Illusion": "IllusionLordPoints", "Life": "LifeLordPoints",
    "Destiny": "DestinyLordPoints", "Wisdom": "WisdomLordPoints", "Death": "DeathLordPoints",
    "Destruction": "DestructionLordPoints",
}

# The one main stat that scales with enchant — identified by id, not by
# whether the item happens to display it as a range or a flat number
# (e.g. Guard shows a flat "Attack: 136", Greatsword/Staff show a range).
_SCALING_STAT_ID = "WeaponFixingDamage"

# Accessories use a completely different (and much simpler) rate than
# weapons/guards for the same scaling stat — confirmed universal across
# every grade sampled.
_ACCESSORY_CATEGORIES = {"Necklace", "Earrings", "Ring", "Bracelet", "Brooch", "Amulet"}
_ACCESSORY_RATE_PER_LEVEL = 5.0

# (k, p) for bonus = k * level**p, fit to real data pulled from 12 actual
# characters' actually-equipped gear via the API (101 samples total, see
# project notes) — one real anchor point plus the confirmed frozen value at
# the grade's own maxEnchantLevel:
#   Legend: lvl1->+10, lvl5->+50                      (exactly linear)
#   Unique: lvl6->+65, lvl10->+125, lvl12->+165, cap lvl15->+225
#   Heroic (Epic): CONFIRMED exactly linear, +17.5/level (350/20 = 17.5,
#     verified against a real +20 screenshot — always whole-number bonuses
#     in-game, never fractional; one outlier sub-cap sample we scraped
#     ("Ludra's Grimoire", a Spellbook, showing +125 at level 10 instead of
#     the expected +175) contradicted this and is treated as bad/anomalous
#     data — likely a scrape glitch — rather than overriding the confirmed
#     linear rate.
# Common/Rare: no samples found (no low-level max-enchanted gear exists in
# practice) — falls back to the Legend shape as a rough placeholder.
_WEAPON_CURVE_PARAMS = {
    "Legend": (10.0, 1.0),
    "Unique": (5.733, 1.355),
}
_HEROIC_RATE_PER_LEVEL = 17.5
_DEFAULT_WEAPON_CURVE = (10.0, 1.0)

# Clash Rune (id 310900001, PvE) / Devotion Rune (id 310900002, PvP) --
# real per-enchant-level growth from "Kanon's Aion 2 Bible" CH2 (2026-08-
# 29 research), NOT the generic estimate_enchant_bonus/estimate_armor_
# bonus curve below (neither knows "Rune" as a category, and shugo.gg's
# own enchant simulator keeps every one of this item's stat values frozen
# across all 10 levels -- confirmed live, so its numbers can't be trusted
# for Runes either). Level-0 base values (Combat Speed 1%, Penetration
# 100, Multi-hit Chance 1%, +the PvE/PvP Damage Boost/Tolerance 0.5%) come
# from the item's own real mainStats via the normal per-slot loop in
# _compute_stat_totals_detailed -- this only adds the DELTA above that
# base for a given enchant level, User-Wunsch 2026-09-04: "die Runen
# reinbringen, so genau wie moeglich - die Successchance koennen wir
# rauslassen" (enchant success % intentionally not modeled, real numbers
# don't exist anywhere).
#
# Combat Speed/Multi-hit Chance don't scale linearly from level 0 -- they
# stay at their base value until a threshold level, then gain +1%/level
# from there on. The guide gives the threshold levels (+6 / +9) but never
# a single concrete "value AT level N" example to pin down whether the
# threshold level itself already shows the first bump or the level after
# it does -- this file assumes the FIRST bump lands ON the threshold
# level (e.g. Combat Speed: level 5 = 1%, level 6 = 2%, level 7 = 3%...).
# Multi-hit Chance's own +9 threshold is additionally flagged UNCONFIRMED
# by the guide itself ("Never seen one, need confirmation") -- treat its
# numbers as the best available estimate, not a verified fact.
_RUNE_PVE_ITEM_ID = 310900001  # Clash Rune
_RUNE_PVP_ITEM_ID = 310900002  # Devotion Rune
_RUNE_COMBAT_SPEED_THRESHOLD = 6
_RUNE_MULTI_HIT_THRESHOLD = 9


def _rune_enchant_bonus(item_id: int, level: int) -> dict[str, float]:
    if level <= 0:
        return {}
    bonus = {
        "CombatSpeed": max(0, level - _RUNE_COMBAT_SPEED_THRESHOLD + 1) * 1.0,
        "DefensePierce": level * 50.0,
        "AdditionalHitRate": max(0, level - _RUNE_MULTI_HIT_THRESHOLD + 1) * 1.0,
    }
    if item_id == _RUNE_PVE_ITEM_ID:
        bonus["PvEAmplifyDamage"] = level * 0.5
        bonus["PvEDecreaseDamage"] = level * 0.5
    elif item_id == _RUNE_PVP_ITEM_ID:
        bonus["PvPAmplifyDamage"] = level * 0.5
        bonus["PvPDecreaseDamage"] = level * 0.5
    return bonus


def estimate_enchant_bonus(
    level: int, grade_name: str = "", normal_max_level: int = 0, category_name: str = "",
) -> float:
    """Estimated bonus ADDED ALONGSIDE (never into) a weapon/armor's ranged
    main stat (e.g. Attack) at a given enchant level — the base min~max
    range itself is always shown completely unchanged, exactly like the
    in-game '396 ~ 545 (+350)' display: only the '(+N)' part is new.

    Only the one main stat that has this id scales with enchant at all —
    verified via the API against real, actually-equipped items: Accuracy/
    Critical Hit/Block/etc. never changed at any enchant level.

    Accessories (Ring, Necklace, ...) scale at a flat, grade-independent
    rate; weapons/guards follow a grade-dependent curve — both fit to real
    data (see the constants above).

    The bonus FREEZES at the item's own maxEnchantLevel (confirmed: this
    varies by grade — Legend/Unique cap at 15, Epic/Heroic at 20) — past
    that point (Exceed range) it stops growing entirely; instead two new
    separate bonus lines appear (see estimate_exceed_bonus)."""
    effective_level = min(level, normal_max_level) if normal_max_level else level
    if effective_level <= 0:
        return 0.0
    if category_name in _ACCESSORY_CATEGORIES:
        return _ACCESSORY_RATE_PER_LEVEL * effective_level
    if grade_name == "Heroic":
        # Confirmed exactly linear at +17.5/level — a real, precise rate,
        # so odd levels land on a decimal internally (e.g. level 1 -> 17.5);
        # _format_number() rounds this to a whole number for display, since
        # in-game bonus displays are always whole numbers.
        return _HEROIC_RATE_PER_LEVEL * effective_level
    k, p = _WEAPON_CURVE_PARAMS.get(grade_name, _DEFAULT_WEAPON_CURVE)
    return k * (effective_level ** p)


def estimate_exceed_bonus(level: int, normal_max_level: int, category_name: str = "") -> dict:
    """Past the item's normal max enchant level (the Exceed range), new
    separate stat lines appear on top of the (now frozen) ranged main stat
    bonus. Confirmed via ~40 real Exceed-range samples (3/4/5 Exceed steps,
    both Unique and Epic grade — rate is identical across grades, only
    category changes it):
      - Weapons/Guards: flat 'Attack' +30/step, 'Attack increase' +1%/step.
      - Accessories: flat 'Attack' +20/step, a separate 'Defense' +40/step,
        'Attack increase' +1%/step (all three lines shown together)."""
    if not normal_max_level or level <= normal_max_level:
        return {"attack": 0.0, "attack_pct": 0.0, "defense": 0.0}
    steps = level - normal_max_level
    if category_name in _ACCESSORY_CATEGORIES:
        return {"attack": 20.0 * steps, "attack_pct": 1.0 * steps, "defense": 40.0 * steps}
    return {"attack": 30.0 * steps, "attack_pct": 1.0 * steps, "defense": 0.0}


# Armor (body pieces) scales TWO main stats simultaneously — Defense AND HP
# — unlike weapons/accessories, which only scale one. Confirmed via 16 real
# samples across all 7 armor slots (Helm/Top/Pauldrons/Gloves/Legs/Shoes/
# Cloak) at both Unique and Epic/Heroic grade, all internally consistent:
#   Unique: Defense cap 450 @15 (=30/level), HP cap 300 @15 (=20/level)
#   Heroic (Epic): Defense cap 700 @20 (=35/level), HP cap 400 @20 (=20/level)
# HP rate is grade-independent (20/level both grades); Defense rate is not.
# Belt is its OWN special case — own maxEnchantLevel of 10 (not 15/20), and
# BOTH grades gave the identical capped values (Defense 300 / HP 500 @10),
# i.e. Belt's rate is grade-independent entirely: 30/level Defense,
# 50/level HP.
_ARMOR_CATEGORIES = {"Helm", "Top", "Pauldrons", "Gloves", "Legs", "Shoes", "Cloak"}
_BELT_CATEGORY = "Belt"
_DEFENSE_STAT_ID = "ArmorDefense"
_HP_STAT_ID = "HPMax"

_ARMOR_DEFENSE_RATE = {"Unique": 30.0, "Heroic": 35.0}
_DEFAULT_ARMOR_DEFENSE_RATE = 30.0
_ARMOR_HP_RATE_PER_LEVEL = 20.0

_BELT_DEFENSE_RATE_PER_LEVEL = 30.0
_BELT_HP_RATE_PER_LEVEL = 50.0


def estimate_armor_bonus(
    level: int, grade_name: str = "", normal_max_level: int = 0, category_name: str = "",
) -> tuple[float, float]:
    """Returns (defense_bonus, hp_bonus) for an armor piece — see the
    constants above for the data this is calibrated against."""
    effective_level = min(level, normal_max_level) if normal_max_level else level
    if effective_level <= 0:
        return 0.0, 0.0
    if category_name == _BELT_CATEGORY:
        return (
            round(_BELT_DEFENSE_RATE_PER_LEVEL * effective_level),
            round(_BELT_HP_RATE_PER_LEVEL * effective_level),
        )
    def_rate = _ARMOR_DEFENSE_RATE.get(grade_name, _DEFAULT_ARMOR_DEFENSE_RATE)
    return round(def_rate * effective_level), round(_ARMOR_HP_RATE_PER_LEVEL * effective_level)


def estimate_armor_exceed_bonus(level: int, normal_max_level: int) -> dict:
    """Exceed range for armor: both Defense and HP get +80/step (confirmed
    identical across Unique and Epic grade), plus a +1%/step 'increase' on
    each — four new lines total, vs. weapons/accessories' two or three."""
    if not normal_max_level or level <= normal_max_level:
        return {"defense": 0.0, "defense_pct": 0.0, "hp": 0.0, "hp_pct": 0.0}
    steps = level - normal_max_level
    return {"defense": 80.0 * steps, "defense_pct": 1.0 * steps, "hp": 80.0 * steps, "hp_pct": 1.0 * steps}


# The GearScore push from enchanting is its OWN real rate — confirmed via
# shugo.gg's live character/equipment/item endpoint (a real enchant-level
# simulator: TW NCSoft's own API, proxied by shugo.gg, returns a per-item
# 'levelValue' for a given characterId/slotPos/enchantLevel combo) against
# 4 independent real equipped items pulled from real TW characters
# ("Levis"/"Skyvie", [HIT] legion, server 1009) swept across enchant 0/5/
# 10/15/20/25: a Heroic/Epic Staff (weapon), a Unique Guard (weapon-like),
# an Epic/Heroic armor Shoulder piece, and an Epic Necklace (accessory).
# All four gave IDENTICALLY +1.0 levelValue per normal enchant level and
# +5.0 per Exceed step (the DELTA between consecutive sweep points) —
# completely independent of grade or category, and clearly NOT the same
# rate as the Attack/Defense/HP stat bonuses (e.g. a Heroic weapon's
# Attack bonus is +17.5/level, its GearScore push only +1/level).
# NOTE: every real sample's levelValue also carried a constant per-
# instance offset even at enchant 0 (13-24, varying by item) — almost
# certainly from that specific character's socketed magic/god stones,
# which our planner doesn't model at all (no UI/data for them) — so only
# the confirmed RATE is used here; push is 0 at enchant 0, matching
# shugo.gg's own static item-catalog API (always levelValue=0 unenchanted).
_GEARSCORE_NORMAL_RATE = 1.0
_GEARSCORE_EXCEED_RATE = 5.0


def _gearscore_push(enchant_level: int, normal_max_level: int) -> float:
    if enchant_level <= 0:
        return 0.0
    normal_steps = min(enchant_level, normal_max_level) if normal_max_level else enchant_level
    exceed_steps = max(0, enchant_level - normal_max_level) if normal_max_level else 0
    return _GEARSCORE_NORMAL_RATE * normal_steps + _GEARSCORE_EXCEED_RATE * exceed_steps


