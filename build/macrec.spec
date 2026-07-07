# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
root = Path(SPECPATH).parent
helper_bin = root / "meetrec" / "platform" / "macos" / "helper" / "MeetRecSystemAudio"

meetrec_hidden = collect_submodules("meetrec")
mac_binaries = []
if helper_bin.is_file():
    mac_binaries.append((str(helper_bin), "."))

a = Analysis(
    [str(root / "meetrec" / "__main__.py")],
    pathex=[str(root)],
    binaries=mac_binaries,
    datas=[
        (str(root / "meetrec" / "resources" / "icons" / "*.png"), "meetrec/resources/icons"),
        (str(root / "meetrec" / "resources" / "logo.png"), "meetrec/resources"),
        (str(root / "meetrec" / "resources" / "logo.jpg"), "meetrec/resources"),
    ],
    hiddenimports=meetrec_hidden
    + [
        "meetrec.gui.native_panel_macos",
        "meetrec.gui.native_prompt_macos",
        "meetrec.gui.panel_factory",
        "customtkinter",
        "PIL",
        "PIL._tkinter_finder",
        "imageio_ffmpeg",
        "psutil",
        "pystray",
        "pystray._darwin",
        "objc",
        "Quartz",
        "AppKit",
        "CoreAudio",
        "sounddevice",
        "numpy",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pyaudiowpatch", "pycaw", "comtypes"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MeetRec",
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
)

app = BUNDLE(
    exe,
    name="Desktop Meeting Recorder.app",
    icon=str(root / "meetrec" / "resources" / "logo.png"),
    bundle_identifier="ai.o2consult.meetrec",
    info_plist={
        "CFBundleDisplayName": "Desktop Meeting Recorder",
        "CFBundleName": "Desktop Meeting Recorder",
        "LSUIElement": True,
        "NSMicrophoneUsageDescription": "Desktop Meeting Recorder needs microphone access to record your side of calls.",
        "NSScreenCaptureUsageDescription": "Desktop Meeting Recorder captures system audio during meetings you choose to record.",
        "NSHighResolutionCapable": True,
    },
)
