"""Design tokens — the single source of every color, size and duration in the UI.

Mirrors ``design-system/aion2-tm/MASTER.md`` (« Aether Cockpit »).  §1 lives in
:data:`PRIMITIVES`, §2 in :class:`Tokens` / :data:`THEMES`, §4 in
:func:`build_qss` and :func:`qcolor`.

Rules this module enforces:

* one set of semantic names; a theme is *the same names with other values*
  (no ``[theme=…]`` duplication in the QSS anymore — see
  :func:`build_qss` and ``ui/styles.template.qss``);
* non-Abyss themes are built with :func:`dataclasses.replace` from
  :data:`ABYSS` so that the inheritance MASTER §2 mandates is explicit and
  testable (a theme may only redefine ``accent*``, ``secondary*`` and the
  ``bg.*`` family);
* data-driven colors (item grade, timer color) go through
  :func:`data_color`, never through a literal in a widget.

Qt-light on purpose: importing this module must work without a
``QApplication`` (``core.fonts`` and the tests rely on it), so nothing here
touches the GUI at import time.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from pathlib import Path

from PySide6.QtGui import QColor, QPalette

from utils.paths import app_root

logger = logging.getLogger(__name__)


def template_path() -> Path:
    """Where ``ui/styles.template.qss`` lives, resolved when it is read.

    Goes through ``utils.paths.app_root()`` like every other read-only
    resource in the repo (``ui/main_window._asset_base_path``,
    ``ItemDatabase/app.py``, ``main.py``) instead of walking up from
    ``__file__``.  Walking up happens to work in a PyInstaller bundle --
    a PYZ module's ``__file__`` is synthesized under ``sys._MEIPASS`` --
    but it worked by coincidence, it could not be monkeypatched in a
    frozen-layout test, and a move of ``core/`` would have turned it into
    an unhandled FileNotFoundError during MainWindow construction.
    """
    return app_root() / "ui" / "styles.template.qss"


#: Back-compatible alias.  Resolved at import for the tests that read the
#: template directly; :func:`build_qss` calls :func:`template_path` instead,
#: so a frozen layout is resolved at read time.
TEMPLATE_PATH = template_path()

# --------------------------------------------------------------------------
# §1 Primitives
# --------------------------------------------------------------------------

#: MASTER §1 — raw palette.  Nothing outside this module reads these directly;
#: the UI only ever sees the semantic names of :class:`Tokens`.
PRIMITIVES: dict[str, str] = {
    "navy.950": "#0b1120",
    "navy.900": "#0f172a",
    "navy.850": "#151e33",
    "navy.800": "#1c2740",
    "navy.700": "#26324a",
    "navy.600": "#3b4863",
    "slate.400": "#94a3b8",
    "slate.300": "#c3cadb",
    "slate.100": "#e5e7eb",
    "cyan.400": "#22d3ee",
    "cyan.300": "#67e8f9",
    "cyan.900a": "rgba(34, 211, 238, 0.14)",
    "violet.400": "#a78bfa",
    "violet.900a": "rgba(167, 139, 250, 0.16)",
    "green.400": "#4ade80",
    "green.900a": "rgba(74, 222, 128, 0.16)",
    "amber.400": "#fbbf24",
    "amber.900a": "rgba(251, 191, 36, 0.16)",
    "red.400": "#f87171",
    "red.900a": "rgba(248, 113, 113, 0.16)",
}

#: Keys a non-Abyss theme is allowed to redefine (MASTER §2, "Thèmes").
#:
#: ``border`` / ``border_strong`` joined the list on 2026-09-18 (MASTER §2,
#: "Bordures par thème"): inherited from Abyss they were a navy line drawn on
#: an Inferno red or Emerald green surface — visible as a cold seam around
#: every card.  A border belongs to its own theme's bg family, so it has to
#: be overridable; the contrast gate is unaffected (no §2 pair involves a
#: border, they are non-text 1 px lines).
THEME_OVERRIDABLE_KEYS: frozenset[str] = frozenset(
    {
        "accent",
        "accent_hover",
        "accent_soft",
        "secondary",
        "secondary_soft",
        "bg_window",
        "bg_surface",
        "bg_elevated",
        "bg_overlay",
        "bg_input",
        "border",
        "border_strong",
    }
)


@dataclass(frozen=True)
class Tokens:
    """One theme: every semantic token of MASTER §2 plus the §1 scales.

    Color attributes hold a CSS-ish string (``#rrggbb`` or
    ``rgba(r, g, b, a)``) that is valid both in QSS and for :func:`qcolor`.
    Scale attributes hold plain numbers; the QSS template appends the unit
    (``{{text_base}}px``).
    """

    name: str

    # --- §2 surfaces -------------------------------------------------
    bg_window: str
    bg_surface: str
    bg_elevated: str
    bg_overlay: str
    bg_input: str

    # --- §2 lines ----------------------------------------------------
    border: str
    border_strong: str

    # --- §2 text -----------------------------------------------------
    fg: str
    fg_secondary: str
    fg_muted: str
    fg_on_accent: str

    # --- §2 accents --------------------------------------------------
    accent: str
    accent_hover: str
    accent_soft: str
    secondary: str
    secondary_soft: str

    # --- §2 status ---------------------------------------------------
    ok: str
    warn: str
    danger: str
    ok_soft: str
    warn_soft: str
    danger_soft: str

    # --- §2 focus ----------------------------------------------------
    # focus.ring is "accent, 2 px, offset 1 px" — the color is *defined* as
    # the accent, so it is a derived property, not a stored duplicate that a
    # new theme could forget to update (it did, once: caught by
    # tests/test_theme.py::test_focus_ring_follows_accent).
    focus_ring_width: int
    focus_ring_offset: int

    # --- §1 typography -----------------------------------------------
    font_display: str
    font_body: str
    font_mono: str
    font_weight_regular: int
    font_weight_medium: int
    font_weight_semibold: int
    font_weight_bold: int
    text_xs: int
    text_sm: int
    text_base: int
    text_md: int
    text_lg: int
    text_xl: int
    text_2xl: int
    text_display: int
    letter_spacing_caps: str
    line_height: str

    # --- §1 spacing / radius / borders / shadow ----------------------
    space_1: int
    space_2: int
    space_3: int
    space_4: int
    space_6: int
    space_8: int
    radius_sm: int
    radius_md: int
    radius_full: int
    border_width: int
    shadow_popup: str

    # --- §1 motion ---------------------------------------------------
    motion_fast: int
    motion_base: int
    motion_slow: int
    motion_ease: str
    motion_offset: int

    @property
    def focus_ring(self) -> str:
        """MASTER §2 ``focus.ring`` — always this theme's accent."""
        return self.accent

    # --- focus ring geometry ----------------------------------------
    # MASTER §2 revised 2026-09-18: the ring is a BORDER on the control's
    # own edge, not an outline around it.  Qt cannot draw outside a widget's
    # rect -- `outline` on a QWidget only recolours Fusion's
    # PE_FrameFocusRect, which is painted around the *label* sub-rect,
    # inside the control and through the text (verified in
    # docs/audit-2026-09-18/shots/aether/).
    #
    # Growing the border from `border_width` to `focus_ring_width` would
    # grow the widget's sizeHint and nudge its whole row, so the focus rule
    # also has to give back exactly that much padding.  QSS has no
    # arithmetic, so the compensated values are tokens: `space_2_inset` is
    # `space_2` minus `focus_inset`.

    @property
    def focus_inset(self) -> int:
        """Pixels the focus border adds per edge over the resting border."""
        return max(0, self.focus_ring_width - self.border_width)

    @property
    def space_1_inset(self) -> int:
        return max(0, self.space_1 - self.focus_inset)

    @property
    def space_2_inset(self) -> int:
        return max(0, self.space_2 - self.focus_inset)

    @property
    def space_3_inset(self) -> int:
        return max(0, self.space_3 - self.focus_inset)

    @property
    def space_4_inset(self) -> int:
        return max(0, self.space_4 - self.focus_inset)

    @property
    def space_6_inset(self) -> int:
        return max(0, self.space_6 - self.focus_inset)

    @property
    def space_0_inset(self) -> int:
        """For controls with no resting padding (e.g. the toast action)."""
        return 0


