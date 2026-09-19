"""The upgrade-hop graph, material trees and the Kinah rollup.

Moved verbatim out of ``ItemDatabase/app.py`` (audit B-armory.md §3.1, old
app.py:7216–7486): how an "upgrade hop" is detected from a recipe's own
ingredient list, the BFS that walks a multi-tier chain, the quantity-aware
material tree, its shopping-list flatten and its per-craft Kinah sum.

What stayed in app.py: ``_load_recipes`` and ``_recipe_method`` (they read
``data/recipes_all.json`` through ``RECIPE_DATA_PATH`` and apply the
app-level grade/profession label maps), and ``CRAFTING_CATEGORIES`` and the
colour/label tables around them.  The engine takes the *normalized* recipe
list ``_load_recipes`` produces.

The detection rule in ``_transfer_source_name`` is the subtle part and is
kept exactly as calibrated: a recipe is an upgrade hop when exactly one input
is consumed at qty 1, is neither the Transfer Stone nor a Kinah row, shares
its item-type word with the output, AND is the same grade.  The index is
built from ALL recipes, not just ``method == "Transfer"`` ones — a real chain
hop is often a pure-Kinah upgrade with no stone at all, and restricting to
Transfer recipes silently broke real chains one hop before their end.
"""

from __future__ import annotations

import re
from collections import deque

__all__ = [
    "_build_material_node",
    "_build_material_tree",
    "_build_recipe_output_index",
    "_build_transfer_source_index",
    "_compute_tree_kinah",
    "_find_transfer_path",
    "_flatten_material_tree",
    "_item_grade",
    "_item_type_word",
    "_ordered_tier_chain",
    "_parse_gold_cost",
    "_resolve_material_name",
    "_transfer_source_name",
]


def _item_type_word(name: str) -> str:
    """Last real word of an item name, ignoring a trailing "(Bound)"/"(...)"
    tag -- used to check that an upgrade recipe's single-qty source item is
    actually the same equipment slot as its output (see
    _transfer_source_name)."""
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
    parts = name.split()
    return parts[-1] if parts else ""


def _item_grade(name: str | None, item_id: int | None, items_by_id: dict, output_index: dict) -> str | None:
    item = items_by_id.get(item_id) if item_id else None
    if item and item.get("grade"):
        return item["grade"]
    recipe = output_index.get(name) if name else None
    return recipe.get("grade") if recipe else None


def _transfer_source_name(recipe: dict, items_by_id: dict, output_index: dict) -> str | None:
    """A recipe is an "upgrade hop" (Transfer-Stone or Kinah-only alike) if
    exactly one input is consumed at qty 1, isn't the stone or a pure Kinah
    row, shares its item-type word with the output (e.g. both end in
    "Boots"), AND -- confirmed by the user -- is the SAME grade tier as the
    output (a real Transfer/Splendent upgrade never jumps e.g. "Legend"
    (blue) straight to "Unique" (gold) in one hop; that's a normal
    Herstellung recipe instead, not a chain link). The word check alone is
    needed because a good chunk of ordinary multi-material recipes also
    happen to consume exactly one other craftable item at qty 1 as a plain
    catalyst (e.g. "Wrathful Mind" x1 into a completely unrelated "Celestial
    Dragon Lord Ring"); the grade check on top catches the rarer case where
    the shared word is coincidental AND the two items happen to be
    different tiers. Verified against the full dataset: with just the word
    check, 288 of the real 304 Transfer-Stone recipes match (the rest have
    >1 qty-1 input) plus 482 further Kinah-only upgrade hops are found this
    way; every single one of those is already same-grade (706x Unique-
    Unique, 36x Legend-Legend, 26x Rare-Rare), so the grade check costs
    zero real matches and only guards against a hop the game doesn't
    actually have. Shared module-level (not just CraftingCalculatorWindow)
    so the Build Planner's Schnellauswahl can derive the same tier chains."""
    candidates = [
        i for i in recipe["inputs"]
        if (i.get("qty") or 1) == 1 and i.get("name")
        and "Transfer Stone" not in i["name"] and "Kina" not in i["name"]
    ]
    if len(candidates) != 1:
        return None
    candidate = candidates[0]
    candidate_name = candidate["name"]
    output_name = recipe["outputs"][0].get("name") or ""
    if _item_type_word(candidate_name) != _item_type_word(output_name):
        return None
    candidate_grade = _item_grade(candidate_name, candidate.get("id"), items_by_id, output_index)
    output_grade = recipe.get("grade")
    if candidate_grade and output_grade and candidate_grade != output_grade:
        return None
    return candidate_name


