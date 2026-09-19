"""The explainability contract — data only, no logic yet.

Audit B-armory.md §3.3 states it as a rule rather than a feature: *solvers
never return bare picks*.  Every recommendation the engine will grow — the
stat-gap report, the missing set piece, the best upgrade for a slot, the
cheapest GearScore +N, what to craft next (§3.4) — returns the choice
together with the numbers that produced it, so the UI can render "why this
item" out of data the engine already computed rather than guessing after the
fact.

The surface to render it on already exists: Build Compare's per-stat delta
rows (app.py's ``_rebuild_compare_stat_rows``) are exactly a list of
(stat, value A, value B, coloured delta), and
``armory_engine.stats.compute_stat_totals_detailed`` already returns the
per-slot attribution those deltas would be explained from.

This module ships in Stage 1 with the shapes and none of the logic, on
purpose: fixing the return type before the first solver is written is what
stops solver number two from inventing its own.  Both dataclasses are frozen
— a Reason is a record of a computation that already happened.

``text_key`` is a translation KEY, never display text.  Everything the
Armory shows goes through ``_t()`` at widget-build time (app.py's
``_ARMORY_LANGUAGE``), so a Reason built during a solve must survive a
language switch that happens before it is rendered.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["Recommendation", "Reason"]


@dataclass(frozen=True)
class Reason:
    """One weighted contribution behind a recommendation.

    :param stat_id: the normalized stat id (post ``_GEAR_STAT_ID_ALIASES``),
        so it joins straight onto a totals/``by_slot`` map.
    :param delta: how much this stat changes if the recommendation is taken —
        signed, in the stat's own units, not normalized.
    :param weight: what that change was worth to the active role profile.
        Today's profiles are ordinal ranks, not weights (audit §2.2), so the
        first consumer will derive this from rank; keeping it a float here
        means a real weight vector later is a data change, not a shape change.
    :param text_key: translation key for the human sentence, resolved through
        ``_t()`` at render time.  ``text_kwargs`` carries its format
        arguments, exactly like ``_arcana_uncovered_reason`` already returns
        a ``(key, kwargs)`` pair.
    """

    stat_id: str
    delta: float
    weight: float
    text_key: str
    text_kwargs: dict = field(default_factory=dict)

    @property
    def score_contribution(self) -> float:
        """``delta * weight`` — this reason's share of the total score delta.

        Named rather than inlined so the sum over a recommendation's reasons
        is verifiably its ``score_delta``: a solver whose parts do not add up
        to its whole is showing the player an explanation that is not the
        reason.
        """
        return self.delta * self.weight


@dataclass(frozen=True)
class Recommendation:
    """A pick, what it is worth, and why.

    :param pick: what is being recommended.  Intentionally untyped: an item
        dict for a slot upgrade, a set root name for set completion, a
        ``(slot_id, level)`` pair for an enchant step.
    :param score_delta: the scalar improvement over the current build, in the
        same units the reasons' ``score_contribution`` values sum to.
    :param reasons: the per-stat breakdown, best first.  Never empty for a
        real recommendation — a pick with no reasons is a pick with no
        explanation, which §3.3 exists to forbid.
    :param text_key: translation key for the recommendation's own headline —
        the one line the dashboard shows before the player expands "Why?".
        Added in Stage 2, with a default, because the first two solvers
        proved the shape was incomplete: every ``Reason`` could name itself
        and the ``Recommendation`` holding them could not, so the headline
        had to be re-derived from ``pick`` at the widget, which is exactly
        the "render out of data the engine already computed" this contract
        exists to prevent.  A KEY, never display text, for the same reason
        ``Reason.text_key`` is one.
    :param text_kwargs: its format arguments, same pair as ``Reason``'s.

    **On ``score_delta`` and the reasons' sum.**  For a stat-space solver
    (audit §3.4 #3/#4) ``score_delta`` is Σ ``reason.score_contribution``,
    and a solver whose parts do not add up to its whole is showing an
    explanation that is not the reason.  Stage 2's two features are not
    stat-space solvers — they are completeness statements in [0, 1], because
    the combat model that would make a stat-space delta meaningful is not in
    the data (§3.4's closing line).  Their reasons therefore ENUMERATE the
    finding rather than decompose it, except ``recommend.missing_set_pieces``
    where the decomposition happens to be exact (one reason per missing
    piece, each worth ``1/total`` of the set).  Which of the two a given
    recommendation is, is stated in that solver's own docstring.
    """

    pick: object
    score_delta: float
    reasons: tuple[Reason, ...] = ()
    text_key: str = ""
    text_kwargs: dict = field(default_factory=dict)
