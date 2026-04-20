"""
Media Modernizer — convert legacy video and image formats to modern ones.

Video:  3gp, avi, mov, wmv, flv, mkv, m4v, mpg, mpeg, ts, vob, rm, rmvb  → mp4 / mkv / webm
Image:  bmp, tiff, tif, webp, ico, ppm, pgm, pbm, tga, pcx, dds           → png / jpg / webp

Video conversion uses ffmpeg (must be in PATH).
Image conversion uses Pillow (pip install Pillow).
Both run in QThread so the UI stays responsive.
"""
import os
import subprocess
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QComboBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QSplitter,
    QTextEdit, QSpinBox, QSizePolicy, QAbstractItemView
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor, QDragEnterEvent, QDropEvent

# ── Format definitions ────────────────────────────────────────────────────────

LEGACY_VIDEO_EXTS = {
    ".3gp", ".3g2", ".avi", ".mov", ".wmv", ".flv", ".f4v",
    ".mkv", ".m4v", ".mpg", ".mpeg", ".ts", ".mts", ".m2ts",
    ".vob", ".rm", ".rmvb", ".asf", ".divx", ".ogv", ".webm",
    ".dv", ".mxf",
}

LEGACY_IMAGE_EXTS = {
    ".bmp", ".tiff", ".tif", ".ico", ".ppm", ".pgm", ".pbm",
    ".tga", ".pcx", ".dds", ".xbm", ".xpm", ".sgi", ".psd",
    ".heic", ".heif", ".avif", ".jfif",
}

VIDEO_OUT_FMTS  = ["mp4", "mkv", "webm", "avi"]
IMAGE_OUT_FMTS  = ["png", "jpg", "webp", "bmp"]

VIDEO_PRESETS   = ["ultrafast", "superfast", "veryfast", "faster", "fast",
                   "medium", "slow", "slower", "veryslow"]
VIDEO_QUALITIES = ["18 (best)", "22 (good)", "26 (balanced)", "30 (smaller)", "36 (smallest)"]

STATUS_COLORS = {
    "waiting":    "#555555",
    "converting": "#FF9800",
    "done":       "#4CAF50",
    "error":      "#F44336",
    "skipped":    "#888888",
}


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _pillow_available() -> bool:
    try:
        import PIL
        return True
    except ImportError:
        return False


# ── Worker threads ────────────────────────────────────────────────────────────

class _VideoWorker(QThread):
    file_started  = Signal(int)           # row index
    file_done     = Signal(int, bool, str)  # row, ok, message
    log_line      = Signal(str)
    overall       = Signal(int)           # 0–100

    def __init__(self, jobs: list[dict]):
        super().__init__()
        # jobs: [{row, src, dst, crf, preset, delete_orig}]
        self._jobs   = jobs
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        total = len(self._jobs)
        for i, job in enumerate(self._jobs):
            if self._cancel:
                break
            self.file_started.emit(job["row"])
            src, dst = job["src"], job["dst"]
            crf     = job.get("crf", 22)
            preset  = job.get("preset", "medium")

            cmd = [
                "ffmpeg", "-y", "-i", src,
                "-c:v", "libx264",
                "-crf", str(crf),
                "-preset", preset,
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                dst
            ]
            # webm needs different codec
            if dst.endswith(".webm"):
                cmd = [
                    "ffmpeg", "-y", "-i", src,
                    "-c:v", "libvpx-vp9",
                    "-crf", str(crf),
                    "-b:v", "0",
                    "-c:a", "libopus",
                    dst
                ]
            elif dst.endswith(".mkv"):
                cmd = [
                    "ffmpeg", "-y", "-i", src,
                    "-c:v", "libx264",
                    "-crf", str(crf),
                    "-preset", preset,
                    "-c:a", "aac",
                    dst
                ]

            self.log_line.emit(f"▶ {os.path.basename(src)}")
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=3600
                )
                if result.returncode == 0:
                    if job.get("delete_orig"):
                        os.remove(src)
                    size = os.path.getsize(dst) / 1024 / 1024
                    self.file_done.emit(job["row"], True, f"✅ {size:.1f} MB")
                    self.log_line.emit(f"  ✅ → {os.path.basename(dst)} ({size:.1f} MB)")
                else:
                    err = result.stderr[-300:] if result.stderr else "Unknown error"
                    self.file_done.emit(job["row"], False, "❌ ffmpeg error")
                    self.log_line.emit(f"  ❌ {err}")
            except subprocess.TimeoutExpired:
                self.file_done.emit(job["row"], False, "❌ Timeout")
                self.log_line.emit("  ❌ Timeout")
            except Exception as e:
                self.file_done.emit(job["row"], False, f"❌ {e}")
                self.log_line.emit(f"  ❌ {e}")

            self.overall.emit(int((i + 1) / total * 100))


