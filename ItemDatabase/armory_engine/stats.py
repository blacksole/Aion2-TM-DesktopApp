"""The equipment stat merge and GearScore — the Armory's central arithmetic.

Extracted from ``LoadoutWindow._compute_stat_totals_detailed`` and
``LoadoutWindow._compute_gearscore`` (old app.py:19104 and :19173).  Audit
B-armory.md §3.1 calls the first one "*almost* pure -- its only impurity is
``self.detail_cache.get(...)``", and that is exactly what the extraction
confirmed: the bodies here are the originals with that one call replaced by
``provider.get(...)``.  Nothing else was read off ``self``, so nothing else
had to become a parameter.

``LoadoutWindow`` keeps both methods as thin wrappers that pass
``self.detail_cache``, so every call site inside app.py — and the Build
Compare tab that shares them — is unchanged.

This is the "core asset a recommendation engine must reuse" the audit names:
``by_slot`` is not a debugging extra, it is the per-piece attribution that
lets the Stat Info tooltip say where a number came from, and that a future
explanation (see :mod:`armory_engine.explain`) turns into "why this item".

NOT here, and deliberately: the SIX-source merge
(``LoadoutWindow._refresh_stat_info`` / ``_compute_full_build_totals``) that
adds Genius Insight, attribute-derived, Arcana-Lord, Daevanion, passive-skill
and wings totals on top of these equipment totals.  Those read eight further
pieces of ``self`` sub-state; see the note on ``_compute_full_build_totals``
in app.py for the list and for why that is a later stage.
"""

from __future__ import annotations

from armory_engine.enchant import (
    _ARMOR_CATEGORIES,
    _BELT_CATEGORY,
    _DEFENSE_STAT_ID,
    _GEAR_STAT_ID_ALIASES,
    _HP_STAT_ID,
    _SCALING_STAT_ID,
    _gearscore_push,
    _rune_enchant_bonus,
    estimate_armor_bonus,
    estimate_armor_exceed_bonus,
    estimate_enchant_bonus,
    estimate_exceed_bonus,
)
from armory_engine.model import DetailProvider, StatsBySlot, StatTotals

__all__ = ["_parse_stat_value", "compute_gearscore", "compute_stat_totals_detailed"]


def _parse_stat_value(raw) -> float:
    try:
        return float(str(raw).replace("%", "").strip())
    except (ValueError, TypeError):
        return 0.0


def compute_stat_totals_detailed(
    equipped: dict,
    substats: dict,
    enchant: dict,
    provider: DetailProvider,
) -> tuple[StatTotals, StatsBySlot]:
    """Equipment stat totals plus a per-slot breakdown
    (``by_slot[stat_id][slot_id] = contribution``) so the Stat Info tooltip
    can show exactly which equipped piece a value came from (User-Wunsch,
    2026-08-30: "auf die 3000+ attack hovern und sehen, woher diese attack
    stammen ... 50 atk Waffe / 100 atk Guard").

    ``equipped`` is ``{slot_id: item}``, ``substats`` is ``{slot_id: set of
    indices into that item's subStats}``, ``enchant`` is ``{slot_id: level}``.
    ``provider`` answers ``get(item_id) -> detail | None``; a slot whose
    detail is not resolvable is skipped, which is the normal cold-cache
    state rather than an error.
    """
    totals: StatTotals = {}
    by_slot: StatsBySlot = {}

    def add(slot_id: str, stat_id: str | None, value: float):
        if not stat_id or not value:
            return
        # Real gear can use a different id than this file's own
        # convention for the same stat (see _GEAR_STAT_ID_ALIASES) --
        # normalize before it ever reaches totals/by_slot.
        stat_id = _GEAR_STAT_ID_ALIASES.get(stat_id, stat_id)
        totals[stat_id] = totals.get(stat_id, 0.0) + value
        slot_totals = by_slot.setdefault(stat_id, {})
        slot_totals[slot_id] = slot_totals.get(slot_id, 0.0) + value

    for slot_id, item in equipped.items():
        detail = provider.get(item.get("id"))
        if not detail:
            continue
        for stat in detail.get("mainStats") or []:
            add(slot_id, stat.get("id"), _parse_stat_value(stat.get("value")))
        sub_stats = detail.get("subStats") or []
        for i in substats.get(slot_id, set()):
            if i < len(sub_stats):
                add(slot_id, sub_stats[i].get("id"), _parse_stat_value(sub_stats[i].get("value")))

        # Enchant bonus — same estimate formulas the item's own detail
        # panel uses for its "(+N)" line, so Stat Info stays consistent
        # with what that panel shows instead of ignoring the slider.
        level = enchant.get(slot_id, 0)
        if level:
            grade_name = detail.get("gradeName") or detail.get("grade") or ""
            category_name = detail.get("categoryName") or ""
            normal_max = int(detail.get("maxEnchantLevel") or 0)
            if category_name == "Rune":
                # Own real per-level curve -- see _rune_enchant_bonus's
                # docstring for why the generic estimators below don't
                # apply to this category at all.
                for stat_id, value in _rune_enchant_bonus(item.get("id"), level).items():
                    add(slot_id, stat_id, value)
                continue
            is_armor = category_name in _ARMOR_CATEGORIES or category_name == _BELT_CATEGORY
            if is_armor:
                def_bonus, hp_bonus = estimate_armor_bonus(level, grade_name, normal_max, category_name)
                add(slot_id, _DEFENSE_STAT_ID, def_bonus)
                add(slot_id, _HP_STAT_ID, hp_bonus)
                exceed = estimate_armor_exceed_bonus(level, normal_max)
                add(slot_id, _DEFENSE_STAT_ID, exceed["defense"])
                add(slot_id, _HP_STAT_ID, exceed["hp"])
                if exceed["defense_pct"]:
                    add(slot_id, "DefenseRatio", exceed["defense_pct"])
            else:
                bonus = estimate_enchant_bonus(level, grade_name, normal_max, category_name)
                add(slot_id, _SCALING_STAT_ID, bonus)
                exceed = estimate_exceed_bonus(level, normal_max, category_name)
                add(slot_id, _SCALING_STAT_ID, exceed["attack"])
                if exceed["attack_pct"]:
                    add(slot_id, "DamageRatio", exceed["attack_pct"])
                if exceed["defense"]:
                    add(slot_id, _DEFENSE_STAT_ID, exceed["defense"])
    return totals, by_slot


def compute_gearscore(equipped: dict, enchant: dict, provider: DetailProvider) -> float:
    """Σ each equipped detail's own ``level``, plus the enchant push.

    The push rate is its own confirmed number (+1.0 per normal enchant
    level, +5.0 per Exceed step, independent of grade and category — see
    ``enchant._gearscore_push``), deliberately NOT the same rate as the
    Attack/Defense/HP stat bonuses.
    """
    total = 0.0
    for slot_id, item in equipped.items():
        detail = provider.get(item.get("id"))
        if not detail or not detail.get("level"):
            continue
        total += detail["level"]
        level = enchant.get(slot_id, 0)
        if not level:
            continue
        normal_max = int(detail.get("maxEnchantLevel") or 0)
        total += _gearscore_push(level, normal_max)
    return total
