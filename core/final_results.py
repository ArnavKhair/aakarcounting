"""What a finished run hands to the user.

A run works in outputs/<video_id>/ so that checkpoints and resume keep a
stable address. When it completes, publish() turns that working folder into

    Final Results/
      <video name> - <date time>/
        Traffic Count Report.xlsx
        raw data/
          crossings.csv
          detections.csv
          summary.json

and build_share_text() writes the overview that the results page copies to
the clipboard for WhatsApp.

Everything here works from the run summary (the dict the server sends to the
results page), so the report, the message and the page show the same numbers.
"""
import csv
import datetime
import json
import os
import re
import shutil
from pathlib import Path

from core import aakar_categories

REPORT_NAME = "Traffic Count Report.xlsx"
RAW_DIR = "raw data"
CROSSINGS_NAME = "crossings.csv"
DETECTIONS_NAME = "detections.csv"
SUMMARY_NAME = "summary.json"

DASH = "-"
_MAX_NAME = 80
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


# ── Names and small formats ────────────────────────────────────────────────

def safe_folder_name(video_name, finished_at: datetime.datetime) -> str:
    """"<video name> - 2026-11-11 14.30", safe to use as a Windows folder."""
    name = _FORBIDDEN.sub("", str(video_name or "")).strip(" .")[:_MAX_NAME].strip(" .")
    return f"{name or 'Video'} - {finished_at:%Y-%m-%d %H.%M}"


def unique_dir(parent, name: str) -> Path:
    """A path under parent that does not exist yet: name, then "name (2)"..."""
    parent = Path(parent)
    candidate = parent / name
    number = 2
    while candidate.exists():
        candidate = parent / f"{name} ({number})"
        number += 1
    return candidate


def format_video_length(seconds) -> str:
    seconds = float(seconds or 0)
    if seconds < 60:
        return f"{int(round(seconds))} sec"
    minutes = int(round(seconds / 60))
    hours, minutes = divmod(minutes, 60)
    if not hours:
        return f"{minutes} min"
    return f"{hours} h {minutes} min" if minutes else f"{hours} h"


def format_time_in_video(seconds) -> str:
    total = int(float(seconds or 0))
    return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}"


def _processed_at(summary: dict):
    try:
        return datetime.datetime.fromisoformat(summary.get("processed_at") or "")
    except ValueError:
        return None


def _date(moment) -> str:
    return f"{moment.day} {moment:%b %Y}" if moment else ""


def _model_data(summary: dict) -> dict:
    """The app runs one model per video; its results are the run's results."""
    models = summary.get("models") or {}
    return next(iter(models.values()), {})


# ── Aakar categories on the summary ────────────────────────────────────────

def add_categories(summary: dict) -> dict:
    """Add Aakar's categories beside the model's own counts.

    The model's breakdown (by_type, vehicle_counts) is left as it is; the
    categories are a second view of the same vehicles.
    """
    for data in (summary.get("models") or {}).values():
        data["category_counts"] = aakar_categories.count_by_category(
            data.get("vehicle_counts"))
        for road in (data.get("road_counts") or {}).values():
            road["by_category"] = aakar_categories.count_by_category(road.get("by_type"))
    summary["category_headings"] = {
        c: aakar_categories.heading(c) for c in aakar_categories.CATEGORIES
    }
    summary["category_legend"] = aakar_categories.legend()
    return summary


def _road_categories(road: dict) -> dict:
    return road.get("by_category") or aakar_categories.count_by_category(road.get("by_type"))


# ── The copied message ─────────────────────────────────────────────────────

def _plain(text) -> str:
    """A name as it can sit inside WhatsApp bold: its own formatting
    characters would end the bold early or start italics."""
    text = re.sub(r"[*~`]", "", str(text or ""))
    return " ".join(text.replace("_", " ").split())


def _category_lines(counts: dict) -> list:
    listed = [(c, n) for c, n in counts.items() if n]
    listed.sort(key=lambda item: -item[1])  # stable: ties stay in Aakar's order
    return [f"- {category}: {count}" for category, count in listed]


