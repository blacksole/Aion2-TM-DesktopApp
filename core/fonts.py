"""Bundled OFL typefaces (MASTER §1, typography).

The app ships its three faces in ``assets/fonts/`` so that every machine
renders the same UI — the old QSS hardcoded ``Consolas`` (audit D/C4), which
does not exist off Windows.  :func:`load_fonts` registers them with Qt and
reports the family names Qt *actually* resolved, so a caller never has to
assume a face loaded.

Must be called once, after the ``QApplication`` exists and before the
stylesheet is applied.  Without a ``QApplication`` it does not raise: it
returns the fallback stacks, which is exactly what a headless import (tests,
packaging tools) needs.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtGui import QFontDatabase, QGuiApplication

logger = logging.getLogger(__name__)

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

#: role -> (preferred family, files that provide it, fallback family).
#: The fallbacks mirror MASTER §1 ("Segoe UI, Noto Sans, sans-serif" /
#: "Consolas, DejaVu Sans Mono") reduced to the first entry, since a Qt
#: family name is a single name, not a stack.
FONT_SPECS: dict[str, tuple[str, tuple[str, ...], str]] = {
    "display": (
        "Barlow Condensed",
        ("BarlowCondensed-SemiBold.ttf", "BarlowCondensed-Bold.ttf"),
        "Segoe UI",
    ),
    "body": (
        "Barlow",
        ("Barlow-Regular.ttf", "Barlow-Medium.ttf", "Barlow-SemiBold.ttf"),
        "Segoe UI",
    ),
    "mono": (
        "JetBrains Mono",
        ("JetBrainsMono[wght].ttf",),
        "DejaVu Sans Mono",
    ),
}

_loaded: dict[str, str] | None = None


def _register(path: Path) -> list[str]:
    """Register one font file; return the families Qt found in it."""
    font_id = QFontDatabase.addApplicationFont(str(path))
    if font_id < 0:
        logger.warning("Font rejected by Qt: %s", path)
        return []
    families = list(QFontDatabase.applicationFontFamilies(font_id))
    if not families:
        logger.warning("Font registered but exposes no family: %s", path)
    return families


def load_fonts(force: bool = False) -> dict[str, str]:
    """Register ``assets/fonts/*.ttf`` and return ``{role: family}``.

    Roles are ``display``, ``body`` and ``mono``.  A role whose files are
    missing or rejected falls back to the MASTER fallback family, so the
    returned mapping always has the three keys and is always usable in a
    ``QFont``.  Repeated calls are cached (registering the same file twice
    is wasteful, not harmful).
    """
    global _loaded
    if _loaded is not None and not force:
        return dict(_loaded)

    # Verified 2026-09-18: QFontDatabase.addApplicationFont() *segfaults*
    # (not raises) when no QGuiApplication exists, so this guard is load-
    # bearing, not defensive politeness — it is what makes importing and
    # calling this module safe from a headless test or a packaging tool.
    if QGuiApplication.instance() is None:
        fallbacks = {role: spec[2] for role, spec in FONT_SPECS.items()}
        logger.warning("No QGuiApplication — returning fallback families %s", fallbacks)
        return fallbacks

    resolved: dict[str, str] = {}
    for role, (preferred, filenames, fallback) in FONT_SPECS.items():
        families: list[str] = []
        for filename in filenames:
            path = FONT_DIR / filename
            if not path.is_file():
                logger.warning("Bundled font missing: %s", path)
                continue
            families.extend(_register(path))

        if preferred in families:
            resolved[role] = preferred
        elif families:
            # Qt reported a name we did not expect (a renamed upstream
            # release): trust Qt, not the spec.
            resolved[role] = families[0]
            logger.info("Font role %r resolved to %r (expected %r)", role, families[0], preferred)
        else:
            resolved[role] = fallback
            logger.warning("Font role %r falling back to %r", role, fallback)

    _loaded = resolved
    return dict(resolved)


def family(role: str) -> str:
    """Family name for one role, loading the fonts on first use."""
    fonts = load_fonts()
    if role not in fonts:
        raise KeyError(f"Unknown font role: {role!r} (known: {sorted(FONT_SPECS)})")
    return fonts[role]
