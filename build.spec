# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

block_cipher = None

# Core + required libs 
libs = [
    'PySide6',
    'PIL',              # Pillow
    'qrcode',
    'bcrypt',
    'cryptography',
    'requests',
    'pyperclip',
    'psutil',
    'pandas',
    'matplotlib',
    'yt_dlp'
]

# OPTIONAL libs 
optional_libs = [
    'numpy',
    'cv2',              # opencv-python-headless
    'pyzbar',
    'pytesseract',
    'moviepy'
]

# Merge if needed (you can comment this line if you don't want optional ones bundled)
#libs += optional_libs

hidden_imports = []
for lib in libs:
    try:
        hidden_imports += collect_submodules(lib)
    except Exception:
        pass  # prevents crash if a lib isn't installed

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('tools', 'tools'),
        ('ui', 'ui'),
        ('database', 'database'),
        ('core', 'core'),
        ('services', 'services')
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'tkinter',  # unused, reduces size
        'pytest',
        'unittest'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MultiToolStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='icom.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='MultiToolStudio'
)