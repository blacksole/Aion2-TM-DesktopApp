"""Armory landing page — a live dashboard, not a launcher menu.

Audit 2026-09-18 §3 Phase 4c ("Landing Armory = tableau de bord next best
action") and D-ux-review M7/§3.2: the page used to show three generic
launcher rows under a subtitle that said "coming soon", while the app was
already carrying a fully populated Build Planner state in the profile.  So
the page now *reads* that state and shows it: class/race/build, how many
equip slots are filled, the enchant window, Daevanion nodes, skills tracked.

Two deliberate constraints:

* **No ItemDatabase import, no network.**  ``summarize_build_planner`` is a
  plain function over the persisted ``profile["build_planner"]`` dict (17
  keys, pinned by ``tests/test_build_planner_state.py``).  Importing the
  22k-line ``ItemDatabase/app.py`` just to draw five cards would make
  opening the sidebar page cost a module load; deriving from the dict costs
  nothing and works even if the Armory window was never opened this session
  (same reasoning as MainWindow's overlay priority readers).
* **Qt-free derivation.**  The summary is a frozen dataclass computed
  without touching a widget, so the numbers are unit-testable without a
  QApplication (``tests/test_armory_dashboard.py``).

Stage 2 (2026-09-19) adds one card the page does NOT derive: the
recommendations.  They come from ``ItemDatabase/armory_engine`` — which
needs the catalog on disk and a detail provider — so they are **pushed in**
by the host through :meth:`ArmoryPage.set_recommendations`, exactly like the
state is.  What arrives is duck-typed on purpose (``.text_key``,
``.text_kwargs``, ``.reasons``): the page never imports the engine, so the
two constraints above still hold, and a recommendation stays a translation
KEY plus arguments until this file renders it — which is what lets a
language switch re-render recommendations computed minutes earlier.

Styling is tokens-only via objectNames (``armoryCard`` /
``armoryCardTitle`` / ``armoryCardValue`` / ``armoryCardHint`` /
``armoryCardCta`` / ``armoryRecoCard`` / ``armoryRecoItem`` /
``armoryRecoWhy``), styled in ``ui/styles.template.qss`` §15 — this file
contains no colour and no font.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.translations import DEFAULT_LANGUAGE, tr as _default_tr
from ui.widgets.empty_state import EmptyStateWidget

#: The **active** equip slots of the Build Planner paperdoll, in paperdoll
#: order: ``_LEFT_EQUIP_SECTIONS`` (weapon + armor + wings) then
#: ``_RIGHT_EQUIP_SECTIONS`` (accessory) — ItemDatabase/app.py:3007-3033,
#: consumed at :19549/:19558.
#:
#: NOT ``SLOT_LAYOUT``, which is the *definition* table and two slots longer
#: (review G/M3).  ``Brooch1``/``Brooch2`` are defined there but excluded
#: from the paperdoll ("Brooch doesn't exist yet at global release",
#: app.py:3021), so no widget can ever fill them and a fully geared
#: character read "20/22 slots equipped" forever.
#:
#: Mirrored rather than imported on purpose (see module docstring); drift is
#: not left to a comment —
#: ``tests/test_armory_dashboard.py::test_the_active_slot_mirror_matches_the_armory``
#: loads app.py and recomputes the active set, so adding Brooch back over
#: there fails loudly here.  The denominator also grows on its own if a
#: state carries a filled slot this tuple does not know
#: (``summarize_build_planner``), so the ratio can never exceed 1.
#: MASTER §3 "Carte" — padding `3`.  The space scale lives in
#: ``core.theme`` (``space_3 = 12``) and is identical across all six
#: themes, so a layout margin can be a plain int here; the equality is a
#: gate, not a comment
#: (``tests/test_armory_dashboard.py::test_the_card_padding_is_space_3``).
#: A layout margin cannot come from QSS — Qt's box model applies a
#: stylesheet ``padding`` to the frame, not to the QVBoxLayout inside it.
CARD_PADDING = 12

ARMORY_EQUIP_SLOTS: tuple[str, ...] = (
    # left column: weapon, armor, wings
    "MainHand", "SubHand",
    "Helmet", "Shoulder", "Torso", "Gloves", "Pants", "Boots", "Cloak",
    "Wings1",
    # right column: accessory
    "Earring1", "Earring2", "Necklace", "Amulet",
    "Ring1", "Ring2", "Bracelet1", "Bracelet2",
    "Rune1", "Rune2",
)


# ---------------------------------------------------------------------------
# Derivation (Qt-free)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArmorySummary:
    """What the dashboard shows, derived from one ``build_planner`` dict.

    Every field has a neutral default, so a missing key, a ``None`` state or
    a half-written dict yields a valid summary rather than an exception —
    the page is a read-only view over user data that six different windows
    write into.
    """

    has_state: bool = False
    character_class: str = ""
    character_race: str = ""
    build_name: str = ""
    equipped_slots: int = 0
    total_slots: int = len(ARMORY_EQUIP_SLOTS)
    enchant_min: int | None = None
    enchant_max: int | None = None
    gear_types: tuple[str, ...] = field(default_factory=tuple)
    daevanion_nodes: int = 0
    skill_build_name: str = ""
    skill_count: int = 0
    genius_build_name: str = ""
    pantheon_filled: int = 0
    pantheon_total: int = 0

    @property
    def is_empty(self) -> bool:
        """True when there is nothing worth showing a card for.

        A state that only carries defaults (an empty class, no equipped
        item, no node, no skill, no pantheon piece) is the "no build yet"
        case even though the dict itself exists — that is what a profile
        saved before the Armory was ever opened looks like.
        """
        if not self.has_state:
            return True
        return not (
            self.character_class
            or self.equipped_slots
            or self.daevanion_nodes
            or self.skill_count
            or self.pantheon_filled
        )

    @property
    def has_equip_build(self) -> bool:
        """True when the per-class equip build behind the numbers was found.

        ``equip_builds_data`` is keyed by ``character_class.lower()``, so an
        unknown, misspelled or not-yet-chosen class resolves to no build at
        all — and then ``equipped_slots`` is 0 for a reason that has nothing
        to do with how geared the character is.  ``daevanion_active`` and
        ``pantheon_slots`` are class-INDEPENDENT, so such a state is not
        ``is_empty`` and the card still renders: without this flag it read
        "0/20 slots equipped" over a fully equipped build (review G/m3).

        ``build_name`` is emptied by :func:`summarize_build_planner` in
        exactly that case, so it is the flag — named here so the render
        does not have to re-derive the meaning of an empty string.
        """
        return bool(self.build_name)


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def _as_text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _current_build(state: dict, data_key: str, name_key: str, class_key: str) -> tuple[str, dict]:
    """(build name, build dict) for one of the two per-class build stores.

    Both ``equip_builds_data`` and ``skill_builds_data`` are shaped
    ``{class_lower: {build_name: {...}}}`` with the selected name kept in its
    own top-level key, and MainWindow's own readers default that name to
    "Default" — this mirrors them exactly (ui/main_window.py:1014/1043).
    """
    name = _as_text(state.get(name_key)) or "Default"
    builds = _as_dict(_as_dict(state.get(data_key)).get(class_key))
    return name, _as_dict(builds.get(name))


def _count_chosen_daevanion_nodes(node_ids: list, start_id: str | None) -> int:
    """Nodes on one board the PLAYER actually picked.

    Every board carries a free, always-on "start" node
    (``LoadoutWindow._daevanion_active_set`` seeds it lazily and
    ``_daevanion_on_node_clicked`` refuses to toggle it), so it must not
    inflate this card's "N nodes active" count -- User-reported,
    2026-09-22: a fresh board nobody had clicked read "1 nodes active".

    With ``start_id`` known the node is excluded BY ID, which is the real
    rule (``armory_engine.daevanion.daevanion_chosen_node_count``).  Without
    it -- board data absent, or a host that pushes nothing in -- this falls
    back to subtracting one, which is what shipped in 2.0.8 and is wrong in
    exactly one direction: a board saved WITHOUT its start node (a legacy
    profile, or a board seeded by an older build) under-reports by one
    (Apex review of PR #7, finding 8).
    """
    present = [node_id for node_id in node_ids if node_id]
    if start_id is not None:
        return sum(1 for node_id in present if node_id != start_id)
    return max(0, len(present) - 1)


def summarize_build_planner(
    state: dict | None, daevanion_start_ids: dict[str, str] | None = None
) -> ArmorySummary:
    """Fold the persisted Armory state into the numbers the cards show.

    ``None`` (no profile loaded, or a profile saved before the Build Planner
    existed) returns the default summary, whose ``is_empty`` is True.

    ``daevanion_start_ids`` maps a ``daevanion_active`` key
    (``"<variant>:<board id>"``) to that board's free start-node id.  It is
    PUSHED IN by the host, exactly like the recommendations are and for the
    same reason: which node is the start is a fact about the board data
    under ``ItemDatabase/data/``, and this page imports neither the data nor
    the engine.  ``None``/missing key falls back to the old "subtract one"
    guess -- see :func:`_count_chosen_daevanion_nodes`.
    """
    if not isinstance(state, dict):
        return ArmorySummary()

    character_class = _as_text(state.get("character_class"))
    class_key = character_class.lower()

    build_name, build = _current_build(state, "equip_builds_data", "current_build_name", class_key)
    equipped = _as_dict(build.get("equipped"))
    equipped_slots = sum(1 for item in equipped.values() if item)

    # "Enchant levels present" = the positive ones.  A freshly equipped
    # piece persists `enchant: {"MainHand": 0}`, and "+0–+0" is noise, not
    # information — no positive level at all hides the line entirely.
    #
    # ``math.isfinite`` is the one guard the rest of the derivation does not
    # need (review G/m2): every other access goes through _as_dict/_as_list/
    # _as_text, but this one calls ``int(value)``, and ``int(inf)`` raises
    # OverflowError.  ``json.loads`` accepts ``Infinity`` by default, so a
    # hand-edited or corrupted profile could carry one — and the exception
    # would propagate through set_build_planner_state -> load_profile (a
    # try/finally with no except) into MainWindow.__init__, i.e. the app
    # would not start.  ``NaN`` was already safe (``NaN > 0`` is False).
    levels = [
        int(value)
        for value in _as_dict(build.get("enchant")).values()
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    ]

    skill_build_name, skill_build = _current_build(
        state, "skill_builds_data", "current_skill_build_name", class_key
    )
    skill_priority = _as_dict(skill_build.get("priority"))
    skill_count = sum(
        1
        for group in skill_priority.values()
        for skill_id in _as_list(group)
        if skill_id
    )

    daevanion_nodes = sum(
        _count_chosen_daevanion_nodes(_as_list(nodes), (daevanion_start_ids or {}).get(key))
        for key, nodes in _as_dict(state.get("daevanion_active")).items()
    )

    pantheon = _as_dict(state.get("pantheon_slots"))

    return ArmorySummary(
        has_state=True,
        character_class=character_class,
        character_race=_as_text(state.get("character_race")),
        build_name=build_name if build else "",
        equipped_slots=equipped_slots,
        # Counting FILLED unknown slots, not every key: a profile written
        # by an older build can hold an empty `Brooch1` entry, which must
        # not inflate the denominator -- but a slot that really carries an
        # item always does, so equipped_slots <= total_slots holds.
        total_slots=max(len(ARMORY_EQUIP_SLOTS), equipped_slots),
        enchant_min=min(levels) if levels else None,
        enchant_max=max(levels) if levels else None,
        gear_types=tuple(_as_text(gear) for gear in _as_list(state.get("active_gear_types")) if _as_text(gear)),
        daevanion_nodes=daevanion_nodes,
        skill_build_name=skill_build_name if skill_build else "",
        skill_count=skill_count,
        genius_build_name=_as_text(state.get("current_genius_build_name")),
        pantheon_filled=sum(1 for slot in pantheon.values() if slot),
        pantheon_total=len(pantheon),
    )


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------


class _ElidedLabel(QLabel):
    """A single-line label that ends in "…" instead of being cut mid-glyph.

    ``QLabel`` has no ``setElideMode`` — that is ``QComboBox``/``QTabBar``
    territory — so a value wider than its cell is simply clipped, with no
    ellipsis and no way to read the rest (review G/m11).  The display face
    carries prose (``"Gladiator · Elyos · PvE t1"``, and full RU/DE
    sentences) in a half-width grid cell, so that is a real information
    loss, not a cosmetic one.

    The *logical* text stays whole: :meth:`text` returns what was set and
    the tooltip carries it too, so the full string is always one hover
    away and readable by a test.  Only the rendered string is shortened,
    recomputed from ``QFontMetrics`` on every resize.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._full_text = ""

    def setText(self, text: str):
        self._full_text = text or ""
        # The tooltip is the whole point: eliding without one would trade a
        # cut string for a shorter cut string.
        self.setToolTip(self._full_text)
        self._apply_elide()

    def text(self) -> str:
        """The full string, not the elided face Qt paints."""
        return self._full_text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self):
        width = self.contentsRect().width()
        elided = (
            self.fontMetrics().elidedText(self._full_text, Qt.ElideRight, width)
            if width > 0
            else self._full_text
        )
        # Guarded: QLabel.setText can trigger a resize, which re-enters here.
        if super().text() != elided:
            super().setText(elided)