def build_share_text(summary: dict) -> str:
    """The overview for WhatsApp: *bold*, _italic_ and "- " lists."""
    data = _model_data(summary)
    total = data.get("total_crossings") or 0
    roads = data.get("road_counts") or {}

    subtitle = " - ".join(part for part in (
        _date(_processed_at(summary)),
        f"{format_video_length(summary.get('duration_seconds'))} video",
    ) if part)

    blocks = [
        f"*Traffic Count - {_plain(summary.get('video_name')) or 'Video'}*\n_{subtitle}_",
        f"*Total: {total} {'vehicle' if total == 1 else 'vehicles'}*",
    ]
    for label, road in roads.items():
        lines = [f"*{_plain(label)} - {road.get('total') or 0}*"]
        lines += _category_lines(_road_categories(road))
        blocks.append("\n".join(lines))
    if not roads:
        lines = _category_lines(
            aakar_categories.count_by_category(data.get("vehicle_counts")))
        if lines:
            blocks.append("\n".join(lines))

    overall = data.get("category_counts") or aakar_categories.count_by_category(
        data.get("vehicle_counts"))
    notes = aakar_categories.notes_for(overall) if total else []
    if notes:
        blocks.append(f"_{'; '.join(notes)}._")
    return "\n\n".join(blocks)


# ── The Excel report ───────────────────────────────────────────────────────

def write_report(path, summary: dict, crossings_rows: list, road_labels: list):
    """Write Traffic Count Report.xlsx: Overview, By Road, Crossings."""
    # Imported here so a machine that has not installed openpyxl yet can
    # still finish a run and keep its raw results.
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    bold = Font(bold=True)
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", start_color="1F4E78")
    total_fill = PatternFill("solid", start_color="DDEBF7")
    muted = Font(italic=True, color="595959")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    right = Alignment(horizontal="right")

    def header(sheet, row, values):
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=column, value=value)
            cell.font, cell.fill, cell.border = head_font, head_fill, border
            if column > 1:
                cell.alignment = right

    def body(sheet, row, values, total=False):
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=column, value=value)
            cell.border = border
            if column > 1:
                cell.alignment = right
            if total:
                cell.font, cell.fill = bold, total_fill

    def widths(sheet, sizes):
        for column, size in enumerate(sizes, start=1):
            sheet.column_dimensions[get_column_letter(column)].width = size

    data = _model_data(summary)
    roads = data.get("road_counts") or {}
    moment = _processed_at(summary)

    book = Workbook()

    # Overview
    sheet = book.active
    sheet.title = "Overview"
    sheet["A1"] = "Traffic Count Report"
    sheet["A1"].font = Font(bold=True, size=16)
    row = 3
    for label, value in (
        ("Video", summary.get("video_name") or ""),
        ("Processed on", f"{_date(moment)}, {moment:%H:%M}" if moment else ""),
        ("Video length", format_video_length(summary.get("duration_seconds"))),
        ("Resolution", summary.get("resolution") or ""),
        ("Total vehicles", data.get("total_crossings") or 0),
    ):
        sheet.cell(row=row, column=1, value=label).font = bold
        sheet.cell(row=row, column=2, value=value).alignment = Alignment(horizontal="left")
        row += 1
    row += 1
    header(sheet, row, ["Road", "Vehicles"])
    row += 1
    for label, road in roads.items():
        body(sheet, row, [label, road.get("total") or 0])
        row += 1
    body(sheet, row, ["Total", data.get("total_crossings") or 0], total=True)
    row += 2
    for label, value in (
        ("Counting method", summary.get("counting_method") or ""),
        ("Model", data.get("model_name") or ""),
        ("Software version", summary.get("app_version") or ""),
    ):
        sheet.cell(row=row, column=1, value=label).font = bold
        sheet.cell(row=row, column=2, value=value)
        row += 1
    widths(sheet, [24, 44])

    # By Road
    sheet = book.create_sheet("By Road")
    labels = list(roads)
    header(sheet, 1, ["Vehicle category"] + labels + ["Total"])
    per_road = [_road_categories(roads[label]) for label in labels]
    row = 2
    for category in aakar_categories.CATEGORIES:
        counts = [road[category] for road in per_road]
        if category in aakar_categories.COUNTED_IN:
            values = [DASH] * (len(labels) + 1)
        else:
            values = counts + [sum(counts)]
        body(sheet, row, [aakar_categories.heading(category)] + values)
        row += 1
    road_totals = [roads[label].get("total") or 0 for label in labels]
    body(sheet, row, ["Total"] + road_totals + [sum(road_totals)], total=True)
    row += 2
    sheet.cell(row=row, column=1,
               value=f"{DASH} = not yet separated by the software. "
                     "These vehicles are counted in another row:").font = muted
    for line in aakar_categories.legend():
        row += 1
        sheet.cell(row=row, column=1, value=line).font = muted
    sheet.freeze_panes = "B2"
    widths(sheet, [46] + [max(12, len(str(label)) + 2) for label in labels] + [12])

    # Crossings
    sheet = book.create_sheet("Crossings")
    columns = ["#", "Time in video", "Road", "Vehicle category",
               "Model classification", "Confidence"]
    header(sheet, 1, columns)
    for number, event in enumerate(crossings_rows, start=1):
        index = int(float(event.get("line_zone_index") or 0))
        road = road_labels[index] if road_labels and 0 <= index < len(road_labels) \
            else f"Road {index + 1}"
        model_type = event.get("vehicle_type") or ""
        try:
            confidence = round(float(event.get("mean_confidence")), 4)
        except (TypeError, ValueError):
            confidence = None
        sheet.append([
            number,
            format_time_in_video(event.get("timestamp")),
            road,
            aakar_categories.to_category(model_type),
            model_type,
            confidence,
        ])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{max(sheet.max_row, 1)}"
    widths(sheet, [8, 15, 24, 22, 22, 12])

    book.save(str(path))


