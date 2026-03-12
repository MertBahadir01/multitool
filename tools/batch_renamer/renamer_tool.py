"""
Batch File Renamer Tool
"""
import os
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QFileDialog, QCheckBox, QSpinBox, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt
from core.plugin_manager import ToolInterface


class BatchRenamerTool(ToolInterface):
    name = "Batch File Renamer"
    description = "Rename multiple files with patterns and rules"
    icon = "✏️"
    category = "File Tools"

    def get_widget(self):
        return BatchRenamerWidget()


class BatchRenamerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._files = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("✏️ Batch File Renamer")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # File selection
        sel_group = QGroupBox("Files")
        sel_layout = QHBoxLayout(sel_group)
        self.folder_path = QLineEdit()
        self.folder_path.setReadOnly(True)
        self.folder_path.setPlaceholderText("Select a folder...")
        browse_btn = QPushButton("Select Folder")
        browse_btn.clicked.connect(self._browse_folder)
        add_files_btn = QPushButton("Add Files")
        add_files_btn.setObjectName("btn_secondary")
        add_files_btn.clicked.connect(self._add_files)
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("btn_secondary")
        clear_btn.clicked.connect(self._clear_files)
        sel_layout.addWidget(self.folder_path, 1)
        sel_layout.addWidget(browse_btn)
        sel_layout.addWidget(add_files_btn)
        sel_layout.addWidget(clear_btn)
        layout.addWidget(sel_group)

        # Rename rules
        rules_group = QGroupBox("Rename Rules")
        rules_layout = QVBoxLayout(rules_group)

        # Find & Replace
        fr_row = QHBoxLayout()
        fr_row.addWidget(QLabel("Find:"))
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Text to find")
        fr_row.addWidget(self.find_input)
        fr_row.addWidget(QLabel("Replace:"))
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replacement text")
        fr_row.addWidget(self.replace_input)
        self.regex_chk = QCheckBox("Regex")
        fr_row.addWidget(self.regex_chk)
        rules_layout.addLayout(fr_row)

        # Prefix / Suffix
        ps_row = QHBoxLayout()
        ps_row.addWidget(QLabel("Add Prefix:"))
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("Text before filename")
        ps_row.addWidget(self.prefix_input)
        ps_row.addWidget(QLabel("Add Suffix:"))
        self.suffix_input = QLineEdit()
        self.suffix_input.setPlaceholderText("Text after filename (before ext)")
        ps_row.addWidget(self.suffix_input)
        rules_layout.addLayout(ps_row)

        # Numbering
        num_row = QHBoxLayout()
        self.add_num = QCheckBox("Add Numbers")
        num_row.addWidget(self.add_num)
        num_row.addWidget(QLabel("Start from:"))
        self.num_start = QSpinBox()
        self.num_start.setRange(0, 9999)
        self.num_start.setValue(1)
        num_row.addWidget(self.num_start)
        num_row.addWidget(QLabel("Padding:"))
        self.num_pad = QSpinBox()
        self.num_pad.setRange(1, 6)
        self.num_pad.setValue(3)
        num_row.addWidget(self.num_pad)
        num_row.addWidget(QLabel("Position:"))
        self.num_pos = QComboBox()
        self.num_pos.addItems(["Prefix", "Suffix"])
        num_row.addWidget(self.num_pos)
        num_row.addStretch()
        rules_layout.addLayout(num_row)

        # Case
        case_row = QHBoxLayout()
        case_row.addWidget(QLabel("Change Case:"))
        self.case_combo = QComboBox()
        self.case_combo.addItems(["No Change", "lowercase", "UPPERCASE", "Title Case"])
        case_row.addWidget(self.case_combo)
        case_row.addStretch()
        rules_layout.addLayout(case_row)

        layout.addWidget(rules_group)

        btn_row = QHBoxLayout()
        preview_btn = QPushButton("Preview Changes")
        preview_btn.clicked.connect(self._preview)
        rename_btn = QPushButton("Apply Rename")
        rename_btn.clicked.connect(self._apply_rename)
        btn_row.addWidget(preview_btn)
        btn_row.addWidget(rename_btn)
        layout.addLayout(btn_row)

        # Preview table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Original Name", "New Name"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_path.setText(folder)
            files = [os.path.join(folder, f) for f in os.listdir(folder)
                     if os.path.isfile(os.path.join(folder, f))]
            self._files = sorted(files)
            self._preview()

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        if files:
            self._files.extend(f for f in files if f not in self._files)
            self._preview()

    def _clear_files(self):
        self._files.clear()
        self.table.setRowCount(0)

    def _get_new_name(self, filepath, index):
        folder = os.path.dirname(filepath)
        base = os.path.basename(filepath)
        name, ext = os.path.splitext(base)

        # Find & Replace
        find = self.find_input.text()
        replace = self.replace_input.text()
        if find:
            try:
                if self.regex_chk.isChecked():
                    name = re.sub(find, replace, name)
                else:
                    name = name.replace(find, replace)
            except re.error:
                pass

        # Case
        case_idx = self.case_combo.currentIndex()
        if case_idx == 1:
            name = name.lower()
        elif case_idx == 2:
            name = name.upper()
        elif case_idx == 3:
            name = name.title()

        # Numbering
        num_str = ""
        if self.add_num.isChecked():
            n = self.num_start.value() + index
            num_str = str(n).zfill(self.num_pad.value())

        # Prefix/Suffix
        prefix = self.prefix_input.text()
        suffix = self.suffix_input.text()

        if self.add_num.isChecked() and self.num_pos.currentIndex() == 0:
            name = f"{prefix}{num_str}_{name}{suffix}"
        elif self.add_num.isChecked():
            name = f"{prefix}{name}{suffix}_{num_str}"
        else:
            name = f"{prefix}{name}{suffix}"

        return os.path.join(folder, name + ext)

    def _preview(self):
        self.table.setRowCount(0)
        for i, filepath in enumerate(self._files):
            new_path = self._get_new_name(filepath, i)
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(os.path.basename(filepath)))
            new_name = os.path.basename(new_path)
            item = QTableWidgetItem(new_name)
            if new_name != os.path.basename(filepath):
                item.setForeground(Qt.cyan)
            self.table.setItem(row, 1, item)

    def _apply_rename(self):
        if not self._files:
            return
        reply = QMessageBox.question(
            self, "Confirm", f"Rename {len(self._files)} file(s)?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        renamed = 0
        errors = 0
        for i, filepath in enumerate(self._files):
            new_path = self._get_new_name(filepath, i)
            if filepath != new_path:
                try:
                    os.rename(filepath, new_path)
                    renamed += 1
                except Exception as e:
                    errors += 1
        self._files = []
        self.table.setRowCount(0)
        self.status_label.setText(f"✓ Renamed {renamed} files. {errors} errors.")
        self.status_label.setStyleSheet(f"color: {'#4CAF50' if not errors else '#FF9800'};")
