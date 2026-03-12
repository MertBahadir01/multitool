"""
MP4 to MP3 Converter Tool (fallback using ffmpeg if available)
"""
import os
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QGroupBox, QSpinBox, QComboBox, QFileDialog
)
from PySide6.QtCore import Qt, QThread, Signal
from core.plugin_manager import ToolInterface


class ConvertWorker(QThread):
    progress = Signal(str)
    done = Signal(str, bool)

    def __init__(self, input_path, output_path, bitrate):
        super().__init__()
        self.input = input_path
        self.output = output_path
        self.bitrate = bitrate

    def run(self):
        self.progress.emit(f"Converting: {os.path.basename(self.input)}")
        try:
            # Try ffmpeg
            result = subprocess.run(
                ["ffmpeg", "-i", self.input, "-b:a", f"{self.bitrate}k",
                 "-vn", "-y", self.output],
                capture_output=True, timeout=120
            )
            if result.returncode == 0:
                self.done.emit(os.path.basename(self.output), True)
            else:
                # Try moviepy as fallback
                try:
                    from moviepy.editor import VideoFileClip
                    clip = VideoFileClip(self.input)
                    clip.audio.write_audiofile(self.output, bitrate=f"{self.bitrate}k")
                    clip.close()
                    self.done.emit(os.path.basename(self.output), True)
                except Exception as e2:
                    self.done.emit(f"Error: {e2}", False)
        except FileNotFoundError:
            # ffmpeg not found, try moviepy
            try:
                from moviepy.editor import VideoFileClip
                clip = VideoFileClip(self.input)
                clip.audio.write_audiofile(self.output, bitrate=f"{self.bitrate}k")
                clip.close()
                self.done.emit(os.path.basename(self.output), True)
            except Exception as e:
                self.done.emit(f"Error: {e}\nInstall ffmpeg or moviepy", False)


class MP4ToMP3Tool(ToolInterface):
    name = "MP4 → MP3"
    description = "Convert MP4 video files to MP3 audio"
    icon = "🎵"
    category = "Media Tools"

    def get_widget(self):
        return MP4ToMP3Widget()


class MP4ToMP3Widget(QWidget):
    def __init__(self):
        super().__init__()
        self._files = []
        self._workers = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("🎵 MP4 → MP3 Converter")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel("Convert video files to audio. Requires ffmpeg or moviepy.")
        desc.setStyleSheet("color: #777777;")
        layout.addWidget(desc)

        # File selection
        files_group = QGroupBox("Video Files")
        files_layout = QVBoxLayout(files_group)
        self.file_list = QListWidget()
        files_layout.addWidget(self.file_list, 1)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add MP4 Files")
        add_btn.clicked.connect(self._add_files)
        remove_btn = QPushButton("Remove")
        remove_btn.setObjectName("btn_secondary")
        remove_btn.clicked.connect(self._remove)
        clear_btn = QPushButton("Clear All")
        clear_btn.setObjectName("btn_secondary")
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addWidget(clear_btn)
        files_layout.addLayout(btn_row)
        layout.addWidget(files_group, 1)

        # Options
        opts_group = QGroupBox("Options")
        opts_layout = QHBoxLayout(opts_group)
        opts_layout.addWidget(QLabel("Bitrate:"))
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(["128 kbps", "192 kbps", "256 kbps", "320 kbps"])
        self.bitrate_combo.setCurrentIndex(1)
        opts_layout.addWidget(self.bitrate_combo)

        opts_layout.addWidget(QLabel("Output Folder:"))
        self.out_path = QLineEdit()
        self.out_path.setPlaceholderText("Same as input")
        out_btn = QPushButton("Browse")
        out_btn.setObjectName("btn_secondary")
        out_btn.clicked.connect(self._browse_output)
        opts_layout.addWidget(self.out_path, 1)
        opts_layout.addWidget(out_btn)
        layout.addWidget(opts_group)

        convert_btn = QPushButton("Convert All to MP3")
        convert_btn.clicked.connect(self._convert)
        layout.addWidget(convert_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #00BFA5; font-size: 12px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Video Files", "", "Video Files (*.mp4 *.avi *.mkv *.mov *.wmv *.flv)"
        )
        for f in files:
            if f not in self._files:
                self._files.append(f)
                self.file_list.addItem(os.path.basename(f))

    def _remove(self):
        for item in self.file_list.selectedItems():
            idx = self.file_list.row(item)
            self.file_list.takeItem(idx)
            self._files.pop(idx)

    def _clear(self):
        self._files.clear()
        self.file_list.clear()

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.out_path.setText(folder)

    def _convert(self):
        if not self._files:
            return
        bitrate = int(self.bitrate_combo.currentText().split()[0])
        out_folder = self.out_path.text()
        for filepath in self._files:
            folder = out_folder or os.path.dirname(filepath)
            base = os.path.splitext(os.path.basename(filepath))[0]
            output = os.path.join(folder, f"{base}.mp3")
            worker = ConvertWorker(filepath, output, bitrate)
            worker.progress.connect(lambda msg: self.status_label.setText(f"🔄 {msg}"))
            worker.done.connect(self._on_done)
            worker.start()
            self._workers.append(worker)

    def _on_done(self, name, success):
        if success:
            self.status_label.setText(f"✓ Converted: {name}")
            self.status_label.setStyleSheet("color: #4CAF50;")
        else:
            self.status_label.setText(f"✗ Failed: {name}")
            self.status_label.setStyleSheet("color: #F44336;")
