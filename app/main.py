"""Loopback-only web API. Run: uvicorn app.main:app --host 127.0.0.1."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
import copy
import json
import os
import shutil
import threading
import uuid
from urllib.parse import urlsplit

import cv2
from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .media import MAX_BYTES, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, inspect_media, iter_frames
from .ocr import OCR
from .paths import JOBS, ROOT, SAMPLES, safe_child
from .pipeline import Cancelled, analyze_media, export_media, validate_masks
from .session import COOKIE_NAME, SessionState

JOBS.mkdir(parents=True, exist_ok=True)
SAMPLES.mkdir(parents=True, exist_ok=True)
MAX_JOBS = 20


class Runtime:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="demosafe")
        self.jobs = {}
        self.lock = threading.RLock()
        self.closed = False

    def close(self):
        with self.lock:
            for job in self.jobs.values():
                job["_cancel"].set()
            self.closed = True
        self.executor.shutdown(wait=False, cancel_futures=True)


@asynccontextmanager
async def lifespan(app):
    if app.state.runtime.closed:
        app.state.runtime = Runtime()
    app.state.session.rotate()
    try:
        yield
    finally:
        app.state.session.invalidate()
        app.state.runtime.close()


router = APIRouter()


class RequestTooLarge(Exception):
    pass


class UploadLimitMiddleware:
    """Bound multipart bodies before Starlette can spool an unbounded upload."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST":
            return await self.app(scope, receive, send)
        limit = MAX_BYTES + 1024 * 1024  # multipart envelope overhead
        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length")
        if length and length.isdigit() and int(length) > limit:
            return await JSONResponse({"detail": "Request exceeds the 100 MB file limit"}, status_code=413)(scope, receive, send)
        consumed = 0
        async def limited_receive():
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > limit:
                    raise RequestTooLarge()
            return message
        try:
            await self.app(scope, limited_receive, send)
        except RequestTooLarge:
            await JSONResponse({"detail": "Request exceeds the 100 MB file limit"}, status_code=413)(scope, receive, send)


def worker_active(job):
    future = job.get("_future")
    return bool(job.get("_incoming") or (future is not None and not future.done()))


def public_job(state, job):
    with state.lock:
        output = copy.deepcopy({key: value for key, value in job.items() if not key.startswith("_")})
        output["events"] = [{key: value for key, value in event.items() if key != "text"}
                            for event in output.get("events", [])]
        output["worker_active"] = worker_active(job)
        return output


def get_job(state, job_id):
    with state.lock:
        if job_id not in state.jobs:
            raise HTTPException(404, "Job not found")
        return state.jobs[job_id]


def sample_catalog():
    catalog = SAMPLES / "catalog.json"
    if not catalog.exists():
        return []
    payload = json.loads(catalog.read_text(encoding="utf-8-sig"))
    return payload if isinstance(payload, list) else payload.get("samples", [])


def parse_keywords(values):
    if isinstance(values, str):
        values = values.splitlines()
    if len(values) > 30 or any(len(value) > 100 for value in values):
        raise HTTPException(422, "Use at most 30 keywords of 100 characters each")
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def allocate_job(state, filename):
    with state.lock:
        if len(state.jobs) >= MAX_JOBS:
            raise HTTPException(429, "Session job limit reached. Delete finished jobs to free a slot.")
        job_id = uuid.uuid4().hex
        directory = safe_child(JOBS, job_id)
        directory.mkdir()
        job = {"id": job_id, "status": "queued", "progress": 0.0, "filename": Path(filename).name[:200],
               "media_type": "video", "width": 0, "height": 0, "fps": 0, "duration": 0,
               "backend": OCR.backend, "model": OCR.model, "events": [], "metrics": {},
               "_directory": directory, "_cancel": threading.Event(), "_incoming": True, "_future": None}
        state.jobs[job_id] = job
        return job


def set_progress(state, job, status, value):
    with state.lock:
        if not job["_cancel"].is_set():
            job["status"] = status
            job["progress"] = round(float(value), 4)


