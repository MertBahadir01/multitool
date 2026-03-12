from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QTextEdit)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QFont
import cv2

# COCO class labels
LABELS = ["person","bicycle","car","motorcycle","airplane","bus","train","truck","boat",
    "traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat","dog",
    "horse","sheep","cow","elephant","bear","zebra","giraffe","backpack","umbrella",
    "handbag","tie","suitcase","frisbee","skis","snowboard","sports ball","kite",
    "baseball bat","baseball glove","skateboard","surfboard","tennis racket","bottle",
    "wine glass","cup","fork","knife","spoon","bowl","banana","apple","sandwich","orange",
    "broccoli","carrot","hot dog","pizza","donut","cake","chair","couch","potted plant",
    "bed","dining table","toilet","tv","laptop","mouse","remote","keyboard","cell phone",
    "microwave","oven","toaster","sink","refrigerator","book","clock","vase","scissors",
    "teddy bear","hair drier","toothbrush"]

class ObjectDetectorTool(QWidget):
    name = "Object Detector"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._net = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("📦 Object Detector (YOLOv3-tiny)")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        note = QLabel("Requires YOLOv3-tiny weights (yolov3-tiny.cfg + yolov3-tiny.weights).\nPlace in tools/object_detector/ folder.")
        note.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(note)

        row = QHBoxLayout()
        btn = QPushButton("📂 Select Image"); btn.clicked.connect(self._detect)
        row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)

        self.img_label = QLabel("Select an image to detect objects")
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("background: #1A1A1A; border: 1px solid #3E3E3E; border-radius: 8px; min-height: 340px;")
        layout.addWidget(self.img_label)

        self.result = QTextEdit(); self.result.setReadOnly(True)
        self.result.setMaximumHeight(100)
        layout.addWidget(self.result)
        layout.addStretch()

    def _detect(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", filter="Images (*.jpg *.png *.jpeg *.bmp)")
        if not path: return
        frame = cv2.imread(path)
        if frame is None: return
        import os
        tool_dir = os.path.dirname(__file__)
        cfg = os.path.join(tool_dir, "yolov3-tiny.cfg")
        weights = os.path.join(tool_dir, "yolov3-tiny.weights")
        if not os.path.exists(cfg) or not os.path.exists(weights):
            self.result.setPlainText("YOLO model files not found.\nDownload yolov3-tiny.cfg and yolov3-tiny.weights and place in tools/object_detector/")
            return
        try:
            net = cv2.dnn.readNet(weights, cfg)
            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
            net.setInput(blob)
            layer_names = [net.getLayerNames()[i - 1] for i in net.getUnconnectedOutLayers()]
            outputs = net.forward(layer_names)
            h, w = frame.shape[:2]
            found = []
            for out in outputs:
                for det in out:
                    scores = det[5:]
                    cid = int(scores.argmax())
                    conf = scores[cid]
                    if conf > 0.4:
                        cx, cy, bw, bh = (det[:4] * [w, h, w, h]).astype(int)
                        x, y = cx - bw // 2, cy - bh // 2
                        cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 191, 165), 2)
                        lbl = LABELS[cid] if cid < len(LABELS) else str(cid)
                        cv2.putText(frame, f"{lbl} {conf:.0%}", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 191, 165), 2)
                        found.append(f"{lbl} ({conf:.0%})")
            self.result.setPlainText("Detected: " + ", ".join(found) if found else "No objects detected")
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        hh, ww, c = rgb.shape
        qimg = QImage(rgb.data, ww, hh, ww * c, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(600, 400, Qt.KeepAspectRatio)
        self.img_label.setPixmap(pix)
