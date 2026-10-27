# DemoSafe robustness v2 results

## Interruption and continuation provenance

The original held-out run was interrupted at the participant's shutdown request after 10 completed clips. On explicit instruction to continue DemoSafe, the saved resume command verified all 17 frozen source hashes and all 24 frozen clips, preserved the first 10 sample values and their observation/export bytes, and restarted only the two incomplete spreadsheet C clips from frame zero. This completes the same original held-out evaluation; it is not a second blind trial. The historical pause checkpoint and pre-resume snapshot remain unchanged. See `evaluation_v2_resume_provenance.json`.

A new process performed this continuation; the first resumed clip can include model initialization. Analysis and export/rescan wall times are observations on a shared workstation, not standardized throughput or speedup measurements.

Fictional raster-rendered English UI, 24 correlated clips; CPU only; not customer or browser recordings.

The frozen method is documented in evaluation_v2_method.md. Pending/running splits are not final claims.

## dev

Status: **completed**, 12/12 fully evaluated clips. Final-headline gate: **True**.

Independent truth-region scoring: 336/336; unscored/unknown: **0**. The gate checks evidence completeness, not high accuracy.

| Measurement | Result |
|---|---:|
| Detected / expected events | 20 / 24 (83.33%) |
| False-positive events | 0 |
| Clean negatives | 6 / 6 |
| Independently masked annotated frame regions, scored clips only | 237 / 336 (70.54%) |
| Correctly applied selected mask rectangles | 237 / 237 |
| Analysis wall time, sum of completed clips | 974.40 s |
| Export plus rescan wall time, sum | 932.30 s |

Selected-mask coverage measures export geometry only; missed sensitive regions remain in the independent annotation denominator.

1 Hz phase replay event recall: mean 45.00%, range 25.00%–54.17% across 15 phases.

| Condition | Events | Annotated frame regions fully masked | False-positive events |
|---|---:|---:|---:|
| A | 6/8 | 57/112 | 0 |
| B | 7/8 | 97/112 | 0 |
| C | 7/8 | 83/112 | 0 |

Failures and residual exposure:

- v2_dev_helpdesk_A_positive: missed events custom; 40 uncovered annotated frame regions; 0 false-positive events; same-model rescan=findings.
- v2_dev_helpdesk_C_positive: missed events none wholly missed; 14 uncovered annotated frame regions; 0 false-positive events; same-model rescan=findings.
- v2_dev_terminal_A_positive: missed events custom; 15 uncovered annotated frame regions; 0 false-positive events; same-model rescan=passed.
- v2_dev_terminal_B_positive: missed events custom; 15 uncovered annotated frame regions; 0 false-positive events; same-model rescan=passed.
- v2_dev_terminal_C_positive: missed events custom; 15 uncovered annotated frame regions; 0 false-positive events; same-model rescan=passed.

## heldout

Status: **completed**, 12/12 fully evaluated clips. Final-headline gate: **True**.

Independent truth-region scoring: 336/336; unscored/unknown: **0**. The gate checks evidence completeness, not high accuracy.

| Measurement | Result |
|---|---:|
| Detected / expected events | 18 / 24 (75.00%) |
| False-positive events | 0 |
| Clean negatives | 6 / 6 |
| Independently masked annotated frame regions, scored clips only | 231 / 336 (68.75%) |
| Correctly applied selected mask rectangles | 231 / 231 |
| Analysis wall time, sum of completed clips | 1070.73 s |
| Export plus rescan wall time, sum | 1075.09 s |

Selected-mask coverage measures export geometry only; missed sensitive regions remain in the independent annotation denominator.

1 Hz phase replay event recall: mean 43.33%, range 25.00%–50.00% across 15 phases.

| Condition | Events | Annotated frame regions fully masked | False-positive events |
|---|---:|---:|---:|
| A | 6/8 | 82/112 | 0 |
| B | 7/8 | 97/112 | 0 |
| C | 5/8 | 52/112 | 0 |

Failures and residual exposure:

- v2_heldout_crm_A_positive: missed events custom; 15 uncovered annotated frame regions; 0 false-positive events; same-model rescan=passed.
- v2_heldout_crm_B_positive: missed events custom; 15 uncovered annotated frame regions; 0 false-positive events; same-model rescan=passed.
- v2_heldout_crm_C_positive: missed events custom; 15 uncovered annotated frame regions; 0 false-positive events; same-model rescan=passed.
- v2_heldout_spreadsheet_A_positive: missed events custom; 15 uncovered annotated frame regions; 0 false-positive events; same-model rescan=passed.
- v2_heldout_spreadsheet_C_positive: missed events token, custom; 45 uncovered annotated frame regions; 0 false-positive events; same-model rescan=passed.

## Same-model rescan blind spot

The held-out **spreadsheet C positive** clip detected **2/4 events** and independently masked **11/56 annotated frame regions**. It wholly missed the token (2.0 seconds) and the custom keyword (1.0 second), leaving 45 annotated frame regions uncovered. Nevertheless, the same-model output rescan reported **passed, 0 findings**. This is a concrete false-assurance risk: rescan success does not establish that sensitive text was removed. All misses and uncovered regions remain in the headline denominators and failure list below.

## Interpretation limits

Original dev_019 token miss remains known; same-model output rescan did not catch it.

All 15 sampling phases replay identical per-frame observations. Eligible OCR-call counts are work counts, not measured speedup or human time saved.

Conditions jointly vary font/compression, and C also varies contrast/motion. Paired variants are correlated. Unmatched prediction tracks count as false-positive events and can include fragmentation duplicates; this is not necessarily spurious text. Matching uses intersection divided by truth area, not IoU. Do not describe these findings as universal accuracy, customer validation, a privacy guarantee, real-time capability, or UGen300 acceleration.

The source package includes the input media, fixture truth, manifests, notices and reports needed to reproduce the checks. Per-clip observations, exported benchmark media and visual previews are retained locally and can be regenerated; the source ZIP intentionally excludes these derived artifacts. Reports do not discard misses or replace old benchmark evidence.
