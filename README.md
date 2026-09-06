# Vehicle Counting AI

Multi-model comparison tool for vehicle detection on Indian roads with object tracking.

## Models

One file per model in `models/`. Each declares its own native class vocabulary
and maps it onto the shared canonical taxonomy.

| Model | File | Native classes | Source |
|-------|------|----------------|--------|
| YOLOv8n | `models/yolov8n.py` | 8 Indian vehicle types | Ultralytics (HuggingFace) |
| YOLOv11-S (UVH-26) | `models/yolov11s_uvh26.py` | 14 Indian vehicle types | AIM@IISc (HuggingFace) |
| YOLOv11-X (UVH-26) | `models/yolov11x_uvh26.py` | 14 Indian vehicle types | AIM@IISc (HuggingFace) |
| RT-DETR (r50vd) | `models/rtdetr.py` | 4 COCO vehicle types | HuggingFace Transformers |
| VehicleDINO | `models/vehicledino.py` | 5 generic types | ONNX (off by default; output decoding unverified) |

To add a model: write `models/<name>.py` exposing a `create()` factory that
returns a `BaseModel`, then add one entry to `MODEL_REGISTRY` in
`models/__init__.py`. Nothing else needs to change.

## Canonical taxonomy

Models disagree on vocabulary — RT-DETR says `car`, UVH-26 says `Sedan`, and
neither has a word for an auto-rickshaw. Counts in different vocabularies
cannot be compared with each other or scored against the same manual counts,
so every model maps its native label onto one shared set
(`core/taxonomy.py`):

```
two_wheeler  three_wheeler  car  lcv  bus  truck  multi_axle  tractor  bicycle  other
```

The native label is kept alongside the canonical one, so mapping adds a
comparison axis without discarding per-model detail. A native label with no
mapping falls back to `other` and is reported as a warning after the run —
add it to `_ALIASES` in `core/taxonomy.py`.

Each model also reports which canonical classes it is *capable* of emitting.
In the comparison table, a class a model cannot express is written `n/a`
rather than `0`: RT-DETR reporting no three-wheelers is a limitation of COCO,
not a detection miss.

## Tracking & Counting

**ByteTrack** (via supervision) assigns IDs across frames, **DetectionsSmoother**
stabilises boxes, and **LineZone** counts crossings of a horizontal line.

Counting measures **vehicles that cross the line**, not vehicles present in the
frame. Parked cars, background traffic and two-frame flicker contribute
nothing, which is what makes the numbers comparable to a manual count. Each
crossing vehicle is labelled by a **majority vote over its whole track**
rather than by its label in the single frame it happened to cross.

A crossing only counts if its track was seen at least
`MIN_TRACK_FRAMES_TO_COUNT` frames. This is the false-positive filter, applied
at counting time rather than by suppressing short tracks in the tracker, which
is what used to make small vehicles invisible.

### Line placement is camera-specific and matters more than any model choice

Because counting is defined as line crossings, a badly placed line does not
undercount a little -- it counts the wrong population. Measured on the
Ahmedabad junction clip, 600 frames, YOLOv11-S:

| Line position | Crossings | Class mix |
|---|---|---|
| y=360 (0.50, the old default) | 14 | **all cars**, zero two-wheelers |
| y=201 (0.28) | 20 | mixed |
| y=251 (0.35, current) | **27** | 16 car, 7 two-wheeler, 3 three-wheeler, 1 LCV |

At 0.50 the line sat over the median, below the traffic. Set `LINE_POSITION`
in `core/config.py` for each camera.

## Tuning

Every knob lives in `core/config.py`. Notable settings:

| Setting | Value | Why |
|---|---|---|
| `INFERENCE_SIZE` | `None` = native | Frames go to the detector at their own resolution instead of being letterboxed down to 640 |
| `DEFAULT_CONFIDENCE` | 0.25 | Detect low, count strict -- marginal detections are rescued by tracking, spurious ones rejected at counting time |
| `MINIMUM_CONSECUTIVE_FRAMES` | 1 | Must stay 1; see Known issues |
| `MIN_TRACK_FRAMES_TO_COUNT` | 3 | The actual false-positive filter |
| `LINE_POSITION` | 0.35 | Camera-specific, see above |

## Project layout

