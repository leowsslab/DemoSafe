"""HTTP and worker lifecycle tests. No OCR model behavior is replaced or retuned."""
import threading
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import allocate_job, submit_worker, create_app
from app.session import COOKIE_NAME, SessionState

ORIGIN = "http://127.0.0.1:8765"


def idle_job(local_app):
    job = allocate_job(local_app.state.runtime, "private-input.png")
    job["status"] = "ready"
    job["_incoming"] = False
    original = job["_directory"] / "original.png"
    original.write_bytes(b"private media")
    job["_source"] = original
    return job


@pytest.mark.parametrize("path", ["/api/session", "/api/health", "/api/samples", "/api/jobs/unknown", "/api/jobs/unknown/report"])
def test_unauthenticated_api_reads_are_denied(unauth_client, path):
    assert unauth_client.get(path).status_code == 401


@pytest.mark.parametrize("kind", ["original", "poster", "redacted"])
def test_media_requires_session_even_when_job_exists(local_app, unauth_client, kind):
    job = idle_job(local_app)
    assert unauth_client.get(f"/api/jobs/{job['id']}/media/{kind}").status_code == 401


def test_wrong_bootstrap_never_authenticates(unauth_client):
    for credential in ["wrong-token", "非ASCII也不應造成500"]:
        response = unauth_client.post("/api/session", headers={"Origin": ORIGIN}, json={"credential": credential})
        assert response.status_code == 401
        assert "set-cookie" not in response.headers
        assert credential not in response.text
    assert unauth_client.get("/api/health").status_code == 401


@pytest.mark.parametrize("origin", [None, "null", "http://127.0.0.1:8766", "http://localhost:8765", "https://127.0.0.1:8765", "https://evil.example"])
def test_bootstrap_requires_exact_origin(local_app, unauth_client, origin):
    headers = {} if origin is None else {"Origin": origin}
    response = unauth_client.post("/api/session", headers=headers, json={"credential": local_app.state.session.bootstrap_credential})
    assert response.status_code == 403


def test_session_cookie_is_httponly_strict_and_credential_is_not_returned(local_app, unauth_client):
    credential = local_app.state.session.bootstrap_credential
    response = unauth_client.post("/api/session", headers={"Origin": ORIGIN}, json={"credential": credential})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert "Domain=" not in cookie
    assert credential not in cookie and credential not in response.text
    assert unauth_client.get("/api/session").json()["status"] == "authenticated"


@pytest.mark.parametrize("method,path", [("POST", "/api/jobs/sample"), ("POST", "/api/jobs/missing/cancel"), ("DELETE", "/api/jobs/missing")])
def test_authenticated_mutations_reject_other_local_ports(authed_client, method, path):
    response = authed_client.request(method, path, headers={"Origin": "http://127.0.0.1:9000"}, json={"sample_id": "demo"})
    assert response.status_code == 403


def test_authenticated_mutation_rejects_missing_origin(authed_client):
    del authed_client.headers["Origin"]
    assert authed_client.delete("/api/jobs/missing").status_code == 403


def test_wrong_host_is_rejected(authed_client):
    assert authed_client.get("/api/health", headers={"Host": "localhost:8765"}).status_code == 403
    assert authed_client.get("/api/health", headers={"Host": "127.0.0.1:9000"}).status_code == 403


def test_restart_invalidates_cookie_and_bootstrap(local_app):
    with TestClient(local_app, base_url=ORIGIN) as first:
        credential = local_app.state.session.bootstrap_credential
        first.post("/api/session", headers={"Origin": ORIGIN}, json={"credential": credential})
        old_cookie = first.cookies.get(COOKIE_NAME)
        assert first.get("/api/health").status_code == 200
    assert not local_app.state.session.authenticated(old_cookie)
    with TestClient(local_app, base_url=ORIGIN) as restarted:
        restarted.cookies.set(COOKIE_NAME, old_cookie)
        assert restarted.get("/api/health").status_code == 401
        assert restarted.post("/api/session", headers={"Origin": ORIGIN}, json={"credential": credential}).status_code == 401
        assert local_app.state.session.bootstrap_credential != credential


def test_separate_server_instances_do_not_share_sessions():
    first, second = SessionState(), SessionState()
    session = first.exchange(first.bootstrap_credential)
    assert first.authenticated(session)
    assert not second.authenticated(session)


def test_response_omits_plaintext_without_mutating_analysis(local_app, authed_client):
    job = idle_job(local_app)
    event = {"id": "e1", "type": "email", "text": "private@example.com", "display": "Email address ••••", "box": [0, 0, 10, 10]}
    job["events"] = [event]
    response = authed_client.get(f"/api/jobs/{job['id']}")
    assert response.status_code == 200
    assert "private@example.com" not in response.text
    assert "text" not in response.json()["events"][0]
    assert event["text"] == "private@example.com"
    assert response.json()["worker_active"] is False


