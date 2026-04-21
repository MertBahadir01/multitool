"""Smart File Organizer — sorts files into categorized subfolders."""
import os, shutil
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QListWidget, QProgressBar, QGroupBox
)
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont

CATEGORIES = {
    "Images":      [".jpg",".jpeg",".png",".gif",".bmp",".webp",".tiff",".svg",".ico"],
    "Videos":      [".mp4",".mkv",".avi",".mov",".wmv",".flv",".webm",".3gp"],
    "Audio":       [".mp3",".wav",".flac",".aac",".ogg",".wma",".m4a"],
    "Documents":   [".pdf",".doc",".docx",".xls",".xlsx",".ppt",".pptx",".txt",".rtf"],
    "Archives":    [".zip",".rar",".7z",".tar",".gz",".bz2"],
    "Code":        [".py",".js",".ts",".html",".css",".java",".cpp",".c",".json",".xml",".sql"],
    "Executables": [".exe",".msi",".apk",".dmg",".deb"],
}

class _Worker(QThread):
    progress = Signal(int)
    log      = Signal(str)
    finished = Signal(int, int)

    def __init__(self, folder, dry_run):
        super().__init__()
        self.folder = folder
        self.dry_run = dry_run

    def run(self):
        files = [f for f in os.listdir(self.folder) if os.path.isfile(os.path.join(self.folder, f))]
        moved = skipped = 0
        for i, fname in enumerate(files):
            ext = os.path.splitext(fname)[1].lower()
            cat = next((c for c, exts in CATEGORIES.items() if ext in exts), "Other")
            dest_dir = os.path.join(self.folder, cat)
            if not self.dry_run:
                os.makedirs(dest_dir, exist_ok=True)
                try:
                    shutil.move(os.path.join(self.folder, fname), os.path.join(dest_dir, fname))
                    self.log.emit(f"[OK]  {fname}  ->  {cat}/")
                    moved += 1
                except Exception as e:
                    self.log.emit(f"[ERR] {fname}: {e}")
                    skipped += 1
            else:
                self.log.emit(f"[PREVIEW]  {fname}  ->  {cat}/")
                moved += 1
            self.progress.emit(int((i + 1) / len(files) * 100))
        self.finished.emit(moved, skipped)


class SmartFileOrganizerTool(QWidget):
    name        = "Smart File Organizer"
    description = "Automatically sort files into categorized subfolders"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._folder = ""
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        t = QLabel("Automatically sort files into subfolders by type")
        t.setStyleSheet("color: #888888;")
        lay.addWidget(t)

        fb = QGroupBox("Target Folder")
        fl = QHBoxLayout(fb)
        self.folder_lbl = QLabel("No folder selected")
        self.folder_lbl.setStyleSheet("color: #888888;")
        fl.addWidget(self.folder_lbl, 1)
        b = QPushButton("Browse")
        b.clicked.connect(self._browse)
        fl.addWidget(b)
        lay.addWidget(fb)

        cb = QGroupBox("Categories")
        cl = QVBoxLayout(cb)
        for cat, exts in CATEGORIES.items():
            row = QHBoxLayout()
            lbl = QLabel(f"<b>{cat}</b>")
            lbl.setFixedWidth(100)
            row.addWidget(lbl)
            row.addWidget(QLabel("  ".join(exts[:6]) + ("..." if len(exts) > 6 else "")))
            row.addStretch()
            cl.addLayout(row)
        cl.addWidget(QLabel("Everything else  ->  <b>Other/</b>"))
        lay.addWidget(cb)

        btn_row = QHBoxLayout()
        self.prev_btn = QPushButton("Preview (Dry Run)")
        self.prev_btn.setObjectName("secondary")
        self.prev_btn.clicked.connect(lambda: self._run(True))
        btn_row.addWidget(self.prev_btn)
        self.run_btn = QPushButton("Organize Files")
        self.run_btn.clicked.connect(lambda: self._run(False))
        btn_row.addWidget(self.run_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.bar = QProgressBar()
        self.bar.setVisible(False)
        lay.addWidget(self.bar)

        self.log = QListWidget()
        lay.addWidget(self.log)

    def _browse(self):
        f = QFileDialog.getExistingDirectory(self, "Select Folder")
        if f:
            self._folder = f
            self.folder_lbl.setText(f)
            self.folder_lbl.setStyleSheet("color: #CCCCCC;")

    def _run(self, dry_run):
        if not self._folder:
            self.log.addItem("Please select a folder first.")
            return
        self.log.clear()
        self.bar.setVisible(True)
        self.bar.setValue(0)
        self.run_btn.setEnabled(False)
        self.prev_btn.setEnabled(False)
        self._worker = _Worker(self._folder, dry_run)
        self._worker.progress.connect(self.bar.setValue)
        self._worker.log.connect(self.log.addItem)
        self._worker.finished.connect(self._done)
        self._worker.start()

    def _done(self, moved, skipped):
        self.log.addItem(f"Done: {moved} processed, {skipped} skipped.")
        self.run_btn.setEnabled(True)
        self.prev_btn.setEnabled(True)
