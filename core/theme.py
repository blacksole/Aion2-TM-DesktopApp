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

from PySide6.QtGui import QColor

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = _REPO_ROOT / "ui" / "styles.template.qss"

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
        accent="#fb923c",
        accent_hover="#fdba74",
        accent_soft="rgba(251, 146, 60, 0.14)",
        secondary="#fda4af",
        secondary_soft="rgba(253, 164, 175, 0.16)",
        bg_window="#140c0c",
        bg_surface="#1c1010",
        bg_elevated="#241616",
        bg_overlay="#2e1c1c",
        bg_input="#140c0c",
    ),
    "emerald": replace(
        ABYSS,
        name="emerald",
        accent="#34d399",
        accent_hover="#6ee7b7",
        accent_soft="rgba(52, 211, 153, 0.14)",
        secondary="#a3e635",
        secondary_soft="rgba(163, 230, 53, 0.16)",
        bg_window="#081410",
        bg_surface="#0c1a15",
        bg_elevated="#11231c",
        bg_overlay="#172d24",
        bg_input="#081410",
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
    ),
}

DEFAULT_THEME = "abyss"


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

#: Item rarity colors — mirror of ``ItemDatabase/app.py``'s ``GRADE_COLORS``
#: (read-only; that module stays the owner until it is migrated).
_ITEM_GRADE_COLORS: dict[str, str] = {
    "Common": "#94a3b8",
    "Rare": "#4ade80",
    "Unique": "#facc15",
    "Epic": "#f59e0b",
    "Legend": "#38bdf8",
}

#: Gear-flavor colors — mirror of ``ItemDatabase/app.py``'s ``GEAR_TYPE_COLORS``.
_GEAR_TYPE_COLORS: dict[str, str] = {
    "PvP": "#fb7185",
    "PvE": "#4ade80",
    "Neutral": "#94a3b8",
}

#: Built-in reset timers — mirror of ``ui/overlay/overlay_window.py``'s
#: ``TIMER_COLORS`` / ``CUSTOM_TIMER_COLOR``.
_TIMER_COLORS: dict[str, str] = {
    "daily": "#3b82f6",
    "weekly": "#8b5cf6",
    "shugo": "#f59e0b",
    "rift": "#22d3ee",
    "custom": "#14b8a6",
}

#: The eight swatches a user can pick for a custom timer — mirror of
#: ``ui/custom_timer_dialog.py``'s ``CUSTOM_TIMER_COLORS``.
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
    "item_grade": _ITEM_GRADE_COLORS,
    "gear_type": _GEAR_TYPE_COLORS,
    "timer": _TIMER_COLORS,
    "timer_swatch": _TIMER_SWATCHES,
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

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")


def render_qss(template: str, theme: str = DEFAULT_THEME, asset_path: str = "") -> str:
    """Substitute ``{{token}}`` and ``ASSET_PATH`` in an in-memory template.

    Raises :class:`KeyError` on an unknown placeholder — a typo in the
    template must fail the build, not silently ship a broken rule.
    """
    theme_tokens = tokens(theme)
    unknown: list[str] = []

    def substitute(match: re.Match[str]) -> str:
        attr = _token_attr(match.group(1))
        if not hasattr(theme_tokens, attr):
            unknown.append(match.group(1))
            return match.group(0)
        return str(getattr(theme_tokens, attr))

    rendered = _PLACEHOLDER_RE.sub(substitute, template)
    if unknown:
        raise KeyError(f"Unknown token placeholder(s) in QSS template: {sorted(set(unknown))}")
    return rendered.replace("ASSET_PATH", asset_path)


def build_qss(theme: str = DEFAULT_THEME, asset_path: str = "") -> str:
    """Render ``ui/styles.template.qss`` for ``theme``.

    ``asset_path`` replaces the ``ASSET_PATH`` marker in ``url(...)`` rules,
    exactly like the loader it supersedes (``MainWindow.load_styles``): the
    repo root in a dev checkout, ``sys._MEIPASS`` in a frozen build.
    """
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return render_qss(template, theme=theme, asset_path=asset_path)


def apply(app, theme: str = DEFAULT_THEME, asset_path: str = "") -> str:
    """Apply the rendered stylesheet to ``app`` and return it (MASTER §4-1).

    Parentless windows (Overlay, ItemDatabase, FlowMap) inherit an
    application-wide stylesheet, so this replaces the three separate delivery
    paths the old per-widget ``setStyleSheet`` needed.
    """
    styles = build_qss(theme, asset_path)
    app.setStyleSheet(styles)
    return styles
