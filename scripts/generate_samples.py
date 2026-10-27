"""Create reproducible fictional screen fixtures; benchmark truth is kept separately.

This is a dataset renderer, not the OCR implementation. The application must only
read rendered media under data/samples. It must never read benchmark_truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT, FPS, DURATION = 1280, 720, 10, 4
KEYWORD = "ORCHID CONFIDENTIAL"
TEMPLATES = (
    ("customer_dashboard", "dev", False),
    ("support_inbox", "dev", False),
    ("developer_terminal", "dev", True),
    ("project_board", "heldout", True),
    ("order_spreadsheet", "heldout", False),
    ("workspace_settings", "heldout", True),
)
SCENARIOS = (
    ("email_flash", 0.2, ("email",)),
    ("phone_notice", 0.5, ("phone",)),
    ("token_preview", 2.0, ("token",)),
    ("private_label", 0.5, ("custom",)),
    ("mixed_panel", 2.0, ("email", "phone", "custom")),
    ("moving_email", 0.2, ("email",)),
    ("clean_summary", 0.0, ()),
    ("clean_numbers", 0.0, ()),
)


def font_path(mono: bool = False) -> Path:
    choices = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / ("consola.ttf" if mono else "segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf" if mono else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in choices:
        if path.exists():
            return path
    raise RuntimeError("No reproducible TrueType font found. Install Segoe UI/Consolas or DejaVu Sans.")


def font(size: int, mono: bool = False):
    return ImageFont.truetype(str(font_path(mono)), size)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def base_screen(template: str, dark: bool, variant: int) -> Image.Image:
    bg, card, fg, muted, line = (("#111827", "#1e293b", "#f1f5f9", "#aebcd0", "#35445b")
                                  if dark else ("#edf2f7", "#ffffff", "#1e293b", "#586b83", "#d6e0ea"))
    im = Image.new("RGB", (WIDTH, HEIGHT), bg)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, WIDTH, 58), fill="#102c46")
    d.text((28, 12), "NORTHSTAR  /  FICTIONAL WORKSPACE", font=font(23), fill="#ffffff")
    d.text((958, 18), "Demo data only", font=font(18), fill="#98dcd2")
    d.text((36, 85), template.replace("_", " ").title(), font=font(31), fill=fg)
    d.text((38, 132), "Local preview  |  Synthetic test scene", font=font(17), fill=muted)

    if template == "customer_dashboard":
        for j, (title, value) in enumerate((("Open projects", "12"), ("Tasks completed", "84"), ("Review queue", "3"))):
            x = 38 + j * 407
            d.rounded_rectangle((x, 178, x + 388, 310), radius=14, fill=card)
            d.text((x + 20, 195), title, font=font(21), fill=muted)
            d.text((x + 20, 234), value, font=font(36), fill=fg)
        d.rounded_rectangle((38, 337, 1240, 645), radius=14, fill=card)
        d.text((60, 355), "Activity log", font=font(23), fill=fg)
        for j, name in enumerate(("Layout review completed", "Preview approved", "Assets ready for export")):
            d.text((62, 408 + j * 63), name, font=font(22), fill=muted)
    elif template == "support_inbox":
        d.rounded_rectangle((36, 172, 320, 645), radius=12, fill=card)
        for j, name in enumerate(("Inbox", "Assigned to me", "Resolved", "Draft replies")):
            d.text((58, 202 + j * 65), name, font=font(22), fill=fg)
        d.rounded_rectangle((344, 172, 1244, 645), radius=12, fill=card)
        for j, name in enumerate(("Ticket: export preview", "Status: waiting for review", "The sample attachment is ready.")):
            d.text((375, 201 + j * 66), name, font=font(23), fill=fg if j == 0 else muted)
    elif template == "developer_terminal":
        d.rounded_rectangle((37, 177, 1241, 645), radius=12, fill="#0b1220")
        for j, text in enumerate(("PS> run local-preview", "Loading synthetic workspace...", "Build completed successfully", "Preview listening on loopback", "No external requests")):
            d.text((62, 203 + j * 49), text, font=font(23, True), fill="#acd8bd")
    elif template == "project_board":
        for j, title in enumerate(("Planned", "In progress", "Review")):
            x = 37 + 408 * j
            d.rounded_rectangle((x, 180, x + 386, 644), radius=13, fill=card)
            d.text((x + 19, 199), title, font=font(23), fill=fg)
            for k, text in enumerate(("Refresh component library", "Prepare launch materials")):
                y = 258 + 130 * k
                d.rounded_rectangle((x + 14, y, x + 372, y + 102), radius=9, fill="#2c3b50")
                d.text((x + 27, y + 22), text, font=font(19), fill=fg)
                d.text((x + 27, y + 57), "Standard priority", font=font(16), fill=muted)
    elif template == "order_spreadsheet":
        d.rectangle((38, 181, 1240, 645), fill=card)
        cols = (38, 340, 640, 940, 1240)
        for x in cols:
            d.line((x, 181, x, 645), fill=line, width=1)
        for j in range(8):
            y = 181 + j * 58
            d.line((38, y, 1240, y), fill=line, width=1)
        for j, text in enumerate(("Item", "Quantity", "Status", "Review")):
            d.text((cols[j] + 17, 193), text, font=font(22), fill=fg)
        for row in range(1, 5):
            for j, text in enumerate((f"Sample component {row}", str(12 + row), "Ready", "Pending")):
                d.text((cols[j] + 17, 193 + 58 * row), text, font=font(20), fill=muted)
    else:
        d.rounded_rectangle((36, 174, 338, 644), radius=12, fill=card)
        for j, text in enumerate(("General", "Notifications", "Integrations", "Workspace")):
            d.text((63, 205 + 65 * j), text, font=font(22), fill=fg)
        d.rounded_rectangle((363, 174, 1244, 644), radius=12, fill=card)
        for j, text in enumerate(("Workspace name", "Northstar sample project", "Save previews locally", "Auto-save enabled")):
            d.text((392, 202 + 59 * j), text, font=font(23), fill=fg if j % 2 == 0 else muted)
    if variant == 7:
        d.rectangle((41, 573, 1237, 640), fill=card)
        d.text((62, 590), "Release 2026.10  |  Items 125  |  Completion 87%  |  Batch 0042", font=font(23), fill=fg)
    d.text((38, 682), "SELF-AUTHORED TEST FIXTURE  /  No real personal data or credentials", font=font(16), fill=muted)
    return im


def sensitive_value(kind: str, template_index: int, scenario_index: int) -> str:
    if kind == "email":
        return f"demo{template_index}{scenario_index}@example.com"
    if kind == "phone":
        return "+1 (202) 555-0147"
    if kind == "token":
        return "DEMO_ONLY_7f9a20bc61d44803"
    return KEYWORD


def paint_notice(image, items, size, dark, position=(376, 392), mono=False):
    d = ImageDraw.Draw(image)
    x, y = position
    height = 65 + 53 * len(items)
    card, fg = ("#273c51", "#ffffff") if dark else ("#ffffff", "#18354c")
    d.rounded_rectangle((x, y, min(WIDTH - 26, x + 828), y + height), radius=10, fill=card, outline="#31b4aa", width=3)
    d.text((x + 19, y + 12), "PRIVATE PREVIEW", font=font(15), fill="#15998f" if not dark else "#8aede0")
    boxes = []
    for i, (kind, value) in enumerate(items):
        label = {"email": "Email: ", "phone": "Phone: ", "token": "API_TOKEN: ", "custom": "Project: "}[kind]
        f = font(size, mono)
        yy = y + 45 + 53 * i
        d.text((x + 19, yy), label + value, font=f, fill=fg)
        start = x + 19 + d.textlength(label, font=f)
        box = d.textbbox((start, yy), value, font=f)
        boxes.append([int(np.floor(box[0])), int(np.floor(box[1])), int(np.ceil(box[2])), int(np.ceil(box[3]))])
    return boxes


def encode_video(path: Path, frames, fps=FPS):
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for frame in frames:
            proc.stdin.write(np.asarray(frame, dtype=np.uint8).tobytes())
        proc.stdin.close()
        error = proc.stderr.read().decode("utf-8", errors="replace")
        if proc.wait() != 0:
            raise RuntimeError(f"Video encoding failed: {error}")
    except BaseException:
        proc.kill()
        proc.wait()
        raise


def generate_fixture(index, scenario_index, samples_root, truth_root):
    template, split, dark = TEMPLATES[index]
    scenario, exposure, kinds = SCENARIOS[scenario_index]
    sample_id = f"{split}_{index * 8 + scenario_index + 1:03d}"
    relative = Path(split) / f"{sample_id}.mp4"
    size = (28, 25, 23)[scenario_index % 3]
    base = base_screen(template, dark, scenario_index)
    first = 10
    end = first + round(exposure * FPS)
    items = [(kind, sensitive_value(kind, index, scenario_index)) for kind in kinds]
    events = [{"id": f"{sample_id}_{n}", "type": kind, "text": value, "start": first / FPS, "end": end / FPS, "frames": []} for n, (kind, value) in enumerate(items)]
    def frames():
        for frame_index in range(DURATION * FPS):
            image = base.copy()
            if first <= frame_index < end:
                offset = (frame_index - first) * 12 if scenario == "moving_email" else 0
                boxes = paint_notice(image, items, size, dark, (376 - offset, 392), mono=(template == "developer_terminal"))
                for event, box in zip(events, boxes):
                    event["frames"].append({"index": frame_index, "box": box})
            yield image
    path = samples_root / relative
    encode_video(path, frames())
    truth = {"schema": 1, "id": sample_id, "split": split, "template": template, "scenario": scenario, "media": str(relative).replace("\\", "/"), "width": WIDTH, "height": HEIGHT, "fps": FPS, "frame_count": DURATION * FPS, "duration": DURATION, "font_size": size, "exposure": exposure, "keywords": [KEYWORD], "events": events, "sha256": sha256(path)}
    write_json(truth_root / f"{sample_id}.json", truth)
    return {"id": sample_id, "name": f"{template.replace('_', ' ').title()} / {scenario.replace('_', ' ')}", "description": f"Fictional {split} fixture; {exposure:g}s exposure" if kinds else f"Fictional {split} negative control", "path": truth["media"], "file": truth["media"], "url": "/samples/" + truth["media"], "split": split, "template": template}


def generate_demo(samples_root, truth_root):
    base = base_screen("customer_dashboard", False, 0)
    schedule = [(20, 23, "email"), (40, 50, "phone"), (65, 90, "token"), (96, 110, "custom")]
    events = [{"id": f"demo_{i}", "type": kind, "text": sensitive_value(kind, 0, i), "start": a / FPS, "end": b / FPS, "frames": []} for i, (a, b, kind) in enumerate(schedule)]
    def frames():
        for frame_index in range(120):
            image = base.copy()
            for event, (a, b, kind) in zip(events, schedule):
                if a <= frame_index < b:
                    boxes = paint_notice(image, [(kind, event["text"])], 28, False)
                    event["frames"].append({"index": frame_index, "box": boxes[0]})
            yield image
    path = samples_root / "demo_workspace.mp4"
    encode_video(path, frames())
    poster = base.copy()
    paint_notice(poster, [("email", "demo00@example.com"), ("phone", "+1 (202) 555-0147")], 28, False, (376, 392))
    poster.save(samples_root / "demo_screenshot.png")
    write_json(truth_root / "demo_workspace.json", {"schema": 1, "id": "demo_workspace", "split": "demo", "template": "customer_dashboard", "media": "demo_workspace.mp4", "width": WIDTH, "height": HEIGHT, "fps": FPS, "frame_count": 120, "duration": 12, "keywords": [KEYWORD], "events": events, "sha256": sha256(path)})
    return [{"id": "demo_workspace", "name": "The 0.3-second disclosure", "description": "12-second fictional dashboard. Four sensitive events, including a 0.3-second email flash. Custom keyword: ORCHID CONFIDENTIAL", "path": "demo_workspace.mp4", "file": "demo_workspace.mp4", "url": "/samples/demo_workspace.mp4", "split": "demo"}, {"id": "demo_screenshot", "name": "Fictional customer preview", "description": "Still-image example with fictional email and phone.", "path": "demo_screenshot.png", "file": "demo_screenshot.png", "url": "/samples/demo_screenshot.png", "split": "demo"}]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data")
    parser.add_argument("--demo-only", action="store_true")
    args = parser.parse_args()
    samples, truth_root = args.output / "samples", args.output / "benchmark_truth"
    samples.mkdir(parents=True, exist_ok=True)
    catalog = generate_demo(samples, truth_root)
    if not args.demo_only:
        for index in range(len(TEMPLATES)):
            for scenario_index in range(len(SCENARIOS)):
                item = generate_fixture(index, scenario_index, samples, truth_root)
                catalog.append(item)
                print(item["id"], flush=True)
    write_json(samples / "catalog.json", {"samples": catalog})
    manifest = {"schema": 1, "generator": "scripts/generate_samples.py", "generator_sha256": sha256(Path(__file__)), "license": "CC0-1.0", "authorship": "Self-authored synthetic UI fixtures. No captured third-party interfaces. All persons, workspace content and credentials are fictional.", "fonts": [{"name": font_path(mono).name, "sha256": sha256(font_path(mono))} for mono in (False, True)], "ffmpeg": imageio_ffmpeg.get_ffmpeg_version(), "split_policy": "Locked by UI template. Development: customer_dashboard, support_inbox, developer_terminal. Held-out: project_board, order_spreadsheet, workspace_settings. Never tune on held-out outcomes.", "counts": {"dev": sum(s.get("split") == "dev" for s in catalog), "heldout": sum(s.get("split") == "heldout" for s in catalog), "demo": sum(s.get("split") == "demo" for s in catalog)}, "limitations": "Synthetic English screen text, high contrast, 23-28px labels, 1280x720 at 10fps. This does not establish recall on real customer recordings. Same render and matching rules across splits; layouts are held out, categories are not.", "truth_location": "../benchmark_truth"}
    write_json(samples / "manifest.json", manifest)
    (samples / "LICENSE.txt").write_text("CC0 1.0 Universal. Self-authored synthetic dataset content is dedicated to the public domain. System font files are not distributed; their licenses remain with their owners. No real personal information or usable credentials are included.\n", encoding="utf-8")
    print(json.dumps(manifest["counts"]))


if __name__ == "__main__":
    main()
