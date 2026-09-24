# Aion 2 Companion

**v2.0.7** — Modern desktop productivity manager for Aion players.

Aion 2 Companion combines task management, shopping organization, event timers, a visual flow map planner and an in-game HUD overlay into a single lightweight desktop application — built specifically for Aion 2 players who want to stay on top of their daily and weekly goals without alt-tabbing constantly. An Armory module (item database, crafting calculator, build planner) is included as a full, always-available feature — see the Armory (Expert) section below.

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
* Custom Timers (Daily/Weekly/Hourly/Custom/Countdown modes) with per-timer color, notification sound and category — the Countdown mode is started/stopped directly from the in-game overlay

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
* Armory (Expert) - Profiles

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

### 🛡️ Armory (Expert)

Gear planning and theorycrafting tools, always available from the sidebar.

* **Item Database** — searchable catalog with category/class/rarity/PvP-PvE-Neutral filters, a grouped Categories sidebar, dedicated Wings filters
* **Crafting Calculator** — full material chain for any craftable item, expandable ingredient-by-ingredient; a Compare (Direct Craft vs. Transfer) comparison tab; the item picker shows a Gear Level column so same-rarity items can be told apart by strength at a glance
* **Build Planner** — assemble a virtual character loadout, compare gear side-by-side (Build Compare), save multiple named gear sets per class, enchant-level tracking per slot, and a Quick Select for auto-equipping a full crafted/dungeon-drop/PvP gear set by race and gear tier in one click, plus a Property Priority editor (per role and gear mode) to customize which substats get auto-picked
* **Build Planner: Wings equipment slot** — pick from every real Wings item (both race variants, colored by rarity, filterable by Owned/Equip Effect), with both effect types feeding the stat panel and GearScore the same way normal gear does; level/enchant stays locked until Wings enhancement is confirmed live on Global
* **Daevanion Board** — interactive per-class/deity board with real tier art, a checkable stat/skill sidebar, and an auto-router that finds the cheapest path to everything you've checked; feeds its skill bonuses straight into the Skill Planner and persists to your profile
* **Skill Planner** — browse/filter class skills, track Skill Points and Stigma Points separately, build a Priority List (with remove/favorite/star), and an "Arcana Calculator" that finds the best-case Arcana card setup for a wishlist of extra skill levels
* **Arcana tab** — an Information sub-tab to browse all card types/sets, and a Sets sub-tab holding your 5 real equip slots for this season's usable cards, which the Arcana Calculator can write straight into with one click; Sets share the same named build as the Skill Planner
* **Full English/Deutsch/Русский localization** across all Armory windows, following your Settings → Language choice (item/recipe/skill/card/material names stay in their original form until an official in-game translation exists)
* **Templates: pick items directly from the Item Database** — the Shopping template "Import from Database" link opens the real catalog (icons, search, a shop-type sidebar pre-filtered to purchasable items) instead of typing a name
* **Templates: CSV Import/Export** for Shopping and Task templates — export any list to a spreadsheet, or bulk-import one back in with a choice between adding to your list or replacing only what an earlier import added, automatic duplicate-title detection, and an optional one-click insert straight into your active list

---

## 🚀 Download

Download the latest release from the [Releases](../../releases/latest) page.

No installation required — unzip and run `Aion2 TM.exe`.

The app checks for updates automatically on startup. When a new version is available, an update button appears in the top-left header.

---

## 🐧 Run on Linux

Runs from source on Linux (no packaged build yet). Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/):

```sh
uv sync                 # creates .venv from uv.lock
./scripts/aion2-tm      # launcher (or: .venv/bin/python main.py)
```

**Wayland.** The launcher runs the app through XWayland (`QT_QPA_PLATFORM=xcb`) when it finds no deliberate choice of its own. Native Wayland gives a client no way to place its own windows: measured on Hyprland, the HUD overlay opens on whatever monitor and workspace the compositor picks, while under XWayland it appears where the app puts it. Run `QT_QPA_PLATFORM=wayland ./scripts/aion2-tm` to override. Tiling window managers still size the main window themselves; on Hyprland, `windowrule = float, class:^([Aa]ion2[- ][Tt][Mm])$` floats both windows and `windowrule = pin, title:^(Aion2 TM)$` keeps the overlay above the rest.

