"""
Self-updater for the bundled yt-dlp library.

WHY THIS EXISTS
----------------
MultiTool Studio uses yt-dlp as a Python *library* (``import yt_dlp``) rather
than shelling out to a separate ``yt-dlp.exe``. That's convenient in normal
development, but it creates a real problem once the app is frozen into a
single .exe with PyInstaller: PyInstaller embeds every imported package
(including yt_dlp) inside the executable itself. There is no "yt-dlp.exe
file" sitting next to the app that a user (or this app) could just
overwrite — the copy of yt-dlp is baked into the frozen binary and can never
be modified in place. Since YouTube changes frequently, an old, unpatched
yt-dlp is the single most common reason a "YouTube downloader" app silently
stops working after a few months.

HOW THIS SOLVES IT
-------------------
yt-dlp ships on PyPI as a pure-Python, platform-independent wheel (no C
extensions, no compiler, no admin rights needed to install it). That means
a *newer* copy of the ``yt_dlp`` package can simply be unpacked as plain
.py files onto disk, in a writable, per-user folder outside the frozen
.exe, e.g. ``%LOCALAPPDATA%\\MultiTool Studio\\ytdlp_vendor\\yt_dlp`` on
Windows.

At startup, :func:`bootstrap` makes sure that folder (if it has a copy in
it) is what Python actually imports when anything in the app does
``import yt_dlp`` — taking priority over whatever version PyInstaller froze
into the .exe at build time. If no updated copy has been installed yet, the
app transparently falls back to the version bundled inside the .exe, so a
fresh install works immediately, offline, out of the box.

"Update yt-dlp" (triggered from the UI) then just means: ask PyPI for the
latest version, compare it to what's currently importable, and if newer,
download that version's wheel to a temp location, unpack and verify it
there, and only *after* that fully succeeds, atomically swap it in for the
old vendor copy (keeping a backup so a swap that fails partway can be
rolled back). None of this touches the running process's already-imported
yt_dlp module, so the update takes effect the next time the app starts —
by design, since replacing code backing an already-imported module while a
download might be using it is unsafe.

See docs/YT_DLP_UPDATER.md for the matching PyInstaller build instructions.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import traceback
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import requests

APP_FOLDER_NAME = "MultiTool Studio"
PYPI_PROJECT_URL = "https://pypi.org/pypi/yt-dlp/json"
REQUEST_TIMEOUT = 15          # seconds, per HTTP request
DOWNLOAD_CHUNK_SIZE = 1 << 16  # 64 KiB
MIN_VALID_WHEEL_BYTES = 200_000  # sanity floor — a real yt-dlp wheel is several MB


# ---------------------------------------------------------------------------
# Diagnostics — the app is built with console=False, so without this,
# a silent failure (e.g. a seeding step that fails and is intentionally
# swallowed so it doesn't take down the whole app) is completely invisible.
# Every meaningful step below writes one line here.
# ---------------------------------------------------------------------------

def _log_path() -> Path:
    return get_app_data_dir() / "ytdlp_update.log"


def _log(message: str) -> None:
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {message}\n")
    except OSError:
        pass  # logging must never be the reason something else breaks


def _log_exception(context: str, exc: BaseException) -> None:
    _log(f"{context}: {exc!r}\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class UpdaterError(Exception):
    """Base class for all yt-dlp updater failures. Message is user-facing."""


class NetworkError(UpdaterError):
    """No internet connection, DNS failure, timeout, etc."""


class ServerError(UpdaterError):
    """PyPI (or the download host) reached but returned an error/unavailable."""


class DownloadFailedError(UpdaterError):
    """The download completed the HTTP request but the payload was bad
    (too small, not a valid zip/wheel, missing expected contents)."""


class PermissionDeniedError(UpdaterError):
    """Couldn't write to the vendor directory (locked file, read-only
    filesystem, antivirus lock, etc.)."""


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def get_app_data_dir() -> Path:
    """Per-user, writable data directory for this app — never inside the
    PyInstaller .exe/temp-extraction folder, so it survives updates/
    reinstalls of the app itself and never needs admin rights."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    path = Path(base) / APP_FOLDER_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_vendor_dir() -> Path:
    """Folder that gets prepended to sys.path — its ``yt_dlp`` subfolder,
    if present, is the "installed" copy of yt-dlp."""
    path = get_app_data_dir() / "ytdlp_vendor"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_vendor_package_dir() -> Path:
    return get_vendor_dir() / "yt_dlp"


