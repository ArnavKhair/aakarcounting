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
import queue
import re
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
from fastapi import Body, FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from core import final_results
from core.media import create_preview, is_browser_playable, probe_video
from core.processor import load_checkpoint

# ── Paths ──────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent
INTERFACE_DIR = PROJECT_ROOT / "interface"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
FINAL_RESULTS_DIR = PROJECT_ROOT / "Final Results"
CHANGELOG_DIR = PROJECT_ROOT / "changelog"

# Temp directory for uploaded videos
UPLOAD_DIR = Path(tempfile.mkdtemp(prefix="vcai_uploads_"))

_SEMVER_HEADING = re.compile(
    r"^\s{0,3}#{1,6}\s+.*?\bv?(\d+)\.(\d+)\.(\d+)\b",
    re.MULTILINE,
)


def get_latest_version() -> Optional[str]:
    """Return the highest semver found in changelog headings, e.g. 'v1.2.1'."""
    latest = None
    for path in CHANGELOG_DIR.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in _SEMVER_HEADING.finditer(text):
            version = tuple(int(part) for part in match.groups())
            if latest is None or version > latest:
                latest = version
    return "v" + ".".join(map(str, latest)) if latest else None

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


class Session:
    """The state of one processing run.

    stop/pause/resume are separate because stopping and pausing mean
    different things to the user: a stop ends the run, a pause holds it
    where it is and lets it carry on from the same frame.
    """

    def __init__(self):
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.resume_event = threading.Event()
        self.thread: threading.Thread | None = None

    def stop(self):
        self.stop_event.set()
        # A run that is paused waits on resume_event, so a stop has to wake
        # it up as well or the thread sits there until the client reconnects.
        self.resume_event.set()

    def pause(self):
        self.pause_event.set()

    def resume(self):
        self.resume_event.set()


# Active processing sessions: video_id -> Session
active_sessions: dict[str, Session] = {}

# Finished runs: video_id -> its folder under Final Results
final_dirs: dict[str, Path] = {}

COUNTING_METHOD = "Line crossing (ByteTrack + LineZone)"


def _final_dir(video_id: str) -> Optional[Path]:
    """The Final Results folder of a finished run, or None.

    Remembered while the server is up; after a restart it is found again by
    the id saved in the folder's summary, so it survives being renamed.
    """
    folder = final_dirs.get(video_id)
    if folder is not None and folder.is_dir():
        return folder
    folder = final_results.find_folder(FINAL_RESULTS_DIR, video_id)
    if folder is not None:
        final_dirs[video_id] = folder
    return folder


# What can be downloaded from a finished run. The client names a kind, never
# a file, so a request cannot reach outside the run's folder.
DOWNLOADS = {
    "report": (final_results.REPORT_NAME,),
    "crossings": (final_results.RAW_DIR, final_results.CROSSINGS_NAME),
    "detections": (final_results.RAW_DIR, final_results.DETECTIONS_NAME),
    "summary": (final_results.RAW_DIR, final_results.SUMMARY_NAME),
}


# ── REST endpoints ─────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return RedirectResponse(url="/file-input/")


@app.get("/api/version")
async def get_version():
    """Return the latest version parsed from the changelog."""
    return {"version": get_latest_version()}


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

    try:
        fmt, video_codec, audio_codec = probe_video(dest)
    except Exception as exc:
        os.remove(dest)
        raise HTTPException(400, f"Could not read video metadata: {exc}")

    if not video_codec:
        os.remove(dest)
        raise HTTPException(400, "No video stream found")

    original_playable = ext == ".mp4" and is_browser_playable(fmt, video_codec, audio_codec)
    preview_path = dest
    if not original_playable:
        preview_path = dest.with_name(f"{dest.stem}_preview.mp4")

    duration = frame_count / fps if fps > 0 else 0

    meta = {
        "video_id": video_id,
        "filename": file.filename,
        "path": str(dest),
        "preview_path": str(preview_path),
        "preview_ready": original_playable,
        "original_playable": original_playable,
        "width": width,
        "height": height,
        "fps": round(fps, 2),
        "frames": frame_count,
        "duration": round(duration, 2),
    }
    video_store[video_id] = meta

    # Making a playable preview of an hour of CCTV takes a while, and the
    # upload does not have to wait for it: the line drawing screen asks for
    # the preview when it is ready. A file the browser can already play is
    # served as it is, with no transcode at all.
    if not original_playable:
        threading.Thread(
            target=_make_preview,
            args=(video_id, dest, preview_path, video_codec),
            daemon=True,
        ).start()

    return meta


