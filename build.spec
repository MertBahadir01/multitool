# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

block_cipher = None

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
YTDLP_SEED_DIR = os.path.join(SPEC_DIR, 'resources', 'ytdlp_seed', 'yt_dlp')

# yt-dlp is deliberately handled differently from every other dependency
# below (see services/ytdlp_updater.py for the full explanation): it is
# EXCLUDED from Analysis rather than bundled normally, and instead a seed
# copy is shipped as plain data files under ytdlp_seed/. That's what lets
# "Update yt-dlp" inside the app replace it later without rebuilding the
# .exe — a version PyInstaller had compiled into its own frozen module
# archive could never be swapped out at runtime.
if not os.path.isfile(os.path.join(YTDLP_SEED_DIR, 'version.py')):
    raise SystemExit(
        "\n"
        "ERROR: resources/ytdlp_seed/yt_dlp is missing or empty.\n"
        "Run this first, from the project root, before building:\n"
        "\n"
        "    python scripts/prepare_ytdlp_seed.py\n"
        "\n"
        "This copies the currently pip-installed yt-dlp package into "
        "resources/ytdlp_seed/ so the .exe has a working copy on first "
        "run (before the user ever clicks \"Update yt-dlp\"). See "
        "docs/YT_DLP_UPDATER.md for details.\n"
    )

# Core + required libs  — NOTE: yt_dlp is intentionally NOT in this list,
# see the comment above and docs/YT_DLP_UPDATER.md.
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
        ('services', 'services'),
        # Raw, uncompiled seed copy of yt-dlp — NOT collected as code, so
        # it's found by services.ytdlp_updater on first run via plain
        # filesystem access under sys._MEIPASS, and copied into the
        # writable, updatable vendor directory. See docs/YT_DLP_UPDATER.md.
        (YTDLP_SEED_DIR, os.path.join('ytdlp_seed', 'yt_dlp')),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'tkinter',  # unused, reduces size
        'pytest',
        'unittest',
        'yt_dlp',   # see the comment near the top of this file
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