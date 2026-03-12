import os, subprocess
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QListWidget, QSpinBox, QGroupBox, QProgressBar, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont


class ConvertWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(int, int)

    def __init__(self, files, out_dir, quality):
        super().__init__()
        self.files = files
        self.out_dir = out_dir
        self.quality = quality

    def run(self):
        done = 0
        for i, f in enumerate(self.files):
            self.progress.emit(i + 1, len(self.files))
            try:
                base = os.path.splitext(os.path.basename(f))[0]
                out = os.path.join(self.out_dir, f"{base}.mp3")
                # Try ffmpeg first, then fall back to moviepy-like approach
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", f, "-q:a", str(self.quality), "-map", "a", out],
                    capture_output=True, timeout=300
                )
                if result.returncode == 0:
                    done += 1
                else:
                    # Try with moviepy
                    try:
                        from moviepy.editor import VideoFileClip
                        clip = VideoFileClip(f)
                        clip.audio.write_audiofile(out, verbose=False, logger=None)
                        clip.close()
                        done += 1
                    except: pass
            except Exception as e:
                pass
        self.finished.emit(done, len(self.files))


class MP4ToMP3Tool(QWidget):
    name = "MP4 to MP3 Converter"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._files = []
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("🎵 MP4 → MP3 Converter")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        note = QLabel("ℹ️ Requires ffmpeg installed on PATH (or moviepy as fallback)")
        note.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(note)

        row = QHBoxLayout()
        add = QPushButton("Add MP4 Files"); add.clicked.connect(self._add)
        row.addWidget(add)
        clr = QPushButton("Clear"); clr.setObjectName("secondary"); clr.clicked.connect(self._clear)
        row.addWidget(clr)
        row.addStretch()
        layout.addLayout(row)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(200)
        self.file_list.setStyleSheet("background: #2D2D2D; border: 1px solid #3E3E3E; border-radius: 6px;")
        layout.addWidget(self.file_list)

        grp = QGroupBox("Quality")
        gl = QHBoxLayout(grp)
        gl.addWidget(QLabel("Audio Quality (0=best, 9=worst):"))
        self.quality = QSpinBox(); self.quality.setRange(0, 9); self.quality.setValue(2)
        gl.addWidget(self.quality)
        gl.addStretch()
        layout.addWidget(grp)

        convert = QPushButton("Convert All")
        convert.clicked.connect(self._convert)
        layout.addWidget(convert)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.status = QLabel("")
        layout.addWidget(self.status)
        layout.addStretch()

    def _add(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select MP4 Files", filter="Video (*.mp4 *.mkv *.avi *.mov);;All (*)")
        for f in files:
            if f not in self._files:
                self._files.append(f); self.file_list.addItem(os.path.basename(f))

    def _clear(self):
        self._files.clear(); self.file_list.clear()

    def _convert(self):
        if not self._files: return
        out_dir = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if not out_dir: return
        self.progress.setValue(0)
        self.progress.setMaximum(len(self._files))
        self._worker = ConvertWorker(self._files, out_dir, self.quality.value())
        self._worker.progress.connect(lambda cur, tot: self.progress.setValue(cur))
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_done(self, done, total):
        self.status.setText(f"✅ Converted {done}/{total} files.")
        self.status.setStyleSheet("color: #4CAF50;")
