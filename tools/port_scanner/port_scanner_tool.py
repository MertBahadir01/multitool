"""Port Scanner — multithreaded TCP port scanner with live results."""
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QSpinBox, QCheckBox, QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal, QMutex
from PySide6.QtGui import QFont, QColor

COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 3306: "MySQL",
    3389: "RDP", 5432: "PostgreSQL", 5900: "VNC", 6379: "Redis",
    8080: "HTTP-Alt", 8443: "HTTPS-Alt", 27017: "MongoDB",
}


class _ScanWorker(QThread):
    port_result = Signal(int, bool, str)   # port, is_open, service
    progress    = Signal(int)
    finished    = Signal(int, int)         # open_count, total

    def __init__(self, host, ports, timeout, threads):
        super().__init__()
        self._host = host; self._ports = ports
        self._timeout = timeout; self._threads = threads
        self._stop = False

    def stop(self): self._stop = True

    def _check(self, port):
        if self._stop: return port, False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self._timeout)
            result = s.connect_ex((self._host, port))
            s.close()
            return port, result == 0
        except Exception:
            return port, False

    def run(self):
        open_count = 0; total = len(self._ports)
        done = 0
        with ThreadPoolExecutor(max_workers=self._threads) as ex:
            futures = {ex.submit(self._check, p): p for p in self._ports}
            for fut in as_completed(futures):
                if self._stop: break
                port, is_open = fut.result()
                service = COMMON_PORTS.get(port, "")
                self.port_result.emit(port, is_open, service)
                if is_open: open_count += 1
                done += 1
                self.progress.emit(int(done / total * 100))
        self.finished.emit(open_count, total)


