# Vehicle Counting AI

Web-based vehicle detection and counting tool for Indian roads. Users annotate road areas and counting lines on video, then the system tracks and counts vehicles per road with per-vehicle-type breakdowns.

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py
```

Open **http://localhost:8080** in your browser.

### Windows

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

Or double-click `start.bat`.

## How It Works

### 1. Upload Video
Select a video file (MP4, AVI, MOV, MKV, WebM) through the web interface.

### 2. Annotate Roads
- **Pen Tool (P):** Draw polygons around road areas
- **Line Tool (L):** Draw counting lines across each road
- **Label:** Name each road (e.g., "Main Street Northbound")

### 3. Process
The AI model detects and tracks vehicles across all frames. Live preview shows annotated frames with road labels and running counts.

### 4. Results
View per-road crossing counts broken down by Aakar's vehicle categories. Every finished run is saved to its own folder under `Final Results/` with an Excel report. **Copy for WhatsApp** puts an overview of the run on the clipboard, formatted to paste into a chat.

## Architecture

```
server.py                   FastAPI server (REST + WebSocket)
interface/                  Web frontend (HTML/CSS/JS)
  file-input/               Video upload screen
  option1/                  Annotation tool (pen + line drawing)
  processing/               Live processing preview
  results/                  Per-road results display
  shared/                   CSS variables, base styles, WebSocket client
core/
  base.py                   BaseModel interface
  taxonomy.py               Canonical vehicle classes
  processor.py              Detection → tracking → counting pipeline
  overlay.py                Annotated frame rendering
models/
  __init__.py               MODEL_REGISTRY
  _ultralytics.py           Shared YOLO loading + inference
  yolov11s_uvh26.py         YOLOv11-S (14 Indian vehicle types)
```

## Model

| Model | File | Native classes | Source |
|-------|------|----------------|--------|
| YOLOv11-S (UVH-26) | `models/yolov11s_uvh26.py` | 14 Indian vehicle types | AIM@IISc (HuggingFace) |

Model weights are not in the repo. Each model downloads its own from HuggingFace on first use into `models/weights/`.

## Canonical Taxonomy

Models disagree on vocabulary. Every model maps its native labels onto one shared set (`core/taxonomy.py`):

```
two_wheeler  three_wheeler  car  lcv  bus  truck  multi_axle  tractor  bicycle  other
```

## Counting Method

**ByteTrack** (via supervision) assigns IDs across frames, **DetectionsSmoother** stabilises boxes, and **LineZone** counts crossings of user-drawn lines.

Counting measures **vehicles that cross the line**, not vehicles present in the frame. A crossing only counts if its track was seen at least `MIN_TRACK_FRAMES_TO_COUNT` (3) frames, which filters out flicker and false positives.

### Per-Road Counting

Each road is annotated with:
- A **polygon** defining the road area
- A **counting line** across the road
- A **label** (road name)

Crossings are tracked per line zone. Results show total crossings per road with vehicle type breakdown.

## Tuning

All settings in `core/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `INFERENCE_SIZE` | `None` | `None` = native resolution |
| `DEFAULT_CONFIDENCE` | 0.25 | Detection confidence threshold |
| `MIN_TRACK_FRAMES_TO_COUNT` | 3 | Minimum track frames to count a crossing |
| `LINE_POSITION` | 0.35 | Fallback line position (fraction of frame height) |

## Output Files

Each finished run gets one folder, named after the video and the time the run finished:

```
Final Results/
  MG Road cam2 - 2026-11-11 14.30/
    Traffic Count Report.xlsx
    raw data/
      crossings.csv
      detections.csv
      summary.json
```

| File | Contents |
|------|----------|
| `Traffic Count Report.xlsx` | **Overview** (video, date, totals per road), **By Road** (every vehicle category against every road), **Crossings** (one row per counted vehicle) |
| `raw data/crossings.csv` | One row per counted vehicle with road zone, class, confidence |
| `raw data/detections.csv` | Every per-frame detection with tracker_id |
| `raw data/summary.json` | Full run metadata and per-road results |

While a run is in progress its files and checkpoint live in `outputs/<video id>/`; they move to `Final Results/` when the run completes.

### Vehicle categories

Results use Aakar's 16 categories. The mapping from the model's own labels lives in `core/aakar_categories.py`, and each category is shown with the model's classification in brackets, e.g. `Cars/Vans/Jeeps (Hatchback, Sedan, SUV, Van)`.

Six categories describe a distinction the model cannot make yet. They are listed with a dash, and their vehicles are counted in a neighbouring category:

| Category | Counted in |
|----------|------------|
| Taxi | Cars/Vans/Jeeps |
| Govt. Bus | Private Bus |
| Goods Auto | Auto Rickshaw |
| Mini LCV | LCV |
| 3 Axle Truck, MAV | 2 Axle Truck |

## Tests

```
venv\Scripts\python -m unittest discover tests
```

## Requirements

- Python 3.11+
- macOS, Linux, or Windows
- ~2GB disk for model weights (downloaded on first run)

## Versioning & Changelog

The version shown in the app is the highest `vX.Y.Z` heading in `changelog/*.md`. Every push needs a new version entry. The `.githooks/pre-push` hook enforces this, and the setup scripts turn it on. See `CLAUDE.md` for the full workflow, which humans and agents both follow. Each new version is also published automatically to the repo's [Releases](https://github.com/ArnavKhair/aakarcounting/releases) page, with that version's changelog section as the release notes.

## License

See repository for license details.