def submit_worker(state, job, function, *args):
    with state.lock:
        job["_incoming"] = False
        job["_future"] = state.executor.submit(function, state, job, *args)


def analyze_job(state, job, source, keywords):
    try:
        if job["_cancel"].is_set():
            raise Cancelled()
        set_progress(state, job, "analyzing", 0)
        metadata = inspect_media(source)
        with state.lock:
            job.update(metadata)
            job["_source"] = source
        first_frame = next(iter_frames(source, metadata))[1]
        cv2.imwrite(str(job["_directory"] / "poster.png"), first_frame)
        analysis = analyze_media(source, keywords, lambda p: set_progress(state, job, "analyzing", p), job["_cancel"].is_set)
        with state.lock:
            if job["_cancel"].is_set():
                raise Cancelled()
            job.update(analysis.metadata)
            job.update({"status": "ready", "progress": 1, "events": analysis.events,
                        "metrics": analysis.metrics.copy(), "_analysis": analysis})
    except Cancelled:
        with state.lock:
            job["status"] = "cancelled"
    except Exception as exc:
        with state.lock:
            job["status"] = "cancelled" if job["_cancel"].is_set() else "error"
            job["error"] = str(exc) if isinstance(exc, ValueError) else f"Analysis failed ({type(exc).__name__}). Check local dependencies and file format."


def export_job(state, job, decisions, masks):
    extension = ".png" if job["media_type"] == "image" else ".mp4"
    output = job["_directory"] / ("redacted" + extension)
    try:
        report = export_media(job["_source"], output, job["_analysis"], decisions, masks,
                              lambda p: set_progress(state, job, "exporting", p), job["_cancel"].is_set)
        with state.lock:
            if job["_cancel"].is_set():
                output.unlink(missing_ok=True)
                raise Cancelled()
            report_path = job["_directory"] / "report.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            job["_output"] = output
            job["_report"] = report
            job["metrics"]["rescan"] = report["rescan"]
            job["metrics"]["export_seconds"] = report["export_seconds"]
            job["status"], job["progress"] = "done", 1
            job["export_url"] = f"/api/jobs/{job['id']}/media/redacted"
            job["report_url"] = f"/api/jobs/{job['id']}/report"
    except Cancelled:
        with state.lock:
            job["status"] = "cancelled"
    except Exception as exc:
        with state.lock:
            job["status"] = "cancelled" if job["_cancel"].is_set() else "error"
            job["error"] = str(exc) if isinstance(exc, ValueError) else f"Export failed ({type(exc).__name__}). Original media was preserved."


class BootstrapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credential: str = Field(min_length=1, max_length=128)


@router.post("/api/session")
def bootstrap_session(request: Request, body: BootstrapRequest):
    session = request.app.state.session.exchange(body.credential)
    if session is None:
        raise HTTPException(401, "Invalid local launch credential")
    response = JSONResponse({"status": "authenticated", "origin": request.app.state.session.origin})
    response.set_cookie(COOKIE_NAME, session, httponly=True, samesite="strict", secure=False, path="/")
    return response


@router.get("/api/session")
def read_session(request: Request):
    return {"status": "authenticated", "origin": request.app.state.session.origin}


@router.get("/api/health")
def health():
    return {"status": "ok", "backend": OCR.backend, "model": OCR.model, "model_loaded": OCR.loaded,
            "hardware_verified": False, "hailo_available": False, "local_only": True}


@router.get("/api/samples")
def samples():
    return {"samples": [{key: sample.get(key, "") for key in ("id", "name", "description", "url")} for sample in sample_catalog()]}


