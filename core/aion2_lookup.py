"""Looking up a live character on NC's own Aion 2 Global backend
(@koordinator, 2026-10-03), for the "Nach Spieler suchen" Build Planner
import feature (User-Wunsch: "Die Spieler Suche und das Somit importieren
des Builds in den Buildplanner").

These are NC's own endpoints behind the public character pages on
aion2.plaync.com -- no API key, no login, just a normal browser
User-Agent. Confirmed live and unauthenticated (2026-10-03) by hand with
curl before writing this. They are, however, completely undocumented:
NC can change the shape or kill them without notice, which is why this
whole feature sits behind AION2_LOOKUP_ENABLED (see ui/player_search_dialog.py)
as a kill-switch, same convention as NEWS_POPUP_ENABLED/ARMORY_ENABLED.

Scope for v1 (tobia, 2026-10-03): EU shard only ("Nur EU (reicht erstmal,
du spielst EU)") -- REGION below is a single hardcoded constant, not a
user-facing picker. Extending to the other Global shards (nae/naw/as/la)
later is just adding them to a dropdown and passing the chosen shard
through; the endpoints themselves already take any of them via `region`.

Two calls, modeled on core/news_checker.py's QThread+signal shape (same
"never raise into the caller, resolve to a signal" contract):
- CharacterSearchWorker: GET .../search/v2/character?keyword=...
- CharacterEquipmentWorker: GET .../api/character/{info,equipment}

Response shapes were confirmed by hand against real EU characters
(2026-10-03) -- see memory/GeniusInsight_Rohdaten.md's sibling notes in
the shared planner for the curl transcripts this is based on. Equipment
item ids match core.persistence's items_all.json ids directly (confirmed
for every weapon/armor/accessory slot); Rune/Arcana/Pet/Wing ids do NOT
(those catalogs aren't in items_all.json at all) -- callers must expect
match_build_to_catalog() to simply skip those slots, not raise.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from PySide6.QtCore import QThread, Signal

# v1 scope: EU only (tobia, 2026-10-03). Add more of these + a picker to
# extend -- the API itself already supports "nae", "naw", "as", "la".
REGION = "eu"

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Aion2-TM-PlayerLookup"
_SEARCH_URL = "https://api-search.plaync.com/aion2global/search/v2/character"
_INFO_URL = "https://aion2.plaync.com/api/character/info"
_EQUIPMENT_URL = "https://aion2.plaync.com/api/character/equipment"

# SLOT_LAYOUT (ItemDatabase/app.py) uses "Cloak"; NC's API calls the same
# armor piece "Cape". Only naming differs -- the category of items that
# can go there ("Cloak" in items_all.json) is identical either way.
_API_SLOT_TO_APP_SLOT = {
    "Cape": "Cloak",
}

# Slots NC's API returns that our SLOT_LAYOUT has no equivalent for yet.
# Belt is a real, separate armor category in items_all.json but never got
# its own SLOT_LAYOUT entry (see the Planner bug @koordinator opened
# 2026-10-03, "Build Planner: Belt-Equip-Slot fehlt komplett") -- until
# that's resolved one way or the other, an imported Belt item is reported
# back to the caller as skipped, never silently dropped or guessed onto
# Brooch (a different, unconfirmed-related slot).
UNMAPPED_API_SLOTS = {"Belt"}


def _get_json(url: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{qs}", headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read())


class CharacterSearchWorker(QThread):
    """Runs the character-name search. Emits a plain list of dicts
    (name/level/className-less -- the search endpoint doesn't return
    class, only the character/equipment endpoints do) so the UI never
    touches raw NC response shapes directly."""

    results_ready = Signal(list)
    search_failed = Signal(str)

    def __init__(self, keyword: str, parent=None):
        super().__init__(parent)
        self._keyword = keyword

    def run(self):
        try:
            data = _get_json(_SEARCH_URL, {
                "lang": "en",
                "region": REGION,
                "localeInfo": REGION,
                "keyword": self._keyword,
            })
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            self.search_failed.emit(str(exc))
            return

        rows = []
        for row in data.get("list") or []:
            # The search endpoint wraps the matched substring in <strong>
            # tags (e.g. "<strong>Tasse</strong>lass") for highlighting on
            # NC's own site -- meaningless noise for us, strip it so the
            # picker shows a plain name.
            name = (row.get("name") or "").replace("<strong>", "").replace("</strong>", "")
            rows.append({
                "name": name,
                "level": row.get("level"),
                "server_id": row.get("serverId"),
                "server_name": row.get("serverName") or "",
                "character_id": row.get("characterId") or "",
            })
        self.results_ready.emit(rows)


class CharacterEquipmentWorker(QThread):
    """Fetches one character's profile (info) + equipped gear
    (equipment) and hands back a single merged dict a caller can show a
    preview from and/or feed into match_build_to_catalog()."""

    build_ready = Signal(dict)
    fetch_failed = Signal(str)

    def __init__(self, character_id: str, server_id: int, parent=None):
        super().__init__(parent)
        self._character_id = character_id
        self._server_id = server_id

    def run(self):
        params = {
            "lang": "en",
            "region": REGION,
            "serverId": self._server_id,
            "characterId": self._character_id,
        }
        try:
            info = _get_json(_INFO_URL, params)
            equipment = _get_json(_EQUIPMENT_URL, params)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            self.fetch_failed.emit(str(exc))
            return

        profile = info.get("profile") or {}
        equipped = (equipment.get("equipment") or {}).get("equipmentList") or []
        self.build_ready.emit({
            "character_name": profile.get("characterName") or "",
            "class_name": profile.get("className") or "",
            "race_name": profile.get("raceName") or "",
            "level": profile.get("characterLevel"),
            "combat_power": profile.get("combatPower"),
            "server_name": profile.get("serverName") or "",
            # Each: {slot_pos_name, item_id, name, grade, enchant_level, exceed_level}
            "equipped": [
                {
                    "slot_pos_name": row.get("slotPosName") or "",
                    "item_id": row.get("id"),
                    "name": row.get("name") or "",
                    "grade": row.get("grade") or "",
                    "enchant_level": row.get("enchantLevel") or 0,
                    "exceed_level": row.get("exceedLevel") or 0,
                }
                for row in equipped
            ],
        })


def match_build_to_catalog(equipped: list[dict], items_by_id: dict[int, dict]) -> dict:
    """Resolves a CharacterEquipmentWorker build's `equipped` rows against
    our own items_all.json catalog (keyed by item id, as loaded by the
    ItemDatabase host app already -- see ItemDatabase/app.py's
    self._raw_items for the existing by-id lookup this reuses).

    Returns {"matched": {app_slot_id: (catalog_item, enchant_level)},
    "skipped": [reason strings]} -- never raises. A row is skipped (not
    matched, not guessed) when: its API slot has no SLOT_LAYOUT
    equivalent yet (see UNMAPPED_API_SLOTS), the slot is empty
    (item_id is None), or the id simply isn't in our catalog (Rune/
    Arcana/Pet/Wing ids -- confirmed 2026-10-03 these aren't in
    items_all.json at all, not a lookup bug).
    """
    matched: dict[str, tuple[dict, int]] = {}
    skipped: list[str] = []

    for row in equipped:
        api_slot = row.get("slot_pos_name") or ""
        item_id = row.get("item_id")
        name = row.get("name") or api_slot

        if item_id is None:
            continue  # an empty slot, nothing to report

        if api_slot in UNMAPPED_API_SLOTS:
            skipped.append(f"{name} ({api_slot}): kein passender Build-Planner-Slot")
            continue

        app_slot = _API_SLOT_TO_APP_SLOT.get(api_slot, api_slot)
        catalog_item = items_by_id.get(item_id)
        if catalog_item is None:
            skipped.append(f"{name} ({api_slot}): nicht in der Item-Datenbank gefunden")
            continue

        matched[app_slot] = (catalog_item, row.get("enchant_level") or 0)

    return {"matched": matched, "skipped": skipped}
