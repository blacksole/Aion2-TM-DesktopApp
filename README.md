# Aion2 Task Manager

**v1.3.0** — Modern desktop productivity manager for Aion players.

Aion2 Task Manager combines task management, shopping organization, event timers, a visual flow map planner and an in-game HUD overlay into a single lightweight desktop application — built specifically for Aion 2 players who want to stay on top of their daily and weekly goals without alt-tabbing constantly.

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

### 🧪 Armory (Beta)

Opt-in area for gear planning, unlockable at your own risk via Settings → "Unlock Beta Area" (shows a warning before enabling — still under active development).

* **Item Database** — searchable catalog with class, category, rarity and level filters; per-slot equipment priority lists with recommended order.
* **Crafting Calculator** — full material chain for any craftable item, expandable ingredient-by-ingredient; filterable by profession, category and rarity, with rarity-textured material icons.
* **Build Planner** — assemble a virtual character loadout, compare stats, save multiple named gear/skill sets per class.

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

Ideas gathered so far, not yet implemented — no fixed timeline, order isn't priority.

**Armory / Gear**
* Rune slots (Clash Rune / Devotion Rune) in the Build Planner
* Jewelry-granted skills factored into the Skill Planner
* Quick Select — auto-suggest a full gear set by role and gear tier
* Favoriting individual stat rows for a pinned quick-glance view
* Shugo.gg character import & stat comparison (blocked until a Global-region endpoint exists)

**Overlay & Flow Map**
* Skills and Equipment sections in the in-game overlay, with two-way sync back to the app when checked off
* Per-section toggle for which equipment priorities show up in the overlay
* Flow Map: item picker + a dedicated "Item Node" card type
* Flow Map: merge branches instead of a strict tree

**Item Database & Crafting**
* Monthly automatic refresh of the item/skill database
* Season-aware dungeon/material availability (once a reliable patch-notes source is available)

**Quality of Life**
* Templates: pick items directly from the database instead of typing them in
* Profile sharing via a short share-code
* In-app wiki / documentation
* About page banner
* Overlay timer mode (Daily/Weekly/Shugo/Rift countdowns in the HUD)

---

## 📄 License

This project is currently under a custom license.

---

## ❤️ Credits

Developed with Python · PySide6 · Qt · GitHub Releases API
