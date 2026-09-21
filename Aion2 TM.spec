# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        # The bundled OFL faces core/fonts.py registers at startup. Already
        # inside ('assets', 'assets') above -- named again on purpose so that
        # trimming the broad assets entry (it also carries icons/logos/banner)
        # can never silently ship a build with no typography: MASTER §1 makes
        # Barlow/Barlow Condensed/JetBrains Mono part of the design system,
        # not decoration. PyInstaller de-duplicates identical TOC entries.
        ('assets/fonts', 'assets/fonts'),
        # The vendored Lucide subset (MASTER §3, "Icônes : Lucide (ISC)") and
        # the per-theme chevrons under its tinted/ folder.  Same reasoning as
        # the fonts line above: already inside ('assets', 'assets'), named
        # again so that trimming the broad entry cannot silently ship a build
        # with no icons -- and unlike a missing font, a missing icon set
        # fails *loudly* (ui/widgets/icons.py raises KeyError on an unknown
        # name) rather than falling back to something that still renders.
        # The tinted chevrons are what QSS `image: url()` points at, so
        # losing them un-draws every combo/spin-box arrow.
        ('assets/icons/lucide', 'assets/icons/lucide'),
        # ui/styles.qss is gone (2026-09-18): the app renders its stylesheet
        # from this template via core/theme.build_qss(), so the TEMPLATE is
        # what has to reach _MEIPASS/ui/.
        ('ui/styles.template.qss', 'ui'),
        ('ItemDatabase/app.py', 'ItemDatabase'),
        # The Armory's calculation core (Stage 1 of the split in
        # docs/audit-2026-09-18/B-armory.md §4.2).  app.py is shipped as a
        # DATA file above, not in the PYZ -- the host loads it with
        # spec_from_file_location -- so PyInstaller never follows its
        # imports, and a package it imports has to be shipped as data too or
        # the frozen app dies at Armory-open with ModuleNotFoundError.  A
        # directory source is copied recursively, which is what makes this
        # ONE line instead of one per module: unlike ItemDatabase/data/
        # below, there is nothing in here but source to ship, so the
        # per-file discipline that folder needs does not apply.
        #
        # The destination has to be exactly beside app.py: app.py puts its
        # own directory (and, frozen, _MEIPASS/ItemDatabase) on sys.path so
        # `import armory_engine` resolves.  Gated by
        # tests/test_armory_engine_packaging.py.
        ('ItemDatabase/armory_engine', 'ItemDatabase/armory_engine'),
        # ItemDatabase/styles.qss is gone (2026-09-18, the Armory
        # tokenization wave): the Armory renders its own sheet from this
        # TEMPLATE via core.theme.build_qss_from(), per theme, exactly as
        # the app does from ui/styles.template.qss above.  Both halves have
        # to reach _MEIPASS/ItemDatabase/ -- the template AND the
        # dropdown-arrow PNG its one url() points at, which travels inside
        # ('ItemDatabase/assets', …) below.
        ('ItemDatabase/styles.template.qss', 'ItemDatabase'),
        ('ItemDatabase/assets', 'ItemDatabase/assets'),
        # Real bug found + fixed (User-reported, 2026-09-05, screenshot:
        # the Pantheon Lord filter always showed zero results after
        # updating to 1.9.2) -- this list silently fell 5 files behind as
        # new data/*.json files got added over time without anyone
        # remembering to add a matching line here (pantheon_items.json,
        # wings_items.json, shop_items.json, dungeon_sets.json,
        # stat_priority_options.json were all missing). Deliberately NOT
        # bundling the whole ItemDatabase/data/ folder in one entry --
        # confirmed it also holds ~278MB of runtime icon/detail-fetch
        # caches (icons/, details/) plus dev-only research screenshots
        # that must never ship, so each real data file still needs its
        # own explicit line; whoever adds the next fetch_*.py script's
        # output file needs to add it here too.
        ('ItemDatabase/data/items_all.json', 'ItemDatabase/data'),
        ('ItemDatabase/data/recipes_all.json', 'ItemDatabase/data'),
        ('ItemDatabase/data/skills_all.json', 'ItemDatabase/data'),
        ('ItemDatabase/data/arcana_info.json', 'ItemDatabase/data'),
        ('ItemDatabase/data/arcana_class_skills.json', 'ItemDatabase/data'),
        ('ItemDatabase/data/dungeons_all.json', 'ItemDatabase/data'),
        ('ItemDatabase/data/daevanion_boards_s.json', 'ItemDatabase/data'),
        ('ItemDatabase/data/daevanion_boards_a.json', 'ItemDatabase/data'),
        ('ItemDatabase/data/pantheon_items.json', 'ItemDatabase/data'),
        ('ItemDatabase/data/wings_items.json', 'ItemDatabase/data'),
        ('ItemDatabase/data/shop_items.json', 'ItemDatabase/data'),
        ('ItemDatabase/data/dungeon_sets.json', 'ItemDatabase/data'),
        ('ItemDatabase/data/stat_priority_options.json', 'ItemDatabase/data'),
        # Read-only reference copies of the 3 language Default profiles
        # (User-Wunsch, 2026-09-10, after discovering the packaged app never
        # shipped these at all: "Können wir in der App die Profile mitgeben
        # ... Dann machen wir in der App ein 'Backup Verzeichnis' - in dem
        # liegen dann die Defaults"). Sourced straight from the real
        # profiles/ folder (single source of truth, no separate copy to
        # keep in sync) but land under their OWN "default_profiles" bundle
        # folder -- deliberately NOT reusing the name "profiles" here, since
        # MainWindow._resolve_profile_dir() already treats a folder literally
        # named "profiles" next to the exe as the user's own LIVE, portable-
        # mode profile directory; bundling seed data under that same name
        # would silently flip every fresh install from AppData to portable
        # mode. MainWindow._refresh_default_profiles_backup() copies these
        # into the user's own profile_dir/Backup/ on every launch.
        ('profiles/Default.json', 'default_profiles'),
        ('profiles/Default_de.json', 'default_profiles'),
        ('profiles/Default_ru.json', 'default_profiles'),
        # The Settings -> Changelog "Update History" dialog now reads this
        # directly (User-Wunsch, 2026-09-17: show every version, including
        # ones that were tagged/built but never separately published as a
        # GitHub Release) instead of only what GitHub's /releases list
        # happens to contain -- see ui/update_dialog.py's _changelog_path().
        ('CHANGELOG.md', '.'),
    ],
    hiddenimports=['email', 'email.mime', 'email.mime.text', 'email.mime.multipart'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 'xml' removed (real bug found + fixed, User-reported via Discord,
        # 2026-09-05: "Could not read the file: No module named 'xml'")
        # -- openpyxl (added this update for Full View's XLSX export/
        # import) needs xml.etree.ElementTree internally to read/write
        # .xlsx files, which are just zipped XML under the hood. Excluding
        # the whole 'xml' package predates that dependency and broke both
        # directions in the packaged EXE (export likely too, just not yet
        # reported) even though it worked fine from source, since a dev
        # run always has the full stdlib available regardless of this
        # exclude list.
        'tkinter', 'unittest', 'xmlrpc', 'pydoc', 'doctest',
        'difflib', 'multiprocessing', 'concurrent', 'sqlite3',
        'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtSensors',
        'PySide6.QtWebEngine', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets', 'PySide6.QtWebChannel',
        'PySide6.QtWebSockets', 'PySide6.Qt3DCore', 'PySide6.Qt3DRender',
        'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.Qt3DAnimation',
        'PySide6.Qt3DExtras', 'PySide6.QtCharts', 'PySide6.QtDataVisualization',
        # 'PySide6.QtMultimedia' removed (Linux port, 2026-09-18): core/sound.py
        # plays notification sounds through QSoundEffect on every non-Windows
        # host (winsound stays the Windows backend). Excluding it shipped a
        # build that could never make a sound outside Windows. QtMultimedia
        # WIDGETS stays excluded -- no video surface is used anywhere.
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtLocation', 'PySide6.QtPositioning',
        'PySide6.QtRemoteObjects', 'PySide6.QtScxml',
        'PySide6.QtSerialPort', 'PySide6.QtSerialBus',
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Aion2 TM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Forward slashes: a backslash path is one literal filename on a
    # Linux PyInstaller run, and the Linux port landed 2026-09-18.
    icon=['assets/icons/aion2_tm_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Aion2 TM',
)
