import numpy as np
import torch
from transformers import RTDetrForObjectDetection, RTDetrImageProcessor

from models.base import BaseModel


COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
    "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
    "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
    "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv",
    "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
    "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush",
]

VEHICLE_CLASSES = ["car", "motorcycle", "bus", "truck"]


class RTDetrModel(BaseModel):
    def __init__(self):
        self._model = None
        self._processor = None
        self._device = "mps" if torch.backends.mps.is_available() else "cpu"

    @property
    def name(self) -> str:
        return "RT-DETR (r50vd)"

    @property
    def classes(self) -> list[str]:
        return VEHICLE_CLASSES

    def load(self):
        print(f"  Loading RT-DETR on {self._device}...")
        self._processor = RTDetrImageProcessor.from_pretrained("PekingU/rtdetr_r50vd")
        self._model = RTDetrForObjectDetection.from_pretrained("PekingU/rtdetr_r50vd")
        self._model.to(self._device)
        self._model.eval()
        print("  RT-DETR loaded.")

    def detect(self, frame) -> list[dict]:
        if self._model is None:
            raise RuntimeError("RT-DETR not loaded. Call load() first.")

        import cv2
        import torch

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = __import__("PIL").Image.fromarray(rgb)

        inputs = self._processor(images=pil_image, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)

        h_orig, w_orig = frame.shape[:2]
        results = self._processor.post_process_object_detection(
            outputs,
            target_sizes=torch.tensor([[h_orig, w_orig]]),
            threshold=0.35,
        )[0]

        detections = []
        for box, score, label_id in zip(
            results["boxes"], results["scores"], results["labels"]
        ):
            cls_name = COCO_CLASSES[label_id]
            if cls_name not in VEHICLE_CLASSES:
                continue

            x1, y1, x2, y2 = map(int, box.tolist())
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w_orig, x2)
            y2 = min(h_orig, y2)

            detections.append({
                "bbox": (x1, y1, x2, y2),
                "class": cls_name,
                "confidence": float(score),
            })

        return detections


def create_rtdetr():
    return RTDetrModel()
