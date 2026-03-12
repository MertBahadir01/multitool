"""
Base64 Encoder / Decoder Tool
"""
import base64
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QFileDialog, QTabWidget, QLineEdit
)
from PySide6.QtCore import Qt
from core.plugin_manager import ToolInterface


class Base64Tool(ToolInterface):
    name = "Base64 Encoder"
    description = "Encode and decode Base64 data, including files"
    icon = "🔤"
    category = "Developer Tools"

    def get_widget(self):
        return Base64Widget()


class Base64Widget(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("🔤 Base64 Encoder / Decoder")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_text_tab(), "📝 Text")
        tabs.addTab(self._build_file_tab(), "📁 File")
        layout.addWidget(tabs, 1)

    def _build_text_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Input
        layout.addWidget(QLabel("Input Text:"))
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Enter text to encode or Base64 to decode...")
        layout.addWidget(self.text_input, 1)

        # Buttons
        btn_row = QHBoxLayout()
        enc_btn = QPushButton("Encode to Base64")
        enc_btn.clicked.connect(self._encode_text)
        dec_btn = QPushButton("Decode from Base64")
        dec_btn.setObjectName("btn_secondary")
        dec_btn.clicked.connect(self._decode_text)
        swap_btn = QPushButton("⇅ Swap")
        swap_btn.setObjectName("btn_secondary")
        swap_btn.clicked.connect(self._swap)
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("btn_secondary")
        clear_btn.clicked.connect(lambda: [self.text_input.clear(), self.text_output.clear()])
        btn_row.addWidget(enc_btn)
        btn_row.addWidget(dec_btn)
        btn_row.addWidget(swap_btn)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        self.text_status = QLabel("")
        layout.addWidget(self.text_status)

        # Output
        layout.addWidget(QLabel("Output:"))
        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        layout.addWidget(self.text_output, 1)

        copy_btn = QPushButton("Copy Output")
        copy_btn.clicked.connect(self._copy_text)
        layout.addWidget(copy_btn)
        return w

    def _build_file_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Select a file to encode:"))
        file_row = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(self.file_path, 1)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        encode_file_btn = QPushButton("Encode File to Base64")
        encode_file_btn.clicked.connect(self._encode_file)
        layout.addWidget(encode_file_btn)

        self.file_status = QLabel("")
        layout.addWidget(self.file_status)

        layout.addWidget(QLabel("Base64 Output:"))
        self.file_output = QTextEdit()
        self.file_output.setReadOnly(True)
        layout.addWidget(self.file_output, 1)

        save_btn = QPushButton("Save Base64 to File")
        save_btn.clicked.connect(self._save_output)
        layout.addWidget(save_btn)
        return w

    def _encode_text(self):
        text = self.text_input.toPlainText()
        if not text:
            return
        try:
            encoded = base64.b64encode(text.encode('utf-8')).decode('ascii')
            self.text_output.setPlainText(encoded)
            self.text_status.setStyleSheet("color: #4CAF50;")
            self.text_status.setText(f"✓ Encoded {len(text)} chars → {len(encoded)} Base64 chars")
        except Exception as e:
            self.text_status.setStyleSheet("color: #F44336;")
            self.text_status.setText(f"Error: {e}")

    def _decode_text(self):
        text = self.text_input.toPlainText().strip()
        if not text:
            return
        try:
            decoded = base64.b64decode(text).decode('utf-8')
            self.text_output.setPlainText(decoded)
            self.text_status.setStyleSheet("color: #4CAF50;")
            self.text_status.setText(f"✓ Decoded successfully")
        except Exception as e:
            self.text_status.setStyleSheet("color: #F44336;")
            self.text_status.setText(f"Error: Invalid Base64 – {e}")

    def _swap(self):
        inp = self.text_input.toPlainText()
        out = self.text_output.toPlainText()
        self.text_input.setPlainText(out)
        self.text_output.setPlainText(inp)

    def _copy_text(self):
        try:
            import pyperclip
            pyperclip.copy(self.text_output.toPlainText())
        except Exception:
            pass

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if path:
            self.file_path.setText(path)

    def _encode_file(self):
        path = self.file_path.text()
        if not path:
            return
        try:
            with open(path, 'rb') as f:
                data = f.read()
            encoded = base64.b64encode(data).decode('ascii')
            self.file_output.setPlainText(encoded)
            self.file_status.setStyleSheet("color: #4CAF50;")
            self.file_status.setText(f"✓ Encoded {len(data):,} bytes → {len(encoded):,} chars")
        except Exception as e:
            self.file_status.setStyleSheet("color: #F44336;")
            self.file_status.setText(f"Error: {e}")

    def _save_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Output", "encoded.b64", "Text Files (*.b64 *.txt)")
        if path:
            with open(path, 'w') as f:
                f.write(self.file_output.toPlainText())
