"""Aakar's vehicle categories, and how the model's labels map onto them.

Aakar reports traffic in 16 categories. The model (UVH-26) reports 14 of its
own, and the two sets do not line up one to one: several model labels fold
into one Aakar category, and six Aakar categories describe a distinction the
model was never trained to make (a taxi from a private car, a government bus
from a private one, the number of axles on a truck).

Those six are still listed, so a report lines up row for row with Aakar's
own sheet, but they carry no count of their own. Their vehicles are counted
in the neighbouring category named in COUNTED_IN, and the report says so.

This file is the only place the mapping lives. Teaching the software to
separate one of the six later means giving it an entry in _MODEL_LABELS and
removing it from COUNTED_IN.
"""
from core.taxonomy import _normalise

OTHER = "Other"

# Aakar's order, as on their count sheet.
CATEGORIES = [
    "Cars/Vans/Jeeps",
    "Taxi",
    "Auto Rickshaw",
    "6/8 seater",
    "Two Wheeler",
    "Cycle",
    "Mini Bus",
    "Private Bus",
    "Govt. Bus",
    "Goods Auto",
    "Mini LCV",
    "LCV",
    "2 Axle Truck",
    "3 Axle Truck",
    "MAV",
    OTHER,
]

# Category -> the model labels counted in it, spelled as the model spells
# them, because these are shown in brackets beside the category name.
_MODEL_LABELS = {
    "Cars/Vans/Jeeps": ["Hatchback", "Sedan", "SUV", "Van"],
    "Auto Rickshaw": ["Three-wheeler"],
    "6/8 seater": ["MUV"],
    "Two Wheeler": ["Two-wheeler"],
    "Cycle": ["bicycle"],
    # Tempo traveller under Mini Bus is our reading, not yet confirmed by Aakar.
    "Mini Bus": ["Mini-bus", "tempo-traveller"],
    "Private Bus": ["Bus"],
    "LCV": ["LCV"],
    "2 Axle Truck": ["Truck"],
    OTHER: ["Others"],
}

# Category with no count of its own -> the category its vehicles are counted in.
COUNTED_IN = {
    "Taxi": "Cars/Vans/Jeeps",
    "Govt. Bus": "Private Bus",
    "Goods Auto": "Auto Rickshaw",
    "Mini LCV": "LCV",
    "3 Axle Truck": "2 Axle Truck",
    "MAV": "2 Axle Truck",
}

_FROM_MODEL = {
    _normalise(label): category
    for category, labels in _MODEL_LABELS.items()
    for label in labels
}


def to_category(model_label: str) -> str:
    """Aakar category for one model label. A label with no mapping is Other,
    so a vehicle is never dropped from the totals."""
    return _FROM_MODEL.get(_normalise(model_label), OTHER)


def heading(category: str) -> str:
    """The category with the model's classification in brackets, e.g.
    "Cars/Vans/Jeeps (Hatchback, Sedan, SUV, Van)". A category the model
    cannot separate has nothing to put in brackets."""
    labels = _MODEL_LABELS.get(category)
    if not labels:
        return category
    return f"{category} ({', '.join(labels)})"


def count_by_category(by_type: dict) -> dict:
    """Counts per model label -> counts for all 16 categories, in order.

    A category the model cannot separate is None (shown as a dash), which is
    not the same as 0: zero means none were seen.
    """
    counts = {c: (None if c in COUNTED_IN else 0) for c in CATEGORIES}
    for label, count in (by_type or {}).items():
        counts[to_category(label)] += count
    return counts


def _join(names: list) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def notes_for(counts: dict) -> list:
    """One line per category that is carrying another's vehicles, for the
    categories that actually have a count: "Private Bus includes Govt. Bus"."""
    notes = []
    for category in CATEGORIES:
        if not counts.get(category):
            continue
        carried = [c for c in CATEGORIES if COUNTED_IN.get(c) == category]
        if carried:
            notes.append(f"{category} includes {_join(carried)}")
    return notes


def legend() -> list:
    """One line per dash row, saying where its vehicles are counted."""
    return [f"{c}: counted in {COUNTED_IN[c]}" for c in CATEGORIES if c in COUNTED_IN]
