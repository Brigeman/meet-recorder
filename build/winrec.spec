# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
# SPECPATH is the build/ directory; parent is the repository root.
root = Path(SPECPATH).parent
winrec_hidden = collect_submodules("winrec")

a_gui = Analysis(
    [str(root / "winrec" / "__main__.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[],
    hiddenimports=winrec_hidden
    + [
        "pyaudiowpatch",
        "comtypes",
        "customtkinter",
        "PIL",
        "PIL._tkinter_finder",
        "imageio_ffmpeg",
        "pycaw",
        "psutil",
        "pystray",
        "pystray._win32",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_gui = PYZ(a_gui.pure, a_gui.zipped_data, cipher=block_cipher)

exe_gui = EXE(
    pyz_gui,
    a_gui.scripts,
    a_gui.binaries,
    a_gui.zipfiles,
    a_gui.datas,
    [],
    name="WinRec",
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
)

a_det = Analysis(
    [str(root / "winrec" / "detector" / "service.py")],
    pathex=[str(root)],
    hiddenimports=winrec_hidden + ["comtypes", "pycaw", "psutil"],
    cipher=block_cipher,
)
pyz_det = PYZ(a_det.pure, a_det.zipped_data, cipher=block_cipher)
exe_det = EXE(
    pyz_det,
    a_det.scripts,
    a_det.binaries,
    a_det.zipfiles,
    a_det.datas,
    [],
    name="WinRec.Detector",
    console=True,
)

a_rec = Analysis(
    [str(root / "winrec" / "recorder" / "service.py")],
    pathex=[str(root)],
    hiddenimports=winrec_hidden + ["pyaudiowpatch", "numpy", "imageio_ffmpeg"],
    cipher=block_cipher,
)
pyz_rec = PYZ(a_rec.pure, a_rec.zipped_data, cipher=block_cipher)
exe_rec = EXE(
    pyz_rec,
    a_rec.scripts,
    a_rec.binaries,
    a_rec.zipfiles,
    a_rec.datas,
    [],
    name="WinRec.Recorder",
    console=True,
)
