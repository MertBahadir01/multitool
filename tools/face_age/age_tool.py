from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QFont
import cv2

class FaceAgeTool(QWidget):
    name = "Face Age Estimator"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("🎂 Face Age Estimator")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        note = QLabel("Requires: deepface, opencv-python")
        note.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(note)

        btn = QPushButton("📂 Select Image to Analyze")
        btn.clicked.connect(self._analyze)
        layout.addWidget(btn)

        self.img_label = QLabel("Image preview")
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("background: #1A1A1A; border: 1px solid #3E3E3E; border-radius: 8px; min-height: 320px;")
        layout.addWidget(self.img_label)

        self.result_lbl = QLabel("Estimated age and gender will appear here")
        self.result_lbl.setFont(QFont("Segoe UI", 15, QFont.Bold))
        self.result_lbl.setAlignment(Qt.AlignCenter)
        self.result_lbl.setStyleSheet("color: #00BFA5; margin-top: 8px;")
        layout.addWidget(self.result_lbl)
        layout.addStretch()

    def _analyze(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", filter="Images (*.jpg *.png *.jpeg *.bmp)")
        if not path: return
        frame = cv2.imread(path)
        if frame is None: return
        try:
            from deepface import DeepFace
            results = DeepFace.analyze(frame, actions=['age', 'gender', 'race'], enforce_detection=False, silent=True)
            r = results[0] if isinstance(results, list) else results
            age = r.get('age', 'N/A')
            gender = r.get('dominant_gender', r.get('gender', 'N/A'))
            race = r.get('dominant_race', 'N/A')
            self.result_lbl.setText(f"Age: ~{age}  |  Gender: {gender}  |  Ethnicity: {race.title()}")
        except ImportError:
            self.result_lbl.setText("deepface not installed. Install: pip install deepface")
        except Exception as e:
            self.result_lbl.setText(f"Analysis failed: {e}")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, c = rgb.shape
        qimg = QImage(rgb.data, w, h, w * c, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(580, 400, Qt.KeepAspectRatio)
        self.img_label.setPixmap(pix)
