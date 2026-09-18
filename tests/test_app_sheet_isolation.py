"""The application stylesheet must not reach the Armory (review F-0/F-0b/F-0c).

Qt weights each matched declaration by ``(origin + depth) * 0x100000 +
specificity * 0x100 + order`` — **depth dominates specificity by 4096×** — so
two stylesheets do not replace each other, they MERGE per property.  A
window-level sheet (``ItemDatabase/styles.qss``, applied by ``app.py`` to each
Armory window) wins every property it declares, at any specificity; and every
property it does *not* declare cascades down from the QApplication sheet into
that window.

That is why moving the sheet to the QApplication — right in every other
respect — quietly leaked typography and item colour into 22k lines of UI that
were tuned against the default font and paint their own per-rarity
foregrounds.  The worst case was a documented, user-reported, already-fixed
defect being silently re-broken (F-0).

The fix is a scope, not a per-rule judgement: every rule is prefixed with
``QWidget[aion2="true"]``, our three top-levels set that property, and the
Armory's parentless windows therefore never match.  This module gates both
halves of that claim — the sheet is scoped, and the scope covers us.
"""

import re
from pathlib import Path

import pytest

from core import theme

REPO = Path(__file__).resolve().parent.parent
ALLOWLIST = Path(__file__).resolve().parent / "fixtures" / "unscoped_selectors_allowlist.txt"
SCOPE = 'QWidget[aion2="true"]'

ARMORY_SHEET = REPO / "ItemDatabase" / "styles.qss"


def _without_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _rules(qss: str):
    """Yield ``(selector, declarations)`` for every selector of every rule."""
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", _without_comments(qss)):
        declarations = match.group(2)
        for selector in (" ".join(s.split()) for s in match.group(1).split(",")):
            if selector:
                yield selector, declarations


def _allowlist() -> dict[str, str]:
    entries = {}
    for raw in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        selector, _, reason = line.partition("#")
        entries[selector.strip()] = reason.strip()
    return entries


def _declares(declarations: str, prop: str) -> bool:
    return bool(re.search(rf"(^|;|\s){re.escape(prop)}\s*:", declarations))


# ---------------------------------------------------------------------------
# the scope
# ---------------------------------------------------------------------------


def test_the_allowlist_is_tiny_and_justified():
    entries = _allowlist()
    assert entries, "allow-list parsed empty — wrong format?"
    assert len(entries) <= 3, f"the escape hatch is widening: {sorted(entries)}"
    for selector, reason in entries.items():
        assert len(reason) > 60, f"{selector} needs a reason Qt forces, got {reason!r}"


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_every_rule_is_scoped_to_our_own_window_tree(name):
    allowed = _allowlist()
    unscoped = sorted(
        selector
        for selector, _decls in _rules(theme.build_qss(name, "/assets"))
        if not selector.startswith(SCOPE) and selector not in allowed
    )
    assert not unscoped, (
        "these rules reach every window in the process, the Armory included "
        f"— scope them or allow-list them with a reason:\n  {unscoped}"
    )


def test_the_allowlist_has_no_stale_entry():
    live = {selector for selector, _ in _rules(theme.build_qss("abyss", "/assets"))}
    for selector in _allowlist():
        assert selector in live, f"allow-listed selector no longer exists: {selector}"


# ---------------------------------------------------------------------------
# BLOCKER F-0: no `color` on an item view, ever
# ---------------------------------------------------------------------------

#: Selectors where a QSS ``color`` overrides each item's own
#: ``setForeground()`` unconditionally.  ``ItemDatabase`` sets per-rarity
#: item colours in code, so a blanket colour here flattens them.
_ITEM_VIEW_SELECTORS = (
    "QComboBox QAbstractItemView",
    "QComboBox QAbstractItemView::item",
    "QAbstractItemView",
    "QListView",
    "QListWidget",
    "QTableView",
    "QTreeView",
    "QListView::item",
    "QListWidget::item",
    "QTableView::item",
    "QTreeView::item",
    "QListView::item:selected",
    "QTableView::item:selected",
    "QTreeView::item:selected",
)

