"""LAN File Transfer Tool — send and receive files over a local network."""

import os
import socket
import struct
import threading
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QGroupBox, QFrame, QTabWidget,
    QSpinBox, QProgressBar, QFileDialog, QListWidget,
    QListWidgetItem, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont, QTextCursor

# ── Protocol constants ────────────────────────────────────────────────────────
# Frame format: [8-byte filename length][filename][8-byte file size][file data]
_HEADER_FMT = "!QQ"        # (name_len: uint64, file_size: uint64)
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)
_CHUNK_SIZE = 65536          # 64 KiB


def _recvall(sock: socket.socket, n: int) -> bytes:
    """Receive exactly n bytes, or raise if connection dropped."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed unexpectedly.")
        buf.extend(chunk)
    return bytes(buf)


# ── Signals carrier ───────────────────────────────────────────────────────────

class _Signals(QObject):
    log      = Signal(str, str)          # message, level
    progress = Signal(int, int, str)     # current, total, label
    done     = Signal()
    error    = Signal(str)


# ── Sender Worker ─────────────────────────────────────────────────────────────

class _SenderWorker(QThread):
    def __init__(self, host: str, port: int, files: list[str]):
        super().__init__()
        self.host = host
        self.port = port
        self.files = files
        self.signals = _Signals()
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        for idx, path in enumerate(self.files):
            if self._stop:
                break
            fname = os.path.basename(path)
            fsize = os.path.getsize(path)
            self.signals.log.emit(
                f"[{idx+1}/{len(self.files)}] Connecting to {self.host}:{self.port} …", "system"
            )
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10)
                sock.connect((self.host, self.port))
                sock.settimeout(None)

                # Send header: name_len + file_size, then name bytes
                name_bytes = fname.encode("utf-8")
                header = struct.pack(_HEADER_FMT, len(name_bytes), fsize)
                sock.sendall(header)
                sock.sendall(name_bytes)

                # Send file data
                sent = 0
                with open(path, "rb") as f:
                    while not self._stop:
                        chunk = f.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        sock.sendall(chunk)
                        sent += len(chunk)
                        self.signals.progress.emit(sent, fsize, f"Sending {fname}")
                sock.close()
                self.signals.log.emit(
                    f"✅ Sent: {fname}  ({_fmt_size(fsize)})", "send"
                )
            except Exception as e:
                self.signals.log.emit(f"❌ Error sending {fname}: {e}", "error")
            finally:
                try:
                    sock.close()
                except Exception:
                    pass

        self.signals.progress.emit(0, 1, "")
        self.signals.done.emit()


# ── Receiver Worker ───────────────────────────────────────────────────────────

class _ReceiverWorker(QThread):
    def __init__(self, port: int, save_dir: str):
        super().__init__()
        self.port = port
        self.save_dir = save_dir
        self.signals = _Signals()
        self._stop = False
        self._server_sock = None

    def stop(self):
        self._stop = True
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass

    def _handle_client(self, conn: socket.socket, addr):
        try:
            # Read header
            raw = _recvall(conn, _HEADER_SIZE)
            name_len, fsize = struct.unpack(_HEADER_FMT, raw)
            fname = _recvall(conn, name_len).decode("utf-8")

            self.signals.log.emit(
                f"📥 Incoming: {fname}  ({_fmt_size(fsize)}) from {addr[0]}:{addr[1]}", "system"
            )

            # Resolve save path (avoid collisions)
            save_path = os.path.join(self.save_dir, fname)
            if os.path.exists(save_path):
                base, ext = os.path.splitext(fname)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = os.path.join(self.save_dir, f"{base}_{ts}{ext}")
                fname = os.path.basename(save_path)

            # Receive file
            received = 0
            with open(save_path, "wb") as f:
                while received < fsize:
                    to_read = min(_CHUNK_SIZE, fsize - received)
                    chunk = conn.recv(to_read)
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
                    self.signals.progress.emit(received, fsize, f"Receiving {fname}")

            self.signals.log.emit(
                f"✅ Saved: {fname}  ({_fmt_size(received)}) → {self.save_dir}", "recv"
            )
        except Exception as e:
            self.signals.log.emit(f"❌ Receive error: {e}", "error")
        finally:
            self.signals.progress.emit(0, 1, "")
            conn.close()

    def run(self):
        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind(("0.0.0.0", self.port))
            self._server_sock.listen(5)
            self._server_sock.settimeout(1.0)
            self.signals.log.emit(
                f"👂 Listening on port {self.port}  —  save dir: {self.save_dir}", "system"
            )
            while not self._stop:
                try:
                    conn, addr = self._server_sock.accept()
                    t = threading.Thread(
                        target=self._handle_client, args=(conn, addr), daemon=True
                    )
                    t.start()
                except socket.timeout:
                    continue
                except Exception:
                    break
        except Exception as e:
            self.signals.log.emit(f"❌ Server error: {e}", "error")
        finally:
            self.signals.log.emit("🔴 Receiver stopped.", "system")
            self.signals.done.emit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ── Style constants ───────────────────────────────────────────────────────────

_INPUT_STYLE = """
    QLineEdit, QSpinBox {
        background: #2D2D2D;
        color: #EEEEEE;
        border: 1px solid #3E3E3E;
        border-radius: 5px;
        padding: 5px 8px;
        font-size: 13px;
    }
    QLineEdit:focus, QSpinBox:focus { border: 1px solid #00BFA5; }
"""

_BTN_PRIMARY = """
    QPushButton {
        background: #00BFA5; color: #000;
        border: none; border-radius: 6px;
        padding: 7px 18px; font-size: 13px; font-weight: bold;
    }
    QPushButton:hover   { background: #00D4B8; }
    QPushButton:pressed { background: #009E8D; }
    QPushButton:disabled{ background: #3E3E3E; color: #666; }
"""

_BTN_DANGER = """
    QPushButton {
        background: #C62828; color: #FFF;
        border: none; border-radius: 6px;
        padding: 7px 18px; font-size: 13px; font-weight: bold;
    }
    QPushButton:hover   { background: #E53935; }
    QPushButton:pressed { background: #B71C1C; }
    QPushButton:disabled{ background: #3E3E3E; color: #666; }
"""

_BTN_NEUTRAL = """
    QPushButton {
        background: #37474F; color: #EEE;
        border: none; border-radius: 6px;
        padding: 7px 18px; font-size: 13px;
    }
    QPushButton:hover   { background: #455A64; }
    QPushButton:pressed { background: #263238; }
"""

_GROUP_STYLE = """
    QGroupBox {
        color: #AAAAAA; font-size: 12px;
        border: 1px solid #3E3E3E; border-radius: 7px;
        margin-top: 6px; padding-top: 10px;
    }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
"""

_LOG_COLORS = {
    "system": "#FFB74D",
    "send":   "#4FC3F7",
    "recv":   "#81C784",
    "error":  "#EF5350",
    "info":   "#CCCCCC",
}


# ── Main Widget ───────────────────────────────────────────────────────────────

class LANFileTransferTool(QWidget):
    name = "LAN File Transfer"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sender: _SenderWorker | None = None
        self._receiver: _ReceiverWorker | None = None
        self._send_files: list[str] = []
        self._save_dir: str = os.path.expanduser("~")
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title = QLabel("📡 LAN File Transfer")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        root.addWidget(title)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3E3E3E; border-radius: 6px; background: #1E1E1E;
            }
            QTabBar::tab {
                background: #252526; color: #AAAAAA;
                padding: 8px 22px; border-top-left-radius: 6px; border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected { background: #1E1E1E; color: #00BFA5; font-weight: bold; }
        """)
        tabs.addTab(self._build_send_tab(), "📤  Send")
        tabs.addTab(self._build_recv_tab(), "📥  Receive")
        root.addWidget(tabs, stretch=1)

        # Shared log
        log_lbl = QLabel("Activity Log")
        log_lbl.setStyleSheet("color: #CCCCCC; font-weight: bold;")
        root.addWidget(log_lbl)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Courier New", 10))
        self._log.setFixedHeight(140)
        self._log.setStyleSheet("""
            QTextEdit {
                background: #1A1A1A; color: #CCCCCC;
                border: 1px solid #3E3E3E; border-radius: 6px; padding: 6px;
            }
        """)
        root.addWidget(self._log)

        btn_clear = QPushButton("Clear Log")
        btn_clear.setFixedHeight(32)
        btn_clear.setStyleSheet(_BTN_NEUTRAL)
        btn_clear.clicked.connect(self._log.clear)
        root.addWidget(btn_clear, alignment=Qt.AlignRight)

    # ── Send tab ──────────────────────────────────────────────────────────────

    def _build_send_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        # File list
        file_box = QGroupBox("Files to Send")
        file_box.setStyleSheet(_GROUP_STYLE)
        fb_lay = QVBoxLayout(file_box)

        self._file_list = QListWidget()
        self._file_list.setStyleSheet("""
            QListWidget {
                background: #2D2D2D; color: #EEEEEE;
                border: 1px solid #3E3E3E; border-radius: 5px;
            }
            QListWidget::item:selected { background: #1A3A35; }
        """)
        self._file_list.setMinimumHeight(100)
        fb_lay.addWidget(self._file_list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add Files")
        btn_add.setStyleSheet(_BTN_NEUTRAL)
        btn_add.clicked.connect(self._add_files)
        btn_row.addWidget(btn_add)

        btn_rem = QPushButton("Remove Selected")
        btn_rem.setStyleSheet(_BTN_NEUTRAL)
        btn_rem.clicked.connect(self._remove_selected)
        btn_row.addWidget(btn_rem)
        btn_row.addStretch()
        fb_lay.addLayout(btn_row)
        lay.addWidget(file_box)

        # Target
        target_box = QGroupBox("Target")
        target_box.setStyleSheet(_GROUP_STYLE)
        tb_lay = QHBoxLayout(target_box)

        tb_lay.addWidget(QLabel("IP:"))
        self._send_ip = QLineEdit("192.168.1.x")
        self._send_ip.setStyleSheet(_INPUT_STYLE)
        self._send_ip.setFixedWidth(150)
        tb_lay.addWidget(self._send_ip)

        tb_lay.addWidget(QLabel("Port:"))
        self._send_port = QSpinBox()
        self._send_port.setRange(1, 65535)
        self._send_port.setValue(5001)
        self._send_port.setStyleSheet(_INPUT_STYLE)
        self._send_port.setFixedWidth(80)
        tb_lay.addWidget(self._send_port)
        tb_lay.addStretch()
        lay.addWidget(target_box)

        # Progress
        self._send_progress = QProgressBar()
        self._send_progress.setRange(0, 100)
        self._send_progress.setValue(0)
        self._send_progress.setTextVisible(True)
        self._send_progress.setStyleSheet("""
            QProgressBar {
                background: #2D2D2D; border: 1px solid #3E3E3E;
                border-radius: 5px; text-align: center; color: #EEEEEE; height: 20px;
            }
            QProgressBar::chunk { background: #00BFA5; border-radius: 4px; }
        """)
        lay.addWidget(self._send_progress)

        self._send_status_lbl = QLabel("")
        self._send_status_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        lay.addWidget(self._send_status_lbl)

        # Buttons
        btn_send_row = QHBoxLayout()
        self._btn_send_start = QPushButton("▶  Send Files")
        self._btn_send_start.setStyleSheet(_BTN_PRIMARY)
        self._btn_send_start.clicked.connect(self._start_send)
        btn_send_row.addWidget(self._btn_send_start)

        self._btn_send_stop = QPushButton("■  Cancel")
        self._btn_send_stop.setEnabled(False)
        self._btn_send_stop.setStyleSheet(_BTN_DANGER)
        self._btn_send_stop.clicked.connect(self._stop_send)
        btn_send_row.addWidget(self._btn_send_stop)
        btn_send_row.addStretch()
        lay.addLayout(btn_send_row)
        lay.addStretch()
        return w

    # ── Receive tab ───────────────────────────────────────────────────────────

    def _build_recv_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        cfg_box = QGroupBox("Receiver Settings")
        cfg_box.setStyleSheet(_GROUP_STYLE)
        cb_lay = QVBoxLayout(cfg_box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Listen Port:"))
        self._recv_port = QSpinBox()
        self._recv_port.setRange(1, 65535)
        self._recv_port.setValue(5001)
        self._recv_port.setStyleSheet(_INPUT_STYLE)
        self._recv_port.setFixedWidth(90)
        row1.addWidget(self._recv_port)
        row1.addStretch()
        cb_lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Save Directory:"))
        self._save_dir_lbl = QLabel(self._save_dir)
        self._save_dir_lbl.setStyleSheet(
            "color: #888; background: #2D2D2D; border: 1px solid #3E3E3E; "
            "border-radius: 5px; padding: 4px 8px;"
        )
        self._save_dir_lbl.setWordWrap(True)
        row2.addWidget(self._save_dir_lbl, stretch=1)

        btn_browse = QPushButton("Browse…")
        btn_browse.setStyleSheet(_BTN_NEUTRAL)
        btn_browse.clicked.connect(self._browse_save_dir)
        row2.addWidget(btn_browse)
        cb_lay.addLayout(row2)
        lay.addWidget(cfg_box)

        # Progress
        self._recv_progress = QProgressBar()
        self._recv_progress.setRange(0, 100)
        self._recv_progress.setValue(0)
        self._recv_progress.setTextVisible(True)
        self._recv_progress.setStyleSheet("""
            QProgressBar {
                background: #2D2D2D; border: 1px solid #3E3E3E;
                border-radius: 5px; text-align: center; color: #EEEEEE; height: 20px;
            }
            QProgressBar::chunk { background: #81C784; border-radius: 4px; }
        """)
        lay.addWidget(self._recv_progress)

        self._recv_status_lbl = QLabel("")
        self._recv_status_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        lay.addWidget(self._recv_status_lbl)

        # Buttons
        btn_row = QHBoxLayout()
        self._btn_recv_start = QPushButton("▶  Start Listening")
        self._btn_recv_start.setStyleSheet(_BTN_PRIMARY)
        self._btn_recv_start.clicked.connect(self._start_recv)
        btn_row.addWidget(self._btn_recv_start)

        self._btn_recv_stop = QPushButton("■  Stop")
        self._btn_recv_stop.setEnabled(False)
        self._btn_recv_stop.setStyleSheet(_BTN_DANGER)
        self._btn_recv_stop.clicked.connect(self._stop_recv)
        btn_row.addWidget(self._btn_recv_stop)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        # Local IP helper
        local_ip = self._get_local_ip()
        hint = QLabel(f"💡 Your local IP: {local_ip}")
        hint.setStyleSheet("color: #777; font-size: 11px;")
        lay.addWidget(hint)
        lay.addStretch()
        return w

    # ── Actions: Send ─────────────────────────────────────────────────────────

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        for p in paths:
            if p not in self._send_files:
                self._send_files.append(p)
                self._file_list.addItem(os.path.basename(p))

    def _remove_selected(self):
        for item in self._file_list.selectedItems():
            row = self._file_list.row(item)
            self._file_list.takeItem(row)
            del self._send_files[row]

    def _start_send(self):
        if not self._send_files:
            self._append_log("No files selected.", "error")
            return
        host = self._send_ip.text().strip()
        port = self._send_port.value()
        if not host:
            self._append_log("Enter a target IP address.", "error")
            return

        self._sender = _SenderWorker(host, port, list(self._send_files))
        self._sender.signals.log.connect(self._append_log)
        self._sender.signals.progress.connect(self._on_send_progress)
        self._sender.signals.done.connect(self._on_send_done)
        self._sender.start()

        self._btn_send_start.setEnabled(False)
        self._btn_send_stop.setEnabled(True)

    def _stop_send(self):
        if self._sender:
            self._sender.stop()

    def _on_send_progress(self, current: int, total: int, label: str):
        pct = int(current / total * 100) if total else 0
        self._send_progress.setValue(pct)
        self._send_status_lbl.setText(
            f"{label}  —  {_fmt_size(current)} / {_fmt_size(total)}"
        )

    def _on_send_done(self):
        self._btn_send_start.setEnabled(True)
        self._btn_send_stop.setEnabled(False)
        self._send_progress.setValue(0)
        self._send_status_lbl.setText("")

    # ── Actions: Receive ──────────────────────────────────────────────────────

    def _browse_save_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Save Directory", self._save_dir)
        if d:
            self._save_dir = d
            self._save_dir_lbl.setText(d)

    def _start_recv(self):
        port = self._recv_port.value()
        self._receiver = _ReceiverWorker(port, self._save_dir)
        self._receiver.signals.log.connect(self._append_log)
        self._receiver.signals.progress.connect(self._on_recv_progress)
        self._receiver.signals.done.connect(self._on_recv_done)
        self._receiver.start()

        self._btn_recv_start.setEnabled(False)
        self._btn_recv_stop.setEnabled(True)
        self._recv_port.setEnabled(False)

    def _stop_recv(self):
        if self._receiver:
            self._receiver.stop()

    def _on_recv_progress(self, current: int, total: int, label: str):
        pct = int(current / total * 100) if total else 0
        self._recv_progress.setValue(pct)
        self._recv_status_lbl.setText(
            f"{label}  —  {_fmt_size(current)} / {_fmt_size(total)}"
        )

    def _on_recv_done(self):
        self._btn_recv_start.setEnabled(True)
        self._btn_recv_stop.setEnabled(False)
        self._recv_port.setEnabled(True)
        self._recv_progress.setValue(0)
        self._recv_status_lbl.setText("")

    # ── Shared log ────────────────────────────────────────────────────────────

    def _append_log(self, message: str, level: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        color = _LOG_COLORS.get(level, "#CCCCCC")
        html = (
            f'<span style="color:#555555;">[{ts}]</span> '
            f'<span style="color:{color};">{message}</span>'
        )
        self._log.append(html)
        self._log.moveCursor(QTextCursor.End)

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _get_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "Unknown"

    def closeEvent(self, event):
        if self._sender:
            self._sender.stop()
            self._sender.wait(1000)
        if self._receiver:
            self._receiver.stop()
            self._receiver.wait(1000)
        super().closeEvent(event)
