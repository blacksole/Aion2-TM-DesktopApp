# Aion2 Task Manager

**v1.7.0** — Modern desktop productivity manager for Aion players.

Aion2 Task Manager combines task management, shopping organization, event timers, a visual flow map planner and an in-game HUD overlay into a single lightweight desktop application — built specifically for Aion 2 players who want to stay on top of their daily and weekly goals without alt-tabbing constantly. An Armory module (item database, crafting calculator, build planner) is available as an opt-in Beta and is still under active development — see the Roadmap section below.

---

## ✨ Features

### 📋 Task Management

* Daily Tasks, Weekly Tasks, Event Tasks
* Priority system (High / Medium / Low) with color coding
* Real-time progress bar with gradient fill (Cyan → Purple)
* Dynamic sorting & filtering
* Event badge system

### 🛒 Shopping Lists

* Daily Shopping, Weekly Shopping
* Price tracking with Kinah calculation
* Amount & location management
* Dynamic sorting

### ⏱ Event Timers

* Daily Reset countdown
* Weekly Reset countdown
* Shugo Event Timer (configurable interval)
* Rift Timer (configurable anchor & interval)

### 🗺 Flow Map Planner

* Visual node-based character progression planner
* Drag & Drop nodes freely on an 8000×8000 canvas
* Edit mode & Guide mode
* Node status: Completed / Active / Optional / Locked
* Zoom: 60 % – 100 %
* Positions saved per profile and restored on next launch

### 🎮 In-Game Overlay (HUD)

* Floating, frameless overlay — always on top of other windows
* **Tasks Mode**: shows all open tasks across all tabs, organized by priority
* **Guide Mode**: shows current Flow Map nodes with status indicators
* Check tasks off directly in the overlay — syncs instantly with the main app
* Adjustable opacity (20–100%) via slider in the title bar
* Resizable height via drag handle at the bottom
* Draggable by title bar, toggled via sidebar button

### 👤 Profile System

Profiles store:

* Tasks & shopping lists
* Settings, theme, language
* Timer configuration
* Flow map layout with node positions

Export/Import profiles as `.json` for backup or sharing.

### 🔄 Auto-Update System

* Automatic update check on startup (background, non-blocking)
* Manual check via Settings → General
* In-app dialog with Markdown changelog
* One-click in-place installation (downloads ZIP, extracts, clears cache)
* App restarts automatically after update

### 🔗 Community

* GitHub, version copy and Discord links on the About page
(If you like my tool and want to share it, I can link your community as well)

### 🌈 Themes

Abyss · Inferno · Emerald · Frostbite · Obsidian · Void

### 🌍 Languages

English · Deutsch · Русский

---

## 🚀 Download

Download the latest release from the [Releases](../../releases/latest) page.

No installation required — unzip and run `Aion2 TM.exe`.

The app checks for updates automatically on startup. When a new version is available, an update button appears in the top-left header.

---

## 🛠 Run from Source

Requires Python 3.11+ and PySide6.

```bash
pip install -r requirements.txt
python main.py
```

---

## 📸 Screenshots

Screenshots and previews will be added soon.

---

## 📘 Changelog

See [CHANGELOG.md](../CHANGELOG.md) for the full version history.

---

## 🧭 Roadmap

Everything above this section is current, shipped functionality. The **Armory** module and its Item Database are still under active development — this is where ongoing and planned work lives, no fixed timeline, order isn't priority.

### 🧪 Armory (Beta)

Opt-in area for gear planning, unlockable at your own risk via Settings → "Unlock Beta Area" (shows a warning before enabling).