@router.post("/api/jobs")
async def create_job(request: Request, file: UploadFile = File(...), keywords: str = Form("")):
    state = request.app.state.runtime
    parsed_keywords = parse_keywords(keywords)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
        raise HTTPException(415, "Unsupported file extension")
    job = allocate_job(state, file.filename or "upload")
    source = job["_directory"] / ("original" + suffix)
    size = 0
    try:
        with source.open("wb") as destination:
            while block := await file.read(1024 * 1024):
                size += len(block)
                if size > MAX_BYTES:
                    raise HTTPException(413, "File exceeds the 100 MB limit")
                destination.write(block)
        if size == 0:
            raise HTTPException(422, "File is empty")
    except BaseException:
        source.unlink(missing_ok=True)
        with state.lock:
            state.jobs.pop(job["id"], None)
        job["_directory"].rmdir()
        raise
    finally:
        await file.close()
    submit_worker(state, job, analyze_job, source, parsed_keywords)
    return {"id": job["id"]}


class SampleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sample_id: str = Field(min_length=1, max_length=100)
    keywords: list[str] = Field(default_factory=list, max_length=30)


@router.post("/api/jobs/sample")
def create_sample_job(request: Request, body: SampleRequest):
    state = request.app.state.runtime
    sample = next((item for item in sample_catalog() if item.get("id") == body.sample_id), None)
    if sample is None:
        raise HTTPException(404, "Sample not found")
    relative = sample.get("file") or sample.get("path") or sample.get("url", "").removeprefix("/samples/")
    try:
        source = safe_child(SAMPLES, relative)
    except ValueError:
        raise HTTPException(400, "Invalid sample path")
    if not source.is_file():
        raise HTTPException(404, "Sample file not found")
    keywords = parse_keywords(body.keywords)
    job = allocate_job(state, source.name)
    copied = job["_directory"] / ("original" + source.suffix.lower())
    try:
        shutil.copyfile(source, copied)
        submit_worker(state, job, analyze_job, copied, keywords)
    except Exception:
        with state.lock:
            job["_incoming"] = False
            job["status"] = "error"
            job["error"] = "Could not prepare the sample job"
        raise HTTPException(500, "Could not prepare the sample job")
    return {"id": job["id"]}


@router.get("/api/jobs/{job_id}")
def read_job(request: Request, job_id: str):
    state = request.app.state.runtime
    return public_job(state, get_job(state, job_id))


@router.post("/api/jobs/{job_id}/cancel")
def cancel_job(request: Request, job_id: str):
    state = request.app.state.runtime
    with state.lock:
        job = get_job(state, job_id)
        if job["status"] in {"queued", "analyzing", "exporting"}:
            job["_cancel"].set()
            job["status"] = "cancelled"
    return public_job(state, job)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    redact: bool


class ManualMask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: float
    end: float
    box: list[float] = Field(min_length=4, max_length=4)


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decisions: list[Decision] = Field(default_factory=list, max_length=10000)
    manual_masks: list[ManualMask] = Field(default_factory=list, max_length=100)


@router.post("/api/jobs/{job_id}/export")
def begin_export(request: Request, job_id: str, body: ExportRequest):
    state = request.app.state.runtime
    with state.lock:
        # Lookup and admission share the deletion lock: a stale reference must
        # never schedule work after DELETE has removed this job's directory.
        job = get_job(state, job_id)
        if job["status"] not in {"ready", "done"} or worker_active(job):
            raise HTTPException(409, "Job must be ready before export")
        decisions = {item.event_id: item.redact for item in body.decisions}
        expected = {event["id"] for event in job["events"]}
        if len(decisions) != len(body.decisions) or set(decisions) != expected:
            raise HTTPException(422, "Provide exactly one explicit decision for every event")
        try:
            masks = validate_masks([item.model_dump() for item in body.manual_masks], job["_analysis"].metadata)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        job["status"], job["progress"] = "exporting", 0
        job.pop("export_url", None)
        job.pop("report_url", None)
        job.pop("_report", None)
        job.pop("_output", None)
        job["metrics"].pop("rescan", None)
        submit_worker(state, job, export_job, decisions, masks)
    return public_job(state, job)


@router.get("/api/jobs/{job_id}/report")
def get_report(request: Request, job_id: str):
    job = get_job(request.app.state.runtime, job_id)
    if job["status"] != "done" or "_report" not in job:
        raise HTTPException(404, "Report is not ready")
    return JSONResponse(job["_report"], headers={"Content-Disposition": 'attachment; filename="demosafe-report.json"'})


