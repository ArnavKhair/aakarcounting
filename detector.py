import os
import torch
from huggingface_hub import hf_hub_download
from ultralytics import YOLO

MODEL_REPO = "gayatrigovindasetty/vehicle-detection-yolov8"
MODEL_FILE = "best.pt"
VEHICLE_CLASSES = [
    "auto", "bus", "car", "lcv",
    "motorcycle", "multiaxle", "tractor", "truck",
]

CLASS_COLORS = {
    "auto": (0, 255, 255),
    "bus": (255, 0, 0),
    "car": (0, 255, 0),
    "lcv": (255, 255, 0),
    "motorcycle": (0, 128, 255),
    "multiaxle": (128, 0, 255),
    "tractor": (255, 128, 0),
    "truck": (0, 0, 255),
}


def get_device():
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load_model():
    device = get_device()
    print(f"Using device: {device}")

    model_path = os.path.join("models", MODEL_FILE)
    if not os.path.exists(model_path):
        os.makedirs("models", exist_ok=True)
        print(f"Downloading model from HuggingFace: {MODEL_REPO}...")
        hf_hub_download(
            repo_id=MODEL_REPO,
            filename=MODEL_FILE,
            local_dir="models",
        )
        print("Model downloaded.")

    model = YOLO(model_path)
    return model, device


def detect_frame(model, frame, conf_threshold=0.35):
    results = model.predict(
        source=frame,
        conf=conf_threshold,
        verbose=False,
    )
    detections = []
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            if cls_name not in VEHICLE_CLASSES:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = float(box.conf[0])
            detections.append({
                "bbox": (x1, y1, x2, y2),
                "class": cls_name,
                "confidence": conf,
            })
    return detections
