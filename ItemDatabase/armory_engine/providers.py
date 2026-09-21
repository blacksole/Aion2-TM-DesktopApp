"""Disk-backed data access — the one module in the engine that touches the
filesystem, and the reason the rest of it does not have to.

Stage 2 of ``docs/audit-2026-09-18/B-armory.md``.  §3.2 named the coupling
that blocked a recommendation engine and Stage 1 broke it with
:class:`~armory_engine.model.DetailProvider`: a one-method ``Protocol`` that
``ItemDatabase/app.py``'s Qt ``ItemDetailCache`` satisfies structurally.  A
recommendation, though, has to run **before** anyone opens the Armory window
— the dashboard draws on the landing page, with no ``QNetworkAccessManager``
anywhere near it.  So the engine needs a second implementation of that same
protocol, one that reads the disk cache ``fetch_item_details.py`` writes and
nothing else.  That is :class:`DiskDetailProvider`.

**Never fetches, never writes, never raises.**  A missing directory, a
missing file and an unparseable file are all the same answer — ``None`` —
because they are all the same situation for the caller: this clone does not
have the data pack.  That is the normal state of a fresh checkout (the pack
is ~278 MB of runtime cache and is not in git), so it is the path the
dashboard is *designed* around rather than an error branch bolted on after.

:class:`DataBundle` is the same idea one level up: the three catalog files a
recommendation needs, loaded once, with an explicit ``available`` /
``reason_key`` pair instead of a silent empty result.  A UI that has to guess
whether "no recommendations" means "your build is perfect" or "the data is
missing" will guess wrong, so the bundle answers it.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from armory_engine.model import Detail

__all__ = [
    "ARMORY_CACHE_SUBDIR",
    "CATALOG_SUBDIR",
    "DATA_MISSING_KEY",
    "DETAILS_SUBDIR",
    "DUNGEON_SETS_FILE",
    "ITEMS_FILE",
    "STAT_PRIORITY_OPTIONS_FILE",
    "DataBundle",
    "DiskDetailProvider",
    "load_data_bundle",
    "load_json_or_none",
    "resolve_armory_dirs",
]

logger = logging.getLogger("item_database")

#: The three files under ``ItemDatabase/data/`` a recommendation reads.
#: Named here rather than assembled at the call site so the host never has to
#: repeat a filename that only this package knows the meaning of.
ITEMS_FILE = "items_all.json"
DUNGEON_SETS_FILE = "dungeon_sets.json"
STAT_PRIORITY_OPTIONS_FILE = "stat_priority_options.json"

#: Translation key for "the Armory data pack is not on this machine".  A KEY,
#: like every other string the engine produces (see :mod:`armory_engine.explain`).
DATA_MISSING_KEY = "armory_reco_needs_data"

#: Directory names ``ItemDatabase/app.py`` uses.  Mirrored here, in the one
#: module of the engine that is allowed to know a path, so that the host and
#: the Armory window cannot drift (see :func:`resolve_armory_dirs`).
CATALOG_SUBDIR = "data"
DETAILS_SUBDIR = "details"
ARMORY_CACHE_SUBDIR = "armory"


def resolve_armory_dirs(frozen: bool, bundle_dir: Path | str,
                        cache_dir: Path | str) -> tuple[Path, Path]:
    """``(catalog_dir, details_dir)`` — the two trees, which are NOT one tree.

    This function exists because one caller assumed they were.  The catalog
    (``items_all.json`` & co.) is **read-only payload**: it ships in the
    bundle and, frozen, extracts under ``_MEIPASS/ItemDatabase/data``.  The
    detail cache is **written at runtime** by ``ItemDetailCache``, so frozen
    it cannot live in the bundle at all — ``app.py``'s ``_cache_root()``
    puts it under ``user_cache_dir()/armory``, because the bundle directory
    is re-extracted every launch (onefile) and an install under
    ``/opt``, ``/usr/lib`` or ``Program Files`` is not writable.

    From source the two coincide (``ItemDatabase/data`` and
    ``ItemDatabase/data/details``), which is exactly why deriving the second
    from the first passed every test and every dev run while being wrong in
    the only build users install: ``"Aion2 TM.spec"`` deliberately never
    ships ``details/``, so a provider pointed at the bundle reads an empty
    directory **forever** and two of the three recommendation features
    silently never appear.

    ``frozen``, ``bundle_dir`` and ``cache_dir`` are parameters rather than
    read off ``sys`` here for two reasons: the engine must stay Qt-free and
    side-effect-free (MASTER §5-1), and a frozen layout has to be testable
    from a source run — see
    ``tests/test_armory_dashboard.py::test_the_two_armory_dirs_mirror_the_armorys_own_constants``,
    which computes app.py's own ``_BUNDLE_DIR``/``DETAIL_CACHE_DIR`` under a
    faked frozen layout and compares them to this function's answer.

    ``cache_dir`` is ``utils.paths.user_cache_dir()`` — the *parent* of the
    Armory's cache root, not the root itself, so the ``"armory"`` segment
    that ``_cache_root()`` appends is spelled in exactly one place here.
    Nothing is created: this is a pure path computation.
    """
    catalog = Path(bundle_dir) / CATALOG_SUBDIR
    if not frozen:
        # app.py: `_cache_root()` -> `BASE_DIR / "data"`, and from source
        # BASE_DIR is ItemDatabase/ -- the same tree as the catalog.
        return catalog, catalog / DETAILS_SUBDIR
    return catalog, Path(cache_dir) / ARMORY_CACHE_SUBDIR / DETAILS_SUBDIR


def load_json_or_none(path: Path | str):
    """Parse ``path``, or return ``None`` for every way that can fail.

    The three failures are deliberately collapsed: absent (no data pack),
    unreadable (permissions, a half-written file from an interrupted fetch)
    and malformed (a truncated download).  None of them is recoverable here
    and all of them mean the same thing to a caller that is drawing a card.
    Logged at WARNING when the file exists but could not be used, silent when
    it simply is not there — the second is the expected state of a checkout,
    the first is a real problem worth a line in the log.
    """
    file_path = Path(path)
    if not file_path.is_file():
        return None
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        logger.warning("armory_engine: could not read %s (%s)", file_path, error)
        return None


class DiskDetailProvider:
    """``DetailProvider`` over ``data/details/{id}.json``.

    Satisfies the protocol structurally, exactly like ``ItemDetailCache``
    does, so anything the engine already takes a provider for accepts this
    one unchanged — ``compute_stat_totals_detailed`` included.

    **Both hits and misses are memoized.**  A miss is the common case on a
    checkout without the pack, and a build of 20 slots re-read 20 absent
    paths on every dashboard refresh (which fires on every window
    activation) would be 20 syscalls per focus change for a permanently
    known answer.  ``None`` stored in the cache is that answer.

    The cache is unbounded on purpose: its ceiling is the number of distinct
    item ids a single build can reference, i.e. a couple of dozen, not the
    ~3 000-item catalog.  A batch job that walked the whole catalog through
    one instance would want a bound; nothing in the app does.
    """

    def __init__(self, details_dir: Path | str):
        self._dir = Path(details_dir)
        self._cache: dict[int, Detail | None] = {}

    @property
    def details_dir(self) -> Path:
        return self._dir

    @property
    def cached_ids(self) -> tuple[int, ...]:
        """Ids answered so far, hits and misses alike — read by tests to
        prove the memoization, never by the app."""
        return tuple(sorted(self._cache))

    def get(self, item_id: int | None) -> Detail | None:
        """The protocol's whole surface.  ``None`` for an id this machine
        has no detail file for, which is never an error (see the module
        docstring)."""
        if item_id is None:
            return None
        try:
            key = int(item_id)
        except (TypeError, ValueError):
            return None
        if key in self._cache:
            return self._cache[key]
        payload = load_json_or_none(self._dir / f"{key}.json")
        detail = payload if isinstance(payload, dict) else None
        self._cache[key] = detail
        return detail


def _items_by_id(payload) -> dict[int, dict]:
    """``items_all.json`` -> ``{id: item}``.

    The file ships as ``{"items": [...]}`` but ``compute_dungeon_sets.py``
    already guards for a bare list (``data.get("items", data)``), so this
    accepts both rather than being the one reader that does not.  Rows
    without a usable integer id are dropped: an id is the only field the
    engine joins on, so a row without one cannot participate in anything.
    """
    rows = payload.get("items", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return {}
    result: dict[int, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            result[int(row["id"])] = row
        except (KeyError, TypeError, ValueError):
            continue
    return result


@dataclass
class DataBundle:
    """The catalog side of a recommendation, loaded once.

    Not frozen, and not because anything mutates the data: ``set_index``
    below is a derived table that costs a pass over the whole catalog, and
    the dashboard recomputes its recommendations on every window activation.
    Caching it on the bundle is what keeps that pass from happening 50 times
    a session.  The three data fields are never written after construction.

    ``available`` / ``reason_key`` are the graceful-degradation contract
    (audit §3.4): a consumer asks the bundle whether there is anything to
    reason about, and gets a translation key to show when there is not —
    rather than an empty list that reads as "nothing to improve".
    """

    items_by_id: dict[int, dict] = field(default_factory=dict)
    dungeon_sets: dict = field(default_factory=dict)
    stat_priority_options: dict = field(default_factory=dict)
    #: Filenames that were looked for and not found — for the log and for
    #: tests; the UI shows ``reason_key``, never this.
    missing: tuple[str, ...] = ()
    #: Lazily filled by :func:`armory_engine.recommend.build_set_index`.
    set_index: dict | None = field(default=None, repr=False, compare=False)

    @property
    def available(self) -> bool:
        """True when the item catalog was found.

        ``items_all.json`` is the marker for the whole pack, not an
        arbitrary pick: ``fetch_items.py`` writes it first and every other
        file in ``data/`` is derived from it, so a machine with the details
        or the set table but not the catalog does not occur in practice.
        Per-feature requirements are still checked per feature — a bundle
        can be available and still carry no ``dungeon_sets``.
        """
        return bool(self.items_by_id)

    @property
    def reason_key(self) -> str:
        """The translation key explaining an empty result, or ``""``."""
        return "" if self.available else DATA_MISSING_KEY


def load_data_bundle(data_dir: Path | str) -> DataBundle:
    """Read the three catalog files out of one ``ItemDatabase/data``.

    The directory is passed in rather than derived here: the engine must not
    know whether it is running from a source checkout or from inside a
    PyInstaller bundle (``_MEIPASS/ItemDatabase``).  app.py's ``_BUNDLE_DIR``
    owns that decision and the host mirrors it — see
    ``MainWindow._armory_data_dir``.
    """
    base = Path(data_dir)
    payloads = {name: load_json_or_none(base / name) for name in
                (ITEMS_FILE, DUNGEON_SETS_FILE, STAT_PRIORITY_OPTIONS_FILE)}
    return DataBundle(
        items_by_id=_items_by_id(payloads[ITEMS_FILE]),
        dungeon_sets=payloads[DUNGEON_SETS_FILE] if isinstance(payloads[DUNGEON_SETS_FILE], dict) else {},
        stat_priority_options=(
            payloads[STAT_PRIORITY_OPTIONS_FILE]
            if isinstance(payloads[STAT_PRIORITY_OPTIONS_FILE], dict)
            else {}
        ),
        missing=tuple(name for name, payload in payloads.items() if payload is None),
    )
