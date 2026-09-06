"""RT-DETR r50vd, COCO-pretrained, via HuggingFace transformers.

Generic baseline only. COCO has no auto-rickshaw, tractor, LCV or multi-axle
category, so this model cannot express most of the canonical taxonomy -- an
auto will come back as "car", "truck" or nothing at all. Read its numbers as
"what a general-purpose detector gets on Indian roads", not as a peer of the
UVH-26 models.
"""
import cv2
import numpy as np
import torch
from PIL import Image
from transformers import RTDetrForObjectDetection, RTDetrImageProcessor

from core import config
from core.base import BaseModel, Detection

CHECKPOINT = "PekingU/rtdetr_r50vd"

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

# COCO labels we treat as vehicles; everything else is discarded.
NATIVE_CLASSES = ["car", "motorcycle", "bus", "truck"]

DISPLAY_NAME = "RT-DETR (r50vd)"

# RT-DETR r50vd was trained at 640x640. Running it at the video's native
# resolution gives it more pixels, but also moves it off its training
# distribution -- unlike the YOLO models, which are trained multi-scale. Set
# native_size=False to pin it back to 640 if its numbers look off.
TRAINED_SIZE = 640


class RTDetrModel(BaseModel):
    def __init__(self, conf: float = config.DEFAULT_CONFIDENCE, native_size: bool = True):
        self._model = None
        self._processor = None
        self._conf = conf
        self._native_size = native_size
        self._device = "mps" if torch.backends.mps.is_available() else "cpu"

    @property
    def name(self) -> str:
        return DISPLAY_NAME

    @property
    def native_classes(self) -> list[str]:
        return NATIVE_CLASSES

    def load(self):
        print(f"  Loading RT-DETR on {self._device}...")
        self._processor = RTDetrImageProcessor.from_pretrained(CHECKPOINT)
        self._model = RTDetrForObjectDetection.from_pretrained(CHECKPOINT)
        self._model.to(self._device)
        self._model.eval()
        print("  RT-DETR loaded.")

    def detect(self, frame) -> list[Detection]:
        if self._model is None:
            raise RuntimeError("RT-DETR not loaded. Call load() first.")

        height, width = frame.shape[:2]
        pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        if self._native_size:
            size = {"height": config.round_to_stride(height),
                    "width": config.round_to_stride(width)}
        else:
            size = {"height": TRAINED_SIZE, "width": TRAINED_SIZE}

        inputs = self._processor(images=pil_image, return_tensors="pt", size=size)
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)

        results = self._processor.post_process_object_detection(
            outputs,
            target_sizes=torch.tensor([[height, width]]),
            threshold=self._conf,
        )[0]

        detections = []
        for box, score, label_id in zip(results["boxes"], results["scores"], results["labels"]):
            native_class = COCO_CLASSES[label_id]
            if native_class not in NATIVE_CLASSES:
                continue

            x1, y1, x2, y2 = map(int, box.tolist())
            bbox = (max(0, x1), max(0, y1), min(width, x2), min(height, y2))
            detections.append(self.make_detection(bbox, float(score), native_class))

        return detections


def create():
    return RTDetrModel()
