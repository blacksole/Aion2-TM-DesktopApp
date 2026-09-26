"""The contract between the Item Compare window and the logic behind it.

Split of work (Planner, Item-Vergleich, 2026-09-24):

* @designer owns the window -- ``ItemCompareDialog`` in ``app.py`` -- which
  only *shows* an :class:`ItemComparison`.  It decides nothing.
* @developer owns ``build_item_comparison(detail_a, detail_b)``, which turns
  two cached item details into one.

This module holds what both sides need and must agree on: the dataclasses,
and the ONE number formatter.  The formatter lives here rather than in the
window because the winner of a row is decided on the *displayed* value, not
the raw one (the rule Build Compare got after the 2026-09-04 screenshot of
red "0%" deltas).  If the window rounded one way and the logic another, a row
could show "3.5% vs 3.5%" and still crown a winner.  One function, imported
by both, makes that impossible.

Qt-free on purpose, like the rest of ``armory_engine`` (enforced by
``tests/test_armory_engine_qt_free.py``).

Design reference: Obsidian vault, ``Design/Konzept - Item-Vergleich.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

Winner = Literal["a", "b", "tie", "none"]


def format_stat_value(value: float, percent: bool = False) -> str:
    """How a stat value is written in the compare window.

    Whole numbers stay whole (``742``); fractions keep at most two places
    with trailing zeros dropped (``3.5``, not ``3.50``), because the cached
    details carry values like ``"3.5%"`` and ``"12.25%"`` that
    ``_format_number``'s integer rounding would flatten to ``4``/``12``.
    """
    rounded = round(float(value), 2)
    if rounded == int(rounded):
        text = str(int(rounded))
    else:
        text = f"{rounded:.2f}".rstrip("0").rstrip(".")
    return f"{text}%" if percent else text


def format_signed(value: float, percent: bool = False) -> str:
    """A delta with its sign always shown: ``+85``, ``−85``, ``±0``.

    The minus is U+2212, not a hyphen -- it is as wide as the plus, so a
    column of deltas stays aligned.
    """
    text = format_stat_value(abs(value), percent)
    if format_stat_value(value, percent) in ("0", "0%"):
        return f"±{text}"
    return f"+{text}" if value > 0 else f"−{text}"


@dataclass(frozen=True)
class StatValue:
    """One side of one row.  ``low`` is set only for a range (``489 ~ 661``)."""

    high: float
    low: float | None = None

    @property
    def is_range(self) -> bool:
        return self.low is not None and self.low != self.high


@dataclass(frozen=True)
class StatComparison:
    """One row of the compare table.

    ``winner`` is decided by the logic, never by the window:

    * ``"a"`` / ``"b"`` -- that side's displayed value is higher (for a
      range: the upper end decides);
    * ``"tie"`` -- both sides display the same value;
    * ``"none"`` -- not comparable: one side lacks the stat, or the section
      has no winners at all (possible sub stats, properties).
    """

    stat_id: str
    name: str
    a: StatValue | None
    b: StatValue | None
    percent: bool = False
    winner: Winner = "none"
    #: For rows that are not numbers (``"Yes"``/``"No"``, ``"+20"``):
    #: shown verbatim instead of ``a``/``b``.  Used by the properties section.
    text_a: str | None = None
    text_b: str | None = None

    @property
    def delta_high(self) -> float | None:
        """B minus A at the upper end; ``None`` when either side is missing."""
        if self.a is None or self.b is None:
            return None
        return self.b.high - self.a.high

    @property
    def delta_low(self) -> float | None:
        """B minus A at the lower end, only when BOTH sides are ranges.

        A range moves at both ends; showing only the top end hid half the
        change (``489~661`` -> ``574~776`` is +85 at the floor, +115 at the
        ceiling -- measured on real cached weapons, see the concept note).
        """
        if self.a is None or self.b is None:
            return None
        if self.a.low is None or self.b.low is None:
            return None
        if not (self.a.is_range and self.b.is_range):
            return None
        return self.b.low - self.a.low


@dataclass
class ItemComparison:
    """Everything the compare window shows, for one pair of items.

    ``item_a`` / ``item_b`` are the raw cached details (``ItemDetailCache``)
    -- the window reads only display fields from them: ``id``, ``name``,
    ``grade``, ``gradeName``, ``icon``, ``categoryName``, ``level``,
    ``subStatRandom``, ``subStatCount``.
    """

    item_a: dict
    item_b: dict
    main: list[StatComparison] = field(default_factory=list)
    #: The pool random sub stats are rolled from -- upper bounds, not values
    #: the item has.  Every row's ``winner`` must be ``"none"``: 1776 of the
    #: 2092 cached items roll these randomly, so "B has more Defense" would be
    #: a claim about a roll that has not happened.
    sub_pool: list[StatComparison] = field(default_factory=list)
    #: Enchant cap, socket counts, tradability.  ``winner`` always ``"none"``.
    meta: list[StatComparison] = field(default_factory=list)

    @property
    def wins(self) -> tuple[int, int, int]:
        """``(a ahead, b ahead, equal)`` over the main stats -- the summary
        line.  Deliberately no overall verdict: which stat matters more
        depends on class and build, so a single "B is better" would be a
        guess dressed up as a result."""
        a = sum(1 for row in self.main if row.winner == "a")
        b = sum(1 for row in self.main if row.winner == "b")
        tie = sum(1 for row in self.main if row.winner == "tie")
        return a, b, tie

    def swapped(self) -> ItemComparison:
        """The same comparison with A and B exchanged -- the window's swap
        button.  Pure mirroring, so swapping never needs the logic again and
        cannot disagree with it."""
        flip = {"a": "b", "b": "a"}

        def mirror(rows: list[StatComparison]) -> list[StatComparison]:
            return [
                replace(
                    row, a=row.b, b=row.a, text_a=row.text_b, text_b=row.text_a,
                    winner=flip.get(row.winner, row.winner),
                )
                for row in rows
            ]

        return ItemComparison(
            item_a=self.item_b, item_b=self.item_a,
            main=mirror(self.main), sub_pool=mirror(self.sub_pool),
            meta=mirror(self.meta),
        )


def _parse_stat_entry(stat: dict) -> tuple[float, float | None, bool]:
    """(high, low, percent) for one ``StatEntry``-shaped dict.

    ``value`` is the number always shown (the upper end for a range);
    ``minValue`` -- when present and different -- is the lower end
    (``format_tooltip``/``_render_stats`` already read these two fields the
    same way).  ``percent`` is read off the RAW string, since the cached
    details spell a percent stat as ``\"3%\"``/``\"3.5%\"`` rather than
    carrying a separate boolean flag anywhere in the API response.
    """
    raw_high = stat.get("value")
    raw_low = stat.get("minValue")
    percent = "%" in str(raw_high) or "%" in str(raw_low)

    def _num(raw) -> float | None:
        if raw is None:
            return None
        try:
            return float(str(raw).replace("%", "").strip())
        except (ValueError, TypeError):
            return None

    high = _num(raw_high) or 0.0
    low = _num(raw_low)
    if low is not None and low == high:
        low = None
    return high, low, percent


def _decide_winner(a: StatValue | None, b: StatValue | None, percent: bool) -> Winner:
    """Decided on the DISPLAYED (rounded) value, per row -- see
    ``format_stat_value``'s docstring for why the raw floats are never
    compared directly.  A range is decided by its upper end (``a.high``/
    ``b.high``), matching the docstring on ``StatComparison.delta_high``.
    Missing either side means nothing to compare: ``\"none\"``, not a win."""
    if a is None or b is None:
        return "none"
    text_a = format_stat_value(a.high, percent)
    text_b = format_stat_value(b.high, percent)
    if text_a == text_b:
        return "tie"
    return "b" if b.high > a.high else "a"


