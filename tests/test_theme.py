"""core/theme.py + ui/styles.template.qss — token system invariants."""

import dataclasses
import re
from pathlib import Path

import pytest

from core import theme


def test_six_themes_exactly():
    assert set(theme.THEMES) == {"abyss", "inferno", "emerald", "frostbite", "obsidian", "void"}
    assert theme.THEMES["abyss"] is theme.ABYSS


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_theme_name_matches_key(name):
    assert theme.THEMES[name].name == name


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_every_theme_builds_qss(name):
    qss = theme.build_qss(name, asset_path="/tmp/assets")
    assert len(qss) > 5000, "template rendered suspiciously small"
    assert "{{" not in qss and "}}" not in qss, "unsubstituted placeholder left in output"
    assert "ASSET_PATH" not in qss
    assert "/tmp/assets/assets/icons/arrow_down_orange.png" in qss


def _without_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def test_template_has_no_theme_scoped_selectors():
    """MASTER §4-2: a theme is other token values, not another QSS block."""
    template = _without_comments(theme.TEMPLATE_PATH.read_text(encoding="utf-8"))
    assert "[theme=" not in template


def test_template_declares_no_gradient():
    """MASTER thesis: "zéro dégradé décoratif"."""
    template = _without_comments(theme.TEMPLATE_PATH.read_text(encoding="utf-8"))
    assert "qlineargradient" not in template
    assert "qradialgradient" not in template


def test_every_placeholder_in_template_resolves():
    template = theme.TEMPLATE_PATH.read_text(encoding="utf-8")
    names = {m.group(1) for m in theme._PLACEHOLDER_RE.finditer(template)}
    assert names, "template has no placeholders at all — wrong file?"
    unknown = {n for n in names if not hasattr(theme.ABYSS, n.replace(".", "_").replace("-", "_"))}
    assert not unknown, f"placeholders with no matching token: {sorted(unknown)}"


def test_unknown_placeholder_raises_loudly():
    with pytest.raises(KeyError) as excinfo:
        theme.render_qss("QWidget { color: {{not_a_token}}; }")
    assert "not_a_token" in str(excinfo.value)


def test_unknown_placeholder_names_every_offender():
    with pytest.raises(KeyError) as excinfo:
        theme.render_qss("a{color:{{nope_one}};} b{color:{{nope_two}};}")
    message = str(excinfo.value)
    assert "nope_one" in message and "nope_two" in message


def test_render_qss_accepts_master_spelling():
    assert theme.render_qss("x { color: {{bg.window}}; }", "abyss") == f"x {{ color: {theme.ABYSS.bg_window}; }}"


def test_unknown_theme_falls_back_to_abyss_with_warning(caplog):
    with caplog.at_level("WARNING"):
        got = theme.tokens("chartreuse")
    assert got is theme.ABYSS
    assert "chartreuse" in caplog.text


@pytest.mark.parametrize("name", ["abyss", "ABYSS", " Abyss "])
def test_theme_lookup_is_forgiving_about_case(name):
    assert theme.tokens(name) is theme.ABYSS


def test_tokens_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        theme.ABYSS.accent = "#ff0000"


# --------------------------------------------------------------------------
# MASTER §2: a theme may only redefine accent*/secondary*/bg.*
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(set(theme.THEMES) - {"abyss"}))
def test_theme_only_overrides_allowed_keys(name):
    tokens = theme.THEMES[name]
    differing = {
        field.name
        for field in dataclasses.fields(theme.Tokens)
        if field.name != "name" and getattr(tokens, field.name) != getattr(theme.ABYSS, field.name)
    }
    illegal = differing - theme.THEME_OVERRIDABLE_KEYS
    assert not illegal, f"{name} redefines tokens MASTER §2 forbids: {sorted(illegal)}"


