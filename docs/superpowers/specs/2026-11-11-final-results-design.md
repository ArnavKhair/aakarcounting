# v1.3.0: Final Results folder, Excel report, and Copy for WhatsApp

## Context

Today a finished run leaves five loose files in `outputs/<random id>/` (two summary CSVs, a crossings
CSV, a 7 MB per-frame CSV and `summary.json`). Nothing records the video's real name or when it was
processed, and the only way to pass results on is to download CSVs. v1.3.x is about how results reach
the user. v1.3.0 does two things:

1. Every finished run produces one named **Final Results** folder with a formatted Excel report.
2. The results page gets a **Copy for WhatsApp** button that puts a ready-to-paste overview on the
   clipboard.

Repo: `D:\ArnavKhair\aakarcounting\aakarcounting` (FastAPI + plain HTML/JS, no tests today).

## Decisions

Chosen by you:

- **D1 Final Results = named folder + Excel report**, raw files in a `raw data` subfolder.
- **D2 Message = totals plus a breakdown for each road.**
- **D3 Vocabulary = Aakar's 16 categories** in the report, the message and the results page
  (replaces the earlier "broad in message, detailed in report"). The live preview during processing
  keeps the model's labels for now.
- **D3a "6/8 seater" = MUVs** (Innova, Ertiga), so the model's MUV class maps to it directly.
- **D3b All 16 rows are always shown.** Where the model cannot split a group, the whole count goes
  in one row and the others show a dash:

  | Aakar category | YOLO classification | Row heading as shown |
  |---|---|---|
  | Cars/Vans/Jeeps | Hatchback, Sedan, SUV, Van | Cars/Vans/Jeeps (Hatchback, Sedan, SUV, Van) |
  | Taxi | none: counted in Cars/Vans/Jeeps | Taxi, with a dash |
  | Auto Rickshaw | Three-wheeler (all) | Auto Rickshaw (Three-wheeler) |
  | 6/8 seater | MUV | 6/8 seater (MUV) |
  | Two Wheeler | Two-wheeler | Two Wheeler (Two-wheeler) |
  | Cycle | bicycle | Cycle (bicycle) |
  | Mini Bus | Mini-bus, tempo-traveller | Mini Bus (Mini-bus, tempo-traveller) |
  | Private Bus | Bus (all) | Private Bus (Bus) |
  | Govt. Bus | none: counted in Private Bus | Govt. Bus, with a dash |
  | Goods Auto | none: counted in Auto Rickshaw | Goods Auto, with a dash |
  | Mini LCV | none: counted in LCV | Mini LCV, with a dash |
  | LCV | LCV (all) | LCV (LCV) |
  | 2 Axle Truck | Truck (all) | 2 Axle Truck (Truck) |
  | 3 Axle Truck | none: counted in 2 Axle Truck | 3 Axle Truck, with a dash |
  | MAV | none: counted in 2 Axle Truck | MAV, with a dash |
  | Other | Others, and any label with no mapping | Other (Others) |

- **D3c Each category heading names the YOLO classification behind it in brackets**, as in the last
  column. This applies to the By Road sheet and the results page tables. The brackets are built from
  the same mapping table, so they cannot drift from what is actually counted. My call: the copied
  WhatsApp message keeps the plain Aakar names, because the brackets would make every line wrap on
  a phone; say so if you want them there too.

My calls (change any of them):

- **D4 Build the report and the message on the server, in Python.** The workbook has to exist on disk
  inside the folder, so a browser-side Excel library does not fit. Building the message in the same
  place keeps one source for the numbers and makes both testable. The text travels with the results,
  so the Copy button works instantly.
- **D5 `openpyxl` for the workbook** (one new line in `requirements.txt`, installed into the project
  venv with `venv\Scripts\python -m pip install openpyxl`). Chosen over XlsxWriter because it can also
  read the file back, which the tests use.
- **D6 Tests use Python's built-in `unittest`**, so no test dependency is added.
- **D7 `outputs/<video_id>/` stays as the working folder during a run** (checkpoints and resume are
  untouched). When the run completes, the files move into the Final Results folder and the working
  folder is removed.
- **D8 The two old summary CSVs are no longer written** (`vehicle_summary.csv`,
  `canonical_summary.csv`); the workbook and `summary.json` carry the same numbers.
- **D9 Tempo traveller counts as Mini Bus.** This is my assumption; it is one line in the mapping if
  Aakar files it elsewhere.
- **D11 A dash is explained wherever it appears.** The By Road sheet has a short legend under the
  table ("- = not yet separated by the software; counted in ..."), and the copied message ends with
  one italic line when buses, trucks, LCVs or autos have counts, e.g.
  `_Private Bus includes Govt. Bus; 2 Axle Truck includes all trucks._` Without it, a reader of the
  message would take "Private Bus: 6" literally. Say so if you want the message without that line.
