# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

# Dynamically collect PySide6 plugin binaries and useful data files
hiddenimports = collect_submodules('pyqtgraph')  # include pyqtgraph submodules if any

datas = []
binaries = []

try:
    from PySide6 import QtCore

    pyside_dir = os.path.dirname(QtCore.__file__)
    plugins_dir = os.path.join(pyside_dir, 'plugins')
    if os.path.isdir(plugins_dir):
        for root, _, files in os.walk(plugins_dir):
            for f in files:
                src = os.path.join(root, f)
                # target path inside dist: plugins/<subpath>
                rel_dir = os.path.relpath(root, pyside_dir)
                dest_dir = os.path.join('plugins', rel_dir)
                binaries.append((src, dest_dir))

    qt_bin_dir = os.path.join(pyside_dir, 'Qt', 'bin')
    if os.path.isdir(qt_bin_dir):
        for fname in os.listdir(qt_bin_dir):
            if fname.lower().endswith('.dll'):
                src = os.path.join(qt_bin_dir, fname)
                binaries.append((src, os.path.join('PySide6', 'Qt', 'bin')))

    # include shiboken6 shared libraries (required by PySide6)
    shiboken_dir = os.path.join(os.path.dirname(pyside_dir), 'shiboken6')
    if os.path.isdir(shiboken_dir):
        for fname in os.listdir(shiboken_dir):
            if fname.lower().endswith('.dll'):
                binaries.append((os.path.join(shiboken_dir, fname), '.'))
except Exception:
    # best-effort: if PySide6 not available at build-time, leave empty
    pass

# Include top-level json resources used by app
root_dir = os.path.abspath(os.getcwd())
for fname in ('palette.json', 'signal_definitions.json', 'acu_config.json'):
    p = os.path.join(root_dir, fname)
    if os.path.isfile(p):
        datas.append((p, '.'))

# Include protocol templates folder if present
tpl_src = os.path.join(root_dir, 'protocol_templates')
if os.path.isdir(tpl_src):
    for root, _, files in os.walk(tpl_src):
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(root, root_dir)
            datas.append((src, rel))

# Also include the `protocols/templates` package data so loader can find
# `protocols/templates/acusim.yaml` when running the frozen app.
pkg_tpl_src = os.path.join(root_dir, 'protocols', 'templates')
if os.path.isdir(pkg_tpl_src):
    for root, _, files in os.walk(pkg_tpl_src):
        for f in files:
            src = os.path.join(root, f)
            # preserve package relative path so files end up under
            # _internal\protocols\templates\...
            rel = os.path.relpath(root, root_dir)
            datas.append((src, rel))

block_cipher = None

main_script = os.path.join(root_dir, 'main.py')


# No filtering of ICU dlls here — bundle dependencies from the active
# build environment so that the Qt/PySide6 ICU versions match.

a = Analysis([
    main_script,
],
             pathex=[root_dir],
             binaries=binaries,
             datas=datas,
             hiddenimports=hiddenimports,
             hookspath=[],
             runtime_hooks=[os.path.join(root_dir, 'build', 'pyside6_rth_path.py')],
             excludes=['PyQt5', 'PyQt5.*'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

filtered_binaries = a.binaries

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='ACU_simulation_UI',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          console=False )

coll = COLLECT(exe,
               filtered_binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=False,
               name='ACU_simulation_UI')
