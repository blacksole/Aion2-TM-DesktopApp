# Aion2 Task Manager

**v0.8.0** — Modern desktop productivity manager for Aion players.

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

### 🌈 Themes

Abyss · Inferno · Emerald · Frostbite · Obsidian · Void

### 🌍 Languages

English · Deutsch

---

## 🚀 Download

Download the latest release from the [Releases](../../releases/latest) page.

No installation required — unzip and run `Aion2_TM.exe`.

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

## 🔐 Planned Features

* Discord authentication
* License system (in progress — separate service)
* Cloud synchronization / shared profiles
* Launcher support

---

## 📄 License

This project is currently under a custom license.

---

## ❤️ Credits

Developed with Python · PySide6 · Qt · GitHub Releases API
