"""
Run this once before building the .exe with PyInstaller:

    python scripts/prepare_ytdlp_seed.py
    pyinstaller build.spec

It copies whatever yt-dlp version is currently pip-installed in this
environment into resources/ytdlp_seed/yt_dlp/, as plain .py files. build.spec
ships that folder inside the .exe as raw data (not compiled into
PyInstaller's frozen module archive), so services.ytdlp_updater can seed a
writable, updatable copy from it the first time the app runs — see
docs/YT_DLP_UPDATER.md for the full picture.

You don't need to run this again for every build unless you want to bump
the "starting" version users get on a fresh install — "Update yt-dlp"
inside the app fetches newer releases at runtime regardless.
"""

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = PROJECT_ROOT / "resources" / "ytdlp_seed" / "yt_dlp"


def main() -> int:
    try:
        import yt_dlp
    except ImportError:
        print(
            "ERROR: yt-dlp isn't installed in this Python environment.\n"
            "Run:  pip install -r requirements.txt\nthen try again.",
            file=sys.stderr,
        )
        return 1

    source_dir = Path(yt_dlp.__file__).resolve().parent
    if not (source_dir / "version.py").is_file():
        print(f"ERROR: {source_dir} doesn't look like a real yt_dlp package.", file=sys.stderr)
        return 1

    if SEED_DIR.exists():
        shutil.rmtree(SEED_DIR)
    SEED_DIR.parent.mkdir(parents=True, exist_ok=True)

    shutil.copytree(
        source_dir,
        SEED_DIR,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    from yt_dlp.version import __version__ as version
    print(f"Seeded yt-dlp v{version} into {SEED_DIR.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