class ArmoryCard(QFrame):
    """A whole-card button: title, big value, hint lines, CTA.

    The card is clickable everywhere (User-Wunsch, 2026-09-10/11) — but via
    a real ``clicked`` Signal and an overridden ``mousePressEvent``, not the
    ``row.mousePressEvent = closure`` monkey-patch this page used to carry.
    That pattern stored, on the widget, a function whose default arguments
    held the widget itself: a reference cycle Qt's own teardown cannot see
    (audit review of the same pattern in MainWindow._wire_card).  Focusable
    and Space/Enter-activatable, so the card is reachable by keyboard like
    the QPushButton it behaves as.
    """

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("armoryCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(self)
        # MASTER §3 "Carte": padding `3`, i.e. space_3 = 12 px on all four
        # sides.  It used to be (16, 12, 16, 12) — space_4 horizontally —
        # which made this the only card in the app with its own padding
        # (review G/m12).  Pinned to the token by
        # tests/test_armory_dashboard.py::test_the_card_padding_is_space_3.
        layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        layout.setSpacing(4)

        # Title and value are single-line on purpose.  A word-wrapped QLabel
        # reports the height of *two* lines as its sizeHint and one line as
        # its minimum, so in a row that is even slightly short of space a
        # QBoxLayout shrinks it to one line's worth of pixels -- which for
        # the 20 px display face meant the figure rendered with its
        # descenders cut and the hint below sitting on top of it (first grab
        # of this page, before the scroll area below).
        self.title_label = QLabel("")
        self.title_label.setObjectName("armoryCardTitle")
        layout.addWidget(self.title_label)

        self.value_label = _ElidedLabel()
        self.value_label.setObjectName("armoryCardValue")
        self.value_label.setVisible(False)
        layout.addWidget(self.value_label)

        self._hint_layout = QVBoxLayout()
        self._hint_layout.setContentsMargins(0, 0, 0, 0)
        self._hint_layout.setSpacing(2)
        layout.addLayout(self._hint_layout)
        self._hint_labels: list[QLabel] = []

        layout.addStretch()

        self.cta_button = QPushButton("")
        self.cta_button.setObjectName("armoryCardCta")
        self.cta_button.setCursor(Qt.PointingHandCursor)
        self.cta_button.clicked.connect(self.clicked)
        layout.addWidget(self.cta_button, 0, Qt.AlignLeft)

    # ── content ───────────────────────────────────────────────────────────

    def set_title(self, text: str):
        self.title_label.setText(text)

    def set_value(self, text: str):
        """Empty text hides the big figure (the two launcher cards have none)."""
        self.value_label.setText(text)
        self.value_label.setVisible(bool(text))

    def set_hints(self, lines: list[str]):
        """Reuses the hint labels instead of rebuilding them.

        Rebuilding on every render (every language switch, every state push)
        would churn widgets under a page that is alive for the whole session.
        """
        for index, line in enumerate(lines):
            if index >= len(self._hint_labels):
                label = QLabel("")
                label.setObjectName("armoryCardHint")
                label.setWordWrap(True)
                self._hint_layout.addWidget(label)
                self._hint_labels.append(label)
            self._hint_labels[index].setText(line)
            self._hint_labels[index].setVisible(True)
        for label in self._hint_labels[len(lines):]:
            label.setText("")
            label.setVisible(False)

    def set_cta(self, text: str):
        self.cta_button.setText(text)

    # ── behaviour ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class RecommendationRow(QWidget):
    """One recommendation: its line, and a "Why?" that opens the reasons.

    The explainability contract (``armory_engine/explain.py`` §3.3: solvers
    never return bare picks) only pays off if the player can actually see
    the reasons, and only stays readable if they are not all on screen at
    once — three set recommendations with four missing pieces each is twelve
    lines of small print above the fold.  So the headline is always visible
    and the breakdown is one click away, per row.

    Deliberately NOT animated.  ``ui/motion.fade_in`` would suit the reveal,
    but MASTER §4-6 says "aucune autre animation ailleurs" and
    ``tests/test_theme_wiring.py::test_exactly_three_places_animate`` counts
    the call sites: a sixth is a design decision that goes through MASTER
    first, not a detail of this card.

    The button is a ``QToolButton`` rather than a ``QPushButton`` for the
    same reason the rest of the app uses one for inline affordances: it
    carries no button chrome by default, so it reads as the text link it is.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("armoryRecoItem")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)

        self.text_label = QLabel("")
        self.text_label.setObjectName("armoryCardHint")
        self.text_label.setWordWrap(True)
        self.text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        head.addWidget(self.text_label, 1)

        self.why_button = QToolButton()
        self.why_button.setObjectName("armoryRecoWhyButton")
        self.why_button.setCheckable(True)
        self.why_button.setCursor(Qt.PointingHandCursor)
        self.why_button.toggled.connect(self._on_toggled)
        head.addWidget(self.why_button, 0, Qt.AlignTop)
        layout.addLayout(head)

        self.why_label = QLabel("")
        self.why_label.setObjectName("armoryRecoWhy")
        self.why_label.setWordWrap(True)
        self.why_label.setVisible(False)
        layout.addWidget(self.why_label)

    def _on_toggled(self, checked: bool):
        self.why_label.setVisible(checked and bool(self.why_label.text()))

    def set_content(self, text: str, reasons: list[str], why_text: str):
        """Fill the row.  No reason -> no button, not a button that opens
        an empty box (a recommendation with no reasons is the degradation
        line, which explains itself)."""
        self.text_label.setText(text)
        self.why_button.setText(why_text)
        self.why_label.setText("\n".join(reasons))
        has_reasons = bool(reasons)
        self.why_button.setVisible(has_reasons)
        if not has_reasons:
            self.why_button.setChecked(False)
        self.why_label.setVisible(self.why_button.isChecked() and has_reasons)


class ArmoryRecommendationCard(QFrame):
    """The card the rows live in — a list, not a figure.

    Not an :class:`ArmoryCard`: that one is a whole-card button with one big
    value and a CTA, and this card's rows are individually interactive, so
    making the frame clickable too would mean a click on "Why?" also fired
    the card's own action.  It shares the card *surface* through its own
    objectName in §15 instead.

    Rows are reused across renders, like ``ArmoryCard.set_hints`` does and
    for the same reason: this page lives for the whole session and
    re-renders on every language switch and every state push.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("armoryRecoCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        layout.setSpacing(6)

        self.title_label = QLabel("")
        self.title_label.setObjectName("armoryCardTitle")
        layout.addWidget(self.title_label)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(8)
        layout.addLayout(self._rows_layout)
        self._rows: list[RecommendationRow] = []

    @property
    def rows(self) -> list[RecommendationRow]:
        """Every row ever built, visible or not (read by tests)."""
        return list(self._rows)

    def visible_rows(self) -> list[RecommendationRow]:
        return [row for row in self._rows if not row.isHidden()]

    def set_title(self, text: str):
        self.title_label.setText(text)

    def set_rows(self, entries: list[tuple[str, list[str]]], why_text: str):
        for index, (text, reasons) in enumerate(entries):
            if index >= len(self._rows):
                row = RecommendationRow()
                self._rows_layout.addWidget(row)
                self._rows.append(row)
            self._rows[index].set_content(text, reasons, why_text)
            self._rows[index].setVisible(True)
        for row in self._rows[len(entries):]:
            row.set_content("", [], why_text)
            row.setVisible(False)


class ArmoryPage(QWidget):
    """Armory dashboard: build summary cards + the two tool launchers.

    The three signals are unchanged, so MainWindow's existing wiring keeps
    working.  State only ever arrives **pushed**, through
    ``set_build_planner_state`` — MainWindow routes every write of
    ``_build_planner_state`` through its own ``_set_build_planner_state``,
    which calls it (review G/M1).  The page therefore holds no callable
    belonging to the host: the earlier ``state_provider=lambda: …`` made a
    MainWindow -> page -> lambda -> MainWindow cycle (review G/m10).
    """

    open_item_database_requested = Signal()
    open_crafting_calculator_requested = Signal()
    open_build_planner_requested = Signal()
    open_daevanion_requested = Signal()
    open_skill_planner_requested = Signal()

    def __init__(self):
        super().__init__()

        self._language = DEFAULT_LANGUAGE
        self._tr = _default_tr
        self._summary = ArmorySummary()
        # Pushed in by the host (see set_recommendations); never derived
        # here, and kept as engine objects rather than as rendered strings
        # so a language switch re-renders them.
        self._recommendations: tuple = ()
        # Same contract as the recommendations: pushed in by the host (see
        # set_daevanion_start_ids), never read off disk here.
        self._daevanion_start_ids: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.title_label = QLabel("Armory")
        self.title_label.setObjectName("mainTitle")
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("subtitle")
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)

        # The cards live in a scroll area, not straight in the page: five
        # cards plus the title block need ~500 px, and the window's own
        # minimum is 700 px tall with a header, a sort row and the toast
        # above/below.  Without it the grid gets less than its sizeHint and
        # QBoxLayout pays for that by shrinking labels below their text
        # height (M1 "text truncation" in reverse).  objectNames reused from
        # the Tasks list: `#scrollArea` is transparent + borderless, and the
        # viewport needs its own name because QAbstractScrollArea paints it
        # from QPalette::Base (§14 of the template).
        self._scroll = QScrollArea()
        self._scroll.setObjectName("scrollArea")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.viewport().setObjectName("transparentViewport")

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(14)

        self.empty_state = EmptyStateWidget()
        self.empty_state.set_content("", "", "", self.open_build_planner_requested.emit)
        body_layout.addWidget(self.empty_state)

        self.cards_container = QWidget()
        grid = QGridLayout(self.cards_container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self.build_card = ArmoryCard()
        self.reco_card = ArmoryRecommendationCard()
        self.daevanion_card = ArmoryCard()
        self.skill_card = ArmoryCard()
        self.items_card = ArmoryCard()
        self.crafting_card = ArmoryCard()

        # The build summary is the hero row (it carries three hint lines);
        # everything else pairs up two per row.
        grid.addWidget(self.build_card, 0, 0, 1, 2)
        # Directly under the hero row: audit §3 Phase 4c calls this page a
        # "tableau de bord next best action", and the next best action is
        # not something the reader should have to scroll past two launchers
        # to find.
        grid.addWidget(self.reco_card, 1, 0, 1, 2)
        grid.addWidget(self.daevanion_card, 2, 0)
        grid.addWidget(self.skill_card, 2, 1)
        grid.addWidget(self.items_card, 3, 0)
        grid.addWidget(self.crafting_card, 3, 1)
        body_layout.addWidget(self.cards_container)
        body_layout.addStretch()

        self._scroll.setWidget(body)
        layout.addWidget(self._scroll, 1)

        # Daevanion and Skill Planner both live inside the Build Planner
        # window as their own tab, so their cards get their own signals
        # (same one-purpose-per-card pattern as items_card/crafting_card
        # below) -- MainWindow.open_build_planner_window(tab=...) jumps
        # straight to the right tab instead of always landing on Equipment.
        self.build_card.clicked.connect(self.open_build_planner_requested)
        self.daevanion_card.clicked.connect(self.open_daevanion_requested)
        self.skill_card.clicked.connect(self.open_skill_planner_requested)
        self.items_card.clicked.connect(self.open_item_database_requested)
        self.crafting_card.clicked.connect(self.open_crafting_calculator_requested)

        self._render()

    # ── state ─────────────────────────────────────────────────────────────

    @property
    def summary(self) -> ArmorySummary:
        """The summary currently on screen (read by tests and by the host)."""
        return self._summary

    def set_build_planner_state(self, state: dict | None):
        """Host hook: re-derive and re-render from the persisted dict."""
        self._summary = summarize_build_planner(state, self._daevanion_start_ids)
        self._render()

    @property
    def recommendations(self) -> tuple:
        """What the recommendation card currently holds (read by tests)."""
        return self._recommendations

    def set_recommendations(self, recommendations) -> None:
        """Host hook: the engine's ``next_best_actions`` output, unrendered.

        Duck-typed (``.text_key``, ``.text_kwargs``, ``.reasons``) so this
        module keeps its no-ItemDatabase-import rule; ``None`` and anything
        that is not a list or a tuple are the same as "none yet", because
        the host computes these behind a try/except and must be able to say
        so without inventing a shape.  The type is checked rather than
        ``tuple()``-ed: a string is iterable, and tuple("abc") would put
        three characters on the dashboard instead of nothing.
        """
        self._recommendations = (
            tuple(recommendations) if isinstance(recommendations, (list, tuple)) else ()
        )
        self._render()

    def set_daevanion_start_ids(self, start_ids: dict[str, str] | None) -> None:
        """Host hook: ``{"<variant>:<board id>": start node id}``.

        Which node is a board's free start node is a fact about the board
        data under ``ItemDatabase/data/``; the host reads it (Qt-free, via
        ``armory_engine.daevanion.daevanion_start_id_by_board_key``) and
        pushes it in, so this page keeps its no-ItemDatabase-import rule.
        Anything but a dict is "not known", which is what makes the
        fallback in :func:`_count_chosen_daevanion_nodes` reachable rather
        than theoretical.
        """
        self._daevanion_start_ids = dict(start_ids) if isinstance(start_ids, dict) else {}

    # ── language ──────────────────────────────────────────────────────────

    def update_language(self, language: str, tr_func):
        self._language = language
        self._tr = tr_func
        self._render()

    # ── render ────────────────────────────────────────────────────────────

    def _render(self):
        def t(key: str, **kwargs) -> str:
            return self._tr(self._language, key, **kwargs)

        summary = self._summary
        empty = summary.is_empty

        self.title_label.setText(t("armory"))
        self.subtitle_label.setText(t("armory_subtitle"))

        self.empty_state.retranslate(
            t("armory_empty_title"), t("armory_empty_hint"), t("armory_card_open_build")
        )
        self.empty_state.setVisible(empty)
        for card in (self.build_card, self.daevanion_card, self.skill_card, self.reco_card):
            card.setVisible(not empty)

        # ── Recommendations (Stage 2) ──
        def resolve(item, fallback_key: str = "") -> str:
            """An engine text_key + its kwargs -> a sentence.

            Guarded: ``tr`` formats with ``str.format``, so a key whose
            placeholders and an engine's kwargs ever disagree raises
            KeyError/IndexError — inside a paint, on a dashboard, for a
            string.  Falling back to the untranslated key makes that a
            visible typo instead of a page that does not draw.
            """
            key = getattr(item, "text_key", "") or fallback_key
            if not key:
                return ""
            try:
                return t(key, **(getattr(item, "text_kwargs", None) or {}))
            except (KeyError, IndexError, ValueError):
                return key

        self.reco_card.set_title(t("armory_reco_title"))
        entries = [
            (resolve(reco), [line for line in (resolve(reason) for reason in getattr(reco, "reasons", ()) or ()) if line])
            for reco in self._recommendations
        ]
        entries = [entry for entry in entries if entry[0]]
        if not entries:
            entries = [(t("armory_reco_empty"), [])]
        self.reco_card.set_rows(entries, t("armory_reco_why"))

        # ── Build Planner ──
        self.build_card.set_title(t("armory_card_build_title"))
        self.build_card.set_cta(t("armory_card_open_build"))
        identity = " · ".join(
            part for part in (summary.character_class, summary.character_race, summary.build_name) if part
        )
        self.build_card.set_value(identity or t("armory_card_build_empty"))
        # The slots line is only true when the equip build it counts was
        # actually found (review G/m3) — otherwise it states "0/20" about a
        # build it never read.  No line at all is the honest degradation:
        # the card still shows what IS known (identity, Daevanion, skills).
        hints = []
        if summary.has_equip_build:
            hints.append(
                t("armory_card_slots", equipped=summary.equipped_slots, total=summary.total_slots)
            )
        if summary.enchant_max is not None:
            hints.append(t("armory_card_enchant", min=summary.enchant_min, max=summary.enchant_max))
        if summary.gear_types:
            hints.append(" · ".join(summary.gear_types))
        self.build_card.set_hints(hints)

        # ── Daevanion ──
        self.daevanion_card.set_title(t("armory_card_daevanion_title"))
        self.daevanion_card.set_value(t("armory_card_daevanion_value", count=summary.daevanion_nodes))
        self.daevanion_card.set_hints([])
        self.daevanion_card.set_cta(t("armory_card_open_daevanion"))

        # ── Skill Planner ──
        self.skill_card.set_title(t("armory_card_skills_title"))
        self.skill_card.set_value(t("armory_card_skills_value", count=summary.skill_count))
        self.skill_card.set_hints([summary.skill_build_name] if summary.skill_build_name else [])
        self.skill_card.set_cta(t("armory_card_open_skills"))

        # ── Launchers (unchanged role, one-line description) ──
        self.items_card.set_title(t("armory_roadmap_items_title"))
        self.items_card.set_value("")
        self.items_card.set_hints([t("armory_roadmap_items_desc")])
        self.items_card.set_cta(t("armory_card_open_items"))

        self.crafting_card.set_title(t("armory_roadmap_crafting_title"))
        self.crafting_card.set_value("")
        self.crafting_card.set_hints([t("armory_roadmap_crafting_desc")])
        self.crafting_card.set_cta(t("armory_card_open_crafting"))
