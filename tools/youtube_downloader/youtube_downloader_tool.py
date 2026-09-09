"""
YouTube Downloader Tool — main PySide6 widget.
Integrates with the multitool_studio plugin architecture.
"""

import os
import re

from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QProgressBar,
    QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem,
    QFileDialog, QTextEdit, QSpinBox, QGroupBox, QSizePolicy,
    QMessageBox, QSplitter, QHeaderView, QFrame,
)

from . import history_service as hs
from .ytdlp_update_worker import YtDlpUpdateWorker
from services import ytdlp_updater

# playlist_parser / download_manager both do `import yt_dlp` at module level.
# In the worst case — a frozen build where no yt-dlp copy is available at
# all yet (no seed shipped, no vendor copy installed, nothing on
# sys.path) — that import fails. Rather than let this whole tool disappear
# from the app (main_window's tool loader silently skips any tool module
# that fails to import), fall back to a minimal "install yt-dlp" screen
# that only needs the updater (which has no yt_dlp dependency itself) to
# get the app fully working again, no rebuild required.
try:
    from .playlist_parser import fetch_info, fetch_formats, format_duration, human_size
    from .download_manager import DownloadManager, CANCEL_REASON
    _YTDLP_IMPORT_ERROR = None
except Exception as _e:  # noqa: BLE001
    fetch_info = fetch_formats = format_duration = human_size = None
    DownloadManager = None
    CANCEL_REASON = "Cancelled by user"
    _YTDLP_IMPORT_ERROR = _e


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m|\x1b\[[0-9;]*[A-Za-z]")

def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# Background fetch worker
# ---------------------------------------------------------------------------

class FetchWorker(QObject):
    done    = Signal(dict)
    error   = Signal(str)
    formats = Signal(list)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            info = fetch_info(self.url)
            self.done.emit(info)
            if info["entries"]:
                fmts = fetch_formats(info["entries"][0]["url"])
                self.formats.emit(fmts)
        except Exception as e:
            self.error.emit(str(e))


# ---------------------------------------------------------------------------
# Per-item download row widget
# ---------------------------------------------------------------------------

class DownloadRow(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)

        self.lbl_title = QLabel(title)
        self.lbl_title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.lbl_title.setMinimumWidth(180)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setFixedWidth(180)
        self.bar.setFixedHeight(18)
        self.bar.setTextVisible(True)

        self.lbl_speed = QLabel("—")
        self.lbl_speed.setFixedWidth(90)
        self.lbl_speed.setStyleSheet("color: #888888;")

        self.lbl_eta = QLabel("—")
        self.lbl_eta.setFixedWidth(55)
        self.lbl_eta.setStyleSheet("color: #888888;")

        self.lbl_status = QLabel("Queued")
        self.lbl_status.setFixedWidth(90)
        self.lbl_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        lay.addWidget(self.lbl_title)
        lay.addWidget(self.bar)
        lay.addWidget(self.lbl_speed)
        lay.addWidget(self.lbl_eta)
        lay.addWidget(self.lbl_status)

    def update_progress(self, pct: float, speed: str, eta: str):
        self.bar.setValue(int(pct))
        self.lbl_speed.setText(_strip_ansi(speed) if speed else "—")
        self.lbl_eta.setText(_strip_ansi(eta) if eta else "—")
        self.lbl_status.setText("Downloading")
        self.lbl_status.setStyleSheet("color: #CCCCCC;")

    def mark_done(self, ok: bool, reason: str = ""):
        self.bar.setValue(100 if ok else self.bar.value())
        self.lbl_speed.setText("")
        self.lbl_eta.setText("")
        if ok:
            self.lbl_status.setText("✓  Done")
            self.lbl_status.setStyleSheet("color: #00BFA5;")
        else:
            self.lbl_status.setText("✗  Failed")
            self.lbl_status.setStyleSheet("color: #F44336;")

    def mark_stopped(self):
        """Distinct from Failed — this item can be picked back up with
        Resume, it didn't error out."""
        self.lbl_speed.setText("")
        self.lbl_eta.setText("")
        self.lbl_status.setText("⏸  Stopped")
        self.lbl_status.setStyleSheet("color: #FFB300;")

    def reset_for_resume(self):
        self.lbl_status.setText("Queued")
        self.lbl_status.setStyleSheet("color: #CCCCCC;")
        self.lbl_speed.setText("—")
        self.lbl_eta.setText("—")


# ---------------------------------------------------------------------------
# Main tool widget
# ---------------------------------------------------------------------------

class YouTubeDownloaderTool(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        # yt-dlp self-updater state — needed in both the normal and the
        # fallback ("engine missing") UI below.
        self._ytdlp_update_worker = None

        if _YTDLP_IMPORT_ERROR is not None:
            self._build_missing_engine_ui()
            return

        self._info         = None
        self._formats      = []
        self._item_rows:   dict[str, DownloadRow] = {}
        self._fetch_thread = None
        self._fetch_obj    = None
        self._manager      = DownloadManager(self)
        self._output_dir   = os.path.expanduser("~/Downloads")
        self._current_fmt  = "MP4"
        self._pl_checks:   list[tuple[QCheckBox, dict]] = []
        self._completed_count = 0
        self._total_count     = 0

        # Stop/Resume state. _pending_entries holds the entries from the
        # current batch that haven't completed successfully yet — either
        # still queued or interrupted by Stop. Resume re-launches exactly
        # these, with the same output dir/format/quality/concurrency as the
        # original run, so yt-dlp's default partial-file resume can pick up
        # any .part files where they left off instead of starting over.
        self._pending_entries: dict[str, dict] = {}
        self._launch_settings = None
        self._was_stopped     = False

        self._manager.item_progress.connect(self._on_item_progress)
        self._manager.item_done.connect(self._on_item_done)
        self._manager.all_done.connect(self._on_all_done)

        self._build_ui()

    # ------------------------------------------------------------------
    # Fallback UI — shown only if yt-dlp couldn't be imported at all
    # ------------------------------------------------------------------

    def _build_missing_engine_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addStretch()

        title = QLabel("yt-dlp engine not found")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)

        msg = QLabel(
            "MultiTool Studio couldn't find a working copy of the yt-dlp "
            "download engine. This can happen on a fresh install if it "
            "wasn't bundled. Click below to download it automatically — "
            "an internet connection is required."
        )
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet("color: #AAAAAA;")

        self.lbl_ytdlp_version = QLabel("yt-dlp engine: not installed")
        self.lbl_ytdlp_version.setAlignment(Qt.AlignCenter)
        self.lbl_ytdlp_version.setStyleSheet("color: #888888;")

        self.btn_update_ytdlp = QPushButton("Download yt-dlp")
        self.btn_update_ytdlp.setFixedWidth(220)
        self.btn_update_ytdlp.clicked.connect(self._update_ytdlp)

        for w in (title, msg, self.lbl_ytdlp_version):
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(w)
            row.addStretch()
            root.addLayout(row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.btn_update_ytdlp)
        btn_row.addStretch()
        root.addLayout(btn_row)

        root.addStretch()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        tabs = QTabWidget()
        tabs.addTab(self._build_download_tab(), "⬇  Download")
        tabs.addTab(self._build_history_tab(),  "🕘  History")
        root.addWidget(tabs)
    def _build_download_tab(self):
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
    
        # =========================
        # URL BAR (TOP FIXED STYLE)
        # =========================
        url_row = QHBoxLayout()
    
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube URL (video or playlist)…")
        self.url_input.returnPressed.connect(self._fetch_info)
    
        self.btn_fetch = QPushButton("Fetch")
        self.btn_fetch.setFixedWidth(100)
        self.btn_fetch.clicked.connect(self._fetch_info)
    
        url_row.addWidget(self.url_input)
        url_row.addWidget(self.btn_fetch)
        root.addLayout(url_row)

        # =========================
        # YT-DLP ENGINE / UPDATER
        # =========================
        engine_row = QHBoxLayout()

        self.lbl_ytdlp_version = QLabel()
        self.lbl_ytdlp_version.setStyleSheet("color: #888888;")

        self.btn_update_ytdlp = QPushButton("Check for yt-dlp Update")
        self.btn_update_ytdlp.setFixedWidth(190)
        self.btn_update_ytdlp.setToolTip(
            "Checks PyPI for a newer yt-dlp release and installs it "
            "automatically if one is available — no manual download needed."
        )
        self.btn_update_ytdlp.clicked.connect(self._update_ytdlp)

        engine_row.addWidget(self.lbl_ytdlp_version, 1)
        engine_row.addWidget(self.btn_update_ytdlp)
        root.addLayout(engine_row)

        self._refresh_ytdlp_version_label()

        # =========================
        # MAIN SCROLL AREA
        # =========================
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    
        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setSpacing(14)
        body_lay.setContentsMargins(8, 8, 8, 8)
    
        # =========================
        # INFO LABEL
        # =========================
        self.lbl_info = QLabel("No video loaded.")
        self.lbl_info.setWordWrap(True)
        body_lay.addWidget(self.lbl_info)
    
        # =========================
        # FORMAT & QUALITY (clean UI + working logic)
        # =========================
        fmt_box = QGroupBox("Format & Quality")
        fmt_lay = QHBoxLayout(fmt_box)
    
        self.btn_mp4 = QPushButton("MP4")
        self.btn_mp3 = QPushButton("MP3")
        self.btn_mp4.setCheckable(True)
        self.btn_mp3.setCheckable(True)
    
        self.btn_mp4.setFixedWidth(80)
        self.btn_mp3.setFixedWidth(80)
    
        # KEEP WORKING LOGIC (from version 2)
        self.btn_mp4.clicked.connect(lambda: self._set_format("MP4"))
        self.btn_mp3.clicked.connect(lambda: self._set_format("MP3"))
    
        self.cmb_quality = QComboBox()
        self.cmb_quality.setMinimumWidth(140)
    
        self.lbl_size = QLabel("Est. size: —")
    
        fmt_lay.addWidget(self.btn_mp4)
        fmt_lay.addWidget(self.btn_mp3)
        fmt_lay.addSpacing(10)
        fmt_lay.addWidget(QLabel("Quality:"))
        fmt_lay.addWidget(self.cmb_quality)
        fmt_lay.addSpacing(10)
        fmt_lay.addWidget(self.lbl_size)
        fmt_lay.addStretch()
    
        body_lay.addWidget(fmt_box)
    
        # =========================
        # PLAYLIST (CLEAN + NO INNER SCROLL BUGS)
        # =========================
        pl_box = QGroupBox("Playlist")
        pl_lay = QVBoxLayout(pl_box)
    
        sel_row = QHBoxLayout()
    
        self.btn_sel_all = QPushButton("Select All")
        self.btn_desel_all = QPushButton("Deselect All")
    
        # keep logic
        self.btn_sel_all.clicked.connect(self._select_all)
        self.btn_desel_all.clicked.connect(self._deselect_all)
    
        self.lbl_sel_count = QLabel("0 items selected")
    
        sel_row.addWidget(self.btn_sel_all)
        sel_row.addWidget(self.btn_desel_all)
        sel_row.addSpacing(12)
        sel_row.addWidget(self.lbl_sel_count)
        sel_row.addStretch()
    
        pl_lay.addLayout(sel_row)
    
        # container (same logic, cleaner layout)
        self._pl_container = QWidget()
        self._pl_layout = QVBoxLayout(self._pl_container)
        self._pl_layout.setAlignment(Qt.AlignTop)
        self._pl_layout.setSpacing(6)
    
        # Scrolls internally once the list gets long, instead of stretching
        # the whole page — keeps Save Settings / Start / Downloads in view.
        pl_scroll = QScrollArea()
        pl_scroll.setWidgetResizable(True)
        pl_scroll.setFrameShape(QFrame.NoFrame)
        pl_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        pl_scroll.setMinimumHeight(230)
        pl_scroll.setMaximumHeight(1100)
        pl_scroll.setWidget(self._pl_container)
    
        pl_lay.addWidget(pl_scroll)
    
        body_lay.addWidget(pl_box)
    
        # =========================
        # SAVE SETTINGS (CLEAN VERSION)
        # =========================
        save_box = QGroupBox("Save Settings")
        save_row = QHBoxLayout(save_box)
    
        self.lbl_outdir = QLabel(self._output_dir)
    
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self._browse_output)
        btn_browse.setFixedWidth(90)
    
        self.spin_conc = QSpinBox()
        self.spin_conc.setRange(1, 10)
        self.spin_conc.setValue(3)
        self.spin_conc.setFixedWidth(60)
    
        save_row.addWidget(QLabel("Save:"))
        save_row.addWidget(self.lbl_outdir, 1)
        save_row.addWidget(btn_browse)
        save_row.addSpacing(15)
        save_row.addWidget(QLabel("Parallel:"))
        save_row.addWidget(self.spin_conc)
    
        body_lay.addWidget(save_box)
    
        # =========================
        # ACTION BUTTONS
        # =========================
        btn_row = QHBoxLayout()
    
        self.btn_start = QPushButton("Start Download")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_resume = QPushButton("Resume")
    
        self.btn_cancel.setEnabled(False)
        self.btn_resume.setEnabled(False)
        self.btn_resume.setVisible(False)
        self.btn_resume.setToolTip(
            "Continue the items that were stopped, at the same format/quality "
            "as the original run — yt-dlp resumes partially-downloaded files "
            "automatically where the server supports it."
        )
    
        # keep working logic
        self.btn_start.clicked.connect(self._start_download)
        self.btn_cancel.clicked.connect(self._cancel_download)
        self.btn_resume.clicked.connect(self._resume_download)
    
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_resume)
        btn_row.addStretch()
    
        body_lay.addLayout(btn_row)
    
        # =========================
        # PROGRESS BAR
        # =========================
        self.bar_global = QProgressBar()
        self.bar_global.setRange(0, 100)
        body_lay.addWidget(self.bar_global)
    
        # =========================
        # DOWNLOAD LIST (FIXED UI SCROLL)
        # =========================
        dl_box = QGroupBox("Downloads")
        dl_lay = QVBoxLayout(dl_box)
    
        self._dl_container = QWidget()
        self._dl_container_lay = QVBoxLayout(self._dl_container)
        self._dl_container_lay.setAlignment(Qt.AlignTop)
        self._dl_container_lay.setSpacing(6)
    
        # Same fix as the playlist list above: scrolls internally so a big
        # batch of downloads doesn't push the rest of the page off-screen.
        dl_scroll = QScrollArea()
        dl_scroll.setWidgetResizable(True)
        dl_scroll.setFrameShape(QFrame.NoFrame)
        dl_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        dl_scroll.setMinimumHeight(230)
        dl_scroll.setMaximumHeight(1100)
        dl_scroll.setWidget(self._dl_container)
    
        dl_lay.addWidget(dl_scroll)
        body_lay.addWidget(dl_box)
    
        # =========================
        # FAILED LOG
        # =========================
        failed_box = QGroupBox("Failed Items")
        failed_lay = QVBoxLayout(failed_box)
    
        self.txt_failed = QTextEdit()
        self.txt_failed.setReadOnly(True)
        self.txt_failed.setFixedHeight(100)
    
        failed_lay.addWidget(self.txt_failed)
        body_lay.addWidget(failed_box)
    
        # FINAL ATTACH
        scroll.setWidget(body)
        root.addWidget(scroll)
    
        self._set_format("MP4")
    
        return w
    # ---- History tab ────────────────────────────────────────────────────────

    def _build_history_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self.cmb_filter = QComboBox()
        self.cmb_filter.addItems(["All", "Completed", "Failed", "Stopped"])
        self.cmb_filter.setFixedWidth(130)
        self.cmb_filter.currentTextChanged.connect(self._load_history)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.setObjectName("secondary")
        btn_refresh.setFixedWidth(90)
        btn_refresh.clicked.connect(self._load_history)
        filter_row.addWidget(self.cmb_filter)
        filter_row.addWidget(btn_refresh)
        filter_row.addStretch()
        lay.addLayout(filter_row)

        self.tbl_history = QTableWidget()
        self.tbl_history.setColumnCount(7)
        self.tbl_history.setHorizontalHeaderLabels(
            ["Title", "Format", "Quality", "Size", "Status", "Date", ""]
        )
        hdr = self.tbl_history.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.tbl_history.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_history.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_history.setAlternatingRowColors(True)
        self.tbl_history.verticalHeader().setVisible(False)
        lay.addWidget(self.tbl_history)

        self._load_history()
        return w

    # ------------------------------------------------------------------
    # Playlist helpers
    # ------------------------------------------------------------------

    def _clear_playlist_ui(self):
        while self._pl_layout.count():
            item = self._pl_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._pl_checks = []

    def _populate_playlist(self, entries):
        self._clear_playlist_ui()
        for i, entry in enumerate(entries):
            container = QWidget()
            container.setStyleSheet(
                "background-color: #2A2A2A;" if i % 2 == 0 else "background-color: #252526;"
            )
            row = QHBoxLayout(container)
            row.setContentsMargins(8, 6, 8, 6)
            row.setSpacing(10)

            cb = QCheckBox()
            cb.setChecked(True)
            cb.stateChanged.connect(self._update_sel_count)

            idx_lbl = QLabel(f"#{entry['index']:>3}")
            idx_lbl.setFixedWidth(32)
            idx_lbl.setStyleSheet("color: #888888;")

            title_lbl = QLabel(entry["title"])
            title_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            dur_lbl = QLabel(f"[{format_duration(entry['duration'])}]")
            dur_lbl.setFixedWidth(60)
            dur_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            dur_lbl.setStyleSheet("color: #888888;")

            row.addWidget(cb)
            row.addWidget(idx_lbl)
            row.addWidget(title_lbl, 1)
            row.addWidget(dur_lbl)

            self._pl_layout.addWidget(container)
            self._pl_checks.append((cb, entry))

        self._update_sel_count()

    def _select_all(self):
        for cb, _ in self._pl_checks:
            cb.setChecked(True)

    def _deselect_all(self):
        for cb, _ in self._pl_checks:
            cb.setChecked(False)

    def _get_selected_entries(self):
        return [e for cb, e in self._pl_checks if cb.isChecked()]

    def _update_sel_count(self):
        n = len(self._get_selected_entries())
        t = len(self._pl_checks)
        self.lbl_sel_count.setText(f"{n} / {t} selected")
        self._update_size_estimate()

    # ------------------------------------------------------------------
    # Format / Quality
    # ------------------------------------------------------------------

    def _set_format(self, fmt: str):
        self._current_fmt = fmt

        # Toggle button appearance — only one active at a time
        self.btn_mp4.setChecked(fmt == "MP4")
        self.btn_mp3.setChecked(fmt == "MP3")
        self.btn_mp4.setStyleSheet(
            "background-color: #00BFA5; color: #fff;" if fmt == "MP4"
            else "background-color: #333333; color: #CCCCCC;"
        )
        self.btn_mp3.setStyleSheet(
            "background-color: #00BFA5; color: #fff;" if fmt == "MP3"
            else "background-color: #333333; color: #CCCCCC;"
        )

        self.cmb_quality.clear()
        if fmt == "MP3":
            self.cmb_quality.addItems(["128 kbps", "192 kbps", "256 kbps", "320 kbps"])
        else:
            if self._formats:
                for f in self._formats:
                    size_str = human_size(f["filesize"])
                    self.cmb_quality.addItem(f"{f['label']}  ({size_str})", f["label"])
            else:
                for res in ["2160p", "1440p", "1080p", "720p", "480p", "360p"]:
                    self.cmb_quality.addItem(res, res)

        self._update_size_estimate()

    def _update_size_estimate(self):
        if not self._info:
            return
        selected = self._get_selected_entries()
        total = sum(e.get("filesize_approx", 0) for e in selected)
        if total:
            self.lbl_size.setText(f"Est. size: {human_size(total)}")
        else:
            self.lbl_size.setText(f"Est. size: —")

    # ------------------------------------------------------------------
    # Fetch info
    # ------------------------------------------------------------------

    def _fetch_info(self):
        url = self.url_input.text().strip()
        if not url:
            return
        self.btn_fetch.setEnabled(False)
        self.btn_fetch.setText("Fetching…")
        self.lbl_info.setText("Fetching video information…")
        self._formats = []

        self._fetch_obj    = FetchWorker(url)
        self._fetch_thread = QThread(self)
        self._fetch_obj.moveToThread(self._fetch_thread)
        self._fetch_thread.started.connect(self._fetch_obj.run)
        self._fetch_obj.done.connect(self._on_fetch_done)
        self._fetch_obj.error.connect(self._on_fetch_error)
        self._fetch_obj.formats.connect(self._on_formats_ready)
        self._fetch_obj.done.connect(self._fetch_thread.quit)
        self._fetch_obj.error.connect(self._fetch_thread.quit)
        self._fetch_thread.start()

    def _on_fetch_done(self, info: dict):
        self._info = info
        self._populate_playlist(info["entries"])
        kind = "Playlist" if info["is_playlist"] else "Video"
        n    = len(info["entries"])
        self.lbl_info.setText(
            f"<b>{info['title']}</b>  —  {kind}  ({n} item{'s' if n != 1 else ''})"
        )
        self.btn_fetch.setText("Fetch Info")
        self.btn_fetch.setEnabled(True)

    def _on_fetch_error(self, msg: str):
        self.lbl_info.setText(f"<span style='color:#F44336;'>Error: {msg}</span>")
        self.btn_fetch.setText("Fetch Info")
        self.btn_fetch.setEnabled(True)

    def _on_formats_ready(self, fmts: list):
        self._formats = fmts
        if self._current_fmt == "MP4":
            self._set_format("MP4")

    # ------------------------------------------------------------------
    # Output directory
    # ------------------------------------------------------------------

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Folder", self._output_dir)
        if d:
            self._output_dir = d
            self.lbl_outdir.setText(d)

    # ------------------------------------------------------------------
    # Download lifecycle
    # ------------------------------------------------------------------

    def _clear_dl_rows(self):
        while self._dl_container_lay.count():
            item = self._dl_container_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._item_rows = {}

    def _start_download(self):
        if not self._info:
            QMessageBox.warning(self, "No Video", "Please fetch a video or playlist first.")
            return
        entries = self._get_selected_entries()
        if not entries:
            QMessageBox.warning(self, "Nothing Selected", "Select at least one item.")
            return

        # Quality text — strip size hint for MP4, strip space for MP3
        quality_raw = self.cmb_quality.currentText()
        quality_text = quality_raw.split()[0]   # "1080p  (120 MB)" → "1080p" | "320 kbps" → "320"

        self._clear_dl_rows()
        self.txt_failed.clear()
        self.bar_global.setValue(0)
        self._completed_count = 0
        self._total_count     = len(entries)
        self._was_stopped     = False
        self.btn_resume.setEnabled(False)
        self.btn_resume.setVisible(False)

        for entry in entries:
            row = DownloadRow(entry["title"])
            self._dl_container_lay.addWidget(row)
            self._item_rows[entry["id"]] = row

            hist_id = hs.add_entry(
                entry["title"], entry["url"],
                self._current_fmt, quality_text,
                human_size(entry.get("filesize_approx", 0)), "Downloading",
            )
            entry["_hist_id"] = hist_id

        self._pending_entries = {e["id"]: e for e in entries}
        # Locked in for the whole batch (including any later Resume) so the
        # output filename yt-dlp computes stays identical — that's what
        # lets it recognize and continue an existing .part file instead of
        # starting the download over from zero.
        self._launch_settings = (self._output_dir, self._current_fmt, quality_text, self.spin_conc.value())

        self._launch(entries)

    def _resume_download(self):
        entries = list(self._pending_entries.values())
        if not entries or not self._launch_settings:
            return

        for entry in entries:
            row = self._item_rows.get(entry["id"])
            if row:
                row.reset_for_resume()
            hist_id = entry.get("_hist_id")
            if hist_id:
                hs.update_status(hist_id, "Downloading")

        self.txt_failed.clear()
        self.btn_resume.setEnabled(False)
        self._launch(entries)

    def _launch(self, entries):
        output_dir, fmt, quality_text, concurrency = self._launch_settings
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self._manager.start_downloads(entries, output_dir, fmt, quality_text, concurrency)

    def _cancel_download(self):
        self._was_stopped = True
        self._manager.cancel_all()
        self.btn_cancel.setEnabled(False)
        # Don't re-enable Start here — some workers may still be winding
        # down cooperatively. Starting a new batch while the old manager's
        # threads are still finishing would drop the last reference to a
        # still-running QThread, which is the same class of bug that used
        # to crash the app on Stop. btn_start/btn_resume get re-enabled in
        # _on_all_done() once the manager confirms everything actually
        # stopped.

    def _on_item_progress(self, item_id: str, pct: float, speed: str, eta: str):
        if item_id in self._item_rows:
            self._item_rows[item_id].update_progress(pct, speed, eta)

    def _on_item_done(self, item_id: str, ok: bool, reason: str, path: str):
        self._completed_count += 1
        pct = int(self._completed_count / self._total_count * 100) if self._total_count else 0
        self.bar_global.setValue(pct)

        stopped = (reason == CANCEL_REASON)

        if ok:
            self._pending_entries.pop(item_id, None)

        if item_id in self._item_rows:
            if stopped:
                self._item_rows[item_id].mark_stopped()
            else:
                self._item_rows[item_id].mark_done(ok, reason)

        for entry in (self._info["entries"] if self._info else []):
            if entry["id"] == item_id and "_hist_id" in entry:
                if ok:
                    status = "Completed"
                elif stopped:
                    status = "Stopped"
                else:
                    status = "Failed"
                hs.update_status(entry["_hist_id"], status)
                break

        if not ok and reason and not stopped:
            title = next(
                (e.get("title", item_id) for e in (self._info["entries"] if self._info else [])
                 if e["id"] == item_id),
                item_id,
            )
            self.txt_failed.append(f"✗  {title}\n   {reason}\n")

    def _on_all_done(self, completed: int, total: int, failures: list):
        self.btn_cancel.setEnabled(False)
        self.btn_start.setEnabled(True)

        can_resume = self._was_stopped and bool(self._pending_entries)
        self.btn_resume.setVisible(can_resume)
        self.btn_resume.setEnabled(can_resume)
        self._was_stopped = False

        if not can_resume:
            self.bar_global.setValue(100)
        self._load_history()

    # ------------------------------------------------------------------
    # yt-dlp self-updater
    # ------------------------------------------------------------------

    def _refresh_ytdlp_version_label(self):
        version = ytdlp_updater.get_installed_version()
        self.lbl_ytdlp_version.setText(f"yt-dlp engine: v{version}")

    def _update_ytdlp(self):
        if self._ytdlp_update_worker is not None:
            return  # a check/update is already running

        self.btn_update_ytdlp.setEnabled(False)
        self.btn_update_ytdlp.setText("Checking…")

        worker = YtDlpUpdateWorker(self)
        worker.progress.connect(self._on_ytdlp_update_progress)
        worker.finished_ok.connect(self._on_ytdlp_update_finished)
        worker.failed.connect(self._on_ytdlp_update_failed)
        # Mirrors the pattern used for downloads: only drop the reference
        # once Qt tells us the thread has actually finished, never while
        # it might still be running.
        worker.finished.connect(self._on_ytdlp_update_thread_finished)
        self._ytdlp_update_worker = worker
        worker.start()

    def _on_ytdlp_update_progress(self, downloaded: int, total: int):
        if total:
            pct = int(downloaded / total * 100)
            self.btn_update_ytdlp.setText(f"Downloading… {pct}%")
        else:
            mb = downloaded / (1024 * 1024)
            self.btn_update_ytdlp.setText(f"Downloading… {mb:.1f} MB")

    def _on_ytdlp_update_finished(self, status: str, current: str, latest: str):
        if _YTDLP_IMPORT_ERROR is not None:
            # We got here from the "engine missing" fallback screen — even
            # in the "up_to_date" case there was nothing usable before, so
            # a fresh copy was always installed.
            QMessageBox.information(
                self, "yt-dlp Installed",
                f"yt-dlp v{latest} was installed successfully.\n\n"
                "Please reopen the YouTube Downloader tool (or restart "
                "MultiTool Studio) to start using it.",
            )
        elif status == "up_to_date":
            QMessageBox.information(
                self, "yt-dlp Update",
                f"yt-dlp is already up to date (v{current}).",
            )
        else:
            QMessageBox.information(
                self, "yt-dlp Update",
                f"yt-dlp updated from v{current} to v{latest}.\n\n"
                "The new version will be used the next time MultiTool "
                "Studio is started.",
            )
        self._refresh_ytdlp_version_label()

    def _on_ytdlp_update_failed(self, message: str):
        QMessageBox.warning(self, "yt-dlp Update Failed", message)

    def _on_ytdlp_update_thread_finished(self):
        self.btn_update_ytdlp.setEnabled(True)
        self.btn_update_ytdlp.setText("Check for yt-dlp Update")
        self._ytdlp_update_worker = None

    # ------------------------------------------------------------------
    # History tab
    # ------------------------------------------------------------------

    def _load_history(self):
        filt = self.cmb_filter.currentText()
        rows = hs.get_all(filt)
        self.tbl_history.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.tbl_history.setItem(r, 0, QTableWidgetItem(row["title"] or ""))
            self.tbl_history.setItem(r, 1, QTableWidgetItem(row["format"] or ""))
            self.tbl_history.setItem(r, 2, QTableWidgetItem(row["quality"] or ""))
            self.tbl_history.setItem(r, 3, QTableWidgetItem(row["size"] or ""))

            status_item = QTableWidgetItem(row["status"] or "")
            if row["status"] == "Completed":
                status_item.setForeground(Qt.darkGreen)
            elif row["status"] == "Failed":
                status_item.setForeground(Qt.red)
            elif row["status"] == "Stopped":
                status_item.setForeground(Qt.darkYellow)
            self.tbl_history.setItem(r, 4, status_item)
            self.tbl_history.setItem(r, 5, QTableWidgetItem(row["timestamp"] or ""))

            btn = QPushButton("↺ Re-download")
            btn.setObjectName("secondary")
            url = row["url"]
            btn.clicked.connect(lambda _, u=url: self._redownload(u))
            self.tbl_history.setCellWidget(r, 6, btn)

        self.tbl_history.resizeRowsToContents()

    def _redownload(self, url: str):
        self.url_input.setText(url)
        self._fetch_info()