```
main.py                 entry point
gui.py                  Tkinter UI
core/
  base.py               BaseModel interface + Detection
  taxonomy.py           canonical classes and native -> canonical mapping
  processor.py          detect -> track -> count pipeline, file output
  overlay.py            annotated preview rendering
  upscaler.py           optional Real-ESRGAN pre-upscaling
  paths.py              weights / output locations
models/
  __init__.py           MODEL_REGISTRY
  _ultralytics.py       shared YOLO loading + inference
  <one file per model>
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

That is the whole setup. Model weights are not in the repo and do not need to
be — each model downloads its own from HuggingFace on first use, into
`models/weights/`.

Previous versions of this README asked for `pip install -e
models/supervision-develop`. That vendored fork was gitignored and absent from
every clone. It has been replaced with the PyPI package: supervision 0.30.2
provides every API this project uses (`ByteTrack` with all five of our
keyword arguments, `DetectionsSmoother`, `LineZone`, `Detections`), verified
against the real library.

### Optional upscaler

The "Upscale Video (2x Real-ESRGAN)" checkbox does not currently work.
`pip install realesrgan` fails because its dependency `basicsr` cannot build
on current Python/setuptools (`KeyError: '__version__'` in basicsr's
setup.py). It is deliberately left out of `requirements.txt`; the checkbox
will raise if ticked. See Known issues for why fixing it is low priority.

## Usage

```bash
python main.py
```

1. Select models to compare
2. Click **Select Video** and choose a video file
3. Click **Run Comparison**

Output goes to an auto-generated `outputs/{mon}{day}/trial{N}/` folder — there
is no folder picker. `trial1` is the first run of the day, `trial2` the second,
and so on. Example: `outputs/sept5/trial1/`.

## Output

| File | Contents |
|------|----------|
| `crossings_{model}.csv` | **One row per counted vehicle** -- id, time, direction, class. This is the file to compare against manual counts. |
| `canonical_summary.csv` | Cross-model comparison table, one column per model |
| `summary.json` | Full run metadata and per-model results |
| `vehicle_summary.csv` | Per-model counts in each model's native vocabulary |
| `vehicle_counts_{model}.csv` | Every per-frame detection with `tracker_id` (raw record) |

### summary.json shape

Per-model results are nested under `models`, keyed by display name:

```json
{
  "video_name": "clip1",
  "resolution": "1280x720",
  "canonical_taxonomy": ["two_wheeler", "three_wheeler", "..."],
  "unmapped_native_labels": [],
  "models": {
    "YOLOv11-S (UVH-26)": {
      "total_unique_vehicles": 47,
      "total_detections": 12480,
      "line_zone_crossings_in": 42,
      "line_zone_crossings_out": 38,
      "native_classes": ["Sedan", "SUV", "..."],
      "canonical_classes": ["car", "two_wheeler", "..."],
      "vehicle_counts": {"Sedan": 23, "truck": 8},
      "canonical_counts": {"car": 31, "truck": 8}
    }
  }
}
```

- `total_unique_vehicles` — distinct tracks seen anywhere in frame, **including
  parked vehicles that never crossed the line**
- `line_zone_crossings_in` / `_out` — tracks crossing the midpoint line. If
  your manual ground truth is "vehicles that passed", compare against these,
  not `total_unique_vehicles`.
- `vehicle_counts` — unique count per native class
- `canonical_counts` — unique count per canonical class

## Known issues

Each of these was reproduced against supervision 0.30.2, not inferred.

- **Fast vehicles are silently dropped or counted many times.**
  `MINIMUM_CONSECUTIVE_FRAMES = 3` in `core/processor.py` is the cause. With a
  100x80 px box, a vehicle moving vertically at 35 px/frame or more produces
  *zero* tracked frames and is never counted at all; the same vehicle at
  `minimum_consecutive_frames=1` tracks perfectly with one stable ID. Moving
  horizontally at 40 px/frame it instead churns through 6 IDs in 20 frames and
  is counted 6 times. Supervision's own default handles both cases. This is
  the most damaging issue in the pipeline: it both under- and over-counts, and
  it hits exactly the fast near-field vehicles a traffic survey cares about.
- **Class labels can be attached to the wrong box.** `core/processor.py` builds
  `sv.Detections` without `class_id`, so ByteTrack drops and reorders rows
  while the class lookup still uses the pre-tracking index. Reproduced: with
  three detections where one is below the activation threshold, the third
  vehicle is mislabelled as the second on every frame. Marked in the source as
  `TIER-1 FIX PENDING`.
- **Detector input resolution is left at the Ultralytics default (640)**, so
  720p frames are downscaled 2x before inference.
- **Upscaling is self-defeating** — frames are upscaled and then resized back
  down by the detector. Combined with the broken install, the feature is
  currently inert.
- **VehicleDINO output decoding is unverified** and likely emits background
  queries as detections.

`LineZone` also supports `in_count_per_class` / `out_count_per_class` and a
`triggering_anchors` argument. Both become usable once `class_id` is carried
through the tracker, which would give per-class crossing counts directly
instead of deriving them from unique-track bookkeeping.
