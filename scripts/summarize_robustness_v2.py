"""Produce a concise evidence readout without modifying frozen measurements."""
import json
from collections import Counter
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DATA = ROOT / "data" / "robustness_v2"
CORE = ("app/media.py", "app/ocr.py", "app/detectors.py", "app/pipeline.py")


def percent(value):
    return "n/a" if value is None else f"{100*value:.2f}%"


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_integrity(report, planned, manifest_matches, core_matches_current):
    """Completeness gate, deliberately separate from detector quality.

    `planned` contains this split's frozen IDs, frame/event/region counts only.
    Unknown fields are failures of evidence completeness, not successful checks.
    """
    rows = report.get("samples", [])
    counts = Counter(row.get("id") for row in rows)
    ids = set(counts)
    duplicate_ids = sorted(str(key) for key, count in counts.items() if count != 1)
    unexpected_ids = sorted(str(key) for key in ids - set(planned))
    missing_ids = sorted(set(planned) - ids)
    split_mismatches, errors, unknown, frame_failures, geometry_failures = [], [], [], [], []
    source_failures, denominator_failures, phase_failures = [], [], []
    scored_detection, fully_evaluated, scored_regions, selected_na = 0, 0, 0, 0
    for row in rows:
        name = row.get("id")
        if name not in planned or counts[name] != 1:
            continue
        expected = planned[name]
        if row.get("split") != report.get("split"):
            split_mismatches.append(name)
        if row.get("error"):
            errors.append(name)
        det = row.get("detection")
        coverage = row.get("mask_coverage")
        selected = row.get("selected_mask_geometry")
        required = ("detection", "mask_coverage", "selected_mask_geometry", "original_unchanged", "ablation_1hz")
        missing = [key for key in required if key not in row or row[key] is None]
        if missing:
            unknown.append({"id": name, "fields": missing})
        det_complete = isinstance(det, dict) and det.get("expected_events") == expected["events"] and det.get("expected_sensitive_frame_occurrences") == expected["regions"]
        if det_complete:
            scored_detection += 1
        else:
            denominator_failures.append({"id": name, "check": "detection denominator"})
        coverage_complete = isinstance(coverage, dict) and coverage.get("checked_sensitive_frame_occurrences") == expected["regions"]
        if coverage_complete:
            scored_regions += expected["regions"]
        else:
            denominator_failures.append({"id": name, "check": "independent mask-region denominator"})
        for label, value in (("independent", coverage), ("selected", selected)):
            if not isinstance(value, dict) or value.get("frame_count_matches") is not True or value.get("output_frames") != expected["frames"] or value.get("expected_frames") != expected["frames"]:
                frame_failures.append({"id": name, "check": label})
        selected_complete = isinstance(selected, dict) and all(key in selected for key in ("checked_sensitive_frame_occurrences", "fully_masked_frame_occurrences", "uncovered_occurrences", "expected_events"))
        selected_ok = selected_complete and selected["fully_masked_frame_occurrences"] == selected["checked_sensitive_frame_occurrences"] and selected["uncovered_occurrences"] == []
        # 0/0 is N/A only when inference really had no detections; it is not an automatic pass for a lost selected-mask check.
        if selected_complete and selected["checked_sensitive_frame_occurrences"] == 0:
            no_detections = isinstance(det, dict) and det.get("predicted_events") == 0 and selected.get("expected_events") == 0
            if no_detections:
                selected_na += 1
            else:
                selected_ok = False
        if not selected_ok:
            geometry_failures.append(name)
        if row.get("original_unchanged") is not True:
            source_failures.append(name)
        phases = (row.get("ablation_1hz") or {}).get("phases", [])
        phases_complete = len(phases) == 15 and {phase.get("phase_frames") for phase in phases} == set(range(15)) and all(phase.get("expected_events") == expected["events"] for phase in phases)
        if not phases_complete:
            phase_failures.append(name)
        if not row.get("error") and not missing and det_complete and coverage_complete and selected_complete and phases_complete:
            fully_evaluated += 1
    planned_regions = sum(value["regions"] for value in planned.values())
    ready = (report.get("status") == "completed" and len(rows) == len(planned) and
             fully_evaluated == len(planned) and not any((duplicate_ids, unexpected_ids, missing_ids, split_mismatches,
             errors, unknown, frame_failures, geometry_failures, source_failures, denominator_failures, phase_failures)) and
             manifest_matches is True and core_matches_current is True and report.get("inference_core_unchanged") is True)
    return {"headline_ready": ready,
        "meaning": "Ready means complete, consistent measurements and correctly applied chosen masks. It does not mean high detection accuracy or complete privacy protection.",
        "planned_clips": len(planned), "detection_scored_clips": scored_detection, "fully_evaluated_clips": fully_evaluated,
        "planned_truth_regions": planned_regions, "independently_scored_truth_regions": scored_regions,
        "unscored_truth_regions": planned_regions-scored_regions,
        "unscored_policy": "A clip with a mismatched/missing coverage denominator contributes none of its planned regions to scored; no denominator substitution across clips.",
        "selected_geometry_not_applicable_clips": selected_na,
        "duplicate_ids": duplicate_ids, "unexpected_ids": unexpected_ids, "missing_ids": missing_ids,
        "split_mismatches": split_mismatches, "processing_errors": errors, "unknown_checks": unknown,
        "frame_count_failures": frame_failures, "selected_geometry_failures": geometry_failures,
        "source_preservation_failures": source_failures, "denominator_failures": denominator_failures,
        "phase_replay_failures": phase_failures, "manifest_matches": manifest_matches,
        "inference_core_matches_current": core_matches_current,
        "inference_core_unchanged_during_run": report.get("inference_core_unchanged")}


