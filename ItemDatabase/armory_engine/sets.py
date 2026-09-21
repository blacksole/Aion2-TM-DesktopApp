"""The precomputed dungeon-set table.

Moved out of ``ItemDatabase/app.py`` (old ``_build_dungeon_sets``,
app.py:10797) with one signature change, which is the point of moving it: the
second parameter was typed ``"ItemDetailCache"``, a ``QObject`` holding a
``QNetworkAccessManager``.  Audit B-armory.md §3.2 item 2 names that as the
coupling that blocks the engine, and the fix as a tiny ``DetailProvider``
protocol.  So the parameter is now
:class:`~armory_engine.model.DetailProvider` — and since the Qt cache already
satisfies it structurally, app.py's call site is unchanged.

Both parameters are, today, unused.  That is not an oversight either: an
earlier live version of this really did group ~3 000 items and read each
one's detail through the cache, and it measured ~17 s on a cold cache — far
too slow for a dialog that should open instantly.  It was replaced by the
precomputed ``data/dungeon_sets.json`` that ``compute_dungeon_sets.py``
writes.  The parameters stay because the callers pass them and because the
shape of "given the catalog and a detail source, what sets exist" is what a
set-completion recommendation (audit §3.4 feature 2) will need back.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from armory_engine.model import DetailProvider

__all__ = ["DUNGEON_SETS_PATH", "_build_dungeon_sets", "clear_cache"]

logger = logging.getLogger("item_database")

#: ``ItemDatabase/data/dungeon_sets.json``.  Resolved from this package's own
#: location rather than from ``app.py``'s, and the two agree in both modes:
#: the package sits inside ``ItemDatabase/``, so ``parent.parent`` is the same
#: directory ``Path(app.py).parent`` gives — in a source checkout and under
#: ``_MEIPASS/ItemDatabase/`` in a frozen build alike.
DUNGEON_SETS_PATH = Path(__file__).resolve().parent.parent / "data" / "dungeon_sets.json"

#: Loaded at most once per process (the file is a few hundred KB and the
#: dialog that reads it wants to open instantly).  ``None`` means "not read
#: yet", which is distinct from ``{}`` meaning "read, and there was nothing".
_cache: dict[str, dict[str, str]] | None = None


def clear_cache() -> None:
    """Drop the memoized table — for tests that point ``path`` somewhere else."""
    global _cache
    _cache = None


# Dungeon gear (Neutral gear type, User-Wunsch 2026-08-26: "zusätzlich zu dem
# gecrafteten Gear kommt in die Auswahl das Equipment aus den Dungeons") is
# NOT one clean tier ladder like RACE_TIER_ROOT's crafted line -- it's ~174
# independent named sets (e.g. "Abyssal Helm"/"Abyssal Ring"/... share the
# root "Abyssal"). Their real drop location isn't in the raw catalog at all;
# the closest signal is each item's detail "sources" list. Which tags
# actually produce real, level-45, >=3-slot sets is entirely a property of
# the current data (compute_dungeon_sets.py checks all ~21 tags found in the
# catalog and keeps whichever aren't empty -- e.g. Attendance/Subscribe/
# Ascension never do, they're login/cash-shop rewards, not gear), so this is
# read straight from data/dungeon_sets.json's own keys at runtime rather
# than a hardcoded list that would drift out of sync with it.


def _build_dungeon_sets(
    items_by_id: dict,
    detail_provider: DetailProvider | None = None,
    path: Path | None = None,
) -> dict[str, dict[str, str]]:
    """Returns ``{source_tag: {root_name: grade}}``, one entry per source tag
    ``compute_dungeon_sets.py`` found at least one real set for -- the grade
    lets the Rarität filter narrow the Dungeon-Set dropdown too (User-
    Wunsch, 2026-08-26: "Ich weiß ja, dass in der Liste auch blaue Sets
    dabei sind, nicht nur goldene" -- Legend/blue and Unique/gold both
    appear, confirmed real: e.g. Expedition alone is 13 Unique/6 Legend/3
    Epic at level 45).

    Loads the precomputed data/dungeon_sets.json (see compute_dungeon_sets.py
    -- same offline-maintenance-script convention as fetch_item_details.py,
    run whenever the catalog is refreshed) instead of scanning live: an
    earlier live version of this (grouping ~3000 items and reading each
    one's detail file via ItemDetailCache.request()) measured ~17s on a
    cold cache -- far too slow for a dialog that should open instantly.
    Falls back to an empty result if the precomputed file is missing
    (e.g. a dev checkout that hasn't run the script yet), rather than ever
    falling back to the slow live scan again.
    """
    global _cache
    if path is None and _cache is not None:
        return _cache

    sets_path = path or DUNGEON_SETS_PATH
    result: dict[str, dict[str, str]] = {}
    if sets_path.exists():
        try:
            result = json.loads(sets_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to load %s -- Dungeon-Quelle dropdown will be empty", sets_path)
    else:
        logger.warning(
            "%s not found -- run compute_dungeon_sets.py. Dungeon-Quelle dropdown will be empty.",
            sets_path,
        )

    if path is None:
        _cache = result
    return result