def _build_transfer_source_index(recipes: list[dict], items_by_id: dict, output_index: dict) -> dict[str, list[dict]]:
    """Upgrade-chain recipes indexed by their "source" item -- built from
    ALL recipes, not just method=="Transfer" ones, because a real chain hop
    is often a pure-Kinah upgrade with no Transfer Stone at all (e.g.
    "Celestial Dragon Lord Boots" -> "Splendent Celestial Dragon Lord
    Boots" for 15,000,000 Kina, no stone) -- restricting to Transfer Stone
    recipes alone silently broke real chains one hop before their end."""
    index: dict[str, list[dict]] = {}
    for r in recipes:
        source = _transfer_source_name(r, items_by_id, output_index)
        if source:
            index.setdefault(source, []).append(r)
    return index


def _find_transfer_path(start_name: str, target_name: str, transfer_source_index: dict) -> list[dict] | None:
    """BFS over upgrade-hop recipes from start_name to target_name -- real
    chains can span multiple tiers (verified 3-hop example: Splendent
    White -> Wise -> Splendent Wise -> Celestial Dragon Lord Boots)."""
    if start_name == target_name:
        return []
    queue = deque([(start_name, [])])
    visited = {start_name}
    while queue:
        current, path = queue.popleft()
        if len(path) >= 12:
            continue
        for recipe in transfer_source_index.get(current, []):
            output_name = recipe["outputs"][0].get("name")
            if output_name in visited:
                continue
            new_path = path + [recipe]
            if output_name == target_name:
                return new_path
            visited.add(output_name)
            queue.append((output_name, new_path))
    return None


def _ordered_tier_chain(root_name: str, type_word: str, transfer_source_index: dict) -> list[str]:
    """BFS from root_name, returning tier-prefix names (root_name itself,
    then every reachable output, each with its trailing type_word stripped)
    in visitation order -- a real, natural tier progression order since
    each hop is exactly one upgrade step. Used to populate the Build
    Planner's Schnellauswahl tier dropdown (see project_todo.md: verified
    against real data that the tier-prefix sequence is identical across
    equipment slot types for the same race, e.g. Ring/Boots/Necklace/
    Dagger/Greatsword all reach the same 9 prefixes for "True Dragon Lord")."""
    def strip_word(name: str) -> str:
        return name[: -(len(type_word) + 1)] if name.endswith(" " + type_word) else name

    order = [strip_word(root_name)]
    queue = deque([root_name])
    visited = {root_name}
    while queue:
        current = queue.popleft()
        for recipe in transfer_source_index.get(current, []):
            output_name = recipe["outputs"][0].get("name")
            if output_name in visited:
                continue
            visited.add(output_name)
            order.append(strip_word(output_name))
            queue.append(output_name)
    return order


def _parse_gold_cost(raw) -> int:
    """Raw values are comma-formatted strings like "4,000" (or already 0)."""
    if raw is None:
        return 0
    try:
        return int(str(raw).replace(",", "").strip())
    except ValueError:
        return 0