- **D12 The mapping lives in one new file** and is applied when results are saved, so the counting
  code is untouched and later releases that teach the software to split a group only change that
  file's table.
- **D10 Branch `v1.3.x` from `main`**, with a new `changelog/CHANGELOG-v1.3.x.md`, following the
  repo's rule for a new parent version. Nothing is pushed until you ask.
- **Not in 1.3.0:** actually separating Taxi, Goods Auto, Govt. Bus, Mini LCV, 3 Axle Truck and MAV
  (that is model work: a second classifier or retraining on labelled Aakar footage, with its own
  accuracy testing); Aakar terms in the live preview; redesign of the results page beyond the items
  below; a direct "send to WhatsApp" link; migrating old `outputs/` runs; and the bug where two roads
  with the same name share one count. These are candidates for later 1.3.x releases.

## What the user gets

```
Final Results/
  MG Road cam2 - 2026-11-11 14.30/
    Traffic Count Report.xlsx
    raw data/
      crossings.csv
      detections.csv
      summary.json
```

- Folder name: original video file name (without extension, characters Windows forbids removed) plus
  the finish date and time. A clash gets ` (2)`, ` (3)`...
- **Traffic Count Report.xlsx**
  - *Overview*: video name, processed on, video length, resolution, total vehicles, a table of roads
    with totals, counting method, model, app version.
  - *By Road*: Aakar's 16 categories in Aakar's order, each heading with its YOLO classification in
    brackets, one column per road, plus a Total column and a
    Total row, then the legend for dashes. Bold header, frozen header row, sized columns.
  - *Crossings*: one row per counted vehicle: number, time in video (h:mm:ss), road name, Aakar
    category, the model's own type (for checking), confidence. Frozen header and filter buttons.
- **Copied message** (WhatsApp `*bold*`, `_italic_`, `- ` bullets):

```
*Traffic Count - MG Road cam2*
_11 Nov 2026 - 5 min video_

*Total: 459 vehicles*

*Left - 234*
- Two Wheeler: 96
- Cars/Vans/Jeeps: 70
- 2 Axle Truck: 27
- Auto Rickshaw: 21
- 6/8 seater: 8

*Right - 216*
- Two Wheeler: 81
...

_Auto Rickshaw includes Goods Auto; 2 Axle Truck includes all trucks._
```

  Only categories with a count are listed, largest first; a road with no vehicles shows only its
  heading. Underscores in the video name become spaces in the title so they cannot break the
  formatting.

- **Results page**: heading "Final Results" with the video name and date under it; a primary
  **Copy for WhatsApp** button with a "Copied" toast; sidebar buttons **Excel report**,
  **Open folder**, and the raw **Crossings CSV** / **Summary JSON**. "Video" shows the real name, and
  "Counting Method" shows the method instead of "N/A". Each road's table lists the 16 Aakar
  categories (dashes as in the report); its chart shows only the categories that have a count.

## Changes

### New: `core/aakar_categories.py` (pure logic, written test-first)

- `CATEGORIES`: the 16 names in Aakar's order.
- `_FROM_MODEL`: normalised model label -> category (reuses `taxonomy._normalise` so "Two-wheeler",
  "two_wheeler" and "Two Wheeler" all match). Unknown labels go to Other.
- `COUNTED_IN`: category that has no count of its own -> the row that carries it
  (Taxi -> Cars/Vans/Jeeps, Goods Auto -> Auto Rickshaw, Govt. Bus -> Private Bus, Mini LCV -> LCV,
  3 Axle Truck and MAV -> 2 Axle Truck).
- `to_category(model_label) -> str`
- `heading(category) -> str`: the category plus its YOLO classes in brackets, e.g.
  "Cars/Vans/Jeeps (Hatchback, Sedan, SUV, Van)"; the plain name for a category with no class.
- `count_by_category(by_type: dict) -> dict`: all 16 keys; a number, or `None` for a dash.
- `notes_for(counts) -> list[str]`: the "X includes Y" lines for rows that have a count.

### New: `core/final_results.py` (pure logic, written test-first)

- `safe_folder_name(video_filename, finished_at) -> str`
- `unique_dir(parent, name) -> Path`
- `format_video_length(seconds) -> str` ("5 min", "1 h 2 min")
- `build_share_text(summary) -> str`: uses each road's `by_category` and `notes_for`.
- `write_report(path, summary, crossings_rows, road_labels)`: the three sheets, with `openpyxl`.
  Row order from `aakar_categories.CATEGORIES`; road names from `road_labels[line_zone_index]`.
- `publish(work_dir, summary, road_labels, final_root) -> Path`: creates the folder, writes the
  report, moves `crossings_*.csv` -> `raw data/crossings.csv` and `vehicle_counts_*.csv` ->
  `raw data/detections.csv`, writes `raw data/summary.json`, removes the empty working folder.

### `core/paths.py`

- Add `FINAL_RESULTS_DIR = PROJECT_ROOT / "Final Results"`.

