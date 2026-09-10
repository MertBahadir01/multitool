# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

block_cipher = None

# Core + required libs.
#
# yt_dlp IS included here and bundled completely normally, like every
# other dependency. This matters for the "Update yt-dlp" feature
# (services/ytdlp_updater.py): it's tempting to think an updatable copy
# needs yt_dlp EXCLUDED from the frozen build so a newer copy on disk can
# "win" — but that backfires, because PyInstaller only detects a
# dependency (stdlib or third-party) as needed by scanning the real source
# of each module it bundles. Exclude yt_dlp and PyInstaller never sees its
# internal `import optparse` (and others), so it never bundles them either
# — breaking yt-dlp on a fresh install, before any update was ever
# attempted. Bundling it normally, and instead letting the vendor
# directory take priority on sys.path at runtime (see
# services.ytdlp_updater.bootstrap, called at the top of main.py), gives
# the same self-update capability without that trap. See
# docs/YT_DLP_UPDATER.md for the full explanation.
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
    'yt_dlp',
    'mutagen',
    'pypdf'
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