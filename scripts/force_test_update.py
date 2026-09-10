"""
Forces the "Update yt-dlp" button to have something real to do, so you can
watch the whole download -> verify -> install path run end to end, instead
of correctly deciding there's nothing to update.

It does this by writing a fake, deliberately old yt-dlp copy into the
vendor folder (the same folder the real updater uses:
%LOCALAPPDATA%\\MultiTool Studio\\ytdlp_vendor\\yt_dlp on Windows). The next
time you click "Update yt-dlp" in the app, it will see that "old" version,
see a newer one is available on PyPI, and perform a REAL download and
install — not a simulation. This exercises the exact same code as a real
future yt-dlp release would.

Usage
-----
    python scripts/force_test_update.py

Then start (or restart) MultiToolStudio.exe, open the YouTube Downloader
tool, and click "Update yt-dlp". You should see:
  - the version label showing something old first
  - a real download happen
  - a success dialog with the real new version number
  - the ytdlp_vendor\\yt_dlp folder actually get replaced with real content
  - %LOCALAPPDATA%\\MultiTool Studio\\ytdlp_update.log gain new lines

To undo this and go back to whatever the .exe has built in, just delete
the vendor folder afterwards:
    python scripts/force_test_update.py --reset
"""

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services import ytdlp_updater as u  # noqa: E402

FAKE_OLD_VERSION = "2000.01.01"


def force_outdated():
    pkg_dir = u.get_vendor_package_dir()
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # The updater only reads version.py to determine the "installed"
    # version (see get_installed_version()) — it doesn't need a full,
    # importable yt_dlp package for this test, just that one file, so the
    # app correctly believes an ancient version is currently installed.
    (pkg_dir / "version.py").write_text(
        f"__version__ = '{FAKE_OLD_VERSION}'\n", encoding="utf-8"
    )
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

    print(f"Wrote fake version {FAKE_OLD_VERSION} to: {pkg_dir}")
    print("Now start MultiToolStudio.exe, open YouTube Downloader, and")
    print('click "Update yt-dlp" — it will download and install a real,')
    print("current version of yt-dlp on top of this.")


def reset():
    vendor_pkg = u.get_vendor_package_dir()
    if vendor_pkg.exists():
        shutil.rmtree(vendor_pkg)
        print(f"Removed: {vendor_pkg}")
        print("The app will now fall back to the yt-dlp bundled in the .exe.")
    else:
        print(f"Nothing to remove — {vendor_pkg} doesn't exist.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset", action="store_true",
        help="Remove the vendor copy instead of faking an old version.",
    )
    args = parser.parse_args()
    reset() if args.reset else force_outdated()