def _make_preview(video_id: str, src: Path, dest: Path, video_codec: str):
    """Transcode a browser-playable preview in the background."""
    try:
        create_preview(src, dest, video_codec)
    except Exception as exc:
        print(f"[Preview] Could not prepare a preview for {video_id}: {exc}")
        return
    meta = video_store.get(video_id)
    if meta is not None:
        meta["preview_ready"] = True
    print(f"[Preview] Ready for {video_id}")


@app.get("/api/video/{video_id}/status")
async def get_video_status(video_id: str):
    """Report whether the browser-playable preview is ready to serve."""
    meta = video_store.get(video_id)
    if not meta:
        raise HTTPException(404, "Video not found")
    return {
        "preview_ready": bool(meta.get("preview_ready")),
        "original_playable": bool(meta.get("original_playable")),
    }


@app.get("/api/video/{video_id}")
async def get_video(video_id: str):
    """Serve uploaded video file for playback."""
    meta = video_store.get(video_id)
    if not meta:
        raise HTTPException(404, "Video not found")

    if meta.get("preview_ready"):
        video_path = Path(meta.get("preview_path") or meta["path"])
    elif meta.get("original_playable"):
        video_path = Path(meta["path"])
    else:
        # The preview is still being made. The client polls for it.
        raise HTTPException(503, "Preview is still being prepared")

    media_type = "video/webm" if video_path.suffix.lower() == ".webm" else "video/mp4"
    return FileResponse(str(video_path), media_type=media_type)


def _render_processing_view(meta: dict, annotations: list, time_s: float):
    """Draw one frame the way the processing screen will: same decoder, same
    line conversion, same overlay code. Returns (image, info)."""
    from core import overlay

    t = max(0.0, float(time_s or 0.0))
    cap = cv2.VideoCapture(meta["path"])
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_num = min(int(round(t * fps)), max(total - 1, 0))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ok, frame = cap.read()
        if not ok or frame is None:
            # Seeking can fail near the end of some files; fall back to frame 0.
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            frame_num = 0
            ok, frame = cap.read()
    finally:
        cap.release()
    if not ok or frame is None:
        raise HTTPException(500, "Could not read a frame from the video")

    h, w = frame.shape[:2]
    lines, labels = _convert_annotations(annotations, w, h)
    annotated = overlay.draw(
        frame, [], None, "Preview", frame_num, total,
        counted=0,
        counting_lines=[(sx, sy, ex, ey) for (sx, sy), (ex, ey) in lines] or None,
        road_labels=labels,
        road_counts={label: 0 for label in labels},
    )
    info = {"frame_num": frame_num, "frame_size": [w, h], "lines_px": lines,
            "labels": labels}
    return annotated, info


DEBUG_DIR = PROJECT_ROOT / "debug"


