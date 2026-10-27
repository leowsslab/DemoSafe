"""Test the new evaluator's independence and phase sensitivity."""
from types import SimpleNamespace
from copy import deepcopy

import pytest

from scripts.benchmark_robustness_v2 import eligible_ocr_calls, replay_ablation, selected_geometry_truth, summarize
from scripts.generate_robustness_v2 import CONDITIONS, EXPOSURES, LAYOUTS, contrast_ratio, palette, render
from scripts.summarize_robustness_v2 import evidence_integrity


def trace():
    frames = [{"index": i, "detections": [{"type": "email", "box": [10, 10, 40, 25], "event_id": "p1"}] if i in (18, 19, 20) else []} for i in range(120)]
    analysis = SimpleNamespace(frames=frames, events=[{"id": "p1"}], metadata={"frame_count": 120})
    truth = {"frame_count": 120, "events": [{"id": "t1", "type": "email", "start": 18/15, "end": 21/15,
             "frames": [{"index": i, "box": [10, 10, 40, 25]} for i in (18, 19, 20)]}]}
    return truth, analysis


def test_all_phases_prevent_one_favourable_offset_claim():
    truth, analysis = trace()
    result = replay_ablation(truth, analysis, [str(i) for i in range(120)])
    assert len(result["phases"]) == 15
    assert result["phase_recall_mean"] == pytest.approx(3/15)
    assert result["phase_recall_min"] == 0 and result["phase_recall_max"] == 1
    assert result["all_frame_eligible_ocr_calls"] == 120
    assert all(row["sampled_frames"] == row["eligible_ocr_calls"] == 8 for row in result["phases"])


def test_exact_cache_work_count_includes_lru_eviction():
    assert eligible_ocr_calls(["a", "a", "b", "a"]) == 2
    assert eligible_ocr_calls(["a", "b", "c", "a"], capacity=2) == 4


def test_negative_ablation_does_not_invent_accuracy_denominator():
    truth, analysis = trace()
    truth["events"] = []
    result = replay_ablation(truth, analysis, ["same"]*120)
    assert result["phase_recall_mean"] is None
    assert all(row["event_recall"] is None for row in result["phases"])


def test_incomplete_frame_hashes_fail_instead_of_hiding_truncation():
    truth, analysis = trace()
    with pytest.raises(ValueError):
        replay_ablation(truth, analysis, ["same"]*119)


def test_selected_geometry_remains_separate_from_detection_truth():
    truth, analysis = trace()
    selected = selected_geometry_truth(analysis)
    assert selected["events"][0]["id"] == "p1"
    assert truth["events"][0]["id"] == "t1"
    assert [row["index"] for row in selected["events"][0]["frames"]] == [18, 19, 20]


def test_frozen_design_has_disjoint_families_and_exact_size():
    dev = {name for name, split in LAYOUTS if split == "dev"}
    heldout = {name for name, split in LAYOUTS if split == "heldout"}
    assert dev == {"helpdesk", "terminal"}
    assert heldout == {"crm", "spreadsheet"}
    assert not dev & heldout
    assert len(LAYOUTS)*len(CONDITIONS)*2 == 24
    assert [last-first+1 for _, first, last in EXPOSURES] == [3, 8, 30, 15]


def test_nominal_stress_contrast_and_rendered_box_boundaries():
    for layout, _ in LAYOUTS:
        bg, fg = palette(layout, "C")
        assert contrast_ratio(bg, fg) == pytest.approx(4.5, abs=.06)
        for condition in CONDITIONS:
            image, annotations = render(layout, condition, True, 70)
            assert image.size == (1280, 720)
            assert len(annotations) == 1 and annotations[0]["type"] == "token"
            x1, y1, x2, y2 = annotations[0]["box"]
            assert 0 <= x1 < x2 < 1280 and 0 <= y1 < y2 < 720


def test_empty_summary_does_not_claim_passed_masks():
    result = summarize([])
    assert result["all_original_hashes_unchanged"] is None
    assert result["full_mask_frame_fraction"] is None
    assert result["ablation_1hz"]["phase_recall_mean"] is None