# ---------------------------------------------------------------------------
# Bootstrap — must run before ANYTHING does `import yt_dlp`
# ---------------------------------------------------------------------------

def bootstrap() -> None:
    """Call once, at the very top of main.py, before any module that might
    import yt_dlp (directly or indirectly) is imported.

    This inserts the vendor directory at the front of ``sys.path``, so the
    standard import machinery finds an updated copy there before it finds
    the copy PyInstaller bundled into the .exe at build time (confirmed
    empirically: CPython's normal path-based finder is consulted before
    PyInstaller's frozen-module importer gets a chance to claim the name,
    both for the top-level ``yt_dlp`` package and for its submodules, e.g.
    ``yt_dlp.utils``). If nothing has been installed to the vendor
    directory yet, this is a no-op and the app simply uses whatever
    yt-dlp PyInstaller bundled normally — which is why yt_dlp must NOT be
    excluded from the PyInstaller build (see docs/YT_DLP_UPDATER.md): if
    it were excluded, none of yt-dlp's own dependencies (stdlib modules
    like ``optparse``, third-party ones it uses conditionally) would ever
    get detected and bundled either, breaking it even on a fresh install
    with no update ever applied.

    As a safety net, the vendor copy is sanity-imported right here, before
    the rest of the app starts. If a previous update left behind a broken
    copy (corrupted files, a dependency that genuinely isn't available),
    that failure is caught, the vendor copy is disabled for this run only,
    and the app falls back to the normally bundled yt-dlp instead of
    crashing on startup. Nothing on disk is deleted — a working "Update
    yt-dlp" click can still repair it later.
    """
    vendor_dir = get_vendor_dir()
    vendor_path_str = str(vendor_dir)
    pkg_init = get_vendor_package_dir() / "__init__.py"

    if not pkg_init.is_file():
        return  # nothing installed yet — normal resolution finds the bundled copy

    if vendor_path_str not in sys.path:
        sys.path.insert(0, vendor_path_str)

    if "yt_dlp" in sys.modules:
        return  # something already imported it this process; too late to change

    try:
        import yt_dlp  # noqa: F401
        import yt_dlp.version  # noqa: F401
        _log(f"bootstrap: using vendor yt-dlp v{get_installed_version()} from {vendor_path_str}")
    except Exception as e:
        _log_exception(f"bootstrap: vendor copy at {vendor_path_str} failed to import, disabling it for this run", e)
        _purge_yt_dlp_from_sys_modules()
        try:
            sys.path.remove(vendor_path_str)
        except ValueError:
            pass
        # One retry so a working, normally-bundled fallback copy (if any)
        # gets imported cleanly instead of leaving a half-failed state.
        try:
            import yt_dlp  # noqa: F401
            _log("bootstrap: fell back to the bundled yt-dlp copy successfully")
        except Exception as e2:
            _log_exception("bootstrap: bundled yt-dlp is also unavailable", e2)


def _purge_yt_dlp_from_sys_modules() -> None:
    for name in list(sys.modules):
        if name == "yt_dlp" or name.startswith("yt_dlp."):
            sys.modules.pop(name, None)


# ---------------------------------------------------------------------------
# Version info
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"__version__\s*=\s*['\"]([^'\"]+)['\"]")


def _read_version_from_file(version_py: Path) -> Optional[str]:
    try:
        text = version_py.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _VERSION_RE.search(text)
    return m.group(1) if m else None


