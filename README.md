# DemoSafe

DemoSafe reviews screenshots and short screen recordings for supported visible sensitive-text patterns, lets the operator keep or redact each finding, then exports solid masks and scans the output again. It is a local CPU prototype for the ASUS UGen AI League; **UGen300 inference has not been implemented or verified**.

The current contribution is the complete review workflow: all-frame decoding, exact-pixel OCR reuse, temporal findings, explicit decisions, frame-specific masks, silent export, and a report that does not contain the detected plaintext. It does not claim to invent OCR or automated redaction.

## Competition prototype

Team: **DemoSafe**. One human entrant with AI assistance. Proposed track:
Workplace AI / Battlefield Lightning / Global Online Track.

This repository contains the application, install scripts, fictional samples,
fixed evaluation inputs, tests and technical evidence. It excludes private user
uploads, source narration, credentials, virtual environments and video-editing
intermediates. The existing original-code MIT license and all third-party
notices are preserved.

The current competition film is v4: 156 seconds, English synthetic narration and
52 bilingual caption pairs. Real browser captures are approximately 1-4 frames
per second, held in the 30 fps export. UGen300 inference is still planned.
Source: [github.com/leowsslab/DemoSafe](https://github.com/leowsslab/DemoSafe).
The participant will upload the demonstration video; its verified URL is pending.
Creating a repository does not mean the competition entry has been submitted.

See [AI collaboration and media disclosure](docs/AI_COLLABORATION.md),
[architecture](docs/ARCHITECTURE.md), [hardware plan](docs/HARDWARE_ROADMAP.md),
[model and dependency notices](MODEL_AND_DEPENDENCY_NOTICES.md), and
[controlled results](reports/evaluation_v2_results.md).

### Verify this source tree

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Historical local release reports include packaging tests that are outside this
source-only repository. The release-specific test receipt records the exact
test count for this tree. Do not re-run a held-out evaluation and present it as
a new blind test; the frozen results and interruption/resume provenance remain.

## Install and start

Tested on Windows with Python **3.12.14**. Python 3.12 is recommended; the pinned RapidOCR package requires Python below 3.13. Internet access is needed to install packages. The ONNX models are included in the installed RapidOCR wheel.

In PowerShell, from this project directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\start.ps1
```

The review bundle already includes fictional examples and frozen evaluation fixtures; installation does not require regenerating them. For a source-only copy without examples, run `.\.venv\Scripts\python.exe scripts/generate_samples.py --demo-only` once. Do not overwrite evaluation fixtures when checking the supplied reports.

The launcher opens the browser with a fresh, private authentication fragment. The page removes that fragment immediately and exchanges it for a local HttpOnly, SameSite=Strict cookie. A plain visit to [the local app](http://127.0.0.1:8765) works only when that browser already has a current session; otherwise use the launcher. Credentials and cookies are invalidated when the server restarts.

An equivalent launch command is:

```powershell
.\.venv\Scripts\python.exe scripts/launch.py
```

Keep the server bound to `127.0.0.1`. This is a single-user local capability, not an account service or a multi-user deployment. Requests that change state must originate from the exact configured scheme, hostname, and port. A different localhost port is not trusted. To stop the server, press Ctrl+C in its terminal. Processing is queued through one worker. A session accepts up to 20 jobs; deleting a finished job frees a slot.

For controlled browser automation, the launcher can write the private launch URL to a new JSON file in the current user's OS temporary directory:

```powershell
$launchInfo = Join-Path $env:TEMP ('demosafe-launch-' + [guid]::NewGuid().ToString('N') + '.json')
.\scripts\start.ps1 -Port 8765 -NoBrowser -LaunchInfoPath $launchInfo
```

The JSON appears only after this server instance is listening and contains `origin`, `url`, and `pid`. An automation client may read `url` without printing or logging it, then open it in its browser. Do not put the file into the repository or submission package. The launcher removes it on normal shutdown; an automation client may remove it after reading. Direct `uvicorn` invocation does not deliver a bootstrap URL and is therefore not the supported interactive start method.

## Try the workflow

1. Choose the fictional dashboard sample or the still-image sample, or select a local file. No real personal data is needed for the demonstration.
2. Add `ORCHID CONFIDENTIAL` as a custom keyword for the complete dashboard scenario. Keywords are case-insensitive and tolerate spaces between words.
3. Run analysis. The first run includes model initialization and may take longer. Findings show masked labels, time ranges, and source-pixel boxes.
4. Review every event and explicitly keep or redact it. Add manual time-and-box masks for content the detector misses.
5. Export. Video is re-encoded as an MP4 **with no audio track**; images become PNG files. All chosen masks use opaque black pixels, with no blur reconstruction risk.
6. Inspect the output and its rescan result. Download the JSON report if needed. A report saying that no supported patterns remain is not a privacy guarantee.
7. When finished, delete the job to remove its local original, poster, export, report, and in-memory review state. If you cancel an operation, wait until the worker has actually stopped before deleting it.

Supported input: PNG/JPEG images and decodable MP4/MOV/MKV/WEBM/AVI videos, at most **100 MB**, **60 seconds**, **1920 × 1080 pixels**, and **30 FPS**. Browser preview support varies by codec; constant-frame-rate H.264 MP4 is recommended. Odd image dimensions are padded by up to one pixel for MP4 encoding. Cancel stops at the next processing boundary; an individual OCR call may finish first.

## What is actually running

- **OCR:** `rapidocr-onnxruntime==1.4.4`, using PP-OCRv4 detection and recognition models, executed with ONNX Runtime on the CPU. The angle classifier is disabled during inference.
- **Rules:** email patterns, selected US/Taiwan telephone formats, credential-like text with an explicit label or recognized token prefix, and operator-provided keywords. These are review hints, not a universal PII classifier.
- **Temporal handling:** every decoded frame is checked; byte-identical decoded frames reuse OCR results through a bounded cache. No periodic frame sampling is used by the application. Detections are grouped across adjacent frames using type, value, and spatial overlap. Export uses the original per-frame detection boxes, not an event's combined bounding box.
- **Media:** OpenCV decodes; FFmpeg encodes silent H.264 MP4 output using CRF 0 to preserve the encoded YUV frames and exact-frame reuse during verification. RGB-to-YUV 4:2:0 conversion still changes some color detail; output is not promised to be bit-identical to the RGB source. Files can be larger than conventional lossy exports. Images use lossless PNG output. The original copy is preserved.
- **Rescan:** the exported pixels pass through the same OCR and rules. This catches some output mistakes, but cannot independently prove that everything sensitive has been removed.

The application receives only pixels and user-supplied keywords. Benchmark annotations are stored separately and are read only by the evaluator. See `MODEL_AND_DEPENDENCY_NOTICES.md` for model filenames, hashes, provenance, and dependency notices.

## Privacy and data lifetime

Application inference makes no remote API calls. The browser talks to the loopback FastAPI server; the application has no telemetry integration. Package installation requires network access. Narration for submission materials is supplied separately by the entrant; this application does not generate narration or send uploaded recordings or OCR text to a voice service.

Uploaded originals, posters, exported files, and reports remain in `data/jobs/<random-id>/` until that job is deleted. OCR text remains inside the server's analysis state; public job responses return masked labels and omit the detected `text` field without altering internal analysis. Downloaded reports also omit that plaintext. The original media itself still contains the source content. All job, report, and media API routes require the current local session.

Deletion checks the exact recorded job directory and refuses while an upload or actual worker Future remains unfinished, even if the visible job status already says cancelled. It removes only the selected indexed job. Restarting clears the job index and invalidates authentication, but does not delete old files. The application does not automatically clean up legacy job folders. After stopping the server, the operator may remove unneeded legacy folders manually. Do not include `data/jobs`, `.venv`, launch-info files, cookies, or machine-specific temporary files in a source submission.

The October 4, 2026 security review verified unauthenticated API rejection, exact-origin checks, session bootstrap, response headers, and the loopback listener. OSV returned no known vulnerability matches for the 30 queried installed Python package versions. This narrow result does not cover all bundled native libraries, unknown vulnerabilities, or application logic. See `reports/security_review_v2.json` for the captured evidence and `docs/SECURITY_REVIEW_ZH.md` for remaining risks. Local session cookies and origin checks do not isolate untrusted programs or services on the same computer. Files are not encrypted by the application, and deletion is not forensic erasure.

## Evaluation and limitations

Tests exercise session bootstrap and invalidation, authenticated reads/media, exact origins, framing headers, path boundaries, input bounds, cancellation, deletion after actual worker completion, concurrent export admission, explicit decisions, per-frame mask geometry, source preservation, report privacy, evaluator behavior, and package exclusions:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp=tests/.pytest-work
```

`scripts/generate_samples.py` creates fictional recordings and separate ground truth. `scripts/benchmark.py --help` describes reproducible evaluation. Development and held-out templates must remain separate; a synthetic benchmark demonstrates controlled behavior, not accuracy on arbitrary customer recordings. Report all measured failures and the exact benchmark/model versions.

The v2 extension adds 24 fixed 8-second H.264 clips at 720p/15 FPS across helpdesk, terminal, CRM and spreadsheet layouts. Its annotations and media hashes were frozen before inference. See `data/robustness_v2/README.md`, `scripts/benchmark_robustness_v2.py --help` and `reports/evaluation_v2_method.md` for reproduction. Repeating a supplied held-out run is a regression check, not a new blind evaluation. Event recall and complete truth-frame-region mask coverage are distinct metrics. The 15-phase one-frame-per-second comparison replays OCR observations; it measures neither an actual speedup nor time saved by a human reviewer.

Known boundaries:

- OCR can miss small, low-contrast, partially occluded, compressed, rotated, or unfamiliar text. It may also misread characters and create false findings.
- Names, faces, payment details, arbitrary proprietary material, and voice content are outside the detector's supported scope. A kept finding deliberately remains visible.
- A mask covers an entire OCR line, which can hide adjacent non-sensitive words. Manual review remains part of the workflow.
- Time ranges use decoded frame indexes and the input's reported FPS. The decoder checks frame timestamps against that cadence and rejects material drift or unavailable timing. Constant-frame-rate input is the supported timing path; variable-frame-rate recordings must be converted before review.
- Scanning every unique frame is expensive on CPU. Static recordings benefit from exact-frame reuse; highly animated videos may take substantially longer than their duration.
- A clean rescan is neither a security certificate nor a claim of regulatory compliance. Verify the exported file before sharing it.

## UGen300 plan and competition status

`HailoOCRAdapter` is a deliberately unavailable integration boundary. It raises an explicit error rather than pretending that CPU execution is hardware acceleration. The UI and reports identify the actual CPU backend and `hardware_verified: false`.

Hailo's [official standalone PaddleOCR example](https://github.com/hailo-ai/hailo-apps/blob/main/hailo_apps/python/standalone_apps/paddle_ocr/README.md) documents Hailo-10H and Windows support. A later hardware stage must install the matching runtime, obtain compatible detector/recognizer HEF files under their actual terms, replace the OCR adapter, and rerun the same accuracy/export/latency tests. Model compatibility, USB performance, and speedup remain unverified. No UGen300 benchmark numbers are claimed.

The source, benchmark, deck, and demonstration can support an initial submission. Hardware deployment and a genuine UGen300 demonstration are separate later-stage work.

## Local API

`POST /api/session` exchanges the launch credential with an exact `Origin` header. `GET /api/session` checks an existing cookie. All other `/api/` endpoints require that cookie, and all mutations require the exact canonical origin. Core endpoints are `GET /api/health`, `GET /api/samples`, `POST /api/jobs`, `POST /api/jobs/sample`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel`, `POST /api/jobs/{id}/export`, `DELETE /api/jobs/{id}`, `GET /api/jobs/{id}/report`, and the original/redacted/poster media endpoints. `IMPLEMENTATION.md` specifies request and response shapes. External-CDN interactive API documentation is disabled to keep the frontend's script policy local. Input paths are never accepted as arbitrary public API parameters.
