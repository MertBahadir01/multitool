"""Data Chart Builder — build charts from pasted data using matplotlib."""
import io
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QGroupBox, QLineEdit, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap, QImage


def _make_chart(data_text, chart_type, title, xlabel, ylabel):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    lines = [l.strip() for l in data_text.strip().splitlines() if l.strip()]
    labels, values = [], []
    for line in lines:
        parts = line.replace(",", " ").split()
        if len(parts) >= 2:
            labels.append(parts[0])
            try: values.append(float(parts[1]))
            except ValueError: pass
        elif len(parts) == 1:
            try:
                values.append(float(parts[0]))
                labels.append(str(len(values)))
            except ValueError:
                pass

    if not values:
        raise ValueError("No numeric data found. Format: label value (one per line)")

    fig, ax = plt.subplots(figsize=(8, 5), facecolor="#1E1E1E")
    ax.set_facecolor("#252526")
    ax.tick_params(colors="#CCCCCC")
    for spine in ax.spines.values(): spine.set_edgecolor("#3E3E3E")
    ax.title.set_color("#00BFA5")
    ax.xaxis.label.set_color("#CCCCCC")
    ax.yaxis.label.set_color("#CCCCCC")

    colors = ["#00BFA5","#8BC34A","#FFC107","#03A9F4","#F44336","#9C27B0","#FF9800"]

    if chart_type == "Bar":
        ax.bar(labels, values, color=[colors[i % len(colors)] for i in range(len(values))])
    elif chart_type == "Horizontal Bar":
        ax.barh(labels, values, color=[colors[i % len(colors)] for i in range(len(values))])
    elif chart_type == "Line":
        ax.plot(labels, values, color="#00BFA5", marker="o", linewidth=2)
        ax.fill_between(range(len(values)), values, alpha=0.15, color="#00BFA5")
    elif chart_type == "Pie":
        ax.pie(values, labels=labels, colors=colors[:len(values)],
               autopct="%1.1f%%", textprops={"color": "#CCCCCC"})
    elif chart_type == "Scatter":
        ax.scatter(range(len(values)), values,
                   c=[colors[i % len(colors)] for i in range(len(values))], s=80)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=30, ha="right")

    if title:  ax.set_title(title, fontsize=14, pad=12)
    if xlabel: ax.set_xlabel(xlabel)
    if ylabel: ax.set_ylabel(ylabel)
    if chart_type not in ("Pie",):
        ax.grid(True, color="#3E3E3E", linestyle="--", alpha=0.5)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


class DataChartBuilderTool(QWidget):
    name        = "Data Chart Builder"
    description = "Create bar, line, pie, and scatter charts from your data"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._img_bytes = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        top = QHBoxLayout()

        # Left: input
        left = QVBoxLayout()

        data_box = QGroupBox("Data  (label  value — one per line)")
        dl = QVBoxLayout(data_box)
        self.data_in = QTextEdit()
        self.data_in.setFont(QFont("Courier New", 12))
        self.data_in.setPlaceholderText("Jan 120\nFeb 95\nMar 140\n...")
        self.data_in.setPlainText("Jan 120\nFeb 95\nMar 140\nApr 180\nMay 160\nJun 210")
        dl.addWidget(self.data_in)
        left.addWidget(data_box)

        cfg_box = QGroupBox("Chart Options")
        cl = QVBoxLayout(cfg_box)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Type:"))
        self.type_cb = QComboBox()
        self.type_cb.addItems(["Bar","Horizontal Bar","Line","Pie","Scatter"])
        row1.addWidget(self.type_cb)
        row1.addStretch()
        cl.addLayout(row1)
        for lbl_text, attr in [("Title:", "title_in"), ("X Label:", "xlabel_in"), ("Y Label:", "ylabel_in")]:
            row = QHBoxLayout()
            row.addWidget(QLabel(lbl_text))
            inp = QLineEdit()
            setattr(self, attr, inp)
            row.addWidget(inp)
            cl.addLayout(row)
        self.title_in.setPlaceholderText("Chart title")
        left.addWidget(cfg_box)

        btn_row = QHBoxLayout()
        gen_btn = QPushButton("Generate Chart")
        gen_btn.clicked.connect(self._generate)
        btn_row.addWidget(gen_btn)
        save_btn = QPushButton("Save as PNG")
        save_btn.setObjectName("secondary")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        left.addLayout(btn_row)

        self.status_lbl = QLabel("Requires: pip install matplotlib")
        self.status_lbl.setStyleSheet("color: #555555; font-size: 11px;")
        left.addWidget(self.status_lbl)
        top.addLayout(left, 1)

        # Right: preview
        right = QVBoxLayout()
        right.addWidget(QLabel("Preview:"))
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(500, 350)
        self.preview.setStyleSheet("background: #252526; border: 1px solid #3E3E3E; border-radius: 6px;")
        self.preview.setText("Chart will appear here")
        right.addWidget(self.preview)
        top.addLayout(right, 2)

        lay.addLayout(top)

    def _generate(self):
        try:
            png = _make_chart(
                self.data_in.toPlainText(),
                self.type_cb.currentText(),
                self.title_in.text(),
                self.xlabel_in.text(),
                self.ylabel_in.text(),
            )
            self._img_bytes = png
            img  = QImage.fromData(png)
            pix  = QPixmap.fromImage(img)
            self.preview.setPixmap(
                pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.status_lbl.setText("Chart generated.")
            self.status_lbl.setStyleSheet("color: #00BFA5;")
        except Exception as e:
            self.status_lbl.setText(f"Error: {e}")
            self.status_lbl.setStyleSheet("color: #F44336;")

    def _save(self):
        if not self._img_bytes:
            self.status_lbl.setText("Generate a chart first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Chart", "chart.png", "PNG Files (*.png)")
        if path:
            with open(path, "wb") as f:
                f.write(self._img_bytes)
            self.status_lbl.setText(f"Saved: {path}")
            self.status_lbl.setStyleSheet("color: #00BFA5;")
