import csv
import json
import os
from collections import defaultdict

import cv2

from detector import CLASS_COLORS


def draw_detections(frame, detections, tracker_objects):
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        cls = det["class"]
        conf = det["confidence"]
        color = CLASS_COLORS.get(cls, (255, 255, 255))

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        label = f"{cls} {conf:.2f}"
        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, y1 - h - 10), (x1 + w, y1), color, -1)
        cv2.putText(frame, label, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    for obj_id, centroid in tracker_objects.items():
        cx, cy = int(centroid[0]), int(centroid[1])
        cv2.circle(frame, (cx, cy), 4, (255, 255, 255), -1)
        cv2.putText(frame, str(obj_id), (cx + 5, cy - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return frame


def create_video_writer(output_path, width, height, fps):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    return writer


def save_frame_counts(csv_path, frame_data):
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["frame", "timestamp", "vehicle_type", "count"])
        writer.writeheader()
        writer.writerows(frame_data)


def save_summary(json_path, tracker, fps, total_frames):
    counts = tracker.get_total_counts()
    history = tracker.get_history()

    unique_by_class = defaultdict(int)
    for entry in history:
        unique_by_class[entry["class"]] += 1

    summary = {
        "total_vehicles_detected": sum(unique_by_class.values()),
        "unique_vehicles_by_class": dict(unique_by_class),
        "total_frames_processed": total_frames,
        "video_fps": fps,
        "detections_per_frame": len(history) / max(total_frames, 1),
    }

    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)

    return summary
