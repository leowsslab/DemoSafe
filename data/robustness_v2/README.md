# Robustness v2 fictional fixtures

These 24 short clips and their annotations were created specifically for DemoSafe by `scripts/generate_robustness_v2.py`. They are raster-rendered fictional interfaces, **not recordings of real customer software or data, browser automation evidence, customer interviews, or user-efficiency measurements**. They are separate from the actual DemoSafe browser demonstration footage.

All displayed contact addresses use `example.invalid`, phone values use the fictional US `202-555-01xx` range, credential strings are deliberately generated dummy values, and `CEDAR INTERNAL` is a made-up keyword. No user-uploaded recordings, actual customer records, third-party screenshots, stock images, logos, functioning account credentials, or real personal data were used to construct this dataset. Interface names and layouts are original fictional compositions.

## Layout split and construction

The development layouts are helpdesk and terminal; the held-out layouts are CRM and spreadsheet. Each layout has positive and negative pairs under A, B and C, for 12 clips per split. Full layout families are disjoint, while rendering infrastructure, event timing and keyword are shared. Variants are correlated and cannot be treated as independent population samples.

Every clip is 8 seconds, 1280 x 720, 15 FPS and silent H.264 MP4. Conditions are A: 24 px, high contrast, CRF 18; B: 16 px, high contrast, CRF 28; C: 20 px, nominal contrast approximately 4.5:1 before antialiasing/compression, CRF 32, moving background. C is a composite stress condition, not a test isolating one causal variable.

The renderer uses locally installed Windows fonts through Pillow: Segoe UI (`segoeui.ttf`) for helpdesk, Consolas (`consola.ttf`) for terminal, Arial (`arial.ttf`) for CRM, and Calibri (`calibri.ttf`) for spreadsheet. Rendered pixels are stored in PNG/MP4 files. **No font files are copied, embedded, or distributed in this fixture folder or source submission.** Each truth file records the installed font filename and SHA-256 to identify the environment. Font rights and terms remain with their respective owners; the dataset notice does not relicense those font files. Reproduction uses the operator's own installed fonts.

The project invokes its installed FFmpeg executable to encode media and does not distribute that executable with these fixtures. See the root model/dependency notices for the exact installed FFmpeg build's separate terms.

## Frozen artifacts and evidence

- `manifest.json` and `manifest.sha256` identify the frozen source media and annotations. Creation finished before the first OCR benchmark call.
- `media/` contains the 24 input clips; `truth/` contains independently generated annotation geometry and expected event types.
- `previews/` contains construction/visual-check PNGs, which are optional for source reproduction.
- `observations/` and `outputs/` are subsequent benchmark evidence, not inputs passed to inference. Exported observations omit recognized plaintext.
- The application receives only a media path and the fixed caller-supplied keyword. It never reads this dataset's annotations.

Run `python scripts/generate_robustness_v2.py --verify` from the project root to check hashes. Generation refuses to replace a frozen manifest. Run `python scripts/benchmark_robustness_v2.py --split dev` for development evaluation. Held-out evaluation additionally requires a recorded coordinator freeze note and must not be repeatedly used for tuning.

The original generator/evaluator code follows the project root code license. The new self-authored synthetic dataset content follows the existing sample-asset CC0 policy in `LICENSE.txt`. This applies to original authored dataset content, not third-party fonts, model weights, libraries or encoder binaries.

See `reports/evaluation_v2_method.md` and the versioned per-split reports for limitations, failure cases, actual metrics and source hashes. A successful same-model rescan is not an independent privacy guarantee.
