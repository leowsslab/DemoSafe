# DemoSafe implementation contract

Local-only Python FastAPI + static HTML/JS. No outbound inference. Working folder demosafe.

## Start and authentication

- Start with `scripts/start.ps1` or `.venv/Scripts/python.exe scripts/launch.py`. Default canonical origin is exactly `http://127.0.0.1:8765`; `--port` changes the canonical port and listening port together.
- The launcher waits for this process's server to start, then opens `/#bootstrap=<random-credential>`. It never prints that credential. `--no-browser --launch-info <new-OS-temp-file.json>` supplies a controlled automation handshake `{origin,url,pid}`; the file must be outside the package and is removed on normal shutdown.
- Frontend must capture the `bootstrap` fragment and immediately remove it with `history.replaceState` before requests or rendering. It sends `POST /api/session` JSON `{credential}`. Browser sends its exact Origin; server verifies both that Origin and credential.
- A successful bootstrap returns `{status:'authenticated',origin}` and a host-only HttpOnly SameSite=Strict session cookie. HTTP loopback is used, so the cookie does not claim the Secure flag. No client-side token storage is needed. Credentials and server session state rotate on startup and invalidate on shutdown.
- With no fragment, frontend calls `GET /api/session` to check an existing cookie. On401, disable data actions and explain that the local launcher is required. API401 never contains media or OCR plaintext.
- Every `/api/*` route except `POST /api/session` requires a cookie. Every state mutation, including bootstrap, requires an Origin equal to the configured scheme-host-port. Other localhost ports and host aliases are rejected. Host/scheme checks cover static routes too.
- CSP restricts scripts to local files, allows required inline styles, blocks objects and framing; `X-Frame-Options: DENY`, no-referrer, and same-origin resource policy also apply. No remote font, script, or voice service is used by this app.

## API

- POST /api/session JSON {credential}: {status:'authenticated',origin}; sets the local cookie.
- GET /api/session: {status:'authenticated',origin}, or401.
- GET /api/health: {status, backend, model, hardware_verified:false}
- GET /api/samples: {samples:[{id,name,description,url}]}
- POST /api/jobs multipart file plus optional keywords (newline-delimited): {id}
- POST /api/jobs/sample JSON {sample_id,keywords:[]}: {id}
- GET /api/jobs/{id}: job object below.
- POST /api/jobs/{id}/cancel
- DELETE /api/jobs/{id}: {deleted:true,id};409 until incoming upload and actual worker Future have completed, even when visible status is cancelled/done. Removes only that job directory and in-memory record; later reads return404.
- POST /api/jobs/{id}/export JSON {decisions:[{event_id,redact:true}],manual_masks:[{start,end,box:[x1,y1,x2,y2]}]}: schedules export, returns job.
- GET /api/jobs/{id}/report: safe export report, never raw secrets.
- GET /api/jobs/{id}/media/{kind} for kind original,redacted,poster. Use video/mp4 for video.

Job: {id,status:'queued'|'analyzing'|'ready'|'exporting'|'done'|'cancelled'|'error',worker_active:boolean,progress:0..1,filename,media_type:'image'|'video',width,height,fps,duration,backend,model,events:[],metrics:{},error?,export_url?,report_url?}
Event: {id,type:'email'|'phone'|'token'|'custom',display (masked display),start,end,box:[x1,y1,x2,y2],confidence,redact:true}. Public responses never include `event.text`; internal OCR analysis is preserved. Coordinates in original image pixels. end exclusive. Original plaintext is also absent from the downloadable report.

The frontend must keep polling while `worker_active` is true, including after cancelled/done statuses. Disable delete until it becomes false. The server independently enforces this with the actual Future, not only the status label. Export also requires a ready/done job with no active Future.

## Implementation boundaries
- CPU baseline RapidOCR ONNX using shipped Paddle OCR models; label actual model/backend honestly. No fake inference and no truth-data input.
- Hailo adapter contract only: never claim working without device. CPU fallback is explicit.
- Max 60 sec, 1920x1080, 30fps input; images max 1920x1080. Silence video output by default.
- Decode all frames; exact-pixel hashes can reuse OCR. Aggregate events only when spatially and temporally overlapping. Keep per-frame boxes for output masking.
- Bounded one active worker. Preserve originals. Cancellation/error must not become ready/done.
- Artifacts under data/jobs. Samples generated under data/samples; generator truth separate in data/benchmark_truth.
- Bind loopback only. Restrict file paths to job root; allowlist media kinds. Deletion verifies the exact direct child job directory, rejects links/junctions, and leaves unindexed legacy folders untouched.

Ownership: backend agent app/*.py and tests core; frontend agent app/static only; benchmark agent scripts/generate_samples.py and scripts/benchmark.py plus own tests; root environment/media/docs/deck/integration.
