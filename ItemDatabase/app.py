"""Standalone AION 2 item database viewer — filterable, sortable table.

Test app, isolated from cont_ToDo_app (no imports from it, own styles.qss).
Run fetch_items.py first to populate data/items_all.json, then:
    python app.py
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, QSize, Qt, QSortFilterProxyModel, QTimer, Signal
from PySide6.QtGui import (
    QColor, QCursor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
    QStandardItem, QStandardItemModel,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
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
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QTableView,
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

COLUMNS = ["Icon", "ID", "Name", "Grade", "Category", "Classes", "Tradable", "Options", "PvP/PvE"]
GEAR_TYPE_COLUMN = 8

GRADE_COLORS = {
    "Common": "#94a3b8",
    "Rare": "#4ade80",
    "Unique": "#facc15",
    "Epic": "#f59e0b",
    "Legend": "#38bdf8",
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

# Real per-rarity backdrop textures, saved locally under assets/ (from
# questlog.gg's cdn.questlog.gg/aion-2/common/icon_backgrounds/ mirror) —
# confirmed with the user via an artifact preview before wiring these in,
# using real ascending-rarity order Common < Rare < Legend < Unique < Epic
# (a lower position than the name suggests — "Legend" scales weaker than
# Unique in the enchant-bonus formulas too, see estimate_enchant_bonus).
_RARITY_BG_DIR = _BUNDLE_DIR / "assets" / "backgrounds_rarity"
_RARITY_BG_FILES = {
    "Common": "UT_SlotGrade_Common.webp",
    "Rare": "UT_SlotGrade_Rare.webp",
    "Unique": "UT_SlotGrade_Unique.webp",
    "Epic": "UT_SlotGrade_Epic.webp",
    "Legend": "UT_SlotGrade_Legend.webp",
}
_rarity_bg_cache: dict[str, QPixmap] = {}


def _rarity_background(grade: str | None) -> QPixmap | None:
    if not grade or grade not in _RARITY_BG_FILES:
        return None
    if grade not in _rarity_bg_cache:
        path = _RARITY_BG_DIR / _RARITY_BG_FILES[grade]
        pix = QPixmap(str(path)) if path.exists() else QPixmap()
        _rarity_bg_cache[grade] = pix
    pix = _rarity_bg_cache[grade]
    return pix if not pix.isNull() else None

# Same 4-stop diagonal gradient as cont_ToDo_app's "Abyss" theme — copied on
# purpose so this test viewer looks consistent, without importing from it.
ABYSS_GRADIENT = ["#0f172a", "#111827", "#121212", "#2e0f28"]


class GradientBackground(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor(ABYSS_GRADIENT[0]))
        gradient.setColorAt(0.35, QColor(ABYSS_GRADIENT[1]))
        gradient.setColorAt(0.75, QColor(ABYSS_GRADIENT[2]))
        gradient.setColorAt(1.0, QColor(ABYSS_GRADIENT[3]))
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
        rarity's real backdrop texture (see _rarity_background) plus a
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
        if bg_texture:
            scale = max(size / bg_texture.width(), size / bg_texture.height())
            scaled_bg = bg_texture.scaled(
                int(bg_texture.width() * scale) + 1, int(bg_texture.height() * scale) + 1,
                Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation,
            )
            bx = (size - scaled_bg.width()) // 2
            by = (size - scaled_bg.height()) // 2
            painter.drawPixmap(bx, by, scaled_bg)
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
        data = reply.readAll()
        reply.deleteLater()

        raw = QPixmap()
        if not raw.loadFromData(data):
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


class ItemDetailWidget(QWidget):
    """Shared 'left = clean item image, right = details + enchant slider'
    panel, used both by the click-popup and the loadout window."""

    def __init__(self, icon_cache: "IconCache", detail_cache: "ItemDetailCache", parent=None, compact: bool = False):
        super().__init__(parent)
        self.icon_cache = icon_cache
        self.detail_cache = detail_cache
        self._item_id: int | None = None
        self._image_url: str = ""
        self._detail: dict | None = None
        self._enchant_level = 0
        self._philosopher_stone_active = False

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

        self.substats_container = QWidget()
        self.substats_layout = QVBoxLayout(self.substats_container)
        self.substats_layout.setContentsMargins(0, 0, 0, 0)
        self.substats_layout.setSpacing(2)
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
        self.philosopher_stone_btn = QPushButton("Philosopher's Stein verwenden (+1 Subeigenschaft)")
        self.philosopher_stone_btn.setObjectName("SkillFilterButton")
        self.philosopher_stone_btn.setCheckable(True)
        self.philosopher_stone_btn.setToolTip(
            "Simuliert 'Philosopher's Stone: Revelation' — öffnet einen zusätzlichen Soul-Binding-Slot. "
            "Nur für Unique-Grade und höher."
        )
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
        enchant_caption = QLabel("Verzauberung simulieren:")
        enchant_caption.setObjectName("DetailInfo")
        self.enchant_value = QLabel("+0")
        self.enchant_value.setObjectName("DetailEnchantValue")
        caption_row.addWidget(enchant_caption)
        caption_row.addStretch()
        caption_row.addWidget(self.enchant_value)
        self.enchant_row.addLayout(caption_row)

        self.enchant_slider = QSlider(Qt.Horizontal)
        self.enchant_slider.setMinimum(0)
        self.enchant_slider.setMaximum(0)
        self.enchant_slider.setTickPosition(QSlider.TicksBelow)
        self.enchant_slider.setTickInterval(1)
        self.enchant_slider.valueChanged.connect(self._on_enchant_slider_changed)
        self.enchant_row.addWidget(self.enchant_slider)
        self._enchant_row_widgets = [enchant_caption, self.enchant_value, self.enchant_slider]

        self.disclaimer_label = QLabel(
            "Nur der/die skalierende(n) Stat(s) bekommen beim Verzaubern einen Bonus (Attack bei "
            "Waffen; Defense + HP bei Rüstung) — alle anderen Main Stats bleiben unverändert, "
            "Substats sowieso (nur via Soulbinding). Der Bonus ist eine grobe, an echten API-Werten "
            "kalibrierte Schätzung — keine echten Serverwerte. Jenseits der normalen Maximalstufe "
            "(Exceed) wird sie unsicherer."
        )
        self.disclaimer_label.setObjectName("DetailDisclaimer")
        self.disclaimer_label.setWordWrap(True)
        self.disclaimer_label.setVisible(False)

        if compact:
            # Stacked top-to-bottom: icon+title, then enchant, then stats —
            # for embedding inline in a narrower column (Equipment tab).
            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(10)
            outer.addWidget(self.icon_label, 0, Qt.AlignHCenter)
            outer.addWidget(self.name_label, 0, Qt.AlignHCenter)
            outer.addLayout(self.enchant_row)
            outer.addWidget(self.header_label)
            outer.addWidget(self.info_label)
            outer.addWidget(self.main_stats_label)
            outer.addWidget(self.substats_header_label)
            outer.addWidget(self.substats_container)
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
            right.addWidget(self.substats_container)
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
        self.enchant_value.setText(f"+{preset_enchant}")
        # Real slider position is set once the item's max enchant level is
        # known, in _apply_detail — the slider has no valid range yet here.
        self.enchant_slider.blockSignals(True)
        self.enchant_slider.setValue(0)
        self.enchant_slider.blockSignals(False)
        self._set_enchant_controls_visible(False)

        self.name_label.setText(name)
        self.header_label.setText(name)
        self.info_label.setText("Lade Details…")
        self.main_stats_label.setText("")
        self.substats_header_label.setText("")
        self.substats_status_label.setText("")
        self.skills_label.setText("")
        _clear_layout(self.substats_layout)
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

        is_equipment = detail.get("type") == "Equip" and detail.get("enchantable")
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
        self._substat_checkboxes = {}

        sub_stats = self._detail.get("subStats") or []
        self._sub_stat_count = int(self._detail.get("subStatCount") or 0)
        self.philosopher_stone_btn.setVisible(
            self._sub_stat_count > 0 and grade_name in ("Unique", "Epic", "Legend")
        )
        if sub_stats:
            slot_hint = (
                f" — das Item rollt tatsächlich nur <b>{self._sub_stat_count} von {len(sub_stats)}</b> davon"
                if self._sub_stat_count else ""
            )
            self.substats_header_label.setText(
                "<b>Mögliche Substats</b> <span style='font-weight:400;'>"
                f"(zufälliger Roll, unabhängig von Verzauberung — nur durch Soulbinding steigerbar{slot_hint})</span>"
            )
            buckets = {"offensive": [], "defensive": [], "pvp": []}
            for i, s in enumerate(sub_stats):
                buckets[_classify_stat(s.get("id", ""))].append((i, s))

            bucket_meta = [
                ("offensive", "ANGRIFFSWERTE", "56,189,248"),
                ("defensive", "DEFENSIVE WERTE", "74,222,128"),
                ("pvp", "PVP-WERTE", "244,114,182"),
            ]
            for key, badge_text, color in bucket_meta:
                entries = buckets[key]
                if not entries:
                    continue
                badge_label = QLabel(badge(badge_text, color))
                badge_label.setTextFormat(Qt.RichText)
                self.substats_layout.addWidget(badge_label)

                grid = QGridLayout()
                grid.setSpacing(6)
                self.substats_layout.addLayout(grid)
                for pos, (i, stat) in enumerate(entries):
                    row_btn = QPushButton()
                    row_btn.setObjectName("SubstatRow")
                    row_btn.setCheckable(True)
                    row_btn.setChecked(i in self._selected_substats)
                    row_btn.setCursor(Qt.PointingHandCursor)

                    row_layout = QHBoxLayout(row_btn)
                    row_layout.setContentsMargins(8, 4, 8, 4)
                    row_layout.setSpacing(8)

                    check_icon_label = QLabel()
                    check_icon_label.setFixedSize(16, 16)
                    check_icon_label.setPixmap(_make_check_icon(16))
                    check_icon_label.setVisible(i in self._selected_substats)
                    row_layout.addWidget(check_icon_label)

                    label = QLabel(sub_stat_line(stat))
                    label.setObjectName("DetailInfo")
                    row_layout.addWidget(label, 1)

                    row_btn.toggled.connect(lambda checked, idx=i: self._on_substat_toggled(idx, checked))
                    grid_row, grid_col = divmod(pos, 2)
                    grid.addWidget(row_btn, grid_row, grid_col)
                    self._substat_checkboxes[i] = (row_btn, check_icon_label)
        else:
            self.substats_header_label.setText("")
        self._update_substats_status()

        sub_skills = self._detail.get("subSkills") or []
        if sub_skills:
            skill_lines = [badge("MÖGLICHE SKILLS (PASSIV/AKTIV)", "250,204,21")]
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
        self._update_substats_status()

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

        stone_note = " (inkl. Philosopher's Stein)" if self._philosopher_stone_active else ""
        if at_cap:
            self.substats_status_label.setText(
                "<span style='color:#4ade80;font-weight:700;'>Alle möglichen Subeigenschaften ausgewählt "
                f"({selected}/{cap}){stone_note}</span>"
            )
        else:
            self.substats_status_label.setText(
                f"<span style='color:#94a3b8;'>{selected}/{cap} Subeigenschaften ausgewählt{stone_note}</span>"
            )

    def get_selected_substats(self) -> list[dict]:
        """The subStats entries the user has checked — for later use when
        aggregating assumed character stats across the loadout."""
        sub_stats = (self._detail or {}).get("subStats") or []
        return [sub_stats[i] for i in sorted(self._selected_substats) if i < len(sub_stats)]

    def get_selected_substat_indices(self) -> set[int]:
        return set(self._selected_substats)

    def get_enchant_level(self) -> int:
        return self._enchant_level


class ItemDetailDialog(QDialog):
    def __init__(self, icon_cache: "IconCache", detail_cache: "ItemDetailCache", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle("Item Details")
        self.setMinimumSize(560, 340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        self.detail_widget = ItemDetailWidget(icon_cache, detail_cache, self)
        layout.addWidget(self.detail_widget)

        icon_cache.icon_ready.connect(self.detail_widget.on_icon_ready)
        detail_cache.detail_ready.connect(self.detail_widget.on_detail_ready)

    def load_item(self, item_id: int, name: str, image_url: str):
        self.detail_widget.load_item(item_id, name, image_url)

    def closeEvent(self, event):
        _log_window_close("ItemDetailDialog")
        super().closeEvent(event)


# (slot_id, label, valid categoryName values) — ordered as a 2-column grid,
# two consecutive entries form one row, matching the requested paperdoll layout.
SLOT_LAYOUT = [
    ("MainHand", "Mainwaffe", ["Greatsword", "Longsword", "Dagger", "Bow", "Spellbook", "Orb", "Mace", "Staff", "Fist"]),
    ("SubHand", "Guard", ["Guard"]),
    ("Helmet", "Helm", ["Helm"]),
    ("Shoulder", "Schultern", ["Pauldrons"]),
    ("Torso", "Brust", ["Top"]),
    ("Gloves", "Handschuhe", ["Gloves"]),
    ("Pants", "Hose", ["Legs"]),
    ("Boots", "Schuhe", ["Shoes"]),
    ("Earring1", "Ohrringe", ["Earrings"]),
    ("Earring2", "Ohrringe", ["Earrings"]),
    ("Necklace", "Necklace", ["Necklace"]),
    ("Amulet", "Amulet", ["Amulet"]),
    ("Ring1", "Ringe", ["Ring"]),
    ("Ring2", "Ringe", ["Ring"]),
    ("Bracelet1", "Bracelet", ["Bracelet"]),
    ("Bracelet2", "Bracelet", ["Bracelet"]),
    ("Brooch1", "Brooch", ["Brooch"]),
    ("Brooch2", "Brooch", ["Brooch"]),
]

SLOT_BUTTON_SIZE = 76

# Distinguishes real equipment slots (which get the inline "Equipment Item"
# panel) from Arcana slots, which reuse _pick_for_slot but still use the
# old popup-based detail view since there's no inline panel for that tab.
_EQUIP_SLOT_IDS = {slot_id for slot_id, _, _ in SLOT_LAYOUT}

# Groups the paperdoll slots under category headers — Weapon+Armor sit in
# the left column, Accessory in the right one, either side of Stat Info.
_LEFT_EQUIP_SECTIONS = [
    ("Weapon", ["MainHand", "SubHand"]),
    ("Armor", ["Helmet", "Shoulder", "Torso", "Gloves", "Pants", "Boots"]),
]
# Brooch doesn't exist yet at global release — excluded from the active
# slot set for now (still defined in SLOT_LAYOUT above for whenever it's
# added back). Bracelet's global-launch status is unconfirmed — left in.
_RIGHT_EQUIP_SECTIONS = [
    ("Accessory", ["Earring1", "Earring2", "Necklace", "Amulet", "Ring1", "Ring2", "Bracelet1", "Bracelet2"]),
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
_EQUIP_PRIORITY_SECTIONS = [
    ("weapon", "Waffe", ["Greatsword", "Longsword", "Dagger", "Bow", "Spellbook", "Orb", "Mace", "Staff", "Fist"]),
    ("guard", "Guard", ["Guard"]),
    ("helm", "Helm", ["Helm"]),
    ("shoulder", "Schultern", ["Pauldrons"]),
    ("torso", "Brust", ["Top"]),
    ("gloves", "Handschuhe", ["Gloves"]),
    ("legs", "Hose", ["Legs"]),
    ("shoes", "Schuhe", ["Shoes"]),
    ("earrings", "Ohrringe", ["Earrings"]),
    ("necklace", "Necklace", ["Necklace"]),
    ("ring", "Ringe", ["Ring"]),
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
    "Elementalist": "Orb",
    "Cleric": "Mace",
    "Chanter": "Staff",
    "Brawler": "Fist",
}


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
        active_gear_types: set | None = None,
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
        self.search_input.setPlaceholderText("Suchen…")
        self.search_input.textChanged.connect(self._refresh_list)
        filter_row.addWidget(self.search_input, 1)

        self.grade_combo = QComboBox()
        self._populate_grade_combo()
        self.grade_combo.currentIndexChanged.connect(self._refresh_list)
        filter_row.addWidget(self.grade_combo)
        layout.addLayout(filter_row)

        sort_row = QHBoxLayout()
        sort_label = QLabel("SORTIEREN NACH")
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
                level_label.setText(f"Lv. {cached_detail['equipLevel']}")
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
            label.setText(f"Lv. {detail['equipLevel']}")

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
        self.hint_label.setText("Leer")
        self.grade_label.setText("")
        self._restyle()

    def set_unavailable_state(self):
        self.entry = None
        self.setProperty("state", "unavailable")
        self.icon_label.setPixmap(QPixmap())
        self.name_label.setVisible(False)
        self.info_label.setText("")
        self.hint_label.setText("Nicht verfügbar")
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
                f'<span style="font-size:10px;color:#64748b;">+ Zufalls-Substats</span>'
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

        header = QLabel(f"{card_type} — Skills für {class_label}")
        header.setObjectName("DetailName")
        header.setWordWrap(True)
        layout.addWidget(header)

        source = QLabel("Quelle: questlog.gg")
        source.setObjectName("DetailDisclaimer")
        layout.addWidget(source)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        active_skills = [s for s in skills if s.get("type") == "active"]
        passive_skills = [s for s in skills if s.get("type") == "passive"]
        columns.addLayout(self._build_column("Active", active_skills))
        columns.addLayout(self._build_column("Passive", passive_skills))
        layout.addLayout(columns)

    @staticmethod
    def _build_column(title: str, skills: list[dict]) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(4)
        head = QLabel(f"{title} ({len(skills)})")
        head.setObjectName("EquipSectionLabel")
        col.addWidget(head)
        if not skills:
            empty = QLabel("Keine")
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
    "Elementalist", "Sorcerer", "Cleric", "Chanter", "Brawler",
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
            "masteryLevel": r.get("masteryLevel"),
            "inputs": r.get("inputs", []),
            "outputs": r.get("outputs", []),
        })
    return recipes


def _build_recipe_output_index(recipes: list[dict]) -> dict[str, dict]:
    """Maps a craftable item's name to the recipe that makes it — lets a
    recipe's own ingredient list be checked for "is this itself craftable"
    without a separate hand-built table. Real multi-tier upgrade chains
    (e.g. Base -> Fine -> Pure -> Artisan's Orichalcum Longsword) fall out
    of this automatically rather than needing to be curated by hand."""
    index: dict[str, dict] = {}
    for r in recipes:
        if r["outputs"]:
            index.setdefault(r["outputs"][0]["name"], r)
    return index


def _extract_recipe_chain(material: dict, output_index: dict[str, dict]) -> list[dict]:
    """Walks a material's own recipe (if any) as far as it stays linear —
    exactly one ingredient per tier is itself craftable, the common shape
    for a gear upgrade line. Returns tiers ordered from the given (highest)
    material down to the base; each tier carries its own "side" ingredients
    (everything except the next chain link). A tier with zero or several
    chained ingredients ends the walk there — its whole ingredient list
    just becomes that tier's sideMaterials, so a real branch degrades
    gracefully into "one more step, then a plain list" instead of silently
    dropping data. depth caps at 20 as a cheap guard against a data cycle."""
    chain = []
    current = material
    depth = 0
    while current is not None and depth < 20:
        depth += 1
        recipe = output_index.get(current.get("name"))
        if recipe is None:
            chain.append({**current, "masteryLevel": None, "sideMaterials": []})
            break
        sub_inputs = recipe["inputs"]
        chain_candidates = [m for m in sub_inputs if m.get("name") in output_index]
        next_material = chain_candidates[0] if len(chain_candidates) == 1 else None
        side = [m for m in sub_inputs if m is not next_material] if next_material else sub_inputs
        chain.append({**current, "masteryLevel": recipe.get("masteryLevel"), "sideMaterials": side})
        current = next_material
    return chain


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


def _log_window_close(name: str):
    """Debug aid for tracking down which popup/dialog triggered a close,
    since a WA_QuitOnClose slip anywhere in this file has previously caused
    the whole host app to quit when only a sub-window was meant to close."""
    print(f"[ItemDatabase] closeEvent: {name}")


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
    ("Elementalist", "🔮"),
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

    def closeEvent(self, event):
        _log_window_close("ClassSelectDialog")
        super().closeEvent(event)


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

    def closeEvent(self, event):
        _log_window_close("CreateCharacterDialog")
        super().closeEvent(event)


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
        self.setWindowTitle("Skill wählen")
        self.resize(360, 480)
        self.selected_skill: dict | None = None
        self._skills = skills

        layout = QVBoxLayout(self)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Suchen…")
        self.search_input.textChanged.connect(self._refresh_list)
        layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(28, 28))
        self.list_widget.itemDoubleClicked.connect(self._accept_current)
        layout.addWidget(self.list_widget, 1)

        choose_btn = QPushButton("Auswählen")
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

    def closeEvent(self, event):
        _log_window_close("SkillPickerDialog")
        super().closeEvent(event)


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


def _build_recipe_material_row(material: dict, items_by_id: dict, icon_cache: "IconCache", registry: dict | None = None) -> QWidget:
    """Plain leaf ingredient row — no expand affordance, since anything with
    its own recipe is pulled out into a chain strip instead (see
    _RecipeChainStrip)."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    icon_label = QLabel()
    icon_label.setFixedSize(34, 34)
    pix = _crafting_item_icon(
        material.get("id"), items_by_id, icon_cache, 34,
        apply=lambda p, lbl=icon_label: lbl.setPixmap(p), registry=registry,
    )
    if pix:
        icon_label.setPixmap(pix)
    layout.addWidget(icon_label)

    name_label = QLabel(material.get("name") or "?")
    name_label.setObjectName("DetailInfo")
    layout.addWidget(name_label, 1)

    qty_label = QLabel(f"×{material.get('qty', 1):,}")
    qty_label.setObjectName("DetailEnchantValue")
    layout.addWidget(qty_label)

    return row


class _ExpandableMaterialRow(QWidget):
    """A material that's itself craftable but whose own recipe doesn't
    continue the chain any further (no single next tier below it) — most
    chainable materials turn out this shallow in practice (e.g. 42 of 78
    chainable Greatsword materials are exactly one level deep). Rendering
    these as a full _RecipeChainStrip left an orphaned, cramped single
    button with no arrow to justify the chain-node styling; a normal-
    looking row that just expands its own ingredients below reads far
    better for this common case."""

    def __init__(self, material: dict, side_materials: list[dict], mastery_level: int | None,
                 items_by_id: dict, icon_cache: "IconCache", registry: dict | None = None, parent=None):
        super().__init__(parent)
        self._side_materials = side_materials
        self._mastery_level = mastery_level
        self._items_by_id = items_by_id
        self._icon_cache = icon_cache
        self._registry = registry
        self._expanded = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self._header_btn = QToolButton()
        self._header_btn.setObjectName("ExpandableMaterialHeader")
        self._header_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._header_btn.setIconSize(QSize(30, 30))
        self._header_btn.setCursor(Qt.PointingHandCursor)
        pix = _crafting_item_icon(
            material.get("id"), items_by_id, icon_cache, 34,
            apply=lambda p, b=self._header_btn: b.setIcon(QIcon(p)), registry=registry,
        )
        if pix:
            self._header_btn.setIcon(QIcon(pix))
        self._header_btn.setText(f"  {material.get('name') or '?'}    ×{material.get('qty', 1):,}   ▾")
        self._header_btn.clicked.connect(self._on_toggle)
        outer.addWidget(self._header_btn)

        self._panel = QFrame()
        self._panel.setObjectName("ChainSidePanel")
        self._panel_layout = QVBoxLayout(self._panel)
        self._panel_layout.setContentsMargins(10, 8, 10, 8)
        self._panel_layout.setSpacing(4)
        self._panel.setVisible(False)
        outer.addWidget(self._panel)

    def _on_toggle(self):
        self._expanded = not self._expanded
        if self._expanded and self._panel_layout.count() == 0:
            mastery = self._mastery_level
            label = QLabel(f"Rezept · Mastery {mastery if mastery is not None else '—'}")
            label.setObjectName("ChainSideLabel")
            self._panel_layout.addWidget(label)
            for m in self._side_materials:
                self._panel_layout.addWidget(_build_recipe_material_row(m, self._items_by_id, self._icon_cache, self._registry))
        self._panel.setVisible(self._expanded)
        self._header_btn.setProperty("expanded", self._expanded)


class _RecipeChainStrip(QWidget):
    """Compact horizontal alternative to a deep indented tree for a linear
    upgrade chain (Base -> Fine -> Pure -> Artisan's -> ...): one mini
    equip-slot-style node per tier (icon + name, like a Build Planner
    weapon slot), connected by arrows. Clicking a node reveals its own
    tier's other ingredients in a panel below the strip, instead of the
    whole chain growing taller vertically — validated in the Crafting
    Guide browser preview before being ported here."""

    def __init__(self, chain: list[dict], items_by_id: dict, icon_cache: "IconCache", registry: dict | None = None, parent=None):
        super().__init__(parent)
        self._chain = chain  # ordered base (index 0) -> target (last)
        self._items_by_id = items_by_id
        self._icon_cache = icon_cache
        self._registry = registry
        self._expanded_index: int | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        self._strip_row = QHBoxLayout()
        self._strip_row.setSpacing(2)
        self._strip_row.setAlignment(Qt.AlignLeft)
        outer.addLayout(self._strip_row)

        self._panel = QFrame()
        self._panel.setObjectName("ChainSidePanel")
        self._panel_layout = QVBoxLayout(self._panel)
        self._panel_layout.setContentsMargins(10, 8, 10, 8)
        self._panel_layout.setSpacing(4)
        outer.addWidget(self._panel)

        self._rebuild()

    def _rebuild(self):
        _clear_layout(self._strip_row)
        for i, tier in enumerate(self._chain):
            node = QToolButton()
            node.setObjectName("ChainNode")
            node.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            node.setIconSize(QSize(30, 30))
            node.setFixedWidth(72)
            pix = _crafting_item_icon(
                tier.get("id"), self._items_by_id, self._icon_cache, 34,
                apply=lambda p, b=node: b.setIcon(QIcon(p)), registry=self._registry,
            )
            if pix:
                node.setIcon(QIcon(pix))
            node.setText(_short_skill_name(tier.get("name") or "", 14))
            node.setToolTip(tier.get("name") or "")
            has_side = bool(tier.get("sideMaterials"))
            node.setEnabled(has_side)
            node.setProperty("expanded", i == self._expanded_index)
            node.setCursor(Qt.PointingHandCursor if has_side else Qt.ArrowCursor)
            node.clicked.connect(lambda checked=False, idx=i: self._on_node_clicked(idx))
            self._strip_row.addWidget(node)

            if i < len(self._chain) - 1:
                arrow = QLabel("→")
                arrow.setObjectName("ChainArrow")
                self._strip_row.addWidget(arrow)
        self._strip_row.addStretch(1)

        _clear_layout(self._panel_layout)
        if self._expanded_index is not None:
            tier = self._chain[self._expanded_index]
            mastery = tier.get("masteryLevel")
            label = QLabel(f"{tier.get('name')} · Mastery {mastery if mastery is not None else '—'}")
            label.setObjectName("ChainSideLabel")
            self._panel_layout.addWidget(label)
            for m in tier.get("sideMaterials", []):
                self._panel_layout.addWidget(_build_recipe_material_row(m, self._items_by_id, self._icon_cache, self._registry))
            self._panel.setVisible(True)
        else:
            self._panel.setVisible(False)

    def _on_node_clicked(self, index: int):
        self._expanded_index = None if self._expanded_index == index else index
        self._rebuild()


def _build_recipe_card(recipe: dict, output_index: dict, items_by_id: dict, icon_cache: "IconCache", registry: dict | None = None) -> QWidget:
    card = QFrame()
    card.setObjectName("TopBar")
    outer = QVBoxLayout(card)
    outer.setContentsMargins(16, 14, 16, 14)
    outer.setSpacing(10)

    main_output = recipe["outputs"][0]
    combo_output = recipe["outputs"][1] if len(recipe["outputs"]) > 1 else None
    grade = recipe.get("grade")

    head = QHBoxLayout()
    head.setSpacing(12)

    icon_label = QLabel()
    icon_label.setFixedSize(64, 64)
    icon_label.setAlignment(Qt.AlignCenter)
    pix = _crafting_item_icon(
        main_output.get("id"), items_by_id, icon_cache, 60,
        apply=lambda p, lbl=icon_label: lbl.setPixmap(p), registry=registry,
    )
    if pix:
        icon_label.setPixmap(pix)
    head.addWidget(icon_label)

    title_col = QVBoxLayout()
    title_col.setSpacing(4)
    name_label = QLabel(main_output.get("name") or "?")
    name_label.setObjectName("DetailHeader")
    name_label.setWordWrap(True)
    title_col.addWidget(name_label)

    meta_row = QHBoxLayout()
    meta_row.setSpacing(10)
    grade_label = QLabel(grade or "")
    grade_label.setStyleSheet(f"color: {GRADE_COLORS.get(grade, '#94a3b8')}; font-weight: 700;")
    meta_row.addWidget(grade_label)
    mastery = recipe.get("masteryLevel")
    mastery_label = QLabel(f"Mastery {mastery if mastery is not None else '—'}")
    mastery_label.setObjectName("DetailEnchantValue")
    meta_row.addWidget(mastery_label)
    meta_row.addStretch(1)
    title_col.addLayout(meta_row)

    if combo_output:
        combo_label = QLabel(f"Combo-Ergebnis: {combo_output.get('name')}")
        combo_label.setObjectName("DetailInfo")
        title_col.addWidget(combo_label)

    head.addLayout(title_col, 1)
    outer.addLayout(head)

    materials_label = QLabel("ZUTATEN")
    materials_label.setObjectName("EquipSectionLabel")
    outer.addWidget(materials_label)

    for material in recipe["inputs"]:
        sub_recipe = output_index.get(material.get("name"))
        if sub_recipe:
            chain = _extract_recipe_chain(material, output_index)
            if len(chain) == 1:
                # No further chain continuation -- a plain expandable row
                # reads much better than a lone, cramped chain-strip node.
                outer.addWidget(_ExpandableMaterialRow(
                    material, chain[0]["sideMaterials"], chain[0]["masteryLevel"], items_by_id, icon_cache, registry,
                ))
            else:
                chain.reverse()
                outer.addWidget(_RecipeChainStrip(chain, items_by_id, icon_cache, registry))
        else:
            outer.addWidget(_build_recipe_material_row(material, items_by_id, icon_cache, registry))

    return card


class CraftingCalculatorWindow(QMainWindow):
    """Crafting Guide: every real (non-PvP-currency, non-combo-placeholder)
    recipe, filterable by profession/category/rarity + free-text search,
    each shown as a tree rooted at its output item — mirrors the design
    iterated on in the browser preview before being ported here."""

    def __init__(self, raw_items: list[dict], icon_cache: "IconCache", detail_cache: "ItemDetailCache", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle("Crafting Calculator")
        self.resize(1200, 820)
        self.icon_cache = icon_cache
        self.detail_cache = detail_cache
        self._items_by_id = {it["id"]: it for it in raw_items}
        # url -> [(apply_fn, size, grade), ...] -- see _crafting_item_icon's
        # docstring for why this replaces a naive full-rebuild-on-icon_ready.
        self._crafting_icon_registry: dict[str, list] = {}

        self._recipes = _load_recipes()
        self._output_index = _build_recipe_output_index(self._recipes)
        self._recipes_by_profession: dict[str, list[dict]] = {}
        for r in self._recipes:
            self._recipes_by_profession.setdefault(r["profession"], []).append(r)

        # Defaulting to "Alle" categories for the first profession would
        # eagerly build 400+ recipe cards (each several material rows) —
        # exactly the combined-category performance mistake already found
        # and fixed once in the EQ-Priority list (see project_todo.md).
        # Default to that profession's first real category instead, same
        # as every other picker in this app narrows to one category.
        self._state_profession = CRAFTING_PROFESSIONS[0]
        first_categories = [c for c, _ in CRAFTING_CATEGORIES[self._state_profession] if c not in _CRAFTING_HIDDEN_CATEGORIES]
        self._state_category = first_categories[0] if first_categories else "all"
        self._state_rarity = "all"
        self._state_search = ""

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(10)

        title = QLabel("Crafting Calculator")
        title.setObjectName("DetailHeader")
        outer.addWidget(title)

        self.crafting_profession_row = QHBoxLayout()
        self.crafting_profession_row.setSpacing(6)
        outer.addLayout(self.crafting_profession_row)

        search_row = QHBoxLayout()
        self.crafting_search_input = QLineEdit()
        self.crafting_search_input.setPlaceholderText("Rezept oder Zutat suchen…")
        self.crafting_search_input.textChanged.connect(self._on_crafting_search_changed)
        search_row.addWidget(self.crafting_search_input, 1)
        outer.addLayout(search_row)

        self.crafting_category_row = QHBoxLayout()
        self.crafting_category_row.setSpacing(6)
        outer.addLayout(self.crafting_category_row)

        self.crafting_rarity_row = QHBoxLayout()
        self.crafting_rarity_row.setSpacing(6)
        outer.addLayout(self.crafting_rarity_row)

        self.crafting_result_label = QLabel()
        self.crafting_result_label.setObjectName("DetailDisclaimer")
        outer.addWidget(self.crafting_result_label)

        self.crafting_list_container = QWidget()
        self.crafting_list_layout = QVBoxLayout(self.crafting_list_container)
        self.crafting_list_layout.setContentsMargins(0, 0, 0, 0)
        self.crafting_list_layout.setSpacing(10)
        self.crafting_list_layout.setAlignment(Qt.AlignTop)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.crafting_list_container)
        outer.addWidget(scroll, 1)

        self._rebuild_profession_row()
        self._rebuild_category_row()
        self._rebuild_rarity_row()
        self._rebuild_crafting_list()

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
                # a filter change (_rebuild_crafting_list clears the whole
                # registry, but an icon reply already queued before that can
                # still land afterwards) -- harmless, just skip it.
                pass

    def _rebuild_profession_row(self):
        _clear_layout(self.crafting_profession_row)
        group = QButtonGroup(self)
        group.setExclusive(True)
        for prof in CRAFTING_PROFESSIONS:
            count = len(self._recipes_by_profession.get(prof, []))
            btn = QPushButton(f"{prof} ({count})")
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(prof == self._state_profession)
            btn.clicked.connect(lambda checked=False, p=prof: self._on_profession_selected(p))
            group.addButton(btn)
            self.crafting_profession_row.addWidget(btn)
        self.crafting_profession_row.addStretch(1)
        self._crafting_profession_group = group  # kept alive against GC

    def _on_profession_selected(self, profession: str):
        if profession == self._state_profession:
            return
        self._state_profession = profession
        first_categories = [c for c, _ in CRAFTING_CATEGORIES[profession] if c not in _CRAFTING_HIDDEN_CATEGORIES]
        self._state_category = first_categories[0] if first_categories else "all"
        self._rebuild_profession_row()
        self._rebuild_category_row()
        self._rebuild_crafting_list()

    def _rebuild_category_row(self):
        _clear_layout(self.crafting_category_row)
        group = QButtonGroup(self)
        group.setExclusive(True)

        all_btn = QPushButton("Alle")
        all_btn.setObjectName("SkillFilterButton")
        all_btn.setCheckable(True)
        all_btn.setChecked(self._state_category == "all")
        all_btn.clicked.connect(lambda checked=False: self._on_category_selected("all"))
        group.addButton(all_btn)
        self.crafting_category_row.addWidget(all_btn)

        for cat_key, label in CRAFTING_CATEGORIES.get(self._state_profession, []):
            if cat_key in _CRAFTING_HIDDEN_CATEGORIES:
                continue
            btn = QPushButton(label)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(self._state_category == cat_key)
            btn.clicked.connect(lambda checked=False, c=cat_key: self._on_category_selected(c))
            group.addButton(btn)
            self.crafting_category_row.addWidget(btn)
        self.crafting_category_row.addStretch(1)
        self._crafting_category_group = group

    def _on_category_selected(self, category: str):
        if category == self._state_category:
            return
        self._state_category = category
        self._rebuild_category_row()
        self._rebuild_crafting_list()

    def _rebuild_rarity_row(self):
        _clear_layout(self.crafting_rarity_row)
        group = QButtonGroup(self)
        group.setExclusive(True)

        all_btn = QPushButton("Alle")
        all_btn.setObjectName("SkillFilterButton")
        all_btn.setCheckable(True)
        all_btn.setChecked(self._state_rarity == "all")
        all_btn.clicked.connect(lambda checked=False: self._on_rarity_selected("all"))
        group.addButton(all_btn)
        self.crafting_rarity_row.addWidget(all_btn)

        for grade in RARITY_ORDER:
            btn = QPushButton(grade)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(self._state_rarity == grade)
            btn.setStyleSheet(f"color: {GRADE_COLORS[grade]};")
            btn.clicked.connect(lambda checked=False, g=grade: self._on_rarity_selected(g))
            group.addButton(btn)
            self.crafting_rarity_row.addWidget(btn)
        self.crafting_rarity_row.addStretch(1)
        self._crafting_rarity_group = group

    def _on_rarity_selected(self, grade: str):
        if grade == self._state_rarity:
            return
        self._state_rarity = grade
        self._rebuild_rarity_row()
        self._rebuild_crafting_list()

    def _on_crafting_search_changed(self, text: str):
        self._state_search = text.strip().lower()
        self._rebuild_crafting_list()

    def _matches_crafting_filters(self, recipe: dict) -> bool:
        if recipe["category"] in _CRAFTING_HIDDEN_CATEGORIES:
            return False
        if self._state_category != "all" and recipe["category"] != self._state_category:
            return False
        if self._state_rarity != "all" and recipe["grade"] != self._state_rarity:
            return False
        if self._state_search:
            names = [recipe["outputs"][0]["name"]] + [i.get("name") for i in recipe["inputs"]]
            haystack = " ".join(n for n in names if n).lower()
            if self._state_search not in haystack:
                return False
        return True

    def _rebuild_crafting_list(self):
        _clear_layout(self.crafting_list_layout)
        # Fresh registry each rebuild -- old entries would point at widgets
        # _clear_layout just detached above.
        self._crafting_icon_registry = {}
        pool = self._recipes_by_profession.get(self._state_profession, [])
        filtered = [r for r in pool if self._matches_crafting_filters(r)]
        self.crafting_result_label.setText(f"{len(filtered)} Rezept{'e' if len(filtered) != 1 else ''}")

        if not filtered:
            empty = QLabel(f"Keine Rezepte gefunden für {self._state_profession}.")
            empty.setObjectName("DetailInfo")
            self.crafting_list_layout.addWidget(empty)
            return

        # Cap eagerly-built cards — same lesson as the ItemPickerPopup
        # performance fix (building hundreds of full widgets synchronously
        # is what caused a multi-second hang there).
        MAX_CARDS = 150
        for r in filtered[:MAX_CARDS]:
            self.crafting_list_layout.addWidget(_build_recipe_card(
                r, self._output_index, self._items_by_id, self.icon_cache, self._crafting_icon_registry,
            ))
        if len(filtered) > MAX_CARDS:
            note = QLabel(f"… und {len(filtered) - MAX_CARDS} weitere — bitte weiter filtern oder suchen.")
            note.setObjectName("DetailDisclaimer")
            self.crafting_list_layout.addWidget(note)

    def closeEvent(self, event):
        _log_window_close("CraftingCalculatorWindow")
        super().closeEvent(event)


class LoadoutWindow(QMainWindow):
    """Virtual (local-only) equipment loadout — not tied to any real
    character. Lets you try any catalog item per slot and preview its
    (estimated) enchant scaling in the shared detail panel."""

    def __init__(self, items: list[dict], icon_cache: "IconCache", detail_cache: "ItemDetailCache",
                 parent=None, character_class: str | None = None,
                 character_name: str = "", character_race: str | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle("Charakter ausrüsten (virtuell, lokal)")
        self.resize(1300, 780)
        self._items = items
        self.icon_cache = icon_cache
        self.detail_cache = detail_cache
        self._equipped: dict[str, dict] = {}
        self._equipped_substats: dict[str, set[int]] = {}
        self._equipped_enchant: dict[str, int] = {}
        self._equip_builds_data: dict[str, dict[str, dict]] = {}
        self._current_equip_build_name = "Default"
        self._slot_icon_buttons: dict[str, QToolButton] = {}
        self._slot_change_buttons: dict[str, QPushButton] = {}
        self._selected_equip_slot_id: str | None = None

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
        class_label = QLabel("Klasse")
        class_label.setObjectName("EquipSectionLabel")
        class_row.addWidget(class_label)
        class_row.addStretch(1)

        # Global PvP/PvE/Neutral gear-type filter — lives here (not inside
        # the item picker popup, which is recreated fresh per slot click) so
        # it persists across slots while equipping. Deliberately separate
        # from the Stat Info tab's own PvE/PvP mode toggle — that one stays
        # as-is, this one only affects which items the picker offers.
        self._active_gear_types: set[str] = set()
        self._gear_type_buttons: dict[str, QPushButton] = {}
        for key in ("PvP", "PvE", "Neutral"):
            btn = QPushButton(key)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setMinimumSize(64, 28)
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
        self.equip_build_tabs_row.setContentsMargins(16, 12, 16, 0)
        self.equip_build_tabs_row.setSpacing(6)
        self.equip_build_tabs_row.setAlignment(Qt.AlignLeft)
        equipment_outer.addLayout(self.equip_build_tabs_row)

        equip_root = QHBoxLayout()
        equip_root.setContentsMargins(16, 16, 16, 16)
        equip_root.setSpacing(20)
        equip_root.addLayout(self._build_weapon_armor_column(), 0)
        equip_root.addWidget(self._build_equip_center_stack(), 1)
        equip_root.addLayout(self._build_accessory_column(), 0)
        equipment_outer.addLayout(equip_root, 1)
        self.main_tabs.addTab(equipment_tab, "Equipment")

        self.main_tabs.addTab(self._build_equip_priority_tab(), "EQ-Priorität")

        arcana_tab = QWidget()
        arcana_root = QHBoxLayout(arcana_tab)
        arcana_root.setContentsMargins(16, 16, 16, 16)
        arcana_root.setSpacing(30)
        arcana_root.addLayout(self._build_arcana_column())
        arcana_root.addStretch()
        self.main_tabs.addTab(arcana_tab, "Arcana")

        self.main_tabs.addTab(self._build_skill_planner_tab(), "Skill Planner")

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
        title = QLabel("Skill Planner")
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
        tabs.addTab(self._build_skill_description_tab(), "Skill-Beschreibung")
        tabs.addTab(self._build_skill_priority_tab(), "Prioritätenliste")
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
        self.skill_search_input.setPlaceholderText("Suchen…")
        self.skill_search_input.textChanged.connect(self._refresh_skill_description_view)
        controls_row.addWidget(self.skill_search_input, 1)

        self._skill_type_buttons: dict[str, QPushButton] = {}
        for type_key, label in (("active", "Active"), ("passive", "Passive"), ("stigma", "Stigma")):
            btn = QPushButton(label)
            btn.setObjectName("SkillFilterButton")
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setMinimumSize(72, 32)
            btn.toggled.connect(self._refresh_skill_description_view)
            controls_row.addWidget(btn)
            self._skill_type_buttons[type_key] = btn

        self.skill_checked_only_btn = QPushButton("Nur angehakt")
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
            section_label = QLabel(label)
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

        self.skill_desc_title_label = QLabel("Wähle einen Skill")
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

        self.skill_desc_specs_header = QLabel("Spezialisierungen")
        self.skill_desc_specs_header.setObjectName("EquipSectionLabel")
        self.skill_desc_specs_header.setVisible(False)
        right_layout.addWidget(self.skill_desc_specs_header)

        self.skill_desc_specs_label = QLabel("")
        self.skill_desc_specs_label.setObjectName("DetailInfo")
        self.skill_desc_specs_label.setWordWrap(True)
        self.skill_desc_specs_label.setVisible(False)
        right_layout.addWidget(self.skill_desc_specs_label)

        stats_header = QLabel("Details")
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

    _SKILL_BUILD_SECTIONS = (("active", "Active Skills"), ("passive", "Passive Skills"), ("stigma", "Stigma Skills"))

    def _build_skill_priority_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(16)
        outer.setAlignment(Qt.AlignTop)

        hint = QLabel(
            "Lege je eine Skill-Reihenfolge für Aktive, Passive und Stigma-Skills fest — klicke auf "
            "ein Feld, um einen Skill zuzuweisen, und auf '＋', um ein weiteres Feld anzuhängen. "
            "Jeder Skill kann pro Liste nur einmal vorkommen."
        )
        hint.setObjectName("DetailInfo")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        self._skill_priority_ids: dict[str, list[int | None]] = {}
        self.skill_priority_rows: dict[str, QHBoxLayout] = {}

        for type_key, label in self._SKILL_BUILD_SECTIONS:
            section_label = QLabel(label)
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
            btn.setToolTip("Doppelklick zum Umbenennen")
            self._skill_build_tab_group.addButton(btn)
            self.skill_build_tabs_row.addWidget(btn)

        add_btn = QPushButton()
        add_btn.setIcon(_make_plus_icon())
        add_btn.setIconSize(QSize(20, 20))
        add_btn.setFixedSize(40, 32)
        add_btn.setToolTip("Neuen Build hinzufügen")
        add_btn.clicked.connect(self._on_add_build)
        self.skill_build_tabs_row.addWidget(add_btn)

        rename_btn = QPushButton()
        rename_btn.setIcon(_make_edit_icon())
        rename_btn.setIconSize(QSize(20, 20))
        rename_btn.setFixedSize(40, 32)
        rename_btn.setToolTip("Aktuellen Build umbenennen")
        rename_btn.clicked.connect(lambda checked=False: self._on_rename_build(self._current_build_name))
        self.skill_build_tabs_row.addWidget(rename_btn)

        save_btn = QPushButton()
        save_btn.setIcon(_make_save_icon())
        save_btn.setIconSize(QSize(20, 20))
        save_btn.setFixedSize(40, 32)
        save_btn.setToolTip("Aktuellen Build speichern")
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
        name, ok = QInputDialog.getText(self, "Neuer Build", "Name:")
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
        new_name, ok = QInputDialog.getText(self, "Build umbenennen", "Name:", text=old_name)
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
        class_name = self.character_class_combo.currentText().strip().lower()
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

        class_name = self.character_class_combo.currentText().strip().lower()
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
        self.skill_desc_title_label.setText("Wähle einen Skill")
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

        hint = QLabel(
            "Lege je eine Beschaffungs-/Aufwertungsreihenfolge pro Ausrüstungsteil fest — "
            "klicke auf ein Feld, um ein Item zuzuweisen, und auf '＋', um ein weiteres Feld anzuhängen."
        )
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

            section_label = QLabel(label)
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

        full_name = item.get("name", "") if item else "Item wählen"
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

        none_btn = QPushButton("Keine Sets")
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
        bonus_source = QLabel("Quelle: aion2hub.com (Community, ungeprüft)")
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

        title = QLabel("ARCANA-TYPEN")
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
        self._arcana_bonus_title.setText(f"{info.get('setName', theme)} — Set-Bonus")
        self._arcana_bonus_2pc.setText(f"2er: {info.get('2pc', '')}")
        self._arcana_bonus_4pc.setText(f"4er: {info.get('4pc', '')}")
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
        equip_back_btn.setToolTip("Zurück zur Statusübersicht")
        equip_back_btn.setCursor(Qt.PointingHandCursor)
        equip_back_btn.clicked.connect(self._on_equip_back_clicked)
        header_row.addWidget(equip_back_btn)

        self.equip_item_icon_label = QLabel()
        self.equip_item_icon_label.setFixedSize(36, 36)
        self.equip_item_icon_label.setAlignment(Qt.AlignCenter)
        header_row.addWidget(self.equip_item_icon_label)

        self.equip_item_combo_btn = QPushButton("Slot wählen…")
        self.equip_item_combo_btn.setObjectName("EquipItemComboButton")
        self.equip_item_combo_btn.setCursor(Qt.PointingHandCursor)
        self.equip_item_combo_btn.clicked.connect(self._on_equip_item_combo_clicked)
        header_row.addWidget(self.equip_item_combo_btn, 1)

        self.equip_item_clear_btn = QPushButton()
        self.equip_item_clear_btn.setIcon(_make_close_icon())
        self.equip_item_clear_btn.setIconSize(QSize(16, 16))
        self.equip_item_clear_btn.setFixedSize(36, 36)
        self.equip_item_clear_btn.setToolTip("Slot leeren")
        self.equip_item_clear_btn.clicked.connect(self._on_equip_item_clear_clicked)
        header_row.addWidget(self.equip_item_clear_btn)

        page_layout.addLayout(header_row)

        self.equip_detail_widget = ItemDetailWidget(self.icon_cache, self.detail_cache, self, compact=True)
        page_layout.addWidget(self.equip_detail_widget, 1)
        self.icon_cache.icon_ready.connect(self.equip_detail_widget.on_icon_ready)
        self.detail_cache.detail_ready.connect(self.equip_detail_widget.on_detail_ready)

        self.equip_center_stack.addWidget(equip_item_page)
        self.equip_center_stack.setCurrentIndex(0)

        return self.equip_center_stack

    @staticmethod
    def _slot_info(slot_id: str) -> tuple[str, list[str]]:
        for sid, label, categories in SLOT_LAYOUT:
            if sid == slot_id:
                return label, categories
        return slot_id, []

    def _refresh_equip_item_panel(self):
        slot_id = self._selected_equip_slot_id
        if slot_id is None:
            return
        item = self._equipped.get(slot_id)

        if item is None:
            label, _ = self._slot_info(slot_id)
            self.equip_item_combo_btn.setText(f"{label} wählen…")
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
            icon_btn.setToolTip(f"{label} — leer")
            placeholder = _EQUIPMENT_SLOT_PLACEHOLDER.get(slot_id)
            icon = _placeholder_icon("equipment", placeholder) if placeholder else None
            icon_btn.setIcon(icon or QIcon())

        self._update_gearscore()
        self._refresh_stat_info()
        self._refresh_equip_item_panel()

    def _build_stat_info_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(10)

        title = QLabel("Statuswerte")
        title.setObjectName("DetailHeader")
        col.addWidget(title)

        self._stat_gearscore_label = QLabel("GearScore: 0")
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
        tabs.addTab(main_tab, "Main Stats")

        sub_tab = QWidget()
        sub_layout = QVBoxLayout(sub_tab)
        self._build_sub_stats_tab(sub_layout)
        tabs.addTab(sub_tab, "Sub Stats")

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
            tabs.addTab(tab_widget, tab_label)

        col.addWidget(tabs)

        disclaimer = QLabel(
            "Summe der Hauptwerte + angehakter Substats aller ausgerüsteten Items. "
            "Zeilen ohne bestätigte Stat-ID zeigen „—“ statt eines geschätzten Werts."
        )
        disclaimer.setObjectName("DetailDisclaimer")
        disclaimer.setWordWrap(True)
        col.addWidget(disclaimer)

        col.addStretch()
        return col

    def _build_main_stats_tab(self, layout: QVBoxLayout):
        mode_row = QHBoxLayout()
        section_label = QLabel("Main Stats")
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

        movement_label = QLabel("Bewegung")
        movement_label.setObjectName("EquipSectionLabel")
        layout.addWidget(movement_label)
        self._movement_stat_labels = self._build_stat_rows(layout, _MOVEMENT_STAT_ROWS, columns=4, add_stretch=False)

        self._stat_mode_heading = QLabel("PvE Stats")
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

        chance_label = QLabel("Status Chance")
        chance_label.setObjectName("EquipSectionLabel")
        status_layout.addWidget(chance_label)
        self._status_chance_layout = QVBoxLayout()
        self._status_chance_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.addLayout(self._status_chance_layout)
        self._status_chance_labels: dict = {}

        resist_label = QLabel("Status Resist")
        resist_label.setObjectName("EquipSectionLabel")
        status_layout.addWidget(resist_label)
        resist_rows = [(name, stat_id) for name, stat_id, _effect in _STATUS_RESIST_STAT_ROWS]
        self._status_resist_labels = self._build_stat_rows(status_layout, resist_rows, columns=3, add_stretch=False)

        layout.addWidget(self._stat_status_block)
        self._stat_status_block.setVisible(False)

        layout.addStretch()
        self._stat_info_mode = "pve"

    def _build_sub_stats_tab(self, layout: QVBoxLayout):
        sub_label = QLabel("Sub Stats")
        sub_label.setObjectName("EquipSectionLabel")
        layout.addWidget(sub_label)
        self._sub_stat_labels = self._build_stat_rows(layout, _SUB_STAT_ROWS, columns=4, add_stretch=False)

        offense_label = QLabel("Offense")
        offense_label.setObjectName("EquipSectionLabel")
        layout.addWidget(offense_label)
        self._sub_stat_labels.update(
            self._build_stat_rows(layout, _OFFENSE_STAT_ROWS, columns=3, add_stretch=False)
        )

        defense_label = QLabel("Defense")
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
        self._stat_mode_heading.setText("PvP Stats" if is_pvp else "PvE Stats")

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
        class_key = self.character_class_combo.currentText().strip().lower()
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
        slot_lookup = {slot_id: (label, categories) for slot_id, label, categories in SLOT_LAYOUT}

        for section_name, slot_ids in sections:
            section_title = QLabel(section_name)
            section_title.setObjectName("EquipSectionLabel")
            col.addWidget(section_title)

            grid = QGridLayout()
            grid.setSpacing(10)
            for i, slot_id in enumerate(slot_ids):
                label, categories = slot_lookup[slot_id]
                row, col_idx = divmod(i, 2)

                icon_btn = QToolButton()
                icon_btn.setObjectName("SlotIconButton")
                icon_btn.setFixedSize(SLOT_BUTTON_SIZE, SLOT_BUTTON_SIZE)
                icon_btn.setIconSize(QSize(48, 48))
                icon_btn.setToolTip(f"{label} — leer")
                icon_btn.setCursor(Qt.PointingHandCursor)
                icon_btn.clicked.connect(lambda _c=False, s=slot_id: self._select_equip_slot(s))
                placeholder = _EQUIPMENT_SLOT_PLACEHOLDER.get(slot_id)
                if placeholder:
                    icon = _placeholder_icon("equipment", placeholder)
                    if icon:
                        icon_btn.setIcon(icon)
                self._slot_icon_buttons[slot_id] = icon_btn

                change_btn = QPushButton(label)
                change_btn.setObjectName("SlotChangeButton")
                change_btn.setFixedWidth(SLOT_BUTTON_SIZE)
                change_btn.setCursor(Qt.PointingHandCursor)
                change_btn.clicked.connect(
                    lambda _c=False, s=slot_id, cats=categories, b=change_btn: self._pick_for_slot(s, cats, b)
                )
                self._slot_change_buttons[slot_id] = change_btn

                cell = QWidget()
                cell_layout = QVBoxLayout(cell)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                cell_layout.setSpacing(2)
                cell_layout.addWidget(icon_btn)
                cell_layout.addWidget(change_btn)
                grid.addWidget(cell, row, col_idx)

            col.addLayout(grid)
            col.addSpacing(8)

        return col

    def _build_weapon_armor_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        title = QLabel("Equipment")
        title.setObjectName("DetailHeader")
        col.addWidget(title)
        col.addLayout(self._build_slot_sections(_LEFT_EQUIP_SECTIONS))
        col.addStretch()
        return col

    def _build_accessory_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        title = QLabel("Schmuck")
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
        self.gearscore_label = QLabel("GearScore: 0")

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
        dialog.setWindowTitle("Charakter")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.character_name_input.setPlaceholderText("Charaktername")
        layout.addWidget(QLabel("Name"))
        layout.addWidget(self.character_name_input)

        layout.addWidget(QLabel("Klasse"))
        layout.addWidget(self.character_class_combo)

        layout.addWidget(QLabel("Rasse"))
        layout.addWidget(self.character_race_combo)

        self.gearscore_label.setObjectName("DetailHeader")
        self.gearscore_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.gearscore_label)
        gearscore_hint = QLabel("Summe der echten Item-Level-Werte + Enchant-Bonus (per Raritätsstufe)")
        gearscore_hint.setObjectName("DetailDisclaimer")
        gearscore_hint.setAlignment(Qt.AlignCenter)
        gearscore_hint.setWordWrap(True)
        layout.addWidget(gearscore_hint)

        close_btn = QPushButton("Schließen")
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

    def _refresh_all_equip_slot_icons(self):
        """Re-applies every slot button's icon/tooltip from self._equipped —
        needed after switching Sets, since icons are otherwise only ever set
        one slot at a time (on equip/clear), never all at once."""
        for slot_id, icon_btn in self._slot_icon_buttons.items():
            label, _ = self._slot_info(slot_id)
            item = self._equipped.get(slot_id)
            if item is None:
                icon_btn.setToolTip(f"{label} — leer")
                placeholder = _EQUIPMENT_SLOT_PLACEHOLDER.get(slot_id)
                icon = _placeholder_icon("equipment", placeholder) if placeholder else None
                icon_btn.setIcon(icon or QIcon())
                continue
            icon_btn.setToolTip(item.get("name", ""))
            image_url = item.get("image", "")
            cached_icon = self.icon_cache.pixmap(image_url, 48, grade=item.get("grade"))
            if cached_icon:
                icon_btn.setIcon(QIcon(cached_icon))
            else:
                icon_btn.setIcon(QIcon())
                self.icon_cache.request(image_url)
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
            btn.setToolTip("Doppelklick zum Umbenennen")
            self._equip_build_tab_group.addButton(btn)
            self.equip_build_tabs_row.addWidget(btn)

        add_btn = QPushButton()
        add_btn.setIcon(_make_plus_icon())
        add_btn.setIconSize(QSize(20, 20))
        add_btn.setFixedSize(40, 32)
        add_btn.setToolTip("Neues Set hinzufügen")
        add_btn.clicked.connect(self._on_add_equip_build)
        self.equip_build_tabs_row.addWidget(add_btn)

        rename_btn = QPushButton()
        rename_btn.setIcon(_make_edit_icon())
        rename_btn.setIconSize(QSize(20, 20))
        rename_btn.setFixedSize(40, 32)
        rename_btn.setToolTip("Aktuelles Set umbenennen")
        rename_btn.clicked.connect(lambda checked=False: self._on_rename_equip_build(self._current_equip_build_name))
        self.equip_build_tabs_row.addWidget(rename_btn)

        save_btn = QPushButton()
        save_btn.setIcon(_make_save_icon())
        save_btn.setIconSize(QSize(20, 20))
        save_btn.setFixedSize(40, 32)
        save_btn.setToolTip("Aktuelles Set speichern")
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
        name, ok = QInputDialog.getText(self, "Neues Set", "Name:")
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
        new_name, ok = QInputDialog.getText(self, "Set umbenennen", "Name:", text=old_name)
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
        self.detail_cache.request(item.get("id"))
        self._update_gearscore()
        self._refresh_stat_info()

        if slot_id in _EQUIP_SLOT_IDS:
            self._selected_equip_slot_id = slot_id
            self.equip_center_stack.setCurrentIndex(1)
            self._refresh_equip_item_panel()

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
        _log_window_close("LoadoutWindow")
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
        self.category_filter = "All"
        self.class_filter = "All"
        self.gear_type_filter: set[str] = set()
        self.setSortRole(Qt.EditRole)

    def set_search(self, text: str):
        self.search_text = text.strip().lower()
        self.invalidateFilter()

    def set_grade(self, grade: str):
        self.grade_filter = grade
        self.invalidateFilter()

    def set_category(self, category: str):
        self.category_filter = category
        self.invalidateFilter()

    def set_class(self, class_name: str):
        self.class_filter = class_name
        self.invalidateFilter()

    def set_gear_types(self, types: set):
        self.gear_type_filter = types
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

        if self.category_filter != "All":
            category = model.index(source_row, 4, source_parent).data(Qt.DisplayRole) or ""
            if category != self.category_filter:
                return False

        if self.class_filter != "All":
            classes = model.index(source_row, 5, source_parent).data(Qt.DisplayRole) or ""
            if self.class_filter not in [c.strip() for c in classes.split(",")]:
                return False

        if self.gear_type_filter:
            gear_type = model.index(source_row, GEAR_TYPE_COLUMN, source_parent).data(Qt.DisplayRole) or ""
            if gear_type not in self.gear_type_filter:
                return False

        return True


class ItemDatabaseWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle("AION 2 Item Database — Test Viewer")
        self.resize(1400, 800)

        self.background = GradientBackground()
        self.setCentralWidget(self.background)

        outer = QVBoxLayout(self.background)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(14)

        header_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("AION 2 Item Database")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Local test viewer — data cached via fetch_items.py")
        subtitle.setObjectName("PageSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header_row.addLayout(title_col)
        header_row.addStretch()

        self.loadout_btn = QPushButton("Charakter ausrüsten")
        self.loadout_btn.clicked.connect(self._open_loadout_window)
        header_row.addWidget(self.loadout_btn, 0, Qt.AlignTop)

        self.crafting_calc_btn = QPushButton("Crafting Calculator")
        self.crafting_calc_btn.clicked.connect(self._open_crafting_calculator)
        header_row.addWidget(self.crafting_calc_btn, 0, Qt.AlignTop)

        outer.addLayout(header_row)

        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 12, 16, 12)
        top_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name…")
        self.search_input.textChanged.connect(self._on_search_changed)

        self.grade_combo = QComboBox()
        self.category_combo = QComboBox()
        self.class_combo = QComboBox()

        top_layout.addWidget(self.search_input, 2)
        top_layout.addWidget(self.grade_combo, 1)
        top_layout.addWidget(self.category_combo, 1)
        top_layout.addWidget(self.class_combo, 1)
        outer.addWidget(top_bar)

        # PvP/PvE/Neutral gear-type filter — checkable pill buttons like the
        # Skill Planner's Active/Passive/Stigma filter, not a combo. Checking
        # PvP auto-hides PvE (and vice versa) since a build is normally
        # geared for one or the other; Neutral (Dungeon gear) stays
        # independent since it's relevant to both.
        type_row = QHBoxLayout()
        type_label = QLabel("PVP / PVE")
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
        outer.addWidget(self.table, 1)

        self.model = QStandardItemModel(0, len(COLUMNS), self)
        self.model.setHorizontalHeaderLabels(COLUMNS)

        self.proxy = ItemFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy)

        self.grade_combo.currentTextChanged.connect(self._on_grade_changed)
        self.category_combo.currentTextChanged.connect(self._on_category_changed)
        self.class_combo.currentTextChanged.connect(self._on_class_changed)

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
        self._loadout_window.show()
        self._loadout_window.raise_()
        self._loadout_window.activateWindow()

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
        self.proxy.set_category(text)
        self._update_result_label()

    def _on_class_changed(self, text):
        self.proxy.set_class(text)
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
        self.result_label.setText(f"{shown} / {total} items")

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
            self.result_label.setText(f"No cached data at {DATA_PATH} — run fetch_items.py first.")
            return

        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        items = data.get("items", [])
        self._raw_items = items

        grades, categories, classes = set(), set(), set()

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
            row.append(id_item)

            name_item = QStandardItem(item.get("name", ""))
            row.append(name_item)

            grade = item.get("grade", "") or ""
            grade_item = QStandardItem(grade)
            color = GRADE_COLORS.get(grade)
            if color:
                grade_item.setForeground(QColor(color))
            row.append(grade_item)
            if grade:
                grades.add(grade)

            category = item.get("categoryName", "") or ""
            row.append(QStandardItem(category))
            if category:
                categories.add(category)

            class_names = item.get("classNames") or []
            row.append(QStandardItem(", ".join(class_names)))
            for c in class_names:
                classes.add(c)

            row.append(QStandardItem("Yes" if item.get("tradable") else "No"))

            options_text = "; ".join(item.get("options") or [])
            options_item = QStandardItem(options_text)
            options_item.setToolTip(options_text)
            row.append(options_item)

            gear_type = _gear_type(item)
            gear_type_item = QStandardItem(gear_type)
            gear_color = GEAR_TYPE_COLORS.get(gear_type)
            if gear_color:
                gear_type_item.setForeground(QColor(gear_color))
            row.append(gear_type_item)

            self.model.appendRow(row)

        self._populate_filter_combo(self.grade_combo, grades)
        self._populate_filter_combo(self.category_combo, categories)
        self._populate_filter_combo(self.class_combo, classes)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, ICON_SIZE + 16)
        self._update_result_label()

    @staticmethod
    def _populate_filter_combo(combo: QComboBox, values: set):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All")
        for v in sorted(values):
            combo.addItem(v)
        combo.blockSignals(False)

    def closeEvent(self, event):
        _log_window_close("ItemDatabaseWindow")
        super().closeEvent(event)


def _bundled_resource(name: str) -> Path:
    """styles.qss is bundled *inside* the exe (PyInstaller _MEIPASS), unlike
    data/ which lives next to the exe so the cache persists across runs."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / name
    return Path(__file__).parent / name


def _load_qss_text() -> str:
    qss_path = _bundled_resource("styles.qss")
    if qss_path.exists():
        return qss_path.read_text(encoding="utf-8")
    return ""


def _log_about_to_quit():
    app = QApplication.instance()
    widgets = app.topLevelWidgets() if app else []
    print("[ItemDatabase] QApplication.aboutToQuit fired. Top-level widgets still around:")
    for w in widgets:
        print(f"    - {type(w).__name__} (visible={w.isVisible()})")


def create_window(parent=None) -> ItemDatabaseWindow:
    """Builds the ItemDatabase window with its stylesheet scoped to the
    window instance (not the QApplication) — safe to embed as a popup
    inside a host application without overriding its global theme."""
    window = ItemDatabaseWindow(parent)
    window.setStyleSheet(_load_qss_text())
    app = QApplication.instance()
    if app is not None:
        app.aboutToQuit.connect(_log_about_to_quit)
    return window


def main():
    app = QApplication(sys.argv)
    window = create_window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