**Already available in Beta:**
* **Item Database** — searchable catalog with category/class/rarity/PvP-PvE-Neutral filters, a grouped Categories sidebar, dedicated Wings filters
* **Crafting Calculator** — full material chain for any craftable item, expandable ingredient-by-ingredient; a Vergleich (Direct Craft vs. Transfer) comparison tab
* **Build Planner** — assemble a virtual character loadout, compare gear side-by-side (Build Compare), save multiple named gear sets per class, enchant-level tracking per slot, and a Quick Select for auto-equipping a full crafted/dungeon-drop/PvP gear set by race and gear tier in one click, plus a Property Priority editor (per role and gear mode) to customize which substats get auto-picked
* **Daevanion Board** — interactive per-class/deity board with real tier art, a checkable stat/skill sidebar, and an auto-router that finds the cheapest path to everything you've checked; feeds its skill bonuses straight into the Skill Planner and persists to your profile
* **Skill Planner** — browse/filter class skills, track Skill Points and Stigma Points separately, build a Priority List (with remove/favorite/star), and an "Arcana Calculator" that finds the best-case Arcana card setup for a wishlist of extra skill levels
* **Arcana tab** — an Information sub-tab to browse all card types/sets, and a Sets sub-tab holding your 5 real equip slots for this season's usable cards, which the Arcana Calculator can write straight into with one click; Sets share the same named build as the Skill Planner
* **Full English/Deutsch/Русский localization** across all Armory windows, following your Settings → Language choice (item/recipe/skill/card/material names stay in their original form until an official in-game translation exists)
* **Templates: pick items directly from the Item Database** — the Shopping template "Import from Database" link opens the real catalog (icons, search, a shop-type sidebar pre-filtered to purchasable items) instead of typing a name — Already implemented / Done

**Planned / in progress:**
* Item Database: "Compare Items" — compare two catalog items side by side, in the header spot the removed "Equip Character"/"Crafting Calculator" shortcut buttons used to occupy
* Item Database: Class filter replaced with a Shop filter (Merchant NPC / Trade Shop / Black Cloud Merchants / Shugo Festival) — Already implemented / Done
* Templates item picker: Block/Row view toggle, matching the main Item Database's table view — Already implemented / Done
* Settings: an opt-in "Use app offline" download (icons + item details) so a fresh install can browse fully offline without waiting on per-item network fetches
* Template assignment to multiple characters at once via checkboxes, instead of one at a time
* Rune slots (Clash Rune / Devotion Rune) in the Build Planner
* Jewelry-granted skills and character passive/active skills factored into the Build Planner's numeric stat calculation (they already feed the Skill Planner's own level display, not yet GearScore/Stat Info)
* A real "equipped Arcana cards" state feeding GearScore, the same way Gear/Daevanion already do
* Favoriting individual stat rows for a pinned quick-glance view
* Monthly automatic refresh of the item/skill database — Already implemented / Done (a weekly dev-side maintenance script re-fetches everything and reports what changed; not part of the shipped app itself)
* Season-aware dungeon/material availability (once a reliable patch-notes source is available)
* Shugo.gg character import & stat comparison (blocked until a Global-region endpoint exists) — first chance to test is the Sept 17 Global test phase (2-3 days), otherwise full testing from Sept 30; would extend to the Skill Planner/Arcana too, not just the Build Planner, depending on what data is actually available
* Skill Rotation planner (node-based sequence builder for skill casting order) — early idea, not yet scoped
* Crafting Calculator: rename the existing Compare tab to "Transfer" (it only compares transfer chains) and add a second, independent mode to compare any two recipes freely — which comparison types to offer (e.g. item stats for Cooking, which has few enough ingredients to free up space for it) still needs deciding

### Overlay & Flow Map
* Skills and Equipment sections in the in-game overlay, with two-way sync back to the app when checked off
* Per-section toggle for which equipment priorities show up in the overlay
* Flow Map: item picker + a dedicated "Item Node" card type
* Flow Map: merge branches instead of a strict tree

### Quality of Life
* Profile sharing via a short share-code
* In-app wiki / documentation
* About page banner
* Overlay timer mode (Daily/Weekly/Shugo/Rift countdowns in the HUD)
* Automated Discord update announcements with screenshots (currently posted manually via webhook)

---

## 📄 License

This project is currently under a custom license.

---

## ❤️ Credits

Developed with Python · PySide6 · Qt · GitHub Releases API
