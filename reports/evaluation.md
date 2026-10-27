# Measured prototype results

Backend code was frozen before the held-out run.

| Metric | Development | Held out |
|---|---:|---:|
| Clips | 24 | 24 |
| Detected / expected events | 23 / 24 | 24 / 24 |
| False-positive events | 0 | 0 |
| Clean negatives | 6 / 6 | 6 / 6 |
| Fully masked sensitive-frame regions | 262 / 282 | 282 / 282 |
| Correct output frame counts | 24 / 24 | 24 / 24 |
| Analysis total | 107.67 s | 112.31 s |
| Export and rescan total | 102.27 s | 109.06 s |

Event matching requires matching type and at least 50% of the annotated text region on one or more expected frames. A separate per-frame check catches timing failures. Independent coverage requires at least 99.5% of each annotated region to have every RGB channel <=16 in the exported frame.

The development failure is dev_019: a dark terminal credential in 23px monospace text was missed for all 20 exposed frames. Same-model rescan also missed it.

Background layouts are split, but notification rendering is shared. The clips are high contrast, largely static and lossless. Cache benefits do not represent noisy, animated or lossy recordings. These results do not validate real customer recordings, universal PII coverage, real-time speed or UGen300 acceleration.

To reproduce, use the installed project environment: python scripts/benchmark.py --split dev and python scripts/benchmark.py --split heldout.

Do not tune on held-out results and keep labeling the same set unseen. Per-clip measurements and backend SHA-256 values are in benchmark_dev.json, benchmark_heldout.json and benchmark_summary.json.

