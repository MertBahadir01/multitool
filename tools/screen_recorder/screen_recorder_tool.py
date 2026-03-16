"""
Screen Recorder & GIF Maker
— Record a screen region or full screen using ffmpeg (must be installed)
— Trim recorded clips
— Convert/export as MP4 or animated GIF
— Annotate with a note (saved alongside file)
"""

import os
import subprocess
import sys
import datetime
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QComboBox, QListWidget, QListWidgetItem,
    QFrame, QTabWidget, QTextEdit, QFileDialog, QMessageBox,
    QProgressBar, QCheckBox, QSplitter
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QProcess
from PySide6.QtGui import QFont, QColor


def _ffmpeg_available():
    return shutil.which("ffmpeg") is not None


def _ffprobe_duration(path: str) -> float:
    """Return video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


class RecordWorker(QThread):
    stopped = Signal(str)    # output path

    def __init__(self, output_path, fps, region, audio):
        super().__init__()
        self.output_path = output_path
        self.fps = fps
        self.region = region      # None or (x,y,w,h)
        self.audio = audio
        self._proc = None

    def run(self):
        cmd = ["ffmpeg", "-y"]
        if sys.platform == "win32":
            cmd += ["-f", "gdigrab", "-framerate", str(self.fps)]
            if self.region:
                x, y, w, h = self.region
                cmd += ["-offset_x", str(x), "-offset_y", str(y),
                        "-video_size", f"{w}x{h}"]
            cmd += ["-i", "desktop"]
            if self.audio:
                cmd += ["-f", "dshow", "-i", "audio=virtual-audio-capturer"]
        elif sys.platform == "darwin":
            cmd += ["-f", "avfoundation", "-framerate", str(self.fps)]
            if self.region:
                x, y, w, h = self.region
                cmd += ["-filter:v", f"crop={w}:{h}:{x}:{y}"]
            cmd += ["-i", "1:0" if self.audio else "1:none"]
        else:
            # Linux — use x11grab
            display = os.environ.get("DISPLAY", ":0")
            cmd += ["-f", "x11grab", "-framerate", str(self.fps)]
            if self.region:
                x, y, w, h = self.region
                cmd += ["-video_size", f"{w}x{h}", "-i", f"{display}+{x},{y}"]
            else:
                cmd += ["-i", display]
            if self.audio:
                cmd += ["-f", "pulse", "-i", "default"]
        cmd += ["-c:v", "libx264", "-preset", "ultrafast", self.output_path]
        try:
            self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                          stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL)
            self._proc.wait()
        except Exception:
            pass
        self.stopped.emit(self.output_path)

    def stop(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.communicate(input=b"q", timeout=5)
            except Exception:
                self._proc.kill()


class ConvertWorker(QThread):
    done = Signal(bool, str)   # success, message

    def __init__(self, input_path, output_path, start, end, as_gif, fps, scale):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.start = start
        self.end = end
        self.as_gif = as_gif
        self.fps = fps
        self.scale = scale

    def run(self):
        try:
            cmd = ["ffmpeg", "-y"]
            if self.start > 0:
                cmd += ["-ss", str(self.start)]
            cmd += ["-i", self.input_path]
            if self.end > 0:
                duration = self.end - self.start
                cmd += ["-t", str(max(1, duration))]
            if self.as_gif:
                # two-pass palette GIF
                palette = self.output_path + "_palette.png"
                vf = f"fps={self.fps},scale={self.scale}:-1:flags=lanczos"
                subprocess.run(
                    ["ffmpeg", "-y", "-i", self.input_path,
                     "-vf", vf + ",palettegen", palette],
                    capture_output=True
                )
                cmd += ["-vf", vf + f",paletteuse",
                        "-lavfi", vf + f" [x]; [x][1:v] paletteuse"]
                # simpler single pass
                cmd = ["ffmpeg", "-y"]
                if self.start > 0:
                    cmd += ["-ss", str(self.start)]
                cmd += ["-i", self.input_path]
                if self.end > 0:
                    cmd += ["-t", str(max(1, self.end - self.start))]
                cmd += ["-vf", f"fps={self.fps},scale={self.scale}:-1:flags=lanczos",
                        self.output_path]
            else:
                cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "23", self.output_path]
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            if result.returncode == 0:
                self.done.emit(True, self.output_path)
            else:
                self.done.emit(False, result.stderr.decode()[-400:])
        except Exception as e:
            self.done.emit(False, str(e))


class ScreenRecorderTool(QWidget):
    name = "Screen Recorder"
    description = "Record screen, trim clips, export as MP4 or GIF"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recordings = []   # list of file paths
        self._worker = None
        self._record_timer = QTimer(self)
        self._record_timer.timeout.connect(self._update_record_time)
        self._record_seconds = 0
        self._output_dir = str(Path.home() / "MultiTool_Recordings")
        os.makedirs(self._output_dir, exist_ok=True)
        self._build_ui()
        self._scan_recordings()

        if not _ffmpeg_available():
            self._show_ffmpeg_warning()

    def _show_ffmpeg_warning(self):
        self._status_lbl.setText("⚠️ ffmpeg not found. Install ffmpeg to enable recording.")
        self._status_lbl.setStyleSheet("color:#F44336; font-size:13px; padding:8px;")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("🎬 Screen Recorder & GIF Maker")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        root.addWidget(hdr)

        tabs = QTabWidget()

        # ── Record tab ─────────────────────────────────────────────────────────
        rec_tab = QWidget()
        rl = QVBoxLayout(rec_tab)
        rl.setContentsMargins(24, 20, 24, 20)
        rl.setSpacing(14)

        self._status_lbl = QLabel("Ready to record")
        self._status_lbl.setStyleSheet("color:#888; font-size:13px;")
        rl.addWidget(self._status_lbl)

        settings_frame = QFrame()
        settings_frame.setStyleSheet("background:#252525; border-radius:10px; padding:4px;")
        sf = QVBoxLayout(settings_frame)
        sf.setContentsMargins(16, 12, 16, 12)
        sf.setSpacing(10)

        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("FPS:"))
        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(5, 60)
        self._fps_spin.setValue(30)
        fps_row.addWidget(self._fps_spin)
        fps_row.addSpacing(20)
        fps_row.addWidget(QLabel("Output folder:"))
        self._out_dir_lbl = QLabel(self._output_dir)
        self._out_dir_lbl.setStyleSheet("color:#888; font-size:11px;")
        fps_row.addWidget(self._out_dir_lbl, 1)
        out_btn = QPushButton("📁")
        out_btn.setFixedWidth(32)
        out_btn.clicked.connect(self._choose_output_dir)
        fps_row.addWidget(out_btn)
        sf.addLayout(fps_row)

        self._audio_check = QCheckBox("Record audio (if supported)")
        sf.addWidget(self._audio_check)

        region_row = QHBoxLayout()
        region_row.addWidget(QLabel("Region (leave blank for full screen):"))
        self._rx = QSpinBox(); self._rx.setRange(0, 9999); self._rx.setPrefix("X:")
        self._ry = QSpinBox(); self._ry.setRange(0, 9999); self._ry.setPrefix("Y:")
        self._rw = QSpinBox(); self._rw.setRange(0, 9999); self._rw.setPrefix("W:")
        self._rh = QSpinBox(); self._rh.setRange(0, 9999); self._rh.setPrefix("H:")
        for s in (self._rx, self._ry, self._rw, self._rh):
            s.setFixedWidth(90)
            region_row.addWidget(s)
        sf.addLayout(region_row)
        rl.addWidget(settings_frame)

        self._timer_lbl = QLabel("00:00")
        self._timer_lbl.setFont(QFont("Courier New", 36, QFont.Bold))
        self._timer_lbl.setAlignment(Qt.AlignCenter)
        self._timer_lbl.setStyleSheet("color:#00BFA5;")
        rl.addWidget(self._timer_lbl)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        self._rec_btn = QPushButton("⏺  Start Recording")
        self._rec_btn.setFixedSize(180, 48)
        self._rec_btn.setStyleSheet("QPushButton{background:#F44336;color:#fff;border-radius:10px;font-size:16px;font-weight:bold;border:none;}"
                                     "QPushButton:hover{background:#E53935;}")
        self._rec_btn.clicked.connect(self._toggle_record)
        btn_row.addWidget(self._rec_btn)
        rl.addLayout(btn_row)
        rl.addStretch()
        tabs.addTab(rec_tab, "⏺ Record")

        # ── Library tab ────────────────────────────────────────────────────────
        lib_tab = QWidget()
        ll = QVBoxLayout(lib_tab)
        ll.setContentsMargins(12, 12, 12, 12)
        ll.setSpacing(8)

        lib_hdr = QHBoxLayout()
        lib_hdr.addWidget(QLabel("Saved recordings:"))
        lib_hdr.addStretch()
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._scan_recordings)
        lib_hdr.addWidget(refresh_btn)
        open_dir_btn = QPushButton("📁 Open Folder")
        open_dir_btn.clicked.connect(self._open_output_dir)
        lib_hdr.addWidget(open_dir_btn)
        ll.addLayout(lib_hdr)

        self._rec_list = QListWidget()
        self._rec_list.setStyleSheet("background:#252525; border-radius:8px; font-size:13px;")
        ll.addWidget(self._rec_list, 1)

        del_rec_btn = QPushButton("🗑️ Delete Selected")
        del_rec_btn.setObjectName("secondary")
        del_rec_btn.clicked.connect(self._delete_recording)
        ll.addWidget(del_rec_btn)
        tabs.addTab(lib_tab, "📂 Library")

        # ── Convert/GIF tab ────────────────────────────────────────────────────
        conv_tab = QWidget()
        cl = QVBoxLayout(conv_tab)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(12)

        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("Source file:"))
        self._src_edit = QLineEdit()
        self._src_edit.setPlaceholderText("Path to video file…")
        src_row.addWidget(self._src_edit, 1)
        browse_btn = QPushButton("📁")
        browse_btn.clicked.connect(self._browse_source)
        src_row.addWidget(browse_btn)
        cl.addLayout(src_row)

        trim_row = QHBoxLayout()
        trim_row.addWidget(QLabel("Trim — Start (s):"))
        self._trim_start = QSpinBox(); self._trim_start.setRange(0, 9999)
        trim_row.addWidget(self._trim_start)
        trim_row.addWidget(QLabel("End (s, 0=end):"))
        self._trim_end = QSpinBox(); self._trim_end.setRange(0, 9999)
        trim_row.addWidget(self._trim_end)
        trim_row.addStretch()
        cl.addLayout(trim_row)

        gif_row = QHBoxLayout()
        self._gif_check = QCheckBox("Export as animated GIF")
        gif_row.addWidget(self._gif_check)
        gif_row.addWidget(QLabel("  GIF FPS:"))
        self._gif_fps = QSpinBox(); self._gif_fps.setRange(5, 30); self._gif_fps.setValue(15)
        gif_row.addWidget(self._gif_fps)
        gif_row.addWidget(QLabel("  Width (px):"))
        self._gif_scale = QSpinBox(); self._gif_scale.setRange(100, 1920); self._gif_scale.setValue(480)
        gif_row.addWidget(self._gif_scale)
        gif_row.addStretch()
        cl.addLayout(gif_row)

        self._note_edit = QTextEdit()
        self._note_edit.setPlaceholderText("Annotation / description (saved as .txt alongside output)…")
        self._note_edit.setMaximumHeight(80)
        cl.addWidget(self._note_edit)

        self._conv_progress = QProgressBar()
        self._conv_progress.setRange(0, 0)
        self._conv_progress.hide()
        cl.addWidget(self._conv_progress)

        self._conv_status = QLabel("")
        self._conv_status.setStyleSheet("color:#888;")
        cl.addWidget(self._conv_status)

        conv_btn = QPushButton("⚙️  Convert / Export")
        conv_btn.setFixedHeight(44)
        conv_btn.clicked.connect(self._convert)
        cl.addWidget(conv_btn)
        cl.addStretch()
        tabs.addTab(conv_tab, "🎞️ Convert / GIF")

        root.addWidget(tabs, 1)

    # ── recording ──────────────────────────────────────────────────────────────
    def _toggle_record(self):
        if self._worker and self._worker.isRunning():
            self._stop_record()
        else:
            self._start_record()

    def _start_record(self):
        if not _ffmpeg_available():
            QMessageBox.warning(self, "ffmpeg missing",
                                "Install ffmpeg and ensure it's in your PATH.")
            return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(self._output_dir, f"recording_{ts}.mp4")
        rw, rh = self._rw.value(), self._rh.value()
        region = (self._rx.value(), self._ry.value(), rw, rh) if rw > 0 and rh > 0 else None
        self._worker = RecordWorker(out, self._fps_spin.value(), region, self._audio_check.isChecked())
        self._worker.stopped.connect(self._on_record_done)
        self._worker.start()
        self._record_seconds = 0
        self._record_timer.start(1000)
        self._rec_btn.setText("⏹  Stop Recording")
        self._rec_btn.setStyleSheet("QPushButton{background:#555;color:#fff;border-radius:10px;font-size:16px;font-weight:bold;border:none;}")
        self._status_lbl.setText(f"🔴 Recording → {out}")
        self._status_lbl.setStyleSheet("color:#F44336; font-size:13px;")

    def _stop_record(self):
        self._record_timer.stop()
        if self._worker:
            self._worker.stop()

    def _on_record_done(self, path):
        self._record_timer.stop()
        self._rec_btn.setText("⏺  Start Recording")
        self._rec_btn.setStyleSheet("QPushButton{background:#F44336;color:#fff;border-radius:10px;font-size:16px;font-weight:bold;border:none;}"
                                     "QPushButton:hover{background:#E53935;}")
        self._status_lbl.setText(f"✅ Saved: {path}")
        self._status_lbl.setStyleSheet("color:#00BFA5; font-size:13px;")
        self._scan_recordings()

    def _update_record_time(self):
        self._record_seconds += 1
        m, s = divmod(self._record_seconds, 60)
        self._timer_lbl.setText(f"{m:02d}:{s:02d}")

    # ── library ────────────────────────────────────────────────────────────────
    def _scan_recordings(self):
        self._rec_list.clear()
        self._recordings = []
        try:
            for fn in sorted(os.listdir(self._output_dir), reverse=True):
                if fn.endswith((".mp4", ".mkv", ".avi", ".gif")):
                    path = os.path.join(self._output_dir, fn)
                    sz = _fmt_size(os.path.getsize(path))
                    icon = "🎞️" if fn.endswith(".gif") else "🎬"
                    item = QListWidgetItem(f"  {icon}  {fn}   ({sz})")
                    item.setData(Qt.UserRole, path)
                    self._rec_list.addItem(item)
                    self._recordings.append(path)
        except Exception:
            pass

    def _delete_recording(self):
        item = self._rec_list.currentItem()
        if not item:
            return
        path = item.data(Qt.UserRole)
        if QMessageBox.question(self, "Delete", f"Delete {os.path.basename(path)}?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                os.remove(path)
            except Exception:
                pass
            self._scan_recordings()

    def _choose_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Output folder", self._output_dir)
        if d:
            self._output_dir = d
            self._out_dir_lbl.setText(d)
            os.makedirs(d, exist_ok=True)

    def _open_output_dir(self):
        import subprocess, sys
        try:
            if sys.platform == "win32":
                os.startfile(self._output_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self._output_dir])
            else:
                subprocess.Popen(["xdg-open", self._output_dir])
        except Exception:
            pass

    # ── convert ────────────────────────────────────────────────────────────────
    def _browse_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Video",
                                              self._output_dir,
                                              "Video (*.mp4 *.mkv *.avi *.mov *.webm)")
        if path:
            self._src_edit.setText(path)

    def _convert(self):
        src = self._src_edit.text().strip()
        if not src or not os.path.isfile(src):
            QMessageBox.warning(self, "No File", "Select a valid source file.")
            return
        as_gif = self._gif_check.isChecked()
        ext = ".gif" if as_gif else ".mp4"
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(self._output_dir, f"export_{ts}{ext}")
        note = self._note_edit.toPlainText().strip()
        if note:
            with open(out.replace(ext, ".txt"), "w", encoding="utf-8") as f:
                f.write(note)
        self._conv_progress.show()
        self._conv_status.setText("Converting…")
        worker = ConvertWorker(src, out,
                               self._trim_start.value(), self._trim_end.value(),
                               as_gif, self._gif_fps.value(), self._gif_scale.value())
        worker.done.connect(self._on_convert_done)
        worker.start()
        self._conv_worker = worker   # keep reference

    def _on_convert_done(self, success, msg):
        self._conv_progress.hide()
        if success:
            self._conv_status.setText(f"✅ Exported: {msg}")
            self._conv_status.setStyleSheet("color:#00BFA5;")
            self._scan_recordings()
        else:
            self._conv_status.setText(f"❌ Error: {msg[:200]}")
            self._conv_status.setStyleSheet("color:#F44336;")


def _fmt_size(b):
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"
