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

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=vgamepad_dlls,
    datas=logo_files,
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
        'logger_config',
        'error_handler',
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
