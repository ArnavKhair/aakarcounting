import os
from huggingface_hub import hf_hub_download
from ultralytics import YOLO

from models.base import BaseModel

WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "weights")


class YOLOModel(BaseModel):
    def __init__(self, repo_id: str, filename: str, model_name: str, local_name: str, classes: list[str]):
        self._repo_id = repo_id
        self._filename = filename
        self._model_name = model_name
        self._local_name = local_name
        self._classes = classes
        self._model = None

    @property
    def name(self) -> str:
        return self._model_name

    @property
    def classes(self) -> list[str]:
        return self._classes

    def load(self):
        model_path = os.path.join(WEIGHTS_DIR, self._local_name)

        if not os.path.exists(model_path):
            os.makedirs(WEIGHTS_DIR, exist_ok=True)
            print(f"  Downloading {self._model_name} from {self._repo_id}...")
            hf_hub_download(
                repo_id=self._repo_id,
                filename=self._filename,
                local_dir=WEIGHTS_DIR,
                local_dir_use_symlinks=False,
            )
            # hf_hub_download places the file at WEIGHTS_DIR/filename,
            # which preserves subdirs like weights/YOLOv11-S/file.pt
            downloaded = os.path.join(WEIGHTS_DIR, self._filename)
            if downloaded != model_path:
                os.makedirs(os.path.dirname(model_path), exist_ok=True)
                os.rename(downloaded, model_path)
                # Clean up empty parent dirs left behind
                parent = os.path.dirname(downloaded)
                if parent != WEIGHTS_DIR and not os.listdir(parent):
                    os.rmdir(parent)
            print(f"  Downloaded {self._local_name}")

        self._model = YOLO(model_path)
        self._classes = list(self._model.names.values())

    def detect(self, frame) -> list[dict]:
        if self._model is None:
            raise RuntimeError(f"Model {self._model_name} not loaded. Call load() first.")

        results = self._model.predict(source=frame, conf=0.35, verbose=False)
        detections = []
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                cls_name = self._model.names[cls_id]
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                detections.append({
                    "bbox": (x1, y1, x2, y2),
                    "class": cls_name,
                    "confidence": conf,
                })
        return detections


def create_yolov8():
    return YOLOModel(
        repo_id="gayatrigovindasetty/vehicle-detection-yolov8",
        filename="best.pt",
        model_name="YOLOv8n",
        local_name="yolov8n_best.pt",
        classes=["auto", "bus", "car", "lcv", "motorcycle", "multiaxle", "tractor", "truck"],
    )


def create_yolov11s():
    return YOLOModel(
        repo_id="iisc-aim/UVH-26",
        filename="weights/YOLOv11-S/UVH-26-MV-YOLOv11-S.pt",
        model_name="YOLOv11-S (UVH-26)",
        local_name="yolov11s_uvh26.pt",
        classes=[],
    )


def create_yolov11x():
    return YOLOModel(
        repo_id="iisc-aim/UVH-26",
        filename="weights/YOLOv11-X/UVH-26-MV-YOLOv11-X.pt",
        model_name="YOLOv11-X (UVH-26)",
        local_name="yolov11x_uvh26.pt",
        classes=[],
    )
