from pathlib import Path
import cv2
import numpy as np
from PIL import Image

MAX_SECONDS = 60
MAX_BYTES = 100 * 1024 * 1024
MAX_WIDTH, MAX_HEIGHT, MAX_FPS = 1920, 1080, 30
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}


def inspect_media(path: Path) -> dict:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("File exceeds the 100 MB limit")
    extension = path.suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        with Image.open(path) as picture:
            if picture.format not in {"PNG", "JPEG"}:
                raise ValueError("Only PNG and JPEG images are supported")
            width, height = picture.size
            _validate_size(width, height)
            picture.verify()
        return {"media_type": "image", "width": width, "height": height, "fps": 1.0, "duration": 1.0, "frame_count": 1}
    if extension not in VIDEO_EXTENSIONS:
        raise ValueError("Unsupported file type. Use PNG, JPEG, MP4, MOV, MKV, WEBM or AVI")
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError("Cannot decode this video")
        width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        _validate_size(width, height)
        if not np.isfinite(fps) or fps <= 0 or fps > MAX_FPS + 0.01:
            raise ValueError("Video must have a valid frame rate of 30 FPS or lower")
        if count <= 0:
            raise ValueError("Video frame count is unavailable; re-encode as constant-frame-rate MP4")
        if count / fps > MAX_SECONDS + 0.001 or count > 1800:
            raise ValueError("Video must be 60 seconds or shorter")
        return {"media_type": "video", "width": width, "height": height, "fps": fps, "duration": count / fps, "frame_count": count}
    finally:
        capture.release()


def _validate_size(width, height):
    if width <= 0 or height <= 0 or width > MAX_WIDTH or height > MAX_HEIGHT:
        raise ValueError("Maximum dimensions are 1920 × 1080 pixels")


def iter_frames(path: Path, metadata: dict):
    if metadata["media_type"] == "image":
        with Image.open(path) as picture:
            yield 0, cv2.cvtColor(np.asarray(picture.convert("RGB")), cv2.COLOR_RGB2BGR)
        return
    capture = cv2.VideoCapture(str(path))
    index = 0
    first_timestamp = None
    try:
        while capture.isOpened():
            success, frame = capture.read()
            if not success:
                break
            if index >= 1800 or index / metadata["fps"] >= MAX_SECONDS + 0.001:
                raise ValueError("Decoded video exceeds the 60 second limit")
            if frame.shape[:2] != (metadata["height"], metadata["width"]):
                raise ValueError("Changing video dimensions are unsupported")
            timestamp = float(capture.get(cv2.CAP_PROP_POS_MSEC)) / 1000
            if first_timestamp is None:
                first_timestamp = timestamp
            expected = index / metadata["fps"]
            if (not np.isfinite(timestamp) or timestamp < 0 or
                    abs((timestamp - first_timestamp) - expected) > max(0.01, 0.20 / metadata["fps"])):
                raise ValueError("Video timestamps are variable or unavailable. Convert to constant-frame-rate H.264 MP4 before review.")
            yield index, frame
            index += 1
    finally:
        capture.release()
    if index == 0:
        raise ValueError("Video contains no readable frames")
    if abs(index - metadata["frame_count"]) > 1:
        raise ValueError("Video is truncated or has inconsistent frame metadata")
