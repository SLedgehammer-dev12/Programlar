# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


project_root = Path(SPECPATH)

datas = []
datas += collect_data_files("customtkinter")
datas += collect_data_files("darkdetect")
datas += collect_data_files("matplotlib")
datas += copy_metadata("CoolProp")
datas += copy_metadata("customtkinter")
datas += copy_metadata("fpdf2")
datas += copy_metadata("matplotlib")
datas += copy_metadata("packaging")
datas += copy_metadata("pydantic")

hiddenimports = [
    "CoolProp.CoolProp",
    "tkinter",
    "tkinter.ttk",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.backends._backend_tk",
]
hiddenimports += collect_submodules("customtkinter")
hiddenimports += collect_submodules("PIL")

a = Analysis(
    ["run_app.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["IPython", "jupyter"],
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
    name="Natural Gas Prop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version="file_version_info.txt",
)
