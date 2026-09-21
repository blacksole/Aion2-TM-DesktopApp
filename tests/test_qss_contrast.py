"""WCAG contrast gate on the token table (MASTER §2 / §4-5, audit D/C3).

The old QSS shipped white-on-cyan at 1.81:1 and a 2.48:1 placeholder in all
six themes.  These thresholds are what make that class of regression
impossible to merge: change a token, and the theme has to prove itself here.
"""

import pytest

from core import theme
from core.theme import THEMES, composite, contrast_ratio

THEME_NAMES = sorted(THEMES)

#: MASTER §2 required pairs.  (label, fg token, bg token, minimum ratio)
#: 4.5 = WCAG AA normal text, 7 = AAA, 3 = AA non-text / large text.
REQUIRED_PAIRS = (
    ("fg_on_accent on accent", "fg_on_accent", "accent", 4.5),
    ("fg_muted on bg_surface", "fg_muted", "bg_surface", 4.5),
    ("fg on bg_elevated", "fg", "bg_elevated", 7.0),
    ("fg_secondary on bg_surface", "fg_secondary", "bg_surface", 4.5),
)

#: Badge text on its own soft fill, itself composited over a card.
SOFT_PAIRS = (("ok", "ok_soft"), ("warn", "warn_soft"), ("danger", "danger_soft"))
SOFT_MINIMUM = 3.0


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(round(channel) for channel in rgb)


def _soft_over_card(tokens: theme.Tokens, soft_name: str) -> str:
    """The real color of a ``*.soft`` badge fill sitting on a card."""
    return _hex(composite(getattr(tokens, soft_name), tokens.bg_elevated))


@pytest.mark.parametrize("name", THEME_NAMES)
@pytest.mark.parametrize("label,fg,bg,minimum", REQUIRED_PAIRS, ids=[p[0] for p in REQUIRED_PAIRS])
def test_required_pair(name, label, fg, bg, minimum):
    tokens = THEMES[name]
    ratio = contrast_ratio(getattr(tokens, fg), getattr(tokens, bg))
    assert ratio >= minimum, f"{name}: {label} = {ratio:.2f}:1 (need {minimum}:1)"


@pytest.mark.parametrize("name", THEME_NAMES)
@pytest.mark.parametrize("color,soft", SOFT_PAIRS, ids=[p[0] for p in SOFT_PAIRS])
def test_status_badge_on_its_soft_fill(name, color, soft):
    tokens = THEMES[name]
    background = _soft_over_card(tokens, soft)
    ratio = contrast_ratio(getattr(tokens, color), background)
    assert ratio >= SOFT_MINIMUM, f"{name}: {color} on {soft} over card = {ratio:.2f}:1 (need {SOFT_MINIMUM}:1)"


@pytest.mark.parametrize("name", THEME_NAMES)
def test_accent_text_on_surfaces(name):
    """Accent used as *text* (links, section titles, toast action)."""
    tokens = THEMES[name]
    for surface in ("bg_surface", "bg_elevated"):
        ratio = contrast_ratio(tokens.accent, getattr(tokens, surface))
        assert ratio >= 4.5, f"{name}: accent on {surface} = {ratio:.2f}:1"


@pytest.mark.parametrize("name", THEME_NAMES)
def test_secondary_badge_text_on_its_soft_fill(name):
    """Schedule badges are the secondary color on secondary.soft."""
    tokens = THEMES[name]
    background = _soft_over_card(tokens, "secondary_soft")
    ratio = contrast_ratio(tokens.secondary, background)
    assert ratio >= SOFT_MINIMUM, f"{name}: secondary on its soft fill = {ratio:.2f}:1"


@pytest.mark.parametrize("name", THEME_NAMES)
def test_pill_text_on_accent_soft(name):
    """MASTER §3: an active pill is fg text on accent.soft over a card."""
    tokens = THEMES[name]
    background = _soft_over_card(tokens, "accent_soft")
    ratio = contrast_ratio(tokens.fg, background)
    assert ratio >= 4.5, f"{name}: fg on accent.soft = {ratio:.2f}:1"


@pytest.mark.parametrize("name", THEME_NAMES)
def test_hover_accent_keeps_on_accent_text_legible(name):
    """The hover fill of a primary button must stay readable too."""
    tokens = THEMES[name]
    ratio = contrast_ratio(tokens.fg_on_accent, tokens.accent_hover)
    assert ratio >= 4.5, f"{name}: fg_on_accent on accent_hover = {ratio:.2f}:1"


# --------------------------------------------------------------------------
# The maths itself
# --------------------------------------------------------------------------


def test_contrast_ratio_known_values():
    assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0, abs=0.01)
    assert contrast_ratio("#000000", "#000000") == pytest.approx(1.0, abs=0.001)
    # Direction must not matter.
    assert contrast_ratio("#ffffff", "#0b1120") == pytest.approx(contrast_ratio("#0b1120", "#ffffff"))


def test_contrast_ratio_composites_alpha():
    """A 14 %-alpha white over black is NOT white: 21:1 would be a lie."""
    opaque = contrast_ratio("#ffffff", "#000000")
    translucent = contrast_ratio("rgba(255, 255, 255, 0.14)", "#000000")
    assert translucent < opaque
    # _hex() rounds to 8-bit, hence the tolerance rather than an exact match.
    flattened = contrast_ratio(_hex(composite("rgba(255,255,255,0.14)", "#000000")), "#000000")
    assert translucent == pytest.approx(flattened, abs=0.01)


def test_the_regression_this_gate_exists_for():
    """Audit D/C3: white on the old cyan gradient end, and the fix."""
    assert contrast_ratio("#ffffff", "#22d3ee") < 2.0
    assert contrast_ratio(theme.ABYSS.fg_on_accent, theme.ABYSS.accent) >= 4.5