### `server.py`

- `_run_processing` (lines 758-788): extend the envelope with `video_id`, `video_name` (original file
  stem from `video_store[video_id]["filename"]`), `processed_at`, `duration_seconds`,
  `counting_method`, `app_version` (`get_latest_version()`), `results_folder` and `share_text`; add
  `category_counts` overall, `category_headings` (name -> bracketed heading, so the page does not
  repeat the mapping) and `by_category` to each road (from `count_by_category`, alongside the
  existing `by_type`, which stays); call
  `final_results.publish(...)`; stop calling `_write_native_summary` / `_write_canonical_summary`.
  Record `video_id -> folder` in a module-level dict.
- `_final_dir(video_id)`: the dict first, then a scan of `Final Results/*/raw data/summary.json` for
  a matching `video_id`, so results still load after a server restart.
- `GET /api/results/{video_id}`: read from `_final_dir`.
- `GET /api/download/{video_id}/{kind}`: `kind` is one of `report`, `crossings`, `detections`,
  `summary`, mapped to fixed file names. This replaces the free-form filename, which closes the path
  traversal hole and fixes the Crossings download that only worked by accident on Windows.
- `POST /api/open-folder/{video_id}`: opens the run's folder in the file manager on the machine the
  server runs on (`os.startfile` on Windows, `open` / `xdg-open` elsewhere). Only ever opens the
  resolved Final Results folder for that id.

### `interface/results/` (`index.html`, `js/app.js`, `css/results.css`)

- Heading, subtitle, Copy button and toast (toast pattern from
  `interface/processing/js/app.js:60-80` and `processing/css/processing.css:132-160`).
- Copy uses `navigator.clipboard.writeText(results.share_text)`, with a hidden-textarea
  `execCommand('copy')` fallback for when the page is opened over a LAN address, where the clipboard
  API is unavailable.
- Download buttons point at the new `kind` URLs; Open folder calls the new endpoint.
- Escape the road label and video name when inserting them into the page.

### Docs and housekeeping

- `requirements.txt`: add `openpyxl`.
- `.gitignore`: add `Final Results/`.
- `README.md`: rewrite "4. Results" and the "Output Files" table.
- `changelog/CHANGELOG-v1.3.x.md`: `# Parent Update: v1.3`, summary line, `**Branch:** v1.3.x`,
  `## Version Goal` (results that are easy to read and easy to pass on), then `## Unreleased` with
  the bullets for this work. `CLAUDE.md`: point "current parent changelog" at the new file.
- Design doc at `docs/superpowers/specs/2026-11-11-final-results-design.md` (this plan, as the
  record of the decisions), committed first on the new branch.

## Order of work

1. Create branch `v1.3.x`; add the design doc and the new changelog file.
2. Install `openpyxl` in the venv; add it to `requirements.txt`.
3. `tests/test_aakar_categories.py` then `core/aakar_categories.py` (failing test first): every one
   of the model's 14 labels maps to the expected category, unknown labels go to Other, dashes come
   out as `None`, and the category totals add up to the road total.
4. `tests/test_final_results.py` then `core/final_results.py`, one function at a time (failing test
   first): folder naming, clash handling, video length, share text, workbook contents, `publish`.
5. Wire `server.py`.
6. Results page.
7. README, `.gitignore`, changelog bullets.
8. Verify (below). Commits in the repo's style; no push.

## Verification

- `venv\Scripts\python -m unittest discover tests` passes. The share-text test checks the exact
  message for a fixture taken from the real run `outputs/62f33e0ec8c4` (459 total; left 234,
  right 216, center 9; overall Cars/Vans/Jeeps 140, 6/8 seater 12, Two Wheeler 180, Auto Rickshaw 44,
  LCV 25, Private Bus 6, 2 Axle Truck 52). The workbook test reads the file back with `openpyxl` and
  checks sheet names, the 16 category rows in Aakar's order with dashes in the six unsplit rows, the
  By Road totals row, and that Crossings has one row per vehicle with road names, not indexes.
- Run `publish` against a **copy** of `outputs/62f33e0ec8c4` in a scratch folder and open the
  resulting workbook to check the layout.
- Start the server and check with requests: `/api/results/<id>` returns `share_text`; each download
  `kind` returns the right file; `/api/download/<id>/..%5Cserver.py` and an unknown kind are refused.
- For you to check in the browser with a real video (I cannot drive the full run without a video and
  the model weights on this PC):
  1. Run a short video with two named roads to the end.
  2. The results page says "Final Results" with the video's real name and today's date.
  3. Press **Copy for WhatsApp**, paste into a WhatsApp chat: bold headings and bullet lists appear,
     the categories are Aakar's, and the numbers match the page.
  4. **Open folder** shows the named folder; `Traffic Count Report.xlsx` opens in Excel with three
     sheets; `raw data` holds the three raw files.
  5. Stop a run partway and resume it: it still finishes and produces the folder.
