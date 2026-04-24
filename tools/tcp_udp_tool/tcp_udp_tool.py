"""TCP/UDP Debugger Tool — server/client mode for both TCP and UDP."""

import socket
import threading
import time
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QComboBox, QGroupBox, QFrame,
    QRadioButton, QButtonGroup, QSpinBox, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont, QColor, QTextCursor


# ── Worker signals carrier ────────────────────────────────────────────────────

class _WorkerSignals(QObject):
    log        = Signal(str, str)   # message, level  (info/send/recv/error/system)
    status     = Signal(str, bool)  # label, is_connected
    stopped    = Signal()


# ── TCP Server Worker ─────────────────────────────────────────────────────────

class _TCPServerWorker(QThread):
    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port
        self.signals = _WorkerSignals()
        self._stop_event = threading.Event()
        self._server_sock = None
        self._clients: list[socket.socket] = []
        self._clients_lock = threading.Lock()

    def stop(self):
        self._stop_event.set()
        # Close all client sockets
        with self._clients_lock:
            for c in self._clients:
                try:
                    c.shutdown(socket.SHUT_RDWR)
                    c.close()
                except Exception:
                    pass
            self._clients.clear()
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass

    def send(self, message: str):
        data = (message + "\n").encode("utf-8")
        with self._clients_lock:
            for c in list(self._clients):
                try:
                    c.sendall(data)
                except Exception:
                    self._clients.remove(c)
        self.signals.log.emit(f"[SENT] {message}", "send")

    def _handle_client(self, conn: socket.socket, addr):
        with self._clients_lock:
            self._clients.append(conn)
        self.signals.log.emit(f"[CONNECT] Client connected: {addr[0]}:{addr[1]}", "system")
        self.signals.status.emit(f"Server • {len(self._clients)} client(s)", True)
        try:
            conn.settimeout(1.0)
            while not self._stop_event.is_set():
                try:
                    data = conn.recv(4096)
                    if not data:
                        break
                    text = data.decode("utf-8", errors="replace").strip()
                    self.signals.log.emit(f"[RECV from {addr[0]}:{addr[1]}] {text}", "recv")
                except socket.timeout:
                    continue
                except Exception:
                    break
        finally:
            with self._clients_lock:
                if conn in self._clients:
                    self._clients.remove(conn)
            try:
                conn.close()
            except Exception:
                pass
            self.signals.log.emit(f"[DISCONNECT] Client disconnected: {addr[0]}:{addr[1]}", "system")
            self.signals.status.emit(
                f"Server • {len(self._clients)} client(s)" if self._clients else "Server • Listening…",
                bool(self._clients)
            )

    def run(self):
        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind((self.host, self.port))
            self._server_sock.listen(5)
            self._server_sock.settimeout(1.0)
            self.signals.log.emit(f"[SERVER] Listening on {self.host}:{self.port} (TCP)", "system")
            self.signals.status.emit("Server • Listening…", False)
            while not self._stop_event.is_set():
                try:
                    conn, addr = self._server_sock.accept()
                    t = threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True)
                    t.start()
                except socket.timeout:
                    continue
                except Exception:
                    break
        except Exception as e:
            self.signals.log.emit(f"[ERROR] {e}", "error")
            self.signals.status.emit("Error", False)
        finally:
            self.signals.log.emit("[SERVER] Stopped.", "system")
            self.signals.status.emit("Disconnected", False)
            self.signals.stopped.emit()


# ── TCP Client Worker ─────────────────────────────────────────────────────────

