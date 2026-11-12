# Parent Update: v1.3

Results that are easy to read and easy to pass on.

**Branch:** `v1.3.0`

## Version Goal

Until now a finished run left a handful of loose CSV files in a folder named with a random id, in the model's own vocabulary. For this parent update, we want the results to arrive the way Aakar uses them: one clearly named place per video, a report that opens in Excel, Aakar's own vehicle categories, and a quick way to share an overview on the channels people already use, starting with WhatsApp.

---

## v1.3.0

### What's added

- Final Results folder. Every finished run now produces one folder under `Final Results/`, named after the video and the time it finished. It holds `Traffic Count Report.xlsx` and a `raw data` folder with the crossings, the per-frame detections and the run summary.
- Excel report with three sheets: an Overview (video, date, length, totals per road), By Road (every vehicle category against every road, with totals), and Crossings (one row per counted vehicle with its time, road and category).
- Copy for WhatsApp. A button on the results page copies an overview of the run, with a breakdown for each road, formatted so it pastes into a WhatsApp chat with bold headings and bullet lists.
- Aakar's vehicle categories. The report, the copied message and the results page now use Aakar's 16 categories instead of the model's own names, and each category shows the model's classification behind it in brackets. Six categories the model cannot separate yet (Taxi, Goods Auto, Govt. Bus, Mini LCV, 3 Axle Truck, MAV) show a dash, and their vehicles are counted in the neighbouring category named in the note.
- The results page is headed "Final Results" and shows the video's real name and the date it was processed. It has buttons for the Excel report and for opening the results folder.
- The video's original file name, the time of the run, the video length and the app version are saved with the results.
- The Excel report needs one new package. Run `setup.bat` (or `setup.sh`) once after updating. Without it a run still finishes and keeps its raw data, and the results page says the report could not be written.

### Fixed

- "Counting Method" on the results page always showed "N/A".
- The Crossings CSV download only worked by accident on Windows, and a crafted download link could reach files outside the results folder. Downloads are now limited to a fixed list of result files.

### What's removed

- `vehicle_summary.csv` and `canonical_summary.csv` are no longer written. The Excel report and `summary.json` carry the same numbers.

---
