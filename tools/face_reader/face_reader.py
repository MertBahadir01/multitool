from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QSlider, QFileDialog)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QImage, QPixmap, QFont
import numpy as np

class CameraWorker(QThread):
    frame_ready = Signal(np.ndarray)
    def __init__(self): super().__init__(); self.running = False
    def run(self):
        import cv2
        self.running = True
        cap = cv2.VideoCapture(0)
        while self.running:
            ret, frame = cap.read()
            if ret: self.frame_ready.emit(frame)
        cap.release()
    def stop(self): self.running = False

class FaceReaderTool(QWidget):
    name = "Face Emotion Reader"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("🧠 Face Emotion Reader")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        note = QLabel("Requires: opencv-python, deepface\nInstall: pip install deepface tf-keras")
        note.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(note)

        row = QHBoxLayout()
        self.start_btn = QPushButton("▶ Start Camera")
        self.start_btn.clicked.connect(self._toggle_camera)
        row.addWidget(self.start_btn)
        img_btn = QPushButton("📂 Analyze Image")
        img_btn.setObjectName("secondary")
        img_btn.clicked.connect(self._analyze_image)
        row.addWidget(img_btn)
        row.addStretch()
        layout.addLayout(row)

        self.video_label = QLabel("Camera feed will appear here")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background: #1A1A1A; border: 1px solid #3E3E3E; border-radius: 8px; min-height: 360px;")
        layout.addWidget(self.video_label)

        self.emotion_lbl = QLabel("Emotion: —")
        self.emotion_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.emotion_lbl.setAlignment(Qt.AlignCenter)
        self.emotion_lbl.setStyleSheet("color: #00BFA5; margin-top: 8px;")
        layout.addWidget(self.emotion_lbl)
        layout.addStretch()
        self._camera_on = False

    def _toggle_camera(self):
        if self._camera_on:
            if self._worker: self._worker.stop(); self._worker = None
            self._camera_on = False
            self.start_btn.setText("▶ Start Camera")
            self.video_label.setText("Camera stopped")
        else:
            self._camera_on = True
            self.start_btn.setText("⏹ Stop Camera")
            self._worker = CameraWorker()
            self._worker.frame_ready.connect(self._process_frame)
            self._worker.start()

    def _process_frame(self, frame):
        import cv2
        try:
            from deepface import DeepFace
            result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False, silent=True)
            emotion = result[0]['dominant_emotion'] if isinstance(result, list) else result['dominant_emotion']
            self.emotion_lbl.setText(f"Emotion: {emotion.capitalize()} 😊")
            cv2.putText(frame, emotion.upper(), (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 191, 165), 2)
        except ImportError:
            self.emotion_lbl.setText("deepface not installed")
        except Exception:
            pass
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, c = rgb.shape
        qimg = QImage(rgb.data, w, h, w * c, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(640, 360, Qt.KeepAspectRatio)
        self.video_label.setPixmap(pix)

    def _analyze_image(self):
        import cv2
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", filter="Images (*.jpg *.png *.jpeg *.bmp)")
        if not path: return
        frame = cv2.imread(path)
        if frame is not None: self._process_frame(frame)

    def closeEvent(self, event):
        if self._worker: self._worker.stop()
        super().closeEvent(event)

# Face Age Estimator
#cat > /home/claude/multitool_studio/tools/face_age/__init__.py << 'EOF'
#from .age_tool import FaceAgeTool
#TOOL_META = {"id": "face_age", "name": "Face Age Estimator", "category": "ai", "widget_class": FaceAgeTool}
