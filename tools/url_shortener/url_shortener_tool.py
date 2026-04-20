"""URL Shortener + Expander — TinyURL (no key) + history."""
import re, requests
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QListWidget, QListWidgetItem,
    QApplication, QSplitter, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor


class _Worker(QThread):
    result = Signal(str)
    error  = Signal(str)
    def __init__(self, fn): super().__init__(); self._fn = fn
    def run(self):
        try: self.result.emit(self._fn())
        except Exception as e: self.error.emit(str(e))


def _shorten(url: str) -> str:
    r = requests.get(f"https://tinyurl.com/api-create.php?url={url}", timeout=10)
    r.raise_for_status()
    return r.text.strip()


def _expand(url: str) -> str:
    r = requests.head(url, allow_redirects=True, timeout=10)
    return r.url


class URLShortenerTool(QWidget):
    name        = "URL Shortener"
    description = "Shorten or expand URLs using TinyURL"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history = []
        self._worker  = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E;border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(24, 14, 24, 14)
        t = QLabel("🔗 URL Shortener"); t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;"); hl.addWidget(t); hl.addStretch()
        root.addWidget(hdr)

        body = QWidget(); body.setStyleSheet("background:#151515;")
        bl = QVBoxLayout(body); bl.setContentsMargins(24, 20, 24, 20); bl.setSpacing(14)

        # Input
        bl.addWidget(QLabel("Enter URL:", styleSheet="color:#888;font-size:12px;"))
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://example.com/very/long/url...")
        self._url_edit.setStyleSheet(self._inp())
        self._url_edit.setFixedHeight(38)
        self._url_edit.returnPressed.connect(self._shorten)
        bl.addWidget(self._url_edit)

        # Buttons
        btn_row = QHBoxLayout()
        self._shorten_btn = QPushButton("✂️  Shorten")
        self._shorten_btn.setFixedHeight(38)
        self._shorten_btn.setStyleSheet(
            "background:#00BFA5;color:#000;border:none;border-radius:7px;"
            "font-weight:bold;font-size:13px;padding:0 20px;")
        self._shorten_btn.clicked.connect(self._shorten)
        btn_row.addWidget(self._shorten_btn)

        self._expand_btn = QPushButton("🔍  Expand")
        self._expand_btn.setFixedHeight(38)
        self._expand_btn.setStyleSheet(
            "background:#FF9800;color:#000;border:none;border-radius:7px;"
            "font-weight:bold;font-size:13px;padding:0 20px;")
        self._expand_btn.clicked.connect(self._expand)
        btn_row.addWidget(self._expand_btn)
        btn_row.addStretch()
        bl.addLayout(btn_row)

        # Result
        res_frame = QFrame()
        res_frame.setStyleSheet("background:#1A1A1A;border-radius:8px;border:1px solid #2A2A2A;")
        rl = QVBoxLayout(res_frame); rl.setContentsMargins(16, 12, 16, 12)
        self._result_lbl = QLabel("—")
        self._result_lbl.setFont(QFont("Segoe UI", 14))
        self._result_lbl.setStyleSheet("color:#00BFA5;background:transparent;border:none;")
        self._result_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._result_lbl.setWordWrap(True)
        rl.addWidget(self._result_lbl)

        copy_btn = QPushButton("📋 Copy")
        copy_btn.setFixedWidth(90); copy_btn.setFixedHeight(30)
        copy_btn.setStyleSheet("background:#252525;color:#E0E0E0;border:none;border-radius:5px;font-size:12px;")
        copy_btn.clicked.connect(lambda: (
            QApplication.clipboard().setText(self._result_lbl.text()),
            self._status("Copied!")
        ))
        rl.addWidget(copy_btn, 0, Qt.AlignLeft)
        bl.addWidget(res_frame)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color:#888;font-size:12px;")
        bl.addWidget(self._status_lbl)

        # History
        bl.addWidget(QLabel("History:", styleSheet="color:#555;font-size:11px;"))
        self._hist_list = QListWidget()
        self._hist_list.setStyleSheet(
            "QListWidget{background:#1A1A1A;border:none;font-size:12px;color:#888;}"
            "QListWidget::item:selected{background:#252525;color:#00BFA5;}")
        self._hist_list.itemDoubleClicked.connect(
            lambda item: (self._url_edit.setText(item.data(Qt.UserRole)),
                          self._result_lbl.setText(item.text().split(" → ")[-1])))
        bl.addWidget(self._hist_list, 1)

        clear_btn = QPushButton("🗑 Clear History")
        clear_btn.setFixedHeight(30)
        clear_btn.setStyleSheet("background:#3A3A3A;color:#888;border:none;border-radius:5px;font-size:12px;")
        clear_btn.clicked.connect(lambda: (self._hist_list.clear(), self._history.clear()))
        bl.addWidget(clear_btn, 0, Qt.AlignLeft)

        root.addWidget(body, 1)

    def _inp(self):
        return ("background:#252525;border:1px solid #3E3E3E;border-radius:6px;"
                "padding:6px 12px;color:#E0E0E0;font-size:13px;")

    def _status(self, msg, color="#888"):
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(f"color:{color};font-size:12px;")

    def _shorten(self):
        url = self._url_edit.text().strip()
        if not url: return
        if not url.startswith("http"): url = "https://" + url
        self._status("Shortening…", "#FF9800")
        self._shorten_btn.setEnabled(False)
        self._run(lambda: _shorten(url), url, "short")

    def _expand(self):
        url = self._url_edit.text().strip()
        if not url: return
        self._status("Expanding…", "#FF9800")
        self._expand_btn.setEnabled(False)
        self._run(lambda: _expand(url), url, "expand")

    def _run(self, fn, original, mode):
        self._worker = _Worker(fn)
        self._worker.result.connect(lambda r: self._on_result(r, original, mode))
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, result, original, mode):
        self._result_lbl.setText(result)
        self._status("✅ Done", "#4CAF50")
        self._shorten_btn.setEnabled(True); self._expand_btn.setEnabled(True)
        label = f"{original[:50]}… → {result}" if len(original) > 50 else f"{original} → {result}"
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, original)
        self._hist_list.insertItem(0, item)

    def _on_error(self, err):
        self._status(f"❌ {err}", "#F44336")
        self._shorten_btn.setEnabled(True); self._expand_btn.setEnabled(True)
