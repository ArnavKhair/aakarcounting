"""Canonical vehicle taxonomy shared by every detection model.

Each model speaks its own vocabulary: RT-DETR emits 4 COCO labels, YOLOv8n
emits 8 Indian classes, UVH-26 emits 14. Those vocabularies are not directly
comparable, so a "car" count from one model and a "Sedan" count from another
cannot be added, differenced, or scored against the same ground truth.

Every model therefore maps its native label onto the canonical set below.
The native label is preserved alongside the canonical one, so mapping loses
no information -- it only adds a common axis for comparison.
"""

TWO_WHEELER = "two_wheeler"
THREE_WHEELER = "three_wheeler"
CAR = "car"
LCV = "lcv"
BUS = "bus"
TRUCK = "truck"
MULTI_AXLE = "multi_axle"
TRACTOR = "tractor"
BICYCLE = "bicycle"
OTHER = "other"

CANONICAL_CLASSES = [
    TWO_WHEELER,
    THREE_WHEELER,
    CAR,
    LCV,
    BUS,
    TRUCK,
    MULTI_AXLE,
    TRACTOR,
    BICYCLE,
    OTHER,
]

# BGR, for OpenCV overlays.
CANONICAL_COLORS = {
    TWO_WHEELER: (0, 128, 255),
    THREE_WHEELER: (0, 255, 255),
    CAR: (0, 255, 0),
    LCV: (255, 255, 0),
    BUS: (255, 0, 0),
    TRUCK: (0, 0, 255),
    MULTI_AXLE: (128, 0, 255),
    TRACTOR: (255, 128, 0),
    BICYCLE: (0, 192, 192),
    OTHER: (128, 128, 128),
}

# Normalised native label -> canonical class. Keys are lower-cased with
# separators collapsed to single spaces; see _normalise().
_ALIASES = {
    # two-wheelers
    "motorcycle": TWO_WHEELER,
    "motorbike": TWO_WHEELER,
    "motor bike": TWO_WHEELER,
    "two wheeler": TWO_WHEELER,
    "twowheeler": TWO_WHEELER,
    "2 wheeler": TWO_WHEELER,
    "scooter": TWO_WHEELER,
    "bike": TWO_WHEELER,
    # three-wheelers
    "auto": THREE_WHEELER,
    "auto rickshaw": THREE_WHEELER,
    "autorickshaw": THREE_WHEELER,
    "rickshaw": THREE_WHEELER,
    "three wheeler": THREE_WHEELER,
    "threewheeler": THREE_WHEELER,
    "3 wheeler": THREE_WHEELER,
    # passenger cars
    "car": CAR,
    "hatchback": CAR,
    "sedan": CAR,
    "suv": CAR,
    "muv": CAR,
    "van": CAR,
    "jeep": CAR,
    "taxi": CAR,
    # light commercial
    "lcv": LCV,
    "light commercial vehicle": LCV,
    "tempo": LCV,
    "pickup": LCV,
    "pick up": LCV,
    "mini truck": LCV,
    "minitruck": LCV,
    # buses
    "bus": BUS,
    "mini bus": BUS,
    "minibus": BUS,
    "tempo traveller": BUS,
    "tempo traveler": BUS,
    # rigid trucks
    "truck": TRUCK,
    "lorry": TRUCK,
    "hcv": TRUCK,
    # multi-axle / articulated
    "multiaxle": MULTI_AXLE,
    "multi axle": MULTI_AXLE,
    "multiaxle truck": MULTI_AXLE,
    "trailer": MULTI_AXLE,
    "articulated truck": MULTI_AXLE,
    # farm
    "tractor": TRACTOR,
    # cycles
    "bicycle": BICYCLE,
    "cycle": BICYCLE,
    # catch-all
    "others": OTHER,
    "other": OTHER,
    "unknown": OTHER,
    "misc": OTHER,
}

_unmapped_seen = set()


def _normalise(label: str) -> str:
    text = str(label).strip().lower()
    for separator in ("-", "_", "/", "."):
        text = text.replace(separator, " ")
    return " ".join(text.split())


def to_canonical(native_label: str) -> str:
    """Map a model's native label onto the canonical taxonomy.

    Unrecognised labels fall back to OTHER and are recorded once so they can
    be surfaced after a run -- a checkpoint whose class names we have not seen
    should show up as a warning, not silently vanish into OTHER.
    """
    key = _normalise(native_label)
    canonical = _ALIASES.get(key)
    if canonical is None:
        _unmapped_seen.add(str(native_label))
        return OTHER
    return canonical


def canonical_set(native_labels) -> list[str]:
    """Canonical classes reachable from a list of native labels, in taxonomy order."""
    mapped = {to_canonical(label) for label in native_labels}
    return [cls for cls in CANONICAL_CLASSES if cls in mapped]


def unmapped_labels() -> list[str]:
    """Native labels seen this session that had no alias entry."""
    return sorted(_unmapped_seen)


def reset_unmapped():
    _unmapped_seen.clear()