def main():
    data = {"schema": 2, "reports": {}, "scope": "Fictional raster-rendered English UI, 24 correlated clips; CPU only; not customer or browser recordings.",
            "original_failure_preserved": "Original dev_019 token miss remains known; same-model output rescan did not catch it.",
            "ablation_limit": "All 15 sampling phases replay identical per-frame observations. Eligible OCR-call counts are work counts, not measured speedup or human time saved."}
    lines = ["# DemoSafe robustness v2 results", "", data["scope"], "", "The frozen method is documented in evaluation_v2_method.md. Pending/running splits are not final claims.", ""]
    manifest_path = DATA / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_hash = file_digest(manifest_path)
    marker_matches = (DATA / "manifest.sha256").read_text(encoding="ascii").strip() == manifest_hash
    for split in ("dev", "heldout"):
        path = REPORTS / f"benchmark_robustness_v2_{split}.json"
        lines += [f"## {split}", ""]
        if not path.exists():
            data["reports"][split] = {"status": "not_run", "headline_ready": False}
            lines += ["Not run. Held-out execution requires the coordinator's source-freeze authorization.", ""]
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        summary = report["summary"]
        # Do not open an unrun split's annotations. Its status stays not_run above.
        planned, frozen_files_match = {}, True
        for item in manifest["clips"]:
            if item["split"] != split:
                continue
            truth_path = DATA / item["truth"]
            truth = json.loads(truth_path.read_text(encoding="utf-8"))
            planned[item["id"]] = {"events": len(truth["events"]), "regions": sum(len(event["frames"]) for event in truth["events"]), "frames": truth["frame_count"]}
            frozen_files_match = frozen_files_match and file_digest(truth_path) == item["truth_sha256"] and file_digest(DATA / item["media"]) == item["media_sha256"]
        integrity = evidence_integrity(report, planned,
            manifest_matches=marker_matches and frozen_files_match and report.get("manifest_sha256") == manifest_hash,
            core_matches_current=all(report.get("source_sha256", {}).get(key) == file_digest(ROOT / key) for key in CORE))
        failures = []
        for row in report["samples"]:
            det, masks = row.get("detection") or {}, row.get("mask_coverage") or {}
            selected = row.get("selected_mask_geometry") or {}
            if (row.get("error") or det.get("missed_events") or det.get("false_positive_events") or masks.get("uncovered_occurrences") or
                masks.get("frame_count_matches") is not True or selected.get("frame_count_matches") is not True or
                "selected_mask_geometry" not in row or selected.get("fully_masked_frame_occurrences") != selected.get("checked_sensitive_frame_occurrences") or
                row.get("original_unchanged") is not True):
                failures.append({"id": row["id"], "error": row.get("error"), "missed_events": det.get("missed_events", []),
                    "false_positive_events": det.get("false_positive_events"),
                    "uncovered_frame_regions": len(masks.get("uncovered_occurrences", [])),
                    "rescan_status": row.get("application_verification", {}).get("rescan", {}).get("status"),
                    "independent_frame_count_matches": masks.get("frame_count_matches"),
                    "selected_frame_count_matches": selected.get("frame_count_matches"),
                    "selected_geometry_present": "selected_mask_geometry" in row,
                    "selected_geometry_complete": bool(selected) and selected.get("fully_masked_frame_occurrences") == selected.get("checked_sensitive_frame_occurrences"),
                    "original_unchanged": row.get("original_unchanged")})
        data["reports"][split] = {"status": report["status"], "path": path.name, "summary": summary,
            "evidence_integrity": integrity, "headline_ready": integrity["headline_ready"],
            "failures": failures, "manifest_sha256": report["manifest_sha256"],
            "inference_core_sha256": {key: report["source_sha256"][key] for key in CORE},
            "inference_core_unchanged": report.get("inference_core_unchanged"),
            "freeze_note": report.get("freeze_note", "")}
        lines += [f"Status: **{report['status']}**, {integrity['fully_evaluated_clips']}/{integrity['planned_clips']} fully evaluated clips. Final-headline gate: **{integrity['headline_ready']}**.", "",
            f"Independent truth-region scoring: {integrity['independently_scored_truth_regions']}/{integrity['planned_truth_regions']}; unscored/unknown: **{integrity['unscored_truth_regions']}**. The gate checks evidence completeness, not high accuracy.", "",
            "| Measurement | Result |", "|---|---:|",
            f"| Detected / expected events | {summary['detected_events']} / {summary['expected_events']} ({percent(summary['event_recall'])}) |",
            f"| False-positive events | {summary['false_positive_events']} |",
            f"| Clean negatives | {summary['negative_samples']-summary['negative_samples_with_false_positives']} / {summary['negative_samples']} |",
            f"| Independently masked annotated frame regions, scored clips only | {summary['fully_masked_frame_occurrences']} / {summary['checked_sensitive_frame_occurrences']} ({percent(summary['full_mask_frame_fraction'])}) |",
            f"| Correctly applied selected mask rectangles | {summary['selected_mask_geometry']['fully_masked_frame_regions']} / {summary['selected_mask_geometry']['checked_frame_regions']} |",
            f"| Analysis wall time, sum of completed clips | {summary['analysis_wall_seconds']:.2f} s |",
            f"| Export plus rescan wall time, sum | {summary['export_wall_seconds']:.2f} s |", "",
            "Selected-mask coverage measures export geometry only; missed sensitive regions remain in the independent annotation denominator.", ""]
        ablation = summary["ablation_1hz"]
        lines += [f"1 Hz phase replay event recall: mean {percent(ablation['phase_recall_mean'])}, range {percent(ablation['phase_recall_min'])}–{percent(ablation['phase_recall_max'])} across 15 phases.", "",
                  "| Condition | Events | Annotated frame regions fully masked | False-positive events |", "|---|---:|---:|---:|"]
        for condition, values in summary["by_condition"].items():
            lines.append(f"| {condition} | {values['detected_events']}/{values['expected_events']} | {values['fully_masked_frame_occurrences']}/{values['checked_sensitive_frame_occurrences']} | {values['false_positive_events']} |")
        lines += ["", "Failures and residual exposure:", ""]
        if not failures:
            lines += ["No failures recorded in the completed samples; this is limited to this small fixture set.", ""]
        for fail in failures:
            missed = ", ".join(event["id"] for event in fail["missed_events"]) or "none wholly missed"
            lines.append(f"- {fail['id']}: missed events {missed}; {fail['uncovered_frame_regions']} uncovered annotated frame regions; {fail['false_positive_events']} false-positive events; same-model rescan={fail['rescan_status']}." + (f" Error: {fail['error']}" if fail['error'] else ""))
        if not integrity["headline_ready"]:
            lines += ["", "Final claims are blocked until all planned clips and required checks are complete. Inspect `evidence_integrity` in the JSON for missing IDs, unknown checks, denominator, source, frame-count or selected-geometry failures."]
        lines.append("")
    lines += ["## Interpretation limits", "", data["original_failure_preserved"], "", data["ablation_limit"], "",
        "Conditions jointly vary font/compression, and C also varies contrast/motion. Paired variants are correlated. Unmatched prediction tracks count as false-positive events and can include fragmentation duplicates; this is not necessarily spurious text. Matching uses intersection divided by truth area, not IoU. Do not describe these findings as universal accuracy, customer validation, a privacy guarantee, real-time capability, or UGen300 acceleration.", "",
        "The source package includes the input media, fixture truth, manifests, notices and reports needed to reproduce the checks. Per-clip observations, exported benchmark media and visual previews are retained locally and can be regenerated; the source ZIP intentionally excludes these derived artifacts. Reports do not discard misses or replace old benchmark evidence.", ""]
    (REPORTS / "evaluation_v2_results.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (REPORTS / "evaluation_v2_results.md").write_text("\n".join(lines), encoding="utf-8")
    print({split: item["status"] for split, item in data["reports"].items()})


if __name__ == "__main__":
    main()
