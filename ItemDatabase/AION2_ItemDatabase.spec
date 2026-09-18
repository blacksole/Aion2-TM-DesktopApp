# -*- mode: python ; coding: utf-8 -*-
import os

# The standalone Armory viewer (`python app.py`'s packaged twin).  It needs
# three things the hand-written styles.qss used to make unnecessary:
#
#   * the TEMPLATE instead of the sheet -- app.py renders it per theme;
#   * core/theme.py, which owns every token and data colour in it.  app.py
#     imports it optionally (see its "Design tokens" block) and falls back
#     to plain Abyss without it, so this is what keeps the standalone build
#     on the real six-theme engine rather than the fallback;
#   * assets/, for the one url() in the sheet (the combo dropdown arrow).
#     That was already missing before this wave -- the arrow silently did
#     not load in this build.
#
# EVERY destination below has to be "ItemDatabase" or under it, and that is
# not cosmetic: frozen, `app.py` reads its own files through
# `_bundled_resource()`, which is `Path(sys._MEIPASS) / "ItemDatabase" /
# name` (app.py:352).  A destination of '.' puts the file in _MEIPASS
# itself, one level too shallow -- `_load_qss_text()` then logs a warning,
# returns "", and the exe runs on Qt's bare default style with no error.
# That is verbatim the 2026-08-27 regression `_bundled_resource`'s own
# docstring memorializes ("was farbig angezeigt wird, ist das Icon eines
# Items - der Rest Grau mit weisser Schrift"), and this spec had re-laid it.
# Gated by tests/test_armory_theme.py::test_the_standalone_spec_bundles_what_the_app_reads.
#
# `pathex` is likewise absolute: PyInstaller resolves a relative pathex
# against the BUILD CWD, not the spec's directory, so '..' only found
# core/ when the build happened to run from inside ItemDatabase/.  From the
# repo root it silently dropped `hiddenimports=['core.theme']` with a
# warning, and the exe fell back to _FALLBACK_TOKENS + _MutedTable(), i.e.
# an item database with no rarity colours at all.
_REPO_ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

a = Analysis(
    ['app.py'],
    pathex=[_REPO_ROOT],
    binaries=[],
    datas=[
        ('styles.template.qss', 'ItemDatabase'),
        ('assets', 'ItemDatabase/assets'),
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
