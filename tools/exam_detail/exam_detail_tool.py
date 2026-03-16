"""
Exam Detail Tool
================
Left panel  — list of past exams (filter by type)
Right panel — tabbed entry for each section (subject):
                • Section totals  (correct / incorrect / empty / net auto-calc)
                • Topic breakdown — pre-loaded from EXAM_DEFS, editable
                • Wrong questions tab — photo upload, link to lesson, topic tag

Key design rules:
  • Subjects and topics are NEVER typed — chosen from EXAM_DEFS dropdowns
    (custom "Özel/Diğer" type lets the user add free-text subjects)
  • Lessons pulled live from study_lessons via LessonsService
  • Net = correct − 0.25 × incorrect, shown in real-time
  • Everything encrypted at rest via ExamDetailService
"""

import base64

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QDialogButtonBox, QFormLayout, QLineEdit, QComboBox, QSpinBox,
    QTextEdit, QScrollArea, QFileDialog, QMessageBox, QGridLayout,
    QSizePolicy, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor, QPixmap

from core.auth_manager import auth_manager
from tools.study_lessons.study_service import LessonsService
from tools.exam_detail.exam_detail_service import ExamDetailService, EXAM_DEFS

PALETTE = [
    "#00BFA5", "#FF9800", "#9C27B0", "#F44336",
    "#2196F3", "#4CAF50", "#FF5722", "#607D8B",
]


def _net(c, i):
    return round(c - i * 0.25, 2)

def _pct(c, total):
    return round(c / max(total, 1) * 100, 1)

def _color_net(n):
    return "#4CAF50" if n > 0 else ("#F44336" if n < 0 else "#888")

def _color_pct(p):
    return "#4CAF50" if p >= 70 else ("#FF9800" if p >= 45 else "#F44336")


# ── New Exam Dialog ────────────────────────────────────────────────────────────
class NewExamDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Sınav Ekle")
        self.setFixedWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self.type_combo = QComboBox()
        self.type_combo.addItems(list(EXAM_DEFS.keys()))
        form.addRow("Sınav Türü:", self.type_combo)

        self.date_edit = QLineEdit(QDate.currentDate().toString("yyyy-MM-dd"))
        form.addRow("Tarih (YYYY-AA-GG):", self.date_edit)

        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("örn. 2024 TYT, Palme Deneme #5 …")
        form.addRow("Kaynak / Etiket:", self.source_edit)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Genel notlar (opsiyonel)…")
        self.notes_edit.setFixedHeight(60)
        form.addRow("Notlar:", self.notes_edit)

        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def get_data(self):
        return {
            "type":   self.type_combo.currentText(),
            "date":   self.date_edit.text().strip(),
            "source": self.source_edit.text().strip(),
            "notes":  self.notes_edit.toPlainText().strip(),
        }


# ── TopicRow ──────────────────────────────────────────────────────────────────
class TopicRow(QWidget):
    """One row: topic name | D spin | Y spin | B spin | net label."""

    def __init__(self, topic_name: str, correct=0, incorrect=0, empty=0, parent=None):
        super().__init__(parent)
        self.topic_name = topic_name
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(6)

        name = QLabel(topic_name)
        name.setMinimumWidth(200)
        name.setStyleSheet("color:#CCCCCC; font-size:13px;")
        lay.addWidget(name, 3)

        self.d_spin = QSpinBox(); self.d_spin.setRange(0, 200); self.d_spin.setFixedWidth(62)
        self.y_spin = QSpinBox(); self.y_spin.setRange(0, 200); self.y_spin.setFixedWidth(62)
        self.b_spin = QSpinBox(); self.b_spin.setRange(0, 200); self.b_spin.setFixedWidth(62)
        self.d_spin.setValue(correct); self.y_spin.setValue(incorrect); self.b_spin.setValue(empty)
        for s in (self.d_spin, self.y_spin, self.b_spin):
            s.valueChanged.connect(self._refresh_net)
        lay.addWidget(self.d_spin)
        lay.addWidget(self.y_spin)
        lay.addWidget(self.b_spin)

        self.net_lbl = QLabel("0")
        self.net_lbl.setFixedWidth(52)
        self.net_lbl.setAlignment(Qt.AlignCenter)
        self.net_lbl.setStyleSheet("font-weight:bold; font-size:12px;")
        lay.addWidget(self.net_lbl)
        self._refresh_net()

    def _refresh_net(self):
        n = _net(self.d_spin.value(), self.y_spin.value())
        self.net_lbl.setText(str(n))
        self.net_lbl.setStyleSheet(f"color:{_color_net(n)}; font-weight:bold; font-size:12px;")

    def values(self):
        return self.d_spin.value(), self.y_spin.value(), self.b_spin.value()