**Where your data lives.** Config in `$XDG_CONFIG_HOME/aion2-tm` (`~/.config/aion2-tm`), profiles in `$XDG_DATA_HOME/aion2-tm/Profiles`, the Armory cache in `$XDG_CACHE_HOME/aion2-tm`, the log in `$XDG_STATE_HOME/aion2-tm`. Windows and macOS keep their own conventions (`%APPDATA%\Aion2 TM`, `~/Library/Application Support`) — nothing moved there. Running from a git clone keeps everything in the repo folder, as before.

**Portable mode.** Put an empty `portable.txt` next to the executable (beside `Aion2 TM.exe`, *not* inside `_internal/`) and the app reads and writes its profiles from `profiles/` beside itself instead of your home directory — for a USB stick or a self-contained folder. Without the marker an installed build never writes next to its own files.

Windows-visible changes this branch makes on purpose (minimum window height, the `Browse...` row, the Armory cache location) are listed in [docs/DEV.md](docs/DEV.md).

Notification sounds are played through Qt (WAV only). Desktop sound themes ship `.oga` files, which Qt cannot play, so the sound picker is usually empty on Linux — use its **Browse...** entry to point at any `.wav`. Without a system tray (a Wayland session with no StatusNotifier host), notifications appear as in-app toasts and minimize-to-tray is skipped. The in-app updater is Windows-only; on Linux the update button opens the release page.

---

## 📸 Screenshots

<img width="1186" height="839" alt="image" src="https://github.com/user-attachments/assets/59d05594-a1ad-41ed-949f-3246b8db7320" />
<img width="1201" height="845" alt="image" src="https://github.com/user-attachments/assets/573d043c-aee6-4e42-a6d7-1e461d299779" />
<img width="1697" height="977" alt="image" src="https://github.com/user-attachments/assets/71b4ad42-c24a-445a-a1c7-90b10963a258" />
<img width="1285" height="992" alt="image" src="https://github.com/user-attachments/assets/273524a9-29bc-44c9-9c9f-18d69637f1d1" />
<img width="1300" height="993" alt="image" src="https://github.com/user-attachments/assets/bc005bfb-f890-488b-8bc0-80e447505c05" />
<img width="497" height="401" alt="image" src="https://github.com/user-attachments/assets/a3d4b46c-a3ed-4a55-ba24-520d9e0a3c8c" />


---

## 📘 Changelog

See [CHANGELOG.md](../CHANGELOG.md) for the full version history.

---

## 💡 Future Ideas

Everything above this section is current, shipped functionality. The list below is loose ideas for later, not a committed plan — no fixed timeline, order isn't priority.

**Armory ideas:**
* Item Database: "Compare Items" — compare two catalog items side by side, in the header spot the removed "Equip Character"/"Crafting Calculator" shortcut buttons used to occupy
* Settings: an opt-in "Use app offline" download (icons + item details) so a fresh install can browse fully offline without waiting on per-item network fetches
* A real "equipped Arcana cards" state feeding GearScore, the same way Gear/Daevanion already do
* Favoriting individual stat rows for a pinned quick-glance view
* Season-aware dungeon/material availability (once a reliable patch-notes source is available)
* Shugo.gg character import & stat comparison (blocked until a Global-region endpoint exists) — first chance to test is the Sept 17 Global test phase (2-3 days), otherwise full testing from Sept 30; would extend to the Skill Planner/Arcana too, not just the Build Planner, depending on what data is actually available

### Overlay & Flow Map
* Flow Map: item picker + a dedicated "Item Node" card type
* Flow Map: merge branches instead of a strict tree

### Quality of Life
* Profile sharing via a short share-code
* In-app wiki / documentation
* About page banner
* Automated Discord update announcements with screenshots (currently posted manually via webhook)

---

## 📄 License

This project is currently under a custom license.

---

## ❤️ Credits

Developed with Python · PySide6 · Qt · GitHub Releases API
