"""
QThread wrapper around services.ytdlp_updater so the "Update yt-dlp" button
never blocks the UI thread with network calls.
"""

from PySide6.QtCore import QThread, Signal

from services import ytdlp_updater as updater


class YtDlpUpdateWorker(QThread):
    """Runs a full check-then-update pass off the UI thread.

    Signals
    -------
    progress(downloaded_bytes, total_bytes)
        Emitted repeatedly while a new version is downloading. total_bytes
        may be 0 if the server didn't send a Content-Length header.
    finished_ok(status, current_version, latest_version)
        status is "up_to_date" or "updated".
    failed(message)
        Any error — network, server, corrupt download, permissions —
        already reduced to a single user-facing message.
    """

    progress    = Signal(int, int)
    finished_ok = Signal(str, str, str)
    failed      = Signal(str)

    def run(self):
        try:
            result = updater.check_for_update()

            if not result.update_available:
                self.finished_ok.emit(
                    "up_to_date", result.current_version, result.latest_version
                )
                return

            updater.download_and_install(
                result.download_url,
                result.filename,
                result.latest_version,
                progress_cb=lambda done, total: self.progress.emit(done, total),
            )
            self.finished_ok.emit(
                "updated", result.current_version, result.latest_version
            )
        except updater.UpdaterError as e:
            self.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001 — last-resort safety net for the UI
            self.failed.emit(f"Unexpected error while updating yt-dlp: {e}")
