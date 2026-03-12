"""
Image Converter Tool
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QListWidget, QGroupBox,
    QFileDialog, QCheckBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from core.plugin_manager import ToolInterface

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class ImageConverterTool(ToolInterface):
    name = "Image Converter"
    description = "Convert images between formats (PNG, JPG, WebP, BMP, etc.)"
    icon = "🖼️"
    category = "Media Tools"

    def get_widget(self):
        return ImageConverterWidget()


class ImageConverterWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._files = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("🖼️ Image Converter")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        if not HAS_PIL:
            layout.addWidget(QLabel("⚠️ Pillow not installed. Run: pip install Pillow"))
            return

        content = QHBoxLayout()

        # Left
        left = QVBoxLayout()
        files_group = QGroupBox("Input Images")
        files_layout = QVBoxLayout(files_group)
        self.file_list = QListWidget()
        files_layout.addWidget(self.file_list, 1)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Images")
        add_btn.clicked.connect(self._add_files)
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("btn_secondary")
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(clear_btn)
        files_layout.addLayout(btn_row)
        left.addWidget(files_group)

        opts_group = QGroupBox("Conversion Options")
        opts_layout = QVBoxLayout(opts_group)
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Output Format:"))
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["PNG", "JPEG", "WebP", "BMP", "TIFF", "ICO", "GIF"])
        fmt_row.addWidget(self.fmt_combo)
        opts_layout.addLayout(fmt_row)

        qual_row = QHBoxLayout()
        qual_row.addWidget(QLabel("Quality (JPEG/WebP):"))
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(90)
        qual_row.addWidget(self.quality_spin)
        qual_row.addStretch()
        opts_layout.addLayout(qual_row)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output Folder:"))
        self.out_path = QLineEdit()
        self.out_path.setPlaceholderText("Same as input")
        out_btn = QPushButton("Browse")
        out_btn.setObjectName("btn_secondary")
        out_btn.clicked.connect(self._browse_output)
        out_row.addWidget(self.out_path, 1)
        out_row.addWidget(out_btn)
        opts_layout.addLayout(out_row)

        left.addWidget(opts_group)

        convert_btn = QPushButton("Convert Images")
        convert_btn.clicked.connect(self._convert)
        left.addWidget(convert_btn)
        content.addLayout(left, 1)

        # Right - preview
        right = QVBoxLayout()
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel("Select images to preview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(280, 280)
        self.preview_label.setStyleSheet("color: #555555;")
        preview_layout.addWidget(self.preview_label)
        right.addWidget(preview_group, 1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #00BFA5; word-wrap: break-word;")
        self.status_label.setWordWrap(True)
        right.addWidget(self.status_label)
        content.addLayout(right, 1)

        layout.addLayout(content, 1)
        self.file_list.currentRowChanged.connect(self._preview_selected)

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Images", "", "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.webp *.gif)"
        )
        for f in files:
            if f not in self._files:
                self._files.append(f)
                self.file_list.addItem(os.path.basename(f))

    def _clear(self):
        self._files.clear()
        self.file_list.clear()
        self.preview_label.setText("Select images to preview")
        self.preview_label.setPixmap(QPixmap())

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.out_path.setText(folder)

    def _preview_selected(self, row):
        if 0 <= row < len(self._files):
            pixmap = QPixmap(self._files[row])
            if not pixmap.isNull():
                pixmap = pixmap.scaled(260, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview_label.setPixmap(pixmap)

    def _convert(self):
        if not self._files:
            return
        fmt = self.fmt_combo.currentText()
        quality = self.quality_spin.value()
        out_folder = self.out_path.text()
        converted = 0
        errors = 0
        for filepath in self._files:
            try:
                folder = out_folder or os.path.dirname(filepath)
                base = os.path.splitext(os.path.basename(filepath))[0]
                out_path = os.path.join(folder, f"{base}.{fmt.lower()}")
                img = Image.open(filepath)
                if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                if fmt in ("JPEG", "WebP"):
                    img.save(out_path, quality=quality)
                else:
                    img.save(out_path)
                converted += 1
            except Exception as e:
                errors += 1
        self.status_label.setText(f"✓ Converted {converted} image(s). {errors} error(s).")


class ImageResizerTool(ToolInterface):
    name = "Image Resizer"
    description = "Resize images to specific dimensions"
    icon = "📐"
    category = "Media Tools"

    def get_widget(self):
        return ImageResizerWidget()


class ImageResizerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._files = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("📐 Image Resizer")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        if not HAS_PIL:
            layout.addWidget(QLabel("⚠️ Pillow not installed. Run: pip install Pillow"))
            return

        # File selection
        sel_group = QGroupBox("Images")
        sel_layout = QHBoxLayout(sel_group)
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(100)
        add_btn = QPushButton("Add Images")
        add_btn.clicked.connect(self._add_files)
        sel_layout.addWidget(self.file_list, 1)
        sel_layout.addWidget(add_btn)
        layout.addWidget(sel_group)

        # Resize options
        opts_group = QGroupBox("Resize Options")
        opts_layout = QVBoxLayout(opts_group)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Width:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 10000)
        self.width_spin.setValue(800)
        size_row.addWidget(self.width_spin)
        size_row.addWidget(QLabel("×  Height:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 10000)
        self.height_spin.setValue(600)
        size_row.addWidget(self.height_spin)
        size_row.addStretch()
        opts_layout.addLayout(size_row)

        self.keep_aspect = QCheckBox("Keep aspect ratio (uses width as reference)")
        self.keep_aspect.setChecked(True)
        opts_layout.addWidget(self.keep_aspect)

        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("Or scale by:"))
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.01, 10.0)
        self.scale_spin.setValue(0.5)
        self.scale_spin.setSingleStep(0.1)
        scale_row.addWidget(self.scale_spin)
        scale_row.addWidget(QLabel("× (leave 1.0 to use pixel dimensions)"))
        scale_row.addStretch()
        opts_layout.addLayout(scale_row)

        layout.addWidget(opts_group)

        resize_btn = QPushButton("Resize Images")
        resize_btn.clicked.connect(self._resize)
        layout.addWidget(resize_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #00BFA5;")
        layout.addWidget(self.status_label)
        layout.addStretch()

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Images", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        for f in files:
            if f not in self._files:
                self._files.append(f)
                self.file_list.addItem(os.path.basename(f))

    def _resize(self):
        if not self._files:
            return
        scale = self.scale_spin.value()
        done = 0
        for filepath in self._files:
            try:
                img = Image.open(filepath)
                if scale != 1.0:
                    new_w = int(img.width * scale)
                    new_h = int(img.height * scale)
                elif self.keep_aspect.isChecked():
                    ratio = self.width_spin.value() / img.width
                    new_w = self.width_spin.value()
                    new_h = int(img.height * ratio)
                else:
                    new_w = self.width_spin.value()
                    new_h = self.height_spin.value()
                resized = img.resize((new_w, new_h), Image.LANCZOS if hasattr(Image, 'LANCZOS') else Image.ANTIALIAS)
                base, ext = os.path.splitext(filepath)
                out_path = f"{base}_resized{ext}"
                resized.save(out_path)
                done += 1
            except Exception as e:
                pass
        self.status_label.setText(f"✓ Resized {done} image(s) – saved with '_resized' suffix")
