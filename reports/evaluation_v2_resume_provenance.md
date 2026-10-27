# DemoSafe v2 held-out continuation provenance

Completed: 2026-10-05T01:03:23.692980+00:00.

The participant explicitly requested continuation after the shutdown pause. The saved resume script exited 0 and completed exactly the two unfinished spreadsheet C clips from frame zero. This is continuation of the original evaluation, not a new blind trial. No OCR, model, fixture, evaluator or method changes were made.

- Verified all 17 frozen source files, the manifest, and all 24 media/truth pairs before and after continuation.
- Preserved the historical pause checkpoint and immutable pre-resume snapshot.
- First 10 parsed sample objects are identical; all 10 observation and 10 exported-video byte hashes match their baseline.
- Standard runner JSON serialization changed escaped Unicode representation only; no raw measurement-report edits were performed.
- Both splits are complete at 12/12, and both final-headline evidence gates are true.
- All 24 input hashes, 120-frame output counts, selected-mask geometry checks and 15-phase replay completeness checks pass.

Held-out results: 18/24 detected events (75%); 231/336 independently masked annotated frame regions (68.75%); 0 false-positive events; 6/6 clean negatives; selected geometry 231/231.

Spreadsheet C positive: 2/4 events, 11/56 annotated regions; token and custom keyword wholly missed. Same-model rescan passed with 0 findings despite 45 uncovered regions. The gate confirms complete evidence and chosen-mask application, not privacy protection.

A new process resumed the two incomplete clips, so the first resumed clip can include model initialization. All times are observations on the shared workstation, not standardized throughput or a speedup comparison.

Machine-readable preservation checks and hashes: `evaluation_v2_resume_provenance.json`. Detailed metrics and all failure cases: `evaluation_v2_results.json` and `.md`.