#: Fallback stacks (MASTER §1, typography) used when the bundled OFL faces
#: fail to register — kept inside the token so QSS never hardcodes a family.
_FALLBACK_SANS = '"Segoe UI", "Noto Sans", sans-serif'
_FALLBACK_MONO = '"Consolas", "DejaVu Sans Mono", monospace'

ABYSS = Tokens(
    name="abyss",
    bg_window=PRIMITIVES["navy.950"],
    bg_surface=PRIMITIVES["navy.900"],
    bg_elevated=PRIMITIVES["navy.850"],
    bg_overlay=PRIMITIVES["navy.800"],
    bg_input=PRIMITIVES["navy.950"],
    border=PRIMITIVES["navy.700"],
    border_strong=PRIMITIVES["navy.600"],
    fg=PRIMITIVES["slate.100"],
    fg_secondary=PRIMITIVES["slate.300"],
    fg_muted=PRIMITIVES["slate.400"],
    fg_on_accent=PRIMITIVES["navy.950"],
    accent=PRIMITIVES["cyan.400"],
    accent_hover=PRIMITIVES["cyan.300"],
    accent_soft=PRIMITIVES["cyan.900a"],
    secondary=PRIMITIVES["violet.400"],
    secondary_soft=PRIMITIVES["violet.900a"],
    ok=PRIMITIVES["green.400"],
    warn=PRIMITIVES["amber.400"],
    danger=PRIMITIVES["red.400"],
    ok_soft=PRIMITIVES["green.900a"],
    warn_soft=PRIMITIVES["amber.900a"],
    danger_soft=PRIMITIVES["red.900a"],
    focus_ring_width=2,
    focus_ring_offset=1,
    font_display=f'"Barlow Condensed", "Barlow", {_FALLBACK_SANS}',
    font_body=f'"Barlow", {_FALLBACK_SANS}',
    font_mono=f'"JetBrains Mono", {_FALLBACK_MONO}',
    font_weight_regular=400,
    font_weight_medium=500,
    font_weight_semibold=600,
    font_weight_bold=700,
    text_xs=11,
    text_sm=12,
    text_base=13,
    text_md=14,
    text_lg=16,
    text_xl=20,
    text_2xl=26,
    text_display=34,
    letter_spacing_caps="0.06em",
    line_height="1.45",
    space_1=4,
    space_2=8,
    space_3=12,
    space_4=16,
    space_6=24,
    space_8=32,
    radius_sm=4,
    radius_md=6,
    radius_full=999,
    border_width=1,
    shadow_popup="0 6px 18px rgba(0, 0, 0, 0.35)",
    motion_fast=120,
    motion_base=160,
    motion_slow=220,
    motion_ease="OutCubic",
    motion_offset=6,
)