# ── Publishing a finished run ──────────────────────────────────────────────

def _first(folder: Path, pattern: str):
    return next(iter(sorted(folder.glob(pattern))), None)


def _read_csv(path) -> list:
    if path is None or not Path(path).exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def publish(work_dir, summary: dict, road_labels: list, final_root,
            finished_at: datetime.datetime = None) -> Path:
    """Turn a finished run's working folder into its Final Results folder.

    The raw files are moved first and the summary is written last, so a
    report that cannot be written (it is the only step that needs openpyxl)
    costs the report and nothing else. The reason is left in
    summary["report_error"].
    """
    work_dir = Path(work_dir)
    finished_at = finished_at or datetime.datetime.now()
    folder = unique_dir(final_root, safe_folder_name(summary.get("video_name"), finished_at))
    raw = folder / RAW_DIR
    os.makedirs(raw)

    moved = {}
    for pattern, name in (("crossings_*.csv", CROSSINGS_NAME),
                          ("vehicle_counts_*.csv", DETECTIONS_NAME)):
        source = _first(work_dir, pattern)
        if source is not None:
            shutil.move(str(source), str(raw / name))
            moved[name] = str(raw / name)

    summary["results_folder"] = folder.name
    for data in (summary.get("models") or {}).values():
        if CROSSINGS_NAME in moved:
            data["crossings_csv_path"] = moved[CROSSINGS_NAME]
        if DETECTIONS_NAME in moved:
            data["csv_path"] = moved[DETECTIONS_NAME]

    try:
        write_report(folder / REPORT_NAME, summary,
                     _read_csv(moved.get(CROSSINGS_NAME)), road_labels)
    except Exception as exc:  # the run's numbers matter more than the workbook
        summary["report_error"] = f"{type(exc).__name__}: {exc}"

    with open(raw / SUMMARY_NAME, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in summary.items() if not k.startswith("_")}, f, indent=2)

    try:
        os.rmdir(work_dir)  # only if nothing else is left in it
    except OSError:
        pass
    return folder


def find_folder(final_root, video_id: str):
    """The Final Results folder of a run, found by the id in its summary.
    Used after a server restart, when the folder is no longer remembered."""
    final_root = Path(final_root)
    if not final_root.is_dir():
        return None
    candidates = sorted(final_root.glob(f"*/{RAW_DIR}/{SUMMARY_NAME}"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as f:
                if json.load(f).get("video_id") == video_id:
                    return path.parent.parent
        except (OSError, ValueError):
            continue
    return None
