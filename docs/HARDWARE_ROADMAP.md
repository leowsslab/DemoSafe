# DemoSafe: UGen300 hardware roadmap

Status: 2026-10-05. Stage I runs PP-OCRv4 on CPU. No UGen300 has been attached or validated. This document is an integration plan, not a hardware performance result.

## Selected route and evidence

First confirm whether the supplied device is USB or M.2 and its capacity. Then use its matching ASUS/Hailo runtime and an official OCR example with matched pretrained HEFs before attempting any custom conversion. USB has the documented route below, but the supplied interface is not yet confirmed. Keep the working CPU environment intact.

- [ASUS UGen Utility](https://github.com/Asus-UGen-Series/Ugen-Utility) offers separate USB and PCIe packages, documents driver 5.3.0, and lists Paddle OCR. That utility currently supports Linux only.
- [ASUS Windows demos](https://github.com/Asus-UGen-Series/UGen300-Series-11-Ready-to-run-AI-Demos-for-Windows) documents Windows 11, USB UGen300, Python 3.10 and HailoRT 5.3.x. This establishes a Windows device route, not DemoSafe OCR accuracy.
- [Hailo standalone Paddle OCR](https://github.com/hailo-ai/hailo-apps/blob/main/hailo_apps/python/standalone_apps/paddle_ocr/README.md) documents Windows installation and Hailo-10H, with runtime 5.3.0. Its [resource configuration](https://github.com/hailo-ai/hailo-apps/blob/main/hailo_apps/config/resources_config.yaml) currently names the default detector/recognizer `ocr_det` and `ocr`.
- The official [HAILO10H detection](https://github.com/hailo-ai/hailo_model_zoo/blob/master/docs/public_models/HAILO10H/HAILO10H_text_detection.rst) and [recognition](https://github.com/hailo-ai/hailo_model_zoo/blob/master/docs/public_models/HAILO10H/HAILO10H_text_recognition.rst) tables also list PP-OCRv5 mobile HEFs. These are a separate candidate model pair, not a drop-in replacement for the current PP-OCRv4 weights.

These pages are moving references. Before installation, record the exact repository commit, package versions, source URLs, hashes and terms in a hardware run manifest.

## Compatibility gates

1. Confirm the **actual device interface and capacity**, including compatible host connection. Match driver, firmware, HailoRT, Python wheel and HEF architecture. A Hailo-8 example is not evidence of Hailo-10H compatibility. Do not automatically flash firmware; follow the exact device instructions when required.
2. Do not mix a 5.3 example and a HEF built for a newer runtime without checking compatibility. Current Model Zoo tables cite compiler 5.4.0, while the standalone README cites runtime 5.3.0.
3. The [Model Zoo evaluation guide](https://github.com/hailo-ai/hailo_model_zoo/blob/master/docs/GETTING_STARTED.rst) states PCIe-only hardware support. Its evaluator and published PCIe FPS are not a verified USB execution path or UGen300 benchmark.
4. Use an isolated hardware environment. The current app uses Python 3.12, NumPy 2.3.5 and OpenCV 5.0. The [official OCR requirements](https://github.com/hailo-ai/hailo-apps/blob/main/hailo_apps/python/standalone_apps/paddle_ocr/requirements.txt) specify NumPy below 2 and OpenCV at most 4.10.0.84. Preserve the Stage I environment and reports.
5. Keep the detector, recognizer, input normalization, decoder and character dictionary together. The [v5 recognizer configuration](https://github.com/hailo-ai/hailo_model_zoo/blob/master/hailo_model_zoo/cfg/networks/paddle_ocr_v5_mobile_recognition.yaml) uses 48×320 input and a v5 character dictionary. Do not apply spelling correction to emails or credentials.

## Adapter contract

`recognize(frame)` receives one BGR `uint8` frame and returns a list of `{text, confidence, box}` objects. `box` is `[x1, y1, x2, y2]` in original-frame pixels, with right/bottom exclusive, clipped to image bounds and nonempty. Map resizing/padding back before returning. Confidence must be finite and within 0–1.

The adapter returns an empty list only when inference succeeded with no text. Missing hardware, incompatible HEF, timeout or failed inference raises an explicit error. Selecting UGen must never silently execute CPU. Reports identify the backend actually used, exact model artifacts and whether device execution was verified.

Keep rule matching, event tracking, manual decisions, frame-specific masks and export outside the adapter. Preserve every decoded frame; camera-oriented example code must not introduce dropped or sampled frames. Adapter tests using fixtures validate the interface only, not real hardware support.

## Stage I: ready by October 12

- Keep the CPU backend as the submitted working prototype. Profile decode, OCR, tracking, encode and rescan separately to identify the acceleration target.
- Publish the integration architecture and this compatibility checklist; retain `hardware_verified: false`.
- Prepare representative fictional images and recordings, plus adapter contract tests and a version manifest template.
- Do not require compiler installation, model conversion, new paid services or hardware purchase to finish Stage I. Do not derive application speedup from 40 TOPS.

## Stage II: gates after delivery

`D` is the day the provided device is received and available. Dates below are work targets, not a delivery promise. The participant handles receipt, physical connection, required personal login and OS approval; the assistant handles setup, integration, testing and recording.

| Target | Work | Evidence required to advance |
|---|---|---|
| D to D+2 | Identify USB or M.2 and the host connection; establish a matched, isolated runtime; run an official image model and OCR example. | Device/driver/firmware/runtime manifest; successful inference on a fictional project image. |
| D+3 to D+5 | Connect the OCR adapter and test coordinates, empty results, errors and cancellation. Start at batch size 1. | Real device output used by DemoSafe; explicit failure without the device; no silent fallback. |
| D+6 to D+8 | Rerun accuracy, false-positive, masking and export checks; evaluate the changed model on a newly frozen holdout. | Separate results by model, backend, dataset version and known failures. |
| D+9 to D+10 | Run five repeated CPU and device trials on the same host and inputs, separating cold start from warmed runs. | Median/range for total latency and OCR time; unique-frame count and cache state; no dropped frames. |
| By November 27 | Freeze the stable hardware release; drop optional conversion work. | Reproducible install, model notices, real UGen recording and verified failure behavior. |
| December 1–3 | Finish final-stage English materials and participant review. | Working repository/video access and a verified submission package before the December 4 deadline. |

CPU PP-OCRv4 versus device PP-OCRv5 is a **system comparison with different models**. A pure hardware speedup claim needs a matched-model CPU control. No energy saving claim is made without appropriate measurement.

If the official OCR example still cannot run after three working days, produce a concise diagnostic bundle for an authorized support inquiry and stop speculative conversion work. A detector-on-device/recognizer-on-CPU variant is acceptable only after testing and explicit hybrid labeling. If no genuine device inference exists by the freeze gate, retain the working CPU prototype but do not represent it as a completed hardware final submission.
