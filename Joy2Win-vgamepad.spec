# -*- mode: python ; coding: utf-8 -*-

import os
import vgamepad

# Get vgamepad path
vgamepad_path = os.path.dirname(vgamepad.__file__)

# Collect vgamepad DLL files
vgamepad_dlls = [
    (os.path.join(vgamepad_path, 'win', 'vigem', 'client', 'x64', 'ViGEmClient.dll'), 'vgamepad/win/vigem/client/x64'),
    (os.path.join(vgamepad_path, 'win', 'vigem', 'client', 'x86', 'ViGEmClient.dll'), 'vgamepad/win/vigem/client/x86'),
]

# Check for logo files
logo_file = None
for logo_name in ['logo.ico', 'logo.png', 'icon.ico', 'icon.png']:
    if os.path.exists(logo_name):
        logo_file = logo_name
        break

# Collect logo files for bundling
logo_files = []
if logo_file:
    logo_files.append((logo_file, '.'))

# Optional WinUHid user-mode SDK, built locally with tools/build-winuhid.bat.
# Bundling it lets the single exe use the Raw Input virtual mouse without the
# user having to place the DLLs beside it (virtual_mouse also checks the exe
# folder first, so a user-supplied build still wins).
winuhid_files = []
for _dll in ('WinUHid.dll', 'WinUHidDevs.dll'):
    if os.path.exists(_dll):
        winuhid_files.append((_dll, '.'))

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=vgamepad_dlls,
    datas=logo_files + winuhid_files,
    hiddenimports=[
        'vgamepad',
        'vgamepad.win',
        'vgamepad.win.vigem_client',
        'vgamepad.win.virtual_gamepad',
        'bleak',
        'bleak.backends',
        'bleak.backends.winrt',
        'pynput',
        'pynput.mouse',
        'pynput.keyboard',
        'logger_config',
        'error_handler',
        # These packages have no __init__ side effects that PyInstaller can
        # infer through the entry point in every build mode.
        'control_type',
        'control_type.duo_joycon',
        'control_type.single_joycon',
        'control_type.rumble_stream',
        'control_type.mouse_scroll',
        'control_type.virtual_mouse',
        'controllers',
        'controllers.JoyconL',
        'controllers.JoyconR',
        'controllers.battery',
        'controllers.hd_rumble',
        'controllers.stick_calibration',
    ],
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
    name='Joy2Win-vgamepad',
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
    version='version_info.txt',
    icon='logo_256.ico' if os.path.exists('logo_256.ico') else 'logo.ico' if os.path.exists('logo.ico') else None,
)
