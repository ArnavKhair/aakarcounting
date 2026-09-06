"""YOLOv11-X trained on UVH-26 (AIM@IISc).

Same training data as the -S variant at much larger capacity: the accuracy
ceiling of this comparison, and the slowest of the YOLO models on Apple
Silicon.
"""
from models._ultralytics import UltralyticsModel

DISPLAY_NAME = "YOLOv11-X (UVH-26)"


def create():
    return UltralyticsModel(
        repo_id="iisc-aim/UVH-26",
        filename="weights/YOLOv11-X/UVH-26-MV-YOLOv11-X.pt",
        model_name=DISPLAY_NAME,
        local_name="yolov11x_uvh26.pt",
        declared_classes=[],
    )