# ── Section tab ───────────────────────────────────────────────────────────────
class SectionTab(QWidget):
    """One tab per subject. Top summary row + scrollable topic rows below."""

    def __init__(self, subject: str, total_q: int, topics: list,
                 existing_section=None, existing_topics=None, parent=None):
        super().__init__(parent)
        self.subject  = subject
        self.total_q  = total_q
        self._rows: list[TopicRow] = []
        self._build(topics, existing_section, existing_topics)

    def _build(self, topics, ex_sec, ex_tops):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ── Summary card ───────────────────────────────────────────────────────
        card = QFrame()
        card.setStyleSheet("background:#252525; border-radius:8px;")
        cl = QGridLayout(card)
        cl.setContentsMargins(16, 10, 16, 10)
        cl.setSpacing(8)

        title = QLabel(f"<b>{self.subject}</b>")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet("color:#00BFA5; background:transparent;")
        cl.addWidget(title, 0, 0, 1, 2)

        total_lbl = QLabel(f"Toplam soru: {self.total_q}")
        total_lbl.setStyleSheet("color:#888; font-size:11px; background:transparent;")
        cl.addWidget(total_lbl, 0, 2, 1, 2, Qt.AlignRight)

        for col, txt in enumerate(["", "✅ Doğru", "❌ Yanlış", "⬜ Boş", "Net", "% Başarı"]):
            h = QLabel(txt)
            h.setAlignment(Qt.AlignCenter)
            h.setStyleSheet("color:#555; font-size:11px; font-weight:bold; background:transparent;")
            cl.addWidget(h, 1, col)

        cl.addWidget(QLabel("Bölüm toplamı:", styleSheet="color:#AAA; background:transparent;"), 2, 0)
        self.tot_d = QSpinBox(); self.tot_d.setRange(0, 999); self.tot_d.setFixedWidth(65)
        self.tot_y = QSpinBox(); self.tot_y.setRange(0, 999); self.tot_y.setFixedWidth(65)
        self.tot_b = QSpinBox(); self.tot_b.setRange(0, 999); self.tot_b.setFixedWidth(65)
        self.tot_net = QLabel("0"); self.tot_net.setFixedWidth(52); self.tot_net.setAlignment(Qt.AlignCenter)
        self.tot_pct = QLabel("0%"); self.tot_pct.setFixedWidth(52); self.tot_pct.setAlignment(Qt.AlignCenter)
        for spin in (self.tot_d, self.tot_y, self.tot_b):
            spin.valueChanged.connect(self._refresh_summary)
        if ex_sec:
            self.tot_d.setValue(ex_sec.get("correct", 0))
            self.tot_y.setValue(ex_sec.get("incorrect", 0))
            self.tot_b.setValue(ex_sec.get("empty", 0))
        for col, w in enumerate([self.tot_d, self.tot_y, self.tot_b,
                                   self.tot_net, self.tot_pct], start=1):
            cl.addWidget(w, 2, col)
        root.addWidget(card)
        self._refresh_summary()

        # ── Topic table ────────────────────────────────────────────────────────
        topic_frame = QFrame()
        topic_frame.setStyleSheet("background:#1C1C1C; border-radius:8px;")
        tf = QVBoxLayout(topic_frame)
        tf.setContentsMargins(8, 6, 8, 6)
        tf.setSpacing(0)

        # header row
        hdr = QHBoxLayout()
        for txt, width in [("Konu", 200), ("✅ D", 62), ("❌ Y", 62), ("⬜ B", 62), ("Net", 52)]:
            h = QLabel(txt)
            h.setMinimumWidth(width); h.setAlignment(Qt.AlignCenter)
            h.setStyleSheet("color:#555; font-size:11px; font-weight:bold;")
            hdr.addWidget(h)
        tf.addLayout(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:#2A2A2A; margin:2px 0;")
        tf.addWidget(sep)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 0, 0, 0); inner_lay.setSpacing(1)

        # map existing topic scores
        ex_map = {}
        if ex_tops:
            for t in ex_tops:
                ex_map[t["topic"]] = t

        for topic in topics:
            ex = ex_map.get(topic, {})
            row = TopicRow(topic, ex.get("correct", 0), ex.get("incorrect", 0), ex.get("empty", 0))
            row.setStyleSheet("background:transparent; border-bottom:1px solid #252525;")
            inner_lay.addWidget(row)
            self._rows.append(row)

        inner_lay.addStretch()

        # add custom topic
        add_row_w = QWidget(); add_row_w.setStyleSheet("background:transparent;")
        add_row = QHBoxLayout(add_row_w); add_row.setContentsMargins(4, 4, 4, 4)
        self._custom_edit = QLineEdit(); self._custom_edit.setPlaceholderText("Özel konu adı gir…")
        self._custom_edit.setFixedWidth(200)
        add_btn = QPushButton("➕ Ekle"); add_btn.setFixedWidth(80)
        add_btn.clicked.connect(self._add_custom_topic)
        add_row.addWidget(self._custom_edit); add_row.addWidget(add_btn); add_row.addStretch()
        inner_lay.addWidget(add_row_w)

        scroll.setWidget(inner)
        tf.addWidget(scroll, 1)
        root.addWidget(topic_frame, 1)
        self._inner_lay = inner_lay

    def _add_custom_topic(self):
        name = self._custom_edit.text().strip()
        if not name:
            return
        row = TopicRow(name)
        row.setStyleSheet("background:transparent; border-bottom:1px solid #252525;")
        # insert before last 2 items (stretch + add_row_w)
        idx = self._inner_lay.count() - 2
        self._inner_lay.insertWidget(idx, row)
        self._rows.append(row)
        self._custom_edit.clear()

    def _refresh_summary(self):
        n = _net(self.tot_d.value(), self.tot_y.value())
        p = _pct(self.tot_d.value(), self.total_q)
        self.tot_net.setText(str(n))
        self.tot_pct.setText(f"{p}%")
        self.tot_net.setStyleSheet(f"color:{_color_net(n)}; font-weight:bold;")
        self.tot_pct.setStyleSheet(f"color:{_color_pct(p)}; font-weight:bold;")

    def section_data(self):
        return {
            "subject":   self.subject,
            "total_q":   self.total_q,
            "correct":   self.tot_d.value(),
            "incorrect": self.tot_y.value(),
            "empty":     self.tot_b.value(),
        }

    def topic_data(self):
        result = []
        for row in self._rows:
            c, i, e = row.values()
            if c > 0 or i > 0 or e > 0:
                result.append({"topic": row.topic_name, "correct": c,
                                "incorrect": i, "empty": e})
        return result

    def total_net(self):
        return _net(self.tot_d.value(), self.tot_y.value())


