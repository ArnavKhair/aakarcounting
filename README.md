# Vehicle Counting AI

Multi-model comparison tool for vehicle detection on Indian roads with object tracking.

## Models

| Model | Classes | Source |
|-------|---------|--------|
| YOLOv8n | 8 Indian vehicle types | Ultralytics (HuggingFace) |
| YOLOv11-S (UVH-26) | 14 Indian vehicle types | AIM@IISc (HuggingFace) |
| YOLOv11-X (UVH-26) | 14 Indian vehicle types | AIM@IISc (HuggingFace) |
| RT-DETR (r50vd) | 4 vehicle types (car, motorcycle, bus, truck) | HuggingFace Transformers |
| VehicleDINO | 5 generic types | ONNX (disabled by default, slow on Mac) |

## Tracking & Counting

Uses **ByteTrack** (via supervision-develop) to assign unique IDs to each vehicle across frames. Uses **LineZone** to count vehicles crossing a line at the frame midpoint. Uses **DetectionsSmoother** to stabilize bounding boxes.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e models/supervision-develop
```

## Usage

```bash
python main.py
```

1. Select models to compare
2. Click **Select Video** and choose a video file
3. Click **Output Folder** to pick where results are saved
4. Click **Run Comparison**

## Output

- `summary.json` — Comparison of all models: unique vehicle counts, line crossings, FPS, per-class breakdown
- `vehicle_counts_{model}.csv` — Per-frame detections with tracker_id for each model

### Key fields in summary.json

```json
{
  "total_unique_vehicles": 47,
  "total_detections": 12480,
  "line_zone_crossings_in": 42,
  "line_zone_crossings_out": 38,
  "vehicle_counts": {"car": 23, "truck": 8}
}
```

- `total_unique_vehicles` — Distinct vehicles tracked by ID
- `line_zone_crossings_in` — Vehicles crossing the midpoint line into the frame
- `line_zone_crossings_out` — Vehicles crossing out
- `vehicle_counts` — Unique vehicles per class
