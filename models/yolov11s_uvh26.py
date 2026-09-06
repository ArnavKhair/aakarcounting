"""YOLOv11-S trained on UVH-26 (AIM@IISc).

Trained for Indian vehicle heterogeneity, so its taxonomy is the closest
match to the traffic being counted. Real class names come from the
checkpoint at load time; the list below is only a placeholder for the UI.
"""
from models._ultralytics import UltralyticsModel

DISPLAY_NAME = "YOLOv11-S (UVH-26)"


def create():
    return UltralyticsModel(
        repo_id="iisc-aim/UVH-26",
        filename="weights/YOLOv11-S/UVH-26-MV-YOLOv11-S.pt",
        model_name=DISPLAY_NAME,
        local_name="yolov11s_uvh26.pt",
        declared_classes=[],
    )