def _merge_stat_rows(
    stats_a: list[dict],
    stats_b: list[dict],
    *,
    decide_winner: bool,
) -> list[StatComparison]:
    """One :class:`StatComparison` per stat id present on EITHER side, in
    the order first seen (``stats_a``'s own order, then any id ``stats_a``
    lacks, in ``stats_b``'s order) -- so a row never silently disappears
    just because one side happens to lack that stat."""
    by_id: dict[str, dict] = {}
    order: list[str] = []
    for side_key, stats in (("a", stats_a), ("b", stats_b)):
        for stat in stats or []:
            stat_id = stat.get("id") or stat.get("name") or ""
            if not stat_id:
                continue
            if stat_id not in by_id:
                by_id[stat_id] = {"name": stat.get("name") or stat_id}
                order.append(stat_id)
            high, low, percent = _parse_stat_entry(stat)
            by_id[stat_id][side_key] = StatValue(high=high, low=low)
            by_id[stat_id]["percent"] = by_id[stat_id].get("percent") or percent

    rows = []
    for stat_id in order:
        entry = by_id[stat_id]
        value_a = entry.get("a")
        value_b = entry.get("b")
        percent = bool(entry.get("percent"))
        winner = _decide_winner(value_a, value_b, percent) if decide_winner else "none"
        rows.append(
            StatComparison(
                stat_id=stat_id,
                name=entry["name"],
                a=value_a,
                b=value_b,
                percent=percent,
                winner=winner,
            )
        )
    return rows


