"""Pixel-only analysis and per-frame redaction. Never reads benchmark annotations."""
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
import subprocess
import time
import cv2
import numpy as np

from .detectors import detect_sensitive, masked_display
from .media import inspect_media, iter_frames
from .ocr import OCR


class Cancelled(Exception):
    pass


@dataclass
class Analysis:
    metadata: dict
    events: list = field(default_factory=list)
    frames: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    keywords: list = field(default_factory=list, repr=False)


def _check_cancel(cancelled):
    if cancelled and cancelled():
        raise Cancelled("Operation cancelled")


def _overlap(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return intersection / max(1, smaller)


def _merge_rows(lines):
    """Join adjacent OCR fragments; redact the whole row when a value is found."""
    rows = []
    for line in sorted(lines, key=lambda x: (x["box"][1], x["box"][0])):
        box = line["box"]
        center = (box[1] + box[3]) / 2
        target = None
        for row in rows:
            other = row["box"]
            height = min(box[3] - box[1], other[3] - other[1])
            if abs(center - (other[1] + other[3]) / 2) <= max(4, height * 0.45) and -10 <= box[0] - other[2] <= 180:
                target = row
                break
        if target is None:
            rows.append({"text": line["text"], "confidence": line["confidence"], "box": box.copy()})
        else:
            target["text"] += " " + line["text"]
            target["confidence"] = min(target["confidence"], line["confidence"])
            target["box"] = [min(target["box"][0], box[0]), min(target["box"][1], box[1]), max(target["box"][2], box[2]), max(target["box"][3], box[3])]
    return rows


def analyze_media(path: Path, keywords=None, on_progress=None, cancelled=None, model=None) -> Analysis:
    path = Path(path)
    metadata = inspect_media(path)
    engine = model or OCR
    result = Analysis(metadata=metadata, keywords=list(keywords or []))
    cache = OrderedDict()
    previous = []
    seen_frames = 0
    unique_frames = 0
    start_clock = time.perf_counter()
    ocr_seconds = 0.0
    for index, frame in iter_frames(path, metadata):
        _check_cancel(cancelled)
        digest = hashlib.sha256(frame.tobytes()).digest()
        if digest in cache:
            rows = cache[digest]
            cache.move_to_end(digest)
        else:
            ocr_start = time.perf_counter()
            rows = _merge_rows(engine.recognize(frame))
            ocr_seconds += time.perf_counter() - ocr_start
            unique_frames += 1
            cache[digest] = rows
            if len(cache) > 128:
                cache.popitem(last=False)
        detections = []
        used_events = set()
        for row in rows:
            for match in detect_sensitive(row["text"], result.keywords):
                event = next((item for item in previous if item["type"] == match["type"] and
                              item["text"].casefold() == match["text"].casefold() and
                              item["id"] not in used_events and _overlap(item["box"], row["box"]) >= 0.35), None)
                if event is None:
                    event = {"id": f"e{len(result.events)+1:04d}", "type": match["type"], "text": match["text"],
                             "display": masked_display(match["type"], match["text"]), "start": index / metadata["fps"],
                             "end": (index + 1) / metadata["fps"], "box": row["box"].copy(),
                             "confidence": row["confidence"], "redact": True}
                    result.events.append(event)
                else:
                    event["end"] = (index + 1) / metadata["fps"]
                    event["confidence"] = min(event["confidence"], row["confidence"])
                    event["box"] = [min(event["box"][0], row["box"][0]), min(event["box"][1], row["box"][1]),
                                    max(event["box"][2], row["box"][2]), max(event["box"][3], row["box"][3])]
                used_events.add(event["id"])
                detections.append({"type": match["type"], "text": match["text"], "confidence": row["confidence"],
                                   "box": row["box"].copy(), "event_id": event["id"]})
        previous = [event for event in result.events if event["id"] in used_events]
        result.frames.append({"index": index, "time": index / metadata["fps"], "detections": detections})
        seen_frames += 1
        if on_progress:
            on_progress(min(0.99, seen_frames / metadata["frame_count"]))
    _check_cancel(cancelled)
    elapsed = time.perf_counter() - start_clock
    result.metadata["frame_count"] = seen_frames
    result.metadata["duration"] = seen_frames / metadata["fps"]
    result.metadata["constant_frame_rate_verified"] = metadata["media_type"] == "video"
    result.metrics = {"frames_scanned": seen_frames, "unique_frames_ocr": unique_frames,
                      "exact_cache_hits": seen_frames - unique_frames, "analysis_seconds": round(elapsed, 3),
                      "ocr_seconds": round(ocr_seconds, 3), "processing_fps": round(seen_frames / max(elapsed, .001), 2),
                      "findings_count": len(result.events), "audio_checked": False, "all_frames_decoded": True}
    if on_progress:
        on_progress(1.0)
    return result


def validate_masks(masks, metadata):
    if len(masks) > 100:
        raise ValueError("At most 100 manual masks are allowed")
    validated = []
    for mask in masks:
        start, end = float(mask["start"]), float(mask["end"])
        box = mask["box"]
        if len(box) != 4 or not all(np.isfinite(float(x)) for x in box):
            raise ValueError("Mask must contain four finite coordinates")
        x1, y1, x2, y2 = [int(x) for x in box]
        if not (np.isfinite(start) and np.isfinite(end) and 0 <= start < end <= metadata["duration"] + 0.001):
            raise ValueError("Mask time range is outside the recording")
        if not (0 <= x1 < x2 <= metadata["width"] and 0 <= y1 < y2 <= metadata["height"]):
            raise ValueError("Mask coordinates are outside the image")
        validated.append({"start": start, "end": end, "box": [x1, y1, x2, y2]})
    return validated


def export_media(source: Path, output: Path, analysis: Analysis, decisions: dict, manual_masks=None,
                 on_progress=None, cancelled=None) -> dict:
    import imageio_ffmpeg
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError("Output must not overwrite the source")
    masks = validate_masks(manual_masks or [], analysis.metadata)
    expected = {event["id"] for event in analysis.events}
    if set(decisions) != expected or any(type(value) is not bool for value in decisions.values()):
        raise ValueError("Every detected event must have one explicit keep/redact decision")
    metadata = analysis.metadata
    started = time.perf_counter()
    process = None
    masked_frames = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    if metadata["media_type"] == "video":
        command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                   "-vcodec", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{metadata['width']}x{metadata['height']}",
                   "-r", str(metadata["fps"]), "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", "0", "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-movflags", "+faststart", str(output)]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        for index, frame in iter_frames(source, metadata):
            _check_cancel(cancelled)
            if index >= len(analysis.frames):
                raise ValueError("Source changed after analysis")
            timestamp = index / metadata["fps"]
            boxes = [item["box"] for item in analysis.frames[index]["detections"] if decisions[item["event_id"]]]
            boxes.extend(mask["box"] for mask in masks if mask["start"] <= timestamp < mask["end"])
            for x1, y1, x2, y2 in boxes:
                frame[y1:y2, x1:x2] = 0
            if boxes:
                masked_frames += 1
            if process:
                process.stdin.write(frame.tobytes())
            else:
                if not cv2.imwrite(str(output), frame):
                    raise RuntimeError("Could not write the redacted image")
            if on_progress:
                on_progress(0.65 * (index + 1) / metadata["frame_count"])
        if process:
            process.stdin.close()
            error = process.stderr.read()
            code = process.wait(timeout=120)
            if code:
                raise RuntimeError("Video encoder failed")
        _check_cancel(cancelled)
        rescanned = analyze_media(output, analysis.keywords,
                                  on_progress=lambda p: on_progress(0.65 + p * 0.35) if on_progress else None,
                                  cancelled=cancelled)
        count = len(rescanned.events)
        report = {"schema_version": 1, "backend": OCR.backend, "model": OCR.model, "hardware_verified": False,
                  "media": {key: metadata[key] for key in ("media_type", "width", "height", "fps", "duration", "frame_count")},
                  "analysis": analysis.metrics, "decisions": [{"event_id": event["id"], "type": event["type"],
                  "start": event["start"], "end": event["end"], "action": "redact" if decisions[event["id"]] else "keep"}
                  for event in analysis.events], "manual_mask_count": len(masks), "masked_frames": masked_frames,
                  "audio_removed": metadata["media_type"] == "video", "audio_checked": False,
                  "export_seconds": round(time.perf_counter() - started, 3),
                  "rescan": {"status": "passed" if count == 0 else "findings", "findings_count": count,
                  "message": "No supported text patterns detected in output; not a guarantee of privacy." if count == 0 else
                  "Supported text patterns remain. Review kept events and the exported media before sharing."},
                  "limitations": ["Supported visible text patterns only; names, faces and arbitrary confidential content may be missed.",
                                  "Output rescan uses the same OCR and rules and is not an independent privacy guarantee.",
                                  "OCR accuracy depends on font, size, contrast, compression and language."]}
        _check_cancel(cancelled)
        return report
    except BaseException:
        if process and process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        output.unlink(missing_ok=True)
        raise
    finally:
        if process:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if process.stderr:
                process.stderr.close()
