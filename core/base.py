"""Model interface shared by every detector in models/.

A model is responsible for three things and nothing else: reporting what it
is, loading its weights, and turning a BGR frame into a list of Detection.
Tracking, counting, drawing and file output all live in core.processor, so
adding a new detector never means touching the pipeline.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from core import taxonomy


@dataclass
class Detection:
    """One detected vehicle in one frame.

    native_class is the label the model itself produced; canonical_class is
    that label mapped onto the shared taxonomy. Both are carried through to
    the CSV so per-model detail survives alongside cross-model comparability.
    """

    bbox: tuple[float, float, float, float]  # xyxy, pixels
    confidence: float
    native_class: str
    canonical_class: str


class BaseModel(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Display name, also used to build output filenames."""

    @property
    @abstractmethod
    def native_classes(self) -> list[str]:
        """Labels this model emits in its own vocabulary."""

    @property
    def canonical_classes(self) -> list[str]:
        """Canonical classes this model is capable of emitting.

        Used when scoring against ground truth: a class a model cannot
        express (RT-DETR has no notion of a three-wheeler) is a limitation of
        its taxonomy, not a detection miss, and should be reported as such.
        """
        return taxonomy.canonical_set(self.native_classes)

    @abstractmethod
    def load(self):
        """Fetch weights if needed and prepare for inference."""

    @abstractmethod
    def detect(self, frame) -> list[Detection]:
        """Detect vehicles in a single BGR frame."""

    def make_detection(self, bbox, confidence: float, native_class: str) -> Detection:
        """Build a Detection, applying the canonical mapping."""
        return Detection(
            bbox=tuple(bbox),
            confidence=float(confidence),
            native_class=native_class,
            canonical_class=taxonomy.to_canonical(native_class),
        )
