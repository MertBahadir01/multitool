import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QSpinBox, QSplitter)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

class JSONFormatterTool(QWidget):
    name = "JSON Formatter"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("📋 JSON Formatter & Validator")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        btn_row = QHBoxLayout()
        fmt = QPushButton("Format / Pretty Print"); fmt.clicked.connect(self._format)
        btn_row.addWidget(fmt)
        mini = QPushButton("Minify"); mini.setObjectName("secondary"); mini.clicked.connect(self._minify)
        btn_row.addWidget(mini)
        validate = QPushButton("Validate"); validate.setObjectName("secondary"); validate.clicked.connect(self._validate)
        btn_row.addWidget(validate)
        copy = QPushButton("Copy Output"); copy.setObjectName("secondary"); copy.clicked.connect(self._copy)
        btn_row.addWidget(copy)
        btn_row.addWidget(QLabel("Indent:"))
        self.indent = QSpinBox(); self.indent.setRange(1, 8); self.indent.setValue(2); self.indent.setFixedWidth(60)
        btn_row.addWidget(self.indent)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        splitter = QSplitter(Qt.Horizontal)
        self.input = QTextEdit(); self.input.setPlaceholderText('Paste JSON here...')
        self.input.setFont(QFont("Courier New", 12))
        self.output = QTextEdit(); self.output.setReadOnly(True)
        self.output.setFont(QFont("Courier New", 12))
        splitter.addWidget(self.input)
        splitter.addWidget(self.output)
        layout.addWidget(splitter)

        self.status = QLabel("")
        layout.addWidget(self.status)

    def _parse(self):
        try: return json.loads(self.input.toPlainText()), None
        except json.JSONDecodeError as e: return None, str(e)

    def _format(self):
        data, err = self._parse()
        if err: self.status.setText(f"❌ {err}"); self.status.setStyleSheet("color: #F44336;"); return
        self.output.setPlainText(json.dumps(data, indent=self.indent.value(), ensure_ascii=False))
        self.status.setText("✅ Valid JSON"); self.status.setStyleSheet("color: #4CAF50;")

    def _minify(self):
        data, err = self._parse()
        if err: self.status.setText(f"❌ {err}"); self.status.setStyleSheet("color: #F44336;"); return
        self.output.setPlainText(json.dumps(data, separators=(',', ':'), ensure_ascii=False))
        self.status.setText("✅ Minified"); self.status.setStyleSheet("color: #4CAF50;")

    def _validate(self):
        data, err = self._parse()
        if err: self.status.setText(f"❌ Invalid JSON: {err}"); self.status.setStyleSheet("color: #F44336;")
        else: self.status.setText("✅ Valid JSON"); self.status.setStyleSheet("color: #4CAF50;")

    def _copy(self):
        text = self.output.toPlainText()
        if text: QApplication.clipboard().setText(text)

# Base64 Tool
#cat > D:\Pyto\multitool_studio\tools\base64_tool\__init__.py << 'EOF'
#from .b64_tool import Base64Tool
#TOOL_META = {"id": "base64_tool", "name": "Base64 Encoder/Decoder", "category": "developer", "widget_class": Base64Tool}
