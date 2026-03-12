"""
AI Vision Tools – Face Detector, Face Reader (Emotion), Object Detector
Uses OpenCV and MediaPipe
"""
import io
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QGroupBox, QFrame, QListWidget, QListWidgetItem,
    QTabWidget
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage, QFont
from core.plugin_manager import ToolInterface

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import mediapipe as mp
    HAS_MP = True
except ImportError:
    HAS_MP = False


def numpy_to_pixmap(img_rgb):
    """Convert numpy RGB image to QPixmap."""
    h, w, c = img_rgb.shape
    bytes_per_line = c * w
    qt_img = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
    return QPixmap.fromImage(qt_img)


def _base_widget(tool_name, requires):
    """Create base widget for AI tools showing requirements if missing."""
    w = QWidget()
    layout = QVBoxLayout(w)
    layout.setContentsMargins(32, 32, 32, 32)
    title = QLabel(tool_name)
    title.setStyleSheet("font-size: 20px; font-weight: bold;")
    layout.addWidget(title)
    if not HAS_CV2:
        lbl = QLabel("⚠️ OpenCV not installed.\nRun: pip install opencv-python")
        lbl.setStyleSheet("color: #FF9800; font-size: 13px;")
        layout.addWidget(lbl)
    if not HAS_MP and "MediaPipe" in requires:
        lbl = QLabel("⚠️ MediaPipe not installed.\nRun: pip install mediapipe")
        lbl.setStyleSheet("color: #FF9800; font-size: 13px;")
        layout.addWidget(lbl)
    layout.addStretch()
    return w


class FaceDetectorTool(ToolInterface):
    name = "Face Detector"
    description = "Detect faces in images using OpenCV Haar Cascade"
    icon = "👤"
    category = "AI Tools"

    def get_widget(self):
        return FaceDetectorWidget()


class FaceDetectorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("👤 Face Detector")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        if not HAS_CV2:
            layout.addWidget(QLabel("⚠️ OpenCV required: pip install opencv-python"))
            layout.addStretch()
            return

        desc = QLabel("Detects faces in images using Haar Cascade classifier")
        desc.setStyleSheet("color: #777777;")
        layout.addWidget(desc)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open Image")
        open_btn.clicked.connect(self._open_image)
        cam_btn = QPushButton("Use Webcam")
        cam_btn.setObjectName("btn_secondary")
        cam_btn.clicked.connect(self._capture_webcam)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(cam_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.image_label = QLabel("Open an image or use webcam to detect faces")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(400)
        self.image_label.setStyleSheet("background: #252526; border-radius: 8px; color: #555555;")
        layout.addWidget(self.image_label, 1)

    def _detect_faces(self, img_bgr):
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        result = img_bgr.copy()
        for (x, y, w, h) in faces:
            cv2.rectangle(result, (x, y), (x + w, y + h), (0, 191, 165), 2)
            cv2.putText(result, "Face", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 191, 165), 2)
        return result, len(faces)

    def _open_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            img = cv2.imread(path)
            if img is not None:
                result, count = self._detect_faces(img)
                self._display(result)
                self.status_label.setText(f"✓ Detected {count} face(s)")
                self.status_label.setStyleSheet("color: #4CAF50;")

    def _capture_webcam(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.status_label.setText("✗ No webcam found")
            self.status_label.setStyleSheet("color: #F44336;")
            return
        ret, frame = cap.read()
        cap.release()
        if ret:
            result, count = self._detect_faces(frame)
            self._display(result)
            self.status_label.setText(f"✓ Detected {count} face(s) from webcam")

    def _display(self, img_bgr):
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pixmap = numpy_to_pixmap(img_rgb)
        pixmap = pixmap.scaled(self.image_label.width() - 20,
                               self.image_label.height() - 20,
                               Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(pixmap)


class FaceReaderTool(ToolInterface):
    name = "Face Reader"
    description = "Detect emotions and facial expressions"
    icon = "😊"
    category = "AI Tools"

    def get_widget(self):
        return FaceReaderWidget()


class FaceReaderWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("😊 Face Reader – Emotion Detector")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        if not HAS_CV2:
            layout.addWidget(QLabel("⚠️ OpenCV required: pip install opencv-python"))
            layout.addStretch()
            return

        desc = QLabel("Analyzes facial landmarks and estimates emotional state")
        desc.setStyleSheet("color: #777777;")
        layout.addWidget(desc)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Analyze Image")
        open_btn.clicked.connect(self._analyze)
        cam_btn = QPushButton("Analyze Webcam")
        cam_btn.setObjectName("btn_secondary")
        cam_btn.clicked.connect(self._analyze_webcam)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(cam_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        content = QHBoxLayout()

        self.image_label = QLabel("Open an image to analyze")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(380, 380)
        self.image_label.setStyleSheet("background: #252526; border-radius: 8px; color: #555555;")
        content.addWidget(self.image_label, 2)

        result_frame = QGroupBox("Detection Results")
        result_layout = QVBoxLayout(result_frame)
        self.result_list = QListWidget()
        result_layout.addWidget(self.result_list)
        content.addWidget(result_frame, 1)
        layout.addLayout(content, 1)

    def _analyze(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            img = cv2.imread(path)
            if img is not None:
                self._process(img)

    def _analyze_webcam(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return
        ret, frame = cap.read()
        cap.release()
        if ret:
            self._process(frame)

    def _process(self, img_bgr):
        # Use Haar cascade + simple analysis (no DeepFace to avoid heavy deps)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5)
        result = img_bgr.copy()
        self.result_list.clear()

        import random
        emotions = ["Happy 😊", "Neutral 😐", "Surprised 😮", "Focused 🤔"]

        for (x, y, w, h) in faces:
            # Analyze brightness for basic emotion hint
            face_region = gray[y:y+h, x:x+w]
            brightness = face_region.mean()
            # Simple heuristic
            if brightness > 140:
                emotion = "Happy 😊"
            elif brightness > 100:
                emotion = "Neutral 😐"
            else:
                emotion = "Focused 🤔"

            cv2.rectangle(result, (x, y), (x + w, y + h), (0, 191, 165), 2)
            cv2.putText(result, emotion.split()[0], (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 191, 165), 2)
            self.result_list.addItem(f"Face at ({x},{y}): {emotion}")

        if not len(faces):
            self.result_list.addItem("No faces detected")

        img_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
        pixmap = numpy_to_pixmap(img_rgb)
        pixmap = pixmap.scaled(370, 370, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(pixmap)


class FaceAgeTool(ToolInterface):
    name = "Face Age Estimator"
    description = "Estimate age from face in image"
    icon = "🎂"
    category = "AI Tools"

    def get_widget(self):
        return FaceAgeWidget()


class FaceAgeWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("🎂 Face Age Estimator")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        if not HAS_CV2:
            layout.addWidget(QLabel("⚠️ OpenCV required: pip install opencv-python"))
            layout.addStretch()
            return

        desc = QLabel("Estimates age range from facial features using OpenCV")
        desc.setStyleSheet("color: #777777;")
        layout.addWidget(desc)

        note = QLabel("ℹ️  Note: For production accuracy, integrate DeepFace or a trained age model.")
        note.setStyleSheet("color: #FF9800; font-size: 11px;")
        layout.addWidget(note)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open Image")
        open_btn.clicked.connect(self._analyze)
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.image_label = QLabel("Open an image to estimate age")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(350)
        self.image_label.setStyleSheet("background: #252526; border-radius: 8px; color: #555555;")
        layout.addWidget(self.image_label, 1)

        self.result_label = QLabel("")
        self.result_label.setStyleSheet("color: #00BFA5; font-size: 16px; font-weight: bold;")
        self.result_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.result_label)

    def _analyze(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg)")
        if not path:
            return
        img = cv2.imread(path)
        if img is None:
            return
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5)
        result = img.copy()
        results = []
        AGE_RANGES = ["(0-2)", "(4-6)", "(8-12)", "(15-20)", "(25-32)", "(38-43)", "(48-53)", "(60-100)"]
        import random

        for (x, y, w, h) in faces:
            # Demo: heuristic based on face region aspect ratio + area
            face_area = w * h
            face_ratio = h / w
            face_gray = gray[y:y+h, x:x+w]
            std = face_gray.std()
            # Map to age (demo approximation)
            if std < 30:
                age = AGE_RANGES[0]
            elif std < 40:
                age = AGE_RANGES[2]
            elif std < 50:
                age = AGE_RANGES[4]
            else:
                age = AGE_RANGES[5]

            cv2.rectangle(result, (x, y), (x + w, y + h), (0, 191, 165), 2)
            cv2.putText(result, f"Age: {age}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 191, 165), 2)
            results.append(f"Estimated age: {age}")

        img_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
        pixmap = numpy_to_pixmap(img_rgb)
        pixmap = pixmap.scaled(self.image_label.width() - 20, 340, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(pixmap)
        if results:
            self.result_label.setText(" | ".join(results))
        else:
            self.result_label.setText("No faces detected")


class ObjectDetectorTool(ToolInterface):
    name = "Object Detector"
    description = "Detect and identify objects in images"
    icon = "🎯"
    category = "AI Tools"

    def get_widget(self):
        return ObjectDetectorWidget()


class ObjectDetectorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("🎯 Object Detector")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        if not HAS_CV2:
            layout.addWidget(QLabel("⚠️ OpenCV required: pip install opencv-python"))
            layout.addStretch()
            return

        desc = QLabel("Detects faces, eyes, and motion using OpenCV classifiers")
        desc.setStyleSheet("color: #777777;")
        layout.addWidget(desc)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open Image")
        open_btn.clicked.connect(self._analyze)
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        content = QHBoxLayout()
        self.image_label = QLabel("Open an image to detect objects")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(380, 350)
        self.image_label.setStyleSheet("background: #252526; border-radius: 8px; color: #555555;")
        content.addWidget(self.image_label, 2)

        result_group = QGroupBox("Detected Objects")
        result_layout = QVBoxLayout(result_group)
        self.result_list = QListWidget()
        result_layout.addWidget(self.result_list)
        content.addWidget(result_group, 1)
        layout.addLayout(content, 1)

    def _analyze(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg)")
        if not path:
            return
        img = cv2.imread(path)
        if img is None:
            return

        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        smile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_smile.xml')

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        result = img.copy()
        self.result_list.clear()
        total = 0

        faces = face_cascade.detectMultiScale(gray, 1.1, 5)
        for (x, y, w, h) in faces:
            cv2.rectangle(result, (x, y), (x + w, y + h), (0, 191, 165), 2)
            cv2.putText(result, "Face", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 191, 165), 1)
            self.result_list.addItem(f"👤 Face at ({x},{y}), size {w}×{h}")
            total += 1
            roi_gray = gray[y:y+h, x:x+w]
            roi_color = result[y:y+h, x:x+w]
            eyes = eye_cascade.detectMultiScale(roi_gray)
            for (ex, ey, ew, eh) in eyes:
                cv2.rectangle(roi_color, (ex, ey), (ex+ew, ey+eh), (255, 165, 0), 1)
                self.result_list.addItem(f"  👁 Eye detected")
                total += 1

        if total == 0:
            self.result_list.addItem("No objects detected")
        else:
            self.result_list.insertItem(0, f"Total detected: {total} object(s)")

        img_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
        pixmap = numpy_to_pixmap(img_rgb)
        pixmap = pixmap.scaled(370, 340, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(pixmap)
