"""Lucide icons, tinted from the active theme's tokens (MASTER §3).

MASTER §3 says: « Icônes : Lucide (ISC), 16/20/24 px, couleur héritée via
``fg.*`` ; aucun emoji comme icône ».  Until this module existed the repo
shipped no icon set at all, so three MASTER rows sat in « Décisions
différées » for the same reason -- « le dépôt n'embarque aucun jeu Lucide ».
The set is vendored under ``assets/icons/lucide/`` (see its ``SOURCES.md``
for the pinned tag and the ISC ``LICENSE``).

**Why a QIconEngine rather than a theme-change hook.**  A Lucide SVG paints
``stroke="currentColor"``; Qt has no ``currentColor``, so the colour has to
be substituted into the SVG *text* before :class:`QSvgRenderer` sees it.
That makes a tinted icon a snapshot of one theme -- and a plain
``QIcon(QPixmap)`` handed to a button would keep the old theme's colour
forever after a switch.  Rather than have every call site re-register with
some ``apply_theme`` hook (``ui/main_window.py`` owns that path and would
need one more thing to remember), :class:`_LucideIconEngine` resolves the
colour **at paint time**: it asks :func:`core.theme.current_tokens` on every
``pixmap()``/``paint()`` call, and the module-level cache is keyed on the
resolved colour.  A theme switch therefore re-renders on the next repaint,
which the ``QApplication.setStyleSheet`` of a theme switch already triggers
for every widget.  Same reasoning for :class:`IconLabel`, which paints in
``paintEvent`` instead of holding a pixmap.

Nothing here hardcodes a colour: a caller names a **token**
(``"fg"``, ``"fg.muted"``, ``"accent"``, ``"ok"`` …) and
:func:`core.theme.qcolor` resolves it, exactly like every painter in
``ui/`` (MASTER §4-3).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QIconEngine, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QWidget

from core import theme
from utils.paths import app_root

logger = logging.getLogger(__name__)

#: MASTER §3 — the only three sizes the design system allows.
SIZES: tuple[int, ...] = (16, 20, 24)

#: Default size for an icon that does not name one.
DEFAULT_SIZE = 16

#: Token used when a call site does not name a colour (MASTER §3:
#: « couleur héritée via ``fg.*`` »).
DEFAULT_TOKEN = "fg"

#: The literal every Lucide SVG carries in place of a colour.
CURRENT_COLOR = "currentColor"


def icon_dir() -> Path:
    """Where the vendored Lucide SVGs live.

    Resolved through :func:`utils.paths.app_root` (never by walking up from
    ``__file__``) for the same reason ``core.theme.template_path`` does: in
    a PyInstaller bundle the module's ``__file__`` is synthesized inside the
    PYZ, while the SVGs are shipped as *data* under ``_MEIPASS/assets/``.
    """
    return app_root() / "assets" / "icons" / "lucide"


def tinted_dir() -> Path:
    """Where the per-theme pre-tinted chevrons live.

    QSS ``image: url(...)`` cannot tint anything -- it loads a file as-is --
    so the arrows the sheet draws (combo boxes, spin boxes) are generated
    per theme at *build* time by ``scripts/gen_tinted_icons.py`` and
    committed.  See that script for why this is not a runtime cache.
    """
    return icon_dir() / "tinted"


@lru_cache(maxsize=1)
def available() -> frozenset[str]:
    """Names of every vendored icon (no ``.svg`` suffix)."""
    directory = icon_dir()
    if not directory.is_dir():
        logger.warning("Lucide icon set not found at %s — is it bundled?", directory)
        return frozenset()
    return frozenset(p.stem for p in directory.glob("*.svg"))


@lru_cache(maxsize=128)
def _svg_source(name: str) -> str:
    """Raw SVG text of ``name``.

    Raises :class:`KeyError` on an unknown name rather than returning a
    blank icon: a typo must fail loudly at the call site, the same way an
    unknown ``{{token}}`` fails ``core.theme.render_qss``.
    """
    path = icon_dir() / f"{name}.svg"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise KeyError(
            f"Unknown Lucide icon {name!r} — expected {path}. "
            f"Vendored names: {', '.join(sorted(available())) or '(none found)'}"
        ) from error


def tint(source: str, color: str) -> str:
    """Substitute ``currentColor`` in an SVG for a real colour."""
    return source.replace(CURRENT_COLOR, color)


def resolve_color(color: QColor | str | None = None) -> str:
    """``None`` / a token name / a QColor / a CSS string → ``#rrggbb``.

    A *token* (``"fg.muted"``, ``"accent"``, ``"ok"``) is resolved against
    the theme that is on screen right now, which is what makes an icon
    follow a theme switch without anyone pushing it.
    """
    if color is None:
        color = DEFAULT_TOKEN
    if isinstance(color, QColor):
        return color.name(QColor.HexRgb)
    text = str(color).strip()
    if not text:
        text = DEFAULT_TOKEN
    if text.startswith("#") or text.startswith("rgb"):
        # A caller that already holds a colour (a data colour, MASTER §4-4).
        return QColor(text).name(QColor.HexRgb)
    return theme.qcolor(theme.current_tokens(), text).name(QColor.HexRgb)


@lru_cache(maxsize=512)
def _render(name: str, size: int, color: str, ratio: float) -> QImage:
    """One tinted, device-pixel-ratio-aware raster of an icon.

    Cached on the *resolved* colour, so a theme switch simply misses the
    cache and renders again -- there is no stale entry to invalidate.
    """
    renderer = QSvgRenderer(tint(_svg_source(name), color).encode("utf-8"))
    px = max(1, int(round(size * ratio)))
    image = QImage(px, px, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, px, px))
    painter.end()
    image.setDevicePixelRatio(ratio)
    return image


def pixmap(
    name: str,
    size: int = DEFAULT_SIZE,
    color: QColor | str | None = None,
    ratio: float = 1.0,
) -> QPixmap:
    """A tinted icon raster, ``size`` logical pixels square."""
    return QPixmap.fromImage(_render(name, int(size), resolve_color(color), float(ratio)))


class _LucideIconEngine(QIconEngine):
    """A QIcon that re-tints itself when the theme changes.

    Every ``pixmap``/``paint`` call resolves the colour again (see the
    module docstring), so the engine holds the *token*, never a colour.
    """

    def __init__(self, name: str, size: int = DEFAULT_SIZE,
                 color: QColor | str | None = None):
        super().__init__()
        self._name = name
        self._size = int(size)
        self._color = color

    # -- QIconEngine ---------------------------------------------------
    def pixmap(self, size: QSize, mode, state) -> QPixmap:  # noqa: ARG002
        return self.scaledPixmap(size, mode, state, 1.0)

    def scaledPixmap(self, size: QSize, mode, state, scale: float) -> QPixmap:  # noqa: ARG002
        edge = min(size.width(), size.height()) or self._size
        return pixmap(self._name, edge, self._color, float(scale) or 1.0)

    def paint(self, painter: QPainter, rect, mode, state) -> None:
        raster = self.scaledPixmap(rect.size(), mode, state,
                                   painter.device().devicePixelRatio())
        painter.drawPixmap(rect, raster)

    def availableSizes(self, mode=None, state=None) -> list[QSize]:  # noqa: ARG002
        return [QSize(s, s) for s in SIZES]

    def clone(self) -> QIconEngine:
        return _LucideIconEngine(self._name, self._size, self._color)

    def key(self) -> str:
        return f"lucide:{self._name}"

    def isNull(self) -> bool:
        return self._name not in available()


def icon(name: str, size: int = DEFAULT_SIZE,
         color: QColor | str | None = None) -> QIcon:
    """A theme-following :class:`QIcon` for the Lucide icon ``name``.

    ``color`` is a **token** name (default ``fg``); the icon re-renders in
    the new theme's colour on the first repaint after a theme switch.
    """
    _svg_source(name)  # fail now, at the call site, on a typo
    return QIcon(_LucideIconEngine(name, size, color))


class IconLabel(QWidget):
    """A non-interactive icon, for rows where a ``QPushButton`` would lie.

    A ``QLabel`` holding a pixmap would freeze its tint at construction; this
    paints from the live tokens instead (see the module docstring).
    """

    def __init__(self, name: str, size: int = DEFAULT_SIZE,
                 color: QColor | str | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        _svg_source(name)
        self._name = name
        self._size = int(size)
        self._color = color
        self.setFixedSize(self._size, self._size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def set_icon(self, name: str, color: QColor | str | None = None) -> None:
        """Swap which icon (and optionally which token) this label paints."""
        _svg_source(name)
        self._name = name
        if color is not None:
            self._color = color
        self.update()

    @property
    def icon_name(self) -> str:
        return self._name

    def sizeHint(self) -> QSize:
        return QSize(self._size, self._size)

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.drawPixmap(0, 0, pixmap(self._name, self._size, self._color,
                                        self.devicePixelRatioF()))
        painter.end()


def set_icon(widget: QAbstractButton, name: str, size: int = DEFAULT_SIZE,
             color: QColor | str | None = None, *, clear_text: bool = True) -> None:
    """Put a Lucide icon on a button, replacing whatever glyph it carried.

    ``clear_text`` drops the button's text, which is what turns an
    « emoji as icon » button into a real icon button (MASTER §3).  Pass
    ``False`` for a labelled button that only *prefixes* an icon.
    """
    widget.setIcon(icon(name, size, color))
    widget.setIconSize(QSize(size, size))
    if clear_text:
        widget.setText("")
