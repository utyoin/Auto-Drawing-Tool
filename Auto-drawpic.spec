from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path.cwd()
src_dir = project_root / "src"
icon_file = project_root / "assets" / "auto_drawpic.ico"

hiddenimports = collect_submodules("pynput")


a = Analysis(
    ["run_mouse_draw_app.py"],
    pathex=[str(project_root), str(src_dir)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
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
    name="Auto-drawpic",
    icon=str(icon_file),
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
