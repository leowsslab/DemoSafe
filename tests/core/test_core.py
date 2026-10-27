"""Core invariants; OCR doubles below test geometry, not model accuracy."""
import json
from pathlib import Path
import cv2
import numpy as np
import pytest

from app.detectors import detect_sensitive
from app.media import inspect_media
from app.paths import safe_child
from app.pipeline import Analysis, Cancelled, analyze_media, export_media, validate_masks


@pytest.mark.parametrize("text,kind", [
    ("Send to jane.doe@example.com", "email"),
    ("Phone: +1 (202) 555-0147", "phone"),
    ("Phone:+1(202)555-0147", "phone"),
    ("Contact (202)555-0147", "phone"),
    ("Mobile 0912-345-678", "phone"),
    ("API_TOKEN: DEMO_ONLY_7f9a20bc61d44803", "token"),
    ("password = demo-test-pass", "token"),
])
def test_supported_patterns(text, kind):
    assert kind in {x["type"] for x in detect_sensitive(text)}


@pytest.mark.parametrize("text", ["2026-10-04", "10:30:00", "Monthly sales: 12345", "Token budget", "API documentation", "v1.2.3", "Reference ID: 2025550147"])
def test_common_screen_text_is_not_a_secret(text):
    assert not detect_sensitive(text)


def test_custom_keyword_matches_ocr_whitespace():
    assert detect_sensitive("ORCHID  CONFIDENTIAL", ["orchid confidential"])[0]["type"] == "custom"


@pytest.mark.parametrize("path", ["../secret.txt", "nested/../../secret.txt", "C:\\Windows\\win.ini", "\\\\server\\share\\file", "/etc/passwd"])
def test_paths_cannot_escape(tmp_path, path):
    with pytest.raises(ValueError):
        safe_child(tmp_path, path)


def test_nested_sample_path_is_allowed(tmp_path):
    assert safe_child(tmp_path, "dev/sample.mp4") == tmp_path / "dev" / "sample.mp4"


def test_image_bounds_before_ocr(tmp_path):
    path = tmp_path / "wide.png"
    cv2.imwrite(str(path), np.zeros((50, 1921, 3), dtype=np.uint8))
    with pytest.raises(ValueError, match="1920"):
        inspect_media(path)


def test_wrong_extension_content_rejected(tmp_path):
    path = tmp_path / "bad.png"
    path.write_bytes(b"not an image")
    with pytest.raises(Exception):
        inspect_media(path)


def test_masks_reject_nan_and_out_of_bounds():
    meta = {"width": 100, "height": 80, "duration": 4}
    for mask in [{"start": 0, "end": 2, "box": [-1, 0, 20, 20]},
                 {"start": 0, "end": 5, "box": [0, 0, 20, 20]},
                 {"start": float("nan"), "end": 2, "box": [0, 0, 20, 20]}]:
        with pytest.raises(ValueError):
            validate_masks([mask], meta)


def test_cancelled_analysis_never_invokes_model(tmp_path):
    image = tmp_path / "input.png"
    cv2.imwrite(str(image), np.full((80, 100, 3), 255, dtype=np.uint8))
    class NoCall:
        def recognize(self, frame):
            raise AssertionError("Model should not run")
    with pytest.raises(Cancelled):
        analyze_media(image, cancelled=lambda: True, model=NoCall())


def test_export_solid_mask_preserves_original_and_report_is_safe(tmp_path, monkeypatch):
    source, output = tmp_path / "input.png", tmp_path / "redacted.png"
    original = np.full((80, 100, 3), 255, dtype=np.uint8)
    cv2.imwrite(str(source), original)
    metadata = inspect_media(source)
    sensitive = "private@example.com"
    event = {"id": "e0001", "type": "email", "text": sensitive, "start": 0, "end": 1, "box": [10, 10, 50, 30]}
    analysis = Analysis(metadata, [event], [{"index": 0, "time": 0, "detections": [{"event_id": "e0001", "box": event["box"]}]}], {"findings_count": 1})
    monkeypatch.setattr("app.pipeline.analyze_media", lambda *args, **kwargs: Analysis(metadata))
    report = export_media(source, output, analysis, {"e0001": True})
    redacted = cv2.imread(str(output))
    assert np.max(redacted[10:30, 10:50]) == 0
    assert np.min(redacted[40:60]) == 255
    assert np.array_equal(cv2.imread(str(source)), original)
    assert sensitive not in json.dumps(report)
    assert "text" not in report["decisions"][0]


