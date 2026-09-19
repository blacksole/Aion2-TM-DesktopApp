"""The two Stage-2 recommendations, and the orchestrator the dashboard calls.

``docs/audit-2026-09-18/B-armory.md`` §3.4 lists five feasible features and
sizes two of them **S**, on the grounds that every input they need is already
on disk:

* **#2 missing set piece** — :func:`missing_set_pieces`.  ``dungeon_sets.json``
  plus the equipped items is genuinely all it takes, and the answer needs no
  model of anything: a set has slots, the player has some of them, the rest
  are missing and the catalog knows what they are called.
* **#1 stat gap vs role target** — delegated to :mod:`armory_engine.score`,
  in the coverage form that module's docstring argues for.

Both come back as :class:`~armory_engine.explain.Recommendation` objects
carrying reasons, per §3.3's rule that solvers never return bare picks, and
every string in them is a translation key.

:func:`next_best_actions` is the only function the host calls.  It resolves
the build out of the persisted state, decides which features can run with the
data that is actually present, and — when none can — returns the single
recommendation that says so.  The degradation is a return value, not an empty
list: a dashboard that cannot distinguish "nothing to improve" from "no data"
will show the wrong one, and on a fresh checkout it is always the second.
"""

from __future__ import annotations

from armory_engine.explain import Reason, Recommendation
from armory_engine.model import DetailProvider
from armory_engine.providers import DataBundle
from armory_engine.score import (
    display_names,
    merge_role_weights,
    stat_gap_ranked,
    stat_name_index,
    substat_alignment,
)
from armory_engine.stats import compute_stat_totals_detailed
from armory_engine.substats import _merge_stat_priority_profiles

__all__ = [
    "REASON_SET_MISSING_PIECE",
    "RECO_SET_INCOMPLETE",
    "RECO_STAT_GAP",
    "SET_SLOT_WORDS",
    "build_set_index",
    "missing_set_pieces",
    "next_best_actions",
    "set_root",
]

RECO_SET_INCOMPLETE = "armory_reco_set_incomplete"
REASON_SET_MISSING_PIECE = "armory_reason_set_missing_piece"
RECO_STAT_GAP = "armory_reco_stat_gap"

#: The trailing words a dungeon-set item name ends in, one per equip slot.
#:
#: MIRRORED from ``ItemDatabase/compute_dungeon_sets.py``'s
#: ``DUNGEON_SET_SLOT_WORDS``, which is the script that WRITES
#: ``dungeon_sets.json`` — the roots in that file were derived by stripping
#: exactly these words, so reading the file back and re-deriving a root with
#: a different list would silently fail to match.  Mirrored rather than
#: imported because the script is a standalone maintenance tool that reads
#: ``data/*.json`` at import time; the drift is not left to this comment
#: (``tests/test_armory_engine_recommend.py::test_the_slot_word_mirror_matches_the_script``
#: parses the script and compares).
SET_SLOT_WORDS: tuple[str, ...] = (
    "Helm", "Ring", "Boots", "Greatsword", "Breastplate", "Greaves", "Gloves",
    "Pauldrons", "Necklace", "Earrings", "Dagger", "Longsword", "Bow",
    "Spellbook", "Orb", "Mace", "Staff", "Fist", "Guard",
    "Bracelet", "Brooch", "Amulet",
)

#: Which of the six (gear type x role) profiles a dashboard with no role
#: picker uses.  The persisted state carries ``active_gear_types`` but NOT a
#: role — the role is a per-dialog selection in the Build Planner
#: (``StatPriorityEditorDialog.selected_role``), so there is nothing to read.
#: "Angreifer" is the one profile with real guide backing
#: (``substats._DEFAULT_STAT_PRIORITY_BY_CATEGORY``'s own comment: the other
#: five ship as copies of it), so it is the only defensible default — and the
#: recommendation says which profile it used, rather than implying the player
#: chose it.
DEFAULT_ROLE = "Angreifer"


def set_root(name: str, slot_words=SET_SLOT_WORDS) -> tuple[str, str] | None:
    """``"Abyssal Helm"`` -> ``("Abyssal", "Helm")``, else ``None``.

    The same suffix rule ``compute_dungeon_sets.py``'s pass 1 uses.  Its
    pass 2 (flavor-named Crafting weapons grouped by two-word prefix) is NOT
    reproduced: those three roots are excluded from the written file
    anyway (``EXCLUDED_FROM_OUTPUT``), except "Corroded Sovereign's", which
    is moved into Expedition — and a root that no item name resolves to
    simply contributes no pieces here, which is the correct degradation
    rather than a wrong grouping.
    """
    text = str(name or "")
    for word in slot_words:
        suffix = " " + word
        if text.endswith(suffix):
            return text[: -len(suffix)], word
    return None


