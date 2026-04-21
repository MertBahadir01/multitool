"""Website Change Tracker — detects when a website's content changes."""
import os, json, hashlib, time
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QSpinBox, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor

DATA_FILE = os.path.join(os.path.expanduser("~"), ".multitool_webtracker.json")


def _load():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f: return json.load(f)
        except Exception: pass
    return {}


def _save(data):
    try:
        with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2)
    except Exception: pass


def _fetch_hash(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "MultiToolStudio/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        content = r.read()
    return hashlib.sha256(content).hexdigest(), len(content)


class _CheckWorker(QThread):
    result = Signal(str, bool, str, int)   # url, changed, hash, size

    def __init__(self, url, old_hash):
        super().__init__()
        self.url = url
        self.old_hash = old_hash

    def run(self):
        try:
            h, size = _fetch_hash(self.url)
            changed = (h != self.old_hash) if self.old_hash else False
            self.result.emit(self.url, changed, h, size)
        except Exception as e:
            self.result.emit(self.url, False, f"ERROR:{e}", 0)


class WebsiteChangeTrackerTool(QWidget):
    name        = "Website Change Tracker"
    description = "Monitor websites and get notified when their content changes"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data    = _load()   # {url: {hash, last_checked, last_changed, size, status}}
        self._workers = []
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self._check_all)
        self._build_ui()
        self._refresh_table()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        # Add URL
        add_box = QGroupBox("Add Website")
        al = QHBoxLayout(add_box)
        self.url_in = QLineEdit()
        self.url_in.setPlaceholderText("https://example.com")
        self.url_in.returnPressed.connect(self._add_url)
        al.addWidget(self.url_in)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_url)
        al.addWidget(add_btn)
        lay.addWidget(add_box)

        # Controls
        ctrl = QHBoxLayout()
        self.check_btn = QPushButton("Check All Now")
        self.check_btn.clicked.connect(self._check_all)
        ctrl.addWidget(self.check_btn)

        ctrl.addWidget(QLabel("Auto-check every (min):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1440)
        self.interval_spin.setValue(30)
        ctrl.addWidget(self.interval_spin)

        self.auto_btn = QPushButton("Start Auto-Check")
        self.auto_btn.setObjectName("secondary")
        self.auto_btn.clicked.connect(self._toggle_auto)
        ctrl.addWidget(self.auto_btn)

        del_btn = QPushButton("Remove Selected")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._remove)
        ctrl.addWidget(del_btn)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #888888;")
        lay.addWidget(self.status_lbl)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["URL", "Status", "Last Checked", "Last Changed", "Size"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 150)
        self.table.setColumnWidth(3, 150)
        self.table.setColumnWidth(4, 80)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        lay.addWidget(self.table)

    def _add_url(self):
        url = self.url_in.text().strip()
        if not url: return
        if not url.startswith("http"): url = "https://" + url
        if url not in self._data:
            self._data[url] = {"hash": None, "last_checked": None, "last_changed": None, "size": 0, "status": "Pending"}
            _save(self._data)
            self._refresh_table()
        self.url_in.clear()

    def _check_all(self):
        if not self._data:
            self.status_lbl.setText("No URLs to check.")
            return
        self.status_lbl.setText("Checking...")
        self.check_btn.setEnabled(False)
        for url, info in self._data.items():
            w = _CheckWorker(url, info.get("hash"))
            w.result.connect(self._on_result)
            self._workers.append(w)
            w.start()

    def _on_result(self, url, changed, hash_or_err, size):
        if url not in self._data: return
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        info = self._data[url]
        if hash_or_err.startswith("ERROR:"):
            info["status"] = "Error"
        elif changed:
            info["status"]       = "CHANGED"
            info["last_changed"] = now
            info["hash"]         = hash_or_err
            info["size"]         = size
        else:
            info["status"] = "No Change" if info["hash"] else "Baseline set"
            if not info["hash"]:
                info["hash"] = hash_or_err
            info["size"] = size
        info["last_checked"] = now
        _save(self._data)
        self._refresh_table()
        self._workers = [w for w in self._workers if w.isRunning()]
        if not self._workers:
            self.check_btn.setEnabled(True)
            changed_count = sum(1 for v in self._data.values() if v["status"] == "CHANGED")
            self.status_lbl.setText(f"Done. {changed_count} change(s) detected.")
            self.status_lbl.setStyleSheet("color: #F44336;" if changed_count else "color: #00BFA5;")

    def _refresh_table(self):
        self.table.setRowCount(0)
        for url, info in self._data.items():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(url))
            status = info.get("status", "—")
            si = QTableWidgetItem(status)
            color = {"CHANGED": "#F44336", "No Change": "#00BFA5",
                     "Error": "#FF9800", "Baseline set": "#8BC34A"}.get(status, "#888888")
            si.setForeground(QColor(color))
            self.table.setItem(r, 1, si)
            self.table.setItem(r, 2, QTableWidgetItem(info.get("last_checked") or "—"))
            self.table.setItem(r, 3, QTableWidgetItem(info.get("last_changed") or "Never"))
            size = info.get("size", 0)
            self.table.setItem(r, 4, QTableWidgetItem(f"{size//1024} KB" if size else "—"))

    def _remove(self):
        rows = sorted(set(i.row() for i in self.table.selectedItems()), reverse=True)
        for r in rows:
            url = self.table.item(r, 0).text()
            self._data.pop(url, None)
            self.table.removeRow(r)
        _save(self._data)

    def _toggle_auto(self):
        if self._auto_timer.isActive():
            self._auto_timer.stop()
            self.auto_btn.setText("Start Auto-Check")
        else:
            self._auto_timer.start(self.interval_spin.value() * 60000)
            self.auto_btn.setText("Stop Auto-Check")
