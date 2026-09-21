"""Shared shapes for the engine — the dicts the Armory already passes around.

Audit B-armory.md §1 opens with "everything is plain dicts": game entities
flow from ``data/*.json`` and two runtime caches as raw dictionaries, and 48
classes in app.py are all Qt widgets.  These TypedDicts do not change that —
they are ``total=False`` descriptions of the *existing* shapes, so every dict
already in flight keeps type-checking and nothing has to be constructed
differently.  They exist to make the engine's signatures say what they take.

The one real abstraction here is :class:`DetailProvider`.  Per audit §3.2
item 2, ``ItemDetailCache`` is a ``QObject`` holding a
``QNetworkAccessManager``, and every totals/score computation used to need
one.  A ``Protocol`` with a single ``get`` method breaks that: the engine
depends on the method, the Qt cache satisfies it structurally without
inheriting anything, and a test can pass a dict-backed stub.
"""

from __future__ import annotations

from typing import Protocol, TypedDict, runtime_checkable

__all__ = [
    "BuildState",
    "Detail",
    "DetailProvider",
    "EquipBuild",
    "Item",
    "StatEntry",
    "StatTotals",
    "StatsBySlot",
]


class StatEntry(TypedDict, total=False):
    """One row of a detail's ``mainStats`` / ``subStats``.

    ``value`` is deliberately untyped-ish: the API returns plain numbers,
    percent strings (``"3%"``) and ranges (``"396 ~ 545"``) in the same field.
    ``armory_engine.stats.parse_stat_value`` is the one place that decides
    what a given spelling is worth.
    """

    id: str
    name: str
    value: object


class Item(TypedDict, total=False):
    """A catalog row, as ``data/items_all.json`` ships it and as the equipped
    slots hold it.  Only ``id`` is load-bearing for the engine — everything
    else here is what the UI reads off the same dict."""

    id: int
    name: str
    grade: str
    categoryName: str
    iconUrl: str
    price: int


class Detail(TypedDict, total=False):
    """One item's detail response — the shape ``ItemDetailCache.get`` returns
    and the per-``id`` ``data/details/{id}.json`` disk cache holds.

    ``level`` is the item's GearScore contribution; ``maxEnchantLevel`` is the
    item's OWN normal cap (15 for Legend/Unique, 20 for Epic/Heroic, 10 for a
    Belt), past which the enchant bonus freezes and the Exceed lines start.
    """

    level: int
    gradeName: str
    grade: str
    categoryName: str
    maxEnchantLevel: int
    mainStats: list[StatEntry]
    subStats: list[StatEntry]
    sources: list[dict]
    subSkillCountMax: int


#: ``{stat_id: value}`` after id normalization (see ``GEAR_STAT_ID_ALIASES``).
StatTotals = dict[str, float]

#: ``{stat_id: {slot_id: contribution}}`` — the breakdown behind every total,
#: which is what lets the Stat Info tooltip say *which piece* a number came
#: from, and what a future explanation engine attributes a delta with.
StatsBySlot = dict[str, dict[str, float]]


class EquipBuild(TypedDict, total=False):
    """One saved Equip Build, as persisted under
    ``build_planner -> equip_builds_data[class][name]``.

    ``substats`` is ``{slot_id: set[int]}`` in memory and a list of indices on
    disk; ``enchant`` is ``{slot_id: level}``.
    """

    equipped: dict[str, Item]
    substats: dict[str, set[int]]
    enchant: dict[str, int]
    philosopher_stone: dict
    priority: dict
    priority_progress: dict
    linked_skill_build: str
    linked_genius_build: str


class BuildState(TypedDict, total=False):
    """The whole Build Planner state — the single dict
    ``LoadoutWindow.get_persistable_state`` returns and the host persists
    under the profile key ``"build_planner"``.

    Pinned key-for-key by ``tests/test_build_planner_state.py``, which exists
    because this serialization is explicit-key: a key added to the live state
    but not to ``get_persistable_state`` is silently dropped on the next
    round-trip (audit B-armory.md §1, MED).
    """

    character_class: str
    character_race: str
    current_build_name: str
    active_gear_types: list[str]
    stat_priority_profiles: dict
    monolith_level: int
    skill_levels: dict[str, int]
    skill_arcana_wish: dict[str, int]
    skill_active_specs: dict[str, list[int]]
    current_skill_build_name: str
    skill_builds_data: dict
    equip_builds_data: dict
    daevanion_active: dict
    daevanion_filter_checked: dict
    genius_builds_data: dict
    current_genius_build_name: str
    pantheon_slots: dict


@runtime_checkable
class DetailProvider(Protocol):
    """Anything that can answer "what do I know about item N?".

    ``ItemDetailCache`` (app.py) satisfies this as-is — it is a ``QObject``
    with exactly this ``get``, so the engine never has to know that behind the
    method sit a disk cache and a batched POST to shugo.gg.  A test passes a
    dict lookup; a future batch job could pass a straight file reader.

    Returning ``None`` for an unknown id is part of the contract, not an error
    path: a cold cache is the normal state on first paint, and every engine
    call site skips an item it cannot resolve rather than raising.
    """

    def get(self, item_id: int | None) -> Detail | None:  # pragma: no cover - protocol
        ...
