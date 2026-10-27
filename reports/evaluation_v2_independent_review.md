# DemoSafe robustness v2 independent review

Status: **passed**. 969/969 audit checks passed.

Independent frozen-evidence review. No OCR/inference rerun, tuning, source edits, TTS, publication, or submission. Final film/deck/package assembly validation belongs to coordinator.

Independently sum raw samples; compare raw and published summaries; replay event assignment from saved observations using independent maximum-cardinality matching; decode input pixels for LRU eligible-call counts; decode exports for independent/selected black-region coverage; verify hashes and resume continuity; exercise gate rejection on in-memory copies only.

All 17 frozen source files and all 48 input/truth files retain their SHA-256 values. The first ten heldout sample objects are unchanged; exactly the two originally pending clips completed. This is one resumed heldout evaluation.

Resume continuity compares parsed sample values and observation/export byte hashes. Standard JSON serialization may replace a Unicode escape with the same Unicode character; whole benchmark JSON byte identity is not claimed. The pre-resume snapshot and reports/evaluation_v2_resume_provenance.json preserve that history.

| Split | Event recall | Independent masked truth regions | Correct selected geometry | False positives | Clean negatives | 1 Hz phase recall mean (range) | All-frame eligible OCR calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| dev | 20/24 (83.33%) | 237/336 (70.54%) | 237/237 | 0 | 6/6 | 45.00% (25.00–54.17%) | 841 |
| heldout | 18/24 (75.00%) | 231/336 (68.75%) | 231/231 | 0 | 6/6 | 43.33% (25.00–50.00%) | 909 |

Each split has 12/12 complete clips, 24 expected events, 336 scored annotated frame regions, zero unknown regions, and 120 decoded output frames per clip. All 15 phase values and work counts are in the JSON. Independent pixel rescoring confirms both the residual exposed regions and the selected-mask geometry checks.

Completeness gate negative controls reject export errors, missing evidence, wrong denominators, duplicate/missing IDs, truncation, selected-mask failures, wrong split, missing phases, source/manifest mismatches, and interrupted status. In-memory injected failures did not modify benchmark evidence.

The existing isolated-environment 96-test result remains applicable to unchanged app, tests, pinned requirements, and packager. No full-test rerun was needed. Package allowlist inspection includes all frozen inputs/truth while excluding uploaded jobs, environments, build files, observations and benchmark exports. The final ZIP and media/deck appearance are separately validated by the coordinator.

Interpretation limits:

- 24 fictional raster-rendered English UI clips; correlated paired conditions; no customer/human/real-browser generalization.
- Event recall and independent annotated-region mask coverage are different measures. Correct selected geometry does not imply all sensitive material was detected.
- All 15 sampling phases are retained. OCR-call counts are eligible work, not measured speedup. Shared-workstation observed wall times are not controlled performance.
- One original heldout run resumed after user-authorized shutdown pause; no tuning or second blind test claim.
- Original dev_019 miss remains known. Same-model rescanning is not independent truth or privacy assurance.
- No UGen300 integration, narration audio, publication, or submission receipt is claimed.

Final interruption/rescan annotations and completed resume provenance were checked after the measurement audit. Raw report hashes and every recomputed summary value remain unchanged; the JSON records the final summary and provenance hashes.
