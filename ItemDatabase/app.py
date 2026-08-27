"""Standalone AION 2 item database viewer — filterable, sortable table.

Test app, isolated from cont_ToDo_app (no imports from it, own styles.qss).
Run fetch_items.py first to populate data/items_all.json, then:
    python app.py
"""

import copy
import json
import re
import sys
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

try:
    # Shares one log file with the host app when run through it; standalone
    # `python app.py` (see module docstring) falls back to a plain logger
    # with no file handler configured, so it still runs without cont_ToDo_app.
    from core.app_logger import get_logger
    logger = get_logger("item_database")
except ImportError:
    import logging
    logger = logging.getLogger("item_database")

try:
    # Same optional-import pattern as core.app_logger above -- standalone
    # `python app.py` still runs without cont_ToDo_app, just always in English.
    from core.translations import tr as _tr
except ImportError:
    def _tr(language, key, **kwargs):
        return key.format(**kwargs) if kwargs else key

# Module-level rather than threaded through every one of this file's ~10
# dialog/window classes as a constructor parameter -- this whole module is a
# single-user, single-language-at-a-time desktop session (never two Armory
# windows open in two different languages at once), so one shared "current
# language" is exactly as correct as per-instance state would be, at a
# fraction of the call-site churn. Set via set_armory_language() from
# create_window()/update_language() (see ItemDatabaseWindow); every class
# in this file reads it through the _t() helper below at string-build time.
_ARMORY_LANGUAGE = "en"


def set_armory_language(language: str):
    global _ARMORY_LANGUAGE
    _ARMORY_LANGUAGE = language or "en"


def _t(key: str, **kwargs) -> str:
    """Looks up an Armory-UI translation key in the CURRENT language (see
    set_armory_language). Only for this app's OWN UI chrome (buttons,
    labels, dialog titles, tooltips, messages) -- never for game/API data
    (item/recipe/skill/material/profession/category names, which have no
    official in-game translation yet and must stay in their original
    English form regardless of UI language, see [[feedback-crafting-no-
    translation]])."""
    return _tr(_ARMORY_LANGUAGE, key, **kwargs)

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, QSize, Qt, QSortFilterProxyModel, QTimer, Signal
from PySide6.QtGui import (
    QColor, QCursor, QIcon, QLinearGradient, QPainter, QPainterPath, QPalette, QPen, QPixmap, QRadialGradient,
    QPolygonF, QStandardItem, QStandardItemModel,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionSlider,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

# Two different directories, since PyInstaller (onedir) unpacks read-only
# bundled files under _internal/ next to the exe, separate from the exe's own
# folder:
# - _BUNDLE_DIR: read-only assets/data shipped with the app (icons, static
#   item/recipe/skill catalogs) -- lives inside _MEIPASS when frozen.
# - BASE_DIR: writable, persists across restarts (unlike _MEIPASS, which is
#   re-extracted fresh each launch for onefile builds) -- used for the
#   IconCache/DetailCache HTTP caches, which the app populates itself.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _BUNDLE_DIR = Path(sys._MEIPASS) / "ItemDatabase"
else:
    _BUNDLE_DIR = Path(__file__).parent
BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent

DATA_PATH = _BUNDLE_DIR / "data" / "items_all.json"
ICON_CACHE_DIR = BASE_DIR / "data" / "icons"
DETAIL_CACHE_DIR = BASE_DIR / "data" / "details"
DETAILS_API_URL = "https://shugo.gg/api/items/batch-details"
ICON_SIZE = 32
VISIBLE_ROW_PADDING = 20
NAME_COLUMN = 2

# "Empty slot" placeholder artwork, sourced from aion2planner.com/itemdata/ —
# a fan-made build-planner site's already-processed icon set (not scraped
# game files) — shown until a real item is equipped, then replaced by the
# item's own icon via IconCache as usual. No matching placeholder found for
# Brooch1/Brooch2 on that site (skipped, stays blank until equipped).
_PLACEHOLDER_DIR = _BUNDLE_DIR / "assets" / "slot_placeholders"

_EQUIPMENT_SLOT_PLACEHOLDER = {
    "MainHand": "weapon", "SubHand": "guard", "Helmet": "helm",
    "Shoulder": "pauldrons", "Torso": "top", "Gloves": "gloves",
    "Pants": "legs", "Boots": "shoes", "Earring1": "earrings_1",
    "Earring2": "earrings_2", "Necklace": "necklace", "Amulet": "amulet",
    "Ring1": "ring_1", "Ring2": "ring_2",
    "Bracelet1": "bracelet_1", "Bracelet2": "bracelet_2",
}

def _placeholder_icon(subdir: str, name: str) -> QIcon | None:
    path = _PLACEHOLDER_DIR / subdir / f"{name}.png"
    return QIcon(str(path)) if path.exists() else None
ID_COLUMN = 1

COLUMNS = ["Icon", "ID", "Name", "Grade", "Category", "Classes", "Tradable", "PvP/PvE"]
GEAR_TYPE_COLUMN = 7

# Parsed Wings Equip/Owned Effect stat names (see _parse_wing_effects) are
# stashed on the ID column's QStandardItem under these roles -- there's no
# structured data field for them anywhere in the catalog, so they're parsed
# once at load time instead of re-parsed on every filter check.
WING_EQUIP_STATS_ROLE = Qt.UserRole
WING_OWNED_STATS_ROLE = Qt.UserRole + 1

GRADE_COLORS = {
    "Common": "#94a3b8",
    "Rare": "#4ade80",
    "Unique": "#facc15",
    "Epic": "#f59e0b",
    "Legend": "#38bdf8",
}

# Enchant-level label accent per app Layout theme (User-Wunsch, 2026-08-26:
# make the enchant badge follow the app's Layout theme instead of one fixed
# color). Sourced from the per-theme accent pair ("a"/"b") already vetted in
# the Build Planner browser mockup (scratchpad build_planner_preview.html),
# picking whichever of the two per theme doesn't collide with a GRADE_COLORS
# value (Abyss's/Frostbite's own "a" and cats[0] both land on the exact same
# sky-blue as Legend -- avoided here the same way Epic-amber was avoided for
# the badge color originally).
ENCHANT_ACCENT_BY_THEME = {
    "abyss": "#06b6d4",
    "inferno": "#ef4444",
    "emerald": "#2dd4bf",
    "frostbite": "#6366f1",
    "obsidian": "#e2e8f0",
    "void": "#a78bfa",
}

# Real ascending rarity order, confirmed by the user — "Legend" scales
# BELOW "Unique" despite the name (matches its weaker enchant-bonus curve
# in estimate_enchant_bonus too).
RARITY_ORDER = ["Common", "Rare", "Legend", "Unique", "Epic"]
RARITY_RANK = {g: i for i, g in enumerate(RARITY_ORDER)}

GEAR_TYPE_COLORS = {"PvP": "#fb7185", "PvE": "#4ade80", "Neutral": "#94a3b8"}


def _gear_type(item: dict) -> str:
    """PvP/PvE/Dungeon(neutral) gear is trivially identifiable from the
    catalog's own 'options' strings — a PvP-flavored stat (e.g. 'PvP Damage
    Boost 10%') or PvE-flavored one (e.g. 'PvE Damage Boost 5%') is always
    listed as-is among the item's options when present. Non-equipment items
    (no options at all — materials, consumables, ...) return "" instead of
    "Neutral", since they're not gear at all."""
    options = item.get("options") or []
    if not options:
        return ""
    if any("PvP" in o for o in options):
        return "PvP"
    if any("PvE" in o for o in options):
        return "PvE"
    return "Neutral"

# Sidebar category grouping (User-Wunsch, approved 2026-08-24): the item
# catalog's 78 raw categoryName values are consolidated into 7 top-level
# groups for the right-hand sidebar. "Gear" is the only group with its own
# nested subgroups (Weapons/Armor/Accessories/Wings) -- every other group
# maps its raw categoryName values directly as the Category dropdown's
# entries. All raw values below were cross-checked against a live dump of
# data/items_all.json's categoryName field (incl. near-duplicate/legacy
# spellings like "Gatherable Material" vs. "Gathering Material" or
# "Potion" vs. "Potions", which the catalog genuinely uses side by side).
_GEAR_SUBGROUPS: dict[str, set[str]] = {
    "Weapons": {"Greatsword", "Longsword", "Dagger", "Bow", "Spellbook", "Orb",
                "Mace", "Staff", "Fist", "Gauntlet", "Guard"},
    "Armor": {"Helm", "Pauldrons", "Top", "Gloves", "Legs", "Shoes", "Cloak", "Armor"},
    "Accessories": {"Amulet", "Bracelet", "Brooch", "Earrings", "Necklace",
                    "Ring", "Pendant", "Belt"},
}

# None for "Gear" is a sentinel meaning "use _GEAR_SUBGROUPS instead" --
# every other entry is the flat set of raw categoryName values in that group.
# "Wings" is its own top-level entry (User-Wunsch) rather than a Gear
# subgroup, since it gets its own dedicated Equip/Owned-Effect filters
# (see _parse_wing_effects) instead of the normal Category/Class dropdowns.
_ITEM_TOP_CATEGORIES: list[tuple[str, set[str] | None]] = [
    ("Gear", None),
    ("Wings", {"Wings", "Wings Unlocking Item"}),
    ("Arcana", {"Bell", "Compass", "Mirror", "Parchment", "Scales", "Chalice", "Arcana"}),
    ("Materials & Enhancement", {
        "Crafting Material", "Gathering Material", "Gatherable Material",
        "Special Material", "Special Materials", "Special Substance Morph Material",
        "Substance Morph Material", "Substance Morph Design",
        "Manastone", "Manastone/Soulstone", "Theostone",
        "Potential Enhance Stone", "Transfer Stone",
    }),
    ("Consumables", {"Potion", "Potions", "Food", "Beverage", "Food/Beverage", "Consumables"}),
    ("Tools & Services", {
        "Crafting Skill Learning Tool", "Essence Extraction Learning Tool",
        "Resurrection Tool", "Teleport", "Kisk", "Hourglass",
    }),
    ("Cosmetics", {"Skin Combine", "Skin Reward Voucher", "Customization", "Transformation"}),
    ("Chests & Misc", {
        "Chest", "Reward Chest", "Kina Chest", "Key", "Pantheon", "Pantheon Decor",
        "Title Bestowing Item", "Decoration", "Dice", "Lantern",
        "Quest Scroll", "Scroll", "Miscellaneous",
    }),
]


def _gear_group_categories() -> set[str]:
    """Union of all raw categoryName values across the 3 Gear subgroups --
    the scope used when the sidebar's "Gear" button itself is selected."""
    result: set[str] = set()
    for values in _GEAR_SUBGROUPS.values():
        result |= values
    return result


_WING_EFFECT_RE = re.compile(r"\[Equip Effect\](.*?)\[Owned Effect\](.*)", re.S)


def _parse_wing_effects(description: str) -> tuple[set[str], set[str]]:
    """Wings items carry NO structured stat data anywhere (neither the
    catalog's own `options` field nor shugo.gg's live detail endpoint --
    both confirmed empty for every one of the 86 Wings/Wings Unlocking Item
    entries) -- their real stats only ever show up as free text inside
    `description`, consistently shaped as "[Equip Effect]\\nStat: Value\\n...
    [Owned Effect]\\nStat: Value\\n...". Verified against all 86 real Wings
    descriptions with zero parse failures. Returns (equip_stat_names,
    owned_stat_names) -- just the stat NAMES (not their values), since the
    Equip/Owned Effect filters only need to know which stats an item rolls,
    not the value.

    Note: the catalog's own text contains a real typo, "Criticial Hit"
    alongside the correctly-spelled "Critical Hit" -- kept verbatim rather
    than "fixed", since these are genuine game-source strings, not ours."""
    match = _WING_EFFECT_RE.search(description or "")
    if not match:
        return set(), set()

    def _stat_names(block: str) -> set[str]:
        names = set()
        for line in block.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            name, sep, _value = line.rpartition(":")
            if sep:
                names.add(name.strip())
        return names

    return _stat_names(match.group(1)), _stat_names(match.group(2))


# Per-rarity backdrop was originally a real texture image (from questlog.gg's
# icon_backgrounds mirror, saved locally under assets/) -- replaced with a
# painted gradient instead (User-Wunsch, 2026-08-27, after even a .png
# re-encode of that texture STILL showed as flat grey in a freshly rebuilt +
# reinstalled EXE on a second machine: "Kann man hierfür auf Dateien oder
# Farben zurückgreifen, die direkt in der App hinterlegt sind?"). Drawing the
# backdrop with QPainter from GRADE_COLORS (already a plain Python dict, no
# file I/O at all) can't be affected by however a given PyInstaller build
# happens to bundle -- or fail to bundle -- an image asset/plugin, unlike an
# on-disk texture file. Visually a diagonal rarity-tinted glow instead of the
# original artwork -- an intentional trade (User: "Das Problem ist nicht die
# Entwicklungsumgebung", i.e. reliability in the real distributed build
# matters here, not exact parity with the original texture's look).
def _rarity_backdrop_gradient(size: int, grade: str | None) -> QLinearGradient | None:
    color = GRADE_COLORS.get(grade) if grade else None
    if not color:
        return None
    c = QColor(color)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), 130))
    gradient.setColorAt(0.55, QColor(30, 41, 59, 235))
    gradient.setColorAt(1.0, QColor(15, 23, 42, 255))
    return gradient

# Same 4-stop diagonal gradients as cont_ToDo_app's 6 Layout themes — copied
# on purpose so this semi-isolated sub-app looks consistent without
# importing from ui/main_window.py (User-Wunsch, 2026-08-26: "Die Layouts
# wirken sich aktuell noch nicht auf den Buildplanner aus").
LAYOUT_THEMES = {
    "abyss": ["#0f172a", "#111827", "#121212", "#2e0f28"],
    "inferno": ["#140f0f", "#1f1111", "#281212", "#3b0f0f"],
    "emerald": ["#07130f", "#0b1f17", "#10261f", "#132d26"],
    "frostbite": ["#0b1120", "#111827", "#172554", "#1e3a8a"],
    "obsidian": ["#111111", "#171717", "#1f1f1f", "#262626"],
    "void": ["#120c1c", "#1b1028", "#231236", "#2f1547"],
}


class GradientBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = "abyss"

    def set_theme(self, theme: str):
        self.theme = theme if theme in LAYOUT_THEMES else "abyss"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        colors = LAYOUT_THEMES.get(self.theme, LAYOUT_THEMES["abyss"])
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor(colors[0]))
        gradient.setColorAt(0.35, QColor(colors[1]))
        gradient.setColorAt(0.75, QColor(colors[2]))
        gradient.setColorAt(1.0, QColor(colors[3]))
        painter.fillRect(self.rect(), gradient)


class IconCache(QObject):
    """Downloads item icons on demand and caches them on disk + in memory.

    Many items share the same icon URL (e.g. tier variants of one weapon),
    so requests are deduplicated by URL, and each URL is only ever fetched
    once across app runs thanks to the on-disk cache.
    """

    icon_ready = Signal(str)

    def __init__(self, cache_dir: Path, parent=None):
        super().__init__(parent)
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._raw: dict[str, QPixmap] = {}
        self._composed: dict[tuple[str, int, str | None], QPixmap] = {}
        self._pending: set[str] = set()
        self._manager = QNetworkAccessManager(self)

    def _disk_path(self, url: str) -> Path:
        name = Path(urlparse(url).path).name or "icon.png"
        return self._cache_dir / name

    @staticmethod
    def compose(raw: QPixmap, size: int, grade: str | None = None) -> QPixmap:
        """Item icons are transparent-background renders, often in dark metal
        tones — invisible against a dark table. Composite onto a slot
        backdrop, the way game inventories normally present them.

        grade, when given a known rarity (GRADE_COLORS key), uses that
        rarity's own color for a painted backdrop gradient (see
        _rarity_backdrop_gradient) plus a matching border, instead of the
        neutral slate default — baked into the pixmap itself so it also
        works in contexts with no wrapper widget to style (e.g. a
        QStandardItem's DecorationRole in the item table)."""
        composed = QPixmap(size, size)
        composed.fill(Qt.transparent)

        radius = max(4, size // 8)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)

        painter = QPainter(composed)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.Antialiasing)

        border_color = GRADE_COLORS.get(grade) if grade else None
        bg_gradient = _rarity_backdrop_gradient(size, grade)

        painter.setClipPath(clip_path)
        if bg_gradient is not None:
            painter.fillRect(0, 0, size, size, bg_gradient)
        else:
            painter.fillRect(0, 0, size, size, QColor(71, 85, 105))
        painter.setClipping(False)

        pen = QPen(QColor(border_color), 1.2) if border_color else QPen(QColor(148, 163, 184, 110), 1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1), radius, radius)

        inset = max(2, size // 12)
        scaled = raw.scaled(
            size - inset * 2, size - inset * 2,
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        x = (size - scaled.width()) // 2
        y = (size - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()
        return composed

    def pixmap(self, url: str, size: int = ICON_SIZE, grade: str | None = None) -> QPixmap | None:
        raw = self._raw.get(url)
        if raw is None:
            return None
        key = (url, size, grade)
        if key not in self._composed:
            self._composed[key] = self.compose(raw, size, grade)
        return self._composed[key]

    def request(self, url: str):
        if not url or url in self._raw or url in self._pending:
            return

        disk_path = self._disk_path(url)
        if disk_path.exists():
            raw = QPixmap(str(disk_path))
            if not raw.isNull():
                self._raw[url] = raw
                self.icon_ready.emit(url)
                return

        self._pending.add(url)
        reply = self._manager.get(QNetworkRequest(url))
        reply.finished.connect(lambda: self._on_finished(url, reply, disk_path))

    def _on_finished(self, url: str, reply, disk_path: Path):
        self._pending.discard(url)
        network_error = reply.error()
        data = reply.readAll()
        reply.deleteLater()

        if network_error != QNetworkReply.NoError:
            logger.warning("Icon fetch FAILED (network error=%s, url=%s)", network_error, url)
            return

        raw = QPixmap()
        if not raw.loadFromData(data):
            logger.warning("Icon fetch FAILED (could not decode image data, url=%s, bytes=%s)", url, len(data))
            return

        try:
            disk_path.write_bytes(bytes(data))
        except OSError:
            pass

        self._raw[url] = raw
        self.icon_ready.emit(url)


class ItemDetailCache(QObject):
    """Fetches rich per-item stat details (sockets, required level, main/sub
    stats) from shugo.gg's batch-details endpoint, on demand per item id —
    used for the Name column tooltip. Cached on disk + in memory, same
    dedup/reuse pattern as IconCache."""

    detail_ready = Signal(int)

    def __init__(self, cache_dir: Path, parent=None):
        super().__init__(parent)
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory: dict[int, dict] = {}
        self._pending: set[int] = set()
        self._manager = QNetworkAccessManager(self)

    def _disk_path(self, item_id: int) -> Path:
        return self._cache_dir / f"{item_id}.json"

    def get(self, item_id: int) -> dict | None:
        return self._memory.get(item_id)

    def request(self, item_id: int):
        if not item_id or item_id in self._memory or item_id in self._pending:
            return

        disk_path = self._disk_path(item_id)
        if disk_path.exists():
            try:
                detail = json.loads(disk_path.read_text(encoding="utf-8"))
                self._memory[item_id] = detail
                self.detail_ready.emit(item_id)
                return
            except (OSError, json.JSONDecodeError):
                pass

        self._pending.add(item_id)
        request = QNetworkRequest(DETAILS_API_URL)
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
        request.setRawHeader(b"Referer", b"https://shugo.gg/")
        request.setRawHeader(b"Origin", b"https://shugo.gg")
        body = json.dumps({"itemIds": [item_id]}).encode("utf-8")
        reply = self._manager.post(request, body)
        reply.finished.connect(lambda: self._on_finished(item_id, reply, disk_path))

    def _on_finished(self, item_id: int, reply, disk_path: Path):
        self._pending.discard(item_id)
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        raw = bytes(reply.readAll())
        reply.deleteLater()

        if status != 200:
            return

        try:
            payload = json.loads(raw.decode("utf-8"))
            detail = (payload.get("items") or [None])[0]
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            return

        if not detail:
            return

        self._memory[item_id] = detail
        try:
            disk_path.write_text(json.dumps(detail, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

        self.detail_ready.emit(item_id)

    # Confirmed via a live probe: the endpoint hard-rejects anything past
    # this with HTTP 400 "Maximum 50 items per batch" — silently, since a
    # non-200 reply just aborts (see _on_finished_many), so a single
    # oversized request used to fail every row in a big category with zero
    # visible error.
    _MAX_BATCH_SIZE = 50

    def request_many(self, item_ids: list[int]):
        """Batched variant of request() — used by the item picker to fetch
        required-level for a whole filtered list in as few network calls as
        possible instead of one request per row, chunked to the endpoint's
        50-item batch limit."""
        to_fetch = []
        for item_id in item_ids:
            if not item_id or item_id in self._memory or item_id in self._pending:
                continue
            disk_path = self._disk_path(item_id)
            if disk_path.exists():
                try:
                    detail = json.loads(disk_path.read_text(encoding="utf-8"))
                    self._memory[item_id] = detail
                    self.detail_ready.emit(item_id)
                    continue
                except (OSError, json.JSONDecodeError):
                    pass
            to_fetch.append(item_id)

        for start in range(0, len(to_fetch), self._MAX_BATCH_SIZE):
            chunk = to_fetch[start:start + self._MAX_BATCH_SIZE]
            self._pending.update(chunk)
            request = QNetworkRequest(DETAILS_API_URL)
            request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
            request.setRawHeader(b"Referer", b"https://shugo.gg/")
            request.setRawHeader(b"Origin", b"https://shugo.gg")
            body = json.dumps({"itemIds": chunk}).encode("utf-8")
            reply = self._manager.post(request, body)
            reply.finished.connect(lambda c=chunk, r=reply: self._on_finished_many(c, r))

    def _on_finished_many(self, item_ids: list[int], reply):
        for item_id in item_ids:
            self._pending.discard(item_id)
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        raw = bytes(reply.readAll())
        reply.deleteLater()

        if status != 200:
            return

        try:
            payload = json.loads(raw.decode("utf-8"))
            details = payload.get("items") or []
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            return

        for detail in details:
            item_id = detail.get("id")
            if not item_id:
                continue
            self._memory[item_id] = detail
            try:
                self._disk_path(item_id).write_text(json.dumps(detail, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
            self.detail_ready.emit(item_id)


def format_tooltip(detail: dict) -> str:
    lines = [f"<b>{detail.get('name', '')}</b>"]

    grade_name = detail.get("gradeName") or detail.get("grade") or ""
    category = detail.get("categoryName", "")
    header = " · ".join(p for p in (grade_name, category) if p)
    if header:
        lines.append(f"<i>{header}</i>")

    if detail.get("equipLevel"):
        lines.append(f"Required Level: {detail['equipLevel']}")

    sockets = []
    if detail.get("magicStoneSlotCount"):
        sockets.append(f"{detail['magicStoneSlotCount']} Manastone")
    if detail.get("godStoneSlotCount"):
        sockets.append(f"{detail['godStoneSlotCount']} Godstone")
    if sockets:
        lines.append(" / ".join(sockets))

    def stat_line(stat: dict) -> str:
        name = stat.get("name", "")
        value = stat.get("value", "")
        min_value = stat.get("minValue")
        if min_value and min_value != value:
            return f"{name}: {min_value} ~ {value}"
        return f"{name}: {value}"

    main_stats = detail.get("mainStats") or []
    if main_stats:
        lines.append("<hr>")
        lines.extend(stat_line(s) for s in main_stats)

    sub_stats = detail.get("subStats") or []
    if sub_stats:
        lines.append("<hr><i>Substat potential</i>")
        lines.extend(stat_line(s) for s in sub_stats[:8])

    return "<br>".join(lines)


def _format_number(value: float) -> str:
    return str(int(round(value)))


# The one main stat that scales with enchant — identified by id, not by
# whether the item happens to display it as a range or a flat number
# (e.g. Guard shows a flat "Attack: 136", Greatsword/Staff show a range).
_SCALING_STAT_ID = "WeaponFixingDamage"

# Accessories use a completely different (and much simpler) rate than
# weapons/guards for the same scaling stat — confirmed universal across
# every grade sampled.
_ACCESSORY_CATEGORIES = {"Necklace", "Earrings", "Ring", "Bracelet", "Brooch", "Amulet"}
_ACCESSORY_RATE_PER_LEVEL = 5.0

# (k, p) for bonus = k * level**p, fit to real data pulled from 12 actual
# characters' actually-equipped gear via the API (101 samples total, see
# project notes) — one real anchor point plus the confirmed frozen value at
# the grade's own maxEnchantLevel:
#   Legend: lvl1->+10, lvl5->+50                      (exactly linear)
#   Unique: lvl6->+65, lvl10->+125, lvl12->+165, cap lvl15->+225
#   Heroic (Epic): CONFIRMED exactly linear, +17.5/level (350/20 = 17.5,
#     verified against a real +20 screenshot — always whole-number bonuses
#     in-game, never fractional; one outlier sub-cap sample we scraped
#     ("Ludra's Grimoire", a Spellbook, showing +125 at level 10 instead of
#     the expected +175) contradicted this and is treated as bad/anomalous
#     data — likely a scrape glitch — rather than overriding the confirmed
#     linear rate.
# Common/Rare: no samples found (no low-level max-enchanted gear exists in
# practice) — falls back to the Legend shape as a rough placeholder.
_WEAPON_CURVE_PARAMS = {
    "Legend": (10.0, 1.0),
    "Unique": (5.733, 1.355),
}
_HEROIC_RATE_PER_LEVEL = 17.5
_DEFAULT_WEAPON_CURVE = (10.0, 1.0)


def estimate_enchant_bonus(
    level: int, grade_name: str = "", normal_max_level: int = 0, category_name: str = "",
) -> float:
    """Estimated bonus ADDED ALONGSIDE (never into) a weapon/armor's ranged
    main stat (e.g. Attack) at a given enchant level — the base min~max
    range itself is always shown completely unchanged, exactly like the
    in-game '396 ~ 545 (+350)' display: only the '(+N)' part is new.

    Only the one main stat that has this id scales with enchant at all —
    verified via the API against real, actually-equipped items: Accuracy/
    Critical Hit/Block/etc. never changed at any enchant level.

    Accessories (Ring, Necklace, ...) scale at a flat, grade-independent
    rate; weapons/guards follow a grade-dependent curve — both fit to real
    data (see the constants above).

    The bonus FREEZES at the item's own maxEnchantLevel (confirmed: this
    varies by grade — Legend/Unique cap at 15, Epic/Heroic at 20) — past
    that point (Exceed range) it stops growing entirely; instead two new
    separate bonus lines appear (see estimate_exceed_bonus)."""
    effective_level = min(level, normal_max_level) if normal_max_level else level
    if effective_level <= 0:
        return 0.0
    if category_name in _ACCESSORY_CATEGORIES:
        return _ACCESSORY_RATE_PER_LEVEL * effective_level
    if grade_name == "Heroic":
        # Confirmed exactly linear at +17.5/level — a real, precise rate,
        # so odd levels land on a decimal internally (e.g. level 1 -> 17.5);
        # _format_number() rounds this to a whole number for display, since
        # in-game bonus displays are always whole numbers.
        return _HEROIC_RATE_PER_LEVEL * effective_level
    k, p = _WEAPON_CURVE_PARAMS.get(grade_name, _DEFAULT_WEAPON_CURVE)
    return k * (effective_level ** p)


def estimate_exceed_bonus(level: int, normal_max_level: int, category_name: str = "") -> dict:
    """Past the item's normal max enchant level (the Exceed range), new
    separate stat lines appear on top of the (now frozen) ranged main stat
    bonus. Confirmed via ~40 real Exceed-range samples (3/4/5 Exceed steps,
    both Unique and Epic grade — rate is identical across grades, only
    category changes it):
      - Weapons/Guards: flat 'Attack' +30/step, 'Attack increase' +1%/step.
      - Accessories: flat 'Attack' +20/step, a separate 'Defense' +40/step,
        'Attack increase' +1%/step (all three lines shown together)."""
    if not normal_max_level or level <= normal_max_level:
        return {"attack": 0.0, "attack_pct": 0.0, "defense": 0.0}
    steps = level - normal_max_level
    if category_name in _ACCESSORY_CATEGORIES:
        return {"attack": 20.0 * steps, "attack_pct": 1.0 * steps, "defense": 40.0 * steps}
    return {"attack": 30.0 * steps, "attack_pct": 1.0 * steps, "defense": 0.0}


# Armor (body pieces) scales TWO main stats simultaneously — Defense AND HP
# — unlike weapons/accessories, which only scale one. Confirmed via 16 real
# samples across all 7 armor slots (Helm/Top/Pauldrons/Gloves/Legs/Shoes/
# Cloak) at both Unique and Epic/Heroic grade, all internally consistent:
#   Unique: Defense cap 450 @15 (=30/level), HP cap 300 @15 (=20/level)
#   Heroic (Epic): Defense cap 700 @20 (=35/level), HP cap 400 @20 (=20/level)
# HP rate is grade-independent (20/level both grades); Defense rate is not.
# Belt is its OWN special case — own maxEnchantLevel of 10 (not 15/20), and
# BOTH grades gave the identical capped values (Defense 300 / HP 500 @10),
# i.e. Belt's rate is grade-independent entirely: 30/level Defense,
# 50/level HP.
_ARMOR_CATEGORIES = {"Helm", "Top", "Pauldrons", "Gloves", "Legs", "Shoes", "Cloak"}
_BELT_CATEGORY = "Belt"
_DEFENSE_STAT_ID = "ArmorDefense"
_HP_STAT_ID = "HPMax"

_ARMOR_DEFENSE_RATE = {"Unique": 30.0, "Heroic": 35.0}
_DEFAULT_ARMOR_DEFENSE_RATE = 30.0
_ARMOR_HP_RATE_PER_LEVEL = 20.0

_BELT_DEFENSE_RATE_PER_LEVEL = 30.0
_BELT_HP_RATE_PER_LEVEL = 50.0


def estimate_armor_bonus(
    level: int, grade_name: str = "", normal_max_level: int = 0, category_name: str = "",
) -> tuple[float, float]:
    """Returns (defense_bonus, hp_bonus) for an armor piece — see the
    constants above for the data this is calibrated against."""
    effective_level = min(level, normal_max_level) if normal_max_level else level
    if effective_level <= 0:
        return 0.0, 0.0
    if category_name == _BELT_CATEGORY:
        return (
            round(_BELT_DEFENSE_RATE_PER_LEVEL * effective_level),
            round(_BELT_HP_RATE_PER_LEVEL * effective_level),
        )
    def_rate = _ARMOR_DEFENSE_RATE.get(grade_name, _DEFAULT_ARMOR_DEFENSE_RATE)
    return round(def_rate * effective_level), round(_ARMOR_HP_RATE_PER_LEVEL * effective_level)


def estimate_armor_exceed_bonus(level: int, normal_max_level: int) -> dict:
    """Exceed range for armor: both Defense and HP get +80/step (confirmed
    identical across Unique and Epic grade), plus a +1%/step 'increase' on
    each — four new lines total, vs. weapons/accessories' two or three."""
    if not normal_max_level or level <= normal_max_level:
        return {"defense": 0.0, "defense_pct": 0.0, "hp": 0.0, "hp_pct": 0.0}
    steps = level - normal_max_level
    return {"defense": 80.0 * steps, "defense_pct": 1.0 * steps, "hp": 80.0 * steps, "hp_pct": 1.0 * steps}


# The GearScore push from enchanting is its OWN real rate — confirmed via
# shugo.gg's live character/equipment/item endpoint (a real enchant-level
# simulator: TW NCSoft's own API, proxied by shugo.gg, returns a per-item
# 'levelValue' for a given characterId/slotPos/enchantLevel combo) against
# 4 independent real equipped items pulled from real TW characters
# ("Levis"/"Skyvie", [HIT] legion, server 1009) swept across enchant 0/5/
# 10/15/20/25: a Heroic/Epic Staff (weapon), a Unique Guard (weapon-like),
# an Epic/Heroic armor Shoulder piece, and an Epic Necklace (accessory).
# All four gave IDENTICALLY +1.0 levelValue per normal enchant level and
# +5.0 per Exceed step (the DELTA between consecutive sweep points) —
# completely independent of grade or category, and clearly NOT the same
# rate as the Attack/Defense/HP stat bonuses (e.g. a Heroic weapon's
# Attack bonus is +17.5/level, its GearScore push only +1/level).
# NOTE: every real sample's levelValue also carried a constant per-
# instance offset even at enchant 0 (13-24, varying by item) — almost
# certainly from that specific character's socketed magic/god stones,
# which our planner doesn't model at all (no UI/data for them) — so only
# the confirmed RATE is used here; push is 0 at enchant 0, matching
# shugo.gg's own static item-catalog API (always levelValue=0 unenchanted).
_GEARSCORE_NORMAL_RATE = 1.0
_GEARSCORE_EXCEED_RATE = 5.0


def _gearscore_push(enchant_level: int, normal_max_level: int) -> float:
    if enchant_level <= 0:
        return 0.0
    normal_steps = min(enchant_level, normal_max_level) if normal_max_level else enchant_level
    exceed_steps = max(0, enchant_level - normal_max_level) if normal_max_level else 0
    return _GEARSCORE_NORMAL_RATE * normal_steps + _GEARSCORE_EXCEED_RATE * exceed_steps


def _clear_layout(layout):
    """Remove and delete every item (widget or nested layout) from layout.

    setParent(None) before deleteLater(): takeAt() only detaches the widget
    from layout *management* (it stays a visible child of its parent widget,
    painted at its last position) until the deferred delete actually runs —
    normally fast enough not to notice, but a deep/heavy subtree (many
    nested child widgets, as in the Crafting Calculator's recipe cards) can
    take long enough that the old widget visibly ghosts behind the new one
    rendered in the same spot right after. setParent(None) detaches AND
    hides it immediately, no event-loop turnaround needed; deleteLater()
    still reclaims it right after."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        else:
            sub_layout = item.layout()
            if sub_layout is not None:
                _clear_layout(sub_layout)


_PVP_STAT_HINTS = ("abnormal", "pvp", "suppress", "resil", "tenacity", "resist")
_DEFENSIVE_STAT_HINTS = ("defense", "evasion", "hpmax", "mpmax", "block")


def _classify_stat(stat_id: str) -> str:
    """Rough offense/defense/PvP split for the substat pool, based on the
    stat's id. PvP is checked first since e.g. 'AbnormalAccuracy' (Status
    Effect Chance) and resist-style stats matter specifically in PvP."""
    sid = (stat_id or "").lower()
    if any(hint in sid for hint in _PVP_STAT_HINTS):
        return "pvp"
    if any(hint in sid for hint in _DEFENSIVE_STAT_HINTS):
        return "defensive"
    return "offensive"


# Confirmed by the user (2026-08-24): a gear item's substat slots aren't
# only fillable with numeric stat bonuses -- a class-specific skill can be
# slotted in too, sharing the SAME slot budget (verified against shugo.gg's
# real batch-details API: subSkillCountMax always equals subStatCount for
# every real item checked, e.g. weapon 6/6, boots 5/5, ring 5/5). shugo.gg's
# own API never lists the actual selectable skill pool though (only that
# count) -- per the user's own game knowledge, Weapon/Guard/both Rings can
# take ANY of the class's Active skills, every other slot can take any of
# its Passive skills. No curated shorter list exists to fetch, so the full
# class skill pool (from skills_all.json, already used by the Skill
# Planner tab) is offered as-is.
_ACTIVE_SUBSKILL_SLOT_CATEGORIES = {
    "Greatsword", "Longsword", "Dagger", "Bow", "Spellbook", "Orb", "Mace", "Staff", "Fist", "Guard", "Ring",
}


class _TickedSlider(QSlider):
    """QSlider with hand-painted tick marks (User-Screenshot: "hier kann
    man die Schritte nicht mehr sehen" -- the enchant slider's tick marks
    disappeared). Real bug: Qt's Fusion style (forced app-wide this
    session to fix an unrelated QComboBox arrow bug) renders QSlider tick
    marks so faint they're effectively invisible against a dark
    background -- confirmed by rendering a bare, completely unstyled
    QSlider with setTickPosition(TicksBelow) under Fusion and finding zero
    visible ticks, even before any styling of our own was involved. QSS
    can't add them back either -- there's no ::tick subcontrol in Qt style
    sheets. Painted manually here instead, positioned via the same
    QStyle.sliderPositionFromValue() math Qt itself uses internally, so
    they land exactly under the real handle-travel range (which excludes
    a half-handle-width margin on each side -- naively spacing them across
    the full widget width would drift out of alignment with the handle)."""

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.tickPosition() == QSlider.NoTicks or self.tickInterval() <= 0:
            return

        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        groove_rect = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
        handle_rect = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(148, 163, 184, 200))
        pen.setWidth(1)
        painter.setPen(pen)

        available = groove_rect.width() - handle_rect.width()
        tick_y = groove_rect.bottom() + 4
        for tick in range(self.minimum(), self.maximum() + 1, self.tickInterval()):
            x = QStyle.sliderPositionFromValue(
                self.minimum(), self.maximum(), tick, available
            ) + handle_rect.width() // 2 + groove_rect.left()
            painter.drawLine(x, tick_y, x, tick_y + 4)


class _DownwardComboBox(QComboBox):
    """QComboBox whose popup always opens below the widget, never above.

    User-screenshot: the Item-Set combo's popup opened upward for the short
    (10-item) crafted-chain list but downward for the long (23-item)
    dungeon-set list -- Qt's own popup positioning picks whichever direction
    the list fits in without clipping given the parent window's actual
    position on screen, so a SHORTER list can flip upward exactly where a
    longer one wouldn't. Confusing directly under a label that reads
    top-to-bottom, and inconsistent between two states of the same combo --
    forced downward unconditionally instead by moving the popup right after
    Qt shows it."""

    def showPopup(self):
        super().showPopup()
        popup = self.view().window()
        popup.move(self.mapToGlobal(self.rect().bottomLeft()))


class _RoleColorDelegate(QStyledItemDelegate):
    """Paints each row using its own Qt.ForegroundRole color if it has one
    (User-Wunsch: "die Raritäten für die Schriftfarbe verwenden"). Needed
    because the app-wide stylesheet's base "QWidget { color: ... }" rule
    otherwise wins over per-item ForegroundRole data entirely once any
    global stylesheet is active -- confirmed via screenshot comparison that
    neither a QSS selector override nor an instance-level view stylesheet
    (without a "color" property) was enough on their own; forcing the
    option's palette directly in initStyleOption is what actually works."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        color = index.data(Qt.ForegroundRole)
        if color:
            option.palette.setColor(QPalette.Text, color)
            option.palette.setColor(QPalette.HighlightedText, color)


class ItemDetailWidget(QWidget):
    """Shared 'left = clean item image, right = details + enchant slider'
    panel, used both by the click-popup and the loadout window."""

    def __init__(self, icon_cache: "IconCache", detail_cache: "ItemDetailCache", parent=None,
                 compact: bool = False, selectable: bool = True):
        super().__init__(parent)
        self.icon_cache = icon_cache
        self.detail_cache = detail_cache
        # False for the plain Item Database's browse-only popup (User-
        # Wunsch: "bissl komisch, dass man in der Database Items öffnen
        # kann und Eigenschaften anklicken. Hier sollte man nur sehen, was
        # möglich ist") -- substat/skill rows render as plain read-only
        # info (what's POSSIBLE on this item type), not clickable/checkable
        # picks. The Loadout window's equip panel (an actual equipped
        # instance, where picking real Soulbinding rolls matters) keeps the
        # default True.
        self._selectable = selectable
        self._item_id: int | None = None
        self._image_url: str = ""
        self._detail: dict | None = None
        self._enchant_level = 0
        self._philosopher_stone_active = False
        # Only set when load_item() is given a character_class (the Build
        # Planner's equip panel does; the class-agnostic catalog popup
        # doesn't) -- gates the class-skill substat section entirely, since
        # there's no class context to pick a skill pool from otherwise.
        self._character_class: str | None = None
        self._skills_by_class = _load_skills_by_class()
        self._skill_options: list[dict] = []
        # Persists across _render_stats() re-renders (enchant slider moves,
        # item switches) so a user's "I like seeing Angriffswerte open"
        # preference sticks -- keyed by bucket key, default set the first
        # time each key is seen (see _stat_section_open). Skill buckets
        # default collapsed since they're the longest lists (10-12 rows)
        # and the reason this panel needed an accordion in the first place.
        self._substat_section_state: dict[str, bool] = {}

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(140, 140)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setObjectName("DetailIcon")
        self._icon_glow = QGraphicsDropShadowEffect()
        self._icon_glow.setBlurRadius(0)
        self._icon_glow.setOffset(0, 0)
        self._icon_glow.setColor(QColor("#475569"))
        self.icon_label.setGraphicsEffect(self._icon_glow)

        self.name_label = QLabel()
        self.name_label.setObjectName("DetailName")
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setFixedWidth(160)

        self.header_label = QLabel()
        self.header_label.setObjectName("DetailHeader")

        self.info_label = QLabel()
        self.info_label.setObjectName("DetailInfo")
        self.info_label.setWordWrap(True)

        self.main_stats_label = QLabel()
        self.main_stats_label.setObjectName("DetailInfo")
        self.main_stats_label.setWordWrap(True)
        self.main_stats_label.setTextFormat(Qt.RichText)

        self.substats_header_label = QLabel()
        self.substats_header_label.setObjectName("DetailInfo")
        self.substats_header_label.setWordWrap(True)
        self.substats_header_label.setTextFormat(Qt.RichText)

        # Two tabs (User-Wunsch) -- "Substats" (Angriffs-/Defensive-/PvP-
        # Werte accordions) and "Skills" (Active-or-Passive class skills,
        # see _render_stats) instead of all 5 buckets stacked in one column.
        self.substats_tabs = QTabWidget()
        self.substats_tabs.setObjectName("timerModeTabWidget")

        stats_page = QWidget()
        self.substats_layout = QVBoxLayout(stats_page)
        self.substats_layout.setContentsMargins(0, 0, 0, 0)
        self.substats_layout.setSpacing(2)
        # Without this, a tab holding only a single (short) accordion
        # section -- e.g. the Skills tab, which usually has just one
        # Active-or-Passive bucket -- stretches that one widget across the
        # whole tab height instead of anchoring it to the top, leaving a
        # huge empty gap above it (reported by the user via screenshot).
        self.substats_layout.setAlignment(Qt.AlignTop)
        self.substats_tabs.addTab(stats_page, _t("arm_substats_tab"))

        skills_page = QWidget()
        self.skills_tab_layout = QVBoxLayout(skills_page)
        self.skills_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.skills_tab_layout.setSpacing(2)
        self.skills_tab_layout.setAlignment(Qt.AlignTop)
        self.substats_tabs.addTab(skills_page, _t("arm_skills_tab"))

        # Corner widget (top-right of the tab bar, per user request) --
        # filters both tabs down to only the currently checked rows, for
        # reviewing a selection without scrolling past everything else.
        self.only_selected_check = QCheckBox(_t("arm_show_selected_only"))
        self.only_selected_check.toggled.connect(self._on_only_selected_toggled)
        self.substats_tabs.setCornerWidget(self.only_selected_check, Qt.TopRightCorner)
        self._only_show_selected = False
        if not self._selectable:
            # "Nur ausgewählte..." only makes sense once something CAN be
            # selected -- nothing to filter down to in browse-only mode.
            self.only_selected_check.setVisible(False)

        self._substat_checkboxes: dict[int, tuple[QPushButton, QLabel]] = {}
        self._selected_substats: set[int] = set()
        # Selection order (most-recently-picked last) — needed to know which
        # substat to auto-drop if the Philosopher's Stone is switched back
        # off while at the (now-lower) cap; a plain set has no order.
        self._selected_substats_order: list[int] = []
        self._sub_stat_count: int = 0

        # Philosopher's Stone: Revelation — a consumable that opens one
        # extra Soul Binding/Engraving slot on Unique-grade-or-better
        # equipment (confirmed via AION 2 patch notes / community guides,
        # not guessed). Modeled here as a toggle that raises the effective
        # substat cap by 1 while checked.
        self.philosopher_stone_btn = QPushButton(_t("arm_use_philo_stone"))
        self.philosopher_stone_btn.setObjectName("SkillFilterButton")
        self.philosopher_stone_btn.setCheckable(True)
        self.philosopher_stone_btn.setToolTip(_t("arm_philo_stone_tooltip"))
        self.philosopher_stone_btn.setVisible(False)
        self.philosopher_stone_btn.toggled.connect(self._on_philosopher_stone_toggled)

        self.substats_status_label = QLabel()
        self.substats_status_label.setObjectName("DetailInfo")
        self.substats_status_label.setWordWrap(True)
        self.substats_status_label.setTextFormat(Qt.RichText)

        self.skills_label = QLabel()
        self.skills_label.setObjectName("DetailInfo")
        self.skills_label.setWordWrap(True)
        self.skills_label.setTextFormat(Qt.RichText)

        # Enchant control — a slider (with tick marks) instead of separate
        # -/+ step buttons, matching a reference build-planner site's look.
        self.enchant_row = QVBoxLayout()
        caption_row = QHBoxLayout()
        enchant_caption = QLabel(_t("arm_simulate_enchant"))
        enchant_caption.setObjectName("DetailInfo")
        self.enchant_value = QLabel("+0")
        self.enchant_value.setObjectName("DetailEnchantValue")
        caption_row.addWidget(enchant_caption)
        caption_row.addStretch()
        caption_row.addWidget(self.enchant_value)
        self.enchant_row.addLayout(caption_row)

        self.enchant_slider = _TickedSlider(Qt.Horizontal)
        self.enchant_slider.setMinimum(0)
        self.enchant_slider.setMaximum(0)
        self.enchant_slider.setTickPosition(QSlider.TicksBelow)
        self.enchant_slider.setTickInterval(1)
        self.enchant_slider.valueChanged.connect(self._on_enchant_slider_changed)
        # Centered at ~75% width (User-Wunsch: Rand links/rechts + engere
        # Tick-Abstände) instead of stretching edge-to-edge across the
        # whole column -- a bare full-width slider with up to ~25 ticks
        # (normal + Exceed levels) left almost no breathing room either
        # side and packed the ticks tighter than necessary.
        slider_row = QHBoxLayout()
        slider_row.addStretch(1)
        slider_row.addWidget(self.enchant_slider, 6)
        slider_row.addStretch(1)
        self.enchant_row.addLayout(slider_row)
        self._enchant_row_widgets = [enchant_caption, self.enchant_value, self.enchant_slider]

        self.disclaimer_label = QLabel(_t("arm_enchant_sim_note"))
        self.disclaimer_label.setObjectName("DetailDisclaimer")
        self.disclaimer_label.setWordWrap(True)
        self.disclaimer_label.setVisible(False)

        if compact:
            # Icon on the left, name/grade + basic info + enchant slider in
            # a column to its right (User-Wunsch: bessere Nutzung der Breite
            # statt alles zentriert übereinander), main stats/substats/
            # skills stacked full-width below that — for embedding inline
            # in a narrower column (Equipment tab).
            outer = QVBoxLayout(self)
            # Was 0 all around -- with the panel now scrolled (see
            # equip_detail_scroll) and no frame, content (labels, substat
            # tabs, everything) touched the container/scrollbar edge with
            # no breathing room at all (User-Wunsch: Rand links/rechts).
            outer.setContentsMargins(16, 8, 16, 8)
            outer.setSpacing(10)

            top_row = QHBoxLayout()
            top_row.setSpacing(14)
            icon_col = QVBoxLayout()
            icon_col.setSpacing(6)
            icon_col.addWidget(self.icon_label, 0, Qt.AlignHCenter)
            icon_col.addWidget(self.name_label, 0, Qt.AlignHCenter)
            top_row.addLayout(icon_col)

            info_col = QVBoxLayout()
            info_col.setSpacing(6)
            info_col.addWidget(self.header_label)
            info_col.addWidget(self.info_label)
            info_col.addLayout(self.enchant_row)
            info_col.addStretch()
            top_row.addLayout(info_col, 1)
            outer.addLayout(top_row)

            outer.addWidget(self.main_stats_label)
            outer.addWidget(self.substats_header_label)
            outer.addWidget(self.substats_tabs)
            outer.addWidget(self.philosopher_stone_btn)
            outer.addWidget(self.substats_status_label)
            outer.addWidget(self.skills_label)
            outer.addWidget(self.disclaimer_label)
            outer.addStretch()
        else:
            # Side-by-side: icon+title on the left, everything else on the
            # right — used by the popup dialogs (item-database browser,
            # equipped-slot detail).
            layout = QHBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(20)

            left = QVBoxLayout()
            left.setSpacing(8)
            left.addWidget(self.icon_label, 0, Qt.AlignCenter)
            left.addWidget(self.name_label)
            left.addStretch()
            layout.addLayout(left)

            right = QVBoxLayout()
            right.setSpacing(6)
            right.addWidget(self.header_label)
            right.addWidget(self.info_label)
            right.addWidget(self.main_stats_label)
            right.addWidget(self.substats_header_label)
            right.addWidget(self.substats_tabs)
            right.addWidget(self.philosopher_stone_btn)
            right.addWidget(self.substats_status_label)
            right.addWidget(self.skills_label)
            right.addLayout(self.enchant_row)
            right.addWidget(self.disclaimer_label)
            right.addStretch()
            layout.addLayout(right, 1)

        self._set_enchant_controls_visible(False)

    def _set_enchant_controls_visible(self, visible: bool):
        for w in self._enchant_row_widgets:
            w.setVisible(visible)
        self.disclaimer_label.setVisible(visible)

    def load_item(
        self, item_id: int, name: str, image_url: str,
        preset_substats: set[int] | None = None, preset_enchant: int = 0,
        character_class: str | None = None,
    ):
        """preset_substats/preset_enchant restore a previously-saved
        selection when reopening an already-equipped slot — without them,
        every reopen would silently reset the item back to +0/no substats,
        even though the slot's actual saved state (used for Stat Info)
        still had the real values."""
        self._item_id = item_id
        self._image_url = image_url
        self._detail = None
        self._enchant_level = preset_enchant
        self._selected_substats = set(preset_substats or ())
        self._selected_substats_order = list(self._selected_substats)
        self._sub_stat_count = 0
        self._philosopher_stone_active = False
        self._character_class = character_class
        self._skill_options = []
        self.enchant_value.setText(f"+{preset_enchant}")
        # Real slider position is set once the item's max enchant level is
        # known, in _apply_detail — the slider has no valid range yet here.
        self.enchant_slider.blockSignals(True)
        self.enchant_slider.setValue(0)
        self.enchant_slider.blockSignals(False)
        self._set_enchant_controls_visible(False)

        self.name_label.setText(name)
        self.header_label.setText(name)
        self.info_label.setText(_t("arm_loading_details"))
        self.main_stats_label.setText("")
        self.substats_header_label.setText("")
        self.substats_status_label.setText("")
        self.skills_label.setText("")
        _clear_layout(self.substats_layout)
        _clear_layout(self.skills_tab_layout)
        self._substat_checkboxes = {}
        self.philosopher_stone_btn.blockSignals(True)
        self.philosopher_stone_btn.setChecked(False)
        self.philosopher_stone_btn.blockSignals(False)
        self.philosopher_stone_btn.setVisible(False)

        cached_icon = self.icon_cache.pixmap(image_url, 140)
        if cached_icon:
            self.icon_label.setPixmap(cached_icon)
        else:
            self.icon_label.setPixmap(QPixmap())
            self.icon_cache.request(image_url)

        cached_detail = self.detail_cache.get(item_id)
        if cached_detail:
            self._apply_detail(cached_detail)
        else:
            self.detail_cache.request(item_id)

    def clear(self):
        """Resets to an empty state — used for an unequipped slot instead
        of load_item (which always expects a real item)."""
        self._item_id = None
        self._image_url = ""
        self._detail = None
        self._enchant_level = 0
        self._selected_substats = set()
        self._selected_substats_order = []
        self._sub_stat_count = 0
        self._philosopher_stone_active = False
        self.icon_label.setPixmap(QPixmap())
        self.icon_label.setStyleSheet("")
        self._icon_glow.setBlurRadius(0)
        self.name_label.setText("")
        self.header_label.setText("")
        self.info_label.setText("")
        self.main_stats_label.setText("")
        self.substats_header_label.setText("")
        self.substats_status_label.setText("")
        self.skills_label.setText("")
        _clear_layout(self.substats_layout)
        _clear_layout(self.skills_tab_layout)
        self._substat_checkboxes = {}
        self.philosopher_stone_btn.blockSignals(True)
        self.philosopher_stone_btn.setChecked(False)
        self.philosopher_stone_btn.blockSignals(False)
        self.philosopher_stone_btn.setVisible(False)
        self._set_enchant_controls_visible(False)

    def on_icon_ready(self, url: str):
        if url == self._image_url:
            grade = self._detail.get("grade") if self._detail else None
            pix = self.icon_cache.pixmap(url, 140, grade=grade)
            if pix:
                self.icon_label.setPixmap(pix)

    def on_detail_ready(self, item_id: int):
        if item_id == self._item_id:
            detail = self.detail_cache.get(item_id)
            if detail:
                self._apply_detail(detail)

    def _apply_detail(self, detail: dict):
        self._detail = detail
        grade_name = detail.get("gradeName") or detail.get("grade") or ""
        category = detail.get("categoryName", "")
        header = " · ".join(p for p in (grade_name, category) if p)
        self.header_label.setText(f"{detail.get('name', '')}<br><span style='font-weight:400;font-size:12px;'>{header}</span>")

        info_lines = []
        if detail.get("equipLevel"):
            info_lines.append(f"Required Level: {detail['equipLevel']}")
        sockets = []
        if detail.get("magicStoneSlotCount"):
            sockets.append(f"{detail['magicStoneSlotCount']} Manastone")
        if detail.get("godStoneSlotCount"):
            sockets.append(f"{detail['godStoneSlotCount']} Godstone")
        if sockets:
            info_lines.append(" / ".join(sockets))
        sources = detail.get("sources") or []
        if sources:
            info_lines.append(f"Quelle: {', '.join(sources)}")
        else:
            info_lines.append("Quelle: unbekannt")
        info_lines.append(f"Handelbar: {'Ja' if detail.get('tradable') else 'Nein'}")
        self.info_label.setText("<br>".join(info_lines))

        # Real API bug found via user report: accessories (Ring/Earrings/
        # Necklace/...) come back with type "Accessory", not "Equip", even
        # though they're just as enchantable as weapons/armor (enchantable:
        # true, real maxEnchantLevel -- confirmed live against shugo.gg's
        # API, e.g. "Wise Dragon Lord Earrings" has maxEnchantLevel 15).
        # Requiring type=="Equip" on top of enchantable hid the slider for
        # every accessory slot -- enchantable alone is already the
        # authoritative signal, so use that on its own.
        is_equipment = bool(detail.get("enchantable"))
        self._set_enchant_controls_visible(bool(is_equipment))
        if is_equipment:
            self._normal_max_enchant = int(detail.get("maxEnchantLevel") or 0)
            self._max_enchant = self._normal_max_enchant + int(detail.get("maxExceedEnchantLevel") or 0)
            # Restore whatever enchant level load_item() was given (0 for a
            # freshly-picked item) now that the slider's real range exists —
            # setting it earlier in load_item() would've just clamped to 0.
            self._enchant_level = min(self._enchant_level, max(self._max_enchant, 0))
            self.enchant_slider.blockSignals(True)
            self.enchant_slider.setMaximum(max(self._max_enchant, 0))
            self.enchant_slider.setValue(self._enchant_level)
            self.enchant_slider.blockSignals(False)
            self.enchant_value.setText(f"+{self._enchant_level}")

        # GRADE_COLORS is keyed by the catalog's grade names (Common/Rare/
        # Unique/Epic/Legend); grade_name above prefers the detail API's
        # gradeName, which calls Epic-tier gear "Heroic" instead — needed
        # for the enchant-rate formulas below, but wrong for color lookup.
        catalog_grade = detail.get("grade") or grade_name
        glow_color = GRADE_COLORS.get(catalog_grade, "#475569")
        self._icon_glow.setColor(QColor(glow_color))
        self._icon_glow.setBlurRadius(30)
        recolored_icon = self.icon_cache.pixmap(self._image_url, 140, grade=catalog_grade)
        if recolored_icon:
            self.icon_label.setPixmap(recolored_icon)

        self._render_stats()

    def _on_enchant_slider_changed(self, value: int):
        if not self._detail:
            return
        self._enchant_level = value
        self.enchant_value.setText(f"+{value}")
        self._render_stats()

    def _render_stats(self):
        if not self._detail:
            return

        # Enchantment only ever boosts the ONE main stat that has a min~max
        # range (Attack for weapons, the analogous defensive stat for
        # armor) — via a flat bonus added on top, shown as "(+N)" exactly
        # like the in-game tooltip. Every other main stat (Accuracy,
        # Critical Hit, Block, ...) never changes, verified against real
        # equipped-item API responses at different enchant levels. Substats
        # are a separate random-roll pool unaffected by enchant entirely —
        # only Soulbinding changes those — so they're always shown unscaled.
        grade_name = self._detail.get("gradeName") or self._detail.get("grade") or ""
        normal_max = getattr(self, "_normal_max_enchant", 0)
        category_name = self._detail.get("categoryName") or ""
        is_armor = category_name in _ARMOR_CATEGORIES or category_name == _BELT_CATEGORY

        # Which stat id(s) scale with enchant, and by how much, depends on
        # the item type: weapons/guards and accessories scale exactly one
        # stat (Attack); armor scales two at once (Defense AND HP).
        if is_armor:
            def_bonus, hp_bonus = estimate_armor_bonus(self._enchant_level, grade_name, normal_max, category_name)
            bonus_map = {_DEFENSE_STAT_ID: def_bonus, _HP_STAT_ID: hp_bonus}
            exceed = estimate_armor_exceed_bonus(self._enchant_level, normal_max)
        else:
            bonus = estimate_enchant_bonus(self._enchant_level, grade_name, normal_max, category_name)
            bonus_map = {_SCALING_STAT_ID: bonus}
            exceed = estimate_exceed_bonus(self._enchant_level, normal_max, category_name)

        def main_stat_line(stat: dict) -> str:
            name = stat.get("name", "")
            value = stat.get("value", "")
            min_value = stat.get("minValue")
            # The stat(s) that scale with enchant are identified by id
            # ("WeaponFixingDamage" = Attack, "ArmorDefense" = Defense,
            # "HPMax" = HP), NOT by whether they happen to have a min~max
            # range — e.g. Greatswords/Staves show Attack as a range, but
            # Guards show the exact same stat as a single flat value. Either
            # way, the base number is ALWAYS shown exactly as in the catalog
            # — never modified — with the enchant bonus as a separate
            # "(+N)" add-on, matching the in-game tooltip style.
            stat_bonus = bonus_map.get(stat.get("id"), 0)
            if stat_bonus:
                if min_value:
                    return f"{name}: {min_value} ~ {value} (+{_format_number(stat_bonus)})"
                return f"{name}: {value} (+{_format_number(stat_bonus)})"
            if min_value and min_value != value:
                return f"{name}: {min_value} ~ {value}"
            return f"{name}: {value}"

        def sub_stat_line(stat: dict) -> str:
            name = stat.get("name", "")
            value = stat.get("value", "")
            min_value = stat.get("minValue")
            if min_value and min_value != value:
                return f"{name}: {min_value} ~ {value}"
            return f"{name}: {value}"

        def badge(text: str, color: str) -> str:
            return (
                f"<span style='background-color:rgba({color},0.18); color:rgb({color}); "
                f"padding:2px 8px; border-radius:6px; font-weight:700; font-size:11px;'>{text}</span>"
            )

        lines = []
        main_stats = self._detail.get("mainStats") or []
        if main_stats:
            item_level = self._detail.get("level")
            if item_level:
                gearscore_push = _gearscore_push(self._enchant_level, normal_max)
                if gearscore_push:
                    lines.append(f"<b>GearScore: {_format_number(item_level)} (+{_format_number(gearscore_push)})</b>")
                else:
                    lines.append(f"<b>GearScore: {_format_number(item_level)}</b>")

            lines.append("<b>Main Stats</b>")
            lines.extend(main_stat_line(s) for s in main_stats)

            orange = "color:#f59e0b;"
            if is_armor:
                if exceed["defense"] or exceed["hp"] or exceed["defense_pct"] or exceed["hp_pct"]:
                    if exceed["defense"]:
                        lines.append(f"<span style='{orange}'>Defense: +{_format_number(exceed['defense'])}</span>")
                    if exceed["hp"]:
                        lines.append(f"<span style='{orange}'>HP: +{_format_number(exceed['hp'])}</span>")
                    if exceed["defense_pct"]:
                        lines.append(f"<span style='{orange}'>Defense increase: +{_format_number(exceed['defense_pct'])}%</span>")
                    if exceed["hp_pct"]:
                        lines.append(f"<span style='{orange}'>HP increase: +{_format_number(exceed['hp_pct'])}%</span>")
            elif exceed["attack"] or exceed["attack_pct"] or exceed["defense"]:
                ranged_stat = next((s for s in main_stats if s.get("id") == _SCALING_STAT_ID), None)
                ranged_name = ranged_stat.get("name", "Attack") if ranged_stat else "Attack"
                if exceed["attack"]:
                    lines.append(f"<span style='{orange}'>{ranged_name}: +{_format_number(exceed['attack'])}</span>")
                if exceed["defense"]:
                    lines.append(f"<span style='{orange}'>Defense: +{_format_number(exceed['defense'])}</span>")
                if exceed["attack_pct"]:
                    lines.append(f"<span style='{orange}'>{ranged_name} increase: +{_format_number(exceed['attack_pct'])}%</span>")

        self.main_stats_label.setText("<br>".join(lines))

        # Substats: real checkbox rows (not rich text) — lets the user mark
        # which rolled value to assume for this item, for later use when
        # reading out aggregate character stats.
        _clear_layout(self.substats_layout)
        _clear_layout(self.skills_tab_layout)
        self._substat_checkboxes = {}

        sub_stats = self._detail.get("subStats") or []
        self._sub_stat_count = int(self._detail.get("subStatCount") or 0)
        self.philosopher_stone_btn.setVisible(
            self._selectable and self._sub_stat_count > 0 and grade_name in ("Unique", "Epic", "Legend")
        )

        # A class-specific skill can be slotted into these same substat
        # slots too, sharing the same budget (confirmed: shugo.gg's real
        # subSkillCountMax always equals subStatCount) -- only offered when
        # load_item() was given a character_class (the Build Planner's
        # equip panel does; the class-agnostic catalog popup doesn't).
        # Weapon/Guard/Ring can take any Active skill, everything else any
        # Passive one (user's own game knowledge -- shugo.gg's API never
        # lists the actual selectable pool, only the slot count).
        skill_type = None
        self._skill_options = []
        if self._character_class:
            skill_type = "active" if category_name in _ACTIVE_SUBSKILL_SLOT_CATEGORIES else "passive"
            class_key = _skills_data_class_key(self._character_class)
            self._skill_options = [
                s for s in self._skills_by_class.get(class_key, []) if s.get("type") == skill_type
            ]

        def make_substat_row(idx: int, text: str) -> QPushButton:
            row_btn = QPushButton()
            row_btn.setObjectName("SubstatRow")
            if self._selectable:
                row_btn.setCheckable(True)
                row_btn.setChecked(idx in self._selected_substats)
                row_btn.setCursor(Qt.PointingHandCursor)
            else:
                # Browse-only mode (plain Item Database popup) -- these rows
                # just list what's POSSIBLE on this item type, not a pick.
                row_btn.setCheckable(False)
                row_btn.setCursor(Qt.ArrowCursor)

            row_layout = QHBoxLayout(row_btn)
            row_layout.setContentsMargins(8, 4, 8, 4)
            row_layout.setSpacing(8)

            check_icon_label = QLabel()
            check_icon_label.setFixedSize(16, 16)
            check_icon_label.setPixmap(_make_check_icon(16))
            check_icon_label.setVisible(self._selectable and idx in self._selected_substats)
            row_layout.addWidget(check_icon_label)

            label = QLabel(text)
            label.setObjectName("DetailInfo")
            row_layout.addWidget(label, 1)

            if self._selectable:
                row_btn.toggled.connect(lambda checked, i=idx: self._on_substat_toggled(i, checked))
            self._substat_checkboxes[idx] = (row_btn, check_icon_label)
            return row_btn

        if sub_stats or self._skill_options:
            total_options = len(sub_stats) + len(self._skill_options)
            slot_hint = (
                _t("arm_slot_hint", rolled=self._sub_stat_count, total=total_options)
                if self._sub_stat_count else ""
            )
            self.substats_header_label.setText(_t("arm_possible_substats_html", slot_hint=slot_hint))
            buckets = {"offensive": [], "defensive": [], "pvp": []}
            for i, s in enumerate(sub_stats):
                if self._only_show_selected and i not in self._selected_substats:
                    continue
                buckets[_classify_stat(s.get("id", ""))].append((i, s))

            def add_accordion_section(target_layout: QVBoxLayout, key: str, badge_text: str, color: str, entries: list):
                # Default: stat buckets start open (unchanged from before),
                # skill buckets start collapsed (they're the longest lists
                # and the reason this panel needed an accordion at all) —
                # only the FIRST time this key is seen; a later re-render
                # (enchant slider moved, item switched) keeps whatever the
                # user last chose for that key.
                is_open = self._substat_section_state.setdefault(key, key not in ("active_skills", "passive_skills"))

                header_btn = QToolButton()
                header_btn.setCheckable(True)
                header_btn.setChecked(is_open)
                header_btn.setCursor(Qt.PointingHandCursor)
                header_btn.setStyleSheet(
                    f"QToolButton {{ background-color: rgba({color},0.18); color: rgb({color}); "
                    "padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 11px; "
                    "border: none; text-align: left; }"
                )
                header_btn.setText(f"{'▾' if is_open else '▸'} {badge_text} ({len(entries)})")
                target_layout.addWidget(header_btn)

                panel = QWidget()
                grid = QGridLayout(panel)
                grid.setContentsMargins(0, 4, 0, 4)
                grid.setSpacing(6)
                panel.setVisible(is_open)
                target_layout.addWidget(panel)

                def _on_toggled(checked: bool, k=key, btn=header_btn, pnl=panel, text=badge_text):
                    self._substat_section_state[k] = checked
                    btn.setText(f"{'▾' if checked else '▸'} {text} ({pnl.layout().count()})")
                    pnl.setVisible(checked)

                header_btn.toggled.connect(_on_toggled)
                return grid

            bucket_meta = [
                ("offensive", _t("arm_badge_offensive"), "56,189,248"),
                ("defensive", _t("arm_badge_defensive"), "74,222,128"),
                ("pvp", _t("arm_badge_pvp"), "244,114,182"),
            ]
            for key, badge_text, color in bucket_meta:
                entries = buckets[key]
                if not entries:
                    continue
                grid = add_accordion_section(self.substats_layout, key, badge_text, color, entries)
                for pos, (i, stat) in enumerate(entries):
                    row_btn = make_substat_row(i, sub_stat_line(stat))
                    grid_row, grid_col = divmod(pos, 2)
                    grid.addWidget(row_btn, grid_row, grid_col)

            if self._skill_options:
                skill_offset = len(sub_stats)
                visible_skills = [
                    (skill_offset + pos, skill) for pos, skill in enumerate(self._skill_options)
                    if not self._only_show_selected or (skill_offset + pos) in self._selected_substats
                ]
                if visible_skills:
                    skill_key = "active_skills" if skill_type == "active" else "passive_skills"
                    skill_badge_text = _t("arm_badge_active_skills") if skill_type == "active" else _t("arm_badge_passive_skills")
                    grid = add_accordion_section(self.skills_tab_layout, skill_key, skill_badge_text, "250,204,21", visible_skills)
                    for pos, (idx, skill) in enumerate(visible_skills):
                        row_btn = make_substat_row(idx, skill.get("name", ""))
                        grid_row, grid_col = divmod(pos, 2)
                        grid.addWidget(row_btn, grid_row, grid_col)
        else:
            self.substats_header_label.setText("")

        self.substats_tabs.setTabVisible(0, bool(sub_stats))
        self.substats_tabs.setTabVisible(1, bool(self._skill_options))
        self.substats_tabs.setVisible(bool(sub_stats) or bool(self._skill_options))
        self._update_substats_status()

        sub_skills = self._detail.get("subSkills") or []
        if sub_skills:
            skill_lines = [badge(_t("arm_badge_possible_skills"), "250,204,21")]
            skill_lines.extend(s.get("name", "") for s in sub_skills)
            self.skills_label.setText("<br>".join(skill_lines))
        else:
            self.skills_label.setText("")

    def _on_substat_toggled(self, index: int, checked: bool):
        if checked:
            self._selected_substats.add(index)
            if index in self._selected_substats_order:
                self._selected_substats_order.remove(index)
            self._selected_substats_order.append(index)
        else:
            self._selected_substats.discard(index)
            if index in self._selected_substats_order:
                self._selected_substats_order.remove(index)
        if self._only_show_selected:
            # Unchecking a row while filtered to "only selected" must drop
            # it from view immediately -- a full re-render (not just the
            # cap/status refresh below) is the only way to remove its row.
            self._render_stats()
        else:
            self._update_substats_status()

    def _on_only_selected_toggled(self, checked: bool):
        self._only_show_selected = checked
        self._render_stats()

    def _on_philosopher_stone_toggled(self, checked: bool):
        self._philosopher_stone_active = checked
        if not checked:
            # Dropping the Stone lowers the cap by 1 — if that leaves one
            # substat over the new cap, drop the most-recently-picked one
            # (whichever row happens to be selected last) rather than
            # showing an impossible "5/4" over-cap state.
            cap = self._effective_substat_cap()
            while self._selected_substats_order and len(self._selected_substats) > cap:
                drop_index = self._selected_substats_order.pop()
                self._selected_substats.discard(drop_index)
                row = self._substat_checkboxes.get(drop_index)
                if row:
                    row_btn, _ = row
                    row_btn.blockSignals(True)
                    row_btn.setChecked(False)
                    row_btn.blockSignals(False)
        self._update_substats_status()

    def _effective_substat_cap(self) -> int:
        if not self._sub_stat_count:
            return 0
        return self._sub_stat_count + (1 if self._philosopher_stone_active else 0)

    def _update_substats_status(self):
        if not self._selectable:
            # Nothing to report a "X/Y selected" count for in browse-only
            # mode -- there's no selection at all (see make_substat_row).
            self.substats_status_label.setText("")
            return
        if not self._sub_stat_count:
            self.substats_status_label.setText("")
            return
        cap = self._effective_substat_cap()
        selected = len(self._selected_substats)

        # Once the cap is reached, block picking any further substat — only
        # unchecking an already-selected one (to swap it) stays possible.
        at_cap = selected >= cap
        for idx, (row_btn, check_icon_label) in self._substat_checkboxes.items():
            row_btn.setEnabled(not at_cap or idx in self._selected_substats)
            check_icon_label.setVisible(row_btn.isChecked())

        stone_note = _t("arm_stone_note_suffix") if self._philosopher_stone_active else ""
        if at_cap:
            self.substats_status_label.setText(
                _t("arm_all_substats_selected_html", selected=selected, cap=cap, stone_note=stone_note)
            )
        else:
            self.substats_status_label.setText(
                _t("arm_substats_selected_count_html", selected=selected, cap=cap, stone_note=stone_note)
            )

    def get_selected_substats(self) -> list[dict]:
        """The subStats entries the user has checked — for later use when
        aggregating assumed character stats across the loadout. Selected
        class-skill picks (indices >= len(sub_stats), see _render_stats)
        aren't included here -- they aren't a stat bonus, use
        get_selected_skill_options() for those."""
        sub_stats = (self._detail or {}).get("subStats") or []
        return [sub_stats[i] for i in sorted(self._selected_substats) if i < len(sub_stats)]

    def get_selected_skill_options(self) -> list[dict]:
        """The class-skill substat picks the user has checked (see
        _render_stats's combined stats+skills index space)."""
        sub_stats = (self._detail or {}).get("subStats") or []
        offset = len(sub_stats)
        return [
            self._skill_options[i - offset] for i in sorted(self._selected_substats)
            if i >= offset and (i - offset) < len(self._skill_options)
        ]

    def get_selected_substat_indices(self) -> set[int]:
        return set(self._selected_substats)

    def get_enchant_level(self) -> int:
        return self._enchant_level


class ItemDetailDialog(QDialog):
    def __init__(self, icon_cache: "IconCache", detail_cache: "ItemDetailCache", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle(_t("arm_item_details_title"))
        self.setMinimumSize(560, 340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        self.detail_widget = ItemDetailWidget(icon_cache, detail_cache, self, selectable=False)
        layout.addWidget(self.detail_widget)

        icon_cache.icon_ready.connect(self.detail_widget.on_icon_ready)
        detail_cache.detail_ready.connect(self.detail_widget.on_detail_ready)

    def load_item(self, item_id: int, name: str, image_url: str):
        self.detail_widget.load_item(item_id, name, image_url)



# (slot_id, label, valid categoryName values) — ordered as a 2-column grid,
# two consecutive entries form one row, matching the requested paperdoll layout.
# label is a translation KEY, not display text (module-level -- see
# _QUICK_GEAR_SLOT_LABELS for why) -- _slot_info() translates it at actual
# use time, the one place every caller reads it through.
SLOT_LAYOUT = [
    ("MainHand", "arm_slot_mainhand", ["Greatsword", "Longsword", "Dagger", "Bow", "Spellbook", "Orb", "Mace", "Staff", "Fist"]),
    ("SubHand", "arm_slot_subhand", ["Guard"]),
    ("Helmet", "arm_slot_helmet", ["Helm"]),
    ("Shoulder", "arm_slot_shoulder", ["Pauldrons"]),
    ("Torso", "arm_slot_torso", ["Top"]),
    ("Gloves", "arm_slot_gloves", ["Gloves"]),
    ("Pants", "arm_slot_pants", ["Legs"]),
    ("Boots", "arm_slot_boots", ["Shoes"]),
    ("Earring1", "arm_slot_earrings_plural", ["Earrings"]),
    ("Earring2", "arm_slot_earrings_plural", ["Earrings"]),
    ("Necklace", "arm_slot_necklace", ["Necklace"]),
    ("Amulet", "arm_slot_amulet", ["Amulet"]),
    ("Ring1", "arm_slot_rings_plural", ["Ring"]),
    ("Ring2", "arm_slot_rings_plural", ["Ring"]),
    ("Bracelet1", "arm_slot_bracelet", ["Bracelet"]),
    ("Bracelet2", "arm_slot_bracelet", ["Bracelet"]),
    ("Brooch1", "arm_slot_brooch", ["Brooch"]),
    ("Brooch2", "arm_slot_brooch", ["Brooch"]),
]

SLOT_BUTTON_SIZE = 76

# Distinguishes real equipment slots (which get the inline "Equipment Item"
# panel) from Arcana slots, which reuse _pick_for_slot but still use the
# old popup-based detail view since there's no inline panel for that tab.
_EQUIP_SLOT_IDS = {slot_id for slot_id, _, _ in SLOT_LAYOUT}

# Groups the paperdoll slots under category headers — Weapon+Armor sit in
# the left column, Accessory in the right one, either side of Stat Info.
# 1st element is a translation KEY, not display text (module-level -- see
# _QUICK_GEAR_SLOT_LABELS for why) -- translated in _build_slot_sections().
_LEFT_EQUIP_SECTIONS = [
    ("arm_section_weapon", ["MainHand", "SubHand"]),
    ("arm_section_armor", ["Helmet", "Shoulder", "Torso", "Gloves", "Pants", "Boots"]),
]
# Brooch doesn't exist yet at global release — excluded from the active
# slot set for now (still defined in SLOT_LAYOUT above for whenever it's
# added back). Bracelet's global-launch status is unconfirmed — left in.
_RIGHT_EQUIP_SECTIONS = [
    ("arm_section_accessory", ["Earring1", "Earring2", "Necklace", "Amulet", "Ring1", "Ring2", "Bracelet1", "Bracelet2"]),
]

# Equipment Priority List — same idea as the Skill Planner's own priority
# list (a chain of slots per section, "+" to append), just for planning an
# acquisition/upgrade order across specific items instead of skills.
#
# One section per real equip slot category (same single-category
# granularity _pick_for_slot already uses for every real Equipment-tab
# slot) rather than one combined "Waffen/Rüstung/Schmuck" bucket each —
# combining all 6 armor categories into one picker was ~1984 items and
# took 6+ seconds to build (reported as a hang/error), vs. ~330 for any
# single real armor category, which is the same scale every other picker
# in the app already handles fine. "weapon" (MainHand) and "guard"
# (SubHand) are split into their own sections, mirroring SLOT_LAYOUT —
# combining them into one chain made no sense, since both are equipped at
# once rather than one replacing the other. "weapon" still gets narrowed
# further to the current class's one weapon category at click time (see
# _on_equip_priority_slot_clicked), same as _pick_for_slot does for
# MainHand — the full list here is just the fallback if that lookup ever
# comes back empty.
#
# Amulet, Bracelet and Brooch are excluded — no priority list needed for
# these (per user instruction). Devotion/Clash Rune has no priority list
# either — Rune isn't a real equip slot in SLOT_LAYOUT to begin with.
# 2nd element is a translation KEY, not display text (module-level -- see
# _QUICK_GEAR_SLOT_LABELS for why).
_EQUIP_PRIORITY_SECTIONS = [
    ("weapon", "arm_section_weapon", ["Greatsword", "Longsword", "Dagger", "Bow", "Spellbook", "Orb", "Mace", "Staff", "Fist"]),
    ("guard", "arm_slot_subhand", ["Guard"]),
    ("helm", "arm_slot_helmet", ["Helm"]),
    ("shoulder", "arm_slot_shoulder", ["Pauldrons"]),
    ("torso", "arm_slot_torso", ["Top"]),
    ("gloves", "arm_slot_gloves", ["Gloves"]),
    ("legs", "arm_slot_pants", ["Legs"]),
    ("shoes", "arm_slot_boots", ["Shoes"]),
    ("earrings", "arm_slot_earrings_plural", ["Earrings"]),
    ("necklace", "arm_slot_necklace", ["Necklace"]),
    ("ring", "arm_slot_rings_plural", ["Ring"]),
]

# Max chain length per section — an acquisition/upgrade order realistically
# only needs a handful of steps; unbounded chains would also grow each
# section box past its 3-column grid cell.
_EQUIP_PRIORITY_MAX_ITEMS = 5

# Real Arcana data — extracted from shugo.gg's own item catalog (categoryName
# "Arcana", data/arcana_info.json via fetch_arcana_info.py) + questlog.gg's
# character-builder API (data/arcana_class_skills.json via
# fetch_arcana_class_skills.py). All 10 card types are confirmed live —
# verified via two real TW characters' actual equipped Arcana slots
# (slotPos 41-50, "Arcana1".."Arcana10" — both characters had all 10
# positions filled/fillable), contradicting an earlier assumption that only
# 5 types (Chalice/Parchment/Compass/Bell/Mirror) existed yet.
#
# 6 "Lord cards" (Chalice/Parchment/Compass/Bell/Mirror/Scales) are each
# bound to one of two Empyrean Lords depending on theme, and grant Skill
# Levels (Mastery/Active/Passive, fixed per card type) for a class-specific
# skill pool. The other 4 "Stat cards" (Key/Hourglass/Dice/Lantern) grant a
# fixed main stat + random substats and have no skill pool at all — they
# only exist at Unique grade with 3 themes (Punishment/Protection/
# Indomitability), unlike the 6 Lord cards which have Rare/Legend/Unique
# across all 7 themes (Scales missing Magic/Vigor).
ARCANA_CARD_TYPES = [
    "Chalice", "Parchment", "Compass", "Bell", "Mirror", "Scales",
    "Key", "Hourglass", "Dice", "Lantern",
]
ARCANA_THEME_ORDER = ["Vigor", "Magic", "Frenzy", "Purity", "Punishment", "Protection", "Indomitability"]

# Real Empyrean Lord stat effects — each Lord's value scales two stats at
# once by the same percentage, confirmed via a real character's own stat
# report (shugo.gg character/info endpoint, TW character "Skyvie").
ARCANA_LORD_EFFECTS = {
    "Time": "Combat Speed / Smite Resist",
    "Freedom": "Accuracy / Evasion",
    "Destruction": "Attack Increase / Perfect Resist",
    "Illusion": "Cooldown Reduction / Endurance Penetration",
    "Destiny": "MP Increase / Endurance",
    "Wisdom": "MP Cost / Smite",
    "Justice": "Defense Increase / Perfect Chance",
    "Life": "HP Increase / Regeneration",
    "Death": "Critical Hit Increase / Regeneration Penetration",
    "Space": "Move Speed / Block Increase",
}

# Set-bonus text — community source (aion2hub.com/database/sets), NOT
# officially confirmed by NCSoft. That page's "20/24/26 Piece" headers per
# set don't obviously map onto the 10-slot Arcana system, so only the
# 2pc/4pc effect text is used here, not those piece counts.
ARCANA_SET_BONUSES = {
    "Vigor": {"setName": "Primal Vigor", "2pc": "+60 PvE Attack bei HP ≥70%", "4pc": "+150 PvE Attack bei HP ≥70%"},
    "Magic": {"setName": "Magic Armor", "2pc": "Erstattet 1.500 MP bei MP ≤20% (30s Cooldown)", "4pc": "+1.000 PvE Defense bei MP ≥50%"},
    "Frenzy": {"setName": "Frenzy", "2pc": "+50 PvE Attack", "4pc": "+5% Boss Damage Boost, +10% Boss Damage Tolerance bei HP ≤70%"},
    "Purity": {"setName": "Pure Blood", "2pc": "+500 PvE Defense", "4pc": "+5% Critical Damage Boost, +1.000 Defense bei HP ≤70%"},
    "Punishment": {"setName": "Punishing Overture", "2pc": "+5% Boss Damage Tolerance", "4pc": "+60 PvE Attack, +10% PvE Damage Boost bei HP ≥70%"},
    "Protection": {"setName": "Protected Soul", "2pc": "+5% Restoration", "4pc": "+5% Weapon Damage Boost, Schutzschild (10.000 Schaden, 5s) bei HP ≤30% (2min Cooldown)"},
    "Indomitability": {"setName": "Indomitable Dedication", "2pc": "+5% Weapon Damage Tolerance", "4pc": "+5% Critical Damage Tolerance, +50% PvP Damage Tolerance für 5s bei Stun/Knockdown/Airborne/Grab/Frost/Fear"},
}

# Theme -> UI category, derived from each theme's internal icon-filename
# set-label (PveSetN/PvpSetN/OffenseSetN/DefenceSetN/CureSetN — see
# fetch_arcana_info.py). Purely a display grouping, not an in-game name.
ARCANA_THEME_CATEGORY = {
    "Vigor": "pve", "Punishment": "pve", "Frenzy": "offense",
    "Magic": "defence", "Purity": "defence", "Protection": "cure", "Indomitability": "pvp",
}
ARCANA_CATEGORY_COLORS = {
    "pve": "#4ade80", "pvp": "#fb7185", "offense": "#f59e0b", "defence": "#38bdf8", "cure": "#a855f7",
}
ARCANA_CATEGORY_LABELS = {"pve": "PvE", "pvp": "PvP", "offense": "Offensiv", "defence": "Defensiv", "cure": "Heilung"}
# Fixed width for the whole left column (Keine Sets + 7 banners + bonus
# panel) — kept constant regardless of window size or content so the
# banners never stretch/shrink oddly next to the card grid.
_ARCANA_SET_COLUMN_WIDTH = 220

ARCANA_DATA_PATH = _BUNDLE_DIR / "data" / "arcana_info.json"
ARCANA_CLASS_SKILLS_PATH = _BUNDLE_DIR / "data" / "arcana_class_skills.json"
ARCANA_ICON_DIR = _BUNDLE_DIR / "assets" / "arcana_icons"


def _load_arcana_theme_map() -> tuple[dict, dict]:
    """Returns (theme_map, default_icon). theme_map[theme][cardType] = {
    iconFile, lord, mainStat, grades} for every real (cardType, theme)
    combo that actually exists in the catalog; default_icon[cardType] is
    the icon shown before any set is chosen (Vigor's variant, falling back
    to Punishment for the 4 Stat cards, which have no Vigor entry)."""
    if not ARCANA_DATA_PATH.exists():
        return {}, {}
    arcana = json.loads(ARCANA_DATA_PATH.read_text(encoding="utf-8"))["arcana"]
    theme_map: dict[str, dict] = {}
    for theme in ARCANA_THEME_ORDER:
        theme_map[theme] = {}
        for ct in ARCANA_CARD_TYPES:
            entries = [a for a in arcana if a["theme"] == theme and a["cardType"] == ct]
            if not entries:
                continue
            grades = sorted(set(a["grade"] for a in entries), key=lambda g: RARITY_RANK.get(g, 99))
            e = entries[0]
            theme_map[theme][ct] = {
                "iconFile": e["iconFile"],
                "lord": e.get("empyreanLord"),
                "mainStat": e.get("mainStat"),
                "grades": grades,
            }
    default_icon: dict[str, str] = {}
    for ct in ARCANA_CARD_TYPES:
        for theme in ("Vigor", "Punishment"):
            entry = theme_map.get(theme, {}).get(ct)
            if entry:
                default_icon[ct] = entry["iconFile"]
                break
    return theme_map, default_icon


def _load_arcana_class_skills() -> dict:
    """cardType -> class -> [{id, name, type, levelBase, levelMax}, ...].
    Grade is dropped entirely: the skill pool and level range are confirmed
    identical across Common/Rare/Legend/Unique for every card type + class
    (0 mismatches checked across the full dataset), so there's no need to
    pick a grade to look this up — see fetch_arcana_class_skills.py."""
    if not ARCANA_CLASS_SKILLS_PATH.exists():
        return {}
    raw = json.loads(ARCANA_CLASS_SKILLS_PATH.read_text(encoding="utf-8"))
    result: dict[str, dict[str, list]] = {}
    for card_type, grades in raw.items():
        pool = grades.get("Unique") or next(iter(grades.values()), {})
        result[card_type] = pool
    return result


def _arcana_icon(icon_file: str | None, size: int = 64) -> QPixmap | None:
    if not icon_file:
        return None
    path = ARCANA_ICON_DIR / icon_file
    if not path.exists():
        return None
    pix = QPixmap(str(path))
    if pix.isNull():
        return None
    return pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

# Each AION2 class uses exactly one weapon category (verified 1:1 in the data
# via each weapon's own classNames field) — used to narrow the MainHand
# picker down once a character class is chosen.
CLASS_WEAPON_CATEGORY = {
    "Gladiator": "Greatsword",
    "Templar": "Longsword",
    "Assassin": "Dagger",
    "Ranger": "Bow",
    "Sorcerer": "Spellbook",
    "Spiritmaster": "Orb",
    "Cleric": "Mace",
    "Chanter": "Staff",
    "Brawler": "Fist",
}

# App-wide display name is "Spiritmaster" (2026-08-24, user decision) --
# matches shugo.gg's own item database (all 218 real Orb items' classNames,
# and its class-filter dropdown, both say "Spiritmaster") rather than
# "Elementalist". skills_all.json's own mainCategory field still uses the
# older "elementalist" key though (that data source was never renamed) --
# any lookup into skills-data-derived structures (_skills_by_class,
# _CLASS_RELEVANT_CHANCE_EFFECTS) needs this alias, see
# _skills_data_class_key().
_SKILLS_DATA_CLASS_ALIASES = {"spiritmaster": "elementalist"}


def _skills_data_class_key(display_name: str) -> str:
    key = (display_name or "").strip().lower()
    return _SKILLS_DATA_CLASS_ALIASES.get(key, key)


# Tile size for ItemPickerPopup's grid (was a single full-width column) —
# sized so 3 tiles fit across the popup's fixed width, per user request to
# cap the count of items shown per row at 3-4 rather than a single long
# vertical scroll for a 200-330 item category.
_PICKER_TILE_WIDTH = 124
_PICKER_TILE_HEIGHT = 118


class ItemPickerPopup(QWidget):
    """Anchored, borderless search+pick list — a Qt.Popup positioned right
    under whichever button opened it (combo button, slot's change button)
    instead of a separate modal window. Auto-dismisses on an outside click
    or item pick, like a native combo-box dropdown."""

    item_chosen = Signal(dict)

    def __init__(
        self, items: list[dict], categories: list[str],
        icon_cache: "IconCache", detail_cache: "ItemDetailCache", parent=None,
        active_gear_types: set | None = None, equipped_ids: set | None = None,
    ):
        super().__init__(parent, Qt.Popup)
        self.setObjectName("ItemPickerPopup")
        # Wide enough for 3 tiles of _PICKER_TILE_WIDTH per row plus margins
        # and the vertical scrollbar.
        self.setFixedWidth(3 * _PICKER_TILE_WIDTH + 40)
        self.setMinimumHeight(420)

        self._items = [i for i in items if i.get("categoryName") in categories]
        self.icon_cache = icon_cache
        self.detail_cache = detail_cache
        # Set by the persistent PvP/PvE/Neutral toggle up in the header row
        # (next to the class selector) — not owned by this popup since it's
        # recreated fresh on every slot click.
        self._active_gear_types = active_gear_types or set()
        # Item ids currently equipped in the Build Planner (User-Wunsch, EQ-
        # Priority tab only: "eine Checkbox, die die Items anzeigt, die im
        # Buildplanner eingesetzt sind, verfügbar, sofern welche eingesetzt
        # sind") -- only passed by the EQ-Priority picker, so the checkbox
        # stays absent everywhere else (e.g. the main Equipment tab's own
        # slot picker never passes this).
        self._equipped_ids = equipped_ids or set()
        self._show_equipped_only = False
        self._sort_key = "name"
        # Rebuilt on every _refresh_list() call — maps an icon URL / item id
        # to the currently-visible row label(s) (with that row's own grade,
        # for the correct rarity texture) waiting on async icon/level data,
        # so a late icon_ready/detail_ready still finds the right row.
        self._icon_labels: dict[str, list[tuple[QLabel, str | None]]] = {}
        self._level_labels: dict[int, QLabel] = {}
        # (url, grade) per row, in list order — only rows actually scrolled
        # into view get their icon requested (see _request_visible_icons);
        # requesting all of them up front queued behind Qt's per-host
        # concurrent-connection cap for a large category and made most rows
        # sit blank for a long time even though nothing was actually broken.
        self._row_icon_queue: list[tuple[str, str | None]] = []
        icon_cache.icon_ready.connect(self._on_icon_ready)
        detail_cache.detail_ready.connect(self._on_detail_ready)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        filter_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_t("arm_search_placeholder"))
        self.search_input.textChanged.connect(self._refresh_list)
        filter_row.addWidget(self.search_input, 1)

        self.grade_combo = QComboBox()
        self._populate_grade_combo()
        self.grade_combo.currentIndexChanged.connect(self._refresh_list)
        filter_row.addWidget(self.grade_combo)
        layout.addLayout(filter_row)

        sort_row = QHBoxLayout()
        sort_label = QLabel(_t("arm_sort_by_label"))
        sort_label.setObjectName("EquipSectionLabel")
        sort_row.addWidget(sort_label)
        self._sort_ascending = True
        self._sort_labels: dict[str, str] = {}
        self._sort_buttons: dict[str, QPushButton] = {}
        self._sort_group = QButtonGroup(self)
        self._sort_group.setExclusive(True)
        for key, label in (("name", "Name"), ("grade", "Seltenheit"), ("type", "Typ")):
            self._sort_labels[key] = label
            btn = QPushButton(label)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(key == "name")
            btn.setMinimumHeight(28)
            btn.clicked.connect(lambda _c=False, k=key: self._on_sort_changed(k))
            self._sort_group.addButton(btn)
            self._sort_buttons[key] = btn
            sort_row.addWidget(btn)
        sort_row.addStretch()
        layout.addLayout(sort_row)
        self._update_sort_button_labels()

        # Only shown when there's actually something equipped to filter by
        # (User-Wunsch: "verfügbar, sofern welche eingesetzt sind").
        self.equipped_only_check = QCheckBox(_t("arm_only_equipped_items"))
        self.equipped_only_check.setVisible(bool(self._equipped_ids))
        self.equipped_only_check.toggled.connect(self._on_equipped_only_toggled)
        layout.addWidget(self.equipped_only_check)

        # Multi-column tile grid (was a single-column list of full-width
        # rows) — a category with 200-330 items made for a very long single
        # scroll; IconMode with a fixed grid size flows tiles left-to-right
        # and wraps, same underlying QListWidget/QListWidgetItem machinery.
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setFlow(QListWidget.LeftToRight)
        self.list_widget.setWrapping(True)
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setMovement(QListWidget.Static)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.setGridSize(QSize(_PICKER_TILE_WIDTH, _PICKER_TILE_HEIGHT))
        self.list_widget.setSpacing(0)
        self.list_widget.itemClicked.connect(self._choose)
        self.list_widget.verticalScrollBar().valueChanged.connect(self._request_visible_icons)
        layout.addWidget(self.list_widget, 1)

        self._refresh_list()
        QTimer.singleShot(0, self._request_visible_icons)

    def _populate_grade_combo(self):
        counts: dict[str, int] = {}
        for i in self._items:
            g = i.get("grade")
            if g:
                counts[g] = counts.get(g, 0) + 1

        model = QStandardItemModel(self.grade_combo)
        all_item = QStandardItem(f"All ({len(self._items)})")
        all_item.setData("All", Qt.UserRole)
        model.appendRow(all_item)
        for grade in RARITY_ORDER:
            count = counts.get(grade)
            if not count:
                continue
            item = QStandardItem(f"{grade} ({count})")
            item.setData(grade, Qt.UserRole)
            item.setForeground(QColor(GRADE_COLORS[grade]))
            model.appendRow(item)
        self.grade_combo.setModel(model)

    def _on_sort_changed(self, key: str):
        if key == self._sort_key:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_key = key
            self._sort_ascending = True
        self._update_sort_button_labels()
        self._refresh_list()

    def _on_equipped_only_toggled(self, checked: bool):
        self._show_equipped_only = checked
        self._refresh_list()

    def _update_sort_button_labels(self):
        arrow = "▲" if self._sort_ascending else "▼"
        for key, btn in self._sort_buttons.items():
            label = self._sort_labels[key]
            btn.setText(f"{label} {arrow}" if key == self._sort_key else label)

    def _sort_items(self, items: list[dict]) -> list[dict]:
        reverse = not self._sort_ascending
        if self._sort_key == "grade":
            return sorted(items, key=lambda i: (RARITY_RANK.get(i.get("grade"), 99), i.get("name", "")), reverse=reverse)
        if self._sort_key == "type":
            return sorted(items, key=lambda i: (i.get("categoryName", ""), i.get("name", "")), reverse=reverse)
        return sorted(items, key=lambda i: i.get("name", ""), reverse=reverse)

    def _refresh_list(self):
        query = self.search_input.text().strip().lower()
        grade_filter = self.grade_combo.currentData()
        self.list_widget.clear()
        self._icon_labels = {}
        self._level_labels = {}
        self._row_icon_queue = []
        visible_ids = []

        matched = [
            item for item in self._items
            if (not query or query in item.get("name", "").lower())
            and (grade_filter in (None, "All") or item.get("grade") == grade_filter)
            and (not self._active_gear_types or _gear_type(item) in self._active_gear_types)
            and (not self._show_equipped_only or item.get("id") in self._equipped_ids)
        ]
        for item in self._sort_items(matched):
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, item)

            # Vertical tile (icon on top, name + level below) instead of a
            # full-width horizontal row — fits a grid of _PICKER_TILE_WIDTH
            # columns rather than one long single-column scroll.
            row_widget = QWidget()
            row_widget.setFixedSize(_PICKER_TILE_WIDTH, _PICKER_TILE_HEIGHT)
            row_layout = QVBoxLayout(row_widget)
            row_layout.setContentsMargins(6, 8, 6, 8)
            row_layout.setSpacing(4)
            row_layout.setAlignment(Qt.AlignHCenter)

            grade_color = GRADE_COLORS.get(item.get("grade"), "#94a3b8")

            icon_label = QLabel()
            icon_label.setFixedSize(40, 40)
            icon_label.setAlignment(Qt.AlignCenter)
            image_url = item.get("image", "")
            item_grade = item.get("grade")
            cached_icon = self.icon_cache.pixmap(image_url, 40, grade=item_grade)
            if cached_icon:
                icon_label.setPixmap(cached_icon)
            if image_url:
                self._icon_labels.setdefault(image_url, []).append((icon_label, item_grade))
            self._row_icon_queue.append((image_url, item_grade))
            row_layout.addWidget(icon_label, 0, Qt.AlignHCenter)

            full_name = item.get("name", "")
            # No word-wrap: computing wrapped-text layout for every single
            # tile (not just visible ones) turned out to be the actual
            # remaining slow part after switching to a grid — truncating to
            # one line via character count is just as readable here (full
            # name is still in the tooltip) and much cheaper to lay out.
            name_label = QLabel(_short_skill_name(full_name, 16))
            name_label.setStyleSheet(f"color: {grade_color}; font-weight: 600; font-size: 11px;")
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setToolTip(full_name)
            row_layout.addWidget(name_label)

            level_label = QLabel("")
            level_label.setStyleSheet("color: #94a3b8; font-size: 10px;")
            level_label.setAlignment(Qt.AlignCenter)
            row_layout.addWidget(level_label)

            item_id = item.get("id")
            cached_detail = self.detail_cache.get(item_id) if item_id else None
            if cached_detail and cached_detail.get("equipLevel"):
                level_label.setText(_t("arm_level_prefix", level=cached_detail['equipLevel']))
            elif item_id:
                self._level_labels[item_id] = level_label
                visible_ids.append(item_id)

            list_item.setSizeHint(QSize(_PICKER_TILE_WIDTH, _PICKER_TILE_HEIGHT))
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, row_widget)

        if visible_ids:
            self.detail_cache.request_many(visible_ids)

        self._request_visible_icons()

    def _request_visible_icons(self, *_args):
        count = self.list_widget.count()
        if count == 0:
            return
        # bottomRIGHT, not bottomLeft — in the tile grid (left-to-right,
        # wrapping), indexAt(bottomLeft) only hits the first tile of the
        # last visible row, so the old row-based range would've only ever
        # covered one item per row instead of the whole visible block.
        top_idx = self.list_widget.indexAt(self.list_widget.viewport().rect().topLeft())
        bottom_idx = self.list_widget.indexAt(self.list_widget.viewport().rect().bottomRight())
        top_row = top_idx.row() if top_idx.isValid() else 0
        bottom_row = bottom_idx.row() if bottom_idx.isValid() else count - 1
        if bottom_row < 0:
            bottom_row = count - 1

        # Buffer scaled up 3x from the old single-column value (6) since a
        # linear index range now spans 3 grid rows per 3 units instead of 1.
        buffer = 6 * 3
        start = max(0, top_row - buffer)
        end = min(count - 1, bottom_row + buffer)
        for row in range(start, end + 1):
            if row >= len(self._row_icon_queue):
                continue
            url, grade = self._row_icon_queue[row]
            if url and self.icon_cache.pixmap(url, 40, grade=grade) is None:
                self.icon_cache.request(url)

    def _on_icon_ready(self, url: str):
        entries = self._icon_labels.get(url)
        if not entries:
            return
        for label, grade in entries:
            pix = self.icon_cache.pixmap(url, 40, grade=grade)
            if pix:
                label.setPixmap(pix)

    def _on_detail_ready(self, item_id: int):
        label = self._level_labels.get(item_id)
        if not label:
            return
        detail = self.detail_cache.get(item_id)
        if detail and detail.get("equipLevel"):
            label.setText(_t("arm_level_prefix", level=detail['equipLevel']))

    def _choose(self, list_item: QListWidgetItem):
        item = list_item.data(Qt.UserRole)
        if item:
            self.item_chosen.emit(item)
        self.close()

    def show_anchored(self, anchor: QWidget):
        self.move(anchor.mapToGlobal(QPoint(0, anchor.height())))
        self.show()
        self.search_input.setFocus()


class _ArcanaCardButton(QPushButton):
    """One of the 10 Arcana card slots. Before any Set is chosen it shows a
    neutral default icon ("Leer"); once a Set is active it either shows
    that card's real Lord (+ its stat effect) or Main Stat (for the 4 Stat
    cards, which have no Lord/skills), plus a colored dot per grade this
    combo actually has — or, if this card type doesn't exist in the chosen
    theme at all (e.g. Scales has no Vigor/Magic variant), a clearly
    dashed-border "Nicht verfügbar" state. Clicking only does something for
    an available Lord card (opens the real per-class skill popover)."""

    def __init__(self, card_type: str, parent=None):
        super().__init__(parent)
        self.card_type = card_type
        self.entry: dict | None = None
        self.setObjectName("ArcanaCardButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(148, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setSpacing(6)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(64, 64)
        self.icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_label, 0, Qt.AlignHCenter)

        self.name_label = QLabel(card_type)
        self.name_label.setObjectName("ArcanaCardName")
        self.name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.name_label)

        self.info_label = QLabel()
        self.info_label.setObjectName("ArcanaCardInfo")
        self.info_label.setTextFormat(Qt.RichText)
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.hint_label = QLabel()
        self.hint_label.setObjectName("ArcanaCardHint")
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.grade_label = QLabel()
        self.grade_label.setTextFormat(Qt.RichText)
        self.grade_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.grade_label)

        layout.addStretch()

    def _restyle(self):
        self.style().unpolish(self)
        self.style().polish(self)

    def set_default_state(self, icon_file: str | None):
        self.entry = None
        self.setProperty("state", "default")
        pix = _arcana_icon(icon_file, 56)
        self.icon_label.setPixmap(pix if pix else QPixmap())
        self.name_label.setVisible(True)
        self.info_label.setText("")
        self.hint_label.setText(_t("arm_empty"))
        self.grade_label.setText("")
        self._restyle()

    def set_unavailable_state(self):
        self.entry = None
        self.setProperty("state", "unavailable")
        self.icon_label.setPixmap(QPixmap())
        self.name_label.setVisible(False)
        self.info_label.setText("")
        self.hint_label.setText(_t("arm_not_available"))
        self.grade_label.setText("")
        self._restyle()

    def set_themed_state(self, entry: dict):
        self.entry = entry
        self.setProperty("state", "themed")
        pix = _arcana_icon(entry["iconFile"], 56)
        self.icon_label.setPixmap(pix if pix else QPixmap())
        self.name_label.setVisible(True)
        if entry.get("lord"):
            effect = ARCANA_LORD_EFFECTS.get(entry["lord"], "")
            self.info_label.setText(
                f'<span style="color:#facc15;font-weight:700;">{entry["lord"]}</span><br>'
                f'<span style="font-size:10px;color:#64748b;">{effect}</span>'
            )
        else:
            self.info_label.setText(
                f'<span style="color:#facc15;font-weight:700;">{entry.get("mainStat", "")}</span><br>'
                f'<span style="font-size:10px;color:#64748b;">{_t("arm_random_substats_suffix")}</span>'
            )
        self.hint_label.setText("")
        dots = " ".join(
            f'<span style="color:{GRADE_COLORS.get(g, "#94a3b8")};">&#9679;</span>'
            for g in ("Common", "Rare", "Legend", "Unique") if g in entry["grades"]
        )
        self.grade_label.setText(dots)
        self._restyle()


class _ArcanaSkillPopup(QWidget):
    """Anchored popover (Qt.Popup, same anchoring idea as ItemPickerPopup)
    showing the real class-specific skill pool for one Arcana card type,
    split Active/Passive with each skill's real level range — opened by
    clicking an available Lord card."""

    def __init__(self, card_type: str, class_label: str, skills: list[dict], parent=None):
        super().__init__(parent, Qt.Popup)
        self.setObjectName("ArcanaSkillPopup")
        self.setFixedWidth(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        header = QLabel(_t("arm_skills_for", card=card_type, class_name=class_label))
        header.setObjectName("DetailName")
        header.setWordWrap(True)
        layout.addWidget(header)

        source = QLabel(_t("arm_source_questlog"))
        source.setObjectName("DetailDisclaimer")
        layout.addWidget(source)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        active_skills = [s for s in skills if s.get("type") == "active"]
        passive_skills = [s for s in skills if s.get("type") == "passive"]
        columns.addLayout(self._build_column(_t("arm_active"), active_skills))
        columns.addLayout(self._build_column(_t("arm_passive"), passive_skills))
        layout.addLayout(columns)

    @staticmethod
    def _build_column(title: str, skills: list[dict]) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(4)
        head = QLabel(f"{title} ({len(skills)})")
        head.setObjectName("EquipSectionLabel")
        col.addWidget(head)
        if not skills:
            empty = QLabel(_t("arm_none"))
            empty.setObjectName("DetailDisclaimer")
            col.addWidget(empty)
        for skill in skills:
            row = QLabel(
                f'{skill["name"]} <span style="color:#facc15;font-weight:700;">'
                f'+{skill["levelBase"]}–{skill["levelMax"]}</span>'
            )
            row.setTextFormat(Qt.RichText)
            row.setObjectName("DetailInfo")
            row.setWordWrap(True)
            col.addWidget(row)
        col.addStretch()
        return col

    def show_anchored(self, anchor: QWidget):
        self.adjustSize()
        top_left = anchor.mapToGlobal(QPoint(0, 0))
        anchor_bottom = anchor.mapToGlobal(QPoint(0, anchor.height())).y()
        screen = anchor.screen() or QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        x = min(max(top_left.x(), screen_geo.left()), screen_geo.right() - self.width())
        space_below = screen_geo.bottom() - anchor_bottom
        y = anchor_bottom + 8 if space_below >= self.height() + 12 else top_left.y() - self.height() - 8
        self.move(x, y)
        self.show()


AION2_CLASSES = [
    "Gladiator", "Templar", "Ranger", "Assassin",
    "Spiritmaster", "Sorcerer", "Cleric", "Chanter", "Brawler",
]

# Brawler is not live at global launch — kept in AION2_CLASSES for data
# completeness, but excluded from every class picker until re-enabled.
AION2_ACTIVE_CLASSES = [c for c in AION2_CLASSES if c != "Brawler"]

# GearScore sums each equipped item's own "level" field, as returned by
# shugo.gg's batch-details API — this is the game's real per-item power
# value (confirmed distinct from equipLevel/character-level requirement,
# and confirmed to correlate correctly with the real rarity order: Common
# 1 < Rare 23 < Legend 34 < Unique 50 < Epic 108 for same-tier Greatswords).
# Not an official "total GearScore" formula (no confirmed enchant-scaling
# data), just a real, additive per-item value instead of a guessed weight.

# Real class emblem artwork — extracted from the game's own UI resources via
# questlog.gg's public asset mirror (UT_Class_{Name}_Large.webp, converted to
# PNG). Brawler intentionally excluded per request (not live at launch).
_CLASS_ICON_DIR = _BUNDLE_DIR / "assets" / "class_icons"


def _class_icon(class_name: str) -> QIcon | None:
    path = _CLASS_ICON_DIR / f"{class_name.lower()}.png"
    return QIcon(str(path)) if path.exists() else None


# Real core-attribute icons, from aion2planner.com/images/stats/ (already-
# processed PNGs, not scraped game files) — only the 6 base attributes
# (STR/AGI/DEX/INT/WIS/CON) exist there; the other 10 "special" stats in the
# icon grid have no matching real icon and keep the drawn badge instead.
_STAT_ICON_DIR = _BUNDLE_DIR / "assets" / "stat_icons"


def _real_stat_icon(stat_id: str, size: int = 44) -> QPixmap | None:
    path = _STAT_ICON_DIR / f"stat_{stat_id.lower()}.png"
    if not path.exists():
        return None
    pix = QPixmap(str(path))
    if pix.isNull():
        return None
    return pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


# Real skill data (name/icon/class/description/specializations), scraped
# from gamers4.life's per-skill database pages (see fetch_skills.py) — icons
# themselves come from questlog.gg's public asset mirror, converted to PNG.
SKILLS_DATA_PATH = _BUNDLE_DIR / "data" / "skills_all.json"
SKILL_ICON_DIR = _BUNDLE_DIR / "assets" / "skill_icons"


def _load_skills_by_class() -> dict[str, list[dict]]:
    if not SKILLS_DATA_PATH.exists():
        return {}
    data = json.loads(SKILLS_DATA_PATH.read_text(encoding="utf-8"))
    by_class: dict[str, list[dict]] = {}
    for s in data.get("skills", []):
        cat = (s.get("mainCategory") or "").strip().lower()
        if not cat:
            continue
        by_class.setdefault(cat, []).append(s)
    return by_class


def _skill_icon(skill: dict) -> QIcon | None:
    """Reads the pre-computed 'iconFile' name (see fetch_skills.py's
    compute_icon_filenames — icon_{class4}_{Skill}_{Type}_.png, with the
    name portion lengthened per-group whenever the standard 8 letters would
    collide with another skill in the same class+type)."""
    filename = skill.get("iconFile")
    if not filename:
        return None
    path = SKILL_ICON_DIR / filename
    return QIcon(str(path)) if path.exists() else None


# Real recipe data (profession, mastery level, materials, output item),
# scraped from gamers4.life's per-recipe database pages (see
# fetch_recipes.py) — game-specific terms (recipe/material/profession/
# category names) are never run through tr()/translations.py, per user
# instruction, until an official in-game translation exists.
RECIPE_DATA_PATH = _BUNDLE_DIR / "data" / "recipes_all.json"

# Real professions as shown in-game (user screenshot, 2026-08-23) — order
# matches the live Crafting UI's own tab order. gamers4.life's own
# mainCategory slugs are internal codenames that don't match these 1:1
# (confirmed via subCategory cross-check against the real UI screenshots,
# not guessed): "tailoring" makes armor (Helm/Pauldrons/Top/Legs/Gloves/
# Shoes/Cloak) = real Armorsmithing; "jewelcrafting" makes bows/staves +
# accessories (Bow/Staff/Necklace/Earrings/Ring/Bracelet) = real
# Handicrafting.
CRAFTING_PROFESSIONS = ["Blacksmithing", "Armorsmithing", "Handicrafting", "Alchemy", "Cooking"]
_RECIPE_PROFESSION_MAP = {
    "blacksmithing": "Blacksmithing",
    "tailoring": "Armorsmithing",
    "jewelcrafting": "Handicrafting",
    "alchemy": "Alchemy",
    "cooking": "Cooking",
}

# Real in-game subcategory labels + display order per profession (user
# screenshots, 2026-08-23). gamers4.life's own subCategory slugs sometimes
# differ from the real label (e.g. its "sword" slug is the real
# "Longsword") — kept as the dict key (matches the raw data), the tuple's
# second value is what's actually shown. "materials" is a shared id across
# professions: each has its own "misc_<profession>" slug on gamers4.life,
# normalized into this one shared key in _load_recipes().
CRAFTING_CATEGORIES: dict[str, list[tuple[str, str]]] = {
    "Blacksmithing": [
        ("greatsword", "Greatsword"), ("sword", "Longsword"), ("dagger", "Dagger"),
        ("mace", "Mace"), ("fist", "Fist"), ("guarder", "Guard"), ("materials", "Materials"),
    ],
    "Armorsmithing": [
        ("helmet", "Helm"), ("shoulder", "Pauldrons"), ("torso", "Top"), ("pants", "Legs"),
        ("gloves", "Gloves"), ("boots", "Shoes"), ("cape", "Cloak"), ("materials", "Materials"),
    ],
    "Handicrafting": [
        ("bow", "Bow"), ("staff", "Staff"), ("necklace", "Necklace"), ("earring", "Earrings"),
        ("ring", "Ring"), ("brooch", "Brooch"), ("bracelet", "Bracelet"), ("materials", "Materials"),
    ],
    "Alchemy": [
        ("magicbook", "Spellbook"), ("orb", "Orb"), ("potion", "Potion"),
        ("scroll", "Scroll"), ("magicstone", "Manastone"), ("materials", "Materials"),
    ],
    "Cooking": [
        ("food", "Food"), ("drink", "Beverage"),
    ],
}

# Fist = Brawler's weapon (see CLASS_WEAPON_CATEGORY) — Brawler isn't live
# at global launch (AION2_ACTIVE_CLASSES excludes it app-wide already), so
# hidden here too: the filter option stays in the data, just never shown
# as a pill, so there's no way to select it back in until re-enabled. No
# Fist recipes exist in the fetched data yet either way.
_CRAFTING_HIDDEN_CATEGORIES = {"fist"}

# gamers4.life's own grade badge names don't match this app's established
# Common/Rare/Legend/Unique/Epic scale 1:1 — cross-referenced against the
# shugo.gg catalog across the whole 2442-recipe dataset (100% consistent
# every time, not a one-off guess): g4l "Heroic" = "Epic" here, g4l "Epic"
# = "Legend" here.
_RECIPE_GRADE_MAP = {
    "Common": "Common", "Rare": "Rare", "Unique": "Unique",
    "Heroic": "Epic", "Epic": "Legend",
}

# The real explanation for same-named items having multiple recipes: ingame
# an item can be obtained either by regular crafting from raw materials, or
# by "transferring" an existing item's stats via a Transfer Stone -- gamers4.life
# has no dedicated field for this, so it's detected from the ingredient list
# itself (confirmed against the full 1490-recipe dataset: 304 recipes use one).
_METHOD_COLORS = {"Transfer": "#f59e0b", "Herstellung": "#4ade80"}
# "Herstellung"/"Transfer" stay the stable internal method identifiers
# (matches recipe["method"], used for comparisons/dict lookups) -- only the
# DISPLAYED text is translated, via this label lookup.
_METHOD_LABEL_KEYS = {"Herstellung": "arm_method_direct", "Transfer": "arm_method_transfer"}


def _recipe_method(inputs: list[dict]) -> str:
    return "Transfer" if any("Transfer Stone" in (i.get("name") or "") for i in inputs) else "Herstellung"


def _item_type_word(name: str) -> str:
    """Last real word of an item name, ignoring a trailing "(Bound)"/"(...)"
    tag -- used to check that an upgrade recipe's single-qty source item is
    actually the same equipment slot as its output (see
    _transfer_source_name)."""
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
    parts = name.split()
    return parts[-1] if parts else ""


def _item_grade(name: str | None, item_id: int | None, items_by_id: dict, output_index: dict) -> str | None:
    item = items_by_id.get(item_id) if item_id else None
    if item and item.get("grade"):
        return item["grade"]
    recipe = output_index.get(name) if name else None
    return recipe.get("grade") if recipe else None


def _transfer_source_name(recipe: dict, items_by_id: dict, output_index: dict) -> str | None:
    """A recipe is an "upgrade hop" (Transfer-Stone or Kinah-only alike) if
    exactly one input is consumed at qty 1, isn't the stone or a pure Kinah
    row, shares its item-type word with the output (e.g. both end in
    "Boots"), AND -- confirmed by the user -- is the SAME grade tier as the
    output (a real Transfer/Splendent upgrade never jumps e.g. "Legend"
    (blue) straight to "Unique" (gold) in one hop; that's a normal
    Herstellung recipe instead, not a chain link). The word check alone is
    needed because a good chunk of ordinary multi-material recipes also
    happen to consume exactly one other craftable item at qty 1 as a plain
    catalyst (e.g. "Wrathful Mind" x1 into a completely unrelated "Celestial
    Dragon Lord Ring"); the grade check on top catches the rarer case where
    the shared word is coincidental AND the two items happen to be
    different tiers. Verified against the full dataset: with just the word
    check, 288 of the real 304 Transfer-Stone recipes match (the rest have
    >1 qty-1 input) plus 482 further Kinah-only upgrade hops are found this
    way; every single one of those is already same-grade (706x Unique-
    Unique, 36x Legend-Legend, 26x Rare-Rare), so the grade check costs
    zero real matches and only guards against a hop the game doesn't
    actually have. Shared module-level (not just CraftingCalculatorWindow)
    so the Build Planner's Schnellauswahl can derive the same tier chains."""
    candidates = [
        i for i in recipe["inputs"]
        if (i.get("qty") or 1) == 1 and i.get("name")
        and "Transfer Stone" not in i["name"] and "Kina" not in i["name"]
    ]
    if len(candidates) != 1:
        return None
    candidate = candidates[0]
    candidate_name = candidate["name"]
    output_name = recipe["outputs"][0].get("name") or ""
    if _item_type_word(candidate_name) != _item_type_word(output_name):
        return None
    candidate_grade = _item_grade(candidate_name, candidate.get("id"), items_by_id, output_index)
    output_grade = recipe.get("grade")
    if candidate_grade and output_grade and candidate_grade != output_grade:
        return None
    return candidate_name


def _build_transfer_source_index(recipes: list[dict], items_by_id: dict, output_index: dict) -> dict[str, list[dict]]:
    """Upgrade-chain recipes indexed by their "source" item -- built from
    ALL recipes, not just method=="Transfer" ones, because a real chain hop
    is often a pure-Kinah upgrade with no Transfer Stone at all (e.g.
    "Celestial Dragon Lord Boots" -> "Splendent Celestial Dragon Lord
    Boots" for 15,000,000 Kina, no stone) -- restricting to Transfer Stone
    recipes alone silently broke real chains one hop before their end."""
    index: dict[str, list[dict]] = {}
    for r in recipes:
        source = _transfer_source_name(r, items_by_id, output_index)
        if source:
            index.setdefault(source, []).append(r)
    return index


def _find_transfer_path(start_name: str, target_name: str, transfer_source_index: dict) -> list[dict] | None:
    """BFS over upgrade-hop recipes from start_name to target_name -- real
    chains can span multiple tiers (verified 3-hop example: Splendent
    White -> Wise -> Splendent Wise -> Celestial Dragon Lord Boots)."""
    if start_name == target_name:
        return []
    queue = deque([(start_name, [])])
    visited = {start_name}
    while queue:
        current, path = queue.popleft()
        if len(path) >= 12:
            continue
        for recipe in transfer_source_index.get(current, []):
            output_name = recipe["outputs"][0].get("name")
            if output_name in visited:
                continue
            new_path = path + [recipe]
            if output_name == target_name:
                return new_path
            visited.add(output_name)
            queue.append((output_name, new_path))
    return None


def _ordered_tier_chain(root_name: str, type_word: str, transfer_source_index: dict) -> list[str]:
    """BFS from root_name, returning tier-prefix names (root_name itself,
    then every reachable output, each with its trailing type_word stripped)
    in visitation order -- a real, natural tier progression order since
    each hop is exactly one upgrade step. Used to populate the Build
    Planner's Schnellauswahl tier dropdown (see project_todo.md: verified
    against real data that the tier-prefix sequence is identical across
    equipment slot types for the same race, e.g. Ring/Boots/Necklace/
    Dagger/Greatsword all reach the same 9 prefixes for "True Dragon Lord")."""
    def strip_word(name: str) -> str:
        return name[: -(len(type_word) + 1)] if name.endswith(" " + type_word) else name

    order = [strip_word(root_name)]
    queue = deque([root_name])
    visited = {root_name}
    while queue:
        current = queue.popleft()
        for recipe in transfer_source_index.get(current, []):
            output_name = recipe["outputs"][0].get("name")
            if output_name in visited:
                continue
            visited.add(output_name)
            order.append(strip_word(output_name))
            queue.append(output_name)
    return order


def _parse_gold_cost(raw) -> int:
    """Raw values are comma-formatted strings like "4,000" (or already 0)."""
    if raw is None:
        return 0
    try:
        return int(str(raw).replace(",", "").strip())
    except ValueError:
        return 0

# Recipes that only consume a base item + pure PvP currency (Abyss Points,
# Platinum Medal of Merit) with no real crafting material — these are PvP
# gear upgrades, not "crafting" in the sense this guide is for (excluded
# per user request). Verified as a clean, self-contained set of exactly 16
# "[Faction] High Commander X -> Elite [Faction] High Commander X" recipes
# across the whole dataset — nothing else uses these two item names.
_RECIPE_EXCLUDED_INPUT_NAMES = {"Abyss Points", "Platinum Medal of Merit"}


def _load_recipes() -> list[dict]:
    """Loads + normalizes the fetched recipe data. Two kinds of entries are
    dropped: PvP-currency-only "recipes" (see above), and gamers4.life's own
    "combo" entries (learnType == "combo") — these have empty inputs and
    exist on their site purely as a landing page for a recipe's secondary
    bonus-chance output (already captured as this recipe's own combo output
    below), not as an independently craftable thing."""
    if not RECIPE_DATA_PATH.exists():
        return []
    data = json.loads(RECIPE_DATA_PATH.read_text(encoding="utf-8"))
    recipes = []
    for r in data.get("recipes", []):
        if r.get("learnType") == "combo" or not r.get("inputs"):
            continue
        input_names = {i.get("name") for i in r.get("inputs", [])}
        if input_names & _RECIPE_EXCLUDED_INPUT_NAMES:
            continue
        profession = _RECIPE_PROFESSION_MAP.get(r.get("mainCategory"))
        if not profession or not r.get("outputs"):
            continue
        sub = r.get("subCategory") or ""
        category = "materials" if sub.startswith("misc_") else sub
        grade = _RECIPE_GRADE_MAP.get(r.get("grade"), r.get("grade"))
        recipes.append({
            "id": r["id"],
            "profession": profession,
            "category": category,
            "grade": grade,
            "method": _recipe_method(r.get("inputs", [])),
            "masteryLevel": r.get("masteryLevel"),
            "goldCost": _parse_gold_cost(r.get("remoteGoldCost") or r.get("goldCost")),
            "inputs": r.get("inputs", []),
            "outputs": r.get("outputs", []),
        })
    return recipes


def _build_recipe_output_index(recipes: list[dict]) -> dict[str, dict]:
    """Maps a craftable item's name to the recipe that makes it — lets a
    recipe's own ingredient list be checked for "is this itself craftable"
    without a separate hand-built table. Real multi-tier upgrade chains
    (e.g. Base -> Fine -> Pure -> Artisan's Orichalcum Longsword) fall out
    of this automatically rather than needing to be curated by hand.

    Indexes EVERY output name, not just outputs[0] -- some recipes have a
    second output for a bonus-chance "Splendent" variant (e.g. recipe
    111014001 outputs both "Artisan's Orichalcum Longsword" [guaranteed]
    and "Artisan's Splendent Orichalcum Longsword" [bonus chance]). Only
    indexing the first output meant looking up that second name -- which is
    exactly what a parent recipe's own ingredient list references -- found
    nothing, silently truncating the chain one tier early."""
    index: dict[str, dict] = {}
    for r in recipes:
        for output in r["outputs"]:
            index.setdefault(output["name"], r)
    return index


def _resolve_material_name(name: str | None, item_id: int | None, items_by_id: dict) -> str | None:
    """A handful of recipe inputs carry no name in the scraped data (the
    scraper's own gap, not a missing item) even though the id resolves fine
    in the item catalog -- fall back to that instead of showing "None"."""
    if name:
        return name
    item = items_by_id.get(item_id) if item_id else None
    return item.get("name") if item else None


def _build_material_node(
    name: str | None, item_id: int | None, qty: int, output_index: dict, items_by_id: dict, depth: int = 0,
) -> dict:
    """One node of the quantity-aware material tree used by the Crafting
    Simulator's Baum/Liste views. qty is "how many of this material are
    needed per ONE unit of its parent" -- NOT yet scaled by how many of the
    parent are actually needed; that scaling happens at render/flatten time
    (multiplying down the tree), so the same tree is reusable across
    different Anzahl values without rebuilding it. depth caps at 20 as a
    cheap guard against a data cycle."""
    name = _resolve_material_name(name, item_id, items_by_id)
    node = {"name": name, "id": item_id, "qty": qty, "mastery": None, "goldCost": 0, "children": None}
    if depth >= 20 or not name:
        return node
    recipe = output_index.get(name)
    if recipe is None:
        return node
    node["mastery"] = recipe.get("masteryLevel")
    node["goldCost"] = recipe.get("goldCost", 0)
    node["children"] = [
        _build_material_node(m.get("name"), m.get("id"), m.get("qty") or 1, output_index, items_by_id, depth + 1)
        for m in recipe.get("inputs", [])
    ]
    return node


def _build_material_tree(recipe: dict, output_index: dict, items_by_id: dict) -> dict:
    """Root node for a selected recipe -- mirrors _build_material_node's
    shape, just seeded directly from the chosen recipe instead of a
    name lookup."""
    output = recipe["outputs"][0]
    return {
        "name": output["name"], "id": output.get("id"), "qty": 1,
        "mastery": recipe.get("masteryLevel"), "goldCost": recipe.get("goldCost", 0),
        "children": [
            _build_material_node(m.get("name"), m.get("id"), m.get("qty") or 1, output_index, items_by_id, 1)
            for m in recipe.get("inputs", [])
        ],
    }


def _flatten_material_tree(node: dict, needed_qty: int, totals: dict[str, dict]):
    """Recursively sums every leaf material across the whole tree, regardless
    of how deep it sits -- the "Liste" (shopping-list) view's data source."""
    if not node.get("children"):
        entry = totals.setdefault(node["name"], {"qty": 0, "id": node.get("id")})
        entry["qty"] += needed_qty
        return
    for child in node["children"]:
        _flatten_material_tree(child, needed_qty * (child.get("qty") or 1), totals)


def _compute_tree_kinah(node: dict, needed_qty: int) -> int:
    """Kinah fee paid per craft attempt at every tier that's actually
    crafted (raw/gathered leaf materials have no fee here)."""
    if not node.get("children"):
        return 0
    total = (node.get("goldCost") or 0) * needed_qty
    for child in node["children"]:
        total += _compute_tree_kinah(child, needed_qty * (child.get("qty") or 1))
    return total


_UNRESOLVED_TOKEN_RE = re.compile(r"\{[a-zA-Z_]+(?::[A-Za-z0-9_]+)+\}")


def _make_plus_icon(size: int = 22, color: str = "#e5e7eb") -> QIcon:
    """Draws a plus sign — the full-width '＋' character rendered too faint/
    small to recognize in this button's font, so draw it instead."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    thickness = size * 0.2
    painter.drawRoundedRect(QRectF(size * 0.1, (size - thickness) / 2, size * 0.8, thickness), thickness * 0.3, thickness * 0.3)
    painter.drawRoundedRect(QRectF((size - thickness) / 2, size * 0.1, thickness, size * 0.8), thickness * 0.3, thickness * 0.3)
    painter.end()
    return QIcon(pixmap)


def _make_edit_icon(size: int = 22, color: str = "#e5e7eb") -> QIcon:
    """Draws a small pencil glyph for the 'rename build' action."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.translate(size / 2, size / 2)
    painter.rotate(45)
    body_w = size * 0.2
    body_h = size * 0.62
    painter.drawRoundedRect(QRectF(-body_w / 2, -body_h / 2, body_w, body_h * 0.72), body_w * 0.3, body_w * 0.3)
    tip = QPolygonF([
        QPointF(-body_w / 2, body_h * 0.22),
        QPointF(body_w / 2, body_h * 0.22),
        QPointF(0, body_h / 2),
    ])
    painter.drawPolygon(tip)
    painter.end()
    return QIcon(pixmap)


def _make_gear_icon(size: int = 20, color: str = "#e5e7eb") -> QIcon:
    """Draws a small cog glyph for the "Eigenschaften-Priorität bearbeiten"
    button next to "Eigenschaften" (User-Wunsch: "Ein Zahnrad (similar zu
    Timer)") -- drawn like this file's other toolbar icons instead of
    relying on the "⚙" glyph, which renders inconsistently across fonts."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.translate(size / 2, size / 2)
    outer_r = size * 0.42
    tooth_w = size * 0.17
    tooth_h = size * 0.18
    for i in range(8):
        painter.save()
        painter.rotate(i * 45)
        painter.drawRoundedRect(
            QRectF(-tooth_w / 2, -outer_r - tooth_h * 0.35, tooth_w, tooth_h), tooth_w * 0.3, tooth_w * 0.3,
        )
        painter.restore()
    painter.drawEllipse(QPointF(0, 0), outer_r * 0.8, outer_r * 0.8)
    painter.setCompositionMode(QPainter.CompositionMode_Clear)
    painter.drawEllipse(QPointF(0, 0), outer_r * 0.36, outer_r * 0.36)
    painter.end()
    return QIcon(pixmap)


def _make_back_icon(size: int = 18, color: str = "#e5e7eb") -> QIcon:
    """Draws a left-pointing chevron for the 'back to Stat Info' button."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(size * 0.16)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    points = [QPointF(size * 0.62, size * 0.2), QPointF(size * 0.28, size * 0.5), QPointF(size * 0.62, size * 0.8)]
    for i in range(len(points) - 1):
        painter.drawLine(points[i], points[i + 1])
    painter.end()
    return QIcon(pixmap)


def _make_close_icon(size: int = 18, color: str = "#e5e7eb") -> QIcon:
    """Draws an X glyph for the 'clear equipped slot' button."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = painter.pen()
    pen.setColor(QColor(color))
    pen.setWidthF(size * 0.14)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    m = size * 0.24
    painter.drawLine(QPointF(m, m), QPointF(size - m, size - m))
    painter.drawLine(QPointF(size - m, m), QPointF(m, size - m))
    painter.end()
    return QIcon(pixmap)


def _make_check_icon(size: int = 20, color: str = "#facc15") -> QPixmap:
    """Draws a checkmark for the 'angehakt' marker on a skill card."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = painter.pen()
    pen.setColor(QColor(color))
    pen.setWidthF(size * 0.16)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    path = [
        QPointF(size * 0.2, size * 0.55),
        QPointF(size * 0.42, size * 0.78),
        QPointF(size * 0.82, size * 0.24),
    ]
    for i in range(len(path) - 1):
        painter.drawLine(path[i], path[i + 1])
    painter.end()
    return pixmap


def _make_save_icon(size: int = 22, color: str = "#e5e7eb") -> QIcon:
    """Draws a simple floppy-disk glyph instead of relying on an emoji that
    may not render (or may render too small/faint) in this button's font."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(QRectF(size * 0.12, size * 0.08, size * 0.76, size * 0.84), size * 0.08, size * 0.08)

    painter.setBrush(QColor("#0f172a"))
    painter.drawRect(QRectF(size * 0.26, size * 0.10, size * 0.34, size * 0.24))
    painter.drawRoundedRect(QRectF(size * 0.22, size * 0.50, size * 0.56, size * 0.34), size * 0.05, size * 0.05)

    painter.end()
    return QIcon(pixmap)


def _short_skill_name(name: str, max_len: int = 12) -> str:
    """Truncates by character count (not font metrics — the window's real
    stylesheet/font isn't applied yet at widget-construction time) so a long
    skill name can't wrap to a second line and overlap the tile's icon above
    it."""
    name = name or ""
    if len(name) <= max_len:
        return name
    return name[: max_len - 1].rstrip() + "…"


_SKILL_TYPE_COLORS = {"active": "#22d3ee", "passive": "#a855f7", "stigma": "#facc15"}


def _rgba_str(hex_color: str, alpha: float) -> str:
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


def _make_type_badge(text: str, color: str) -> QLabel:
    badge = QLabel(text)
    badge.setStyleSheet(
        f"background-color: {_rgba_str(color, 0.16)}; color: {color}; "
        f"border: 1px solid {_rgba_str(color, 0.5)}; border-radius: 8px; "
        f"padding: 2px 10px; font-size: 11px; font-weight: 700;"
    )
    return badge


def _format_skill_stats(skill: dict) -> str:
    """MP/other resource cost, cooldown, range, and required weapon(s) —
    fields added to fetch_skills.py after the fact, so older cached entries
    may be missing some of these; each line is only shown if present."""
    lines = []

    consumed = skill.get("consumed") or {}
    costs = [f"{v} {k.upper()}" for k, v in consumed.items() if v]
    if costs:
        lines.append(f"<b>Kosten:</b> {', '.join(costs)}")

    cooldown = skill.get("cooldown")
    if cooldown:
        lines.append(f"<b>Abklingzeit:</b> {cooldown / 1000:.0f}s")

    rng = skill.get("range") or {}
    max_r = rng.get("max")
    if max_r:
        min_r = rng.get("min") or 0
        if min_r and min_r != max_r:
            lines.append(f"<b>Reichweite:</b> {min_r / 100:.0f}-{max_r / 100:.0f}m")
        else:
            lines.append(f"<b>Reichweite:</b> {max_r / 100:.0f}m")

    weapons = skill.get("requiredWeapons") or []
    if weapons:
        lines.append(f"<b>Benötigte Waffe(n):</b> {', '.join(w.capitalize() for w in weapons)}")

    return "<br>".join(lines) if lines else "—"


def _level_value(levels: list[dict], level: int, key: str):
    entry = next((l for l in levels if l.get("level") == level), None)
    if entry is None and levels:
        entry = levels[0]
    return entry.get(key) if entry else None


def _render_skill_description(text: str, levels: list[dict] | None = None, level: int = 1) -> str:
    """Resolves unfilled '{...}' template tokens to a real number from the
    skill's own per-level data when possible (falling back to a plain 'x'),
    and converts newlines to <br> — but keeps the game's own
    <span style="color:..."> tags (only ~4 known safe variants appear in the
    data) so real numbers *and* any remaining 'x' placeholder both keep
    their in-game highlight color when rendered as rich text by
    QLabel/tooltips. Every observed token's field name contains 'Min' or
    'Max' as a literal substring, so that's all we need to check — no need
    to parse out which segment of the token is "the field"."""

    def _sub(match: re.Match) -> str:
        token = match.group(0)
        if levels:
            if "Min" in token:
                value = _level_value(levels, level, "minValue")
            elif "Max" in token:
                value = _level_value(levels, level, "maxValue")
            else:
                value = None
            if value is not None and str(value).lstrip("-").isdigit():
                return str(value)
        return "x"

    text = _UNRESOLVED_TOKEN_RE.sub(_sub, text or "")
    return text.replace("\n", "<br>")


_CLASS_SELECT_ENTRIES = [
    ("Gladiator", "⚔️"),
    ("Templar", "🛡️"),
    ("Assassin", "🗡️"),
    ("Ranger", "🏹"),
    ("Sorcerer", "📖"),
    ("Spiritmaster", "🔮"),
    ("Cleric", "✨"),
    ("Chanter", "🎵"),
]


class ClassSelectDialog(QDialog):
    """'Choose Your Class' gate screen shown before the Build Planner opens
    for the first time in a session — picks the class that pre-fills the
    weapon-category filter and character info in LoadoutWindow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle("Choose Your Class")
        self.selected_class: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(6)

        title = QLabel("Choose Your Class")
        title.setObjectName("DetailHeader")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px;")
        layout.addWidget(title)

        subtitle = QLabel("Start planning your Build")
        subtitle.setObjectName("DetailInfo")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(14)

        grid = QGridLayout()
        grid.setSpacing(14)
        for i, (class_name, emoji) in enumerate(_CLASS_SELECT_ENTRIES):
            row, col = divmod(i, 4)

            btn = QPushButton()
            btn.setObjectName("ClassSelectButton")
            btn.setFixedSize(180, 150)
            btn.setCursor(Qt.PointingHandCursor)
            btn_layout = QVBoxLayout(btn)
            btn_layout.setAlignment(Qt.AlignCenter)

            icon_label = QLabel(emoji)
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setStyleSheet("font-size: 48px; background: transparent;")
            name_label = QLabel(class_name)
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setStyleSheet("font-weight: 700; font-size: 14px; background: transparent;")

            btn_layout.addWidget(icon_label)
            btn_layout.addWidget(name_label)

            btn.clicked.connect(lambda checked=False, c=class_name: self._choose(c))
            grid.addWidget(btn, row, col)

        layout.addLayout(grid)

    def _choose(self, class_name: str):
        self.selected_class = class_name
        self.accept()



AION2_RACES = ["Elyos", "Asmodae"]


class CreateCharacterDialog(QDialog):
    """'Create Build' gate dialog shown before the Build Planner opens for
    the first time — Character Name / Class / Race, styled with the app's
    own theme (not the reference screenshot's look, just its field layout)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle("Create Build")
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(4)

        title = QLabel("Create Character")
        title.setObjectName("DetailHeader")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px;")
        layout.addWidget(title)

        subtitle = QLabel("Create Build")
        subtitle.setObjectName("DetailInfo")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(18)

        name_label = QLabel("Character Name")
        name_label.setObjectName("DetailInfo")
        layout.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Optional")
        layout.addWidget(self.name_input)
        layout.addSpacing(12)

        class_label = QLabel("Select a Class")
        class_label.setObjectName("DetailInfo")
        layout.addWidget(class_label)
        self.class_combo = QComboBox()
        self.class_combo.setIconSize(QSize(28, 28))
        self.class_combo.addItem("Class", "")
        self.class_combo.model().item(0).setEnabled(False)
        for class_name in AION2_ACTIVE_CLASSES:
            self.class_combo.addItem(_class_icon(class_name) or QIcon(), class_name, class_name)
        self.class_combo.setCurrentIndex(0)
        self.class_combo.currentIndexChanged.connect(self._update_create_enabled)
        layout.addWidget(self.class_combo)
        layout.addSpacing(12)

        race_label = QLabel("Select Race")
        race_label.setObjectName("DetailInfo")
        layout.addWidget(race_label)
        self.race_combo = QComboBox()
        self.race_combo.addItems(AION2_RACES)
        layout.addWidget(self.race_combo)
        layout.addSpacing(18)

        btn_row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.create_btn = QPushButton("Create →")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.create_btn)
        layout.addLayout(btn_row)

    def _update_create_enabled(self):
        self.create_btn.setEnabled(bool(self.class_combo.currentData()))

    @property
    def character_name(self) -> str:
        return self.name_input.text().strip()

    @property
    def selected_class(self) -> str:
        return self.class_combo.currentData() or ""

    @property
    def selected_race(self) -> str:
        return self.race_combo.currentText()



# Aggregated Stat Info panel rows: (display label, stat id or None). Only
# ids verified against real per-item API responses are summed across
# equipped slots — everything else shows "—" rather than a fabricated
# number. No source exists yet for "Boss"-specific damage boost/tolerance
# or Move Speed/Evasion/Critical Hit Resist, so those stay None.
_MAIN_STAT_ROWS = [
    ("Attack", "WeaponFixingDamage"),
    ("Attack increase", "DamageRatio"),
    ("Accuracy", "WeaponAccuracy"),
    ("Critical Hit", "Critical"),
    ("HP", "HPMax"),
    ("Combat Speed", "CombatSpeed"),
    ("Cooldown", None),
    ("Smite", "HardHit"),
    ("Perfect Chance", None),
    ("Multi-hit Chance", "AdditionalHitRate"),
]
_MOVEMENT_STAT_ROWS = [
    ("Move Speed", None),
    ("Stamina", None),
    ("Flight Power", "FPMax"),
]
_SUB_STAT_ROWS = [
    ("Defense", "ArmorDefense"),
    ("Evasion", "ArmorEvasion"),
    ("Critical Hit Resist", "CriticalResist"),
    ("MP", "MPMax"),
]
_OFFENSE_STAT_ROWS = [
    ("Attack Bonus", None),
    ("Damage Boost", "AmplifyAllDamage"),
    ("Weapon Damage Boost", "AmplifyWeaponDamage"),
    ("Accuracy Bonus", None),
    ("Accuracy increase", None),
    ("Critical Hit increase", None),
]
_DEFENSE_STAT_ROWS = [
    ("Defense Bonus", None),
    ("Evasion Bonus", None),
    ("Block", "Block"),
    ("Block increase", None),
    ("Parry Damage Reduction Amount", None),
    ("Parry Damage Reduction Rate", None),
    ("Defense increase", "DefenseRatio"),
    ("Endurance", "IronWall"),
    ("Regeneration", "Restoration"),
]
_UTILITY_RECOVERY_STAT_ROWS = [
    ("Natural HP Regen", "HPRegen"),
    ("Natural MP Regen", "MPRegen"),
    ("HP Potion Recovery increase", None),
    ("Incoming Heal", "AmplifyHpHealGet"),
    ("HP increase", None),
    ("MP increase", None),
    ("MP Cost Reduction", None),
    ("MP Cost", None),
    ("Power Shard Damage Bonus", "SealStoneAddDamage"),
]

# Rows shown in the Main Stats tab's mode section, switched by the PvE/PvP
# toggle — folds what used to be separate "PvP"/"PvE" tabs into Main Stats.
_PVE_MODE_STAT_ROWS = [
    ("PvE Attack", None),
    ("PvE Defense", None),
    ("PvE Accuracy", None),
    ("PvE Evasion", None),
    ("PvE Damage Boost", "PvEAmplifyDamage"),
    ("PvE Damage Tolerance", "PvEDecreaseDamage"),
    ("Boss Attack", None),
    ("Boss Defense", None),
    ("Boss Damage Boost", None),
    ("Boss Damage Tolerance", None),
]
_PVP_MODE_STAT_ROWS = [
    ("PvP Attack", None),
    ("PvP Defense", None),
    ("PvP Accuracy", None),
    ("PvP Evasion", None),
    ("PvP Critical Hit", None),
    ("PvP Critical Hit Resist", None),
    ("PvP Damage Boost", "PvPAmplifyDamage"),
    ("PvP Damage Tolerance", "PvPDecreaseDamage"),
    ("PvP Block", None),
    ("PvP Block Penetration", None),
    ("Penetration", "DefensePierce"),
    ("Regeneration Penetration", None),
    ("Endurance Penetration", None),
    ("Smite Resist", "HardHitResist"),
    ("Perfect Resist", None),
]

# Status-effect rows, only shown under Main Stats in PvP mode (folds the old
# separate "Status" grouping in too). Each row is (name, stat id or None,
# effect key) — effect key "general" means the row is never class-filtered.
_STATUS_CHANCE_STAT_ROWS = [
    ("Status Effect Chance", "AbnormalAccuracy", "general"),
    ("Stun Chance", None, "Stun"),
    ("Knockdown Chance", None, "Knockdown"),
    ("Airborne Chance", None, "Airborne"),
    ("Grab Chance", None, "Grab"),
    ("Fear Chance", None, "Fear"),
    ("Sleep Chance", None, "Sleep"),
    ("Polymorph Chance", None, "Polymorph"),
    ("Taunt Chance", None, "Taunt"),
    ("Seal Chance", None, "Seal"),
    ("Frost Chance", None, "Frost"),
    ("Paralyze Chance", None, "Paralyze"),
    ("Root Chance", None, "Root"),
    ("Blind Chance", None, "Blind"),
    ("Lethargy Chance", None, "Lethargy"),
    ("Slow Chance", None, "Slow"),
    ("Poison Chance", None, "Poison"),
    ("Bleed Chance", None, "Bleed"),
]
_STATUS_RESIST_STAT_ROWS = [
    ("Status Effect Resist", "AbnormalResistance", "general"),
    ("Impact-type Resist", None, "general"),
    ("Stun Resist", None, "Stun"),
    ("Knockdown Resist", None, "Knockdown"),
    ("Airborne Resist", None, "Airborne"),
    ("Grab Resist", None, "Grab"),
    ("Fear Resist", None, "Fear"),
    ("Sleep Resist", None, "Sleep"),
    ("Polymorph Resist", None, "Polymorph"),
    ("Taunt Resist", None, "Taunt"),
    ("Seal Resist", None, "Seal"),
    ("Frost Resist", None, "Frost"),
    ("Paralyze Resist", None, "Paralyze"),
    ("Root Resist", None, "Root"),
    ("Blind Resist", None, "Blind"),
    ("Lethargy Resist", None, "Lethargy"),
    ("Slow Resist", None, "Slow"),
    ("Poison Resist", None, "Poison"),
    ("Bleed Resist", None, "Bleed"),
]

# Which Chance effects each class actually inflicts, per a clause-level scan
# of all 295 skills in skills_all.json (descriptions + specializations),
# requiring a real infliction verb and excluding remove/cleanse/immune
# clauses. Resist rows are never filtered — passives only grant the generic
# "Status Effect Resist" bonus, never a per-effect one.
_CLASS_RELEVANT_CHANCE_EFFECTS: dict[str, set[str]] = {
    "gladiator": {"Knockdown", "Root", "Airborne", "Seal", "Slow"},
    "templar": {"Stun", "Knockdown", "Root", "Taunt"},
    "assassin": {"Blind", "Stun", "Airborne", "Slow", "Knockdown", "Seal", "Root"},
    "ranger": {"Stun", "Slow", "Seal", "Root", "Bleed", "Airborne", "Blind"},
    "sorcerer": {"Frost", "Root", "Slow", "Airborne", "Seal"},
    "elementalist": {"Fear", "Root", "Slow", "Taunt", "Seal"},
    "cleric": {"Root", "Stun", "Knockdown"},
    "chanter": {"Stun", "Seal", "Knockdown", "Root"},
}

_PERCENT_STAT_IDS = {
    "CombatSpeed", "PvEAmplifyDamage", "PvPAmplifyDamage", "PvEDecreaseDamage", "PvPDecreaseDamage",
    "AmplifyAllDamage", "AbnormalAccuracy", "AdditionalHitRate", "AmplifyWeaponDamage", "AbnormalResistance",
    "DamageRatio", "DefenseRatio",
}

# Rows shown above Main/Sub Stats in the aggregated Stat Info panel — the 6
# core attributes, then the 10 "Lords" divinity stats (real icons exist for
# both groups at aion2planner.com/images/stats/, but the Lords values have
# no known data source anywhere in the item API, so they always show "—").
# Each entry is (display name, icon key, value stat id or None). The Lords
# stats have a real icon but no known data source anywhere in the item API
# (unlike the 6 attributes, which are real substat ids), so their value
# stat id is None — same "—" convention as _MAIN_STAT_ROWS/_SUB_STAT_ROWS.
_STAT_ICON_ROWS = [
    [
        ("Might", "STR", "STR"), ("Dexterity", "DEX", "DEX"), ("Precision", "AGI", "AGI"),
        ("Willpower", "WIS", "WIS"), ("Intelligence", "INT", "INT"), ("Constitution", "CON", "CON"),
    ],
    [
        ("Death", "lords_death", None), ("Destiny", "lords_destiny", None), ("Destruction", "lords_destruction", None),
        ("Freedom", "lords_freedom", None), ("Illusion", "lords_illusion", None), ("Justice", "lords_justice", None),
    ],
    [
        ("Life", "lords_life", None), ("Space", "lords_space", None),
        ("Time", "lords_time", None), ("Wisdom", "lords_wisdom", None),
    ],
]

_STAT_ICON_ABBREVIATIONS = {
    "STR": "STR", "DEX": "DEX", "AGI": "AGI", "WIS": "WIS", "INT": "INT", "CON": "CON",
    "lords_death": "DTH", "lords_destiny": "DES", "lords_destruction": "DTR", "lords_freedom": "FRE",
    "lords_illusion": "ILL", "lords_justice": "JUS", "lords_life": "LIF", "lords_space": "SPA",
    "lords_time": "TIM", "lords_wisdom": "WIS",
}

_STAT_ICON_ROW_COLORS = ["#22d3ee", "#a855f7", "#facc15"]


def _make_stat_badge_icon(abbrev: str, color: str, size: int = 44) -> QPixmap:
    """Draws a colored ring with a short abbreviation inside — a stand-in
    for real per-stat icons, which don't exist anywhere in the data."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    base = QColor(color)
    fill = QColor(base)
    fill.setAlphaF(0.16)
    painter.setBrush(fill)
    pen = QPen(base)
    pen.setWidthF(2)
    painter.setPen(pen)
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.setPen(base)
    font = painter.font()
    font.setPixelSize(int(size * 0.28))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, abbrev)
    painter.end()
    return pixmap


def _parse_stat_value(raw) -> float:
    try:
        return float(str(raw).replace("%", "").strip())
    except (ValueError, TypeError):
        return 0.0


class _BuildTabButton(QPushButton):
    """A checkable tab-like button that also reports double-clicks, used to
    rename a saved skill build in place (single click still just switches
    to it, like a normal tab)."""

    doubleClicked = Signal()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)


class SkillPickerDialog(QDialog):
    """Small search-and-pick list for choosing a skill, used by the Skill
    Build priority list's empty slots."""

    def __init__(self, skills: list[dict], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle(_t("arm_choose_skill_title"))
        self.resize(360, 480)
        self.selected_skill: dict | None = None
        self._skills = skills

        layout = QVBoxLayout(self)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_t("arm_search_placeholder"))
        self.search_input.textChanged.connect(self._refresh_list)
        layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(28, 28))
        self.list_widget.itemDoubleClicked.connect(self._accept_current)
        layout.addWidget(self.list_widget, 1)

        choose_btn = QPushButton(_t("arm_select_btn"))
        choose_btn.clicked.connect(self._accept_current)
        layout.addWidget(choose_btn)

        self._refresh_list()

    def _refresh_list(self):
        query = self.search_input.text().strip().lower()
        self.list_widget.clear()
        for skill in self._skills:
            if query and query not in skill.get("name", "").lower():
                continue
            list_item = QListWidgetItem(skill.get("name", ""))
            icon = _skill_icon(skill)
            if icon:
                list_item.setIcon(icon)
            list_item.setData(Qt.UserRole, skill)
            self.list_widget.addItem(list_item)

    def _accept_current(self):
        current = self.list_widget.currentItem()
        if current is None:
            return
        self.selected_skill = current.data(Qt.UserRole)
        self.accept()



def _crafting_item_icon(
    item_id: int | None, items_by_id: dict, icon_cache: "IconCache", size: int = 34,
    apply=None, registry: dict | None = None,
) -> QPixmap | None:
    """Recipe materials only carry {id, name, qty} — the real icon/grade
    live in the item catalog, looked up here by id. Requests the icon if
    it isn't cached yet.

    `apply`/`registry`: when given, registers (apply, size, grade) under
    the icon's URL in `registry` so CraftingCalculatorWindow._on_icon_ready
    can push the pixmap into just this one widget once it loads — a full
    _rebuild_crafting_list() on every single icon_ready (the first version
    of this) tore down and rebuilt every card on the page for each of the
    dozens of concurrent requests a filter change kicks off, which raced
    with IconCache's own in-flight QNetworkReply callbacks and crashed
    ("Internal C++ object already deleted"). Same fix pattern already used
    for the main item table/equip slots (_on_icon_ready there)."""
    item = items_by_id.get(item_id) if item_id else None
    if not item:
        return None
    image_url = item.get("image", "")
    if not image_url:
        return None
    grade = item.get("grade")
    if registry is not None and apply is not None:
        registry.setdefault(image_url, []).append((apply, size, grade))
    pix = icon_cache.pixmap(image_url, size, grade=grade)
    if pix is None:
        icon_cache.request(image_url)
    return pix




_CRAFTING_PICKER_DEFAULT_LIMIT = 20
_CRAFTING_PICKER_EXPANDED_LIMIT = 50


class _SortableTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem that sorts by an explicit key instead of its display
    text -- needed for the Grade column (real game progression order, e.g.
    Unique before Legend, not alphabetical) and for any number formatted
    with thousand separators (plain text sort would put "1,000" before
    "200")."""

    def __init__(self, text: str, sort_key):
        super().__init__(text)
        self._sort_key = sort_key

    def __lt__(self, other):
        if isinstance(other, _SortableTableWidgetItem):
            return self._sort_key < other._sort_key
        return super().__lt__(other)


class CraftingItemPickerDialog(QDialog):
    """Item picker scoped to craftable items, for the Crafting Calculator's
    "I don't know exactly which item I need" button. Deliberately separate
    from ItemPickerPopup (equip slots) and the main ItemDatabaseWindow table
    (full catalog) -- this one only ever lists items that have a real
    recipe, grouped by the 5 actual crafting professions.

    Never shows all professions combined (same reasoning as
    CraftingCalculatorWindow's own default: an unfiltered pool is hundreds
    of rows, both slow to build and useless to scan). Row count itself is
    additionally capped (20 by default, expandable once to 50) rather than
    ever listing an unbounded result set.

    "Morph" recipes (Substance Morph Material/Design catalog categories) are
    a different crafting-like system entirely and out of scope here --
    recipes_all.json (gamers4.life's normal recipe scrape) doesn't contain
    them at all, so there is nothing to explicitly exclude yet."""

    def __init__(self, items_by_id: dict, icon_cache: "IconCache", parent=None,
                 allowed_names: set[str] | None = None, min_grade: str | None = None,
                 excluded_professions: frozenset[str] = frozenset()):
        super().__init__(parent)
        self.setWindowTitle(_t("arm_choose_item_title"))
        self.resize(720, 560)
        self._items_by_id = items_by_id
        self._icon_cache = icon_cache
        self._icon_registry: dict[str, list] = {}
        # Vergleich tab's Start/Ziel pickers exclude "Cooking" -- consumables
        # never participate in an equipment Transfer chain.
        self._available_professions = [p for p in CRAFTING_PROFESSIONS if p not in excluded_professions]
        # When set (Vergleich tab's Ziel picker once a Start item is chosen),
        # only these output names are ever shown -- e.g. the items actually
        # reachable via a Transfer chain from that Start item. Naturally
        # keeps race lines apart too: the real recipe data never links a
        # "Star Dragon Lord" item's chain to a "True Dragon Lord" one, so
        # restricting to reachable names alone already prevents picking e.g.
        # a Celestial (True Dragon/Elyos line) item from a Star Dragon
        # (Asmodae line) Start -- verified against the real dataset, see
        # project_todo.md.
        self._allowed_names = allowed_names
        # When set (Vergleich tab's Start picker), only grades at or above
        # this rank are ever offered -- confirmed by the user that no real
        # Transfer/Splendent upgrade chain currently starts below "Unique"
        # ("blau" == Legend or lower here), so lower grades would only ever
        # dead-end the Ziel picker afterwards.
        self._min_grade_rank = RARITY_RANK.get(min_grade) if min_grade else None

        self.selected_recipe: dict | None = None

        recipes = _load_recipes()
        self._by_profession: dict[str, list[dict]] = {}
        for r in recipes:
            self._by_profession.setdefault(r["profession"], []).append(r)

        self._state_profession = self._available_professions[0]
        if allowed_names is not None or self._min_grade_rank is not None:
            # Land on a profession that actually has an eligible item instead
            # of opening on an empty list because the default first
            # profession happens to have none (e.g. no reachable Ziel item,
            # or no item at/above the required min_grade).
            def _prof_has_match(prof: str) -> bool:
                for r in self._by_profession.get(prof, []):
                    if not r.get("outputs"):
                        continue
                    if allowed_names is not None and r["outputs"][0]["name"] not in allowed_names:
                        continue
                    if self._min_grade_rank is not None and RARITY_RANK.get(r.get("grade"), -1) < self._min_grade_rank:
                        continue
                    return True
                return False

            for prof in self._available_professions:
                if _prof_has_match(prof):
                    self._state_profession = prof
                    break
        self._state_search = ""
        self._state_rarity = "all"
        self._state_method = "all"
        self._visible_limit = _CRAFTING_PICKER_DEFAULT_LIMIT

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        self.profession_row = QHBoxLayout()
        self.profession_row.setSpacing(6)
        outer.addLayout(self.profession_row)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_t("arm_search_item_placeholder"))
        self.search_input.textChanged.connect(self._on_search_changed)
        outer.addWidget(self.search_input)

        self.rarity_row = QHBoxLayout()
        self.rarity_row.setSpacing(6)
        outer.addLayout(self.rarity_row)

        self.method_row = QHBoxLayout()
        self.method_row.setSpacing(6)
        outer.addLayout(self.method_row)

        self.result_label = QLabel()
        self.result_label.setObjectName("DetailDisclaimer")
        outer.addWidget(self.result_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", _t("arm_col_name"), _t("arm_rarity_label"), _t("arm_col_method")])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        # 28px icon + the app-wide QTableView::item padding (6px/10px, see
        # styles.qss) needs at least 48px of column width, or the icon
        # renders cramped/off-center against the cell edges.
        self.table.setColumnWidth(0, 52)
        self.table.setIconSize(QSize(28, 28))
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setSortingEnabled(True)
        self.table.cellClicked.connect(self._on_row_clicked)
        outer.addWidget(self.table, 1)

        self.more_btn = QPushButton(_t("arm_show_more", n=_CRAFTING_PICKER_EXPANDED_LIMIT))
        self.more_btn.clicked.connect(self._on_show_more)
        outer.addWidget(self.more_btn)

        # Must connect before the first _rebuild_table(): IconCache.request()
        # resolves synchronously (and emits icon_ready immediately) whenever
        # the icon is already on disk -- connecting afterwards means every
        # already-cached icon's signal fires into the void and never
        # actually reaches a row (only genuinely fresh network fetches,
        # which resolve later, would have worked).
        self._icon_cache.icon_ready.connect(self._on_icon_ready)

        self._rebuild_profession_row()
        self._rebuild_rarity_row()
        self._rebuild_method_row()
        self._rebuild_table()

    def _on_icon_ready(self, url: str):
        entries = self._icon_registry.get(url)
        if not entries:
            return
        for apply, size, grade in entries:
            pix = self._icon_cache.pixmap(url, size, grade=grade)
            if pix is None:
                continue
            try:
                apply(pix)
            except RuntimeError:
                pass

    def _rebuild_profession_row(self):
        _clear_layout(self.profession_row)
        group = QButtonGroup(self)
        group.setExclusive(True)
        for prof in self._available_professions:
            count = len({
                r["outputs"][0]["name"] for r in self._by_profession.get(prof, [])
                if r.get("outputs") and r["category"] != "materials"
            })
            btn = QPushButton(f"{prof} ({count})")
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(prof == self._state_profession)
            btn.clicked.connect(lambda checked=False, p=prof: self._on_profession_selected(p))
            group.addButton(btn)
            self.profession_row.addWidget(btn)
        self.profession_row.addStretch(1)
        self._profession_group = group  # kept alive against GC

    def _on_profession_selected(self, profession: str):
        if profession == self._state_profession:
            return
        self._state_profession = profession
        self._visible_limit = _CRAFTING_PICKER_DEFAULT_LIMIT
        self._rebuild_profession_row()
        self._rebuild_table()

    def _rebuild_rarity_row(self):
        _clear_layout(self.rarity_row)
        group = QButtonGroup(self)
        group.setExclusive(True)

        all_btn = QPushButton(_t("arm_all"))
        all_btn.setObjectName("SkillFilterButton")
        all_btn.setCheckable(True)
        all_btn.setChecked(self._state_rarity == "all")
        all_btn.clicked.connect(lambda checked=False: self._on_rarity_selected("all"))
        group.addButton(all_btn)
        self.rarity_row.addWidget(all_btn)

        for grade in RARITY_ORDER:
            if self._min_grade_rank is not None and RARITY_RANK[grade] < self._min_grade_rank:
                continue
            btn = QPushButton(grade)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(self._state_rarity == grade)
            btn.setStyleSheet(f"color: {GRADE_COLORS[grade]};")
            btn.clicked.connect(lambda checked=False, g=grade: self._on_rarity_selected(g))
            group.addButton(btn)
            self.rarity_row.addWidget(btn)
        self.rarity_row.addStretch(1)
        self._rarity_group = group

    def _on_rarity_selected(self, grade: str):
        if grade == self._state_rarity:
            return
        self._state_rarity = grade
        self._visible_limit = _CRAFTING_PICKER_DEFAULT_LIMIT
        self._rebuild_rarity_row()
        self._rebuild_table()

    def _rebuild_method_row(self):
        _clear_layout(self.method_row)
        group = QButtonGroup(self)
        group.setExclusive(True)

        all_btn = QPushButton(_t("arm_all"))
        all_btn.setObjectName("SkillFilterButton")
        all_btn.setCheckable(True)
        all_btn.setChecked(self._state_method == "all")
        all_btn.clicked.connect(lambda checked=False: self._on_method_selected("all"))
        group.addButton(all_btn)
        self.method_row.addWidget(all_btn)

        for method in ("Herstellung", "Transfer"):
            btn = QPushButton(_t(_METHOD_LABEL_KEYS[method]))
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(self._state_method == method)
            btn.setStyleSheet(f"color: {_METHOD_COLORS[method]};")
            btn.clicked.connect(lambda checked=False, m=method: self._on_method_selected(m))
            group.addButton(btn)
            self.method_row.addWidget(btn)
        self.method_row.addStretch(1)
        self._method_group = group

    def _on_method_selected(self, method: str):
        if method == self._state_method:
            return
        self._state_method = method
        self._visible_limit = _CRAFTING_PICKER_DEFAULT_LIMIT
        self._rebuild_method_row()
        self._rebuild_table()

    def _on_search_changed(self, text: str):
        self._state_search = text.strip().lower()
        self._visible_limit = _CRAFTING_PICKER_DEFAULT_LIMIT
        self._rebuild_table()

    def _on_show_more(self):
        self._visible_limit = _CRAFTING_PICKER_EXPANDED_LIMIT
        self._rebuild_table()

    def _matching_recipes(self) -> list[dict]:
        # One row per craftable item, not per recipe -- several recipe IDs
        # can share an output name (different crafting paths to the same
        # item, often one per faction, see project_todo.md). Filtering
        # happens BEFORE the seen-names dedup, so with e.g. Elyos active,
        # the row shown/selected is that item's Elyos recipe specifically
        # -- not an arbitrary "whichever recipe came first" pick.
        seen_names = set()
        matches = []
        for r in self._by_profession.get(self._state_profession, []):
            if not r.get("outputs") or r["category"] in _CRAFTING_HIDDEN_CATEGORIES:
                continue
            # "Materials" (raw resources/tools, e.g. Novice Blacksmith's
            # Hammer) aren't equipment end-products -- not something a
            # player searches for as a calculation *target*, even though
            # the source data technically carries a recipe for them.
            if r["category"] == "materials":
                continue
            name = r["outputs"][0]["name"]
            if self._allowed_names is not None and name not in self._allowed_names:
                continue
            if self._min_grade_rank is not None and RARITY_RANK.get(r.get("grade"), -1) < self._min_grade_rank:
                continue
            if self._state_rarity != "all" and r.get("grade") != self._state_rarity:
                continue
            if self._state_method != "all" and r.get("method") != self._state_method:
                continue
            if name in seen_names:
                continue
            if self._state_search and self._state_search not in name.lower():
                continue
            seen_names.add(name)
            matches.append(r)
        matches.sort(key=lambda r: r["outputs"][0]["name"])
        return matches

    def _rebuild_table(self):
        # Sorting must be off while (re-)populating -- QTableWidget re-sorts
        # after every setItem() when it's enabled, which scrambles row
        # indices mid-population.
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self._icon_registry = {}
        all_matches = self._matching_recipes()
        visible = all_matches[: self._visible_limit]

        suffix = _t("arm_transfer_only_suffix") if self._allowed_names is not None else ""
        self.result_label.setText(
            _t("arm_craftable_items_found", count=len(all_matches), profession=self._state_profession, suffix=suffix)
        )
        self.more_btn.setVisible(len(all_matches) > len(visible))

        self.table.setRowCount(len(visible))
        for row, recipe in enumerate(visible):
            output = recipe["outputs"][0]
            icon_item = QTableWidgetItem()
            pix = _crafting_item_icon(
                output.get("id"), self._items_by_id, self._icon_cache, 28,
                apply=lambda p, it=icon_item: it.setIcon(QIcon(p)),
                registry=self._icon_registry,
            )
            if pix is not None:
                icon_item.setIcon(QIcon(pix))
            self.table.setItem(row, 0, icon_item)

            name_item = QTableWidgetItem(output["name"])
            name_item.setData(Qt.UserRole, recipe)
            self.table.setItem(row, 1, name_item)

            grade = recipe.get("grade") or ""
            grade_item = _SortableTableWidgetItem(grade, RARITY_RANK.get(grade, 99))
            if grade in GRADE_COLORS:
                grade_item.setForeground(QColor(GRADE_COLORS[grade]))
            self.table.setItem(row, 2, grade_item)

            method = recipe.get("method") or ""
            method_item = QTableWidgetItem(_t(_METHOD_LABEL_KEYS[method]) if method in _METHOD_LABEL_KEYS else method)
            if method in _METHOD_COLORS:
                method_item.setForeground(QColor(_METHOD_COLORS[method]))
            self.table.setItem(row, 3, method_item)

        self.table.setSortingEnabled(True)

    def _on_row_clicked(self, row: int, _column: int):
        name_item = self.table.item(row, 1)
        if name_item is None:
            return
        self.selected_recipe = name_item.data(Qt.UserRole)
        self.accept()


class _MaterialTreeNodeWidget(QWidget):
    """One row of the Crafting Simulator's Baum view, recursively built from
    a _build_material_tree node. needed_qty is this node's own already-
    scaled requirement (root gets the top-level Anzahl; every child then
    multiplies needed_qty by its own "per one parent" qty going down) --
    same model validated in the browser preview before being ported here.

    Children are only built the first time a node is expanded (not eagerly
    for the whole tree) -- cheap for the shallow common case, but avoids
    building every node of a full 5-tier chain up front. Root and its direct
    children (depth 0/1) start expanded, matching the mockup's default."""

    def __init__(self, node: dict, needed_qty: int, owned_map: dict[str, int], items_by_id: dict,
                 icon_cache: "IconCache", registry: dict, on_owned_changed, depth: int = 0,
                 is_root: bool = False, parent=None):
        super().__init__(parent)
        self._node = node
        self._needed_qty = needed_qty
        self._owned_map = owned_map
        self._items_by_id = items_by_id
        self._icon_cache = icon_cache
        self._registry = registry
        self._on_owned_changed = on_owned_changed
        self._depth = depth
        self._expanded = is_root or depth == 1
        self._children_built = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(depth * 18, 0, 0, 0)
        outer.setSpacing(2)

        header = QHBoxLayout()
        header.setSpacing(8)

        has_children = bool(node.get("children"))
        self._expand_btn = QToolButton()
        self._expand_btn.setFixedWidth(18)
        if has_children:
            self._expand_btn.setText("▾" if self._expanded else "▸")
            self._expand_btn.setCursor(Qt.PointingHandCursor)
            self._expand_btn.clicked.connect(self._on_toggle)
        else:
            self._expand_btn.setEnabled(False)
        header.addWidget(self._expand_btn)

        icon_label = QLabel()
        icon_label.setFixedSize(28, 28)
        pix = _crafting_item_icon(
            node.get("id"), items_by_id, icon_cache, 28,
            apply=lambda p, lbl=icon_label: lbl.setPixmap(p), registry=registry,
        )
        if pix:
            icon_label.setPixmap(pix)
        header.addWidget(icon_label)

        name_label = QLabel(node.get("name") or "?")
        name_label.setObjectName("DetailInfo")
        item = items_by_id.get(node.get("id")) if node.get("id") else None
        grade = item.get("grade") if item else None
        if grade in GRADE_COLORS:
            name_label.setStyleSheet(f"color: {GRADE_COLORS[grade]};")
        header.addWidget(name_label)

        if has_children and not is_root:
            mastery = node.get("mastery")
            badge = QLabel(_t("arm_mastery_level", level=mastery if mastery is not None else '—'))
            badge.setObjectName("DetailEnchantValue")
            header.addWidget(badge)

        header.addStretch(1)

        if is_root:
            header.addWidget(QLabel(f"×{needed_qty:,}"))
        else:
            owned = owned_map.get(node.get("name"), 0)
            self._qty_label = QLabel(self._qty_text(needed_qty, owned))
            header.addWidget(self._qty_label)

            owned_spin = QSpinBox()
            owned_spin.setRange(0, 999_999)
            owned_spin.setFixedWidth(72)
            owned_spin.setValue(owned)
            owned_spin.setToolTip(_t("arm_already_owned_tooltip"))
            owned_spin.valueChanged.connect(lambda value, n=node.get("name"): on_owned_changed(n, value))
            header.addWidget(owned_spin)

        outer.addLayout(header)

        self._panel = QWidget()
        self._panel_layout = QVBoxLayout(self._panel)
        self._panel_layout.setContentsMargins(0, 0, 0, 0)
        self._panel_layout.setSpacing(2)
        self._panel.setVisible(self._expanded)
        outer.addWidget(self._panel)

        if self._expanded and has_children:
            self._build_children()

    @staticmethod
    def _qty_text(needed: int, owned: int) -> str:
        if owned <= 0:
            return f"×{needed:,}"
        if owned >= needed:
            return "✓ vorhanden"
        return f"×{needed:,} (noch {needed - owned:,})"

    def _build_children(self):
        if self._children_built:
            return
        self._children_built = True
        for child in self._node.get("children", []):
            child_qty = self._needed_qty * (child.get("qty") or 1)
            widget = _MaterialTreeNodeWidget(
                child, child_qty, self._owned_map, self._items_by_id, self._icon_cache,
                self._registry, self._on_owned_changed, depth=self._depth + 1,
            )
            self._panel_layout.addWidget(widget)

    def _on_toggle(self):
        self._expanded = not self._expanded
        self._expand_btn.setText("▾" if self._expanded else "▸")
        if self._expanded:
            self._build_children()
        self._panel.setVisible(self._expanded)


class CraftingCalculatorWindow(QMainWindow):
    """Crafting Simulator: pick exactly one item via the database picker,
    enter a quantity, and see its full recursive material/Kinah cost --
    replaces the old browsable filter/card-list guide entirely. Two main
    tabs: "Crafting Simulator" (Baum/Liste views of the selected recipe) and
    "Vergleich" (Direct-Craft vs. Transfer-chain Kinah/material comparison
    between a Start- and Ziel-item). Mirrors the design iterated on in the
    browser preview before being ported here."""

    def __init__(self, raw_items: list[dict], icon_cache: "IconCache", detail_cache: "ItemDetailCache", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle(_t("arm_crafting_calculator_title"))
        self.resize(660, 820)
        self.icon_cache = icon_cache
        self.detail_cache = detail_cache
        self._items_by_id = {it["id"]: it for it in raw_items}
        # url -> [(apply_fn, size, grade), ...] -- see _crafting_item_icon's
        # docstring for why this replaces a naive full-rebuild-on-icon_ready.
        self._crafting_icon_registry: dict[str, list] = {}

        self._recipes = _load_recipes()
        self._output_index = _build_recipe_output_index(self._recipes)

        # _build_recipe_output_index picks whichever recipe happens to come
        # first for a given output name, regardless of method -- the
        # Vergleich tab needs both variants when an item has one of each, so
        # index Direct-Craft and Transfer recipes separately here.
        self._direct_by_output: dict[str, dict] = {}
        self._transfer_by_output: dict[str, list[dict]] = {}
        for r in self._recipes:
            for output in r["outputs"]:
                if r["method"] == "Transfer":
                    self._transfer_by_output.setdefault(output["name"], []).append(r)
                else:
                    self._direct_by_output.setdefault(output["name"], r)

        # Upgrade-chain recipes indexed by their "source" item -- built from
        # ALL recipes, not just method=="Transfer" ones, because a real chain
        # hop is often a pure-Kinah upgrade with no Transfer Stone at all
        # (e.g. "Celestial Dragon Lord Boots" -> "Splendent Celestial Dragon
        # Lord Boots" for 15,000,000 Kina, no stone) -- restricting to
        # Transfer Stone recipes alone silently broke real chains one hop
        # before their end. See _transfer_source_name for the detection rule
        # and project_todo.md for how this was found and verified against
        # the real dataset. Lets the Vergleich tab walk a full multi-hop
        # chain between any Start and Ziel item.
        self._transfer_source_index = _build_transfer_source_index(self._recipes, self._items_by_id, self._output_index)

        self._current_recipe: dict | None = None
        self._current_tree: dict | None = None
        self._current_qty = 1
        self._owned_map: dict[str, int] = {}
        self._saved_targets: list[dict] = []  # session-only "Prio-Liste"

        self._compare_start: dict | None = None
        self._compare_target: dict | None = None

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(10)

        title = QLabel(_t("arm_crafting_calculator_title"))
        title.setObjectName("DetailHeader")
        outer.addWidget(title)

        self.main_tabs = QTabWidget()
        self.main_tabs.setObjectName("timerModeTabWidget")
        outer.addWidget(self.main_tabs, 1)

        self.main_tabs.addTab(self._build_simulator_tab(), _t("arm_crafting_simulator_tab"))
        self.main_tabs.addTab(self._build_compare_tab(), _t("arm_compare_tab"))

        # Same ordering fix as CraftingItemPickerDialog -- must connect
        # before any icon is requested below, since IconCache.request()
        # resolves already-on-disk icons synchronously and emits immediately.
        self.icon_cache.icon_ready.connect(self._on_crafting_icon_ready)

    def _on_crafting_icon_ready(self, url: str):
        entries = self._crafting_icon_registry.get(url)
        if not entries:
            return
        for apply, size, grade in entries:
            pix = self.icon_cache.pixmap(url, size, grade=grade)
            if pix is None:
                continue
            try:
                apply(pix)
            except RuntimeError:
                # The widget this entry pointed to was already torn down by
                # a rebuild (which clears the whole registry, but an icon
                # reply already queued before that can still land afterwards)
                # -- harmless, just skip it.
                pass

    def _item_grade(self, name: str | None, item_id: int | None) -> str | None:
        return _item_grade(name, item_id, self._items_by_id, self._output_index)

    def _transfer_source_name(self, recipe: dict) -> str | None:
        return _transfer_source_name(recipe, self._items_by_id, self._output_index)

    def _find_transfer_path(self, start_name: str, target_name: str) -> list[dict] | None:
        return _find_transfer_path(start_name, target_name, self._transfer_source_index)

    # ── "Crafting Simulator" tab: one selected recipe, Baum/Liste views ──

    def _build_simulator_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        pick_row = QHBoxLayout()
        pick_row.setSpacing(8)
        self.open_picker_btn = QPushButton(_t("arm_choose_item_from_db"))
        self.open_picker_btn.clicked.connect(self._open_item_picker)
        pick_row.addWidget(self.open_picker_btn)

        self.prio_btn = QPushButton(_t("arm_priority_list_btn"))
        self.prio_btn.clicked.connect(self._show_prio_menu)
        pick_row.addWidget(self.prio_btn)
        pick_row.addStretch(1)
        outer.addLayout(pick_row)

        self.sim_empty_label = QLabel(_t("arm_choose_item_hint"))
        self.sim_empty_label.setObjectName("DetailInfo")
        outer.addWidget(self.sim_empty_label)

        self.sim_content = QWidget()
        content_outer = QVBoxLayout(self.sim_content)
        content_outer.setContentsMargins(0, 0, 0, 0)
        content_outer.setSpacing(10)
        self.sim_content.setVisible(False)
        outer.addWidget(self.sim_content, 1)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        self.sim_icon_label = QLabel()
        self.sim_icon_label.setFixedSize(48, 48)
        header_row.addWidget(self.sim_icon_label)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        self.sim_name_label = QLabel()
        self.sim_name_label.setObjectName("DetailHeader")
        name_col.addWidget(self.sim_name_label)
        self.sim_grade_label = QLabel()
        name_col.addWidget(self.sim_grade_label)
        header_row.addLayout(name_col, 1)

        header_row.addWidget(QLabel(_t("arm_quantity_label")))
        self.sim_qty_spin = QSpinBox()
        self.sim_qty_spin.setRange(1, 999)
        self.sim_qty_spin.valueChanged.connect(self._on_qty_changed)
        header_row.addWidget(self.sim_qty_spin)

        self.sim_star_btn = QToolButton()
        self.sim_star_btn.setCheckable(True)
        self.sim_star_btn.setToolTip(_t("arm_add_to_priority_tooltip"))
        self.sim_star_btn.clicked.connect(self._on_star_toggled)
        header_row.addWidget(self.sim_star_btn)
        content_outer.addLayout(header_row)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(20)
        self.sim_mastery_label = QLabel()
        self.sim_mastery_label.setObjectName("DetailEnchantValue")
        stats_row.addWidget(self.sim_mastery_label)
        self.sim_kinah_label = QLabel()
        self.sim_kinah_label.setObjectName("DetailEnchantValue")
        stats_row.addWidget(self.sim_kinah_label)
        stats_row.addStretch(1)
        content_outer.addLayout(stats_row)

        view_row = QHBoxLayout()
        view_row.setSpacing(6)
        view_group = QButtonGroup(self)
        view_group.setExclusive(True)
        self.tree_view_btn = QPushButton(_t("arm_tree_view"))
        self.tree_view_btn.setObjectName("SkillFilterButton")
        self.tree_view_btn.setCheckable(True)
        self.tree_view_btn.setChecked(True)
        self.tree_view_btn.clicked.connect(lambda: self.sim_view_stack.setCurrentIndex(0))
        view_group.addButton(self.tree_view_btn)
        view_row.addWidget(self.tree_view_btn)

        self.list_view_btn = QPushButton(_t("arm_list_view"))
        self.list_view_btn.setObjectName("SkillFilterButton")
        self.list_view_btn.setCheckable(True)
        self.list_view_btn.clicked.connect(lambda: self.sim_view_stack.setCurrentIndex(1))
        view_group.addButton(self.list_view_btn)
        view_row.addWidget(self.list_view_btn)
        view_row.addStretch(1)
        content_outer.addLayout(view_row)
        self._sim_view_group = view_group  # kept alive against GC

        self.sim_view_stack = QStackedWidget()
        content_outer.addWidget(self.sim_view_stack, 1)

        self.tree_container = QWidget()
        self.tree_layout = QVBoxLayout(self.tree_container)
        self.tree_layout.setContentsMargins(0, 0, 0, 0)
        self.tree_layout.setSpacing(4)
        self.tree_layout.setAlignment(Qt.AlignTop)
        tree_scroll = QScrollArea()
        tree_scroll.setWidgetResizable(True)
        tree_scroll.setFrameShape(QFrame.NoFrame)
        tree_scroll.setWidget(self.tree_container)
        # QAbstractScrollArea's viewport paints its own QPalette::Base
        # background under Fusion (light grey), which no outer QSS rule
        # reaches -- same real bug found+fixed for the main app's Settings
        # page, applies here too since it's a separate widget instance.
        tree_scroll.viewport().setStyleSheet("background: transparent;")
        self.sim_view_stack.addWidget(tree_scroll)

        list_page = QWidget()
        list_outer = QVBoxLayout(list_page)
        list_outer.setContentsMargins(0, 0, 0, 0)
        list_outer.setSpacing(8)
        copy_row = QHBoxLayout()
        copy_row.addStretch(1)
        self.copy_list_btn = QPushButton(_t("arm_copy_to_clipboard"))
        self.copy_list_btn.clicked.connect(self._copy_flat_list)
        copy_row.addWidget(self.copy_list_btn)
        list_outer.addLayout(copy_row)

        self.flat_table = QTableWidget(0, 3)
        self.flat_table.setHorizontalHeaderLabels([_t("arm_col_material"), _t("arm_col_needed"), _t("arm_col_owned")])
        self.flat_table.verticalHeader().setVisible(False)
        self.flat_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.flat_table.horizontalHeader().setStretchLastSection(True)
        self.flat_table.setColumnWidth(0, 300)
        self.flat_table.setIconSize(QSize(28, 28))
        self.flat_table.setSortingEnabled(True)
        list_outer.addWidget(self.flat_table, 1)
        self.sim_view_stack.addWidget(list_page)

        return page

    def _open_item_picker(self):
        dlg = CraftingItemPickerDialog(self._items_by_id, self.icon_cache, parent=self)
        if dlg.exec() != QDialog.Accepted or not dlg.selected_recipe:
            return
        self._select_recipe(dlg.selected_recipe)

    def _show_prio_menu(self):
        menu = QMenu(self)
        if not self._saved_targets:
            action = menu.addAction(_t("arm_no_saved_targets"))
            action.setEnabled(False)
        else:
            for recipe in self._saved_targets:
                name = recipe["outputs"][0].get("name") or "?"
                action = menu.addAction(name)
                action.triggered.connect(lambda checked=False, r=recipe: self._select_recipe(r))
        menu.exec(self.prio_btn.mapToGlobal(self.prio_btn.rect().bottomLeft()))

    def _select_recipe(self, recipe: dict):
        self._current_recipe = recipe
        self._current_qty = 1
        self._owned_map = {}
        self._current_tree = _build_material_tree(recipe, self._output_index, self._items_by_id)

        self.sim_qty_spin.blockSignals(True)
        self.sim_qty_spin.setValue(1)
        self.sim_qty_spin.blockSignals(False)

        self.sim_empty_label.setVisible(False)
        self.sim_content.setVisible(True)
        self._rebuild_simulator_views()

    def _on_qty_changed(self, value: int):
        self._current_qty = value
        self._rebuild_simulator_views()

    def _on_star_toggled(self, checked: bool):
        recipe = self._current_recipe
        name = recipe["outputs"][0].get("name")
        self._saved_targets = [t for t in self._saved_targets if t["outputs"][0].get("name") != name]
        if checked:
            self._saved_targets.append(recipe)
        self.sim_star_btn.setText("★" if checked else "☆")

    def _on_owned_changed(self, name: str, value: int):
        if value <= 0:
            self._owned_map.pop(name, None)
        else:
            self._owned_map[name] = value
        self._rebuild_tree_view()
        self._rebuild_flat_view()

    def _rebuild_simulator_views(self):
        if not self._current_recipe:
            return
        self._crafting_icon_registry = {}
        recipe = self._current_recipe
        output = recipe["outputs"][0]

        self.sim_name_label.setText(output.get("name") or "?")
        grade = recipe.get("grade")
        self.sim_grade_label.setText(grade or "")
        self.sim_grade_label.setStyleSheet(f"color: {GRADE_COLORS.get(grade, '#94a3b8')}; font-weight: 700;")

        starred = any(t["outputs"][0].get("name") == output.get("name") for t in self._saved_targets)
        self.sim_star_btn.blockSignals(True)
        self.sim_star_btn.setChecked(starred)
        self.sim_star_btn.blockSignals(False)
        self.sim_star_btn.setText("★" if starred else "☆")

        pix = _crafting_item_icon(
            output.get("id"), self._items_by_id, self.icon_cache, 44,
            apply=lambda p: self.sim_icon_label.setPixmap(p), registry=self._crafting_icon_registry,
        )
        if pix:
            self.sim_icon_label.setPixmap(pix)

        mastery = recipe.get("masteryLevel")
        self.sim_mastery_label.setText(_t("arm_mastery_level", level=mastery if mastery is not None else '—'))
        kinah = _compute_tree_kinah(self._current_tree, self._current_qty)
        self.sim_kinah_label.setText(_t("arm_kinah_total", amount=f"{kinah:,}"))

        self._rebuild_tree_view()
        self._rebuild_flat_view()

    def _rebuild_tree_view(self):
        _clear_layout(self.tree_layout)
        self.tree_layout.addWidget(_MaterialTreeNodeWidget(
            self._current_tree, self._current_qty, self._owned_map, self._items_by_id,
            self.icon_cache, self._crafting_icon_registry, self._on_owned_changed, is_root=True,
        ))

    def _rebuild_flat_view(self):
        # Sorting must be off while (re-)populating -- see CraftingItemPickerDialog._rebuild_table.
        self.flat_table.setSortingEnabled(False)
        totals: dict[str, dict] = {}
        _flatten_material_tree(self._current_tree, self._current_qty, totals)
        rows = sorted(totals.items(), key=lambda kv: kv[0])
        self.flat_table.setRowCount(len(rows))
        for row, (name, data) in enumerate(rows):
            name_item = QTableWidgetItem(name)
            pix = _crafting_item_icon(
                data.get("id"), self._items_by_id, self.icon_cache, 28,
                # Captures the item itself, not its row index -- a resort
                # between the async icon request and its callback would
                # otherwise paint the icon onto whatever now sits at that
                # row instead of the material it was actually requested for.
                apply=lambda p, it=name_item: it.setIcon(QIcon(p)),
                registry=self._crafting_icon_registry,
            )
            if pix:
                name_item.setIcon(QIcon(pix))
            grade = self._item_grade(name, data.get("id"))
            if grade in GRADE_COLORS:
                name_item.setForeground(QColor(GRADE_COLORS[grade]))
            self.flat_table.setItem(row, 0, name_item)
            self.flat_table.setItem(row, 1, _SortableTableWidgetItem(f"{data['qty']:,}", data["qty"]))

            owned_spin = QSpinBox()
            owned_spin.setRange(0, 999_999)
            owned_spin.setValue(self._owned_map.get(name, 0))
            owned_spin.valueChanged.connect(lambda value, n=name: self._on_owned_changed(n, value))
            self.flat_table.setCellWidget(row, 2, owned_spin)
        self.flat_table.setSortingEnabled(True)

    def _copy_flat_list(self):
        totals: dict[str, dict] = {}
        _flatten_material_tree(self._current_tree, self._current_qty, totals)
        lines = [f"{name} x{data['qty']:,}" for name, data in sorted(totals.items())]
        QApplication.clipboard().setText("\n".join(lines))

    # ── "Vergleich" tab: Direct-Craft vs. Transfer-chain comparison ──

    def _build_compare_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        note = QLabel(_t("arm_compare_note"))
        note.setObjectName("DetailInfo")
        note.setWordWrap(True)
        outer.addWidget(note)

        setup_row = QHBoxLayout()
        setup_row.setSpacing(10)
        self.compare_start_btn = QPushButton(_t("arm_choose_start_item"))
        self.compare_start_btn.clicked.connect(lambda: self._pick_compare_slot("start"))
        setup_row.addWidget(self.compare_start_btn)
        arrow = QLabel("→")
        arrow.setObjectName("ChainArrow")
        setup_row.addWidget(arrow)
        self.compare_target_btn = QPushButton(_t("arm_choose_target_item"))
        self.compare_target_btn.clicked.connect(lambda: self._pick_compare_slot("target"))
        setup_row.addWidget(self.compare_target_btn)
        setup_row.addStretch(1)
        outer.addLayout(setup_row)

        self.compare_result_label = QLabel()
        self.compare_result_label.setObjectName("DetailDisclaimer")
        self.compare_result_label.setWordWrap(True)
        outer.addWidget(self.compare_result_label)

        columns_row = QHBoxLayout()
        columns_row.setSpacing(20)
        (self.compare_direct_box, self.compare_direct_layout, self.compare_direct_kinah,
         self.compare_direct_costs_section, self.compare_direct_costs_layout) = self._build_compare_column(_t("arm_direct_craft_column"))
        columns_row.addWidget(self.compare_direct_box, 1)
        (self.compare_transfer_box, self.compare_transfer_layout, self.compare_transfer_kinah,
         self.compare_transfer_costs_section, self.compare_transfer_costs_layout) = self._build_compare_column(_t("arm_method_transfer"))
        columns_row.addWidget(self.compare_transfer_box, 1)
        outer.addLayout(columns_row, 1)

        return page

    def _build_compare_column(self, title: str):
        box = QFrame()
        box.setObjectName("TopBar")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("DetailHeader")
        layout.addWidget(title_label)

        kinah_label = QLabel(_t("arm_kinah_dash"))
        kinah_label.setObjectName("DetailEnchantValue")
        layout.addWidget(kinah_label)

        # Separate from the crafting-fee "Kinah" stat above and from the
        # material list below -- a pure-Kinah "Splendent" upgrade step (item
        # + several million Kina, no real material) isn't a "material" and
        # its cost dwarfs the small per-hop crafting fee, so it gets called
        # out here as its own line per hop instead of disappearing into
        # either of those (see project_todo.md for why this was needed).
        costs_section = QWidget()
        costs_outer = QVBoxLayout(costs_section)
        costs_outer.setContentsMargins(0, 0, 0, 0)
        costs_outer.setSpacing(4)
        costs_label = QLabel(_t("arm_splendent_upgrade_costs"))
        costs_label.setObjectName("EquipSectionLabel")
        costs_outer.addWidget(costs_label)
        costs_layout = QVBoxLayout()
        costs_layout.setContentsMargins(0, 0, 0, 0)
        costs_layout.setSpacing(4)
        costs_outer.addLayout(costs_layout)
        costs_section.setVisible(False)
        layout.addWidget(costs_section)

        materials_container = QWidget()
        materials_layout = QVBoxLayout(materials_container)
        materials_layout.setContentsMargins(0, 0, 0, 0)
        materials_layout.setSpacing(4)
        materials_layout.setAlignment(Qt.AlignTop)
        layout.addWidget(materials_container, 1)

        return box, materials_layout, kinah_label, costs_section, costs_layout

    def _reachable_targets(self, start_name: str) -> set[str]:
        """All items reachable from start_name through the upgrade-chain
        graph -- restricts the Vergleich tab's Ziel picker to items actually
        craftable from the chosen Start item. Verified against the real
        dataset that this also naturally keeps Elyos/Asmodae lines apart
        without any separate race check: e.g. "Star Dragon Lord Dagger"
        only ever reaches Crimson/Dark/Demonic/Ebony Dragon Lord Daggers
        (its own Asmodae-side line), never Celestial/Obsidian/White/Wise/
        True Dragon Lord ones (the Elyos-side line for the same slot) --
        the recipe data itself never crosses between the two."""
        reachable: set[str] = set()
        queue = deque([start_name])
        visited = {start_name}
        while queue:
            current = queue.popleft()
            for recipe in self._transfer_source_index.get(current, []):
                output_name = recipe["outputs"][0].get("name")
                if output_name in visited:
                    continue
                visited.add(output_name)
                reachable.add(output_name)
                queue.append(output_name)
        return reachable

    def _pick_compare_slot(self, slot: str):
        allowed_names = None
        min_grade = None
        if slot == "target" and self._compare_start:
            start_name = self._compare_start["outputs"][0].get("name")
            allowed_names = self._reachable_targets(start_name)
            if not allowed_names:
                self.compare_result_label.setText(_t("arm_no_transfer_targets", start=start_name))
                return
        elif slot == "start":
            # Confirmed by the user: no real Transfer/Splendent upgrade
            # chain currently starts below "Unique" grade -- Common/Rare/
            # Legend items would just dead-end the Ziel picker afterwards.
            min_grade = "Unique"

        dlg = CraftingItemPickerDialog(
            self._items_by_id, self.icon_cache, parent=self, allowed_names=allowed_names, min_grade=min_grade,
            # Cooking items are consumables -- never part of an equipment
            # Transfer chain, so pointless clutter for either picker here.
            excluded_professions=frozenset({"Cooking"}),
        )
        if dlg.exec() != QDialog.Accepted or not dlg.selected_recipe:
            return
        recipe = dlg.selected_recipe
        name = recipe["outputs"][0].get("name") or "?"
        if slot == "start":
            self._compare_start = recipe
            self.compare_start_btn.setText(name)
            # A new Start may no longer even reach whatever Ziel was picked
            # before -- clear it rather than leave a stale, possibly
            # unreachable pairing in place.
            self._compare_target = None
            self.compare_target_btn.setText(_t("arm_choose_target_item"))
        else:
            self._compare_target = recipe
            self.compare_target_btn.setText(name)
        self._rebuild_compare_result()

    def _fill_compare_column(self, layout: QVBoxLayout, totals: dict[str, dict], cheaper_names: set[str] = frozenset()):
        for name, data in sorted(totals.items()):
            row_widget = QWidget()
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            icon_label = QLabel()
            icon_label.setFixedSize(24, 24)
            pix = _crafting_item_icon(
                data.get("id"), self._items_by_id, self.icon_cache, 24,
                apply=lambda p, lbl=icon_label: lbl.setPixmap(p), registry=self._crafting_icon_registry,
            )
            if pix:
                icon_label.setPixmap(pix)
            row.addWidget(icon_label)
            name_label = QLabel(name)
            grade = self._item_grade(name, data.get("id"))
            if grade in GRADE_COLORS:
                name_label.setStyleSheet(f"color: {GRADE_COLORS[grade]};")
            row.addWidget(name_label, 1)
            qty_label = QLabel(f"×{data['qty']:,}")
            # Only a material needed on both sides gets a color at all -- and
            # only its quantity number, not a border around the whole column
            # (user explicitly disliked the box-border "cheaper" highlight).
            if name in cheaper_names:
                qty_label.setStyleSheet("color: #4ade80; font-weight: 700;")
            row.addWidget(qty_label)
            layout.addWidget(row_widget)

    def _fill_compare_costs(self, layout: QVBoxLayout, costs: list[tuple[str, int | None, int]]):
        for name, item_id, kina_qty in costs:
            row_widget = QWidget()
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            icon_label = QLabel()
            icon_label.setFixedSize(24, 24)
            pix = _crafting_item_icon(
                item_id, self._items_by_id, self.icon_cache, 24,
                apply=lambda p, lbl=icon_label: lbl.setPixmap(p), registry=self._crafting_icon_registry,
            )
            if pix:
                icon_label.setPixmap(pix)
            row.addWidget(icon_label)
            row.addWidget(QLabel(name), 1)
            amount_label = QLabel(_t("arm_kinah_amount", amount=f"{kina_qty:,}"))
            amount_label.setObjectName("DetailEnchantValue")
            row.addWidget(amount_label)
            layout.addWidget(row_widget)

    def _rebuild_compare_result(self):
        _clear_layout(self.compare_direct_layout)
        _clear_layout(self.compare_transfer_layout)
        _clear_layout(self.compare_direct_costs_layout)
        _clear_layout(self.compare_transfer_costs_layout)
        self.compare_direct_costs_section.setVisible(False)
        self.compare_transfer_costs_section.setVisible(False)
        self.compare_direct_kinah.setText(_t("arm_kinah_dash"))
        self.compare_transfer_kinah.setText(_t("arm_kinah_dash"))

        target = self._compare_target
        if not target:
            self.compare_result_label.setText(_t("arm_choose_target_first"))
            return
        target_name = target["outputs"][0].get("name")

        direct_totals: dict[str, dict] = {}
        direct_recipe = self._direct_by_output.get(target_name)
        direct_kinah = None
        if direct_recipe:
            direct_tree = _build_material_tree(direct_recipe, self._output_index, self._items_by_id)
            direct_kinah = _compute_tree_kinah(direct_tree, 1)
            _flatten_material_tree(direct_tree, 1, direct_totals)
            self.compare_direct_kinah.setText(_t("arm_kinah_colon_amount", amount=f"{direct_kinah:,}"))
        else:
            note = QLabel(_t("arm_no_direct_recipe"))
            note.setObjectName("DetailInfo")
            self.compare_direct_layout.addWidget(note)

        start = self._compare_start
        path = None
        transfer_totals: dict[str, dict] = {}
        if not start:
            note = QLabel(_t("arm_choose_start_first"))
            note.setObjectName("DetailInfo")
            self.compare_transfer_layout.addWidget(note)
        else:
            start_name = start["outputs"][0].get("name")
            path = self._find_transfer_path(start_name, target_name)
            if not path:
                note = QLabel(_t("arm_no_transfer_chain"))
                note.setObjectName("DetailInfo")
                self.compare_transfer_layout.addWidget(note)
            else:
                # Every hop on the path counts, not just the last one -- the
                # old "only the last hop" shortcut hid real cost (see
                # project_todo.md). Every hop's own upgraded-item input is
                # either the previous hop's output or (for the first hop)
                # the given Start item -- both are already "owned" by
                # construction, not a real cost.
                owned_inputs = {h["outputs"][0].get("name") for h in path} | {start_name}
                transfer_kinah = 0
                splendent_costs: list[tuple[str, int | None, int]] = []
                for hop in path:
                    transfer_kinah += hop.get("goldCost", 0)
                    # A hop whose only inputs besides its own source item are
                    # pure Kina rows is a "Splendent" upgrade, not a material
                    # cost -- broken out below as its own cost line instead
                    # of either disappearing into the material list (it
                    # isn't one) or being missed out of the total entirely
                    # (its Kina cost usually dwarfs every other hop's).
                    source_name = self._transfer_source_name(hop)
                    other_inputs = [i for i in hop["inputs"] if i.get("name") != source_name]
                    is_splendent_only = bool(other_inputs) and all("Kina" in (i.get("name") or "") for i in other_inputs)
                    if is_splendent_only:
                        kina_qty = sum(i.get("qty") or 0 for i in other_inputs)
                        splendent_costs.append((hop["outputs"][0].get("name") or "?", hop["outputs"][0].get("id"), kina_qty))
                        continue
                    for material in hop["inputs"]:
                        name = _resolve_material_name(material.get("name"), material.get("id"), self._items_by_id)
                        if name in owned_inputs:
                            continue
                        entry = transfer_totals.setdefault(name, {"qty": 0, "id": material.get("id")})
                        entry["qty"] += material.get("qty") or 1
                self.compare_transfer_kinah.setText(_t("arm_kinah_colon_amount", amount=f"{transfer_kinah:,}"))

                if splendent_costs:
                    self.compare_transfer_costs_section.setVisible(True)
                    self._fill_compare_costs(self.compare_transfer_costs_layout, splendent_costs)

        # No whole-column highlight (user explicitly dislikes it) -- only the
        # quantity number of a material that's needed on BOTH sides gets
        # colored, on whichever side needs less of it.
        shared_names = set(direct_totals) & set(transfer_totals)
        direct_cheaper = {n for n in shared_names if direct_totals[n]["qty"] < transfer_totals[n]["qty"]}
        transfer_cheaper = {n for n in shared_names if transfer_totals[n]["qty"] < direct_totals[n]["qty"]}
        self._fill_compare_column(self.compare_direct_layout, direct_totals, direct_cheaper)
        self._fill_compare_column(self.compare_transfer_layout, transfer_totals, transfer_cheaper)

        self.compare_result_label.setText(_t("arm_transfer_steps_found", count=len(path)) if path else "")

    def update_language(self, language: str):
        """Forwarded by ItemDatabaseWindow.update_language() (see there).
        Re-applies text to this window's always-visible top-level chrome --
        same reasoning/caveat as LoadoutWindow.update_language()."""
        set_armory_language(language)
        self.setWindowTitle(_t("arm_crafting_calculator_title"))
        self.main_tabs.setTabText(0, _t("arm_crafting_simulator_tab"))
        self.main_tabs.setTabText(1, _t("arm_compare_tab"))
        self.open_picker_btn.setText(_t("arm_choose_item_from_db"))
        self.prio_btn.setText(_t("arm_priority_list_btn"))
        # compare_start_btn/compare_target_btn intentionally NOT reset here --
        # their text shows the picked item's real name once selected, not
        # static chrome; resetting them would wipe out a real selection.

    def closeEvent(self, event):
        logger.debug("CraftingCalculatorWindow closed")
        super().closeEvent(event)


# Confirmed real naming pattern (see project_todo.md): the top-tier
# equipment line's root item name marks its race -- "True Dragon Lord" is
# Elyos, "Star Dragon Lord" is Asmodae. Every other tier in that race's
# chain (Splendent/White/Wise/Celestial/Obsidian for Elyos, Splendent/
# Dark/Ebony/Demonic/Crimson for Asmodae) is reached from this root via
# _ordered_tier_chain.
RACE_TIER_ROOT = {"Elyos": "True Dragon Lord", "Asmodae": "Star Dragon Lord"}

# "Abyss Gear" (Gear Type-Filter, PvP) roots are race-locked, unlike every
# other Dungeon-Quelle tag -- e.g. "Guardian Decanus Ring" and "Archon
# Decanus Ring" are two different items, not the same item reachable by
# both races. Confirmed directly in-game (User screenshot, 2026-08-27:
# Elyos's own Abyss shop only ever lists "Guardian ..." items).
_ABYSS_GEAR_RACE_PREFIX = {"Elyos": "Guardian", "Asmodae": "Archon"}

# Slot -> the trailing "type word" its item name ends in at every tier of
# this line (e.g. "True Dragon Lord Boots", "Wise Dragon Lord Boots") --
# verified against the real catalog to differ from the slot's own
# categoryName for three slots (Torso is category "Top" but the item name
# ends in "Breastplate"; Pants is category "Legs" but ends in "Greaves";
# Boots is category "Shoes" but ends in "Boots"). MainHand isn't listed
# here -- its type word depends on the equipped class via
# CLASS_WEAPON_CATEGORY instead. Amulet/Brooch stay excluded (no craftable
# tier item for them in the crafted line, and Brooch isn't live at global
# release yet) -- Bracelet WAS excluded for the same reason but is back in
# now that dungeon sets (which do have Bracelet pieces, e.g. "Faded Shadow
# Bracelet") are part of the Schnellauswahl pool too (User-Wunsch,
# 2026-08-26: "die Bracelet Slots mit reinbringen ... gesamt checkbox und
# br1 und br2 separat").
_QUICK_GEAR_SLOT_WORDS = {
    "SubHand": "Guard",
    "Helmet": "Helm",
    "Shoulder": "Pauldrons",
    "Torso": "Breastplate",
    "Gloves": "Gloves",
    "Pants": "Greaves",
    "Boots": "Boots",
    "Earring1": "Earrings",
    "Earring2": "Earrings",
    "Necklace": "Necklace",
    "Ring1": "Ring",
    "Ring2": "Ring",
    "Bracelet1": "Bracelet",
    "Bracelet2": "Bracelet",
}

# Category prefilter groups for the Schnellauswahl popup -- same 3-group
# split ("Waffe/Guard", "Rüstungsteile", "Schmuck") requested for the
# feature, each a checkbox controlling whether that group's slots are
# included in this run's auto-equip.
# 2nd element is a translation KEY, not display text -- see _QUICK_GEAR_
# SLOT_LABELS above for why (module-level, evaluated once at import time).
_QUICK_GEAR_CATEGORY_GROUPS = [
    ("weapon", "arm_group_weapon", ["MainHand", "SubHand"]),
    ("armor", "arm_group_armor", ["Helmet", "Shoulder", "Torso", "Gloves", "Pants", "Boots"]),
    ("accessory", "arm_group_accessory", ["Earring1", "Earring2", "Necklace", "Ring1", "Ring2", "Bracelet1", "Bracelet2"]),
]

# Explicit per-slot name overrides for the 2 "Crafting" prefix-grouped
# weapon sets (see compute_dungeon_sets.py) -- their real item names are
# flavor text ("Corroded Sovereign's Malice" for Dagger, "Lava Heart Barrier"
# for Guard, ...) with no reliable "{prefix} {type_word}" pattern at all
# (confirmed against the real catalog), unlike every other crafted tier/
# dungeon set _resolve_slot_item already handles generically. Without this,
# these 2 sets listed correctly in Item-Set but resolved 0 equip slots.
_CRAFTING_WEAPON_NAMES = {
    "Corroded Sovereign's": {
        "Greatsword": "Corroded Sovereign's Raptorial Greatsword",
        "Longsword": "Corroded Sovereign's Cinderblade",
        "Dagger": "Corroded Sovereign's Malice",
        "Bow": "Corroded Sovereign's Cinderbow",
        "Spellbook": "Corroded Sovereign's Blazebloom",
        "Orb": "Corroded Sovereign's Crimson Blazestone",
        "Mace": "Corroded Sovereign's Searing Mallet",
        "Staff": "Corroded Sovereign's Searing Staff",
        "Fist": "Corroded Sovereign's Blazestone Fist",
        "Guard": "Corroded Sovereign's Chains",
    },
    "Lava Heart": {
        "Greatsword": "Lava Heart Terrorblade",
        "Longsword": "Lava Heart Flamesword",
        "Dagger": "Lava Heart Deathblade",
        "Bow": "Lava Heart Flamebow",
        "Spellbook": "Lava Heart Tome",
        "Orb": "Lava Heart Voidgem",
        "Mace": "Lava Heart Firemace",
        "Staff": "Lava Heart Flamestaff",
        "Fist": "Lava Heart Gauntlet",
        "Guard": "Lava Heart Barrier",
    },
}

# Slots tried in order to find A real item for a given Item-Set prefix, to
# read its actual max-enchant range off of -- "Ring" alone (the reference
# _tier_grade already uses for grade) doesn't exist for the 2 weapon-only
# Crafting sets, so this falls through to a slot they do have.
_ENCHANT_REFERENCE_SLOTS = ["Ring1", "Helmet", "MainHand", "SubHand", "Necklace", "Bracelet1"]

# Links the global PvP/PvE/Neutral item-picker filter (the 3 pill buttons in
# LoadoutWindow's class row, _active_gear_types) to which Gear Type-Filter
# options the Schnellauswahl offers (User-Wunsch, 2026-08-26: "wenn PvE
# ausgewählt - bitte 'Crafting' Filter anzeigen. wenn PvP ausgewählt - bitte
# 'Abyss Gear' anzeigen. Wenn Neutral ausgewählt - bitte Dungeon Gear
# anzeigen."). "Abyss Gear" (Guardian=Elyos/Archon=Asmodae, confirmed
# in-game 2026-08-27) is built via compute_dungeon_sets.py's
# build_abyss_gear() and filtered to the character's own race in
# _rebuild_tier_combo.
_GEAR_TYPE_TO_QUICK_SELECT_TAGS = {
    "PvE": {"Crafting"},
    "PvP": {"Abyss Gear"},
    "Neutral": {"Expedition", "Sanctuary"},
}

# Dungeon gear (Neutral gear type, User-Wunsch 2026-08-26: "zusätzlich zu dem
# gecrafteten Gear kommt in die Auswahl das Equipment aus den Dungeons") is
# NOT one clean tier ladder like RACE_TIER_ROOT's crafted line -- it's ~174
# independent named sets (e.g. "Abyssal Helm"/"Abyssal Ring"/... share the
# root "Abyssal"). Their real drop location isn't in the raw catalog at all;
# the closest signal is each item's detail "sources" list. Which tags
# actually produce real, level-45, >=3-slot sets is entirely a property of
# the current data (compute_dungeon_sets.py checks all ~21 tags found in the
# catalog and keeps whichever aren't empty -- e.g. Attendance/Subscribe/
# Ascension never do, they're login/cash-shop rewards, not gear), so this is
# read straight from data/dungeon_sets.json's own keys at runtime rather
# than a hardcoded list that would drift out of sync with it.
_dungeon_sets_cache: dict[str, dict[str, str]] | None = None
_DUNGEON_SETS_PATH = Path(__file__).parent / "data" / "dungeon_sets.json"


def _build_dungeon_sets(items_by_id: dict, detail_cache: "ItemDetailCache") -> dict[str, dict[str, str]]:
    """Returns {source_tag: {root_name: grade}}, one entry per source tag
    compute_dungeon_sets.py found at least one real set for -- the grade
    lets the Rarität filter narrow the Dungeon-Set dropdown too (User-
    Wunsch, 2026-08-26: "Ich weiß ja, dass in der Liste auch blaue Sets
    dabei sind, nicht nur goldene" -- Legend/blue and Unique/gold both
    appear, confirmed real: e.g. Expedition alone is 13 Unique/6 Legend/3
    Epic at level 45).

    Loads the precomputed data/dungeon_sets.json (see compute_dungeon_sets.py
    -- same offline-maintenance-script convention as fetch_item_details.py,
    run whenever the catalog is refreshed) instead of scanning live: an
    earlier live version of this (grouping ~3000 items and reading each
    one's detail file via ItemDetailCache.request()) measured ~17s on a
    cold cache -- far too slow for a dialog that should open instantly.
    Falls back to an empty result if the precomputed file is missing
    (e.g. a dev checkout that hasn't run the script yet), rather than ever
    falling back to the slow live scan again."""
    global _dungeon_sets_cache
    if _dungeon_sets_cache is not None:
        return _dungeon_sets_cache

    result: dict[str, dict[str, str]] = {}
    if _DUNGEON_SETS_PATH.exists():
        try:
            result = json.loads(_DUNGEON_SETS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to load %s -- Dungeon-Quelle dropdown will be empty", _DUNGEON_SETS_PATH)
    else:
        logger.warning("%s not found -- run compute_dungeon_sets.py. Dungeon-Quelle dropdown will be empty.", _DUNGEON_SETS_PATH)

    _dungeon_sets_cache = result
    return result

# Per-slot labels for the "Manuelle Auswahl" accordion panel under each group
# -- SLOT_LAYOUT's own labels give both ring/earring slots the identical
# "Ringe"/"Ohrringe" text (fine for the paperdoll, ambiguous as two separate
# checkboxes), so numbered here instead.
# Values are translation KEYS, not display text (module-level -- looked up
# via _t() at actual widget-build time, never baked in here, since this
# dict is only ever evaluated once at import time).
_QUICK_GEAR_SLOT_LABELS = {
    "MainHand": "arm_slot_mainhand",
    "SubHand": "arm_slot_subhand",
    "Helmet": "arm_slot_helmet",
    "Shoulder": "arm_slot_shoulder",
    "Torso": "arm_slot_torso",
    "Gloves": "arm_slot_gloves",
    "Pants": "arm_slot_pants",
    "Boots": "arm_slot_boots",
    "Earring1": "arm_slot_earring1",
    "Earring2": "arm_slot_earring2",
    "Necklace": "arm_slot_necklace",
    "Ring1": "arm_slot_ring1",
    "Ring2": "arm_slot_ring2",
    "Bracelet1": "arm_slot_bracelet1",
    "Bracelet2": "arm_slot_bracelet2",
}

# Eigenschaften-Priorität: which slot ids fall under which of the editor's
# 4 category tabs (User-Wunsch 2026-08-27: "Hier eventuell auch mit Reitern
# arbeiten? Waffe/Guard, Rüstung, Schmuck, Bracelets") -- one shared
# priority list per category rather than per exact slot, since the guide's
# own per-slot lists already mostly agreed within each of these groups.
# Brooch1/2 excluded, same as elsewhere in this file (not active at global
# release yet).
# 2nd element is a translation KEY, not display text (module-level -- see
# _QUICK_GEAR_SLOT_LABELS above for why).
_STAT_PRIORITY_CATEGORIES: list[tuple[str, str, list[str]]] = [
    ("weapon", "arm_category_weapon", ["MainHand", "SubHand"]),
    ("armor", "arm_category_armor", ["Helmet", "Shoulder", "Torso", "Gloves", "Pants", "Boots"]),
    ("jewelry", "arm_category_jewelry", ["Earring1", "Earring2", "Necklace", "Amulet", "Ring1", "Ring2"]),
    ("bracelet", "arm_category_bracelet", ["Bracelet1", "Bracelet2"]),
]
_SLOT_TO_STAT_CATEGORY: dict[str, str] = {
    slot_id: key for key, _, slots in _STAT_PRIORITY_CATEGORIES for slot_id in slots
}

# Eigenschaften-Priorität profiles are keyed [gear_type][role][category] ->
# an ordered list of up to _STAT_PRIORITY_MAX_ENTRIES stat names (User-
# Wunsch: "Filter PvP und PvE drin... Rollen Angreifer, Verteidiger und
# Support... Prioliste bis zu 7 Werte... als Profile, die man setzen kann").
_STAT_PRIORITY_GEAR_TYPES = ("PvE", "PvP")
_STAT_PRIORITY_ROLES = ("Angreifer", "Verteidiger", "Support")
# User-Wunsch: "Angreifer 'Orange', Verteidiger 'Blau' und Support 'Grün' ...
# bei Auswahl des Reiters eine entsprechende Farbkombi" -- objectName per
# role so styles.qss can give each Rolle button its own :checked accent
# color (see #RoleButtonAngreifer/Verteidiger/Support there), used by both
# QuickStatSelectDialog and StatPriorityEditorDialog's Rolle buttons.
_ROLE_BUTTON_OBJECT_NAMES = {
    "Angreifer": "RoleButtonAngreifer",
    "Verteidiger": "RoleButtonVerteidiger",
    "Support": "RoleButtonSupport",
}
# "Angreifer"/"Verteidiger"/"Support" stay the stable internal role
# identifiers (object names above, persisted profile dict keys) -- only the
# DISPLAYED button text is translated, via this label lookup.
_ROLE_LABEL_KEYS = {
    "Angreifer": "arm_role_attacker",
    "Verteidiger": "arm_role_defender",
    "Support": "arm_role_support",
}
_STAT_PRIORITY_MAX_ENTRIES = 7

# Starting point for every one of the 6 (Gear-Typ x Rolle) profiles, all
# identical until the player edits them via the gear-icon editor -- only
# PvE/Angreifer has real guide backing today (project_gear_stat_guide.md,
# 2026-08-24, offered as a "recommendation, please double-check"); the
# other 5 profiles reuse it as a reasonable starting point rather than
# shipping empty (an empty list would leave every substat slot unfilled).
_DEFAULT_STAT_PRIORITY_BY_CATEGORY: dict[str, list[str]] = {
    "weapon": ["Weapon Damage Boost", "Combat Speed", "Damage Boost", "Might", "Precision", "Attack", "Multi-hit Chance"],
    "armor": ["Damage Boost", "Attack Increase", "Critical Damage Boost", "Attack", "Endurance", "Defense Increase", "Accuracy"],
    "jewelry": ["Attack", "Accuracy", "Critical Hit"],
    "bracelet": ["Attack", "Critical Hit", "HP"],
}


def _default_stat_priority_profiles() -> dict[str, dict[str, dict[str, list[str]]]]:
    return {
        gear_type: {
            role: {cat: list(names) for cat, names in _DEFAULT_STAT_PRIORITY_BY_CATEGORY.items()}
            for role in _STAT_PRIORITY_ROLES
        }
        for gear_type in _STAT_PRIORITY_GEAR_TYPES
    }


def _merge_stat_priority_profiles(saved: dict | None) -> dict[str, dict[str, dict[str, list[str]]]]:
    """Merges a persisted profiles dict onto the defaults -- keeps a saved
    profile missing a not-yet-existing gear_type/role/category (e.g. an
    older profile from before this feature) filled in rather than blank."""
    result = _default_stat_priority_profiles()
    for gear_type, roles in (saved or {}).items():
        if gear_type not in result:
            continue
        for role, categories in (roles or {}).items():
            if role not in result[gear_type]:
                continue
            for category, names in (categories or {}).items():
                if category in result[gear_type][role] and isinstance(names, list):
                    result[gear_type][role][category] = [str(n) for n in names][:_STAT_PRIORITY_MAX_ENTRIES]
    return result


# Precomputed real subStat names per category (compute_stat_priority_
# options.py) -- shown as the editor's "Verfügbare Werte" reference list so
# the player picks from real, catalog-verified stat names instead of typing
# them freehand.
_stat_priority_options_cache: dict[str, list[str]] | None = None
_STAT_PRIORITY_OPTIONS_PATH = Path(__file__).parent / "data" / "stat_priority_options.json"


def _load_stat_priority_options() -> dict[str, list[str]]:
    global _stat_priority_options_cache
    if _stat_priority_options_cache is not None:
        return _stat_priority_options_cache
    result: dict[str, list[str]] = {}
    if _STAT_PRIORITY_OPTIONS_PATH.exists():
        try:
            result = json.loads(_STAT_PRIORITY_OPTIONS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to load %s -- Verfügbare Werte list will be empty", _STAT_PRIORITY_OPTIONS_PATH)
    else:
        logger.warning("%s not found -- run compute_stat_priority_options.py", _STAT_PRIORITY_OPTIONS_PATH)
    _stat_priority_options_cache = result
    return result


# Known real-data wording that differs from the guide's own term -- matching
# is otherwise case-insensitive exact-name, which already covers e.g. the
# guide's "Defense Increase" vs. the catalog's "Defense increase".
_STAT_NAME_ALIASES = {"movement speed": "move speed"}


def _normalize_stat_name(name: str) -> str:
    key = (name or "").strip().lower()
    return _STAT_NAME_ALIASES.get(key, key)


def _pick_priority_substats(sub_stats: list[dict], count: int, priority_names: list[str]) -> set[int]:
    """Picks up to `count` indices into sub_stats, walking priority_names
    (the current Gear-Typ/Rolle/Kategorie profile's ordered stat-name list)
    top to bottom and taking the first still-unused match for each name --
    falls through the WHOLE list (not just the first few entries) so a
    slot whose top preferences aren't among its real options still gets its
    substat slots filled from lower-priority ones rather than being left
    empty (explicit user instruction: even the last-ranked entry should
    still be used if a slot has that many substat slots to fill)."""
    if count <= 0 or not sub_stats or not priority_names:
        return set()
    normalized = [_normalize_stat_name(s.get("name") or "") for s in sub_stats]
    chosen: list[int] = []
    used: set[int] = set()
    for wanted_name in priority_names:
        if len(chosen) >= count:
            break
        wanted = _normalize_stat_name(wanted_name)
        for i, name in enumerate(normalized):
            if i in used or name != wanted:
                continue
            chosen.append(i)
            used.add(i)
            break
    return set(chosen[:count])


def _build_quick_slot_group_rows(
    dialog: QDialog, layout: QVBoxLayout, group_checks: dict[str, QCheckBox], slot_checks: dict[str, QCheckBox],
    enabled_slots: set[str] | None = None,
):
    """Shared "group checkbox + Manuelle Auswahl accordion of per-slot
    checkboxes" builder, used by both QuickGearSelectDialog and
    QuickStatSelectDialog so the two independent Schnellauswahl dialogs
    (Equipment vs. Eigenschaften -- split into separate buttons/dialogs per
    user request, so adjusting one never requires re-doing the other's
    checkboxes) still share the exact same slot-group UI pattern.

    enabled_slots: when given (QuickStatSelectDialog only -- there's
    nothing to set substats on for an empty slot), any slot_id not in it is
    built disabled and unchecked; a group whose slots are ALL unequipped is
    disabled too. QuickGearSelectDialog leaves this None so every slot
    stays selectable regardless of what's currently equipped."""
    for key, label, slots in _QUICK_GEAR_CATEGORY_GROUPS:
        group_row = QHBoxLayout()
        group_row.setSpacing(6)
        check = QCheckBox(_t(label))
        group_has_equipped = enabled_slots is None or any(s in enabled_slots for s in slots)
        check.setChecked(group_has_equipped)
        check.setEnabled(group_has_equipped)
        group_row.addWidget(check)
        group_row.addStretch(1)
        manual_btn = QToolButton()
        manual_btn.setObjectName("SkillFilterButton")
        manual_btn.setText(_t("arm_manual_select_collapsed"))
        manual_btn.setCheckable(True)
        manual_btn.setCursor(Qt.PointingHandCursor)
        group_row.addWidget(manual_btn)
        layout.addLayout(group_row)
        group_checks[key] = check

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 0, 0, 4)
        panel_layout.setSpacing(2)
        panel.setVisible(False)
        slot_checks_here = {}
        for slot_id in slots:
            slot_check = QCheckBox(_t(_QUICK_GEAR_SLOT_LABELS.get(slot_id, slot_id)))
            slot_has_equipped = enabled_slots is None or slot_id in enabled_slots
            slot_check.setChecked(slot_has_equipped)
            slot_check.setEnabled(slot_has_equipped)
            if not slot_has_equipped:
                slot_check.setToolTip(_t("arm_slot_empty_hint"))
            panel_layout.addWidget(slot_check)
            slot_checks_here[slot_id] = slot_check
            slot_checks[slot_id] = slot_check
        layout.addWidget(panel)

        def _on_group_toggled(checked: bool, checks=slot_checks_here):
            for c in checks.values():
                if c.isEnabled():
                    c.setChecked(checked)

        def _on_manual_toggled(checked: bool, b=manual_btn, p=panel):
            b.setText(_t("arm_manual_select_expanded") if checked else _t("arm_manual_select_collapsed"))
            p.setVisible(checked)
            dialog.adjustSize()

        check.toggled.connect(_on_group_toggled)
        manual_btn.toggled.connect(_on_manual_toggled)


# Enchant-level defaults per grade, from the user's own guidance ("Blau 15,
# Gold 20, Orange 25" -- Legend/Unique/Epic in this app's own color naming,
# see GRADE_COLORS) -- suggested starting point when a Gear-Stufe is picked
# in QuickGearSelectDialog, always still overridable per slot.
_QUICK_GEAR_ENCHANT_DEFAULTS = {"Common": 0, "Rare": 5, "Legend": 15, "Unique": 20, "Epic": 25}


def _build_gear_slot_group_rows(
    dialog: "QuickGearSelectDialog", layout: QVBoxLayout, group_checks: dict[str, QCheckBox],
    slot_checks: dict[str, QCheckBox], slot_enchant_spins: dict[str, QSpinBox], default_enchant: int,
):
    """Same group-checkbox + "Manuelle Auswahl" accordion pattern as
    _build_quick_slot_group_rows, but each per-slot row in the expanded
    accordion also gets its own enchant-level spinbox (user request) --
    kept as its own function rather than extending the shared one since
    QuickStatSelectDialog's rows have nothing enchant-related to show."""
    for key, label, slots in _QUICK_GEAR_CATEGORY_GROUPS:
        group_row = QHBoxLayout()
        group_row.setSpacing(6)
        check = QCheckBox(_t(label))
        check.setChecked(True)
        group_row.addWidget(check)
        group_row.addStretch(1)
        manual_btn = QToolButton()
        manual_btn.setObjectName("SkillFilterButton")
        manual_btn.setText(_t("arm_manual_select_collapsed"))
        manual_btn.setCheckable(True)
        manual_btn.setCursor(Qt.PointingHandCursor)
        group_row.addWidget(manual_btn)
        layout.addLayout(group_row)
        group_checks[key] = check

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 0, 0, 4)
        panel_layout.setSpacing(2)
        panel.setVisible(False)
        slot_checks_here = {}
        for slot_id in slots:
            slot_row = QWidget()
            slot_row_layout = QHBoxLayout(slot_row)
            slot_row_layout.setContentsMargins(0, 0, 0, 0)
            slot_row_layout.setSpacing(8)

            slot_check = QCheckBox(_t(_QUICK_GEAR_SLOT_LABELS.get(slot_id, slot_id)))
            slot_check.setChecked(True)
            slot_row_layout.addWidget(slot_check, 1)

            enchant_spin = QSpinBox()
            enchant_spin.setRange(0, 30)
            enchant_spin.setPrefix("+")
            enchant_spin.setFixedWidth(64)
            enchant_spin.setValue(default_enchant)
            enchant_spin.setToolTip(_t("arm_default_enchant_slot_tooltip"))
            slot_row_layout.addWidget(enchant_spin)

            panel_layout.addWidget(slot_row)
            slot_checks_here[slot_id] = slot_check
            slot_checks[slot_id] = slot_check
            slot_enchant_spins[slot_id] = enchant_spin
        layout.addWidget(panel)

        def _on_group_toggled(checked: bool, checks=slot_checks_here):
            for c in checks.values():
                c.setChecked(checked)

        def _on_manual_toggled(checked: bool, b=manual_btn, p=panel):
            b.setText(_t("arm_manual_select_expanded") if checked else _t("arm_manual_select_collapsed"))
            p.setVisible(checked)
            dialog.adjustSize()

        check.toggled.connect(_on_group_toggled)
        manual_btn.toggled.connect(_on_manual_toggled)


class QuickGearSelectDialog(QDialog):
    """Build Planner's "Schnellauswahl: Equipment" button -- pick Rasse +
    Gear-Stufe (a real tier name, derived from the same crafting upgrade-
    chain data as the Crafting Simulator's Vergleich tab) + which slot
    groups to include, then auto-equips the one matching item per slot
    directly.

    No stat-based ranking per Rolle yet (explicitly deferred by the user to
    a separate later step -- see QuickStatSelectDialog, its own separate
    button/dialog) -- for a given race+tier, every slot has exactly one
    real item (verified: e.g. "True Dragon Lord" has exactly one
    Breastplate/Greaves/Boots/Helm/etc., no separate variant per armor
    weight class), so a direct name lookup is already unambiguous."""

    def __init__(self, items_by_id: dict, character_class: str, detail_cache: "ItemDetailCache",
                 active_gear_types: set[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("arm_quick_equip_title"))
        self.setMinimumWidth(420)
        self._items_by_id = items_by_id
        self._name_to_item = {it["name"]: it for it in items_by_id.values() if it.get("name")}
        self._character_class = character_class
        self._detail_cache = detail_cache
        # Which Quick-Select tags the global PvP/PvE/Neutral filter allows
        # (see _GEAR_TYPE_TO_QUICK_SELECT_TAGS) -- empty/None means no
        # restriction (show everything), matching the global filter's own
        # "empty active_gear_types = no filter" convention.
        self._allowed_quick_select_tags: set[str] | None = None
        if active_gear_types:
            allowed = set()
            for key in active_gear_types:
                allowed |= _GEAR_TYPE_TO_QUICK_SELECT_TAGS.get(key, set())
            self._allowed_quick_select_tags = allowed
        # Rarity filter narrowing the Gear-Stufe list below (User-Wunsch,
        # 2026-08-26: "Füge bitte Filter für die Rarität hinzu") -- set up
        # front so it already exists by the time _rebuild_tier_combo first
        # runs, whether via race_combo's signal or the explicit call below.
        self._selected_grade = "All"
        # Which Gear Type-Filter tag is active -- always a real one now
        # (Crafting/Expedition/Sanctuary/...), no separate "none" state.
        # "Crafting" is special-cased in _rebuild_tier_combo to ALSO include
        # the crafted Dragon Lord chain alongside its own dungeon sets (User-
        # Wunsch, 2026-08-26: "Bei Crafting zeigst du die crafting Gear
        # sets" -- crafted gear genuinely belongs under "Crafting").
        self._active_dungeon_tag: str = ""
        self._dungeon_sets_by_source = _build_dungeon_sets(items_by_id, detail_cache)

        recipes = _load_recipes()
        output_index = _build_recipe_output_index(recipes)
        self._transfer_source_index = _build_transfer_source_index(recipes, items_by_id, output_index)

        self.result_slots: dict[str, dict] = {}
        self.missing_slots: list[str] = []
        self.result_enchant: dict[str, int] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        # Rasse (narrow, fits its own text -- User-Wunsch: "den hier können
        # wir nun schmaler machen ... dann erhalten wir rechts Platz") next
        # to Dungeon-Quelle in the freed-up space. Dungeon-Set itself moved
        # out of this cramped row entirely (User-Wunsch, 2026-08-26: "nimm
        # oben rechts den Dropdown und mach ihn in die Mitte") -- it's now
        # its own full-width row below the Rarität filter, same visual
        # weight as Gear-Stufe instead of squeezed into a third column.
        top_label_row = QHBoxLayout()
        race_label = QLabel(_t("arm_race_label"))
        race_label.setObjectName("EquipSectionLabel")
        top_label_row.addWidget(race_label)
        dungeon_source_label = QLabel(_t("arm_gear_type_filter_label"))
        dungeon_source_label.setObjectName("EquipSectionLabel")
        top_label_row.addWidget(dungeon_source_label, 1)
        outer.addLayout(top_label_row)

        top_row = QHBoxLayout()
        self.race_combo = QComboBox()
        self.race_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.race_combo.addItems(AION2_RACES)
        self.race_combo.currentTextChanged.connect(self._rebuild_tier_combo)
        top_row.addWidget(self.race_combo)

        self.dungeon_source_combo = QComboBox()
        # No separate "no filter"/"crafted" placeholder anymore (User-Wunsch,
        # 2026-08-26: "das ist scheisse so ... Bei Crafting zeigst du die
        # crafting Gear sets") -- the crafted Dragon Lord chain genuinely IS
        # part of "Crafting" in the game's own sense, so it's merged INTO
        # that option's list (see _rebuild_tier_combo) instead of living
        # under a separate, confusing placeholder label next to it.
        # "Crafting" is always offered even though data/dungeon_sets.json no
        # longer has an entry for it (User-Wunsch, 2026-08-26: its 3 former
        # sets are "Transfer Crafting", excluded there since that reaches
        # almost anything) -- it now purely means "show the crafted Dragon
        # Lord chain", handled entirely in _rebuild_tier_combo, independent
        # of whether the tag has any of its own dungeon-set entries.
        gear_type_options = set(self._dungeon_sets_by_source.keys()) | {"Crafting"}
        # Narrowed by the global PvP/PvE/Neutral filter, if any is active
        # (User-Wunsch, 2026-08-26: "wenn PvE ausgewählt - bitte 'Crafting'
        # Filter anzeigen ... wenn Neutral ausgewählt - bitte Dungeon Gear
        # anzeigen" etc.) -- e.g. with the PvE+Neutral default, PvP-only
        # "Abyss Gear" (once it exists) stays hidden until PvP is toggled on.
        if self._allowed_quick_select_tags is not None:
            gear_type_options &= self._allowed_quick_select_tags
        self.dungeon_source_combo.addItems(sorted(gear_type_options))
        self.dungeon_source_combo.currentTextChanged.connect(self._on_dungeon_source_changed)
        top_row.addWidget(self.dungeon_source_combo, 1)
        outer.addLayout(top_row)

        # Rarity filter — same exclusive-pill-button pattern already used
        # for ItemDatabaseWindow's own Grade row (All + one pill per
        # RARITY_ORDER grade, colored via GRADE_COLORS). Narrows the
        # Gear-Stufe list below to tiers matching the selected grade (each
        # crafted tier has exactly one grade shared across all its slots).
        grade_filter_row = QHBoxLayout()
        grade_filter_label = QLabel(_t("arm_rarity_label"))
        grade_filter_label.setObjectName("EquipSectionLabel")
        grade_filter_row.addWidget(grade_filter_label)
        self._tier_grade_buttons: dict[str, QPushButton] = {}
        tier_grade_group = QButtonGroup(self)
        tier_grade_group.setExclusive(True)

        all_grades_btn = QPushButton(_t("arm_all"))
        all_grades_btn.setObjectName("SkillFilterButton")
        all_grades_btn.setCheckable(True)
        all_grades_btn.setChecked(True)
        all_grades_btn.clicked.connect(lambda checked=False: self._on_tier_grade_filter_changed("All"))
        tier_grade_group.addButton(all_grades_btn)
        grade_filter_row.addWidget(all_grades_btn)
        self._tier_grade_buttons["All"] = all_grades_btn

        for grade in RARITY_ORDER:
            btn = QPushButton(grade)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setStyleSheet(f"color: {GRADE_COLORS[grade]};")
            btn.clicked.connect(lambda checked=False, g=grade: self._on_tier_grade_filter_changed(g))
            tier_grade_group.addButton(btn)
            grade_filter_row.addWidget(btn)
            self._tier_grade_buttons[grade] = btn

        grade_filter_row.addStretch(1)
        self._tier_grade_buttongroup = tier_grade_group  # kept alive against GC
        outer.addLayout(grade_filter_row)

        # Item-Set -- ONE combo that shows either the crafted Gear-Stufe
        # chain (Dungeon-Quelle = "Gecraftet (Dragon Lord)") or the current
        # Dungeon-Quelle's sets, not two separate rows (User-Wunsch,
        # 2026-08-26, after the two-row version caused real confusion:
        # "Die Liste die ich oft gezeigt habe mit splendent True Dragon,
        # die machst du als Item Set Liste ... Die Dungeon Sets ... machst
        # du bei Auswahl Dungeon unten statt splendent"). Dungeon-Set entries
        # are formatted "Name (Gearscore)"; the plain prefix used for actual
        # gear resolution is always in itemData, for both kinds of entry --
        # _on_apply only ever reads currentData(), never the display text.
        tier_label = QLabel(_t("arm_item_set_label"))
        tier_label.setObjectName("EquipSectionLabel")
        outer.addWidget(tier_label)
        self.tier_combo = _DownwardComboBox()
        # Distinct objectName so styles.qss can scope out the global
        # "QComboBox QAbstractItemView { color: ... }" rule just for this
        # dropdown -- that rule forces one uniform text color on every
        # combo's popup, which silently overrode the per-item Qt.
        # ForegroundRole grade colors set in _rebuild_tier_combo (User-
        # Wunsch: "Bitte in der Liste einmal die Raritäten für die
        # Schriftfarbe verwenden" -- confirmed via screenshot the colors
        # weren't actually showing before this fix).
        self.tier_combo.setObjectName("ItemSetCombo")
        # Instance-level stylesheet directly on the popup view, not a QSS
        # selector rule -- the app-wide "QComboBox QAbstractItemView {
        # color: ... }" rule forces one uniform text color on every combo's
        # popup, and an #ItemSetCombo-scoped QSS override for just this
        # dropdown did NOT take effect in the full app despite working in
        # isolation (confirmed via screenshot comparison), likely a
        # selector-matching quirk of Qt's special-cased combo-popup style
        # propagation. Setting it directly on the view instance sidesteps
        # that entirely and reliably lets each item's own Qt.ForegroundRole
        # grade color show through (User-Wunsch: "die Raritäten für die
        # Schriftfarbe verwenden").
        self.tier_combo.view().setStyleSheet(
            "background-color: #0f172a;"
            "border: 1px solid rgba(100, 116, 139, 0.45);"
            "selection-background-color: rgba(34, 211, 238, 0.25);"
            "padding: 4px;"
        )
        self.tier_combo.setItemDelegate(_RoleColorDelegate(self.tier_combo))
        self.tier_combo.currentIndexChanged.connect(self._on_tier_selected)
        outer.addWidget(self.tier_combo)

        # Same slider design as the Equipment Item panel's own "Verzauberung
        # simulieren" control (User-Wunsch: "können wir das similar zum
        # Enchantbalken abbilden? gleiches Design") -- caption row with a
        # live "+N" value on the right, ticked slider centered below it,
        # instead of a plain QSpinBox.
        enchant_caption_row = QHBoxLayout()
        enchant_label = QLabel(_t("arm_default_enchant_label"))
        enchant_label.setObjectName("EquipSectionLabel")
        self.default_enchant_value = QLabel("+0")
        self.default_enchant_value.setObjectName("DetailEnchantValue")
        enchant_caption_row.addWidget(enchant_label)
        enchant_caption_row.addStretch()
        enchant_caption_row.addWidget(self.default_enchant_value)
        outer.addLayout(enchant_caption_row)

        self.default_enchant_slider = _TickedSlider(Qt.Horizontal)
        self.default_enchant_slider.setMinimum(0)
        self.default_enchant_slider.setMaximum(30)
        self.default_enchant_slider.setTickPosition(QSlider.TicksBelow)
        self.default_enchant_slider.setTickInterval(1)
        self.default_enchant_slider.valueChanged.connect(self._on_default_enchant_changed)
        enchant_slider_row = QHBoxLayout()
        enchant_slider_row.addStretch(1)
        enchant_slider_row.addWidget(self.default_enchant_slider, 6)
        enchant_slider_row.addStretch(1)
        outer.addLayout(enchant_slider_row)

        groups_label = QLabel(_t("arm_included_slots"))
        groups_label.setObjectName("EquipSectionLabel")
        outer.addWidget(groups_label)
        # Per-slot checkboxes are the actual source of truth for _on_apply
        # -- the group checkbox is just a convenience bulk on/off for all of
        # them, and "Manuelle Auswahl" is an accordion that reveals the same
        # checkboxes (+ a per-slot enchant spinbox) for fine-tuning
        # individual pieces within a group.
        self._group_checks: dict[str, QCheckBox] = {}
        self._slot_checks: dict[str, QCheckBox] = {}
        self._slot_enchant_spins: dict[str, QSpinBox] = {}
        _build_gear_slot_group_rows(
            self, outer, self._group_checks, self._slot_checks, self._slot_enchant_spins,
            self.default_enchant_slider.value(),
        )

        outer.addStretch(1)

        self.status_label = QLabel()
        self.status_label.setObjectName("DetailDisclaimer")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        apply_btn = QPushButton(_t("arm_equip_btn"))
        apply_btn.clicked.connect(self._on_apply)
        outer.addWidget(apply_btn)

        # dungeon_source_combo's own currentTextChanged never fired during
        # construction (connected only after addItems), so
        # self._active_dungeon_tag is still its unset "" default here --
        # sync it explicitly to whatever the combo actually defaulted to
        # (its first, alphabetically-sorted item) before the first build.
        self._active_dungeon_tag = self.dungeon_source_combo.currentText()
        self._rebuild_tier_combo(self.race_combo.currentText())
        # A fixed resize() guessed too small a height for the real content,
        # which made Windows fight the layout's actual minimum size at
        # startup -- let the layout size the window itself instead, and
        # re-run this whenever a "Manuelle Auswahl" panel opens/closes so
        # the window grows/shrinks with the content rather than clipping it.
        self.adjustSize()

    def _tier_grade(self, tier_prefix: str) -> str | None:
        """"Ring" as a stand-in item to read a tier's real grade off of --
        every slot at a given tier shares the same grade (verified earlier
        for the Vergleich tab's grade-consistency check)."""
        item = self._name_to_item.get(f"{tier_prefix} Ring") if tier_prefix else None
        return item.get("grade") if item else None

    def _on_tier_grade_filter_changed(self, grade: str):
        logger.info("Schnellauswahl: Rarität-Filter -> %r", grade)
        self._selected_grade = grade
        self._rebuild_tier_combo(self.race_combo.currentText())

    def _on_dungeon_source_changed(self, tag: str):
        logger.info("Schnellauswahl: Gear Type-Filter -> %r (Rarität=%r)", tag, self._selected_grade)
        self._active_dungeon_tag = tag
        self._rebuild_tier_combo(self.race_combo.currentText())

    def _rebuild_tier_combo(self, race: str):
        """Populates the single Item-Set combo for whichever Gear
        Type-Filter tag is active (User-Wunsch, 2026-08-26, after the
        two-combo version caused real confusion: "Die Liste die ich oft
        gezeigt habe mit splendent True Dragon, die machst du als Item Set
        Liste ... Die Dungeon Sets ... machst du bei Auswahl Dungeon unten
        statt splendent"). "Crafting" specifically ALSO includes the
        crafted Dragon Lord chain alongside its own 3 dungeon sets (User-
        Wunsch: "Bei Crafting zeigst du die crafting Gear sets" -- the
        crafted chain genuinely IS "Crafting" in the game's own sense, not
        a separate category). Every item's itemData is (prefix, grade) --
        _on_apply/_ on_tier_selected read only that, never the (possibly
        "Name (Gearscore)"-formatted) display text."""
        self.tier_combo.blockSignals(True)
        self.tier_combo.clear()

        if self._active_dungeon_tag == "Crafting":
            root_prefix = RACE_TIER_ROOT.get(race)
            if root_prefix:
                # "Ring" as the reference slot to derive the shared
                # tier-prefix ladder from -- verified against the real
                # dataset that Ring/Boots/Necklace/Dagger/Greatsword all
                # reach the identical prefix set for a given race (Helm's
                # own recipe chain doesn't resolve as cleanly, but the
                # actual Helm items still exist under the same tier names,
                # so borrowing Ring's chain and looking Helm up by name
                # directly still works -- see project_todo.md).
                chain = _ordered_tier_chain(f"{root_prefix} Ring", "Ring", self._transfer_source_index)
                for tier in chain:
                    grade = self._tier_grade(tier)
                    if self._selected_grade == "All" or grade == self._selected_grade:
                        self.tier_combo.addItem(tier, (tier, grade))
                        if grade in GRADE_COLORS:
                            self.tier_combo.setItemData(
                                self.tier_combo.count() - 1, QColor(GRADE_COLORS[grade]), Qt.ForegroundRole
                            )
            # Default to the highest crafted tier if any made it through the
            # Rarität filter -- "give me the current best set" -- before the
            # dungeon-set entries below get appended after it.
            crafted_count = self.tier_combo.count()
            if crafted_count:
                self.tier_combo.setCurrentIndex(crafted_count - 1)

        # Sorted by Gearscore descending -- highest at the top (User-Wunsch,
        # 2026-08-26: "Dieses Dropdown bitte nach Gearscore sortieren" /
        # "Höchste nach oben"), not alphabetical. Also means the same-as-
        # crafted-chain "give me the best" default (index 0) now lands on
        # the highest-Gearscore set automatically.
        info_by_root = self._dungeon_sets_by_source.get(self._active_dungeon_tag, {})
        if self._active_dungeon_tag == "Abyss Gear":
            race_prefix = _ABYSS_GEAR_RACE_PREFIX.get(race)
            info_by_root = {
                root: info for root, info in info_by_root.items()
                if race_prefix and root.startswith(race_prefix + " ")
            }
        roots = sorted(
            (root for root, info in info_by_root.items()
             if self._selected_grade == "All" or info["grade"] == self._selected_grade),
            key=lambda root: info_by_root[root]["gearscore"],
            reverse=True,
        )
        for root in roots:
            info = info_by_root[root]
            self.tier_combo.addItem(f"{root} ({info['gearscore']})", (root, info["grade"]))
            if info["grade"] in GRADE_COLORS:
                self.tier_combo.setItemData(
                    self.tier_combo.count() - 1, QColor(GRADE_COLORS[info["grade"]]), Qt.ForegroundRole
                )

        if self.tier_combo.count() and self.tier_combo.currentIndex() < 0:
            self.tier_combo.setCurrentIndex(0)
        self.tier_combo.setEnabled(self.tier_combo.count() > 0)

        self.tier_combo.blockSignals(False)
        current_data = self.tier_combo.currentData()
        current_prefix = current_data[0] if current_data else None
        all_entries = [self.tier_combo.itemText(i) for i in range(self.tier_combo.count())]
        logger.info("Schnellauswahl: Item-Set neu aufgebaut (Filter=%r, Rasse=%r, Rarität=%r) -> %r (ausgewaehlt: %r)",
                    self._active_dungeon_tag, race, self._selected_grade, all_entries, current_prefix)
        # status_label doesn't exist yet the first time this runs (built
        # further down in __init__) -- only hasattr-guarded uses are safe.
        if hasattr(self, "status_label"):
            if not all_entries:
                self.status_label.setText(
                    _t("arm_no_entries_for_filter", filter=self._active_dungeon_tag, grade=self._selected_grade)
                )
            else:
                self.status_label.setText("")
        self._on_tier_selected(self.tier_combo.currentIndex())

    def _on_tier_selected(self, index: int):
        data = self.tier_combo.itemData(index) if index >= 0 else None
        if not data:
            return
        prefix, grade = data
        # Real max-enchant range comes from the selected set's own item data
        # (User-Wunsch, 2026-08-26: "Halte dich bitte an das bisherige
        # Enhance-System im Buildplanner") -- same maxEnchantLevel +
        # maxExceedEnchantLevel the actual Equipment Item panel's slider
        # uses per-item, instead of a fixed 0-30 range that let you drag
        # past what's actually achievable for that rarity/item.
        max_enchant = 0
        for slot_id in _ENCHANT_REFERENCE_SLOTS:
            ref_item = self._resolve_slot_item(slot_id, prefix)
            if not ref_item or not ref_item.get("id"):
                continue
            self._detail_cache.request(ref_item["id"])
            detail = self._detail_cache.get(ref_item["id"])
            if detail:
                max_enchant = int(detail.get("maxEnchantLevel") or 0) + int(detail.get("maxExceedEnchantLevel") or 0)
                break
        self.default_enchant_slider.setMaximum(max(max_enchant, 0))
        default_value = min(_QUICK_GEAR_ENCHANT_DEFAULTS.get(grade, 0), max_enchant)
        self.default_enchant_slider.setValue(default_value)

    def _on_default_enchant_changed(self, value: int):
        self.default_enchant_value.setText(f"+{value}")
        for spin in self._slot_enchant_spins.values():
            spin.setValue(value)

    def _resolve_slot_item(self, slot_id: str, tier_prefix: str) -> dict | None:
        if slot_id == "MainHand":
            type_word = CLASS_WEAPON_CATEGORY.get(self._character_class)
        else:
            type_word = _QUICK_GEAR_SLOT_WORDS.get(slot_id)
        if not type_word:
            return None
        override_names = _CRAFTING_WEAPON_NAMES.get(tier_prefix)
        if override_names is not None:
            # These 2 Crafting sets are weapon/Guard-only by design -- for
            # any other slot, DON'T fall through to the generic name lookup:
            # "Lava Heart" collides with a completely different, unrelated
            # level-128 armor set of the same name (from Expedition), whose
            # "Lava Heart Helm" etc. would otherwise get silently equipped
            # alongside this level-45 weapon (real bug, found while
            # verifying this fix -- confirmed via the raw catalog that
            # "Corroded Sovereign's" has no such collision, but "Lava Heart"
            # does).
            item_name = override_names.get(type_word)
            return self._name_to_item.get(item_name) if item_name else None
        return self._name_to_item.get(f"{tier_prefix} {type_word}")

    def _on_apply(self):
        # currentData() is (prefix, grade); only the prefix is needed here
        # -- _resolve_slot_item works unchanged whether it's a crafted tier
        # name or a dungeon set's root name (both resolve via the exact same
        # "{prefix} {type_word}" name lookup).
        current_data = self.tier_combo.currentData()
        tier_prefix = current_data[0] if current_data else None
        if not tier_prefix:
            self.status_label.setText(_t("arm_choose_item_set_first"))
            return

        included_slots = [slot_id for slot_id, check in self._slot_checks.items() if check.isChecked()]

        self.result_slots = {}
        self.missing_slots = []
        self.result_enchant = {}
        for slot_id in included_slots:
            item = self._resolve_slot_item(slot_id, tier_prefix)
            if item:
                self.result_slots[slot_id] = item
                self.result_enchant[slot_id] = self._slot_enchant_spins[slot_id].value()
            else:
                self.missing_slots.append(slot_id)

        if not self.result_slots:
            self.status_label.setText(_t("arm_no_matching_items"))
            return

        # Report any misses after closing (via the caller) rather than here
        # -- accept() below closes the dialog immediately, so a message set
        # on this label would never actually be seen.
        self.accept()


class QuickStatSelectDialog(QDialog):
    """Build Planner's "Schnellauswahl: Eigenschaften" button -- separate
    from QuickGearSelectDialog on purpose (user request: adjusting only
    Eigenschaften after already closing the Equipment popup shouldn't
    require re-checking the gear slot boxes again). Picks a Gear-Typ (PvE/
    PvP) + Rolle (Angreifer/Verteidiger/Support) -- selecting which of the 6
    priority profiles edited via the gear-icon StatPriorityEditorDialog to
    apply -- and which slot groups should have their substats auto-picked,
    then locks the priority-ranked substats on whatever is CURRENTLY
    equipped in each included slot."""

    def __init__(self, equipped_slot_ids: set[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("arm_quick_stats_title"))
        self.setMinimumWidth(420)
        self._equipped_slot_ids = equipped_slot_ids

        self.stat_target_slots: set[str] = set()
        self.selected_gear_type = "PvE"
        self.selected_role = "Angreifer"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        gear_type_label = QLabel(_t("arm_gear_mode_label"))
        gear_type_label.setObjectName("EquipSectionLabel")
        outer.addWidget(gear_type_label)
        gear_type_row = QHBoxLayout()
        gear_type_row.setSpacing(6)
        gear_type_group = QButtonGroup(self)
        gear_type_group.setExclusive(True)
        for gear_type in _STAT_PRIORITY_GEAR_TYPES:
            btn = QPushButton(gear_type)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(gear_type == self.selected_gear_type)
            btn.clicked.connect(lambda checked=False, g=gear_type: setattr(self, "selected_gear_type", g))
            gear_type_group.addButton(btn)
            gear_type_row.addWidget(btn)
        gear_type_row.addStretch(1)
        outer.addLayout(gear_type_row)

        role_label = QLabel(_t("arm_role_label"))
        role_label.setObjectName("EquipSectionLabel")
        outer.addWidget(role_label)
        role_row = QHBoxLayout()
        role_row.setSpacing(6)
        role_group = QButtonGroup(self)
        role_group.setExclusive(True)
        for role in _STAT_PRIORITY_ROLES:
            btn = QPushButton(_t(_ROLE_LABEL_KEYS[role]))
            btn.setObjectName(_ROLE_BUTTON_OBJECT_NAMES[role])
            btn.setCheckable(True)
            btn.setChecked(role == self.selected_role)
            btn.clicked.connect(lambda checked=False, r=role: setattr(self, "selected_role", r))
            role_group.addButton(btn)
            role_row.addWidget(btn)
        role_row.addStretch(1)
        outer.addLayout(role_row)

        groups_label = QLabel(_t("arm_auto_set_substats_for"))
        groups_label.setObjectName("EquipSectionLabel")
        outer.addWidget(groups_label)
        self._group_checks: dict[str, QCheckBox] = {}
        self._slot_checks: dict[str, QCheckBox] = {}
        _build_quick_slot_group_rows(self, outer, self._group_checks, self._slot_checks, enabled_slots=equipped_slot_ids)

        outer.addStretch(1)

        apply_btn = QPushButton(_t("arm_apply_btn"))
        apply_btn.clicked.connect(self._on_apply)
        outer.addWidget(apply_btn)

        self.adjustSize()

    def _on_apply(self):
        self.stat_target_slots = {slot_id for slot_id, check in self._slot_checks.items() if check.isChecked()}
        self.accept()


class StatPriorityEditorDialog(QDialog):
    """Gear-icon editor next to "Eigenschaften" (User-Wunsch 2026-08-27:
    "Ein Zahnrad ... darüber soll man die Rollen und die Werte manuell
    anpassen können"). Edits the 6 (Gear-Typ x Rolle) priority profiles
    _pick_priority_substats draws on -- one ranked list of up to
    _STAT_PRIORITY_MAX_ENTRIES stat names per category tab (Waffe/Guard,
    Rüstung, Schmuck, Bracelets), each rank a searchable combo box over the
    real per-category stat names (compute_stat_priority_options.py) so the
    player never has to type a name freehand. A name picked in one rank is
    excluded from every other rank's dropdown in the same category (User-
    Wunsch: "jedes Dropdown schließt den ausgewählten Stat aus der gesamt
    verfügbaren Liste aus")."""

    def __init__(self, profiles: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("arm_stat_priority_editor_title"))
        self.setMinimumSize(560, 520)
        self._data = copy.deepcopy(profiles)
        self._available_options = _load_stat_priority_options()
        self._gear_type = _STAT_PRIORITY_GEAR_TYPES[0]
        self._role = _STAT_PRIORITY_ROLES[0]
        self.result_profiles: dict | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        gear_type_label = QLabel(_t("arm_gear_mode_label"))
        gear_type_label.setObjectName("EquipSectionLabel")
        outer.addWidget(gear_type_label)
        gear_type_row = QHBoxLayout()
        gear_type_row.setSpacing(6)
        gear_type_group = QButtonGroup(self)
        gear_type_group.setExclusive(True)
        for gear_type in _STAT_PRIORITY_GEAR_TYPES:
            btn = QPushButton(gear_type)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(gear_type == self._gear_type)
            btn.clicked.connect(lambda checked=False, g=gear_type: self._on_profile_changed(gear_type=g))
            gear_type_group.addButton(btn)
            gear_type_row.addWidget(btn)
        gear_type_row.addStretch(1)
        outer.addLayout(gear_type_row)

        role_label = QLabel(_t("arm_role_label"))
        role_label.setObjectName("EquipSectionLabel")
        outer.addWidget(role_label)
        role_row = QHBoxLayout()
        role_row.setSpacing(6)
        role_group = QButtonGroup(self)
        role_group.setExclusive(True)
        for role in _STAT_PRIORITY_ROLES:
            btn = QPushButton(_t(_ROLE_LABEL_KEYS[role]))
            btn.setObjectName(_ROLE_BUTTON_OBJECT_NAMES[role])
            btn.setCheckable(True)
            btn.setChecked(role == self._role)
            btn.clicked.connect(lambda checked=False, r=role: self._on_profile_changed(role=r))
            role_group.addButton(btn)
            role_row.addWidget(btn)
        role_row.addStretch(1)
        outer.addLayout(role_row)

        self._tabs = QTabWidget()
        self._category_combos: dict[str, list[QComboBox]] = {}
        for key, label, _slots in _STAT_PRIORITY_CATEGORIES:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(8, 10, 8, 8)
            tab_layout.setSpacing(6)
            combos: list[QComboBox] = []
            for i in range(_STAT_PRIORITY_MAX_ENTRIES):
                row = QHBoxLayout()
                row.setSpacing(8)
                pos_label = QLabel(f"{i + 1}.")
                pos_label.setFixedWidth(20)
                row.addWidget(pos_label)
                combo = _build_stat_priority_combo()
                combo.activated.connect(lambda _idx=0, k=key: self._rebuild_category_combos(k))
                row.addWidget(combo, 1)
                tab_layout.addLayout(row)
                combos.append(combo)
            tab_layout.addStretch(1)
            self._category_combos[key] = combos
            self._tabs.addTab(tab, _t(label))
        outer.addWidget(self._tabs, 1)

        self._load_profile_into_combos()

        button_row = QHBoxLayout()
        reset_btn = QPushButton(_t("arm_reset_to_default"))
        reset_btn.clicked.connect(self._on_reset_current_profile)
        button_row.addWidget(reset_btn)
        button_row.addStretch(1)
        cancel_btn = QPushButton(_t("arm_cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        save_btn = QPushButton(_t("arm_save"))
        save_btn.clicked.connect(self._on_save)
        button_row.addWidget(save_btn)
        outer.addLayout(button_row)

    def _current_selections(self, key: str) -> list[str]:
        return [name for combo in self._category_combos[key] if (name := combo.currentData())]

    def _flush_combos_into_data(self):
        for key in self._category_combos:
            self._data[self._gear_type][self._role][key] = self._current_selections(key)

    def _load_profile_into_combos(self):
        profile = self._data[self._gear_type][self._role]
        for key in self._category_combos:
            self._rebuild_category_combos(key, forced_selections=profile.get(key, []))

    def _rebuild_category_combos(self, key: str, forced_selections: list[str] | None = None):
        """Repopulates every rank's combo for one category so a name picked
        in one rank disappears from the others -- called on every user pick
        (forced_selections=None, reads the combos' own current state) and
        when switching Gear-Typ/Rolle (forced_selections= the stored
        profile, since the combos still show the PREVIOUS profile's picks
        at that point)."""
        combos = self._category_combos[key]
        if forced_selections is not None:
            selections = list(forced_selections) + [""] * len(combos)
            selections = selections[:len(combos)]
        else:
            selections = [combo.currentData() or "" for combo in combos]
        options = self._available_options.get(key, [])
        for i, combo in enumerate(combos):
            others = {selections[j] for j in range(len(combos)) if j != i and selections[j]}
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(_t("arm_empty_option"), "")
            for name in options:
                if name not in others:
                    combo.addItem(name, name)
            current = selections[i]
            idx = combo.findData(current) if current else 0
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def _on_profile_changed(self, gear_type: str | None = None, role: str | None = None):
        self._flush_combos_into_data()
        if gear_type:
            self._gear_type = gear_type
        if role:
            self._role = role
        self._load_profile_into_combos()

    def _on_reset_current_profile(self):
        reply = QMessageBox.question(
            self, _t("arm_reset_confirm_title"),
            _t("arm_reset_confirm_text", gear_type=self._gear_type, role=_t(_ROLE_LABEL_KEYS[self._role])),
        )
        if reply != QMessageBox.Yes:
            return
        self._data[self._gear_type][self._role] = {
            cat: list(names) for cat, names in _DEFAULT_STAT_PRIORITY_BY_CATEGORY.items()
        }
        self._load_profile_into_combos()

    def _on_save(self):
        self._flush_combos_into_data()
        self.result_profiles = self._data
        self.accept()


def _build_stat_priority_combo() -> QComboBox:
    """One rank's searchable dropdown -- [Position][Suchfeld mit Dropdown]
    [Pfeilindikator] per User-Wunsch, the arrow being the combo's own native
    one. Editable + a contains/case-insensitive QCompleter turns typing into
    a live filter; NoInsert keeps a non-matching typed string from ever
    becoming a fake selection."""
    combo = QComboBox()
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.NoInsert)
    combo.lineEdit().setPlaceholderText(_t("arm_search_placeholder"))
    completer = combo.completer()
    completer.setCompletionMode(QCompleter.PopupCompletion)
    completer.setFilterMode(Qt.MatchContains)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    return combo


class LoadoutWindow(QMainWindow):
    """Virtual (local-only) equipment loadout — not tied to any real
    character. Lets you try any catalog item per slot and preview its
    (estimated) enchant scaling in the shared detail panel."""

    def __init__(self, items: list[dict], icon_cache: "IconCache", detail_cache: "ItemDetailCache",
                 parent=None, character_class: str | None = None,
                 character_name: str = "", character_race: str | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle(_t("arm_equip_character_title"))
        self.resize(1300, 780)
        self._items = items
        self._items_by_id = {it["id"]: it for it in items}
        self.icon_cache = icon_cache
        self.detail_cache = detail_cache
        self._equipped: dict[str, dict] = {}
        self._equipped_substats: dict[str, set[int]] = {}
        self._equipped_enchant: dict[str, int] = {}
        self._equip_builds_data: dict[str, dict[str, dict]] = {}
        self._current_equip_build_name = "Default"
        self._slot_icon_buttons: dict[str, QToolButton] = {}
        self._slot_enchant_labels: dict[str, QLabel] = {}
        self._selected_equip_slot_id: str | None = None
        self._theme = "abyss"
        self._stat_priority_profiles = _default_stat_priority_profiles()

        central = QWidget()
        central.setObjectName("LoadoutBackground")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 20, 20, 20)

        # Class selector lives above the tab bar (not inside the Skill
        # Planner tab) so it's visible from Equipment and Arcana & Titel too
        # — the class affects weapon-category filtering and skill data on
        # every tab, not just the planner.
        class_row = QHBoxLayout()
        class_label = QLabel(_t("arm_class_label"))
        class_label.setObjectName("EquipSectionLabel")
        class_row.addWidget(class_label)
        class_row.addStretch(1)

        # Global PvP/PvE/Neutral gear-type filter — lives here (not inside
        # the item picker popup, which is recreated fresh per slot click) so
        # it persists across slots while equipping. Deliberately separate
        # from the Stat Info tab's own PvE/PvP mode toggle — that one stays
        # as-is, this one only affects which items the picker offers.
        # Default PvE+Neutral (User-Wunsch, 2026-08-25: "Standard wird
        # vorgegeben: PvE + Neutral. Benutzer kann die Auswahl wie gehabt
        # jederzeit ändern.") -- restored from the profile in
        # apply_persisted_state() if a saved choice exists there, this is
        # only the fallback for a profile that's never set it before.
        self._active_gear_types: set[str] = {"PvE", "Neutral"}
        self._gear_type_buttons: dict[str, QPushButton] = {}
        for key in ("PvP", "PvE", "Neutral"):
            btn = QPushButton(key)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setMinimumSize(64, 28)
            btn.setChecked(key in self._active_gear_types)
            btn.clicked.connect(lambda checked, k=key: self._on_gear_type_toggled(k, checked))
            class_row.addWidget(btn)
            self._gear_type_buttons[key] = btn

        class_row.addSpacing(12)
        self.skill_planner_class_combo = QComboBox()
        self.skill_planner_class_combo.setIconSize(QSize(22, 22))
        class_row.addWidget(self.skill_planner_class_combo)
        outer.addLayout(class_row)

        self.main_tabs = QTabWidget()
        self.main_tabs.setObjectName("timerModeTabWidget")
        outer.addWidget(self.main_tabs)

        equipment_tab = QWidget()
        equipment_outer = QVBoxLayout(equipment_tab)
        equipment_outer.setContentsMargins(0, 0, 0, 0)
        equipment_outer.setSpacing(6)

        self.equip_build_tabs_row = QHBoxLayout()
        self.equip_build_tabs_row.setContentsMargins(0, 0, 0, 0)
        self.equip_build_tabs_row.setSpacing(6)
        self.equip_build_tabs_row.setAlignment(Qt.AlignLeft)

        equip_header_row = QHBoxLayout()
        equip_header_row.setContentsMargins(16, 12, 16, 0)
        equip_header_row.setSpacing(6)
        equip_header_row.addLayout(self.equip_build_tabs_row)
        equip_header_row.addStretch(1)
        quick_label = QLabel(_t("arm_quick_select_label"))
        quick_label.setObjectName("EquipSectionLabel")
        equip_header_row.addWidget(quick_label)
        # Two separate buttons/dialogs (not one dialog with an internal
        # toggle) -- User-Wunsch: adjusting only Eigenschaften after
        # already closing the Equipment popup shouldn't require re-checking
        # the gear slot boxes again.
        self.quick_gear_btn = QPushButton(_t("arm_equipment_btn"))
        self.quick_gear_btn.clicked.connect(self._open_quick_gear_select)
        equip_header_row.addWidget(self.quick_gear_btn)
        self.quick_stat_btn = QPushButton(_t("arm_properties_btn"))
        self.quick_stat_btn.clicked.connect(self._open_quick_stat_select)
        equip_header_row.addWidget(self.quick_stat_btn)
        self.stat_priority_edit_btn = QToolButton()
        self.stat_priority_edit_btn.setIcon(_make_gear_icon())
        self.stat_priority_edit_btn.setIconSize(QSize(20, 20))
        self.stat_priority_edit_btn.setFixedSize(32, 32)
        self.stat_priority_edit_btn.setToolTip(_t("arm_stat_priority_editor_title"))
        self.stat_priority_edit_btn.clicked.connect(self._open_stat_priority_editor)
        equip_header_row.addWidget(self.stat_priority_edit_btn)
        equipment_outer.addLayout(equip_header_row)

        equip_root = QHBoxLayout()
        equip_root.setContentsMargins(16, 16, 16, 16)
        equip_root.setSpacing(20)
        equip_root.addLayout(self._build_weapon_armor_column(), 0)
        equip_root.addWidget(self._build_equip_center_stack(), 1)
        equip_root.addLayout(self._build_accessory_column(), 0)
        equipment_outer.addLayout(equip_root, 1)
        self.main_tabs.addTab(equipment_tab, _t("arm_equipment_btn"))

        self.main_tabs.addTab(self._build_equip_priority_tab(), _t("arm_eq_priority_tab"))

        arcana_tab = QWidget()
        arcana_root = QHBoxLayout(arcana_tab)
        arcana_root.setContentsMargins(16, 16, 16, 16)
        arcana_root.setSpacing(30)
        arcana_root.addLayout(self._build_arcana_column())
        arcana_root.addStretch()
        self.main_tabs.addTab(arcana_tab, _t("arm_arcana_tab"))

        self.main_tabs.addTab(self._build_skill_planner_tab(), _t("arm_skill_planner_tab"))

        icon_cache.icon_ready.connect(self._on_icon_ready)
        detail_cache.detail_ready.connect(self._on_detail_ready)

        self.character_class_combo.setIconSize(QSize(24, 24))
        self._class_combos = (self.character_class_combo, self.skill_planner_class_combo)
        for class_name in AION2_ACTIVE_CLASSES:
            icon = _class_icon(class_name) or QIcon()
            for combo in self._class_combos:
                combo.addItem(icon, class_name)
        if character_class:
            idx = self.character_class_combo.findText(character_class)
            if idx >= 0:
                for combo in self._class_combos:
                    combo.setCurrentIndex(idx)

        # Class can be changed from any of these combos (gear-icon settings
        # popup, Skill Description tab, or the Skill Planner header) — keep
        # them all in sync without looping.
        for combo in self._class_combos:
            combo.currentIndexChanged.connect(self._on_any_class_combo_changed)

        self._active_skill_class = self.character_class_combo.currentText().strip().lower()
        self._rebuild_skill_build_tabs()
        self._load_current_build_state()
        self._rebuild_equip_build_tabs()
        self._load_current_equip_build_state()

        self.character_class_combo.currentTextChanged.connect(self._rebuild_status_chance_rows)
        self._rebuild_status_chance_rows()

        if character_name:
            self.character_name_input.setText(character_name)

        if character_race:
            idx = self.character_race_combo.findText(character_race)
            if idx >= 0:
                self.character_race_combo.setCurrentIndex(idx)

    # ── "Skill Planner" tab — Skill Description (real data) + Skill Build ──

    def _build_skill_planner_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel(_t("arm_skill_planner_tab"))
        title.setObjectName("DetailHeader")
        title_row.addWidget(title)
        title_row.addStretch(1)
        outer.addLayout(title_row)

        self._skill_builds_data: dict[str, dict[str, dict]] = {}
        self._current_build_name = "Default"
        self.skill_build_tabs_row = QHBoxLayout()
        self.skill_build_tabs_row.setSpacing(6)
        self.skill_build_tabs_row.setAlignment(Qt.AlignLeft)
        outer.addLayout(self.skill_build_tabs_row)

        tabs = QTabWidget()
        tabs.setObjectName("timerModeTabWidget")
        tabs.addTab(self._build_skill_description_tab(), _t("arm_skill_description_tab"))
        tabs.addTab(self._build_skill_priority_tab(), _t("arm_priority_list_tab"))
        outer.addWidget(tabs, 1)

        return page

    def _build_skill_description_tab(self) -> QWidget:
        page = QWidget()
        outer = QHBoxLayout(page)
        outer.setContentsMargins(8, 12, 8, 8)
        outer.setSpacing(14)

        # ── Left: controls + grouped card list ──────────────────────────────
        left_container = QWidget()
        left_outer = QVBoxLayout(left_container)
        left_outer.setContentsMargins(0, 0, 0, 0)
        left_outer.setSpacing(10)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self.skill_search_input = QLineEdit()
        self.skill_search_input.setPlaceholderText(_t("arm_search_placeholder"))
        self.skill_search_input.textChanged.connect(self._refresh_skill_description_view)
        controls_row.addWidget(self.skill_search_input, 1)

        self._skill_type_buttons: dict[str, QPushButton] = {}
        for type_key, label in (("active", _t("arm_active")), ("passive", _t("arm_passive")), ("stigma", "Stigma")):
            btn = QPushButton(label)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setMinimumSize(72, 32)
            btn.toggled.connect(self._refresh_skill_description_view)
            controls_row.addWidget(btn)
            self._skill_type_buttons[type_key] = btn

        self.skill_checked_only_btn = QPushButton(_t("arm_only_checked"))
        self.skill_checked_only_btn.setObjectName("SkillFilterButton")
        self.skill_checked_only_btn.setCheckable(True)
        self.skill_checked_only_btn.setMinimumSize(100, 32)
        self.skill_checked_only_btn.toggled.connect(self._refresh_skill_description_view)
        controls_row.addWidget(self.skill_checked_only_btn)

        left_outer.addLayout(controls_row)

        self._skills_by_class = _load_skills_by_class()
        self._skill_checked_ids: set = set()

        cards_container = QWidget()
        cards_outer = QVBoxLayout(cards_container)
        cards_outer.setContentsMargins(4, 4, 4, 4)
        cards_outer.setSpacing(16)
        cards_outer.setAlignment(Qt.AlignTop)

        self.skill_card_sections: dict[str, QGridLayout] = {}
        self.skill_card_section_headers: dict[str, QLabel] = {}
        self.skill_card_section_containers: dict[str, QWidget] = {}
        for type_key, label in self._SKILL_BUILD_SECTIONS:
            section_label = QLabel(_t(label))
            section_label.setObjectName("SkillSectionHeader")
            cards_outer.addWidget(section_label)
            self.skill_card_section_headers[type_key] = section_label

            grid_widget = QWidget()
            grid = QGridLayout(grid_widget)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(10)
            grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            cards_outer.addWidget(grid_widget)
            self.skill_card_sections[type_key] = grid
            self.skill_card_section_containers[type_key] = grid_widget

        cards_scroll = QScrollArea()
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setWidget(cards_container)
        cards_scroll.viewport().setStyleSheet("background: transparent;")
        left_outer.addWidget(cards_scroll, 1)

        outer.addWidget(left_container, 3)

        # ── Right: selected skill detail ────────────────────────────────────
        right_panel = QFrame()
        right_panel.setObjectName("TopBar")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(10)
        right_layout.setAlignment(Qt.AlignTop)

        self.skill_desc_icon_label = QLabel()
        self.skill_desc_icon_label.setObjectName("SkillTileIcon")
        self.skill_desc_icon_label.setFixedSize(96, 96)
        self.skill_desc_icon_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.skill_desc_icon_label, 0, Qt.AlignHCenter)

        self.skill_desc_title_label = QLabel(_t("arm_choose_a_skill"))
        self.skill_desc_title_label.setObjectName("DetailHeader")
        self.skill_desc_title_label.setAlignment(Qt.AlignCenter)
        self.skill_desc_title_label.setWordWrap(True)
        right_layout.addWidget(self.skill_desc_title_label)

        self.skill_desc_badges_row = QHBoxLayout()
        self.skill_desc_badges_row.setSpacing(6)
        self.skill_desc_badges_row.setAlignment(Qt.AlignCenter)
        right_layout.addLayout(self.skill_desc_badges_row)

        self.skill_desc_text_label = QLabel("")
        self.skill_desc_text_label.setObjectName("DetailInfo")
        self.skill_desc_text_label.setWordWrap(True)
        self.skill_desc_text_label.setTextFormat(Qt.RichText)
        right_layout.addWidget(self.skill_desc_text_label)

        self.skill_desc_specs_header = QLabel(_t("arm_specializations"))
        self.skill_desc_specs_header.setObjectName("EquipSectionLabel")
        self.skill_desc_specs_header.setVisible(False)
        right_layout.addWidget(self.skill_desc_specs_header)

        self.skill_desc_specs_label = QLabel("")
        self.skill_desc_specs_label.setObjectName("DetailInfo")
        self.skill_desc_specs_label.setWordWrap(True)
        self.skill_desc_specs_label.setVisible(False)
        right_layout.addWidget(self.skill_desc_specs_label)

        stats_header = QLabel(_t("arm_details_label"))
        stats_header.setObjectName("EquipSectionLabel")
        right_layout.addWidget(stats_header)

        self.skill_desc_stats_label = QLabel("—")
        self.skill_desc_stats_label.setObjectName("DetailInfo")
        self.skill_desc_stats_label.setWordWrap(True)
        self.skill_desc_stats_label.setTextFormat(Qt.RichText)
        right_layout.addWidget(self.skill_desc_stats_label)

        right_layout.addStretch(1)
        outer.addWidget(right_panel, 2)

        self._skill_desc_selected_id: int | None = None

        self.character_class_combo.currentTextChanged.connect(self._refresh_skill_description_view)
        self._refresh_skill_description_view()

        return page

    # 2nd element is a translation KEY, not display text -- class-level
    # attribute, evaluated once at class-definition (import) time, so it
    # must not bake in _t() -- see _QUICK_GEAR_SLOT_LABELS for the same
    # reasoning at module level.
    _SKILL_BUILD_SECTIONS = (("active", "arm_active_skills"), ("passive", "arm_passive_skills"), ("stigma", "arm_stigma_skills"))

    def _build_skill_priority_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(16)
        outer.setAlignment(Qt.AlignTop)

        hint = QLabel(_t("arm_skill_priority_hint"))
        hint.setObjectName("DetailInfo")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        self._skill_priority_ids: dict[str, list[int | None]] = {}
        self.skill_priority_rows: dict[str, QHBoxLayout] = {}

        for type_key, label in self._SKILL_BUILD_SECTIONS:
            section_label = QLabel(_t(label))
            section_label.setObjectName("SkillSectionHeader")
            outer.addWidget(section_label)

            row_container = QWidget()
            row_layout = QHBoxLayout(row_container)
            row_layout.setContentsMargins(4, 4, 4, 4)
            row_layout.setSpacing(6)
            row_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.skill_priority_rows[type_key] = row_layout

            row_scroll = QScrollArea()
            row_scroll.setWidgetResizable(True)
            row_scroll.setFixedHeight(112)
            row_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            row_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            row_scroll.setWidget(row_container)
            row_scroll.viewport().setStyleSheet("background: transparent;")
            outer.addWidget(row_scroll)

        outer.addStretch(1)

        for type_key, _ in self._SKILL_BUILD_SECTIONS:
            self._skill_priority_ids[type_key] = [None]

        return page

    def _rebuild_all_priority_rows(self):
        for type_key, _ in self._SKILL_BUILD_SECTIONS:
            self._rebuild_priority_row(type_key)

    # ── Saved skill builds (per class): named tabs holding one priority-list
    # + level set each, e.g. "Default" / "PvP" / "PvE" — session-only for now,
    # not yet persisted to disk. ────────────────────────────────────────────

    def _empty_build_state(self) -> dict:
        return {
            "priority": {key: [None] for key, _ in self._SKILL_BUILD_SECTIONS},
        }

    def _ensure_class_builds(self, class_name: str):
        if class_name not in self._skill_builds_data:
            self._skill_builds_data[class_name] = {"Default": self._empty_build_state()}

    def _save_current_build_state(self, class_name: str):
        self._ensure_class_builds(class_name)
        builds = self._skill_builds_data[class_name]
        if self._current_build_name not in builds:
            return
        builds[self._current_build_name] = {
            "priority": {k: list(v) for k, v in self._skill_priority_ids.items()},
        }

    def _load_current_build_state(self):
        class_name = self.character_class_combo.currentText().strip().lower()
        self._ensure_class_builds(class_name)
        builds = self._skill_builds_data[class_name]
        if self._current_build_name not in builds:
            self._current_build_name = next(iter(builds))
        state = builds[self._current_build_name]

        self._skill_priority_ids = {k: list(v) for k, v in state["priority"].items()}
        self._rebuild_all_priority_rows()

    def _rebuild_skill_build_tabs(self):
        _clear_layout(self.skill_build_tabs_row)
        class_name = self.character_class_combo.currentText().strip().lower()
        self._ensure_class_builds(class_name)
        builds = self._skill_builds_data[class_name]
        if self._current_build_name not in builds:
            self._current_build_name = next(iter(builds))

        self._skill_build_tab_group = QButtonGroup(self)
        self._skill_build_tab_group.setExclusive(True)
        for build_name in builds:
            btn = _BuildTabButton(build_name)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(build_name == self._current_build_name)
            btn.setMinimumHeight(32)
            btn.clicked.connect(lambda checked=False, bn=build_name: self._on_switch_build(bn))
            btn.doubleClicked.connect(lambda bn=build_name: self._on_rename_build(bn))
            btn.setToolTip(_t("arm_rename_hint"))
            self._skill_build_tab_group.addButton(btn)
            self.skill_build_tabs_row.addWidget(btn)

        add_btn = QPushButton()
        add_btn.setIcon(_make_plus_icon())
        add_btn.setIconSize(QSize(20, 20))
        add_btn.setFixedSize(40, 32)
        add_btn.setToolTip(_t("arm_add_new_build"))
        add_btn.clicked.connect(self._on_add_build)
        self.skill_build_tabs_row.addWidget(add_btn)

        rename_btn = QPushButton()
        rename_btn.setIcon(_make_edit_icon())
        rename_btn.setIconSize(QSize(20, 20))
        rename_btn.setFixedSize(40, 32)
        rename_btn.setToolTip(_t("arm_rename_current_build"))
        rename_btn.clicked.connect(lambda checked=False: self._on_rename_build(self._current_build_name))
        self.skill_build_tabs_row.addWidget(rename_btn)

        save_btn = QPushButton()
        save_btn.setIcon(_make_save_icon())
        save_btn.setIconSize(QSize(20, 20))
        save_btn.setFixedSize(40, 32)
        save_btn.setToolTip(_t("arm_save_current_build"))
        save_btn.clicked.connect(self._on_save_current_build)
        self.skill_build_tabs_row.addWidget(save_btn)

    def _on_save_current_build(self):
        class_name = self.character_class_combo.currentText().strip().lower()
        self._save_current_build_state(class_name)

    def _on_switch_build(self, build_name: str):
        if build_name == self._current_build_name:
            return
        class_name = self.character_class_combo.currentText().strip().lower()
        self._save_current_build_state(class_name)
        self._current_build_name = build_name
        self._load_current_build_state()

    def _on_add_build(self):
        name, ok = QInputDialog.getText(self, _t("arm_new_build_title"), _t("arm_name_colon"))
        name = name.strip()
        if not ok or not name:
            return
        class_name = self.character_class_combo.currentText().strip().lower()
        self._ensure_class_builds(class_name)
        builds = self._skill_builds_data[class_name]
        if name in builds:
            return
        self._save_current_build_state(class_name)
        builds[name] = self._empty_build_state()
        self._current_build_name = name
        self._rebuild_skill_build_tabs()
        self._load_current_build_state()

    def _on_rename_build(self, old_name: str):
        new_name, ok = QInputDialog.getText(self, _t("arm_rename_build_title"), _t("arm_name_colon"), text=old_name)
        new_name = new_name.strip()
        if not ok or not new_name or new_name == old_name:
            return
        class_name = self.character_class_combo.currentText().strip().lower()
        builds = self._skill_builds_data[class_name]
        if new_name in builds:
            return
        builds[new_name] = builds.pop(old_name)
        if self._current_build_name == old_name:
            self._current_build_name = new_name
        self._rebuild_skill_build_tabs()

    def _find_skill_by_id(self, skill_id: int) -> dict | None:
        for skills in self._skills_by_class.values():
            for s in skills:
                if s.get("id") == skill_id:
                    return s
        return None

    def _rebuild_priority_row(self, type_key: str):
        row = self.skill_priority_rows[type_key]
        ids = self._skill_priority_ids[type_key]
        _clear_layout(row)

        for i, skill_id in enumerate(ids):
            if i > 0:
                arrow = QLabel(">")
                arrow.setObjectName("DetailEnchantValue")
                row.addWidget(arrow)
            skill = self._find_skill_by_id(skill_id) if skill_id else None
            row.addWidget(self._build_priority_slot(type_key, i, skill))

        arrow = QLabel(">")
        arrow.setObjectName("DetailEnchantValue")
        row.addWidget(arrow)

        add_btn = QPushButton("＋")
        add_btn.setFixedSize(44, 32)
        add_btn.setEnabled(ids[-1] is not None)
        add_btn.clicked.connect(lambda checked=False, tk=type_key: self._on_add_priority_slot(tk))
        row.addWidget(add_btn)

    def _build_priority_slot(self, type_key: str, index: int, skill: dict | None) -> QWidget:
        slot = QWidget()
        slot.setFixedWidth(76)
        layout = QVBoxLayout(slot)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        btn = QPushButton()
        btn.setObjectName("SkillTileIcon")
        btn.setFixedSize(64, 64)
        btn.setIconSize(QSize(56, 56))
        if skill:
            icon = _skill_icon(skill)
            if icon:
                btn.setIcon(icon)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda checked=False, tk=type_key, i=index: self._on_priority_slot_clicked(tk, i))
        layout.addWidget(btn, 0, Qt.AlignHCenter)

        full_name = skill.get("name", "") if skill else "Skill wählen"
        name_label = QLabel(_short_skill_name(full_name, 11) if skill else full_name)
        name_label.setObjectName("SkillTileName")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setToolTip(full_name)
        layout.addWidget(name_label)

        return slot

    def _on_priority_slot_clicked(self, type_key: str, index: int):
        class_name = _skills_data_class_key(self.character_class_combo.currentText())
        all_skills = sorted(self._skills_by_class.get(class_name, []), key=lambda s: s.get("name", ""))
        type_skills = [s for s in all_skills if s.get("type", "") == type_key]
        ids = self._skill_priority_ids[type_key]
        used_ids = {sid for i, sid in enumerate(ids) if sid is not None and i != index}
        skills = [s for s in type_skills if s.get("id") not in used_ids]
        dialog = SkillPickerDialog(skills, self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_skill:
            ids[index] = dialog.selected_skill.get("id")
            self._rebuild_priority_row(type_key)

    def _on_add_priority_slot(self, type_key: str):
        self._skill_priority_ids[type_key].append(None)
        self._rebuild_priority_row(type_key)

    _SKILL_DESC_CARD_COLUMNS = 2

    def _refresh_skill_description_view(self):
        for grid in self.skill_card_sections.values():
            _clear_layout(grid)

        class_name = _skills_data_class_key(self.character_class_combo.currentText())
        all_skills = sorted(self._skills_by_class.get(class_name, []), key=lambda s: s.get("name", ""))

        active_types = {t for t, btn in self._skill_type_buttons.items() if btn.isChecked()}
        query = self.skill_search_input.text().strip().lower()
        checked_only = self.skill_checked_only_btn.isChecked()
        skills = [
            s for s in all_skills
            if s.get("type", "") in active_types
            and (not query or query in s.get("name", "").lower())
            and (not checked_only or s.get("id") in self._skill_checked_ids)
        ]

        by_type: dict[str, list[dict]] = {key: [] for key, _ in self._SKILL_BUILD_SECTIONS}
        for skill in skills:
            skill_type = skill.get("type", "")
            if skill_type in by_type:
                by_type[skill_type].append(skill)

        for type_key, group in by_type.items():
            has_results = bool(group)
            self.skill_card_section_headers[type_key].setVisible(has_results)
            self.skill_card_section_containers[type_key].setVisible(has_results)
            if not has_results:
                continue
            grid = self.skill_card_sections[type_key]
            for i, skill in enumerate(group):
                row, col = divmod(i, self._SKILL_DESC_CARD_COLUMNS)
                grid.addWidget(self._build_skill_description_card(skill), row, col)

        self._skill_desc_selected_id = None
        self.skill_desc_icon_label.setPixmap(QPixmap())
        self.skill_desc_title_label.setText(_t("arm_choose_a_skill"))
        self.skill_desc_text_label.setText("")
        self.skill_desc_stats_label.setText("—")
        _clear_layout(self.skill_desc_badges_row)
        self.skill_desc_specs_header.setVisible(False)
        self.skill_desc_specs_label.setVisible(False)

    def _build_skill_description_card(self, skill: dict) -> QWidget:
        card = QPushButton()
        card.setObjectName("SkillDescCard")
        card.setCheckable(True)
        card.setCursor(Qt.PointingHandCursor)
        card.setMinimumHeight(60)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setObjectName("SkillRowIcon")
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignCenter)
        icon = _skill_icon(skill)
        if icon:
            icon_label.setPixmap(icon.pixmap(36, 36))
        layout.addWidget(icon_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name_label = QLabel(skill.get("name", ""))
        name_label.setObjectName("DetailName")
        text_col.addWidget(name_label)

        skill_type = skill.get("type", "")
        type_label = QLabel(skill_type.upper())
        color = _SKILL_TYPE_COLORS.get(skill_type, "#94a3b8")
        type_label.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        text_col.addWidget(type_label)
        layout.addLayout(text_col, 1)

        skill_id = skill.get("id")
        check_icon = QLabel()
        check_icon.setFixedSize(20, 20)
        check_icon.setPixmap(_make_check_icon())
        check_icon.setVisible(skill_id in self._skill_checked_ids)
        layout.addWidget(check_icon)

        card.setChecked(skill_id in self._skill_checked_ids)
        card.toggled.connect(lambda checked, s=skill, ci=check_icon: self._on_skill_description_card_clicked(s, checked, ci))
        return card

    def _on_skill_description_card_clicked(self, skill: dict, checked: bool, check_icon: QLabel):
        skill_id = skill.get("id")
        if checked:
            self._skill_checked_ids.add(skill_id)
        else:
            self._skill_checked_ids.discard(skill_id)
        check_icon.setVisible(checked)

        if self.skill_checked_only_btn.isChecked() and not checked:
            self._refresh_skill_description_view()
            return

        self._skill_desc_selected_id = skill_id

        icon = _skill_icon(skill)
        self.skill_desc_icon_label.setPixmap(icon.pixmap(88, 88) if icon else QPixmap())
        self.skill_desc_title_label.setText(skill.get("name", ""))

        _clear_layout(self.skill_desc_badges_row)
        skill_type = skill.get("type", "")
        if skill_type:
            self.skill_desc_badges_row.addWidget(
                _make_type_badge(skill_type.capitalize(), _SKILL_TYPE_COLORS.get(skill_type, "#94a3b8"))
            )
        damage_type = skill.get("damageType", "")
        if damage_type in ("physic", "magic"):
            label = "Physical" if damage_type == "physic" else "Magic"
            color = "#f87171" if damage_type == "physic" else "#60a5fa"
            self.skill_desc_badges_row.addWidget(_make_type_badge(label, color))

        self.skill_desc_text_label.setText(
            _render_skill_description(skill.get("description", ""), skill.get("levels"), 1)
        )

        specs = skill.get("specializations") or []
        if specs:
            lines = []
            for spec in specs:
                lvl = spec.get("parentSkillLvl", "?")
                note = spec.get("specialized", "").strip()
                lines.append(f"Lv {lvl}: {note}" if note else f"Lv {lvl}")
            self.skill_desc_specs_label.setText("\n".join(lines))
        self.skill_desc_specs_header.setVisible(bool(specs))
        self.skill_desc_specs_label.setVisible(bool(specs))

        self.skill_desc_stats_label.setText(_format_skill_stats(skill))

    # ── "EQ-Priorität" tab ──────────────────────────────────────────────────

    def _build_equip_priority_tab(self) -> QWidget:
        """Same idea as the Skill Planner's own priority list (see
        _build_skill_priority_tab): a chain of slots per section, '+' to
        append — here for planning an acquisition/upgrade order across
        specific equipment items instead of skills. Reuses ItemPickerPopup
        (search/grade filter/PvP-PvE filter) for picking, anchored to the
        clicked slot, same as a real Equipment-tab slot.

        Laid out 3 sections per row (grid) instead of one full-width row
        per section — with 11 sections stacked one-per-row the tab was
        mostly empty horizontal space either side of a short item chain."""
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(16)
        outer.setAlignment(Qt.AlignTop)

        hint = QLabel(_t("arm_equip_priority_hint"))
        hint.setObjectName("DetailInfo")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        outer.addLayout(grid)
        outer.addStretch(1)

        self._equip_priority_items: dict[str, list[dict | None]] = {}
        self.equip_priority_rows: dict[str, QHBoxLayout] = {}

        columns = 3
        for idx, (section_key, label, _categories) in enumerate(_EQUIP_PRIORITY_SECTIONS):
            section_box = QWidget()
            section_layout = QVBoxLayout(section_box)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(6)

            section_label = QLabel(_t(label))
            section_label.setObjectName("SkillSectionHeader")
            section_layout.addWidget(section_label)

            row_container = QWidget()
            row_layout = QHBoxLayout(row_container)
            row_layout.setContentsMargins(4, 4, 4, 4)
            row_layout.setSpacing(6)
            row_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.equip_priority_rows[section_key] = row_layout

            row_scroll = QScrollArea()
            row_scroll.setWidgetResizable(True)
            row_scroll.setFixedHeight(112)
            row_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            row_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            row_scroll.setWidget(row_container)
            row_scroll.viewport().setStyleSheet("background: transparent;")
            section_layout.addWidget(row_scroll)

            grid.addWidget(section_box, idx // columns, idx % columns)

        for col in range(columns):
            grid.setColumnStretch(col, 1)

        for section_key, _label, _categories in _EQUIP_PRIORITY_SECTIONS:
            self._equip_priority_items[section_key] = [None]
            self._rebuild_equip_priority_row(section_key)

        # Several rows of sections can overflow the tab's visible height —
        # wrap in a scroll area, same as the Stat Info column already does.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(page)
        scroll.viewport().setStyleSheet("background: transparent;")
        return scroll

    def _rebuild_equip_priority_row(self, section_key: str):
        row = self.equip_priority_rows[section_key]
        items = self._equip_priority_items[section_key]
        _clear_layout(row)

        for i, item in enumerate(items):
            if i > 0:
                row.addWidget(self._build_equip_priority_arrow())
            row.addWidget(self._build_equip_priority_slot(section_key, i, item))

        if len(items) < _EQUIP_PRIORITY_MAX_ITEMS:
            row.addWidget(self._build_equip_priority_arrow())

            add_btn = QPushButton("＋")
            add_btn.setFixedSize(44, 32)
            add_btn.setEnabled(items[-1] is not None)
            add_btn.clicked.connect(lambda checked=False, sk=section_key: self._on_add_equip_priority_slot(sk))
            row.addWidget(add_btn)

    def _build_equip_priority_arrow(self) -> QLabel:
        arrow = QLabel("→")
        arrow.setObjectName("EquipPriorityArrow")
        arrow.setAlignment(Qt.AlignCenter)
        arrow.setFixedSize(32, 32)
        return arrow

    def _build_equip_priority_slot(self, section_key: str, index: int, item: dict | None) -> QWidget:
        slot = QWidget()
        slot.setFixedWidth(76)
        layout = QVBoxLayout(slot)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        btn = QToolButton()
        btn.setObjectName("SkillTileIcon")
        btn.setFixedSize(64, 64)
        btn.setIconSize(QSize(56, 56))
        if item:
            image_url = item.get("image", "")
            pix = self.icon_cache.pixmap(image_url, 56, grade=item.get("grade"))
            if pix:
                btn.setIcon(QIcon(pix))
            elif image_url:
                self.icon_cache.request(image_url)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(
            lambda checked=False, sk=section_key, i=index, b=btn: self._on_equip_priority_slot_clicked(sk, i, b)
        )
        layout.addWidget(btn, 0, Qt.AlignHCenter)

        full_name = item.get("name", "") if item else _t("arm_choose_item_placeholder")
        name_label = QLabel(_short_skill_name(full_name, 11) if item else full_name)
        name_label.setObjectName("SkillTileName")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setToolTip(full_name)
        layout.addWidget(name_label)

        return slot

    def _on_equip_priority_slot_clicked(self, section_key: str, index: int, anchor: QWidget):
        categories = next(cats for key, _label, cats in _EQUIP_PRIORITY_SECTIONS if key == section_key)
        if section_key == "weapon":
            # Same narrowing _pick_for_slot already does for MainHand — a
            # class only ever uses one weapon category, so without this the
            # popup was built from ALL weapon categories across all 8
            # classes at once (Greatsword+Longsword+Dagger+Bow+Spellbook+
            # Orb+Mace+Staff+Fist combined), thousands of items, which is
            # what caused the reported lag/error. "guard" is its own
            # section now (see _EQUIP_PRIORITY_SECTIONS) and needs no
            # class narrowing, same as SubHand in _pick_for_slot.
            selected_class = self.character_class_combo.currentText()
            weapon_category = CLASS_WEAPON_CATEGORY.get(selected_class)
            if weapon_category:
                categories = [weapon_category]
        popup = ItemPickerPopup(
            self._items, categories, self.icon_cache, self.detail_cache, self,
            active_gear_types=self._active_gear_types,
            equipped_ids={item.get("id") for item in self._equipped.values() if item},
        )
        popup.item_chosen.connect(
            lambda item, sk=section_key, i=index: self._on_equip_priority_item_chosen(sk, i, item)
        )
        # Kept alive via this reference — a Qt.Popup with no other owner
        # would otherwise get garbage-collected before it can emit.
        self._active_picker_popup = popup
        popup.show_anchored(anchor)

    def _on_equip_priority_item_chosen(self, section_key: str, index: int, item: dict):
        self._equip_priority_items[section_key][index] = item
        self._rebuild_equip_priority_row(section_key)

    def _on_add_equip_priority_slot(self, section_key: str):
        if len(self._equip_priority_items[section_key]) >= _EQUIP_PRIORITY_MAX_ITEMS:
            return
        self._equip_priority_items[section_key].append(None)
        self._rebuild_equip_priority_row(section_key)

    # ── "Arcana & Titel" tab ────────────────────────────────────────────────

    def _build_arcana_column(self) -> QHBoxLayout:
        """Arcana Set/card browser, built from real data (see
        ARCANA_CARD_TYPES/ARCANA_THEME_ORDER above): 7 Sets on the left
        (colored by PvE/PvP/Offensiv/Defensiv/Heilung category, mutually
        exclusive with a "Keine Sets" neutral state) and all 10 real card
        slots on the right. Choosing a Set previews which real Empyrean
        Lord (or Main Stat, for the 4 Stat cards) and which grades each
        card would have; clicking an available Lord card opens the real
        class-specific skill pool in a popover, using the class already
        selected up in the shared header (self._active_skill_class) rather
        than a separate class picker. Replaces the old 5-slot equip-picker
        mock-up — real player data (see project notes) confirmed all 10
        card types and all 10 slots are actually live, not just 5.
        This is a browsing/reference tool for now, not wired into equip
        state, GearScore, or Stat Info — shugo.gg exposes no real numeric
        Arcana stat values to integrate with those anyway."""
        root = QHBoxLayout()
        root.setSpacing(24)

        self._arcana_theme_map, self._arcana_default_icon = _load_arcana_theme_map()
        self._arcana_class_skills = _load_arcana_class_skills()
        self._arcana_active_theme: str | None = None
        self._arcana_card_widgets: dict[str, _ArcanaCardButton] = {}
        self._active_arcana_popup: _ArcanaSkillPopup | None = None

        left_col = QVBoxLayout()
        left_col.setSpacing(8)

        self._arcana_set_group = QButtonGroup(self)
        self._arcana_set_group.setExclusive(True)

        none_btn = QPushButton(_t("arm_no_sets"))
        none_btn.setObjectName("ArcanaNoneButton")
        none_btn.setCheckable(True)
        none_btn.setChecked(True)
        none_btn.setFixedWidth(_ARCANA_SET_COLUMN_WIDTH)
        none_btn.setMinimumHeight(40)
        none_btn.setCursor(Qt.PointingHandCursor)
        none_btn.clicked.connect(lambda: self._on_arcana_set_selected(None))
        self._arcana_set_group.addButton(none_btn)
        left_col.addWidget(none_btn)

        for theme in ARCANA_THEME_ORDER:
            category = ARCANA_THEME_CATEGORY[theme]
            btn = QPushButton(f"{theme}\n{ARCANA_CATEGORY_LABELS[category]}")
            btn.setObjectName("ArcanaSetBanner")
            btn.setProperty("category", category)
            btn.setCheckable(True)
            btn.setFixedWidth(_ARCANA_SET_COLUMN_WIDTH)
            btn.setMinimumHeight(68)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _c=False, t=theme: self._on_arcana_set_selected(t))
            self._arcana_set_group.addButton(btn)
            left_col.addWidget(btn)

        self._arcana_bonus_panel = QFrame()
        self._arcana_bonus_panel.setObjectName("ArcanaBonusPanel")
        self._arcana_bonus_panel.setFixedWidth(_ARCANA_SET_COLUMN_WIDTH)
        self._arcana_bonus_panel.setVisible(False)
        bonus_layout = QVBoxLayout(self._arcana_bonus_panel)
        bonus_layout.setContentsMargins(14, 12, 14, 12)
        bonus_layout.setSpacing(4)
        self._arcana_bonus_title = QLabel("")
        self._arcana_bonus_title.setObjectName("EquipSectionLabel")
        self._arcana_bonus_title.setWordWrap(True)
        bonus_layout.addWidget(self._arcana_bonus_title)
        self._arcana_bonus_2pc = QLabel("")
        self._arcana_bonus_2pc.setObjectName("DetailInfo")
        self._arcana_bonus_2pc.setWordWrap(True)
        bonus_layout.addWidget(self._arcana_bonus_2pc)
        self._arcana_bonus_4pc = QLabel("")
        self._arcana_bonus_4pc.setObjectName("DetailInfo")
        self._arcana_bonus_4pc.setWordWrap(True)
        bonus_layout.addWidget(self._arcana_bonus_4pc)
        bonus_source = QLabel(_t("arm_source_aion2hub"))
        bonus_source.setObjectName("DetailDisclaimer")
        bonus_layout.addWidget(bonus_source)
        left_col.addWidget(self._arcana_bonus_panel)

        left_col.addStretch()
        root.addLayout(left_col)

        right_col = QVBoxLayout()
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, card_type in enumerate(ARCANA_CARD_TYPES):
            row, col_idx = divmod(i, 5)
            card = _ArcanaCardButton(card_type)
            card.clicked.connect(lambda _c=False, ct=card_type: self._on_arcana_card_clicked(ct))
            grid.addWidget(card, row, col_idx)
            self._arcana_card_widgets[card_type] = card
        right_col.addLayout(grid)

        right_col.addWidget(self._build_arcana_lord_bar())
        right_col.addStretch()
        root.addLayout(right_col, 1)

        self._refresh_arcana_cards()
        return root

    def _build_arcana_lord_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ArcanaLordBar")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel(_t("arm_arcana_types"))
        title.setObjectName("EquipSectionLabel")
        layout.addWidget(title)

        text = QLabel()
        text.setObjectName("DetailInfo")
        text.setWordWrap(True)
        text.setTextFormat(Qt.RichText)
        parts = [
            f'<span style="color:#facc15;font-weight:700;">{lord}</span> &rarr; {effect}'
            for lord, effect in ARCANA_LORD_EFFECTS.items()
        ]
        text.setText("&nbsp;&nbsp;&nbsp;&nbsp;".join(parts))
        layout.addWidget(text)
        return frame

    def _on_arcana_set_selected(self, theme: str | None):
        self._arcana_active_theme = theme
        self._refresh_arcana_cards()

        if theme is None:
            self._arcana_bonus_panel.setVisible(False)
            return
        info = ARCANA_SET_BONUSES.get(theme, {})
        self._arcana_bonus_title.setText(_t("arm_set_bonus", name=info.get('setName', theme)))
        self._arcana_bonus_2pc.setText(_t("arm_set_bonus_2pc", text=info.get('2pc', '')))
        self._arcana_bonus_4pc.setText(_t("arm_set_bonus_4pc", text=info.get('4pc', '')))
        self._arcana_bonus_panel.setVisible(True)

    def _refresh_arcana_cards(self):
        theme = self._arcana_active_theme
        for card_type, card in self._arcana_card_widgets.items():
            if theme is None:
                card.set_default_state(self._arcana_default_icon.get(card_type))
                continue
            entry = self._arcana_theme_map.get(theme, {}).get(card_type)
            if entry is None:
                card.set_unavailable_state()
            else:
                card.set_themed_state(entry)

    def _on_arcana_card_clicked(self, card_type: str):
        card = self._arcana_card_widgets[card_type]
        if not card.entry or not card.entry.get("lord"):
            return  # unavailable in this Set, or one of the 4 Stat cards (no skills)
        class_name = self._active_skill_class
        pool = self._arcana_class_skills.get(card_type, {}).get(class_name, [])
        popup = _ArcanaSkillPopup(card_type, class_name.capitalize() if class_name else "?", pool, self)
        popup.show_anchored(card)
        # Kept alive via this reference — a Qt.Popup with no other owner
        # would otherwise get garbage-collected before it can show.
        self._active_arcana_popup = popup

    # ── Middle column: aggregated Stat Info by default, per-slot editor
    # (dropdown + clear, icon + title, enchant slider, item stats) once a
    # slot is clicked — swapped via a QStackedWidget. ─────────────────────

    def _build_equip_center_stack(self) -> QStackedWidget:
        self.equip_center_stack = QStackedWidget()

        stat_info_page = QWidget()
        stat_info_page.setLayout(self._build_stat_info_column())
        # PvP mode adds a whole Status Chance/Resist block on top of the
        # mode rows, tall enough to clip on smaller windows without this —
        # scroll the column instead of losing rows off the bottom.
        stat_info_scroll = QScrollArea()
        stat_info_scroll.setWidgetResizable(True)
        stat_info_scroll.setFrameShape(QFrame.NoFrame)
        stat_info_scroll.setWidget(stat_info_page)
        stat_info_scroll.viewport().setStyleSheet("background: transparent;")
        self.equip_center_stack.addWidget(stat_info_scroll)

        equip_item_page = QWidget()
        page_layout = QVBoxLayout(equip_item_page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        equip_back_btn = QPushButton()
        equip_back_btn.setIcon(_make_back_icon())
        equip_back_btn.setIconSize(QSize(16, 16))
        equip_back_btn.setFixedSize(36, 36)
        equip_back_btn.setToolTip(_t("arm_back_to_stat_overview_tooltip"))
        equip_back_btn.setCursor(Qt.PointingHandCursor)
        equip_back_btn.clicked.connect(self._on_equip_back_clicked)
        header_row.addWidget(equip_back_btn)

        self.equip_item_icon_label = QLabel()
        self.equip_item_icon_label.setFixedSize(36, 36)
        self.equip_item_icon_label.setAlignment(Qt.AlignCenter)
        header_row.addWidget(self.equip_item_icon_label)

        self.equip_item_combo_btn = QPushButton(_t("arm_choose_slot"))
        self.equip_item_combo_btn.setObjectName("EquipItemComboButton")
        self.equip_item_combo_btn.setCursor(Qt.PointingHandCursor)
        self.equip_item_combo_btn.clicked.connect(self._on_equip_item_combo_clicked)
        header_row.addWidget(self.equip_item_combo_btn, 1)

        self.equip_item_clear_btn = QPushButton()
        self.equip_item_clear_btn.setIcon(_make_close_icon())
        self.equip_item_clear_btn.setIconSize(QSize(16, 16))
        self.equip_item_clear_btn.setFixedSize(36, 36)
        self.equip_item_clear_btn.setToolTip(_t("arm_clear_slot_tooltip"))
        self.equip_item_clear_btn.clicked.connect(self._on_equip_item_clear_clicked)
        header_row.addWidget(self.equip_item_clear_btn)

        page_layout.addLayout(header_row)

        self.equip_detail_widget = ItemDetailWidget(self.icon_cache, self.detail_cache, self, compact=True)
        # Same reasoning as stat_info_scroll above -- with several substat/
        # skill accordions plus the enchant slider, this panel can get
        # taller than a smaller screen's window; scroll it instead of
        # clipping content, so nothing becomes unreachable regardless of
        # how many accordion sections happen to be open at once.
        equip_detail_scroll = QScrollArea()
        equip_detail_scroll.setWidgetResizable(True)
        equip_detail_scroll.setFrameShape(QFrame.NoFrame)
        equip_detail_scroll.setWidget(self.equip_detail_widget)
        equip_detail_scroll.viewport().setStyleSheet("background: transparent;")
        page_layout.addWidget(equip_detail_scroll, 1)
        self.icon_cache.icon_ready.connect(self.equip_detail_widget.on_icon_ready)
        self.detail_cache.detail_ready.connect(self.equip_detail_widget.on_detail_ready)

        self.equip_center_stack.addWidget(equip_item_page)
        self.equip_center_stack.setCurrentIndex(0)

        return self.equip_center_stack

    @staticmethod
    def _slot_info(slot_id: str) -> tuple[str, list[str]]:
        for sid, label, categories in SLOT_LAYOUT:
            if sid == slot_id:
                return _t(label), categories
        return slot_id, []

    def _refresh_equip_item_panel(self):
        slot_id = self._selected_equip_slot_id
        if slot_id is None:
            return
        item = self._equipped.get(slot_id)

        if item is None:
            label, _ = self._slot_info(slot_id)
            self.equip_item_combo_btn.setText(_t("arm_choose_x", label=label))
            self.equip_item_icon_label.setPixmap(QPixmap())
            self.equip_item_icon_label.setStyleSheet("")
            self.equip_detail_widget.clear()
            return

        self.equip_item_combo_btn.setText(item.get("name", ""))
        image_url = item.get("image", "")
        grade = item.get("grade", "")
        glow_color = GRADE_COLORS.get(grade, "#475569")
        cached_icon = self.icon_cache.pixmap(image_url, 32, grade=grade)
        if cached_icon:
            self.equip_item_icon_label.setPixmap(cached_icon)
        else:
            self.equip_item_icon_label.setPixmap(QPixmap())
            self.icon_cache.request(image_url)
        self.equip_item_icon_label.setStyleSheet(
            f"background-color: rgba(15, 23, 42, 0.75); border: 2px solid {glow_color}; border-radius: 8px;"
        )

        self.equip_detail_widget.load_item(
            item.get("id"), item.get("name", ""), image_url,
            preset_substats=self._equipped_substats.get(slot_id),
            preset_enchant=self._equipped_enchant.get(slot_id, 0),
            character_class=self.character_class_combo.currentText(),
        )

    def _on_equip_back_clicked(self):
        self._capture_current_substats()
        self._selected_equip_slot_id = None
        self.equip_center_stack.setCurrentIndex(0)

    def _on_equip_item_combo_clicked(self):
        slot_id = self._selected_equip_slot_id
        if not slot_id:
            return
        _, categories = self._slot_info(slot_id)
        self._pick_for_slot(slot_id, categories, self.equip_item_combo_btn)

    def _on_equip_item_clear_clicked(self):
        slot_id = self._selected_equip_slot_id
        if not slot_id:
            return
        self._equipped.pop(slot_id, None)
        self._equipped_substats.pop(slot_id, None)

        icon_btn = self._slot_icon_buttons.get(slot_id)
        if icon_btn:
            label, _ = self._slot_info(slot_id)
            icon_btn.setToolTip(_t("arm_slot_empty_tooltip", label=label))
            placeholder = _EQUIPMENT_SLOT_PLACEHOLDER.get(slot_id)
            icon = _placeholder_icon("equipment", placeholder) if placeholder else None
            icon_btn.setIcon(icon or QIcon())
        self._update_slot_enchant_label(slot_id)

        self._update_gearscore()
        self._refresh_stat_info()
        self._refresh_equip_item_panel()
        self._update_quick_stat_btn_visibility()

    def _build_stat_info_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(10)

        title = QLabel(_t("arm_stat_values"))
        title.setObjectName("DetailHeader")
        col.addWidget(title)

        self._stat_gearscore_label = QLabel(_t("arm_gearscore_zero"))
        self._stat_gearscore_label.setObjectName("GearScoreHeaderLabel")
        col.addWidget(self._stat_gearscore_label)

        icon_panel = QFrame()
        icon_panel.setObjectName("TopBar")
        icon_grid = QGridLayout(icon_panel)
        icon_grid.setContentsMargins(12, 12, 12, 12)
        icon_grid.setSpacing(10)
        self._icon_stat_labels: dict[str, tuple[QLabel, str]] = {}
        for row_idx, row_stats in enumerate(_STAT_ICON_ROWS):
            color = _STAT_ICON_ROW_COLORS[row_idx % len(_STAT_ICON_ROW_COLORS)]
            for col_idx, (name, icon_key, value_stat_id) in enumerate(row_stats):
                cell = QWidget()
                cell_layout = QVBoxLayout(cell)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                cell_layout.setSpacing(2)

                icon_label = QLabel()
                icon_label.setFixedSize(38, 38)
                icon_label.setAlignment(Qt.AlignCenter)
                real_icon = _real_stat_icon(icon_key)
                if real_icon:
                    icon_label.setPixmap(real_icon)
                else:
                    icon_label.setPixmap(_make_stat_badge_icon(_STAT_ICON_ABBREVIATIONS.get(icon_key, "?"), color))
                cell_layout.addWidget(icon_label, 0, Qt.AlignHCenter)

                name_label = QLabel(name)
                name_label.setObjectName("DetailName")
                name_label.setAlignment(Qt.AlignCenter)
                name_label.setWordWrap(True)
                name_label.setFixedWidth(78)
                # Reserves room for 2 wrapped lines so a longer name (e.g.
                # "Destruction") never overlaps the value label below it.
                name_label.setMinimumHeight(30)
                cell_layout.addWidget(name_label, 0, Qt.AlignHCenter)

                value_label = QLabel("0")
                value_label.setObjectName("DetailInfo")
                value_label.setAlignment(Qt.AlignCenter)
                cell_layout.addWidget(value_label, 0, Qt.AlignHCenter)

                icon_grid.addWidget(cell, row_idx, col_idx)
                self._icon_stat_labels[name] = (value_label, value_stat_id)

        col.addWidget(icon_panel)

        tabs = QTabWidget()
        tabs.setObjectName("timerModeTabWidget")

        main_tab = QWidget()
        main_layout = QVBoxLayout(main_tab)
        self._build_main_stats_tab(main_layout)
        tabs.addTab(main_tab, _t("arm_main_stats_tab"))

        sub_tab = QWidget()
        sub_layout = QVBoxLayout(sub_tab)
        self._build_sub_stats_tab(sub_layout)
        tabs.addTab(sub_tab, _t("arm_sub_stats_tab"))

        # Column count per tab is chosen by how long its stat names run —
        # fewer columns for tabs with long names (e.g. "Parry Damage
        # Reduction Amount") so cells stay readable instead of cramming.
        extra_tab_defs = [
            ("Utility & Recovery", _UTILITY_RECOVERY_STAT_ROWS, 2),
        ]
        self._extra_stat_labels: dict[str, dict] = {}
        for tab_label, rows, columns in extra_tab_defs:
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            self._extra_stat_labels[tab_label] = self._build_stat_rows(tab_layout, rows, columns=columns)
            # "&" in Qt widget text is a mnemonic marker (the following
            # character -- here a space -- gets underlined instead of
            # showing a literal "&"), which rendered as "Utility_Recovery"
            # (User-Screenshot) instead of "Utility & Recovery". Escaping
            # only the DISPLAYED tab text as "&&"; the dict key above stays
            # the real, un-escaped tab_label for lookups elsewhere.
            tabs.addTab(tab_widget, _t("arm_tab_utility_recovery").replace("&", "&&"))

        col.addWidget(tabs)

        disclaimer = QLabel(_t("arm_stat_sum_note"))
        disclaimer.setObjectName("DetailDisclaimer")
        disclaimer.setWordWrap(True)
        col.addWidget(disclaimer)

        col.addStretch()
        return col

    def _build_main_stats_tab(self, layout: QVBoxLayout):
        mode_row = QHBoxLayout()
        section_label = QLabel(_t("arm_main_stats_tab"))
        section_label.setObjectName("EquipSectionLabel")
        mode_row.addWidget(section_label)
        mode_row.addStretch()

        self._stat_mode_group = QButtonGroup(self)
        self._stat_mode_group.setExclusive(True)
        pve_btn = QPushButton("PvE")
        pve_btn.setObjectName("SkillFilterButton")
        pve_btn.setCheckable(True)
        pve_btn.setChecked(True)
        pve_btn.setMinimumSize(64, 30)
        pvp_btn = QPushButton("PvP")
        pvp_btn.setObjectName("SkillFilterButton")
        pvp_btn.setCheckable(True)
        pvp_btn.setMinimumSize(64, 30)
        self._stat_mode_group.addButton(pve_btn)
        self._stat_mode_group.addButton(pvp_btn)
        pve_btn.clicked.connect(lambda: self._set_stat_info_mode("pve"))
        pvp_btn.clicked.connect(lambda: self._set_stat_info_mode("pvp"))
        mode_row.addWidget(pve_btn)
        mode_row.addWidget(pvp_btn)
        self._stat_mode_pve_btn = pve_btn
        self._stat_mode_pvp_btn = pvp_btn
        layout.addLayout(mode_row)

        self._main_stat_labels = self._build_stat_rows(layout, _MAIN_STAT_ROWS, columns=4, add_stretch=False)

        movement_label = QLabel(_t("arm_movement"))
        movement_label.setObjectName("EquipSectionLabel")
        layout.addWidget(movement_label)
        self._movement_stat_labels = self._build_stat_rows(layout, _MOVEMENT_STAT_ROWS, columns=4, add_stretch=False)

        self._stat_mode_heading = QLabel(_t("arm_pve_stats"))
        self._stat_mode_heading.setObjectName("EquipSectionLabel")
        layout.addWidget(self._stat_mode_heading)

        self._stat_pve_widget = QWidget()
        pve_layout = QVBoxLayout(self._stat_pve_widget)
        pve_layout.setContentsMargins(0, 0, 0, 0)
        self._pve_mode_labels = self._build_stat_rows(pve_layout, _PVE_MODE_STAT_ROWS, columns=4, add_stretch=False)
        layout.addWidget(self._stat_pve_widget)

        self._stat_pvp_widget = QWidget()
        pvp_layout = QVBoxLayout(self._stat_pvp_widget)
        pvp_layout.setContentsMargins(0, 0, 0, 0)
        self._pvp_mode_labels = self._build_stat_rows(pvp_layout, _PVP_MODE_STAT_ROWS, columns=4, add_stretch=False)
        layout.addWidget(self._stat_pvp_widget)
        self._stat_pvp_widget.setVisible(False)

        self._stat_status_block = QWidget()
        status_layout = QVBoxLayout(self._stat_status_block)
        status_layout.setContentsMargins(0, 0, 0, 0)

        chance_label = QLabel(_t("arm_status_chance"))
        chance_label.setObjectName("EquipSectionLabel")
        status_layout.addWidget(chance_label)
        self._status_chance_layout = QVBoxLayout()
        self._status_chance_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.addLayout(self._status_chance_layout)
        self._status_chance_labels: dict = {}

        resist_label = QLabel(_t("arm_status_resist"))
        resist_label.setObjectName("EquipSectionLabel")
        status_layout.addWidget(resist_label)
        resist_rows = [(name, stat_id) for name, stat_id, _effect in _STATUS_RESIST_STAT_ROWS]
        self._status_resist_labels = self._build_stat_rows(status_layout, resist_rows, columns=3, add_stretch=False)

        layout.addWidget(self._stat_status_block)
        self._stat_status_block.setVisible(False)

        layout.addStretch()
        self._stat_info_mode = "pve"

    def _build_sub_stats_tab(self, layout: QVBoxLayout):
        sub_label = QLabel(_t("arm_sub_stats_tab"))
        sub_label.setObjectName("EquipSectionLabel")
        layout.addWidget(sub_label)
        self._sub_stat_labels = self._build_stat_rows(layout, _SUB_STAT_ROWS, columns=4, add_stretch=False)

        offense_label = QLabel(_t("arm_offense"))
        offense_label.setObjectName("EquipSectionLabel")
        layout.addWidget(offense_label)
        self._sub_stat_labels.update(
            self._build_stat_rows(layout, _OFFENSE_STAT_ROWS, columns=3, add_stretch=False)
        )

        defense_label = QLabel(_t("arm_defense"))
        defense_label.setObjectName("EquipSectionLabel")
        layout.addWidget(defense_label)
        self._sub_stat_labels.update(
            self._build_stat_rows(layout, _DEFENSE_STAT_ROWS, columns=2, add_stretch=False)
        )

        layout.addStretch()

    def _set_stat_info_mode(self, mode: str):
        self._stat_info_mode = mode
        is_pvp = mode == "pvp"
        self._stat_pve_widget.setVisible(not is_pvp)
        self._stat_pvp_widget.setVisible(is_pvp)
        self._stat_status_block.setVisible(is_pvp)
        self._stat_mode_heading.setText(_t("arm_pvp_stats") if is_pvp else _t("arm_pve_stats"))

    @staticmethod
    def _build_stat_rows(layout: QVBoxLayout, rows: list[tuple], columns: int = 3, add_stretch: bool = True) -> dict:
        """Lays rows out as a compact multi-column grid (name + value per
        cell, thin divider under each) instead of one value-per-line — a
        single column left the value stranded far right of a narrow name."""
        labels = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(0)
        for col_idx in range(columns):
            grid.setColumnStretch(col_idx, 1)
        for index, (name, stat_id) in enumerate(rows):
            row_idx, col_idx = divmod(index, columns)
            cell = QFrame()
            cell.setObjectName("StatRowCell")
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(0, 7, 0, 7)
            name_label = QLabel(name)
            name_label.setObjectName("DetailInfo")
            value_label = QLabel("—")
            value_label.setObjectName("DetailInfo")
            value_label.setAlignment(Qt.AlignRight)
            cell_layout.addWidget(name_label, 1)
            cell_layout.addWidget(value_label)
            grid.addWidget(cell, row_idx, col_idx)
            labels[name] = (value_label, stat_id)
        layout.addLayout(grid)
        if add_stretch:
            layout.addStretch()
        return labels

    def _rebuild_status_chance_rows(self):
        class_key = _skills_data_class_key(self.character_class_combo.currentText())
        relevant = _CLASS_RELEVANT_CHANCE_EFFECTS.get(class_key)
        rows = [
            (name, stat_id) for name, stat_id, effect in _STATUS_CHANCE_STAT_ROWS
            if effect == "general" or not relevant or effect in relevant
        ]
        _clear_layout(self._status_chance_layout)
        self._status_chance_labels = self._build_stat_rows(
            self._status_chance_layout, rows, columns=3, add_stretch=False
        )
        self._refresh_stat_info()

    def _refresh_stat_info(self):
        totals: dict[str, float] = {}
        for slot_id, item in self._equipped.items():
            detail = self.detail_cache.get(item.get("id"))
            if not detail:
                continue
            for stat in detail.get("mainStats") or []:
                sid = stat.get("id")
                if sid:
                    totals[sid] = totals.get(sid, 0.0) + _parse_stat_value(stat.get("value"))
            sub_stats = detail.get("subStats") or []
            for i in self._equipped_substats.get(slot_id, set()):
                if i < len(sub_stats):
                    sid = sub_stats[i].get("id")
                    if sid:
                        totals[sid] = totals.get(sid, 0.0) + _parse_stat_value(sub_stats[i].get("value"))

            # Enchant bonus — same estimate formulas the item's own detail
            # panel uses for its "(+N)" line, so Stat Info stays consistent
            # with what that panel shows instead of ignoring the slider.
            level = self._equipped_enchant.get(slot_id, 0)
            if level:
                grade_name = detail.get("gradeName") or detail.get("grade") or ""
                category_name = detail.get("categoryName") or ""
                normal_max = int(detail.get("maxEnchantLevel") or 0)
                is_armor = category_name in _ARMOR_CATEGORIES or category_name == _BELT_CATEGORY
                if is_armor:
                    def_bonus, hp_bonus = estimate_armor_bonus(level, grade_name, normal_max, category_name)
                    totals[_DEFENSE_STAT_ID] = totals.get(_DEFENSE_STAT_ID, 0.0) + def_bonus
                    totals[_HP_STAT_ID] = totals.get(_HP_STAT_ID, 0.0) + hp_bonus
                    exceed = estimate_armor_exceed_bonus(level, normal_max)
                    totals[_DEFENSE_STAT_ID] = totals.get(_DEFENSE_STAT_ID, 0.0) + exceed["defense"]
                    totals[_HP_STAT_ID] = totals.get(_HP_STAT_ID, 0.0) + exceed["hp"]
                    if exceed["defense_pct"]:
                        totals["DefenseRatio"] = totals.get("DefenseRatio", 0.0) + exceed["defense_pct"]
                else:
                    bonus = estimate_enchant_bonus(level, grade_name, normal_max, category_name)
                    totals[_SCALING_STAT_ID] = totals.get(_SCALING_STAT_ID, 0.0) + bonus
                    exceed = estimate_exceed_bonus(level, normal_max, category_name)
                    totals[_SCALING_STAT_ID] = totals.get(_SCALING_STAT_ID, 0.0) + exceed["attack"]
                    if exceed["attack_pct"]:
                        totals["DamageRatio"] = totals.get("DamageRatio", 0.0) + exceed["attack_pct"]
                    if exceed["defense"]:
                        totals[_DEFENSE_STAT_ID] = totals.get(_DEFENSE_STAT_ID, 0.0) + exceed["defense"]

        label_groups = [
            (self._main_stat_labels, "—"),
            (self._movement_stat_labels, "—"),
            (self._sub_stat_labels, "—"),
            (self._icon_stat_labels, "0"),
            (self._pve_mode_labels, "—"),
            (self._pvp_mode_labels, "—"),
            (self._status_chance_labels, "—"),
            (self._status_resist_labels, "—"),
        ]
        label_groups.extend((labels, "—") for labels in self._extra_stat_labels.values())

        for labels, none_text in label_groups:
            for name, (value_label, stat_id) in labels.items():
                if stat_id is None:
                    value_label.setText(none_text)
                    continue
                value = totals.get(stat_id, 0.0)
                suffix = "%" if stat_id in _PERCENT_STAT_IDS else ""
                value_label.setText(f"{_format_number(value)}{suffix}")

    # ── Left/right equipment columns (Weapon+Armor left, Accessory right) ──

    def _build_slot_sections(self, sections: list[tuple]) -> QVBoxLayout:
        col = QVBoxLayout()
        slot_lookup = {slot_id: (_t(label), categories) for slot_id, label, categories in SLOT_LAYOUT}

        for section_name, slot_ids in sections:
            section_title = QLabel(_t(section_name))
            section_title.setObjectName("EquipSectionLabel")
            col.addWidget(section_title)

            grid = QGridLayout()
            grid.setSpacing(10)
            for i, slot_id in enumerate(slot_ids):
                label, _categories = slot_lookup[slot_id]
                row, col_idx = divmod(i, 2)

                icon_btn = QToolButton()
                icon_btn.setObjectName("SlotIconButton")
                icon_btn.setFixedSize(SLOT_BUTTON_SIZE, SLOT_BUTTON_SIZE)
                icon_btn.setIconSize(QSize(48, 48))
                icon_btn.setToolTip(_t("arm_slot_empty_tooltip", label=label))
                icon_btn.setCursor(Qt.PointingHandCursor)
                icon_btn.clicked.connect(lambda _c=False, s=slot_id: self._select_equip_slot(s))
                placeholder = _EQUIPMENT_SLOT_PLACEHOLDER.get(slot_id)
                if placeholder:
                    icon = _placeholder_icon("equipment", placeholder)
                    if icon:
                        icon_btn.setIcon(icon)
                self._slot_icon_buttons[slot_id] = icon_btn

                # Replaces the old per-slot "change item" button: clicking
                # the icon already opens the inline Equipment Item panel
                # (dropdown to change the item, enchant slider, stats), so a
                # second button here was pure duplication. This space is
                # reused to show the enchant level as plain text instead --
                # no background needed since it sits on the app's own panel
                # background rather than on top of arbitrary icon artwork.
                enchant_label = QLabel()
                enchant_label.setObjectName("SlotEnchantLabel")
                enchant_label.setFixedWidth(SLOT_BUTTON_SIZE)
                enchant_label.setAlignment(Qt.AlignCenter)
                enchant_label.setStyleSheet(f"color: {ENCHANT_ACCENT_BY_THEME[self._theme]};")
                self._slot_enchant_labels[slot_id] = enchant_label

                cell = QWidget()
                cell_layout = QVBoxLayout(cell)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                cell_layout.setSpacing(2)
                cell_layout.addWidget(icon_btn)
                cell_layout.addWidget(enchant_label)
                grid.addWidget(cell, row, col_idx)

            col.addLayout(grid)
            col.addSpacing(8)

        return col

    def _build_weapon_armor_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        title = QLabel(_t("arm_equipment_btn"))
        title.setObjectName("DetailHeader")
        col.addWidget(title)
        col.addLayout(self._build_slot_sections(_LEFT_EQUIP_SECTIONS))
        col.addStretch()
        return col

    def _build_accessory_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        title = QLabel(_t("arm_jewelry_label"))
        title.setObjectName("DetailHeader")
        col.addWidget(title)
        col.addLayout(self._build_slot_sections(_RIGHT_EQUIP_SECTIONS))
        col.addStretch()

        gear_row = QHBoxLayout()
        gear_row.addStretch()
        settings_btn = QToolButton()
        settings_btn.setObjectName("SlotIconButton")
        settings_btn.setText("⚙")
        settings_btn.setFixedSize(40, 40)
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.clicked.connect(self._open_character_settings)
        gear_row.addWidget(settings_btn)
        col.addLayout(gear_row)

        # Character identity lives in a popup now (see _open_character_settings)
        # rather than a persistent card, to make room for the Stat Info column.
        self.character_name_input = QLineEdit()
        self.character_class_combo = QComboBox()
        self.character_race_combo = QComboBox()
        self.character_race_combo.addItems(AION2_RACES)
        self.gearscore_label = QLabel(_t("arm_gearscore_zero"))

        return col

    def _on_any_class_combo_changed(self, index: int):
        sender = self.sender()
        for combo in self._class_combos:
            if combo is not sender and combo.currentIndex() != index:
                combo.blockSignals(True)
                combo.setCurrentIndex(index)
                combo.blockSignals(False)

        new_class = self.character_class_combo.currentText().strip().lower()
        if self._active_skill_class is not None and self._active_skill_class != new_class:
            self._save_current_build_state(self._active_skill_class)
            self._save_current_equip_build_state(self._active_skill_class)
        self._active_skill_class = new_class

        self._refresh_skill_description_view()
        self._rebuild_skill_build_tabs()
        self._load_current_build_state()
        self._rebuild_equip_build_tabs()
        self._load_current_equip_build_state()

    def _open_character_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(_t("arm_character_title"))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.character_name_input.setPlaceholderText(_t("arm_character_name_placeholder"))
        layout.addWidget(QLabel(_t("arm_name_label")))
        layout.addWidget(self.character_name_input)

        layout.addWidget(QLabel(_t("arm_class_label")))
        layout.addWidget(self.character_class_combo)

        layout.addWidget(QLabel(_t("arm_race_label")))
        layout.addWidget(self.character_race_combo)

        self.gearscore_label.setObjectName("DetailHeader")
        self.gearscore_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.gearscore_label)
        gearscore_hint = QLabel(_t("arm_gearscore_note"))
        gearscore_hint.setObjectName("DetailDisclaimer")
        gearscore_hint.setAlignment(Qt.AlignCenter)
        gearscore_hint.setWordWrap(True)
        layout.addWidget(gearscore_hint)

        close_btn = QPushButton(_t("arm_close"))
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _capture_current_substats(self):
        """Saves whichever substats are checked and whatever enchant level
        is set in the inline detail panel against the slot it's showing,
        before switching away to show a different slot (there's no popup
        'close' anymore to hook this capture onto)."""
        prev_slot = self._selected_equip_slot_id
        if prev_slot and prev_slot in self._equipped:
            self._equipped_substats[prev_slot] = self.equip_detail_widget.get_selected_substat_indices()
            self._equipped_enchant[prev_slot] = self.equip_detail_widget.get_enchant_level()
            self._refresh_stat_info()
            self._update_gearscore()
            self._update_slot_enchant_label(prev_slot)

    def _update_slot_enchant_label(self, slot_id: str):
        """Shows the equipped item's enchant level as plain text under its
        slot icon (User-Wunsch: reuses the space the old per-slot "change
        item" button used to take up, now that clicking the icon itself
        already opens the inline Equipment Item panel to change items/
        enchant -- so no separate button, and no icon-badge background,
        are needed anymore)."""
        label = self._slot_enchant_labels.get(slot_id)
        if not label:
            return
        level = self._equipped_enchant.get(slot_id, 0) if slot_id in self._equipped else 0
        label.setText(f"+{level}" if level else "")

    def set_theme(self, theme: str):
        """Follows the app's Layout theme (User-Wunsch, 2026-08-26) -- the
        enchant labels' accent color and the window's own background color
        switch with it instead of staying fixed to Abyss."""
        self._theme = theme if theme in ENCHANT_ACCENT_BY_THEME else "abyss"
        accent = ENCHANT_ACCENT_BY_THEME[self._theme]
        for label in self._slot_enchant_labels.values():
            label.setStyleSheet(f"color: {accent};")

        # LoadoutBackground is a flat panel color (not the diagonal gradient
        # the main table window/ItemDatabaseWindow uses) -- kept flat here,
        # just swapped to each theme's own base tone (its gradient's first
        # stop, e.g. Abyss's own "#0f172a" this already used before).
        central = self.centralWidget()
        if central is not None:
            bg_color = LAYOUT_THEMES.get(self._theme, LAYOUT_THEMES["abyss"])[0]
            central.setStyleSheet(f"#LoadoutBackground {{ background-color: {bg_color}; }}")

    def update_language(self, language: str):
        """Forwarded by ItemDatabaseWindow.update_language() (see there).
        Re-applies text to this window's always-visible top-level chrome --
        deeply nested/dynamically-rebuilt content (tables, popups, per-slot
        labels) picks up the new language naturally the next time it's
        rebuilt (e.g. switching Sets/slots), since every build path already
        reads through _t() at call time. Reopening the Build Planner always
        guarantees a fully up-to-date language throughout."""
        set_armory_language(language)
        self.setWindowTitle(_t("arm_equip_character_title"))
        self.quick_gear_btn.setText(_t("arm_equipment_btn"))
        self.quick_stat_btn.setText(_t("arm_properties_btn"))
        self.stat_priority_edit_btn.setToolTip(_t("arm_stat_priority_editor_title"))
        self.main_tabs.setTabText(0, _t("arm_equipment_btn"))
        self.main_tabs.setTabText(1, _t("arm_eq_priority_tab"))
        self.main_tabs.setTabText(2, _t("arm_arcana_tab"))
        self.main_tabs.setTabText(3, _t("arm_skill_planner_tab"))

    # ── Saved equipment sets (per class): named tabs holding one full
    # equipped-gear snapshot each, e.g. "Default" / "PvP" / "PvE" — same
    # idea and UI as the Skill Planner's saved builds (see
    # _rebuild_skill_build_tabs), session-only for now, not yet persisted
    # to disk. ────────────────────────────────────────────────────────────

    def _empty_equip_build_state(self) -> dict:
        return {"equipped": {}, "substats": {}, "enchant": {}}

    def _ensure_class_equip_builds(self, class_name: str):
        if class_name not in self._equip_builds_data:
            self._equip_builds_data[class_name] = {"Default": self._empty_equip_build_state()}

    def _save_current_equip_build_state(self, class_name: str):
        self._ensure_class_equip_builds(class_name)
        builds = self._equip_builds_data[class_name]
        if self._current_equip_build_name not in builds:
            return
        self._capture_current_substats()
        builds[self._current_equip_build_name] = {
            "equipped": dict(self._equipped),
            "substats": {k: set(v) for k, v in self._equipped_substats.items()},
            "enchant": dict(self._equipped_enchant),
        }

    def _load_current_equip_build_state(self):
        class_name = self.character_class_combo.currentText().strip().lower()
        self._ensure_class_equip_builds(class_name)
        builds = self._equip_builds_data[class_name]
        if self._current_equip_build_name not in builds:
            self._current_equip_build_name = next(iter(builds))
        state = builds[self._current_equip_build_name]

        self._equipped = dict(state["equipped"])
        self._equipped_substats = {k: set(v) for k, v in state["substats"].items()}
        self._equipped_enchant = dict(state["enchant"])
        self._selected_equip_slot_id = None
        self.equip_center_stack.setCurrentIndex(0)
        self._refresh_all_equip_slot_icons()
        self._update_gearscore()
        self._refresh_stat_info()
        self._update_quick_stat_btn_visibility()

    # ── Profile persistence (User-Wunsch, 2026-08-25: "die Informationen
    # vom Buildplanner im Profil gespeichert werden") -- first step, scoped
    # to equipment + class/race only (saved builds/priority lists come
    # later, per the user's own choice). Called by ItemDatabaseWindow's
    # get_loadout_state/set_pending_loadout_state, which bridge this
    # otherwise-isolated module to the host app's profile save/load. ──────

    def get_persistable_state(self) -> dict:
        # Capture whatever's CURRENTLY equipped into _equip_builds_data
        # first -- that dict only reflects the last explicit save
        # (_save_current_equip_build_state), not necessarily what's live.
        self._save_current_equip_build_state(self.character_class_combo.currentText().strip().lower())
        return {
            "character_class": self.character_class_combo.currentText(),
            "character_race": self.character_race_combo.currentText(),
            "current_build_name": self._current_equip_build_name,
            # User-Wunsch, 2026-08-26: "Speicher bitte die Buttons wie sie
            # zuletzt gesetzt wurden auch im Profil" -- the global PvP/PvE/
            # Neutral item-picker filter (see the "Klasse" row above).
            "active_gear_types": sorted(self._active_gear_types),
            # User-Wunsch, 2026-08-27: "die Werte Zuordnung ... anpassbar
            # durch den Spieler und dann im Profil gespeichert".
            "stat_priority_profiles": self._stat_priority_profiles,
            "equip_builds_data": {
                class_name: {
                    build_name: {
                        "equipped": build["equipped"],
                        "substats": {k: list(v) for k, v in build["substats"].items()},
                        "enchant": build["enchant"],
                    }
                    for build_name, build in builds.items()
                }
                for class_name, builds in self._equip_builds_data.items()
            },
        }

    def apply_persisted_state(self, state: dict):
        self._equip_builds_data = {
            class_name: {
                build_name: {
                    "equipped": build.get("equipped", {}),
                    "substats": {k: set(v) for k, v in build.get("substats", {}).items()},
                    "enchant": build.get("enchant", {}),
                }
                for build_name, build in builds.items()
            }
            for class_name, builds in state.get("equip_builds_data", {}).items()
        }
        self._current_equip_build_name = state.get("current_build_name", "Default")

        # blockSignals so this doesn't trigger _on_any_class_combo_changed's
        # own "save the OLD class's state first" side effect, which would
        # immediately overwrite the data we just restored above with
        # whatever the (empty, freshly-constructed) window had before.
        saved_class = state.get("character_class")
        if saved_class:
            for combo in self._class_combos:
                idx = combo.findText(saved_class)
                if idx >= 0:
                    combo.blockSignals(True)
                    combo.setCurrentIndex(idx)
                    combo.blockSignals(False)

        saved_race = state.get("character_race")
        if saved_race:
            idx = self.character_race_combo.findText(saved_race)
            if idx >= 0:
                self.character_race_combo.setCurrentIndex(idx)

        self._active_skill_class = self.character_class_combo.currentText().strip().lower()
        self._rebuild_equip_build_tabs()
        self._load_current_equip_build_state()

        # "active_gear_types" only exists in profiles saved after this
        # feature was added -- an older/missing key keeps the PvE+Neutral
        # default set at construction time rather than clearing it.
        if "active_gear_types" in state:
            self._active_gear_types = set(state["active_gear_types"])
            for key, btn in self._gear_type_buttons.items():
                btn.blockSignals(True)
                btn.setChecked(key in self._active_gear_types)
                btn.blockSignals(False)

        # _merge_stat_priority_profiles fills in any gear_type/role/category
        # missing from an older or partial profile with the default, rather
        # than leaving _pick_priority_substats with an empty list for it.
        self._stat_priority_profiles = _merge_stat_priority_profiles(state.get("stat_priority_profiles"))

    def _refresh_all_equip_slot_icons(self):
        """Re-applies every slot button's icon/tooltip from self._equipped —
        needed after switching Sets, since icons are otherwise only ever set
        one slot at a time (on equip/clear), never all at once."""
        for slot_id, icon_btn in self._slot_icon_buttons.items():
            label, _ = self._slot_info(slot_id)
            item = self._equipped.get(slot_id)
            if item is None:
                icon_btn.setToolTip(_t("arm_slot_empty_tooltip", label=label))
                placeholder = _EQUIPMENT_SLOT_PLACEHOLDER.get(slot_id)
                icon = _placeholder_icon("equipment", placeholder) if placeholder else None
                icon_btn.setIcon(icon or QIcon())
                self._update_slot_enchant_label(slot_id)
                continue
            icon_btn.setToolTip(item.get("name", ""))
            image_url = item.get("image", "")
            cached_icon = self.icon_cache.pixmap(image_url, 48, grade=item.get("grade"))
            if cached_icon:
                icon_btn.setIcon(QIcon(cached_icon))
            else:
                icon_btn.setIcon(QIcon())
                self.icon_cache.request(image_url)
            self._update_slot_enchant_label(slot_id)
            self.detail_cache.request(item.get("id"))

    def _rebuild_equip_build_tabs(self):
        _clear_layout(self.equip_build_tabs_row)
        class_name = self.character_class_combo.currentText().strip().lower()
        self._ensure_class_equip_builds(class_name)
        builds = self._equip_builds_data[class_name]
        if self._current_equip_build_name not in builds:
            self._current_equip_build_name = next(iter(builds))

        self._equip_build_tab_group = QButtonGroup(self)
        self._equip_build_tab_group.setExclusive(True)
        for build_name in builds:
            btn = _BuildTabButton(build_name)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(build_name == self._current_equip_build_name)
            btn.setMinimumHeight(32)
            btn.clicked.connect(lambda checked=False, bn=build_name: self._on_switch_equip_build(bn))
            btn.doubleClicked.connect(lambda bn=build_name: self._on_rename_equip_build(bn))
            btn.setToolTip(_t("arm_rename_hint"))
            self._equip_build_tab_group.addButton(btn)
            self.equip_build_tabs_row.addWidget(btn)

        add_btn = QPushButton()
        add_btn.setIcon(_make_plus_icon())
        add_btn.setIconSize(QSize(20, 20))
        add_btn.setFixedSize(40, 32)
        add_btn.setToolTip(_t("arm_add_new_set"))
        add_btn.clicked.connect(self._on_add_equip_build)
        self.equip_build_tabs_row.addWidget(add_btn)

        rename_btn = QPushButton()
        rename_btn.setIcon(_make_edit_icon())
        rename_btn.setIconSize(QSize(20, 20))
        rename_btn.setFixedSize(40, 32)
        rename_btn.setToolTip(_t("arm_rename_current_set"))
        rename_btn.clicked.connect(lambda checked=False: self._on_rename_equip_build(self._current_equip_build_name))
        self.equip_build_tabs_row.addWidget(rename_btn)

        save_btn = QPushButton()
        save_btn.setIcon(_make_save_icon())
        save_btn.setIconSize(QSize(20, 20))
        save_btn.setFixedSize(40, 32)
        save_btn.setToolTip(_t("arm_save_current_set"))
        save_btn.clicked.connect(self._on_save_current_equip_build)
        self.equip_build_tabs_row.addWidget(save_btn)

    def _on_save_current_equip_build(self):
        class_name = self.character_class_combo.currentText().strip().lower()
        self._save_current_equip_build_state(class_name)

    def _on_switch_equip_build(self, build_name: str):
        if build_name == self._current_equip_build_name:
            return
        class_name = self.character_class_combo.currentText().strip().lower()
        self._save_current_equip_build_state(class_name)
        self._current_equip_build_name = build_name
        self._rebuild_equip_build_tabs()
        self._load_current_equip_build_state()

    def _on_add_equip_build(self):
        name, ok = QInputDialog.getText(self, _t("arm_new_set_title"), _t("arm_name_colon"))
        name = name.strip()
        if not ok or not name:
            return
        class_name = self.character_class_combo.currentText().strip().lower()
        self._ensure_class_equip_builds(class_name)
        builds = self._equip_builds_data[class_name]
        if name in builds:
            return
        self._save_current_equip_build_state(class_name)
        builds[name] = self._empty_equip_build_state()
        self._current_equip_build_name = name
        self._rebuild_equip_build_tabs()
        self._load_current_equip_build_state()

    def _on_rename_equip_build(self, old_name: str):
        new_name, ok = QInputDialog.getText(self, _t("arm_rename_set_title"), _t("arm_name_colon"), text=old_name)
        new_name = new_name.strip()
        if not ok or not new_name or new_name == old_name:
            return
        class_name = self.character_class_combo.currentText().strip().lower()
        builds = self._equip_builds_data[class_name]
        if new_name in builds:
            return
        builds[new_name] = builds.pop(old_name)
        if self._current_equip_build_name == old_name:
            self._current_equip_build_name = new_name
        self._rebuild_equip_build_tabs()

    def _on_gear_type_toggled(self, key: str, checked: bool):
        if checked:
            other = {"PvP": "PvE", "PvE": "PvP"}.get(key)
            if other and self._gear_type_buttons[other].isChecked():
                self._gear_type_buttons[other].setChecked(False)
            # One-way sync: picking PvP/PvE up here also sets the Stat Info
            # panel's own PvE/PvP mode switch to match, once — the user can
            # then flip that lower switch freely afterwards without it
            # fighting back or re-syncing from this filter again.
            if key in ("PvP", "PvE"):
                self._set_stat_info_mode(key.lower())
                target_btn = self._stat_mode_pvp_btn if key == "PvP" else self._stat_mode_pve_btn
                target_btn.blockSignals(True)
                target_btn.setChecked(True)
                target_btn.blockSignals(False)
        self._active_gear_types = {k for k, b in self._gear_type_buttons.items() if b.isChecked()}

    def _pick_for_slot(self, slot_id: str, categories: list[str], anchor: QWidget):
        if slot_id == "MainHand":
            selected_class = self.character_class_combo.currentText()
            weapon_category = CLASS_WEAPON_CATEGORY.get(selected_class)
            if weapon_category:
                categories = [weapon_category]

        popup = ItemPickerPopup(
            self._items, categories, self.icon_cache, self.detail_cache, self,
            active_gear_types=self._active_gear_types,
        )
        popup.item_chosen.connect(lambda item, s=slot_id: self._on_item_chosen_for_slot(s, item))
        # Kept alive via this reference — a Qt.Popup with no other owner
        # would otherwise get garbage-collected before it can emit.
        self._active_picker_popup = popup
        popup.show_anchored(anchor)

    def _open_quick_gear_select(self):
        character_class = self.character_class_combo.currentText()
        dlg = QuickGearSelectDialog(
            self._items_by_id, character_class, self.detail_cache,
            active_gear_types=self._active_gear_types, parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        for slot_id, item in dlg.result_slots.items():
            self._on_item_chosen_for_slot(slot_id, item)
            # _on_item_chosen_for_slot itself resets enchant to none on
            # equip, so the target level from the dialog must be applied
            # after it, not before.
            enchant = dlg.result_enchant.get(slot_id, 0)
            if enchant:
                self._equipped_enchant[slot_id] = enchant
                # Real bug found here (User: "wenn man Items automatisch
                # ausrüstet ... wurde laut Profil nur das letzte Item
                # enhanced"): _on_item_chosen_for_slot's own
                # _capture_current_substats() call, on the NEXT loop
                # iteration, reads whatever the SHARED equip_detail_widget's
                # slider is CURRENTLY showing for the PREVIOUSLY selected
                # slot and overwrites _equipped_enchant with it -- but we
                # only just set that dict entry directly above, without
                # ever telling the actual slider widget about it (which
                # still shows its freshly-equipped default of 0). The next
                # slot's equip then stomps this slot's real value back to 0.
                # Keeping the widget in sync here (only possible right now,
                # since _on_item_chosen_for_slot above just made slot_id
                # the selected/displayed one) closes that gap.
                if self._selected_equip_slot_id == slot_id:
                    self.equip_detail_widget.enchant_slider.setValue(enchant)
                self._update_slot_enchant_label(slot_id)
        if dlg.result_enchant:
            self._update_gearscore()
            self._refresh_stat_info()
            if self._selected_equip_slot_id in dlg.result_slots:
                self._refresh_equip_item_panel()

        if dlg.missing_slots:
            QMessageBox.information(
                self, _t("arm_quick_select_result_title"),
                _t("arm_quick_select_equipped_result", count=len(dlg.result_slots), missing=', '.join(dlg.missing_slots)),
            )

    def _open_quick_stat_select(self):
        dlg = QuickStatSelectDialog(set(self._equipped.keys()), parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        message = self._apply_quick_substats(dlg.stat_target_slots, dlg.selected_gear_type, dlg.selected_role)
        if message:
            QMessageBox.information(self, _t("arm_quick_select_result_title"), message)

    def _open_stat_priority_editor(self):
        dlg = StatPriorityEditorDialog(self._stat_priority_profiles, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.result_profiles is not None:
            self._stat_priority_profiles = dlg.result_profiles

    def _apply_quick_substats(self, target_slots: set[str], gear_type: str = "PvE", role: str = "Angreifer") -> str:
        """Auto-locks each targeted slot's substats using the selected
        Gear-Typ/Rolle priority profile (_pick_priority_substats) -- applies
        to whatever is CURRENTLY equipped in that slot (freshly equipped
        this run or already there before), independent of the Equipment
        page's own slot selection, since the two accordions are separate
        settings."""
        if not target_slots:
            return ""
        profile = self._stat_priority_profiles.get(gear_type, {}).get(role, {})
        applied, pending, skipped = [], [], []
        for slot_id in target_slots:
            item = self._equipped.get(slot_id)
            if not item:
                skipped.append(slot_id)
                continue
            detail = self.detail_cache.get(item["id"])
            if not detail:
                # Not cached yet -- request it now so a retry works, but
                # can't pick substats without knowing the real options.
                self.detail_cache.request(item["id"])
                pending.append(slot_id)
                continue
            sub_stats = detail.get("subStats") or []
            count = int(detail.get("subStatCount") or 0)
            if not sub_stats or not count:
                skipped.append(slot_id)
                continue
            category = _SLOT_TO_STAT_CATEGORY.get(slot_id)
            priority_names = profile.get(category, []) if category else []
            chosen = _pick_priority_substats(sub_stats, count, priority_names)
            if chosen:
                self._equipped_substats[slot_id] = chosen
                applied.append(slot_id)
            else:
                skipped.append(slot_id)

        if applied and self._selected_equip_slot_id in applied:
            self._refresh_equip_item_panel()

        parts = []
        if applied:
            parts.append(_t("arm_substats_auto_set", slots=', '.join(applied)))
        if pending:
            parts.append(_t("arm_details_not_loaded", slots=', '.join(pending)))
        return " ".join(parts)

    def _on_item_chosen_for_slot(self, slot_id: str, item: dict):
        self._capture_current_substats()
        self._equipped[slot_id] = item
        self._equipped_substats.pop(slot_id, None)
        self._equipped_enchant.pop(slot_id, None)
        icon_btn = self._slot_icon_buttons[slot_id]
        icon_btn.setToolTip(item.get("name", ""))
        image_url = item.get("image", "")
        cached_icon = self.icon_cache.pixmap(image_url, 48, grade=item.get("grade"))
        if cached_icon:
            icon_btn.setIcon(QIcon(cached_icon))
        else:
            self.icon_cache.request(image_url)
        self._update_slot_enchant_label(slot_id)
        self.detail_cache.request(item.get("id"))
        self._update_gearscore()
        self._refresh_stat_info()
        self._update_quick_stat_btn_visibility()

        if slot_id in _EQUIP_SLOT_IDS:
            self._selected_equip_slot_id = slot_id
            self.equip_center_stack.setCurrentIndex(1)
            self._refresh_equip_item_panel()

    def _update_quick_stat_btn_visibility(self):
        """The Eigenschaften Schnellauswahl has nothing to act on with no
        gear equipped at all -- hidden until at least one slot has an item
        (user request)."""
        self.quick_stat_btn.setVisible(bool(self._equipped))

    def _select_equip_slot(self, slot_id: str):
        """Click on a slot's icon (whether equipped or empty) = show it in
        the inline 'Equipment Item' panel (dropdown+clear, icon+title,
        enchant slider, item stats) instead of a popup."""
        self._capture_current_substats()
        self._selected_equip_slot_id = slot_id
        self.equip_center_stack.setCurrentIndex(1)
        self._refresh_equip_item_panel()

    def _update_gearscore(self):
        total = 0.0
        for slot_id, item in self._equipped.items():
            detail = self.detail_cache.get(item.get("id"))
            if not detail or not detail.get("level"):
                continue
            total += detail["level"]

            level = self._equipped_enchant.get(slot_id, 0)
            if not level:
                continue
            normal_max = int(detail.get("maxEnchantLevel") or 0)
            total += _gearscore_push(level, normal_max)

        text = f"GearScore: {_format_number(total)}"
        self.gearscore_label.setText(text)
        self._stat_gearscore_label.setText(text)

    def _on_icon_ready(self, url: str):
        for slot_id, item in self._equipped.items():
            if item.get("image") == url:
                pix = self.icon_cache.pixmap(url, 48, grade=item.get("grade"))
                if pix:
                    self._slot_icon_buttons[slot_id].setIcon(QIcon(pix))
        current_item = self._equipped.get(self._selected_equip_slot_id)
        if current_item and current_item.get("image") == url:
            pix = self.icon_cache.pixmap(url, 32, grade=current_item.get("grade"))
            if pix:
                self.equip_item_icon_label.setPixmap(pix)

    def _on_detail_ready(self, item_id: int):
        if any(item.get("id") == item_id for item in self._equipped.values()):
            self._refresh_stat_info()
            self._update_gearscore()

    def closeEvent(self, event):
        logger.debug("LoadoutWindow (Build Planner) closed")
        super().closeEvent(event)


class ItemTableView(QTableView):
    """QTableView with a rich, async-loaded tooltip on the Name column."""

    def __init__(self, window: "ItemDatabaseWindow", parent=None):
        super().__init__(parent)
        self._window = window

    def viewportEvent(self, event):
        if event.type() == QEvent.ToolTip:
            index = self.indexAt(event.pos())
            if index.isValid() and index.column() == NAME_COLUMN:
                if self._window.show_item_tooltip(index, event.globalPos()):
                    return True
        return super().viewportEvent(event)


class ItemFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_text = ""
        self.grade_filter = "All"
        self.class_filter = "All"
        self.gear_type_filter: set[str] = set()
        # Two-level category scoping (sidebar + Category dropdown, see
        # _ITEM_TOP_CATEGORIES/_GEAR_SUBGROUPS): group_categories narrows to
        # the currently-selected sidebar group's raw categoryName values
        # (None = no sidebar group selected, i.e. every category);
        # subcategory_categories further narrows within that group to the
        # Category dropdown's current selection (None = "All", i.e. the
        # whole group). Kept as sets rather than a single string because
        # "Gear" needs one dropdown entry ("Weapons") to match MANY raw
        # categoryName values at once.
        self.group_categories: set[str] | None = None
        self.subcategory_categories: set[str] | None = None
        # Wings-only stat filters (User-Wunsch) -- replace the Category/
        # Class dropdowns when the "Wings" sidebar group is active. None
        # means unfiltered ("All"); see _parse_wing_effects for where the
        # per-row stat-name sets come from.
        self.wing_equip_filter: str | None = None
        self.wing_owned_filter: str | None = None
        self.setSortRole(Qt.EditRole)

    def set_search(self, text: str):
        self.search_text = text.strip().lower()
        self.invalidateFilter()

    def set_grade(self, grade: str):
        self.grade_filter = grade
        self.invalidateFilter()

    def set_group_categories(self, categories: set | None):
        self.group_categories = categories
        self.invalidateFilter()

    def set_subcategory_categories(self, categories: set | None):
        self.subcategory_categories = categories
        self.invalidateFilter()

    def set_class(self, class_name: str):
        self.class_filter = class_name
        self.invalidateFilter()

    def set_gear_types(self, types: set):
        self.gear_type_filter = types
        self.invalidateFilter()

    def set_wing_equip_filter(self, stat_name: str | None):
        self.wing_equip_filter = stat_name
        self.invalidateFilter()

    def set_wing_owned_filter(self, stat_name: str | None):
        self.wing_owned_filter = stat_name
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()

        if self.search_text:
            name = model.index(source_row, 2, source_parent).data(Qt.DisplayRole) or ""
            if self.search_text not in name.lower():
                return False

        if self.grade_filter != "All":
            grade = model.index(source_row, 3, source_parent).data(Qt.DisplayRole) or ""
            if grade != self.grade_filter:
                return False

        if self.group_categories is not None or self.subcategory_categories is not None:
            category = model.index(source_row, 4, source_parent).data(Qt.DisplayRole) or ""
            if self.group_categories is not None and category not in self.group_categories:
                return False
            if self.subcategory_categories is not None and category not in self.subcategory_categories:
                return False

        if self.class_filter != "All":
            classes = model.index(source_row, 5, source_parent).data(Qt.DisplayRole) or ""
            if self.class_filter not in [c.strip() for c in classes.split(",")]:
                return False

        if self.gear_type_filter:
            gear_type = model.index(source_row, GEAR_TYPE_COLUMN, source_parent).data(Qt.DisplayRole) or ""
            if gear_type not in self.gear_type_filter:
                return False

        if self.wing_equip_filter:
            stats = model.index(source_row, ID_COLUMN, source_parent).data(WING_EQUIP_STATS_ROLE) or set()
            if self.wing_equip_filter not in stats:
                return False

        if self.wing_owned_filter:
            stats = model.index(source_row, ID_COLUMN, source_parent).data(WING_OWNED_STATS_ROLE) or set()
            if self.wing_owned_filter not in stats:
                return False

        return True


class _ComboPopupFilter(QObject):
    """Installed on a label-combo's read-only lineEdit (see
    _make_label_combo). A read-only QLineEdit inside an editable QComboBox
    does NOT forward a plain click to QComboBox.showPopup() the way a
    normal non-editable combo's whole body does -- only its tiny
    ::drop-down arrow subcontrol does, and that hit region can end up
    misaligned with (or hidden behind) a custom-styled arrow depending on
    the active native QStyle (confirmed real bug: User reported the arrow
    now renders, but clicking the field opens nothing). Forcing
    showPopup() on any mouse press on the field sidesteps the whole
    subcontrol-hit-region question entirely."""

    def __init__(self, combo: QComboBox):
        super().__init__(combo)
        self._combo = combo

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            self._combo.showPopup()
            return True
        return super().eventFilter(obj, event)


class ItemDatabaseWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle(_t("arm_item_database_title"))
        self.resize(1400, 800)

        self.background = GradientBackground()
        self.setCentralWidget(self.background)

        outer = QVBoxLayout(self.background)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(14)

        header_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel(_t("arm_item_database_header"))
        title.setObjectName("PageTitle")
        subtitle = QLabel(_t("arm_item_database_subtitle"))
        subtitle.setObjectName("PageSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header_row.addLayout(title_col)
        header_row.addStretch()

        self.loadout_btn = QPushButton(_t("arm_equip_character_btn"))
        self.loadout_btn.clicked.connect(self._open_loadout_window)
        header_row.addWidget(self.loadout_btn, 0, Qt.AlignTop)

        self.crafting_calc_btn = QPushButton(_t("arm_crafting_calculator_title"))
        self.crafting_calc_btn.clicked.connect(self._open_crafting_calculator)
        header_row.addWidget(self.crafting_calc_btn, 0, Qt.AlignTop)

        outer.addLayout(header_row)

        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 12, 16, 12)
        top_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_t("arm_search_by_name_placeholder"))
        self.search_input.textChanged.connect(self._on_search_changed)

        # Editable+read-only line edit so the collapsed field can show a
        # descriptive label ("Category"/"Class") instead of "All" -- "All"
        # itself only ever appears as a real, selectable row inside the
        # opened dropdown list (User-Wunsch: Label nur oben im Feld, "All"
        # nur unten in der Liste, nie beides gleichzeitig an derselben
        # Stelle). Real filter values are read via itemText(index), not the
        # (overridden) displayed text, so the label swap never leaks into
        # the actual filtering logic.
        self.category_combo = self._make_label_combo(_t("arm_filter_category"), self._on_category_changed)
        self.class_combo = self._make_label_combo(_t("arm_filter_class"), self._on_class_changed)

        # Wings-only replacements for Category/Class (User-Wunsch) -- Wings
        # items have no Category/Class distinction that matters (all share
        # the same 2 raw categories, no classNames), but DO have real
        # per-item stats only ever expressed as free text (see
        # _parse_wing_effects). These sit in the exact same two layout
        # slots as category_combo/class_combo and swap in only while the
        # sidebar's "Wings" group is active (see _on_sidebar_group_selected).
        self.wing_equip_combo = self._make_label_combo(_t("arm_filter_equip_effect"), self._on_wing_equip_changed)
        self.wing_owned_combo = self._make_label_combo(_t("arm_filter_owned_effect"), self._on_wing_owned_changed)
        self.wing_equip_combo.setVisible(False)
        self.wing_owned_combo.setVisible(False)

        top_layout.addWidget(self.search_input, 2)
        top_layout.addWidget(self.category_combo, 1)
        top_layout.addWidget(self.class_combo, 1)
        top_layout.addWidget(self.wing_equip_combo, 1)
        top_layout.addWidget(self.wing_owned_combo, 1)
        outer.addWidget(top_bar)

        # Grade/Rarity filter — checkable pill buttons instead of a dropdown
        # (User-Wunsch, referencing gamers4.life's own rarity-pill UI as an
        # example) — same exclusive-QButtonGroup + SkillFilterButton pattern
        # already used for CraftingItemPickerDialog's own rarity row, colored
        # per grade via GRADE_COLORS the same way.
        grade_row = QHBoxLayout()
        grade_label = QLabel(_t("arm_grade_label"))
        grade_label.setObjectName("EquipSectionLabel")
        grade_row.addWidget(grade_label)
        self.grade_buttons: dict[str, QPushButton] = {}
        grade_group = QButtonGroup(self)
        grade_group.setExclusive(True)

        all_grades_btn = QPushButton(_t("arm_all"))
        all_grades_btn.setObjectName("SkillFilterButton")
        all_grades_btn.setCheckable(True)
        all_grades_btn.setChecked(True)
        all_grades_btn.clicked.connect(lambda checked=False: self._on_grade_changed("All"))
        grade_group.addButton(all_grades_btn)
        grade_row.addWidget(all_grades_btn)
        self.grade_buttons["All"] = all_grades_btn

        for grade in RARITY_ORDER:
            btn = QPushButton(grade)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setStyleSheet(f"color: {GRADE_COLORS[grade]};")
            btn.clicked.connect(lambda checked=False, g=grade: self._on_grade_changed(g))
            grade_group.addButton(btn)
            grade_row.addWidget(btn)
            self.grade_buttons[grade] = btn

        grade_row.addStretch(1)
        self._grade_buttongroup = grade_group  # kept alive against GC
        outer.addLayout(grade_row)

        # PvP/PvE/Neutral gear-type filter — checkable pill buttons like the
        # Skill Planner's Active/Passive/Stigma filter, not a combo. Checking
        # PvP auto-hides PvE (and vice versa) since a build is normally
        # geared for one or the other; Neutral (Dungeon gear) stays
        # independent since it's relevant to both.
        type_row = QHBoxLayout()
        type_label = QLabel(_t("arm_pvp_pve_label"))
        type_label.setObjectName("EquipSectionLabel")
        type_row.addWidget(type_label)
        self.gear_type_buttons: dict[str, QPushButton] = {}
        for key in ("PvP", "PvE", "Neutral"):
            btn = QPushButton(key)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setMinimumSize(72, 32)
            btn.clicked.connect(lambda checked, k=key: self._on_gear_type_toggled(k, checked))
            type_row.addWidget(btn)
            self.gear_type_buttons[key] = btn
        type_row.addStretch()

        self.show_id_check = QCheckBox(_t("arm_show_item_id"))
        self.show_id_check.toggled.connect(self._on_show_id_toggled)
        type_row.addWidget(self.show_id_check)
        outer.addLayout(type_row)

        self.result_label = QLabel()
        self.result_label.setObjectName("ResultLabel")
        outer.addWidget(self.result_label)

        self.table = ItemTableView(self)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.table.setMouseTracking(True)
        self.table.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)

        # Right-hand category sidebar (User-Wunsch) -- one exclusive pill
        # per top-level group (_ITEM_TOP_CATEGORIES, "Gear" nesting
        # Weapons/Armor/Accessories/Wings underneath), same SkillFilterButton
        # look as everywhere else. Selecting one narrows the Category
        # dropdown above to just that group's own subcategories and scopes
        # the table's Category filter to the group's raw categoryName
        # values -- "All Categories" restores the original unscoped view.
        #
        # Sits only alongside the table (not the header/search/filter rows
        # above it, which stay full-width in `outer`) -- User-Feedback after
        # a first screenshot: running the sidebar the full window height
        # left it looking mostly empty and wasted horizontal space next to
        # the header and filter bar, which don't have anything to put there.
        sidebar = QFrame()
        sidebar.setObjectName("TopBar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(6)
        sidebar_title = QLabel(_t("arm_categories_label"))
        sidebar_title.setObjectName("EquipSectionLabel")
        sidebar_layout.addWidget(sidebar_title)

        self._category_group_buttons: dict[str, QPushButton] = {}
        category_group_buttongroup = QButtonGroup(self)
        category_group_buttongroup.setExclusive(True)

        all_categories_btn = QPushButton(_t("arm_all_categories"))
        all_categories_btn.setObjectName("SkillFilterButton")
        all_categories_btn.setCheckable(True)
        all_categories_btn.setChecked(True)
        all_categories_btn.clicked.connect(lambda checked=False: self._on_sidebar_group_selected(None))
        category_group_buttongroup.addButton(all_categories_btn)
        sidebar_layout.addWidget(all_categories_btn)
        self._category_group_buttons["All Categories"] = all_categories_btn

        for group_label, _raw_categories in _ITEM_TOP_CATEGORIES:
            # "&" in a QPushButton's text is parsed as a mnemonic marker (the
            # following character gets underlined) unless escaped as "&&" --
            # "Materials & Enhancement" and "Tools & Services" both have a
            # real "&", which rendered as a stray underline artifact (User:
            # "Unterstriche" in the sidebar). Escaping only the DISPLAYED
            # text -- group_label itself (used for lookups/comparisons
            # everywhere else, e.g. _on_sidebar_group_selected) stays the
            # real, un-escaped string.
            btn = QPushButton(group_label.replace("&", "&&"))
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, l=group_label: self._on_sidebar_group_selected(l))
            category_group_buttongroup.addButton(btn)
            sidebar_layout.addWidget(btn)
            self._category_group_buttons[group_label] = btn

        sidebar.setFixedWidth(180)
        self._category_group_buttongroup = category_group_buttongroup  # kept alive against GC

        # No sidebar group selected yet -- the Category dropdown still lists
        # every raw categoryName directly, exactly like before this feature.
        self._current_sidebar_group: str | None = None

        root_row = QHBoxLayout()
        root_row.setSpacing(14)
        root_row.addWidget(self.table, 1)
        # AlignTop keeps the frame's own height down to its buttons' natural
        # size instead of stretching (and painting its background) across
        # the table's full height, which is what made it look empty below.
        root_row.addWidget(sidebar, 0, Qt.AlignTop)
        outer.addLayout(root_row, 1)

        self.model = QStandardItemModel(0, len(COLUMNS), self)
        self.model.setHorizontalHeaderLabels([
            _t("arm_col_icon"), _t("arm_col_id"), _t("arm_col_name"), _t("arm_grade_label"),
            _t("arm_col_category"), _t("arm_col_classes"), _t("arm_col_tradable"), _t("arm_col_pvp_pve"),
        ])

        self.proxy = ItemFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy)
        self.table.setColumnHidden(ID_COLUMN, True)  # matches show_id_check's default unchecked state

        self.icon_cache = IconCache(ICON_CACHE_DIR, self)
        self.icon_cache.icon_ready.connect(self._on_icon_ready)
        self._icon_items_by_url: dict[str, list[QStandardItem]] = {}

        self.detail_cache = ItemDetailCache(DETAIL_CACHE_DIR, self)
        self.detail_cache.detail_ready.connect(self._on_detail_ready)
        self._pending_tooltip_id: int | None = None

        self.table.verticalScrollBar().valueChanged.connect(self._request_visible_icons)
        self.proxy.layoutChanged.connect(self._request_visible_icons)
        self.table.doubleClicked.connect(self._open_detail_popup)

        self._raw_items: list[dict] = []
        self._loadout_window: LoadoutWindow | None = None
        self._crafting_window: CraftingCalculatorWindow | None = None
        # Build Planner profile persistence (User-Wunsch, 2026-08-25) --
        # holds the last known state (equipment + class/race) whether or
        # not LoadoutWindow has been created yet this session; see
        # set_pending_loadout_state/get_loadout_state/open_loadout_window.
        self._pending_loadout_state: dict | None = None
        # App Layout theme (User-Wunsch, 2026-08-26) -- held here too since
        # LoadoutWindow is created lazily, same reasoning/pattern as
        # _pending_loadout_state above.
        self._theme = "abyss"

        self._load_items()
        QTimer.singleShot(0, self._request_visible_icons)

    def _open_detail_popup(self, index):
        source_index = self.proxy.mapToSource(index)
        id_item = self.model.item(source_index.row(), ID_COLUMN)
        icon_item = self.model.item(source_index.row(), 0)
        name_item = self.model.item(source_index.row(), NAME_COLUMN)
        if id_item is None or name_item is None:
            return
        item_id = id_item.data(Qt.EditRole)
        image_url = icon_item.data(Qt.UserRole) if icon_item else ""

        dialog = ItemDetailDialog(self.icon_cache, self.detail_cache, self)
        dialog.load_item(item_id, name_item.text(), image_url)
        dialog.show()

    def _open_loadout_window(self):
        self.open_loadout_window()

    def open_loadout_window(self):
        """Public entry point so a host app can jump straight to the Build
        Planner (the loadout/equip window) without showing the full item
        table first — this window's already-loaded item data and caches
        back the Build Planner either way.

        Opens straight into the Build Planner now — no CreateCharacterDialog
        gate ('Create Build'/'Create Character') beforehand; name/class/race
        can be set any time via the class combo in Skill Planner or the
        gear-icon settings popup. Both dialogs remain defined but unused."""
        if self._loadout_window is None:
            # No Qt parent on purpose: an owned top-level window on Windows
            # shares the owner's taskbar entry, and closing it can leave the
            # whole app looking "minimized" until something restores focus.
            # This window's lifetime is already managed explicitly via this
            # singleton attribute, not by Qt parent-child ownership. Since it
            # no longer has a parent, it also no longer inherits this
            # window's stylesheet automatically — apply it explicitly.
            self._loadout_window = LoadoutWindow(self._raw_items, self.icon_cache, self.detail_cache, None)
            self._loadout_window.setStyleSheet(_load_qss_text())
            self._loadout_window.set_theme(self._theme)
            if self._pending_loadout_state:
                self._loadout_window.apply_persisted_state(self._pending_loadout_state)
        self._loadout_window.show()
        self._loadout_window.raise_()
        self._loadout_window.activateWindow()

    def set_pending_loadout_state(self, state: dict | None):
        """Called by the host app (MainWindow) right after this window is
        created (profile already loaded by then) and again whenever the
        profile changes while this window is already open. Applied
        immediately if LoadoutWindow already exists; otherwise just kept
        until open_loadout_window() actually creates it."""
        self._pending_loadout_state = state
        if self._loadout_window is not None and state:
            self._loadout_window.apply_persisted_state(state)

    def set_theme(self, theme: str):
        """Forwarded by the host app (MainWindow) whenever the Layout theme
        changes, and once right after this window is created -- applied
        immediately if LoadoutWindow already exists; otherwise just kept
        until open_loadout_window() actually creates it (same pattern as
        set_pending_loadout_state)."""
        self._theme = theme
        if hasattr(self, "background"):
            self.background.set_theme(theme)
        if self._loadout_window is not None:
            self._loadout_window.set_theme(theme)

    def update_language(self, language: str):
        """Forwarded by the host app (MainWindow.apply_language()) whenever
        the profile language changes, and once right after this window is
        created (same pattern as set_theme). Sets the module-wide current
        Armory language (see set_armory_language) and re-applies text to
        this window's own static widgets, then forwards to the Build
        Planner/Crafting Calculator windows if already open. A window not
        yet open just picks up the new language naturally when it's built,
        same as set_pending_loadout_state/set_theme."""
        set_armory_language(language)
        self._retranslate_ui()
        if self._loadout_window is not None:
            self._loadout_window.update_language(language)
        if self._crafting_window is not None:
            self._crafting_window.update_language(language)

    def _retranslate_ui(self):
        """Re-applies text to this window's always-visible top-level chrome
        -- the main table's rows/dynamic filter combo contents pick up the
        new language naturally the next time they're rebuilt (_load_items/
        _populate_filter_combo already read through _t() at call time where
        applicable). Reopening the window always guarantees a fully
        up-to-date language throughout, same caveat as LoadoutWindow's own
        update_language()."""
        self.setWindowTitle(_t("arm_item_database_title"))
        self.loadout_btn.setText(_t("arm_equip_character_btn"))
        self.crafting_calc_btn.setText(_t("arm_crafting_calculator_title"))
        self.search_input.setPlaceholderText(_t("arm_search_by_name_placeholder"))
        self.show_id_check.setText(_t("arm_show_item_id"))
        self._update_result_label()

    def get_loadout_state(self) -> dict | None:
        """Called by the host app's save_profile(). Reads the live
        LoadoutWindow if it's been opened this session, otherwise falls
        back to whatever was last loaded/set -- so a save never wipes out
        previously-saved Build Planner data just because the user didn't
        open Armory this session."""
        if self._loadout_window is not None:
            return self._loadout_window.get_persistable_state()
        return self._pending_loadout_state

    def _open_crafting_calculator(self):
        self.open_crafting_calculator()

    def open_crafting_calculator(self):
        """Public entry point so a host app (or the Armory page's own
        'Crafting Calculator' Open button) can jump straight to the
        Crafting Guide — same singleton-window pattern as
        open_loadout_window."""
        if self._crafting_window is None:
            self._crafting_window = CraftingCalculatorWindow(self._raw_items, self.icon_cache, self.detail_cache, None)
            self._crafting_window.setStyleSheet(_load_qss_text())
        self._crafting_window.show()
        self._crafting_window.raise_()
        self._crafting_window.activateWindow()

    def _on_search_changed(self, text):
        self.proxy.set_search(text)
        self._update_result_label()

    def _on_grade_changed(self, text):
        self.proxy.set_grade(text)
        self._update_result_label()

    def _on_category_changed(self, text):
        if text == "All":
            self.proxy.set_subcategory_categories(None)
        elif self._current_sidebar_group == "Gear":
            self.proxy.set_subcategory_categories(_GEAR_SUBGROUPS.get(text, set()))
        else:
            self.proxy.set_subcategory_categories({text})
        self._update_result_label()

    def _on_class_changed(self, text):
        self.proxy.set_class(text)
        self._update_result_label()

    def _on_wing_equip_changed(self, text):
        self.proxy.set_wing_equip_filter(None if text == "All" else text)
        self._update_result_label()

    def _on_wing_owned_changed(self, text):
        self.proxy.set_wing_owned_filter(None if text == "All" else text)
        self._update_result_label()

    def _on_sidebar_group_selected(self, group_label: str | None):
        """Right-hand sidebar click (User-Wunsch): narrows the table to one
        top-level group (_ITEM_TOP_CATEGORIES) and repopulates the Category
        dropdown above to that group's own subcategories -- "Gear" shows its
        3 subgroup labels (Weapons/Armor/Accessories), every other group
        shows its raw categoryName values directly. The dropdown itself
        stays a dropdown per the user's explicit instruction; only its
        CONTENTS and MEANING change with the sidebar selection.

        "Wings" is a special case (User-Wunsch): instead of Category/Class
        (neither means anything for Wings -- no classNames, only 2 near-
        identical raw categories), it swaps in two dedicated stat filters
        (Equip Effect / Owned Effect, see _parse_wing_effects) in the exact
        same layout slots.

        Class is ALSO hidden for every group besides "Gear" (and "All
        Categories") -- confirmed against the real catalog that classNames
        only ever varies within the 10 Weapons categories (Guard included,
        though it turns out never actually class-gated either); every other
        raw categoryName (Materials & Enhancement, Arcana, Consumables,
        ...) always has an empty classNames, so the Class dropdown was
        pure noise there (User: "Bei Material and enhancement kannst du
        den Class filter rausnehmen")."""
        self._current_sidebar_group = group_label
        is_wings = group_label == "Wings"
        class_relevant = group_label in (None, "Gear")

        self.category_combo.setVisible(not is_wings)
        self.class_combo.setVisible(not is_wings and class_relevant)
        self.wing_equip_combo.setVisible(is_wings)
        self.wing_owned_combo.setVisible(is_wings)

        if not is_wings and not class_relevant:
            # Hiding the control must not leave a stale Class filter
            # silently narrowing rows in a group where it's not shown.
            self.class_combo.setCurrentIndex(0)
            self.proxy.set_class("All")

        if is_wings:
            self.proxy.set_group_categories(dict(_ITEM_TOP_CATEGORIES)["Wings"])
            self.proxy.set_subcategory_categories(None)
            self.proxy.set_class("All")
        else:
            # Leaving (or never entering) Wings -- clear any leftover
            # Wings-specific filter so it can't silently hide rows in every
            # other category (which all have empty Equip/Owned stat sets).
            self.wing_equip_combo.setCurrentIndex(0)
            self.wing_owned_combo.setCurrentIndex(0)
            self.proxy.set_wing_equip_filter(None)
            self.proxy.set_wing_owned_filter(None)

            if group_label is None:
                self.proxy.set_group_categories(None)
                combo_values = self._all_categories
            elif group_label == "Gear":
                self.proxy.set_group_categories(_gear_group_categories())
                combo_values = set(_GEAR_SUBGROUPS.keys())
            else:
                group_categories = dict(_ITEM_TOP_CATEGORIES).get(group_label, set())
                self.proxy.set_group_categories(group_categories)
                combo_values = group_categories & self._all_categories

            self._populate_filter_combo(self.category_combo, combo_values)
            self.proxy.set_subcategory_categories(None)

        self._update_result_label()

    def _on_gear_type_toggled(self, key: str, checked: bool):
        if checked:
            other = {"PvP": "PvE", "PvE": "PvP"}.get(key)
            if other and self.gear_type_buttons[other].isChecked():
                self.gear_type_buttons[other].setChecked(False)
        active = {k for k, b in self.gear_type_buttons.items() if b.isChecked()}
        self.proxy.set_gear_types(active)
        self._update_result_label()

    def _update_result_label(self):
        shown = self.proxy.rowCount()
        total = self.model.rowCount()
        self.result_label.setText(_t("arm_items_count", shown=shown, total=total))

    def _on_show_id_toggled(self, checked: bool):
        self.table.setColumnHidden(ID_COLUMN, not checked)

    def _request_visible_icons(self, *_args):
        row_count = self.proxy.rowCount()
        if row_count == 0:
            return

        top_index = self.table.indexAt(self.table.viewport().rect().topLeft())
        bottom_index = self.table.indexAt(self.table.viewport().rect().bottomLeft())
        top_row = top_index.row() if top_index.isValid() else 0
        bottom_row = bottom_index.row() if bottom_index.isValid() else row_count - 1
        if bottom_row < 0:
            bottom_row = row_count - 1

        start = max(0, top_row - VISIBLE_ROW_PADDING)
        end = min(row_count - 1, bottom_row + VISIBLE_ROW_PADDING)

        for row in range(start, end + 1):
            source_index = self.proxy.mapToSource(self.proxy.index(row, 0))
            icon_item = self.model.item(source_index.row(), 0)
            if icon_item is None:
                continue
            url = icon_item.data(Qt.UserRole)
            if not url:
                continue
            grade = icon_item.data(Qt.UserRole + 1)
            cached = self.icon_cache.pixmap(url, grade=grade)
            if cached is not None:
                if icon_item.data(Qt.DecorationRole) is None:
                    icon_item.setData(cached, Qt.DecorationRole)
            else:
                self.icon_cache.request(url)

    def _on_icon_ready(self, url: str):
        for icon_item in self._icon_items_by_url.get(url, []):
            grade = icon_item.data(Qt.UserRole + 1)
            pixmap = self.icon_cache.pixmap(url, grade=grade)
            if pixmap is not None:
                icon_item.setData(pixmap, Qt.DecorationRole)

    def show_item_tooltip(self, index, global_pos) -> bool:
        source_index = self.proxy.mapToSource(index)
        id_item = self.model.item(source_index.row(), ID_COLUMN)
        if id_item is None:
            return False
        item_id = id_item.data(Qt.EditRole)
        if not item_id:
            return False

        detail = self.detail_cache.get(item_id)
        if detail:
            QToolTip.showText(global_pos, format_tooltip(detail), self.table)
        else:
            QToolTip.showText(global_pos, "Loading details…", self.table)
            self._pending_tooltip_id = item_id
            self.detail_cache.request(item_id)
        return True

    def _on_detail_ready(self, item_id: int):
        if self._pending_tooltip_id != item_id:
            return
        self._pending_tooltip_id = None

        # Only refresh the tooltip if the mouse is still hovering the same cell.
        local_pos = self.table.viewport().mapFromGlobal(QCursor.pos())
        current_index = self.table.indexAt(local_pos)
        if not current_index.isValid() or current_index.column() != NAME_COLUMN:
            return

        source_index = self.proxy.mapToSource(current_index)
        current_id_item = self.model.item(source_index.row(), ID_COLUMN)
        if current_id_item is None or current_id_item.data(Qt.EditRole) != item_id:
            return

        detail = self.detail_cache.get(item_id)
        if detail:
            QToolTip.showText(QCursor.pos(), format_tooltip(detail), self.table)

    def _load_items(self):
        if not DATA_PATH.exists():
            self.result_label.setText(_t("arm_no_cached_data", path=DATA_PATH))
            return

        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        items = data.get("items", [])
        # No classNames normalization needed here anymore -- the catalog's
        # own "Spiritmaster" is now the app-wide display name too (matches
        # shugo.gg's own item database, see _SKILLS_DATA_CLASS_ALIASES).
        self._raw_items = items

        categories, classes = set(), set()
        wing_equip_names, wing_owned_names = set(), set()

        for item in items:
            row = []

            icon_item = QStandardItem()
            image_url = item.get("image") or ""
            grade = item.get("grade")
            icon_item.setData(image_url, Qt.UserRole)
            icon_item.setData(grade, Qt.UserRole + 1)
            row.append(icon_item)
            if image_url:
                self._icon_items_by_url.setdefault(image_url, []).append(icon_item)
                cached = self.icon_cache.pixmap(image_url, grade=grade)
                if cached:
                    icon_item.setData(cached, Qt.DecorationRole)

            id_item = QStandardItem(str(item.get("id", "")))
            id_item.setData(int(item.get("id") or 0), Qt.EditRole)
            equip_stats, owned_stats = _parse_wing_effects(item.get("description") or "")
            if equip_stats:
                id_item.setData(equip_stats, WING_EQUIP_STATS_ROLE)
                wing_equip_names |= equip_stats
            if owned_stats:
                id_item.setData(owned_stats, WING_OWNED_STATS_ROLE)
                wing_owned_names |= owned_stats
            row.append(id_item)

            grade = item.get("grade", "") or ""
            color = GRADE_COLORS.get(grade)

            name_item = QStandardItem(item.get("name", ""))
            if color:
                name_item.setForeground(QColor(color))
            row.append(name_item)

            grade_item = QStandardItem(grade)
            if color:
                grade_item.setForeground(QColor(color))
            row.append(grade_item)

            category = item.get("categoryName", "") or ""
            row.append(QStandardItem(category))
            if category:
                categories.add(category)

            class_names = item.get("classNames") or []
            row.append(QStandardItem(", ".join(class_names)))
            for c in class_names:
                # Brawler is real in the raw data (Fist/Gauntlet items) but
                # not live at launch -- excluded from the Class FILTER same
                # as every other class picker in the app (AION2_ACTIVE_CLASSES),
                # while the table's own Classes column still shows it as-is.
                if c in AION2_ACTIVE_CLASSES:
                    classes.add(c)

            row.append(QStandardItem("Yes" if item.get("tradable") else "No"))

            gear_type = _gear_type(item)
            gear_type_item = QStandardItem(gear_type)
            gear_color = GEAR_TYPE_COLORS.get(gear_type)
            if gear_color:
                gear_type_item.setForeground(QColor(gear_color))
            row.append(gear_type_item)

            self.model.appendRow(row)

        self._all_categories = categories
        self._wing_equip_names = wing_equip_names
        self._wing_owned_names = wing_owned_names

        self._populate_filter_combo(self.category_combo, categories)
        self._populate_filter_combo(self.class_combo, classes)
        self._populate_filter_combo(self.wing_equip_combo, wing_equip_names)
        self._populate_filter_combo(self.wing_owned_combo, wing_owned_names)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, ICON_SIZE + 24)
        self._update_result_label()

    @staticmethod
    def _populate_filter_combo(combo: QComboBox, values: set):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All")
        for v in sorted(values):
            combo.addItem(v)
        combo.setCurrentIndex(0)
        combo.blockSignals(False)
        # blockSignals suppressed _make_label_combo's own currentIndexChanged
        # handler during the rebuild above -- refresh the label display once
        # manually now that the combo is back on index 0 ("All").
        label = combo.property("filterLabel")
        if label and combo.lineEdit():
            combo.lineEdit().setText(label)

    def _make_label_combo(self, label: str, on_change) -> QComboBox:
        """Builds a QComboBox whose collapsed field always shows `label`
        (e.g. "Grade") instead of the selected item's own text, while the
        opened dropdown list still shows the real items -- including "All"
        as a genuine, selectable reset option. Editable + read-only line
        edit is the standard Qt trick for decoupling displayed text from
        the actually-selected item; on_change is called with the REAL
        underlying item text (itemText(index)), never the overridden
        display text, so filtering logic is unaffected by the label swap."""
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.lineEdit().setReadOnly(True)
        combo.lineEdit().setCursor(Qt.ArrowCursor)
        combo.lineEdit().installEventFilter(_ComboPopupFilter(combo))
        combo.setProperty("filterLabel", label)

        def _handle_index_changed(index: int):
            real_text = combo.itemText(index) if index >= 0 else "All"
            combo.lineEdit().setText(label if index <= 0 else real_text)
            on_change(real_text)

        combo.currentIndexChanged.connect(_handle_index_changed)
        return combo

    def closeEvent(self, event):
        logger.debug("ItemDatabaseWindow closed")
        super().closeEvent(event)


def _bundled_resource(name: str) -> Path:
    """styles.qss is bundled *inside* the exe (PyInstaller _MEIPASS), unlike
    data/ which lives next to the exe so the cache persists across runs.

    Real bug found via a packaged-build screenshot (User, 2026-08-27: "was
    farbig angezeigt wird, ist das Icon eines Items - der Rest Grau mit
    weißer Schrift"): this used to build the frozen path as
    `_MEIPASS / name` directly, one level too shallow -- Aion2 TM.spec
    bundles this module's files under `ItemDatabase/` inside _MEIPASS (same
    as _BUNDLE_DIR above), so `_MEIPASS / "styles.qss"` never actually
    existed there and _load_qss_text() silently applied an empty
    stylesheet, leaving every widget on Qt's bare default style. Reusing
    _BUNDLE_DIR here (already correct -- items_all.json/icons load fine
    through it) instead of recomputing an independent, wrong path."""
    return _BUNDLE_DIR / name


def _load_qss_text() -> str:
    qss_path = _bundled_resource("styles.qss")
    if qss_path.exists():
        text = qss_path.read_text(encoding="utf-8")
        logger.debug("Stylesheet loaded: %s (%d bytes)", qss_path, len(text))
        # QSS url() needs an absolute path to resolve correctly both when
        # run from source and from inside the PyInstaller-bundled exe (its
        # _MEIPASS extraction dir differs run to run) -- forward slashes
        # since Qt's stylesheet parser doesn't accept Windows backslashes.
        arrow_path = str(_bundled_resource("assets/ui/dropdown_arrow.png")).replace("\\", "/")
        text = text.replace("__DROPDOWN_ARROW_URL__", arrow_path)
        return text
    logger.warning("Stylesheet not found: %s", qss_path)
    return ""


def create_window(parent=None, language: str = "en") -> ItemDatabaseWindow:
    """Builds the ItemDatabase window with its stylesheet scoped to the
    window instance (not the QApplication) — safe to embed as a popup
    inside a host application without overriding its global theme."""
    set_armory_language(language)
    window = ItemDatabaseWindow(parent)
    window.setStyleSheet(_load_qss_text())
    return window


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # native Windows style only partially honors QSS subcontrols (see main.py)
    window = create_window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
