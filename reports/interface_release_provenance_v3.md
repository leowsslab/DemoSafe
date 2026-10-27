# DemoSafe v3 interface verification

The existing 96 automated tests pass (0 failures, 1 existing Starlette/httpx deprecation warning). All 14 non-frontend files in the v2 evaluation freeze still match exactly. The 3 frontend files intentionally changed for the authorized redesign; their original v2 bytes and freeze-matching hashes are preserved in `build/interface-v2-snapshot`. All 91 original IDs and protected control attributes remain. No v2 reports were modified. The only source change between pretest snapshot and the later receipt was the concurrently authored media-production script `scripts/prepare_narrated_audio_v3.py`; app, tests, dependencies and the 14 frozen evaluation files remained unchanged.

The recorded hero export decodes to 120 frames at 1280 × 720, 10 fps, 12 seconds, with matching source timestamps and no audio track. The original sample and imported local copy match the frozen fixture SHA-256. The actual manual mask is [19, 10, 170, 53], consistent with the captured UI's 151 × 43 px, 0–12 s mask. It exceeds 99.5% black coverage on all 120 frames. The independently located NORTHSTAR region [28, 21, 157, 37] is 100% black on every frame while present in every source frame.

The operator's approximate x=18 rectangle includes an extra left column and measures 99.3268% black; that wider approximation is **not** reported as passing the 99.5% check. The actual mask measures 99.9846% or better. No export pixels or source files were changed to obtain these results.

The first downloaded report records 10.513 s analysis and 14.385 s export. The coordinator then canceled a manual draft, deselected/reselected the email to verify the changed-selection state, and re-exported the same final decisions and mask. That later report records 13.171 s export; output bytes are identical. Both observations remain distinct, and the original downloaded report is preserved.

Coordinator browser evidence records actual downloads, manual-draft cancellation, and changed-selection handling. DOM widths show no horizontal overflow at 1267 px and 390 px. Screenshot capture failed after those resizes, so this report does not claim visual verification of the narrow layout. Earlier open-tab intake copy can differ from the finalized source; the coordinator was advised to refresh intake captures. Review/manual/compare are unaffected by that copy refinement.

This is one fictional demonstration. Manual-mask coverage is separate from automatic recall; a passed same-model rescan is not independent privacy assurance. Timings are observations on a shared workstation. No new benchmark or OCR evaluation was run. The frontend author also performed this filesystem audit; independent pixel checks are not an independent-person design review.

Detailed receipts: `test_summary_final_v3.json`, `validation_ui_export_v3.json`, and `interface_release_provenance_v3.json`.