@app.post("/api/debug/snapshot/{video_id}")
def debug_snapshot(video_id: str, payload: dict = Body(...)):
    """Save what the drawing screen showed next to what processing will use.

    Written when the user opens the preview, so a mismatch on someone's
    machine can be inspected from the files instead of described:
      drawing.png          -- the drawing canvas exactly as the browser had it
      processing_view.jpg  -- the server's render of the same moment
      report.json          -- browser geometry, clicks, annotations, video info
    """
    import datetime
    meta = video_store.get(video_id)
    if meta is None:
        raise HTTPException(404, "Video not found")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = DEBUG_DIR / f"{stamp}_{video_id}"
    os.makedirs(out, exist_ok=True)

    canvas_url = payload.pop("canvas_png", None) or ""
    if canvas_url.startswith("data:image/png;base64,"):
        with open(out / "drawing.png", "wb") as f:
            f.write(base64.b64decode(canvas_url.split(",", 1)[1]))

    annotations = payload.get("annotations") or []
    try:
        annotated, info = _render_processing_view(meta, annotations, payload.get("time") or 0.0)
        cv2.imwrite(str(out / "processing_view.jpg"), annotated)
    except Exception as exc:
        info = {"error": str(exc)}

    preview_size = None
    try:
        pcap = cv2.VideoCapture(meta.get("preview_path") or meta["path"])
        preview_size = [int(pcap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(pcap.get(cv2.CAP_PROP_FRAME_HEIGHT))]
        pcap.release()
    except Exception:
        pass

    report = {
        "client": payload.get("client"),
        "clicks": payload.get("clicks"),
        "annotations": annotations,
        "video_meta": {k: meta.get(k) for k in ("filename", "width", "height", "fps",
                                                "original_playable", "preview_path", "path")},
        "preview_file_size": preview_size,
        "server_render": info,
    }
    with open(out / "report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"[Debug] Snapshot saved to {out}")
    return {"saved": str(out)}


@app.post("/api/line-preview/{video_id}")
def line_preview(video_id: str, payload: dict = Body(...)):
    """Render one frame exactly as the processing screen will show it.

    The frame is read from the original video with OpenCV -- the same decoder
    the model reads -- and the counting lines go through the same conversion
    (_convert_annotations) and the same drawing code (core.overlay.draw) as a
    real run. What this returns is therefore what processing will count
    against, not a browser-side approximation of it.

    payload: {"annotations": [...], "time": seconds into the video}
    """
    meta = video_store.get(video_id)
    if meta is None:
        raise HTTPException(404, "Video not found")
    annotated, _info = _render_processing_view(
        meta, payload.get("annotations") or [], payload.get("time") or 0.0
    )
    ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise HTTPException(500, "Could not encode the preview frame")
    return Response(content=buf.tobytes(), media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


@app.get("/api/results/{video_id}")
async def get_results(video_id: str):
    """Return the saved summary of a completed run."""
    folder = _final_dir(video_id)
    summary_path = folder / final_results.RAW_DIR / final_results.SUMMARY_NAME if folder else None
    if summary_path is None or not summary_path.exists():
        raise HTTPException(404, "Results not found")
    with open(summary_path, encoding="utf-8") as f:
        return JSONResponse(json.load(f))


@app.get("/api/checkpoint/{video_id}")
async def check_checkpoint(video_id: str):
    """Report whether an interrupted run can be resumed for this video."""
    from core.processor import build_fingerprint, fingerprint_mismatch, load_checkpoint
    output_dir = OUTPUT_DIR / video_id
    checkpoint = load_checkpoint(str(output_dir))
    if checkpoint is None:
        return {"exists": False}

    # The counting lines are drawn on the next screen, so only the video and
    # the frame rate can be compared here. The line check runs when the
    # processing itself starts.
    meta = video_store.get(video_id)
    if meta is None:
        mismatch = "video is no longer loaded"
    else:
        fingerprint = build_fingerprint(meta["path"], meta.get("fps") or 30.0)
        mismatch = fingerprint_mismatch(
            checkpoint, fingerprint, fields=("video_path", "fps")
        )

    return {
        "exists": True,
        "frame_num": checkpoint["frame_num"],
        "total_frames": checkpoint.get("total_frames", 0),
        "resumable": mismatch is None,
        "reason": mismatch,
    }


@app.delete("/api/checkpoint/{video_id}")
async def clear_checkpoint(video_id: str):
    """Delete the checkpoint for this video, so the next run starts fresh."""
    from core.processor import delete_checkpoint
    delete_checkpoint(str(OUTPUT_DIR / video_id))
    return {"cleared": True}


@app.get("/api/download/{video_id}/{kind}")
async def download_file(video_id: str, kind: str):
    """Download one of a finished run's files: report, crossings, detections
    or summary."""
    parts = DOWNLOADS.get(kind)
    if parts is None:
        raise HTTPException(400, "Unknown download")
    folder = _final_dir(video_id)
    if folder is None:
        raise HTTPException(404, "Results not found")
    file_path = folder.joinpath(*parts)
    if not file_path.is_file():
        raise HTTPException(404, "File not found")
    # The report is named after the run so two downloads can be told apart.
    name = f"{folder.name}.xlsx" if kind == "report" else parts[-1]
    return FileResponse(file_path, filename=name)


@app.post("/api/open-folder/{video_id}")
def open_folder(video_id: str):
    """Show a finished run's folder in the file manager of the machine the
    server runs on. Only ever opens that run's own Final Results folder."""
    folder = _final_dir(video_id)
    if folder is None:
        raise HTTPException(404, "Results not found")
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(folder))
        else:
            import subprocess
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])
    except Exception as exc:
        raise HTTPException(500, f"Could not open the folder: {exc}")
    return {"opened": str(folder)}