@pytest.mark.parametrize("name", sorted(set(theme.THEMES) - {"abyss"}))
def test_theme_actually_differs_from_abyss(name):
    """A theme that changed nothing would be a copy-paste bug, not a theme."""
    assert theme.THEMES[name].accent != theme.ABYSS.accent


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_status_and_on_accent_are_shared(name):
    """MASTER §2: no theme may move ok/warn/danger or fg.on-accent."""
    tokens = theme.THEMES[name]
    for field in ("ok", "warn", "danger", "ok_soft", "warn_soft", "danger_soft", "fg_on_accent"):
        assert getattr(tokens, field) == getattr(theme.ABYSS, field)


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_focus_ring_follows_accent(name):
    tokens = theme.THEMES[name]
    assert tokens.focus_ring == tokens.accent
    assert tokens.focus_ring_width == 2


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_bg_input_matches_bg_window(name):
    """The derivation rule recorded in MASTER §2."""
    tokens = theme.THEMES[name]
    assert tokens.bg_input == tokens.bg_window


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_surfaces_form_a_ladder(name):
    """window darkest → surface → elevated → overlay lightest."""
    tokens = theme.THEMES[name]
    ladder = [tokens.bg_window, tokens.bg_surface, tokens.bg_elevated, tokens.bg_overlay]
    luminances = [theme._relative_luminance(theme.parse_color(c)[:3]) for c in ladder]
    assert luminances == sorted(luminances), f"{name} surfaces are not ordered: {ladder}"


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_every_color_token_parses(name):
    tokens = theme.THEMES[name]
    for field in dataclasses.fields(theme.Tokens):
        value = getattr(tokens, field.name)
        if not isinstance(value, str) or field.name in {
            "name",
            "font_display",
            "font_body",
            "font_mono",
            "letter_spacing_caps",
            "line_height",
            "shadow_popup",
            "motion_ease",
        }:
            continue
        assert theme.parse_color(value), f"{name}.{field.name} = {value!r}"


# --------------------------------------------------------------------------
# Color parsing / QColor
# --------------------------------------------------------------------------


def test_parse_color_hex_forms():
    assert theme.parse_color("#0b1120") == (11, 17, 32, 1.0)
    assert theme.parse_color("#abc") == (170, 187, 204, 1.0)
    red, green, blue, alpha = theme.parse_color("#0b112080")
    assert (red, green, blue) == (11, 17, 32)
    assert alpha == pytest.approx(128 / 255)


def test_parse_color_rgba_forms():
    assert theme.parse_color("rgba(34, 211, 238, 0.14)") == (34, 211, 238, 0.14)
    assert theme.parse_color("rgb(34,211,238)") == (34, 211, 238, 1.0)


def test_parse_color_rejects_garbage():
    with pytest.raises(ValueError):
        theme.parse_color("cyan-ish")


def test_qcolor_parses_hex():
    color = theme.qcolor(theme.ABYSS, "accent")
    assert (color.red(), color.green(), color.blue()) == (34, 211, 238)
    assert color.alphaF() == pytest.approx(1.0)


def test_qcolor_parses_rgba():
    color = theme.qcolor(theme.ABYSS, "accent.soft")
    assert (color.red(), color.green(), color.blue()) == (34, 211, 238)
    assert color.alphaF() == pytest.approx(0.14, abs=0.01)


def test_qcolor_accepts_theme_name_and_both_spellings():
    from_name = theme.qcolor("void", "bg_window")
    from_dotted = theme.qcolor("void", "bg.window")
    assert from_name == from_dotted
    assert from_name.name() == "#0c0a14"


def test_qcolor_rejects_unknown_and_non_color_tokens():
    with pytest.raises(KeyError):
        theme.qcolor(theme.ABYSS, "accent.glow")
    with pytest.raises(TypeError):
        theme.qcolor(theme.ABYSS, "text_base")


# --------------------------------------------------------------------------
# §4-4 data colors
# --------------------------------------------------------------------------


_APP_PY = theme.TEMPLATE_PATH.parent.parent / "ItemDatabase" / "app.py"


def _dict_literal_from_app_py(name: str) -> dict[str, str]:
    """Read a ``{"Key": "#hex", ...}`` literal straight out of the owner file.

    Parsed from source rather than imported: ``ItemDatabase/app.py`` is a
    46k-line module that builds Qt objects on import.
    """
    source = _APP_PY.read_text(encoding="utf-8")
    match = re.search(rf"^{name}\s*=\s*\{{(.*?)^\}}", source, flags=re.S | re.M)
    assert match, f"{name} not found in {_APP_PY}"
    return dict(re.findall(r'"([^"]+)"\s*:\s*"(#[0-9a-fA-F]{6})"', match.group(1)))


@pytest.mark.skipif(not _APP_PY.is_file(), reason="ItemDatabase not present")
@pytest.mark.parametrize("kind,owner_table", [("item_grade", "GRADE_COLORS"), ("gear_type", "GEAR_TYPE_COLORS")])
def test_data_color_mirrors_item_database(kind, owner_table):
    """Detects drift: ItemDatabase/app.py still owns these tables."""
    owner = _dict_literal_from_app_py(owner_table)
    assert owner, f"{owner_table} parsed empty"
    mirrored = {key: theme.data_color(kind, key) for key in theme.data_color_keys(kind)}
    assert mirrored == owner


