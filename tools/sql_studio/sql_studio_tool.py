"""SQL Studio — lightweight SQLite management like SSMS: tree, editor, results, CSV export."""
import sqlite3, csv, os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTreeWidget, QTreeWidgetItem, QPlainTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
    QFileDialog, QMessageBox, QMenu, QTabWidget, QLineEdit,
    QApplication, QStatusBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor, QAction


class _QueryWorker(QThread):
    result = Signal(list, list)   # rows, columns
    error  = Signal(str)
    def __init__(self, db_path, sql):
        super().__init__(); self._db = db_path; self._sql = sql
    def run(self):
        try:
            conn = sqlite3.connect(self._db)
            conn.row_factory = sqlite3.Row
            cur = conn.execute(self._sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = [list(r) for r in cur.fetchall()]
            conn.close()
            self.result.emit(rows, cols)
        except Exception as e:
            self.error.emit(str(e))


class SQLStudioTool(QWidget):
    name        = "SQL Studio"
    description = "SQLite database management — query, browse, export"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db_path = None
        self._worker  = None
        self._last_rows = []
        self._last_cols = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E;border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20, 10, 20, 10)
        t = QLabel("🗄️ SQL Studio"); t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;"); hl.addWidget(t); hl.addStretch()

        open_btn = QPushButton("📂  Open Database")
        open_btn.setFixedHeight(34)
        open_btn.setStyleSheet(
            "background:#00BFA5;color:#000;border:none;border-radius:6px;"
            "font-weight:bold;padding:0 16px;")
        open_btn.clicked.connect(self._open_db)
        hl.addWidget(open_btn)

        new_btn = QPushButton("✨  New DB")
        new_btn.setFixedHeight(34)
        new_btn.setStyleSheet("background:#3A3A3A;color:#E0E0E0;border:none;border-radius:6px;padding:0 12px;")
        new_btn.clicked.connect(self._new_db)
        hl.addWidget(new_btn)

        self._db_lbl = QLabel("No database open")
        self._db_lbl.setStyleSheet("color:#555;font-size:11px;")
        hl.addWidget(self._db_lbl)
        root.addWidget(hdr)

        # Main splitter: tree | editor+results
        main_split = QSplitter(Qt.Horizontal)
        main_split.setHandleWidth(2)
        main_split.setStyleSheet("QSplitter::handle{background:#2A2A2A;}")

        # LEFT — schema tree
        left = QWidget(); left.setStyleSheet("background:#1A1A1A;")
        ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0); ll.setSpacing(0)

        refresh_btn = QPushButton("🔄 Refresh Schema")
        refresh_btn.setFixedHeight(30)
        refresh_btn.setStyleSheet("background:#252525;color:#888;border:none;font-size:11px;")
        refresh_btn.clicked.connect(self._load_schema)
        ll.addWidget(refresh_btn)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setStyleSheet("""
            QTreeWidget { background:#1A1A1A; border:none; font-size:12px; color:#CCC; }
            QTreeWidget::item { padding:3px 6px; }
            QTreeWidget::item:selected { background:#00BFA5; color:#000; }
            QTreeWidget::item:hover:!selected { background:#252525; }
        """)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._tree_context)
        ll.addWidget(self._tree, 1)
        main_split.addWidget(left)

        # RIGHT — editor + results (vertical split)
        right_split = QSplitter(Qt.Vertical)
        right_split.setHandleWidth(2)
        right_split.setStyleSheet("QSplitter::handle{background:#2A2A2A;}")

        # SQL editor
        editor_frame = QFrame(); editor_frame.setStyleSheet("background:#1E1E1E;")
        ef = QVBoxLayout(editor_frame); ef.setContentsMargins(0, 0, 0, 0); ef.setSpacing(0)

        editor_hdr = QWidget(); editor_hdr.setStyleSheet("background:#252525;")
        eh = QHBoxLayout(editor_hdr); eh.setContentsMargins(8, 4, 8, 4); eh.setSpacing(8)
        eh.addWidget(QLabel("SQL Editor", styleSheet="color:#888;font-size:11px;"))
        eh.addStretch()

        run_btn = QPushButton("▶  Run (F5)")
        run_btn.setFixedHeight(26)
        run_btn.setStyleSheet(
            "background:#00BFA5;color:#000;border:none;border-radius:5px;"
            "font-weight:bold;font-size:11px;padding:0 12px;")
        run_btn.clicked.connect(self._run_query)
        eh.addWidget(run_btn)

        clear_btn = QPushButton("🗑 Clear")
        clear_btn.setFixedHeight(26)
        clear_btn.setStyleSheet("background:#3A3A3A;color:#888;border:none;border-radius:5px;font-size:11px;padding:0 10px;")
        clear_btn.clicked.connect(lambda: self._editor.clear())
        eh.addWidget(clear_btn)

        export_btn = QPushButton("📊 Export CSV")
        export_btn.setFixedHeight(26)
        export_btn.setStyleSheet("background:#3A3A3A;color:#888;border:none;border-radius:5px;font-size:11px;padding:0 10px;")
        export_btn.clicked.connect(self._export_csv)
        eh.addWidget(export_btn)
        ef.addWidget(editor_hdr)

        self._editor = QPlainTextEdit()
        self._editor.setPlaceholderText("SELECT * FROM your_table LIMIT 100;")
        self._editor.setFont(QFont("Courier New", 12))
        self._editor.setStyleSheet(
            "QPlainTextEdit{background:#0D0D0D;color:#E0E0E0;border:none;"
            "padding:10px;selection-background-color:#00BFA5;selection-color:#000;}")
        self._editor.setTabStopDistance(40)
        ef.addWidget(self._editor, 1)
        right_split.addWidget(editor_frame)

        # Results
        result_frame = QFrame(); result_frame.setStyleSheet("background:#151515;")
        rf = QVBoxLayout(result_frame); rf.setContentsMargins(0, 0, 0, 0); rf.setSpacing(0)

        result_hdr = QWidget(); result_hdr.setStyleSheet("background:#252525;")
        rh = QHBoxLayout(result_hdr); rh.setContentsMargins(8, 4, 8, 4)
        self._result_lbl = QLabel("Results", styleSheet="color:#888;font-size:11px;")
        rh.addWidget(self._result_lbl); rh.addStretch()
        rf.addWidget(result_hdr)

        self._result_table = QTableWidget(0, 0)
        self._result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._result_table.verticalHeader().setVisible(False)
        self._result_table.setStyleSheet(
            "QTableWidget{background:#1A1A1A;border:none;font-size:12px;}"
            "QHeaderView::section{background:#252525;color:#888;border:none;padding:5px;}"
            "QTableWidget::item{padding:3px 8px;}")
        self._result_table.horizontalHeader().setStretchLastSection(True)
        rf.addWidget(self._result_table, 1)

        self._status_bar = QLabel("Open a SQLite database to begin")
        self._status_bar.setStyleSheet(
            "background:#1E1E1E;color:#555;font-size:11px;padding:4px 12px;"
            "border-top:1px solid #2A2A2A;")
        rf.addWidget(self._status_bar)
        right_split.addWidget(result_frame)
        right_split.setSizes([300, 400])

        main_split.addWidget(right_split)
        main_split.setSizes([220, 800])
        root.addWidget(main_split, 1)

        # F5 shortcut
        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("F5"), self).activated.connect(self._run_query)

    # ── DB operations ─────────────────────────────────────────────────────────
    def _open_db(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open SQLite Database", "", "SQLite (*.db *.sqlite *.sqlite3);;All (*)")
        if path:
            self._db_path = path
            self._db_lbl.setText(os.path.basename(path))
            self._db_lbl.setStyleSheet("color:#00BFA5;font-size:11px;")
            self._load_schema()
            self._status_bar.setText(f"Opened: {path}")

    def _new_db(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "New SQLite Database", "new.db", "SQLite (*.db)")
        if path:
            sqlite3.connect(path).close()
            self._db_path = path
            self._db_lbl.setText(os.path.basename(path))
            self._db_lbl.setStyleSheet("color:#00BFA5;font-size:11px;")
            self._load_schema()

    def _load_schema(self):
        if not self._db_path: return
        self._tree.clear()
        try:
            conn = sqlite3.connect(self._db_path)
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            views = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
            ).fetchall()

            for section, items, icon in [("📋 Tables", tables, "📄"), ("👁 Views", views, "👁")]:
                if not items: continue
                sec_item = QTreeWidgetItem([section])
                sec_item.setForeground(0, QColor("#888"))
                sec_item.setFont(0, QFont("Segoe UI", 11, QFont.Bold))
                self._tree.addTopLevelItem(sec_item)
                for (tbl,) in items:
                    t_item = QTreeWidgetItem([f"{icon}  {tbl}"])
                    t_item.setData(0, Qt.UserRole, tbl)
                    t_item.setForeground(0, QColor("#E0E0E0"))
                    # Columns
                    cols = conn.execute(f"PRAGMA table_info('{tbl}')").fetchall()
                    for col in cols:
                        cname, ctype = col[1], col[2]
                        c_item = QTreeWidgetItem([f"  🔹 {cname}  ({ctype})"])
                        c_item.setForeground(0, QColor("#555"))
                        c_item.setFont(0, QFont("Courier New", 10))
                        t_item.addChild(c_item)
                    sec_item.addChild(t_item)
                sec_item.setExpanded(True)
            conn.close()
            self._status_bar.setText(f"Schema loaded — {len(tables)} table(s), {len(views)} view(s)")
        except Exception as e:
            self._status_bar.setText(f"❌ Schema error: {e}")

    def _tree_context(self, pos):
        item = self._tree.itemAt(pos)
        if not item or not item.data(0, Qt.UserRole): return
        tbl = item.data(0, Qt.UserRole)
        menu = QMenu(self)
        menu.addAction(f"SELECT TOP 100", lambda: self._insert_sql(f"SELECT * FROM \"{tbl}\" LIMIT 100;"))
        menu.addAction(f"SELECT *",        lambda: self._insert_sql(f"SELECT * FROM \"{tbl}\";"))
        menu.addAction(f"COUNT rows",      lambda: self._insert_sql(f"SELECT COUNT(*) FROM \"{tbl}\";"))
        menu.addAction(f"View structure",  lambda: self._insert_sql(f"PRAGMA table_info('{tbl}');"))
        menu.addSeparator()
        menu.addAction(f"DROP TABLE",      lambda: self._drop_table(tbl))
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _insert_sql(self, sql):
        self._editor.setPlainText(sql)
        self._run_query()

    def _drop_table(self, tbl):
        if QMessageBox.question(self, "Drop Table", f"DROP TABLE '{tbl}'?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._editor.setPlainText(f'DROP TABLE "{tbl}";')
            self._run_query()

    def _run_query(self):
        if not self._db_path:
            self._status_bar.setText("❌ No database open"); return
        sql = self._editor.toPlainText().strip()
        if not sql: return
        self._status_bar.setText("⏳ Running…")
        self._result_table.setRowCount(0); self._result_table.setColumnCount(0)
        self._worker = _QueryWorker(self._db_path, sql)
        self._worker.result.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, rows, cols):
        self._last_rows = rows; self._last_cols = cols
        t = self._result_table
        t.setColumnCount(len(cols))
        t.setHorizontalHeaderLabels(cols)
        t.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val) if val is not None else "NULL")
                if val is None: item.setForeground(QColor("#555"))
                t.setItem(r, c, item)
        t.resizeColumnsToContents()
        self._result_lbl.setText(f"Results  ({len(rows)} row{'s' if len(rows) != 1 else ''})")
        self._status_bar.setText(f"✅ {len(rows)} row(s) returned")
        self._load_schema()   # refresh if DDL was executed

    def _on_error(self, err):
        self._status_bar.setText(f"❌ {err}")
        self._result_lbl.setText("Error")

    def _export_csv(self):
        if not self._last_cols:
            QMessageBox.information(self, "No data", "Run a query first."); return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "results.csv", "CSV (*.csv)")
        if not path: return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(self._last_cols)
            w.writerows(self._last_rows)
        self._status_bar.setText(f"💾 Exported {len(self._last_rows)} row(s) → {path}")
