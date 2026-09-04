import csv
import json
import os
import threading
import time
from collections import defaultdict

import cv2
import numpy as np
import supervision as sv

from models.base import BaseModel

CLASS_COLORS = {
    "auto": (0, 255, 255),
    "bus": (255, 0, 0),
    "car": (0, 255, 0),
    "lcv": (255, 255, 0),
    "motorcycle": (0, 128, 255),
    "multiaxle": (128, 0, 255),
    "tractor": (255, 128, 0),
    "truck": (0, 0, 255),
    "Hatchback": (0, 255, 128),
    "Sedan": (255, 128, 255),
    "SUV": (128, 255, 0),
    "MUV": (0, 128, 128),
    "Three-wheeler": (255, 64, 0),
    "Two-wheeler": (64, 0, 255),
    "Mini-bus": (0, 64, 255),
    "tempo-traveller": (192, 0, 192),
    "bicycle": (0, 192, 192),
    "Van": (192, 192, 0),
    "Others": (128, 128, 128),
    "motorbike": (0, 128, 255),
    "bicycle": (0, 192, 192),
}


def draw_overlay(frame, detections, tracker_ids, class_names, confidences,
                 line_zone, model_name, frame_num, total_frames):
    annotated = frame.copy()

    line_y = line_zone.line.center.y if hasattr(line_zone, 'line') else frame.shape[0] // 2
    cv2.line(annotated, (0, int(line_y)), (frame.shape[1], int(line_y)), (255, 255, 255), 2)
    cv2.putText(annotated, f"IN:{line_zone.in_count} OUT:{line_zone.out_count}",
                (10, int(line_y) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    for i in range(len(detections)):
        x1, y1, x2, y2 = map(int, detections[i])
        cls = class_names[i]
        conf = confidences[i]
        tid = tracker_ids[i] if tracker_ids[i] is not None else -1
        color = CLASS_COLORS.get(cls, (255, 255, 255))

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        label = f"{cls} {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
        cv2.putText(annotated, label, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        cv2.circle(annotated, (cx, cy), 4, (255, 255, 255), -1)
        cv2.putText(annotated, str(tid), (cx + 5, cy - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    info = f"{model_name} | {frame_num}/{total_frames}"
    cv2.putText(annotated, info, (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    return annotated


def run_single_model(model: BaseModel, video_path: str, output_dir: str,
                     progress_callback=None, status_callback=None,
                     frame_callback=None, stop_event=None,
                     upscaler=None):
    model_name_safe = model.name.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")
    csv_path = os.path.join(output_dir, f"vehicle_counts_{model_name_safe}.csv")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    tracker = sv.ByteTrack(
        frame_rate=fps,
        track_activation_threshold=0.5,
        minimum_matching_threshold=0.8,
        lost_track_buffer=60,
        minimum_consecutive_frames=3,
    )
    smoother = sv.DetectionsSmoother(length=5)

    line_zone = None

    frame_data = []
    unique_vehicles = {}
    unique_class_counts = defaultdict(int)
    total_detections = 0

    start_time = time.time()
    frame_num = 0
    partial = False

    while True:
        if stop_event and stop_event.is_set():
            partial = True
            break

        ret, frame = cap.read()
        if not ret:
            break

        if upscaler is not None:
            frame = upscaler.upscale(frame)

        if line_zone is None:
            actual_h, actual_w = frame.shape[:2]
            line_start = sv.Point(x=0, y=actual_h // 2)
            line_end = sv.Point(x=actual_w, y=actual_h // 2)
            line_zone = sv.LineZone(start=line_start, end=line_end)

        raw_detections = model.detect(frame)
        det_bboxes = []
        det_tracker_ids = []
        det_class_names = []
        det_confidences = []

        if raw_detections:
            bboxes = np.array([d["bbox"] for d in raw_detections], dtype=np.float32)
            confidences = np.array([d["confidence"] for d in raw_detections], dtype=np.float32)
            class_names = [d["class"] for d in raw_detections]

            sv_detections = sv.Detections(
                xyxy=bboxes,
                confidence=confidences,
            )
            sv_detections = tracker.update_with_detections(sv_detections)
            sv_detections = smoother.update_with_detections(sv_detections)

            crossed_in, crossed_out = line_zone.trigger(sv_detections)

            for i in range(len(sv_detections)):
                tracker_id = int(sv_detections.tracker_id[i])
                cls_name = class_names[i]
                conf = float(sv_detections.confidence[i])

                total_detections += 1

                key = (tracker_id, cls_name)
                if key not in unique_vehicles:
                    unique_vehicles[key] = frame_num
                    unique_class_counts[cls_name] += 1

                timestamp = frame_num / fps
                frame_data.append({
                    "frame": frame_num,
                    "timestamp": round(timestamp, 3),
                    "vehicle_type": cls_name,
                    "confidence": round(conf, 4),
                    "tracker_id": tracker_id,
                })

                det_bboxes.append(sv_detections.xyxy[i])
                det_tracker_ids.append(tracker_id)
                det_class_names.append(cls_name)
                det_confidences.append(conf)

        if frame_callback and frame_num % 2 == 0:
            annotated = draw_overlay(
                frame, det_bboxes, det_tracker_ids, det_class_names,
                det_confidences, line_zone, model.name, frame_num, total_frames
            )
            frame_callback(annotated, frame_num, total_frames)

        frame_num += 1
        if progress_callback:
            progress_callback(frame_num, total_frames)
        if status_callback and frame_num % 30 == 0:
            status_callback(f"[{model.name}] Frame {frame_num}/{total_frames}")

    elapsed = time.time() - start_time
    cap.release()

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "frame", "timestamp", "vehicle_type", "confidence", "tracker_id"
        ])
        writer.writeheader()
        writer.writerows(frame_data)

    return {
        "model_name": model.name,
        "classes": model.classes,
        "total_frames": frame_num,
        "processing_fps": round(frame_num / elapsed, 1) if elapsed > 0 else 0,
        "elapsed_seconds": round(elapsed, 2),
        "detections_per_frame": round(total_detections / max(frame_num, 1), 2),
        "total_detections": total_detections,
        "total_unique_vehicles": len(unique_vehicles),
        "line_zone_crossings_in": line_zone.in_count,
        "line_zone_crossings_out": line_zone.out_count,
        "vehicle_counts": dict(sorted(unique_class_counts.items(), key=lambda x: -x[1])),
        "csv_path": csv_path,
        "partial": partial,
    }


def process_video_multi(video_path, output_dir, models: list[BaseModel],
                        progress_callback=None, status_callback=None,
                        frame_callback=None, stop_event=None,
                        upscaler=None):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if upscaler is not None:
        if status_callback:
            status_callback("Loading upscaler...")
        upscaler.load()
        if status_callback:
            status_callback("Upscaler ready")

    video_name = os.path.splitext(os.path.basename(video_path))[0]
    results = {
        "video": video_path,
        "video_name": video_name,
        "resolution": f"{width}x{height}",
        "upscaled": upscaler is not None,
        "fps": fps,
        "total_frames": total_frames,
        "models": {},
    }

    for i, model in enumerate(models):
        if stop_event and stop_event.is_set():
            break

        if status_callback:
            status_callback(f"Loading model {i+1}/{len(models)}: {model.name}")

        model.load()

        if status_callback:
            status_callback(f"Processing with {model.name}...")

        def model_progress(current, total):
            overall = ((i * total_frames + current) / (len(models) * total_frames)) * 100
            if progress_callback:
                progress_callback(overall)

        model_result = run_single_model(
            model, video_path, output_dir,
            progress_callback=model_progress,
            status_callback=status_callback,
            frame_callback=frame_callback,
            stop_event=stop_event,
            upscaler=upscaler,
        )
        results["models"][model.name] = model_result

    summary_csv_path = os.path.join(output_dir, "vehicle_summary.csv")
    with open(summary_csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["model", "vehicle_class", "count"])
        for model_name, model_data in results["models"].items():
            for cls, count in model_data["vehicle_counts"].items():
                writer.writerow([model_name, cls, count])

    json_path = os.path.join(output_dir, "summary.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    results["output_dir"] = output_dir

    if status_callback:
        status_callback("All models complete!")

    return results
