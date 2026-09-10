# yt-dlp self-updater

MultiTool Studio can update its own yt-dlp engine from inside the app —
no rebuilding the .exe, no manually downloading or swapping files.

## Why this needed a real design, not just "pip install -U yt-dlp"

The YouTube Downloader tool uses yt-dlp as a **Python library**
(`import yt_dlp`), not as a separate `yt-dlp.exe`. That's normally fine,
but once the app is frozen into a single .exe with PyInstaller, the copy
of `yt_dlp` gets compiled into the .exe's own internal module archive.
There is no `yt-dlp.exe` file sitting next to the app to overwrite, and
`pip install -U yt-dlp` doesn't mean anything inside a frozen executable —
there's no interpreter or site-packages folder to install into.

yt-dlp happens to ship as a **pure-Python, platform-independent wheel** on
PyPI (no compiler or admin rights needed to "install" it — it's just a
folder of `.py` files). That makes an in-app updater practical: keep a
second, writable copy of the `yt_dlp` package on disk, outside the frozen
.exe, and make sure Python imports *that* copy instead of whatever was
frozen in at build time.

## How it works

- **`services/ytdlp_updater.py`** is the whole implementation. Read the
  module docstring for the full detail; short version:
  - A writable per-user folder holds the "vendor" copy of yt-dlp:
    - Windows: `%LOCALAPPDATA%\MultiTool Studio\ytdlp_vendor\yt_dlp`
    - macOS: `~/Library/Application Support/MultiTool Studio/ytdlp_vendor/yt_dlp`
    - Linux: `~/.local/share/MultiTool Studio/ytdlp_vendor/yt_dlp`
  - `bootstrap()`, called at the very top of `main.py` before anything
    else is imported, prepends that folder to `sys.path`. If it contains
    an updated copy, `import yt_dlp` (anywhere in the app, including
    submodule imports like `yt_dlp.utils`) resolves to it in preference to
    the copy PyInstaller bundled into the .exe. If nothing has been
    installed there yet, this is a no-op and the app just uses the
    normally bundled copy — a fresh install works immediately, offline,
    with no update required.
  - It also sanity-checks the vendor copy right there at startup: if a
    previous update somehow left a broken copy behind, that failure is
    caught, the vendor copy is disabled *for this run only*, and the app
    falls back to the bundled copy instead of failing to start. Nothing on
    disk is deleted, so a later "Update yt-dlp" click can still repair it.
  - **"Update yt-dlp"** (button in the YouTube Downloader tab) asks PyPI's
    JSON API for the latest version, compares it to what's currently
    installed, and — only if newer — downloads that version's wheel to a
    temp folder, verifies it (valid zip, expected size, correct version
    inside), and *only after all of that succeeds* atomically swaps it in
    for the old vendor copy, keeping a backup that's restored automatically
    if the swap itself fails partway (e.g. a locked file).
  - The change takes effect the next time the app is started — the
    already-imported `yt_dlp` module in the running process is left alone,
    since replacing code backing a module that a download might currently
    be using is not safe to do live.
  - Every meaningful step writes a line to
    `<app data dir>/ytdlp_update.log` (see paths above). The app itself
    runs with `console=False`, so this log is the only way to see what
    happened if something goes wrong on a user's machine.

- **`tools/youtube_downloader/ytdlp_update_worker.py`** is a thin `QThread`
  wrapper so the button never blocks the UI on network I/O.

- **`tools/youtube_downloader/youtube_downloader_tool.py`** shows the
  current version, the button, and progress/result dialogs. If yt-dlp
  somehow can't be imported at all, it falls back to a minimal "yt-dlp
  engine not found — Download yt-dlp" screen instead of the tool silently
  disappearing from the app.

## The one rule for `build.spec`

**`yt_dlp` must stay bundled normally** — it's just another entry in
`build.spec`'s `libs` list, exactly like `requests` or `mutagen`. Do **not**
add it to `excludes` or try to ship a separate "seed" copy as raw data
instead. That was tried and reverted: PyInstaller only detects a module's
own dependencies by scanning its real source as part of bundling it.
Exclude `yt_dlp` and PyInstaller never sees its internal
`import optparse` (and a handful of others) and never bundles them either
— so a fresh install breaks immediately, before any update was ever
attempted, even though "Update yt-dlp" itself reports success (it really
did download and install yt-dlp's own files correctly — the missing piece
was a stdlib module yt-dlp needs that was never bundled in the first
place).

Bundling `yt_dlp` normally and letting `sys.path` priority (see
`bootstrap()` above) do the work instead gives the same self-update
capability without that trap — confirmed by building and running an
actual frozen PyInstaller executable with this exact setup.

## Everything else is unchanged

`download_manager.py` and `playlist_parser.py` still just `import yt_dlp`
and use its normal Python API exactly as before — nothing about how
downloads/parsing actually work was touched. The updater only controls
*which copy* of `yt_dlp` that `import` resolves to.
