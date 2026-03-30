# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\Program\\Python USB\\Hidrostatik_Test\\Hidrostatik_Test_Chat.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['CoolProp.CoolProp'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['CoolProp.GUI', 'CoolProp.Plots', 'CoolProp.tests', 'matplotlib', 'pandas', 'scipy', 'pytest', 'PyQt5', 'PyQt6', 'PySide6', 'openpyxl', 'lxml', 'pyarrow'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HidrostatikTest',
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
    version='D:\\Program\\Python USB\\Hidrostatik_Test\\release\\build-temp\\version_info.txt',
    manifest='D:\\Program\\Python USB\\Hidrostatik_Test\\windows_manifest.xml',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='HidrostatikTest',
)