def _roots_with_tags(dungeon_sets: dict) -> dict[str, dict]:
    """``{root: {"tag":…, "grade":…, "gearscore":…}}`` out of the written file.

    ``dungeon_sets.json`` is ``{source_tag: {root: {"grade":…,
    "gearscore":…}}}`` — ``sets.py``'s docstring still describes the older
    ``{root: grade}`` shape, so both are accepted here rather than trusting
    either.  A root under several tags keeps the alphabetically first, for
    determinism: the tag is shown to the player as "where this comes from"
    and a dashboard that renames it between two refreshes is a broken one.
    """
    result: dict[str, dict] = {}
    for tag in sorted(dungeon_sets or {}):
        roots = (dungeon_sets or {}).get(tag)
        if not isinstance(roots, dict):
            continue
        for root, info in roots.items():
            if root in result:
                continue
            if isinstance(info, dict):
                entry = {"grade": info.get("grade", ""), "gearscore": info.get("gearscore")}
            else:
                entry = {"grade": str(info or ""), "gearscore": None}
            result[str(root)] = {"tag": tag, **entry}
    return result


def build_set_index(items_by_id: dict, dungeon_sets: dict) -> dict[str, dict]:
    """``{root: {tag, grade, gearscore, pieces: {slot_word: {id, name}}}}``.

    One pass over the whole catalog, which is why it is a function of its
    own and why ``DataBundle`` caches the result: the dashboard recomputes
    its recommendations on every window activation, and ~3 000 name splits
    per focus change is a cost with no matching benefit.

    Bound and unbound copies of the identical item share a name (a confirmed
    data quirk, ``compute_dungeon_sets.py``'s own docstring); the lowest id
    wins so the piece a player is told to go get is the same one on every
    refresh.
    """
    index = {
        root: {**info, "pieces": {}}
        for root, info in _roots_with_tags(dungeon_sets).items()
    }
    for item_id, item in (items_by_id or {}).items():
        if not isinstance(item, dict):
            continue
        parsed = set_root(item.get("name") or "")
        if parsed is None:
            continue
        root, slot_word = parsed
        entry = index.get(root)
        if entry is None:
            continue
        previous = entry["pieces"].get(slot_word)
        if previous is None or int(item_id) < int(previous["id"]):
            entry["pieces"][slot_word] = {"id": int(item_id), "name": item.get("name") or ""}
    return index


def _item_id(value) -> int | None:
    """An equipped slot's value -> an item id.

    The persisted state holds the whole item dict per slot
    (``equip_builds_data[class][build]["equipped"]``), while §3.4's sketch
    and every test fixture think in ids.  Both are accepted rather than
    forcing one side to adapt — the id is the only field either shape is
    guaranteed to carry.
    """
    if isinstance(value, dict):
        value = value.get("id")
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _item_name(value, items_by_id: dict) -> str:
    item_id = _item_id(value)
    row = (items_by_id or {}).get(item_id) if item_id is not None else None
    if isinstance(row, dict) and row.get("name"):
        return str(row["name"])
    if isinstance(value, dict) and value.get("name"):
        return str(value["name"])
    return ""


