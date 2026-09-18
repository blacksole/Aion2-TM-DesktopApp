"""core/theme.py + ui/styles.template.qss — token system invariants."""

import ast
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


def test_the_item_database_drift_gate_can_actually_run():
    """The gate below used to carry a skipif, so it vanished silently rather
    than failing when ItemDatabase/ was absent (review F-14)."""
    assert _APP_PY.is_file(), (
        f"{_APP_PY} is gone — it is the consumer this module's data tables "
        f"exist for; re-point the gate below before deleting it"
    )


#: Tables that used to live in ``ItemDatabase/app.py`` as literals, with
#: ``core/theme.py`` mirroring them.  The Armory tokenization wave
#: (2026-09-18) inverted that: this module OWNS them, and app.py binds the
#: same names to these objects at import.  So the drift gate inverted too —
#: there is nothing to compare, and the thing to check is that no second
#: copy has reappeared.
_OWNED_TABLES = ("GRADE_COLORS", "GEAR_TYPE_COLORS", "SKILL_TYPE_COLORS",
                 "ARCANA_THEME_COLORS", "GENIUS_BOARD_COLORS", "ROLE_COLORS")


@pytest.mark.parametrize("name", _OWNED_TABLES)
def test_no_second_copy_of_a_data_table_in_the_armory(name):
    """A re-appearing literal table is the drift this used to detect.

    Parsed from source rather than imported: ``ItemDatabase/app.py`` is a
    23k-line module that builds Qt objects on import.
    """
    source = _APP_PY.read_text(encoding="utf-8")
    literal = re.search(rf"^_?{name}\s*=\s*\{{\s*\n?\s*\"", source, flags=re.M)
    assert not literal, (
        f"ItemDatabase/app.py declares its own {name} again — core/theme.py "
        f"is the owner; bind the name to it instead of copying the values"
    )


#: Module-level name in ``ItemDatabase/app.py`` → the table here it must be
#: bound to.  The absence gate above proves no second literal exists; this
#: proves the name actually points at ours (review G, M5: only two of the
#: six had the binding half asserted).
_ARMORY_BINDINGS = {
    "GRADE_COLORS": "GRADE_COLORS",
    "GEAR_TYPE_COLORS": "GEAR_TYPE_COLORS",
    "_SKILL_TYPE_COLORS": "SKILL_TYPE_COLORS",
    "_METHOD_COLORS": "CRAFT_METHOD_COLORS",
    "_ARCANA_THEME_COLORS": "ARCANA_THEME_COLORS",
    "ARCANA_CATEGORY_COLORS": "ARCANA_CATEGORY_COLORS",
    "_GENIUS_BOARD_COLORS": "GENIUS_BOARD_COLORS",
}


def test_the_armory_reads_the_data_tables_from_here():
    """The other half: the Armory must actually be wired to this module."""
    source = _APP_PY.read_text(encoding="utf-8")
    assert "from core import theme as _theme" in source
    for armory_name, owner_name in _ARMORY_BINDINGS.items():
        assert f"{armory_name} = _theme.{owner_name}" in source, (
            f"{armory_name} is not bound from core.theme.{owner_name}"
        )
        assert hasattr(theme, owner_name), f"core.theme lost {owner_name}"
    for kind in ("item_grade", "skill_type", "arcana_theme", "genius_board"):
        assert f'"{kind}"' in source, f"nothing in the Armory asks for {kind} colours"