def test_export_requires_explicit_decision(tmp_path):
    source = tmp_path / "input.png"
    cv2.imwrite(str(source), np.zeros((20, 20, 3), dtype=np.uint8))
    analysis = Analysis(inspect_media(source), [{"id": "e1"}])
    with pytest.raises(ValueError, match="explicit"):
        export_media(source, tmp_path / "output.png", analysis, {})


def test_export_cannot_overwrite_input(tmp_path):
    source = tmp_path / "input.png"
    cv2.imwrite(str(source), np.zeros((20, 20, 3), dtype=np.uint8))
    with pytest.raises(ValueError, match="overwrite"):
        export_media(source, source, Analysis(inspect_media(source)), {})


def test_cancelled_export_removes_partial_output(tmp_path):
    source, output = tmp_path / "input.png", tmp_path / "output.png"
    cv2.imwrite(str(source), np.zeros((20, 20, 3), dtype=np.uint8))
    analysis = Analysis(inspect_media(source), frames=[{"index": 0, "time": 0, "detections": []}])
    with pytest.raises(Cancelled):
        export_media(source, output, analysis, {}, cancelled=lambda: True)
    assert not output.exists()


def test_reject_cross_site_request(authed_client):
    response = authed_client.post("/api/jobs/sample", json={"sample_id": "none"}, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403


def test_unknown_media_and_jobs_do_not_expose_disk(authed_client):
    assert authed_client.get("/api/jobs/missing/media/original").status_code == 404
    assert authed_client.get("/api/jobs/../../IMPLEMENTATION.md").status_code in {404, 405}


def test_upload_rejected_before_receiving_large_body(authed_client):
    response = authed_client.post("/api/jobs", headers={"Content-Length": str(102 * 1024 * 1024)}, content=b"")
    assert response.status_code == 413


def test_per_frame_masks_do_not_expand_to_entire_temporal_union(tmp_path, monkeypatch):
    import app.pipeline as pipeline
    source, output = tmp_path / "input.png", tmp_path / "output.png"
    cv2.imwrite(str(source), np.full((80, 100, 3), 255, dtype=np.uint8))
    metadata = inspect_media(source)
    # UI event box covers a union, but only this frame's local detection is masked.
    event = {"id": "e1", "type": "email", "start": 0, "end": 1, "box": [0, 0, 100, 80]}
    analysis = Analysis(metadata, [event], [{"index": 0, "time": 0, "detections": [{"event_id": "e1", "box": [10, 10, 20, 20]}]}])
    monkeypatch.setattr(pipeline, "analyze_media", lambda *args, **kwargs: Analysis(metadata))
    export_media(source, output, analysis, {"e1": True})
    result = cv2.imread(str(output))
    assert np.max(result[10:20, 10:20]) == 0
    assert np.min(result[30:70, 30:70]) == 255


def test_real_cfr_passes_and_vfr_is_rejected(tmp_path):
    import subprocess
    import imageio_ffmpeg
    from app.media import iter_frames
    encoder = imageio_ffmpeg.get_ffmpeg_exe()
    cfr, vfr = tmp_path / "cfr.mp4", tmp_path / "vfr.mp4"
    common = [encoder, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=2"]
    subprocess.run(common + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(cfr)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    subprocess.run(common + ["-vf", r"setpts=if(lt(N\,10)\,N/(10*TB)\,(10+(N-10)*2)/(10*TB))", "-fps_mode", "vfr",
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", str(vfr)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert len(list(iter_frames(cfr, inspect_media(cfr)))) == 20
    with pytest.raises(ValueError, match="constant-frame-rate"):
        list(iter_frames(vfr, inspect_media(vfr)))