@router.get("/api/jobs/{job_id}/media/{kind}")
def get_media(request: Request, job_id: str, kind: str):
    job = get_job(request.app.state.runtime, job_id)
    if kind == "original":
        path = job.get("_source")
    elif kind == "poster":
        path = job["_directory"] / "poster.png"
    elif kind == "redacted" and job["status"] == "done":
        path = job.get("_output")
    else:
        raise HTTPException(404, "Media not found")
    if path is None or not path.is_file():
        raise HTTPException(404, "Media is not ready")
    try:
        path.resolve().relative_to(job["_directory"].resolve())
    except ValueError:
        raise HTTPException(400, "Invalid media path")
    content_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".mp4": "video/mp4", ".webm": "video/webm"}
    return FileResponse(path, media_type=content_types.get(path.suffix.lower(), "application/octet-stream"))


@router.delete("/api/jobs/{job_id}")
def delete_job(request: Request, job_id: str):
    state = request.app.state.runtime
    with state.lock:
        job = get_job(state, job_id)
        if worker_active(job):
            raise HTTPException(409, "Worker is still finishing. Wait until worker_active is false before deletion.")
        try:
            expected = safe_child(JOBS, job_id)
            directory = Path(job["_directory"])
            if (len(job_id) != 32 or any(c not in "0123456789abcdef" for c in job_id)
                    or expected.parent != JOBS.resolve() or directory.resolve() != expected
                    or directory.is_symlink() or directory.is_junction()):
                raise ValueError("Unexpected job directory")
            for current, dirs, files in os.walk(directory, followlinks=False):
                for name in dirs + files:
                    child = Path(current) / name
                    if child.is_symlink() or child.is_junction():
                        raise ValueError("Job directory contains a link")
                    child.resolve().relative_to(expected)
        except ValueError:
            raise HTTPException(409, "Job directory failed the deletion boundary check")
        try:
            if directory.exists():
                shutil.rmtree(directory)
        except OSError:
            raise HTTPException(409, "A job file is still open. Close media previews and retry deletion.")
        state.jobs.pop(job_id)
        return {"deleted": True, "id": job_id}


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
                               "script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                               "media-src 'self' blob:; connect-src 'self'; font-src 'self' data:; form-action 'self'",
}


def create_app(origin=None):
    application = FastAPI(title="DemoSafe", version="1.1.0", lifespan=lifespan,
                          docs_url=None, redoc_url=None, openapi_url=None)
    application.state.session = SessionState(origin or os.environ.get("DEMOSAFE_ORIGIN", "http://127.0.0.1:8765"))
    application.state.runtime = Runtime()
    application.add_middleware(UploadLimitMiddleware)

    @application.middleware("http")
    async def session_boundary(request: Request, call_next):
        session = request.app.state.session
        canonical = urlsplit(session.origin)
        origin_header = request.headers.get("origin")
        mutating = request.method not in {"GET", "HEAD", "OPTIONS"}
        if request.url.scheme != canonical.scheme or request.headers.get("host") != canonical.netloc:
            response = JSONResponse({"detail": "Use the canonical local launch URL"}, status_code=403)
        elif (mutating and origin_header != session.origin) or (origin_header and origin_header != session.origin):
            response = JSONResponse({"detail": "Request origin does not match this local server"}, status_code=403)
        elif request.url.path.startswith("/api/") and not (request.method == "POST" and request.url.path == "/api/session") and not session.authenticated(request.cookies.get(COOKIE_NAME)):
            response = JSONResponse({"detail": "Open DemoSafe using its local launcher to authenticate"}, status_code=401)
        else:
            response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    application.include_router(router)
    application.mount("/samples", StaticFiles(directory=SAMPLES), name="samples")
    static = ROOT / "app" / "static"
    static.mkdir(exist_ok=True)
    application.mount("/", StaticFiles(directory=static, html=True), name="frontend")
    return application


app = create_app()
