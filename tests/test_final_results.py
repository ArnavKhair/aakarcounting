import csv
import datetime
import json
import os
import tempfile
import unittest
from pathlib import Path

import openpyxl

from core import final_results as fr

FINISHED = datetime.datetime(2026, 11, 11, 14, 30, 5)

EXPECTED_MESSAGE = """*Traffic Count - MG Road cam2*
_11 Nov 2026 - 5 min video_

*Total: 459 vehicles*

*left - 234*
- Cars/Vans/Jeeps: 88
- Two Wheeler: 85
- 2 Axle Truck: 26
- Auto Rickshaw: 16
- 6/8 seater: 8
- LCV: 8
- Private Bus: 3

*right - 216*
- Two Wheeler: 95
- Cars/Vans/Jeeps: 43
- Auto Rickshaw: 28
- 2 Axle Truck: 26
- LCV: 17
- 6/8 seater: 4
- Private Bus: 3

*center - 9*
- Cars/Vans/Jeeps: 9

_Cars/Vans/Jeeps includes Taxi; Auto Rickshaw includes Goods Auto; Private Bus includes Govt. Bus; LCV includes Mini LCV; 2 Axle Truck includes 3 Axle Truck and MAV._"""

CROSSINGS = [
    {"tracker_id": "2", "frame": "8", "timestamp": "0.267", "line_zone_index": "0",
     "vehicle_type": "Three-wheeler", "canonical_class": "three_wheeler",
     "track_frames": "79", "mean_confidence": "0.7405"},
    {"tracker_id": "1", "frame": "20", "timestamp": "3725.4", "line_zone_index": "1",
     "vehicle_type": "Sedan", "canonical_class": "car",
     "track_frames": "54", "mean_confidence": "0.8108"},
    {"tracker_id": "9", "frame": "30", "timestamp": "61.0", "line_zone_index": "7",
     "vehicle_type": "MUV", "canonical_class": "car",
     "track_frames": "12", "mean_confidence": "0.9"},
]


def make_summary():
    """The real run outputs/62f33e0ec8c4, as the server hands it over."""
    summary = {
        "video_id": "62f33e0ec8c4",
        "video_name": "MG_Road_cam2",
        "processed_at": FINISHED.isoformat(timespec="seconds"),
        "duration_seconds": 300.47,
        "resolution": "1280x720",
        "fps": 29.97,
        "total_frames": 9005,
        "counting_method": "Line crossing",
        "app_version": "v1.3.0",
        "_internal": "not for disk",
        "models": {
            "YOLOv11-S (UVH-26)": {
                "model_name": "YOLOv11-S (UVH-26)",
                "total_crossings": 459,
                "vehicle_counts": {
                    "Two-wheeler": 180, "Sedan": 55, "SUV": 54, "Truck": 52,
                    "Three-wheeler": 44, "Hatchback": 31, "LCV": 25, "MUV": 12, "Bus": 6,
                },
                "road_counts": {
                    "left": {"total": 234, "by_type": {
                        "Two-wheeler": 85, "SUV": 31, "Sedan": 29, "Hatchback": 28,
                        "Truck": 26, "Three-wheeler": 16, "MUV": 8, "LCV": 8, "Bus": 3}},
                    "right": {"total": 216, "by_type": {
                        "Two-wheeler": 95, "Three-wheeler": 28, "Truck": 26, "Sedan": 22,
                        "SUV": 18, "LCV": 17, "MUV": 4, "Hatchback": 3, "Bus": 3}},
                    "center": {"total": 9, "by_type": {"SUV": 5, "Sedan": 4}},
                },
            },
        },
    }
    fr.add_categories(summary)
    return summary


