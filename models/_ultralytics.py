"""Shared loading and inference for the Ultralytics YOLO checkpoints.

The three YOLO models in this project differ only in which HuggingFace
checkpoint they pull, so the mechanics live here and each model file supplies
its own identity and weights.
"""
import os

from huggingface_hub import hf_hub_download
from ultralytics import YOLO

from core import config
from core.base import BaseModel, Detection
from core.paths import WEIGHTS_DIR, ensure_weights_dir


class UltralyticsModel(BaseModel):
    def __init__(self, repo_id: str, filename: str, model_name: str,
                 local_name: str, declared_classes: list[str] | None = None,
                 conf: float = config.DEFAULT_CONFIDENCE):
        self._repo_id = repo_id
        self._filename = filename
        self._model_name = model_name
        self._local_name = local_name
        # Declared up front so the UI can describe a model before it is
        # loaded; replaced with the checkpoint's real names at load().
        self._native_classes = list(declared_classes or [])
        self._conf = conf
        self._model = None

    @property
    def name(self) -> str:
        return self._model_name

    @property
    def native_classes(self) -> list[str]:
        return self._native_classes

    @property
    def weights_path(self) -> str:
        return os.path.join(WEIGHTS_DIR, self._local_name)

    def _download(self):
        ensure_weights_dir()
        print(f"  Downloading {self._model_name} from {self._repo_id}...")
        hf_hub_download(
            repo_id=self._repo_id,
            filename=self._filename,
            local_dir=WEIGHTS_DIR,
            local_dir_use_symlinks=False,
        )
        # hf_hub_download preserves the repo's subdirectories, so a filename
        # like "weights/YOLOv11-S/model.pt" lands nested. Flatten it onto the
        # local name we expect, then clear the empty directories it left.
        downloaded = os.path.join(WEIGHTS_DIR, self._filename)
        target = self.weights_path
        if downloaded != target:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.rename(downloaded, target)
            parent = os.path.dirname(downloaded)
            while parent != WEIGHTS_DIR and os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)
                parent = os.path.dirname(parent)
        print(f"  Downloaded {self._local_name}")

    def load(self):
        if not os.path.exists(self.weights_path):
            self._download()

        self._model = YOLO(self.weights_path)
        # The checkpoint is the authority on class names -- the declared list
        # is only a placeholder for the UI.
        self._native_classes = list(self._model.names.values())

    def detect(self, frame) -> list[Detection]:
        if self._model is None:
            raise RuntimeError(f"{self._model_name} not loaded. Call load() first.")

        # Run at the frame's own resolution rather than the Ultralytics
        # default of 640. On 720p input that default halves every object
        # before the network sees it, which is what was losing distant
        # two-wheelers.
        results = self._model.predict(
            source=frame,
            conf=self._conf,
            imgsz=config.resolve_imgsz(frame),
            verbose=False,
        )

        detections = []
        for result in results:
            for box in result.boxes:
                native_class = self._model.names[int(box.cls[0])]
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                detections.append(
                    self.make_detection((x1, y1, x2, y2), float(box.conf[0]), native_class)
                )
        return detections
