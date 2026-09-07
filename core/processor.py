"""Video processing pipeline: detect -> track -> count crossings -> write.

Model-agnostic. Anything implementing core.base.BaseModel runs through here.

Counting measures vehicles that CROSS THE LINE, not vehicles present in the
frame. A parked car, a vehicle that only ever appears in the background, and a
detection that flickers for two frames all contribute nothing. That matches
how a traffic survey is counted by hand, so the numbers are directly
comparable to manual counts.

Every counted vehicle is recorded twice: in its model's own vocabulary and in
the shared canonical taxonomy (core.taxonomy).
"""
import csv
import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import cv2
import numpy as np
import supervision as sv

from core import config, overlay, taxonomy
from core.base import BaseModel


@dataclass
class TrackedDetection:
    """A detection after it has been through the tracker."""

    bbox: tuple[float, float, float, float]
    tracker_id: int
    native_class: str
    canonical_class: str
    confidence: float


@dataclass
class TrackRecord:
    """What we accumulate about one tracker_id over its lifetime."""

    frames_seen: int = 0
    class_votes: Counter = field(default_factory=Counter)
    confidence_sum: float = 0.0
    first_frame: int | None = None
    last_frame: int | None = None

    def observe(self, frame_num: int, native_class: str, confidence: float):
        self.frames_seen += 1
        self.class_votes[native_class] += 1
        self.confidence_sum += confidence
        if self.first_frame is None:
            self.first_frame = frame_num
        self.last_frame = frame_num

    @property
    def voted_class(self) -> str:
        """The class this track was called most often across its whole life.

        A single frame's label is noisy -- a car briefly reads as an LCV, a
        two-wheeler as a bicycle. Voting over the trajectory is what one
        vehicle, one class actually requires.
        """
        return self.class_votes.most_common(1)[0][0]

    @property
    def mean_confidence(self) -> float:
        return self.confidence_sum / self.frames_seen if self.frames_seen else 0.0


class ClassIndex:
    """Two-way map between class names and the integer ids supervision needs.

    Detections must carry class_id through ByteTrack; without it the tracker
    reorders and drops rows while the caller's class list does not, and labels
    end up on the wrong boxes.
    """

    def __init__(self):
        self._names: list[str] = []
        self._ids: dict[str, int] = {}

    def id_for(self, name: str) -> int:
        if name not in self._ids:
            self._ids[name] = len(self._names)
            self._names.append(name)
        return self._ids[name]

    def name_for(self, class_id: int) -> str:
        return self._names[int(class_id)]


def _safe_filename(name: str) -> str:
    return "".join(
        c if (c.isalnum() or c in "-_") else "_" for c in name.replace(" ", "_")
    ).strip("_")


