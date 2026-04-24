"""Database File Storage Tool — store, retrieve and preview files in SQLite."""

import io
import os
import mimetypes
import sqlite3
import zipfile
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QGroupBox, QFrame, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QFileDialog,
    QTextEdit, QScrollArea, QMessageBox, QDialog, QDialogButtonBox,
    QRadioButton, QButtonGroup, QSizePolicy, QAbstractItemView
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QByteArray
from PySide6.QtGui import QFont, QPixmap, QColor

from database.database import get_connection


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    return get_connection()


# ── Upload Worker ─────────────────────────────────────────────────────────────

class _UploadSignals(QObject):
    progress = Signal(int, int, str)   # done, total, label
    done     = Signal(int)             # rows inserted
    error    = Signal(str)


class _UploadWorker(QThread):
    def __init__(self, paths: list[str], compress: bool):
        super().__init__()
        self.paths = paths
        self.compress = compress
        self.signals = _UploadSignals()

    def run(self):
        inserted = 0
        try:
            conn = _get_conn()
            for i, path in enumerate(self.paths):
                fname = os.path.basename(path)
                self.signals.progress.emit(i, len(self.paths), f"Uploading {fname}…")
                try:
                    with open(path, "rb") as f:
                        raw = f.read()
                    orig_size = len(raw)
                    mime, _ = mimetypes.guess_type(path)
                    mime = mime or "application/octet-stream"

                    if self.compress:
                        buf = io.BytesIO()
                        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                            zf.writestr(fname, raw)
                        stored = buf.getvalue()
                        compressed = 1
                    else:
                        stored = raw
                        compressed = 0

                    conn.execute(
                        """INSERT INTO stored_files
                           (filename, original_size, stored_size, mime_type, compressed, file_data)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (fname, orig_size, len(stored), mime, compressed, stored)
                    )
                    conn.commit()
                    inserted += 1
                except Exception as e:
                    self.signals.error.emit(f"Error uploading {fname}: {e}")
            conn.close()
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.progress.emit(len(self.paths), len(self.paths), "")
            self.signals.done.emit(inserted)


# ── Download Worker ───────────────────────────────────────────────────────────

class _DownloadSignals(QObject):
    done  = Signal(str)   # saved path
    error = Signal(str)


class _DownloadWorker(QThread):
    def __init__(self, file_id: int, save_path: str, extract: bool):
        super().__init__()
        self.file_id = file_id
        self.save_path = save_path
        self.extract = extract
        self.signals = _DownloadSignals()

    def run(self):
        try:
            conn = _get_conn()
            row = conn.execute(
                "SELECT filename, compressed, file_data FROM stored_files WHERE id=?",
                (self.file_id,)
            ).fetchone()
            conn.close()
            if not row:
                self.signals.error.emit("File not found in database.")
                return

            data = bytes(row["file_data"])
            if row["compressed"] and self.extract:
                buf = io.BytesIO(data)
                with zipfile.ZipFile(buf, "r") as zf:
                    names = zf.namelist()
                    data = zf.read(names[0])

            with open(self.save_path, "wb") as f:
                f.write(data)
            self.signals.done.emit(self.save_path)
        except Exception as e:
            self.signals.error.emit(str(e))


# ── Style constants ───────────────────────────────────────────────────────────

_BTN_PRIMARY = """
    QPushButton {
        background: #00BFA5; color: #000;
        border: none; border-radius: 6px;
        padding: 7px 16px; font-size: 13px; font-weight: bold;
    }
    QPushButton:hover   { background: #00D4B8; }
    QPushButton:pressed { background: #009E8D; }
    QPushButton:disabled{ background: #3E3E3E; color: #666; }
"""

_BTN_DANGER = """
    QPushButton {
        background: #C62828; color: #FFF;
        border: none; border-radius: 6px;
        padding: 7px 16px; font-size: 13px; font-weight: bold;
    }
    QPushButton:hover   { background: #E53935; }
    QPushButton:pressed { background: #B71C1C; }
    QPushButton:disabled{ background: #3E3E3E; color: #666; }
"""

_BTN_NEUTRAL = """
    QPushButton {
        background: #37474F; color: #EEE;
        border: none; border-radius: 6px;
        padding: 7px 16px; font-size: 13px;
    }
    QPushButton:hover   { background: #455A64; }
    QPushButton:pressed { background: #263238; }
    QPushButton:disabled{ background: #3E3E3E; color: #666; }
"""

_GROUP_STYLE = """
    QGroupBox {
        color: #AAAAAA; font-size: 12px;
        border: 1px solid #3E3E3E; border-radius: 7px;
        margin-top: 6px; padding-top: 10px;
    }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
"""

_TABLE_STYLE = """
    QTableWidget {
        background: #1E1E1E; color: #EEEEEE;
        gridline-color: #2D2D2D;
        border: 1px solid #3E3E3E; border-radius: 6px;
        selection-background-color: #1A3A35;
    }
    QHeaderView::section {
        background: #252526; color: #AAAAAA;
        padding: 6px; border: none; border-bottom: 1px solid #3E3E3E;
        font-size: 12px;
    }
    QTableWidget::item { padding: 4px 6px; }
"""


# ── Download dialog ───────────────────────────────────────────────────────────

class _DownloadDialog(QDialog):
    """Ask user whether to extract or save as ZIP (for compressed files)."""

    def __init__(self, filename: str, compressed: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Options")
        self.setModal(True)
        self.setFixedWidth(360)
        self.setStyleSheet("background: #1E1E1E; color: #EEEEEE;")
        self.extract = True

        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.addWidget(QLabel(f"<b>{filename}</b>"))

        if compressed:
            lay.addWidget(QLabel("This file is stored compressed. How would you like to save it?"))
            self._rb_extract = QRadioButton("Extract and save original file")
            self._rb_zip = QRadioButton("Save as ZIP archive")
            self._rb_extract.setChecked(True)
            for rb in (self._rb_extract, self._rb_zip):
                rb.setStyleSheet("color: #CCCCCC;")
                lay.addWidget(rb)
        else:
            lay.addWidget(QLabel("Save the file to disk."))
            self._rb_extract = None

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet("""
            QPushButton { background: #2D2D2D; color: #EEE;
                border: 1px solid #3E3E3E; border-radius: 5px; padding: 5px 14px; }
            QPushButton:hover { background: #00BFA5; color: #000; }
        """)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _on_accept(self):
        if self._rb_extract:
            self.extract = self._rb_extract.isChecked()
        self.accept()


# ── Preview panel ─────────────────────────────────────────────────────────────

class _PreviewPanel(QWidget):
    """Right-hand panel that shows a preview of the selected DB file."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        hdr = QLabel("Preview")
        hdr.setFont(QFont("Segoe UI", 13, QFont.Bold))
        hdr.setStyleSheet("color: #CCCCCC;")
        lay.addWidget(hdr)

        self._info_lbl = QLabel("Select a file from the list to preview.")
        self._info_lbl.setWordWrap(True)
        self._info_lbl.setStyleSheet("color: #888888; font-size: 12px;")
        lay.addWidget(self._info_lbl)

        # Image preview
        self._img_scroll = QScrollArea()
        self._img_scroll.setWidgetResizable(True)
        self._img_scroll.setFrameShape(QFrame.NoFrame)
        self._img_scroll.setStyleSheet("background: #121212;")
        self._img_lbl = QLabel(alignment=Qt.AlignCenter)
        self._img_lbl.setStyleSheet("background: transparent;")
        self._img_scroll.setWidget(self._img_lbl)
        self._img_scroll.hide()
        lay.addWidget(self._img_scroll, stretch=1)

        # Text preview
        self._txt_edit = QTextEdit()
        self._txt_edit.setReadOnly(True)
        self._txt_edit.setFont(QFont("Courier New", 10))
        self._txt_edit.setStyleSheet("""
            QTextEdit {
                background: #121212; color: #CCCCCC;
                border: 1px solid #3E3E3E; border-radius: 5px;
            }
        """)
        self._txt_edit.hide()
        lay.addWidget(self._txt_edit, stretch=1)

        # Unsupported placeholder
        self._unsupported = QLabel()
        self._unsupported.setAlignment(Qt.AlignCenter)
        self._unsupported.setWordWrap(True)
        self._unsupported.setStyleSheet("color: #555555; font-size: 12px;")
        self._unsupported.hide()
        lay.addWidget(self._unsupported, stretch=1)

    def clear(self):
        self._img_scroll.hide()
        self._txt_edit.hide()
        self._unsupported.hide()
        self._info_lbl.setText("Select a file from the list to preview.")

    def show_file(self, row: sqlite3.Row):
        """Decode and render a stored_files row."""
        self._img_scroll.hide()
        self._txt_edit.hide()
        self._unsupported.hide()

        fname      = row["filename"]
        orig_size  = row["original_size"]
        mime       = row["mime_type"]
        compressed = bool(row["compressed"])
        data       = bytes(row["file_data"])

        # In-memory decompression for preview (never written to disk)
        preview_data = data
        if compressed:
            try:
                buf = io.BytesIO(data)
                with zipfile.ZipFile(buf, "r") as zf:
                    preview_data = zf.read(zf.namelist()[0])
            except Exception:
                preview_data = None

        # Info header
        comp_tag = " 🗜 (compressed)" if compressed else ""
        self._info_lbl.setText(
            f"<b>{fname}</b>{comp_tag}<br>"
            f"Size: {_fmt_size(orig_size)}  |  Type: {mime}"
        )

        if preview_data is None:
            self._show_unsupported(fname, orig_size, mime, "Could not decompress for preview.")
            return

        # Image
        if mime and mime.startswith("image/"):
            pix = QPixmap()
            ok = pix.loadFromData(QByteArray(preview_data))
            if ok:
                scaled = pix.scaled(
                    500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self._img_lbl.setPixmap(scaled)
                self._img_scroll.show()
                return

        # Text
        text_types = ("text/", "application/json", "application/xml",
                      "application/javascript", "application/x-sh")
        is_text = mime and any(mime.startswith(t) for t in text_types)
        if not is_text:
            ext = os.path.splitext(fname)[1].lower()
            is_text = ext in (
                ".txt", ".md", ".py", ".js", ".ts", ".html", ".css",
                ".json", ".xml", ".yaml", ".yml", ".csv", ".log",
                ".sh", ".bat", ".ini", ".cfg", ".toml", ".rs", ".go", ".c", ".cpp", ".h",
            )
        if is_text:
            try:
                text = preview_data.decode("utf-8", errors="replace")
                self._txt_edit.setPlainText(text[:50_000])  # cap at 50 KiB
                self._txt_edit.show()
                return
            except Exception:
                pass

        # Unsupported
        self._show_unsupported(fname, orig_size, mime, "Preview not supported for this file type.")

    def _show_unsupported(self, fname, size, mime, reason):
        self._unsupported.setText(
            f"📄 {fname}\n\n"
            f"Size: {_fmt_size(size)}\n"
            f"Type: {mime or 'Unknown'}\n\n"
            f"{reason}"
        )
        self._unsupported.show()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ── Main Widget ───────────────────────────────────────────────────────────────

class DBFileStorageTool(QWidget):
    name = "Database File Storage"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._upload_worker = None
        self._download_worker = None
        self._rows: list[sqlite3.Row] = []
        self._build_ui()
        self._refresh_table()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # Title
        title = QLabel("🗄️  Database File Storage")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        root.addWidget(title)

        # ── Upload section ────────────────────────────────────────────────────
        upload_box = QGroupBox("Upload Files")
        upload_box.setStyleSheet(_GROUP_STYLE)
        ub_lay = QVBoxLayout(upload_box)

        row1 = QHBoxLayout()
        self._selected_lbl = QLabel("No files selected.")
        self._selected_lbl.setStyleSheet("color: #888888; font-size: 12px;")
        row1.addWidget(self._selected_lbl, stretch=1)

        btn_pick = QPushButton("+ Select Files")
        btn_pick.setStyleSheet(_BTN_NEUTRAL)
        btn_pick.clicked.connect(self._pick_files)
        row1.addWidget(btn_pick)
        ub_lay.addLayout(row1)

        row2 = QHBoxLayout()
        self._chk_compress = QCheckBox("Compress before storing (ZIP)")
        self._chk_compress.setStyleSheet("color: #CCCCCC; font-size: 13px;")
        row2.addWidget(self._chk_compress)
        row2.addStretch()

        self._btn_upload = QPushButton("⬆  Upload")
        self._btn_upload.setStyleSheet(_BTN_PRIMARY)
        self._btn_upload.setEnabled(False)
        self._btn_upload.clicked.connect(self._start_upload)
        row2.addWidget(self._btn_upload)
        ub_lay.addLayout(row2)

        self._upload_progress = QProgressBar()
        self._upload_progress.setRange(0, 100)
        self._upload_progress.setValue(0)
        self._upload_progress.setFixedHeight(18)
        self._upload_progress.setTextVisible(False)
        self._upload_progress.setStyleSheet("""
            QProgressBar {
                background: #2D2D2D; border: 1px solid #3E3E3E;
                border-radius: 4px;
            }
            QProgressBar::chunk { background: #00BFA5; border-radius: 3px; }
        """)
        ub_lay.addWidget(self._upload_progress)
        self._upload_status = QLabel("")
        self._upload_status.setStyleSheet("color: #888; font-size: 11px;")
        ub_lay.addWidget(self._upload_status)
        root.addWidget(upload_box)

        # ── File list + preview splitter ──────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet("QSplitter::handle { background: #3E3E3E; }")

        # Left: file table
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)

        list_hdr = QHBoxLayout()
        list_title = QLabel("Stored Files")
        list_title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        list_title.setStyleSheet("color: #CCCCCC;")
        list_hdr.addWidget(list_title)
        list_hdr.addStretch()

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setStyleSheet(_BTN_NEUTRAL)
        btn_refresh.setFixedHeight(30)
        btn_refresh.clicked.connect(self._refresh_table)
        list_hdr.addWidget(btn_refresh)

        self._btn_download = QPushButton("⬇  Download")
        self._btn_download.setStyleSheet(_BTN_PRIMARY)
        self._btn_download.setFixedHeight(30)
        self._btn_download.setEnabled(False)
        self._btn_download.clicked.connect(self._start_download)
        list_hdr.addWidget(self._btn_download)

        self._btn_delete = QPushButton("🗑  Delete")
        self._btn_delete.setStyleSheet(_BTN_DANGER)
        self._btn_delete.setFixedHeight(30)
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._delete_selected)
        list_hdr.addWidget(self._btn_delete)

        ll.addLayout(list_hdr)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Filename", "Original Size", "Stored Size", "Compressed", "Uploaded At"]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setStyleSheet(_TABLE_STYLE)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 40)
        self._table.setColumnWidth(2, 100)
        self._table.setColumnWidth(3, 100)
        self._table.setColumnWidth(4, 90)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        ll.addWidget(self._table)

        splitter.addWidget(left)

        # Right: preview
        self._preview = _PreviewPanel()
        self._preview.setMinimumWidth(220)
        splitter.addWidget(self._preview)
        splitter.setSizes([560, 300])

        root.addWidget(splitter, stretch=1)

        self._pending_files: list[str] = []

    # ── Actions ───────────────────────────────────────────────────────────────

    def _pick_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Files to Upload")
        if paths:
            self._pending_files = paths
            names = [os.path.basename(p) for p in paths]
            self._selected_lbl.setText(", ".join(names))
            self._btn_upload.setEnabled(True)
        else:
            self._pending_files = []
            self._selected_lbl.setText("No files selected.")
            self._btn_upload.setEnabled(False)

    def _start_upload(self):
        if not self._pending_files:
            return
        compress = self._chk_compress.isChecked()
        self._upload_worker = _UploadWorker(list(self._pending_files), compress)
        self._upload_worker.signals.progress.connect(self._on_upload_progress)
        self._upload_worker.signals.done.connect(self._on_upload_done)
        self._upload_worker.signals.error.connect(
            lambda e: self._upload_status.setText(f"⚠ {e}")
        )
        self._upload_worker.start()
        self._btn_upload.setEnabled(False)

    def _on_upload_progress(self, done: int, total: int, label: str):
        pct = int(done / total * 100) if total else 0
        self._upload_progress.setValue(pct)
        self._upload_status.setText(label)

    def _on_upload_done(self, inserted: int):
        self._upload_progress.setValue(100)
        self._upload_status.setText(f"✅ {inserted} file(s) uploaded successfully.")
        self._pending_files = []
        self._selected_lbl.setText("No files selected.")
        self._btn_upload.setEnabled(False)
        self._refresh_table()

    def _refresh_table(self):
        conn = _get_conn()
        self._rows = conn.execute(
            "SELECT id, filename, original_size, stored_size, compressed, uploaded_at "
            "FROM stored_files ORDER BY uploaded_at DESC"
        ).fetchall()
        conn.close()

        self._table.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
            comp = "🗜 Yes" if row["compressed"] else "No"
            values = [
                str(row["id"]),
                row["filename"],
                _fmt_size(row["original_size"]),
                _fmt_size(row["stored_size"]),
                comp,
                row["uploaded_at"][:16] if row["uploaded_at"] else "",
            ]
            for c, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setForeground(QColor("#EEEEEE"))
                if c == 4 and row["compressed"]:
                    item.setForeground(QColor("#FFB74D"))
                self._table.setItem(r, c, item)

        self._btn_download.setEnabled(False)
        self._btn_delete.setEnabled(False)
        self._preview.clear()

    def _on_selection_changed(self):
        selected = self._table.selectedItems()
        has_sel = bool(selected)
        self._btn_download.setEnabled(has_sel)
        self._btn_delete.setEnabled(has_sel)

        if not has_sel:
            self._preview.clear()
            return

        row_idx = self._table.currentRow()
        if row_idx < 0 or row_idx >= len(self._rows):
            return

        # Load full row (with file_data) for preview
        file_id = self._rows[row_idx]["id"]
        conn = _get_conn()
        full_row = conn.execute(
            "SELECT * FROM stored_files WHERE id=?", (file_id,)
        ).fetchone()
        conn.close()
        if full_row:
            self._preview.show_file(full_row)

    def _start_download(self):
        row_idx = self._table.currentRow()
        if row_idx < 0:
            return
        row = self._rows[row_idx]
        file_id    = row["id"]
        fname      = row["filename"]
        compressed = bool(row["compressed"])

        # Show dialog
        dlg = _DownloadDialog(fname, compressed, self)
        if dlg.exec() != QDialog.Accepted:
            return
        extract = dlg.extract

        # Pick save path
        if compressed and not extract:
            base, _ = os.path.splitext(fname)
            default_name = base + ".zip"
            filter_str = "ZIP Archive (*.zip)"
        else:
            default_name = fname
            filter_str = "All Files (*)"

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save File As", os.path.join(os.path.expanduser("~"), default_name), filter_str
        )
        if not save_path:
            return

        self._download_worker = _DownloadWorker(file_id, save_path, extract)
        self._download_worker.signals.done.connect(
            lambda p: QMessageBox.information(self, "Download Complete", f"Saved to:\n{p}")
        )
        self._download_worker.signals.error.connect(
            lambda e: QMessageBox.critical(self, "Download Error", e)
        )
        self._download_worker.start()

    def _delete_selected(self):
        row_idx = self._table.currentRow()
        if row_idx < 0:
            return
        row = self._rows[row_idx]
        fname = row["filename"]
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{fname}' from the database?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        conn = _get_conn()
        conn.execute("DELETE FROM stored_files WHERE id=?", (row["id"],))
        conn.commit()
        conn.close()
        self._refresh_table()
