# Developer setup

Requires [uv](https://docs.astral.sh/uv/). Python 3.12 is pinned by `pyproject.toml`; same commands on Linux and Windows.

```bash
uv sync --group dev                        # runtime + pytest/ruff, from uv.lock
uv run python main.py                      # launch
uv run ruff check .                        # lint
QT_QPA_PLATFORM=offscreen uv run pytest    # tests, no display needed
```
`pyproject.toml` + `uv.lock` are the source of truth for dev; `requirements*.txt` exist only for the
Windows release workflow (`requirements-build.txt` = PyInstaller and friends).

**Config and profiles** — path resolution lives in `utils/paths.py`; do not hardcode paths.
`config.json` is runtime state and gitignored — copy `config.example.json` for a starting point.
Profiles sit in `profiles/` next to the repo from source, in `%APPDATA%\Aion2 TM\Profiles` when frozen
(`$XDG_DATA_HOME/aion2-tm/Profiles` on Linux); `profiles/last_profile.txt` is rewritten every launch and
untracked. See "Portable mode" below for `<install>/profiles`.

**Build the Windows exe** (Windows only, output in `dist/`):
```bash
uv sync --group build && uv run pyinstaller "Aion2 TM.spec"
```
**Run on Linux** — `./scripts/aion2-tm` (forces XWayland on a Wayland session; see README). The
dev-only `winsound` stub that used to live in `.venv` is gone: `core/sound.py` is the real cross-platform
backend, and CI's `smoke-import` job fails the build if `ui.main_window` ever stops importing on Linux.

---

## Windows-visible changes in this branch

The port's hard rule is that Windows behaviour stays byte-identical. These are the
deliberate exceptions, each one a decision rather than an accident.

| Change | Where | Why |
|---|---|---|
| Minimum window height `820` → `700` | `ui/main_window.py` `_setup_window` | 820 px exceeded the usable height of a 1366×768 laptop (and of a 1080p screen with a taskbar plus a title bar), so the window could not be fitted or resized down on those machines. Applies to every platform, Windows included. |
| `Browse...` row in the notification-sound picker | `ui/pages/settings_page.py` `populate_sound_combo` | On Linux the system sound themes ship `.oga`, which `QSoundEffect` cannot play, so the system list is empty and Browse is the only way to pick a sound. On Windows the list is non-empty, so the row is appended **last** and the existing entries keep their order and position. |
| Profile folder opens via `os.startfile` instead of `explorer "<dir>"` | `core/platform.py` `open_path`, called from `SettingsPage._open_profile_dir` | One cross-platform "open this path" helper. On a default Windows install this is Explorer; on a machine that registers another file manager (Directory Opus, Total Commander) it now honours that choice. The sibling "reveal and select" path deliberately still spawns `explorer /select,` verbatim, because no portable verb selects a file inside its folder. |
| Armory HTTP cache moves to `%LOCALAPPDATA%\Aion2 TM\Cache\armory` (frozen only) | `ItemDatabase/app.py` `_cache_root`, `_migrate_legacy_cache` | The cache used to be written inside the installation directory, which a per-machine install (Program Files, `/opt`, `/usr/lib`) cannot write to at all. Existing caches are moved once on first launch, per subdirectory, never overwriting an existing one; a cross-volume move falls back from `rename` to copy+unlink. Running from source still uses `ItemDatabase/data/`. |

Not a deviation, but worth recording: the notification-sound picker keeps the old
`sorted(glob.glob(r"C:\Windows\Media\*.wav"))` ordering — sorted by full path,
case-sensitively, so `Ring01` still precedes `chimes`. `core.sound.list_system_wavs`
sorts by `str(path)` for exactly this reason, and
`tests/test_platform.py::test_list_system_wavs_keeps_the_windows_glob_order` locks it with
mixed-case names.

## Portable mode

An empty `portable.txt` **next to the executable** (not inside `_internal/`) makes a frozen
install read and write `<install>/profiles`. `utils.paths.install_root()` is the executable's
directory; `utils.paths.app_root()` is the read-only bundle payload (`sys._MEIPASS`, i.e.
`<install>/_internal` for this onedir spec). They are different directories — anything the
user is told to place next to the app is addressed from `install_root()`.

An install that already has a `<install>/profiles` folder **containing `*.json`** keeps using
it without a marker: those are existing (often portable) installations, and their profiles must
not appear to vanish because a stored absolute path stopped resolving. The marker is only
required to *create* a new portable directory.

## Update integrity

`core.update_checker.decide_checksum_policy` distinguishes three cases the old code collapsed
into one:

- **skip** — the release published no `.sha256` asset (every release older than the checksum
  step). Install, with a warning in `app.log`.
- **abort** — the release *does* publish one but it could not be fetched or parsed. A network
  failure and a tampered mirror are indistinguishable from the client, and the next step
  overwrites the installation: refuse, delete the download, tell the user.
- **verify** — compare the digest.

Only the checker sees the release's asset list, so `sha256_url` travels on the
`update_available` signal to the installer thread; the thread can no longer re-derive the
distinction from a URL alone.

`AION2TM_NO_UPDATE_CHECK=1` disables the startup update check (set automatically by the test suite; useful for packaged Linux builds).
