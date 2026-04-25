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
    Return the directory containing ffmpeg.exe, or None if already on PATH.
    Checks common Windows install locations and the plugin's own folder.
    """
    if shutil.which("ffmpeg"):
        return None  # Already on PATH — yt-dlp finds it automatically

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
        if os.path.isfile(os.path.join(path, "ffmpeg.exe")):
            return path
    return None


FFMPEG_LOCATION = _find_ffmpeg()


# ---------------------------------------------------------------------------
# Per-item worker
# ---------------------------------------------------------------------------

class DownloadWorker(QThread):
    """Downloads a single item and emits progress / completion signals."""

    progress    = Signal(str, float, str, str)   # item_id, percent, speed, eta
    finished    = Signal(str, bool, str, str)     # item_id, success, reason, filepath

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
            if not self._cancelled:
                self.finished.emit(item_id, True, "", self._filepath)
        except yt_dlp.utils.DownloadError as e:
            reason = str(e)
            if "Private video" in reason:
                reason = "Private video"
            elif "age" in reason.lower():
                reason = "Age-restricted content"
            elif "not available" in reason.lower():
                reason = "Not available in your region"
            elif "ffmpeg" in reason.lower():
                reason = "ffmpeg not found — check CHANGES_NEEDED.txt"
            self.finished.emit(item_id, False, reason, "")
        except Exception as e:
            self.finished.emit(item_id, False, str(e), "")

    def _hook(self, d):
        if self._cancelled:
            raise yt_dlp.utils.DownloadError("Cancelled by user")

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

    def start_downloads(self, entries: list[dict], output_dir: str,
                        fmt: str, quality: str, max_workers: int = 3):
        self._workers   = []
        self._queue     = [(e, output_dir, fmt, quality) for e in entries]
        self._max       = max_workers
        self._completed = 0
        self._failed    = []
        self._total     = len(entries)
        self._active    = 0

        os.makedirs(output_dir, exist_ok=True)
        self._fill_slots()

    def cancel_all(self):
        # 1. Set global cancel flag (IMPORTANT)
        self._cancelled = True
    
        # 2. Cancel all active workers
        for w in list(self._workers):
            try:
                w.cancel()
            except Exception:
                pass
            
            # optional hard stop if supported
            if hasattr(w, "terminate"):
                try:
                    w.terminate()
                except Exception:
                    pass
                
        # 3. Clear queue (prevents future starts)
        if hasattr(self, "_queue"):
            self._queue.clear()
    
        # 4. Reset worker tracking
        self._workers.clear()
    
        # 5. Optional: reset state flags
        self._running = False
    
    # ------------------------------------------------------------------
    def _fill_slots(self):
        while self._queue and self._active < self._max:
            item, d, f, q = self._queue.pop(0)
            worker = DownloadWorker(item, d, f, q)
            worker.progress.connect(self.item_progress)
            worker.finished.connect(self._on_item_done)
            self._workers.append(worker)
            self._active += 1
            worker.start()

    def _on_item_done(self, item_id: str, ok: bool, reason: str, path: str):
        self._active    -= 1
        self._completed += 1
        if not ok:
            title = item_id
            for w in self._workers:
                if w.item["id"] == item_id:
                    title = w.item.get("title", item_id)
                    break
            self._failed.append({"id": item_id, "title": title, "reason": reason})
        self.item_done.emit(item_id, ok, reason, path)

        if self._completed >= self._total:
            self.all_done.emit(
                self._completed - len(self._failed),
                self._total,
                self._failed,
            )
        else:
            self._fill_slots()