_FORBIDDEN_ON_ITEM_VIEWS = ("color", "selection-color")


@pytest.mark.parametrize("name", sorted(theme.THEMES))
@pytest.mark.parametrize("bare", _ITEM_VIEW_SELECTORS)
def test_no_colour_on_a_bare_item_view_selector(name, bare):
    """The 2026-08-29 fix, re-gated.

    ``ItemDatabase/styles.qss`` removed exactly this declaration with the
    user report attached ("Grade/Rarity dropdown items showed plain white
    instead of their per-rarity color"); putting it back on the application
    sheet undid the fix through the merge rule above.  Item text colour comes
    from the palette instead (``QPalette::Text`` / ``::HighlightedText``,
    both token-derived in ``core.theme.build_palette``).
    """
    for selector, declarations in _rules(theme.build_qss(name, "/assets")):
        if selector.replace(SCOPE + " ", "") != bare:
            continue
        for prop in _FORBIDDEN_ON_ITEM_VIEWS:
            assert not _declares(declarations, prop), (
                f"{name}: '{prop}' on '{selector}' flattens every item's own "
                f"setForeground() — put it on an objectName-scoped rule instead"
            )


def test_our_own_combos_still_get_their_colour_by_objectname():
    """Dropping the blanket colour must not leave our own popups unstyled —
    the review's fix says "objectName-scoped rules for our own widgets"."""
    qss = theme.build_qss("abyss", "/assets")
    ours = [
        (selector, declarations)
        for selector, declarations in _rules(qss)
        if "QAbstractItemView" in selector and "#" in selector
    ]
    assert ours, "no objectName-scoped item-view rule left at all"
    assert any(_declares(d, "color") for _s, d in ours), (
        "our own combo popups lost their text colour with the blanket rule"
    )


@pytest.mark.parametrize("name", sorted(theme.THEMES))
def test_the_palette_supplies_the_item_text_colour(qapp, name):
    """What replaces the dropped declaration has to actually be there."""
    from PySide6.QtGui import QPalette

    palette = theme.build_palette(name)
    tokens = theme.THEMES[name]
    assert palette.color(QPalette.Text) == theme.qcolor(tokens, "fg")
    assert palette.color(QPalette.HighlightedText) == theme.qcolor(tokens, "fg.on_accent")


# ---------------------------------------------------------------------------
# What the Armory sheet does and does not declare — the merge, spelled out
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not ARMORY_SHEET.is_file(), reason="ItemDatabase not present")
def test_the_armory_sheet_still_omits_colour_on_its_item_view():
    """If the Armory ever declares it itself, this whole gate can relax —
    so the assumption is pinned rather than remembered."""
    armory = {
        selector: declarations
        for selector, declarations in _rules(ARMORY_SHEET.read_text(encoding="utf-8"))
    }
    view = armory.get("QComboBox QAbstractItemView")
    assert view is not None, "the Armory stopped styling its combo popups"
    assert not _declares(view, "color"), (
        "ItemDatabase now declares `color` on its item view — re-read "
        "ItemDatabase/styles.qss:104-112 before changing anything here"
    )


@pytest.mark.skipif(not ARMORY_SHEET.is_file(), reason="ItemDatabase not present")
def test_no_font_family_leaks_anywhere_near_the_armory():
    """Review F-0b: ``ItemDatabase/styles.qss`` declares no ``font-family``
    at all, so any unscoped one in our sheet would retype the whole Armory."""
    armory_text = _without_comments(ARMORY_SHEET.read_text(encoding="utf-8"))
    assert "font-family" not in armory_text, (
        "the Armory now sets its own font-family — this gate can be revisited"
    )
    allowed = _allowlist()
    for selector, declarations in _rules(theme.build_qss("abyss", "/assets")):
        if _declares(declarations, "font-family"):
            assert selector.startswith(SCOPE) or selector in allowed, (
                f"unscoped font-family on '{selector}' would reach the Armory"
            )
