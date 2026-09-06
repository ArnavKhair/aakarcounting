"""YOLOv8n fine-tuned on 8 Indian vehicle classes.

Smallest model in the comparison (~3.2M parameters). Useful as a speed
reference; its capacity is the limiting factor on distant or occluded
vehicles.
"""
from models._ultralytics import UltralyticsModel

NATIVE_CLASSES = [
    "auto", "bus", "car", "lcv",
    "motorcycle", "multiaxle", "tractor", "truck",
]

DISPLAY_NAME = "YOLOv8n"


def create():
    return UltralyticsModel(
        repo_id="gayatrigovindasetty/vehicle-detection-yolov8",
        filename="best.pt",
        model_name=DISPLAY_NAME,
        local_name="yolov8n_best.pt",
        declared_classes=NATIVE_CLASSES,
    )
