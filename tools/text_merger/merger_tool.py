import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QListWidget, QTextEdit, QCheckBox, QMessageBox)
from PySide6.QtGui import QFont

class TextMergerTool(QWidget):
    name = "Text File Merger"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._files = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("📄 Text File Merger")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        row = QHBoxLayout()
        add = QPushButton("Add Files"); add.clicked.connect(self._add)
        row.addWidget(add)
        clr = QPushButton("Clear"); clr.setObjectName("secondary"); clr.clicked.connect(self._clear)
        row.addWidget(clr)
        row.addStretch()
        layout.addLayout(row)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(160)
        self.file_list.setStyleSheet("background: #2D2D2D; border: 1px solid #3E3E3E; border-radius: 6px;")
        layout.addWidget(self.file_list)

        self.sep_chk = QCheckBox("Add filename headers between files")
        self.sep_chk.setChecked(True)
        layout.addWidget(self.sep_chk)

        merge = QPushButton("Merge Files"); merge.clicked.connect(self._merge)
        layout.addWidget(merge)
        save = QPushButton("Save Merged File"); save.setObjectName("secondary"); save.clicked.connect(self._save)
        layout.addWidget(save)

        self.preview = QTextEdit(); self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Courier New", 11))
        layout.addWidget(self.preview)
        layout.addStretch()

    def _add(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Text Files", filter="Text Files (*.txt *.csv *.log *.md);;All Files (*)")
        for f in files:
            if f not in self._files:
                self._files.append(f); self.file_list.addItem(os.path.basename(f))

    def _clear(self):
        self._files.clear(); self.file_list.clear(); self.preview.clear()

    def _merge(self):
        parts = []
        for f in self._files:
            try:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                if self.sep_chk.isChecked():
                    parts.append(f"{'='*60}\n# {os.path.basename(f)}\n{'='*60}\n{content}")
                else:
                    parts.append(content)
            except Exception as e:
                parts.append(f"[Error reading {f}: {e}]")
        self.preview.setPlainText("\n\n".join(parts))

    def _save(self):
        text = self.preview.toPlainText()
        if not text: return
        path, _ = QFileDialog.getSaveFileName(self, "Save Merged File", "merged.txt", "Text Files (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f: f.write(text)
            QMessageBox.information(self, "Saved", f"File saved to {path}")
