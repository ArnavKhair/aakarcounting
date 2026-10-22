# Parent Update: v1.2

Making existing CCTV footage compatible with the counting software, alongside accuracy improvements there may be on the table.

**Branch:** `v1.2.x`

## Version Goal

Aakar exports their 24hr CCTV footage into 1 hour chunks. For this parent update, we want to use their existing video exporting tools. Eventually, we want to upload the raw CCTV footage into this software directly. With previous updates, there have been improvements in accuracy and reliability of the software. We now want to ensure that the results received on our machines are the same for Aakar.

---

## v1.2.1

### What's added

- Support for 1-hour long videos
  - The live preview is throttled to 2fps and queued, so a browser that falls behind drops preview frames instead of slowing the counting down.
  - The per-detection log is written as it is produced rather than held in memory, and a resumed run appends to it.
  - A browser-playable preview is made in the background at 480p instead of before the upload returns.
- Version number on the upload screen to ensure updates are installed correctly. It is read from the highest version heading in `changelog/`, so it cannot drift from the code.
- Pause and resume. A paused run holds its position with the model loaded and writes a checkpoint, so resuming continues from the same frame.
- Crash-safe checkpoints. State is written to a temp file and renamed into place, with the previous checkpoint kept as a `.bak`, so a kill partway through a write cannot leave a checkpoint that cannot be read.
- A checkpoint records the total frame count and a fingerprint of the video, frame rate and counting lines, so a resume against different settings is refused rather than reporting numbers that look valid and are not.
- "Start Fresh" on the upload screen now actually deletes the checkpoint it is meant to discard.

### Fixed

- A stopped run deleted its own checkpoint, so there was never anything to resume from.
- A resumed run reused the tracker ids from the checkpoint. A new vehicle could be issued an old id, its observations merged into the old vehicle's record, and its crossing discarded as already counted -- the run reported fewer vehicles than it saw, with nothing to indicate it. The tracker's id counter is now reserved above the checkpointed range.
- A reconnect started a second run for a video that was already being processed. Two threads raced to write the same checkpoint, and the one shutting down wrote a checkpoint from further along the video than the live one. The server now stops the previous run and waits for it, and a reconnect continues from the latest checkpoint rather than starting over.
- A seek to a frame in a compressed video lands on the nearest keyframe, not the frame asked for, so the frame counter and the decoder could disagree and every timestamp after the seek was wrong. The position is read back and the counter follows it.
- The stop button carried the pause icon, which read as the wrong action. Stop now uses a circle with a minus, and the pause icon moved to a Pause button beside it.

### Not included

- PR Request: vehicle heatmap overlay during the line drawing screen. The PR added `tools/motion_heatmap.py`, a standalone tool that reports where the movement is in a clip so a counting line can be placed on evidence. It is not wired into the line drawing screen, so the overlay is not there yet.

### What's removed

- None

### Goals for next version

- Test these changes and make any iterations needed