def run_single_model(model: BaseModel, video_path: str, output_dir: str,
                     progress_callback=None, status_callback=None,
                     frame_callback=None, stop_event=None) -> dict:
    """Run one model over the whole video, counting line crossings."""
    safe_name = _safe_filename(model.name)
    detections_csv = os.path.join(output_dir, f"vehicle_counts_{safe_name}.csv")
    crossings_csv = os.path.join(output_dir, f"crossings_{safe_name}.csv")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    tracker = sv.ByteTrack(
        frame_rate=fps,
        track_activation_threshold=config.TRACK_ACTIVATION_THRESHOLD,
        minimum_matching_threshold=config.MINIMUM_MATCHING_THRESHOLD,
        lost_track_buffer=config.LOST_TRACK_BUFFER,
        minimum_consecutive_frames=config.MINIMUM_CONSECUTIVE_FRAMES,
    )
    smoother = sv.DetectionsSmoother(length=config.SMOOTHER_LENGTH)
    class_index = ClassIndex()

    # Built from the first decoded frame.
    line_zone = None
    line_y = None

    frame_rows = []
    tracks: dict[int, TrackRecord] = defaultdict(TrackRecord)
    crossing_events = []   # one entry per line crossing, class resolved at the end
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

        if line_zone is None:
            height, width = frame.shape[:2]
            line_y = int(height * config.LINE_POSITION)
            line_zone = sv.LineZone(
                start=sv.Point(x=0, y=line_y),
                end=sv.Point(x=width, y=line_y),
            )

        detections = model.detect(frame)
        tracked: list[TrackedDetection] = []

        if detections:
            sv_detections = sv.Detections(
                xyxy=np.array([d.bbox for d in detections], dtype=np.float32),
                confidence=np.array([d.confidence for d in detections], dtype=np.float32),
                # Carrying class_id is what keeps labels attached to their own
                # box through the tracker's filtering and reordering.
                class_id=np.array(
                    [class_index.id_for(d.native_class) for d in detections], dtype=int
                ),
            )
            sv_detections = tracker.update_with_detections(sv_detections)
            sv_detections = smoother.update_with_detections(sv_detections)

            crossed_in, crossed_out = line_zone.trigger(sv_detections)

            for i in range(len(sv_detections)):
                tracker_id = int(sv_detections.tracker_id[i])
                native_class = class_index.name_for(sv_detections.class_id[i])
                canonical_class = taxonomy.to_canonical(native_class)
                confidence = float(sv_detections.confidence[i])

                total_detections += 1
                tracks[tracker_id].observe(frame_num, native_class, confidence)

                if crossed_in[i] or crossed_out[i]:
                    crossing_events.append({
                        "tracker_id": tracker_id,
                        "frame": frame_num,
                        "timestamp": round(frame_num / fps, 3),
                        "direction": "in" if crossed_in[i] else "out",
                    })

                frame_rows.append({
                    "frame": frame_num,
                    "timestamp": round(frame_num / fps, 3),
                    "tracker_id": tracker_id,
                    "vehicle_type": native_class,
                    "canonical_class": canonical_class,
                    "confidence": round(confidence, 4),
                })

                tracked.append(TrackedDetection(
                    bbox=tuple(sv_detections.xyxy[i]),
                    tracker_id=tracker_id,
                    native_class=native_class,
                    canonical_class=canonical_class,
                    confidence=confidence,
                ))

        if frame_callback and frame_num % config.PREVIEW_EVERY_N_FRAMES == 0:
            counted_so_far = sum(
                1 for e in crossing_events
                if tracks[e["tracker_id"]].frames_seen >= config.MIN_TRACK_FRAMES_TO_COUNT
            )
            frame_callback(
                overlay.draw(
                    frame, tracked, line_y,
                    line_zone.in_count, line_zone.out_count,
                    model.name, frame_num, total_frames,
                    counted=counted_so_far,
                ),
                frame_num,
                total_frames,
            )

        frame_num += 1
        if progress_callback:
            progress_callback(frame_num, total_frames)
        if status_callback and frame_num % 30 == 0:
            status_callback(f"[{model.name}] Frame {frame_num}/{total_frames}")

    elapsed = time.time() - start_time
    cap.release()

    result = _summarise(model, tracks, crossing_events, frame_num, fps,
                        total_detections, elapsed, line_zone, partial)

    with open(detections_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "frame", "timestamp", "tracker_id",
            "vehicle_type", "canonical_class", "confidence",
        ])
        writer.writeheader()
        writer.writerows(frame_rows)

    _write_crossings(crossings_csv, result.pop("_counted_events"))

    result["csv_path"] = detections_csv
    result["crossings_csv_path"] = crossings_csv
    return result


def _summarise(model, tracks, crossing_events, frame_num, fps,
               total_detections, elapsed, line_zone, partial) -> dict:
    """Turn raw crossing events into counts, filtering out flicker."""
    counted, rejected = [], 0
    for event in crossing_events:
        record = tracks[event["tracker_id"]]
        if record.frames_seen < config.MIN_TRACK_FRAMES_TO_COUNT:
            rejected += 1
            continue
        native_class = record.voted_class
        counted.append({
            **event,
            "vehicle_type": native_class,
            "canonical_class": taxonomy.to_canonical(native_class),
            "track_frames": record.frames_seen,
            "mean_confidence": round(record.mean_confidence, 4),
        })

    native_counts = Counter()
    canonical_counts = Counter()
    canonical_in = Counter()
    canonical_out = Counter()
    for event in counted:
        native_counts[event["vehicle_type"]] += 1
        canonical_counts[event["canonical_class"]] += 1
        (canonical_in if event["direction"] == "in" else canonical_out)[
            event["canonical_class"]
        ] += 1

    crossings_in = sum(1 for e in counted if e["direction"] == "in")
    crossings_out = len(counted) - crossings_in

    return {
        "model_name": model.name,
        "native_classes": model.native_classes,
        "canonical_classes": model.canonical_classes,
        "classes": model.native_classes,

        "total_frames": frame_num,
        "processing_fps": round(frame_num / elapsed, 1) if elapsed > 0 else 0,
        "elapsed_seconds": round(elapsed, 2),
        "total_detections": total_detections,
        "detections_per_frame": round(total_detections / max(frame_num, 1), 2),

        # The headline numbers: vehicles that crossed the line.
        "total_crossings": len(counted),
        "crossings_in": crossings_in,
        "crossings_out": crossings_out,
        "vehicle_counts": dict(native_counts.most_common()),
        "canonical_counts": {
            cls: canonical_counts[cls]
            for cls in taxonomy.CANONICAL_CLASSES if canonical_counts[cls]
        },
        "canonical_counts_in": {
            cls: canonical_in[cls]
            for cls in taxonomy.CANONICAL_CLASSES if canonical_in[cls]
        },
        "canonical_counts_out": {
            cls: canonical_out[cls]
            for cls in taxonomy.CANONICAL_CLASSES if canonical_out[cls]
        },

        # Diagnostics, not counts.
        "tracks_seen_anywhere": len(tracks),
        "crossings_rejected_short_track": rejected,
        "raw_line_zone_in": line_zone.in_count if line_zone is not None else 0,
        "raw_line_zone_out": line_zone.out_count if line_zone is not None else 0,

        "partial": partial,
        "_counted_events": counted,
    }