_OVERLAY_PY = theme.TEMPLATE_PATH.parent / "overlay" / "overlay_window.py"
_TIMER_DIALOG_PY = theme.TEMPLATE_PATH.parent / "custom_timer_dialog.py"


@pytest.mark.skipif(not _OVERLAY_PY.is_file(), reason="overlay module not present")
def test_the_overlay_reads_timer_colors_from_here():
    """Ownership inverted on 2026-09-18.

    ``ui/overlay/overlay_window.py`` used to OWN ``TIMER_COLORS`` as
    ``QColor(r, g, b)`` literals and this module mirrored them, so the test
    checked the mirror for drift.  The literals are gone from ``ui/`` (see
    tests/test_no_hex_literals_in_ui.py), core/theme.py is the owner, and
    what needs pinning now is that the overlay still resolves the same four
    built-in timers plus the custom fallback through it.
    """
    from ui.overlay import overlay_window

    for key in ("daily", "weekly", "shugo", "rift"):
        assert overlay_window.timer_color(key).name() == theme.data_color("timer", key), key
    assert overlay_window.DEFAULT_CUSTOM_TIMER_COLOR == theme.data_color("timer", "custom")

    source = _OVERLAY_PY.read_text(encoding="utf-8")
    assert "QColor(59," not in source and "QColor(59 " not in source, "a colour literal came back"


@pytest.mark.skipif(not _TIMER_DIALOG_PY.is_file(), reason="timer dialog not present")
def test_the_timer_dialog_builds_its_swatches_from_here():
    """Same inversion: the dialog's 8 swatches are now a view of the table.

    Order matters — the grid lays them out 4 × 2 and the user learns
    positions — so this pins the sequence, not just the set.
    """
    from ui import custom_timer_dialog

    expected = [
        (theme.data_color("timer_swatch", key), f"ct_color_{key}")
        for key in theme.data_color_keys("timer_swatch")
    ]
    assert custom_timer_dialog.CUSTOM_TIMER_COLORS == expected
    assert len(expected) == 8
    assert custom_timer_dialog.DEFAULT_TIMER_COLOR == expected[0][0]


def test_data_color_unknown_key_is_muted_not_an_error():
    assert theme.data_color("item_grade", "Mythic++") == theme.ABYSS.fg_muted


def test_data_color_unknown_kind_raises():
    with pytest.raises(KeyError):
        theme.data_color("mood", "happy")


def test_data_color_keys_are_stable():
    assert theme.data_color_keys("timer") == ("daily", "weekly", "shugo", "rift", "custom")
    assert len(theme.data_color_keys("timer_swatch")) == 8


@pytest.mark.parametrize("kind", ["item_grade", "gear_type", "timer", "timer_swatch"])
def test_every_data_color_parses(kind):
    for key in theme.data_color_keys(kind):
        assert theme.parse_color(theme.data_color(kind, key))


# --------------------------------------------------------------------------
# The template still styles everything the app relies on
# --------------------------------------------------------------------------

#: Snapshot of every selector the deleted ``ui/styles.qss`` carried.  The
#: guarantee has to outlive the file it was taken from, so it lives in a
#: fixture rather than being diffed against a sheet that no longer exists.
_LEGACY_SELECTORS_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "legacy_selectors.txt"


def _selectors(text: str) -> set[str]:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    found = set()
    for match in re.finditer(r"([^{}]+)\{", text):
        for part in match.group(1).split(","):
            cleaned = " ".join(part.split())
            if cleaned:
                found.add(cleaned)
    return found


def _legacy_selector_snapshot() -> set[str]:
    """Read the fixture.  A comment is ``"# "`` — with the space, because
    almost every line in the file is an ``#objectName`` selector."""
    lines = _LEGACY_SELECTORS_FIXTURE.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("# ")}


def test_template_keeps_every_legacy_selector():
    """Porting must not silently drop a widget's styling."""
    legacy = _legacy_selector_snapshot()
    assert len(legacy) > 300, "the snapshot itself looks truncated"
    ported = _selectors(theme.TEMPLATE_PATH.read_text(encoding="utf-8"))
    missing = sorted(legacy - ported)
    assert not missing, f"selectors lost in the port: {missing}"


