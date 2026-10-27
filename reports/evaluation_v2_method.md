# DemoSafe robustness v2: frozen method

This suite extends the original 48-clip test without replacing any old evidence. It is a small, correlated set of **raster-rendered fictional interfaces**, not customer footage, actual browser recordings, human-user research, or UGen300 measurements.

## Frozen design

The manifest and SHA-256 marker under `data/robustness_v2` were created before inference. The generator refuses to overwrite a frozen dataset. Four complete layout families use different structures and fonts: helpdesk/Segoe UI and terminal/Consolas are development; CRM/Arial and spreadsheet/Calibri are held out. They do not reuse the original notification-card renderer. Rendering infrastructure, event timing, and keyword are still shared across layouts, so no broad UI-generalization claim follows.

Each layout has a positive/negative pair in three conditions, for 24 clips total, 12 per split. Every clip is 1280 x 720, 15 FPS, 120 frames, H.264 yuv420p with no audio. A uses 24 px high-contrast text and CRF 18. B uses 16 px high-contrast text and CRF 28. C uses 20 px text with nominal full-pixel contrast approximately 4.5:1, CRF 32, and a changing background outside the sensitive regions. Antialiased edge pixels and compressed pixels do not retain the nominal contrast. C is a composite stress test, not an isolated causal comparison.

Each positive clip has four events: email at frames 18-20 inclusive (0.2 s), phone at frames 38-45 (0.533 s), dummy credential at frames 60-89 (2 s), and supplied keyword at frames 96-110 (1 s). Each split contains 24 expected events and 336 annotated sensitive-frame regions. Negative pairs show ordinary text at matching times and have zero expected findings.

All four layout families were visually inspected for clipping and overlap before inference. This only validates fixture construction; it is not OCR tuning on held-out results.

## Inference and independent scoring

The evaluator passes only the encoded media and the fixed operator keyword `CEDAR INTERNAL` into `analyze_media`. It reads truth regions only after the call returns. No inference code imports the fixture renderer, manifest, or truth annotations.

Event matching is one-to-one by type with at least 50% overlap of the expected text rectangle on an expected frame. Per-frame recall independently records duration misses. Exports choose every detected event and add no manual masks. Coverage is then checked against the original annotation regions in decoded output pixels: at least 99.5% of each region must have every RGB channel at most 16. Undetected regions stay in the denominator. Output frame counts and original source hashes are checked.

A separate selected-geometry check examines the detection rectangles the operator chose to mask. It demonstrates whether the export applied those selections correctly, not whether all sensitive material was detected. Both metrics must remain distinct in any presentation. Same-model output rescanning is recorded separately and is not ground truth or a privacy guarantee.

## 1 Hz phase ablation

The evaluator replays unchanged per-frame observations at all 15 possible phase offsets for a 1 Hz sampler. It reports the mean, minimum, and maximum event recall across phases. This avoids selecting an especially favorable phase. Original temporal track IDs are retained for event matching; this is not a second product implementation.

Decoded-pixel hashes are also replayed through the same bounded 128-entry LRU cache rule to count eligible OCR calls. These are work counts, not measured runtime savings. The all-frame pipeline has real measured analysis/export wall times; the 1 Hz replay does not provide speedup, hardware-performance, or human-efficiency evidence. Measurements on this shared workstation are not controlled throughput benchmarks.

Observed test host: Intel Core i5-10400F at 2.90 GHz (Windows registry processor name), 12 logical processors, Windows 11 build 26200, Python 3.12.14. Product OCR uses the existing two intra-operation threads and one inter-operation thread. RAM capacity and physical-core count were not independently confirmed because WMI queries were unavailable in this sandbox. The first sample can include model initialization; later samples reuse the same process/model. Background desktop activity is not isolated, and timings must be described as observed run times rather than hardware guarantees.

The authorized held-out run shares this workstation with low-thread FFmpeg editing/encoding and PDF/media-production work. No separate application OCR demonstration is scheduled during that run. This concurrency is a known timing confound: wall-clock times are observations of this particular run, not standardized performance measurements or a controlled comparison against the development split. They cannot support a hardware-speedup claim.

## Reporting and freeze rules

Reports are saved after each clip and preserve failed samples. A completed report is never silently overwritten. Resuming requires the same dataset manifest and inference-core source hashes. Any OCR, media, rule, or pipeline change requires new versioned evidence; previously observed held-out data cannot keep the label of unseen evaluation after tuning.

The held-out runner requires an explicit root freeze note. It must not run until the coordinator authorizes the final source freeze. Security/UI-only changes can alter other application hashes; the report therefore stores before/after hashes and separately verifies the inference core remained unchanged.

Acceptance is complete, reproducible evidence with source preservation, correct output frame counts, correct chosen-mask geometry, and visible failures. No target OCR percentage is used as a reason to tune held-out data, discard hard cases, or hide residual exposure. The original `dev_019` miss remains a known failure regardless of v2 results.
