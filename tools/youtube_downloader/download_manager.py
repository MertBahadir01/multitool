"""
Download manager: spawns worker QThreads for concurrent yt-dlp downloads.
Signals carry per-item and global progress updates back to the UI thread.
"""

import os
import re
import shutil
import time

import yt_dlp
from PySide6.QtCore import QObject, QThread, Signal


def _find_ffmpeg() -> str | None:
    """
    Returns a valid ffmpeg location for yt-dlp.
    - If ffmpeg is found in PATH → returns its folder
    - Otherwise → searches common locations
    - If not found → returns None
    """

    # 1. Check system PATH
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return os.path.dirname(ffmpeg_path)

    # 2. Common locations
    candidates = [
        r"C:\ffmpeg\bin",
        r"C:\Program Files\ffmpeg\bin",
        r"C:\Program Files (x86)\ffmpeg\bin",
        os.path.join(os.path.expanduser("~"), "ffmpeg", "bin"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ffmpeg", "bin"),
        os.path.join(os.path.dirname(__file__), "ffmpeg", "bin"),
        os.path.dirname(__file__),
    ]

    for path in candidates:
        exe = os.path.join(path, "ffmpeg.exe")
        if os.path.isfile(exe):
            return path

    return None

FFMPEG_LOCATION = _find_ffmpeg()

# Exact reason string used for user-initiated stops, so the UI layer can
# tell "stopped on purpose" apart from a genuine failure (different status
# label, not logged to the Failed panel, eligible for Resume).
CANCEL_REASON = "Cancelled by user"


# ---------------------------------------------------------------------------
# Per-item worker
# ---------------------------------------------------------------------------

class DownloadWorker(QThread):
    """Downloads a single item and emits progress / completion signals.

    NOTE: this Signal is deliberately named `download_finished`, not
    `finished` — QThread already has a built-in no-arg `finished` signal,
    and a same-named Signal on a subclass shadows it, which is a classic
    PySide footgun (wrong signal gets connected/emitted depending on
    lookup order). Keeping them named differently avoids that entirely.
    """

    progress          = Signal(str, float, str, str)   # item_id, percent, speed, eta
    download_finished = Signal(str, bool, str, str)     # item_id, success, reason, filepath

    def __init__(self, item: dict, output_dir: str, fmt: str, quality: str, parent=None):
        super().__init__(parent)
        self.item       = item
        self.output_dir = output_dir
        self.fmt        = fmt           # "MP4" | "MP3"
        self.quality    = quality       # e.g. "1080p" | "320kbps"
        self._cancelled = False
        self._filepath  = ""

    def cancel(self):
        self._cancelled = True

    # ------------------------------------------------------------------
    def run(self):
        item_id = self.item["id"]
        url     = self.item["url"]

        outtmpl = os.path.join(self.output_dir, "%(title)s.%(ext)s")

        # Build yt-dlp options
        if self.fmt == "MP3":
            bitrate = re.sub(r"\D", "", self.quality) or "192"
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": outtmpl,
                "writethumbnail": True,
                "postprocessors": [
                    {
                        # 1. Extract audio and convert to MP3
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": bitrate,
                    },
                    {
                        # 2. Convert thumbnail to jpg — YouTube often sends webp
                        #    which mutagen/ID3 cannot embed directly
                        "key": "FFmpegThumbnailsConvertor",
                        "format": "jpg",
                        "when": "before_dl",
                    },
                    {
                        # 3. Write ID3 tags (title, uploader, album, year…)
                        #    Must come before EmbedThumbnail
                        "key": "FFmpegMetadata",
                        "add_metadata": True,
                    },
                    {
                        # 4. Embed the jpg thumbnail as ID3 APIC (cover art)
                        "key": "EmbedThumbnail",
                        "already_have_thumbnail": False,
                    },
                ],
                "quiet": True,
                "no_warnings": True,
                "progress_hooks": [self._hook],
            }
        else:
            height = re.sub(r"\D", "", self.quality) or "1080"
            ydl_opts = {
                "format": f"bestvideo[height<={height}]+bestaudio/best[height<={height}]",
                "outtmpl": outtmpl,
                "merge_output_format": "mp4",
                "quiet": True,
                "no_warnings": True,
                "progress_hooks": [self._hook],
            }

        # Inject ffmpeg path if not on system PATH
        if FFMPEG_LOCATION:
            ydl_opts["ffmpeg_location"] = FFMPEG_LOCATION

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            if self._cancelled:
                # Download happened to finish right as cancel was requested —
                # still report it as cancelled for consistent bookkeeping.
                self.download_finished.emit(item_id, False, CANCEL_REASON, "")
            else:
                self.download_finished.emit(item_id, True, "", self._filepath)
        except yt_dlp.utils.DownloadError as e:
            if self._cancelled:
                reason = CANCEL_REASON
            else:
                reason = str(e)
                if "Private video" in reason:
                    reason = "Private video"
                elif "age" in reason.lower():
                    reason = "Age-restricted content"
                elif "not available" in reason.lower():
                    reason = "Not available in your region"
                elif "ffmpeg" in reason.lower():
                    reason = "ffmpeg not found — check CHANGES_NEEDED.txt"
            self.download_finished.emit(item_id, False, reason, "")
        except Exception as e:
            # Covers anything unexpected raised while unwinding a cancelled
            # download too (e.g. ffmpeg subprocess errors mid-cleanup) — a
            # download_finished signal must ALWAYS fire exactly once, or the
            # manager's bookkeeping stalls and Start/Cancel stay stuck.
            reason = CANCEL_REASON if self._cancelled else str(e)
            self.download_finished.emit(item_id, False, reason, "")

    def _hook(self, d):
        if self._cancelled:
            raise yt_dlp.utils.DownloadError(CANCEL_REASON)

        if d["status"] == "downloading":
            pct_raw = d.get("_percent_str", "0%").strip().replace("%", "")
            try:
                pct = float(pct_raw)
            except ValueError:
                pct = 0.0
            speed = d.get("_speed_str", "").strip() or "—"
            eta   = d.get("_eta_str",   "").strip() or "—"
            self.progress.emit(self.item["id"], pct, speed, eta)

        elif d["status"] == "finished":
            self._filepath = d.get("filename", "")
            self.progress.emit(self.item["id"], 100.0, "", "")


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class DownloadManager(QObject):
    """
    Orchestrates concurrent workers (up to max_workers at a time).
    """

    item_progress   = Signal(str, float, str, str)   # id, pct, speed, eta
    item_done       = Signal(str, bool, str, str)     # id, ok, reason, path
    all_done        = Signal(int, int, list)          # completed, total, failures

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers:   list[DownloadWorker] = []
        self._queue:     list[tuple]          = []
        self._max:       int                  = 3
        self._completed: int                  = 0
        self._failed:    list                 = []
        self._total:     int                  = 0
        self._active:    int                  = 0
        self._stopping:  bool                 = False

    def start_downloads(self, entries: list[dict], output_dir: str,
                        fmt: str, quality: str, max_workers: int = 3):
        self._workers   = []
        self._queue     = [(e, output_dir, fmt, quality) for e in entries]
        self._max       = max_workers
        self._completed = 0
        self._failed    = []
        self._total     = len(entries)
        self._active    = 0
        self._stopping  = False

        os.makedirs(output_dir, exist_ok=True)
        self._fill_slots()

    def cancel_all(self):
        """Gracefully stop everything — queued items never start, active
        items are asked to stop cooperatively.

        IMPORTANT: this must never call QThread.terminate(). Forcibly
        killing a thread that may be inside yt-dlp/ffmpeg's C code is
        unsafe and was the actual cause of the app crashing on Stop.
        It also must never drop the last Python reference to a worker
        while its underlying QThread might still be running — Qt treats
        that as a fatal error ("QThread: Destroyed while thread is still
        running") and aborts the whole process. So workers are only
        removed from self._workers in _on_item_done(), once each one has
        actually reported back that it stopped.
        """
        self._stopping = True

        # Nothing still waiting in line gets started.
        self._queue.clear()

        # Cooperative cancel — checked by each worker's progress hook,
        # which then exits its own run() cleanly on the next callback.
        for w in list(self._workers):
            w.cancel()

        # If nothing was actually active, there's nothing to wait for.
        if not self._workers:
            self.all_done.emit(self._completed - len(self._failed), self._total, self._failed)

    # ------------------------------------------------------------------
    def _fill_slots(self):
        if self._stopping:
            return
        while self._queue and self._active < self._max:
            item, d, f, q = self._queue.pop(0)
            worker = DownloadWorker(item, d, f, q)
            worker.progress.connect(self.item_progress)
            worker.download_finished.connect(self._on_item_done)
            self._workers.append(worker)
            self._active += 1
            worker.start()

    def _on_item_done(self, item_id: str, ok: bool, reason: str, path: str):
        self._active    -= 1
        self._completed += 1

        # Safe to drop the reference now — the worker just told us (via a
        # queued cross-thread signal) that its run() has finished, so the
        # underlying QThread is done or is finishing up on its own; we're
        # not yanking it out from under a still-running thread.
        finished_worker = None
        for w in list(self._workers):
            if w.item["id"] == item_id:
                finished_worker = w
                self._workers.remove(w)
                break

        if not ok:
            title = finished_worker.item.get("title", item_id) if finished_worker else item_id
            self._failed.append({"id": item_id, "title": title, "reason": reason})
        self.item_done.emit(item_id, ok, reason, path)

        if self._stopping:
            # Don't queue anything new; just wait for whatever was already
            # active to finish reporting back, then signal completion once.
            if not self._workers:
                self.all_done.emit(self._completed - len(self._failed), self._total, self._failed)
            return

        if self._completed >= self._total:
            self.all_done.emit(
                self._completed - len(self._failed),
                self._total,
                self._failed,
            )
        else:
            self._fill_slots()