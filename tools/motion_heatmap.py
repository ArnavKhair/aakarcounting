#!/usr/bin/env python3
"""Where does traffic actually go? A motion heatmap for placing counting lines.

Counting lines are camera-specific, and a line placed off the traffic stream
does not undercount slightly -- it counts the wrong population entirely. This
tool answers "where is there movement, and in which direction" from the
footage itself, so a line can be placed on evidence instead of intuition.

Method
------
1. Background: the per-pixel MEDIAN of frames sampled across the clip.
   Vehicles are transient so they average away, leaving empty road.
2. Foreground: MOG2 background subtraction per frame; accumulating the mask
   gives total motion density.
3. Direction: Farneback dense optical flow between consecutive sampled
   frames. A pixel is LATERAL when |dx| > ratio * |dy| and the magnitude
   clears a floor. Cross-median (U-turn) movement is lateral; traffic running
   along the road is not.
4. ROI band report: the lateral accumulator summed over horizontal bands
   inside a region of interest. THIS is the quantitative output -- the images
   are a sanity check.

Caveat that matters
-------------------
Under perspective, distant road runs ACROSS the frame, so ordinary through
traffic there moves horizontally in image space and is flagged lateral. Those
false bands appear near the horizon. Always read the ROI band report over the
region you care about rather than eyeballing the whole picture.

Examples
--------
    # both heatmaps plus the band report over the median column
    python tools/motion_heatmap.py --video data/clip1.mp4 \\
        --roi 560,280,780,520

    # quick pass over the first 3000 frames, overlay the configured lines
    python tools/motion_heatmap.py --video data/clip1.mp4 \\
        --max-frames 3000 --draw-lines
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def build_background(cap, samples=40):
    """Per-pixel median of sampled frames: the road with the traffic removed."""
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        raise ValueError("Video reports no frames; is the file readable?")
    frames = []
    for index in np.linspace(0, max(total - 2, 0), samples).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = cap.read()
        if ok:
            frames.append(frame)
    if not frames:
        raise ValueError("Could not read any frame for the background model.")
    return np.median(np.stack(frames), axis=0).astype(np.uint8)


def accumulate(cap, step, max_frames, lateral_ratio, min_magnitude,
               history, var_threshold, progress=None):
    """Return (all_motion, lateral_motion) float accumulators."""
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    subtractor = cv2.createBackgroundSubtractorMOG2(
        history=history, varThreshold=var_threshold, detectShadows=False
    )
    kernel = np.ones((3, 3), np.uint8)

    all_motion = np.zeros((height, width), np.float32)
    lateral_motion = np.zeros((height, width), np.float32)

    previous_gray = None
    index = used = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if max_frames and index >= max_frames:
            break
        if index % step:
            index += 1
            continue

        mask = subtractor.apply(frame)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        all_motion += mask > 0

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if previous_gray is not None:
            flow = cv2.calcOpticalFlowFarneback(
                previous_gray, gray, None, 0.5, 3, 21, 3, 5, 1.2, 0
            )
            dx, dy = np.abs(flow[..., 0]), np.abs(flow[..., 1])
            magnitude = np.linalg.norm(flow, axis=2)
            lateral_motion += (
                (dx > lateral_ratio * dy) & (magnitude > min_magnitude) & (mask > 0)
            )
        previous_gray = gray

        used += 1
        index += 1
        if progress and used % 200 == 0:
            progress(used, index)

    return all_motion, lateral_motion, used


def colorize(accumulator, background, title, gain=3.0):
    """Blend a normalised accumulator over the background as a TURBO heatmap."""
    normalised = accumulator / max(accumulator.max(), 1)
    normalised = np.clip(normalised * gain, 0, 1)
    heat = cv2.applyColorMap((normalised * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    blended = cv2.addWeighted(background, 0.45, heat, 0.55, 0)
    cv2.putText(blended, title, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (255, 255, 255), 2)
    return blended


def band_report(accumulator, roi, band_height=30):
    """Lateral energy per horizontal band inside the ROI. The real evidence."""
    x0, y0, x1, y1 = roi
    rows = []
    for top in range(y0, y1, band_height):
        bottom = min(top + band_height, y1)
        rows.append((top, bottom, float(accumulator[top:bottom, x0:x1].sum())))
    return rows


def draw_counting_lines(image):
    """Overlay the lines currently configured in core/config.py, if importable."""
    try:
        from core import config
    except Exception as exc:  # noqa: BLE001 - tool should still work standalone
        print(f"  (could not import core.config to draw lines: {exc})")
        return image
    height, width = image.shape[:2]
    colors = [(255, 255, 255), (0, 200, 255), (255, 0, 255), (0, 255, 128)]

    # Works with either config shape: a COUNTING_LINES list if one is ever
    # configured, otherwise the single horizontal LINE_POSITION the pipeline
    # currently uses.
    specs = getattr(config, "COUNTING_LINES", None)
    if specs:
        for i, spec in enumerate(specs):
            color = colors[i % len(colors)]
            (sx, sy), (ex, ey) = spec.pixels(width, height)
            cv2.line(image, (sx, sy), (ex, ey), color, 3)
            mx, my = (sx + ex) // 2, (sy + ey) // 2
            anchor = (mx + 12, my) if abs(ex - sx) < abs(ey - sy) else (mx - 60, my - 12)
            cv2.putText(image, spec.name, anchor, cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
        return image

    y = int(config.LINE_POSITION * height)
    cv2.line(image, (0, y), (width, y), colors[0], 3)
    cv2.putText(image, f"counting line (y={y})", (12, y - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, colors[0], 2)
    return image


def parse_roi(text, width, height):
    if not text:
        # Default: the middle fifth of the frame, full height.
        return (int(width * 0.4), 0, int(width * 0.6), height)
    parts = [int(v) for v in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--roi needs x0,y0,x1,y1")
    return tuple(parts)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--video", required=True, help="Path to the input video.")
    parser.add_argument("--out", default="heatmap_out", help="Output directory.")
    parser.add_argument("--step", type=int, default=3,
                        help="Process every Nth frame. Optical flow is measured "
                             "between consecutive SAMPLED frames, so displacement "
                             "scales with this; raise --min-magnitude if you raise "
                             "step. Default 3.")
    parser.add_argument("--max-frames", type=int, default=0,
                        help="Stop after this many frames (0 = whole video).")
    parser.add_argument("--roi", default=None,
                        help="x0,y0,x1,y1 for the band report. Default: middle "
                             "fifth of the frame, full height.")
    parser.add_argument("--band-height", type=int, default=30,
                        help="Row height for the band report. Default 30.")
    parser.add_argument("--lateral-ratio", type=float, default=1.6,
                        help="|dx| must exceed this times |dy| to count as "
                             "lateral. Default 1.6.")
    parser.add_argument("--min-magnitude", type=float, default=2.0,
                        help="Minimum flow magnitude in px. Default 2.0.")
    parser.add_argument("--history", type=int, default=400,
                        help="MOG2 history length. Default 400.")
    parser.add_argument("--var-threshold", type=float, default=40,
                        help="MOG2 variance threshold. Default 40.")
    parser.add_argument("--gain", type=float, default=3.0,
                        help="Brightness gain for the heatmap overlay. Default 3.")
    parser.add_argument("--draw-lines", action="store_true",
                        help="Overlay the counting lines from core/config.py.")
    args = parser.parse_args()

    if not os.path.exists(args.video):
        parser.error(f"No such file: {args.video}")

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        parser.error(
            f"Could not open {args.video}. On macOS a file handed to another app "
            "can carry a com.apple.macl grant that blocks other processes; "
            "copying it into the project usually clears that."
        )

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    roi = parse_roi(args.roi, width, height)
    os.makedirs(args.out, exist_ok=True)

    print(f"video   : {args.video}  ({width}x{height})")
    print(f"roi     : {roi}")
    print("building background (median of sampled frames)...")
    background = build_background(cap)
    cv2.imwrite(os.path.join(args.out, "background.jpg"), background)

    print("accumulating motion...")
    all_motion, lateral_motion, used = accumulate(
        cap, args.step, args.max_frames, args.lateral_ratio, args.min_magnitude,
        args.history, args.var_threshold,
        progress=lambda u, i: print(f"  {u} sampled ({i} read)", flush=True),
    )
    cap.release()
    print(f"frames sampled: {used}")

    for accumulator, name, title in (
        (all_motion, "heat_all.jpg", "ALL motion"),
        (lateral_motion, "heat_lateral.jpg", "LATERAL (cross-road) motion only"),
    ):
        image = colorize(accumulator, background, title, args.gain)
        if args.draw_lines:
            image = draw_counting_lines(image)
        cv2.imwrite(os.path.join(args.out, name), image)

    np.save(os.path.join(args.out, "motion_all.npy"), all_motion)
    np.save(os.path.join(args.out, "motion_lateral.npy"), lateral_motion)

    rows = band_report(lateral_motion, roi, args.band_height)
    peak = max((r[2] for r in rows), default=0.0)
    print(f"\nLateral energy per band inside ROI x {roi[0]}-{roi[2]}:")
    print("(a median gap used for U-turns shows a clear peak that falls to "
          "~zero where the median resumes)")
    for top, bottom, energy in rows:
        bar = "#" * int(40 * energy / peak) if peak else ""
        print(f"  y {top:4d}-{bottom:<4d} {energy:12.0f}  {bar}")

    print(f"\nWrote to {args.out}/: background.jpg, heat_all.jpg, "
          "heat_lateral.jpg, motion_*.npy")


if __name__ == "__main__":
    main()