def complete_evidence(negative=False):
    regions, events = (0, 0) if negative else (3, 1)
    selected = {"checked_sensitive_frame_occurrences": regions, "fully_masked_frame_occurrences": regions,
        "uncovered_occurrences": [], "expected_events": events, "frame_count_matches": True,
        "output_frames": 120, "expected_frames": 120}
    row = {"id": "clip", "split": "dev", "original_unchanged": True,
        "detection": {"expected_events": events, "predicted_events": events, "expected_sensitive_frame_occurrences": regions},
        "mask_coverage": dict(selected), "selected_mask_geometry": dict(selected),
        "ablation_1hz": {"phases": [{"phase_frames": i, "expected_events": events} for i in range(15)]}}
    report = {"split": "dev", "status": "completed", "inference_core_unchanged": True, "samples": [row]}
    return report, {"clip": {"frames": 120, "events": events, "regions": regions}}


def test_integrity_gate_accepts_complete_measurement_not_only_high_accuracy():
    report, planned = complete_evidence()
    report["samples"][0]["mask_coverage"]["fully_masked_frame_occurrences"] = 0
    report["samples"][0]["mask_coverage"]["uncovered_occurrences"] = [{"frame": 18}]
    result = evidence_integrity(report, planned, True, True)
    assert result["headline_ready"] is True
    assert result["unscored_truth_regions"] == 0


def test_integrity_gate_reports_export_failure_unknown_denominator():
    report, planned = complete_evidence()
    row = report["samples"][0]
    row["error"] = "export failed"
    del row["mask_coverage"]
    del row["selected_mask_geometry"]
    del row["original_unchanged"]
    result = evidence_integrity(report, planned, True, True)
    assert result["headline_ready"] is False
    assert result["detection_scored_clips"] == 1
    assert result["fully_evaluated_clips"] == 0
    assert result["unscored_truth_regions"] == 3
    assert result["unknown_checks"] and result["source_preservation_failures"]


@pytest.mark.parametrize("check", ["mask_coverage", "selected_mask_geometry"])
def test_integrity_gate_rejects_wrong_frame_counts_in_either_check(check):
    report, planned = complete_evidence()
    report["samples"][0][check]["frame_count_matches"] = False
    report["samples"][0][check]["output_frames"] = 119
    result = evidence_integrity(report, planned, True, True)
    assert result["headline_ready"] is False and result["frame_count_failures"]


def test_integrity_gate_rejects_failed_selected_geometry():
    report, planned = complete_evidence()
    report["samples"][0]["selected_mask_geometry"]["fully_masked_frame_occurrences"] = 2
    result = evidence_integrity(report, planned, True, True)
    assert result["headline_ready"] is False and result["selected_geometry_failures"] == ["clip"]


def test_integrity_gate_clean_negative_zero_selected_boxes_is_not_applicable():
    report, planned = complete_evidence(negative=True)
    result = evidence_integrity(report, planned, True, True)
    assert result["headline_ready"] is True and result["selected_geometry_not_applicable_clips"] == 1


def test_integrity_gate_does_not_let_duplicates_replace_missing_clips():
    report, planned = complete_evidence()
    planned["missing"] = dict(planned["clip"])
    report["samples"].append(deepcopy(report["samples"][0]))
    result = evidence_integrity(report, planned, True, True)
    assert result["headline_ready"] is False
    assert result["missing_ids"] == ["missing"] and result["duplicate_ids"] == ["clip"]
    assert result["unscored_truth_regions"] == 6


def test_integrity_gate_rejects_wrong_split_and_mismatched_per_clip_denominator():
    report, planned = complete_evidence()
    report["samples"][0]["split"] = "heldout"
    report["samples"][0]["mask_coverage"]["checked_sensitive_frame_occurrences"] = 4
    result = evidence_integrity(report, planned, True, True)
    assert result["headline_ready"] is False and result["split_mismatches"]
    assert result["unscored_truth_regions"] == 3 and result["denominator_failures"]


@pytest.mark.parametrize("manifest_matches,core_matches", [(False, True), (True, False)])
def test_integrity_gate_requires_frozen_source_and_model(manifest_matches, core_matches):
    report, planned = complete_evidence()
    assert evidence_integrity(report, planned, manifest_matches, core_matches)["headline_ready"] is False
