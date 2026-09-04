import os
import numpy as np
from huggingface_hub import hf_hub_download

from models.base import BaseModel

try:
    import onnxruntime as ort
except ImportError:
    ort = None


VEHICLEDINO_CLASSES = ["car", "suv", "truck", "bus", "van"]


class VehicleDINOModel(BaseModel):
    def __init__(self):
        self._session = None
        self._input_name = None

    @property
    def name(self) -> str:
        return "VehicleDINO"

    @property
    def classes(self) -> list[str]:
        return VEHICLEDINO_CLASSES

    def load(self):
        if ort is None:
            raise ImportError("onnxruntime not installed. Run: pip install onnxruntime")

        model_dir = os.path.join("models", "weights")
        model_path = os.path.join(model_dir, "vehicledino_dinov2_int8.onnx")

        if not os.path.exists(model_path):
            os.makedirs(model_dir, exist_ok=True)
            print("  Downloading VehicleDINO INT8 from HuggingFace...")
            hf_hub_download(
                repo_id="wms2537/VehicleDINO",
                filename="vehicledino_dinov2_int8.onnx",
                local_dir=model_dir,
            )
            print("  Downloaded vehicledino_dinov2_int8.onnx")

        self._session = ort.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"],
        )
        self._input_name = self._session.get_inputs()[0].name

    def _preprocess(self, frame):
        import cv2
        img = cv2.resize(frame, (560, 560))
        img = img.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img = (img - mean) / std
        img = img.transpose(2, 0, 1)
        return img[np.newaxis].astype(np.float32)

    def detect(self, frame) -> list[dict]:
        if self._session is None:
            raise RuntimeError("VehicleDINO not loaded. Call load() first.")

        import cv2

        tensor = self._preprocess(frame)
        outputs = self._session.run(None, {self._input_name: tensor})

        det_boxes = outputs[0][0]
        det_classes = outputs[1][0]

        h_orig, w_orig = frame.shape[:2]
        detections = []

        for i in range(len(det_boxes)):
            scores = det_classes[i]
            cls_id = int(np.argmax(scores))
            conf = float(scores[cls_id])

            if conf < 0.35:
                continue

            cx, cy, w, h = det_boxes[i]
            x1 = int((cx - w / 2) * w_orig)
            y1 = int((cy - h / 2) * h_orig)
            x2 = int((cx + w / 2) * w_orig)
            y2 = int((cy + h / 2) * h_orig)

            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w_orig, x2)
            y2 = min(h_orig, y2)

            detections.append({
                "bbox": (x1, y1, x2, y2),
                "class": VEHICLEDINO_CLASSES[cls_id],
                "confidence": conf,
            })

        return detections


def create_vehicledino():
    return VehicleDINOModel()