def get_installed_version() -> str:
    """The version of yt-dlp actually in effect right now — the vendor
    copy if one has been installed, otherwise whatever is importable
    (the copy bundled inside the .exe, or a normal pip install in dev
    mode). Deliberately reads version.py directly rather than importing,
    so it works correctly even before/without calling bootstrap()."""
    vendor_version = get_vendor_package_dir() / "version.py"
    v = _read_version_from_file(vendor_version)
    if v:
        return v
    try:
        import yt_dlp.version as ydv  # noqa: PLC0415
        return getattr(ydv, "__version__", "unknown")
    except Exception:
        return "unknown"


def _version_tuple(v: str):
    parts = re.split(r"[.\-]", v)
    out = []
    for p in parts:
        out.append(int(p) if p.isdigit() else p)
    return tuple(out)


def _is_newer(latest: str, current: str) -> bool:
    if latest == current:
        return False
    try:
        return _version_tuple(latest) > _version_tuple(current)
    except TypeError:
        # Mixed int/str tuple comparison blew up (unexpected version
        # scheme) — fall back to a plain inequality check so we still
        # offer the update rather than silently doing nothing.
        return latest != current


# ---------------------------------------------------------------------------
# Update check
# ---------------------------------------------------------------------------

@dataclass
class UpdateCheckResult:
    current_version: str
    latest_version: str
    update_available: bool
    download_url: Optional[str]
    filename: Optional[str]


def check_for_update() -> UpdateCheckResult:
    current = get_installed_version()

    try:
        resp = requests.get(PYPI_PROJECT_URL, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout as e:
        raise NetworkError("Timed out contacting PyPI. Check your internet connection.") from e
    except requests.exceptions.ConnectionError as e:
        raise NetworkError("Couldn't reach PyPI. Check your internet connection.") from e
    except requests.exceptions.RequestException as e:
        raise NetworkError(f"Network error while checking for updates: {e}") from e

    if resp.status_code >= 500:
        raise ServerError(f"PyPI is currently unavailable (HTTP {resp.status_code}). Try again later.")
    if resp.status_code != 200:
        raise ServerError(f"Unexpected response from PyPI (HTTP {resp.status_code}).")

    try:
        data = resp.json()
    except (json.JSONDecodeError, ValueError) as e:
        raise ServerError("PyPI returned an unreadable response.") from e

    latest = data.get("info", {}).get("version")
    if not latest:
        raise ServerError("Couldn't determine the latest yt-dlp version from PyPI.")

    wheel_url = None
    wheel_name = None
    for entry in data.get("urls", []):
        if entry.get("packagetype") == "bdist_wheel" and entry.get("filename", "").endswith("-py3-none-any.whl"):
            wheel_url = entry.get("url")
            wheel_name = entry.get("filename")
            break

    if wheel_url is None:
        raise ServerError(f"No downloadable wheel found for yt-dlp {latest}.")

    return UpdateCheckResult(
        current_version=current,
        latest_version=latest,
        update_available=_is_newer(latest, current),
        download_url=wheel_url,
        filename=wheel_name,
    )


# ---------------------------------------------------------------------------
# Download + install
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[int, int], None]  # (bytes_downloaded, total_bytes_or_0)