#: MASTER §2 theme table.  Every entry is an explicit ``replace`` of
#: :data:`ABYSS` restricted to :data:`THEME_OVERRIDABLE_KEYS`.
THEMES: dict[str, Tokens] = {
    "abyss": ABYSS,
    "inferno": replace(
        ABYSS,
        name="inferno",
        # 2026-09-18: was #fb923c (orange.400), only ΔE≈14 from warn
        # (#fbbf24) — "attention" and "actif" read as the same colour on a
        # badge row.  Deeper orange.500 pulls the accent away from warn
        # while keeping fg.on-accent at 6.72:1 (was 8.44:1, still ≥ 4.5).
        accent="#f97316",
        accent_hover="#fdba74",
        accent_soft="rgba(249, 115, 22, 0.14)",
        secondary="#fda4af",
        secondary_soft="rgba(253, 164, 175, 0.16)",
        bg_window="#140c0c",
        bg_surface="#1c1010",
        bg_elevated="#241616",
        bg_overlay="#2e1c1c",
        bg_input="#140c0c",
        border="#3a2222",
        border_strong="#4f2e2e",
    ),
    "emerald": replace(
        ABYSS,
        name="emerald",
        # 2026-09-18: was accent #34d399 (a green) + secondary #a3e635 (a
        # lime) on top of ok=#4ade80 — three greens, so "completed",
        # "active" and "schedule" were indistinguishable.  Teal accent +
        # lavender secondary keep one hue each for accent / ok / secondary.
        accent="#2dd4bf",
        accent_hover="#5eead4",
        accent_soft="rgba(45, 212, 191, 0.14)",
        secondary="#c4b5fd",
        secondary_soft="rgba(196, 181, 253, 0.16)",
        bg_window="#081410",
        bg_surface="#0c1a15",
        bg_elevated="#11231c",
        bg_overlay="#172d24",
        bg_input="#081410",
        border="#173026",
        border_strong="#224536",
    ),
    "frostbite": replace(
        ABYSS,
        name="frostbite",
        accent="#7dd3fc",
        accent_hover="#bae6fd",
        accent_soft="rgba(125, 211, 252, 0.14)",
        secondary="#c4b5fd",
        secondary_soft="rgba(196, 181, 253, 0.16)",
        bg_window="#0b1220",
        bg_surface="#101a2e",
        bg_elevated="#17233b",
        bg_overlay="#1e2c49",
        bg_input="#0b1220",
        border="#223354",
        border_strong="#2f4670",
    ),
    "obsidian": replace(
        ABYSS,
        name="obsidian",
        accent="#e5e7eb",
        accent_hover="#f8fafc",
        accent_soft="rgba(229, 231, 235, 0.14)",
        secondary="#94a3b8",
        secondary_soft="rgba(148, 163, 184, 0.16)",
        bg_window="#0a0a0c",
        bg_surface="#111114",
        bg_elevated="#18181c",
        bg_overlay="#212126",
        bg_input="#0a0a0c",
        border="#26262c",
        border_strong="#3a3a44",
    ),
    "void": replace(
        ABYSS,
        name="void",
        accent="#c084fc",
        accent_hover="#d8b4fe",
        accent_soft="rgba(192, 132, 252, 0.14)",
        secondary="#f472b6",
        secondary_soft="rgba(244, 114, 182, 0.16)",
        bg_window="#0c0a14",
        bg_surface="#120f1e",
        bg_elevated="#1a1528",
        bg_overlay="#231c34",
        bg_input="#0c0a14",
        border="#2a2140",
        border_strong="#3b2f5c",
    ),
}

