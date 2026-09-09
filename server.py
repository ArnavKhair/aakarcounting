"""FastAPI server for the Vehicle Counting AI web interface.

Serves the 4-screen HTML/CSS/JS frontend and exposes REST + WebSocket
endpoints for video upload, processing, and results.

Usage:
    python server.py          # starts on port 8080
    python server.py 9090     # starts on custom port
"""
import asyncio
import base64
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

import cv2
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ── Paths ──────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent
INTERFACE_DIR = PROJECT_ROOT / "interface"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Temp directory for uploaded videos
UPLOAD_DIR = Path(tempfile.mkdtemp(prefix="vcai_uploads_"))

# ── App state ──────────────────────────────────────────────────────────────

app = FastAPI(title="Vehicle Counting AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store: video_id -> metadata
video_store: dict[str, dict] = {}

# Active processing sessions: video_id -> threading.Event (stop signal)
active_sessions: dict[str, threading.Event] = {}


# ── REST endpoints ─────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return RedirectResponse(url="/file-input/")


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """Accept a video file, save to temp dir, return metadata."""
    allowed = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    ext = Path(file.filename or "video.mp4").suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported format: {ext}")

    video_id = uuid.uuid4().hex[:12]
    dest = UPLOAD_DIR / f"{video_id}{ext}"

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Extract metadata with OpenCV
    cap = cv2.VideoCapture(str(dest))
    if not cap.isOpened():
        os.remove(dest)
        raise HTTPException(400, "Could not open video file")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    duration = frame_count / fps if fps > 0 else 0

    meta = {
        "video_id": video_id,
        "filename": file.filename,
        "path": str(dest),
        "width": width,
        "height": height,
        "fps": round(fps, 2),
        "frames": frame_count,
        "duration": round(duration, 2),
    }
    video_store[video_id] = meta

    return meta


@app.get("/api/video/{video_id}")
async def get_video(video_id: str):
    """Serve uploaded video file for playback."""
    meta = video_store.get(video_id)
    if not meta:
        raise HTTPException(404, "Video not found")
    return FileResponse(meta["path"], media_type="video/mp4")


@app.get("/api/results/{video_id}")
async def get_results(video_id: str):
    """Return summary.json contents for a completed run."""
    output_dir = OUTPUT_DIR / video_id
    summary_path = output_dir / "summary.json"
    if not summary_path.exists():
        raise HTTPException(404, "Results not found")
    with open(summary_path) as f:
        return JSONResponse(json.load(f))


@app.get("/api/download/{video_id}/{filename}")
async def download_file(video_id: str, filename: str):
    """Download a CSV or JSON file from the output directory."""
    output_dir = OUTPUT_DIR / video_id
    file_path = output_dir / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    if not filename.endswith((".csv", ".json")):
        raise HTTPException(400, "Only CSV and JSON files can be downloaded")
    return FileResponse(file_path, filename=filename)


# ── Static file serving ────────────────────────────────────────────────────

import mimetypes
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")


def _serve_file(file_path: Path):
    """Serve a file with the correct MIME type."""
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    return FileResponse(file_path, media_type=media_type)


@app.get("/shared/{path:path}")
async def serve_shared(path: str):
    file_path = INTERFACE_DIR / "shared" / path
    if file_path.exists() and file_path.is_file():
        return _serve_file(file_path)
    raise HTTPException(404, "Not found")


@app.get("/{screen}/")
async def serve_screen(screen: str):
    """Serve index.html for each screen."""
    allowed = {"file-input", "option1", "processing", "results"}
    if screen not in allowed:
        raise HTTPException(404, "Screen not found")
    index = INTERFACE_DIR / screen / "index.html"
    if not index.exists():
        raise HTTPException(404, "Screen not found")
    return FileResponse(index)


@app.get("/{screen}/{path:path}")
async def serve_screen_static(screen: str, path: str):
    """Serve static assets (CSS, JS, images) for each screen."""
    allowed = {"file-input", "option1", "processing", "results", "shared"}
    if screen not in allowed:
        raise HTTPException(404, "Not found")
    file_path = INTERFACE_DIR / screen / path
    if file_path.exists() and file_path.is_file():
        return _serve_file(file_path)
    raise HTTPException(404, "Not found")


# ── WebSocket processing ───────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[WS] Client connected")
    current_video_id = None
    stop_event = threading.Event()
    loop = asyncio.get_event_loop()

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "")
            data = msg.get("data", {})
            print(f"[WS] Received: {msg_type}")

            if msg_type == "start_processing":
                video_id = data.get("video_id")
                annotations = data.get("annotations", [])
                current_video_id = video_id

                if not video_id or video_id not in video_store:
                    print(f"[WS] Error: Invalid video ID '{video_id}'")
                    await _ws_send(websocket, "error", {"message": "Invalid video ID"})
                    continue

                print(f"[WS] Starting processing for {video_id}, {len(annotations)} annotations")
                stop_event.clear()
                active_sessions[video_id] = stop_event

                # Run processing in background thread
                thread = threading.Thread(
                    target=_run_processing,
                    args=(websocket, loop, video_id, annotations, stop_event),
                    daemon=True,
                )
                thread.start()

            elif msg_type == "stop_processing":
                print("[WS] Stop requested")
                stop_event.set()
                if current_video_id:
                    active_sessions.pop(current_video_id, None)

    except WebSocketDisconnect:
        print("[WS] Client disconnected")
        stop_event.set()
        if current_video_id:
            active_sessions.pop(current_video_id, None)
    except Exception as e:
        print(f"[WS] Error: {e}")
        try:
            await _ws_send(websocket, "error", {"message": str(e)})
        except Exception:
            pass