def _download_wheel(url: str, dest_path: Path, progress_cb: Optional[ProgressCallback]) -> None:
    try:
        resp = requests.get(url, stream=True, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout as e:
        raise NetworkError("Timed out downloading the update. Check your internet connection.") from e
    except requests.exceptions.ConnectionError as e:
        raise NetworkError("Lost connection while downloading the update.") from e
    except requests.exceptions.RequestException as e:
        raise NetworkError(f"Network error while downloading the update: {e}") from e

    if resp.status_code >= 500:
        raise ServerError(f"Download server is currently unavailable (HTTP {resp.status_code}).")
    if resp.status_code != 200:
        raise ServerError(f"Unexpected response while downloading the update (HTTP {resp.status_code}).")

    total = int(resp.headers.get("Content-Length", 0) or 0)
    downloaded = 0

    try:
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb:
                    progress_cb(downloaded, total)
    except requests.exceptions.RequestException as e:
        raise NetworkError(f"Connection interrupted mid-download: {e}") from e
    except OSError as e:
        raise PermissionDeniedError(f"Couldn't write the downloaded update to disk: {e}") from e

    if downloaded < MIN_VALID_WHEEL_BYTES:
        raise DownloadFailedError(
            f"Downloaded file looks incomplete ({downloaded} bytes) — update aborted."
        )
    if total and downloaded != total:
        raise DownloadFailedError(
            f"Downloaded {downloaded} of {total} expected bytes — update aborted."
        )


def _extract_package(wheel_path: Path, extract_to: Path, expected_version: str) -> Path:
    try:
        with zipfile.ZipFile(wheel_path) as zf:
            bad = zf.testzip()
            if bad is not None:
                raise DownloadFailedError(f"Downloaded update is corrupted (bad entry: {bad}).")
            members = [n for n in zf.namelist() if n.startswith("yt_dlp/")]
            if not members:
                raise DownloadFailedError("Downloaded update doesn't contain a yt_dlp package.")
            zf.extractall(extract_to, members=members)
    except zipfile.BadZipFile as e:
        raise DownloadFailedError("Downloaded update is not a valid package (corrupted download).") from e

    new_pkg_dir = extract_to / "yt_dlp"
    version_file = new_pkg_dir / "version.py"
    got_version = _read_version_from_file(version_file)
    if not got_version:
        raise DownloadFailedError("Downloaded update is missing version information.")
    # yt-dlp's package metadata sometimes formats the version slightly
    # differently between PyPI's JSON API (e.g. "2026.8.19") and the
    # version.py baked into the wheel itself (e.g. "2026.08.19") — compare
    # numerically rather than as exact strings so that isn't mistaken for
    # a corrupted download.
    if _version_tuple(got_version) != _version_tuple(expected_version):
        raise DownloadFailedError(
            f"Downloaded update reports version {got_version}, expected {expected_version}."
        )
    return new_pkg_dir


def _atomic_swap(new_pkg_dir: Path) -> None:
    target = get_vendor_package_dir()
    backup = target.with_name(target.name + ".backup")

    try:
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)

        moved_old = False
        if target.exists():
            os.replace(target, backup)  # rename aside — near-instant, same volume
            moved_old = True

        try:
            shutil.move(str(new_pkg_dir), str(target))
        except OSError:
            # Roll back so the app is never left without a working copy.
            if moved_old:
                if target.exists():
                    shutil.rmtree(target, ignore_errors=True)
                os.replace(backup, target)
            raise
    except PermissionError as e:
        raise PermissionDeniedError(
            "Couldn't replace the old yt-dlp files — check that no download "
            "is currently running and that the app has write access to "
            f"{get_vendor_dir()}."
        ) from e
    except OSError as e:
        raise PermissionDeniedError(f"Couldn't install the update: {e}") from e
    else:
        shutil.rmtree(backup, ignore_errors=True)


def download_and_install(
    download_url: str,
    filename: str,
    expected_version: str,
    progress_cb: Optional[ProgressCallback] = None,
) -> str:
    """Downloads `download_url` to a temp location, verifies it, and only
    then swaps it in for the current vendor copy. Raises UpdaterError (or a
    subclass) with a user-facing message on any failure; the existing,
    working yt-dlp copy is left untouched if anything goes wrong.

    Returns the newly installed version string on success.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="mtstudio_ytdlp_update_"))
    try:
        wheel_path = tmp_dir / (filename or "yt_dlp.whl")
        _download_wheel(download_url, wheel_path, progress_cb)

        extract_dir = tmp_dir / "extracted"
        extract_dir.mkdir()
        new_pkg_dir = _extract_package(wheel_path, extract_dir, expected_version)

        _atomic_swap(new_pkg_dir)
        _log(f"download_and_install: succeeded, now at v{expected_version}")
        return expected_version
    except UpdaterError as e:
        _log(f"download_and_install: failed — {e}")
        raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
