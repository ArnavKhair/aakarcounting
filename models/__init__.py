"""Registry of available detection models.

One file per model in this package; this module is the only place that knows
the full set. Adding a model means writing models/<name>.py with a create()
factory and adding one MODEL_REGISTRY entry -- nothing in the GUI or the
processing pipeline needs to change.

Factories are imported lazily so that starting the app does not pull in
ultralytics, transformers and onnxruntime, and so a missing optional
dependency only breaks the model that needs it.
"""
import importlib
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    key: str
    display_name: str
    module: str
    default_enabled: bool
    description: str

    def create(self):
        """Import the model's module and build an unloaded instance."""
        return importlib.import_module(self.module).create()


MODEL_REGISTRY: dict[str, ModelSpec] = {
    spec.key: spec
    for spec in [
        ModelSpec(
            key="yolov8n",
            display_name="YOLOv8n",
            module="models.yolov8n",
            default_enabled=True,
            description="8 Indian classes. Smallest model; speed reference.",
        ),
        ModelSpec(
            key="yolov11s_uvh26",
            display_name="YOLOv11-S (UVH-26)",
            module="models.yolov11s_uvh26",
            default_enabled=True,
            description="UVH-26 taxonomy. Best accuracy/speed balance.",
        ),
        ModelSpec(
            key="yolov11x_uvh26",
            display_name="YOLOv11-X (UVH-26)",
            module="models.yolov11x_uvh26",
            default_enabled=True,
            description="UVH-26 taxonomy at high capacity. Slow on Apple Silicon.",
        ),
        ModelSpec(
            key="rtdetr",
            display_name="RT-DETR (r50vd)",
            module="models.rtdetr",
            default_enabled=True,
            description="COCO-pretrained generic baseline. 4 classes only.",
        ),
        ModelSpec(
            key="vehicledino",
            display_name="VehicleDINO",
            module="models.vehicledino",
            default_enabled=False,
            description="ONNX INT8. Output decoding unverified; slow on CPU.",
        ),
    ]
}


def get(key: str) -> ModelSpec:
    return MODEL_REGISTRY[key]


def create(key: str):
    return MODEL_REGISTRY[key].create()


def all_specs() -> list[ModelSpec]:
    return list(MODEL_REGISTRY.values())
