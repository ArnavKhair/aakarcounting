"""Annotated-frame rendering for the live preview.

Deliberately independent of supervision: the caller passes the counting
line's y position and the running totals as plain values, so a rename in the
tracking library cannot silently break the overlay.
"""
import cv2

from core import taxonomy

_FONT = cv2.FONT_HERSHEY_SIMPLEX
_WHITE = (255, 255, 255)


def draw(frame, tracked, line_y, model_name, frame_num, total_frames,
         counted=None, counting_lines=None, road_labels=None, road_counts=None):
    """Draw boxes, track IDs, the counting line(s) and a status banner.

    tracked is a list of TrackedDetection; colours come from the canonical
    class so the same vehicle type looks the same across every model.

    counting_lines: optional list of (start_x, start_y, end_x, end_y) tuples
    for user-drawn lines. When provided, these are drawn instead of the default
    horizontal line.
    road_labels: optional list of road name strings, one per counting line.
    road_counts: optional dict of {road_name: count} for live per-road counts.
    """
    annotated = frame.copy()
    height, width = annotated.shape[:2]

    if counting_lines:
        # Draw user-drawn counting lines with road labels and counts
        for i, (sx, sy, ex, ey) in enumerate(counting_lines):
            cv2.line(annotated, (int(sx), int(sy)), (int(ex), int(ey)),
                    _WHITE, 2)
            # Draw endpoint markers
            cv2.circle(annotated, (int(sx), int(sy)), 5, _WHITE, -1)
            cv2.circle(annotated, (int(ex), int(ey)), 5, _WHITE, -1)
            cv2.circle(annotated, (int(sx), int(sy)), 3, (0, 0, 255), -1)
            cv2.circle(annotated, (int(ex), int(ey)), 3, (0, 0, 255), -1)

            # Draw road label + count near the line midpoint
            mid_x = (sx + ex) / 2
            mid_y = (sy + ey) / 2
            label = road_labels[i] if road_labels and i < len(road_labels) else f"Road {i + 1}"
            count = road_counts.get(label, 0) if road_counts else 0
            text = f"{label}: {count}"

            # Position label above the line midpoint
            font_scale = 0.6
            thickness = 2
            (tw, th), _ = cv2.getTextSize(text, _FONT, font_scale, thickness)
            tx = int(mid_x - tw / 2)
            ty = int(mid_y - 10)

            # Draw background rectangle for readability
            cv2.rectangle(annotated, (tx - 4, ty - th - 4), (tx + tw + 4, ty + 4),
                         (0, 0, 0), -1)
            cv2.putText(annotated, text, (tx, ty), _FONT, font_scale,
                       (0, 255, 0), thickness)
    else:
        # Default horizontal line
        line_y = int(line_y if line_y is not None else height // 2)
        cv2.line(annotated, (0, line_y), (width, line_y), _WHITE, 2)

    # Status banner at top-left
    banner = f"COUNTED:{counted}" if counted is not None else ""
    if banner:
        cv2.putText(annotated, banner, (10, 25), _FONT, 0.7, _WHITE, 2)

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

    # Model/frame info at bottom-left
    model_banner = f"{model_name} | {frame_num}/{total_frames}"
    cv2.putText(annotated, model_banner,
                (10, height - 10), _FONT, 0.6, (0, 255, 0), 2)

    return annotated
