"""core/theme.py + ui/styles.template.qss — token system invariants."""

import dataclasses
import re

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
def test_timer_colors_mirror_the_overlay_module():
    """``TIMER_COLORS`` there is QColor(r, g, b); here it is hex."""
    source = _OVERLAY_PY.read_text(encoding="utf-8")
    block = re.search(r"^TIMER_COLORS\s*=\s*\{(.*?)^\}", source, flags=re.S | re.M)
    assert block, "TIMER_COLORS not found"
    owner = {
        key: "#%02x%02x%02x" % (int(red), int(green), int(blue))
        for key, red, green, blue in re.findall(
            r'"(\w+)"\s*:\s*QColor\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', block.group(1)
        )
    }
    assert owner, "TIMER_COLORS parsed empty"
    for key, hex_value in owner.items():
        assert theme.data_color("timer", key) == hex_value, key

    custom = re.search(r"^CUSTOM_TIMER_COLOR\s*=\s*QColor\(\s*(\d+),\s*(\d+),\s*(\d+)\s*\)", source, flags=re.M)
    assert custom, "CUSTOM_TIMER_COLOR not found"
    expected = "#%02x%02x%02x" % tuple(int(group) for group in custom.groups())
    assert theme.data_color("timer", "custom") == expected


@pytest.mark.skipif(not _TIMER_DIALOG_PY.is_file(), reason="timer dialog not present")
def test_timer_swatches_mirror_the_dialog_palette():
    source = _TIMER_DIALOG_PY.read_text(encoding="utf-8")
    block = re.search(r"^CUSTOM_TIMER_COLORS\s*=\s*\[(.*?)^\]", source, flags=re.S | re.M)
    assert block, "CUSTOM_TIMER_COLORS not found"
    owner = {
        name: hex_value
        for hex_value, name in re.findall(r'\(\s*"(#[0-9a-fA-F]{6})"\s*,\s*"ct_color_(\w+)"\s*\)', block.group(1))
    }
    assert owner, "CUSTOM_TIMER_COLORS parsed empty"
    mirrored = {key: theme.data_color("timer_swatch", key) for key in theme.data_color_keys("timer_swatch")}
    assert mirrored == owner


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

_LEGACY_QSS = theme.TEMPLATE_PATH.parent / "styles.qss"


def _selectors(text: str) -> set[str]:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    found = set()
    for match in re.finditer(r"([^{}]+)\{", text):
        for part in match.group(1).split(","):
            cleaned = " ".join(part.split())
            if cleaned:
                found.add(cleaned)
    return found


@pytest.mark.skipif(not _LEGACY_QSS.is_file(), reason="legacy stylesheet already removed")
def test_template_keeps_every_legacy_selector():
    """Porting must not silently drop a widget's styling."""
    legacy = {s for s in _selectors(_LEGACY_QSS.read_text(encoding="utf-8")) if "[theme=" not in s}
    ported = _selectors(theme.TEMPLATE_PATH.read_text(encoding="utf-8"))
    missing = sorted(legacy - ported)
    assert not missing, f"selectors lost in the port: {missing}"


def test_template_styles_the_object_names_added_this_wave():
    """Empty state + toast + focusable card, i.e. what the old QSS lacked."""
    ported = _selectors(theme.TEMPLATE_PATH.read_text(encoding="utf-8"))
    for selector in ("#emptyState", "#emptyStateTitle", "#emptyStateHint", "#toastBar", "#taskCard:focus"):
        assert selector in ported