async def _ws_send(websocket: WebSocket, msg_type: str, data: dict):
    """Send a JSON message over WebSocket (thread-safe)."""
    try:
        payload = json.dumps({"type": msg_type, "data": data})
        await websocket.send_text(payload)
    except Exception as e:
        print(f"[WS] Send error ({msg_type}): {e}")


def _ws_send_sync(websocket: WebSocket, loop: asyncio.AbstractEventLoop,
                  msg_type: str, data: dict):
    """Send a WebSocket message from a background thread."""
    try:
        future = asyncio.run_coroutine_threadsafe(
            _ws_send(websocket, msg_type, data), loop
        )
        future.result(timeout=5)
    except Exception as e:
        print(f"[WS] _ws_send_sync error ({msg_type}): {e}")


def _run_processing(
    websocket: WebSocket,
    loop: asyncio.AbstractEventLoop,
    video_id: str,
    annotations: list,
    stop_event: threading.Event,
):
    """Run the processing pipeline in a background thread."""
    try:
        meta = video_store[video_id]
        video_path = meta["path"]

        # Create output directory
        output_dir = OUTPUT_DIR / video_id
        os.makedirs(output_dir, exist_ok=True)

        # Convert annotations to processor format (normalized -> pixel coords)
        counting_lines, road_labels = _convert_annotations(
            annotations,
            meta.get("width", 1920),
            meta.get("height", 1080),
        )
        print(f"[Processing] video={video_path}, lines={counting_lines}, labels={road_labels}")

        # Import and run the processor
        from core.processor import run_single_model
        from models import create

        _ws_send_sync(websocket, loop, "status", {"text": "Loading model..."})
        print("[Processing] Loading model...")
        model = create("yolov11s_uvh26")
        model.load()

        start_time = time.time()

        def on_status(msg):
            print(f"[Processing] Status: {msg}")
            _ws_send_sync(websocket, loop, "status", {"text": msg})

        def on_progress(frame_num, total_frames):
            if frame_num % 10 != 0 and frame_num != total_frames:
                return
            elapsed = time.time() - start_time
            percent = (frame_num / total_frames * 100) if total_frames > 0 else 0
            fps = frame_num / elapsed if elapsed > 0 else 0
            eta = (total_frames - frame_num) / fps if fps > 0 else 0
            _ws_send_sync(websocket, loop, "progress", {
                "frame": frame_num,
                "total": total_frames,
                "percent": round(percent, 1),
                "fps": round(fps, 1),
                "eta_seconds": round(eta, 1),
            })

        frame_count = [0]

        def on_frame(annotated_frame, frame_num, total_frames):
            frame_count[0] += 1
            if frame_count[0] <= 3:
                print(f"[Processing] Frame {frame_num}, shape={annotated_frame.shape}")
            # Encode frame as JPEG and send via WebSocket
            _, buffer = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            b64 = base64.b64encode(buffer).decode("utf-8")
            _ws_send_sync(websocket, loop, "frame", b64)

        # Import summary writers
        from core.processor import _write_native_summary, _write_canonical_summary

        _ws_send_sync(websocket, loop, "status", {"text": "Processing..."})
        print("[Processing] Starting run_single_model()...")

        single_result = run_single_model(
            model, video_path, str(output_dir),
            progress_callback=on_progress,
            status_callback=on_status,
            frame_callback=on_frame,
            stop_event=stop_event,
            counting_lines=counting_lines if counting_lines else None,
            road_labels=road_labels if road_labels else None,
        )

        if stop_event.is_set():
            print("[Processing] Cancelled by user")
            _ws_send_sync(websocket, loop, "status", {"text": "Cancelled"})
            return

        # Wrap into the multi-model envelope the results page expects
        cap2 = cv2.VideoCapture(video_path)
        result = {
            "video": video_path,
            "video_name": os.path.splitext(os.path.basename(video_path))[0],
            "resolution": f"{int(cap2.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap2.get(cv2.CAP_PROP_FRAME_HEIGHT))}",
            "fps": cap2.get(cv2.CAP_PROP_FPS) or 30.0,
            "total_frames": int(cap2.get(cv2.CAP_PROP_FRAME_COUNT)),
            "models": {model.name: single_result},
        }
        cap2.release()

        # Write files the results page needs for downloads
        _write_native_summary(
            os.path.join(str(output_dir), "vehicle_summary.csv"),
            result["models"],
        )
        _write_canonical_summary(
            os.path.join(str(output_dir), "canonical_summary.csv"),
            result["models"],
        )
        # Write summary.json (excluding internal keys)
        summary_for_disk = {
            k: v for k, v in result.items() if not k.startswith("_")
        }
        with open(os.path.join(str(output_dir), "summary.json"), "w") as sf:
            json.dump(summary_for_disk, sf, indent=2)

        print(f"[Processing] Complete. Crossings: {single_result.get('total_crossings', 0)}")
        # Send result summary
        _ws_send_sync(websocket, loop, "result", result)
        _ws_send_sync(websocket, loop, "status", {"text": "Complete!"})

    except Exception as e:
        print(f"[Processing] ERROR: {e}")
        import traceback
        traceback.print_exc()
        _ws_send_sync(websocket, loop, "error", {"message": str(e)})
    finally:
        active_sessions.pop(video_id, None)


def _convert_annotations(annotations: list, video_width: int, video_height: int) -> tuple:
    """Convert frontend annotation format to processor counting_lines format.

    Frontend sends pixel coordinates (video-native resolution): [{line: {start:{x,y}, end:{x,y}}, label: "...", ...}]
    screenToCanvas() already converts screen coords to video pixel coords.
    Processor expects: [((sx, sy), (ex, ey)), ...] and a list of labels.
    """
    lines = []
    labels = []
    for road in annotations:
        line = road.get("line")
        if line and line.get("start") and line.get("end"):
            start = line["start"]
            end = line["end"]
            lines.append(((start["x"], start["y"]), (end["x"], end["y"])))
            labels.append(road.get("label", "Unnamed Road"))
    return lines, labels


# ── Cleanup on exit ────────────────────────────────────────────────────────

import atexit

def _cleanup():
    """Remove temp upload directory on exit."""
    try:
        shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
    except Exception:
        pass

atexit.register(_cleanup)


# ── Entry point ────────────────────────────────────────────────────────────

def start_server(port: int = 8080):
    """Start the FastAPI server (blocking)."""
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    start_server(port)
