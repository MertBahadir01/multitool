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
    else is imported, makes sure `import yt_dlp` (anywhere in the app)
    resolves to that vendor copy if one exists, falling back transparently
    to whatever's bundled in the .exe if not.
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

- **`tools/youtube_downloader/ytdlp_update_worker.py`** is a thin `QThread`
  wrapper so the button never blocks the UI on network I/O.

- **`tools/youtube_downloader/youtube_downloader_tool.py`** shows the
  current version, the button, and progress/result dialogs. If yt-dlp
  turns out to be completely unavailable (see the build step below), it
  falls back to a minimal "yt-dlp engine not found — Download yt-dlp"
  screen instead of the tool silently disappearing from the app.

## Required build step — read this before running PyInstaller

`build.spec` deliberately **excludes** `yt_dlp` from PyInstaller's
`Analysis`. If it weren't excluded, PyInstaller would compile yt-dlp's code
into its own internal frozen-module archive, and *that* copy would always
win over the vendor copy on `sys.path` for submodule imports (e.g.
`yt_dlp.utils`) — silently defeating the whole updater. Excluding it means
the .exe genuinely has no yt-dlp code of its own; it only ever runs the
version sitting in the vendor folder.

That means a **seed copy** has to ship with the .exe instead, as plain
data files, so a fresh install works immediately, offline, before the user
ever clicks Update. Before building:

```bash
python scripts/prepare_ytdlp_seed.py     # copies your installed yt-dlp into resources/ytdlp_seed/
pyinstaller build.spec
```

`build.spec` will refuse to build (with a clear error message) if you skip
the seed step — better to catch that at build time than ship a broken .exe.
You only need to re-run `prepare_ytdlp_seed.py` if you want to bump the
*starting* version that fresh installs get; "Update yt-dlp" inside the app
fetches newer releases at runtime regardless, independent of what was
seeded at build time.

## Everything else is unchanged

`download_manager.py` and `playlist_parser.py` still just `import yt_dlp`
and use its normal Python API exactly as before — nothing about how
downloads/parsing actually work was touched. The updater only controls
*which copy* of `yt_dlp` that `import` resolves to.
