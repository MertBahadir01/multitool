import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QListWidget, QGroupBox, QSpinBox, QCheckBox, QMessageBox)
from PySide6.QtGui import QFont

class BatchRenamerTool(QWidget):
    name = "Batch File Renamer"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._files = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("✏️ Batch File Renamer")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        row = QHBoxLayout()
        add_btn = QPushButton("Add Files"); add_btn.clicked.connect(self._add_files)
        row.addWidget(add_btn)
        clr = QPushButton("Clear"); clr.setObjectName("secondary"); clr.clicked.connect(self._clear)
        row.addWidget(clr)
        row.addStretch()
        layout.addLayout(row)

        self.file_list = QListWidget()
        self.file_list.setStyleSheet("background: #2D2D2D; border: 1px solid #3E3E3E; border-radius: 6px;")
        layout.addWidget(self.file_list)

        grp = QGroupBox("Rename Options")
        gl = QVBoxLayout(grp)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Prefix:"))
        self.prefix = QLineEdit(); self.prefix.setPlaceholderText("Optional prefix")
        r1.addWidget(self.prefix)
        r1.addWidget(QLabel("Suffix:"))
        self.suffix = QLineEdit(); self.suffix.setPlaceholderText("Optional suffix")
        r1.addWidget(self.suffix)
        gl.addLayout(r1)
        r2 = QHBoxLayout()
        self.num_chk = QCheckBox("Add numbering")
        self.num_chk.setChecked(True)
        r2.addWidget(self.num_chk)
        r2.addWidget(QLabel("Start at:"))
        self.start_num = QSpinBox(); self.start_num.setRange(0, 9999); self.start_num.setValue(1)
        r2.addWidget(self.start_num)
        r2.addStretch()
        gl.addLayout(r2)
        layout.addWidget(grp)

        rename_btn = QPushButton("Rename Files")
        rename_btn.clicked.connect(self._rename)
        layout.addWidget(rename_btn)
        layout.addStretch()

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        for f in files:
            if f not in self._files:
                self._files.append(f)
                self.file_list.addItem(os.path.basename(f))

    def _clear(self):
        self._files.clear(); self.file_list.clear()

    def _rename(self):
        if not self._files: return
        prefix = self.prefix.text()
        suffix = self.suffix.text()
        start = self.start_num.value()
        renamed = 0
        for i, path in enumerate(self._files):
            folder = os.path.dirname(path)
            _, ext = os.path.splitext(path)
            num = f"_{start + i:04d}" if self.num_chk.isChecked() else ""
            new_name = f"{prefix}{num}{suffix}{ext}"
            new_path = os.path.join(folder, new_name)
            try:
                os.rename(path, new_path)
                renamed += 1
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not rename {path}: {e}")
        QMessageBox.information(self, "Done", f"Renamed {renamed} files.")
        self._clear()
