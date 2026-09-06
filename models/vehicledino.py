"""VehicleDINO (DINOv2 backbone) as an INT8 ONNX graph.

WARNING -- the output decoding below is unverified and is very likely wrong.
It takes an argmax over the class scores of every query with no "no object"
class excluded and no NMS afterwards, which for a DETR-style head means most
of the ~100-300 queries that should be discarded as background will instead
be emitted as detections. Confirm the graph's real output signature before
reading any number this model produces. Off by default for that reason as
much as for its speed on CPU.
"""
import os

import cv2
import numpy as np
from huggingface_hub import hf_hub_download

from core.base import BaseModel, Detection
from core.paths import WEIGHTS_DIR, ensure_weights_dir

try:
    import onnxruntime as ort
except ImportError:
    ort = None

REPO_ID = "wms2537/VehicleDINO"
WEIGHTS_FILE = "vehicledino_dinov2_int8.onnx"

NATIVE_CLASSES = ["car", "suv", "truck", "bus", "van"]

DISPLAY_NAME = "VehicleDINO"

INPUT_SIZE = 560
CONF_THRESHOLD = 0.35

# ImageNet normalisation, as used by the DINOv2 backbone.
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class VehicleDINOModel(BaseModel):
    def __init__(self, conf: float = CONF_THRESHOLD):
        self._session = None
        self._input_name = None
        self._conf = conf

    @property
    def name(self) -> str:
        return DISPLAY_NAME

    @property
    def native_classes(self) -> list[str]:
        return NATIVE_CLASSES

    def load(self):
        if ort is None:
            raise ImportError("onnxruntime not installed. Run: pip install onnxruntime")

        model_path = os.path.join(WEIGHTS_DIR, WEIGHTS_FILE)
        if not os.path.exists(model_path):
            ensure_weights_dir()
            print(f"  Downloading {WEIGHTS_FILE} from HuggingFace...")
            hf_hub_download(repo_id=REPO_ID, filename=WEIGHTS_FILE, local_dir=WEIGHTS_DIR)
            print(f"  Downloaded {WEIGHTS_FILE}")

        self._session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self._input_name = self._session.get_inputs()[0].name

    def _preprocess(self, frame):
        img = cv2.resize(frame, (INPUT_SIZE, INPUT_SIZE)).astype(np.float32) / 255.0
        img = (img - _MEAN) / _STD
        return img.transpose(2, 0, 1)[np.newaxis].astype(np.float32)

    def detect(self, frame) -> list[Detection]:
        if self._session is None:
            raise RuntimeError("VehicleDINO not loaded. Call load() first.")

        outputs = self._session.run(None, {self._input_name: self._preprocess(frame)})
        boxes = outputs[0][0]
        class_scores = outputs[1][0]

        height, width = frame.shape[:2]
        detections = []

        for i in range(len(boxes)):
            scores = class_scores[i]
            class_id = int(np.argmax(scores))
            confidence = float(scores[class_id])
            if confidence < self._conf:
                continue

            cx, cy, w, h = boxes[i]
            x1 = max(0, int((cx - w / 2) * width))
            y1 = max(0, int((cy - h / 2) * height))
            x2 = min(width, int((cx + w / 2) * width))
            y2 = min(height, int((cy + h / 2) * height))

            detections.append(
                self.make_detection((x1, y1, x2, y2), confidence, NATIVE_CLASSES[class_id])
            )

        return detections


def create():
    return VehicleDINOModel()
