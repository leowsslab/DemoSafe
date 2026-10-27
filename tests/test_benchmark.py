"""Test evaluator error sensitivity without substituting fake product inference."""
from types import SimpleNamespace

import numpy as np

from scripts.benchmark import aggregate, intersection_fraction, score_detections, solid_black_fraction
from scripts.generate_samples import SCENARIOS, TEMPLATES


def expected():
    return {"events": [{"id": "e1", "type": "email", "start": 1.0, "end": 1.2,
                         "frames": [{"index": 10, "box": [10, 10, 30, 20]}, {"index": 11, "box": [10, 10, 30, 20]}]}]}


def inference(frames, events):
    return SimpleNamespace(frames=frames, events=[{"id": e} for e in events])


def test_partial_duration_is_visible_even_when_event_detected():
    result = score_detections(expected(), inference([
        {"index": 10, "detections": [{"type": "email", "box": [8, 8, 32, 22], "event_id": "p1"}]},
        {"index": 11, "detections": []}], ["p1"]))
    assert result["event_recall"] == 1.0
    assert result["sensitive_frame_recall"] == 0.5


def test_unrelated_spatial_detection_is_false_positive_and_miss():
    result = score_detections(expected(), inference([
        {"index": 10, "detections": [{"type": "email", "box": [100, 100, 130, 120], "event_id": "p1"}]}], ["p1"]))
    assert result["detected_events"] == 0
    assert result["false_positive_events"] == 1


def test_duplicate_predictions_do_not_inflate_recall():
    result = score_detections(expected(), inference([
        {"index": 10, "detections": [{"type": "email", "box": [8, 8, 32, 22], "event_id": e} for e in ("p1", "p2")]}], ["p1", "p2"]))
    assert result["detected_events"] == 1
    assert result["false_positive_events"] == 1


def test_clean_scene_reports_no_recall_denominator():
    result = score_detections({"events": []}, inference([], ["spurious"]))
    assert result["event_recall"] is None
    assert result["false_positive_events"] == 1
    summary = aggregate([{"detection": result}])
    assert summary["negative_samples_with_false_positives"] == 1


def test_mask_coverage_reads_pixels_not_a_declared_box():
    frame = np.full((32, 32, 3), 255, dtype=np.uint8)
    frame[10:20, 10:20] = 0
    assert solid_black_fraction(frame, [10, 10, 20, 20]) == 1.0
    assert solid_black_fraction(frame, [10, 10, 30, 20]) == 0.5
    assert solid_black_fraction(frame, [-1, 10, 20, 20]) == 0.0


def test_event_box_matching_does_not_count_merely_touching_edges():
    assert intersection_fraction([0, 0, 10, 10], [10, 0, 20, 10]) == 0.0
    assert intersection_fraction([0, 0, 20, 20], [10, 10, 20, 20]) == 1.0


def test_dataset_splits_hold_out_entire_templates():
    dev = {name for name, split, _ in TEMPLATES if split == "dev"}
    heldout = {name for name, split, _ in TEMPLATES if split == "heldout"}
    assert len(dev) == len(heldout) == 3
    assert not dev & heldout
    assert len(TEMPLATES) * len(SCENARIOS) == 48
    assert sum(not kinds for _, _, kinds in SCENARIOS) == 2