# ── Static file serving ────────────────────────────────────────────────────

import mimetypes
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")


_NO_CACHE = {"Cache-Control": "no-cache"}


def _serve_file(file_path: Path):
    """Serve a file with the correct MIME type."""
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    # no-cache: the browser must revalidate on every load, so an updated
    # interface file is never silently replaced by a stale cached copy.
    return FileResponse(file_path, media_type=media_type, headers=_NO_CACHE)


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
    return FileResponse(index, headers=_NO_CACHE)


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
    current_session: Session | None = None
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
                resume_frame = data.get("resume_frame")

                if not video_id or video_id not in video_store:
                    print(f"[WS] Error: Invalid video ID '{video_id}'")
                    await _ws_send(websocket, "error", {"message": "Invalid video ID"})
                    continue

                # A run for this video may still be going -- the client
                # reconnects automatically, and a reconnect re-sends this
                # message. Stop the old run and wait for it to clear out
                # before starting another, or two threads would process the
                # same video and race to write the same checkpoint, with the
                # dying one writing a checkpoint from further along the
                # video than the live one.
                previous = active_sessions.get(video_id)
                if previous is not None and previous.thread is not None \
                        and previous.thread.is_alive():
                    print(f"[WS] Stopping the previous run for {video_id} first")
                    previous.stop()
                    previous.thread.join(timeout=60)

                # With no explicit frame, pick up from the checkpoint if there
                # is one. That is what makes a reconnect pick up where the
                # interrupted run left off instead of starting over.
                if not resume_frame:
                    existing = load_checkpoint(str(OUTPUT_DIR / video_id))
                    if existing:
                        resume_frame = existing["frame_num"]

                print(f"[WS] Starting processing for {video_id}, "
                      f"{len(annotations)} annotations, resume_frame={resume_frame}")

                session = Session()
                active_sessions[video_id] = session
                current_session = session

                # Run processing in background thread
                thread = threading.Thread(
                    target=_run_processing,
                    args=(websocket, loop, video_id, annotations, session, resume_frame),
                    daemon=True,
                )
                session.thread = thread
                thread.start()

            elif msg_type == "pause_processing":
                print("[WS] Pause requested")
                if current_session is not None:
                    current_session.pause()

            elif msg_type == "resume_processing":
                print("[WS] Resume requested")
                if current_session is not None:
                    current_session.resume()

            elif msg_type == "stop_processing":
                print("[WS] Stop requested")
                if current_session is not None:
                    current_session.stop()

    except WebSocketDisconnect:
        print("[WS] Client disconnected")
        if current_session is not None:
            current_session.stop()
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