class PortScannerTool(QWidget):
    name        = "Port Scanner"
    description = "Multithreaded TCP port scanner"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E;border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(24, 14, 24, 14)
        t = QLabel("🔍 Port Scanner"); t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;"); hl.addWidget(t); hl.addStretch()
        root.addWidget(hdr)

        body = QWidget(); body.setStyleSheet("background:#151515;")
        bl = QVBoxLayout(body); bl.setContentsMargins(24, 20, 24, 20); bl.setSpacing(12)

        # Controls
        ctrl = QHBoxLayout(); ctrl.setSpacing(12)
        ctrl.addWidget(QLabel("Host / IP:", styleSheet="color:#888;"))
        self._host_edit = QLineEdit(); self._host_edit.setPlaceholderText("192.168.1.1  or  example.com")
        self._host_edit.setStyleSheet(self._inp()); self._host_edit.setFixedHeight(36)
        ctrl.addWidget(self._host_edit)

        ctrl.addWidget(QLabel("From:", styleSheet="color:#888;"))
        self._from_spin = QSpinBox(); self._from_spin.setRange(1, 65535)
        self._from_spin.setValue(1); self._from_spin.setFixedWidth(80)
        self._from_spin.setStyleSheet(self._inp())
        ctrl.addWidget(self._from_spin)

        ctrl.addWidget(QLabel("To:", styleSheet="color:#888;"))
        self._to_spin = QSpinBox(); self._to_spin.setRange(1, 65535)
        self._to_spin.setValue(1024); self._to_spin.setFixedWidth(80)
        self._to_spin.setStyleSheet(self._inp())
        ctrl.addWidget(self._to_spin)

        ctrl.addWidget(QLabel("Preset:", styleSheet="color:#888;"))
        self._preset = QComboBox()
        self._preset.addItems(["Custom", "Common (top 20)", "1–1024", "1–65535"])
        self._preset.setStyleSheet(self._inp()); self._preset.setFixedWidth(140)
        self._preset.currentIndexChanged.connect(self._apply_preset)
        ctrl.addWidget(self._preset)
        bl.addLayout(ctrl)

        opt = QHBoxLayout(); opt.setSpacing(16)
        opt.addWidget(QLabel("Timeout (s):", styleSheet="color:#888;"))
        self._timeout = QSpinBox(); self._timeout.setRange(1, 10); self._timeout.setValue(1)
        self._timeout.setFixedWidth(60); self._timeout.setStyleSheet(self._inp())
        opt.addWidget(self._timeout)

        opt.addWidget(QLabel("Threads:", styleSheet="color:#888;"))
        self._threads = QSpinBox(); self._threads.setRange(1, 200); self._threads.setValue(100)
        self._threads.setFixedWidth(70); self._threads.setStyleSheet(self._inp())
        opt.addWidget(self._threads)

        self._open_only_chk = QCheckBox("Show open ports only")
        self._open_only_chk.setChecked(True)
        self._open_only_chk.setStyleSheet("color:#888;font-size:12px;")
        opt.addWidget(self._open_only_chk)
        opt.addStretch()

        self._scan_btn = QPushButton("▶  Start Scan")
        self._scan_btn.setFixedHeight(36)
        self._scan_btn.setStyleSheet(
            "background:#00BFA5;color:#000;border:none;border-radius:7px;"
            "font-weight:bold;font-size:13px;padding:0 20px;")
        self._scan_btn.clicked.connect(self._start)
        opt.addWidget(self._scan_btn)

        self._stop_btn = QPushButton("⏹  Stop")
        self._stop_btn.setFixedHeight(36); self._stop_btn.setEnabled(False)
        self._stop_btn.setStyleSheet("background:#F44336;color:#fff;border:none;border-radius:7px;font-size:13px;padding:0 14px;")
        self._stop_btn.clicked.connect(self._stop)
        opt.addWidget(self._stop_btn)
        bl.addLayout(opt)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100); self._progress.setValue(0)
        self._progress.setFixedHeight(8); self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar{background:#252525;border-radius:4px;border:none;}"
            "QProgressBar::chunk{background:#00BFA5;border-radius:4px;}")
        bl.addWidget(self._progress)

        self._status_lbl = QLabel("Ready — enter a host and click Start Scan")
        self._status_lbl.setStyleSheet("color:#555;font-size:12px;")
        bl.addWidget(self._status_lbl)

        # Results table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Port", "Status", "Service", "Banner"])
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 80); self._table.setColumnWidth(1, 80)
        self._table.setColumnWidth(2, 120)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(
            "QTableWidget{background:#1A1A1A;border:none;font-size:12px;}"
            "QHeaderView::section{background:#252525;color:#888;border:none;padding:6px;}"
            "QTableWidget::item{padding:4px 8px;}")
        bl.addWidget(self._table, 1)

        root.addWidget(body, 1)

    def _inp(self):
        return ("background:#252525;border:1px solid #3E3E3E;border-radius:6px;"
                "padding:5px 10px;color:#E0E0E0;font-size:13px;")

    def _apply_preset(self, idx):
        presets = [None, None, (1, 1024), (1, 65535)]
        if idx == 1:
            self._from_spin.setValue(1); self._to_spin.setValue(65535)
        elif presets[idx]:
            self._from_spin.setValue(presets[idx][0])
            self._to_spin.setValue(presets[idx][1])

    def _start(self):
        host = self._host_edit.text().strip()
        if not host:
            self._status_lbl.setText("❌ Enter a host/IP"); return
        p_from = self._from_spin.value(); p_to = self._to_spin.value()
        if p_from > p_to:
            self._status_lbl.setText("❌ 'From' must be ≤ 'To'"); return

        # Resolve hostname
        try: host = socket.gethostbyname(host)
        except Exception as e:
            self._status_lbl.setText(f"❌ Cannot resolve host: {e}"); return

        if self._preset.currentIndex() == 1:
            ports = list(COMMON_PORTS.keys())
        else:
            ports = list(range(p_from, p_to + 1))

        self._table.setRowCount(0)
        self._progress.setValue(0)
        self._scan_btn.setEnabled(False); self._stop_btn.setEnabled(True)
        self._status_lbl.setText(f"🔍 Scanning {host}  ({len(ports)} ports)…")
        self._status_lbl.setStyleSheet("color:#FF9800;font-size:12px;")

        self._worker = _ScanWorker(host, ports,
                                   self._timeout.value(),
                                   self._threads.value())
        self._worker.port_result.connect(self._on_port)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _stop(self):
        if self._worker: self._worker.stop()

    def _on_port(self, port, is_open, service):
        if not is_open and self._open_only_chk.isChecked(): return
        r = self._table.rowCount(); self._table.insertRow(r)
        p_item = QTableWidgetItem(str(port))
        p_item.setTextAlignment(Qt.AlignCenter); self._table.setItem(r, 0, p_item)
        status_item = QTableWidgetItem("OPEN" if is_open else "closed")
        status_item.setForeground(QColor("#4CAF50" if is_open else "#555"))
        status_item.setTextAlignment(Qt.AlignCenter); self._table.setItem(r, 1, status_item)
        self._table.setItem(r, 2, QTableWidgetItem(service))
        self._table.setItem(r, 3, QTableWidgetItem(""))
        self._table.scrollToBottom()

    def _on_done(self, open_count, total):
        self._scan_btn.setEnabled(True); self._stop_btn.setEnabled(False)
        self._status_lbl.setText(f"✅ Done — {open_count} open port(s) found out of {total} scanned")
        self._status_lbl.setStyleSheet("color:#4CAF50;font-size:12px;")
        # Sort by port number
        self._table.sortItems(0, Qt.AscendingOrder)
