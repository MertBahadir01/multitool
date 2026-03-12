from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QFont
import cv2

class FaceDetectorTool(QWidget):
    name = "Face Detector"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("👤 Face Detector")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        note = QLabel("Uses OpenCV Haar Cascade — no additional dependencies required")
        note.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(note)

        btn = QPushButton("📂 Select Image")
        btn.clicked.connect(self._detect)
        layout.addWidget(btn)

        self.img_label = QLabel("Select an image to detect faces")
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("background: #1A1A1A; border: 1px solid #3E3E3E; border-radius: 8px; min-height: 380px;")
        layout.addWidget(self.img_label)

        self.count_lbl = QLabel("")
        self.count_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.count_lbl.setAlignment(Qt.AlignCenter)
        self.count_lbl.setStyleSheet("color: #00BFA5;")
        layout.addWidget(self.count_lbl)
        layout.addStretch()

    def _detect(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", filter="Images (*.jpg *.png *.jpeg *.bmp)")
        if not path: return
        frame = cv2.imread(path)
        if frame is None: return
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = cascade.detectMultiScale(gray, 1.1, 4, minSize=(30, 30))
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 191, 165), 3)
            cv2.putText(frame, "Face", (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 191, 165), 2)
        self.count_lbl.setText(f"Detected {len(faces)} face(s)")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h_img, w_img, c = rgb.shape
        qimg = QImage(rgb.data, w_img, h_img, w_img * c, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(640, 480, Qt.KeepAspectRatio)
        self.img_label.setPixmap(pix)

# Object Detector
#cat > /home/claude/multitool_studio/tools/object_detector/__init__.py << 'EOF'
#from .od_tool import ObjectDetectorTool
#TOOL_META = {"id": "object_detector", "name": "Object Detector", "category": "ai", "widget_class": ObjectDetectorTool}
