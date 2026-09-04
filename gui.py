import datetime
import os
import re
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2
import psutil
from PIL import Image, ImageTk

from models.yolo_model import create_yolov8, create_yolov11s, create_yolov11x
from models.vehicledino import create_vehicledino
from models.rtdetr import create_rtdetr
from processor import process_video_multi

ALL_MODELS = {
    "YOLOv8n": (create_yolov8, True),
    "YOLOv11-S (UVH-26)": (create_yolov11s, True),
    "YOLOv11-X (UVH-26)": (create_yolov11x, True),
    "RT-DETR (r50vd)": (create_rtdetr, True),
    "VehicleDINO (slow on Mac)": (create_vehicledino, False),
}

MONTH_ABBRS = {
    1: "jan", 2: "feb", 3: "mar", 4: "apr",
    5: "may", 6: "jun", 7: "jul", 8: "aug",
    9: "sept", 10: "oct", 11: "nov", 12: "dec",
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Output")


class ResourceMonitor:
    def __init__(self, callback, interval=1.0):
        self._callback = callback
        self._interval = interval
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _poll(self):
        psutil.cpu_percent(interval=None)
        while not self._stop_event.is_set():
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            ram_gb = mem.used / (1024 ** 3)
            total_gb = mem.total / (1024 ** 3)
            msg = f"CPU: {cpu:.0f}%  |  RAM: {mem.percent:.0f}% ({ram_gb:.1f}/{total_gb:.1f} GB)"
            self._callback(msg)
            self._stop_event.wait(self._interval)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Vehicle Counting AI - Multi-Model Comparison")
        self.geometry("1280x800")
        self.minsize(950, 600)
        self.resizable(True, True)

        self.video_path = None
        self.processing = False
        self.cap = None
        self.preview_job = None
        self.model_vars = {}
        self.stop_event = threading.Event()
        self._resource_monitor = None
        self._processing_thread = None

        self._build_ui()

    def _build_ui(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Helvetica", 14, "bold"))
        style.configure("Sub.TLabel", font=("Helvetica", 10))
        style.configure("Big.TButton", font=("Helvetica", 11), padding=8)
        style.configure("Model.TCheckbutton", font=("Helvetica", 10))
        style.configure("Stop.TButton", font=("Helvetica", 11), padding=8)
        style.configure("Restart.TButton", font=("Helvetica", 11), padding=8)
        style.configure("Resource.TLabel", font=("Courier", 10), foreground="#333")

        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="Vehicle Counting AI", style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="Multi-Model Comparison for Indian Roads", style="Sub.TLabel").pack(anchor="w")

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=12)

        mid = ttk.Frame(self, padding=12)
        mid.pack(fill="both", expand=True)

        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        self.canvas = tk.Canvas(left, bg="#1e1e1e")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self._show_placeholder()

        right = ttk.Frame(mid, width=320)
        right.pack(side="right", fill="y")

        file_frame = ttk.LabelFrame(right, text="File Selection", padding=8)
        file_frame.pack(fill="x", pady=(0, 8))

        self.btn_select = ttk.Button(file_frame, text="Select Video", style="Big.TButton",
                                     command=self._select_video)
        self.btn_select.pack(fill="x", pady=2)

        self.video_label = ttk.Label(file_frame, text="No video", style="Sub.TLabel",
                                     foreground="gray")
        self.video_label.pack(anchor="w")

        model_frame = ttk.LabelFrame(right, text="Select Models", padding=8)
        model_frame.pack(fill="x", pady=(0, 8))

        for model_name, (_, default_on) in ALL_MODELS.items():
            var = tk.BooleanVar(value=default_on)
            self.model_vars[model_name] = var
            cb = ttk.Checkbutton(model_frame, text=model_name, variable=var,
                                 style="Model.TCheckbutton")
            cb.pack(anchor="w")

        upscale_frame = ttk.LabelFrame(right, text="Processing Options", padding=8)
        upscale_frame.pack(fill="x", pady=(0, 8))

        self.upscale_var = tk.BooleanVar(value=False)
        upscale_cb = ttk.Checkbutton(upscale_frame, text="Upscale Video (2x Real-ESRGAN)",
                                     variable=self.upscale_var)
        upscale_cb.pack(anchor="w")

        control_frame = ttk.Frame(right)
        control_frame.pack(fill="x", pady=(0, 4))

        self.btn_process = ttk.Button(control_frame, text="Run Comparison", style="Big.TButton",
                                      command=self._start_processing, state="disabled")
        self.btn_process.pack(fill="x", pady=(0, 4))

        stop_restart = ttk.Frame(control_frame)
        stop_restart.pack(fill="x", pady=(0, 4))

        self.btn_stop = ttk.Button(stop_restart, text="Stop", style="Stop.TButton",
                                   command=self._stop_processing, state="disabled")
        self.btn_stop.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_restart = ttk.Button(stop_restart, text="Restart", style="Restart.TButton",
                                      command=self._restart, state="disabled")
        self.btn_restart.pack(side="right", fill="x", expand=True, padx=(4, 0))

        self.progress = ttk.Progressbar(right, mode="determinate", length=280)
        self.progress.pack(fill="x")

        self.status_label = ttk.Label(right, text="Ready", style="Sub.TLabel",
                                      foreground="green")
        self.status_label.pack(anchor="w", pady=(4, 0))

        resource_frame = ttk.LabelFrame(right, text="System Resources", padding=6)
        resource_frame.pack(fill="x", pady=(8, 0))

        self.resource_label = ttk.Label(resource_frame, text="CPU: --%  |  RAM: --% (--/-- GB)",
                                        style="Resource.TLabel")
        self.resource_label.pack(anchor="w")

        bottom = ttk.Frame(self, padding=(12, 4, 12, 12))
        bottom.pack(fill="x")

        self.results_text = tk.Text(bottom, height=7, font=("Courier", 9),
                                    state="disabled", bg="#f0f0f0")
        self.results_text.pack(fill="x")

    def _select_video(self):
        path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.webm"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.video_path = path
        self.video_label.config(text=os.path.basename(path), foreground="black")
        self._show_preview(path)
        self._check_ready()

    def _generate_output_dir(self):
        today = datetime.date.today()
        month_abbr = MONTH_ABBRS[today.month]
        day = today.day
        date_folder = f"{month_abbr}{day}"
        date_path = os.path.join(OUTPUT_DIR, date_folder)
        os.makedirs(date_path, exist_ok=True)

        existing = []
        for name in os.listdir(date_path):
            match = re.match(r"^trial(\d+)$", name)
            if match and os.path.isdir(os.path.join(date_path, name)):
                existing.append(int(match.group(1)))

        next_trial = max(existing) + 1 if existing else 0
        trial_path = os.path.join(date_path, f"trial{next_trial}")
        os.makedirs(trial_path, exist_ok=True)

        return trial_path

    def _check_ready(self):
        selected = [k for k, v in self.model_vars.items() if v.get()]
        if self.video_path and selected and not self.processing:
            self.btn_process.config(state="normal")
        else:
            self.btn_process.config(state="disabled")

    def _show_placeholder(self):
        self.canvas.delete("all")
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 2:
            cw, ch = 800, 500
        self.canvas.create_text(
            cw // 2, ch // 2, text="No video selected",
            fill="gray", font=("Helvetica", 12), tags="placeholder"
        )

    def _on_canvas_resize(self, event):
        if not self.processing and self.cap and self.cap.isOpened():
            return
        self._show_placeholder()

    def _show_preview(self, path):
        if self.cap:
            self.cap.release()
        self.cap = cv2.VideoCapture(path)
        self._update_preview()

    def _update_preview(self):
        if self.processing:
            return
        if not self.cap or not self.cap.isOpened():
            return
        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
        if not ret:
            return

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = frame_rgb.shape[:2]
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 2 or ch < 2:
            cw, ch = 800, 500
        scale = min(cw / w, ch / h)
        new_w, new_h = int(w * scale), int(h * scale)
        frame_resized = cv2.resize(frame_rgb, (new_w, new_h))

        img = Image.fromarray(frame_resized)
        imgtk = ImageTk.PhotoImage(image=img)

        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, anchor="center", image=imgtk)
        self.canvas.image = imgtk

        self.preview_job = self.after(33, self._update_preview)

    def _start_processing(self):
        if self.processing:
            return

        selected = [ALL_MODELS[name][0]() for name, var in self.model_vars.items() if var.get()]
        if not selected:
            return

        upscaler = None
        if self.upscale_var.get():
            try:
                from models.upscaler import RealESRGANUpscaler
                upscaler = RealESRGANUpscaler(scale=2)
                upscaler.load()
            except Exception as e:
                messagebox.showerror(
                    "Upscaler Error",
                    f"Failed to initialize upscaler:\n\n{type(e).__name__}: {e}\n\n"
                    f"Run from terminal to see full traceback.",
                )
                return

        self.processing = True
        self.stop_event.clear()
        self._check_ready()
        self.btn_select.config(state="disabled")
        self.btn_process.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.btn_restart.config(state="disabled")
        self.progress["value"] = 0
        self.status_label.config(text=f"Running {len(selected)} models...", foreground="orange")

        self._processing_start_time = time.time()
        output_dir = self._generate_output_dir()
        self._set_results_text(f"Processing with {len(selected)} models...\nOutput: {output_dir}\n")

        if self.cap:
            self.cap.release()
            self.cap = None
        if self.preview_job:
            self.after_cancel(self.preview_job)
            self.preview_job = None

        self._start_resource_monitor()

        self._processing_thread = threading.Thread(
            target=self._run_processing, args=(selected, output_dir, upscaler), daemon=True
        )
        self._processing_thread.start()

    def _run_processing(self, models, output_dir, upscaler=None):
        try:
            def on_progress(pct):
                elapsed = time.time() - self._processing_start_time
                if pct > 0:
                    eta_seconds = elapsed * (100 - pct) / pct
                else:
                    eta_seconds = 0
                self.after(0, lambda p=pct, e=eta_seconds: self._update_progress(p, e))

            def on_status(msg):
                self.after(0, lambda m=msg: self.status_label.config(text=m))

            def on_frame(annotated_frame, frame_num, total):
                self.after(0, lambda f=annotated_frame: self._update_processing_preview(f))

            results = process_video_multi(
                self.video_path,
                output_dir,
                models,
                progress_callback=on_progress,
                status_callback=on_status,
                frame_callback=on_frame,
                stop_event=self.stop_event,
                upscaler=upscaler,
            )
            self.after(0, lambda r=results: self._on_complete(r))

        except Exception as e:
            self.after(0, lambda err=str(e): self._on_error(err))

    def _update_processing_preview(self, frame_bgr):
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w = frame_rgb.shape[:2]
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 2 or ch < 2:
            cw, ch = 800, 500
        scale = min(cw / w, ch / h)
        new_w, new_h = int(w * scale), int(h * scale)
        frame_resized = cv2.resize(frame_rgb, (new_w, new_h))

        img = Image.fromarray(frame_resized)
        imgtk = ImageTk.PhotoImage(image=img)

        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, anchor="center", image=imgtk)
        self.canvas.image = imgtk

    def _update_progress(self, pct, eta_seconds):
        self.progress["value"] = pct
        if eta_seconds >= 3600:
            h = int(eta_seconds // 3600)
            m = int((eta_seconds % 3600) // 60)
            eta_str = f"ETA: {h}h {m:02d}m"
        elif eta_seconds >= 60:
            m = int(eta_seconds // 60)
            s = int(eta_seconds % 60)
            eta_str = f"ETA: {m}m {s:02d}s"
        else:
            s = int(eta_seconds)
            eta_str = f"ETA: {s}s"
        self.status_label.config(text=f"Processing... {pct:.1f}% | {eta_str}", foreground="orange")

    def _stop_processing(self):
        if not self.processing:
            return
        self.stop_event.set()
        self.status_label.config(text="Stopping...", foreground="orange")
        self.btn_stop.config(state="disabled")

    def _restart(self):
        if self.processing:
            self.stop_event.set()
            if self._processing_thread:
                self._processing_thread.join(timeout=5)

        self._stop_resource_monitor()

        if self.cap:
            self.cap.release()
            self.cap = None
        if self.preview_job:
            self.after_cancel(self.preview_job)
            self.preview_job = None

        self.video_path = None
        self.processing = False
        self.stop_event.clear()
        self._processing_thread = None

        self.video_label.config(text="No video", foreground="gray")

        self.canvas.delete("all")
        self._show_placeholder()

        self._set_results_text("")
        self.progress["value"] = 0
        self.status_label.config(text="Ready", foreground="green")
        self.resource_label.config(text="CPU: --%  |  RAM: --% (--/-- GB)")

        self.btn_select.config(state="normal")
        self.btn_process.config(state="disabled")
        self.btn_stop.config(state="disabled")
        self.btn_restart.config(state="disabled")

        for name, var in self.model_vars.items():
            default = ALL_MODELS[name][1]
            var.set(default)

    def _start_resource_monitor(self):
        self._stop_resource_monitor()
        self._resource_monitor = ResourceMonitor(
            callback=lambda msg: self.after(0, lambda m=msg: self.resource_label.config(text=m)),
            interval=1.0,
        )
        self._resource_monitor.start()

    def _stop_resource_monitor(self):
        if self._resource_monitor:
            self._resource_monitor.stop()
            self._resource_monitor = None

    def _on_complete(self, results):
        self.processing = False
        self._stop_resource_monitor()
        self._check_ready()
        self.btn_select.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.btn_restart.config(state="normal")
        self.progress["value"] = 100
        self.status_label.config(text="All models complete!", foreground="green")

        subprocess.Popen(
            ["afplay", "/System/Library/Sounds/Glass.aiff"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if self.video_path:
            self._show_preview(self.video_path)

        lines = [
            f"Video: {results['video_name']} ({results['resolution']}, {results['total_frames']} frames)",
            "",
        ]

        if results.get("upscaled"):
            lines.insert(1, "Upscaling: Real-ESRGAN 2x applied")

        for model_name, data in results["models"].items():
            lines.append(f"--- {model_name} ---")
            lines.append(f"  FPS: {data['processing_fps']}  |  Time: {data['elapsed_seconds']}s")
            lines.append(f"  Unique vehicles: {data['total_unique_vehicles']}  |  Raw detections: {data['total_detections']}")
            lines.append(f"  Line crossings IN: {data['line_zone_crossings_in']}  |  OUT: {data['line_zone_crossings_out']}")
            lines.append(f"  Classes ({len(data['classes'])}): {', '.join(data['classes'][:8])}{'...' if len(data['classes']) > 8 else ''}")
            counts = data["vehicle_counts"]
            top5 = list(counts.items())[:5]
            count_str = ", ".join(f"{k}:{v}" for k, v in top5)
            lines.append(f"  Unique by class: {count_str}")
            lines.append("")

        lines.append(f"Output: {results.get('output_dir', 'N/A')}")
        lines.append("Files: summary.json, vehicle_counts_{model}.csv per model")

        self._set_results_text("\n".join(lines))

        messagebox.showinfo(
            "Complete",
            f"Processed with {len(results['models'])} models.\n\n"
            f"Summary: {results.get('output_dir', 'N/A')}/summary.json",
        )

    def _on_error(self, msg):
        self.processing = False
        self._stop_resource_monitor()
        self._check_ready()
        self.btn_select.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.btn_restart.config(state="normal")
        self.progress["value"] = 0
        self.status_label.config(text="Error", foreground="red")
        self._set_results_text(f"Error: {msg}")
        messagebox.showerror("Error", msg)

        if self.video_path:
            self._show_preview(self.video_path)

    def _set_results_text(self, text):
        self.results_text.config(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.insert("1.0", text)
        self.results_text.config(state="disabled")

    def on_close(self):
        if self.processing:
            self.stop_event.set()
        self._stop_resource_monitor()
        if self.preview_job:
            self.after_cancel(self.preview_job)
        if self.cap:
            self.cap.release()
        self.destroy()
