import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Collection, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CHART = ROOT / "chart"
DEPLOYMENT = ROOT / "deployment.json"
ORGANIZATION = ROOT / "organization.json"
VALUES_TEMPLATE = CHART / "values.yaml.tmpl"
STATE_DIR = Path("/var/lib/element-chat")
STATE_FILE = STATE_DIR / "installation.json"
IMPORT_DIR = STATE_DIR / "imports"
RELEASE = "ess"
NAMESPACE = "ess"


class Failure(RuntimeError):
    pass


def run(
    args: Iterable[object],
    *,
    input_text: str | None = None,
    env: Mapping[str, str] | None = None,
    capture: bool = False,
    timeout: float | None = None,
) -> str:
    arguments = [str(arg) for arg in args]
    displayed = arguments.copy()
    secrets_to_redact: list[str] = []
    for index, argument in enumerate(arguments[:-1]):
        if argument == "--password":
            secrets_to_redact.append(arguments[index + 1])
            displayed[index + 1] = "<redacted>"
    try:
        result = subprocess.run(
            arguments,
            check=False,
            text=True,
            input=input_text,
            env=env,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise Failure(f"Command timed out: {' '.join(displayed)}") from error
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip()
        for secret in secrets_to_redact:
            detail = detail.replace(secret, "<redacted>")
        raise Failure(
            f"Command failed ({result.returncode}): {' '.join(displayed)}\n{detail}"
        )
    return (
        ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        if capture
        else ""
    )


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, value: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.chmod(mode)
    temporary.replace(path)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as error:
        raise Failure(f"Required file does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise Failure(f"Invalid JSON in {path}: {error}") from error


def require_root() -> None:
    if os.geteuid() != 0:
        raise Failure("Run this operation as root.")


def command_output(args: Iterable[object]) -> str:
    return run(args, capture=True)


def systemd_active(service: str) -> bool:
    result = subprocess.run(["systemctl", "is-active", "--quiet", service], check=False)
    return result.returncode == 0


def wait_for(
    description: str,
    check: Callable[[], object],
    timeout: float = 300,
    interval: float = 3,
) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except Exception as error:
            last_error = error
        time.sleep(interval)
    suffix = f": {last_error}" if last_error else ""
    raise Failure(f"Timed out waiting for {description}{suffix}")


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "Element-Deployment/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data: bytes = response.read()
        return data


def asset_checksum(*names: str) -> str:
    digest = hashlib.sha256()
    for name in names:
        digest.update((CHART / "files" / name).read_bytes())
    return digest.hexdigest()


def request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    body: Any = None,
    headers: Mapping[str, str] | None = None,
    allowed: Collection[int] = (200,),
) -> Any:
    request_headers = {"User-Agent": "Element-Deployment/1.0", **(headers or {})}
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        request_headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        payload = error.read()
        status = error.code
        content_type = error.headers.get("Content-Type", "")
    if status not in allowed:
        detail = payload.decode(errors="replace")[:500]
        raise Failure(f"HTTP {status} from {url}: {detail}")
    if not payload:
        return None
    if "json" in content_type or payload.lstrip().startswith((b"{", b"[")):
        return json.loads(payload)
    return payload.decode(errors="replace")