def test_the_legacy_stylesheet_is_gone():
    """MASTER §4-2: one sheet, generated.  A reappearing styles.qss means
    two sources of truth and the [theme=…] duplication coming back."""
    assert not (theme.TEMPLATE_PATH.parent / "styles.qss").exists()


def test_template_styles_the_object_names_added_this_wave():
    """Empty state + toast + focusable card, i.e. what the old QSS lacked."""
    ported = _selectors(theme.TEMPLATE_PATH.read_text(encoding="utf-8"))
    for selector in ("#emptyState", "#emptyStateTitle", "#emptyStateHint", "#toastBar", "#taskCard:focus"):
        assert selector in ported


# --------------------------------------------------------------------------
# current() — the accessor painters use instead of plumbing (MASTER §4-3)
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_current_theme():
    """set_current() is process-wide state; don't leak it into other tests."""
    before = theme.current()
    yield
    theme.set_current(before)


def test_current_defaults_to_the_default_theme():
    assert theme.current() == theme.DEFAULT_THEME
    assert theme.current_tokens() is theme.THEMES[theme.DEFAULT_THEME]


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_set_current_round_trips(name):
    assert theme.set_current(name) == name
    assert theme.current() == name
    assert theme.current_tokens() is theme.THEMES[name]


def test_set_current_normalises_instead_of_storing_garbage(caplog):
    """A profile from a future version must not leave current() unusable."""
    with caplog.at_level("WARNING"):
        stored = theme.set_current("chartreuse")
    assert stored == theme.DEFAULT_THEME
    assert theme.current() == theme.DEFAULT_THEME


def test_set_current_is_case_insensitive():
    theme.set_current("  VOID ")
    assert theme.current() == "void"


# --------------------------------------------------------------------------
# build_palette — the Fusion fallback, from the tokens
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_build_palette_follows_the_theme(qapp, name):
    from PySide6.QtGui import QPalette

    tokens = theme.THEMES[name]
    palette = theme.build_palette(name)

    assert palette.color(QPalette.Window) == theme.qcolor(tokens, "bg.surface")
    assert palette.color(QPalette.Base) == theme.qcolor(tokens, "bg.input")
    assert palette.color(QPalette.AlternateBase) == theme.qcolor(tokens, "bg.elevated")
    assert palette.color(QPalette.Text) == theme.qcolor(tokens, "fg")
    assert palette.color(QPalette.Highlight) == theme.qcolor(tokens, "accent")


def test_build_palette_accepts_tokens_or_a_name(qapp):
    assert theme.build_palette(theme.THEMES["void"]) == theme.build_palette("void")


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_palette_highlight_text_is_never_white_on_the_accent(qapp, name):
    """Audit D/C3's regression, at the palette level this time.

    QPalette::HighlightedText is what Qt paints over a selection, and Fusion's
    own default for it is white -- which on Abyss's cyan accent is 1.81:1.
    """
    from PySide6.QtGui import QPalette

    palette = theme.build_palette(name)
    tokens = theme.THEMES[name]
    assert palette.color(QPalette.HighlightedText) == theme.qcolor(tokens, "fg.on_accent")
    ratio = theme.contrast_ratio(tokens.fg_on_accent, tokens.accent)
    assert ratio >= 4.5, f"{name}: {ratio:.2f}:1"


def test_palette_placeholder_is_the_muted_foreground(qapp):
    """Qt paints placeholders from the palette, not from the QSS (audit D/C3)."""
    from PySide6.QtGui import QPalette

    palette = theme.build_palette("abyss")
    assert palette.color(QPalette.PlaceholderText) == theme.qcolor(theme.ABYSS, "fg.muted")
    assert theme.contrast_ratio(theme.ABYSS.fg_muted, theme.ABYSS.bg_input) >= 4.5


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_palette_has_no_light_role_left(qapp, name):
    """Every one of the six themes is dark; a light role means Fusion's own
    (OS-following) default leaked through — the 2026-08-29 bug."""
    from PySide6.QtGui import QPalette

    palette = theme.build_palette(name)
    for role in (QPalette.Window, QPalette.Base, QPalette.AlternateBase, QPalette.Button):
        luminance = theme._relative_luminance(
            (palette.color(role).red(), palette.color(role).green(), palette.color(role).blue())
        )
        assert luminance < 0.2, f"{name}: {role} is light ({luminance:.3f})"


# --------------------------------------------------------------------------
# Theme decisions recorded in MASTER on 2026-09-18
# --------------------------------------------------------------------------


