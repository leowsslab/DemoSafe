# DemoSafe interface v3 design notes

The interface is a media-review workstation: a quiet wordmark, restrained source intake, a large dark media surface, and a clearly ordered decision inspector. The former marketing hero, shield branding, pill badges, rounded panel grid, and decorative color gradients are removed.

## Visual system

- Warm paper `#F4F2EC`, graphite `#171918`, fine neutral rules, restrained vermilion `#D66545` for active emphasis. Normal secondary text uses darker `#62665F`; the brighter accent is not used for small text.
- Same-origin IBM Plex Sans variable and IBM Plex Mono regular/medium, with Segoe UI / Consolas fallbacks. No CDN requests, framework, or new network runtime.
- Flat regions, 2 px control corners, numeric/time metadata in mono, sentence-case labels, and visible keyboard focus. Reduced-motion, more-contrast, and forced-colors treatments are included.

## Main selectors and behavior

- `.site-header`, `.brand`, `.workspace-masthead`, `.workflow`: compact identity and context. The intake masthead disappears when intake is hidden.
- `.intake-grid`, `.dropzone`, `.intake-lead`, `.sample-section`, `.setup-panel`: one source area plus one detection setup column; file limits and fictional sample status remain explicit.
- `.review-grid`, `.media-column`, `.preview-grid`, `.media-frame`: source-first display, true image aspect ratio, and a viewport-based display cap. The image/video and SVG overlay remain within the same frame. Comparison uses two panes, stacking on narrow phones.
- `.findings-panel`, `.finding-item`, `.decision-summary`, `.export-area`: ordered inspection, checkbox decisions, compact numeric totals, then export/download.
- `.manual-section`, `.manual-editor`, `.coordinate-editor`: existing timed mask and keyboard rectangle controls retained below the source.
- `.verification`, `.bottom-row`: explicit rescan limitation and human-review requirement; no privacy guarantee is added.

## Preservation and verification

The immutable pre-redesign source snapshot is `build/interface-v2-snapshot` with SHA-256 manifest. All 91 existing IDs, each element type, and protected form/media/ARIA control attributes are retained. Callback wiring, state, authentication, requests, OCR, export, and deletion logic are unchanged. JavaScript edits are limited to UI copy and two CSS aspect-ratio custom properties.

`reports/interface_static_validation_v3.json` records the static checks and text contrast values. The coordinator owns real-browser functional validation and captures at 1440 × 900, 1266 × 890, and narrow width. Backend/OCR/evaluation evidence was not modified for this design change.
