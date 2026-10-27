"""Run real DemoSafe inference on isolated, independently rendered truth.

The app is passed the media and a keyword list only. Ground truth is read by
this evaluator after the media path is resolved, never by application code.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def intersection_fraction(box, truth_box):
    x1, y1, x2, y2 = map(float, box)
    a, b, c, d = map(float, truth_box)
    area = max(0.0, c - a) * max(0.0, d - b)
    if area == 0:
        return 0.0
    return max(0.0, min(x2, c) - max(x1, a)) * max(0.0, min(y2, d) - max(y1, b)) / area


def score_detections(truth, analysis):
    """One-to-one event matching, plus per-frame detection to expose brief misses."""
    frames = {int(frame["index"]): frame.get("detections", []) for frame in analysis.frames}
    candidates = defaultdict(int)
    matched_occurrences = 0
    total_occurrences = 0
    for expected in truth["events"]:
        for occurrence in expected["frames"]:
            total_occurrences += 1
            matched_this_frame = False
            for detection in frames.get(occurrence["index"], []):
                if detection["type"] != expected["type"]:
                    continue
                if intersection_fraction(detection["box"], occurrence["box"]) >= 0.5:
                    event_id = detection.get("event_id")
                    if event_id is not None:
                        candidates[(expected["id"], str(event_id))] += 1
                    matched_this_frame = True
            matched_occurrences += int(matched_this_frame)
    matched_truth, matched_predictions, pairs = set(), set(), []
    for (truth_id, predicted_id), frame_count in sorted(candidates.items(), key=lambda item: (-item[1], item[0])):
        if truth_id not in matched_truth and predicted_id not in matched_predictions:
            matched_truth.add(truth_id)
            matched_predictions.add(predicted_id)
            pairs.append({"truth_event": truth_id, "prediction_event": predicted_id, "matching_frames": frame_count})
    predicted_ids = {str(event["id"]) for event in analysis.events}
    expected_count = len(truth["events"])
    return {
        "expected_events": expected_count,
        "detected_events": len(matched_truth),
        "missed_events": [{"id": event["id"], "type": event["type"], "exposure_seconds": event["end"] - event["start"]} for event in truth["events"] if event["id"] not in matched_truth],
        "predicted_events": len(predicted_ids),
        "false_positive_events": len(predicted_ids - matched_predictions),
        "false_positive_ids": sorted(predicted_ids - matched_predictions),
        "event_recall": len(matched_truth) / expected_count if expected_count else None,
        "expected_sensitive_frame_occurrences": total_occurrences,
        "detected_sensitive_frame_occurrences": matched_occurrences,
        "sensitive_frame_recall": matched_occurrences / total_occurrences if total_occurrences else None,
        "matches": pairs,
    }


def solid_black_fraction(frame, box, tolerance=16):
    x1, y1, x2, y2 = map(int, box)
    h, w = frame.shape[:2]
    if x1 < 0 or y1 < 0 or x2 > w or y2 > h or x2 <= x1 or y2 <= y1:
        return 0.0
    crop = frame[y1:y2, x1:x2]
    return float(np.mean(np.max(crop, axis=2) <= tolerance))


def score_mask_coverage(truth, output_path, threshold=0.995):
    """Read the exported pixels, independently of detected/masked box metadata."""
    expected_by_frame = defaultdict(list)
    for event in truth["events"]:
        for item in event["frames"]:
            expected_by_frame[item["index"]].append((event["id"], item["box"]))
    cap = cv2.VideoCapture(str(output_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot decode export {output_path}")
    fractions = defaultdict(list)
    uncovered = []
    frame_index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            for event_id, box in expected_by_frame.get(frame_index, []):
                coverage = solid_black_fraction(frame, box)
                fractions[event_id].append(coverage)
                if coverage < threshold:
                    uncovered.append({"event_id": event_id, "frame": frame_index, "black_fraction": round(coverage, 6)})
            frame_index += 1
    finally:
        cap.release()
    for index, occurrences in expected_by_frame.items():
        if index >= frame_index:
            for event_id, _ in occurrences:
                fractions[event_id].append(0.0)
                uncovered.append({"event_id": event_id, "frame": index, "black_fraction": 0.0, "reason": "output_frame_missing"})
    all_fractions = [v for values in fractions.values() for v in values]
    fully_masked = sum(bool(fractions[event["id"]]) and min(fractions[event["id"]]) >= threshold for event in truth["events"])
    return {
        "solid_mask_color": "RGB(0,0,0)", "codec_tolerance_per_channel": 16, "required_black_fraction": threshold,
        "output_frames": frame_index, "expected_frames": truth["frame_count"], "frame_count_matches": frame_index == truth["frame_count"],
        "checked_sensitive_frame_occurrences": len(all_fractions),
        "fully_masked_frame_occurrences": sum(v >= threshold for v in all_fractions),
        "fully_masked_events": fully_masked, "expected_events": len(truth["events"]),
        "minimum_black_fraction": min(all_fractions) if all_fractions else None,
        "mean_black_fraction": sum(all_fractions) / len(all_fractions) if all_fractions else None,
        "uncovered_occurrences": uncovered,
    }


def aggregate(results):
    detection = [row["detection"] for row in results if row.get("detection")]
    expected = sum(row["expected_events"] for row in detection)
    detected = sum(row["detected_events"] for row in detection)
    occurrences = sum(row["expected_sensitive_frame_occurrences"] for row in detection)
    detected_occurrences = sum(row["detected_sensitive_frame_occurrences"] for row in detection)
    coverages = [row["mask_coverage"] for row in results if row.get("mask_coverage")]
    checked = sum(row["checked_sensitive_frame_occurrences"] for row in coverages)
    fully_masked = sum(row["fully_masked_frame_occurrences"] for row in coverages)
    clean_results = [row for row in detection if row["expected_events"] == 0]
    return {
        "completed_samples": len(detection), "failed_samples": sum("error" in row for row in results),
        "expected_events": expected, "detected_events": detected, "event_recall": detected / expected if expected else None,
        "false_positive_events": sum(row["false_positive_events"] for row in detection),
        "negative_samples": len(clean_results), "negative_samples_with_false_positives": sum(row["false_positive_events"] > 0 for row in clean_results),
        "sensitive_frame_recall": detected_occurrences / occurrences if occurrences else None,
        "checked_sensitive_frame_occurrences": checked, "fully_masked_frame_occurrences": fully_masked,
        "full_mask_frame_fraction": fully_masked / checked if checked else None,
        "fully_masked_events": sum(row["fully_masked_events"] for row in coverages),
        "mask_checked_events": sum(row["expected_events"] for row in coverages),
        "all_export_frame_counts_match": all(row["frame_count_matches"] for row in coverages) if coverages else None,
        "analysis_wall_seconds": sum(row.get("analysis_wall_seconds", 0) for row in results),
        "export_wall_seconds": sum(row.get("export_wall_seconds", 0) for row in results),
    }


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def save_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    report["summary"] = aggregate(report["samples"])
    report["updated_at"] = utc_now()
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def run(args):
    from app.pipeline import analyze_media, export_media
    truth_root = args.data / "benchmark_truth"
    truth_files = []
    for path in sorted(truth_root.glob("*.json")):
        truth = json.loads(path.read_text(encoding="utf-8"))
        if truth.get("split") == args.split or args.split == "all" and truth.get("split") in ("dev", "heldout"):
            truth_files.append((path, truth))
    if args.limit is not None:
        truth_files = truth_files[:args.limit]
    if not truth_files:
        raise RuntimeError("No fixtures found. Run scripts/generate_samples.py first.")
    output = args.output or ROOT / "reports" / f"benchmark_{args.split}.json"
    report = {
        "schema": 1, "started_at": utc_now(), "status": "running", "split": args.split,
        "planned_samples": len(truth_files), "exports_checked": not args.skip_export,
        "matching_policy": "One-to-one predicted/truth event matching by type and >=50% truth-box intersection on any truth frame. Separate per-frame recall and independent >=99.5% black-mask coverage detect partial duration/box failures.",
        "data_limitations": "Self-authored English synthetic recordings; fixed layouts; high-contrast 23-28px text; 720p10fps lossless encoded video with repeated static frames. Throughput is not representative of changing/lossy real recordings. No market validation is implied.",
        "heldout_policy": "Templates split before inference. This evaluator does not optimize thresholds or modify models. Report misses, do not tune on held-out results.",
        "source_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): file_hash(p) for p in sorted((ROOT / "app").glob("*.py"))},
        "samples": [],
    }
    save_report(output, report)
    for index, (_, truth) in enumerate(truth_files):
        row = {"id": truth["id"], "split": truth["split"], "template": truth["template"], "scenario": truth.get("scenario", "demo"), "source_sha256": truth["sha256"]}
        try:
            media = args.data / "samples" / truth["media"]
            if file_hash(media) != truth["sha256"]:
                raise RuntimeError("Fixture content differs from frozen truth manifest")
            started = time.perf_counter()
            analysis = analyze_media(media, keywords=truth.get("keywords", []))
            row["analysis_wall_seconds"] = round(time.perf_counter() - started, 4)
            row["runtime_metrics"] = analysis.metrics
            row["detection"] = score_detections(truth, analysis)
            if not args.skip_export:
                target = args.data / "benchmark_outputs" / f"{truth['id']}_redacted.mp4"
                target.parent.mkdir(parents=True, exist_ok=True)
                started = time.perf_counter()
                export_report = export_media(media, target, analysis, decisions={str(event["id"]): True for event in analysis.events}, manual_masks=[])
                row["export_wall_seconds"] = round(time.perf_counter() - started, 4)
                row["mask_coverage"] = score_mask_coverage(truth, target)
                row["output_sha256"] = file_hash(target)
                # The application's report is deliberately not used as benchmark truth.
                row["application_verification"] = export_report
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        report["samples"].append(row)
        save_report(output, report)
        metric = row.get("detection", {})
        print(f"[{index + 1}/{len(truth_files)}] {truth['id']} recall={metric.get('detected_events', 0)}/{metric.get('expected_events', 0)} fp={metric.get('false_positive_events', '?')} {row.get('error', '')}", flush=True)
    report["status"] = "completed_with_errors" if any("error" in row for row in report["samples"]) else "completed"
    report["finished_at"] = utc_now()
    save_report(output, report)
    print(json.dumps(report["summary"], indent=2))
    print(f"Report: {output}")
    return 1 if report["status"] != "completed" else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--split", choices=("dev", "heldout", "all", "demo"), default="dev")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--skip-export", action="store_true", help="Detection-only run; cannot support masking claims")
    parser.add_argument("--output", type=Path)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
