# Accuracy Baseline – September 20 Update

**Date:** September 20, 2026  
**Branch:** `sept20-accuracy-baseline`

## Summary

This update tightens the vehicle counting pipeline to reduce false positives from fragmented tracks and flickering detections. The goal is to establish an accuracy baseline that closely matches manual ground-truth counts.

---

## Configuration Changes (`core/config.py`)

### 1. `MIN_TRACK_FRAMES_TO_COUNT`: `1` → `3`

A vehicle must now be tracked for at least 3 frames before its crossing is counted. This replaces the older `MINIMUM_CONSECUTIVE_FRAMES` approach and acts as a lightweight false-positive filter — rejecting brief flicker without making real vehicles invisible to the tracker.

### 2. New: `MIN_MEAN_CONFIDENCE_TO_COUNT = 0.60`

A new threshold requiring that a vehicle's **mean detection confidence** across its entire track life exceeds 0.60. This targets fragmented tracks caused by ID churn (occlusion → tracker loses vehicle → re-detects with new ID), which tend to have lower average confidence than unbroken tracks.

**Ground-truth validation:** On the Ahmedabad junction clip, this threshold reduced 616 raw crossings to 461 — within 4 of the manual count of 465.

---

## Processor Changes (`core/processor.py`)

### 1. Crossing Deduplication

Added a `counted_crossings` set that tracks `(tracker_id, line_zone_index)` tuples. Before recording a crossing event, the system now checks whether that vehicle-line combination has already been counted. This prevents the same vehicle from being double-counted at the same line.

### 2. Mean Confidence Filter in `_summarise()`

The summarisation function now checks `record.mean_confidence` against `MIN_MEAN_CONFIDENCE_TO_COUNT`. Tracks falling below the threshold are rejected and added to the `rejected` count, keeping them out of the final tally.

---

## Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| Raw crossings (ground-truth clip) | 616 | 461 |
| Manual ground truth | 465 | 465 |
| Off by | +151 | -4 |

These changes prioritise **precision** (fewer false positives) with minimal impact on recall for clearly tracked vehicles.