def missing_set_pieces(
    equipped: dict,
    items_by_id: dict,
    dungeon_sets: dict,
    *,
    index: dict | None = None,
    limit: int = 0,
) -> list[Recommendation]:
    """Audit §3.4 feature #2: the sets this build has started and not finished.

    For every set root the player wears at least one piece of, the missing
    slots are listed with the set's source tag ("where do I get it").  Sets
    already complete produce nothing — there is no action to recommend — and
    a root no equipped item belongs to is not the player's problem.

    Sorted by completeness descending: the set that is one piece short is
    the one worth acting on, and the one at 1/6 is noise.  ``score_delta``
    is therefore the INVERSE of the sort key — the share of the set still
    missing — which is the one place in Stage 2 where
    ``explain.Recommendation``'s "reasons sum to the whole" really holds:
    each missing piece is one ``Reason`` worth ``1/total``, and they add up
    to ``score_delta`` exactly.

    ``limit`` of 0 means all of them.
    """
    index = build_set_index(items_by_id, dungeon_sets) if index is None else index

    owned: dict[str, set[str]] = {}
    for slot_id, value in (equipped or {}).items():
        parsed = set_root(_item_name(value, items_by_id))
        if parsed is None:
            continue
        root, slot_word = parsed
        if root in index:
            owned.setdefault(root, set()).add(slot_word)

    rows: list[tuple[float, str, Recommendation]] = []
    for root, slot_words in owned.items():
        entry = index[root]
        pieces: dict = entry.get("pieces") or {}
        total = len(pieces)
        have = len(slot_words & set(pieces))
        missing = sorted(set(pieces) - slot_words)
        if not total or not missing:
            continue
        share = 1.0 / total
        completeness = have / total
        reasons = tuple(
            Reason(
                # No stat is involved in completing a set, and inventing one
                # would be worse than saying so: ``stat_id`` is documented as
                # joinable onto a totals map, and "" is the honest "joins
                # onto nothing".  The piece travels in ``text_kwargs``.
                stat_id="",
                delta=1.0,
                weight=share,
                text_key=REASON_SET_MISSING_PIECE,
                text_kwargs={
                    "slot": slot_word,
                    "set": root,
                    "source": entry.get("tag", ""),
                    "item": (pieces.get(slot_word) or {}).get("name", ""),
                },
            )
            for slot_word in missing
        )
        rows.append((
            completeness,
            root,
            Recommendation(
                pick={
                    "kind": "set_completion",
                    "root": root,
                    "tag": entry.get("tag", ""),
                    "grade": entry.get("grade", ""),
                    "gearscore": entry.get("gearscore"),
                    "owned": have,
                    "total": total,
                    "completeness": completeness,
                    "missing": tuple(
                        {
                            "slot": slot_word,
                            "id": (pieces.get(slot_word) or {}).get("id"),
                            "name": (pieces.get(slot_word) or {}).get("name", ""),
                        }
                        for slot_word in missing
                    ),
                },
                score_delta=len(missing) * share,
                reasons=reasons,
                text_key=RECO_SET_INCOMPLETE,
                text_kwargs={
                    "set": root,
                    "owned": have,
                    "total": total,
                    "source": entry.get("tag", ""),
                },
            ),
        ))

    rows.sort(key=lambda row: (-row[0], row[1]))
    ordered = [recommendation for _, _, recommendation in rows]
    return ordered[:limit] if limit > 0 else ordered


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _active_build(state: dict) -> tuple[dict, dict, dict]:
    """``(equipped, substats, enchant)`` of the state's selected equip build.

    Mirrors ``ui/pages/armory_page.py``'s ``_current_build`` and
    MainWindow's own readers: ``equip_builds_data`` is keyed by
    ``character_class.lower()`` and the selected name defaults to "Default".
    An unresolvable class yields three empty dicts, which every feature
    below already degrades on.
    """
    class_key = str(state.get("character_class") or "").strip().lower()
    name = str(state.get("current_build_name") or "").strip() or "Default"
    build = _as_dict(_as_dict(_as_dict(state.get("equip_builds_data")).get(class_key)).get(name))
    return (
        _as_dict(build.get("equipped")),
        _as_dict(build.get("substats")),
        _as_dict(build.get("enchant")),
    )


def _substat_indices(raw) -> set[int]:
    """The persisted substat selection -> the ``set[int]`` the engine takes.

    On disk it is a list of indices (``model.EquipBuild``); in memory the
    Armory holds a set.  ``compute_stat_totals_detailed`` wants membership,
    so both are normalized here rather than in it.
    """
    result: set[int] = set()
    for value in raw if isinstance(raw, (list, tuple, set, frozenset)) else ():
        if isinstance(value, bool):
            continue
        try:
            result.add(int(value))
        except (TypeError, ValueError):
            continue
    return result


def _equipped_substat_names(equipped: dict, substats: dict, provider: DetailProvider) -> dict:
    """``{slot: [chosen substat names]}`` for :func:`score.substat_alignment`.

    The indices point into the item's own ``subStats``, so the names only
    exist once a detail is resolvable — a slot whose detail is missing
    contributes nothing instead of guessing, which is the same cold-cache
    rule ``compute_stat_totals_detailed`` follows.
    """
    result: dict[str, list[str]] = {}
    for slot_id, item in (equipped or {}).items():
        detail = provider.get(_item_id(item))
        if not detail:
            continue
        sub_stats = detail.get("subStats") or []
        names = [
            str(sub_stats[i].get("name") or "")
            for i in sorted(_substat_indices(substats.get(slot_id)))
            if i < len(sub_stats)
        ]
        names = [name for name in names if name]
        if names:
            result[str(slot_id)] = names
    return result


