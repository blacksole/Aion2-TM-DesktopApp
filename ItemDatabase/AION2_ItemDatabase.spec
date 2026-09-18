# -*- mode: python ; coding: utf-8 -*-


# The standalone Armory viewer (`python app.py`'s packaged twin).  It now
# needs three things the hand-written styles.qss used to make unnecessary:
#
#   * the TEMPLATE instead of the sheet -- app.py renders it per theme;
#   * core/theme.py, which owns every token and data colour in it.  app.py
#     imports it optionally (see its "Design tokens" block) and falls back
#     to plain Abyss without it, so this is what keeps the standalone build
#     on the real six-theme engine rather than the fallback;
#   * assets/, for the one url() in the sheet (the combo dropdown arrow).
#     That was already missing before this wave -- the arrow silently did
#     not load in this build.
a = Analysis(
    ['app.py'],
    pathex=['..'],
    binaries=[],
    datas=[
        ('styles.template.qss', '.'),
        ('assets', 'assets'),
    ],
    hiddenimports=['core.theme'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AION2_ItemDatabase',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
