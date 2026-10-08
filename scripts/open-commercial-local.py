"""Open a self-contained commercial-v1 environment for manual browser testing.

This uses disposable PostgreSQL, synthetic OIDC/model responses, the accepted
Docker image, and the controlled deployment provider fixture. It is for local
manual product testing only; it does not prove live Vercel deployment.
"""
from __future__ import annotations

import asyncio
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy import create_engine

from test_database import free_port, test_database

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--production', action='store_true', help='Review the existing production build instead of starting Next dev.')
parser.add_argument('--no-open', action='store_true', help='Print the URL without opening the default browser.')
args = parser.parse_args()

root = Path(__file__).resolve().parents[1]
api_root = root / "apps/api"
sys.path.insert(0,str(api_root))
from scripts.disposable_runtimes import cleanup_disposable
report_path = root / ".runtime/production-acceptance-report.json"


def fail(message: str) -> "NoReturn":
    raise SystemExit(message)


def docker_socket() -> str:
    explicit = os.environ.get("F01_DOCKER_SOCKET")
    candidates = [
        Path(explicit).expanduser() if explicit else None,
        Path.home() / ".docker/run/docker.sock",
        Path("/var/run/docker.sock"),
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate)
    fail("Docker socket not found. Start Docker Desktop and retry.")


def wait_http(url: str, attempts: int = 200) -> None:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return
        except OSError:
            time.sleep(0.1)
    fail(f"Service did not become ready: {url}")


