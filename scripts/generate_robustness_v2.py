"""Freeze fictional UI robustness fixtures without importing product inference.

These are raster-rendered fictional interfaces, not customer or browser recordings.
The four complete layout families are split before any inference. Condition C is a
composite stress condition, so its result does not isolate a single causal factor.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "robustness_v2"
WIDTH, HEIGHT, FPS, FRAME_COUNT = 1280, 720, 15, 120
KEYWORD = "CEDAR INTERNAL"
LAYOUTS = (("helpdesk", "dev"), ("terminal", "dev"), ("crm", "heldout"), ("spreadsheet", "heldout"))
CONDITIONS = {
    "A": {"font_px": 24, "crf": 18, "contrast": "high", "moving_background": False},
    "B": {"font_px": 16, "crf": 28, "contrast": "high", "moving_background": False},
    "C": {"font_px": 20, "crf": 32, "contrast": "approximately 4.5:1", "moving_background": True},
}
EXPOSURES = (("email", 18, 20), ("phone", 38, 45), ("token", 60, 89), ("custom", 96, 110))
FONT_NAMES = {"helpdesk": "segoeui.ttf", "terminal": "consola.ttf", "crm": "arial.ttf", "spreadsheet": "calibri.ttf"}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def font_path(layout):
    path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / FONT_NAMES[layout]
    if not path.is_file():
        raise RuntimeError(f"Required frozen font is unavailable: {path.name}")
    return path


def font(layout, size):
    return ImageFont.truetype(str(font_path(layout)), size)


def luminance(rgb):
    channels = [v / 255 for v in rgb]
    values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return sum(v * weight for v, weight in zip(values, (.2126, .7152, .0722)))


def contrast_ratio(a, b):
    first, second = sorted((luminance(a), luminance(b)))
    return (second + .05) / (first + .05)


def palette(layout, condition):
    background = (15, 23, 33) if layout == "terminal" else (255, 255, 255)
    if condition != "C":
        foreground = (244, 248, 250) if layout == "terminal" else (22, 35, 49)
    else:
        candidates = [(v, v, v) for v in range(256)]
        foreground = min(candidates, key=lambda rgb: abs(contrast_ratio(rgb, background) - 4.5))
    return background, foreground


def layout_canvas(layout, frame, condition):
    """Four structurally distinct layouts, not the old shared notification card."""
    dark = layout == "terminal"
    canvas = Image.new("RGB", (WIDTH, HEIGHT), (15, 23, 33) if dark else (240, 244, 248))
    draw = ImageDraw.Draw(canvas)
    title_font, small = font(layout, 26), font(layout, 17)
    if layout == "helpdesk":
        draw.rectangle((0, 0, 1279, 77), fill="#173d50")
        draw.text((28, 24), "FIELD DESK  |  Case workspace", font=title_font, fill="white")
        draw.rectangle((0, 78, 252, 719), fill="#dfe9ee")
        for i, value in enumerate(("My queue", "New requests", "Assigned", "Resolved", "Draft response")):
            draw.text((24, 124 + 66 * i), value, font=small, fill="#294859")
        draw.rectangle((276, 99, 1256, 650), fill="white")
        draw.text((302, 124), "Export issue / customer reply", font=title_font, fill="#182d3c")
        for i, label in enumerate(("Reply address", "Callback", "Temporary credential", "Internal subject")):
            draw.text((308, 190 + i * 100), label, font=small, fill="#667985")
        positions = [(308, 222 + i * 100) for i in range(4)]
    elif layout == "terminal":
        draw.rectangle((0, 0, 1279, 65), fill="#253244")
        draw.text((26, 20), "Run console / fictional deployment", font=title_font, fill="#f2f6fa")
        draw.text((36, 102), "Local build succeeded. Output follows:", font=small, fill="#83cec4")
        for i, label in enumerate(("[mail]", "[call]", "[credential]", "[project]")):
            draw.text((35, 191 + i * 98), label, font=small, fill="#92b0c7")
        positions = [(252, 190 + i * 98) for i in range(4)]
        draw.line((25, 605, 1255, 605), fill="#465565", width=1)
        draw.text((36, 628), "No live service credentials. All data is fictional.", font=small, fill="#aebbc8")
    elif layout == "crm":
        draw.rectangle((0, 0, 1279, 91), fill="#413853")
        draw.text((32, 30), "RELATION  /  Contact dossier", font=title_font, fill="white")
        draw.ellipse((54, 133, 166, 245), fill="#cabedb")
        draw.text((48, 271), "Sample contact", font=title_font, fill="#30263f")
        for i, value in enumerate(("Overview", "Activity", "Preferences")):
            draw.text((51, 344 + i * 70), value, font=small, fill="#625a70")
        draw.rectangle((340, 120, 1241, 653), fill="white")
        for i, label in enumerate(("Electronic mail", "Telephone", "Integration value", "Private notes")):
            draw.line((365, 154 + i * 120, 1210, 154 + i * 120), fill="#ded6e6")
            draw.text((368, 169 + i * 120), label, font=small, fill="#796d83")
        positions = [(368, 203 + i * 120) for i in range(4)]
    else:
        draw.rectangle((0, 0, 1279, 69), fill="#22543f")
        draw.text((30, 21), "Inventory notes / fictional workbook", font=title_font, fill="white")
        draw.rectangle((0, 70, 1279, 119), fill="#e0eee6")
        draw.text((35, 86), "File     Edit     View     Insert                 Sheet: Review", font=small, fill="#315243")
        draw.rectangle((37, 145, 1247, 633), fill="white")
        columns = (37, 91, 320, 1040, 1247)
        for x in columns:
            draw.line((x, 145, x, 633), fill="#b7c6bc")
        for row in range(7):
            y = 145 + row * 80
            draw.line((37, y, 1247, y), fill="#b7c6bc")
            if row < 6:
                draw.text((54, y + 22), str(row + 1), font=small, fill="#5d7364")
        for i, label in enumerate(("Owner email", "Support phone", "Service config", "Project label")):
            draw.text((110, 246 + i * 80), label, font=small, fill="#41634d")
        draw.text((110, 166), "FIELD", font=small, fill="#41634d")
        draw.text((338, 166), "VALUE", font=small, fill="#41634d")
        positions = [(338, 244 + i * 80) for i in range(4)]
    if condition == "C":
        # Changes outside sensitive regions defeat exact-pixel reuse without moving truth boxes.
        x = 25 + (frame * 9) % 1100
        draw.rectangle((0, 672, 1279, 719), fill="#34495a" if dark else "#dbe6ee")
        draw.rectangle((x, 684, x + 90, 695), fill="#8fbfb4")
        draw.line((0, 713 - frame % 11, 1279, 713 - frame % 11), fill="#607f90")
    return canvas, positions


def event_values(layout):
    index = [item[0] for item in LAYOUTS].index(layout)
    return (f"review.{layout}@example.invalid", f"202-555-01{20+index}",
            f"API key: demo_{layout}_7Q2M9X4P", KEYWORD)


def render(layout, condition, positive, frame):
    canvas, positions = layout_canvas(layout, frame, condition)
    draw = ImageDraw.Draw(canvas)
    background, foreground = palette(layout, condition)
    selected_font = font(layout, CONDITIONS[condition]["font_px"])
    positives = event_values(layout)
    negatives = ("Address hidden for preview", "Contact reference pending", "Runtime mode: read only", "Public sample workspace")
    annotations = []
    for i, (kind, first, last) in enumerate(EXPOSURES):
        if not first <= frame <= last:
            continue
        value = positives[i] if positive else negatives[i]
        x, y = positions[i]
        box = draw.textbbox((x, y), value, font=selected_font)
        if box[2] >= 1238 or box[3] >= 660:
            raise RuntimeError(f"Text would overflow layout: {layout} / {condition} / {value}")
        # Erase only the text's own plain field. No shared notification card is drawn.
        draw.rectangle((box[0]-2, box[1]-2, box[2]+2, box[3]+2), fill=background)
        draw.text((x, y), value, font=selected_font, fill=foreground)
        if positive:
            # Credential truth covers the secret value, excluding the context label.
            if kind == "token":
                prefix_width = draw.textlength("API key: ", font=selected_font)
                box = (int(x + prefix_width), box[1], box[2], box[3])
            annotations.append({"type": kind, "index": frame, "box": list(map(int, box))})
    return canvas, annotations


def generate_clip(directory, layout, split, condition, positive):
    name = f"v2_{split}_{layout}_{condition}_{'positive' if positive else 'negative'}"
    target = directory / "media" / f"{name}.mp4"
    target.parent.mkdir(parents=True, exist_ok=True)
    args = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "pipe:0", "-an", "-c:v", "libx264", "-threads", "2", "-preset", "medium", "-crf", str(CONDITIONS[condition]["crf"]), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target)]
    process = subprocess.Popen(args, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    events = {kind: {"id": kind, "type": kind, "start": first/FPS, "end": (last+1)/FPS, "frames": []} for kind, first, last in EXPOSURES} if positive else {}
    try:
        for index in range(FRAME_COUNT):
            frame, annotations = render(layout, condition, positive, index)
            process.stdin.write(np.asarray(frame, dtype=np.uint8).tobytes())
            for row in annotations:
                events[row["type"]]["frames"].append({"index": index, "box": row["box"]})
            if positive and index in {19, 70}:
                preview = directory / "previews" / f"{name}_f{index:03d}.png"
                preview.parent.mkdir(parents=True, exist_ok=True)
                frame.save(preview)
        process.stdin.close()
        error = process.stderr.read().decode("utf-8", errors="replace")
        if process.wait(timeout=120):
            raise RuntimeError(error)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
    bg, fg = palette(layout, condition)
    truth = {"schema": 2, "id": name, "split": split, "layout": layout, "condition": condition,
             "positive": positive, "width": WIDTH, "height": HEIGHT, "fps": FPS, "frame_count": FRAME_COUNT,
             "media": f"media/{target.name}", "media_sha256": digest(target),
             "keywords": [KEYWORD], "events": list(events.values()),
             "font_file": font_path(layout).name, "font_sha256": digest(font_path(layout)),
             "condition_parameters": CONDITIONS[condition], "text_foreground": fg, "text_background": bg,
             "uncompressed_full_pixel_contrast_ratio": round(contrast_ratio(fg, bg), 4),
             "contrast_note": "Nominal full-pixel foreground/background ratio before antialiasing and video compression; edge pixels differ."}
    truth_path = directory / "truth" / f"{name}.json"
    write_json(truth_path, truth)
    return {"id": name, "split": split, "layout": layout, "condition": condition, "positive": positive,
            "media": truth["media"], "media_sha256": truth["media_sha256"],
            "truth": str(truth_path.relative_to(directory)).replace("\\", "/"), "truth_sha256": digest(truth_path)}


def verify(directory=DATA):
    manifest_path = directory / "manifest.json"
    expected = (directory / "manifest.sha256").read_text().strip()
    if digest(manifest_path) != expected:
        raise RuntimeError("Frozen manifest changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["clips"]:
        for kind in ("media", "truth"):
            if digest(directory / item[kind]) != item[f"{kind}_sha256"]:
                raise RuntimeError(f"Frozen {kind} changed: {item['id']}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        manifest = verify()
        print(f"Verified {len(manifest['clips'])} frozen clips", flush=True)
        return
    if (DATA / "manifest.json").exists():
        raise RuntimeError("Dataset is frozen. Refusing to overwrite it; use --verify.")
    rows = []
    for layout, split in LAYOUTS:
        for condition in CONDITIONS:
            for positive in (True, False):
                rows.append(generate_clip(DATA, layout, split, condition, positive))
                print(f"[{len(rows)}/24] {rows[-1]['id']}", flush=True)
    manifest = {"schema": 2, "dataset": "robustness_v2", "frozen_at": datetime.now(timezone.utc).isoformat(),
                "generator_sha256": digest(__file__), "seed": "deterministic; no random generator",
                "limitations": ["Fictional raster-rendered UI, not customer or browser recordings.",
                    "Layout families disjoint between splits, but renderer infrastructure and event timing are shared.",
                    "Conditions are paired correlated variants, not independent population samples.",
                    "C changes font size, contrast, compression and background motion together; no single-factor causal claim.",
                    "English supported text patterns only. Does not evaluate human efficiency or UGen300."],
                "clips": rows}
    write_json(DATA / "manifest.json", manifest)
    (DATA / "manifest.sha256").write_text(digest(DATA / "manifest.json") + "\n", encoding="ascii")
    verify()
    print("Dataset frozen and verified before inference.", flush=True)


if __name__ == "__main__":
    main()
