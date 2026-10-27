"""Ephemeral loopback authentication. No credentials are persisted by the server."""
import hashlib
import secrets
import threading
from urllib.parse import urlsplit

COOKIE_NAME = "demosafe_session"


def canonical_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
            or parsed.port is None or not 1024 <= parsed.port <= 65535):
        raise ValueError("DemoSafe origin must be an explicit http loopback origin with a port")
    expected = f"http://{parsed.hostname}:{parsed.port}"
    if value != expected:
        raise ValueError("DemoSafe origin must use canonical scheme, host and port spelling")
    return expected


class SessionState:
    def __init__(self, origin="http://127.0.0.1:8765"):
        self.origin = canonical_origin(origin)
        self._lock = threading.RLock()
        self.rotate()

    def rotate(self):
        with self._lock:
            self.bootstrap_credential = secrets.token_urlsafe(32)
            self._sessions = []
            self._valid = True

    def invalidate(self):
        with self._lock:
            self.bootstrap_credential = ""
            self._sessions.clear()
            self._valid = False

    def exchange(self, credential):
        with self._lock:
            if (not self._valid or not isinstance(credential, str) or
                    not secrets.compare_digest(credential.encode("utf-8"), self.bootstrap_credential.encode("ascii"))):
                return None
            session = secrets.token_urlsafe(32)
            self._sessions.append(hashlib.sha256(session.encode("ascii")).digest())
            self._sessions = self._sessions[-16:]
            return session

    def authenticated(self, session):
        if not session or not isinstance(session, str) or len(session) > 128:
            return False
        try:
            digest = hashlib.sha256(session.encode("ascii")).digest()
        except UnicodeEncodeError:
            return False
        with self._lock:
            return self._valid and any(secrets.compare_digest(digest, candidate) for candidate in self._sessions)