class NamingTest(unittest.TestCase):
    def test_folder_name_is_video_and_finish_time(self):
        self.assertEqual(fr.safe_folder_name("MG Road cam2", FINISHED),
                         "MG Road cam2 - 2026-11-11 14.30")

    def test_folder_name_drops_characters_windows_forbids(self):
        self.assertEqual(fr.safe_folder_name('a<b>:"c/d\\e|f?g*h. ', FINISHED),
                         "abcdefgh - 2026-11-11 14.30")

    def test_folder_name_falls_back_when_nothing_is_left(self):
        self.assertEqual(fr.safe_folder_name("???", FINISHED), "Video - 2026-11-11 14.30")
        self.assertEqual(fr.safe_folder_name(None, FINISHED), "Video - 2026-11-11 14.30")

    def test_folder_name_is_capped(self):
        name = fr.safe_folder_name("x" * 300, FINISHED)
        self.assertEqual(name, "x" * 80 + " - 2026-11-11 14.30")

    def test_unique_dir_adds_a_number_on_a_clash(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            self.assertEqual(fr.unique_dir(parent, "run"), parent / "run")
            (parent / "run").mkdir()
            self.assertEqual(fr.unique_dir(parent, "run"), parent / "run (2)")
            (parent / "run (2)").mkdir()
            self.assertEqual(fr.unique_dir(parent, "run"), parent / "run (3)")

    def test_video_length(self):
        self.assertEqual(fr.format_video_length(42.2), "42 sec")
        self.assertEqual(fr.format_video_length(300.47), "5 min")
        self.assertEqual(fr.format_video_length(3600), "1 h")
        self.assertEqual(fr.format_video_length(3725), "1 h 2 min")
        self.assertEqual(fr.format_video_length(0), "0 sec")

    def test_time_in_video(self):
        self.assertEqual(fr.format_time_in_video(0.267), "0:00:00")
        self.assertEqual(fr.format_time_in_video(61.0), "0:01:01")
        self.assertEqual(fr.format_time_in_video(3725.4), "1:02:05")


class CategoriesOnSummaryTest(unittest.TestCase):
    def test_roads_and_totals_get_category_counts(self):
        data = make_summary()["models"]["YOLOv11-S (UVH-26)"]
        self.assertEqual(data["road_counts"]["right"]["by_category"]["Cars/Vans/Jeeps"], 43)
        self.assertIsNone(data["road_counts"]["right"]["by_category"]["Taxi"])
        self.assertEqual(data["category_counts"]["Cars/Vans/Jeeps"], 140)
        self.assertEqual(data["category_counts"]["6/8 seater"], 12)
        self.assertEqual(data["category_counts"]["2 Axle Truck"], 52)
        # The model's own breakdown is kept beside it.
        self.assertEqual(data["road_counts"]["right"]["by_type"]["Sedan"], 22)

    def test_headings_travel_with_the_summary(self):
        summary = make_summary()
        self.assertEqual(summary["category_headings"]["6/8 seater"], "6/8 seater (MUV)")
        self.assertEqual(len(summary["category_headings"]), 16)
        self.assertEqual(len(summary["category_legend"]), 6)


class ShareTextTest(unittest.TestCase):
    def test_message_for_the_real_run(self):
        self.assertEqual(fr.build_share_text(make_summary()), EXPECTED_MESSAGE)

    def test_one_vehicle_is_singular_and_empty_road_has_only_a_heading(self):
        summary = make_summary()
        data = summary["models"]["YOLOv11-S (UVH-26)"]
        data["total_crossings"] = 1
        data["vehicle_counts"] = {"bicycle": 1}
        data["road_counts"] = {
            "North": {"total": 1, "by_type": {"bicycle": 1}},
            "South": {"total": 0, "by_type": {}},
        }
        fr.add_categories(summary)
        self.assertEqual(fr.build_share_text(summary), "\n".join([
            "*Traffic Count - MG Road cam2*",
            "_11 Nov 2026 - 5 min video_",
            "",
            "*Total: 1 vehicle*",
            "",
            "*North - 1*",
            "- Cycle: 1",
            "",
            "*South - 0*",
        ]))

    def test_formatting_characters_in_names_cannot_break_the_message(self):
        summary = make_summary()
        summary["video_name"] = "*cam*_2"
        data = summary["models"]["YOLOv11-S (UVH-26)"]
        data["road_counts"] = {"NH*48_east": {"total": 0, "by_type": {}}}
        text = fr.build_share_text(summary)
        self.assertIn("*Traffic Count - cam 2*", text)
        self.assertIn("*NH48 east - 0*", text)


class ReportTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "report.xlsx"
        fr.write_report(self.path, make_summary(), CROSSINGS, ["left", "right", "center"])
        self.book = openpyxl.load_workbook(self.path)

    def rows(self, sheet):
        return [list(r) for r in self.book[sheet].iter_rows(values_only=True)]

    def test_three_sheets(self):
        self.assertEqual(self.book.sheetnames, ["Overview", "By Road", "Crossings"])

    def test_overview(self):
        pairs = {r[0]: r[1] for r in self.rows("Overview") if r[0]}
        self.assertEqual(pairs["Video"], "MG_Road_cam2")
        self.assertEqual(pairs["Processed on"], "11 Nov 2026, 14:30")
        self.assertEqual(pairs["Video length"], "5 min")
        self.assertEqual(pairs["Total vehicles"], 459)
        self.assertEqual(pairs["left"], 234)
        self.assertEqual(pairs["right"], 216)
        self.assertEqual(pairs["center"], 9)
        self.assertEqual(pairs["Model"], "YOLOv11-S (UVH-26)")
        self.assertEqual(pairs["Software version"], "v1.3.0")

    def test_by_road_has_sixteen_rows_in_aakar_order_with_headings(self):
        rows = self.rows("By Road")
        self.assertEqual(rows[0], ["Vehicle category", "left", "right", "center", "Total"])
        self.assertEqual(rows[1], ["Cars/Vans/Jeeps (Hatchback, Sedan, SUV, Van)", 88, 43, 9, 140])
        self.assertEqual(rows[2], ["Taxi", "-", "-", "-", "-"])
        self.assertEqual(rows[3], ["Auto Rickshaw (Three-wheeler)", 16, 28, 0, 44])
        self.assertEqual(rows[4], ["6/8 seater (MUV)", 8, 4, 0, 12])
        self.assertEqual(rows[6], ["Cycle (bicycle)", 0, 0, 0, 0])
        self.assertEqual([r[0] for r in rows[1:17]][-1], "Other (Others)")
        dashes = [r[0] for r in rows[1:17] if r[4] == "-"]
        self.assertEqual(dashes, ["Taxi", "Govt. Bus", "Goods Auto", "Mini LCV",
                                  "3 Axle Truck", "MAV"])

    def test_by_road_totals_and_legend(self):
        rows = self.rows("By Road")
        self.assertEqual(rows[17], ["Total", 234, 216, 9, 459])
        legend = [r[0] for r in rows[18:] if r[0]]
        self.assertIn("Taxi: counted in Cars/Vans/Jeeps", legend)
        self.assertEqual(len(legend), 7)  # one explaining line plus six rows

    def test_crossings_name_the_road_and_the_category(self):
        rows = self.rows("Crossings")
        self.assertEqual(rows[0], ["#", "Time in video", "Road", "Vehicle category",
                                   "Model classification", "Confidence"])
        self.assertEqual(rows[1], [1, "0:00:00", "left", "Auto Rickshaw", "Three-wheeler", 0.7405])
        self.assertEqual(rows[2], [2, "1:02:05", "right", "Cars/Vans/Jeeps", "Sedan", 0.8108])
        # A line index with no label still gets a name.
        self.assertEqual(rows[3][2], "Road 8")
        self.assertEqual(len(rows), 4)


class PublishTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.work = root / "outputs" / "62f33e0ec8c4"
        self.final_root = root / "Final Results"
        self.make_work()

    def make_work(self):
        self.work.mkdir(parents=True)
        with open(self.work / "crossings_YOLOv11-S__UVH-26.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(CROSSINGS[0]))
            writer.writeheader()
            writer.writerows(CROSSINGS)
        (self.work / "vehicle_counts_YOLOv11-S__UVH-26.csv").write_text("frame\n1\n")

    def publish(self):
        summary = make_summary()
        summary["share_text"] = fr.build_share_text(summary)
        folder = fr.publish(self.work, summary, ["left", "right", "center"],
                            self.final_root, FINISHED)
        return folder, summary

    def test_folder_layout(self):
        folder, summary = self.publish()
        self.assertEqual(folder, self.final_root / "MG_Road_cam2 - 2026-11-11 14.30")
        files = sorted(str(p.relative_to(folder)).replace(os.sep, "/")
                       for p in folder.rglob("*") if p.is_file())
        self.assertEqual(files, [
            "Traffic Count Report.xlsx",
            "raw data/crossings.csv",
            "raw data/detections.csv",
            "raw data/summary.json",
        ])
        self.assertEqual(summary["results_folder"], folder.name)
        self.assertNotIn("report_error", summary)

    def test_working_folder_is_removed(self):
        self.publish()
        self.assertFalse(self.work.exists())

    def test_saved_summary_can_be_found_again_and_has_no_internal_keys(self):
        folder, _ = self.publish()
        with open(folder / "raw data" / "summary.json", encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["video_id"], "62f33e0ec8c4")
        self.assertEqual(saved["share_text"], EXPECTED_MESSAGE)
        self.assertNotIn("_internal", saved)
        self.assertEqual(fr.find_folder(self.final_root, "62f33e0ec8c4"), folder)
        self.assertIsNone(fr.find_folder(self.final_root, "nope"))

    def test_second_run_of_the_same_video_gets_its_own_folder(self):
        first, _ = self.publish()
        self.make_work()
        second, _ = self.publish()
        self.assertEqual(second.name, first.name + " (2)")

    def test_raw_results_survive_a_report_that_cannot_be_written(self):
        original = fr.write_report

        def broken(*args, **kwargs):
            raise RuntimeError("no openpyxl")

        fr.write_report = broken
        self.addCleanup(setattr, fr, "write_report", original)
        folder, summary = self.publish()
        self.assertTrue((folder / "raw data" / "crossings.csv").exists())
        self.assertTrue((folder / "raw data" / "summary.json").exists())
        self.assertIn("no openpyxl", summary["report_error"])


if __name__ == "__main__":
    unittest.main()