# ── Wrong Questions Tab ───────────────────────────────────────────────────────
class WrongQuestionsTab(QWidget):
    def __init__(self, svc: ExamDetailService, exam_id: int, parent=None):
        super().__init__(parent)
        self._svc = svc
        self._exam_id = exam_id
        self._lessons = svc.get_lesson_names()   # [{id, name}]
        self._build()
        self._refresh()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Add-new controls
        add_frame = QFrame()
        add_frame.setStyleSheet("background:#252525; border-radius:8px;")
        al = QGridLayout(add_frame)
        al.setContentsMargins(12, 10, 12, 10)
        al.setSpacing(8)

        al.addWidget(QLabel("Ders:", styleSheet="color:#AAA;"), 0, 0)
        self._subj_combo = QComboBox()
        self._subj_combo.setEditable(True)
        # populate from all subjects in EXAM_DEFS
        all_subjects = []
        for subs in EXAM_DEFS.values():
            all_subjects.extend(subs.keys())
        self._subj_combo.addItems(sorted(set(all_subjects)))
        self._subj_combo.currentTextChanged.connect(self._update_topic_combo)
        al.addWidget(self._subj_combo, 0, 1)

        al.addWidget(QLabel("Konu:", styleSheet="color:#AAA;"), 0, 2)
        self._topic_combo = QComboBox()
        self._topic_combo.setEditable(True)
        al.addWidget(self._topic_combo, 0, 3)

        al.addWidget(QLabel("İlgili Ders:", styleSheet="color:#AAA;"), 1, 0)
        self._lesson_combo = QComboBox()
        self._lesson_combo.addItem("— Bağlantısız —", None)
        for les in self._lessons:
            self._lesson_combo.addItem(les["name"], les["id"])
        al.addWidget(self._lesson_combo, 1, 1)

        al.addWidget(QLabel("Not:", styleSheet="color:#AAA;"), 1, 2)
        self._note_edit = QLineEdit()
        self._note_edit.setPlaceholderText("Kısa not…")
        al.addWidget(self._note_edit, 1, 3)

        self._photo_btn = QPushButton("📷 Fotoğraf Ekle")
        self._photo_btn.clicked.connect(self._pick_photo)
        al.addWidget(self._photo_btn, 2, 0, 1, 2)
        self._photo_b64 = ""

        add_btn = QPushButton("➕ Yanlış Soru Kaydet")
        add_btn.clicked.connect(self._add_wq)
        al.addWidget(add_btn, 2, 2, 1, 2)
        root.addWidget(add_frame)

        # List of wrong questions
        self._wq_table = QTableWidget(0, 5)
        self._wq_table.setHorizontalHeaderLabels(["Ders", "Konu", "İlgili Ders", "Not", "Fotoğraf"])
        self._wq_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._wq_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._wq_table.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(self._wq_table, 1)

        btn_row = QHBoxLayout()
        view_btn = QPushButton("🔍 Fotoğrafı Görüntüle")
        view_btn.clicked.connect(self._view_photo)
        btn_row.addWidget(view_btn)
        del_btn = QPushButton("🗑️ Seçili Sil")
        del_btn.setObjectName("secondary")
        del_btn.clicked.connect(self._delete_wq)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._update_topic_combo()

    def _update_topic_combo(self):
        subj = self._subj_combo.currentText()
        self._topic_combo.clear()
        self._topic_combo.addItem("")
        for exam_subs in EXAM_DEFS.values():
            if subj in exam_subs:
                self._topic_combo.addItems(exam_subs[subj]["topics"])
                break

    def _pick_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Fotoğraf Seç", "", "Görseller (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return
        ext = path.rsplit(".", 1)[-1].lower()
        with open(path, "rb") as f:
            self._photo_b64 = "data:image/" + ext + ";base64," + base64.b64encode(f.read()).decode()
        self._photo_btn.setText("✅ Fotoğraf Seçildi")
        self._photo_btn.setStyleSheet("color:#00BFA5;")

    def _add_wq(self):
        subj = self._subj_combo.currentText().strip()
        topic = self._topic_combo.currentText().strip()
        if not subj:
            QMessageBox.warning(self, "Eksik", "Ders seçin.")
            return
        les_id   = self._lesson_combo.currentData()
        les_name = self._lesson_combo.currentText() if les_id else ""
        note = self._note_edit.text().strip()
        self._svc.add_wrong_question(
            self._exam_id, subj, topic, les_id, les_name,
            self._photo_b64, note)
        self._photo_b64 = ""
        self._photo_btn.setText("📷 Fotoğraf Ekle")
        self._photo_btn.setStyleSheet("")
        self._note_edit.clear()
        self._refresh()

    def _refresh(self):
        self._wq_table.setRowCount(0)
        self._wq_data = self._svc.get_wrong_questions(self._exam_id)
        for wq in self._wq_data:
            r = self._wq_table.rowCount()
            self._wq_table.insertRow(r)
            self._wq_table.setItem(r, 0, QTableWidgetItem(wq["subject"]))
            self._wq_table.setItem(r, 1, QTableWidgetItem(wq.get("topic", "")))
            self._wq_table.setItem(r, 2, QTableWidgetItem(wq.get("lesson_name", "")))
            self._wq_table.setItem(r, 3, QTableWidgetItem(wq.get("note", "")))
            has_photo = "📷 Var" if wq.get("photo_b64") else "—"
            photo_item = QTableWidgetItem(has_photo)
            if wq.get("photo_b64"):
                photo_item.setForeground(QColor("#00BFA5"))
            self._wq_table.setItem(r, 4, photo_item)

    def _view_photo(self):
        row = self._wq_table.currentRow()
        if row < 0 or row >= len(self._wq_data):
            return
        wq = self._wq_data[row]
        if not wq.get("photo_b64"):
            QMessageBox.information(self, "Fotoğraf Yok", "Bu soru için fotoğraf eklenmemiş.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{wq['subject']} — {wq.get('topic','')}")
        lay = QVBoxLayout(dlg)
        lbl = QLabel()
        try:
            raw = wq["photo_b64"].split(",", 1)[-1]
            pix = QPixmap()
            pix.loadFromData(base64.b64decode(raw))
            lbl.setPixmap(pix.scaledToWidth(600, Qt.SmoothTransformation))
        except Exception:
            lbl.setText("Görüntülenemiyor")
        scroll = QScrollArea(); scroll.setWidget(lbl)
        lay.addWidget(scroll)
        dlg.setMinimumSize(620, 480)
        dlg.exec()

    def _delete_wq(self):
        row = self._wq_table.currentRow()
        if row < 0 or row >= len(self._wq_data):
            return
        wq = self._wq_data[row]
        if QMessageBox.question(self, "Sil", "Bu yanlış soru silinsin mi?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._svc.delete_wrong_question(wq["id"])
            self._refresh()


# ── Exam Entry Panel (right side) ─────────────────────────────────────────────
class ExamEntryPanel(QWidget):
    def __init__(self, svc: ExamDetailService, parent=None):
        super().__init__(parent)
        self._svc   = svc
        self._exam  = None
        self._sec_tabs: list[SectionTab] = []
        self._built = False
        self._build_placeholder()

    def _build_placeholder(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel(
            "← Sol listeden bir sınav seçin\n    veya ➕ ile yeni sınav ekleyin.")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("color:#444; font-size:14px;")
        root.addWidget(self._placeholder)
        self._main_widget = QWidget()
        self._main_widget.hide()
        self._main_layout = QVBoxLayout(self._main_widget)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._main_widget)

    def _init_main(self):
        if self._built:
            return
        self._built = True
        ml = self._main_layout

        # info bar
        info = QFrame()
        info.setStyleSheet("background:#252526; border-bottom:1px solid #3E3E3E;")
        il = QHBoxLayout(info)
        il.setContentsMargins(20, 10, 20, 10)
        self._title_lbl = QLabel("")
        self._title_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self._title_lbl.setStyleSheet("color:#00BFA5;")
        il.addWidget(self._title_lbl)
        il.addStretch()
        self._total_net_lbl = QLabel("")
        self._total_net_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self._total_net_lbl.setStyleSheet("color:#FF9800;")
        il.addWidget(self._total_net_lbl)
        save_btn = QPushButton("💾 Kaydet")
        save_btn.setFixedHeight(34)
        save_btn.clicked.connect(self._save)
        il.addWidget(save_btn)
        ml.addWidget(info)

        self._sections_tabs = QTabWidget()
        ml.addWidget(self._sections_tabs, 1)

        notes_row = QHBoxLayout()
        notes_row.setContentsMargins(12, 6, 12, 6)
        notes_row.addWidget(QLabel("Notlar:"))
        self._notes_edit = QLineEdit()
        self._notes_edit.setPlaceholderText("Bu sınava ait genel not…")
        notes_row.addWidget(self._notes_edit, 1)
        ml.addLayout(notes_row)

    def load_exam(self, exam: dict):
        self._init_main()
        self._exam = exam
        self._placeholder.hide()
        self._main_widget.show()

        exam_type = exam["exam_type"]
        source    = exam.get("source", "") or ""
        date      = str(exam["exam_date"])[:10]
        self._title_lbl.setText(f"{exam_type}  {source}  —  {date}")
        self._notes_edit.setText(exam.get("notes", "") or "")

        # Load existing data
        ex_sections = {s["subject"]: s for s in self._svc.get_section_scores(exam["id"])}
        ex_topics_raw = self._svc.get_topic_scores(exam["id"])
        ex_topics: dict[str, list] = {}
        for t in ex_topics_raw:
            ex_topics.setdefault(t["subject"], []).append(t)

        self._sections_tabs.clear()
        self._sec_tabs = []

        definition = EXAM_DEFS.get(exam_type, {})

        if definition:
            for subject, subj_def in definition.items():
                total_q = subj_def["total_q"]
                topics  = subj_def["topics"]
                tab = SectionTab(
                    subject, total_q, topics,
                    ex_sections.get(subject),
                    ex_topics.get(subject)
                )
                self._sections_tabs.addTab(tab, subject[:18])
                self._sec_tabs.append(tab)
                tab.tot_d.valueChanged.connect(self._refresh_total)
                tab.tot_y.valueChanged.connect(self._refresh_total)
        else:
            # Custom exam — show existing sections or blank
            if ex_sections:
                for subject, ex_sec in ex_sections.items():
                    tab = SectionTab(subject, ex_sec.get("total_q", 0), [],
                                     ex_sec, ex_topics.get(subject))
                    self._sections_tabs.addTab(tab, subject[:18])
                    self._sec_tabs.append(tab)
                    tab.tot_d.valueChanged.connect(self._refresh_total)
                    tab.tot_y.valueChanged.connect(self._refresh_total)

        # Wrong questions tab — always last
        wq_tab = WrongQuestionsTab(self._svc, exam["id"])
        self._sections_tabs.addTab(wq_tab, "❌ Yanlışlar")

        self._refresh_total()

    def _refresh_total(self):
        total = sum(t.total_net() for t in self._sec_tabs)
        color = _color_net(total)
        self._total_net_lbl.setText(f"Toplam Net: {total:.2f}")
        self._total_net_lbl.setStyleSheet(f"color:{color}; font-size:13px; font-weight:bold;")

    def _save(self):
        if not self._exam:
            return
        exam_id = self._exam["id"]
        self._svc.update_exam_notes(exam_id, self._notes_edit.text().strip())
        for tab in self._sec_tabs:
            sd = tab.section_data()
            self._svc.upsert_section_score(
                exam_id, sd["subject"], sd["total_q"],
                sd["correct"], sd["incorrect"], sd["empty"]
            )
            for td in tab.topic_data():
                self._svc.upsert_topic_score(
                    exam_id, sd["subject"], td["topic"],
                    td["correct"], td["incorrect"], td["empty"]
                )
        QMessageBox.information(self, "✅ Kaydedildi", "Sınav başarıyla kaydedildi.")

    def clear(self):
        self._exam = None
        self._placeholder.show()
        self._main_widget.hide()


# ── Main Tool ──────────────────────────────────────────────────────────────────
class ExamDetailTool(QWidget):
    name        = "Exam Detail"
    description = "Sınav detayı: TYT/AYT/YDT bölüm ve konu bazlı not girişi"

    def __init__(self, parent=None):
        super().__init__(parent)
        user = auth_manager.current_user
        self._svc   = ExamDetailService(user) if user else None
        self._exams : list[dict] = []
        self._build_ui()
        if self._svc:
            self._refresh_list()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("📋 Sınav Detayı")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        hl.addWidget(QLabel("Filtre:"))
        self._filter = QComboBox()
        self._filter.addItem("Tümü")
        self._filter.addItems(list(EXAM_DEFS.keys()))
        self._filter.currentTextChanged.connect(self._refresh_list)
        hl.addWidget(self._filter)
        new_btn = QPushButton("➕ Yeni Sınav")
        new_btn.clicked.connect(self._add_exam)
        hl.addWidget(new_btn)
        del_btn = QPushButton("🗑️ Sil")
        del_btn.setObjectName("secondary")
        del_btn.clicked.connect(self._delete_exam)
        hl.addWidget(del_btn)
        root.addWidget(hdr)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self._list = QListWidget()
        self._list.setMinimumWidth(210)
        self._list.setMaximumWidth(270)
        self._list.setStyleSheet("""
            QListWidget { background:#1E1E1E; border:none; font-size:13px; }
            QListWidget::item { padding:10px 12px; border-bottom:1px solid #2A2A2A; }
            QListWidget::item:selected { background:#1A3A35; color:#00BFA5; }
            QListWidget::item:hover:!selected { background:#252525; }
        """)
        self._list.currentRowChanged.connect(self._on_select)
        ll.addWidget(self._list, 1)
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color:#555; font-size:11px; padding:4px 12px;")
        ll.addWidget(self._count_lbl)
        splitter.addWidget(left)

        # Right panel
        self._entry = ExamEntryPanel(self._svc)
        splitter.addWidget(self._entry)
        splitter.setSizes([250, 950])
        root.addWidget(splitter, 1)

    def _refresh_list(self):
        if not self._svc:
            return
        f = self._filter.currentText()
        self._exams = self._svc.get_exams(None if f == "Tümü" else f)
        self._list.clear()
        for ex in self._exams:
            source = ex.get("source", "") or ""
            text = f"  {ex['exam_type']}\n  {source}\n  {str(ex['exam_date'])[:10]}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, ex)
            self._list.addItem(item)
        self._count_lbl.setText(f"{len(self._exams)} sınav")

    def _on_select(self, row):
        if 0 <= row < len(self._exams):
            self._entry.load_exam(self._exams[row])

    def _add_exam(self):
        dlg = NewExamDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        d = dlg.get_data()
        exam_id = self._svc.add_exam(d["type"], d["date"], d["source"], d["notes"])
        self._refresh_list()
        for i, ex in enumerate(self._exams):
            if ex["id"] == exam_id:
                self._list.setCurrentRow(i)
                break

    def _delete_exam(self):
        row = self._list.currentRow()
        if not 0 <= row < len(self._exams):
            return
        ex = self._exams[row]
        label = f"{ex['exam_type']} — {ex.get('source','')} ({str(ex['exam_date'])[:10]})"
        if QMessageBox.question(self, "Sil", f"Silinsin mi?\n{label}",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._svc.delete_exam(ex["id"])
        self._entry.clear()
        self._refresh_list()