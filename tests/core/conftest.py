import pytest
from fastapi.testclient import TestClient

ORIGIN = "http://127.0.0.1:8765"


@pytest.fixture
def local_app(tmp_path, monkeypatch):
    import app.main as main
    job_root = tmp_path / "jobs"
    job_root.mkdir()
    monkeypatch.setattr(main, "JOBS", job_root)
    application = main.create_app(ORIGIN)
    yield application
    application.state.session.invalidate()
    application.state.runtime.close()


@pytest.fixture
def unauth_client(local_app):
    with TestClient(local_app, base_url=ORIGIN) as client:
        yield client


@pytest.fixture
def authed_client(unauth_client, local_app):
    unauth_client.headers["Origin"] = ORIGIN
    response = unauth_client.post("/api/session", json={"credential": local_app.state.session.bootstrap_credential})
    assert response.status_code == 200
    yield unauth_client
