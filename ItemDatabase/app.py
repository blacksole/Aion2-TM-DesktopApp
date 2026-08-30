"""Standalone AION 2 item database viewer — filterable, sortable table.

Test app, isolated from cont_ToDo_app (no imports from it, own styles.qss).
Run fetch_items.py first to populate data/items_all.json, then:
    python app.py
"""

import copy
import json
import math
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
    QBrush, QColor, QCursor, QIcon, QLinearGradient, QPainter, QPainterPath, QPalette, QPen, QPixmap,
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
    QRadioButton,
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
SHOP_ITEMS_PATH = _BUNDLE_DIR / "data" / "shop_items.json"
# The only 4 real, sources-tagged shops (see compute_shop_items.py) -- shared
# between TemplateItemPickerDialog's sidebar and ItemDatabaseWindow's own
# Shop filter dropdown so the two can never drift apart.
REAL_SHOP_TYPES = ("Merchant NPC", "Trade Shop", "Black Cloud Merchants", "Shugo Festival")
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

# Skill Points available at the current level-45 cap (User-Wunsch,
# 2026-08-27) -- researched externally, not derivable from our own item/
# recipe data since Empyrean Trace/Monolith is a pure map-collectible system
# (see project_skillpoint_sources.md memory for the full source list).
# Base: 1 Skill Point per level-up, levels 2-45 (level 1 itself gives none).
_SKILLPOINTS_BASE_AT_LEVEL_45 = 44

# Wisdom Stone rewards per Monolith level (1 Wisdom Stone = 1 permanent
# Skill Point) -- only the character's own starting-zone Monolith (Verteron
# for Elyos, Altgard for Asmodae) grants these; the other two Monoliths
# (Morheim/Eltnen, Ereshkigal) give cosmetics/PvP stats instead, no Skill
# Points. (level_from, level_to, wisdom_stones_per_level_in_range).
_MONOLITH_WISDOM_STONE_TIERS = [
    (2, 2, 1), (3, 9, 2), (10, 14, 3), (15, 19, 4), (20, 24, 5), (25, 29, 6), (30, 30, 7),
]
_MONOLITH_MAX_LEVEL = 30
_SKILLPOINTS_MONOLITH_MAX_BONUS = sum(amount * (hi - lo + 1) for lo, hi, amount in _MONOLITH_WISDOM_STONE_TIERS)


def _monolith_skillpoints(level: int) -> int:
    """Cumulative Skill Points (1 per Wisdom Stone) earned by reaching a
    given Monolith level, from _MONOLITH_WISDOM_STONE_TIERS."""
    level = max(0, min(_MONOLITH_MAX_LEVEL, level))
    total = 0
    for lo, hi, amount in _MONOLITH_WISDOM_STONE_TIERS:
        if level < lo:
            break
        total += amount * (min(level, hi) - lo + 1)
    return total

# Every skill's "normal" cap via plain Skill Points -- levels beyond this
# come from other systems (gear/Arcana/Daevanion Board), see the per-skill
# level counter's own docstring for why those aren't modeled with a real
# per-skill max yet. Stigma skills use a different, higher breakpoint since
# they're paid for from a wholly separate Stigma Point pool, not Skill
# Points (User-Wunsch, 2026-08-27: "Bei Stigmas gibt es erst blaue Zahlen
# ab Level 20").
_SKILL_LEVEL_BASE_CAP = 10
_STIGMA_LEVEL_BASE_CAP = 20


_ARCANA_WISH_COLOR = "#c084fc"


def _format_skill_level_html(manual_level: int, bonus_level: int = 0, wish_level: int = 0) -> str:
    """White = Skill Points actually invested via the -/+ counter, shown
    as-is regardless of any cap (the 10/20-per-skill BUDGET cap still
    applies separately -- see _refresh_skillpoints_label/
    _refresh_stigma_points_label -- it just no longer decides this label's
    color). A positive bonus -- equipped Trait/Skill picks plus active
    Daevanion Board skill_level nodes, never Skill Points -- is appended
    in blue as "(+N)" (User-Wunsch, 2026-08-28: "Die weisse Zahl ist nur
    für das Nutzen von Skillpunkten. Sobald man über das Gear oder Board
    etc Skill Level bekommt, werden diese in blau in Klammern angezeigt").
    A separate positive Arcana wish -- what you'd still like the Arcana
    Planner to cover, on top of the other two -- gets its OWN parenthetical
    in purple, e.g. "10 (+6) (+4)" (User-Wunsch, 2026-08-28: "eine weitere
    farbige Zahl ... testweise mal lila ... 10 weiss, 6 tuerkis, 4 lila").
    Supersedes the earlier convention where manual+bonus were summed into
    one number and only the generic 10/20-level cap decided white vs. blue,
    which wrongly colored manually-overinvested points blue too."""
    html = f"<span style='color:white; font-weight:700;'>{manual_level}</span>"
    if bonus_level > 0:
        html += f" <span style='color:#22d3ee; font-weight:700;'>(+{bonus_level})</span>"
    if wish_level > 0:
        html += f" <span style='color:{_ARCANA_WISH_COLOR}; font-weight:700;'>(+{wish_level})</span>"
    return html

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


# Per-rarity backdrop is the real texture image the user sourced from
# questlog.gg (saved locally under assets/backgrounds_rarity/, .png). A
# 2026-08-27 detour briefly replaced these with a painted gradient after the
# packaged build showed flat grey -- but the actual bug was unrelated
# (_bundled_resource() missing a path prefix, see _BUNDLE_DIR/_bundled_resource
# below, since fixed) and the gradient was a much paler, less saturated stand-
# in for the real artwork (User, 2026-08-27: "Der Orangene Hintergrund von
# Epischen Gegenständen war kräftig von der Farbe her" / current gradient
# looked "blass"). Reverted back to the real texture files.
_RARITY_BG_DIR = _BUNDLE_DIR / "assets" / "backgrounds_rarity"
_RARITY_BG_FILES = {
    "Common": "UT_SlotGrade_Common.png",
    "Rare": "UT_SlotGrade_Rare.png",
    "Unique": "UT_SlotGrade_Unique.png",
    "Epic": "UT_SlotGrade_Epic.png",
    "Legend": "UT_SlotGrade_Legend.png",
}
_rarity_bg_cache: dict[str, QPixmap] = {}


def _rarity_background(grade: str | None) -> QPixmap | None:
    if not grade or grade not in _RARITY_BG_FILES:
        return None
    if grade not in _rarity_bg_cache:
        path = _RARITY_BG_DIR / _RARITY_BG_FILES[grade]
        pix = QPixmap(str(path)) if path.exists() else QPixmap()
        if pix.isNull():
            logger.warning("Rarity background FAILED to load (grade=%s, path=%s, exists=%s) -- falling back to flat gray", grade, path, path.exists())
        else:
            logger.info("Rarity background loaded (grade=%s, path=%s, size=%s)", grade, path, pix.size())
        _rarity_bg_cache[grade] = pix
    pix = _rarity_bg_cache[grade]
    return pix if not pix.isNull() else None

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
        rarity's own texture backdrop (see _rarity_background) plus a
        matching border, instead of the neutral slate default — baked into
        the pixmap itself so it also works in contexts with no wrapper
        widget to style (e.g. a QStandardItem's DecorationRole in the item
        table)."""
        composed = QPixmap(size, size)
        composed.fill(Qt.transparent)

        radius = max(4, size // 8)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)

        painter = QPainter(composed)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.Antialiasing)

        border_color = GRADE_COLORS.get(grade) if grade else None
        bg_texture = _rarity_background(grade)

        painter.setClipPath(clip_path)
        if bg_texture is not None:
            scaled_bg = bg_texture.scaled(
                size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation,
            )
            painter.drawPixmap(0, 0, scaled_bg)
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
        try:
            network_error = reply.error()
            data = reply.readAll()
            reply.deleteLater()
        except RuntimeError:
            # The QNetworkReply's C++ object can already be gone by the time
            # this runs (observed live, 2026-08-29) -- nothing to recover,
            # the request just never completes; a later request() call for
            # the same url (not in _pending anymore) will simply retry it.
            return

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


def _build_collapsible_section(title: str, expanded: bool) -> tuple[QWidget, QVBoxLayout]:
    """Small reusable collapsible section (Qt has no built-in accordion) --
    a checkable QToolButton header toggles the body's visibility. Built
    for the Daevanion Board sidebar (User-Wunsch, 2026-08-28: "Accordions
    bauen") and reused by the Arcana Calculator results popup -- shares
    the same #DaevanionAccordionSection/Header/Body QSS rules since both
    want the identical dark-card-with-chevron look, not just similar
    code."""
    container = QWidget()
    container.setObjectName("DaevanionAccordionSection")
    outer = QVBoxLayout(container)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    header = QToolButton()
    header.setObjectName("DaevanionAccordionHeader")
    header.setCheckable(True)
    header.setChecked(expanded)
    header.setCursor(Qt.PointingHandCursor)

    body = QWidget()
    body.setObjectName("DaevanionAccordionBody")
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(10, 4, 10, 10)
    body_layout.setSpacing(2)
    body.setVisible(expanded)

    def set_text(checked: bool):
        header.setText(("▾  " if checked else "▸  ") + title)
    set_text(expanded)
    header.toggled.connect(lambda checked: (body.setVisible(checked), set_text(checked)))

    outer.addWidget(header)
    outer.addWidget(body)
    return container, body_layout


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
            # Qt.ForegroundRole always comes back as a QBrush (even when
            # set via QStandardItem.setForeground(QColor(...))), not a
            # QColor -- QPalette.setColor rejects a bare QBrush in this
            # PySide6 version (User-reported real crash, 2026-08-29, first
            # time this delegate got reused for grade_combo: TypeError
            # "setColor(...) called with wrong argument types"). Unwrap it.
            if isinstance(color, QBrush):
                color = color.color()
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
        stats_page.setObjectName("StatsPane")
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
        skills_page.setObjectName("StatsPane")
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
        character_class: str | None = None, preset_philosopher_stone: bool = False,
    ):
        """preset_substats/preset_enchant restore a previously-saved
        selection when reopening an already-equipped slot — without them,
        every reopen would silently reset the item back to +0/no substats,
        even though the slot's actual saved state (used for Stat Info)
        still had the real values. preset_philosopher_stone does the same
        for the Stone toggle -- previously always reset to False here, so
        reopening a slot (or Quick Select rebuilding it, see
        _apply_quick_substats) silently forgot it was active, even though
        the extra substat pick it allowed stayed checked (User-Wunsch,
        2026-08-27: "wird bislang der Philostein wieder entfernt und es
        steht wieder bei 6/6 statt 7/7")."""
        self._item_id = item_id
        self._image_url = image_url
        self._detail = None
        self._enchant_level = preset_enchant
        self._selected_substats = set(preset_substats or ())
        self._selected_substats_order = list(self._selected_substats)
        self._sub_stat_count = 0
        self._philosopher_stone_active = preset_philosopher_stone
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
        self.philosopher_stone_btn.setChecked(preset_philosopher_stone)
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
        # Requires BOTH: a real substat roll (subStatCount>0, same signal
        # the Priority List/auto-pick already uses) AND Unique grade or
        # better -- the grade half of this got wrongly dropped in an
        # earlier pass today (reasoned purely from "which grades have real
        # substats", which isn't the same question). Re-confirmed via
        # external sources after the user double-checked their own memory
        # (2026-08-27, "soweit ich weiß/glaube, kann man Philo Steine nur
        # auf Unique Gear und höher setzen"): Aion 2's real Soul Binding/
        # "Philosopher's Stone: Revelation" system is Unique-grade-and-up
        # only, independent of whether a lower-grade item happens to roll
        # real substats too (questlog.gg patch notes, aion2hub item DB).
        # "Legend" excluded here -- real rarity order in this app is Common
        # < Rare < Legend < Unique < Epic (see RARITY_ORDER and the enchant
        # defaults, which climb in that same order), so Legend sits BELOW
        # Unique despite its name, not "Unique or better". Deliberately NOT
        # grade_name (which prefers the detail API's "gradeName" field) --
        # that's a DIFFERENT axis used only for the enchant-curve formulas
        # above (e.g. an Epic-rarity item can have gradeName "Heroic", see
        # _ARMOR_DEFENSE_RATE/_WEAPON_CURVE_PARAMS), unrelated to the item's
        # actual displayed rarity that Soul Binding eligibility goes by --
        # comparing grade_name here silently misclassified real items
        # (verified: "Elder Greatsword" is rarity Legend but gradeName
        # "Epic", "Noble Dragon Lord Greatsword" is rarity Epic but
        # gradeName "Heroic" -- exactly backwards from intended).
        item_rarity = self._detail.get("grade") or ""
        self.philosopher_stone_btn.setVisible(
            self._selectable and self._sub_stat_count > 0 and item_rarity in ("Unique", "Epic")
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
                    # "Only show selected" merges Skills into the same tab
                    # as Substats instead of keeping them split (User-Wunsch,
                    # 2026-08-27: "alle traits und skills gemeinsam anzeigen
                    # ... nur ein Tab") -- reviewing a short combined
                    # selection doesn't need two near-empty tabs to click
                    # between.
                    skill_target_layout = self.substats_layout if self._only_show_selected else self.skills_tab_layout
                    grid = add_accordion_section(skill_target_layout, skill_key, skill_badge_text, "250,204,21", visible_skills)
                    for pos, (idx, skill) in enumerate(visible_skills):
                        row_btn = make_substat_row(idx, skill.get("name", ""))
                        grid_row, grid_col = divmod(pos, 2)
                        grid.addWidget(row_btn, grid_row, grid_col)
        else:
            self.substats_header_label.setText("")

        # Same merge: hide the now-redundant Skills tab entirely while
        # filtering to selected-only, and make sure tab 0 (which now hosts
        # the combined view) is the one actually shown.
        show_tab0 = bool(sub_stats) or (self._only_show_selected and bool(self._skill_options))
        show_tab1 = bool(self._skill_options) and not self._only_show_selected
        self.substats_tabs.setTabVisible(0, show_tab0)
        self.substats_tabs.setTabVisible(1, show_tab1)
        self.substats_tabs.setVisible(show_tab0 or show_tab1)
        if self._only_show_selected and show_tab0:
            self.substats_tabs.setCurrentIndex(0)
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

    def get_philosopher_stone_active(self) -> bool:
        return self._philosopher_stone_active


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

# ---- Arcana Planner (2026-08-29) -------------------------------------------
# One equip slot per Lord card TYPE (not a generic duplicates-allowed pool --
# corrected by the user after an initial wrong assumption: "da bei Magic und
# Vigor keine Waage existiert, sind es nur 5 Karten, somit betraegt die
# gesamt Anzahl der Setkarten nur 5, nicht 6"). Each slot's real in-game
# card can be leveled up independently of its base grade -- each level-up
# always grants +1 to exactly ONE random skill from the card's pool (never
# player-chosen -- User, 2026-08-29: "Der Spieler kann nicht waehlen,
# welcher Wert gelevelt wird ... nur immer wieder neue Karten farmen und
# leveln") -- and grade caps the max level reachable (Rare=3, Legend=4,
# Unique=5, User-confirmed). The Calculator deliberately does NOT simulate
# that randomness -- "Wir machen das aber nicht im Kalkulator, wir gehen
# von den perfekten Werten aus": it shows the PERFECT/best-case reference
# (every level-up landing on the one skill you care about, on a maxed
# Unique card) so a player can judge how close their own randomly-rolled
# real cards are to that ceiling -- not a literal "buy this and get
# exactly this" recommendation. Same perfect-case logic applies to the
# card's own Empyrean Lord stat effect, which also gains +1 per level
# (User: "Bei Magic und Vigor geht der Hauptwert ... auch nur +1"), so a
# maxed Unique card's Lord effect is shown at its max level's value too.
# Applies to ONE skill chosen from that type's class-specific pool
# (grade-independent -- see _load_arcana_class_skills), constrained by the
# type's fixed skill category: Chalice can target either an Active or a
# Passive skill ("Mastery"), Parchment/Compass/Scales only Active, Bell/
# Mirror only Passive. Common grade doesn't exist for any Lord card.
_ARCANA_LORD_TYPES = ["Chalice", "Parchment", "Compass", "Bell", "Mirror", "Scales"]
_ARCANA_LORD_CATEGORY = {
    "Chalice": "both", "Parchment": "active", "Compass": "active",
    "Bell": "passive", "Mirror": "passive", "Scales": "active",
}
_ARCANA_GRADE_MAX_LEVEL = {"Rare": 3, "Legend": 4, "Unique": 5}
# The Calculator always reasons about the perfect/best case -- a maxed
# Unique card -- so this is simply the Unique entry above. This is the
# CARD's overall level (how many shared extra-points its leveling
# provides in total -- see _ARCANA_CARD_EXTRA_BUDGET below, same number),
# distinct from _ARCANA_PER_SKILL_CAP (the max any ONE skill on that card
# can individually reach).
_ARCANA_MAX_CARD_LEVEL = _ARCANA_GRADE_MAX_LEVEL["Unique"]

# "Season 1" assumption (User-Wunsch, 2026-08-29, explicitly UNVERIFIED --
# "die Wahrscheinlichkeit ist sehr hoch, dass nur Vigor und Magic
# existieren"): only these two themes are treated as currently obtainable.
# The other 5 (Frenzy/Purity/Punishment/Protection/Indomitability) stay out
# of the planner's candidate pool for now -- same forward-compat intent as
# the Daevanion Board's _s/_a split, but here it's one flat set rather than
# two named variants since the user wants more seasons/slots addable later
# without a redesign (see _arcana_usable_lord_types below).
_ARCANA_ACTIVE_THEMES = {"Vigor", "Magic"}


def _arcana_usable_lord_types(theme_map: dict, active_themes: set[str]) -> list[str]:
    """Which Lord card types actually exist in at least one of the given
    themes -- e.g. Scales has no Vigor/Magic entry at all, so it's excluded
    from the Season-1 candidate pool entirely, dropping the real usable
    total from 6 to 5. Data-driven (reads theme_map, already scanned from
    arcana_info.json) rather than a hardcoded count, so a later season
    adding Scales -- or a wholly new theme -- just changes the result here,
    no separate constant to update."""
    return [
        ct for ct in _ARCANA_LORD_TYPES
        if any(ct in theme_map.get(theme, {}) for theme in active_themes)
    ]


_ARCANA_SKILL_SLOTS_PER_CARD = 4
# A real card rolls _ARCANA_SKILL_SLOTS_PER_CARD (4) of its type's ~5-6
# possible skills; the instant one is rolled it already sits at
# _ARCANA_SKILL_BASELINE (1), not 0 (User, 2026-08-29: "bei diesen Skills
# ist das Startlevel nicht '0' sondern 1" / "kann eine Karte, wenn sie +0
# ist, folgende Werte haben: Rushing Smash +1, Spinning Strike +1,
# Impactful Crush +1, Dark Crush +1"). Leveling the card then spends a
# SHARED pool of _ARCANA_CARD_EXTRA_BUDGET (5, for Unique) extra points,
# one at a time, each landing on ONE random already-rolled skill (never
# player-chosen) -- but no single skill can exceed _ARCANA_PER_SKILL_CAP
# (4) regardless of how many hits land on it (User: "das Limit ist +4 auf
# den Skills und das maximale Level, das eine Arcana erhalten kann, ist
# +5, also 5 Level auf die vorhandenen Skills verteilen"). Verified
# against the user's own worked examples: Parchment showing Onslaught +4
# (needs 3 hits beyond baseline) and Spinning Strike +3 (needs 2 hits) =
# exactly 5 hits, the full shared budget, with the card's other 2
# (unlisted, uninteresting) slots staying at baseline; Chalice showing
# Dark Crush +4 (3 hits, AT the per-skill cap) + Rushing Smash +2 (1 hit)
# = 4 of 5 hits used, the 5th would be wasted since Dark Crush is already
# capped. Both examples are inconsistent with either "no shared budget,
# every skill independently to +5" (Parchment's 2 slots alone would need
# 5 hits for just +4/+3, leaving nothing baseline-related unaccounted)
# or "one skill per card" (both cards clearly show 2+ skills at once).
_ARCANA_SKILL_BASELINE = 1
_ARCANA_CARD_EXTRA_BUDGET = _ARCANA_MAX_CARD_LEVEL
_ARCANA_PER_SKILL_CAP = 4
_ARCANA_SKILL_SLOTS_PER_CARD = 4
_ARCANA_DEFAULT_GRADE = "Unique"


def _arcana_card_slot_list(card_data: dict | None) -> list[dict | None]:
    """Exactly _ARCANA_SKILL_SLOTS_PER_CARD (4) positional entries, each
    either None (empty) or {"skill_id": ..., "level": ...} -- the shape
    manual per-slot editing needs (User-Wunsch, 2026-08-29: "Jede der 4
    Skill-Zeilen einzeln anklickbar", needs a stable index per slot).
    Migrates the older {"skill_ids": {sid: level}} shape on the fly (still
    what's stored in any profile saved before this existed, and still what
    the Calculator's Apply writes) -- a dict has no way to represent "slot
    2 is specifically empty while slot 3 has X", only "whatever order
    happened to get assigned"."""
    if not card_data:
        return [None] * _ARCANA_SKILL_SLOTS_PER_CARD
    slots = card_data.get("slots")
    if slots is None:
        old = card_data.get("skill_ids") or {}
        slots = [{"skill_id": sid, "level": lvl} for sid, lvl in old.items()]
    slots = list(slots[:_ARCANA_SKILL_SLOTS_PER_CARD])
    while len(slots) < _ARCANA_SKILL_SLOTS_PER_CARD:
        slots.append(None)
    return slots


def _arcana_card_grade(card_data: dict | None) -> str:
    if not card_data:
        return _ARCANA_DEFAULT_GRADE
    return card_data.get("grade", _ARCANA_DEFAULT_GRADE)


def _arcana_eligible_skills_for_type(
    ct: str, wishes: dict[str, int], class_skill_pools: dict[str, list[dict]], skill_type_by_id: dict[str, str],
) -> list[str]:
    """Wished skills this Lord type could ever roll (in its pool, matching
    its fixed Active/Passive/both category)."""
    category = _ARCANA_LORD_CATEGORY.get(ct)
    pool_ids = {s["id"] for s in class_skill_pools.get(ct, [])}
    return [
        sid for sid in wishes
        if sid in pool_ids and (category == "both" or skill_type_by_id.get(sid) == category)
    ]


def _arcana_full_pool_for_type(ct: str, class_skill_pools: dict[str, list[dict]]) -> list[str]:
    """Every real skill id this Lord type's pool can roll, wished or not --
    used to fill a card's 4 skill slots with something sensible once real
    wishes run out (User-Wunsch, 2026-08-29: "Immer alle 5 verteilen" /
    "kannst bei der Verteilung der restlichen Punkte auch gerne die
    Prioliste der Skills nehmen"), instead of leaving slots/budget
    stranded just because nothing was explicitly wished for them."""
    return [s["id"] for s in class_skill_pools.get(ct, [])]


def _arcana_best_card_contribution(
    eligible: list[str], full_pool: list[str], priority_rank: dict[str, int],
    wishes: dict[str, int], covered: dict[str, int],
) -> dict[str, int]:
    """What ONE card of this type contributes in the perfect/best case,
    given what's ALREADY covered by other assigned cards so far. Two
    phases:

    1. Choose up to _ARCANA_SKILL_SLOTS_PER_CARD (4) of the card's real
       skill slots: eligible (wished) skills with remaining unmet need
       first (an exchange argument shows no reason to pick a skill with
       less need over one with more, so no need to try every possible
       4-of-N subset), ranked by need then Priority List position as a
       tiebreak; if fewer than 4 wished skills have real need, the
       remaining slots are filled from the type's FULL pool ranked by
       Priority List position, then pool order as a last resort (User,
       2026-08-29: "kannst bei der Verteilung der restlichen Punkte auch
       gerne die Prioliste der Skills nehmen" / "wenn dort nur 4 Skills
       angegeben sind, nimm den erst besten") -- so a card's slots are
       never left conceptually "empty" just because nothing was wished.
    2. Spend the shared _ARCANA_CARD_EXTRA_BUDGET one point at a time,
       never past _ARCANA_PER_SKILL_CAP: real wish-need first, then once
       every chosen skill's own wish is met, keep spending the REST of
       the budget too (User: "Immer alle 5 verteilen") on whichever
       chosen skill ranks highest on the Priority List, falling back to
       pool order -- a real card's leveling doesn't stop just because
       your specific wish was already satisfied.

    Returns {skill_id: added_value} for the chosen skills (empty only if
    the type's pool has nothing at all matching its category)."""
    def remaining_need(sid: str, value: int) -> int:
        return max(0, wishes.get(sid, 0) - covered.get(sid, 0) - value)

    def choice_key(sid: str) -> tuple:
        need = max(0, wishes.get(sid, 0) - covered.get(sid, 0))
        return (-need, priority_rank.get(sid, float("inf")), sid)

    chosen = sorted(
        (sid for sid in eligible if wishes.get(sid, 0) - covered.get(sid, 0) > 0),
        key=choice_key,
    )[:_ARCANA_SKILL_SLOTS_PER_CARD]
    if len(chosen) < _ARCANA_SKILL_SLOTS_PER_CARD:
        filler = sorted(
            (sid for sid in full_pool if sid not in chosen),
            key=lambda sid: (priority_rank.get(sid, float("inf")), sid),
        )
        chosen += filler[: _ARCANA_SKILL_SLOTS_PER_CARD - len(chosen)]
    if not chosen:
        return {}

    values = {sid: _ARCANA_SKILL_BASELINE for sid in chosen}
    budget = _ARCANA_CARD_EXTRA_BUDGET
    while budget > 0:
        candidates = [sid for sid in chosen if values[sid] < _ARCANA_PER_SKILL_CAP]
        if not candidates:
            break
        best_sid = min(
            candidates,
            key=lambda sid: (-remaining_need(sid, values[sid]), priority_rank.get(sid, float("inf")), sid),
        )
        values[best_sid] += 1
        budget -= 1
    return values


def _arcana_best_combination(
    usable_types: list[str], type_to_theme: dict[str, str],
    eligible_by_type: dict[str, list[str]], full_pool_by_type: dict[str, list[str]],
    priority_rank: dict[str, int], wishes: dict[str, int],
) -> tuple[dict[str, int], list[dict]]:
    """Each of the 5 usable Lord types is now a real, fixed card (its
    theme chosen up front via ArcanaThemeChoiceDialog, not searched) --
    so unlike the earlier count-budget model, there's no more "which
    theme"/"skip this type" decision left to explore. Each type's card
    independently contributes _arcana_best_card_contribution's perfect-
    case values (sequentially, in usable_types order, so a later type's
    "remaining need" already reflects what earlier types covered)."""
    covered: dict[str, int] = {}
    path: list[dict] = []
    for ct in usable_types:
        theme = type_to_theme.get(ct)
        if not theme:
            continue
        contribution = _arcana_best_card_contribution(
            eligible_by_type.get(ct, []), full_pool_by_type.get(ct, []), priority_rank, wishes, covered,
        )
        if not contribution:
            continue
        for sid, value in contribution.items():
            covered[sid] = covered.get(sid, 0) + value
        path.append({"type": ct, "theme": theme, "skill_ids": contribution})
    return covered, path


def _arcana_compute_combinations(
    usable_types: list[str], type_to_theme: dict[str, str],
    class_skill_pools: dict[str, list[dict]], wishes: dict[str, int],
    skill_type_by_id: dict[str, str], priority_rank: dict[str, int] | None = None,
    max_results: int = 3,
) -> list[dict]:
    """Up to max_results distinct combinations, best first: the single
    result from _arcana_best_combination, then that same sequential fill
    repeated with the previous result's exact (type, skill) pairs excluded
    from that type's eligible AND full pool each time, forcing a
    structurally different combination whenever a type's real pool has
    more viable wished skills than its 4 slots (or a skill is shared
    across more than one type's pool) -- the only remaining source of
    alternatives now that each type's theme is fixed rather than
    searched. Pruning full_pool_by_type too (not just eligible_by_type)
    matters: otherwise a skill excluded as a WISH target could still
    silently reappear as plain FILLER on the very same card (filler
    selection draws from the whole pool), quietly re-covering the same
    wish and making the "different" combination not actually different."""
    if not wishes:
        return []

    eligible_by_type = {
        ct: _arcana_eligible_skills_for_type(ct, wishes, class_skill_pools, skill_type_by_id)
        for ct in usable_types
    }
    full_pool_by_type = {ct: _arcana_full_pool_for_type(ct, class_skill_pools) for ct in usable_types}
    priority_rank = priority_rank or {}

    results = []
    excluded: set[tuple] = set()
    for _ in range(max_results):
        pruned_eligible = {
            ct: [sid for sid in eligible if (ct, sid) not in excluded]
            for ct, eligible in eligible_by_type.items()
        }
        pruned_full_pool = {
            ct: [sid for sid in pool if (ct, sid) not in excluded]
            for ct, pool in full_pool_by_type.items()
        }
        covered, path = _arcana_best_combination(
            usable_types, type_to_theme, pruned_eligible, pruned_full_pool, priority_rank, wishes,
        )
        if not path:
            break
        results.append({"assignments": path, "covered": covered})
        for a in path:
            for sid in a["skill_ids"]:
                excluded.add((a["type"], sid))
    return results


def _arcana_result_coverage_percent(result: dict, wishes: dict[str, int]) -> float:
    """What percentage of the total wishlist this combination covers,
    clamped per skill at its own wish (overshoot on one skill doesn't
    offset a shortfall on another) -- used to filter out combinations
    that aren't a useful alternative (User-Wunsch, 2026-08-29: "nur
    Kombinationen anzeigen, die besser als 50% sind")."""
    total_wish = sum(wishes.values())
    if total_wish <= 0:
        return 0.0
    covered = result.get("covered", {})
    total_useful = sum(min(covered.get(sid, 0), need) for sid, need in wishes.items())
    return total_useful / total_wish * 100.0


def _arcana_eligible_types(
    skill_id: str, category: str | None, usable_types: list[str], class_skill_pools: dict[str, list[dict]],
) -> list[str]:
    """Which usable Lord types could ever target this skill -- in its
    pool AND matching its Active/Passive category (Chalice's "both"
    always matches)."""
    return [
        ct for ct in usable_types
        if any(s["id"] == skill_id for s in class_skill_pools.get(ct, []))
        and (_ARCANA_LORD_CATEGORY.get(ct) == "both" or _ARCANA_LORD_CATEGORY.get(ct) == category)
    ]


def _arcana_max_ceiling(
    skill_id: str, category: str | None, usable_types: list[str], class_skill_pools: dict[str, list[dict]],
) -> int:
    """The absolute most this skill could ever gain from Arcana THIS
    season assuming perfect leveling, ignoring every other wish -- one
    maxed Unique card can push any ONE skill up to _ARCANA_PER_SKILL_CAP
    (4), per eligible Lord type, since a type can go to whichever theme
    still has budget when the real split is chosen later (User-Wunsch,
    2026-08-29: "wenn ein Skill bereits +4 ist, kann der Rest maximal
    noch +3 werden" -- this is the standalone half of that; the OTHER
    half, how much competing wishes actually leave once slots are shared,
    is what _arcana_compute_combinations/_arcana_uncovered_reason resolve
    for a specific split+wishlist instead of a live, always-on number)."""
    eligible = _arcana_eligible_types(skill_id, category, usable_types, class_skill_pools)
    return len(eligible) * _ARCANA_PER_SKILL_CAP


def _arcana_uncovered_reason(
    skill_id: str, wish: int, covered: int, usable_types: list[str],
    class_skill_pools: dict[str, list[dict]], skill_type_by_id: dict[str, str],
) -> tuple[str, dict]:
    """Why a wished skill didn't fully reach its target in a given result
    (User-Wunsch, 2026-08-29: "einen Grund zeigen, warum gewisse Skills
    nicht gepusht werden koennen") -- returns a translation key + kwargs
    for _t(), one of three tiers:

    1. No eligible Lord type at all -- structural, can never be covered
       regardless of slots (skill isn't in any usable card's pool, or
       none match its Active/Passive category).
    2. Eligible types exist, but even dedicating every one of them to
       ONLY this skill can't reach the wish -- a hard ceiling from this
       season's real card pool, not specific to this one combination
       (theme choice no longer matters here: every usable type is always
       a real card regardless of which theme it's set to).
    3. Eligible types exist and COULD in principle reach the wish, just
       not in this particular combination -- those slots went to other
       wishes instead in this solve."""
    category = skill_type_by_id.get(skill_id)
    eligible_types = _arcana_eligible_types(skill_id, category, usable_types, class_skill_pools)
    if not eligible_types:
        return "arm_arcana_reason_no_card", {}

    max_possible = len(eligible_types) * _ARCANA_PER_SKILL_CAP
    if max_possible < wish:
        return "arm_arcana_reason_not_enough_slots", {"max": max_possible}

    return "arm_arcana_reason_competing_wishes", {}


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
# Fallback gradient per category (stop, color) -- used by _ArcanaSetBanner's
# paintEvent only for a Set that has no real background photo yet (see
# _arcana_set_background_path). Custom-painted directly on the widget
# rather than via QSS, both to layer cleanly with the photo+overlay and
# because a real Qt quirk was found here (Round 20): any ancestor with its
# OWN locally-set stylesheet (the Information tab's
# scroll.viewport().setStyleSheet("background: transparent;") from
# Round 14) silently blocks background-color from cascading through
# attribute/class QSS selectors, even though border/color/text still
# cascade fine.
ARCANA_CATEGORY_GRADIENT_STOPS = {
    "pve": ((0.0, "#14532d"), (1.0, "#4ade80")),
    "pvp": ((0.0, "#4c0519"), (1.0, "#fb7185")),
    "offense": ((0.0, "#78350f"), (1.0, "#f59e0b")),
    "defence": ((0.0, "#0c4a6e"), (1.0, "#38bdf8")),
    "cure": ((0.0, "#4c1d95"), (1.0, "#a855f7")),
}
# Browser-mockup-approved per-image crop (zoom relative to "cover", anchor_x/
# anchor_y in 0-1, same semantics as CSS background-size/background-position
# -- see project_arcana_planner.md Runde 21). Only Sets with a real photo
# (see _arcana_set_background_path) need an entry; anything missing here
# just defaults to (1.0, 0.5, 0.5) i.e. plain cover/center.
_ARCANA_SET_BANNER_IMAGE_TRANSFORM = {
    "Primal Vigor": (1.0, 0.5, 0.5),
    "Magic Armor": (1.2, 0.20, 0.5),
}
# Fixed width for the whole left column (Keine Sets + 7 banners + bonus
# panel) — kept constant regardless of window size or content so the
# banners never stretch/shrink oddly next to the card grid.
_ARCANA_SET_COLUMN_WIDTH = 220
# ~25% wider than the original 148 (User-Wunsch, 2026-08-29: "die Karten
# noch etwas breiter machen ... vllt von der aktuellen breite 20 oder 30%
# breiter").
_ARCANA_CARD_WIDTH = 185
# Every Arcana card always has exactly 4 skill slots (see
# [[project_arcana_planner]]) -- the Sets tab's cards show them inline.
_ARCANA_EQUIP_SLOT_COUNT = 4

ARCANA_DATA_PATH = _BUNDLE_DIR / "data" / "arcana_info.json"
ARCANA_CLASS_SKILLS_PATH = _BUNDLE_DIR / "data" / "arcana_class_skills.json"
ARCANA_ICON_DIR = _BUNDLE_DIR / "assets" / "arcana_icons"
# Wide banner photos for the Set-selection sidebar (User-Wunsch, 2026-08-29,
# with a real in-game reference screenshot from a colleague) -- filename is
# just the real Set name (ARCANA_SET_BONUSES[theme]["setName"]) with spaces
# turned into underscores, e.g. "Primal Vigor" -> "Primal_Vigor.png". Not
# every Set has one yet -- _ArcanaSetBanner falls back to a flat category
# gradient when the file doesn't exist, so images can be dropped in here
# one at a time with no further code changes needed.
ARCANA_SET_BACKGROUND_DIR = _BUNDLE_DIR / "assets" / "Arcana_Set_background"


def _arcana_set_background_path(set_name: str) -> Path | None:
    path = ARCANA_SET_BACKGROUND_DIR / f"{set_name.replace(' ', '_')}.png"
    return path if path.exists() else None


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


def _dedupe_bound_unbound(items) -> list[dict]:
    """Collapses Bound/Unbound catalog duplicates -- same name, grade and
    substat options, just a different tradable flag and item id (User-
    Wunsch, 2026-08-27: "werden noch doppelte Items angezeigt ... Entweder
    ist eines Unbound und das andere Bound"). Verified against the whole
    catalog: ~1969 such exact pairs exist (checked options AND full detail
    JSON -- byte-identical subStats/subStatCount/level/maxEnchantLevel
    between a pair), so keeping just one representative changes nothing
    mechanically, only removes the confusing lookalike row. Keeps
    whichever copy is encountered first (list order from items_all.json is
    stable run-to-run, so this is deterministic, not arbitrary per-call)."""
    seen: set[tuple] = set()
    result = []
    for item in items:
        key = (item.get("name"), item.get("grade"), tuple(item.get("options") or []))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


# Tile size for ItemPickerPopup's grid (was a single full-width column) —
# sized so 3 tiles fit across the popup's fixed width, per user request to
# cap the count of items shown per row at 3-4 rather than a single long
# vertical scroll for a 200-330 item category.
_PICKER_TILE_WIDTH = 124
_PICKER_TILE_HEIGHT = 118


class ItemPickerPopup(QWidget):
    """Anchored, borderless search+pick list — positioned right under
    whichever button opened it (combo button, slot's change button)
    instead of a separate modal window. Auto-dismisses on an outside click,
    Escape, or item pick, like a native combo-box dropdown.

    NOT a real Qt.Popup (was, until 2026-08-29) -- User-reported real bug:
    on a multi-monitor setup with mixed per-monitor scaling, Qt.Popup's own
    built-in grab/activation handling closed this the instant it was shown
    (confirmed via logging: geometry/isActiveWindow=True, then closeEvent
    fires in the very same tick, on every single slot click, only on that
    machine's cross-monitor DPI setup -- tried QGuiApplication.
    setHighDpiScaleFactorRoundingPolicy(PassThrough) first, didn't help,
    so this isn't a rounding-precision issue, Qt.Popup's grab itself is
    the problem). Replaced with a plain frameless always-on-top window +
    a manual QApplication-wide event filter that closes it on an outside
    click, plus an explicit Escape handler -- reimplements exactly what
    Qt.Popup gave us for free, just without its buggy cross-monitor grab."""

    item_chosen = Signal(dict)

    def __init__(
        self, items: list[dict], categories: list[str],
        icon_cache: "IconCache", detail_cache: "ItemDetailCache", parent=None,
        active_gear_types: set | None = None, equipped_ids: set | None = None,
        priority_ids: set | None = None,
    ):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        logger.info("ItemPickerPopup.__init__ starting: %d raw items, categories=%r", len(items), categories)
        self.setObjectName("ItemPickerPopup")
        # Wide enough for 3 tiles of _PICKER_TILE_WIDTH per row plus margins
        # and the vertical scrollbar.
        self.setFixedWidth(3 * _PICKER_TILE_WIDTH + 40)
        self.setMinimumHeight(420)

        self._items = _dedupe_bound_unbound(i for i in items if i.get("categoryName") in categories)
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
        # Item ids present anywhere on the EQ Priority list (User-Wunsch,
        # 2026-08-29: "Bei Auswahl des EQ spielt nur die Rolle, dass diese
        # als Favoriten angezeigt werden - aehnlich wie beim Skillplanner
        # mit den Sternchen") -- only passed by the main Equipment tab's
        # slot picker (_pick_for_slot), same one-sided convention as
        # equipped_ids above (EQ-Priority's own picker doesn't need to
        # star its own list).
        self._priority_ids = priority_ids or set()
        self._show_favorites_only = False
        self._sort_key = "name"
        # Block/Row view toggle (User-Wunsch, 2026-08-29: "Dann bitte
        # wieder Block ansicht und Row ansicht"), same pattern already
        # used by TemplateItemPickerDialog -- both views share this one
        # filtered+sorted item pool, only one is ever built at a time.
        self._view_mode = "block"
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
        # Forces each row to paint in its own per-grade color (User-
        # reported, 2026-08-29: dropdown showed plain white instead) --
        # the app-wide stylesheet's QComboBox{color:...} rule otherwise
        # wins over the model's own Qt.ForegroundRole once any global
        # stylesheet is active, a QSS selector tweak alone isn't enough
        # (already documented/solved this exact way for tier_combo, see
        # _RoleColorDelegate's own docstring).
        self.grade_combo.setItemDelegate(_RoleColorDelegate(self.grade_combo))
        self._populate_grade_combo()
        self.grade_combo.currentIndexChanged.connect(self._refresh_list)
        filter_row.addWidget(self.grade_combo)

        view_group = QButtonGroup(self)
        view_group.setExclusive(True)
        self.block_view_btn = QPushButton(_t("template_view_block"))
        self.block_view_btn.setObjectName("SkillFilterButton")
        self.block_view_btn.setCheckable(True)
        self.block_view_btn.setChecked(True)
        self.block_view_btn.clicked.connect(lambda _c=False: self._on_view_mode_changed("block"))
        self.row_view_btn = QPushButton(_t("template_view_row"))
        self.row_view_btn.setObjectName("SkillFilterButton")
        self.row_view_btn.setCheckable(True)
        self.row_view_btn.clicked.connect(lambda _c=False: self._on_view_mode_changed("row"))
        view_group.addButton(self.block_view_btn)
        view_group.addButton(self.row_view_btn)
        filter_row.addWidget(self.block_view_btn)
        filter_row.addWidget(self.row_view_btn)
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
        # NOTE: a "checked by default" attempt here (both synchronous and
        # deferred via QTimer.singleShot) caused a real, reproducible bug
        # (User-reported, 2026-08-29: clicking an EQ-Priority slot showed a
        # tiny ~2x3cm empty window for under a second, then nothing, on
        # every slot) -- toggling this checkbox's state at all around this
        # Qt.Popup's construction/show seems to confuse its own grab/focus
        # handling on Windows and self-dismisses it. Reverted to plain
        # unchecked-by-default (pre-existing, known-working behavior) --
        # the user can still check it manually. See project_todo.md for
        # the open follow-up on how to surface equipped items first
        # without touching this checkbox's checked-state programmatically.
        self.equipped_only_check = QCheckBox(_t("arm_only_equipped_items"))
        self.equipped_only_check.setVisible(bool(self._equipped_ids))
        self.equipped_only_check.toggled.connect(self._on_equipped_only_toggled)
        layout.addWidget(self.equipped_only_check)

        # "Favoriten anzeigen" -- items on the EQ Priority list (User-
        # Wunsch, 2026-08-29: "hat man bereits eine EQ Prioliste gesetzt und
        # moechte beim Gear Items austauschen ... hier eine Checkbox:
        # 'Favoriten anzeigen'"). Mirrors equipped_only_check's visibility
        # convention (only shown when there's something to filter by) but
        # stays unchecked by default -- unlike the EQ-Priority picker's own
        # equipped-checkbox above, browsing gear normally should show
        # everything until the user opts into narrowing it down.
        self.favorites_only_check = QCheckBox(_t("arm_only_favorites"))
        self.favorites_only_check.setVisible(bool(self._priority_ids))
        self.favorites_only_check.toggled.connect(self._on_favorites_only_toggled)
        layout.addWidget(self.favorites_only_check)

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

        # Row view -- same Icon/Name/Rarity table style as
        # CraftingItemPickerDialog/TemplateItemPickerDialog's own pickers.
        self.table_widget = QTableWidget(0, 3)
        self.table_widget.setHorizontalHeaderLabels(["", _t("arm_col_name"), _t("arm_rarity_label")])
        self.table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setSelectionBehavior(QTableView.SelectRows)
        self.table_widget.setEditTriggers(QTableView.NoEditTriggers)
        self.table_widget.setColumnWidth(0, 44)
        self.table_widget.setIconSize(QSize(28, 28))
        self.table_widget.verticalHeader().setDefaultSectionSize(34)
        self.table_widget.cellClicked.connect(self._choose_row)
        self.table_widget.verticalScrollBar().valueChanged.connect(self._request_visible_icons)
        self.table_widget.setVisible(False)
        layout.addWidget(self.table_widget, 1)

        self._refresh_list()
        QTimer.singleShot(0, self._request_visible_icons)
        logger.info("ItemPickerPopup.__init__ finished OK: %d items after filtering", len(self._items))

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

    def _on_favorites_only_toggled(self, checked: bool):
        self._show_favorites_only = checked
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

    def _on_view_mode_changed(self, mode: str):
        self._view_mode = mode
        self.list_widget.setVisible(mode == "block")
        self.table_widget.setVisible(mode == "row")
        self._refresh_list()

    def _active_view_widget(self):
        return self.list_widget if self._view_mode == "block" else self.table_widget

    def _refresh_list(self):
        query = self.search_input.text().strip().lower()
        grade_filter = self.grade_combo.currentData()
        self._icon_labels = {}
        self._level_labels = {}
        self._row_icon_queue = []

        matched = [
            item for item in self._items
            if (not query or query in item.get("name", "").lower())
            and (grade_filter in (None, "All") or item.get("grade") == grade_filter)
            and (not self._active_gear_types or _gear_type(item) in self._active_gear_types)
            and (not self._show_equipped_only or item.get("id") in self._equipped_ids)
            and (not self._show_favorites_only or item.get("id") in self._priority_ids)
        ]
        matched = self._sort_items(matched)

        if self._view_mode == "block":
            self._populate_block_view(matched)
        else:
            self._populate_row_view(matched)

        self._request_visible_icons()

    def _populate_block_view(self, matched: list[dict]):
        self.list_widget.clear()
        visible_ids = []
        for item in matched:
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

            # Gold star = this item is on the EQ Priority list (User-Wunsch,
            # 2026-08-29), same visual convention as the Skill Planner's
            # Priority List star. Only built when there's actually a
            # priority list to check against, same guard as
            # favorites_only_check's visibility above. Row view doesn't
            # get this badge (kept simple, matching TemplateItemPicker-
            # Dialog's row view, which never had a favorites concept).
            if self._priority_ids:
                star_row = QHBoxLayout()
                star_row.setContentsMargins(0, 0, 0, 0)
                star_row.addStretch()
                star_icon = QLabel()
                star_icon.setFixedSize(14, 14)
                star_icon.setPixmap(_make_star_icon(14))
                star_icon.setVisible(item.get("id") in self._priority_ids)
                star_icon.setToolTip(_t("arm_on_priority_list_tooltip"))
                star_row.addWidget(star_icon)
                row_layout.addLayout(star_row)

            icon_label = QLabel()
            icon_label.setFixedSize(40, 40)
            icon_label.setAlignment(Qt.AlignCenter)
            image_url = item.get("image", "")
            item_grade = item.get("grade")
            cached_icon = self.icon_cache.pixmap(image_url, 40, grade=item_grade)
            if cached_icon:
                icon_label.setPixmap(cached_icon)
            if image_url:
                self._icon_labels.setdefault(image_url, []).append((icon_label.setPixmap, item_grade))
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

    def _populate_row_view(self, matched: list[dict]):
        self.table_widget.setRowCount(len(matched))
        for row, item in enumerate(matched):
            icon_item = QTableWidgetItem()
            icon_item.setData(Qt.UserRole, item)
            image_url = item.get("image", "")
            item_grade = item.get("grade")
            cached_icon = self.icon_cache.pixmap(image_url, 28, grade=item_grade)
            if cached_icon:
                icon_item.setIcon(QIcon(cached_icon))
            if image_url:
                apply_fn = lambda pix, it=icon_item: it.setIcon(QIcon(pix))
                self._icon_labels.setdefault(image_url, []).append((apply_fn, item_grade))
            self._row_icon_queue.append((image_url, item_grade))
            self.table_widget.setItem(row, 0, icon_item)

            name_item = QTableWidgetItem(item.get("name", ""))
            self.table_widget.setItem(row, 1, name_item)

            grade = item.get("grade") or ""
            grade_item = QTableWidgetItem(grade)
            if grade in GRADE_COLORS:
                grade_item.setForeground(QColor(GRADE_COLORS[grade]))
            self.table_widget.setItem(row, 2, grade_item)

    def _request_visible_icons(self, *_args):
        widget = self._active_view_widget()
        count = len(self._row_icon_queue)
        if count == 0 or not widget.isVisible():
            return

        viewport = widget.viewport()
        if self._view_mode == "block":
            # bottomRIGHT, not bottomLeft — in the tile grid (left-to-right,
            # wrapping), indexAt(bottomLeft) only hits the first tile of
            # the last visible row, so the old row-based range would've
            # only ever covered one item per row instead of the whole
            # visible block.
            top_idx = widget.indexAt(viewport.rect().topLeft())
            bottom_idx = widget.indexAt(viewport.rect().bottomRight())
            top_row = top_idx.row() if top_idx.isValid() else 0
            bottom_row = bottom_idx.row() if bottom_idx.isValid() else count - 1
        else:
            top_row = widget.rowAt(0)
            top_row = top_row if top_row >= 0 else 0
            row_height = widget.verticalHeader().defaultSectionSize() or 34
            bottom_row = top_row + viewport.height() // row_height + 2
        if bottom_row < 0:
            bottom_row = count - 1

        # Buffer scaled up 3x from the old single-column value (6) since a
        # linear index range now spans 3 grid rows per 3 units instead of 1
        # (row view doesn't need the multiplier, but the extra buffer is
        # harmless there too).
        buffer = 6 * 3
        start = max(0, top_row - buffer)
        end = min(count - 1, bottom_row + buffer)
        icon_size = 40 if self._view_mode == "block" else 28
        for row in range(start, end + 1):
            if row >= len(self._row_icon_queue):
                continue
            url, grade = self._row_icon_queue[row]
            if url and self.icon_cache.pixmap(url, icon_size, grade=grade) is None:
                self.icon_cache.request(url)

    def _on_icon_ready(self, url: str):
        entries = self._icon_labels.get(url)
        if not entries:
            return
        icon_size = 40 if self._view_mode == "block" else 28
        for apply_fn, grade in entries:
            pix = self.icon_cache.pixmap(url, icon_size, grade=grade)
            if not pix:
                continue
            try:
                apply_fn(pix)
            except RuntimeError:
                # The tile/row this icon belonged to may already be gone
                # (view switched or list re-filtered since the request went
                # out) -- nothing to recover, just skip it.
                pass

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

    def _choose_row(self, row: int, _col: int):
        item = self.table_widget.item(row, 0)
        data = item.data(Qt.UserRole) if item else None
        if data:
            self.item_chosen.emit(data)
        self.close()

    def show_anchored(self, anchor: QWidget):
        target_pos = anchor.mapToGlobal(QPoint(0, anchor.height()))
        logger.info("ItemPickerPopup.show_anchored: anchor global pos target=%s", target_pos)
        self.move(target_pos)
        self.show()
        logger.info(
            "ItemPickerPopup.show_anchored: after show() -- visible=%s geometry=%s isActiveWindow=%s",
            self.isVisible(), self.geometry(), self.isActiveWindow(),
        )
        self.search_input.setFocus()
        logger.info("ItemPickerPopup.show_anchored: after setFocus() -- visible=%s", self.isVisible())
        # Manual outside-click dismissal, replacing Qt.Popup's built-in
        # (buggy, see class docstring) grab -- installed on the whole app
        # so a click anywhere outside this window's geometry closes it.
        QApplication.instance().installEventFilter(self)
        # Being WindowStaysOnTopHint, this otherwise stayed floating on top
        # of everything even after alt-tabbing away or clicking a
        # completely different application (User-reported, 2026-08-29:
        # "wenn man das Fenster in den Hintergrund verschiebt, bleibt das
        # immer noch da") -- an outside click never fires for that since
        # the click lands in a different app/process entirely. Closing on
        # applicationStateChanged -> inactive covers exactly that case.
        # Connected a beat late (User-reported real bug, 2026-08-29: the
        # popup closed itself instantly on every open, log showed
        # isActiveWindow=True immediately followed by an Inactive state
        # change in the SAME show_anchored call) -- creating this frameless
        # always-on-top window on this multi-monitor setup produces a
        # transient real Inactive blip during its own activation handshake,
        # not an actual "user switched away" -- the delay just needs to
        # outlast that blip before this starts listening.
        QTimer.singleShot(250, self._arm_inactive_close)

    def _arm_inactive_close(self):
        try:
            QApplication.instance().applicationStateChanged.connect(self._on_app_state_changed)
        except RuntimeError:
            pass  # already closed before the timer fired

    def _on_app_state_changed(self, state):
        if state != Qt.ApplicationActive:
            logger.info("ItemPickerPopup: app became inactive (state=%s) -- closing", state)
            self.close()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            # A click on grade_combo's OWN dropdown list closed this whole
            # popup (User-reported, 2026-08-29: "Filter oeffnet sich nach
            # oben [...] wenn man dann wieder auf 'All' wechselt, schliesst
            # sich die Suche wieder") -- that dropdown is a genuinely
            # separate top-level window Qt positions wherever it fits,
            # sometimes ABOVE this popup's own rect, so a pure
            # self.geometry().contains(...) check saw it as an "outside"
            # click. Tried checking Qt widget ancestry first (the dropdown
            # view IS parented under grade_combo in QObject terms) but
            # QWidget.isAncestorOf() doesn't cross a top-level window
            # boundary, so that came back False too -- checking whether
            # ANY native popup (combo dropdown, QMenu, ...) is currently
            # open is the actual reliable signal: defer to it entirely
            # and let Qt's own popup-click handling do its job instead of
            # us second-guessing it.
            if QApplication.activePopupWidget() is not None:
                return super().eventFilter(obj, event)
            global_pos = event.globalPosition().toPoint()
            if not self.geometry().contains(global_pos):
                logger.info("ItemPickerPopup: outside click at %s -- closing", global_pos)
                self.close()
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        logger.info("ItemPickerPopup.closeEvent fired (visible before=%s)", self.isVisible())
        app = QApplication.instance()
        app.removeEventFilter(self)
        try:
            app.applicationStateChanged.disconnect(self._on_app_state_changed)
        except (RuntimeError, TypeError):
            # Already disconnected (e.g. closeEvent firing twice) -- harmless.
            pass
        super().closeEvent(event)

    def hideEvent(self, event):
        logger.info("ItemPickerPopup.hideEvent fired")
        super().hideEvent(event)


def _load_shop_items() -> dict[str, list[int]]:
    """{shop_name: [item_id, ...]} for the 4 real, sources-tagged shops --
    see compute_shop_items.py. Empty dict if the derived file hasn't been
    generated yet (e.g. a fresh checkout before ever running that script)."""
    if not SHOP_ITEMS_PATH.exists():
        return {}
    try:
        return json.loads(SHOP_ITEMS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# Taller than ItemPickerPopup's own _PICKER_TILE_HEIGHT (118) -- proper
# breathing room around the icon (User-Wunsch, 2026-08-29: "brauchen wir
# auf jedenfall das Spacing für das Icon und somit eine höhere Zeile").
_TEMPLATE_PICKER_TILE_WIDTH = 124
_TEMPLATE_PICKER_TILE_HEIGHT = 132


class TemplateItemPickerDialog(QDialog):
    """Full item-database picker for the Templates dialog's "Import from
    Database" link -- real icons, search/grade filters (same idea as
    ItemPickerPopup, kept as its own class rather than shared/
    parameterized since the two have genuinely different interaction
    models: ItemPickerPopup is an anchored Qt.Popup that picks instantly
    on click and closes on any outside click -- fine for a quick equip-
    slot swap, but a poor fit here, where losing all your filters to a
    stray click while browsing the full catalog would be frustrating
    (User-Wunsch, 2026-08-29: "eine Möglichkeit, das Item auszuwählen und
    einen 'Apply' Button"). This is a real modal QDialog instead: click a
    tile to SELECT it (stays open, highlighted), Apply confirms and
    closes.

    Left sidebar: "All Categories" + one button per real, sources-tagged
    shop (see compute_shop_items.py/SHOP_ITEMS_PATH) -- Windbreeze/Season/
    Nightmare/Abyss shops have zero backing data in the catalog at all
    (verified 2026-08-29, checked every sources tag and every item name),
    so User-decision: those stay hand-curated Template entries instead,
    no picker filter for them until real Global data is available."""

    def __init__(self, items: list[dict], icon_cache: "IconCache", detail_cache: "ItemDetailCache", parent=None):
        super().__init__(parent)
        self.setObjectName("TemplateItemPickerDialog")
        self.setWindowTitle(_t("template_import_from_db_title"))
        self.resize(760, 640)

        self._all_items = items
        self.icon_cache = icon_cache
        self.detail_cache = detail_cache
        self._shop_items = _load_shop_items()
        # "All Categories" means "every purchasable item across the 4 real
        # shops" (the whole point of this picker is pre-filtering Shopping
        # templates to buyable items, User-Wunsch 2026-08-29), NOT the raw
        # unfiltered 10k-item catalog -- that would defeat the pre-filter
        # entirely (and made the dialog needlessly slow to render/search).
        self._all_shop_ids: set[int] = set()
        for ids in self._shop_items.values():
            self._all_shop_ids.update(ids)
        self._active_shop: str | None = None  # None == "All Categories"
        self._icon_labels: dict[str, list[tuple[QLabel, str | None]]] = {}
        self._row_icon_queue: list[tuple[str, str | None]] = []
        self.selected_item: dict | None = None

        icon_cache.icon_ready.connect(self._on_icon_ready)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        # ── Sidebar: All Categories + real shop types ───────────────────
        sidebar = QVBoxLayout()
        sidebar.setSpacing(6)
        self._shop_group = QButtonGroup(self)
        self._shop_group.setExclusive(True)

        all_btn = QPushButton(f"{_t('template_import_all_categories')} ({len(self._all_shop_ids)})")
        all_btn.setObjectName("SkillFilterButton")
        all_btn.setCheckable(True)
        all_btn.setChecked(True)
        all_btn.setMinimumHeight(36)
        all_btn.clicked.connect(lambda _c=False: self._on_shop_selected(None))
        self._shop_group.addButton(all_btn)
        sidebar.addWidget(all_btn)

        for shop_name in REAL_SHOP_TYPES:
            count = len(self._shop_items.get(shop_name, []))
            btn = QPushButton(f"{shop_name} ({count})")
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setMinimumHeight(36)
            btn.setEnabled(count > 0)
            btn.clicked.connect(lambda _c=False, s=shop_name: self._on_shop_selected(s))
            self._shop_group.addButton(btn)
            sidebar.addWidget(btn)

        sidebar.addStretch(1)
        sidebar_frame = QWidget()
        sidebar_frame.setLayout(sidebar)
        sidebar_frame.setFixedWidth(200)
        root.addWidget(sidebar_frame)

        # ── Right side: filters + tile/row view + Cancel/Apply ──────────
        right = QVBoxLayout()
        right.setSpacing(8)

        # Block/Row view toggle (User-Wunsch, 2026-08-29: "einmal die
        # aktuelle Block Ansicht und dann die Zeilenansicht, wie in der
        # Haupt Database") -- both views share the same filtered item pool
        # and the same lazy icon-loading queue; only one is ever built at a
        # time (switching re-runs _refresh_list for the newly active view)
        # so filtering never pays to populate both.
        self._view_mode = "block"
        view_group = QButtonGroup(self)
        view_group.setExclusive(True)
        self.block_view_btn = QPushButton(_t("template_view_block"))
        self.block_view_btn.setObjectName("SkillFilterButton")
        self.block_view_btn.setCheckable(True)
        self.block_view_btn.setChecked(True)
        self.block_view_btn.clicked.connect(lambda _c=False: self._on_view_mode_changed("block"))
        self.row_view_btn = QPushButton(_t("template_view_row"))
        self.row_view_btn.setObjectName("SkillFilterButton")
        self.row_view_btn.setCheckable(True)
        self.row_view_btn.clicked.connect(lambda _c=False: self._on_view_mode_changed("row"))
        view_group.addButton(self.block_view_btn)
        view_group.addButton(self.row_view_btn)

        filter_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_t("arm_search_placeholder"))
        self.search_input.textChanged.connect(self._refresh_list)
        filter_row.addWidget(self.search_input, 1)

        self.grade_combo = QComboBox()
        # Forces each row to paint in its own per-grade color (User-
        # reported, 2026-08-29: dropdown showed plain white instead) --
        # the app-wide stylesheet's QComboBox{color:...} rule otherwise
        # wins over the model's own Qt.ForegroundRole once any global
        # stylesheet is active, a QSS selector tweak alone isn't enough
        # (already documented/solved this exact way for tier_combo, see
        # _RoleColorDelegate's own docstring).
        self.grade_combo.setItemDelegate(_RoleColorDelegate(self.grade_combo))
        self._populate_grade_combo()
        self.grade_combo.currentIndexChanged.connect(self._refresh_list)
        filter_row.addWidget(self.grade_combo)
        filter_row.addWidget(self.block_view_btn)
        filter_row.addWidget(self.row_view_btn)
        right.addLayout(filter_row)

        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setFlow(QListWidget.LeftToRight)
        self.list_widget.setWrapping(True)
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setMovement(QListWidget.Static)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.setGridSize(QSize(_TEMPLATE_PICKER_TILE_WIDTH, _TEMPLATE_PICKER_TILE_HEIGHT))
        self.list_widget.setSpacing(0)
        self.list_widget.itemDoubleClicked.connect(lambda _i: self._accept_selected())
        self.list_widget.verticalScrollBar().valueChanged.connect(self._request_visible_icons)
        right.addWidget(self.list_widget, 1)

        # Row view -- same Icon/Name/Rarity table style as
        # CraftingItemPickerDialog's own picker table.
        self.table_widget = QTableWidget(0, 3)
        self.table_widget.setHorizontalHeaderLabels(["", _t("arm_col_name"), _t("arm_rarity_label")])
        self.table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setSelectionBehavior(QTableView.SelectRows)
        self.table_widget.setEditTriggers(QTableView.NoEditTriggers)
        self.table_widget.setColumnWidth(0, 52)
        self.table_widget.setIconSize(QSize(28, 28))
        self.table_widget.verticalHeader().setDefaultSectionSize(38)
        self.table_widget.cellDoubleClicked.connect(lambda _r, _c: self._accept_selected())
        self.table_widget.verticalScrollBar().valueChanged.connect(self._request_visible_icons)
        self.table_widget.setVisible(False)
        right.addWidget(self.table_widget, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(_t("cancel"))
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton(_t("template_import_select_btn"))
        apply_btn.setObjectName("primaryButton")
        apply_btn.clicked.connect(self._accept_selected)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)
        right.addLayout(btn_row)

        root.addLayout(right, 1)

        self._refresh_list()
        QTimer.singleShot(0, self._request_visible_icons)

    def _populate_grade_combo(self):
        # Scoped to the currently active shop pool (User-Wunsch, 2026-08-29:
        # "pruef einmal, dass die rechten Filterzahlen mit den Zahlen der
        # Shops uebereinstimmen") -- counting self._all_items here instead
        # showed "All (10000)" even while the sidebar said "All Categories
        # (1718)", i.e. two different "All"s disagreeing in the same dialog.
        pool = self._current_pool()
        counts: dict[str, int] = {}
        for i in pool:
            g = i.get("grade")
            if g:
                counts[g] = counts.get(g, 0) + 1
        model = QStandardItemModel(self.grade_combo)
        all_item = QStandardItem(f"All ({len(pool)})")
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

    def _on_shop_selected(self, shop_name: str | None):
        self._active_shop = shop_name
        # Grade counts are scoped to the active shop pool (see
        # _populate_grade_combo) -- must be rebuilt on every shop switch, or
        # they'd keep showing the previous shop's (or the very first,
        # "All Categories") counts. blockSignals so the model swap's
        # implicit reset-to-index-0 doesn't fire a redundant _refresh_list
        # before the explicit one below.
        self.grade_combo.blockSignals(True)
        self._populate_grade_combo()
        self.grade_combo.blockSignals(False)
        self._refresh_list()

    def _current_pool(self) -> list[dict]:
        if self._active_shop is None:
            return [it for it in self._all_items if it.get("id") in self._all_shop_ids]
        ids = set(self._shop_items.get(self._active_shop, []))
        return [it for it in self._all_items if it.get("id") in ids]

    def _on_view_mode_changed(self, mode: str):
        self._view_mode = mode
        self.list_widget.setVisible(mode == "block")
        self.table_widget.setVisible(mode == "row")
        self._refresh_list()

    def _refresh_list(self):
        query = self.search_input.text().strip().lower()
        grade_filter = self.grade_combo.currentData()
        self._icon_labels = {}
        self._row_icon_queue = []

        matched = [
            item for item in self._current_pool()
            if (not query or query in item.get("name", "").lower())
            and (grade_filter in (None, "All") or item.get("grade") == grade_filter)
        ]
        matched.sort(key=lambda i: i.get("name", ""))

        if self._view_mode == "block":
            self._populate_block_view(matched)
        else:
            self._populate_row_view(matched)

        self._request_visible_icons()

    def _populate_block_view(self, matched: list[dict]):
        self.list_widget.clear()
        for item in matched:
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, item)

            row_widget = QWidget()
            row_widget.setFixedSize(_TEMPLATE_PICKER_TILE_WIDTH, _TEMPLATE_PICKER_TILE_HEIGHT)
            row_layout = QVBoxLayout(row_widget)
            row_layout.setContentsMargins(6, 10, 6, 10)
            row_layout.setSpacing(6)
            row_layout.setAlignment(Qt.AlignHCenter)

            grade_color = GRADE_COLORS.get(item.get("grade"), "#94a3b8")

            icon_label = QLabel()
            icon_label.setFixedSize(44, 44)
            icon_label.setAlignment(Qt.AlignCenter)
            image_url = item.get("image", "")
            item_grade = item.get("grade")
            cached_icon = self.icon_cache.pixmap(image_url, 44, grade=item_grade)
            if cached_icon:
                icon_label.setPixmap(cached_icon)
            if image_url:
                self._icon_labels.setdefault(image_url, []).append((icon_label.setPixmap, item_grade))
            self._row_icon_queue.append((image_url, item_grade))
            row_layout.addWidget(icon_label, 0, Qt.AlignHCenter)

            full_name = item.get("name", "")
            name_label = QLabel(_short_skill_name(full_name, 16))
            name_label.setStyleSheet(f"color: {grade_color}; font-weight: 600; font-size: 11px;")
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setToolTip(full_name)
            row_layout.addWidget(name_label)

            list_item.setSizeHint(QSize(_TEMPLATE_PICKER_TILE_WIDTH, _TEMPLATE_PICKER_TILE_HEIGHT))
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, row_widget)

    def _populate_row_view(self, matched: list[dict]):
        self.table_widget.setRowCount(len(matched))
        for row, item in enumerate(matched):
            icon_item = QTableWidgetItem()
            icon_item.setData(Qt.UserRole, item)
            image_url = item.get("image", "")
            item_grade = item.get("grade")
            cached_icon = self.icon_cache.pixmap(image_url, 28, grade=item_grade)
            if cached_icon:
                icon_item.setIcon(QIcon(cached_icon))
            if image_url:
                apply_fn = lambda pix, it=icon_item: it.setIcon(QIcon(pix))
                self._icon_labels.setdefault(image_url, []).append((apply_fn, item_grade))
            self._row_icon_queue.append((image_url, item_grade))
            self.table_widget.setItem(row, 0, icon_item)

            name_item = QTableWidgetItem(item.get("name", ""))
            self.table_widget.setItem(row, 1, name_item)

            grade = item.get("grade") or ""
            grade_item = QTableWidgetItem(grade)
            if grade in GRADE_COLORS:
                grade_item.setForeground(QColor(GRADE_COLORS[grade]))
            self.table_widget.setItem(row, 2, grade_item)

    def _active_view_widget(self):
        return self.list_widget if self._view_mode == "block" else self.table_widget

    def _request_visible_icons(self, *_args):
        widget = self._active_view_widget()
        count = len(self._row_icon_queue)
        if count == 0 or not widget.isVisible():
            # Before the dialog is actually shown (or while the inactive
            # view is hidden), the viewport has no real geometry yet -- see
            # the geometry-estimate fallback below for why this used to
            # matter even once shown.
            return

        viewport = widget.viewport()
        if self._view_mode == "block":
            top_idx = widget.indexAt(viewport.rect().topLeft())
            bottom_idx = widget.indexAt(viewport.rect().bottomRight())
            top_row = top_idx.row() if top_idx.isValid() else 0
            cols = max(1, viewport.width() // _TEMPLATE_PICKER_TILE_WIDTH)
            rows_on_screen = viewport.height() // _TEMPLATE_PICKER_TILE_HEIGHT + 2
            estimate = cols * rows_on_screen
        else:
            top_row = widget.rowAt(0)
            top_row = top_row if top_row >= 0 else 0
            bottom_idx = None
            row_height = widget.verticalHeader().defaultSectionSize() or 38
            estimate = viewport.height() // row_height + 2

        # Real measured bottom index wins when Qt can give us one; otherwise
        # fall back to a geometry-based ESTIMATE (never "assume the whole
        # list"), which was the actual bug behind a ~1700-item burst of
        # synchronous IconCache.request() calls (measured ~1.8s) whenever
        # indexAt()/rowAt() couldn't resolve a real hit yet (both right after
        # construction and, it turns out, briefly after the real show()
        # too -- the flow/row layout needs a moment to settle).
        if self._view_mode == "block" and bottom_idx is not None and bottom_idx.isValid():
            bottom_row = bottom_idx.row()
        else:
            bottom_row = min(count - 1, top_row + estimate)

        buffer = 12
        start = max(0, top_row - buffer)
        end = min(count - 1, bottom_row + buffer)
        for row in range(start, end + 1):
            if row >= len(self._row_icon_queue):
                continue
            url, grade = self._row_icon_queue[row]
            if url and self.icon_cache.pixmap(url, 44 if self._view_mode == "block" else 28, grade=grade) is None:
                self.icon_cache.request(url)

    def _on_icon_ready(self, url: str):
        entries = self._icon_labels.get(url)
        if not entries:
            return
        for apply_fn, grade in entries:
            size = 44 if self._view_mode == "block" else 28
            pix = self.icon_cache.pixmap(url, size, grade=grade)
            if not pix:
                continue
            try:
                apply_fn(pix)
            except RuntimeError:
                # The row/tile this icon belonged to may already be gone
                # (view switched or list re-filtered since the request went
                # out) -- nothing to recover, just skip it.
                pass

    def _accept_selected(self):
        if self._view_mode == "block":
            item = self.list_widget.currentItem()
            data = item.data(Qt.UserRole) if item else None
        else:
            item = self.table_widget.item(self.table_widget.currentRow(), 0)
            data = item.data(Qt.UserRole) if item else None
        if data:
            self.selected_item = data
            self.accept()


class _ArcanaSkillSlotFrame(QFrame):
    """One clickable skill-slot row on a Sets-tab _ArcanaCardButton (User-
    Wunsch, 2026-08-29: "Jede der 4 Skill-Zeilen einzeln anklickbar").
    Plain QFrame otherwise doesn't emit anything on a mouse click -- this
    just adds that, kept separate from _ArcanaCardButton itself (a
    QPushButton) so a click here doesn't also register as a click on the
    whole card. event.accept() is required for that separation to
    actually hold -- confirmed via a real QTest.mouseClick that without
    it, the parent QPushButton ALSO fired its own clicked (an ignored
    mouse event bubbles up to the parent in Qt), which would have opened
    both the skill picker AND the card's own Set-picker from one click."""

    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            event.accept()
            self.clicked.emit()
        else:
            super().mousePressEvent(event)


class _ArcanaCardButton(QPushButton):
    """One of the 10 Arcana card slots. Before any Set is chosen it shows a
    neutral default icon ("Leer"); once a Set is active it either shows
    that card's real Lord (+ its stat effect) or Main Stat (for the 4 Stat
    cards, which have no Lord/skills), plus a colored dot per grade this
    combo actually has — or, if this card type doesn't exist in the chosen
    theme at all (e.g. Scales has no Vigor/Magic variant), a clearly
    dashed-border "Nicht verfügbar" state. Clicking only does something for
    an available Lord card (opens the real per-class skill popover)."""

    # Sets-tab only (with_skill_slots=True): emitted when one of the 4
    # skill-slot rows is clicked (User-Wunsch, 2026-08-29, manual per-slot
    # skill/level editing) or when a grade pill is picked.
    skill_slot_clicked = Signal(int)
    grade_changed = Signal(str)

    def __init__(self, card_type: str, parent=None, with_skill_slots: bool = False):
        super().__init__(parent)
        self.card_type = card_type
        self.entry: dict | None = None
        self.setObjectName("ArcanaCardButton")
        self.setCursor(Qt.PointingHandCursor)
        self._hover_tooltip = None
        self._hover_data_fn = None
        self.skill_slot_labels: list[tuple[QLabel, QLabel]] = []
        self.slot_frames: list[_ArcanaSkillSlotFrame] = []
        self.grade_buttons: dict[str, QPushButton] = {}

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

        if with_skill_slots:
            # Every Arcana card always has exactly 4 skill slots (see
            # [[project_arcana_planner]]) -- shown inline as part of this
            # same bordered card (User-Wunsch, 2026-08-29, with a rough
            # mockup screenshot: "Schau mal bitte, dass jede Karte diesen
            # Aufbau hat im Set. In die Boxen darunter zeigen wir dann die
            # Skills der jeweiligen Karte an"), NOT a hover tooltip -- Sets
            # cards represent a real committed assignment (via the
            # Calculator's Apply button, or eventually manual per-slot
            # picking), unlike the Information tab's pure browsing
            # reference (User: "sollen kein Hover Effekt haben").
            layout.addSpacing(4)

            # Card grade pills (User-Wunsch, 2026-08-29: manuelle Skill/
            # Level-Auswahl soll die echte Kartenraritaet beruecksichtigen,
            # "Raritaet waehlbar, Budget passt sich an") -- picks which
            # shared extra-point budget (_ARCANA_GRADE_MAX_LEVEL) applies
            # when manually setting a slot's level below. Independent of
            # "theme" (still only set via the Calculator's Apply) -- a
            # card's grade/level and its Set/theme are separate axes.
            grade_row = QHBoxLayout()
            grade_row.setSpacing(4)
            grade_group = QButtonGroup(self)
            grade_group.setExclusive(True)
            for grade in ("Rare", "Legend", "Unique"):
                btn = QPushButton(grade)
                btn.setObjectName("ArcanaGradePill")
                btn.setCheckable(True)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet(f"color: {GRADE_COLORS[grade]};")
                btn.clicked.connect(lambda _c=False, g=grade: self.grade_changed.emit(g))
                grade_group.addButton(btn)
                self.grade_buttons[grade] = btn
                grade_row.addWidget(btn)
            layout.addLayout(grade_row)

            for i in range(_ARCANA_EQUIP_SLOT_COUNT):
                # Name left-aligned, value right-aligned (User-Wunsch,
                # 2026-08-29: "die Zahl rechtsbuendig machen und den Text
                # linksbuendig, damit sollte es immer gleich aussehen") --
                # two separate QLabels in an HBox rather than one combined
                # rich-text string, so the value's position is independent
                # of how long the (already truncated) name happens to be.
                slot = _ArcanaSkillSlotFrame()
                slot.setObjectName("ArcanaEquipSkillSlot")
                slot.setFixedHeight(24)
                slot.setCursor(Qt.PointingHandCursor)
                slot.clicked.connect(lambda idx=i: self.skill_slot_clicked.emit(idx))
                slot_layout = QHBoxLayout(slot)
                slot_layout.setContentsMargins(8, 0, 8, 0)
                slot_layout.setSpacing(4)
                name_label = QLabel()
                name_label.setTextFormat(Qt.RichText)
                value_label = QLabel()
                value_label.setTextFormat(Qt.RichText)
                value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                slot_layout.addWidget(name_label, 1)
                slot_layout.addWidget(value_label, 0)
                layout.addWidget(slot)
                self.skill_slot_labels.append((name_label, value_label))
                self.slot_frames.append(slot)
            self.setFixedSize(_ARCANA_CARD_WIDTH, 200 + 24 + _ARCANA_EQUIP_SLOT_COUNT * 28 + 10)
        else:
            layout.addStretch()
            self.setFixedSize(_ARCANA_CARD_WIDTH, 200)

    def _restyle(self):
        self.style().unpolish(self)
        self.style().polish(self)

    def set_grade(self, grade: str):
        """Reflects the card's currently-selected rarity pill (User-
        Wunsch, 2026-08-29) -- purely visual state, doesn't itself change
        any assignment."""
        btn = self.grade_buttons.get(grade)
        if btn:
            btn.setChecked(True)

    def set_slots_enabled(self, enabled: bool):
        """Gates the 4 skill slots (and the grade pills) behind a Set
        being chosen first (User-Wunsch, 2026-08-29: "Wenn keine Karte
        hinterlegt ist, sollte keine Eigenschaft waehlbar sein. Erst wenn
        eine Karte und Set gewaehlt wurde, dann kann man Skills und deren
        Level waehlen"). A disabled QFrame/QPushButton in Qt simply
        doesn't deliver mouse events to it at all, so this alone is
        enough to block the click -- the ":disabled" QSS rules just make
        that visually obvious too."""
        for frame in self.slot_frames:
            frame.setEnabled(enabled)
        for grade, btn in self.grade_buttons.items():
            btn.setEnabled(enabled)
            # A disabled QPushButton's OWN inline per-grade color
            # (setStyleSheet in __init__) otherwise wins over the global
            # "#ArcanaGradePill:disabled { color: ... }" QSS rule entirely
            # -- same local-stylesheet-blocks-cascade quirk already
            # documented elsewhere this session (Round 20) -- so the dim
            # color has to be applied here directly instead of relying on
            # the QSS pseudo-state alone.
            color = GRADE_COLORS[grade] if enabled else "#475569"
            btn.setStyleSheet(f"color: {color};")

    def set_skill_slots(self, slots: list[dict | None], id_to_skill: dict[str, dict]):
        """Fills the 4 fixed skill-slot boxes (with_skill_slots=True only)
        from a real positional slot list -- exactly 4 entries, each either
        None (empty) or {"skill_id": ..., "level": ...} (User-Wunsch,
        2026-08-29: manual per-slot editing needs a stable slot INDEX,
        unlike the old {skill_id: level} dict this replaced, which could
        only ever represent "whatever order got assigned", not "slot 2 is
        specifically empty while slot 3 has X")."""
        for i, (name_label, value_label) in enumerate(self.skill_slot_labels):
            entry = slots[i] if i < len(slots) else None
            if not entry or not entry.get("skill_id"):
                name_label.setText("")
                value_label.setText("")
                continue
            sid = entry["skill_id"]
            level = entry.get("level", _ARCANA_SKILL_BASELINE)
            skill = id_to_skill.get(sid, {})
            name_color = _SKILL_TYPE_COLORS.get(skill.get("type", ""), "#94a3b8")
            # Raised from 16 (User-Wunsch, 2026-08-29, after the wider
            # cards from the previous round: "jetzt bitte die volle Laenge
            # fuer den Text nutzen ... Attack Preparation ist der Text
            # abgebrochen") -- 26 comfortably covers all but the single
            # longest real skill name in the dataset ("Lightning Strike
            # Scattershot", 28 chars) at this box width; still elides with
            # "…" past that (User: "wenn der Inhalt dann immernoch zu lang
            # ist, kannst du gerne den Text weiterhin mit ... abbrechen").
            name = _short_skill_name(skill.get("name", ""), 26)
            # Name left-aligned, value right-aligned in its own label
            # (User-Wunsch, 2026-08-29: "die Zahl rechtsbuendig machen und
            # den Text linksbuendig, damit sollte es immer gleich
            # aussehen") -- keeps the "+N" lined up on the right regardless
            # of name length, instead of trailing right after it.
            name_label.setText(f'<span style="color:{name_color};">{name}</span>')
            value_label.setText(f'<span style="color:#facc15;font-weight:700;">+{level}</span>')

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

    def enable_hover_tooltip(self, tooltip, data_fn):
        """Wires this card up to a shared ArcanaCardTooltip instance, shown
        on hover (User-Wunsch, 2026-08-29: "bitte umbauen auf Tipptool") --
        same _hover_token/"only rebuild on an actual key change" guard
        already proven for _ArcanaResultCardIcon's identical hover pattern
        (fixes a real Windows flicker bug: a floating translucent window
        sitting right over its own small source widget can trigger
        spurious native enter/leave messages). data_fn() -> (theme, lord,
        pool, assigned_values) or None (nothing to show, e.g. no Set
        active) -- called fresh on every hover, never cached, so it's
        always current."""
        self._hover_tooltip = tooltip
        self._hover_data_fn = data_fn

    def enterEvent(self, event):
        super().enterEvent(event)
        if self._hover_tooltip is None or self._hover_data_fn is None:
            return
        data = self._hover_data_fn()
        if data is None:
            return
        theme, lord, pool, assigned_values = data
        self._hover_tooltip._hover_token = getattr(self._hover_tooltip, "_hover_token", 0) + 1
        key = (self.card_type, theme)
        if getattr(self._hover_tooltip, "_shown_for_key", None) == key:
            return
        self._hover_tooltip._shown_for_key = key
        self._hover_tooltip.set_card(self.card_type, theme, lord, pool, assigned_values)
        self._hover_tooltip.show_at(QCursor.pos())

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if self._hover_tooltip is None:
            return
        token = getattr(self._hover_tooltip, "_hover_token", 0)
        tooltip = self._hover_tooltip

        def _maybe_hide():
            if getattr(tooltip, "_hover_token", 0) == token:
                tooltip._shown_for_key = None
                tooltip.hide()

        QTimer.singleShot(0, _maybe_hide)


class _ArcanaSetBanner(QPushButton):
    """One Set-selection banner in the Information tab's left sidebar
    (User-Wunsch, 2026-08-29, real in-game reference screenshot from a
    colleague: wide photo background + dark fade-from-left overlay +
    small spark icon + Set name, no PvE/PvP category label anymore) --
    replaces the old flat-gradient QPushButton (which also turned out to
    have a real, separately-fixed Qt background-color cascade bug, see
    [[project_arcana_planner]] Runde 20). Falls back to the previous
    flat category gradient when no real photo exists yet for this Set
    (see _arcana_set_background_path) -- browser-mockup-approved crop/
    zoom per image is baked in via _ARCANA_SET_BANNER_IMAGE_TRANSFORM."""

    def __init__(self, theme: str, set_name: str, category: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ArcanaSetBanner")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(_ARCANA_SET_COLUMN_WIDTH)
        self.setMinimumHeight(68)
        self._theme = theme
        self._set_name = set_name
        self._category = category
        path = _arcana_set_background_path(set_name)
        self._pixmap = QPixmap(str(path)) if path else None
        transform = _ARCANA_SET_BANNER_IMAGE_TRANSFORM.get(set_name)
        self._zoom, self._anchor_x, self._anchor_y = transform or (1.0, 0.5, 0.5)
        self.toggled.connect(lambda _c=False: self.update())
        self._bonus_tooltip = None

    def enable_bonus_tooltip(self, tooltip: "ArcanaSetBonusTooltip"):
        """Wires this banner up to a shared ArcanaSetBonusTooltip, shown on
        hover (User-Wunsch, 2026-08-29: "Kannst du diese Seteffekte als
        Hover Effekt abbilden?") -- same hover_token/shown_for_key guard as
        _ArcanaCardButton's card-skill hover (fixes the same real Windows
        flicker bug: a floating translucent window sitting right over its
        own small source widget can trigger spurious native enter/leave
        messages)."""
        self._bonus_tooltip = tooltip

    def enterEvent(self, event):
        super().enterEvent(event)
        if self._bonus_tooltip is None:
            return
        self._bonus_tooltip._hover_token = getattr(self._bonus_tooltip, "_hover_token", 0) + 1
        if getattr(self._bonus_tooltip, "_shown_for_key", None) == self._theme:
            return
        self._bonus_tooltip._shown_for_key = self._theme
        self._bonus_tooltip.set_bonus(self._theme)
        self._bonus_tooltip.show_at(QCursor.pos())

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if self._bonus_tooltip is None:
            return
        token = getattr(self._bonus_tooltip, "_hover_token", 0)
        tooltip = self._bonus_tooltip

        def _maybe_hide():
            if getattr(tooltip, "_hover_token", 0) == token:
                tooltip._shown_for_key = None
                tooltip.hide()

        QTimer.singleShot(0, _maybe_hide)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = 10.0
        clip_path = QPainterPath()
        clip_path.addRoundedRect(rect, radius, radius)
        painter.setClipPath(clip_path)

        if self._pixmap and not self._pixmap.isNull():
            # Approved browser mockup: image zoomed in slightly beyond
            # "cover" and anchored per-image (_ARCANA_SET_BANNER_IMAGE_
            # TRANSFORM), so a specific motif (e.g. Primal Vigor's wings)
            # lands where the overlay clears rather than dead-center.
            pw, ph = self._pixmap.width(), self._pixmap.height()
            cover_scale = max(rect.width() / pw, rect.height() / ph)
            scale = cover_scale * self._zoom
            sw, sh = pw * scale, ph * scale
            slack_x = max(0.0, sw - rect.width())
            slack_y = max(0.0, sh - rect.height())
            x = -slack_x * self._anchor_x
            y = -slack_y * self._anchor_y
            scaled = self._pixmap.scaled(
                int(sw), int(sh), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            )
            painter.drawPixmap(QRectF(x, y, sw, sh), scaled, QRectF(scaled.rect()))
        else:
            grad = QLinearGradient(0, 0, rect.width(), rect.height())
            for stop, color in ARCANA_CATEGORY_GRADIENT_STOPS[self._category]:
                grad.setColorAt(stop, QColor(color))
            painter.fillRect(rect, grad)

        # Dark fade-from-left overlay (Variant A from the browser mockup --
        # gradual, even fade -- User: "das finde ich an sich schon gut").
        overlay = QLinearGradient(0, 0, rect.width(), 0)
        overlay.setColorAt(0.0, QColor(6, 10, 18, 235))
        overlay.setColorAt(0.42, QColor(6, 10, 18, 140))
        overlay.setColorAt(0.75, QColor(6, 10, 18, 20))
        painter.fillRect(rect, overlay)
        painter.setClipping(False)

        border_color = QColor(255, 255, 255, 255 if self.isChecked() else 20)
        painter.setPen(QPen(border_color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)

        spark_font = self.font()
        spark_font.setPointSize(11)
        painter.setFont(spark_font)
        painter.setPen(QColor("#22d3ee"))
        painter.drawText(
            QRectF(18, 10, rect.width() - 30, 16), Qt.AlignLeft | Qt.AlignVCenter, "✦"
        )

        name_font = self.font()
        name_font.setBold(True)
        name_font.setPointSize(12)
        painter.setFont(name_font)
        painter.setPen(QColor("#fdfdfd"))
        painter.drawText(
            rect.adjusted(18, 0, -10, -10), Qt.AlignLeft | Qt.AlignBottom, self._set_name
        )
        painter.end()


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


# ── Skill damage estimate (User-Wunsch, 2026-08-29) ─────────────────────────
# Source: "Kanon's Aion 2 Bible" (community research doc, shared by the
# user: docs.google.com/document/d/11u4wLCG1WfL-xSka2Aze0rI9vYRa7mq3N3Gp1bt0AWY
# -- credits a Korean YouTuber "Aion Research Lab" for discovering the
# formula, explicitly still a work in progress per the doc itself). Real
# damage formula as documented there:
#
#   [[[((Pure Attack x Weapon Damage Boost) x Multi-Hit x Power Shard)
#       + Attack Bonus) x Attack Increase% + PvE/Boss/Species/FrontBack
#       Attack] x Skill Coefficient]
#    - [(Defense - Penetration) x DefenseMult]]
#   x (Damage Boost + PvE/Boss/Species Damage Boost) x Critical Damage Boost
#   x Smite x Perfect x Front/Back Damage Boost x Rear Damage Boost
#   x Skill Additional Damage = Final Damage
#
# We deliberately do NOT recompute this from scratch: nowhere (including
# this doc) publishes real base character stats by class/level, so there is
# no known "Pure Attack" reference to plug in, and no per-skill "Skill
# Coefficient" is published either. Instead, skills_all.json's own real
# per-level tooltip numbers (levels[].minValue/maxValue -- the game's own
# precomputed damage preview) are scaled by the player's ACTUAL percentage-
# based amplifiers below. This is an ESTIMATE of the doc's formula, not a
# from-scratch recomputation -- labeled as such everywhere it's shown.
#
# Every stat id below is a real, verified id from the game's own item data
# (cross-checked against ItemDatabase/data/details/*.json) -- if Global
# ever renames/rebalances one of these, only this block needs editing.
_DMG_STAT_WEAPON_DAMAGE_BOOST = "AmplifyWeaponDamage"   # Weapon Damage Boost
_DMG_STAT_ATTACK_INCREASE = "DamageRatio"               # Attack Increase (called "Attack increase" in-game)
_DMG_STAT_DAMAGE_BOOST = "AmplifyAllDamage"             # Damage Boost
_DMG_STAT_PVE_DAMAGE_BOOST = "PvEAmplifyDamage"         # PvE Damage Boost
_DMG_STAT_BOSS_DAMAGE_BOOST = "BossNpcAmplifyDamage"    # Boss Damage Boost
_DMG_STAT_CRIT_DAMAGE_BOOST = "AmplifyCriticalDamage"   # Critical Damage Boost
_DMG_STAT_SMITE = "HardHit"                             # Smite
_DMG_STAT_FRONT_DAMAGE_BOOST = "AmplifyFrontAttack"     # Front Attack Damage Boost
_DMG_STAT_BACK_DAMAGE_BOOST = "AmplifyBackAttack"       # Back/Rear Attack Damage Boost
# NOT modelled here (no real stat id found / not applicable to an estimate
# without a target): Species Attack/Damage Boost (mob-type specific, no
# equip stat for it), Perfect (a proc chance, not a guaranteed multiplier),
# Multi-Hit/Power Shard (same reason), Defense/Penetration (needs a TARGET's
# stats, meaningless for "my own skill's damage"), Skill Additional Damage
# (per-skill flat bonus, not in our data), Guaranteed Crit Ratio and Boss
# Crit/Damage Resistance (opponent-side or class-passive specific).


def _skill_damage_level_index(skill: dict, level: int) -> dict | None:
    """The skills_all.json levels[] entry matching `level` (1-based, same
    counting as the Skill Planner's own manual+bonus level), clamped to
    whatever range the data actually has."""
    levels = skill.get("levels") or []
    if not levels or level < 1:
        return None
    idx = min(level, len(levels)) - 1
    return levels[idx]


def _skill_tooltip_damage_range(skill: dict, level: int) -> tuple[float, float] | None:
    """The game's own real per-level damage preview (min, max) -- None for
    passives (skills_all.json's levels[].minValue is a non-damage internal
    reference id for those, not an actual number) or a skill/level with no
    numeric data."""
    if skill.get("type") != "active":
        return None
    entry = _skill_damage_level_index(skill, level)
    if not entry:
        return None
    try:
        min_v = float(entry.get("minValue"))
        max_v = float(entry.get("maxValue"))
    except (TypeError, ValueError):
        return None
    return min_v, max_v


def _skill_damage_estimate_multiplier(stat_totals: dict[str, float]) -> float:
    """The combined percentage-based amplifier from the player's real
    stats -- see the module comment above this constants block for exactly
    what this does and does NOT model. Same multiplier applies to both a
    skill's min and max tooltip value (User-Wunsch, 2026-08-29: show both
    estimated min AND max, not just max)."""
    def pct(stat_id: str) -> float:
        return stat_totals.get(stat_id, 0.0) / 100.0

    multiplier = 1 + pct(_DMG_STAT_WEAPON_DAMAGE_BOOST)
    multiplier *= 1 + pct(_DMG_STAT_ATTACK_INCREASE)
    multiplier *= 1 + pct(_DMG_STAT_DAMAGE_BOOST) + pct(_DMG_STAT_PVE_DAMAGE_BOOST) + pct(_DMG_STAT_BOSS_DAMAGE_BOOST)
    multiplier *= 1 + pct(_DMG_STAT_CRIT_DAMAGE_BOOST)
    multiplier *= 1 + pct(_DMG_STAT_SMITE)
    multiplier *= 1 + max(pct(_DMG_STAT_FRONT_DAMAGE_BOOST), pct(_DMG_STAT_BACK_DAMAGE_BOOST))
    return multiplier


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


def _make_minus_icon(size: int = 22, color: str = "#e5e7eb") -> QIcon:
    """Draws a minus sign -- same reasoning as _make_plus_icon (used for the
    per-skill level -/+ counter, see _build_skill_description_card)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    thickness = size * 0.2
    painter.drawRoundedRect(QRectF(size * 0.1, (size - thickness) / 2, size * 0.8, thickness), thickness * 0.3, thickness * 0.3)
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


def _make_duplicate_icon(size: int = 22, color: str = "#e5e7eb") -> QIcon:
    """Draws two overlapping squares (back outlined, front filled) -- the
    classic 'copy/duplicate' glyph, for the 'duplicate this Set' action
    (User-Wunsch, 2026-08-28)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(color), size * 0.09))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(QRectF(size * 0.10, size * 0.10, size * 0.56, size * 0.56), size * 0.08, size * 0.08)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(QRectF(size * 0.36, size * 0.36, size * 0.56, size * 0.56), size * 0.08, size * 0.08)
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


def _make_star_icon(size: int = 18, color: str = "#facc15") -> QPixmap:
    """Draws a filled 5-point star -- marks a skill that's on the Priority
    List, on its Skill Description card (User-Wunsch, 2026-08-27)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)

    cx, cy = size / 2, size / 2
    outer_r, inner_r = size * 0.5, size * 0.5 * 0.42
    points = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        r = outer_r if i % 2 == 0 else inner_r
        points.append(QPointF(cx + r * math.cos(angle), cy - r * math.sin(angle)))
    painter.drawPolygon(QPolygonF(points))
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


def _make_compare_icon(size: int = 20, color: str = "#e5e7eb") -> QIcon:
    """Draws two opposing arrows ('vs'/swap glyph) for the 'Build Vergleich'
    tab button."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)

    thickness = size * 0.14
    # Top arrow, pointing right.
    painter.drawRoundedRect(QRectF(size * 0.15, size * 0.28 - thickness / 2, size * 0.55, thickness), thickness * 0.4, thickness * 0.4)
    top_head = QPolygonF([
        QPointF(size * 0.68, size * 0.28 - size * 0.16),
        QPointF(size * 0.88, size * 0.28),
        QPointF(size * 0.68, size * 0.28 + size * 0.16),
    ])
    painter.drawPolygon(top_head)

    # Bottom arrow, pointing left.
    painter.drawRoundedRect(QRectF(size * 0.30, size * 0.72 - thickness / 2, size * 0.55, thickness), thickness * 0.4, thickness * 0.4)
    bottom_head = QPolygonF([
        QPointF(size * 0.32, size * 0.72 - size * 0.16),
        QPointF(size * 0.12, size * 0.72),
        QPointF(size * 0.32, size * 0.72 + size * 0.16),
    ])
    painter.drawPolygon(bottom_head)

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


def _render_skill_description(
    text: str, levels: list[dict] | None = None, level: int = 1,
    estimate_multiplier: float | None = None,
) -> str:
    """Resolves unfilled '{...}' template tokens to a real number from the
    skill's own per-level data when possible (falling back to a plain 'x'),
    and converts newlines to <br> — but keeps the game's own
    <span style="color:..."> tags (only ~4 known safe variants appear in the
    data) so real numbers *and* any remaining 'x' placeholder both keep
    their in-game highlight color when rendered as rich text by
    QLabel/tooltips. Every observed token's field name contains 'Min' or
    'Max' as a literal substring, so that's all we need to check — no need
    to parse out which segment of the token is "the field".

    `estimate_multiplier` (User-Wunsch, 2026-08-29: "die estimated min/max
    Value hinter den Standard-Zahlen in der Skillbeschreibung ... statt
    unter den Skills auf der linken Seite") appends the estimated damage
    range right after the real range, e.g. "161-161 (≈237 ~ 237)" -- only
    on the Max token's substitution (always the later of the two in every
    observed template, "...Min...}-{...Max...}"), so it lands after the
    whole range instead of wedged in the middle of it. See
    _skill_damage_estimate_multiplier's module comment for what this
    multiplier does and does not model."""

    def _sub(match: re.Match) -> str:
        token = match.group(0)
        if levels:
            if "Min" in token:
                value = _level_value(levels, level, "minValue")
                if value is not None and str(value).lstrip("-").isdigit():
                    return str(value)
            elif "Max" in token:
                value = _level_value(levels, level, "maxValue")
                if value is not None and str(value).lstrip("-").isdigit():
                    result = str(value)
                    if estimate_multiplier is not None:
                        min_value = _level_value(levels, level, "minValue")
                        if min_value is not None and str(min_value).lstrip("-").isdigit():
                            est_min = _format_number(float(min_value) * estimate_multiplier)
                            est_max = _format_number(float(value) * estimate_multiplier)
                            result += f" (≈{est_min} ~ {est_max})"
                    return result
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


class _SkillPickerListWidget(QListWidget):
    """QListWidget with a hover-tracked signal for SkillPickerDialog's
    tooltip (User-Wunsch, 2026-08-28: "wär es geil, wenn man hier ein
    Tooltip hat"). Only re-emits when the hovered item actually CHANGES,
    not on every pixel of mouse movement -- same fix already needed for
    DaevanionBoardCanvas's own hover tooltip, which caused Windows
    layered-window redraw spam when it re-showed/repositioned on every
    mouseMoveEvent instead of only on a real change."""

    itemHoverChanged = Signal(object)  # QListWidgetItem or None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._hovered_item: QListWidgetItem | None = None

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        item = self.itemAt(event.position().toPoint())
        if item is not self._hovered_item:
            self._hovered_item = item
            self.itemHoverChanged.emit(item)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if self._hovered_item is not None:
            self._hovered_item = None
            self.itemHoverChanged.emit(None)


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
        self._tooltip = SkillInfoTooltip(self)
        self.finished.connect(lambda _result: self._tooltip.hide())

        layout = QVBoxLayout(self)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_t("arm_search_placeholder"))
        self.search_input.textChanged.connect(self._refresh_list)
        layout.addWidget(self.search_input)

        self.list_widget = _SkillPickerListWidget()
        self.list_widget.setIconSize(QSize(28, 28))
        self.list_widget.itemDoubleClicked.connect(self._accept_current)
        self.list_widget.itemHoverChanged.connect(self._on_item_hover)
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

    def _on_item_hover(self, item: QListWidgetItem | None):
        if item is None:
            self._tooltip.hide()
            return
        skill = item.data(Qt.UserRole)
        if not skill:
            self._tooltip.hide()
            return
        self._tooltip.set_skill(skill)
        self._tooltip.show_at(QCursor.pos())

    def _accept_current(self):
        current = self.list_widget.currentItem()
        if current is None:
            return
        self.selected_skill = current.data(Qt.UserRole)
        self.accept()


class ArcanaSkillSlotDialog(QDialog):
    """Manual skill+level picker for one Sets-tab Arcana card slot (User-
    Wunsch, 2026-08-29: "Jede der 4 Skill-Zeilen einzeln anklickbar ...
    Raritaet waehlbar, Budget passt sich an"). `pool` is already narrowed
    by the caller to this card type's real class skill pool minus whatever
    the OTHER 3 slots on this same card already use. `remaining_budget` is
    the card's shared grade budget (_ARCANA_GRADE_MAX_LEVEL) still unspent
    by those other 3 slots -- NOT counting this slot's own current spend,
    which the caller already excluded so re-picking this same skill can
    still reach back up to wherever it was."""

    def __init__(self, pool: list[dict], remaining_budget: int, current_entry: dict | None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle(_t("arm_choose_skill_title"))
        self.resize(360, 480)
        self.result_entry: dict | None = current_entry
        self._pool = pool
        self._remaining_budget = remaining_budget
        self._selected_skill: dict | None = None
        self._level = _ARCANA_SKILL_BASELINE
        if current_entry:
            for s in pool:
                if s.get("id") == current_entry.get("skill_id"):
                    self._selected_skill = s
                    self._level = current_entry.get("level", _ARCANA_SKILL_BASELINE)
                    break

        layout = QVBoxLayout(self)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_t("arm_search_placeholder"))
        self.search_input.textChanged.connect(self._refresh_list)
        layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(28, 28))
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget, 1)

        level_row = QHBoxLayout()
        level_row.addStretch()
        self._minus_btn = QPushButton()
        self._minus_btn.setObjectName("SkillLevelStepBtn")
        self._minus_btn.setIcon(_make_minus_icon(16))
        self._minus_btn.setIconSize(QSize(14, 14))
        self._minus_btn.setFixedSize(26, 26)
        self._minus_btn.setCursor(Qt.PointingHandCursor)
        self._minus_btn.clicked.connect(lambda: self._change_level(-1))
        level_row.addWidget(self._minus_btn)
        self._level_label = QLabel()
        self._level_label.setAlignment(Qt.AlignCenter)
        self._level_label.setFixedWidth(34)
        level_row.addWidget(self._level_label)
        self._plus_btn = QPushButton()
        self._plus_btn.setObjectName("SkillLevelStepBtn")
        self._plus_btn.setIcon(_make_plus_icon(16))
        self._plus_btn.setIconSize(QSize(14, 14))
        self._plus_btn.setFixedSize(26, 26)
        self._plus_btn.setCursor(Qt.PointingHandCursor)
        self._plus_btn.clicked.connect(lambda: self._change_level(1))
        level_row.addWidget(self._plus_btn)
        level_row.addStretch()
        layout.addLayout(level_row)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton(_t("arm_clear_slot_tooltip"))
        clear_btn.setObjectName("secondaryButton")
        clear_btn.clicked.connect(self._clear_and_accept)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        choose_btn = QPushButton(_t("arm_select_btn"))
        choose_btn.setObjectName("primaryButton")
        choose_btn.clicked.connect(self._accept_current)
        btn_row.addWidget(choose_btn)
        layout.addLayout(btn_row)

        self._refresh_list()
        self._update_level_controls()

    def _refresh_list(self):
        # Grouped by Active/Passive with the same color convention used
        # everywhere else in the app (_SKILL_TYPE_COLORS) -- User-Wunsch,
        # 2026-08-29, live screenshot: "in der Skillauswahl waere die
        # Unterteilung wieder mit Aktive und Passive und farblich gut".
        # Only bothers with section headers when the pool actually mixes
        # both types (Chalice/Scales, _ARCANA_LORD_CATEGORY == "both") --
        # a pure-Active or pure-Passive card type's pool is already
        # uniform, a lone header there would just be noise.
        query = self.search_input.text().strip().lower()
        self.list_widget.clear()
        matched = [s for s in self._pool if not query or query in s.get("name", "").lower()]
        types_present = {s.get("type") for s in matched}
        show_headers = len(types_present & {"active", "passive"}) > 1

        def add_skill_item(skill: dict):
            list_item = QListWidgetItem(skill.get("name", ""))
            icon = _skill_icon(skill)
            if icon:
                list_item.setIcon(icon)
            list_item.setData(Qt.UserRole, skill)
            color = _SKILL_TYPE_COLORS.get(skill.get("type", ""), "#e5e7eb")
            list_item.setForeground(QColor(color))
            if self._selected_skill and skill.get("id") == self._selected_skill.get("id"):
                list_item.setSelected(True)
            self.list_widget.addItem(list_item)

        def add_header(skill_type: str):
            # A plain colored QListWidgetItem can't have its own border,
            # so this is a real widget row instead (User-Wunsch, 2026-08-
            # 29, live screenshot with an ASCII sketch: "Active" followed
            # by a thin grey divider line under the title) -- same
            # setItemWidget pattern already used elsewhere in this file
            # for tile-style rows.
            header_item = QListWidgetItem()
            header_item.setFlags(Qt.NoItemFlags)
            widget = QWidget()
            # Fixed height instead of trusting widget.sizeHint() (User-
            # reported, 2026-08-29: title almost clipped away) -- a
            # freshly-built widget's sizeHint() can come back too small
            # before the label's stylesheet font has actually been
            # resolved, undersizing the row the list then allocates.
            widget.setFixedHeight(32)
            col = QVBoxLayout(widget)
            col.setContentsMargins(6, 8, 6, 4)
            col.setSpacing(4)
            label = QLabel(skill_type.upper())
            color = _SKILL_TYPE_COLORS.get(skill_type, "#94a3b8")
            label.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 11px;")
            col.addWidget(label)
            divider = QFrame()
            divider.setFrameShape(QFrame.HLine)
            divider.setFixedHeight(1)
            divider.setStyleSheet("background-color: rgba(148, 163, 184, 0.25); border: none;")
            col.addWidget(divider)
            header_item.setSizeHint(QSize(widget.sizeHint().width(), 32))
            self.list_widget.addItem(header_item)
            self.list_widget.setItemWidget(header_item, widget)

        if show_headers:
            for skill_type in ("active", "passive"):
                group = [s for s in matched if s.get("type") == skill_type]
                if not group:
                    continue
                add_header(skill_type)
                for skill in group:
                    add_skill_item(skill)
        else:
            for skill in matched:
                add_skill_item(skill)

    def _on_item_clicked(self, item: QListWidgetItem):
        skill = item.data(Qt.UserRole)
        if not skill:
            return
        if not self._selected_skill or skill.get("id") != self._selected_skill.get("id"):
            self._selected_skill = skill
            self._level = _ARCANA_SKILL_BASELINE
        self._update_level_controls()

    def _max_level(self) -> int:
        return min(_ARCANA_PER_SKILL_CAP, _ARCANA_SKILL_BASELINE + self._remaining_budget)

    def _change_level(self, delta: int):
        if not self._selected_skill:
            return
        self._level = max(_ARCANA_SKILL_BASELINE, min(self._max_level(), self._level + delta))
        self._update_level_controls()

    def _update_level_controls(self):
        has_skill = self._selected_skill is not None
        self._level_label.setText(f"+{self._level}" if has_skill else "—")
        self._minus_btn.setEnabled(has_skill and self._level > _ARCANA_SKILL_BASELINE)
        self._plus_btn.setEnabled(has_skill and self._level < self._max_level())

    def _accept_current(self):
        if not self._selected_skill:
            self.reject()
            return
        self.result_entry = {"skill_id": self._selected_skill["id"], "level": self._level}
        self.accept()

    def _clear_and_accept(self):
        self.result_entry = None
        self.accept()


class ArcanaCardThemeDialog(QDialog):
    """Manual Set/Card picker for one Sets-tab card slot (User-Wunsch,
    2026-08-29: "Hier fehlt noch die Option, Karte und Set zu waehlen").
    Only the currently-active Season themes (_ARCANA_ACTIVE_THEMES) that
    actually have an entry for this card type are offered -- the same
    theme+card_type -> Lord/icon lookup the Information tab and the
    Calculator both already use (_arcana_theme_map)."""

    def __init__(self, options: list[tuple[str, dict]], current_theme: str | None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle(_t("arm_arcana_choose_set_title"))
        self.resize(320, 300)
        self.result_theme: str | None = current_theme

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        for theme_name, entry in options:
            label = f"{theme_name} — {entry['lord']}" if entry.get("lord") else theme_name
            list_item = QListWidgetItem(label)
            list_item.setData(Qt.UserRole, theme_name)
            self.list_widget.addItem(list_item)
            if theme_name == current_theme:
                list_item.setSelected(True)
                self.list_widget.setCurrentItem(list_item)
        self.list_widget.itemDoubleClicked.connect(lambda _i: self._accept_current())
        layout.addWidget(self.list_widget, 1)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton(_t("arm_clear_slot_tooltip"))
        clear_btn.setObjectName("secondaryButton")
        clear_btn.clicked.connect(self._clear_and_accept)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        select_btn = QPushButton(_t("arm_select_btn"))
        select_btn.setObjectName("primaryButton")
        select_btn.clicked.connect(self._accept_current)
        btn_row.addWidget(select_btn)
        layout.addLayout(btn_row)

    def _accept_current(self):
        current = self.list_widget.currentItem()
        if current is None:
            self.reject()
            return
        self.result_theme = current.data(Qt.UserRole)
        self.accept()

    def _clear_and_accept(self):
        self.result_theme = None
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

# The first Epic-grade crafted tier (User-Wunsch, 2026-08-27: "jetzt sollten
# wir einmal bei Crafting die Epischen rezepte hinzufügen, denn Derzeit haben
# wir nur die Unique rezepte drin") -- a genuinely SEPARATE root from
# RACE_TIER_ROOT above, not its continuation: verified in recipes_all.json
# that "Noble/Horned Dragon Lord Ring" craft from "Artisan's Splendent
# Sapphire Ring" + Balaur materials, not from any Splendent Obsidian/Crimson
# Dragon Lord item, so _ordered_tier_chain's Transfer-hop BFS from
# RACE_TIER_ROOT can never reach it on its own. Race resolved via the
# recipe's own input item ID for that shared display name ("Artisan's
# Splendent Sapphire Ring" is id 310330013 with qualificationRace "light" for
# the Noble recipe, id 310330014 "dark" for the Horned recipe -- light/dark
# are Elyos/Asmodae, same convention confirmed elsewhere via Abyss Gear).
# "Splendent Noble/Horned Dragon Lord X" is a bonus-chance combo output of
# that SAME recipe (learnType=="combo", empty inputs), not a further Transfer
# hop, so it's listed directly here as a fixed 2nd entry rather than
# discovered via BFS. Genesis/Nemesis Dragon Lord (the next Epic tier up --
# same stats as each other, higher than Noble/Horned) exist in items_all.json
# but have ZERO recipes anywhere in recipes_all.json (checked 2026-08-27) --
# not actually craftable with what's currently scraped, so intentionally left
# out; add once a real recipe for either shows up in a data refresh.
RACE_EPIC_TIER_ROOT = {"Elyos": "Noble Dragon Lord", "Asmodae": "Horned Dragon Lord"}

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
    # Armor split into one category per real piece (User-Wunsch, 2026-08-27:
    # "Jedes Rüstungsteil hat eine eigene Prio Liste" -- the guide gives a
    # genuinely different priority per piece), each reusing its existing
    # SLOT_LAYOUT label key rather than new ones.
    ("helmet", "arm_slot_helmet", ["Helmet"]),
    ("shoulder", "arm_slot_shoulder", ["Shoulder"]),
    ("torso", "arm_slot_torso", ["Torso"]),
    ("gloves", "arm_slot_gloves", ["Gloves"]),
    ("pants", "arm_slot_pants", ["Pants"]),
    ("boots", "arm_slot_boots", ["Boots"]),
    # Split from one combined "jewelry" tab (User-Wunsch, 2026-08-27, after
    # the user's own guide showed Rings need a fundamentally different
    # priority -- "Active Skill 1-6 > Attack" -- from Earring/Necklace's
    # "Attack > Accuracy > Critical Hit > Passive Skills") -- Ring is also
    # the only one offering an Active skill option (_ACTIVE_SUBSKILL_SLOT_
    # CATEGORIES: "Unterschied zwischen Ring und Ohrring -> Aktive und
    # passive Skills"), so this split also removes the old active+passive
    # skill-type ambiguity for free. Amulet dropped entirely (User-Wunsch:
    # "Amulet kannst du rauslassen - hat nur static Werte") -- confirmed all
    # 8 Amulet items in the catalog have subStatRandom=False, nothing to
    # ever prioritize. Quick Select's own equip-slot grouping
    # (_QUICK_GEAR_CATEGORY_GROUPS) stays combined as "Jewelry" -- explicitly
    # NOT part of this split ("nur bei der Quickslot kann das gerne weiterhin
    # unter 'Schmuck' zusammengefasst werden").
    ("ring", "arm_category_ring", ["Ring1", "Ring2"]),
    ("jewelry", "arm_category_earring_necklace", ["Earring1", "Earring2", "Necklace"]),
    ("bracelet", "arm_category_bracelet", ["Bracelet1", "Bracelet2"]),
]
_SLOT_TO_STAT_CATEGORY: dict[str, str] = {
    slot_id: key for key, _, slots in _STAT_PRIORITY_CATEGORIES for slot_id in slots
}
# Which of the 3 top-level group buttons (User-Wunsch, 2026-08-27: "Wir
# machen 3 Buttons ... Waffe/Guard, Rüstung, Schmuck ... jedes Teil separat
# via Reiter") each category tab lives under, and in what order within that
# group. A group with only one category (Weapon/Guard) shows that
# category's rank editor directly instead of nesting a redundant single-tab
# QTabWidget inside the group page.
_STAT_PRIORITY_GROUPS: list[tuple[str, str, list[str]]] = [
    ("weapon_guard", "arm_category_weapon", ["weapon"]),
    ("armor", "arm_category_armor", ["helmet", "shoulder", "torso", "gloves", "pants", "boots"]),
    ("jewelry", "arm_category_jewelry", ["ring", "jewelry", "bracelet"]),
]
# Which skill-option type (see _ACTIVE_SUBSKILL_SLOT_CATEGORIES) applies to
# each Stat-Priority-Editor category tab -- unambiguous now that Ring has
# its own tab, split from "jewelry" (Earring/Necklace). Bracelet has none at
# all: real data confirms subSkillCountMax is always 0 across every
# Bracelet in the catalog (checked all 21, User-Wunsch, 2026-08-27: "Hier
# zeigen Bracelets skills an - bitte korrigieren") -- unlike weapon/armor/
# ring/jewelry, where subSkillCountMax mirrors subStatCount.
_STAT_PRIORITY_CATEGORY_SKILL_TYPES: dict[str, list[str]] = {
    "weapon": ["active"], "ring": ["active"], "jewelry": ["passive"],
    "helmet": ["passive"], "shoulder": ["passive"], "torso": ["passive"],
    "gloves": ["passive"], "pants": ["passive"], "boots": ["passive"],
}

# Overrides the dropdown's default frequency order (compute_stat_priority_
# options.py's "most common on real items first") for categories where the
# guide gives an explicit preference instead (User-Wunsch, 2026-08-27:
# "die Reihenfolge der Auswahl anhand meines Guides bestimmen"). Guide:
# "Bracelet priority: top 4 = Wisdom, Time, Illusion, Destruction; then
# Death, Freedom, Justice" -- doesn't rank Life/Destiny/Space, which fall
# back to the default frequency order after these 7, same as any category
# without an override at all.
_STAT_PRIORITY_CATEGORY_ORDER_OVERRIDE: dict[str, list[str]] = {
    "bracelet": [
        "Wisdom [Lumiel]", "Time [Siel]", "Illusion [Kaisinel]", "Destruction [Zikel]",
        "Death [Triniel]", "Freedom [Vaizel]", "Justice [Nezekan]",
    ],
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
# Names/casing must match the real catalog exactly (not the guide's own
# prose wording, e.g. "Attack increase"/"Move Speed", not "Attack Increase"/
# "Movement Speed") -- the editor's dropdown restore (QComboBox.findData) is
# an exact-string lookup, unlike the case-insensitive matching
# _pick_priority_substats uses for the real auto-pick, so a wording
# mismatch here silently resets to "— empty —" in the editor even though
# auto-pick itself would have matched fine.
_DEFAULT_STAT_PRIORITY_BY_CATEGORY: dict[str, list[str]] = {
    "weapon": ["Weapon Damage Boost", "Combat Speed", "Damage Boost", "Might", "Precision", "Attack", "Multi-hit Chance"],
    # Per-piece armor priorities straight from the guide's detailed
    # per-slot breakdown (User-Wunsch, 2026-08-27: "Jedes Rüstungsteil hat
    # eine eigene Prio Liste"). "Passive Skills" (every guide line's last
    # entry) isn't a literal matchable name -- whatever ranks remain after
    # these already get filled from the player's own Passive Skill Priority
    # List automatically (see _apply_quick_substats), no explicit entry
    # needed, same reasoning as Jewelry/Ring below.
    "helmet": ["Attack increase", "Smite", "Attack", "Endurance", "Incoming Heal"],
    "shoulder": ["Critical Damage Boost", "Attack", "Endurance", "Defense increase", "Accuracy", "Critical Hit"],
    "torso": ["Damage Boost", "Attack", "Endurance", "Defense increase", "Accuracy", "Critical Hit"],
    "gloves": ["Combat Speed", "Attack", "Perfect Chance", "Defense increase", "Accuracy", "Critical Hit"],
    "pants": ["Damage Tolerance", "Attack increase", "Attack", "Perfect Chance", "Endurance"],
    "boots": ["Move Speed", "Attack", "Perfect Chance", "Defense increase", "Accuracy", "Critical Hit"],
    # Guide: "Earrings & Necklace: Attack > Accuracy > Critical Hit >
    # Passive Skills" -- the trailing "Passive Skills" isn't a literal
    # matchable name (no fixed one is universal/class-agnostic), so it's
    # left off here; whatever substat slots remain after these 3 already
    # get filled from the player's own Passive Skill Priority List
    # automatically (see _apply_quick_substats), no explicit entry needed.
    "jewelry": ["Attack", "Accuracy", "Critical Hit"],
    # Guide: "Rings: Active Skill 1-6 (in slot order) > Attack" -- only the
    # "Attack" fallback is a universal name safe to bake in; the 6 Active
    # skill ranks ahead of it are class-/player-specific (same reasoning as
    # Bracelet below) and must be set by hand via the editor, which already
    # lists the player's own Active Skill Priority List first in this tab's
    # dropdown for convenience (see StatPriorityEditorDialog).
    "ring": ["Attack"],
    # Left empty on purpose (User-Wunsch, 2026-08-27): only the fixed,
    # non-random story-reward Bracelet ever rolled Attack/Critical Hit/HP,
    # and its stats can't be changed anyway. Every actually customizable
    # Bracelet (Abyssal and above) only rolls the 10 Deity stats instead
    # (see compute_stat_priority_options.py) -- no real guide backing
    # exists yet for ranking those against each other, so this stays empty
    # rather than pointing at values no Bracelet can ever roll.
    "bracelet": [],
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
            # Epic-tier root -- see RACE_EPIC_TIER_ROOT: not reachable via
            # _ordered_tier_chain's Transfer-hop BFS (different, unconnected
            # recipe chain), so its 2 entries (base + Splendent bonus output)
            # are listed directly instead of discovered.
            epic_root_prefix = RACE_EPIC_TIER_ROOT.get(race)
            if epic_root_prefix:
                for tier in (epic_root_prefix, f"Splendent {epic_root_prefix}"):
                    grade = self._tier_grade(tier)
                    if not grade:
                        continue
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


class StatPriorityEditorDialog(QWidget):
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
    verfügbaren Liste aus").

    A full-panel takeover in equip_view_stack (back-arrow/X, same pattern
    as Build Vergleich) rather than a separate modal popup (User-Wunsch,
    2026-08-28: "Dann können wir im Equip Prio wieder mit Zurück-Pfeil und
    X arbeiten") -- on_done(data_or_None) is called instead of accept()/
    reject() since there's no QDialog result code to report back through."""

    def __init__(
        self, profiles: dict, skill_priority_names: dict[str, list[str]] | None = None,
        on_done: "Callable[[dict | None], None] | None" = None, parent=None,
    ):
        super().__init__(parent)
        self._on_done = on_done
        self._data = copy.deepcopy(profiles)
        self._available_options = _load_stat_priority_options()
        # Skill names from the current class's Priority List, already in
        # that list's rank order -- shown first in each relevant category's
        # dropdown (User-Wunsch, 2026-08-27), ahead of the plain numeric
        # stat names. Weapon/Guard/Ring slots take an Active skill,
        # everything else a Passive one (_ACTIVE_SUBSKILL_SLOT_CATEGORIES);
        # "jewelry" spans both since Ring (Active) and Earring/Necklace/
        # Amulet (Passive) share that one category tab.
        self._skill_priority_names = skill_priority_names or {"active": [], "passive": []}
        self._gear_type = _STAT_PRIORITY_GEAR_TYPES[0]
        self._role = _STAT_PRIORITY_ROLES[0]

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        back_btn = QToolButton()
        back_btn.setObjectName("PanelNavButton")
        back_btn.setIcon(_make_back_icon())
        back_btn.setIconSize(QSize(16, 16))
        back_btn.setFixedSize(32, 32)
        back_btn.setToolTip(_t("arm_back"))
        back_btn.clicked.connect(self._cancel)
        header_row.addWidget(back_btn)

        title = QLabel(_t("arm_stat_priority_editor_title"))
        title.setObjectName("DetailHeader")
        header_row.addWidget(title, 1)

        close_btn = QToolButton()
        close_btn.setObjectName("PanelNavButton")
        close_btn.setIcon(_make_close_icon())
        close_btn.setIconSize(QSize(16, 16))
        close_btn.setFixedSize(32, 32)
        close_btn.setToolTip(_t("arm_close"))
        close_btn.clicked.connect(self._cancel)
        header_row.addWidget(close_btn)
        outer.addLayout(header_row)

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

        # 3 group buttons (User-Wunsch, 2026-08-27: "Wir machen 3 Buttons
        # ... Waffe/Guard, Rüstung, Schmuck ... dann machen wir bei jedem
        # Content jedes Teil separat via Reiter") -- each switches which
        # page of self._group_stack is shown; a group with only one
        # category (Weapon/Guard) shows that category's editor directly,
        # everything else nests a QTabWidget of its categories.
        self._category_combos: dict[str, list[QComboBox]] = {}
        group_row = QHBoxLayout()
        group_row.setSpacing(6)
        group_button_group = QButtonGroup(self)
        group_button_group.setExclusive(True)
        self._group_stack = QStackedWidget()
        for group_idx, (_group_key, group_label, category_keys) in enumerate(_STAT_PRIORITY_GROUPS):
            btn = QPushButton(_t(group_label))
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(group_idx == 0)
            btn.clicked.connect(lambda checked=False, idx=group_idx: self._group_stack.setCurrentIndex(idx))
            group_button_group.addButton(btn)
            group_row.addWidget(btn)

            category_lookup = {key: (label, slots) for key, label, slots in _STAT_PRIORITY_CATEGORIES}
            if len(category_keys) == 1:
                page = self._build_stat_priority_category_widget(category_keys[0])
            else:
                page = QTabWidget()
                for cat_key in category_keys:
                    label_key, _slots = category_lookup[cat_key]
                    # "&" is a Qt mnemonic marker in tab/button text (see
                    # the same fix for "Utility & Recovery" elsewhere) --
                    # escaped so "Earrings & Necklace" doesn't render as
                    # "Earrings Necklace" with a hidden underline.
                    page.addTab(self._build_stat_priority_category_widget(cat_key), _t(label_key).replace("&", "&&"))
            self._group_stack.addWidget(page)
        group_row.addStretch(1)
        outer.addLayout(group_row)
        outer.addWidget(self._group_stack, 1)

        self._load_profile_into_combos()

        button_row = QHBoxLayout()
        reset_btn = QPushButton(_t("arm_reset_to_default"))
        reset_btn.clicked.connect(self._on_reset_current_profile)
        button_row.addWidget(reset_btn)
        button_row.addStretch(1)
        cancel_btn = QPushButton(_t("arm_cancel"))
        cancel_btn.clicked.connect(self._cancel)
        button_row.addWidget(cancel_btn)
        save_btn = QPushButton(_t("arm_save"))
        save_btn.clicked.connect(self._on_save)
        button_row.addWidget(save_btn)
        outer.addLayout(button_row)

    def _build_stat_priority_category_widget(self, key: str) -> QWidget:
        """One category's scrollable rank editor -- extracted so it can be
        embedded either directly (Weapon/Guard, the only 1-category group)
        or inside a group's inner QTabWidget (Armor's 6 pieces, Jewelry's
        Ring/Earring+Necklace/Bracelet)."""
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
        tab_scroll = QScrollArea()
        tab_scroll.setWidgetResizable(True)
        tab_scroll.setFrameShape(QFrame.NoFrame)
        tab_scroll.setWidget(tab)
        return tab_scroll

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
        # Skill names from the Priority List come first, already in that
        # list's rank order, ahead of the plain numeric stat names --
        # User-Wunsch, 2026-08-27. Colored by skill type (same convention
        # as the Skill Description cards' type label, _SKILL_TYPE_COLORS)
        # so they visually stand out from plain stat names in the dropdown
        # (User-Wunsch, 2026-08-27: "die Skills mit Farben markieren ...
        # Schriftart der Farbe der Skillart anpassen").
        skill_names: list[str] = []
        skill_name_colors: dict[str, str] = {}
        for skill_type in _STAT_PRIORITY_CATEGORY_SKILL_TYPES.get(key, []):
            color = _SKILL_TYPE_COLORS.get(skill_type)
            for name in self._skill_priority_names.get(skill_type, []):
                if name not in skill_names:
                    skill_names.append(name)
                    if color:
                        skill_name_colors[name] = color
        # Guide-ordered names next (only the ones actually in this
        # category's real option pool), then whatever's left in the
        # default frequency order.
        stat_pool = self._available_options.get(key, [])
        guide_order = [n for n in _STAT_PRIORITY_CATEGORY_ORDER_OVERRIDE.get(key, []) if n in stat_pool]
        already_placed = set(skill_names) | set(guide_order)
        options = skill_names + guide_order + [n for n in stat_pool if n not in already_placed]
        for i, combo in enumerate(combos):
            others = {selections[j] for j in range(len(combos)) if j != i and selections[j]}
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(_t("arm_empty_option"), "")
            for name in options:
                if name not in others:
                    combo.addItem(name, name)
                    color = skill_name_colors.get(name)
                    if color:
                        combo.setItemData(combo.count() - 1, QColor(color), Qt.ForegroundRole)
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

    def _cancel(self):
        if self._on_done:
            self._on_done(None)

    def _on_save(self):
        self._flush_combos_into_data()
        if self._on_done:
            self._on_done(self._data)


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


# ── Daevanion Board (2026-08-28) ─────────────────────────────────────────
# Ported from the approved browser mockup (see [[project_daevanion_board_
# port]] in memory for the full requirements list this was checked against).
# Two variants per board, same ids overlapping between them (same game,
# same internal numbering, different per-variant content) -- "_s" (Start)
# is Global's real current content (48 boards: 6 deities x 8 classes, no
# Fighter -- source: talentbuilds.com), "_a" (Advanced) is KR/TW's post-
# Eltnen/Morheim content (72 boards: 8 deities x 9 classes -- source:
# questlog.gg). Only "_s" ships; flipping _DAEVANION_DEV_MODE to True is a
# local dev-only switch, never shipped as True (User-Wunsch, 2026-08-28).
DAEVANION_START_PATH = _BUNDLE_DIR / "data" / "daevanion_boards_s.json"
DAEVANION_ADVANCED_PATH = _BUNDLE_DIR / "data" / "daevanion_boards_a.json"
_DAEVANION_DEV_MODE = False

_DAEVANION_GRID_SIZE = 15
_DAEVANION_GRADE_HEX = {
    "start": "#22d3ee", "common": GRADE_COLORS["Common"], "rare": GRADE_COLORS["Rare"],
    "legend": GRADE_COLORS["Legend"], "unique": GRADE_COLORS["Unique"],
}
_DAEVANION_GRADE_LABEL = {"start": "Start", "common": "Common", "rare": "Rare", "legend": "Legend", "unique": "Unique"}

# Real per-grade node-frame art (see fetch_daevanion_node_sprites.py) --
# User-found real CDN path, 2026-08-28: cdn.questlog.gg/aion-2/assets/
# images-test/ (questlog.gg/assets/ , tried earlier that same day, serves
# an identical SPA-fallback image for every filename -- a dead end).
# "Disabled" is the locked/unpicked look; Start has no disabled variant
# (always auto-active). One shared cache since the art is grade-only, not
# per-board/per-variant.
_DAEVANION_SPRITE_DIR = _BUNDLE_DIR / "assets" / "daevanion_nodes"
_DAEVANION_SPRITE_GRADE_FILE = {"common": "Common", "rare": "Rare", "legend": "Legend", "unique": "Unique"}
_daevanion_sprite_cache: dict[str, "QPixmap"] = {}


def _daevanion_node_sprite(grade: str, enabled: bool, size: int) -> "QPixmap | None":
    if grade == "start":
        filename = "UT_FWindow_Daevanion_Node_Start_Sprite.webp"
    else:
        tier = _DAEVANION_SPRITE_GRADE_FILE.get(grade)
        if not tier:
            return None
        suffix = "Sprite" if enabled else "Disabled_Sprite"
        filename = f"UT_FWindow_Daevanion_Node_{tier}_{suffix}.webp"
    cache_key = f"{filename}:{size}"
    if cache_key not in _daevanion_sprite_cache:
        path = _DAEVANION_SPRITE_DIR / filename
        pix = QPixmap(str(path)) if path.exists() else QPixmap()
        if not pix.isNull():
            pix = pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        _daevanion_sprite_cache[cache_key] = pix
    pix = _daevanion_sprite_cache[cache_key]
    return pix if not pix.isNull() else None


def _load_daevanion_raw(path: Path) -> dict:
    if not path.exists():
        return {"boards": [], "nodes": []}
    return json.loads(path.read_text(encoding="utf-8"))


_daevanion_variant_cache: dict[str, dict] = {}


# "fighter" only exists in the "_a" data (KR/TW) -- almost certainly the
# app's own "Brawler" class (listed in AION2_CLASSES but deliberately kept
# out of AION2_ACTIVE_CLASSES since it isn't released/selectable yet, see
# [[project_daevanion_board_port]]). character_class_combo already can
# never select it, so this is belt-and-suspenders: keeps that exclusion
# explicit within the Daevanion feature itself rather than relying only on
# the unrelated shared class list (User-Wunsch, 2026-08-28: "kann man den
# Brawler genauso erstmal inaktiv setzen, bis dieser released wird").
_DAEVANION_DISABLED_CLASSES = {"fighter"}


def _daevanion_variant(variant: str) -> dict:
    """Lazily builds+caches the per-variant lookup structures (board list,
    class ids, deity orders, grid-by-board, node-by-id) -- mirrors the
    browser mockup's SEASON_BUILD exactly, kept fully separate per variant
    since board/node ids overlap between "s" and "a"."""
    if variant not in _daevanion_variant_cache:
        path = DAEVANION_START_PATH if variant == "s" else DAEVANION_ADVANCED_PATH
        raw = _load_daevanion_raw(path)
        boards = [b for b in raw.get("boards", []) if b["classId"] not in _DAEVANION_DISABLED_CLASSES]
        allowed_board_ids = {b["id"] for b in boards}
        nodes = [n for n in raw.get("nodes", []) if n["b"] in allowed_board_ids]
        board_by_class_order = {(b["classId"], b["order"]): b for b in boards}
        nodes_by_board: dict[str, dict[tuple[int, int], dict]] = {}
        node_by_id: dict[str, dict] = {}
        for n in nodes:
            nodes_by_board.setdefault(n["b"], {})[(n["r"], n["c"])] = n
            node_by_id[n["id"]] = n
        _daevanion_variant_cache[variant] = {
            "boards": boards,
            "class_ids": sorted({b["classId"] for b in boards}),
            "deity_orders": sorted({b["order"] for b in boards}),
            "board_by_class_order": board_by_class_order,
            "nodes_by_board": nodes_by_board,
            "node_by_id": node_by_id,
        }
    return _daevanion_variant_cache[variant]


def _daevanion_neighbors(r: int, c: int) -> list[tuple[int, int]]:
    return [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]


def _daevanion_is_reachable(node: dict, grid: dict, active: set) -> bool:
    """A node with no real stat/skill value can never bridge two others --
    only nodes with a real value connect to each other (User-Wunsch,
    2026-08-28: "Es können zum verbinden nur Felder genutzt werden, die
    Werte beinhalten")."""
    if node["id"] in active:
        return True
    for rc in _daevanion_neighbors(node["r"], node["c"]):
        nb = grid.get(rc)
        if nb and nb["g"] != "empty" and nb["id"] in active:
            return True
    return False


def _daevanion_total_cost(grid: dict) -> int:
    return sum(n["cost"] for n in grid.values())


def _daevanion_spent_cost(active: set, node_by_id: dict) -> int:
    return sum(node_by_id[nid]["cost"] for nid in active if nid in node_by_id)


_DAEVANION_MP_NAMES = {"mpmax", "Max MP"}  # "a" data uses the lowercase questlog code, "s" data the plain name


def _daevanion_node_mp_count(node: dict) -> int:
    return 1 if any(e.get("t") == "s" and e.get("n") in _DAEVANION_MP_NAMES for e in node.get("e") or []) else 0


def _daevanion_shortest_from_tree(grid: dict, tree: set, node_by_id: dict):
    """Multi-source Dijkstra from every node already in `tree` (distance
    (0, 0)) -- distance is (points, mpNodeCount), Python tuples already
    compare lexicographically: cheapest point cost wins outright, ties
    broken toward fewer Max MP nodes crossed (User-Wunsch, 2026-08-28).
    "empty" cells are skipped entirely, never traversable."""
    inf = (float("inf"), float("inf"))
    dist = {n["id"]: ((0, 0) if n["id"] in tree else inf) for n in grid.values()}
    prev: dict[str, str] = {}
    visited: set[str] = set()
    while len(visited) < len(dist):
        best_id, best_d = None, inf
        for nid, d in dist.items():
            if nid not in visited and d < best_d:
                best_d, best_id = d, nid
        if best_id is None:
            break
        visited.add(best_id)
        n = node_by_id[best_id]
        for rc in _daevanion_neighbors(n["r"], n["c"]):
            nb = grid.get(rc)
            if not nb or nb["g"] == "empty" or nb["id"] in visited:
                continue
            in_tree = nb["id"] in tree
            nd = (best_d[0] + (0 if in_tree else nb["cost"]), best_d[1] + (0 if in_tree else _daevanion_node_mp_count(nb)))
            if nd < dist[nb["id"]]:
                dist[nb["id"]] = nd
                prev[nb["id"]] = best_id
    return dist, prev


def _daevanion_path_nodes_to_add(prev: dict, target_id: str, tree: set) -> list[str]:
    chain = []
    cur = target_id
    while cur is not None:
        chain.append(cur)
        if cur in tree:
            break
        cur = prev.get(cur)
    return chain


def _daevanion_compute_auto_route(grid: dict, node_by_id: dict, wanted_ids: set, start_id: str) -> dict:
    """Greedy Steiner-tree heuristic (identical to the approved browser
    mockup): repeatedly connects whichever wanted node is currently
    cheapest to reach from the tree built so far, until every wanted node
    is connected or the board's point cap runs out."""
    tree = {start_id}
    cap = _daevanion_total_cost(grid)
    spent = 0
    remaining = set(wanted_ids) - {start_id}
    included: set[str] = set()
    skipped: set[str] = set()
    while remaining:
        dist, prev = _daevanion_shortest_from_tree(grid, tree, node_by_id)
        best_id, best_d = None, (float("inf"), float("inf"))
        for nid in remaining:
            d = dist.get(nid, (float("inf"), float("inf")))
            if d < best_d:
                best_d, best_id = d, nid
        if best_id is None or best_d[0] == float("inf") or spent + best_d[0] > cap:
            skipped |= remaining
            break
        for nid in _daevanion_path_nodes_to_add(prev, best_id, tree):
            if nid not in tree:
                tree.add(nid)
                spent += node_by_id[nid]["cost"]
        included.add(best_id)
        remaining.discard(best_id)
    return {"tree": tree, "included": included, "skipped": skipped, "spent": spent, "cap": cap}


def _daevanion_stat_key(raw: str) -> str:
    """Canonical lookup key for a stat_name -- strips everything but
    letters/digits and lowercases, so questlog's "_a" data (lowercase
    joined codes like "fixingdamage") and talentbuilds' "_s" data (spaced
    "Attack Bonus" OR un-spaced "PvPAddDamage", both occur -- confirmed via
    the real data, not assumed) all converge on the same key regardless of
    which convention a given raw name happens to use."""
    return re.sub(r"[^a-z0-9]", "", raw.lower())


# Exhaustive per-stat display labels, keyed by the canonical form above --
# built from the real distinct stat_name values found in BOTH datasets (35
# in "_s", 50 in "_a"), including a few pairs that are almost certainly the
# same real stat under a different internal name between the two sites
# (e.g. "_s"'s "HP"/"Max HP" grade vs "_a"'s "hpmax", both mapped to "Max
# HP"; "_s"'s "Attack Bonus" vs "_a"'s "fixingdamage", both "Attack").
_DAEVANION_STAT_LABELS: dict[str, str] = {
    "hpmax": "Max HP", "hp": "Max HP", "maxhp": "Max HP",
    "mpmax": "Max MP", "mp": "Max MP", "maxmp": "Max MP",
    "fixingdamage": "Attack", "attackbonus": "Attack",
    "defense": "Defense", "defensebonus": "Defense",
    "critical": "Critical Hit", "criticalhit": "Critical Hit",
    "criticalresist": "Critical Resist", "criticalhitresist": "Critical Resist",
    "accuracy": "Accuracy", "block": "Block", "blockpierce": "Block Penetration",
    "evasion": "Evasion", "weapondamage": "Weapon Damage",
    "perfect": "Perfect Chance", "perfectresist": "Perfect Resist",
    "combatspeed": "Combat Speed",
    "restoration": "Restoration", "ignorerestoration": "Ignore Restoration",
    "ironwall": "Iron Wall", "ignoreironwall": "Ignore Iron Wall",
    "damageratio": "Damage Ratio", "defenseratio": "Defense Ratio", "maxhpratio": "Max HP Ratio",
    "cooltimedecrease": "Cooldown Reduction", "cooldowndecrease": "Cooldown Reduction",
    "amplifyalldamage": "Amplify All Damage",
    "amplifycriticaldamage": "Amplify Critical Damage", "decreasecriticaldamage": "Decrease Critical Damage",
    "amplifyweapondamage": "Amplify Weapon Damage", "decreaseweapondamage": "Decrease Weapon Damage",
    "decreasedamage": "Decrease Damage",
    "additionalhitrate": "Additional Hit Rate", "additionalhitresistrate": "Additional Hit Resist",
    "multihitchance": "Multi-hit Chance", "multihitresist": "Multi-hit Resist",
    "abnormalaccuracy": "Abnormal Accuracy", "abnormalresistance": "Abnormal Resistance",
    "damageboost": "Damage Boost", "damagetolerance": "Damage Tolerance",
    "criticaldamageboost": "Critical Damage Boost", "criticaldamagetolerance": "Critical Damage Tolerance",
    "bossattack": "Boss Damage", "bossnpcadddamage": "Boss Damage",
    "bossdefense": "Boss Defense", "bossnpcdefense": "Boss Defense",
    "bossnpcamplifydamage": "Boss Amplify Damage", "bossnpcdecreasedamage": "Boss Decrease Damage",
    "pvpaccuracy": "PvP Accuracy", "pveaccuracy": "PvE Accuracy",
    "pvpevasion": "PvP Evasion", "pveevasion": "PvE Evasion",
    "pvpcritical": "PvP Critical Hit", "pvpcriticalresist": "PvP Critical Resist",
    "pvpadddamage": "PvP Damage", "pvpdamagedefense": "PvP Damage Defense", "pvpdefense": "PvP Damage Defense",
    "pvpdecreasedamage": "PvP Decrease Damage", "pvpamplifydamage": "PvP Amplify Damage",
    "pveattack": "PvE Damage", "pveadddamage": "PvE Damage",
    "pvedamagedefense": "PvE Damage Defense", "pvedefense": "PvE Damage Defense",
    "pvedecreasedamage": "PvE Decrease Damage", "pveamplifydamage": "PvE Amplify Damage",
    "pvedamageboost": "PvE Damage Boost", "pvedamagetolerance": "PvE Damage Tolerance",
}

# Backward-compat alias -- _daevanion_effect_lines/_daevanion_build_node_icons
# used to look this up directly by raw (non-canonicalized) name; now they go
# through _daevanion_stat_label() below instead, which canonicalizes first.
STAT_LABEL_OVERRIDES = _DAEVANION_STAT_LABELS


def _daevanion_stat_label(raw_name: str) -> str:
    return _DAEVANION_STAT_LABELS.get(_daevanion_stat_key(raw_name), raw_name)


def _daevanion_effect_lines(node: dict, class_skills_by_id: dict) -> list[tuple[str, str]]:
    """[(label, value)] pairs for a node's effects -- resolves skill_level
    effects' real name/level against the SAME live skills_all.json lookup
    the rest of the app already uses (class_skills_by_id), falling back to
    whatever name the raw data itself carried (talentbuilds' "_s" data
    embeds one; questlog's "_a" data doesn't)."""
    lines = []
    for e in node.get("e") or []:
        if e.get("t") == "s":
            name = e.get("n") or ""
            label = _daevanion_stat_label(name)
            value = e.get("v")
            lines.append((label, f"{'+' if value and value > 0 else ''}{value}"))
        elif e.get("t") == "k":
            skill_id = str(e.get("skill_id") or "")
            skill = class_skills_by_id.get(skill_id)
            label = skill.get("name") if skill else (e.get("n") or f"Skill #{skill_id}")
            lines.append((label, f"+{e.get('v')} Lvl"))
    return lines


class DaevanionBoardCanvas(QWidget):
    """Paints one board's 15x15 grid and reports clicks/hover -- all
    business logic (which nodes are active/reachable/highlighted, what a
    click should do) lives in the owning DaevanionBoardTab; this widget
    only knows how to draw a grid dict + active/highlighted id sets and
    turn mouse events into (row, col) hits."""

    nodeClicked = Signal(str)
    nodeHovered = Signal(object)  # node dict or None

    _CELL = 30
    _GAP = 3
    _PAD = 10
    _ZOOM_MIN = 0.6
    _ZOOM_MAX = 2.4
    _ZOOM_STEP = 1.12

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid: dict[tuple[int, int], dict] = {}
        self._active: set[str] = set()
        self._highlighted: set[str] = set()
        self._node_icons: dict[str, QPixmap] = {}
        self._id_to_node: dict[str, dict] = {}
        self._hovered_rc: tuple[int, int] | None = None
        self._zoom = 1.0
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self._update_geometry()

    def set_data(self, grid: dict, active: set, highlighted: set, node_icons: dict[str, "QPixmap"]):
        self._grid = grid
        self._active = active
        self._highlighted = highlighted
        self._node_icons = node_icons
        self._id_to_node = {n["id"]: n for n in grid.values()}
        self.update()

    def set_scroll_area(self, scroll_area: "QScrollArea"):
        """So wheelEvent can re-center the viewport on whatever point the
        zoom was centered on -- without this, growing the canvas keeps its
        (0, 0) corner pinned to the viewport's top-left, so zooming in just
        pushes content down/right into empty space instead of filling the
        view (User-Wunsch, 2026-08-28: "von der Mitte aus zoomen ... dass
        das Feld beim Zoomen komplett ausgefüllt wird")."""
        self._scroll_area = scroll_area

    def wheelEvent(self, event):
        """Mouse-wheel zoom, centered on the viewport's current center (or
        the cursor, if the wheel happens over a specific point) so the
        zoomed board keeps filling the visible area instead of drifting
        toward one corner."""
        scroll = getattr(self, "_scroll_area", None)
        anchor_x = anchor_y = None
        if scroll is not None:
            hbar, vbar = scroll.horizontalScrollBar(), scroll.verticalScrollBar()
            viewport_w, viewport_h = scroll.viewport().width(), scroll.viewport().height()
            old_w, old_h = max(1, self.width()), max(1, self.height())
            anchor_x = (hbar.value() + viewport_w / 2) / old_w
            anchor_y = (vbar.value() + viewport_h / 2) / old_h

        factor = self._ZOOM_STEP if event.angleDelta().y() > 0 else 1 / self._ZOOM_STEP
        self._zoom = max(self._ZOOM_MIN, min(self._ZOOM_MAX, self._zoom * factor))
        self._update_geometry()
        self.update()

        if scroll is not None and anchor_x is not None:
            hbar, vbar = scroll.horizontalScrollBar(), scroll.verticalScrollBar()
            viewport_w, viewport_h = scroll.viewport().width(), scroll.viewport().height()
            hbar.setValue(round(anchor_x * self.width() - viewport_w / 2))
            vbar.setValue(round(anchor_y * self.height() - viewport_h / 2))
        event.accept()

    def _update_geometry(self):
        cell = self._CELL * self._zoom
        gap = self._GAP * self._zoom
        pad = self._PAD * self._zoom
        side = round(pad * 2 + _DAEVANION_GRID_SIZE * cell + (_DAEVANION_GRID_SIZE - 1) * gap)
        self.setFixedSize(side, side)

    def _cell_rect(self, r: int, c: int) -> QRectF:
        cell = self._CELL * self._zoom
        gap = self._GAP * self._zoom
        pad = self._PAD * self._zoom
        x = pad + (c - 1) * (cell + gap)
        y = pad + (r - 1) * (cell + gap)
        return QRectF(x, y, cell, cell)

    def _rc_at(self, pos: QPointF) -> tuple[int, int] | None:
        cell = self._CELL * self._zoom
        gap = self._GAP * self._zoom
        pad = self._PAD * self._zoom
        step = cell + gap
        c = int((pos.x() - pad) // step) + 1
        r = int((pos.y() - pad) // step) + 1
        if not (1 <= r <= _DAEVANION_GRID_SIZE and 1 <= c <= _DAEVANION_GRID_SIZE):
            return None
        rect = self._cell_rect(r, c)
        return (r, c) if rect.contains(pos) else None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0b1220"))

        # Connective lines between two active orthogonal neighbors.
        painter.setPen(QPen(QColor(34, 211, 238, 90), max(1.2, 2 * self._zoom)))
        for nid in self._active:
            n = self._id_to_node.get(nid)
            if not n:
                continue
            for rc in [(n["r"] + 1, n["c"]), (n["r"], n["c"] + 1)]:
                nb = self._grid.get(rc)
                if nb and nb["id"] in self._active:
                    a, b = self._cell_rect(n["r"], n["c"]), self._cell_rect(*rc)
                    painter.drawLine(a.center(), b.center())

        icon_side = self._CELL * self._zoom * 0.62
        cell_px = max(1, round(self._CELL * self._zoom))

        for (r, c), n in self._grid.items():
            rect = self._cell_rect(r, c)
            is_active = n["id"] in self._active
            reachable = not is_active and _daevanion_is_reachable(n, self._grid, self._active)
            grade = n["g"]

            if grade != "empty":
                hex_color = _DAEVANION_GRADE_HEX.get(grade, _DAEVANION_GRADE_HEX["common"])
                color = QColor(hex_color)
                # Real per-grade frame art (see fetch_daevanion_node_sprites.py)
                # -- "enabled" look once active, "disabled" (locked) look
                # otherwise; falls back to the old drawn rounded-rect if the
                # asset is somehow missing.
                sprite = _daevanion_node_sprite(grade, is_active, cell_px)
                if sprite:
                    if not (is_active or reachable):
                        painter.setOpacity(0.5)
                    painter.drawPixmap(rect.toRect(), sprite)
                    painter.setOpacity(1.0)
                    if reachable:
                        painter.setPen(QPen(QColor("#4ade80"), 1.4))
                        painter.setBrush(Qt.NoBrush)
                        painter.drawRoundedRect(rect, 8, 8)
                elif is_active:
                    fill = QColor(color)
                    fill.setAlphaF(0.9 if grade == "start" else 0.85)
                    painter.setPen(QPen(QColor("#22d3ee"), 1.5))
                    painter.setBrush(fill)
                    painter.drawRoundedRect(rect, 8, 8)
                else:
                    fill = QColor(color)
                    fill.setAlphaF(0.16 if reachable else 0.06)
                    painter.setBrush(fill)
                    painter.setPen(QPen(QColor("#4ade80") if reachable else QColor(148, 163, 184, 46), 1.4))
                    painter.drawRoundedRect(rect, 8, 8)

                icon = self._node_icons.get(n["id"])
                if icon and not icon.isNull():
                    if not (is_active or reachable):
                        painter.setOpacity(0.5)
                    icon_rect = QRectF(0, 0, icon_side, icon_side)
                    icon_rect.moveCenter(rect.center())
                    painter.drawPixmap(icon_rect.toRect(), icon)
                    painter.setOpacity(1.0)
                elif grade != "start" and not sprite:
                    dot = QColor(color)
                    dot.setAlphaF(0.9 if (is_active or reachable) else 0.35)
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(dot)
                    painter.drawEllipse(rect.center(), 4 * self._zoom, 4 * self._zoom)

            if n["id"] in self._highlighted:
                painter.setPen(QPen(QColor("#fbbf24"), 2.2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 9, 9)

            if self._hovered_rc == (r, c):
                painter.setPen(QPen(QColor("#f8fafc"), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect.adjusted(-1.5, -1.5, 1.5, 1.5), 9, 9)

        painter.end()

    def mouseMoveEvent(self, event):
        rc = self._rc_at(event.position())
        if rc != self._hovered_rc:
            self._hovered_rc = rc
            self.update()
            node = self._grid.get(rc) if rc else None
            self.nodeHovered.emit(node)

    def leaveEvent(self, event):
        self._hovered_rc = None
        self.update()
        self.nodeHovered.emit(None)

    def mousePressEvent(self, event):
        rc = self._rc_at(event.position())
        node = self._grid.get(rc) if rc else None
        if node:
            self.nodeClicked.emit(node["id"])


class _TranslucentCardTooltip(QWidget):
    """Base for floating, semi-transparent detail-card tooltips (rounded
    dark card + drop shadow, native-tooltip window flags so they float
    above everything without stealing focus) -- shared by
    DaevanionNodeTooltip and SkillInfoTooltip so both stay visually
    identical without duplicating the paint/shadow/positioning code
    (User-Wunsch, 2026-08-28, re: the skill tooltip: "gerne ähnlicher
    Aufbau des Tooltips wie beim Daeva Board")."""

    def __init__(self, width: int, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedWidth(width)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 16)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(148, 163, 184, 90), 1))
        painter.setBrush(QColor(15, 22, 38, 235))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 13, 13)
        painter.end()

    def show_at(self, global_pos: QPoint):
        self.adjustSize()
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        x = global_pos.x() + 16
        y = global_pos.y() + 16
        if avail is not None:
            if x + self.width() > avail.right():
                x = global_pos.x() - self.width() - 16
            if y + self.height() > avail.bottom():
                y = global_pos.y() - self.height() - 16
            x = max(avail.left(), x)
            y = max(avail.top(), y)
        self.move(x, y)
        self.show()


class DaevanionNodeTooltip(_TranslucentCardTooltip):
    """Node detail card -- replaces the native QToolTip (User-Wunsch,
    2026-08-28: "Den Tooltip aus der Browservorschau fand ich noch
    schoener") so effects can render as their own mini cards and the
    status line as a colored pill, matching the browser mockup's
    node-tooltip design -- a plain QToolTip's rich-text subset has no
    per-row backgrounds/pills to work with."""

    _STATUS_COLORS = {
        "start": ("#22d3ee", 0.15),
        "active": ("#22d3ee", 0.15),
        "available": ("#4ade80", 0.14),
        "locked": ("#94a3b8", 0.12),
        "no_points": ("#fca5a5", 0.14),
    }

    def __init__(self, parent=None):
        super().__init__(240, parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        self._grade_label = QLabel()
        outer.addWidget(self._grade_label, 0, Qt.AlignLeft)

        self._title_label = QLabel()
        self._title_label.setWordWrap(True)
        self._title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #f1f5f9; background: transparent; border: none;")
        outer.addWidget(self._title_label)

        self._meta_label = QLabel()
        self._meta_label.setWordWrap(True)
        self._meta_label.setStyleSheet(
            "font-size: 12px; color: #94a3b8; background: transparent;"
            "border: none; border-top: 1px solid rgba(148, 163, 184, 60); padding-top: 8px;"
        )
        outer.addWidget(self._meta_label)

        self._effects_container = QWidget()
        self._effects_container.setStyleSheet("background: transparent;")
        self._effects_layout = QVBoxLayout(self._effects_container)
        self._effects_layout.setContentsMargins(0, 0, 0, 0)
        self._effects_layout.setSpacing(6)
        outer.addWidget(self._effects_container)

        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setWordWrap(True)
        outer.addWidget(self._status_label)

    def set_node(
        self,
        name: str,
        grade_label: str,
        grade_hex: str,
        cost: int,
        level: int,
        effect_rows: list[tuple[str, str]],
        status_key: str,
        status_text: str,
    ):
        self._grade_label.setText(grade_label.upper())
        self._grade_label.setStyleSheet(
            "font-size: 10.5px; font-weight: 700; letter-spacing: 1px;"
            "padding: 2px 8px; border-radius: 9px;"
            f"background: {_rgba_str(grade_hex, 0.2)}; color: {grade_hex}; border: none;"
        )
        self._title_label.setText(name)
        self._meta_label.setText(f"Cost: {cost} pt{'s' if cost != 1 else ''} · Required level: {level}")

        while self._effects_layout.count():
            item = self._effects_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for label, value in effect_rows:
            row = QFrame()
            row.setStyleSheet(
                "background: rgba(15, 23, 42, 150); border: 1px solid rgba(148, 163, 184, 50); border-radius: 8px;"
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 8, 10, 8)
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 12px; color: #cbd5e1; background: transparent; border: none;")
            lbl.setWordWrap(True)
            val = QLabel(value)
            val.setStyleSheet("font-size: 12px; font-weight: 700; color: #22d3ee; background: transparent; border: none;")
            row_layout.addWidget(lbl, 1)
            row_layout.addWidget(val, 0)
            self._effects_layout.addWidget(row)

        color, alpha = self._STATUS_COLORS.get(status_key, self._STATUS_COLORS["locked"])
        self._status_label.setText(status_text)
        self._status_label.setStyleSheet(
            "font-size: 12px; font-weight: 600; border-radius: 8px; padding: 8px 10px; border: none;"
            f"background: {_rgba_str(color, alpha)}; color: {color};"
        )

        self.adjustSize()


class SkillInfoTooltip(_TranslucentCardTooltip):
    """Skill detail card for hovering a skill in the Priority List's picker
    dialog (SkillPickerDialog) -- same visual language as
    DaevanionNodeTooltip (User-Wunsch, 2026-08-28: "wär es geil, wenn man
    hier ein Tooltip hat, welcher nochmal die Infos zum Skill anzeigt.
    gerne ähnlicher Aufbau des Tooltips wie beim Daeva Board")."""

    def __init__(self, parent=None):
        super().__init__(260, parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        self._type_label = QLabel()
        outer.addWidget(self._type_label, 0, Qt.AlignLeft)

        self._title_label = QLabel()
        self._title_label.setWordWrap(True)
        self._title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #f1f5f9; background: transparent; border: none;")
        outer.addWidget(self._title_label)

        self._desc_label = QLabel()
        self._desc_label.setWordWrap(True)
        self._desc_label.setTextFormat(Qt.RichText)
        self._desc_label.setStyleSheet("font-size: 12px; color: #cbd5e1; background: transparent; border: none;")
        outer.addWidget(self._desc_label)

        self._stats_label = QLabel()
        self._stats_label.setWordWrap(True)
        self._stats_label.setTextFormat(Qt.RichText)
        self._stats_label.setStyleSheet(
            "font-size: 12px; color: #94a3b8; background: transparent;"
            "border: none; border-top: 1px solid rgba(148, 163, 184, 60); padding-top: 8px;"
        )
        outer.addWidget(self._stats_label)

        # Specialization level breakpoints (User-Wunsch, 2026-08-29: "beim
        # Skillpickerpop bei dem Tooltip fuer die Skills auch die
        # jeweiligen Bonis anzeigen") -- same real per-skill data
        # (skill["specializations"]) the main Skill Planner description
        # panel already renders (_on_skill_description_card_clicked), just
        # not previously shown here in the Priority List's picker tooltip.
        self._specs_label = QLabel()
        self._specs_label.setWordWrap(True)
        self._specs_label.setTextFormat(Qt.RichText)
        self._specs_label.setStyleSheet(
            "font-size: 12px; color: #94a3b8; background: transparent;"
            "border: none; border-top: 1px solid rgba(148, 163, 184, 60); padding-top: 8px;"
        )
        outer.addWidget(self._specs_label)

    def set_skill(self, skill: dict):
        skill_type = skill.get("type", "")
        color = _SKILL_TYPE_COLORS.get(skill_type, "#94a3b8")
        self._type_label.setText(skill_type.upper())
        self._type_label.setStyleSheet(
            "font-size: 10.5px; font-weight: 700; letter-spacing: 1px;"
            "padding: 2px 8px; border-radius: 9px;"
            f"background: {_rgba_str(color, 0.2)}; color: {color}; border: none;"
        )
        self._title_label.setText(skill.get("name", ""))

        desc = _render_skill_description(skill.get("description", ""), skill.get("levels"), 1)
        self._desc_label.setText(desc)
        self._desc_label.setVisible(bool(desc))

        stats = _format_skill_stats(skill)
        self._stats_label.setText(stats)
        self._stats_label.setVisible(bool(stats))

        # Specialization breakpoints (e.g. Active: Lv 8/8/8/12/16, Stigma:
        # Lv 5/10/15/20) -- same real per-skill "specializations" data the
        # main Skill Planner description panel already shows.
        specs = skill.get("specializations") or []
        spec_lines = []
        for spec in specs:
            lvl = spec.get("parentSkillLvl", "?")
            note = spec.get("specialized", "").strip()
            spec_lines.append(f"<b>Lv {lvl}:</b> {note}" if note else f"<b>Lv {lvl}</b>")
        specs_text = "<br>".join(spec_lines)
        self._specs_label.setText(specs_text)
        self._specs_label.setVisible(bool(specs_text))

        self.adjustSize()


class ArcanaCardTooltip(_TranslucentCardTooltip):
    """Card detail tooltip for hovering one card in the Arcana Calculator
    results popup -- same CONTENT style as the Information tab's own
    inline skill list (Active/Passive skill columns with level ranges),
    plus the card's Empyrean Lord effect at its maxed
    value, with whichever skill THIS combination committed to (if any)
    highlighted at its real perfect-case value instead of the generic
    range (User-Wunsch, 2026-08-29: "Das Tooltip soll similar zu dem sein,
    welches wir bereits als Hover bei den Arcanas nutzen")."""

    def __init__(self, parent=None):
        # Wide enough that most skill names fit on one line at this font
        # size (User-Wunsch, 2026-08-29, after a live screenshot showed
        # ragged wrapping making rows look like they had blank lines in
        # between: "hier scheinen leere Zeilen zu sein. Dies soll ordentlich
        # aussehen") -- combined with eliding any name that still doesn't
        # fit (see set_card), every row is now guaranteed exactly one line
        # tall, so the two columns can never drift out of vertical sync.
        # Widened again 340 -> 380 (User-Wunsch, 2026-08-29: "jetzt bitte
        # die volle Laenge fuer den Text nutzen") to match the raised
        # per-row character cap in set_card.
        super().__init__(380, parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(8)

        self._title_label = QLabel()
        self._title_label.setWordWrap(True)
        self._title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #f1f5f9; background: transparent; border: none;")
        outer.addWidget(self._title_label)

        self._lord_label = QLabel()
        self._lord_label.setWordWrap(True)
        self._lord_label.setTextFormat(Qt.RichText)
        self._lord_label.setStyleSheet(
            "font-size: 11px; background: transparent;"
            "border: none; border-bottom: 1px solid rgba(148, 163, 184, 60); padding-bottom: 8px;"
        )
        outer.addWidget(self._lord_label)

        columns = QHBoxLayout()
        columns.setSpacing(14)
        # Header colored per type (User-Wunsch, 2026-08-29: "jetzt noch
        # farbig fuer aktiv und passiv jeweils") -- same Active/Passive
        # colors used everywhere else in the app (_SKILL_TYPE_COLORS).
        self._active_container, self._active_layout = self._build_category_column(
            "arm_active", _SKILL_TYPE_COLORS["active"]
        )
        self._passive_container, self._passive_layout = self._build_category_column(
            "arm_passive", _SKILL_TYPE_COLORS["passive"]
        )
        columns.addWidget(self._active_container, 1)
        columns.addWidget(self._passive_container, 1)
        outer.addLayout(columns)

    @staticmethod
    def _build_category_column(title_key: str, color: str) -> tuple[QWidget, QVBoxLayout]:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)
        head = QLabel(_t(title_key))
        head.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 1px; color: {color}; background: transparent; border: none;"
        )
        col.addWidget(head)
        rows_layout = QVBoxLayout()
        rows_layout.setSpacing(3)
        col.addLayout(rows_layout)
        return container, rows_layout

    @staticmethod
    def _clear(layout: QVBoxLayout):
        # setParent(None) BEFORE deleteLater() -- takeAt() alone only
        # detaches the widget from layout *management*, it stays a
        # visible child at its old position until the deferred delete
        # actually runs (same fix already documented on _clear_layout
        # above). Missing here caused the real bug the user spotted: old
        # skill rows from the PREVIOUS hovered card stayed on screen,
        # overlapping the new card's rows underneath.
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def set_card(
        self, card_type: str, theme: str, lord: str | None, pool: list[dict],
        assigned_values: dict[str, int],
    ):
        self._title_label.setText(f"{card_type} — {theme}")
        if lord:
            effect = ARCANA_LORD_EFFECTS.get(lord, "")
            self._lord_label.setText(
                f'<span style="color:#facc15;font-weight:700;">{lord}</span> '
                f'<span style="color:#22d3ee;font-weight:700;">+{_ARCANA_CARD_EXTRA_BUDGET}</span><br>'
                f'<span style="color:#64748b;">{effect}</span>'
            )
        else:
            self._lord_label.setText("")

        self._clear(self._active_layout)
        self._clear(self._passive_layout)
        has_active = any(skill.get("type") == "active" for skill in pool)
        has_passive = any(skill.get("type") == "passive" for skill in pool)
        # A card type is always fixed to Active-only, Passive-only, or
        # both (Chalice) -- never zero -- so at least one of these is
        # always true. Hiding the empty side lets the other take the
        # full width instead of an empty "Passive"/"Active" header
        # floating over nothing (User-Wunsch, 2026-08-29: "koennen wir
        # bei den Tooltips von Karten, keine Passiven haben, das
        # einspaltig anzeigen? genauso wenn keine Aktiven Skills?").
        self._active_container.setVisible(has_active)
        self._passive_container.setVisible(has_passive)
        for skill in pool:
            target = self._active_layout if skill.get("type") == "active" else self._passive_layout
            sid = skill.get("id")
            is_assigned = sid in assigned_values
            value_text = (
                f"+{assigned_values[sid]}" if is_assigned
                else f"+{_ARCANA_SKILL_BASELINE}–{_ARCANA_PER_SKILL_CAP}"
            )
            name_color = "#f1f5f9" if is_assigned else "#94a3b8"
            value_color = "#22d3ee" if is_assigned else "#64748b"
            full_name = skill.get("name", "")
            # Truncated by character count, not word-wrapped (User-Wunsch,
            # 2026-08-29, after a live screenshot: "hier scheinen leere
            # Zeilen zu sein. Dies soll ordentlich aussehen") -- a wrapped
            # 2-line row in one column doesn't line up with a 1-line row
            # at the same position in the other column, which read as
            # stray blank lines. Guaranteeing every row is exactly one
            # line keeps both columns in tidy vertical sync regardless of
            # name length. Same char-count approach as _short_skill_name
            # (real stylesheet font isn't applied yet at construction time,
            # so font-metrics-based eliding can't be trusted here either).
            # Raised 18 -> 26 (User-Wunsch, 2026-08-29: "jetzt bitte die
            # volle Laenge fuer den Text nutzen ... Attack Preparation ist
            # der Text abgebrochen") -- 26 covers all but the single
            # longest real skill name in the dataset; still elides with
            # "…" past that (User: "wenn der Inhalt dann immernoch zu lang
            # ist, kannst du gerne den Text weiterhin mit ... abbrechen").
            display_name = _short_skill_name(full_name, 26)
            row = QLabel(
                f'<span style="color:{name_color};">{display_name}</span>&nbsp;&nbsp;'
                f'<span style="color:{value_color};font-weight:700;">{value_text}</span>'
            )
            row.setTextFormat(Qt.RichText)
            row.setWordWrap(False)
            row.setStyleSheet("font-size: 11px; background: transparent; border: none;")
            target.addWidget(row)

        self.adjustSize()


class ArcanaSetBonusTooltip(_TranslucentCardTooltip):
    """Set Bonus detail on hover over a Set-selection banner (User-Wunsch,
    2026-08-29: "Kannst du diese Seteffekte als Hover Effekt abbilden?
    ... statt unten die Set Effekte als Hover Effekt angezeigt werden")
    -- replaces the old always-reserved-space panel below the sidebar,
    same 2-piece/4-piece content, just shown only while actually hovering
    instead of taking up permanent layout space. No source attribution
    shown here (User-Wunsch, 2026-08-29: "Die Source auf den Seiten
    kannst du weglassen") -- see project_arcana_planner.md memory for
    where this data actually comes from."""

    def __init__(self, parent=None):
        super().__init__(260, parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(6)

        self._title_label = QLabel()
        self._title_label.setWordWrap(True)
        self._title_label.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #22d3ee; background: transparent; border: none;"
        )
        outer.addWidget(self._title_label)

        self._2pc_label = QLabel()
        self._2pc_label.setWordWrap(True)
        self._2pc_label.setStyleSheet("font-size: 12px; color: #e5e7eb; background: transparent; border: none;")
        outer.addWidget(self._2pc_label)

        self._4pc_label = QLabel()
        self._4pc_label.setWordWrap(True)
        self._4pc_label.setStyleSheet("font-size: 12px; color: #e5e7eb; background: transparent; border: none;")
        outer.addWidget(self._4pc_label)

    def set_bonus(self, theme: str):
        info = ARCANA_SET_BONUSES.get(theme, {})
        self._title_label.setText(_t("arm_set_bonus", name=info.get("setName", theme)))
        self._2pc_label.setText(_t("arm_set_bonus_2pc", text=info.get("2pc", "")))
        self._4pc_label.setText(_t("arm_set_bonus_4pc", text=info.get("4pc", "")))
        self.adjustSize()


class _ArcanaResultCardIcon(QLabel):
    """One hoverable card icon in an Arcana Calculator result row -- shows
    an ArcanaCardTooltip on hover instead of relying on a plain QToolTip,
    for the same reason DaevanionNodeTooltip replaced the native one
    (richer layout than the native rich-text subset allows). Highlighted
    border marks a card that's actually committed to one of the wished
    skills this round; unassigned cards (still shown -- User-Wunsch,
    2026-08-29: "Es sollen alle 5 Karten gezeigt werden") get a plainer
    border since they're just "along for the ride" this combination."""

    def __init__(
        self, tooltip: ArcanaCardTooltip, card_type: str, theme: str, lord: str | None,
        pool: list[dict], assigned_values: dict[str, int], parent=None,
    ):
        super().__init__(parent)
        self._tooltip = tooltip
        self._card_type = card_type
        self._theme = theme
        self._lord = lord
        self._pool = pool
        self._assigned_values = assigned_values
        self.setFixedSize(56, 56)
        self.setAlignment(Qt.AlignCenter)
        border = "rgba(34, 211, 238, 0.7)" if assigned_values else "rgba(100, 116, 139, 0.5)"
        self.setStyleSheet(
            f"background: rgba(15, 23, 42, 0.75); border: 2px solid {border}; border-radius: 8px;"
        )

    def enterEvent(self, event):
        super().enterEvent(event)
        # A floating, cursor-following translucent window sitting right
        # next to/over its own small source widget can trigger spurious
        # native enter/leave messages on Windows, which then repeatedly
        # resizes+repositions/hides+reshows the tooltip in a tight loop
        # (User-reported: "UpdateLayeredWindowIndirect failed" spammed
        # while hovering). Two guards, same category of fix already
        # proven for the Daevanion Board canvas / skill-picker list (only
        # re-emit hover on an actual CHANGE, not on every event):
        # 1. A hover "token" bumped on every enter -- leaveEvent's
        #    deferred hide (below) checks this is still current before
        #    actually hiding, so a leave immediately followed by a
        #    re-enter (the flicker pattern) never hides at all.
        # 2. Skip the rebuild+reposition entirely if we're already
        #    showing this exact card (covers spurious repeated enters
        #    with no leave in between).
        self._tooltip._hover_token = getattr(self._tooltip, "_hover_token", 0) + 1
        key = (self._card_type, self._theme)
        if getattr(self._tooltip, "_shown_for_key", None) == key:
            return
        self._tooltip._shown_for_key = key
        self._tooltip.set_card(self._card_type, self._theme, self._lord, self._pool, self._assigned_values)
        self._tooltip.show_at(QCursor.pos())

    def leaveEvent(self, event):
        super().leaveEvent(event)
        token = getattr(self._tooltip, "_hover_token", 0)
        tooltip = self._tooltip

        def _maybe_hide():
            if getattr(tooltip, "_hover_token", 0) == token:
                tooltip._shown_for_key = None
                tooltip.hide()

        QTimer.singleShot(0, _maybe_hide)


class _ArcanaThemeOption(QFrame):
    """One Magic/Vigor pill inside ArcanaThemeChoiceDialog's table -- a
    whole clickable row (not just a tiny radio dot) that highlights gold
    when selected, wrapping a real QRadioButton (kept for QButtonGroup
    exclusivity + keyboard nav) so the widget tree stays a normal radio
    group underneath the custom look. Matches the browser mockup the
    user approved before asking to "in diesem Design uebernehmen"
    (2026-08-29)."""

    _BASE_STYLE = (
        "QFrame#ArcanaThemeOption { background: transparent; border: 1px solid transparent; border-radius: 8px; }"
        "QFrame#ArcanaThemeOption:hover { background: rgba(34, 211, 238, 0.08); }"
    )
    _SELECTED_STYLE = (
        "QFrame#ArcanaThemeOption { background: rgba(250, 204, 21, 0.10); "
        "border: 1px solid rgba(250, 204, 21, 0.35); border-radius: 8px; }"
    )
    _RADIO_STYLE = (
        "QRadioButton::indicator { width: 14px; height: 14px; border-radius: 7px; "
        "border: 2px solid #64748b; background: transparent; }"
        "QRadioButton::indicator:checked { border-color: #facc15; background: #facc15; }"
        "QRadioButton::indicator:disabled { border-color: #334155; }"
    )

    def __init__(self, theme: str, lord: str | None, group: QButtonGroup, parent=None):
        super().__init__(parent)
        self.setObjectName("ArcanaThemeOption")
        self.setStyleSheet(self._BASE_STYLE)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(8)

        self.radio = QRadioButton()
        self.radio.setStyleSheet(self._RADIO_STYLE)
        self.radio.setEnabled(bool(lord))
        group.addButton(self.radio)
        row.addWidget(self.radio)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        self._lord_label = QLabel(f"{lord} +{_ARCANA_CARD_EXTRA_BUDGET}" if lord else "—")
        self._lord_label.setStyleSheet("font-size: 12.5px; font-weight: 600; background: transparent; border: none;")
        text_col.addWidget(self._lord_label)
        row.addLayout(text_col)

        if lord:
            effect = ARCANA_LORD_EFFECTS.get(lord, "")
            tooltip = f"{lord}\n{effect}" if effect else lord
            self.setToolTip(tooltip)
            self.radio.setToolTip(tooltip)
            self.setCursor(Qt.PointingHandCursor)
        self.radio.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool):
        self.setStyleSheet(self._SELECTED_STYLE if checked else self._BASE_STYLE)
        color = "#facc15" if checked else "#e2e8f0"
        self._lord_label.setStyleSheet(
            f"font-size: 12.5px; font-weight: 600; color: {color}; background: transparent; border: none;"
        )

    def mousePressEvent(self, event):
        if self.radio.isEnabled():
            self.radio.setChecked(True)
        super().mousePressEvent(event)


class ArcanaThemeChoiceDialog(QDialog):
    """First step of the Arcana Calculator: for each of this season's
    usable Lord card TYPES, pick whether you're running its Vigor or
    Magic version -- each of the 5 slots is always a real, specific card
    now, not an abstract Vigor/Magic head-count budget (User-Spezifikation,
    2026-08-29: "Tabelle ... Magic links / Vigor rechts, 5 Zeilen
    [untereinander] ... Radiobutton + Karte + Lord-Wert")."""

    def __init__(self, usable_types: list[str], theme_map: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("arm_arcana_theme_title"))
        self.type_to_theme: dict[str, str] | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        hint = QLabel(_t("arm_arcana_theme_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(hint)

        header = QHBoxLayout()
        header.addWidget(QLabel(""), 1)
        for theme in ("Magic", "Vigor"):
            head = QLabel(theme)
            head.setStyleSheet("font-weight: 700; font-size: 11px; letter-spacing: 1px; color: #64748b;")
            header.addWidget(head, 2, Qt.AlignCenter)
        layout.addLayout(header)

        self._options: dict[str, dict[str, _ArcanaThemeOption]] = {}
        for ct in usable_types:
            row = QHBoxLayout()
            row.setSpacing(8)
            type_label = QLabel(ct)
            type_label.setStyleSheet("font-size: 13px; font-weight: 600;")
            row.addWidget(type_label, 1)
            group = QButtonGroup(self)
            self._options[ct] = {}
            for theme in ("Magic", "Vigor"):
                entry = theme_map.get(theme, {}).get(ct, {})
                option = _ArcanaThemeOption(theme, entry.get("lord"), group, self)
                row.addWidget(option, 2)
                self._options[ct][theme] = option
            default_theme = "Vigor" if self._options[ct]["Vigor"].radio.isEnabled() else "Magic"
            if self._options[ct][default_theme].radio.isEnabled():
                self._options[ct][default_theme].radio.setChecked(True)
            layout.addLayout(row)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton(_t("arm_cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        ok_btn = QPushButton(_t("arm_apply_btn"))
        ok_btn.clicked.connect(self._accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _accept(self):
        self.type_to_theme = {}
        for ct, options in self._options.items():
            for theme, option in options.items():
                if option.radio.isChecked():
                    self.type_to_theme[ct] = theme
                    break
        self.accept()


class ArcanaApplyTargetDialog(QDialog):
    """Asks WHERE to apply a chosen Arcana Calculator combination, instead
    of always silently targeting whatever build happens to be active
    (User-Wunsch, 2026-08-29: "faellt mir gerade ein, wenn das popup kommt,
    ob die aktuellen Arcanas ueberschrieben werden sollen, sollten wir die
    Wahl geben, falls jemand vergessen hat, das Buildprofil zu aendern,
    darunter sein Zielprofil zu waehlen, oder ein neues Profil anzulegen").
    Always shown (not just when the target already has cards) since the
    whole point is catching "forgot to switch build" before it happens,
    not just warning after the fact."""

    def __init__(self, current_build: str, other_builds: list[str], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle(_t("arm_arcana_apply_target_title"))
        self.resize(340, 320)
        self.result_build_name: str | None = None
        self.result_is_new = False

        layout = QVBoxLayout(self)
        hint = QLabel(_t("arm_arcana_apply_target_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        current_btn = QPushButton(_t("arm_arcana_apply_current_build", name=current_build))
        current_btn.setObjectName("primaryButton")
        current_btn.clicked.connect(lambda: self._pick(current_build, False))
        layout.addWidget(current_btn)

        if other_builds:
            other_label = QLabel(_t("arm_arcana_apply_other_build_label"))
            other_label.setObjectName("EquipSectionLabel")
            layout.addWidget(other_label)
            self.other_list = QListWidget()
            for name in other_builds:
                self.other_list.addItem(name)
            self.other_list.itemDoubleClicked.connect(lambda item: self._pick(item.text(), False))
            layout.addWidget(self.other_list, 1)
            pick_btn = QPushButton(_t("arm_select_btn"))
            pick_btn.clicked.connect(self._pick_selected_other)
            layout.addWidget(pick_btn)

        new_btn = QPushButton(_t("arm_arcana_apply_new_build"))
        new_btn.setObjectName("secondaryButton")
        new_btn.clicked.connect(self._pick_new)
        layout.addWidget(new_btn)

        cancel_btn = QPushButton(_t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def _pick(self, name: str, is_new: bool):
        self.result_build_name = name
        self.result_is_new = is_new
        self.accept()

    def _pick_selected_other(self):
        item = self.other_list.currentItem()
        if item:
            self._pick(item.text(), False)

    def _pick_new(self):
        name, ok = QInputDialog.getText(self, _t("arm_new_build_title"), _t("arm_name_colon"))
        name = name.strip()
        if ok and name:
            self._pick(name, True)


class ArcanaResultsDialog(QDialog):
    """Second step: shows every combination _arcana_compute_combinations
    found, one collapsible "Kombination N" per result (User-Wunsch:
    "ein Popup ... Am besten Accordion pro Set. Mit Set meine ich ...
    eine Zusammenstellung.") -- reuses _build_collapsible_section, the
    same accordion look as the Daevanion Board sidebar. Each combination
    shows ALL 5 usable Lord card types as a single hoverable-icon row --
    not just the ones committed to a wished skill this round (User-
    Wunsch, 2026-08-29: "Es sollen alle 5 Karten gezeigt werden ... alle
    Karten sollen auf Stufe 5 dargestellt werden auch mit dem
    Gotteswert") -- followed by a green/red line per wished skill, red
    ones getting an extra reason line from _arcana_uncovered_reason
    ("einen Grund zeigen, warum gewisse Skills nicht gepusht werden
    koennen")."""

    _MIN_COVERAGE_PERCENT = 50

    # Emitted with one combination's {card_type: assignment} dict when the
    # user clicks that combination's "Use this combination" button (User-
    # Wunsch, 2026-08-29: "einen Button in den Calc, der dafuer sorgt,
    # dass die richtigen Karten in die Slots kommen") -- the dialog itself
    # doesn't own _skill_builds_data/arcana_cards, so it just hands the
    # chosen combination back to whoever opened it (LoadoutWindow), which
    # does the actual overwrite-confirmation + persistence.
    arcana_combination_chosen = Signal(dict)

    def __init__(
        self, results: list[dict], wishes: dict[str, int], skill_names: dict[str, str],
        theme_map: dict, usable_types: list[str], class_skill_pools: dict[str, list[dict]],
        skill_type_by_id: dict[str, str], type_to_theme: dict[str, str], parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(_t("arm_arcana_results_title"))
        self.resize(640, 720)
        self._card_tooltip = ArcanaCardTooltip(self)

        # Only combinations that actually cover more than half the total
        # wishlist are worth showing -- a combo that reaches almost none
        # of what you asked for isn't a useful "alternative" (User-Wunsch,
        # 2026-08-29: "nur Kombinationen anzeigen, die besser als 50%
        # sind ... eine Kombination von 5 Skills, die nicht erreicht
        # werden, brauchen wir nicht"). If NONE clear that bar, the
        # wishlist itself is too ambitious for what 5 real cards can ever
        # deliver -- say so instead of showing a discouraging result
        # (this shouldn't normally happen at all, since the live "max +N"
        # ceiling hint next to each purple counter already stops you from
        # wishing higher than Arcana could ever reach -- but the Priority-
        # List-based "always spend the full budget" fill can still shift
        # coverage around unevenly across combinations, so this is a
        # safety net, not the primary guard).
        had_any_result = bool(results)
        results = [
            r for r in results
            if _arcana_result_coverage_percent(r, wishes) > self._MIN_COVERAGE_PERCENT
        ]

        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setAlignment(Qt.AlignTop)
        content_layout.setSpacing(8)

        if not results:
            # Distinct messages: the solver found literally nothing at all
            # (structurally impossible, e.g. no card can ever reach any
            # wished skill) vs. it found combinations but none cleared the
            # 50% bar (the wishlist is just too ambitious for 5 real cards).
            empty_key = "arm_arcana_too_many_wishes" if had_any_result else "arm_arcana_no_combination"
            empty = QLabel(_t(empty_key))
            empty.setWordWrap(True)
            content_layout.addWidget(empty)
        else:
            for i, result in enumerate(results):
                section, body = _build_collapsible_section(
                    _t("arm_arcana_combination_label", n=i + 1), expanded=(i == 0)
                )

                assignment_by_type = {a["type"]: a for a in result["assignments"]}

                card_row = QHBoxLayout()
                card_row.setSpacing(8)
                card_row.addStretch(1)
                for ct in usable_types:
                    assignment = assignment_by_type.get(ct)
                    theme = assignment["theme"] if assignment else type_to_theme.get(ct, "")
                    assigned_values = assignment["skill_ids"] if assignment else {}
                    lord = theme_map.get(theme, {}).get(ct, {}).get("lord")
                    icon_file = theme_map.get(theme, {}).get(ct, {}).get("iconFile")
                    pool = class_skill_pools.get(ct, [])
                    icon = _ArcanaResultCardIcon(self._card_tooltip, ct, theme, lord, pool, assigned_values)
                    pix = _arcana_icon(icon_file, 44)
                    if pix:
                        icon.setPixmap(pix)
                    card_row.addWidget(icon)
                card_row.addStretch(1)
                body.addLayout(card_row)

                divider = QFrame()
                divider.setFrameShape(QFrame.HLine)
                body.addWidget(divider)

                for sid, need in wishes.items():
                    covered = result["covered"].get(sid, 0)
                    name = skill_names.get(sid, sid)
                    fully_covered = covered >= need
                    color = "#4ade80" if fully_covered else "#f87171"
                    summary = QLabel(
                        f'<span style="color:{color};font-weight:700;">'
                        f'{_t("arm_arcana_covered_label", name=name, covered=covered, wish=need)}</span>'
                    )
                    summary.setTextFormat(Qt.RichText)
                    summary.setWordWrap(True)
                    body.addWidget(summary)

                    if not fully_covered:
                        reason_key, reason_kwargs = _arcana_uncovered_reason(
                            sid, need, covered, usable_types, class_skill_pools, skill_type_by_id,
                        )
                        reason = QLabel(_t(reason_key, **reason_kwargs))
                        reason.setStyleSheet("color: #94a3b8; font-size: 11px;")
                        reason.setWordWrap(True)
                        body.addWidget(reason)

                apply_btn = QPushButton(_t("arm_arcana_apply_combination"))
                apply_btn.setObjectName("EqPriorityButton")
                apply_btn.clicked.connect(
                    lambda checked=False, a=assignment_by_type: self._on_apply_clicked(a)
                )
                body.addWidget(apply_btn)

                content_layout.addWidget(section)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        close_btn = QPushButton(_t("arm_close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _on_apply_clicked(self, assignment_by_type: dict):
        self.arcana_combination_chosen.emit(assignment_by_type)
        self.accept()


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
        self._equipped_philosopher_stone: dict[str, bool] = {}
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

        # Name/Race moved here from the old "Character Settings" popup
        # (gear button, bottom-right of the Jewelry column) -- that spot
        # now opens the Eigenschaften-Priorität editor instead, and Class/
        # GearScore were already shown elsewhere too, so only Name/Race
        # actually needed a new home (User-Wunsch, 2026-08-28: "In die
        # Kopfzeile verschieben").
        class_row.addSpacing(12)
        self.character_name_input = QLineEdit()
        self.character_name_input.setPlaceholderText(_t("arm_character_name_placeholder"))
        self.character_name_input.setMaximumWidth(140)
        class_row.addWidget(self.character_name_input)
        self.character_race_combo = QComboBox()
        self.character_race_combo.addItems(AION2_RACES)
        self.character_race_combo.setToolTip(_t("arm_race_label"))
        class_row.addWidget(self.character_race_combo)
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
        self.stat_priority_edit_btn.setObjectName("StatPriorityEditBtn")
        self.stat_priority_edit_btn.setIcon(_make_gear_icon())
        self.stat_priority_edit_btn.setIconSize(QSize(20, 20))
        self.stat_priority_edit_btn.setFixedSize(32, 32)
        self.stat_priority_edit_btn.setToolTip(_t("arm_stat_priority_editor_title"))
        self.stat_priority_edit_btn.clicked.connect(self._open_stat_priority_editor)
        equip_header_row.addWidget(self.stat_priority_edit_btn)
        # Wrapped in a widget (not addLayout directly) so it can be hidden
        # as a unit while a full-panel takeover page is showing -- Set
        # tabs/Quick Select are meaningless there and just cost vertical
        # space, forcing extra scrolling (User-Wunsch, 2026-08-28, re:
        # EQ Priority: "können wir diese Leiste ausblenden? ... spart Platz
        # und man braucht nicht scrollen").
        self.equip_top_bar = QWidget()
        self.equip_top_bar.setLayout(equip_header_row)
        equipment_outer.addWidget(self.equip_top_bar)

        equip_normal_page = QWidget()
        equip_root = QHBoxLayout(equip_normal_page)
        equip_root.setContentsMargins(16, 16, 16, 16)
        equip_root.setSpacing(20)
        equip_root.addLayout(self._build_weapon_armor_column(), 0)
        equip_root.addWidget(self._build_equip_center_stack(), 1)
        equip_root.addLayout(self._build_accessory_column(), 0)

        # "Build Vergleich" (User-Wunsch, 2026-08-27) is a 2nd full-panel
        # page in the same stack as the normal equip view, not a popup --
        # switched to via a tab-like button in equip_build_tabs_row (see
        # _rebuild_equip_build_tabs), left via its own back-arrow/X header.
        self.equip_view_stack = QStackedWidget()
        self.equip_view_stack.addWidget(equip_normal_page)
        self.equip_view_stack.addWidget(self._build_compare_page())
        self._equip_priority_page_index = self.equip_view_stack.addWidget(self._build_equip_priority_page())
        self._stat_priority_editor_widget: QWidget | None = None
        equipment_outer.addWidget(self.equip_view_stack, 1)
        self.main_tabs.addTab(equipment_tab, _t("arm_equipment_btn"))

        # "EQ Priority" moved out of main_tabs into its own equip_view_stack
        # takeover (see _open_equip_priority_page) -- this slot now holds
        # the Daevanion Board (User-Wunsch, 2026-08-28: "da wo EQ Priority
        # steht, da soll stattdessen Daevanionboard hin"). Placeholder for
        # now -- the real interactive board (72 boards x 225 nodes, ported
        # from the browser mockup) is its own separate, larger task.
        self.main_tabs.addTab(self._build_daevanion_board_tab(), _t("arm_daevanion_board_tab"))

        # Built before the Arcana tab below even though it appears AFTER it
        # in the tab bar -- _build_arcana_sets_tab() needs
        # self._skill_builds_data/_current_build_name/skill_build_tabs_row
        # to already exist (a build now spans Skill AND Arcana together,
        # see _rebuild_skill_build_tabs), and _build_skill_planner_tab() is
        # what sets those up.
        skill_planner_widget = self._build_skill_planner_tab()

        self.main_tabs.addTab(self._build_arcana_tab(), _t("arm_arcana_tab"))

        self.main_tabs.addTab(skill_planner_widget, _t("arm_skill_planner_tab"))

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

        # _build_daevanion_board_tab() ran earlier, above, before
        # character_class_combo had any items/selection at all (it's only
        # populated here) -- currentText() was "" at that point, so its
        # first render always showed the "no board for this class" state
        # regardless of the real starting class. Re-run now that the combo
        # actually has a value (User-reported bug, 2026-08-28: "aktuell wird
        # noch nichts angezeigt").
        self._daevanion_rebuild_deity_tabs()
        self._daevanion_refresh()

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
        # Initialized here (before the "Skillpunkte frei" label below reads
        # it for the first time) rather than in _build_skill_description_tab,
        # which only runs later when this tab's inner QTabWidget is built.
        self._skill_levels: dict[str, int] = {}
        # Auto-computed (never persisted directly, never touched by
        # _on_skill_level_changed) -- +1 per equipped Trait/Skill substat
        # pick, stacking across slots (User-Wunsch, 2026-08-28: "2 Ringe ->
        # Skills die auf beiden vorhanden sind werden dann im Skillplaner
        # +2 gerechnet"), PLUS every active Daevanion Board skill_level
        # node for the current class (User-Wunsch, 2026-08-28: "die Skills
        # auf den Skillplaner rechnen"). Recomputed in _refresh_stat_info,
        # which already runs after every equip mutation (Quick Select,
        # manual substat pick, Set switch) and after Daevanion node clicks.
        self._skill_bonus: dict[str, int] = {}
        # Arcana Planner wish list (User-Wunsch, 2026-08-28/29): "die
        # zusaetzlichen Punkte, die man nicht durch Daeva Board und Gear
        # erreichen kann" -- a manual per-skill planning target, purely an
        # input to _arcana_compute_combinations, not part of the level
        # math above. Persisted like _skill_levels (see
        # get_persistable_state/apply_persisted_state).
        self._skill_arcana_wish: dict[str, int] = {}
        # So _on_skill_arcana_wish_changed can re-enable/disable the "+"
        # button live as the wish approaches its ceiling, without a full
        # card rebuild (see _arcana_ceiling_for_skill).
        self._arcana_wish_plus_buttons: dict[str, QPushButton] = {}
        self._skill_level_labels: dict[str, QLabel] = {}
        self._skill_star_labels: dict[str, QLabel] = {}
        # Empty placeholder -- the real per-type [None] entries are only
        # added once _build_skill_priority_tab actually runs (later in this
        # same method), but _build_skill_description_tab's cards (built
        # first) already call _priority_skill_ids(), which reads this.
        self._skill_priority_ids: dict[str, list[int | None]] = {}
        # Real values filled in later by _build_skill_description_tab (which
        # needs self._skills_by_class loaded first) -- empty here just so
        # _refresh_skillpoints_label/_refresh_stigma_points_label below have
        # something to read on this tab's very first construction.
        self._skill_id_to_type: dict[str, str] = {}

        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel(_t("arm_skill_planner_tab"))
        title.setObjectName("DetailHeader")
        title_row.addWidget(title)
        title_row.addStretch(1)

        # "Skillpunkte Frei" (User-Wunsch, 2026-08-27) -- total Skill Points
        # available at the current level-45 cap: base from leveling (1 per
        # level-up, levels 2-45) in white, plus however many Wisdom Stones
        # the character's own starting-zone Monolith (Verteron/Altgard, 30
        # levels -- see project_skillpoint_sources.md memory) has paid out
        # SO FAR, in turquoise, e.g. "44 (+63)" at Monolith level 15 -- NOT
        # always the theoretical level-30 max, since the user tracks their
        # own real Monolith progress via the spinbox below (User: "Das ist
        # die maximale Anzahl ... Dann brauchen wir eine Option, wo man das
        # aktuelle Level des Monolithen angeben kann").
        self.skillpoints_title_lbl = QLabel(_t("arm_skillpoints_free_label"))
        self.skillpoints_title_lbl.setObjectName("EquipSectionLabel")
        title_row.addWidget(self.skillpoints_title_lbl)
        self.skillpoints_value_lbl = QLabel()
        title_row.addWidget(self.skillpoints_value_lbl)

        title_row.addSpacing(16)
        self.monolith_level_title_lbl = QLabel(_t("arm_monolith_level_label"))
        self.monolith_level_title_lbl.setObjectName("EquipSectionLabel")
        title_row.addWidget(self.monolith_level_title_lbl)
        self.monolith_level_spin = QSpinBox()
        self.monolith_level_spin.setRange(0, _MONOLITH_MAX_LEVEL)
        self.monolith_level_spin.setFixedWidth(60)
        self.monolith_level_spin.valueChanged.connect(self._on_monolith_level_changed)
        title_row.addWidget(self.monolith_level_spin)

        # "Stigmapunkte" (User-Wunsch, 2026-08-27) -- separate from Skill
        # Points entirely ("Stigma Punkte werden separat gerechnet und nicht
        # von den Skillpunkten abgezogen"), so this doesn't share a pool
        # with skillpoints_value_lbl above -- just counts how many points
        # are currently assigned to Stigma-type skills, shown as a negative
        # red number (no known budget/cap to count down from, unlike Skill
        # Points, so there's nothing to subtract it FROM).
        title_row.addSpacing(16)
        self.stigma_points_title_lbl = QLabel(_t("arm_stigma_points_label"))
        self.stigma_points_title_lbl.setObjectName("EquipSectionLabel")
        title_row.addWidget(self.stigma_points_title_lbl)
        self.stigma_points_value_lbl = QLabel()
        title_row.addWidget(self.stigma_points_value_lbl)

        # "Arcana Calculator" (User-Wunsch, 2026-08-28/29) -- disabled until
        # at least one skill has a purple Arcana wish set (>0); opens the
        # Vigor/Magic slot-split question, then runs
        # _arcana_compute_combinations and shows the results.
        title_row.addSpacing(16)
        self.arcana_calculator_btn = QPushButton(_t("arm_arcana_calculator_btn"))
        self.arcana_calculator_btn.setObjectName("EqPriorityButton")
        self.arcana_calculator_btn.setEnabled(False)
        self.arcana_calculator_btn.clicked.connect(self._on_arcana_calculator_clicked)
        title_row.addWidget(self.arcana_calculator_btn)

        outer.addLayout(title_row)
        self._monolith_level = 0
        self._refresh_skillpoints_label()
        self._refresh_stigma_points_label()

        self._skill_builds_data: dict[str, dict[str, dict]] = {}
        self._current_build_name = "Default"
        self.skill_build_tabs_row = QHBoxLayout()
        self.skill_build_tabs_row.setSpacing(6)
        self.skill_build_tabs_row.setAlignment(Qt.AlignLeft)
        outer.addLayout(self.skill_build_tabs_row)
        # Mirrored build-tab row for the Arcana "Sets" sub-tab (built later
        # in __init__, once this shared build state already exists) --
        # not attached to any layout here, just created early so
        # _rebuild_skill_build_tabs() can populate both rows uniformly
        # regardless of which tab happens to be built/rebuilt first.
        self.arcana_build_tabs_row = QHBoxLayout()
        self.arcana_build_tabs_row.setSpacing(6)
        self.arcana_build_tabs_row.setAlignment(Qt.AlignLeft)

        tabs = QTabWidget()
        tabs.setObjectName("timerModeTabWidget")
        tabs.addTab(self._build_skill_description_tab(), _t("arm_skill_description_tab"))
        tabs.addTab(self._build_skill_priority_tab(), _t("arm_priority_list_tab"))
        outer.addWidget(tabs, 1)

        return page

    def _on_monolith_level_changed(self, value: int):
        self._monolith_level = value
        self._refresh_skillpoints_label()

    def _refresh_skillpoints_label(self):
        """Shows what's actually still LEFT to spend, not the flat total --
        every point put into a skill (see _on_skill_level_changed) counts
        against this (User-Wunsch, 2026-08-27: "pro Skillpunkt der gesetzt
        wird, oben ein Skillpunkt angezogen werden"). Spent points come out
        of the white leveling pool first, then the turquoise Monolith pool,
        matching how the two numbers already read left-to-right."""
        base = _SKILLPOINTS_BASE_AT_LEVEL_45
        bonus = _monolith_skillpoints(self._monolith_level)
        # Only the first _SKILL_LEVEL_BASE_CAP levels of any NON-Stigma
        # skill are paid for with actual Skill Points -- levels past that
        # come from gear/Arcana/Daevanion Board instead (User-Wunsch,
        # 2026-08-27: "Wichtig ist, dass nur bis 10 Skillpunkte abgezogen
        # werden"), so each skill's contribution here is capped at 10 even
        # though its own level counter keeps counting past that with no
        # limit. Stigma skills are excluded entirely -- they're paid for
        # with a separate Stigma Point pool (User-Wunsch, 2026-08-27:
        # "Stigma Punkte werden separat gerechnet und nicht von den
        # Skillpunkten abgezogen"), see _refresh_stigma_points_label.
        spent = sum(
            min(v, _SKILL_LEVEL_BASE_CAP) for sid, v in self._skill_levels.items()
            if self._skill_id_to_type.get(sid) != "stigma"
        )
        remaining = max(0, base + bonus - spent)
        remaining_base = min(remaining, base)
        remaining_bonus = remaining - remaining_base
        self.skillpoints_value_lbl.setText(
            f"<span style='color:white; font-weight:700;'>{remaining_base}</span> "
            f"<span style='color:#22d3ee; font-weight:700;'>(+{remaining_bonus})</span>"
        )

    def _refresh_stigma_points_label(self):
        """Just a running count of points assigned to Stigma-type skills,
        shown as a negative red number -- no budget to subtract it from
        (unlike Skill Points), since Stigma Points have no known cap/source
        data yet. Uncapped per skill (Stigma skills don't share the
        Skill Points 10-per-skill cap either, since they're not paid for
        from that pool at all)."""
        spent = sum(
            v for sid, v in self._skill_levels.items()
            if self._skill_id_to_type.get(sid) == "stigma"
        )
        # Plain white "0" at rest (User-Wunsch, 2026-08-27: "und '0'
        # Stigmapunkte sollte weiß sein") -- only turns red once something
        # is actually assigned.
        if spent <= 0:
            self.stigma_points_value_lbl.setText("<span style='color:white; font-weight:700;'>0</span>")
        else:
            self.stigma_points_value_lbl.setText(
                f"<span style='color:#f87171; font-weight:700;'>-{spent}</span>"
            )

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

        # "Nur Favoriten" (User-Wunsch, 2026-08-27) -- filters down to just
        # the skills that are on the Priority List (see _priority_skill_ids),
        # marked with a gold star on their card. The older separate "Only
        # checked"/_skill_checked_ids manual bookmark (a plain checkmark
        # icon, unrelated to the Priority List) was removed entirely
        # (User-Wunsch, 2026-08-29: "Den Haken innerhalb des Planners kann
        # man weg machen. Dadurch, dass man die Skills als Favoriten
        # markiert hat, erledigt sich das") -- the star/Priority List
        # already covers what it was for.
        self.skill_favorites_only_btn = QPushButton(_t("arm_only_favorites"))
        self.skill_favorites_only_btn.setObjectName("SkillFilterButton")
        self.skill_favorites_only_btn.setCheckable(True)
        self.skill_favorites_only_btn.setMinimumSize(100, 32)
        self.skill_favorites_only_btn.toggled.connect(self._refresh_skill_description_view)
        controls_row.addWidget(self.skill_favorites_only_btn)

        # Skill damage estimate toggle (User-Wunsch, 2026-08-29): the real
        # "minValue ~ maxValue" tooltip range (straight from skills_all.
        # json) always shows; checked, appends an estimated range scaled by
        # the player's own stats in parentheses after it (see
        # _skill_damage_estimate_multiplier's module comment for the
        # exact, deliberately-approximate method and why).
        self.skill_estimated_damage_btn = QPushButton(_t("arm_estimated_damage_btn"))
        self.skill_estimated_damage_btn.setObjectName("SkillEstimatedDamageButton")
        self.skill_estimated_damage_btn.setCheckable(True)
        self.skill_estimated_damage_btn.setMinimumSize(100, 32)
        self.skill_estimated_damage_btn.setToolTip(_t("arm_estimated_damage_tooltip"))
        self.skill_estimated_damage_btn.toggled.connect(self._refresh_skill_description_view)
        controls_row.addWidget(self.skill_estimated_damage_btn)

        left_outer.addLayout(controls_row)

        self._skills_by_class = _load_skills_by_class()
        # Flat skill id -> type lookup (User-Wunsch, 2026-08-27: "Stigma
        # Punkte werden separat gerechnet und nicht von den Skillpunkten
        # abgezogen") -- built once so _refresh_stigma_points_label can tell
        # which entries in self._skill_levels are Stigma without re-scanning
        # every class's skill list each time.
        self._skill_id_to_type: dict[str, str] = {
            s["id"]: s.get("type", "")
            for skills in self._skills_by_class.values()
            for s in skills
        }
        # Full skill dict lookup (2026-08-29) -- lets _on_skill_level_changed
        # refresh an already-open description panel without re-scanning
        # every class's skill list on each +/- click.
        self._skill_id_to_skill: dict[str, dict] = {
            s["id"]: s
            for skills in self._skills_by_class.values()
            for s in skills
        }
        # Per-skill invested level (User-Wunsch, 2026-08-27) -- keyed by
        # skill id directly (already class-specific, no separate per-class
        # keying needed; see _build_skill_planner_tab for where this dict
        # is actually initialized, since the "Skillpunkte frei" label built
        # there needs it to already exist). Skill ids are strings in the
        # source data (unlike item ids, which are real ints) -- kept as-is,
        # no int() cast. No enforced per-skill max for now: the real cap
        # varies per skill and stacks from multiple systems (Skill Points,
        # gear, Arcana, Daevanion Board) that aren't reliably derivable from
        # our scraped data yet (see project_skillpoint_sources.md memory) --
        # only a floor of 0 is enforced, in _on_skill_level_changed. Only
        # the first _SKILL_LEVEL_BASE_CAP levels of any skill actually
        # count against "Skillpunkte frei" (see _refresh_skillpoints_label).

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

    def _priority_skill_ids(self) -> set:
        """Every skill id currently assigned to any Priority List slot
        (Active/Passive/Stigma combined) -- drives the gold star + "Nur
        Favoriten" filter on the Skill Description cards (User-Wunsch,
        2026-08-27)."""
        return {sid for ids in self._skill_priority_ids.values() for sid in ids if sid is not None}

    def _skill_priority_rank(self) -> dict[str, int]:
        """Flat skill_id -> position (0 = highest priority) across every
        Priority List slot, active+passive combined (never stigma --
        Arcana can't target those). Used by the Arcana Calculator to fill
        a card's leftover skill slots/points sensibly once real wishes
        are satisfied, instead of an arbitrary choice (User-Wunsch,
        2026-08-29: "kannst bei der Verteilung der restlichen Punkte auch
        gerne die Prioliste der Skills nehmen")."""
        rank: dict[str, int] = {}
        i = 0
        for type_key in ("active", "passive"):
            for sid in self._skill_priority_ids.get(type_key, []):
                if sid is not None and sid not in rank:
                    rank[sid] = i
                    i += 1
        return rank

    def _refresh_favorite_stars(self):
        """Cheap path for when the Priority List changes but the Skill
        Description grid doesn't need a full rebuild -- just flips each
        already-built card's star visibility. Only correct while "Nur
        Favoriten" is off (a favorite being removed while that filter is on
        must actually disappear from the grid, which needs a real rebuild
        instead -- see _rebuild_priority_row)."""
        favorite_ids = self._priority_skill_ids()
        for sid, star in self._skill_star_labels.items():
            star.setVisible(sid in favorite_ids)

    # ── Saved skill builds (per class): named tabs holding one priority-list
    # + level set each, e.g. "Default" / "PvP" / "PvE" — session-only for now,
    # not yet persisted to disk. ────────────────────────────────────────────

    def _empty_build_state(self) -> dict:
        return {
            "priority": {key: [None] for key, _ in self._SKILL_BUILD_SECTIONS},
            # Placeholder for the future Arcana "Sets" equip slots (card
            # type -> assigned card data) -- not written to by anything
            # yet (the Sets tab is still just 5 empty placeholders, see
            # _build_arcana_sets_tab), but reserved now so the schema
            # doesn't need another migration once real card assignment
            # ships (User-Wunsch, 2026-08-29: "Wie beim Buildplanner
            # bauen wir bei Arcana und Skill einen gemeinsamen Build").
            "arcana_cards": {},
        }

    def _ensure_class_builds(self, class_name: str):
        if class_name not in self._skill_builds_data:
            self._skill_builds_data[class_name] = {"Default": self._empty_build_state()}

    def _save_current_build_state(self, class_name: str):
        self._ensure_class_builds(class_name)
        builds = self._skill_builds_data[class_name]
        if self._current_build_name not in builds:
            return
        existing = builds[self._current_build_name]
        builds[self._current_build_name] = {
            "priority": {k: list(v) for k, v in self._skill_priority_ids.items()},
            "arcana_cards": dict(existing.get("arcana_cards", {})),
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
        self._refresh_arcana_equip_slots()
        # Switching builds swaps in a different set of Arcana card
        # assignments -- the blue Skill Planner bonus must follow (see
        # _on_arcana_skill_slot_clicked's own call to this for why),
        # otherwise it would keep showing the PREVIOUS build's Arcana
        # bonus until something unrelated happened to trigger a recompute.
        self._recompute_skill_bonus()

    def _rebuild_skill_build_tabs(self):
        """Populates BOTH build-tab rows -- the Skill Planner's own
        (self.skill_build_tabs_row) and the Arcana "Sets" tab's mirrored
        one (self.arcana_build_tabs_row) -- from the SAME
        _skill_builds_data/_current_build_name, since a build now spans
        Skill AND Arcana together (User-Wunsch, 2026-08-29: "Wie beim
        Buildplanner bauen wir bei Arcana und Skill einen gemeinsamen
        Build ... wenn ein Build beim Skillplaner angelegt wird, dieser
        fuer die Arcana genauso gilt"). Each row gets its OWN button
        instances/QButtonGroup (matching the existing pattern for the
        two class combo boxes elsewhere in this window) since the same
        QWidget can't live in two layouts at once."""
        class_name = self.character_class_combo.currentText().strip().lower()
        self._ensure_class_builds(class_name)
        builds = self._skill_builds_data[class_name]
        if self._current_build_name not in builds:
            self._current_build_name = next(iter(builds))

        self._skill_build_tab_group = self._populate_build_tabs_row(self.skill_build_tabs_row, builds)
        self._arcana_build_tab_group = self._populate_build_tabs_row(self.arcana_build_tabs_row, builds)

    def _populate_build_tabs_row(self, row: QHBoxLayout, builds: dict) -> QButtonGroup:
        _clear_layout(row)
        group = QButtonGroup(self)
        group.setExclusive(True)
        for build_name in builds:
            btn = _BuildTabButton(build_name)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(build_name == self._current_build_name)
            btn.setMinimumHeight(32)
            btn.clicked.connect(lambda checked=False, bn=build_name: self._on_switch_build(bn))
            btn.doubleClicked.connect(lambda bn=build_name: self._on_rename_build(bn))
            btn.setToolTip(_t("arm_rename_hint"))
            group.addButton(btn)
            row.addWidget(btn)

        add_btn = QPushButton()
        add_btn.setIcon(_make_plus_icon())
        add_btn.setIconSize(QSize(20, 20))
        add_btn.setFixedSize(40, 32)
        add_btn.setToolTip(_t("arm_add_new_build"))
        add_btn.clicked.connect(self._on_add_build)
        row.addWidget(add_btn)

        duplicate_btn = QPushButton()
        duplicate_btn.setIcon(_make_duplicate_icon())
        duplicate_btn.setIconSize(QSize(20, 20))
        duplicate_btn.setFixedSize(40, 32)
        duplicate_btn.setToolTip(_t("arm_duplicate_current_build"))
        duplicate_btn.clicked.connect(self._on_duplicate_build)
        row.addWidget(duplicate_btn)

        rename_btn = QPushButton()
        rename_btn.setIcon(_make_edit_icon())
        rename_btn.setIconSize(QSize(20, 20))
        rename_btn.setFixedSize(40, 32)
        rename_btn.setToolTip(_t("arm_rename_current_build"))
        rename_btn.clicked.connect(lambda checked=False: self._on_rename_build(self._current_build_name))
        row.addWidget(rename_btn)

        save_btn = QPushButton()
        save_btn.setIcon(_make_save_icon())
        save_btn.setIconSize(QSize(20, 20))
        save_btn.setFixedSize(40, 32)
        save_btn.setToolTip(_t("arm_save_current_build"))
        save_btn.clicked.connect(self._on_save_current_build)
        row.addWidget(save_btn)

        return group

    def _on_save_current_build(self):
        class_name = self.character_class_combo.currentText().strip().lower()
        self._save_current_build_state(class_name)

    def _on_switch_build(self, build_name: str):
        if build_name == self._current_build_name:
            return
        class_name = self.character_class_combo.currentText().strip().lower()
        self._save_current_build_state(class_name)
        self._current_build_name = build_name
        # Re-syncs BOTH build-tab rows' checked button (User-reported,
        # 2026-08-29: "Wenn man bei Arcana auf Default anzeigt, wird beim
        # Skillplaner nicht gewechselt") -- clicking a tab in one row only
        # auto-updates THAT row's own QButtonGroup; the other tab's row is
        # a separate QButtonGroup with its own button instances (see
        # _rebuild_skill_build_tabs's docstring) that nothing else told to
        # follow along.
        self._rebuild_skill_build_tabs()
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

    def _on_duplicate_build(self):
        """Copies the current build's Priority List (+ future Arcana Sets
        card assignment) into a new, user-named build -- same "Duplicate"
        pattern as the Gear/Equip builds already have (User-Wunsch,
        2026-08-29: "Du kannst gerne wie aus dem Screenshot die gleichen
        Buttons nutzen, wie 'neu', 'bearbeiten', 'Duplizieren' und
        speichern")."""
        class_name = self.character_class_combo.currentText().strip().lower()
        self._save_current_build_state(class_name)
        builds = self._skill_builds_data[class_name]
        source_name = self._current_build_name
        default_name = _t("arm_duplicate_default_name", name=source_name)
        name, ok = QInputDialog.getText(self, _t("arm_duplicate_build_title"), _t("arm_name_colon"), text=default_name)
        name = name.strip()
        if not ok or not name or name in builds:
            return
        source = builds[source_name]
        builds[name] = {
            "priority": {k: list(v) for k, v in source["priority"].items()},
            "arcana_cards": dict(source.get("arcana_cards", {})),
        }
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

        # Keeps the Skill Description cards' gold stars (and "Nur
        # Favoriten" filter) in sync with whatever the Priority List looks
        # like now.
        if self.skill_favorites_only_btn.isChecked():
            self._refresh_skill_description_view()
        else:
            self._refresh_favorite_stars()

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

        if skill:
            # Overlay "x" badge, child of the icon button itself so its
            # click is consumed there and doesn't also reopen the picker
            # (same nested-QPushButton-inside-QPushButton pattern already
            # used for the Skill Description cards' -/+ level buttons).
            # User-Wunsch, 2026-08-28: "die Möglichkeit ... Skills zu
            # entfernen. Wenn man einen Skill entfernt, soll der Skill
            # aufrücken" -- _on_remove_priority_slot pops the entry outright
            # rather than just clearing it to None, so every later slot
            # shifts up by one for free.
            remove_btn = QToolButton(btn)
            remove_btn.setObjectName("PrioritySlotRemoveBtn")
            remove_btn.setIcon(_make_close_icon(12))
            remove_btn.setIconSize(QSize(10, 10))
            remove_btn.setFixedSize(18, 18)
            remove_btn.setCursor(Qt.PointingHandCursor)
            remove_btn.move(64 - 18, 0)
            remove_btn.setToolTip(_t("arm_remove_priority_skill"))
            remove_btn.clicked.connect(lambda checked=False, tk=type_key, i=index: self._on_remove_priority_slot(tk, i))
            remove_btn.raise_()

        full_name = skill.get("name", "") if skill else _t("arm_choose_skill_title")
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

    def _on_remove_priority_slot(self, type_key: str, index: int):
        """Pops the slot outright (not just clearing it to None) so every
        later slot shifts up by one -- also what lets you actually swap a
        skill for one that's currently used elsewhere: pull that other
        entry out first, then it's free to pick here (User-Wunsch,
        2026-08-28: "Wenn man einen Skill austauschen möchte, gegen einen
        anderen, geht das nicht" -- there was no way to free up an
        already-used skill before this)."""
        ids = self._skill_priority_ids[type_key]
        if 0 <= index < len(ids):
            ids.pop(index)
        if not ids:
            ids.append(None)
        self._rebuild_priority_row(type_key)

    _SKILL_DESC_CARD_COLUMNS = 2

    def _refresh_skill_description_view(self):
        for grid in self.skill_card_sections.values():
            _clear_layout(grid)
        # Cards (and their level QLabels/star labels) are destroyed above --
        # drop the now-dangling references so _on_skill_level_changed
        # doesn't try to touch a deleted widget; rebuilt fresh per card
        # below.
        self._skill_level_labels = {}
        self._skill_star_labels = {}
        self._arcana_wish_plus_buttons = {}

        class_name = _skills_data_class_key(self.character_class_combo.currentText())
        all_skills = sorted(self._skills_by_class.get(class_name, []), key=lambda s: s.get("name", ""))

        active_types = {t for t, btn in self._skill_type_buttons.items() if btn.isChecked()}
        query = self.skill_search_input.text().strip().lower()
        favorites_only = self.skill_favorites_only_btn.isChecked()
        favorite_ids = self._priority_skill_ids() if favorites_only else None
        skills = [
            s for s in all_skills
            if s.get("type", "") in active_types
            and (not query or query in s.get("name", "").lower())
            and (favorite_ids is None or s.get("id") in favorite_ids)
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
        card.setCursor(Qt.PointingHandCursor)
        card.setMinimumHeight(108)

        outer = QVBoxLayout(card)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        icon_label = QLabel()
        icon_label.setObjectName("SkillRowIcon")
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignCenter)
        icon = _skill_icon(skill)
        if icon:
            icon_label.setPixmap(icon.pixmap(36, 36))
        top_row.addWidget(icon_label)

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
        top_row.addLayout(text_col, 1)

        skill_id = skill.get("id")

        # Gold star = this skill is on the Priority List (User-Wunsch,
        # 2026-08-27). The older separate checkmark bookmark (unrelated
        # manual "angehakt" state) was removed entirely (User-Wunsch,
        # 2026-08-29) -- the star/Priority List already covers what it
        # was for.
        star_icon = QLabel()
        star_icon.setFixedSize(18, 18)
        star_icon.setPixmap(_make_star_icon())
        star_icon.setVisible(skill_id in self._priority_skill_ids())
        star_icon.setToolTip(_t("arm_on_priority_list_tooltip"))
        top_row.addWidget(star_icon)
        self._skill_star_labels[skill_id] = star_icon

        outer.addLayout(top_row)

        # Per-skill invested level (User-Wunsch, 2026-08-27): "-"/level/"+"
        # -- deliberately no upper bound shown/enforced yet (real cap varies
        # per skill and stacks from Skill Points + gear + Arcana + Daevanion
        # Board, none of which we can reliably derive per-skill from our
        # scraped data right now). Child QPushButtons inside this card
        # consume their own clicks, so pressing +/- doesn't also trigger
        # the card's own click handler.
        level_row = QHBoxLayout()
        level_row.setSpacing(6)
        level_row.addStretch(1)

        minus_btn = QPushButton()
        minus_btn.setObjectName("SkillLevelStepBtn")
        minus_btn.setIcon(_make_minus_icon(16))
        minus_btn.setIconSize(QSize(14, 14))
        minus_btn.setFixedSize(26, 26)
        minus_btn.setCursor(Qt.PointingHandCursor)
        minus_btn.clicked.connect(lambda checked=False, sid=skill_id: self._on_skill_level_changed(sid, -1))
        level_row.addWidget(minus_btn)

        manual_level = self._skill_levels.get(skill_id, 0)
        bonus_level = self._skill_bonus.get(skill_id, 0)
        wish_level = self._skill_arcana_wish.get(skill_id, 0)
        level_label = QLabel(_format_skill_level_html(manual_level, bonus_level, wish_level))
        level_label.setObjectName("SkillLevelValue")
        level_label.setAlignment(Qt.AlignCenter)
        level_label.setMinimumWidth(28)
        level_row.addWidget(level_label)
        self._skill_level_labels[skill_id] = level_label

        plus_btn = QPushButton()
        plus_btn.setObjectName("SkillLevelStepBtn")
        plus_btn.setIcon(_make_plus_icon(16))
        plus_btn.setIconSize(QSize(14, 14))
        plus_btn.setFixedSize(26, 26)
        plus_btn.setCursor(Qt.PointingHandCursor)
        plus_btn.clicked.connect(lambda checked=False, sid=skill_id: self._on_skill_level_changed(sid, 1))
        level_row.addWidget(plus_btn)

        level_row.addStretch(1)
        outer.addLayout(level_row)

        # Arcana wish counter (User-Wunsch, 2026-08-28/29): a THIRD,
        # independent -/+ counter -- "die zusaetzlichen Punkte, die man
        # nicht durch Daeva Board und Gear erreichen kann. Sie sollen als
        # Stuetze dienen, um die Sets fuer die Arcanas zu berechnen." Feeds
        # the Arcana Calculator button (arm_arcana_calculator_btn), not the
        # level display's own bonus math -- purely a planning target for
        # _arcana_compute_combinations. Stigma skills don't get one: no
        # Arcana card can ever target a Stigma skill (every real
        # skillCategory in arcana_info.json is Mastery/Active/Passive or
        # None for Stat cards -- never Stigma), so the counter would be
        # meaningless there.
        if skill_type in ("active", "passive"):
            # Live ceiling (User-Wunsch, 2026-08-29: "im Skillplaner bei
            # den lila Zahlen mit einkalkulieren beim setzen ... wenn ein
            # Skill bereits +4 ist, kann der Rest maximal noch +3 werden")
            # -- the independent half of that (ignores competition from
            # OTHER wishes, which depends on a Vigor/Magic split not
            # chosen yet at this point -- see _arcana_uncovered_reason for
            # that half once a Calculator run's specific split is known).
            ceiling = self._arcana_ceiling_for_skill(skill_id, skill_type)

            wish_row = QHBoxLayout()
            wish_row.setSpacing(4)
            wish_row.addStretch(1)

            if ceiling <= 0:
                no_card_label = QLabel(_t("arm_arcana_reason_no_card"))
                no_card_label.setStyleSheet("color: #64748b; font-size: 10px;")
                no_card_label.setWordWrap(True)
                no_card_label.setAlignment(Qt.AlignCenter)
                wish_row.addWidget(no_card_label, 1)
            else:
                wish_minus_btn = QPushButton()
                wish_minus_btn.setObjectName("ArcanaWishStepBtn")
                wish_minus_btn.setIcon(_make_minus_icon(12, _ARCANA_WISH_COLOR))
                wish_minus_btn.setIconSize(QSize(11, 11))
                wish_minus_btn.setFixedSize(20, 20)
                wish_minus_btn.setCursor(Qt.PointingHandCursor)
                wish_minus_btn.setToolTip(_t("arm_arcana_wish_tooltip"))
                wish_minus_btn.clicked.connect(lambda checked=False, sid=skill_id: self._on_skill_arcana_wish_changed(sid, -1))
                wish_row.addWidget(wish_minus_btn)

                max_hint_label = QLabel(_t("arm_arcana_max_hint", max=ceiling))
                max_hint_label.setStyleSheet("color: #64748b; font-size: 10px;")
                wish_row.addWidget(max_hint_label)

                wish_plus_btn = QPushButton()
                wish_plus_btn.setObjectName("ArcanaWishStepBtn")
                wish_plus_btn.setIcon(_make_plus_icon(12, _ARCANA_WISH_COLOR))
                wish_plus_btn.setIconSize(QSize(11, 11))
                wish_plus_btn.setFixedSize(20, 20)
                wish_plus_btn.setCursor(Qt.PointingHandCursor)
                wish_plus_btn.setToolTip(_t("arm_arcana_wish_tooltip"))
                wish_plus_btn.setEnabled(self._skill_arcana_wish.get(skill_id, 0) < ceiling)
                wish_plus_btn.clicked.connect(lambda checked=False, sid=skill_id: self._on_skill_arcana_wish_changed(sid, 1))
                wish_row.addWidget(wish_plus_btn)
                self._arcana_wish_plus_buttons[skill_id] = wish_plus_btn

            wish_row.addStretch(1)
            outer.addLayout(wish_row)

        card.clicked.connect(lambda checked=False, s=skill: self._on_skill_description_card_clicked(s))
        return card

    def _on_skill_level_changed(self, skill_id: str, delta: int):
        # Skill Points alone can raise a Passive/Active skill to at most
        # _SKILL_LEVEL_BASE_CAP (10) -- Stigma has its own separate point
        # pool/cap (_STIGMA_LEVEL_BASE_CAP, 20). Anything past that only
        # ever comes from Gear/Daevanion Board (self._skill_bonus), never
        # from this counter (User-Wunsch, 2026-08-28: "durch Skillpunkte
        # passive und aktive skills maximal 10 level erhalten können") --
        # previously unbounded above, only a floor of 0 was enforced.
        is_stigma = self._skill_id_to_type.get(skill_id) == "stigma"
        cap = _STIGMA_LEVEL_BASE_CAP if is_stigma else _SKILL_LEVEL_BASE_CAP
        new_value = max(0, min(cap, self._skill_levels.get(skill_id, 0) + delta))
        self._skill_levels[skill_id] = new_value
        label = self._skill_level_labels.get(skill_id)
        if label:
            bonus_level = self._skill_bonus.get(skill_id, 0)
            wish_level = self._skill_arcana_wish.get(skill_id, 0)
            label.setText(_format_skill_level_html(new_value, bonus_level, wish_level))
        self._refresh_skillpoints_label()
        self._refresh_stigma_points_label()
        # Keep an already-open description panel's damage numbers in sync
        # (User-reported, 2026-08-29 -- see _render_selected_skill_
        # description's docstring).
        if self._skill_desc_selected_id == skill_id:
            skill = self._skill_id_to_skill.get(skill_id)
            if skill:
                self._render_selected_skill_description(skill)

    def _on_skill_arcana_wish_changed(self, skill_id: str, delta: int):
        skill_type = self._skill_id_to_type.get(skill_id)
        ceiling = self._arcana_ceiling_for_skill(skill_id, skill_type)
        new_value = max(0, min(ceiling, self._skill_arcana_wish.get(skill_id, 0) + delta))
        self._skill_arcana_wish[skill_id] = new_value
        label = self._skill_level_labels.get(skill_id)
        if label:
            manual_level = self._skill_levels.get(skill_id, 0)
            bonus_level = self._skill_bonus.get(skill_id, 0)
            label.setText(_format_skill_level_html(manual_level, bonus_level, new_value))
        plus_btn = self._arcana_wish_plus_buttons.get(skill_id)
        if plus_btn:
            plus_btn.setEnabled(new_value < ceiling)
        self._refresh_arcana_calculator_button()
        # Wish now counts toward the damage preview too (User-Wunsch,
        # 2026-08-29) -- keep an already-open description in sync, same as
        # _on_skill_level_changed already does for the white/blue counters.
        if self._skill_desc_selected_id == skill_id:
            skill = self._skill_id_to_skill.get(skill_id)
            if skill:
                self._render_selected_skill_description(skill)

    def _arcana_usable_and_pools(self) -> tuple[list[str], dict[str, list[dict]]]:
        """This class's usable Lord types + their (grade-independent)
        skill pools -- shared by the live per-skill ceiling hint and the
        actual Calculator run, so both agree on the exact same candidate
        set."""
        usable_types = _arcana_usable_lord_types(self._arcana_theme_map, _ARCANA_ACTIVE_THEMES)
        class_key = _skills_data_class_key(self.character_class_combo.currentText())
        class_skill_pools = {ct: self._arcana_class_skills.get(ct, {}).get(class_key, []) for ct in usable_types}
        return usable_types, class_skill_pools

    def _arcana_ceiling_for_skill(self, skill_id: str, skill_type: str) -> int:
        """Live, always-on version of the "how much could this skill ever
        gain from Arcana" question (User-Wunsch, 2026-08-29: "im Skillplaner
        bei den lila Zahlen mit einkalkulieren beim setzen") -- the
        independent ceiling only (ignores what OTHER wishes might also
        need from the same shared card-type pool, since that competitive
        half depends on a specific Vigor/Magic split the user hasn't
        chosen yet at this point; see _arcana_uncovered_reason for that
        half once a Calculator run's specific split is known)."""
        usable_types, class_skill_pools = self._arcana_usable_and_pools()
        return _arcana_max_ceiling(skill_id, skill_type, usable_types, class_skill_pools)

    def _refresh_arcana_calculator_button(self):
        has_wish = any(v > 0 for v in self._skill_arcana_wish.values())
        self.arcana_calculator_btn.setEnabled(has_wish)

    def _on_arcana_calculator_clicked(self):
        wishes = {sid: v for sid, v in self._skill_arcana_wish.items() if v > 0}
        if not wishes:
            return

        usable_types, class_skill_pools = self._arcana_usable_and_pools()

        theme_dialog = ArcanaThemeChoiceDialog(usable_types, self._arcana_theme_map, self)
        if theme_dialog.exec() != QDialog.Accepted or not theme_dialog.type_to_theme:
            return

        results = _arcana_compute_combinations(
            usable_types, theme_dialog.type_to_theme, class_skill_pools, wishes, self._skill_id_to_type,
            priority_rank=self._skill_priority_rank(), max_results=3,
        )
        skill_names = {sid: (self._find_skill_by_id(sid) or {}).get("name", sid) for sid in wishes}
        results_dlg = ArcanaResultsDialog(
            results, wishes, skill_names, self._arcana_theme_map, usable_types,
            class_skill_pools, self._skill_id_to_type, theme_dialog.type_to_theme, self,
        )
        results_dlg.arcana_combination_chosen.connect(self._on_apply_arcana_combination)
        results_dlg.exec()

    def _on_apply_arcana_combination(self, assignment_by_type: dict):
        """Writes one Arcana Calculator result into a build's "Sets" slots
        (User-Wunsch, 2026-08-29: "einen Button in den Calc, der dafuer
        sorgt, dass die richtigen Karten in die Slots kommen"). Always asks
        WHICH build first via ArcanaApplyTargetDialog (User-Wunsch, same
        day: "falls jemand vergessen hat, das Buildprofil zu aendern,
        darunter sein Zielprofil zu waehlen, oder ein neues Profil
        anzulegen") -- not just a plain overwrite-confirmation anymore,
        since the point is catching a wrong ACTIVE build before it happens,
        not only warning once it's about to overwrite something. A
        separate overwrite confirmation still fires if the CHOSEN target
        already has cards."""
        class_name = self.character_class_combo.currentText().strip().lower()
        self._ensure_class_builds(class_name)
        builds = self._skill_builds_data[class_name]
        current_build_name = self._current_build_name
        other_builds = [name for name in builds if name != current_build_name]

        dlg = ArcanaApplyTargetDialog(current_build_name, other_builds, self)
        if dlg.exec() != QDialog.Accepted or not dlg.result_build_name:
            return
        target_name = dlg.result_build_name

        if dlg.result_is_new:
            builds[target_name] = self._empty_build_state()
        elif builds.get(target_name, {}).get("arcana_cards"):
            reply = QMessageBox.question(
                self, _t("arm_arcana_overwrite_title"), _t("arm_arcana_overwrite_hint"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        target_build = builds[target_name]
        target_build["arcana_cards"] = {
            # Calculator always reasons about the best/maxed case (see its
            # own docstring), so a fresh Apply always writes grade=Unique
            # (the full 5-point budget) -- the user can still manually pull
            # a card down to Rare/Legend afterward via its grade pills.
            ct: {"theme": a["theme"], "grade": _ARCANA_DEFAULT_GRADE,
                 "slots": [{"skill_id": sid, "level": lvl} for sid, lvl in a["skill_ids"].items()]}
            for ct, a in assignment_by_type.items()
        }

        if target_name != current_build_name:
            self._save_current_build_state(class_name)
            self._current_build_name = target_name
            self._rebuild_skill_build_tabs()
            self._load_current_build_state()  # also covers _refresh_arcana_equip_slots/_recompute_skill_bonus
        else:
            self._refresh_arcana_equip_slots()
            # See _on_arcana_skill_slot_clicked's own call to this for why.
            self._recompute_skill_bonus()

        # Reset every Arcana wish once real cards have been generated and
        # applied (User-Wunsch, 2026-08-29: "sobald die Arcana Karten
        # generiert und gesetzt wurden, [sollten] die Wishzahlen dann
        # resettet werden") -- the wish's whole purpose was feeding this
        # exact Apply step, and now that it counts toward the damage
        # preview too, leaving it non-zero afterward would double-count
        # the same level increase in both the blue Arcana-card bonus AND
        # the purple wish.
        self._skill_arcana_wish = {}
        for skill_id, plus_btn in self._arcana_wish_plus_buttons.items():
            ceiling = self._arcana_ceiling_for_skill(skill_id, self._skill_id_to_type.get(skill_id))
            plus_btn.setEnabled(ceiling > 0)
        self._refresh_skill_level_labels()
        self._refresh_arcana_calculator_button()
        if self._skill_desc_selected_id:
            selected = self._skill_id_to_skill.get(self._skill_desc_selected_id)
            if selected:
                self._render_selected_skill_description(selected)

    def _refresh_arcana_equip_slots(self):
        """Repaints the "Sets" tab's 5 slot widgets from the current
        build's arcana_cards -- assigned slots show the real Lord/effect/
        grade dots (same _ArcanaCardButton.set_themed_state the
        "Informationen" browser already uses), unassigned ones stay in
        the neutral default/"Empty" state. Also fills each card's 4 fixed
        skill-slot boxes (User-Wunsch, 2026-08-29) straight from the real
        per-card assignment (arcana_cards[ct]["slots"], a positional list
        migrated on the fly from any older {skill_ids: {...}} shape via
        _arcana_card_slot_list -- see that helper's docstring) -- NOT
        filtered by self._skill_levels like the discarded previous
        approach, since a card's slots are their own fixed structure,
        independent of whatever else the player has leveled in the Skill
        Planner. The grade pills (User-Wunsch, 2026-08-29, manual editing)
        reflect arcana_cards[ct]["grade"], independent of "theme"."""
        class_name = self.character_class_combo.currentText().strip().lower()
        build = self._skill_builds_data.get(class_name, {}).get(self._current_build_name, {})
        arcana_cards = build.get("arcana_cards") or {}
        for ct, card in self._arcana_equip_slot_widgets.items():
            assignment = arcana_cards.get(ct)
            theme = assignment.get("theme") if assignment else None
            entry = self._arcana_theme_map.get(theme, {}).get(ct) if theme else None
            if entry:
                card.set_themed_state(entry)
            else:
                card.set_default_state(self._arcana_default_icon.get(ct))
            card.set_grade(_arcana_card_grade(assignment))
            # Gated behind a Set actually being chosen (User-Wunsch,
            # 2026-08-29: "Erst wenn eine Karte und Set gewaehlt wurde,
            # dann kann man Skills und deren Level waehlen").
            card.set_slots_enabled(theme is not None)

            slots = _arcana_card_slot_list(assignment)
            pool = self._arcana_class_skills.get(ct, {}).get(class_name, [])
            id_to_skill = {s["id"]: s for s in pool}
            card.set_skill_slots(slots, id_to_skill)

    def _on_arcana_card_set_clicked(self, card_type: str):
        """A Sets-tab card itself was clicked -- lets the user manually
        pick which Set/theme this slot represents (User-Wunsch, 2026-08-
        29: "Hier fehlt noch die Option, Karte und Set zu waehlen"),
        independent of the Calculator. Only offers this Season's active
        themes (_ARCANA_ACTIVE_THEMES) that actually have an entry for
        this card type -- e.g. a theme where this card type doesn't exist
        at all is never offered. Doesn't touch any already-picked skill
        slots even if the Set changes -- see _on_arcana_card_grade_changed
        for the same reasoning (never destroys existing manual data)."""
        class_name = self.character_class_combo.currentText().strip().lower()
        self._ensure_class_builds(class_name)
        build = self._skill_builds_data[class_name][self._current_build_name]
        arcana_cards = build.setdefault("arcana_cards", {})
        card_data = arcana_cards.setdefault(card_type, {})
        current_theme = card_data.get("theme")

        options = [
            (theme, self._arcana_theme_map[theme][card_type])
            for theme in _ARCANA_ACTIVE_THEMES
            if card_type in self._arcana_theme_map.get(theme, {})
        ]
        if not options:
            return

        dlg = ArcanaCardThemeDialog(options, current_theme, self)
        if dlg.exec() != QDialog.Accepted:
            return
        card_data["theme"] = dlg.result_theme
        arcana_cards[card_type] = card_data
        self._refresh_arcana_equip_slots()

    def _on_arcana_card_grade_changed(self, card_type: str, grade: str):
        """A card's rarity pill was clicked (User-Wunsch, 2026-08-29) --
        just persists the new grade; doesn't retroactively clamp any
        already-set skill levels down even if the new grade's budget is
        now smaller than what's spent (mirrors how the game itself would
        only ever let a card's level go up, never down -- and the next
        _on_arcana_skill_slot_clicked for any slot will correctly compute
        a reduced/zero remaining budget from here on regardless)."""
        class_name = self.character_class_combo.currentText().strip().lower()
        self._ensure_class_builds(class_name)
        build = self._skill_builds_data[class_name][self._current_build_name]
        arcana_cards = build.setdefault("arcana_cards", {})
        card_data = arcana_cards.setdefault(card_type, {})
        card_data["grade"] = grade
        card_data.setdefault("slots", _arcana_card_slot_list(card_data))
        self._refresh_arcana_equip_slots()

    def _on_arcana_skill_slot_clicked(self, card_type: str, slot_index: int):
        """Opens the manual skill+level picker for one of a card's 4 fixed
        slots (User-Wunsch, 2026-08-29: "Jede der 4 Skill-Zeilen einzeln
        anklickbar"). Pool is this card type's real class skill pool
        (respecting its fixed Active/Passive/both category, same as the
        Calculator/solver) minus whatever the other 3 slots already use;
        remaining budget is the card's grade budget minus what those other
        3 slots have already spent above baseline."""
        class_name = self.character_class_combo.currentText().strip().lower()
        self._ensure_class_builds(class_name)
        build = self._skill_builds_data[class_name][self._current_build_name]
        arcana_cards = build.setdefault("arcana_cards", {})
        card_data = arcana_cards.setdefault(card_type, {})
        slots = _arcana_card_slot_list(card_data)
        grade = _arcana_card_grade(card_data)

        category = _ARCANA_LORD_CATEGORY.get(card_type, "both")
        full_pool = self._arcana_class_skills.get(card_type, {}).get(class_name, [])
        eligible = [s for s in full_pool if category == "both" or s.get("type") == category]
        used_elsewhere = {
            slots[i]["skill_id"] for i in range(len(slots))
            if i != slot_index and slots[i]
        }
        available = [s for s in eligible if s.get("id") not in used_elsewhere]

        spent_elsewhere = sum(
            max(0, slots[i]["level"] - _ARCANA_SKILL_BASELINE) for i in range(len(slots))
            if i != slot_index and slots[i]
        )
        remaining_budget = max(0, _ARCANA_GRADE_MAX_LEVEL.get(grade, _ARCANA_MAX_CARD_LEVEL) - spent_elsewhere)

        dlg = ArcanaSkillSlotDialog(available, remaining_budget, slots[slot_index], self)
        if dlg.exec() != QDialog.Accepted:
            return
        slots[slot_index] = dlg.result_entry
        card_data["slots"] = slots
        card_data["grade"] = grade
        arcana_cards[card_type] = card_data
        self._refresh_arcana_equip_slots()
        # The blue Skill Planner bonus (and any open description's damage
        # numbers) needs to follow a real skill/level assignment change --
        # _refresh_arcana_equip_slots only repaints the Sets-tab cards
        # themselves (User-Wunsch, 2026-08-29: "die Arcana Level, sobald
        # die Karten gesetzt sind, in die blaue Zahl einberechnen").
        self._recompute_skill_bonus()
        if self._skill_desc_selected_id:
            selected = self._skill_id_to_skill.get(self._skill_desc_selected_id)
            if selected:
                self._render_selected_skill_description(selected)

    def _on_skill_description_card_clicked(self, skill: dict):
        skill_id = skill.get("id")
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

        self._render_selected_skill_description(skill)

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

    def _render_selected_skill_description(self, skill: dict):
        """Renders skill_desc_text_label's damage-aware description text --
        factored out of _on_skill_description_card_clicked so
        _on_skill_level_changed can also call it (User-reported, 2026-08-
        29: "Aktuell werden beim Skill selber die Zahlen beim Level vom
        Skill nicht veraendert" -- leveling a skill while its description
        was already open didn't refresh the shown numbers at all)."""
        skill_id = skill.get("id")

        # Effective skill level: manual + gear/Daevanion/Arcana-card bonus
        # + the Arcana WISH counter -- User-Wunsch, 2026-08-29: "Ich denke,
        # die Wish Zahl kann gerne auch mit den Schaden erhoehen", reversing
        # the earlier "wish is purely hypothetical" stance now that a real
        # Arcana card assignment resets the wish back to 0 once applied
        # (see _on_apply_arcana_combination), so double-counting can't
        # happen: either the wish still represents an ungranted target (fair
        # to preview), or it's already 0 because a real card now covers it.
        # Floored at 1 so an un-leveled skill still shows a sensible
        # level-1 preview instead of an out-of-range lookup. This used to
        # be hardcoded to 1 regardless of the invested level at all.
        manual_level = self._skill_levels.get(skill_id, 0)
        bonus_level = self._skill_bonus.get(skill_id, 0)
        wish_level = self._skill_arcana_wish.get(skill_id, 0)
        effective_level = max(1, manual_level + bonus_level + wish_level)

        # Estimated damage range (User-Wunsch, 2026-08-29) -- appended
        # right after the real numbers inside the description text itself
        # when the toggle is on and this is an active skill.
        estimate_multiplier = None
        if self.skill_estimated_damage_btn.isChecked() and skill.get("type") == "active":
            totals = self._compute_stat_totals(self._equipped, self._equipped_substats, self._equipped_enchant)
            estimate_multiplier = _skill_damage_estimate_multiplier(totals)
        self.skill_desc_text_label.setText(
            _render_skill_description(skill.get("description", ""), skill.get("levels"), effective_level, estimate_multiplier)
        )

    # ── "Daevanion Board" tab (2026-08-28) ───────────────────────────────────
    # Ported from the approved browser mockup -- see [[project_daevanion_
    # board_port]] for the full requirement list this was checked against.
    # Skill/GearScore integration (feeding node effects into the Skill
    # Planner and Stat Info/GearScore) and Stat-Priority-List-aware sidebar
    # ordering are NOT wired up yet (still open per that memory's points 1-3)
    # -- this is the board + routing itself. Board state (which nodes are
    # active) is session-only for now, keyed by "<variant>:<boardId>", not
    # yet persisted into profiles/equip builds.

    def _build_daevanion_board_tab(self) -> QWidget:
        self._daevanion_variant = "s"
        self._daevanion_order: int | None = None
        self._daevanion_active: dict[str, set[str]] = {}
        self._daevanion_filter_checked: dict[str, set[str]] = {}
        self._daevanion_hovered_node: dict | None = None

        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        if _DAEVANION_DEV_MODE:
            variant_row = QHBoxLayout()
            variant_row.setSpacing(6)
            variant_group = QButtonGroup(self)
            variant_group.setExclusive(True)
            self._daevanion_variant_buttons: dict[str, QPushButton] = {}
            for key, label in (("s", "Start"), ("a", "Advanced (dev)")):
                btn = QPushButton(label)
                btn.setObjectName("SkillFilterButton")
                btn.setCheckable(True)
                btn.setChecked(key == self._daevanion_variant)
                btn.clicked.connect(lambda checked=False, k=key: self._daevanion_switch_variant(k))
                variant_group.addButton(btn)
                variant_row.addWidget(btn)
                self._daevanion_variant_buttons[key] = btn
            variant_row.addStretch(1)
            outer.addLayout(variant_row)

        header_row = QHBoxLayout()
        header_row.setSpacing(6)
        self._daevanion_deity_tabs_row = QHBoxLayout()
        self._daevanion_deity_tabs_row.setSpacing(6)
        header_row.addLayout(self._daevanion_deity_tabs_row)
        header_row.addStretch(1)

        budget_col = QVBoxLayout()
        budget_col.setSpacing(2)
        self._daevanion_budget_label = QLabel()
        self._daevanion_budget_label.setObjectName("EquipSectionLabel")
        budget_col.addWidget(self._daevanion_budget_label)
        header_row.addLayout(budget_col)

        reset_btn = QPushButton(_t("arm_reset_board"))
        reset_btn.setObjectName("SkillFilterButton")
        reset_btn.clicked.connect(self._daevanion_on_reset)
        header_row.addWidget(reset_btn)
        outer.addLayout(header_row)

        body_row = QHBoxLayout()
        body_row.setSpacing(16)

        # A QScrollArea (not a shrink-wrapped fixed-size frame) since the
        # canvas itself now resizes with mouse-wheel zoom (User-Wunsch,
        # 2026-08-28: "die Map mit den Nodes zoomable machen mit Mausrad") --
        # the viewport stays a fixed, reasonable size and scrolls once the
        # zoomed-in board no longer fits.
        canvas_scroll = QScrollArea()
        canvas_scroll.setObjectName("DaevanionCanvasFrame")
        canvas_scroll.setWidgetResizable(False)
        # Sized generously above the unzoomed board (512px) so scrollbars
        # only ever appear once you've genuinely zoomed in past what fits
        # -- User-Wunsch, 2026-08-28: at the old 640px size, a small early
        # zoom step (real board=642px) crossed the threshold by only ~4px,
        # triggering scrollbars for an overflow too small to visually
        # notice ("warum erscheinen Scrollbalken, wenn doch alle Nodes
        # sichtbar sind"). Same 15x15/225-node grid on every board/variant,
        # so this threshold behavior was identical everywhere, not
        # board-specific -- confirmed across multiple zoom levels.
        canvas_scroll.setFixedSize(760, 760)
        canvas_scroll.setAlignment(Qt.AlignCenter)
        canvas_scroll.viewport().setStyleSheet("background: transparent;")
        self._daevanion_canvas = DaevanionBoardCanvas()
        self._daevanion_canvas.nodeClicked.connect(self._daevanion_on_node_clicked)
        self._daevanion_canvas.nodeHovered.connect(self._daevanion_on_node_hovered)
        self._daevanion_tooltip = DaevanionNodeTooltip(self)
        canvas_scroll.setWidget(self._daevanion_canvas)
        self._daevanion_canvas.set_scroll_area(canvas_scroll)
        body_row.addWidget(canvas_scroll, 0)

        sidebar = QWidget()
        sidebar.setFixedWidth(300)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(8)

        route_btn = QPushButton(_t("arm_daevanion_find_route"))
        route_btn.setObjectName("EqPriorityButton")
        route_btn.clicked.connect(self._daevanion_on_route)
        sidebar_layout.addWidget(route_btn)

        self._daevanion_route_status_label = QLabel()
        self._daevanion_route_status_label.setObjectName("DetailDisclaimer")
        self._daevanion_route_status_label.setWordWrap(True)
        sidebar_layout.addWidget(self._daevanion_route_status_label)

        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.NoFrame)
        self._daevanion_sidebar_content = QWidget()
        self._daevanion_sidebar_layout = QVBoxLayout(self._daevanion_sidebar_content)
        self._daevanion_sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self._daevanion_sidebar_layout.setSpacing(8)
        self._daevanion_sidebar_layout.addStretch(1)
        sidebar_scroll.setWidget(self._daevanion_sidebar_content)
        sidebar_layout.addWidget(sidebar_scroll, 1)

        body_row.addWidget(sidebar, 1)
        outer.addLayout(body_row, 1)

        self._daevanion_rebuild_deity_tabs()
        self._daevanion_refresh()
        return page

    def _daevanion_class_key(self) -> str:
        return _skills_data_class_key(self.character_class_combo.currentText())

    def _daevanion_current_board(self) -> dict | None:
        variant = _daevanion_variant(self._daevanion_variant)
        class_key = self._daevanion_class_key()
        if class_key not in variant["class_ids"]:
            return None
        if self._daevanion_order not in variant["deity_orders"]:
            self._daevanion_order = variant["deity_orders"][0] if variant["deity_orders"] else None
        if self._daevanion_order is None:
            return None
        return variant["board_by_class_order"].get((class_key, self._daevanion_order))

    def _daevanion_active_set(self, board: dict, grid: dict) -> set[str]:
        key = self._daevanion_variant + ":" + board["id"]
        if key not in self._daevanion_active:
            start_id = next((n["id"] for n in grid.values() if n["g"] == "start"), None)
            self._daevanion_active[key] = {start_id} if start_id else set()
        return self._daevanion_active[key]

    def _daevanion_filter_set(self) -> set[str]:
        """Shared across every board/deity of the CURRENT class within the
        current variant (User-Wunsch, 2026-08-28: "den Filter fuer alle
        Daevanion Seiten behalten") -- full_key is stat-name/skill-id
        based, not board-specific, so a value checked once stays checked
        on any other board of the same class that happens to carry it too;
        a board without that value simply never lists it as an option, so
        nothing extra needs pruning when switching boards. Keyed by class
        too (not just variant) -- skill full_keys are skill-IDs, which are
        only meaningful within one class, and a stat filter checked for one
        class showing checked under an unrelated class would be confusing
        (real bug found by user, 2026-08-28: switching from Gladiator to
        Chanter kept Gladiator's checked substats highlighted)."""
        key = self._daevanion_variant + ":" + self._daevanion_class_key()
        if key not in self._daevanion_filter_checked:
            self._daevanion_filter_checked[key] = set()
        return self._daevanion_filter_checked[key]

    def _daevanion_switch_variant(self, variant: str):
        if variant == self._daevanion_variant:
            return
        self._daevanion_variant = variant
        self._daevanion_order = None
        self._daevanion_rebuild_deity_tabs()
        self._daevanion_refresh()

    def _daevanion_rebuild_deity_tabs(self):
        _clear_layout(self._daevanion_deity_tabs_row)
        variant = _daevanion_variant(self._daevanion_variant)
        class_key = self._daevanion_class_key()
        if class_key not in variant["class_ids"]:
            return
        if self._daevanion_order not in variant["deity_orders"]:
            self._daevanion_order = variant["deity_orders"][0] if variant["deity_orders"] else None
        group = QButtonGroup(self)
        group.setExclusive(True)
        for order in variant["deity_orders"]:
            board = variant["board_by_class_order"].get((class_key, order))
            if not board:
                continue
            btn = QPushButton(board["name"])
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(order == self._daevanion_order)
            btn.clicked.connect(lambda checked=False, o=order: self._daevanion_switch_order(o))
            group.addButton(btn)
            self._daevanion_deity_tabs_row.addWidget(btn)

    def _daevanion_switch_order(self, order: int):
        if order == self._daevanion_order:
            return
        self._daevanion_order = order
        self._daevanion_refresh()

    def _daevanion_refresh(self):
        """Equivalent of the mockup's draw()+renderFilterPanel() -- redraws
        the canvas, budget readout and rebuilds the sidebar to match
        whatever board is currently selected."""
        self._daevanion_tooltip.hide()
        board = self._daevanion_current_board()
        if not board:
            self._daevanion_canvas.set_data({}, set(), set(), {})
            self._daevanion_budget_label.setText(_t("arm_daevanion_no_board_for_class"))
            _clear_layout(self._daevanion_sidebar_layout)
            self._daevanion_sidebar_layout.addStretch(1)
            return
        variant = _daevanion_variant(self._daevanion_variant)
        grid = variant["nodes_by_board"].get(board["id"], {})
        active = self._daevanion_active_set(board, grid)
        highlighted = self._daevanion_highlighted_ids(board, grid)
        class_skills_by_id = {str(s["id"]): s for s in self._skills_by_class.get(self._daevanion_class_key(), [])}
        node_icons = self._daevanion_build_node_icons(grid, class_skills_by_id)
        self._daevanion_canvas.set_data(grid, active, highlighted, node_icons)

        spent = _daevanion_spent_cost(active, variant["node_by_id"])
        cap = _daevanion_total_cost(grid)
        self._daevanion_budget_label.setText(_t("arm_daevanion_points_label", spent=spent, cap=cap))

        for i in range(self._daevanion_deity_tabs_row.count()):
            btn = self._daevanion_deity_tabs_row.itemAt(i).widget()
            if isinstance(btn, QPushButton):
                order = variant["deity_orders"][i] if i < len(variant["deity_orders"]) else None
                btn.setChecked(order == self._daevanion_order)

        self._daevanion_rebuild_sidebar(board, grid)

    def _daevanion_build_node_icons(self, grid: dict, class_skills_by_id: dict) -> dict[str, "QPixmap"]:
        """Real skill icon (same assets the Skill Description cards use)
        for skill-granting nodes -- stat-granting nodes get no overlay at
        all (just the real tier-frame sprite underneath), the sidebar's own
        filter/search already covers finding a specific stat, so a label on
        every tile was redundant clutter (User-Wunsch, 2026-08-28: "Die
        Werte kannst du von den Kacheln auch entfernen. Durch den Filter
        auf der rechten Seite, brauchen wir die links nicht")."""
        icons: dict[str, QPixmap] = {}
        for n in grid.values():
            if n["g"] in ("empty", "start"):
                continue
            skill_effs = [e for e in n.get("e") or [] if e.get("t") == "k"]
            if skill_effs:
                skill_id = str(skill_effs[0].get("skill_id") or "")
                skill = class_skills_by_id.get(skill_id)
                icon = _skill_icon(skill) if skill else None
                if icon and not icon.isNull():
                    icons[n["id"]] = icon.pixmap(28, 28)
        return icons

    def _daevanion_build_filter_groups(self, grid: dict) -> dict[str, dict[str, dict]]:
        class_key = self._daevanion_class_key()
        class_skills = self._skills_by_class.get(class_key, [])
        class_skills_by_id = {str(s["id"]): s for s in class_skills}
        groups = {"substats": {}, "combined": {}, "passive": {}, "active": {}}
        for n in grid.values():
            stat_effs = [e for e in n.get("e") or [] if e.get("t") == "s"]
            skill_effs = [e for e in n.get("e") or [] if e.get("t") == "k"]
            if len(stat_effs) == 1:
                name = stat_effs[0].get("n") or ""
                label = _daevanion_stat_label(name)
                entry = groups["substats"].setdefault(name, {"label": label, "ids": set(), "grades": set()})
                entry["ids"].add(n["id"])
                entry["grades"].add(n["g"])
            elif len(stat_effs) > 1:
                names = sorted(e.get("n") or "" for e in stat_effs)
                key = "+".join(names)
                labels = [_daevanion_stat_label(nm) for nm in names]
                entry = groups["combined"].setdefault(key, {"label": " + ".join(labels), "ids": set(), "grades": set()})
                entry["ids"].add(n["id"])
                entry["grades"].add(n["g"])
            for e in skill_effs:
                skill_id = str(e.get("skill_id") or "")
                skill = class_skills_by_id.get(skill_id)
                name = skill.get("name") if skill else (e.get("n") or f"Skill #{skill_id}")
                bucket = "active" if (skill and skill.get("type") == "active") else "passive"
                entry = groups[bucket].setdefault(skill_id or name, {"label": name, "ids": set(), "grades": set()})
                entry["ids"].add(n["id"])
                entry["grades"].add(n["g"])
        return groups

    _DAEVANION_GRADE_RANK = {"unique": 3, "legend": 2, "rare": 1, "common": 0, "start": -1, "empty": -1}

    def _daevanion_entry_accent_color(self, grades: set[str]) -> str | None:
        """Highest-tier grade among an entry's nodes gets its board color as
        a text accent in the sidebar (User-Wunsch, 2026-08-28: "die goldenen
        oder epic nodes farbig markieren ... falls andere Statnodes mit blau
        oder gruen existieren, diese farbig markieren") -- Common-only
        entries stay the default label color, nothing to call out there."""
        best = max(grades, default="common", key=lambda g: self._DAEVANION_GRADE_RANK.get(g, -1))
        if self._DAEVANION_GRADE_RANK.get(best, -1) <= 0:
            return None
        return _DAEVANION_GRADE_HEX.get(best)

    def _daevanion_highlighted_ids(self, board: dict, grid: dict) -> set[str]:
        checked = self._daevanion_filter_set()
        if not checked:
            return set()
        groups = self._daevanion_build_filter_groups(grid)
        ids: set[str] = set()
        for full_key in checked:
            cat, _, key = full_key.partition("|")
            entry = groups.get(cat, {}).get(key)
            if entry:
                ids |= entry["ids"]
        return ids

    _DAEVANION_FILTER_SECTIONS = [
        ("substats", "arm_daevanion_substats"), ("combined", "arm_daevanion_combined_substats"),
        ("passive", "arm_daevanion_passive_skills"), ("active", "arm_daevanion_active_skills"),
    ]

    def _daevanion_build_collapsible(self, title: str, expanded: bool) -> tuple[QWidget, QVBoxLayout]:
        return _build_collapsible_section(title, expanded)

    def _daevanion_rebuild_sidebar(self, board: dict, grid: dict):
        _clear_layout(self._daevanion_sidebar_layout)
        groups = self._daevanion_build_filter_groups(grid)
        checked = self._daevanion_filter_set()
        for i, (cat_key, label_key) in enumerate(self._DAEVANION_FILTER_SECTIONS):
            entries = sorted(groups[cat_key].items(), key=lambda kv: kv[1]["label"])
            section, body_layout = self._daevanion_build_collapsible(f"{_t(label_key)} ({len(entries)})", expanded=(i == 0))
            for key, entry in entries:
                full_key = cat_key + "|" + key
                cb = QCheckBox(f"{entry['label']} (×{len(entry['ids'])})")
                cb.setChecked(full_key in checked)
                accent = self._daevanion_entry_accent_color(entry.get("grades", set()))
                if accent:
                    cb.setStyleSheet(f"color: {accent}; font-weight: 600;")
                cb.toggled.connect(lambda on, fk=full_key: self._daevanion_on_filter_toggled(fk, on))
                body_layout.addWidget(cb)
            self._daevanion_sidebar_layout.addWidget(section)
        self._daevanion_sidebar_layout.addStretch(1)

    def _daevanion_on_filter_toggled(self, full_key: str, checked: bool):
        board = self._daevanion_current_board()
        if not board:
            return
        checked_set = self._daevanion_filter_set()
        if checked:
            checked_set.add(full_key)
        else:
            checked_set.discard(full_key)
        self._daevanion_route_status_label.setText("")
        variant = _daevanion_variant(self._daevanion_variant)
        grid = variant["nodes_by_board"].get(board["id"], {})
        active = self._daevanion_active_set(board, grid)
        highlighted = self._daevanion_highlighted_ids(board, grid)
        class_skills_by_id = {str(s["id"]): s for s in self._skills_by_class.get(self._daevanion_class_key(), [])}
        node_icons = self._daevanion_build_node_icons(grid, class_skills_by_id)
        self._daevanion_canvas.set_data(grid, active, highlighted, node_icons)

    def _daevanion_on_node_clicked(self, node_id: str):
        board = self._daevanion_current_board()
        if not board:
            return
        variant = _daevanion_variant(self._daevanion_variant)
        grid = variant["nodes_by_board"].get(board["id"], {})
        node = variant["node_by_id"].get(node_id)
        if not node or node["g"] in ("start", "empty"):
            return
        active = self._daevanion_active_set(board, grid)
        if node_id in active:
            active.discard(node_id)
            self._daevanion_prune_unreachable(grid, active, variant["node_by_id"])
        elif _daevanion_is_reachable(node, grid, active):
            cap = _daevanion_total_cost(grid)
            spent = _daevanion_spent_cost(active, variant["node_by_id"])
            if spent + node["cost"] <= cap:
                active.add(node_id)
        self._daevanion_refresh()
        self._recompute_skill_bonus()
        self._daevanion_show_tooltip(node)

    def _daevanion_prune_unreachable(self, grid: dict, active: set[str], node_by_id: dict):
        """Cascade-remove any active (non-start) node no longer connected
        to start, mirroring the mockup's pruneUnreachable exactly."""
        changed = True
        while changed:
            changed = False
            for nid in list(active):
                node = node_by_id.get(nid)
                if not node or node["g"] == "start":
                    continue
                connected = any(
                    (nb := grid.get(rc)) and nb["id"] in active
                    for rc in _daevanion_neighbors(node["r"], node["c"])
                )
                if not connected:
                    active.discard(nid)
                    changed = True

    def _daevanion_on_node_hovered(self, node: dict | None):
        self._daevanion_hovered_node = node
        if not node or node["g"] == "empty":
            self._daevanion_tooltip.hide()
            return
        self._daevanion_show_tooltip(node)

    def _daevanion_show_tooltip(self, node: dict):
        board = self._daevanion_current_board()
        if not board:
            return
        variant = _daevanion_variant(self._daevanion_variant)
        grid = variant["nodes_by_board"].get(board["id"], {})
        active = self._daevanion_active_set(board, grid)
        class_key = self._daevanion_class_key()
        class_skills_by_id = {str(s["id"]): s for s in self._skills_by_class.get(class_key, [])}
        is_active = node["id"] in active
        reachable = not is_active and _daevanion_is_reachable(node, grid, active)
        cap = _daevanion_total_cost(grid)
        spent = _daevanion_spent_cost(active, variant["node_by_id"])

        grade_label = _DAEVANION_GRADE_LABEL.get(node["g"], node["g"])
        name = node.get("name") or grade_label
        grade_hex = _DAEVANION_GRADE_HEX.get(node["g"], "#94a3b8")
        effect_rows = _daevanion_effect_lines(node, class_skills_by_id)

        if node["g"] == "start":
            status_key, status_text = "start", _t("arm_daevanion_status_start")
        elif is_active:
            status_key, status_text = "active", _t("arm_daevanion_status_active")
        elif not reachable:
            status_key, status_text = "locked", _t("arm_daevanion_status_locked")
        elif spent + node["cost"] > cap:
            status_key, status_text = "no_points", _t("arm_daevanion_status_no_points")
        else:
            status_key, status_text = "available", _t("arm_daevanion_status_available")

        self._daevanion_tooltip.set_node(
            name, grade_label, grade_hex, node["cost"], node["lvl"], effect_rows, status_key, status_text
        )
        self._daevanion_tooltip.show_at(QCursor.pos())

    def _daevanion_on_reset(self):
        board = self._daevanion_current_board()
        if not board:
            return
        variant = _daevanion_variant(self._daevanion_variant)
        grid = variant["nodes_by_board"].get(board["id"], {})
        start_id = next((n["id"] for n in grid.values() if n["g"] == "start"), None)
        key = self._daevanion_variant + ":" + board["id"]
        self._daevanion_active[key] = {start_id} if start_id else set()
        self._daevanion_route_status_label.setText("")
        self._daevanion_refresh()
        self._recompute_skill_bonus()

    def _daevanion_on_route(self):
        board = self._daevanion_current_board()
        if not board:
            return
        variant = _daevanion_variant(self._daevanion_variant)
        grid = variant["nodes_by_board"].get(board["id"], {})
        wanted = self._daevanion_highlighted_ids(board, grid)
        if not wanted:
            self._daevanion_route_status_label.setText(_t("arm_daevanion_route_pick_value"))
            return
        start_id = next((n["id"] for n in grid.values() if n["g"] == "start"), None)
        result = _daevanion_compute_auto_route(grid, variant["node_by_id"], wanted, start_id)
        key = self._daevanion_variant + ":" + board["id"]
        self._daevanion_active[key] = result["tree"]
        if result["skipped"]:
            self._daevanion_route_status_label.setText(_t(
                "arm_daevanion_route_partial", included=len(result["included"]),
                total=len(result["included"]) + len(result["skipped"]), spent=result["spent"], cap=result["cap"],
            ))
        else:
            self._daevanion_route_status_label.setText(_t(
                "arm_daevanion_route_full", count=len(result["included"]), spent=result["spent"], cap=result["cap"],
            ))
        self._daevanion_refresh()
        self._recompute_skill_bonus()

    # ── "EQ-Priorität" tab ──────────────────────────────────────────────────

    def _build_equip_priority_page(self) -> QWidget:
        """Same idea as the Skill Planner's own priority list (see
        _build_skill_priority_tab): a chain of slots per section, '+' to
        append — here for planning an acquisition/upgrade order across
        specific equipment items instead of skills. Reuses ItemPickerPopup
        (search/grade filter/PvP-PvE filter) for picking, anchored to the
        clicked slot, same as a real Equipment-tab slot.

        Laid out 3 sections per row (grid) instead of one full-width row
        per section — with 11 sections stacked one-per-row the tab was
        mostly empty horizontal space either side of a short item chain.

        A full-panel takeover in equip_view_stack (back-arrow/X, same
        pattern as Build Vergleich) rather than its own main_tabs entry
        (User-Wunsch, 2026-08-28) -- freed that tab slot for the Daevanion
        Board instead."""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(16, 12, 16, 16)
        container_layout.setSpacing(10)

        # Styled circular pill (not a bare unstyled QToolButton, like Build
        # Vergleich/Stat Priority Editor's back/X currently are -- User-
        # Wunsch, 2026-08-28: "den Backpfeil und das 'X' an den Stil
        # anpassen") so they read as real themed buttons instead of native
        # Qt chrome floating on the dark background.
        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        back_btn = QToolButton()
        back_btn.setObjectName("PanelNavButton")
        back_btn.setIcon(_make_back_icon())
        back_btn.setIconSize(QSize(16, 16))
        back_btn.setFixedSize(32, 32)
        back_btn.setToolTip(_t("arm_back"))
        back_btn.clicked.connect(self._close_equip_priority_page)
        header_row.addWidget(back_btn)

        title = QLabel(_t("arm_eq_priority_tab"))
        title.setObjectName("DetailHeader")
        header_row.addWidget(title, 1)

        close_btn = QToolButton()
        close_btn.setObjectName("PanelNavButton")
        close_btn.setIcon(_make_close_icon())
        close_btn.setIconSize(QSize(16, 16))
        close_btn.setFixedSize(32, 32)
        close_btn.setToolTip(_t("arm_close"))
        close_btn.clicked.connect(self._close_equip_priority_page)
        header_row.addWidget(close_btn)
        container_layout.addLayout(header_row)

        # Scrollable body (unaffected by the header move) -- everything
        # below stays exactly as it was as a plain main_tabs page.
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
        container_layout.addWidget(scroll, 1)
        return container

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
        logger.info(
            "EQ-Priority slot clicked: section=%r index=%r anchor visible=%s geometry=%s",
            section_key, index, anchor.isVisible(), anchor.geometry(),
        )
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

        # Deferred a tick (User-reported, 2026-08-29: clicking any EQ-
        # Priority slot shows a tiny ~2x3cm empty window for under a
        # second, then nothing -- confirmed pre-existing since 1.4.0, not
        # caused by recent work here). These slot buttons sit inside a
        # QScrollArea's viewport (row_scroll in _build_equip_priority_page)
        # unlike the normal Equipment tab's single stable combo button --
        # opening a Qt.Popup synchronously from within the very click that
        # triggered it can race with that button's own pending mouse-
        # release/repaint, especially with a scroll-area ancestor still
        # settling geometry, and Windows appears to misread the trailing
        # event as an outside click and self-dismiss the popup instantly.
        # Not reproducible via offscreen/QTest simulated clicks here (both
        # show the popup rendering and staying open correctly), so this is
        # a targeted mitigation for the real-world timing race rather than
        # a confirmed root-cause fix -- please re-test on a real click.
        def _open_popup():
            logger.info("EQ-Priority _open_popup firing (deferred tick) for section=%r index=%r", section_key, index)
            try:
                equipped_ids = {item.get("id") for item in self._equipped.values() if item}
                logger.info("EQ-Priority building ItemPickerPopup: %d catalog items, %d equipped ids", len(self._items), len(equipped_ids))
                popup = ItemPickerPopup(
                    self._items, categories, self.icon_cache, self.detail_cache, self,
                    active_gear_types=self._active_gear_types,
                    equipped_ids=equipped_ids,
                )
                popup.item_chosen.connect(
                    lambda item, sk=section_key, i=index: self._on_equip_priority_item_chosen(sk, i, item)
                )
                # Kept alive via this reference — a Qt.Popup with no other
                # owner would otherwise get garbage-collected before it can
                # emit.
                self._active_picker_popup = popup
                logger.info("EQ-Priority popup constructed OK, calling show_anchored")
                popup.show_anchored(anchor)
                logger.info(
                    "EQ-Priority popup shown: visible=%s geometry=%s isActiveWindow=%s",
                    popup.isVisible(), popup.geometry(), popup.isActiveWindow(),
                )
            except Exception:
                # console=False in the packaged build (Aion2 TM.spec) means
                # an uncaught exception here would otherwise vanish with no
                # trace at all -- User-reported, 2026-08-29: "kurzes
                # Flackern und dann kein Popup" with no visible error,
                # exactly matching a silently-swallowed exception in a
                # windowed/no-console build. Logged here so app.log (via
                # Settings -> View Log) captures the real cause.
                logger.exception("EQ-Priority popup failed to open for section=%r index=%r", section_key, index)

        QTimer.singleShot(0, _open_popup)

    def _on_equip_priority_item_chosen(self, section_key: str, index: int, item: dict):
        self._equip_priority_items[section_key][index] = item
        self._rebuild_equip_priority_row(section_key)

    def _on_add_equip_priority_slot(self, section_key: str):
        if len(self._equip_priority_items[section_key]) >= _EQUIP_PRIORITY_MAX_ITEMS:
            return
        self._equip_priority_items[section_key].append(None)
        self._rebuild_equip_priority_row(section_key)

    def _open_equip_priority_page(self):
        self.equip_top_bar.setVisible(False)
        self.equip_view_stack.setCurrentIndex(self._equip_priority_page_index)

    def _close_equip_priority_page(self):
        self.equip_top_bar.setVisible(True)
        self.equip_view_stack.setCurrentIndex(0)

    # ── "Arcana & Titel" tab ────────────────────────────────────────────────

    def _build_arcana_tab(self) -> QWidget:
        """Main "Arcana" tab, now split into two sub-tabs (User-Wunsch,
        2026-08-29): "Informationen" (the existing browse-only card/set
        catalog, unchanged) and "Sets" (the real Arcana equip slots).
        The "Arcana Types" legend used to be duplicated inside each
        sub-tab's own layout -- now built once here as a permanent footer
        below both (User-Wunsch, 2026-08-29: "Kann man das eventuell als
        Dauerfooter setzen?"), so it stays visible no matter which
        sub-tab is active instead of scrolling away with either one."""
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        self._arcana_sub_tabs = QTabWidget()
        self._arcana_sub_tabs.setObjectName("timerModeTabWidget")
        self._arcana_sub_tabs.addTab(self._build_arcana_information_tab(), _t("arm_arcana_information_tab"))
        self._arcana_sub_tabs.addTab(self._build_arcana_sets_tab(), _t("arm_arcana_sets_tab"))
        outer.addWidget(self._arcana_sub_tabs, 1)
        outer.addWidget(self._build_arcana_lord_bar())
        return page

    def _build_arcana_information_tab(self) -> QWidget:
        content = QWidget()
        root = QHBoxLayout(content)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(30)
        root.addLayout(self._build_arcana_column())
        root.addStretch()

        # Scrollable now that each of the 10 cards can carry its own full
        # skill-pool list below it (User-Wunsch, 2026-08-29) -- same
        # overflow reasoning as the Sets tab's own scroll area.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setStyleSheet("background: transparent;")
        scroll.setWidget(content)
        return scroll

    def _build_arcana_sets_tab(self) -> QWidget:
        """"Sets" sub-tab: the 5 real Lord card slots (Chalice/Parchment/
        Compass/Bell/Mirror, matching the Calculator's usable types), no
        assignment functionality yet (User-Wunsch, 2026-08-29: "Unter Sets
        haben wir dann nur noch die Slots fuer die Arcanas, die moeglich
        sind ... Dort fuegen wir dann spaeter die ausgewaehlten Karten aus
        dem Calc ein"). Reuses the exact same _ArcanaCardButton widget (in
        its neutral "default"/empty state) as the "Informationen" browser
        tab, at the same size -- just without that tab's Set-selection
        sidebar, since these slots aren't about browsing a theme, they're
        the real equip target
        (User-Wunsch: "genauso aufbauen ... nur dass auf der linken Seite
        die Sets nicht angezeigt werden und die Kartenslots leer sind").
        Shares ONE build list with the Skill Planner via the mirrored
        arcana_build_tabs_row (see _rebuild_skill_build_tabs) -- switching
        builds here is the same as switching them in the Skill Planner."""
        tab = QWidget()
        page_layout = QVBoxLayout(tab)
        page_layout.setContentsMargins(16, 16, 16, 16)
        page_layout.setSpacing(12)
        page_layout.addLayout(self.arcana_build_tabs_row)

        # Scrollable below the (fixed) build-tabs row -- a card with a large
        # skill pool (e.g. Chalice/Time can run 20+ entries for some
        # classes) would otherwise overflow the window with no way to
        # reach the Cancel/Apply-less bottom, same reasoning as every other
        # long detail panel in this window (see equip_detail_scroll etc.).
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setStyleSheet("background: transparent;")

        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        grid = QGridLayout()
        grid.setSpacing(14)
        usable_types, _pools = self._arcana_usable_and_pools()
        self._arcana_equip_slot_widgets: dict[str, _ArcanaCardButton] = {}
        # 4 fixed skill-slot boxes inline on the card itself, no hover
        # (User-Wunsch, 2026-08-29, with a rough mockup screenshot: "Sets,
        # die durch den Calc oder User angelegt wurden, sollen kein Hover
        # Effekt haben. Dort werden ohnehin nur 4 Zeilen angezeigt ... In
        # die Boxen darunter zeigen wir dann die Skills der jeweiligen
        # Karte an") -- a real committed assignment, unlike the
        # Information tab's pure browsing/hover reference.
        for col_idx, ct in enumerate(usable_types):
            card = _ArcanaCardButton(ct, with_skill_slots=True)
            card.set_default_state(self._arcana_default_icon.get(ct))
            card.set_grade(_ARCANA_DEFAULT_GRADE)
            card.set_slots_enabled(False)
            card.skill_slot_clicked.connect(lambda idx, c=ct: self._on_arcana_skill_slot_clicked(c, idx))
            card.grade_changed.connect(lambda grade, c=ct: self._on_arcana_card_grade_changed(c, grade))
            card.clicked.connect(lambda checked=False, c=ct: self._on_arcana_card_set_clicked(c))
            grid.addWidget(card, 0, col_idx)
            self._arcana_equip_slot_widgets[ct] = card
        grid_row = QHBoxLayout()
        grid_row.addLayout(grid)
        grid_row.addStretch(1)
        outer.addLayout(grid_row)
        outer.addStretch(1)

        scroll.setWidget(content)
        page_layout.addWidget(scroll, 1)
        return tab

    def _build_arcana_column(self) -> QHBoxLayout:
        """Arcana Set/card browser, built from real data (see
        ARCANA_CARD_TYPES/ARCANA_THEME_ORDER above): 7 Sets on the left
        (colored by PvE/PvP/Offensiv/Defensiv/Heilung category, mutually
        exclusive with a "Keine Sets" neutral state) and all 10 real card
        slots on the right. Choosing a Set previews which real Empyrean
        Lord (or Main Stat, for the 4 Stat cards) and which grades each
        card would have, with the real class-specific skill pool that Lord
        could buff shown inline below each card (see _refresh_arcana_cards),
        using the class already selected up in the shared header
        (self._active_skill_class) rather than a separate class picker.
        Replaces the old 5-slot equip-picker mock-up — real player data
        (see project notes) confirmed all 10 card types and all 10 slots
        are actually live, not just 5. This is a browsing/reference tool
        for now, not wired into equip state, GearScore, or Stat Info —
        shugo.gg exposes no real numeric Arcana stat values to integrate
        with those anyway."""
        root = QHBoxLayout()
        root.setSpacing(24)

        self._arcana_theme_map, self._arcana_default_icon = _load_arcana_theme_map()
        self._arcana_class_skills = _load_arcana_class_skills()
        self._arcana_active_theme: str | None = None
        self._arcana_card_widgets: dict[str, _ArcanaCardButton] = {}

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

        # Set Bonus shown on hover instead of a persistent panel below the
        # sidebar (User-Wunsch, 2026-08-29: "Kannst du diese Seteffekte als
        # Hover Effekt abbilden? ... statt unten die Set Effekte als Hover
        # Effekt angezeigt werden") -- same hover_token/shown_for_key guard
        # already proven for the card hover tooltips (see
        # _ArcanaCardButton.enterEvent).
        self._arcana_set_bonus_tooltip = ArcanaSetBonusTooltip(self)
        for theme in ARCANA_THEME_ORDER:
            category = ARCANA_THEME_CATEGORY[theme]
            set_name = ARCANA_SET_BONUSES.get(theme, {}).get("setName", theme)
            btn = _ArcanaSetBanner(theme, set_name, category)
            btn.clicked.connect(lambda _c=False, t=theme: self._on_arcana_set_selected(t))
            btn.enable_bonus_tooltip(self._arcana_set_bonus_tooltip)
            self._arcana_set_group.addButton(btn)
            left_col.addWidget(btn)

        left_col.addStretch()
        root.addLayout(left_col)

        right_col = QVBoxLayout()
        grid = QGridLayout()
        grid.setSpacing(14)
        grid.setAlignment(Qt.AlignTop)
        # Possible skills, shown via a real hover tooltip (User-Wunsch,
        # 2026-08-29, after the click/dropdown-overlay attempt didn't work
        # out: "bitte umbauen auf Tipptool") -- reuses ArcanaCardTooltip
        # as-is (already built for the Calculator results' card hover, same
        # title/lord-effect/Active-Passive-columns content this needed),
        # instead of a second bespoke widget. 2-column Active+Passive only
        # for the 2 card types whose pool genuinely mixes both (Chalice,
        # Scales per real data); every other card type is Active-only or
        # Passive-only and ArcanaCardTooltip.set_card() already collapses
        # to a single column for those on its own.
        self._arcana_info_tooltip = ArcanaCardTooltip(self)
        for i, card_type in enumerate(ARCANA_CARD_TYPES):
            row, col_idx = divmod(i, 5)
            card = _ArcanaCardButton(card_type)
            card.enable_hover_tooltip(self._arcana_info_tooltip, lambda ct=card_type: self._arcana_info_hover_data(ct))
            grid.addWidget(card, row, col_idx)
            self._arcana_card_widgets[card_type] = card
        right_col.addLayout(grid)
        right_col.addStretch()
        root.addLayout(right_col, 1)

        self._refresh_arcana_cards()
        return root

    def _arcana_info_hover_data(self, card_type: str):
        """Callback for _ArcanaCardButton.enable_hover_tooltip -- computed
        fresh on every hover (not pre-rendered) so it's always current for
        whatever Set/class is active right now."""
        card = self._arcana_card_widgets.get(card_type)
        if card is None or not card.entry:
            return None
        theme = self._arcana_active_theme or ""
        lord = card.entry.get("lord")
        pool = self._arcana_class_skills.get(card_type, {}).get(self._active_skill_class, [])
        return theme, lord, pool, {}

    def _build_arcana_lord_bar(self) -> QFrame:
        """Compact permanent footer for the whole "Arcana" tab (User-
        Wunsch, 2026-08-29: "als Dauerfooter setzen ... gerne etwas
        kompakter - durch das lang ziehen, sieht das wie verschwendeter
        Platz aus") -- a single row (title + legend), tight dot
        separators instead of the old 4-nbsp gaps, smaller text, so it
        reads as a slim reference strip instead of a stretched panel."""
        frame = QFrame()
        frame.setObjectName("ArcanaLordBar")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(2)

        self._arcana_lord_bar_title = QLabel(_t("arm_arcana_types"))
        self._arcana_lord_bar_title.setObjectName("EquipSectionLabel")
        self._arcana_lord_bar_title.setStyleSheet("font-size: 10px;")
        layout.addWidget(self._arcana_lord_bar_title)

        text = QLabel()
        text.setObjectName("DetailInfo")
        text.setWordWrap(True)
        text.setTextFormat(Qt.RichText)
        text.setStyleSheet("font-size: 11px;")
        parts = [
            f'<span style="color:#facc15;font-weight:700;">{lord}</span> &rarr; {effect}'
            for lord, effect in ARCANA_LORD_EFFECTS.items()
        ]
        text.setText(" &nbsp;·&nbsp; ".join(parts))
        layout.addWidget(text)
        return frame

    def _on_arcana_set_selected(self, theme: str | None):
        self._arcana_active_theme = theme
        self._refresh_arcana_cards()

    def _refresh_arcana_cards(self):
        theme = self._arcana_active_theme
        # A Set/class change can invalidate whatever the hover tooltip is
        # currently showing (it caches "_shown_for_key" to skip redundant
        # rebuilds on repeated enter events, see _ArcanaCardButton) --
        # clearing that key + hiding forces a fresh set_card() call next
        # time the user actually hovers a card.
        tooltip = getattr(self, "_arcana_info_tooltip", None)
        if tooltip is not None:
            tooltip._shown_for_key = None
            tooltip.hide()

        for card_type, card in self._arcana_card_widgets.items():
            if theme is None:
                card.set_default_state(self._arcana_default_icon.get(card_type))
            else:
                entry = self._arcana_theme_map.get(theme, {}).get(card_type)
                if entry is None:
                    card.set_unavailable_state()
                else:
                    card.set_themed_state(entry)

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
            preset_philosopher_stone=self._equipped_philosopher_stone.get(slot_id, False),
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

    def _compute_stat_totals(self, equipped: dict, substats: dict, enchant: dict) -> dict[str, float]:
        """Shared with the Build Vergleich tab (see _open_build_compare) so
        both a live-equipped build and an arbitrary saved build compute
        totals the exact same way, instead of duplicating this logic."""
        totals: dict[str, float] = {}
        for slot_id, item in equipped.items():
            detail = self.detail_cache.get(item.get("id"))
            if not detail:
                continue
            for stat in detail.get("mainStats") or []:
                sid = stat.get("id")
                if sid:
                    totals[sid] = totals.get(sid, 0.0) + _parse_stat_value(stat.get("value"))
            sub_stats = detail.get("subStats") or []
            for i in substats.get(slot_id, set()):
                if i < len(sub_stats):
                    sid = sub_stats[i].get("id")
                    if sid:
                        totals[sid] = totals.get(sid, 0.0) + _parse_stat_value(sub_stats[i].get("value"))

            # Enchant bonus — same estimate formulas the item's own detail
            # panel uses for its "(+N)" line, so Stat Info stays consistent
            # with what that panel shows instead of ignoring the slider.
            level = enchant.get(slot_id, 0)
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
        return totals

    def _compute_gearscore(self, equipped: dict, enchant: dict) -> float:
        """Shared with the Build Vergleich tab -- see _compute_stat_totals."""
        total = 0.0
        for slot_id, item in equipped.items():
            detail = self.detail_cache.get(item.get("id"))
            if not detail or not detail.get("level"):
                continue
            total += detail["level"]
            level = enchant.get(slot_id, 0)
            if not level:
                continue
            normal_max = int(detail.get("maxEnchantLevel") or 0)
            total += _gearscore_push(level, normal_max)
        return total

    def _refresh_stat_info(self):
        totals = self._compute_stat_totals(self._equipped, self._equipped_substats, self._equipped_enchant)

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

        self._recompute_skill_bonus()

    def _recompute_skill_bonus(self):
        """Combines the gear bonus (_compute_equipped_skill_bonus), the
        Daevanion Board bonus (_compute_daevanion_skill_bonus), and the
        Arcana card bonus (_compute_arcana_card_skill_bonus) into
        self._skill_bonus and repaints every Skill Description card's level
        label. Called from _refresh_stat_info (every equip mutation) AND
        directly from the Daevanion node-click/reset/route handlers and
        Arcana slot/grade change handlers, since those change state without
        going through _refresh_stat_info at all."""
        self._skill_bonus = self._compute_equipped_skill_bonus()
        for sid, v in self._compute_daevanion_skill_bonus().items():
            self._skill_bonus[sid] = self._skill_bonus.get(sid, 0) + v
        for sid, v in self._compute_arcana_card_skill_bonus().items():
            self._skill_bonus[sid] = self._skill_bonus.get(sid, 0) + v
        self._refresh_skill_level_labels()

    def _compute_equipped_skill_bonus(self) -> dict[str, int]:
        """+1 per equipped Trait/Skill substat pick, summed across every
        slot (stacking -- the same Active skill picked on both Ring1 and
        Ring2 counts twice). Mirrors the exact same skill_options
        construction _apply_quick_substats/ItemDetailWidget._apply_detail
        use (self._skills_by_class filtered by type), so the index space
        lines up with what's actually stored in _equipped_substats."""
        class_key = _skills_data_class_key(self.character_class_combo.currentText())
        class_skills = self._skills_by_class.get(class_key, [])
        bonus: dict[str, int] = {}
        for slot_id, item in self._equipped.items():
            detail = self.detail_cache.get(item.get("id"))
            if not detail or not int(detail.get("subSkillCountMax") or 0):
                continue
            offset = len(detail.get("subStats") or [])
            skill_type = "active" if detail.get("categoryName") in _ACTIVE_SUBSKILL_SLOT_CATEGORIES else "passive"
            skill_options = [s for s in class_skills if s.get("type") == skill_type]
            for i in self._equipped_substats.get(slot_id, ()):
                if i >= offset and (i - offset) < len(skill_options):
                    sid = skill_options[i - offset].get("id")
                    if sid:
                        bonus[sid] = bonus.get(sid, 0) + 1
        return bonus

    def _compute_daevanion_skill_bonus(self) -> dict[str, int]:
        """+level_increase per active skill_level node, summed across every
        one of the current class's Daevanion boards (User-Wunsch,
        2026-08-28: "die Skills auf den Skillplaner rechnen") -- a class
        has one board per deity, all contributing to the same skills, so
        this sums over ALL of them, not just whichever one is currently on
        screen. Uses self._daevanion_active directly (not
        _daevanion_active_set, which lazily creates a {start_id}-only entry
        as a side effect for boards never opened) since a never-opened
        board simply has no bonus to contribute."""
        class_key = self._daevanion_class_key()
        variant = _daevanion_variant(self._daevanion_variant)
        bonus: dict[str, int] = {}
        for board in variant["boards"]:
            if board["classId"] != class_key:
                continue
            active = self._daevanion_active.get(self._daevanion_variant + ":" + board["id"], set())
            for node_id in active:
                node = variant["node_by_id"].get(node_id)
                if not node:
                    continue
                for e in node.get("e") or []:
                    if e.get("t") == "k":
                        sid = str(e.get("skill_id") or "")
                        if sid:
                            bonus[sid] = bonus.get(sid, 0) + int(e.get("v") or 0)
        return bonus

    def _compute_arcana_card_skill_bonus(self) -> dict[str, int]:
        """+level per skill actually assigned to a Sets-tab Arcana card
        slot, summed across all 5 cards of the CURRENT build (User-Wunsch,
        2026-08-29: "die Arcana Level, sobald die Karten gesetzt sind, in
        die blaue Zahl einberechnen ... aehnlich wie beim Daeva Board") --
        real, currently-in-effect levels from a committed card assignment,
        the same "blue" bucket as Gear/Daevanion (unlike the purple Arcana
        WISH counter, which stays a separate hypothetical planning target
        and deliberately does NOT feed into this)."""
        class_name = self.character_class_combo.currentText().strip().lower()
        build = self._skill_builds_data.get(class_name, {}).get(self._current_build_name, {})
        arcana_cards = build.get("arcana_cards") or {}
        bonus: dict[str, int] = {}
        for card_data in arcana_cards.values():
            for entry in _arcana_card_slot_list(card_data):
                if entry and entry.get("skill_id"):
                    bonus[entry["skill_id"]] = bonus.get(entry["skill_id"], 0) + int(entry.get("level") or 0)
        return bonus

    def _refresh_skill_level_labels(self):
        """Redraws every currently-built Skill Description card's level
        number so it includes the gear + Daevanion Board bonus (see
        _compute_equipped_skill_bonus/_compute_daevanion_skill_bonus) on
        top of the manually-invested value -- called from
        _refresh_stat_info, which already runs after every equip mutation
        (Quick Select, manual substat pick, Set switch), so this stays in
        sync for free."""
        for skill_id, label in self._skill_level_labels.items():
            manual_level = self._skill_levels.get(skill_id, 0)
            bonus_level = self._skill_bonus.get(skill_id, 0)
            wish_level = self._skill_arcana_wish.get(skill_id, 0)
            label.setText(_format_skill_level_html(manual_level, bonus_level, wish_level))

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

        # Bottom-right slot used to hold the "Character Settings" gear
        # button (Name/Race/redundant Class+GearScore popup) -- Name/Race
        # moved into the always-visible header row instead (see class_row),
        # Class/GearScore were already shown elsewhere too, so that popup
        # is gone. This spot now opens the "EQ Priority" panel (User-Wunsch,
        # 2026-08-28: the Eigenschaften-Priorität gear icon next to
        # "Eigenschaften" stays where it was -- this is about the EQ
        # Priority TAB, moved out of main_tabs into the same back-arrow/X
        # equip_view_stack takeover Build Vergleich already uses, freeing
        # that tab slot for the Daevanion Board instead).
        # Labeled pill (same SkillFilterButton look as "Build Compare")
        # instead of a bare icon button -- User-Wunsch, 2026-08-28: "der
        # Button unten Rechts wird sonst übersehen". Own #EqPriorityButton
        # rule (not #SkillFilterButton directly) since the plain 12px/4-10px
        # padding still read as too small/easy to miss here -- User-Wunsch:
        # "einen längeren Button ... Schriftgröße anpassen" -- a dedicated,
        # bigger-font/bigger-padding style scoped to just this one button,
        # same pattern as #RoleButtonAngreifer/etc. in styles.qss.
        gear_row = QHBoxLayout()
        gear_row.addStretch()
        self.equip_priority_btn = QPushButton(_t("arm_eq_priority_tab"))
        self.equip_priority_btn.setObjectName("EqPriorityButton")
        self.equip_priority_btn.setMinimumSize(190, 40)
        self.equip_priority_btn.setCursor(Qt.PointingHandCursor)
        self.equip_priority_btn.clicked.connect(self._open_equip_priority_page)
        gear_row.addWidget(self.equip_priority_btn)
        col.addLayout(gear_row)

        # Never added to a visible layout -- kept in sync with the visible
        # skill_planner_class_combo (see _class_combos/_on_any_class_combo_
        # changed) purely so every other `character_class_combo.currentText()`
        # read throughout this class keeps working unchanged.
        self.character_class_combo = QComboBox()

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
        # Information tab's inline skill lists are class-specific too (see
        # _refresh_arcana_cards) -- _load_current_build_state above already
        # refreshes the Sets tab's own equivalent (_refresh_arcana_equip_
        # slots), but not this one.
        self._refresh_arcana_cards()
        # Switching class while Build Vergleich is open would otherwise keep
        # showing it with the OLD class's build names still selected.
        self._close_build_compare()
        self._rebuild_equip_build_tabs()
        self._load_current_equip_build_state()

        self._daevanion_order = None
        self._daevanion_rebuild_deity_tabs()
        self._daevanion_refresh()

    def _capture_current_substats(self):
        """Saves whichever substats are checked and whatever enchant level
        is set in the inline detail panel against the slot it's showing,
        before switching away to show a different slot (there's no popup
        'close' anymore to hook this capture onto)."""
        prev_slot = self._selected_equip_slot_id
        if prev_slot and prev_slot in self._equipped:
            self._equipped_substats[prev_slot] = self.equip_detail_widget.get_selected_substat_indices()
            self._equipped_enchant[prev_slot] = self.equip_detail_widget.get_enchant_level()
            self._equipped_philosopher_stone[prev_slot] = self.equip_detail_widget.get_philosopher_stone_active()
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
        Re-applies text to this window's always-visible top-level chrome,
        PLUS the Arcana tab's nested content (see below) -- everything
        else (tables, popups, per-slot labels) picks up the new language
        naturally the next time it's rebuilt (e.g. switching Sets/slots),
        since every build path already reads through _t() at call time.

        CORRECTION (User-reported, 2026-08-29): the old version of this
        docstring claimed "reopening the Build Planner always guarantees
        a fully up-to-date language" -- that's false. ItemDatabaseWindow
        caches this window as a singleton (self._loadout_window) and
        only ever calls .show()/.raise_() again on the SAME instance;
        "closing" it doesn't destroy/rebuild anything, so any text not
        explicitly re-applied HERE stays stuck in whatever language it
        was originally built in, no matter how many times you close and
        reopen the window. Confirmed by the user switching Russian ->
        English, reopening, and still seeing the Arcana sub-tabs/Sets
        cards/lord-bar footer in Russian. Fixed by explicitly refreshing
        that content below, reusing its own existing rebuild helpers
        (_refresh_arcana_cards/_refresh_arcana_equip_slots/
        _rebuild_skill_build_tabs) rather than duplicating their logic."""
        set_armory_language(language)
        self.setWindowTitle(_t("arm_equip_character_title"))
        self.quick_gear_btn.setText(_t("arm_equipment_btn"))
        self.quick_stat_btn.setText(_t("arm_properties_btn"))
        self.stat_priority_edit_btn.setToolTip(_t("arm_stat_priority_editor_title"))
        self.equip_priority_btn.setText(_t("arm_eq_priority_tab"))
        self.main_tabs.setTabText(0, _t("arm_equipment_btn"))
        self.main_tabs.setTabText(1, _t("arm_daevanion_board_tab"))
        self.main_tabs.setTabText(2, _t("arm_arcana_tab"))
        self.main_tabs.setTabText(3, _t("arm_skill_planner_tab"))
        self.skillpoints_title_lbl.setText(_t("arm_skillpoints_free_label"))
        self.monolith_level_title_lbl.setText(_t("arm_monolith_level_label"))
        self.stigma_points_title_lbl.setText(_t("arm_stigma_points_label"))
        self.arcana_calculator_btn.setText(_t("arm_arcana_calculator_btn"))

        self._arcana_sub_tabs.setTabText(0, _t("arm_arcana_information_tab"))
        self._arcana_sub_tabs.setTabText(1, _t("arm_arcana_sets_tab"))
        self._arcana_lord_bar_title.setText(_t("arm_arcana_types"))
        self._refresh_arcana_cards()
        self._refresh_arcana_equip_slots()
        self._rebuild_skill_build_tabs()

    # ── Saved equipment sets (per class): named tabs holding one full
    # equipped-gear snapshot each, e.g. "Default" / "PvP" / "PvE" — same
    # idea and UI as the Skill Planner's saved builds (see
    # _rebuild_skill_build_tabs), session-only for now, not yet persisted
    # to disk. ────────────────────────────────────────────────────────────

    def _empty_equip_build_state(self) -> dict:
        return {"equipped": {}, "substats": {}, "enchant": {}, "philosopher_stone": {}}

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
            "philosopher_stone": dict(self._equipped_philosopher_stone),
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
        # .get(...) with a fallback -- "philosopher_stone" only exists in
        # builds saved after this feature was added (User-Wunsch,
        # 2026-08-27), an older/missing key just means none were active.
        self._equipped_philosopher_stone = dict(state.get("philosopher_stone", {}))
        self._selected_equip_slot_id = None

        # Same setUpdatesEnabled guard as the Quick Select bulk-equip path
        # (see _open_quick_gear_select) -- switching Sets touches every
        # slot icon plus the whole Stat Info panel in one go, which could
        # otherwise paint in visibly separate steps (User, 2026-08-27:
        # "kommt viel Flimmern durch die Fenster ... wie beim Flow Chart").
        self.setUpdatesEnabled(False)
        try:
            self.equip_center_stack.setCurrentIndex(0)
            self._refresh_all_equip_slot_icons()
            self._update_gearscore()
            self._refresh_stat_info()
            self._update_quick_stat_btn_visibility()
        finally:
            self.setUpdatesEnabled(True)
        self.update()

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
        # Same idea for the Skill Planner's Priority List builds -- these
        # were session-only until now (User-Wunsch, 2026-08-27: "prüf mal,
        # ob die Skill Prioliste im Profil gespeichert wird" -- it wasn't).
        self._save_current_build_state(self.character_class_combo.currentText().strip().lower())
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
            # User-Wunsch, 2026-08-27: eigenes Monolith-Level (Empyrean
            # Trace/Wisdom Stone Fortschritt) für die "Skillpunkte frei"-
            # Anzeige im Skill Planner -- account-weit, nicht pro Build/Set.
            "monolith_level": self._monolith_level,
            # User-Wunsch, 2026-08-27: pro Skill investierte Level (-/+
            # Zähler auf den Skill-Description-Karten) -- skill ids are
            # already strings in the source data (unlike item ids, which
            # are real ints), so this dict's keys need no type conversion
            # in either direction.
            "skill_levels": dict(self._skill_levels),
            # Arcana Planner wish list (User-Wunsch, 2026-08-28/29) --
            # purely a planning target, saved the same way as skill_levels
            # so it survives a restart like everything else here.
            "skill_arcana_wish": dict(self._skill_arcana_wish),
            "current_skill_build_name": self._current_build_name,
            "skill_builds_data": {
                class_name: {
                    build_name: {
                        "priority": {k: list(v) for k, v in build["priority"].items()},
                        "arcana_cards": dict(build.get("arcana_cards", {})),
                    }
                    for build_name, build in builds.items()
                }
                for class_name, builds in self._skill_builds_data.items()
            },
            "equip_builds_data": {
                class_name: {
                    build_name: {
                        "equipped": build["equipped"],
                        "substats": {k: list(v) for k, v in build["substats"].items()},
                        "enchant": build["enchant"],
                        "philosopher_stone": build.get("philosopher_stone", {}),
                    }
                    for build_name, build in builds.items()
                }
                for class_name, builds in self._equip_builds_data.items()
            },
            # User-Wunsch, 2026-08-28: "diese Daevanion Boards einmal
            # abspeichern im Build Profil" -- board progress belongs to
            # the CLASS, not to any one gear Set (a character only has one
            # real board state, same as skill_levels above), so this lives
            # at the profile level like skill_levels/monolith_level, not
            # inside equip_builds_data. Keyed by "variant:boardId", sets
            # turned into sorted lists for JSON-safety.
            "daevanion_active": {
                key: sorted(ids) for key, ids in self._daevanion_active.items()
            },
        }

    def apply_persisted_state(self, state: dict):
        self._equip_builds_data = {
            class_name: {
                build_name: {
                    "equipped": build.get("equipped", {}),
                    "substats": {k: set(v) for k, v in build.get("substats", {}).items()},
                    "enchant": build.get("enchant", {}),
                    "philosopher_stone": build.get("philosopher_stone", {}),
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

        # "daevanion_active" only exists in profiles saved after this
        # feature was added -- an older/missing key just keeps the fresh,
        # empty state this window was constructed with. Restored BEFORE
        # _load_current_equip_build_state() below, since that call's
        # _refresh_stat_info() already recomputes the Skill Planner's
        # Daevanion bonus (_compute_daevanion_skill_bonus) and needs this
        # in place first; the class combo above was just switched (with
        # signals blocked, so _on_any_class_combo_changed's own Daevanion
        # rebuild never fired), so the tab still needs rebuilding here too
        # -- same fix as the one applied in __init__ for the equivalent
        # "class combo has no selection yet" ordering issue.
        if "daevanion_active" in state:
            self._daevanion_active = {
                key: set(ids) for key, ids in state["daevanion_active"].items()
            }
        self._daevanion_order = None
        self._daevanion_rebuild_deity_tabs()
        self._daevanion_refresh()

        self._active_skill_class = self.character_class_combo.currentText().strip().lower()
        self._rebuild_equip_build_tabs()
        self._load_current_equip_build_state()

        # Skill Planner Priority List builds (User-Wunsch, 2026-08-27) --
        # "skill_builds_data" only exists in profiles saved after this was
        # added; an older/missing key just keeps the fresh "Default" build
        # this window was constructed with.
        if "skill_builds_data" in state:
            self._skill_builds_data = {
                class_name: {
                    build_name: {
                        "priority": {k: list(v) for k, v in build.get("priority", {}).items()},
                        "arcana_cards": dict(build.get("arcana_cards", {})),
                    }
                    for build_name, build in builds.items()
                }
                for class_name, builds in state["skill_builds_data"].items()
            }
            self._current_build_name = state.get("current_skill_build_name", "Default")
            self._rebuild_skill_build_tabs()
            self._load_current_build_state()

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

        self._monolith_level = state.get("monolith_level", 0)
        self.monolith_level_spin.blockSignals(True)
        self.monolith_level_spin.setValue(self._monolith_level)
        self.monolith_level_spin.blockSignals(False)
        self._refresh_skillpoints_label()

        self._skill_levels = dict(state.get("skill_levels", {}))
        self._skill_arcana_wish = dict(state.get("skill_arcana_wish", {}))
        self._refresh_skill_description_view()
        self._refresh_skillpoints_label()
        self._refresh_stigma_points_label()
        self._refresh_arcana_calculator_button()

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

        # Not part of _equip_build_tab_group -- this doesn't select a build,
        # it swaps the whole page (see equip_view_stack) into the compare
        # view instead, so it stays a plain (non-exclusive, non-checkable)
        # button among the build tabs.
        compare_btn = QPushButton(_t("arm_build_compare_btn"))
        compare_btn.setObjectName("SkillFilterButton")
        compare_btn.setIcon(_make_compare_icon())
        compare_btn.setIconSize(QSize(18, 18))
        compare_btn.setMinimumHeight(32)
        compare_btn.setToolTip(_t("arm_build_compare_tooltip"))
        compare_btn.clicked.connect(self._open_build_compare)
        self.equip_build_tabs_row.addWidget(compare_btn)

        add_btn = QPushButton()
        add_btn.setIcon(_make_plus_icon())
        add_btn.setIconSize(QSize(20, 20))
        add_btn.setFixedSize(40, 32)
        add_btn.setToolTip(_t("arm_add_new_set"))
        add_btn.clicked.connect(self._on_add_equip_build)
        self.equip_build_tabs_row.addWidget(add_btn)

        duplicate_btn = QPushButton()
        duplicate_btn.setIcon(_make_duplicate_icon())
        duplicate_btn.setIconSize(QSize(20, 20))
        duplicate_btn.setFixedSize(40, 32)
        duplicate_btn.setToolTip(_t("arm_duplicate_current_set"))
        duplicate_btn.clicked.connect(self._on_duplicate_equip_build)
        self.equip_build_tabs_row.addWidget(duplicate_btn)

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

    def _on_duplicate_equip_build(self):
        """Copies the currently selected Set's full state (equipped items,
        substats, enchant, Philosopher's Stone) into a new Set the user
        names -- distinct from _on_add_equip_build, which always starts
        from an empty Set (User-Wunsch, 2026-08-28)."""
        class_name = self.character_class_combo.currentText().strip().lower()
        self._save_current_equip_build_state(class_name)
        builds = self._equip_builds_data[class_name]
        source_name = self._current_equip_build_name
        default_name = _t("arm_duplicate_default_name", name=source_name)
        name, ok = QInputDialog.getText(self, _t("arm_duplicate_set_title"), _t("arm_name_colon"), text=default_name)
        name = name.strip()
        if not ok or not name or name in builds:
            return
        source = builds[source_name]
        builds[name] = {
            "equipped": dict(source["equipped"]),
            "substats": {k: set(v) for k, v in source["substats"].items()},
            "enchant": dict(source["enchant"]),
            "philosopher_stone": dict(source.get("philosopher_stone", {})),
        }
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

    # ── "Build Vergleich" tab (User-Wunsch, 2026-08-27) -- full-panel
    # takeover in equip_view_stack (see the equipment_tab construction
    # above), not a popup. Iterated first as a browser mockup (User: "Die
    # Darstellung des Vergleiches machen wir wieder im Browser"), approved
    # unchanged ("Perfekt, den Vergleich kannst du genau so übernehmen") --
    # ported 1:1 from that preview: 5 stat-category tabs (Main/Sub/Offense/
    # Defense/Utility & Recovery), matching the existing Stat Info panel's
    # own row lists even though that panel itself only groups them into 3
    # real QTabWidget tabs (Sub Stats nests Offense+Defense inline) -- the
    # 5-way split reads better side-by-side without one giant tab. ────────

    _STAT_COMPARE_CATEGORIES = [
        ("main", "arm_main_stats_tab", _MAIN_STAT_ROWS),
        ("sub", "arm_sub_stats_tab", _SUB_STAT_ROWS),
        ("offense", "arm_offense", _OFFENSE_STAT_ROWS),
        ("defense", "arm_defense", _DEFENSE_STAT_ROWS),
        ("utility", "arm_tab_utility_recovery", _UTILITY_RECOVERY_STAT_ROWS),
        # The live Stat Info panel folds these two behind a PvE/PvP toggle
        # (_set_stat_info_mode) since a character only ever has one active
        # mode at a time -- but Build Compare's whole point is comparing
        # across builds that may use different gear types, so both are
        # shown here as their own tabs instead of a toggle (User-reported
        # bug, 2026-08-28: comparing a PvP-geared build against a PvE one
        # showed no PvP stats at all -- this whole category was simply
        # missing from the comparison, not just hidden behind a toggle).
        ("pve_mode", "arm_pve_stats", _PVE_MODE_STAT_ROWS),
        ("pvp_mode", "arm_pvp_stats", _PVP_MODE_STAT_ROWS),
    ]

    def _build_compare_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        back_btn = QToolButton()
        back_btn.setObjectName("PanelNavButton")
        back_btn.setIcon(_make_back_icon())
        back_btn.setIconSize(QSize(16, 16))
        back_btn.setFixedSize(32, 32)
        back_btn.setToolTip(_t("arm_back"))
        back_btn.clicked.connect(self._close_build_compare)
        header_row.addWidget(back_btn)

        title = QLabel(_t("arm_build_compare_title"))
        title.setObjectName("DetailHeader")
        header_row.addWidget(title, 1)

        close_btn = QToolButton()
        close_btn.setObjectName("PanelNavButton")
        close_btn.setIcon(_make_close_icon())
        close_btn.setIconSize(QSize(16, 16))
        close_btn.setFixedSize(32, 32)
        close_btn.setToolTip(_t("arm_close"))
        close_btn.clicked.connect(self._close_build_compare)
        header_row.addWidget(close_btn)
        outer.addLayout(header_row)

        picker_row = QHBoxLayout()
        picker_row.setSpacing(16)
        self.compare_build_a_combo = QComboBox()
        self.compare_build_b_combo = QComboBox()
        for combo, label_key in ((self.compare_build_a_combo, "arm_compare_build_a"),
                                  (self.compare_build_b_combo, "arm_compare_build_b")):
            col = QVBoxLayout()
            col.setSpacing(4)
            label = QLabel(_t(label_key))
            label.setObjectName("EquipSectionLabel")
            col.addWidget(label)
            col.addWidget(combo)
            picker_row.addLayout(col, 1)
            combo.currentIndexChanged.connect(self._on_compare_build_changed)
        outer.addLayout(picker_row)

        gs_frame = QFrame()
        gs_frame.setObjectName("TopBar")
        gs_row = QHBoxLayout(gs_frame)
        gs_row.setContentsMargins(16, 12, 16, 12)
        self.compare_gs_a_label = QLabel()
        self.compare_gs_a_label.setObjectName("DetailHeader")
        self.compare_gs_a_label.setAlignment(Qt.AlignCenter)
        gs_row.addWidget(self.compare_gs_a_label, 1)
        vs_label = QLabel("VS")
        vs_label.setObjectName("DetailInfo")
        vs_label.setAlignment(Qt.AlignCenter)
        gs_row.addWidget(vs_label)
        self.compare_gs_b_label = QLabel()
        self.compare_gs_b_label.setObjectName("DetailHeader")
        self.compare_gs_b_label.setAlignment(Qt.AlignCenter)
        gs_row.addWidget(self.compare_gs_b_label, 1)
        outer.addWidget(gs_frame)

        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(6)
        self._compare_category_group = QButtonGroup(self)
        self._compare_category_group.setExclusive(True)
        for key, label_key, _rows in self._STAT_COMPARE_CATEGORIES:
            btn = QPushButton(_t(label_key).replace("&", "&&"))
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(key == "main")
            btn.setMinimumHeight(30)
            btn.clicked.connect(lambda checked=False, k=key: self._on_compare_category_changed(k))
            self._compare_category_group.addButton(btn)
            tabs_row.addWidget(btn)
        tabs_row.addStretch(1)
        outer.addLayout(tabs_row)

        table_frame = QFrame()
        table_frame.setObjectName("TopBar")
        table_outer = QVBoxLayout(table_frame)
        table_outer.setContentsMargins(0, 0, 0, 0)
        table_outer.setSpacing(0)

        head_row = QHBoxLayout()
        head_row.setContentsMargins(16, 10, 16, 8)
        head_row.addWidget(QLabel(""), 3)
        self.compare_head_a_label = QLabel()
        self.compare_head_a_label.setObjectName("DetailInfo")
        self.compare_head_a_label.setAlignment(Qt.AlignCenter)
        head_row.addWidget(self.compare_head_a_label, 2)
        self.compare_head_b_label = QLabel()
        self.compare_head_b_label.setObjectName("DetailInfo")
        self.compare_head_b_label.setAlignment(Qt.AlignCenter)
        head_row.addWidget(self.compare_head_b_label, 2)
        table_outer.addLayout(head_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setStyleSheet("background: transparent;")
        self.compare_rows_container = QWidget()
        self.compare_rows_layout = QVBoxLayout(self.compare_rows_container)
        self.compare_rows_layout.setContentsMargins(16, 0, 16, 12)
        self.compare_rows_layout.setSpacing(2)
        self.compare_rows_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.compare_rows_container)
        table_outer.addWidget(scroll, 1)
        outer.addWidget(table_frame, 1)

        self._compare_active_category = "main"
        return page

    def _open_build_compare(self):
        class_name = self.character_class_combo.currentText().strip().lower()
        self._save_current_equip_build_state(class_name)
        self._ensure_class_equip_builds(class_name)
        builds = self._equip_builds_data[class_name]
        build_names = list(builds.keys())

        for combo in (self.compare_build_a_combo, self.compare_build_b_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(build_names)
            combo.blockSignals(False)

        self.compare_build_a_combo.setCurrentText(self._current_equip_build_name)
        # Defaults Build B to a DIFFERENT build than A when one exists --
        # comparing a build against itself on open would just show all
        # zero-deltas, not useful as a first impression of the feature.
        other = next((n for n in build_names if n != self._current_equip_build_name), self._current_equip_build_name)
        self.compare_build_b_combo.setCurrentText(other)

        self._request_compare_details()
        self.equip_view_stack.setCurrentIndex(1)
        self._refresh_build_compare()

    def _close_build_compare(self):
        self.equip_view_stack.setCurrentIndex(0)

    def _on_compare_build_changed(self, _index: int):
        self._request_compare_details()
        self._refresh_build_compare()

    def _request_compare_details(self):
        class_name = self.character_class_combo.currentText().strip().lower()
        builds = self._equip_builds_data.get(class_name, {})
        for name in (self.compare_build_a_combo.currentText(), self.compare_build_b_combo.currentText()):
            state = builds.get(name)
            if not state:
                continue
            for item in state["equipped"].values():
                if item.get("id"):
                    self.detail_cache.request(item["id"])

    def _on_compare_category_changed(self, key: str):
        self._compare_active_category = key
        self._rebuild_compare_stat_rows()

    def _refresh_build_compare(self):
        if self.equip_view_stack.currentIndex() != 1:
            return
        class_name = self.character_class_combo.currentText().strip().lower()
        builds = self._equip_builds_data.get(class_name, {})
        name_a = self.compare_build_a_combo.currentText()
        name_b = self.compare_build_b_combo.currentText()
        state_a = builds.get(name_a) or self._empty_equip_build_state()
        state_b = builds.get(name_b) or self._empty_equip_build_state()

        self.compare_head_a_label.setText(name_a)
        self.compare_head_b_label.setText(name_b)

        gs_a = self._compute_gearscore(state_a["equipped"], state_a["enchant"])
        gs_b = self._compute_gearscore(state_b["equipped"], state_b["enchant"])
        self.compare_gs_a_label.setText(f"{_format_number(gs_a)}")
        delta = gs_b - gs_a
        if delta:
            sign = "+" if delta > 0 else ""
            color = "#4ade80" if delta > 0 else "#f87171"
            self.compare_gs_b_label.setText(
                f"{_format_number(gs_b)} <span style='color:{color}; font-size:12px;'>({sign}{_format_number(delta)})</span>"
            )
        else:
            self.compare_gs_b_label.setText(f"{_format_number(gs_b)}")

        self._compare_totals_a = self._compute_stat_totals(state_a["equipped"], state_a["substats"], state_a["enchant"])
        self._compare_totals_b = self._compute_stat_totals(state_b["equipped"], state_b["substats"], state_b["enchant"])
        self._rebuild_compare_stat_rows()

    def _rebuild_compare_stat_rows(self):
        _clear_layout(self.compare_rows_layout)
        rows = next(rows for key, _label, rows in self._STAT_COMPARE_CATEGORIES if key == self._compare_active_category)
        totals_a = getattr(self, "_compare_totals_a", {})
        totals_b = getattr(self, "_compare_totals_b", {})

        for name, stat_id in rows:
            row = QHBoxLayout()
            row.setSpacing(8)
            name_label = QLabel(name)
            name_label.setObjectName("DetailInfo")
            row.addWidget(name_label, 3)

            if stat_id is None:
                for _ in range(2):
                    val_label = QLabel("—")
                    val_label.setAlignment(Qt.AlignCenter)
                    row.addWidget(val_label, 2)
            else:
                val_a = totals_a.get(stat_id, 0.0)
                val_b = totals_b.get(stat_id, 0.0)
                suffix = "%" if stat_id in _PERCENT_STAT_IDS else ""

                label_a = QLabel(f"{_format_number(val_a)}{suffix}")
                label_a.setAlignment(Qt.AlignCenter)
                label_b = QLabel(f"{_format_number(val_b)}{suffix}")
                label_b.setAlignment(Qt.AlignCenter)

                if val_a != val_b:
                    better_color, worse_color = "#4ade80", "#f87171"
                    if val_a > val_b:
                        label_a.setStyleSheet(f"color: {better_color}; font-weight: 700;")
                        label_b.setStyleSheet(f"color: {worse_color}; font-weight: 700;")
                    else:
                        label_a.setStyleSheet(f"color: {worse_color}; font-weight: 700;")
                        label_b.setStyleSheet(f"color: {better_color}; font-weight: 700;")
                    delta = val_b - val_a
                    sign = "+" if delta > 0 else ""
                    delta_color = "#4ade80" if delta > 0 else "#f87171"
                    label_b.setText(
                        f"{_format_number(val_b)}{suffix} "
                        f"<span style='color:{delta_color}; font-size:11px;'>({sign}{_format_number(delta)}{suffix})</span>"
                    )
                row.addWidget(label_a, 2)
                row.addWidget(label_b, 2)

            row_widget = QWidget()
            row_widget.setLayout(row)
            self.compare_rows_layout.addWidget(row_widget)

    def _on_gear_type_toggled(self, key: str, checked: bool):
        # PvP and PvE used to force each other off here -- User-Wunsch,
        # 2026-08-29: "PvP und PvE parallel moeglich machen, sodass man ...
        # gleichzeitig PvP Set und PvE gemeinsam bauen kann". Both can now
        # stay checked at once; the item picker (_active_gear_types) then
        # simply shows the union of whichever types are active, same as
        # Neutral already coexisted with either one before this change.
        if checked and key in ("PvP", "PvE"):
            # One-way sync: picking PvP/PvE up here also sets the Stat Info
            # panel's own PvE/PvP mode switch to match, once — the user can
            # then flip that lower switch freely afterwards without it
            # fighting back or re-syncing from this filter again. Still
            # only syncs to whichever of the two was just clicked (the
            # Stat Info panel itself only ever shows one mode at a time).
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

        priority_ids = {
            item.get("id")
            for chain in self._equip_priority_items.values()
            for item in chain
            if item
        }
        popup = ItemPickerPopup(
            self._items, categories, self.icon_cache, self.detail_cache, self,
            active_gear_types=self._active_gear_types,
            priority_ids=priority_ids,
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

        # setUpdatesEnabled(False) around the whole bulk-equip loop --
        # refresh=False below already stops the redundant per-slot stat/
        # panel recompute (see _on_item_chosen_for_slot's docstring), this
        # additionally suppresses the visible flicker from ~13 individual
        # icon/label repaints landing on screen one at a time (User,
        # 2026-08-27: "kommt viel Flimmern durch die Fenster ... wie beim
        # Flow Chart" -- same fix as FlowRenderer.render_flow there).
        self.setUpdatesEnabled(False)
        try:
            self._capture_current_substats()
            for slot_id, item in dlg.result_slots.items():
                self._on_item_chosen_for_slot(slot_id, item, refresh=False)
                # _on_item_chosen_for_slot itself resets enchant to none on
                # equip, so the target level from the dialog must be applied
                # after it, not before.
                enchant = dlg.result_enchant.get(slot_id, 0)
                if enchant:
                    self._equipped_enchant[slot_id] = enchant
                    self._update_slot_enchant_label(slot_id)
            if dlg.result_enchant or dlg.result_slots:
                self._update_gearscore()
                self._refresh_stat_info()
                self._update_quick_stat_btn_visibility()
                if self._selected_equip_slot_id in dlg.result_slots:
                    self._refresh_equip_item_panel()
        finally:
            self.setUpdatesEnabled(True)
        self.update()

        if dlg.missing_slots:
            QMessageBox.information(
                self, _t("arm_quick_select_result_title"),
                _t("arm_quick_select_equipped_result", count=len(dlg.result_slots), missing=', '.join(dlg.missing_slots)),
            )

    def _open_quick_stat_select(self):
        # Flush whatever's LIVE in the currently-open slot's panel (picks,
        # enchant, Philosopher's Stone) into _equipped_substats/_enchant/
        # _philosopher_stone first -- without this, toggling the Stone (or
        # picking a substat) on the slot that's still open when Quick
        # Select runs used stale/uncaptured state, silently dropping the
        # Stone back off (User-Wunsch, 2026-08-27: "Bei Waffe und Guard
        # fliegt der Philostein auch raus, wenn man danach wieder Quick
        # macht" -- not actually specific to Weapon/Guard, just whichever
        # slot happened to still be open).
        self._capture_current_substats()
        dlg = QuickStatSelectDialog(set(self._equipped.keys()), parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        message = self._apply_quick_substats(dlg.stat_target_slots, dlg.selected_gear_type, dlg.selected_role)
        if message:
            QMessageBox.information(self, _t("arm_quick_select_result_title"), message)

    def _open_stat_priority_editor(self):
        """Full-panel takeover in equip_view_stack (see _open_build_compare
        for the same pattern) -- a fresh widget each open, matching the old
        modal dialog's "start from the current saved profiles every time"
        behavior (User-Wunsch, 2026-08-28: back-arrow/X navigation instead
        of a separate popup window)."""
        if self._stat_priority_editor_widget is not None:
            self.equip_view_stack.removeWidget(self._stat_priority_editor_widget)
            self._stat_priority_editor_widget.deleteLater()
        widget = StatPriorityEditorDialog(
            self._stat_priority_profiles, self._skill_priority_names_by_type(),
            on_done=self._on_stat_priority_editor_done,
        )
        self._stat_priority_editor_widget = widget
        self.equip_view_stack.addWidget(widget)
        self.equip_view_stack.setCurrentWidget(widget)

    def _on_stat_priority_editor_done(self, result_profiles: dict | None):
        if result_profiles is not None:
            self._stat_priority_profiles = result_profiles
        self.equip_view_stack.setCurrentIndex(0)

    def _skill_priority_names_by_type(self) -> dict[str, list[str]]:
        """Current class's Active/Passive Priority List, resolved from ids
        to names -- feeds both the skill-option auto-pick below and
        StatPriorityEditorDialog's dropdowns (User-Wunsch, 2026-08-27:
        "Skills sollten, sofern vorhanden, in der Reihenfolge der
        Skillprioliste aufgelistet werden bei der Eigenschaftenauswahl")."""
        result: dict[str, list[str]] = {"active": [], "passive": []}
        for skill_type in result:
            for sid in self._skill_priority_ids.get(skill_type, []):
                if sid is None:
                    continue
                skill = self._find_skill_by_id(sid)
                if skill and skill.get("name"):
                    result[skill_type].append(skill["name"])
        return result

    def _apply_quick_substats(self, target_slots: set[str], gear_type: str = "PvE", role: str = "Angreifer") -> str:
        """Auto-locks each targeted slot's substats using the selected
        Gear-Typ/Rolle priority profile (_pick_priority_substats) -- applies
        to whatever is CURRENTLY equipped in that slot (freshly equipped
        this run or already there before), independent of the Equipment
        page's own slot selection, since the two accordions are separate
        settings.

        Also auto-picks a skill-option slot (Weapon/Guard/Ring = Active,
        everything else = Passive -- see _ACTIVE_SUBSKILL_SLOT_CATEGORIES),
        when the item has one (User-Wunsch, 2026-08-27) -- previously never
        auto-picked at all, only settable by hand in the Equipment Item
        panel. Matched in ONE unified pass against the category's own
        saved priority_names list (numeric stats AND skill names combined
        into one candidate pool per slot), not two separate sequential
        passes -- an earlier version of this tried all numeric matches
        first and only gave skills whatever was left over, which silently
        ignored the actual rank order the player set in the editor (e.g. a
        Ring's real ranks 1-6 = Active skills, rank 7 = Attack, per the
        user's own guide -- skills must be tried FIRST there, not last).
        Skill picks share the SAME total budget as numeric substat picks
        (subStatCount) rather than adding a separate one on top --
        confirmed against the interactive Equipment Item panel's own
        _effective_substat_cap(), which is subStatCount alone (ignores
        subSkillCountMax entirely; that field is just a mirror of
        subStatCount, "always equal" per an earlier finding, not an
        independent budget) -- User-Wunsch, 2026-08-27: "wenn Traits schon
        4/5 belegen, kann von Skills maximal noch 1 hinzugefügt werden"."""
        if not target_slots:
            return ""
        profile = self._stat_priority_profiles.get(gear_type, {}).get(role, {})
        class_key = _skills_data_class_key(self.character_class_combo.currentText())
        class_skills = self._skills_by_class.get(class_key, [])
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
            if not count:
                skipped.append(slot_id)
                continue
            # +1 if Philosopher's Stone is active for this slot -- same cap
            # the interactive Equipment Item panel's own
            # _effective_substat_cap() uses, previously ignored here
            # entirely (User-Wunsch, 2026-08-27: "nachdem ein Philostein
            # hinzugefügt wurde, Quickslot nutzt, wird ... der Philostein
            # wieder entfernt und es steht wieder bei 6/6 statt 7/7").
            if self._equipped_philosopher_stone.get(slot_id):
                count += 1

            candidates = list(sub_stats)
            skill_count_max = int(detail.get("subSkillCountMax") or 0)
            if skill_count_max and class_skills:
                skill_type = "active" if detail.get("categoryName") in _ACTIVE_SUBSKILL_SLOT_CATEGORIES else "passive"
                candidates += [s for s in class_skills if s.get("type") == skill_type]

            category = _SLOT_TO_STAT_CATEGORY.get(slot_id)
            priority_names = profile.get(category, []) if category else []
            chosen = _pick_priority_substats(candidates, count, priority_names)

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

    def _on_item_chosen_for_slot(self, slot_id: str, item: dict, refresh: bool = True):
        """refresh=False skips the capture/recompute/panel-switch tail --
        used by the Quick Select bulk-equip loop (see _open_quick_gear_select),
        which used to call this once per slot (up to ~13x) with each call
        doing its own full _refresh_stat_info() (recomputes totals across
        EVERY equipped item, updates ~80 labels) AND flipping the inline
        Equipment Item panel to whichever slot was just processed -- visibly
        flickering through every slot's panel in sequence and repeating the
        same full recompute 13 times over (User, 2026-08-27: "kommt viel
        Flimmern durch die Fenster ... beschleunigen"). The caller now does
        the capture once up front and the recompute/panel-refresh once at
        the end instead."""
        if refresh:
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

        if not refresh:
            return

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
        total = self._compute_gearscore(self._equipped, self._equipped_enchant)
        text = f"GearScore: {_format_number(total)}"
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
        if self.equip_view_stack.currentIndex() == 1:
            self._refresh_build_compare()

    def closeEvent(self, event):
        logger.debug("LoadoutWindow (Build Planner) closed")
        # ItemPickerPopup is no longer a real Qt.Popup (2026-08-29) -- it
        # only closes itself on an outside click, Escape, or picking an
        # item, none of which fire when this WHOLE window closes instead.
        # User-reported: closing the Build Planner while a slot's search
        # popup was open left it floating on screen with the rest of the
        # app still running. Close it explicitly here.
        popup = getattr(self, "_active_picker_popup", None)
        if popup is not None and popup.isVisible():
            popup.close()
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
        # Shop filter (User-Wunsch, 2026-08-29: "Class Auswahl brauchen wir
        # da nicht mehr") replaces the old Class dropdown/filter entirely --
        # classNames are still shown as their own table column, just no
        # longer filterable here. shop_items maps shop name -> item id set
        # (see compute_shop_items.py/REAL_SHOP_TYPES).
        self.shop_filter = "All"
        self.shop_items: dict[str, set[int]] = {k: set(v) for k, v in _load_shop_items().items()}
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

    def set_shop(self, shop_name: str):
        self.shop_filter = shop_name
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

        if self.shop_filter != "All":
            item_id = model.index(source_row, ID_COLUMN, source_parent).data(Qt.EditRole)
            if item_id not in self.shop_items.get(self.shop_filter, set()):
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
        self.shop_combo = self._make_label_combo(_t("arm_filter_shop"), self._on_shop_changed)

        # Wings-only replacements for Category/Shop (User-Wunsch) -- Wings
        # items have no Category/Shop distinction that matters (all share
        # the same 2 raw categories, no shop-sources tags), but DO have real
        # per-item stats only ever expressed as free text (see
        # _parse_wing_effects). These sit in the exact same two layout
        # slots as category_combo/shop_combo and swap in only while the
        # sidebar's "Wings" group is active (see _on_sidebar_group_selected).
        self.wing_equip_combo = self._make_label_combo(_t("arm_filter_equip_effect"), self._on_wing_equip_changed)
        self.wing_owned_combo = self._make_label_combo(_t("arm_filter_owned_effect"), self._on_wing_owned_changed)
        self.wing_equip_combo.setVisible(False)
        self.wing_owned_combo.setVisible(False)

        top_layout.addWidget(self.search_input, 2)
        top_layout.addWidget(self.category_combo, 1)
        top_layout.addWidget(self.shop_combo, 1)
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

    def open_crafting_calculator(self):
        """Public entry point so a host app can jump straight to the
        Crafting Guide without showing the full item table first — same
        singleton-window pattern as open_loadout_window. The Item
        Database window itself used to have its own "Crafting
        Calculator"/"Equip Character" shortcut buttons in its header,
        removed (User-Wunsch, 2026-08-29) since MainWindow's own sidebar
        already opens both directly -- this method is still the real
        entry point both paths share."""
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

    def _on_shop_changed(self, text):
        self.proxy.set_shop(text)
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

        "Wings" is a special case (User-Wunsch): instead of Category/Shop
        (neither means anything for Wings -- no classNames/shop tags, only
        2 near-identical raw categories), it swaps in two dedicated stat
        filters (Equip Effect / Owned Effect, see _parse_wing_effects) in
        the exact same layout slots.

        Unlike the old Class filter (which only ever varied within Gear's
        Weapons categories), the Shop filter applies across every category
        -- a shop can sell materials, consumables, etc, not just gear -- so
        it stays visible for every group except Wings, matching Category's
        own visibility rule."""
        self._current_sidebar_group = group_label
        is_wings = group_label == "Wings"

        self.category_combo.setVisible(not is_wings)
        self.shop_combo.setVisible(not is_wings)
        self.wing_equip_combo.setVisible(is_wings)
        self.wing_owned_combo.setVisible(is_wings)

        if is_wings:
            # Hiding the control must not leave a stale Shop filter
            # silently narrowing rows while it's not shown.
            self.shop_combo.setCurrentIndex(0)
            self.proxy.set_shop("All")
            self.proxy.set_group_categories(dict(_ITEM_TOP_CATEGORIES)["Wings"])
            self.proxy.set_subcategory_categories(None)
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
        # Collapses exact-duplicate catalog rows (same name/grade/options,
        # different id) -- already used for picker popups since 2026-08-27
        # (Bound/Unbound pairs), but the main Item Database table itself
        # never applied it, so those same duplicates still showed up
        # there directly (User-reported, 2026-08-29, specifically noticed
        # under "Wings": e.g. two byte-identical "Ancient Aullaeu Wings"
        # rows, id 512400003/512400004 -- both tradable, so not even a
        # real Bound/Unbound pair, just a genuine duplicate catalog entry;
        # 42 of the 86 real Wings items had one). _dedupe_bound_unbound's
        # (name, grade, options) key already handles this correctly since
        # Wings items have no "options" field at all (both sides collapse
        # to the same empty tuple), no separate fix needed for Wings
        # specifically.
        items = _dedupe_bound_unbound(data.get("items", []))
        # No classNames normalization needed here anymore -- the catalog's
        # own "Spiritmaster" is now the app-wide display name too (matches
        # shugo.gg's own item database, see _SKILLS_DATA_CLASS_ALIASES).
        self._raw_items = items

        categories = set()
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
        self._populate_filter_combo(self.shop_combo, set(REAL_SHOP_TYPES))
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