def _build_recipe_output_index(recipes: list[dict]) -> dict[str, dict]:
    """Maps a craftable item's name to the recipe that makes it — lets a
    recipe's own ingredient list be checked for "is this itself craftable"
    without a separate hand-built table. Real multi-tier upgrade chains
    (e.g. Base -> Fine -> Pure -> Artisan's Orichalcum Longsword) fall out
    of this automatically rather than needing to be curated by hand.

    Indexes EVERY output name, not just outputs[0] -- some recipes have a
    second output for a bonus-chance "Splendent" variant (e.g. recipe
    111014001 outputs both "Artisan's Orichalcum Longsword" [guaranteed]
    and "Artisan's Splendent Orichalcum Longsword" [bonus chance]). Only
    indexing the first output meant looking up that second name -- which is
    exactly what a parent recipe's own ingredient list references -- found
    nothing, silently truncating the chain one tier early."""
    index: dict[str, dict] = {}
    for r in recipes:
        for output in r["outputs"]:
            index.setdefault(output["name"], r)
    return index


def _resolve_material_name(name: str | None, item_id: int | None, items_by_id: dict) -> str | None:
    """A handful of recipe inputs carry no name in the scraped data (the
    scraper's own gap, not a missing item) even though the id resolves fine
    in the item catalog -- fall back to that instead of showing "None"."""
    if name:
        return name
    item = items_by_id.get(item_id) if item_id else None
    return item.get("name") if item else None


def _build_material_node(
    name: str | None, item_id: int | None, qty: int, output_index: dict, items_by_id: dict, depth: int = 0,
) -> dict:
    """One node of the quantity-aware material tree used by the Crafting
    Simulator's Baum/Liste views. qty is "how many of this material are
    needed per ONE unit of its parent" -- NOT yet scaled by how many of the
    parent are actually needed; that scaling happens at render/flatten time
    (multiplying down the tree), so the same tree is reusable across
    different Anzahl values without rebuilding it. depth caps at 20 as a
    cheap guard against a data cycle."""
    name = _resolve_material_name(name, item_id, items_by_id)
    node = {"name": name, "id": item_id, "qty": qty, "mastery": None, "goldCost": 0, "children": None}
    if depth >= 20 or not name:
        return node
    recipe = output_index.get(name)
    if recipe is None:
        return node
    node["mastery"] = recipe.get("masteryLevel")
    node["goldCost"] = recipe.get("goldCost", 0)
    node["children"] = [
        _build_material_node(m.get("name"), m.get("id"), m.get("qty") or 1, output_index, items_by_id, depth + 1)
        for m in recipe.get("inputs", [])
    ]
    return node


def _build_material_tree(recipe: dict, output_index: dict, items_by_id: dict) -> dict:
    """Root node for a selected recipe -- mirrors _build_material_node's
    shape, just seeded directly from the chosen recipe instead of a
    name lookup."""
    output = recipe["outputs"][0]
    return {
        "name": output["name"], "id": output.get("id"), "qty": 1,
        "mastery": recipe.get("masteryLevel"), "goldCost": recipe.get("goldCost", 0),
        "children": [
            _build_material_node(m.get("name"), m.get("id"), m.get("qty") or 1, output_index, items_by_id, 1)
            for m in recipe.get("inputs", [])
        ],
    }


def _flatten_material_tree(node: dict, needed_qty: int, totals: dict[str, dict]):
    """Recursively sums every leaf material across the whole tree, regardless
    of how deep it sits -- the "Liste" (shopping-list) view's data source."""
    if not node.get("children"):
        entry = totals.setdefault(node["name"], {"qty": 0, "id": node.get("id")})
        entry["qty"] += needed_qty
        return
    for child in node["children"]:
        _flatten_material_tree(child, needed_qty * (child.get("qty") or 1), totals)


def _compute_tree_kinah(node: dict, needed_qty: int) -> int:
    """Kinah fee paid per craft attempt at every tier that's actually
    crafted (raw/gathered leaf materials have no fee here)."""
    if not node.get("children"):
        return 0
    total = (node.get("goldCost") or 0) * needed_qty
    for child in node["children"]:
        total += _compute_tree_kinah(child, needed_qty * (child.get("qty") or 1))
    return total
