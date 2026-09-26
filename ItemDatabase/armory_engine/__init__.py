"""The Armory's calculation core — pure Python, and deliberately Qt-free.

Stage 1 of the split laid out in ``docs/audit-2026-09-18/B-armory.md`` §4.2.
``ItemDatabase/app.py`` is 23 000 lines of interleaved Qt and arithmetic; the
arithmetic was already pure (§3.1) but unreachable without importing PySide6
and executing the whole module, monkey-patch included.  Everything in this
package was moved out of app.py **verbatim** — same names, same numbers, same
documented quirks — and app.py imports it back under those names, so every
internal call site is unchanged.

**The rule this package exists to enforce: no module in here may import
PySide6, directly or transitively.**  ``tests/test_armory_engine_qt_free.py``
imports each one in a subprocess with a meta-path finder that makes any
PySide6 import raise, so the rule is checked rather than remembered.  It is
what lets the solvers be tested, profiled and reused (a CLI, a batch
recompute, a future recommendation engine) without a display.

The one thing the engine genuinely needs from the Qt side is item details,
and it takes them through :class:`~armory_engine.model.DetailProvider` — a
structural protocol with a single ``get(item_id) -> dict | None`` method that
``ItemDetailCache`` already satisfies without changing a line.

Modules
-------
``model``       shared shapes: Item/Detail/EquippedItem TypedDicts, DetailProvider.
``enchant``     the four calibrated estimators, the Rune curve, GearScore push.
``substats``    the priority-profile defaults and the greedy substat auto-pick.
``arcana``      the best-case Lord-card solver and its coverage/"why not" reporting.
``daevanion``   the greedy Steiner router over the Daeva board.
``transfer``    the upgrade-hop graph, material trees and the Kinah rollup.
``sets``        the precomputed dungeon-set table.
``stats``       the per-slot stat merge and GearScore, over a DetailProvider.
``explain``     the data contract every recommendation returns.
``providers``   the disk-backed DetailProvider and the catalog DataBundle.
``score``       rank-derived role weights, stat coverage, substat alignment.
``recommend``   set completion, and the orchestrator the dashboard calls.
``compare``     the Item Compare window's data contract + comparison builder.

Stage 2 added the last three (audit §3.4 features #1 and #2).  They keep the
rule: ``providers`` is the only module that touches the filesystem, and it
does it with ``json`` and ``pathlib``, not with Qt.

Nothing is re-exported here on purpose: app.py imports from the leaf modules
by name, which keeps the "where did this come from" answer one grep away.
"""

__all__ = [
    "arcana",
    "compare",
    "daevanion",
    "enchant",
    "explain",
    "model",
    "providers",
    "recommend",
    "score",
    "sets",
    "stats",
    "substats",
    "transfer",
]
