"""Measured, resumable robustness evaluation; truth never enters the app.

The 1 Hz comparison replays frozen per-frame observations at all 15 phases.
It is a detection/eligible-work ablation, not a separate speed benchmark.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
from types import SimpleNamespace

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.benchmark import aggregate, score_detections, score_mask_coverage
from scripts.generate_robustness_v2 import DATA, digest, verify, write_json


def source_hashes():
    return {str(path.relative_to(ROOT)).replace("\\", "/"): digest(path) for path in sorted((ROOT / "app").glob("*.py"))}


def frame_hashes(path):
    capture = cv2.VideoCapture(str(path))
    values = []
    try:
        if not capture.isOpened():
            raise RuntimeError("Cannot decode clip for replay hashes")
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            values.append(hashlib.sha256(frame.tobytes()).hexdigest())
    finally:
        capture.release()
    return values


def eligible_ocr_calls(hashes, capacity=128):
    cache, calls = OrderedDict(), 0
    for value in hashes:
        if value in cache:
            cache.move_to_end(value)
        else:
            calls += 1
            cache[value] = None
            if len(cache) > capacity:
                cache.popitem(last=False)
    return calls


def replay_ablation(truth, analysis, hashes, fps=15):
    if len(hashes) != truth["frame_count"]:
        raise ValueError("Decoded hash count differs from truth")
    phases = []
    for phase in range(fps):
        sampled = [row for row in analysis.frames if row["index"] % fps == phase]
        ids = {str(item["event_id"]) for row in sampled for item in row.get("detections", [])}
        observations = SimpleNamespace(frames=sampled, events=[{"id": item} for item in sorted(ids)])
        score = score_detections(truth, observations)
        phases.append({"phase_frames": phase, "phase_seconds": phase/fps,
                       "sampled_frames": len(sampled), "eligible_ocr_calls": eligible_ocr_calls(hashes[phase::fps]),
                       "detected_events": score["detected_events"], "expected_events": score["expected_events"],
                       "event_recall": score["event_recall"]})
    recalls = [row["event_recall"] for row in phases if row["event_recall"] is not None]
    return {"method": "Replay unchanged per-frame observations at every 1 Hz phase; original temporal track IDs retained only to match events. No separate product implementation or speedup measurement.",
            "cache_model": "Exact decoded-pixel SHA-256 LRU, capacity 128, empty at clip start; call counts are eligible work, not timings.",
            "all_frame_eligible_ocr_calls": eligible_ocr_calls(hashes),
            "all_frame_decoded_frames": len(hashes), "phases": phases,
            "phase_recall_mean": statistics.mean(recalls) if recalls else None,
            "phase_recall_min": min(recalls) if recalls else None,
            "phase_recall_max": max(recalls) if recalls else None}


def selected_geometry_truth(analysis):
    """Check chosen geometry separately; it is not detector ground truth."""
    events = {}
    for frame in analysis.frames:
        for item in frame.get("detections", []):
            key = str(item["event_id"])
            events.setdefault(key, {"id": key, "type": item["type"], "frames": []})["frames"].append({"index": frame["index"], "box": item["box"]})
    return {"frame_count": analysis.metadata["frame_count"], "events": list(events.values())}


def summarize(rows):
    summary = aggregate(rows)
    summary["by_condition"] = {condition: aggregate([row for row in rows if row["condition"] == condition]) for condition in "ABC"}
    summary["by_layout"] = {layout: aggregate([row for row in rows if row["layout"] == layout]) for layout in sorted({row["layout"] for row in rows})}
    summary["all_original_hashes_unchanged"] = all(row.get("original_unchanged") is True for row in rows) if rows else None
    selected = [row["selected_mask_geometry"] for row in rows if "selected_mask_geometry" in row]
    summary["selected_mask_geometry"] = {
        "checked_frame_regions": sum(row["checked_sensitive_frame_occurrences"] for row in selected),
        "fully_masked_frame_regions": sum(row["fully_masked_frame_occurrences"] for row in selected),
        "meaning": "Selected detection boxes only; independent annotation coverage above still counts missed/partial detections."}
    completed = [row for row in rows if "ablation_1hz" in row]
    phases = []
    for phase in range(15):
        observations = [row["ablation_1hz"]["phases"][phase] for row in completed]
        expected = sum(row["expected_events"] for row in observations)
        detected = sum(row["detected_events"] for row in observations)
        phases.append({"phase_frames": phase, "expected_events": expected, "detected_events": detected,
                       "event_recall": detected/expected if expected else None,
                       "eligible_ocr_calls": sum(row["eligible_ocr_calls"] for row in observations)})
    recalls = [row["event_recall"] for row in phases if row["event_recall"] is not None]
    summary["ablation_1hz"] = {"phases": phases,
        "phase_recall_mean": statistics.mean(recalls) if recalls else None,
        "phase_recall_min": min(recalls) if recalls else None, "phase_recall_max": max(recalls) if recalls else None,
        "all_frame_eligible_ocr_calls": sum(row["ablation_1hz"]["all_frame_eligible_ocr_calls"] for row in completed),
        "claim_limit": "Sampling replay and eligible-call counts only. No human-efficiency or wall-time speedup claim."}
    return summary


def save(path, report):
    report["summary"] = summarize(report["samples"])
    report["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(path, report)


def run(args):
    manifest = verify()
    if args.split == "heldout" and not args.freeze_note:
        raise RuntimeError("Heldout requires root freeze authorization recorded with --freeze-note.")
    path = ROOT / "reports" / f"benchmark_robustness_v2_{args.split}.json"
    selected = [item for item in manifest["clips"] if item["split"] == args.split]
    if path.exists():
        if not args.resume:
            raise RuntimeError("Report exists; refusing overwrite. --resume skips completed samples without changing evidence.")
        report = json.loads(path.read_text(encoding="utf-8"))
        if report["manifest_sha256"] != digest(DATA / "manifest.json"):
            raise RuntimeError("Cannot resume against changed fixtures")
        core = {"app/media.py", "app/ocr.py", "app/detectors.py", "app/pipeline.py"}
        current = source_hashes()
        if any(report["source_sha256"][key] != current[key] for key in core):
            raise RuntimeError("Cannot resume after inference source changed")
    else:
        report = {"schema": 2, "split": args.split, "status": "running", "planned_samples": len(selected),
                  "started_at": datetime.now(timezone.utc).isoformat(), "manifest_sha256": digest(DATA / "manifest.json"),
                  "dataset_frozen_at": manifest["frozen_at"], "source_sha256": source_hashes(),
                  "evaluator_sha256": digest(__file__), "freeze_note": args.freeze_note,
                  "data_limitations": manifest["limitations"],
                  "event_matching": "One-to-one type plus >=50% truth box coverage on at least one expected frame. Per-frame recall and independent pixel coverage report partial misses.",
                  "mask_coverage": ">=99.5% of each annotated region, every RGB channel <=16, on every annotated frame. Original missed regions remain in denominator.",
                  "samples": []}
    save(path, report)
    from app.pipeline import analyze_media, export_media
    processed = {row["id"] for row in report["samples"]}
    for item in selected:
        if item["id"] in processed:
            continue
        row = {key: item[key] for key in ("id", "layout", "condition", "positive", "split")}
        media = DATA / item["media"]
        try:
            if digest(media) != item["media_sha256"] or digest(DATA / item["truth"]) != item["truth_sha256"]:
                raise RuntimeError("Frozen source or truth differs")
            # Keyword is caller configuration, not annotation-driven: every positive and negative gets the same list.
            started = time.perf_counter()
            analysis = analyze_media(media, keywords=["CEDAR INTERNAL"])
            row["analysis_wall_seconds"] = round(time.perf_counter()-started, 4)
            row["runtime_metrics"] = analysis.metrics
            # Read expected regions only after inference has finished.
            truth = json.loads((DATA / item["truth"]).read_text(encoding="utf-8"))
            row["detection"] = score_detections(truth, analysis)
            row["ablation_1hz"] = replay_ablation(truth, analysis, frame_hashes(media))
            observations = {"frames": [{"index": frame["index"], "detections": [{key: detection[key] for key in ("type", "box", "event_id")} for detection in frame["detections"]]} for frame in analysis.frames],
                            "events": [{key: event[key] for key in ("id", "type", "start", "end", "box")} for event in analysis.events]}
            observed_path = DATA / "observations" / f"{item['id']}.json"
            write_json(observed_path, observations)
            row["observations_sha256"] = digest(observed_path)
            output = DATA / "outputs" / f"{item['id']}_redacted.mp4"
            output.parent.mkdir(parents=True, exist_ok=True)
            started = time.perf_counter()
            application_report = export_media(media, output, analysis,
                decisions={str(event["id"]): True for event in analysis.events}, manual_masks=[])
            row["export_wall_seconds"] = round(time.perf_counter()-started, 4)
            row["mask_coverage"] = score_mask_coverage(truth, output)
            row["selected_mask_geometry"] = score_mask_coverage(selected_geometry_truth(analysis), output)
            row["application_verification"] = application_report
            row["output_sha256"] = digest(output)
            row["source_sha256"] = item["media_sha256"]
            row["original_unchanged"] = digest(media) == item["media_sha256"]
            if not row["original_unchanged"]:
                raise RuntimeError("Source changed during inference/export")
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        report["samples"].append(row)
        save(path, report)
        score = row.get("detection", {})
        print(f"[{len(report['samples'])}/{len(selected)}] {row['id']} events={score.get('detected_events','?')}/{score.get('expected_events','?')} fp={score.get('false_positive_events','?')} analysis={row.get('analysis_wall_seconds','?')}s export={row.get('export_wall_seconds','?')}s {row.get('error','')}", flush=True)
    report["status"] = "completed_with_errors" if any("error" in row for row in report["samples"]) else "completed"
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["source_sha256_after"] = source_hashes()
    report["inference_core_unchanged"] = all(report["source_sha256"][key] == report["source_sha256_after"][key] for key in ("app/media.py", "app/ocr.py", "app/detectors.py", "app/pipeline.py"))
    verify()
    save(path, report)
    print(json.dumps(report["summary"], indent=2), flush=True)
    return 0 if report["status"] == "completed" and report["inference_core_unchanged"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "heldout"), default="dev")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--freeze-note", default="")
    raise SystemExit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