DEFAULT_THEME = "abyss"


#: The theme the app is currently rendering.  Painters need the active
#: theme's colors (MASTER §4-3) but a QPainter lives deep inside a widget
#: that has no reference to MainWindow — plumbing the name through every
#: constructor would be ~15 signatures.  :func:`set_current` is called from
#: exactly one place (``MainWindow.apply_theme``), which is also the only
#: place that re-renders the stylesheet, so the two can never disagree.
_current_theme: str = DEFAULT_THEME


def set_current(theme: str) -> str:
    """Record the theme the app is rendering; returns the name stored.

    An unknown name is normalised to the fallback rather than stored as-is,
    so :func:`current` always names a real theme.
    """
    global _current_theme
    _current_theme = tokens(theme).name
    return _current_theme


def current() -> str:
    """Name of the theme the app is currently rendering."""
    return _current_theme


def current_tokens() -> Tokens:
    """Shorthand for ``tokens(current())`` — what painters actually want."""
    return tokens(_current_theme)


def tokens(theme: str) -> Tokens:
    """Return the token set of ``theme``; unknown names fall back to Abyss.

    A wrong theme name must never crash the app (a profile can carry a theme
    from a future version), but it must not pass silently either — hence the
    warning.
    """
    key = (theme or "").strip().lower()
    found = THEMES.get(key)
    if found is None:
        logger.warning("Unknown theme %r — falling back to %r", theme, DEFAULT_THEME)
        return THEMES[DEFAULT_THEME]
    return found


# --------------------------------------------------------------------------
# Color parsing / contrast
# --------------------------------------------------------------------------

_RGBA_RE = re.compile(
    r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([0-9.]+)\s*)?\)$",
    re.IGNORECASE,
)


def parse_color(value: str) -> tuple[int, int, int, float]:
    """Parse ``#rgb`` / ``#rrggbb`` / ``rgb(...)`` / ``rgba(...)`` to RGBA.

    Alpha is returned as a 0..1 float (QSS spells it that way).
    """
    text = value.strip()
    match = _RGBA_RE.match(text)
    if match:
        red, green, blue = (int(match.group(i)) for i in (1, 2, 3))
        alpha = float(match.group(4)) if match.group(4) is not None else 1.0
        return red, green, blue, alpha
    if text.startswith("#"):
        digits = text[1:]
        if len(digits) == 3:
            digits = "".join(ch * 2 for ch in digits)
        if len(digits) == 6:
            return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16), 1.0
        if len(digits) == 8:
            return (
                int(digits[0:2], 16),
                int(digits[2:4], 16),
                int(digits[4:6], 16),
                int(digits[6:8], 16) / 255.0,
            )
    raise ValueError(f"Unparseable color: {value!r}")


def _token_attr(name: str) -> str:
    """``"bg.window"`` / ``"bg-window"`` / ``"bg_window"`` → ``"bg_window"``."""
    return name.strip().replace(".", "_").replace("-", "_")


def qcolor(tokens_or_theme: Tokens | str, name: str) -> QColor:
    """Return the named token of a theme as a :class:`QColor`.

    Accepts either a :class:`Tokens` instance or a theme name, and either the
    MASTER spelling (``"bg.window"``) or the attribute spelling
    (``"bg_window"``).  This is what painters (overlay, flow map, delegates)
    use instead of a color literal (MASTER §4-3).
    """
    theme_tokens = tokens_or_theme if isinstance(tokens_or_theme, Tokens) else tokens(tokens_or_theme)
    attr = _token_attr(name)
    if not hasattr(theme_tokens, attr):
        raise KeyError(f"Unknown token: {name!r}")
    value = getattr(theme_tokens, attr)
    if not isinstance(value, str):
        raise TypeError(f"Token {name!r} is not a color ({value!r})")
    red, green, blue, alpha = parse_color(value)
    color = QColor(red, green, blue)
    color.setAlphaF(alpha)
    return color