def next_best_actions(
    state: dict | None,
    provider: DetailProvider | None,
    data: DataBundle,
    *,
    limit: int = 5,
    top_k: int = 3,
) -> list[Recommendation]:
    """What the Armory dashboard shows, in the order it shows it.

    Ordering is by how actionable the finding is, not by score: a set that
    is one piece short names an item to go and get, the substat alignment
    names slots to re-pick, and the stat gap is a diagnosis. So:

    1. up to three incomplete sets (feature #2),
    2. the substat alignment (feature #1, the actionable half),
    3. the stat-coverage gap (feature #1, the diagnostic half).

    Degradation, in the order it is checked:

    * no data pack -> exactly one recommendation carrying
      ``data.reason_key``, so the card says why it is empty;
    * no ``dungeon_sets.json`` -> no set recommendations, the rest still run;
    * no provider, or no detail on disk for any equipped item -> no stat
      features at all (a build whose pieces cannot be read has no measurable
      coverage, and reporting it as "no piece provides this" would be a
      sentence about the cache, not about the build); the set
      recommendations still run, since they need names, not details;
    * nothing to say with data that IS present -> an empty list, which the
      dashboard renders as "nothing to improve" rather than as an error.

    The role profile used is ``DEFAULT_ROLE`` under the gear type the Build
    Planner's own toggle selects (``"PvP" in active_gear_types``, the same
    test app.py's Quick Select makes); both travel in the stat-gap
    recommendation's ``text_kwargs`` so the sentence can name them.
    """
    if not data.available:
        return [
            Recommendation(
                pick={"kind": "unavailable", "missing": data.missing},
                score_delta=0.0,
                text_key=data.reason_key,
            )
        ]

    state = _as_dict(state)
    equipped, substats, enchant = _active_build(state)
    if not equipped:
        return []

    recommendations: list[Recommendation] = []
    if data.dungeon_sets:
        if data.set_index is None:
            data.set_index = build_set_index(data.items_by_id, data.dungeon_sets)
        recommendations += missing_set_pieces(
            equipped, data.items_by_id, data.dungeon_sets, index=data.set_index, limit=3
        )

    gear_type = "PvP" if "PvP" in set(state.get("active_gear_types") or ()) else "PvE"
    profiles = _merge_stat_priority_profiles(_as_dict(state.get("stat_priority_profiles")))
    categories = _as_dict(_as_dict(profiles.get(gear_type)).get(DEFAULT_ROLE))
    weights = merge_role_weights(categories)
    names = display_names(categories)

    if provider is not None and weights:
        alignment = substat_alignment(
            _equipped_substat_names(equipped, substats, provider), weights, names=names
        )
        if alignment.text_key:
            recommendations.append(alignment)

        totals, by_slot = compute_stat_totals_detailed(equipped, {
            slot: _substat_indices(value) for slot, value in substats.items()
        }, enchant, provider)
        resolved = {slot: provider.get(_item_id(item)) for slot, item in equipped.items()}
        # Slots whose detail did NOT resolve are excluded from the coverage
        # denominator, and empty totals skip the feature entirely: "no piece
        # provides Critical Hit" and "no piece could be read" produce the
        # same numbers and mean opposite things, so the second must not be
        # reported as the first (the cold-cache state is the normal one).
        ranked = stat_gap_ranked(
            totals,
            weights,
            by_slot=by_slot,
            slots=tuple(sorted(str(slot) for slot, detail in resolved.items() if detail)),
            index=stat_name_index(resolved.values()),
            names=names,
            top_k=top_k,
        ) if totals else []
        if ranked:
            recommendations.append(
                Recommendation(
                    pick={
                        "kind": "stat_gap",
                        "gear_type": gear_type,
                        "role": DEFAULT_ROLE,
                        "shortfalls": tuple(shortfall for shortfall, _ in ranked),
                    },
                    score_delta=sum(shortfall for shortfall, _ in ranked),
                    reasons=tuple(reason for _, reason in ranked),
                    text_key=RECO_STAT_GAP,
                    text_kwargs={
                        "count": len(ranked),
                        "gear_type": gear_type,
                        "role": DEFAULT_ROLE,
                    },
                )
            )

    return recommendations[:limit] if limit > 0 else recommendations
