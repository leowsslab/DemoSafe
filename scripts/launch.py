"""Launch the local server without writing its credential to terminal logs."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def validate_launch_info_path(value):
    path = Path(value).expanduser().resolve()
    try:
        path.relative_to(Path(tempfile.gettempdir()).resolve())
    except ValueError as exc:
        raise ValueError("Launch-info must be a new file in the current user's OS temporary directory") from exc
    try:
        path.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise ValueError("Launch-info cannot be inside the project/package")
    if path.exists():
        raise ValueError("Launch-info path already exists; choose a new temporary filename")
    return path


def main():
    parser = argparse.ArgumentParser(description="Start DemoSafe with a private browser bootstrap.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="Use only with --launch-info for controlled automation")
    parser.add_argument("--launch-info", help="Write launch URL to a NEW OS-temp JSON file; never log its contents")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Port must be between 1024 and 65535")
    if args.no_browser and not args.launch_info:
        parser.error("--no-browser requires --launch-info to deliver the private launch credential")
    try:
        info_path = validate_launch_info_path(args.launch_info) if args.launch_info else None
    except ValueError as exc:
        parser.error(str(exc))
    origin = f"http://127.0.0.1:{args.port}"
    import uvicorn
    from app.main import create_app
    app = create_app(origin)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning"))
    written = threading.Event()
    delivery_error = threading.Event()

    def deliver_when_ready():
        while not server.started:
            if server.should_exit:
                return
            time.sleep(0.05)
        url = origin + "/#bootstrap=" + app.state.session.bootstrap_credential
        try:
            if info_path:
                # O_EXCL avoids overwriting an existing file or following a substituted symlink.
                handle = os.open(str(info_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(handle, "w", encoding="utf-8") as destination:
                    json.dump({"origin": origin, "url": url, "pid": os.getpid()}, destination)
                written.set()
            if not args.no_browser and not webbrowser.open(url, new=2):
                raise RuntimeError("Default browser could not be opened")
            print(f"DemoSafe is ready at {origin}. Local authentication was delivered privately.", flush=True)
        except Exception:
            # Never print the exception: a browser exception can contain the credential URL.
            print("Could not deliver the private launch URL. Check the default browser or temporary-file permissions.", file=sys.stderr, flush=True)
            delivery_error.set()
            server.should_exit = True

    thread = threading.Thread(target=deliver_when_ready, daemon=True, name="demosafe-launch")
    thread.start()
    try:
        server.run()
    finally:
        if info_path and written.is_set():
            info_path.unlink(missing_ok=True)
    return 1 if delivery_error.is_set() else 0


if __name__ == "__main__":
    raise SystemExit(main())
