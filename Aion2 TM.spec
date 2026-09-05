# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('ui/styles.qss', 'ui'),
        ('ItemDatabase/app.py', 'ItemDatabase'),
        ('ItemDatabase/styles.qss', 'ItemDatabase'),
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
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
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
    icon=['assets\\icons\\aion2_tm_icon.ico'],
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