def _write_crossings(path: str, counted_events: list[dict]):
    """One row per counted vehicle -- the file to compare against manual counts."""
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "tracker_id", "frame", "timestamp", "direction",
            "vehicle_type", "canonical_class", "track_frames", "mean_confidence",
        ])
        writer.writeheader()
        writer.writerows(sorted(counted_events, key=lambda e: e["frame"]))


def _write_native_summary(path: str, models: dict):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["model", "vehicle_class", "crossings"])
        for model_name, data in models.items():
            for cls, count in data["vehicle_counts"].items():
                writer.writerow([model_name, cls, count])


def _write_canonical_summary(path: str, models: dict):
    """Cross-model comparison table, one column per model.

    A class the model's taxonomy cannot express is written "n/a" rather than 0:
    RT-DETR reporting no three-wheelers is a limit of COCO, not a detection
    miss, and scoring it as zero would be misleading.
    """
    names = list(models.keys())
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric"] + names)

        for cls in taxonomy.CANONICAL_CLASSES:
            row = [f"canonical:{cls}"]
            for name in names:
                data = models[name]
                row.append("n/a" if cls not in data["canonical_classes"]
                           else data["canonical_counts"].get(cls, 0))
            writer.writerow(row)

        for metric in ("total_crossings", "crossings_in", "crossings_out",
                       "tracks_seen_anywhere", "crossings_rejected_short_track",
                       "total_detections", "processing_fps"):
            writer.writerow([metric] + [models[name][metric] for name in names])


def process_video_multi(video_path, output_dir, models: list[BaseModel],
                        progress_callback=None, status_callback=None,
                        frame_callback=None, stop_event=None) -> dict:
    """Run every selected model over the same video and write the comparison."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    taxonomy.reset_unmapped()

    results = {
        "video": video_path,
        "video_name": os.path.splitext(os.path.basename(video_path))[0],
        "resolution": f"{width}x{height}",
        "fps": fps,
        "total_frames": total_frames,
        "counting_method": (
            "line crossings at y = "
            f"{config.LINE_POSITION:.2f} x frame height; a crossing counts only if "
            f"its track was seen >= {config.MIN_TRACK_FRAMES_TO_COUNT} frames"
        ),
        "inference_size": config.INFERENCE_SIZE or "native (matches video)",
        "confidence_threshold": config.DEFAULT_CONFIDENCE,
        "canonical_taxonomy": taxonomy.CANONICAL_CLASSES,
        "models": {},
    }

    for i, model in enumerate(models):
        if stop_event and stop_event.is_set():
            break

        if status_callback:
            status_callback(f"Loading model {i + 1}/{len(models)}: {model.name}")
        model.load()

        if status_callback:
            status_callback(f"Processing with {model.name}...")

        def model_progress(current, total, index=i):
            if progress_callback:
                progress_callback(
                    ((index * total_frames + current) / (len(models) * total_frames)) * 100
                )

        results["models"][model.name] = run_single_model(
            model, video_path, output_dir,
            progress_callback=model_progress,
            status_callback=status_callback,
            frame_callback=frame_callback,
            stop_event=stop_event,
        )

    results["unmapped_native_labels"] = taxonomy.unmapped_labels()

    _write_native_summary(os.path.join(output_dir, "vehicle_summary.csv"), results["models"])
    _write_canonical_summary(os.path.join(output_dir, "canonical_summary.csv"), results["models"])

    with open(os.path.join(output_dir, "summary.json"), "w") as f:
        json.dump(results, f, indent=2)

    results["output_dir"] = output_dir

    if status_callback:
        status_callback("All models complete!")

    return results