class _TCPClientWorker(QThread):
    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port
        self.signals = _WorkerSignals()
        self._stop_event = threading.Event()
        self._sock = None

    def stop(self):
        self._stop_event.set()
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
                self._sock.close()
            except Exception:
                pass

    def send(self, message: str):
        if self._sock:
            try:
                self._sock.sendall((message + "\n").encode("utf-8"))
                self.signals.log.emit(f"[SENT] {message}", "send")
            except Exception as e:
                self.signals.log.emit(f"[ERROR] Send failed: {e}", "error")
        else:
            self.signals.log.emit("[ERROR] Not connected.", "error")

    def run(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(5.0)
            self._sock.connect((self.host, self.port))
            self._sock.settimeout(1.0)
            self.signals.log.emit(f"[CONNECT] Connected to {self.host}:{self.port} (TCP)", "system")
            self.signals.status.emit(f"Connected to {self.host}:{self.port}", True)
            while not self._stop_event.is_set():
                try:
                    data = self._sock.recv(4096)
                    if not data:
                        break
                    text = data.decode("utf-8", errors="replace").strip()
                    self.signals.log.emit(f"[RECV] {text}", "recv")
                except socket.timeout:
                    continue
                except Exception:
                    break
        except Exception as e:
            self.signals.log.emit(f"[ERROR] {e}", "error")
            self.signals.status.emit("Error", False)
        finally:
            self.signals.log.emit("[CLIENT] Disconnected.", "system")
            self.signals.status.emit("Disconnected", False)
            self.signals.stopped.emit()


# ── UDP Server Worker ─────────────────────────────────────────────────────────

class _UDPServerWorker(QThread):
    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port
        self.signals = _WorkerSignals()
        self._stop_event = threading.Event()
        self._sock = None
        self._last_addr = None

    def stop(self):
        self._stop_event.set()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    def send(self, message: str):
        if self._sock and self._last_addr:
            try:
                self._sock.sendto(message.encode("utf-8"), self._last_addr)
                self.signals.log.emit(f"[SENT → {self._last_addr[0]}:{self._last_addr[1]}] {message}", "send")
            except Exception as e:
                self.signals.log.emit(f"[ERROR] Send failed: {e}", "error")
        else:
            self.signals.log.emit("[INFO] No client has sent yet — no target to reply to.", "info")

    def run(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind((self.host, self.port))
            self._sock.settimeout(1.0)
            self.signals.log.emit(f"[SERVER] Listening on {self.host}:{self.port} (UDP)", "system")
            self.signals.status.emit("Server • Listening…", False)
            while not self._stop_event.is_set():
                try:
                    data, addr = self._sock.recvfrom(65535)
                    self._last_addr = addr
                    text = data.decode("utf-8", errors="replace").strip()
                    self.signals.log.emit(f"[RECV from {addr[0]}:{addr[1]}] {text}", "recv")
                    self.signals.status.emit(f"Last peer: {addr[0]}:{addr[1]}", True)
                except socket.timeout:
                    continue
                except Exception:
                    break
        except Exception as e:
            self.signals.log.emit(f"[ERROR] {e}", "error")
            self.signals.status.emit("Error", False)
        finally:
            self.signals.log.emit("[SERVER] Stopped.", "system")
            self.signals.status.emit("Disconnected", False)
            self.signals.stopped.emit()


# ── UDP Client Worker ─────────────────────────────────────────────────────────

class _UDPClientWorker(QThread):
    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port
        self.signals = _WorkerSignals()
        self._stop_event = threading.Event()
        self._sock = None

    def stop(self):
        self._stop_event.set()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    def send(self, message: str):
        if self._sock:
            try:
                self._sock.sendto(message.encode("utf-8"), (self.host, self.port))
                self.signals.log.emit(f"[SENT] {message}", "send")
            except Exception as e:
                self.signals.log.emit(f"[ERROR] Send failed: {e}", "error")
        else:
            self.signals.log.emit("[ERROR] Not started.", "error")

    def run(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.settimeout(1.0)
            self.signals.log.emit(f"[CLIENT] UDP client ready → {self.host}:{self.port}", "system")
            self.signals.status.emit(f"UDP Client → {self.host}:{self.port}", True)
            while not self._stop_event.is_set():
                try:
                    data, addr = self._sock.recvfrom(65535)
                    text = data.decode("utf-8", errors="replace").strip()
                    self.signals.log.emit(f"[RECV from {addr[0]}:{addr[1]}] {text}", "recv")
                except socket.timeout:
                    continue
                except Exception:
                    break
        except Exception as e:
            self.signals.log.emit(f"[ERROR] {e}", "error")
            self.signals.status.emit("Error", False)
        finally:
            self.signals.log.emit("[CLIENT] Stopped.", "system")
            self.signals.status.emit("Disconnected", False)
            self.signals.stopped.emit()


# ── Main Tool Widget ──────────────────────────────────────────────────────────

_LEVEL_COLORS = {
    "info":   "#CCCCCC",
    "send":   "#4FC3F7",
    "recv":   "#81C784",
    "error":  "#EF5350",
    "system": "#FFB74D",
}

_INPUT_STYLE = """
    QLineEdit, QSpinBox, QComboBox {
        background: #2D2D2D;
        color: #EEEEEE;
        border: 1px solid #3E3E3E;
        border-radius: 5px;
        padding: 5px 8px;
        font-size: 13px;
    }
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
        border: 1px solid #00BFA5;
    }
"""

_BTN_PRIMARY = """
    QPushButton {
        background: #00BFA5;
        color: #000000;
        border: none;
        border-radius: 6px;
        padding: 7px 18px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton:hover  { background: #00D4B8; }
    QPushButton:pressed{ background: #009E8D; }
    QPushButton:disabled { background: #3E3E3E; color: #666666; }
"""

_BTN_DANGER = """
    QPushButton {
        background: #C62828;
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        padding: 7px 18px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton:hover  { background: #E53935; }
    QPushButton:pressed{ background: #B71C1C; }
    QPushButton:disabled { background: #3E3E3E; color: #666666; }
"""

_BTN_NEUTRAL = """
    QPushButton {
        background: #37474F;
        color: #EEEEEE;
        border: none;
        border-radius: 6px;
        padding: 7px 18px;
        font-size: 13px;
    }
    QPushButton:hover  { background: #455A64; }
    QPushButton:pressed{ background: #263238; }
"""


class TCPUDPTool(QWidget):
    name = "TCP / UDP Debugger"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._running = False
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # Title
        title = QLabel("🔌 TCP / UDP Debugger")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        root.addWidget(title)

        # ── Config row ───────────────────────────────────────────────────────
        cfg_box = QGroupBox("Connection Settings")
        cfg_box.setStyleSheet("""
            QGroupBox {
                color: #AAAAAA; font-size: 12px;
                border: 1px solid #3E3E3E; border-radius: 7px;
                margin-top: 6px; padding-top: 10px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
        """)
        cfg_layout = QHBoxLayout(cfg_box)
        cfg_layout.setSpacing(12)

        # Protocol toggle
        proto_lbl = QLabel("Protocol:")
        proto_lbl.setStyleSheet("color: #CCCCCC;")
        cfg_layout.addWidget(proto_lbl)

        self._rb_tcp = QRadioButton("TCP")
        self._rb_udp = QRadioButton("UDP")
        self._rb_tcp.setChecked(True)
        for rb in (self._rb_tcp, self._rb_udp):
            rb.setStyleSheet("color: #CCCCCC; font-size: 13px;")
        self._proto_group = QButtonGroup(self)
        self._proto_group.addButton(self._rb_tcp)
        self._proto_group.addButton(self._rb_udp)
        cfg_layout.addWidget(self._rb_tcp)
        cfg_layout.addWidget(self._rb_udp)

        # Separator
        sep1 = QFrame(); sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("color: #3E3E3E;")
        cfg_layout.addWidget(sep1)

        # Mode toggle
        mode_lbl = QLabel("Mode:")
        mode_lbl.setStyleSheet("color: #CCCCCC;")
        cfg_layout.addWidget(mode_lbl)

        self._rb_server = QRadioButton("Server (Listen)")
        self._rb_client = QRadioButton("Client (Connect)")
        self._rb_server.setChecked(True)
        for rb in (self._rb_server, self._rb_client):
            rb.setStyleSheet("color: #CCCCCC; font-size: 13px;")
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._rb_server)
        self._mode_group.addButton(self._rb_client)
        cfg_layout.addWidget(self._rb_server)
        cfg_layout.addWidget(self._rb_client)

        # Separator
        sep2 = QFrame(); sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("color: #3E3E3E;")
        cfg_layout.addWidget(sep2)

        # IP + Port
        ip_lbl = QLabel("IP:")
        ip_lbl.setStyleSheet("color: #CCCCCC;")
        cfg_layout.addWidget(ip_lbl)

        self._ip_input = QLineEdit("0.0.0.0")
        self._ip_input.setFixedWidth(130)
        self._ip_input.setStyleSheet(_INPUT_STYLE)
        cfg_layout.addWidget(self._ip_input)

        port_lbl = QLabel("Port:")
        port_lbl.setStyleSheet("color: #CCCCCC;")
        cfg_layout.addWidget(port_lbl)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setValue(9000)
        self._port_spin.setFixedWidth(80)
        self._port_spin.setStyleSheet(_INPUT_STYLE)
        cfg_layout.addWidget(self._port_spin)

        cfg_layout.addStretch()

        # Start / Stop buttons
        self._btn_start = QPushButton("▶  Start")
        self._btn_start.setFixedHeight(34)
        self._btn_start.setStyleSheet(_BTN_PRIMARY)
        self._btn_start.clicked.connect(self._on_start)
        cfg_layout.addWidget(self._btn_start)

        self._btn_stop = QPushButton("■  Stop")
        self._btn_stop.setFixedHeight(34)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setStyleSheet(_BTN_DANGER)
        self._btn_stop.clicked.connect(self._on_stop)
        cfg_layout.addWidget(self._btn_stop)

        root.addWidget(cfg_box)

        # ── Status bar ───────────────────────────────────────────────────────
        status_row = QHBoxLayout()

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #555555; font-size: 16px;")
        status_row.addWidget(self._status_dot)

        self._status_lbl = QLabel("Not running")
        self._status_lbl.setStyleSheet("color: #888888; font-size: 12px;")
        status_row.addWidget(self._status_lbl)
        status_row.addStretch()
        root.addLayout(status_row)

        # ── Log output ───────────────────────────────────────────────────────
        log_lbl = QLabel("Log")
        log_lbl.setStyleSheet("color: #CCCCCC; font-weight: bold;")
        root.addWidget(log_lbl)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Courier New", 11))
        self._log.setStyleSheet("""
            QTextEdit {
                background: #1A1A1A;
                color: #CCCCCC;
                border: 1px solid #3E3E3E;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        root.addWidget(self._log, stretch=1)

        # ── Send row ─────────────────────────────────────────────────────────
        send_row = QHBoxLayout()

        self._msg_input = QLineEdit()
        self._msg_input.setPlaceholderText("Type a message to send…")
        self._msg_input.setStyleSheet(_INPUT_STYLE)
        self._msg_input.setEnabled(False)
        self._msg_input.returnPressed.connect(self._on_send)
        send_row.addWidget(self._msg_input, stretch=1)

        self._btn_send = QPushButton("Send ↑")
        self._btn_send.setFixedHeight(36)
        self._btn_send.setEnabled(False)
        self._btn_send.setStyleSheet(_BTN_PRIMARY)
        self._btn_send.clicked.connect(self._on_send)
        send_row.addWidget(self._btn_send)

        self._btn_clear = QPushButton("Clear Log")
        self._btn_clear.setFixedHeight(36)
        self._btn_clear.setStyleSheet(_BTN_NEUTRAL)
        self._btn_clear.clicked.connect(self._log.clear)
        send_row.addWidget(self._btn_clear)

        root.addLayout(send_row)

        # Connect mode radio to update IP hint
        self._rb_server.toggled.connect(self._update_ip_hint)
        self._update_ip_hint()

    def _update_ip_hint(self):
        if self._rb_server.isChecked():
            self._ip_input.setPlaceholderText("0.0.0.0")
            if self._ip_input.text() in ("", "127.0.0.1"):
                self._ip_input.setText("0.0.0.0")
        else:
            self._ip_input.setPlaceholderText("192.168.1.x")
            if self._ip_input.text() == "0.0.0.0":
                self._ip_input.setText("127.0.0.1")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_start(self):
        host = self._ip_input.text().strip() or "0.0.0.0"
        port = self._port_spin.value()
        proto = "TCP" if self._rb_tcp.isChecked() else "UDP"
        mode  = "server" if self._rb_server.isChecked() else "client"

        if proto == "TCP":
            self._worker = _TCPServerWorker(host, port) if mode == "server" else _TCPClientWorker(host, port)
        else:
            self._worker = _UDPServerWorker(host, port) if mode == "server" else _UDPClientWorker(host, port)

        self._worker.signals.log.connect(self._append_log)
        self._worker.signals.status.connect(self._update_status)
        self._worker.signals.stopped.connect(self._on_worker_stopped)
        self._worker.start()

        self._running = True
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._msg_input.setEnabled(True)
        self._btn_send.setEnabled(True)
        self._set_controls_enabled(False)

    def _on_stop(self):
        if self._worker:
            self._worker.stop()

    def _on_send(self):
        msg = self._msg_input.text().strip()
        if not msg:
            return
        if self._worker:
            self._worker.send(msg)
        self._msg_input.clear()

    def _on_worker_stopped(self):
        self._running = False
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._msg_input.setEnabled(False)
        self._btn_send.setEnabled(False)
        self._set_controls_enabled(True)
        self._update_status("Not running", False)

    def _set_controls_enabled(self, enabled: bool):
        for w in (self._rb_tcp, self._rb_udp, self._rb_server, self._rb_client,
                  self._ip_input, self._port_spin):
            w.setEnabled(enabled)

    # ── Log helpers ───────────────────────────────────────────────────────────

    def _append_log(self, message: str, level: str):
        ts = datetime.now().strftime("%H:%M:%S")
        color = _LEVEL_COLORS.get(level, "#CCCCCC")
        html = f'<span style="color:#555555;">[{ts}]</span> <span style="color:{color};">{message}</span>'
        self._log.append(html)
        self._log.moveCursor(QTextCursor.End)

    def _update_status(self, label: str, connected: bool):
        dot_color = "#00BFA5" if connected else "#555555"
        self._status_dot.setStyleSheet(f"color: {dot_color}; font-size: 16px;")
        self._status_lbl.setText(label)
        self._status_lbl.setStyleSheet(
            f"color: {'#00BFA5' if connected else '#888888'}; font-size: 12px;"
        )

    def closeEvent(self, event):
        if self._worker:
            self._worker.stop()
            self._worker.wait(2000)
        super().closeEvent(event)
