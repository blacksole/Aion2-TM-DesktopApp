"""MASTER §3, « Icônes » — the gates that keep the icon wave from rotting.

Four separate promises, each with its own failure mode, each gated here:

* **the set is complete** — a name a widget asks for exists as a file, in
  the repo *and* in the bundle.  ``ui/widgets/icons.py`` raises on a typo,
  but it raises at *paint* time in a dialog nobody opens in CI; this scans
  the source instead so the typo fails on the next run.
* **the set is tintable** — a Lucide SVG is only theme-able because it says
  ``currentColor``.  A hand-edited file that lost it would render black on
  black and nothing else would notice.
* **the arrows are per theme** — 6 × 4 committed chevrons that must still
  equal what ``scripts/gen_tinted_icons.py`` produces from today's tokens.
  This is the gate the deferred MASTER row asked for: the orange PNGs were
  wrong *because* one bitmap served six themes.
* **no emoji came back** — ``aucun emoji comme icône``.  The scan carries an
  allow-list, and every entry in it names a reason.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from PySide6.QtGui import QColor

from core import theme
from ui.widgets import icons

REPO = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
EMOJI_ALLOWLIST = FIXTURES / "icon_emoji_allowlist.txt"

#: Files this change owns; the emoji scan is clean here and nowhere else
#: (``ui/main_window.py``, ``core/translations.py`` and the Armory belong to
#: other owners — their remaining glyphs are listed in the allow-list with
#: the reason and the owner).
OWNED = (
    "ui/widgets/icons.py",
    "ui/widgets/empty_state.py",
    "ui/widgets/sidebar_widget.py",
    "ui/widgets/header_widget.py",
    "ui/widgets/template_dialog.py",
    "ui/widgets/shopping_card.py",
    "ui/pages/tasks_page.py",
    "ui/pages/settings_page.py",
    "ui/pages/about_page.py",
    "ui/pages/timers_page.py",
    "ui/overlay/overlay_window.py",
    "ui/custom_timer_dialog.py",
    "ui/custom_timer_manager_dialog.py",
) + tuple(
    p.relative_to(REPO).as_posix() for p in sorted((REPO / "ui" / "flow").rglob("*.py"))
)


# ---------------------------------------------------------------------------
# the vendored set
# ---------------------------------------------------------------------------

def _vendored() -> list[Path]:
    return sorted(icons.icon_dir().glob("*.svg"))


def test_the_set_is_vendored_with_its_licence():
    assert _vendored(), "no Lucide SVG found — assets/icons/lucide is empty"
    licence = icons.icon_dir() / "LICENSE"
    assert licence.is_file(), "the ISC licence must ship with the icons"
    assert "ISC License" in licence.read_text(encoding="utf-8")
    sources = icons.icon_dir() / "SOURCES.md"
    assert sources.is_file()
    assert "1.47.0" in sources.read_text(encoding="utf-8"), "the pinned tag must be named"


def test_the_set_stays_small():
    """A full Lucide checkout is 1848 icons; the exe ships what it uses."""
    files = _vendored()
    assert len(files) <= 60, f"{len(files)} icons vendored — prune or justify"
    total = sum(p.stat().st_size for p in files)
    assert total < 150_000, f"{total} bytes of SVG — too much for a subset"


@pytest.mark.parametrize("path", _vendored(), ids=lambda p: p.stem)
def test_every_icon_is_tintable(path: Path):
    """No ``currentColor``, no theming — ui/widgets/icons.py tints by text."""
    assert icons.CURRENT_COLOR in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# every name the code asks for exists
# ---------------------------------------------------------------------------

def _icon_call_sites() -> list[tuple[str, int, str, int | None]]:
    """``(file, line, icon name, size)`` for every icons.* call in ui/."""
    found: list[tuple[str, int, str, int | None]] = []
    for path in sorted((REPO / "ui").rglob("*.py")):
        if path.name == "icons.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(REPO).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name not in ("set_icon", "IconLabel", "icon", "pixmap"):
                continue
            args = list(node.args)
            if name == "set_icon" and args and not isinstance(args[0], ast.Constant):
                args = args[1:]  # icons.set_icon(widget, "name", size)
            if not args or not isinstance(args[0], ast.Constant):
                continue
            if not isinstance(args[0].value, str):
                continue
            size = None
            if len(args) > 1 and isinstance(args[1], ast.Constant):
                size = args[1].value if isinstance(args[1].value, int) else None
            found.append((rel, node.lineno, args[0].value, size))
    return found


def test_the_scan_finds_the_call_sites():
    """Guard the guard: an AST walk that silently matches nothing passes."""
    assert len(_icon_call_sites()) >= 15


def test_every_referenced_icon_exists():
    missing = [
        f"{rel}:{line} -> {name!r}"
        for rel, line, name, _ in _icon_call_sites()
        if name and name not in icons.available()
    ]
    assert not missing, "icon name with no file:\n  " + "\n  ".join(missing)


def test_every_widget_icon_uses_a_master_size():
    """MASTER §3: 16 / 20 / 24 px, nothing else on a widget.

    ``icons.pixmap`` is exempt: a painter draws at the scale of what it is
    drawing (the Flow guide's check follows the node dot's zoom).
    """
    bad = [
        f"{rel}:{line} -> {name} at {size}px"
        for rel, line, name, size in _icon_call_sites()
        if size is not None and size not in icons.SIZES
    ]
    assert not bad, "size outside MASTER's 16/20/24:\n  " + "\n  ".join(bad)


# ---------------------------------------------------------------------------
# the per-theme arrows
# ---------------------------------------------------------------------------

def _stroke_of(path: Path) -> str:
    match = re.search(r'stroke="(#[0-9a-fA-F]{6})"', path.read_text(encoding="utf-8"))
    assert match, f"{path} has no literal stroke colour"
    return match.group(1).lower()


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_every_theme_has_its_tinted_chevrons(name):
    from scripts.gen_tinted_icons import (
        ARROW_HOVER_TOKEN,
        ARROW_TOKEN,
        CHEVRONS,
        HOVER_SUFFIX,
    )

    for token, suffix in ((ARROW_TOKEN, ""), (ARROW_HOVER_TOKEN, HOVER_SUFFIX)):
        expected = theme.qcolor(theme.tokens(name), token).name().lower()
        for chevron in CHEVRONS:
            path = icons.tinted_dir() / name / f"{chevron}{suffix}.svg"
            assert path.is_file(), f"missing tinted arrow: {path}"
            assert _stroke_of(path) == expected, (
                f"{path} is stroked {_stroke_of(path)}, but {name}'s "
                f"{token} is {expected} — re-run scripts/gen_tinted_icons.py"
            )
            assert icons.CURRENT_COLOR not in path.read_text(encoding="utf-8")


def test_the_hovered_arrow_is_actually_different_per_theme():
    """Otherwise the per-theme folders would be six copies of one file.

    ``fg.muted`` is not theme-overridable (MASTER §2), so the RESTING
    chevron is deliberately identical everywhere; the hovered one is the
    accent, and the accent is what a theme is.
    """
    from scripts.gen_tinted_icons import HOVER_SUFFIX

    strokes = {
        name: _stroke_of(icons.tinted_dir() / name / f"chevron-down{HOVER_SUFFIX}.svg")
        for name in theme.THEMES
    }
    assert len(set(strokes.values())) == len(theme.THEMES), (
        f"two themes share a hovered arrow colour: {strokes}"
    )


def test_the_committed_arrows_equal_what_the_generator_produces(tmp_path):
    """The committed files are a build artefact; this is their CI rebuild."""
    from scripts.gen_tinted_icons import generate

    for produced in generate(tmp_path):
        committed = icons.tinted_dir() / produced.relative_to(tmp_path)
        assert committed.is_file(), f"generator produced an uncommitted {committed}"
        assert committed.read_text(encoding="utf-8") == produced.read_text(
            encoding="utf-8"
        ), f"{committed} is stale — re-run scripts/gen_tinted_icons.py"


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_the_sheet_points_at_an_arrow_that_exists(name):
    """The QSS url() is a *path*: a wrong one draws nothing, silently."""
    qss = theme.build_qss(name, asset_path=REPO.as_posix())
    urls = re.findall(r"url\(([^)]+chevron[^)]*)\)", qss)
    assert urls, f"{name}: the sheet draws no chevron at all"
    for url in urls:
        assert Path(url).is_file(), f"{name}: sheet points at a missing {url}"


def test_no_arrow_rule_puts_its_pseudo_state_on_the_widget():
    """``#combo:hover::down-arrow`` makes Qt draw the image TWICE.

    Both forms parse.  The widget-level one (`:hover::down-arrow`) adds a
    second, unsized and unpositioned draw of the same image, landing on top
    of the combo's own text as a half-clipped chevron that reads as a stray
    "✓" — in every theme, with no hover involved.  The subcontrol-level form
    (`::down-arrow:hover`) is correct.  Caught in a grab, not by a name, so
    it gets a gate rather than a comment.
    """
    offenders: list[str] = []
    for template in (
        REPO / "ui" / "styles.template.qss",
        REPO / "ItemDatabase" / "styles.template.qss",
    ):
        text = re.sub(r"/\*.*?\*/", "", template.read_text(encoding="utf-8"), flags=re.S)
        for number, line in enumerate(text.splitlines(), 1):
            if re.search(r":[a-z-]+::(?:down|up)-arrow", line):
                offenders.append(
                    f"{template.relative_to(REPO).as_posix()}:{number}: {line.strip()}"
                )
    assert not offenders, (
        "put the pseudo-state on the subcontrol (`::down-arrow:hover`):\n  "
        + "\n  ".join(offenders)
    )


def test_the_orange_png_arrows_are_gone():
    """The deferred MASTER row, closed: one bitmap cannot serve six themes."""
    for stale in ("arrow_down_orange.png", "arrow_up_orange.png"):
        assert not (REPO / "assets" / "icons" / stale).exists(), f"{stale} is back"

    offenders: list[str] = []
    for path in list((REPO / "ui").rglob("*.py")) + [
        REPO / "ui" / "styles.template.qss",
        REPO / "ItemDatabase" / "styles.template.qss",
        REPO / "Aion2 TM.spec",
    ]:
        text = path.read_text(encoding="utf-8")
        # Comments may name the old asset -- both sheets explain in place
        # why the arrows stopped being a bitmap.  Only a live reference
        # counts, so strip QSS block comments and Python line comments.
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
        if "orange.png" in text:
            offenders.append(path.relative_to(REPO).as_posix())
    assert not offenders, f"still referencing the orange arrows: {offenders}"


# ---------------------------------------------------------------------------
# packaging
# ---------------------------------------------------------------------------

def test_the_spec_ships_the_icons_and_keeps_qtsvg():
    spec = (REPO / "Aion2 TM.spec").read_text(encoding="utf-8")
    assert "('assets/icons/lucide', 'assets/icons/lucide')" in spec
    # QtSvg is what renders every icon; excluding it (as QtMultimedia once
    # was) would ship a build whose every icon is blank.
    assert "'PySide6.QtSvg'" not in spec


# ---------------------------------------------------------------------------
# rendering, and re-tinting on a theme switch
# ---------------------------------------------------------------------------

def _opaque_colors(image) -> set[str]:
    seen = set()
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() > 240:
                seen.add(color.name())
    return seen


def test_icon_renders_offscreen(qapp):
    icon = icons.icon("settings", 16)
    assert not icon.isNull()
    pixmap = icon.pixmap(16, 16)
    assert not pixmap.isNull()
    assert pixmap.size().width() == 16
    assert _opaque_colors(pixmap.toImage()), "the icon rendered fully transparent"


def test_an_unknown_name_fails_at_the_call_site(qapp):
    with pytest.raises(KeyError):
        icons.icon("definitely-not-a-lucide-icon")


def test_the_same_qicon_retints_when_the_theme_changes(qapp):
    """The whole reason for the QIconEngine (see ui/widgets/icons.py)."""
    before = theme.current()
    try:
        icon = icons.icon("settings", 24, "accent")

        theme.set_current("abyss")
        abyss = _opaque_colors(icon.pixmap(24, 24).toImage())
        theme.set_current("inferno")
        inferno = _opaque_colors(icon.pixmap(24, 24).toImage())

        assert abyss == {theme.qcolor(theme.tokens("abyss"), "accent").name()}
        assert inferno == {theme.qcolor(theme.tokens("inferno"), "accent").name()}
        assert abyss != inferno, "the QIcon kept the old theme's colour"
    finally:
        theme.set_current(before)


def test_a_colour_can_be_a_token_a_qcolor_or_a_literal(qapp):
    before = theme.current()
    try:
        theme.set_current("abyss")
        assert icons.resolve_color("ok") == theme.qcolor(theme.ABYSS, "ok").name()
        assert icons.resolve_color("fg.muted") == theme.qcolor(theme.ABYSS, "fg.muted").name()
        assert icons.resolve_color(None) == theme.qcolor(theme.ABYSS, "fg").name()
        assert icons.resolve_color(QColor(theme.ABYSS.danger)) == theme.ABYSS.danger
    finally:
        theme.set_current(before)


def test_the_empty_state_can_carry_an_icon(qapp):
    """MASTER §3 « État vide : icône Lucide 24 px fg.muted » (review G/m13)."""
    from ui.widgets.empty_state import EmptyStateWidget

    widget = EmptyStateWidget()
    try:
        assert widget.icon_label is None, "an empty state without an icon grows none"
        widget.set_icon("list-todo")
        assert widget.icon_label is not None
        assert widget.icon_label.icon_name == "list-todo"
        assert widget.icon_label.sizeHint().width() == 24
        widget.set_icon("shopping-cart")
        assert widget.icon_label.icon_name == "shopping-cart"
    finally:
        widget.deleteLater()


# ---------------------------------------------------------------------------
# no emoji came back
# ---------------------------------------------------------------------------

#: Pictographs, dingbats, geometric shapes and arrows — the four blocks the
#: app actually drew icons out of ("🎉", "✓", "●", "▾", "⚙", "↺").  Plain
#: punctuation ("!", "|", "·") and letters (Σ) are not matched: they are
#: typography, not an icon standing in for one.
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # pictographs, transport, symbols
    "←-⇿"          # arrows
    "⌀-⏿"          # technical (⌚ ⏰ ⚙ is 2699 -> misc symbols below)
    "①-⓿"          # enclosed alphanumerics
    "■-➿"          # geometric shapes, misc symbols, dingbats
    "⬀-⯿"          # misc symbols and arrows
    "️"                 # variation selector-16
    "]"
)

#: Only *displayed* text is scanned.  A "✓" in a docstring or a comment is
#: prose about the old glyph, which several of these files now carry.
_TEXT_CALL_RE = re.compile(
    r"""(?:\.setText\(|QLabel\(|QPushButton\(|QToolButton\(|\.setToolTip\()"""
)


def _allowlist() -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in EMOJI_ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, reason = line.partition("  # ")
        assert reason.strip(), f"allow-list entry without a reason: {line}"
        entries[key.strip()] = reason.strip()
    return entries


def _emoji_text_sites() -> list[str]:
    """``file:line`` for every emoji inside a widget-text call in OWNED."""
    sites: list[str] = []
    for rel in OWNED:
        path = REPO / rel
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if _TEXT_CALL_RE.search(code) and _EMOJI_RE.search(code):
                sites.append(f"{rel}:{number}")
    return sites


def test_no_emoji_is_used_as_an_icon_in_the_owned_files():
    allowed = _allowlist()
    offenders = [site for site in _emoji_text_sites() if site not in allowed]
    assert not offenders, (
        "MASTER §3 « aucun emoji comme icône » — new glyph(s) in widget text:\n  "
        + "\n  ".join(offenders)
        + "\nReplace with ui.widgets.icons, or allow-list WITH a reason in "
        + EMOJI_ALLOWLIST.name
    )


# ---------------------------------------------------------------------------
# ... and none came back through a translated string either
# ---------------------------------------------------------------------------

#: The glyphs the app used as icons, banned from every translated value.
#: Two groups, both verified against the real fonts by the test below:
#:
#: * pictographs (📋 🛒 👤 🎉 🌐 …) — Barlow has no cmap entry for any of
#:   them and neither does a stock Linux font stack, so they rendered as
#:   **tofu boxes** on the landing page (visible in the review's reading of
#:   ``icons_todo_abyss.png``: "▯ Templates", "▯ Import", "▯ Overlay");
#: * dingbats, geometric shapes and arrows (▾ ● ○ ✓ ★ ⚙ ↺ ▶ ⬆ …) — not in
#:   Barlow either.  They *render*, through a system fallback face, which is
#:   worse in a different way: a hairline glyph from another typeface eight
#:   pixels from a crisp Lucide chevron reads as a broken icon rather than
#:   as a style.
_BANNED_IN_TRANSLATIONS = "🎉📋📅🛒🛍🎁👤🌐🗄🐛🔍▾▸▴▪●○✓✕✎✏★☆☑⚙↺↻↩↗⬆⬇⬛▶⏸☕❤️"

#: Text characters a translated string MAY carry.  Everything here except
#: ``→`` is in Barlow's own cmap — asserted below, so this list cannot grow
#: by taste.  ``→`` is the one documented exception: it is a prose
#: connective ("{done} → erledigt", "used for your wish → 3 more"), never an
#: icon standing in for a control, and rewriting four sentences in three
#: languages to avoid a fallback-rendered arrow buys nothing.
_ALLOWED_TEXT_SYMBOLS = "×·—…"
_FALLBACK_TEXT_EXCEPTIONS = {"→": "prose connective, never an icon; not in Barlow's cmap"}


def _body_font_path() -> Path:
    return REPO / "assets" / "fonts" / "Barlow-Regular.ttf"


def test_the_allowed_text_symbols_really_are_in_the_body_font(qapp):
    """The allow-list above is a claim about a font file; check the file.

    ``QRawFont.supportsCharacter`` needs an int code point — passing the
    one-character string answers False for everything, which is how a
    "verified" list could quietly be verified against nothing.
    """
    from PySide6.QtGui import QRawFont

    raw = QRawFont(str(_body_font_path()), 16.0)
    assert raw.isValid(), f"{_body_font_path()} did not load"
    assert raw.supportsCharacter(ord("A")), "the cmap probe itself is broken"

    missing = [c for c in _ALLOWED_TEXT_SYMBOLS if not raw.supportsCharacter(ord(c))]
    assert not missing, (
        f"{missing} are allow-listed as text but Barlow has no glyph for them — "
        "they would render from a fallback face, which is what this gate exists "
        "to stop.  Move them to _FALLBACK_TEXT_EXCEPTIONS with a reason, or ban them."
    )
    for glyph in _FALLBACK_TEXT_EXCEPTIONS:
        assert not raw.supportsCharacter(ord(glyph)), (
            f"{glyph!r} IS in Barlow now — move it to _ALLOWED_TEXT_SYMBOLS"
        )


def test_no_translated_string_carries_an_icon_glyph():
    """The gate the source-literal scan could not be.

    Stripping ``"▶ Test"`` down to ``"Test"`` in a constructor is a **no-op
    in the running app**: ``update_language()`` runs at startup and on every
    language change and puts the translated value back, glyph and all.  The
    only place that sweep can happen is the translation table, so that is
    what this reads — the resolved values, all three languages.
    """
    from core.translations import TRANSLATIONS

    offenders: list[str] = []
    for language, table in sorted(TRANSLATIONS.items()):
        for key, value in sorted(table.items()):
            if not isinstance(value, str):
                continue
            found = {c for c in value if c in _BANNED_IN_TRANSLATIONS}
            if found:
                offenders.append(f"{language}/{key}: {''.join(sorted(found))} in {value!r}")
    assert not offenders, (
        "MASTER §3 « aucun emoji comme icône » — icon glyphs in translated "
        "text:\n  " + "\n  ".join(offenders)
        + "\nStrip the glyph from the STRING and put a Lucide icon on the "
          "widget with icons.set_icon(..., clear_text=False)."
    )


def test_every_other_symbol_in_a_translation_is_allow_listed():
    """Catches the next glyph nobody thought to ban.

    The banned list above is a denylist, which only ever knows about the
    characters someone already found.  This is the other direction: every
    non-ASCII symbol in every translated value must be either a letter of
    that language, allow-listed punctuation, or a named exception.
    """
    import unicodedata

    from core.translations import TRANSLATIONS

    allowed = set(_ALLOWED_TEXT_SYMBOLS) | set(_FALLBACK_TEXT_EXCEPTIONS)
    unexpected: dict[str, set[str]] = {}
    for language, table in TRANSLATIONS.items():
        for key, value in table.items():
            if not isinstance(value, str):
                continue
            for char in value:
                if char.isalnum() or char.isspace() or ord(char) < 128 or char in allowed:
                    continue
                if unicodedata.category(char) in (
                        "Pd", "Pi", "Pf", "Po", "Ps", "Pe", "Zs"):
                    # Dashes, quotation marks and brackets of a real
                    # language -- German „…“ and Russian «…» included.
                    continue
                unexpected.setdefault(char, set()).add(f"{language}/{key}")
    assert not unexpected, (
        "new non-text symbol(s) in the translation tables: "
        + ", ".join(f"{c!r} ({sorted(k)[0]})" for c, k in sorted(unexpected.items()))
        + " — ban it in _BANNED_IN_TRANSLATIONS or allow-list it with a reason"
    )


def test_the_allowlist_has_no_dead_entries():
    """An allow-list that outlives its offender hides the next one."""
    live = set(_emoji_text_sites())
    dead = sorted(set(_allowlist()) - live)
    assert not dead, f"allow-list entries that no longer match anything: {dead}"