def test_emerald_accent_and_secondary_are_not_more_greens():
    """Accent, ok and secondary were a green, a green and a lime.

    Hue distance, not a hardcoded hex, so a later re-tune still has to keep
    the three apart.
    """
    tokens = theme.THEMES["emerald"]
    accent_hue = theme.QColor(tokens.accent).hue()
    ok_hue = theme.QColor(tokens.ok).hue()
    secondary_hue = theme.QColor(tokens.secondary).hue()

    def apart(first, second):
        delta = abs(first - second) % 360
        return min(delta, 360 - delta)

    assert apart(accent_hue, ok_hue) >= 25, "accent still reads as the ok green"
    assert apart(secondary_hue, ok_hue) >= 60, "secondary still reads as a green"


def test_inferno_accent_is_distinguishable_from_warn():
    tokens = theme.THEMES["inferno"]
    accent_hue = theme.QColor(tokens.accent).hue()
    warn_hue = theme.QColor(tokens.warn).hue()
    assert abs(accent_hue - warn_hue) >= 12, "accent and warn are the same orange"


@pytest.mark.parametrize("name", sorted(set(theme.THEMES) - {"abyss"}))
def test_every_theme_brings_its_own_borders(name):
    """MASTER §2 (2026-09-18): a border belongs to its theme's bg family.

    Inherited from Abyss they were a navy line on an Inferno-red surface.
    """
    tokens = theme.THEMES[name]
    assert tokens.border != theme.ABYSS.border, f"{name} still uses Abyss's border"
    assert tokens.border_strong != theme.ABYSS.border_strong


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_borders_sit_between_the_surfaces_and_the_text(name):
    """A border has to be visible against the card it outlines, and must not
    be mistaken for text."""
    tokens = theme.THEMES[name]
    surface = theme._relative_luminance(theme.parse_color(tokens.bg_elevated)[:3])
    border = theme._relative_luminance(theme.parse_color(tokens.border)[:3])
    strong = theme._relative_luminance(theme.parse_color(tokens.border_strong)[:3])
    muted = theme._relative_luminance(theme.parse_color(tokens.fg_muted)[:3])
    assert surface < border < strong < muted, (
        f"{name}: surface {surface:.3f} border {border:.3f} "
        f"strong {strong:.3f} muted {muted:.3f}"
    )


# --------------------------------------------------------------------------
# MASTER §2 focus.ring — and the specificity trap that hid it
# --------------------------------------------------------------------------


def test_the_focus_ring_is_an_outline_not_a_border():
    """Regression guard on a real, verified defect (2026-09-18).

    Qt resolves stylesheet conflicts by CSS2 specificity: `#objectName`
    scores 100, `QPushButton:focus` scores 11.  While the ring was declared
    as a `border`, all 157 `#objectName` rules in the template that declare
    a border outranked it, and a focused button/pill/field/combo showed no
    ring at all.  `outline` is set by nothing else, so it cannot lose —
    switching the property back to `border` would silently un-do keyboard
    accessibility everywhere.
    """
    # The RENDERED sheet, not the template: `{{token}}` placeholders are
    # themselves braces and would break any rule-level parse of the source.
    rendered = _without_comments(theme.build_qss("abyss"))
    focus_rules = re.findall(r"([^{}]*:focus[^{}]*)\{([^{}]*)\}", rendered)
    assert focus_rules, "the template declares no :focus rule at all"
    for selector, body in focus_rules:
        # The `border` SHORTHAND is what loses to an #id rule -- and it also
        # changes the width, which nudges the widget's row.  `border-color`
        # is fine (a focused field tinting its own 1 px edge, MASTER §3).
        assert not re.search(r"(^|;|\s)border\s*:", body), (
            f"focus rule declares a border, which every #id rule outranks: {selector.strip()}"
        )
        assert "outline" in body or "border-color" in body, (
            f"focus rule indicates nothing: {selector.strip()} {{{body}}}"
        )

    outlined = [selector for selector, body in focus_rules if "outline" in body]
    assert len(outlined) >= 4, "the ring itself is gone, only field tints are left"


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_the_focus_ring_uses_the_theme_accent_and_master_geometry(name):
    qss = theme.build_qss(name)
    tokens = theme.THEMES[name]
    expected = f"outline: {tokens.focus_ring_width}px solid {tokens.focus_ring}"
    assert expected in qss, f"{name}: no '{expected}' in the rendered sheet"
    assert f"outline-offset: {tokens.focus_ring_offset}px" in qss