class _ImageWorker(QThread):
    file_started = Signal(int)
    file_done    = Signal(int, bool, str)
    log_line     = Signal(str)
    overall      = Signal(int)

    def __init__(self, jobs: list[dict]):
        super().__init__()
        self._jobs   = jobs
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            from PIL import Image
        except ImportError:
            for job in self._jobs:
                self.file_done.emit(job["row"], False, "❌ Pillow not installed")
            return

        total = len(self._jobs)
        for i, job in enumerate(self._jobs):
            if self._cancel:
                break
            self.file_started.emit(job["row"])
            src, dst = job["src"], job["dst"]
            quality = job.get("quality", 90)
            self.log_line.emit(f"▶ {os.path.basename(src)}")
            try:
                img = Image.open(src)
                # Handle RGBA → RGB for jpg
                if dst.lower().endswith((".jpg", ".jpeg")) and img.mode in ("RGBA", "P", "LA"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                    img = bg
                save_kw = {}
                if dst.lower().endswith((".jpg", ".jpeg")):
                    save_kw["quality"] = quality
                    save_kw["optimize"] = True
                elif dst.lower().endswith(".webp"):
                    save_kw["quality"] = quality
                img.save(dst, **save_kw)
                if job.get("delete_orig"):
                    os.remove(src)
                size_kb = os.path.getsize(dst) / 1024
                self.file_done.emit(job["row"], True,
                                    f"✅ {size_kb:.0f} KB")
                self.log_line.emit(f"  ✅ → {os.path.basename(dst)}")
            except Exception as e:
                self.file_done.emit(job["row"], False, f"❌ {e}")
                self.log_line.emit(f"  ❌ {e}")
            self.overall.emit(int((i + 1) / total * 100))


# ── Main tool ─────────────────────────────────────────────────────────────────

class MediaModernizerTool(QWidget):
    name        = "Media Modernizer"
    description = "Convert legacy video/image formats to modern mp4 or png"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker  = None
        self._rows    = []   # [{path, type, row_idx}]
        self._build_ui()
        self._check_deps()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 14, 24, 14)
        t = QLabel("🎬 Media Modernizer")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        self._dep_lbl = QLabel("")
        self._dep_lbl.setStyleSheet("color:#888; font-size:11px;")
        hl.addWidget(self._dep_lbl)
        root.addWidget(hdr)

        # Body splitter: left controls | right log
        body_splitter = QSplitter(Qt.Horizontal)
        body_splitter.setHandleWidth(2)
        body_splitter.setStyleSheet("QSplitter::handle{background:#2A2A2A;}")

        # ── LEFT ──────────────────────────────────────────────────────────────
        left = QWidget()
        left.setStyleSheet("background:#151515;")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(20, 16, 12, 16)
        ll.setSpacing(12)

        # Add files / folder buttons
        add_row = QHBoxLayout()
        add_files_btn = QPushButton("➕  Add Files…")
        add_files_btn.setStyleSheet(self._btn_style("#00BFA5", "#000"))
        add_files_btn.clicked.connect(self._add_files)
        add_row.addWidget(add_files_btn)

        add_folder_btn = QPushButton("📂  Add Folder…")
        add_folder_btn.setStyleSheet(self._btn_style("#2196F3", "#fff"))
        add_folder_btn.clicked.connect(self._add_folder)
        add_row.addWidget(add_folder_btn)

        clear_btn = QPushButton("🗑  Clear All")
        clear_btn.setStyleSheet(self._btn_style("#3A3A3A", "#E0E0E0"))
        clear_btn.clicked.connect(self._clear)
        add_row.addWidget(clear_btn)
        add_row.addStretch()
        ll.addLayout(add_row)

        # Drop hint
        drop_lbl = QLabel("💡  Drag & drop files or folders here")
        drop_lbl.setStyleSheet("color:#444; font-size:11px;")
        ll.addWidget(drop_lbl)

        # Queue table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Type", "Filename", "Size", "Output", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 55)
        self._table.setColumnWidth(2, 70)
        self._table.setColumnWidth(4, 110)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet("""
            QTableWidget { background:#1A1A1A; border:none; font-size:12px; }
            QHeaderView::section { background:#252525; color:#888;
                                   border:none; padding:5px; }
            QTableWidget::item { padding:3px 6px; }
        """)
        self.setAcceptDrops(True)
        ll.addWidget(self._table, 1)

        # Options
        opts_frame = QFrame()
        opts_frame.setStyleSheet(
            "QFrame{background:#1E1E1E;border-radius:8px;border:1px solid #2A2A2A;}"
            "QLabel{border:none;background:transparent;color:#888;font-size:12px;}")
        ofl = QVBoxLayout(opts_frame)
        ofl.setContentsMargins(14, 12, 14, 12)
        ofl.setSpacing(10)

        # Video options
        vid_row = QHBoxLayout()
        vid_row.addWidget(QLabel("Video out:"))
        self._vid_fmt = QComboBox()
        self._vid_fmt.addItems([f.upper() for f in VIDEO_OUT_FMTS])
        self._vid_fmt.setFixedWidth(80)
        self._vid_fmt.setStyleSheet(self._combo_style())
        vid_row.addWidget(self._vid_fmt)

        vid_row.addWidget(QLabel("  Quality (CRF):"))
        self._crf_cb = QComboBox()
        self._crf_cb.addItems(VIDEO_QUALITIES)
        self._crf_cb.setCurrentIndex(1)
        self._crf_cb.setFixedWidth(140)
        self._crf_cb.setStyleSheet(self._combo_style())
        vid_row.addWidget(self._crf_cb)

        vid_row.addWidget(QLabel("  Preset:"))
        self._preset_cb = QComboBox()
        self._preset_cb.addItems(VIDEO_PRESETS)
        self._preset_cb.setCurrentIndex(5)  # medium
        self._preset_cb.setFixedWidth(110)
        self._preset_cb.setStyleSheet(self._combo_style())
        vid_row.addWidget(self._preset_cb)
        vid_row.addStretch()
        ofl.addLayout(vid_row)

        # Image options
        img_row = QHBoxLayout()
        img_row.addWidget(QLabel("Image out:"))
        self._img_fmt = QComboBox()
        self._img_fmt.addItems([f.upper() for f in IMAGE_OUT_FMTS])
        self._img_fmt.setFixedWidth(80)
        self._img_fmt.setStyleSheet(self._combo_style())
        img_row.addWidget(self._img_fmt)

        img_row.addWidget(QLabel("  JPEG/WebP quality:"))
        self._quality_spin = QSpinBox()
        self._quality_spin.setRange(1, 100)
        self._quality_spin.setValue(90)
        self._quality_spin.setFixedWidth(60)
        self._quality_spin.setStyleSheet(
            "background:#252525;border:1px solid #3E3E3E;border-radius:4px;"
            "padding:4px;color:#E0E0E0;")
        img_row.addWidget(self._quality_spin)
        img_row.addStretch()
        ofl.addLayout(img_row)

        # Output & behaviour
        out_row = QHBoxLayout()
        self._same_folder_chk = QCheckBox("Save next to original")
        self._same_folder_chk.setChecked(True)
        self._same_folder_chk.setStyleSheet("color:#888; font-size:12px;")
        self._same_folder_chk.toggled.connect(self._on_same_folder_toggle)
        out_row.addWidget(self._same_folder_chk)

        self._out_folder_btn = QPushButton("📁 Choose output folder…")
        self._out_folder_btn.setEnabled(False)
        self._out_folder_btn.setStyleSheet(self._btn_style("#252525", "#888"))
        self._out_folder_btn.clicked.connect(self._pick_out_folder)
        out_row.addWidget(self._out_folder_btn)
        self._out_folder_lbl = QLabel("")
        self._out_folder_lbl.setStyleSheet("color:#555; font-size:11px;")
        out_row.addWidget(self._out_folder_lbl)
        out_row.addStretch()
        ofl.addLayout(out_row)

        chk_row = QHBoxLayout()
        self._delete_chk = QCheckBox("Delete original after successful conversion")
        self._delete_chk.setStyleSheet("color:#F44336; font-size:12px;")
        chk_row.addWidget(self._delete_chk)

        self._skip_modern_chk = QCheckBox("Skip if output already exists")
        self._skip_modern_chk.setChecked(True)
        self._skip_modern_chk.setStyleSheet("color:#888; font-size:12px;")
        chk_row.addWidget(self._skip_modern_chk)
        chk_row.addStretch()
        ofl.addLayout(chk_row)

        ll.addWidget(opts_frame)

        # Progress
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(8)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet("""
            QProgressBar { background:#252525; border-radius:4px; border:none; }
            QProgressBar::chunk { background:#00BFA5; border-radius:4px; }
        """)
        self._progress.hide()
        ll.addWidget(self._progress)

        # Action buttons
        act_row = QHBoxLayout()
        self._convert_btn = QPushButton("🚀  Convert All")
        self._convert_btn.setFixedHeight(42)
        self._convert_btn.setEnabled(False)
        self._convert_btn.setStyleSheet(self._btn_style("#00BFA5", "#000", big=True))
        self._convert_btn.clicked.connect(self._start_conversion)
        act_row.addWidget(self._convert_btn)

        self._cancel_btn = QPushButton("⏹  Cancel")
        self._cancel_btn.setFixedHeight(42)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setStyleSheet(self._btn_style("#F44336", "#fff", big=True))
        self._cancel_btn.clicked.connect(self._cancel)
        act_row.addWidget(self._cancel_btn)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color:#888; font-size:12px;")
        act_row.addWidget(self._status_lbl)
        act_row.addStretch()
        ll.addLayout(act_row)

        body_splitter.addWidget(left)

        # ── RIGHT: log ────────────────────────────────────────────────────────
        right = QWidget()
        right.setStyleSheet("background:#0D0D0D;")
        right.setMaximumWidth(340)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 16, 16, 16)
        rl.setSpacing(6)

        log_title = QLabel("📋 Conversion Log")
        log_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        log_title.setStyleSheet("color:#555;")
        rl.addWidget(log_title)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            "background:#0D0D0D; border:none; color:#666;"
            "font-family:'Consolas','Courier New'; font-size:11px;")
        rl.addWidget(self._log, 1)

        clr_log_btn = QPushButton("Clear log")
        clr_log_btn.setStyleSheet(self._btn_style("#1A1A1A", "#555"))
        clr_log_btn.clicked.connect(self._log.clear)
        rl.addWidget(clr_log_btn)

        body_splitter.addWidget(right)
        body_splitter.setSizes([800, 320])

        root.addWidget(body_splitter, 1)

        self._out_folder = ""

    # ── Style helpers ─────────────────────────────────────────────────────────
    def _btn_style(self, bg, fg, big=False):
        h = "42px" if big else "34px"
        return (f"background:{bg};color:{fg};border:none;border-radius:6px;"
                f"font-weight:bold;padding:0 14px;min-height:{h};")

    def _combo_style(self):
        return ("background:#252525;border:1px solid #3E3E3E;border-radius:6px;"
                "padding:4px 8px;color:#E0E0E0;")

    # ── Dependency check ──────────────────────────────────────────────────────
    def _check_deps(self):
        parts = []
        if _ffmpeg_available():
            parts.append("✅ ffmpeg")
        else:
            parts.append("❌ ffmpeg (not in PATH — video conversion disabled)")
        if _pillow_available():
            parts.append("✅ Pillow")
        else:
            parts.append("❌ Pillow (pip install Pillow)")
        self._dep_lbl.setText("  |  ".join(parts))

    # ── File handling ─────────────────────────────────────────────────────────
    def _add_files(self):
        all_exts = " ".join(
            f"*{e}" for e in sorted(LEGACY_VIDEO_EXTS | LEGACY_IMAGE_EXTS)
        )
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select legacy media files", "",
            f"Legacy Media ({all_exts});;All Files (*.*)"
        )
        for p in paths:
            self._add_path(p)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select folder")
        if not folder:
            return
        count = 0
        for root_dir, _, files in os.walk(folder):
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in LEGACY_VIDEO_EXTS or ext in LEGACY_IMAGE_EXTS:
                    self._add_path(os.path.join(root_dir, f))
                    count += 1
        self._status_lbl.setText(f"Added {count} file(s) from folder")

    def _add_path(self, path: str):
        ext = Path(path).suffix.lower()
        if ext not in LEGACY_VIDEO_EXTS and ext not in LEGACY_IMAGE_EXTS:
            return
        # Avoid duplicates
        existing = [r["path"] for r in self._rows]
        if path in existing:
            return

        mtype = "🎬 Video" if ext in LEGACY_VIDEO_EXTS else "🖼 Image"
        row = self._table.rowCount()
        self._table.insertRow(row)

        try:
            size_mb = os.path.getsize(path) / 1024 / 1024
            size_str = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{os.path.getsize(path)//1024} KB"
        except Exception:
            size_str = "?"

        out_ext = self._vid_fmt.currentText().lower() if ext in LEGACY_VIDEO_EXTS \
                  else self._img_fmt.currentText().lower()
        out_name = Path(path).stem + "." + out_ext

        self._table.setItem(row, 0, QTableWidgetItem(mtype))
        self._table.setItem(row, 1, QTableWidgetItem(os.path.basename(path)))
        self._table.setItem(row, 2, QTableWidgetItem(size_str))
        self._table.setItem(row, 3, QTableWidgetItem(out_name))
        status_item = QTableWidgetItem("waiting")
        status_item.setForeground(QColor(STATUS_COLORS["waiting"]))
        self._table.setItem(row, 4, status_item)

        self._rows.append({"path": path, "ext": ext, "row": row,
                           "type": "video" if ext in LEGACY_VIDEO_EXTS else "image"})
        self._convert_btn.setEnabled(True)

    def _clear(self):
        self._table.setRowCount(0)
        self._rows.clear()
        self._convert_btn.setEnabled(False)
        self._status_lbl.setText("")

    # ── Drag and drop ─────────────────────────────────────────────────────────
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                for root_dir, _, files in os.walk(path):
                    for f in files:
                        self._add_path(os.path.join(root_dir, f))
            else:
                self._add_path(path)

    # ── Options ───────────────────────────────────────────────────────────────
    def _on_same_folder_toggle(self, checked):
        self._out_folder_btn.setEnabled(not checked)
        if checked:
            self._out_folder = ""
            self._out_folder_lbl.setText("")

    def _pick_out_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Output folder")
        if folder:
            self._out_folder = folder
            self._out_folder_lbl.setText(folder[:50] + "…" if len(folder) > 50 else folder)

    def _get_crf(self) -> int:
        return int(self._crf_cb.currentText().split()[0])

    def _dst_path(self, row: dict) -> str:
        src = row["path"]
        if row["type"] == "video":
            out_ext = self._vid_fmt.currentText().lower()
        else:
            out_ext = self._img_fmt.currentText().lower()
        new_name = Path(src).stem + "." + out_ext
        if self._out_folder:
            return os.path.join(self._out_folder, new_name)
        return os.path.join(os.path.dirname(src), new_name)

    # ── Conversion ────────────────────────────────────────────────────────────
    def _start_conversion(self):
        if not self._rows:
            return

        video_jobs = []
        image_jobs = []
        skip_count = 0

        for row in self._rows:
            dst = self._dst_path(row)
            if self._skip_modern_chk.isChecked() and os.path.exists(dst):
                self._set_status(row["row"], "skipped", "⏭ Exists")
                skip_count += 1
                continue
            job = {
                "row":         row["row"],
                "src":         row["path"],
                "dst":         dst,
                "delete_orig": self._delete_chk.isChecked(),
                "crf":         self._get_crf(),
                "preset":      self._preset_cb.currentText(),
                "quality":     self._quality_spin.value(),
            }
            # Also update output column with real path
            self._table.item(row["row"], 3).setText(os.path.basename(dst))

            if row["type"] == "video":
                if not _ffmpeg_available():
                    self._set_status(row["row"], "error", "❌ No ffmpeg")
                    continue
                video_jobs.append(job)
            else:
                if not _pillow_available():
                    self._set_status(row["row"], "error", "❌ No Pillow")
                    continue
                image_jobs.append(job)

        all_jobs = image_jobs + video_jobs   # images first (fast)
        if not all_jobs:
            self._status_lbl.setText(f"Nothing to convert ({skip_count} skipped)")
            return

        self._convert_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._progress.setValue(0)
        self._progress.show()
        self._log.clear()
        self._status_lbl.setText(f"Converting {len(all_jobs)} file(s)…")

        # Run images inline if only images, else run both via combined approach
        if image_jobs and not video_jobs:
            self._worker = _ImageWorker(image_jobs)
        elif video_jobs and not image_jobs:
            self._worker = _VideoWorker(video_jobs)
        else:
            # Run images first, then chain video
            self._worker = _ImageWorker(image_jobs)
            self._pending_video_jobs = video_jobs
        
        self._worker.file_started.connect(lambda r: self._set_status(r, "converting", "⚙ Converting…"))
        self._worker.file_done.connect(self._on_file_done)
        self._worker.log_line.connect(self._log.append)
        self._worker.overall.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_batch_done)
        self._worker.start()

    def _on_file_done(self, row: int, ok: bool, msg: str):
        self._set_status(row, "done" if ok else "error", msg)

    def _on_batch_done(self):
        # If we had pending video jobs after image batch
        if hasattr(self, "_pending_video_jobs") and self._pending_video_jobs:
            jobs = self._pending_video_jobs
            self._pending_video_jobs = []
            self._worker = _VideoWorker(jobs)
            self._worker.file_started.connect(lambda r: self._set_status(r, "converting", "⚙ Converting…"))
            self._worker.file_done.connect(self._on_file_done)
            self._worker.log_line.connect(self._log.append)
            self._worker.overall.connect(self._progress.setValue)
            self._worker.finished.connect(self._on_all_done)
            self._worker.start()
        else:
            self._on_all_done()

    def _on_all_done(self):
        self._progress.hide()
        self._convert_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        done  = sum(1 for r in range(self._table.rowCount())
                    if self._table.item(r, 4) and "✅" in self._table.item(r, 4).text())
        errs  = sum(1 for r in range(self._table.rowCount())
                    if self._table.item(r, 4) and "❌" in self._table.item(r, 4).text())
        self._status_lbl.setText(
            f"✅ {done} converted" + (f"  ❌ {errs} error(s)" if errs else ""))
        self._log.append(f"\n--- Done: {done} ok, {errs} errors ---")

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
        self._cancel_btn.setEnabled(False)
        self._status_lbl.setText("Cancelling…")

    def _set_status(self, row: int, state: str, text: str):
        item = self._table.item(row, 4)
        if item:
            item.setText(text)
            item.setForeground(QColor(STATUS_COLORS.get(state, "#888")))