def _armory_fallback_tokens() -> dict[str, str]:
    """``ItemDatabase/app.py``'s ``_FALLBACK_TOKENS``, read from source.

    Parsed, not imported: that module builds Qt objects at import time and
    this test has no QApplication (and should not need one to compare two
    tables of strings).
    """
    tree = ast.parse(_APP_PY.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(getattr(t, "id", None) == "_FALLBACK_TOKENS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("_FALLBACK_TOKENS not found at module level in ItemDatabase/app.py")


def test_the_armory_fallback_table_parses_and_is_small():
    table = _armory_fallback_tokens()
    assert 20 <= len(table) <= 40, (
        f"_FALLBACK_TOKENS has {len(table)} entries — it is meant to stay the "
        f"tiny last-resort mirror the literal baseline justifies, not a palette"
    )


@pytest.mark.parametrize("key", sorted(_armory_fallback_tokens()))
def test_the_armory_fallback_table_still_matches_abyss(key):
    """Review G (M5): a mirror without a comparison is a comment.

    ``_FALLBACK_TOKENS`` is a second copy of MASTER §2 Abyss, kept for the
    build that cannot import this module at all.  MASTER's "Statut"
    paragraph and ``tests/fixtures/itemdatabase_literal_baseline.txt`` both
    justify the Armory's 18 remaining hex literals by asserting that they
    ARE the Abyss values — an equality nothing checked.  It holds today;
    without this it would hold only until someone tuned a token.
    """
    assert hasattr(theme.ABYSS, key), (
        f"_FALLBACK_TOKENS defines {key!r}, which is not a token of this module"
    )
    assert _armory_fallback_tokens()[key] == str(getattr(theme.ABYSS, key)), (
        f"the Armory's fallback {key} has drifted from Abyss"
    )


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


#: The prefix every rule in the template carries so the application sheet
#: cannot reach the Armory's own windows — see tests/test_app_sheet_isolation.py.
_SCOPE = 'QWidget[aion2="true"]'


def test_template_keeps_every_legacy_selector():
    """Porting must not silently drop a widget's styling.

    The scope prefix is stripped before comparing: a legacy `#taskCard` is
    still styled when the template says `QWidget[aion2="true"] #taskCard`,
    and requiring the snapshot to grow the prefix too would only pin the
    prefix twice (test_app_sheet_isolation already owns that).
    """
    legacy = _legacy_selector_snapshot()
    assert len(legacy) > 300, "the snapshot itself looks truncated"
    ported = {
        selector.replace(_SCOPE + " ", "").strip()
        for selector in _selectors(theme.TEMPLATE_PATH.read_text(encoding="utf-8"))
    }
    missing = sorted(legacy - ported)
    assert not missing, f"selectors lost in the port: {missing}"


def test_the_legacy_stylesheet_is_gone():
    """MASTER §4-2: one sheet, generated.  A reappearing styles.qss means
    two sources of truth and the [theme=…] duplication coming back."""
    assert not (theme.TEMPLATE_PATH.parent / "styles.qss").exists()


def test_template_styles_the_object_names_added_this_wave():
    """Empty state + toast + focusable card, i.e. what the old QSS lacked."""
    ported = {
        selector.replace(_SCOPE + " ", "").strip()
        for selector in _selectors(theme.TEMPLATE_PATH.read_text(encoding="utf-8"))
    }
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


def test_the_focus_ring_is_a_border_at_id_specificity():
    """Regression guard on two defects, in the order they were found.

    First the ring was a `border` on type selectors (`QPushButton:focus`),
    which Qt scores at 11 while an `#objectName` rule scores 100 — and 157
    `#objectName` rules in this template declare a border, so the ring never
    appeared.  Then it was an `outline`, which no other rule sets and so
    cannot lose the cascade — but Qt cannot paint outside a widget's rect:
    `outline` on a QWidget only recolours Fusion's PE_FrameFocusRect, drawn
    around the *label* sub-rect INSIDE the control, through the text
    (review F-4, visible in shots/aether/app_focus_ring_detail.png).

    Both of those are excluded now: the ring is a border, declared at ID
    specificity, and the type-level rules only turn Fusion's own rect off.
    """
    rendered = _without_comments(theme.build_qss("abyss"))
    focus_rules = re.findall(r"([^{}]*:focus[^{}]*)\{([^{}]*)\}", rendered)
    assert focus_rules, "the template declares no :focus rule at all"

    id_rules = []
    for selector, body in focus_rules:
        if not re.search(r"(^|;|\s)border\s*:", body):
            # A `border-color`-only rule is a tint, not the ring: it changes
            # no geometry and losing it to an #id rule costs nothing (the
            # #id rules carry their own tint).  MASTER §3's "Champ: focus
            # accent" is expressed that way on the bare input types.
            continue
        entries = [s.strip() for s in selector.split(",") if s.strip()]
        # The RING itself must be ID- or sub-control-scoped: on a bare type
        # selector it would lose to any #id border rule and never paint.
        for entry in entries:
            assert "#" in entry or "::" in entry, (
                f"focus ring on a bare type selector, which #id rules outrank: {entry}"
            )
        id_rules.append(selector)

    assert len(id_rules) >= 8, f"only {len(id_rules)} ring rules left"
    assert "outline: none" in rendered, (
        "Fusion's own PE_FrameFocusRect is not suppressed, so the control "
        "will show both its rect and ours"
    )


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_the_focus_ring_uses_the_theme_accent_and_compensates_its_width(name):
    qss = theme.build_qss(name)
    tokens = theme.THEMES[name]
    expected = f"border: {tokens.focus_ring_width}px solid {tokens.focus_ring}"
    assert expected in qss, f"{name}: no '{expected}' in the rendered sheet"
    # The pixel the wider border takes has to be given back as padding, or
    # focusing a control grows it and nudges its row.
    assert f"padding: {tokens.space_2_inset}px {tokens.space_3_inset}px" in qss
    assert tokens.focus_inset == tokens.focus_ring_width - tokens.border_width
    # An accent ring on an accent fill is invisible (review F-9).
    assert f"border: {tokens.focus_ring_width}px solid {tokens.fg_on_accent}" in qss


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_the_inset_tokens_give_back_exactly_the_added_border(name):
    tokens = theme.THEMES[name]
    for scale in (1, 2, 3, 4, 6):
        base = getattr(tokens, f"space_{scale}")
        inset = getattr(tokens, f"space_{scale}_inset")
        assert inset == base - tokens.focus_inset, scale
        assert inset >= 0


# --------------------------------------------------------------------------
# Resource resolution — review F-11
# --------------------------------------------------------------------------


def test_the_template_is_resolved_through_app_root_at_read_time(monkeypatch, tmp_path):
    """The point of routing through ``utils.paths.app_root()``: a frozen
    layout becomes expressible in a test.

    Before, the path was ``Path(core/theme.py).parent.parent`` computed at
    import — correct inside a PyInstaller bundle only by coincidence, and
    impossible to exercise.
    """
    import utils.paths as paths

    fake_root = tmp_path / "meipass"
    (fake_root / "ui").mkdir(parents=True)
    (fake_root / "ui" / "styles.template.qss").write_text(
        "QWidget { color: {{fg}}; }", encoding="utf-8"
    )
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(fake_root), raising=False)

    assert theme.template_path() == fake_root / "ui" / "styles.template.qss"
    assert theme.build_qss("abyss") == f"QWidget {{ color: {theme.ABYSS.fg}; }}"


def test_a_missing_template_names_the_path_it_tried(monkeypatch, tmp_path):
    """It used to surface as a bare FileNotFoundError from inside
    MainWindow.__init__, with no hint about bundling."""
    import utils.paths as paths

    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(tmp_path / "nowhere"), raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        theme.build_qss("abyss")
    message = str(excinfo.value)
    assert "styles.template.qss" in message
    assert "nowhere" in message
    assert "spec datas" in message


# --------------------------------------------------------------------------
# Fonts — review F-11b
# --------------------------------------------------------------------------


def test_the_qss_names_the_family_qt_actually_registered():
    """``load_fonts()`` resolves what Qt REALLY loaded (including its
    "trust Qt, not the spec" branch for a renamed upstream release).  That
    answer was being discarded, so the branch was dead with respect to the
    stylesheet: the QSS still asked for "Barlow" by name and Qt silently
    dropped a name it did not know."""
    try:
        theme.set_font_families({"body": "Barlow Renamed 2.0", "mono": "", "display": ""})
        stack = theme.font_stack(theme.ABYSS, "body")
        assert stack.startswith('"Barlow Renamed 2.0"'), stack
        # The declared stack survives behind it as the fallback chain.
        assert stack.endswith("sans-serif")
        assert '"Barlow"' in stack
        assert '"Barlow Renamed 2.0"' in theme.build_qss("abyss")

        # An unresolved role falls back to the token's own stack untouched.
        assert theme.font_stack(theme.ABYSS, "mono") == theme.ABYSS.font_mono
    finally:
        theme.set_font_families({})
    assert theme.font_stack(theme.ABYSS, "body") == theme.ABYSS.font_body