def _meta_row(stat_id: str, name: str, text_a: str, text_b: str) -> StatComparison:
    """One non-numeric properties row (Required Level, Sockets, Enchant
    cap, Tradable, ...) -- always ``winner=\"none\"`` per ``ItemComparison
    .meta``'s own docstring, shown verbatim via ``text_a``/``text_b``."""
    return StatComparison(stat_id=stat_id, name=name, a=None, b=None, text_a=text_a, text_b=text_b)


def _sockets_text(detail: dict) -> str:
    parts = []
    if detail.get("magicStoneSlotCount"):
        parts.append(f"{detail['magicStoneSlotCount']} Manastone")
    if detail.get("godStoneSlotCount"):
        parts.append(f"{detail['godStoneSlotCount']} Godstone")
    return " / ".join(parts) if parts else "-"


def build_item_comparison(detail_a: dict, detail_b: dict) -> ItemComparison:
    """Turns two cached item details into the one ``ItemComparison`` the
    window shows -- the only place a winner is decided (see this module's
    own docstring for why that must not also happen in the window).

    * ``main`` -- ``mainStats``, winners decided (the rule: displayed value,
      range's upper end, missing side means \"none\").
    * ``sub_pool`` -- ``subStats``, winners forced to ``\"none\"``: these are
      the random-roll ceiling, not a value either item actually has.
    * ``meta`` -- Required Level, Sockets, Enchant cap, Tradable -- always
      ``\"none\"``, same reasoning as ``sub_pool``.
    """
    main = _merge_stat_rows(detail_a.get("mainStats") or [], detail_b.get("mainStats") or [], decide_winner=True)
    sub_pool = _merge_stat_rows(detail_a.get("subStats") or [], detail_b.get("subStats") or [], decide_winner=False)

    meta = [
        _meta_row(
            "equipLevel", "Required Level",
            str(detail_a.get("equipLevel") or "-"), str(detail_b.get("equipLevel") or "-"),
        ),
        _meta_row("sockets", "Sockets", _sockets_text(detail_a), _sockets_text(detail_b)),
        _meta_row(
            "maxEnchantLevel", "Enchant Cap",
            str(detail_a.get("maxEnchantLevel") or "-"), str(detail_b.get("maxEnchantLevel") or "-"),
        ),
        _meta_row(
            "tradable", "Tradable",
            "Yes" if detail_a.get("tradable") else "No",
            "Yes" if detail_b.get("tradable") else "No",
        ),
    ]

    return ItemComparison(item_a=detail_a, item_b=detail_b, main=main, sub_pool=sub_pool, meta=meta)