def _relative_luminance(rgb: tuple[float, float, float]) -> float:
    """WCAG 2.1 relative luminance of a fully opaque sRGB triplet."""

    def channel(raw: float) -> float:
        value = raw / 255.0
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = rgb
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def composite(fg: str, bg: str) -> tuple[float, float, float]:
    """Alpha-composite ``fg`` over ``bg`` and return an opaque RGB triplet."""
    f_red, f_green, f_blue, f_alpha = parse_color(fg)
    b_red, b_green, b_blue, b_alpha = parse_color(bg)
    if b_alpha < 1.0:  # a translucent backdrop ultimately sits on the window
        b_red, b_green, b_blue = (
            b_red * b_alpha,
            b_green * b_alpha,
            b_blue * b_alpha,
        )
    return (
        f_red * f_alpha + b_red * (1.0 - f_alpha),
        f_green * f_alpha + b_green * (1.0 - f_alpha),
        f_blue * f_alpha + b_blue * (1.0 - f_alpha),
    )


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG 2.1 contrast ratio between ``fg`` and ``bg`` (1.0 … 21.0).

    A translucent ``fg`` is composited over ``bg`` first — QSS has no notion
    of blending, so this is what the eye actually sees.
    """
    fg_rgb = composite(fg, bg)
    bg_rgb = composite(bg, bg) if parse_color(bg)[3] < 1.0 else parse_color(bg)[:3]
    light, dark = sorted((_relative_luminance(fg_rgb), _relative_luminance(bg_rgb)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


# --------------------------------------------------------------------------
# §4-4 data-driven colors
# --------------------------------------------------------------------------

#: Item rarity colors.  THIS is the owner since the Armory tokenization
#: wave (2026-09-18): ``ItemDatabase/app.py`` binds its own ``GRADE_COLORS``
#: to this table at import and only falls back to its own literal copy when
#: ``core.theme`` is unimportable at all (the standalone
#: ``AION2_ItemDatabase.spec`` build, or ``python ItemDatabase/app.py`` from
#: a checkout without the repo root on ``sys.path``).  That copy is gated
#: against this one by ``tests/test_theme.py::test_data_color_mirrors_item_database``.
GRADE_COLORS: dict[str, str] = {
    "Common": "#94a3b8",
    "Rare": "#4ade80",
    "Unique": "#facc15",
    "Epic": "#f59e0b",
    "Legend": "#38bdf8",
}

#: Gear-flavor colors — same ownership story as :data:`GRADE_COLORS`.
GEAR_TYPE_COLORS: dict[str, str] = {
    "PvP": "#fb7185",
    "PvE": "#4ade80",
    "Neutral": "#94a3b8",
}

# ---- Armory data tables (moved here whole on 2026-09-18) ----------------
#
# Every table below used to be a module-level literal in
# ``ItemDatabase/app.py``.  They are colors the *data* picks -- a skill's
# type, a recipe's method, an Arcana Set's theme, a Genius board, a stat
# role -- which MASTER §4-4 names as the one tolerated exception to "no
# color outside the tokens".  The exception is about *where the value comes
# from*, not about *who stores it*: stored in the widget file they were 190
# unreachable literals, stored here they are one inventory the QSS template
# can also read (``{{data.<kind>.<key>}}``).

#: Skill kind — active / passive / stigma (Skill Planner, badges, cards).
SKILL_TYPE_COLORS: dict[str, str] = {
    "active": "#22d3ee",
    "passive": "#a855f7",
    "stigma": "#facc15",
}

#: How a recipe is obtained.  ``Herstellung``/``Transfer`` are the stable
#: internal method identifiers of the recipe data, not display strings.
CRAFT_METHOD_COLORS: dict[str, str] = {
    "Transfer": "#f59e0b",
    "Herstellung": "#4ade80",
}

#: Arcana Set theme identity (Choose Card Sets, Set banners, card pills).
ARCANA_THEME_COLORS: dict[str, str] = {
    "Vigor": "#facc15",
    "Magic": "#22d3ee",
    "Frenzy": "#f97316",
    "Purity": "#a78bfa",
    "Punishment": "#ef4444",
    "Protection": "#4ade80",
    "Indomitability": "#f472b6",
}

#: Arcana Set display category (derived from each theme's icon set-label).
ARCANA_CATEGORY_COLORS: dict[str, str] = {
    "pve": "#4ade80",
    "pvp": "#fb7185",
    "offense": "#f59e0b",
    "defence": "#38bdf8",
    "cure": "#a855f7",
}

#: Dark end of each category's fallback banner gradient (the 0.0 stop; the
#: 1.0 stop is :data:`ARCANA_CATEGORY_COLORS`).  Only used for a Set with
#: no real background photo yet.
ARCANA_CATEGORY_DEEP_COLORS: dict[str, str] = {
    "pve": "#14532d",
    "pvp": "#4c0519",
    "offense": "#78350f",
    "defence": "#0c4a6e",
    "cure": "#4c1d95",
}

#: Genius Insight board identity.
GENIUS_BOARD_COLORS: dict[str, str] = {
    "Cogni": "#3ba7f2",
    "Fera": "#ef4444",
    "Natura": "#22c55e",
    "Varian": "#f2b90c",
    "Special": "#2dd4bf",
}

#: Stat-priority role (User-Wunsch: "Angreifer Orange, Verteidiger Blau
#: und Support Grün").  Keys are the role identifiers the profile stores.
ROLE_COLORS: dict[str, str] = {
    "Angreifer": "#fb923c",
    "Verteidiger": "#60a5fa",
    "Support": "#4ade80",
}

#: A skill's damage type (physical vs magical), Skill Planner badges.
DAMAGE_TYPE_COLORS: dict[str, str] = {
    "physic": "#f87171",
    "magic": "#60a5fa",
}

#: Active-skill specialization slot state, as the user specified it
#: ("30% Türkis, 70% schwarz, 50% Transparenz" for an unlocked-but-unpicked
#: option; solid dark turquoise once picked).  Not accent-derived on
#: purpose: it reads as "this belongs to the skill tree", not as "this is
#: the app's current accent".
SPEC_STATE_COLORS: dict[str, str] = {
    "available": "rgba(94, 234, 212, 0.35)",
    "chosen": "#0d9488",
}

#: Built-in reset timers.  THIS is the owner (ownership was inverted on
#: 2026-09-18): ``ui/overlay/overlay_window.py`` and ``ui/pages/timers_page.py``
#: read from here by key.  A drift "fix" must change this table, not theirs.
_TIMER_COLORS: dict[str, str] = {
    "daily": "#3b82f6",
    "weekly": "#8b5cf6",
    "shugo": "#f59e0b",
    "rift": "#22d3ee",
    "custom": "#14b8a6",
}

#: The eight swatches a user can pick for a custom timer.  THIS is the
#: owner: ``ui/custom_timer_dialog.CUSTOM_TIMER_COLORS`` is built from it
#: (ownership inverted 2026-09-18).
_TIMER_SWATCHES: dict[str, str] = {
    "cyan": "#22d3ee",
    "purple": "#a855f7",
    "green": "#22c55e",
    "red": "#ef4444",
    "orange": "#f97316",
    "pink": "#ec4899",
    "yellow": "#f59e0b",
    "blue": "#3b82f6",
}

_DATA_COLORS: dict[str, dict[str, str]] = {
    "item_grade": GRADE_COLORS,
    "gear_type": GEAR_TYPE_COLORS,
    "timer": _TIMER_COLORS,
    "timer_swatch": _TIMER_SWATCHES,
    "skill_type": SKILL_TYPE_COLORS,
    "craft_method": CRAFT_METHOD_COLORS,
    "arcana_theme": ARCANA_THEME_COLORS,
    "arcana_category": ARCANA_CATEGORY_COLORS,
    "arcana_category_deep": ARCANA_CATEGORY_DEEP_COLORS,
    "genius_board": GENIUS_BOARD_COLORS,
    "role": ROLE_COLORS,
    "damage_type": DAMAGE_TYPE_COLORS,
    "spec_state": SPEC_STATE_COLORS,
}

#: Returned when a data key is unknown (MASTER §2 ``fg.muted``).
_DATA_FALLBACK = PRIMITIVES["slate.400"]


def data_color(kind: str, key: str) -> str:
    """Color for a value the *data* decides, not the theme (MASTER §4-4).

    ``kind`` is one of ``item_grade``, ``gear_type``, ``timer``,
    ``timer_swatch``.  An unknown key yields the muted foreground rather than
    raising: catalogs grow, the UI must not.
    """
    table = _DATA_COLORS.get(kind)
    if table is None:
        raise KeyError(f"Unknown data-color kind: {kind!r} (known: {sorted(_DATA_COLORS)})")
    return table.get(key, _DATA_FALLBACK)


def data_color_keys(kind: str) -> tuple[str, ...]:
    """Known keys of a data-color table, in declaration order."""
    table = _DATA_COLORS.get(kind)
    if table is None:
        raise KeyError(f"Unknown data-color kind: {kind!r} (known: {sorted(_DATA_COLORS)})")
    return tuple(table)


# --------------------------------------------------------------------------
# QSS generation
# --------------------------------------------------------------------------

#: ``{{token}}``, ``{{bg.window}}``, ``{{data.item_grade.Legend}}`` and any
#: of those with an alpha modifier: ``{{accent|0.14}}``.
#:
#: The alpha form exists for the Armory template (2026-09-18).  Its
#: hand-written ancestor was built out of translucent layers -- 60 rules
#: spelling ``rgba(34, 211, 238, 0.06 … 0.25)`` over a dark ground -- and
#: the semantic set has exactly one alpha per role (``accent.soft`` at
#: 0.14).  Without a modifier, porting it meant either flattening every
#: layer to one soft token (visibly different) or inventing a dozen
#: ``*.soft-er`` tokens nothing else would use.  ``{{accent|0.06}}``
#: renders the *active theme's* accent at the layer the widget asked for,
#: which is what the literal meant in the first place.
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)(?:\|([0-9.]+))?\s*\}\}")


#: Families Qt actually registered, as reported by ``core.fonts.load_fonts``.
#: Empty until someone feeds them in (``main.py``, ``scripts/theme_preview``).
#:
#: Why this exists: the QSS asks for ``"Barlow"`` by name, and a family Qt
#: does not know is dropped silently -- the whole rule falls back with no
#: warning.  ``load_fonts()`` already resolves what Qt really loaded
#: (including the "trust Qt, not the spec" branch for a renamed upstream
#: release), but that answer was being discarded, so the branch was dead
#: with respect to the stylesheet (review F-11b).
_RESOLVED_FAMILIES: dict[str, str] = {}


def set_font_families(resolved: dict[str, str]) -> None:
    """Record the families Qt registered, so the QSS names those."""
    _RESOLVED_FAMILIES.clear()
    _RESOLVED_FAMILIES.update({role: family for role, family in resolved.items() if family})


def font_stack(tokens_or_theme: Tokens | str, role: str) -> str:
    """The QSS ``font-family`` stack for ``role``, Qt's answer first.

    Falls back to the token's own stack when nothing has been registered
    (a headless import, a test) -- which is also the stack that carries the
    MASTER §1 fallbacks.
    """
    theme_tokens = tokens_or_theme if isinstance(tokens_or_theme, Tokens) else tokens(tokens_or_theme)
    declared = getattr(theme_tokens, f"font_{role}")
    resolved = _RESOLVED_FAMILIES.get(role)
    if not resolved:
        return declared
    entries = [part.strip() for part in declared.split(",")]
    quoted = f'"{resolved}"'
    if entries and entries[0] == quoted:
        return declared
    # Put what Qt really has in front, keep the declared stack as fallback.
    return ", ".join([quoted] + [e for e in entries if e != quoted])


def with_alpha(color: str, alpha: float) -> str:
    """``("#22d3ee", 0.14)`` → ``"rgba(34, 211, 238, 0.14)"``.

    Multiplies into an already-translucent color rather than replacing its
    alpha, so ``with_alpha(accent_soft, 0.5)`` is half of the soft layer
    instead of a surprise opacity bump.
    """
    red, green, blue, own_alpha = parse_color(color)
    effective = max(0.0, min(1.0, own_alpha * alpha))
    return f"rgba({red}, {green}, {blue}, {effective:g})"


def render_qss(template: str, theme: str = DEFAULT_THEME, asset_path: str = "") -> str:
    """Substitute ``{{token}}`` and ``ASSET_PATH`` in an in-memory template.

    Three placeholder forms (see :data:`_PLACEHOLDER_RE`):

    * ``{{accent}}`` / ``{{bg.window}}`` — a semantic token of ``theme``;
    * ``{{data.item_grade.Legend}}`` — a :func:`data_color` entry, for the
      rules a *data* color decides (MASTER §4-4);
    * either of those with ``|alpha``, e.g. ``{{accent|0.06}}``.

    Raises :class:`KeyError` on an unknown placeholder — a typo in the
    template must fail the build, not silently ship a broken rule.
    """
    theme_tokens = tokens(theme)
    unknown: list[str] = []

    def resolve(name: str) -> str | None:
        if name.startswith("data."):
            parts = name.split(".", 2)
            if len(parts) != 3:
                return None
            _, kind, key = parts
            if kind not in _DATA_COLORS or key not in _DATA_COLORS[kind]:
                return None
            return data_color(kind, key)
        attr = _token_attr(name)
        if attr in ("font_display", "font_body", "font_mono"):
            # Resolved through core.fonts so the sheet names the family Qt
            # actually registered (see set_font_families).
            return font_stack(theme_tokens, attr.removeprefix("font_"))
        if not hasattr(theme_tokens, attr):
            return None
        return str(getattr(theme_tokens, attr))

    def substitute(match: re.Match[str]) -> str:
        value = resolve(match.group(1))
        if value is None:
            unknown.append(match.group(1))
            return match.group(0)
        alpha = match.group(2)
        if alpha is None:
            return value
        try:
            return with_alpha(value, float(alpha))
        except ValueError:
            # A number the template spelled wrong, or a non-color token:
            # same class of mistake as an unknown name, same loud failure.
            unknown.append(f"{match.group(1)}|{alpha}")
            return match.group(0)

    rendered = _PLACEHOLDER_RE.sub(substitute, template)
    if unknown:
        raise KeyError(f"Unknown token placeholder(s) in QSS template: {sorted(set(unknown))}")
    return rendered.replace("ASSET_PATH", asset_path)


def build_qss_from(
    path: Path | str, theme: str = DEFAULT_THEME, asset_path: str = "", *, bundle_hint: str = ""
) -> str:
    """Render *any* ``{{token}}`` template file for ``theme``.

    The app's own sheet goes through :func:`build_qss`; this is the generic
    form, added for ``ItemDatabase/styles.template.qss`` (the Armory owns
    its own sheet because its windows are parentless and therefore outside
    the application sheet's ``QWidget[aion2="true"]`` scope -- see
    tests/test_app_sheet_isolation.py).

    ``bundle_hint`` is appended to the not-found error: a template missing
    from a frozen build is a spec-datas mistake, and the message should say
    which line is missing rather than leave the reader to guess.
    """
    path = Path(path)
    try:
        template = path.read_text(encoding="utf-8")
    except OSError as error:
        # A missing template means an unstyled app, and the message must
        # name the path that was actually tried -- this used to surface as a
        # bare FileNotFoundError from inside MainWindow.__init__.
        raise RuntimeError(
            f"QSS template not found at {path} — is it bundled?"
            + (f" ({bundle_hint})" if bundle_hint else "")
        ) from error
    return render_qss(template, theme=theme, asset_path=asset_path)


def build_qss(theme: str = DEFAULT_THEME, asset_path: str = "") -> str:
    """Render ``ui/styles.template.qss`` for ``theme``.

    ``asset_path`` replaces the ``ASSET_PATH`` marker in ``url(...)`` rules,
    exactly like the loader it supersedes (``MainWindow.load_styles``): the
    repo root in a dev checkout, ``sys._MEIPASS`` in a frozen build.
    """
    return build_qss_from(
        template_path(),
        theme=theme,
        asset_path=asset_path,
        bundle_hint="spec datas must carry ('ui/styles.template.qss', 'ui')",
    )


def build_palette(tokens_or_theme: Tokens | str = DEFAULT_THEME) -> QPalette:
    """The Fusion fallback palette for one theme, from the tokens.

    Everything the QSS *doesn't* explicitly cover (a sub-control, a native
    dialog, a widget nobody thought to style) is painted by Qt from the
    application palette, and Fusion's default palette follows the OS's own
    light/dark setting — which is how a system in light mode used to produce
    black-on-dark text and plain white list boxes inside this all-dark app
    (User-reported, 2026-08-29; the literal-hex version of this function
    used to live in ``main.py``).

    Derived from the same tokens as the stylesheet so that a theme switch
    moves both together instead of leaving a navy baseline under an Inferno
    sheet.
    """
    theme_tokens = tokens_or_theme if isinstance(tokens_or_theme, Tokens) else tokens(tokens_or_theme)

    def color(name: str) -> QColor:
        return qcolor(theme_tokens, name)

    palette = QPalette()
    palette.setColor(QPalette.Window, color("bg.surface"))
    palette.setColor(QPalette.WindowText, color("fg"))
    palette.setColor(QPalette.Base, color("bg.input"))
    palette.setColor(QPalette.AlternateBase, color("bg.elevated"))
    palette.setColor(QPalette.ToolTipBase, color("bg.overlay"))
    palette.setColor(QPalette.ToolTipText, color("fg"))
    palette.setColor(QPalette.Text, color("fg"))
    palette.setColor(QPalette.Button, color("bg.elevated"))
    palette.setColor(QPalette.ButtonText, color("fg"))
    palette.setColor(QPalette.BrightText, color("danger"))
    palette.setColor(QPalette.Link, color("accent"))
    palette.setColor(QPalette.Highlight, color("accent"))
    # MASTER §2: text on the accent is fg.on-accent — never white on cyan.
    palette.setColor(QPalette.HighlightedText, color("fg.on_accent"))
    # Qt paints QLineEdit/QComboBox placeholders from this role, not from
    # the QSS (audit D/C3: the old placeholder sat at 2.48:1).
    palette.setColor(QPalette.PlaceholderText, color("fg.muted"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, color("fg.muted"))
    return palette


def apply(app, theme: str = DEFAULT_THEME, asset_path: str = "") -> str:
    """Apply the rendered stylesheet to ``app`` and return it (MASTER §4-1).

    Parentless windows (Overlay, ItemDatabase, FlowMap) inherit an
    application-wide stylesheet, so this replaces the three separate delivery
    paths the old per-widget ``setStyleSheet`` needed.
    """
    styles = build_qss(theme, asset_path)
    app.setStyleSheet(styles)
    return styles
