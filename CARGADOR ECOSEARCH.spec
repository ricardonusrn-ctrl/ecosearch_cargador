# -*- mode: python ; coding: utf-8 -*-
# Build:  py -m PyInstaller "CARGADOR ECOSEARCH.spec" --noconfirm --clean
# Rutas relativas a la carpeta del .spec para que funcione en cualquier equipo.

from PyInstaller.utils.hooks import collect_data_files

# config.json, logo e ícono van dentro del .exe (core.config.ROOT) y además junto al .exe
# instalado (el config.json de ahí es el editable).
datas = collect_data_files('customtkinter') + [
    ('config.json', '.'),
    ('LOGO BOND.png', '.'),
    ('CARGADOR ECOSEARCH.ico', '.'),
]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['openpyxl', 'customtkinter', 'PIL', 'PIL._tkinter_finder'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # No los usa: evita que PyInstaller arrastre librerías pesadas instaladas en el equipo.
    excludes=['numpy', 'pandas', 'matplotlib', 'scipy', 'pytest', 'lasio', 'dlisio'],
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
    name='CARGADOR ECOSEARCH',
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
    icon=['CARGADOR ECOSEARCH.ico'],
    version='version_info.txt',
)