def test_cancelled_actual_worker_must_finish_before_delete(local_app, authed_client):
    state = local_app.state.runtime
    job = allocate_job(state, "held.png")
    (job["_directory"] / "original.png").write_bytes(b"keep until done")
    started, release = threading.Event(), threading.Event()
    def blocking_worker(state, job):
        with state.lock:
            job["status"] = "analyzing"
        started.set()
        release.wait(5)
    submit_worker(state, job, blocking_worker)
    try:
        assert started.wait(2)
        cancelled = authed_client.post(f"/api/jobs/{job['id']}/cancel").json()
        assert cancelled["status"] == "cancelled" and cancelled["worker_active"] is True
        assert authed_client.delete(f"/api/jobs/{job['id']}").status_code == 409
        assert job["_directory"].exists()
    finally:
        release.set()
        job["_future"].result(timeout=2)
    assert authed_client.get(f"/api/jobs/{job['id']}").json()["worker_active"] is False
    assert authed_client.delete(f"/api/jobs/{job['id']}").status_code == 200
    assert not job["_directory"].exists()
    assert authed_client.get(f"/api/jobs/{job['id']}").status_code == 404


def test_upload_in_progress_cannot_be_deleted(local_app, authed_client):
    job = allocate_job(local_app.state.runtime, "incoming.png")
    job["status"] = "cancelled"
    assert authed_client.get(f"/api/jobs/{job['id']}").json()["worker_active"] is True
    assert authed_client.delete(f"/api/jobs/{job['id']}").status_code == 409


def test_premature_done_status_does_not_allow_reexport(local_app, authed_client):
    job = idle_job(local_app)
    started, release = threading.Event(), threading.Event()
    def worker(state, job):
        with state.lock:
            job["status"] = "done"
        started.set()
        release.wait(5)
    submit_worker(local_app.state.runtime, job, worker)
    try:
        assert started.wait(2)
        response = authed_client.post(f"/api/jobs/{job['id']}/export", json={"decisions": [], "manual_masks": []})
        assert response.status_code == 409
        assert authed_client.delete(f"/api/jobs/{job['id']}").status_code == 409
    finally:
        release.set()
        job["_future"].result(timeout=2)


def test_delete_removes_only_selected_job_and_cannot_serve_it(local_app, authed_client):
    job, other = idle_job(local_app), idle_job(local_app)
    legacy = job["_directory"].parent / "legacy-unindexed"
    legacy.mkdir()
    (legacy / "keep.txt").write_text("keep")
    assert authed_client.get(f"/api/jobs/{job['id']}/media/original").status_code == 200
    response = authed_client.delete(f"/api/jobs/{job['id']}")
    assert response.json() == {"deleted": True, "id": job["id"]}
    assert not job["_directory"].exists()
    assert other["_directory"].exists() and legacy.exists()
    assert authed_client.get(f"/api/jobs/{job['id']}/media/original").status_code == 404
    assert authed_client.delete(f"/api/jobs/{job['id']}").status_code == 404


def test_delete_refuses_forged_directory_boundary(local_app, authed_client, tmp_path):
    job = idle_job(local_app)
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("preserve")
    job["_directory"] = outside
    assert authed_client.delete(f"/api/jobs/{job['id']}").status_code == 409
    assert marker.read_text() == "preserve"


def test_security_headers_also_cover_auth_errors(unauth_client):
    response = unauth_client.get("/api/health")
    assert response.headers["x-frame-options"] == "DENY"
    policy = response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in policy and "script-src 'self'" in policy
    assert "'unsafe-inline'" not in policy.split("script-src ", 1)[1].split(";", 1)[0]
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"


def test_export_admission_and_delete_cannot_use_a_stale_job(local_app, monkeypatch):
    """Pause export after lookup; a concurrent delete cannot slip into the gap."""
    import app.main as main
    from app.pipeline import Analysis
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace
    from fastapi import HTTPException
    job = idle_job(local_app)
    job["_analysis"] = Analysis(metadata={})
    request = SimpleNamespace(app=local_app)
    lookup_reached, release_lookup = threading.Event(), threading.Event()
    delete_started, delete_finished, release_worker = threading.Event(), threading.Event(), threading.Event()
    original_lookup = main.get_job

    def paused_lookup(state, job_id):
        result = original_lookup(state, job_id)
        if threading.current_thread().name.startswith("export-admission"):
            lookup_reached.set()
            assert release_lookup.wait(3)
        return result

    def held_export(state, job, decisions, masks):
        release_worker.wait(5)

    def delete_concurrently():
        delete_started.set()
        try:
            return main.delete_job(request, job["id"])
        finally:
            delete_finished.set()

    monkeypatch.setattr(main, "get_job", paused_lookup)
    monkeypatch.setattr(main, "export_job", held_export)
    export_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="export-admission")
    delete_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="delete-admission")
    try:
        exporting = export_pool.submit(main.begin_export, request, job["id"], main.ExportRequest())
        assert lookup_reached.wait(2)
        deleting = delete_pool.submit(delete_concurrently)
        assert delete_started.wait(2)
        assert not delete_finished.wait(0.15), "Delete must wait for export admission's lock"
        release_lookup.set()
        assert exporting.result(timeout=2)["worker_active"] is True
        with pytest.raises(HTTPException) as error:
            deleting.result(timeout=2)
        assert error.value.status_code == 409
        assert job["_directory"].exists()
    finally:
        release_lookup.set()
        release_worker.set()
        export_pool.shutdown(wait=True)
        delete_pool.shutdown(wait=True)
        if job.get("_future"):
            job["_future"].result(timeout=2)
