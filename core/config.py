"""All tuning knobs in one place, so a parameter sweep is one file to edit.

Values here were chosen from measurements on 720p CCTV footage; the reasoning
is in the comments. Change them together with a re-run against known manual
counts, not in isolation.
"""
import math

# --- Detection -------------------------------------------------------------

# Confidence floor for every detector. Deliberately lower than a per-frame
# "looks right" threshold: a marginal detection that persists across frames is
# rescued by tracking, and a spurious one is rejected at counting time by
# MIN_TRACK_FRAMES_TO_COUNT. Detect low, count strict.
DEFAULT_CONFIDENCE = 0.25

# Inference resolution. None means "match the video": the frame is fed to the
# detector at its own size instead of being letterboxed down to a fixed 640,
# which is what was costing distant vehicles half their pixels. Set an int to
# force a specific long-side size.
INFERENCE_SIZE = None

# Detector input dimensions must be a multiple of this.
STRIDE = 32


# --- Tracking --------------------------------------------------------------

TRACK_ACTIVATION_THRESHOLD = 0.5
MINIMUM_MATCHING_THRESHOLD = 0.8
LOST_TRACK_BUFFER = 60

# Must stay at 1. At 3, ByteTrack never emits a track whose per-frame
# displacement exceeds roughly 0.4-0.5x its box height -- measured, not
# guessed. On 720p footage that silently deletes far-field two-wheelers and
# autos entirely, and churns IDs (one vehicle counted 6-8 times) just below
# that threshold. False positives are filtered at counting time instead.
MINIMUM_CONSECUTIVE_FRAMES = 1

SMOOTHER_LENGTH = 5


# --- Counting --------------------------------------------------------------

# A line crossing only counts if the tracker was seen at least this many
# frames over its whole life. This replaces MINIMUM_CONSECUTIVE_FRAMES as the
# false-positive filter: it rejects flicker without ever making a real vehicle
# invisible to the tracker.
MIN_TRACK_FRAMES_TO_COUNT = 3

# Counting line height as a fraction of frame height.
#
# THIS IS CAMERA-SPECIFIC AND MUST BE SET PER SITE. Since counting is defined
# as line crossings, a line placed off the traffic stream does not undercount
# slightly -- it counts the wrong population entirely.
#
# Measured on the Ahmedabad junction clip (1280x720, camera looking down the
# median, both carriageways running diagonally across the upper half of the
# frame), 600 frames, YOLOv11-S:
#
#     y=360 (0.50)  ->  14 crossings, ALL cars, no two-wheelers at all
#     y=201 (0.28)  ->  20 crossings, mixed
#     y=251 (0.35)  ->  27 crossings, mixed: 16 car, 7 two-wheeler,
#                       3 three-wheeler, 1 LCV
#
# At 0.50 the line sat below the traffic, over the median, and caught only
# vehicles leaving toward the bottom-left corner -- which is why every count
# came back "car". To re-derive this for another camera, plot vehicle
# ground-contact points per image row and put the line through the dense band.
LINE_POSITION = 0.35

PREVIEW_EVERY_N_FRAMES = 2


def round_to_stride(value: int, stride: int = STRIDE) -> int:
    """Round up to the next multiple of the detector stride."""
    return int(math.ceil(value / stride) * stride)


def native_imgsz(frame) -> int:
    """Long-side inference size matching the frame's own resolution."""
    height, width = frame.shape[:2]
    return round_to_stride(max(height, width))


def resolve_imgsz(frame) -> int:
    """Inference size for this frame, honouring INFERENCE_SIZE if set."""
    if INFERENCE_SIZE is not None:
        return round_to_stride(INFERENCE_SIZE)
    return native_imgsz(frame)