class FrameSender:
    """Sends preview frames without letting a slow client stall the run.

    The preview used to be sent straight from the processing thread, and the
    send waited for the WebSocket to accept it. On a long video that is
    thousands of sends, each one a place for the inference loop to sit
    waiting on a browser.

    Frames go through a short queue instead. If the client cannot keep up,
    the queue fills and frames are dropped -- the preview skips ahead rather
    than the counting falling behind.
    """

    def __init__(self, websocket, loop, maxsize: int = 2):
        self._websocket = websocket
        self._loop = loop
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self._closed = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def send(self, payload: str):
        if self._closed:
            return
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            # The client is behind. Skip this frame.
            pass

    def _run(self):
        while True:
            payload = self._queue.get()
            if payload is None:
                break
            _ws_send_sync(self._websocket, self._loop, "frame", payload)

    def close(self):
        self._closed = True
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass


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
    session: Session,
    resume_frame: int = None,
):
    """Run the processing pipeline in a background thread."""
    stop_event = session.stop_event
    frame_sender = None
    try:
        meta = video_store[video_id]
        video_path = meta["path"]

        # Create output directory
        output_dir = OUTPUT_DIR / video_id
        os.makedirs(output_dir, exist_ok=True)

        # Convert annotations to processor format (normalized -> pixel coords)
        # Scale against the frames the model will actually see, read from
        # the video itself rather than the size recorded at upload.
        frame_w, frame_h = _decoded_frame_size(
            video_path, meta.get("width", 1920), meta.get("height", 1080)
        )
        counting_lines, road_labels = _convert_annotations(
            annotations, frame_w, frame_h,
        )
        run_line = (f"[Processing] video={video_path} frame={frame_w}x{frame_h}, "
                    f"normalized={[a.get('normalized', False) for a in annotations]}, "
                    f"annotations={json.dumps(annotations)}, "
                    f"lines={counting_lines}, labels={road_labels}")
        print(run_line)
        try:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            with open(DEBUG_DIR / "processing.log", "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + run_line + "\n")
        except Exception:
            pass

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
        frame_sender = FrameSender(websocket, loop)

        def on_frame(annotated_frame, frame_num, total_frames):
            frame_count[0] += 1
            if frame_count[0] <= 3:
                print(f"[Processing] Frame {frame_num}, shape={annotated_frame.shape}")
            # Encode frame as JPEG and send via WebSocket
            _, buffer = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            b64 = base64.b64encode(buffer).decode("utf-8")
            frame_sender.send(b64)

        _ws_send_sync(websocket, loop, "status", {"text": "Processing..."})
        print("[Processing] Starting run_single_model()...")

        def on_checkpoint(frame_num, total_frames):
            print(f"[Processing] Checkpoint saved at frame {frame_num}/{total_frames}")
            _ws_send_sync(websocket, loop, "quicksaved", {
                "frame": frame_num,
                "total": total_frames,
            })

        def on_pause(frame_num, total_frames):
            print(f"[Processing] Paused at frame {frame_num}/{total_frames}")
            _ws_send_sync(websocket, loop, "paused", {
                "frame": frame_num,
                "total": total_frames,
            })

        def on_resume(frame_num, total_frames):
            print(f"[Processing] Resumed at frame {frame_num}/{total_frames}")
            _ws_send_sync(websocket, loop, "resumed", {
                "frame": frame_num,
                "total": total_frames,
            })

        single_result = run_single_model(
            model, video_path, str(output_dir),
            progress_callback=on_progress,
            status_callback=on_status,
            frame_callback=on_frame,
            stop_event=stop_event,
            counting_lines=counting_lines if counting_lines else None,
            road_labels=road_labels if road_labels else None,
            checkpoint_callback=on_checkpoint,
            resume_frame=resume_frame,
            pause_event=session.pause_event,
            resume_event=session.resume_event,
            pause_callback=on_pause,
            resume_callback=on_resume,
        )

        if stop_event.is_set():
            print("[Processing] Cancelled by user")
            _ws_send_sync(websocket, loop, "status", {"text": "Cancelled"})
            return

        # Wrap into the multi-model envelope the results page expects
        import datetime
        finished_at = datetime.datetime.now()
        cap2 = cv2.VideoCapture(video_path)
        video_fps = cap2.get(cv2.CAP_PROP_FPS) or 30.0
        video_frames = int(cap2.get(cv2.CAP_PROP_FRAME_COUNT))
        # The upload is stored under its id, so the name the user knows the
        # video by is the one recorded at upload.
        source_filename = meta.get("filename") or os.path.basename(video_path)
        result = {
            "video_id": video_id,
            "video": video_path,
            "video_name": os.path.splitext(os.path.basename(source_filename))[0],
            "source_filename": source_filename,
            "processed_at": finished_at.isoformat(timespec="seconds"),
            "resolution": f"{int(cap2.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap2.get(cv2.CAP_PROP_FRAME_HEIGHT))}",
            "fps": video_fps,
            "total_frames": video_frames,
            "duration_seconds": round(video_frames / video_fps, 2) if video_fps > 0 else 0,
            "counting_method": COUNTING_METHOD,
            "app_version": get_latest_version(),
            "models": {model.name: single_result},
        }
        cap2.release()

        # Aakar's categories and the message for WhatsApp travel with the
        # results, so the page, the report and the message agree.
        final_results.add_categories(result)
        result["share_text"] = final_results.build_share_text(result)

        # Hand the run over: Final Results/<video> - <date time>/
        folder = final_results.publish(
            output_dir, result, road_labels, FINAL_RESULTS_DIR, finished_at
        )
        final_dirs[video_id] = folder
        print(f"[Processing] Final results saved to {folder}")
        if result.get("report_error"):
            print(f"[Processing] The Excel report could not be written: {result['report_error']}")

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
        if frame_sender is not None:
            frame_sender.close()
        # Only clear the entry if it is still this session. A reconnect
        # replaces it with a new one, and clearing that would leave the
        # live run untracked.
        if active_sessions.get(video_id) is session:
            active_sessions.pop(video_id, None)


def _decoded_frame_size(video_path: str, fallback_w: int, fallback_h: int) -> tuple:
    """Return (width, height) of the frames the processor will decode.

    Read from an actual frame, not CAP_PROP_FRAME_WIDTH/HEIGHT: with a rotated
    phone video OpenCV rotates the frames it decodes, and the reported
    properties do not always follow.
    """
    cap = cv2.VideoCapture(str(video_path))
    try:
        ok, frame = cap.read()
        if ok and frame is not None:
            h, w = frame.shape[:2]
            return w, h
    finally:
        cap.release()
    return fallback_w, fallback_h


def _convert_annotations(annotations: list, frame_width: int, frame_height: int) -> tuple:
    """Convert frontend annotation format to processor counting_lines format.

    The frontend sends each point as a fraction (0-1) of the video frame box:
    [{line: {start:{x,y}, end:{x,y}}, label: "...", normalized: true, ...}]
    Fractions are resolution-independent, so they are scaled here to the size
    of the frames the processor decodes.

    Older clients sent pixels in the preview's resolution, with an optional
    frame: {width, height}; those are still scaled from that frame size.

    Processor expects: [((sx, sy), (ex, ey)), ...] and a list of labels.
    """
    lines = []
    labels = []
    for road in annotations:
        line = road.get("line")
        if not (line and line.get("start") and line.get("end")):
            continue
        if road.get("normalized"):
            sx_scale, sy_scale = frame_width, frame_height
        else:
            frame = road.get("frame") or {}
            sx_scale = frame_width / (frame.get("width") or frame_width)
            sy_scale = frame_height / (frame.get("height") or frame_height)
        start = line["start"]
        end = line["end"]
        lines.append((
            (start["x"] * sx_scale, start["y"] * sy_scale),
            (end["x"] * sx_scale, end["y"] * sy_scale),
        ))
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
