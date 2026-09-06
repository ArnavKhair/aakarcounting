"""Annotated-frame rendering for the live preview.

Deliberately independent of supervision: the caller passes the counting
line's y position and the running totals as plain values, so a rename in the
tracking library cannot silently break the overlay.
"""
import cv2

from core import taxonomy

_FONT = cv2.FONT_HERSHEY_SIMPLEX
_WHITE = (255, 255, 255)


def draw(frame, tracked, line_y, in_count, out_count,
         model_name, frame_num, total_frames, counted=None):
    """Draw boxes, track IDs, the counting line and a status banner.

    tracked is a list of TrackedDetection; colours come from the canonical
    class so the same vehicle type looks the same across every model.
    """
    annotated = frame.copy()
    height, width = annotated.shape[:2]

    line_y = int(line_y if line_y is not None else height // 2)
    cv2.line(annotated, (0, line_y), (width, line_y), _WHITE, 2)
    banner = f"IN:{in_count} OUT:{out_count}"
    if counted is not None:
        # Raw line-zone triggers vs. crossings that survive the track-length
        # filter; the second number is the one that gets reported.
        banner += f"  COUNTED:{counted}"
    cv2.putText(annotated, banner, (10, line_y - 10), _FONT, 0.7, _WHITE, 2)

    for det in tracked:
        x1, y1, x2, y2 = map(int, det.bbox)
        color = taxonomy.CANONICAL_COLORS.get(det.canonical_class, _WHITE)

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        label = f"{det.native_class} {det.confidence:.2f}"
        (text_w, text_h), _ = cv2.getTextSize(label, _FONT, 0.5, 1)
        cv2.rectangle(annotated, (x1, y1 - text_h - 8), (x1 + text_w + 4, y1), color, -1)
        cv2.putText(annotated, label, (x1 + 2, y1 - 4), _FONT, 0.5, _WHITE, 1)

        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        cv2.circle(annotated, (cx, cy), 4, _WHITE, -1)
        cv2.putText(annotated, str(det.tracker_id), (cx + 5, cy - 5), _FONT, 0.5, _WHITE, 1)

    cv2.putText(annotated, f"{model_name} | {frame_num}/{total_frames}",
                (10, 25), _FONT, 0.6, (0, 255, 0), 2)

    return annotated
