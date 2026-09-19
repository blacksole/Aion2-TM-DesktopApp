"""The Daevanion Board's greedy Steiner router.

Moved verbatim out of ``ItemDatabase/app.py`` (audit B-armory.md §2.4/§3.1,
old app.py:12426–12528): neighbour walk, reachability rule, board cap,
multi-source Dijkstra and the greedy connect loop.

What stayed in app.py: ``_daevanion_variant`` and ``_load_daevanion_raw``
(they read ``data/daevanion_boards_{s,a}.json`` and cache per variant),
``_daevanion_stat_key`` and the label tables (display), and the canvas.

WHY THERE IS NO ``heapq`` HERE
------------------------------
Audit §2.4 notes the Dijkstra uses an O(V²) linear scan; a heap is the
obvious "while you are in there" improvement, and V = 225 makes it look free.
It is not behaviour-preserving, and this was measured rather than assumed
before the move (400 randomized 6×6 boards, ``prev``/``dist`` compared
against a ``heapq`` port):

* ``dist`` is identical on every board — as Dijkstra guarantees.
* ``prev`` — the parent pointers that decide WHICH of several equal-cost
  paths gets materialized, and therefore which nodes actually enter the
  tree and what the route costs downstream — **differed on 169 of 400
  boards**.

The reason is the tie-break.  The linear scan's ``d < best_d`` keeps the
FIRST minimum it meets, i.e. ``grid.values()`` insertion order; a heap breaks
ties on ``(distance, node_id)``, i.e. node-id order.  Costs here are small
integers on a dense grid, so equal-cost ties are the common case, not the
corner case.  (A first pass of this experiment showed zero mismatches — with
synthetic ``r{r}c{c}`` ids, whose lexicographic order happens to equal the
grid's own row-major order.  Real questlog node ids are arbitrary strings.)

So: the linear scan stays.  A heap would need an explicit tie-break on the
grid's insertion index to be equivalent, and that is a deliberate change with
its own approval, not a Stage-1 move.  ``tests/test_armory_engine_golden.py``
pins 12 seeded random boards' full routes so either decision stays honest.
"""

from __future__ import annotations

__all__ = [
    "_DAEVANION_MP_NAMES",
    "_daevanion_compute_auto_route",
    "_daevanion_is_reachable",
    "_daevanion_neighbors",
    "_daevanion_node_mp_count",
    "_daevanion_path_nodes_to_add",
    "_daevanion_shortest_from_tree",
    "_daevanion_spent_cost",
    "_daevanion_total_cost",
]

def _daevanion_neighbors(r: int, c: int) -> list[tuple[int, int]]:
    return [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]


def _daevanion_is_reachable(node: dict, grid: dict, active: set) -> bool:
    """A node with no real stat/skill value can never bridge two others --
    only nodes with a real value connect to each other (User-Wunsch,
    2026-08-28: "Es können zum verbinden nur Felder genutzt werden, die
    Werte beinhalten")."""
    if node["id"] in active:
        return True
    for rc in _daevanion_neighbors(node["r"], node["c"]):
        nb = grid.get(rc)
        if nb and nb["g"] != "empty" and nb["id"] in active:
            return True
    return False


def _daevanion_total_cost(grid: dict) -> int:
    return sum(n["cost"] for n in grid.values())


def _daevanion_spent_cost(active: set, node_by_id: dict) -> int:
    return sum(node_by_id[nid]["cost"] for nid in active if nid in node_by_id)


_DAEVANION_MP_NAMES = {"mpmax", "Max MP"}  # "a" data uses the lowercase questlog code, "s" data the plain name


def _daevanion_node_mp_count(node: dict) -> int:
    return 1 if any(e.get("t") == "s" and e.get("n") in _DAEVANION_MP_NAMES for e in node.get("e") or []) else 0


def _daevanion_shortest_from_tree(grid: dict, tree: set, node_by_id: dict):
    """Multi-source Dijkstra from every node already in `tree` (distance
    (0, 0)) -- distance is (points, mpNodeCount), Python tuples already
    compare lexicographically: cheapest point cost wins outright, ties
    broken toward fewer Max MP nodes crossed (User-Wunsch, 2026-08-28).
    "empty" cells are skipped entirely, never traversable."""
    inf = (float("inf"), float("inf"))
    dist = {n["id"]: ((0, 0) if n["id"] in tree else inf) for n in grid.values()}
    prev: dict[str, str] = {}
    visited: set[str] = set()
    while len(visited) < len(dist):
        best_id, best_d = None, inf
        for nid, d in dist.items():
            if nid not in visited and d < best_d:
                best_d, best_id = d, nid
        if best_id is None:
            break
        visited.add(best_id)
        n = node_by_id[best_id]
        for rc in _daevanion_neighbors(n["r"], n["c"]):
            nb = grid.get(rc)
            if not nb or nb["g"] == "empty" or nb["id"] in visited:
                continue
            in_tree = nb["id"] in tree
            nd = (best_d[0] + (0 if in_tree else nb["cost"]), best_d[1] + (0 if in_tree else _daevanion_node_mp_count(nb)))
            if nd < dist[nb["id"]]:
                dist[nb["id"]] = nd
                prev[nb["id"]] = best_id
    return dist, prev


def _daevanion_path_nodes_to_add(prev: dict, target_id: str, tree: set) -> list[str]:
    chain = []
    cur = target_id
    while cur is not None:
        chain.append(cur)
        if cur in tree:
            break
        cur = prev.get(cur)
    return chain


def _daevanion_compute_auto_route(grid: dict, node_by_id: dict, wanted_ids: set, start_id: str) -> dict:
    """Greedy Steiner-tree heuristic (identical to the approved browser
    mockup): repeatedly connects whichever wanted node is currently
    cheapest to reach from the tree built so far, until every wanted node
    is connected or the board's point cap runs out."""
    tree = {start_id}
    cap = _daevanion_total_cost(grid)
    spent = 0
    remaining = set(wanted_ids) - {start_id}
    included: set[str] = set()
    skipped: set[str] = set()
    while remaining:
        dist, prev = _daevanion_shortest_from_tree(grid, tree, node_by_id)
        best_id, best_d = None, (float("inf"), float("inf"))
        for nid in remaining:
            d = dist.get(nid, (float("inf"), float("inf")))
            if d < best_d:
                best_d, best_id = d, nid
        if best_id is None or best_d[0] == float("inf") or spent + best_d[0] > cap:
            skipped |= remaining
            break
        for nid in _daevanion_path_nodes_to_add(prev, best_id, tree):
            if nid not in tree:
                tree.add(nid)
                spent += node_by_id[nid]["cost"]
        included.add(best_id)
        remaining.discard(best_id)
    return {"tree": tree, "included": included, "skipped": skipped, "spent": spent, "cap": cap}