def terminate(process: subprocess.Popen[bytes] | subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def post_step(api: str, gateway: str, kind: str) -> None:
    request = urllib.request.Request(
        f"{api}/test/commercial-step",
        data=json.dumps({"kind": kind}).encode(),
        headers={
            "Authorization": f"Bearer {gateway}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300):
            pass
    except urllib.error.HTTPError as exc:
        if exc.code not in (409, 422):
            raise
    except OSError:
        pass


if not report_path.is_file():
    fail(
        "Missing .runtime/production-acceptance-report.json. "
        "Run exact-image production acceptance first."
    )

accepted = json.loads(report_path.read_text())
if any(
    accepted.get(key) != "passed"
    for key in ("docker_containment", "docker_journey", "production_packaging")
):
    fail("Production acceptance report is not fully passing.")

image_id = accepted.get("image_id")
if not isinstance(image_id, str) or not image_id.startswith("sha256:"):
    fail("Production acceptance report has no exact image ID.")

socket_path = docker_socket()
gateway = "synthetic-commercial-local-gateway-12345678901234567890"
api_port, web_port, preview_port = free_port(), free_port(), free_port()
api_url = f"http://127.0.0.1:{api_port}"
web_url = f"http://127.0.0.1:{web_port}"

processes: list[subprocess.Popen[bytes] | subprocess.Popen[str]] = []
stop = threading.Event()
thread: threading.Thread | None = None
cleanup_ok = False

with test_database(root) as database:
    config = Config(str(api_root / "alembic.ini"))
    engine = create_engine(database)
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    engine.dispose()

    env = {
        **os.environ,
        "APP_ENV": "test",
        "AUTH_MODE": "oidc",
        "EXECUTION_MODE": "real",
        "REAL_EXECUTION_ENABLED": "true",
        "RELEASE_ENABLED": "true",
        "SIMULATION_RUNNER_ENABLED": "false",
        "DATABASE_URL": database,
        "AUTH_GATEWAY_TOKEN": gateway,
        "SESSION_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "OIDC_ISSUER": f"{api_url}/oidc",
        "OIDC_AUTHORIZATION_URL": f"{api_url}/oidc/authorize",
        "OIDC_TOKEN_URL": f"{api_url}/oidc/token",
        "OIDC_JWKS_URL": f"{api_url}/oidc/jwks",
        "OIDC_CLIENT_ID": "fixture-client",
        "OIDC_CLIENT_SECRET": "synthetic-fixture-client-secret",
        "OIDC_API_AUDIENCE": "fixture-api",
        "OIDC_REDIRECT_URI": f"{web_url}/api/auth/callback",
        "OPENAI_API_KEY": "synthetic-commercial-local-provider-key",
        "PLANNING_TIMEOUT_SECONDS": "10",
        "PLANNING_REQUESTS_PER_MINUTE": "20",
        "SANDBOX_IMAGE_ID": image_id,
        "PRODUCTION_IMAGE_ID": image_id,
        "SANDBOX_ACCEPTANCE_REPORT": str(report_path),
        "PRODUCTION_ACCEPTANCE_REPORT": str(report_path),
        "SANDBOX_SOCKET": socket_path,
        "PREVIEW_ORIGIN": f"http://localhost:{preview_port}",
        "FACTORY_ORIGIN": web_url,
        "API_INTERNAL_URL": api_url,
        "NEXT_PUBLIC_APP_URL": web_url,
    }

    runtime = root / ".runtime"
    runtime.mkdir(exist_ok=True)
    log = (runtime / "commercial-local.log").open("w")

    try:
        api = subprocess.Popen(
            [
                str(api_root / ".venv/bin/python"),
                "-m",
                "uvicorn",
                "commercial_browser_fixture:app",
                "--app-dir",
                str(api_root / "tests"),
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
            ],
            cwd=api_root,
            env=env,
            stdout=log,
            stderr=log,
        )
        processes.append(api)
        wait_http(f"{api_url}/v1/health/live")

        preview = subprocess.Popen(
            [
                str(api_root / ".venv/bin/python"),
                "-m",
                "uvicorn",
                "f01.execution.preview_gateway:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(preview_port),
            ],
            cwd=api_root,
            env={**env, "F01_PREVIEW_PORT": str(preview_port)},
            stdout=log,
            stderr=log,
        )
        processes.append(preview)

        if not (root / "node_modules").exists():
            subprocess.run(["pnpm", "install", "--frozen-lockfile"], cwd=root, check=True)

        web = subprocess.Popen(
            [
                "pnpm",
                "--filter",
                "@f01/web",
                "start" if args.production else "dev",
                "--hostname",
                "127.0.0.1",
                "--port",
                str(web_port),
            ],
            cwd=root,
            env=env,
            stdout=log,
            stderr=log,
        )
        processes.append(web)
        wait_http(web_url)

        def workers() -> None:
            while not stop.is_set():
                for kind in ("build", "target", "package", "release"):
                    if stop.is_set():
                        return
                    post_step(api_url, gateway, kind)
                stop.wait(0.75)

        thread = threading.Thread(target=workers, daemon=True)
        thread.start()

        print()
        print("F01 commercial-v1 manual test is ready.")
        print(f"Open: {web_url}")
        print("Use the test sign-in, then try:")
        print("Create -> Plan -> Approve -> Build -> Preview -> Deploy -> Modify -> Redeploy")
        print("Docker execution is real; model and deployment provider are controlled fixtures.")
        print("Press Ctrl+C here when finished.")
        print(f"Logs: {runtime / 'commercial-local.log'}")
        if not args.no_open: webbrowser.open(web_url)

        while True:
            time.sleep(1)
            dead = [p for p in processes if p.poll() is not None]
            if dead:
                fail(
                    "A local service exited unexpectedly. "
                    f"Inspect {runtime / 'commercial-local.log'}."
                )
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        for process in reversed(processes):
            terminate(process)
        if thread: thread.join(timeout=5)
        try:
            removed=asyncio.run(cleanup_disposable(database,socket_path,image_id))
            print(f'Disposable runtime cleanup confirmed: {removed} containers removed.')
            cleanup_ok=True
        except Exception:
            print('Disposable runtime cleanup needs attention. No clean-shutdown claim; inspect this test environment.')
        log.close()

print("F01 commercial-v1 local test stopped cleanly." if cleanup_ok else "F01 local services stopped; runtime cleanup is unconfirmed.")
if not cleanup_ok:raise SystemExit(1)
