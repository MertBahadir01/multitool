import base64
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QRadioButton, QButtonGroup, QGroupBox, QFileDialog)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

class Base64Tool(QWidget):
    name = "Base64 Encoder/Decoder"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("🔄 Base64 Encoder / Decoder")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        grp = QGroupBox("Mode")
        gl = QHBoxLayout(grp)
        self.enc_radio = QRadioButton("Encode (Text → Base64)"); self.enc_radio.setChecked(True)
        self.dec_radio = QRadioButton("Decode (Base64 → Text)")
        self.url_radio = QRadioButton("URL-safe Base64 Encode")
        for r in [self.enc_radio, self.dec_radio, self.url_radio]: gl.addWidget(r)
        gl.addStretch()
        layout.addWidget(grp)

        layout.addWidget(QLabel("Input:"))
        self.input = QTextEdit(); self.input.setFont(QFont("Courier New", 12))
        self.input.setMaximumHeight(160)
        layout.addWidget(self.input)

        row = QHBoxLayout()
        go = QPushButton("Convert"); go.clicked.connect(self._convert)
        row.addWidget(go)
        copy = QPushButton("Copy Output"); copy.setObjectName("secondary")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.output.toPlainText()))
        row.addWidget(copy)
        clr = QPushButton("Clear"); clr.setObjectName("secondary")
        clr.clicked.connect(lambda: [self.input.clear(), self.output.clear()])
        row.addWidget(clr)
        row.addStretch()
        layout.addLayout(row)

        layout.addWidget(QLabel("Output:"))
        self.output = QTextEdit(); self.output.setReadOnly(True)
        self.output.setFont(QFont("Courier New", 12))
        layout.addWidget(self.output)

        self.status = QLabel("")
        layout.addWidget(self.status)

    def _convert(self):
        text = self.input.toPlainText()
        try:
            if self.enc_radio.isChecked():
                result = base64.b64encode(text.encode()).decode()
            elif self.dec_radio.isChecked():
                result = base64.b64decode(text.encode()).decode()
            else:
                result = base64.urlsafe_b64encode(text.encode()).decode()
            self.output.setPlainText(result)
            self.status.setText("✅ Success"); self.status.setStyleSheet("color: #4CAF50;")
        except Exception as e:
            self.status.setText(f"❌ {e}"); self.status.setStyleSheet("color: #F44336;")

# Timestamp Converter
#cat > /home/claude/multitool_studio/tools/timestamp_converter/__init__.py << 'EOF'
#from .ts_tool import TimestampConverterTool
#TOOL_META = {"id": "timestamp_converter", "name": "Timestamp Converter", "category": "developer", "widget_class": TimestampConverterTool}
