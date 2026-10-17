import hashlib
import io
import json
import os
import platform
import re
import secrets
import shutil
import tarfile
import urllib.parse
from collections.abc import Callable, Collection
from pathlib import Path
from typing import Any

from .chart import rendered_values, validate
from .config import load_configuration, load_deployment
from .support import (
    CHART,
    NAMESPACE,
    RELEASE,
    STATE_DIR,
    STATE_FILE,
    Failure,
    asset_checksum,
    command_output,
    download,
    load_json,
    request,
    run,
    systemd_active,
    timestamp,
    wait_for,
    write_json,
)

State = dict[str, Any]

K3S_VERSION = "v1.36.2+k3s1"
TOOLS = {
    "helm": {
        "version": "v4.2.3",
        "url": "https://get.helm.sh/helm-v4.2.3-linux-amd64.tar.gz",
        "sha256": "e9b88b4ee95b18c706839c28d3a0220e5bc470e9cd9262410c90793c45ff8b7c",
        "member": "linux-amd64/helm",
    },
    "kubectl": {
        "version": "v1.36.2",
        "url": "https://dl.k8s.io/v1.36.2/bin/linux/amd64/kubectl",
        "sha256": "1e9045ec32bea85da43de85f0065358529ea7c7a152eca78154fba5b58c27d82",
    },
    "cloudflared": {
        "version": "2026.7.2",
        "url": "https://github.com/cloudflare/cloudflared/releases/download/2026.7.2/cloudflared-linux-amd64",
        "sha256": "ec905ea7b7e327ff8abdde8cb64697a2152de74dbcdbf6aec9db8364eb3886cd",
    },
}
PHASES = (
    "preflight",
    "tools",
    "k3s",
    "tunnel",
    "application",
    "organization",
    "verify",
)


def ensure_host_requirements() -> None:
    os_release: dict[str, str] = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            os_release[key] = value.strip('"')
    if os_release.get("ID") != "ubuntu" or os_release.get("VERSION_ID") != "26.04":
        raise Failure("This installer supports Ubuntu 26.04 only.")
    if platform.machine() != "x86_64":
        raise Failure("This installer supports x86_64 only.")
    memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    if memory < 7_500_000_000:
        raise Failure("At least 8 GB of RAM is required.")
    if shutil.disk_usage("/").free < 30_000_000_000:
        raise Failure("At least 30 GB of free disk space is required.")


def fresh_host_must_be_empty() -> None:
    conflicts: list[str] = []
    if systemd_active("k3s") or Path("/etc/rancher/k3s/k3s.yaml").exists():
        conflicts.append("k3s")
    if systemd_active("cloudflared") or Path("/etc/cloudflared/token").exists():
        conflicts.append("cloudflared")
    if conflicts:
        raise Failure("Existing infrastructure found: " + ", ".join(conflicts))


def install_tool(name: str, tool: dict[str, str]) -> None:
    archive = download(tool["url"])
    if hashlib.sha256(archive).hexdigest() != tool["sha256"]:
        raise Failure(f"Checksum mismatch while downloading {name}.")
    target = Path("/usr/local/bin") / name
    temporary = target.with_suffix(".tmp")
    if "member" in tool:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            source = bundle.extractfile(tool["member"])
            if source is None:
                raise Failure(f"The {name} archive does not contain its binary.")
            temporary.write_bytes(source.read())
    else:
        temporary.write_bytes(archive)
    temporary.chmod(0o755)
    temporary.replace(target)


def phase_preflight(state: State) -> None:
    ensure_host_requirements()
    fresh_host_must_be_empty()
    load_configuration()


def phase_tools(state: State) -> None:
    for name, tool in TOOLS.items():
        install_tool(name, tool)
    actual = {
        "helm": command_output(["helm", "version", "--short"]),
        "kubectl": command_output(["kubectl", "version", "--client", "--output=json"]),
        "cloudflared": command_output(["cloudflared", "--version"]),
    }
    actual["kubectl"] = json.loads(actual["kubectl"])["clientVersion"]["gitVersion"]
    for name, tool in TOOLS.items():
        if tool["version"] not in actual[name]:
            raise Failure(f"Expected {name} {tool['version']}; got {actual[name]}")
    installer = STATE_DIR / "k3s-install.sh"
    installer.write_bytes(download("https://get.k3s.io"))
    installer.chmod(0o700)
    validate(*load_configuration())


def phase_k3s(state: State) -> None:
    installer_path = STATE_DIR / "k3s-install.sh"
    if not installer_path.is_file():
        raise Failure("The prepared k3s installer is missing.")
    env = os.environ.copy()
    env["INSTALL_K3S_VERSION"] = K3S_VERSION
    run(
        ["sh", "-s", "-", "server"],
        input_text=installer_path.read_text(),
        env=env,
        timeout=600,
    )
    wait_for("k3s", lambda: systemd_active("k3s"), timeout=120)
    wait_for(
        "the Kubernetes node",
        lambda: (
            " Ready "
            in " " + command_output(["kubectl", "get", "nodes", "--no-headers"]) + " "
        ),
        timeout=300,
    )
    if K3S_VERSION.removeprefix("v") not in command_output(["k3s", "--version"]):
        raise Failure("k3s installed a version different from the pinned version.")
    wait_for(
        "Traefik",
        lambda: (
            command_output(
                [
                    "kubectl",
                    "-n",
                    "kube-system",
                    "get",
                    "deployment",
                    "traefik",
                    "-o",
                    "jsonpath={.status.readyReplicas}",
                ]
            )
            == "1"
        ),
        timeout=300,
    )
    installer_path.unlink()


def phase_tunnel(state: State) -> None:
    deployment = load_deployment()
    print(
        "Create a remotely managed Cloudflare Tunnel and configure these public hostnames:"
    )
    for url in deployment["urls"].values():
        print(f"  {urllib.parse.urlparse(url).hostname} -> http://localhost:80")
    print("Add a final catch-all rule with service http_status:404.")
    import getpass

    token = getpass.getpass("Cloudflare Tunnel token: ").strip()
    if len(token) < 80 or any(character.isspace() for character in token):
        raise Failure("The Cloudflare Tunnel token is invalid.")
    if not Path("/usr/local/bin/cloudflared").is_file():
        raise Failure("The pinned cloudflared binary is unavailable.")
    config_dir = Path("/etc/cloudflared")
    config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    token_file = config_dir / "token"
    token_file.write_text(token)
    token_file.chmod(0o600)
    service = """[Unit]
Description=Matrix Cloudflare Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/cloudflared --no-autoupdate tunnel run --token-file /etc/cloudflared/token
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
"""
    Path("/etc/systemd/system/cloudflared.service").write_text(service)
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "--now", "cloudflared"])
    wait_for("Cloudflare Tunnel", lambda: systemd_active("cloudflared"), timeout=60)


def phase_application(state: State) -> None:
    deployment, organization = load_configuration()
    element_hash = asset_checksum(
        "favicon.ico", "logo.webp", "custom-translations.json"
    )
    mas_hash = asset_checksum("mas-es.json")
    synapse_hash = asset_checksum("room_creation_policy.py")
    with rendered_values(deployment, organization) as values:
        run(
            [
                "helm",
                "install",
                RELEASE,
                CHART,
                "--namespace",
                NAMESPACE,
                "--create-namespace",
                "--rollback-on-failure",
                "--wait",
                "--timeout",
                "12m",
                "--values",
                values,
                "--set-string",
                f"matrix-stack.elementWeb.annotations.element-assets-checksum={element_hash}",
                "--set-string",
                f"matrix-stack.matrixAuthenticationService.annotations.mas-translations-checksum={mas_hash}",
                "--set-string",
                f"matrix-stack.synapse.annotations.room-policy-checksum={synapse_hash}",
            ],
            timeout=900,
        )


def mas_manage(*args: str, capture: bool = False) -> str:
    return run(
        [
            "kubectl",
            "exec",
            "-n",
            NAMESPACE,
            f"deployment/{RELEASE}-matrix-authentication-service",
            "--container",
            "matrix-authentication-service",
            "--",
            "mas-cli",
            "manage",
            *args,
        ],
        capture=capture,
        timeout=120,
    )


def compatibility_token(username: str) -> str:
    output = mas_manage(
        "issue-compatibility-token",
        "--yes-i-want-to-grant-synapse-admin-privileges",
        username,
        capture=True,
    )
    match = re.search(r"mct_[A-Za-z0-9_-]+", output)
    if not match:
        raise Failure("MAS did not return a compatibility token.")
    return match.group(0)


def matrix_request(
    deployment: Any,
    method: str,
    path: str,
    *,
    token: str,
    body: Any = None,
    allowed: Collection[int] = (200,),
) -> Any:
    return request(
        method,
        deployment["urls"]["matrix"] + path,
        token=token,
        body=body,
        allowed=allowed,
    )


def save_install_state(state: State) -> None:
    state["updated_at"] = timestamp()
    write_json(STATE_FILE, state)


def phase_organization(state: State) -> None:
    deployment, organization = load_configuration()
    progress = state.setdefault("organization", {})
    admin = organization["administrator"]
    username = admin["username"]
    if "administrator" not in progress:
        password = "Chat!" + secrets.token_urlsafe(24)
        mas_manage(
            "register-user",
            "--yes",
            "--admin",
            "--display-name",
            admin["display_name"],
            "--password",
            password,
            username,
        )
        credentials = STATE_DIR / "bootstrap-credentials.txt"
        credentials.write_text(f"username,password\n{username},{password}\n")
        credentials.chmod(0o600)
        progress["administrator"] = {
            "username": username,
            "credentials": str(credentials),
        }
        save_install_state(state)
    mas_manage("provision-all-users")
    token = compatibility_token(username)
    rooms = progress.setdefault("rooms", {})
    space = organization["space"]
    if space["key"] not in rooms:
        result = matrix_request(
            deployment,
            "POST",
            "/_matrix/client/v3/createRoom",
            token=token,
            body={
                "creation_content": {"type": "m.space"},
                "name": deployment["brand"],
                "preset": "private_chat",
                "room_alias_name": space["key"],
            },
        )
        rooms[space["key"]] = result["room_id"]
        save_install_state(state)
    space_id = rooms[space["key"]]
    for position, room in enumerate(organization["rooms"]):
        if room["key"] not in rooms:
            result = matrix_request(
                deployment,
                "POST",
                "/_matrix/client/v3/createRoom",
                token=token,
                body={
                    "name": room["name"],
                    "preset": "private_chat",
                    "room_alias_name": room["key"],
                    "initial_state": [
                        {
                            "type": "m.space.parent",
                            "state_key": space_id,
                            "content": {
                                "via": [deployment["hosts"]["matrix"]],
                                "canonical": True,
                            },
                        }
                    ],
                },
            )
            rooms[room["key"]] = result["room_id"]
            save_install_state(state)
        room_id = rooms[room["key"]]
        path = "/_matrix/client/v3/rooms/{}/state/m.space.child/{}".format(
            urllib.parse.quote(space_id, safe=""), urllib.parse.quote(room_id, safe="")
        )
        matrix_request(
            deployment,
            "PUT",
            path,
            token=token,
            body={
                "via": [deployment["hosts"]["matrix"]],
                "order": f"{position:02d}",
            },
        )


def ready_pods() -> bool:
    items = json.loads(
        command_output(["kubectl", "-n", NAMESPACE, "get", "pods", "-o", "json"])
    )["items"]
    if not items:
        return False
    for item in items:
        if item["status"].get("phase") == "Succeeded":
            continue
        if item["status"].get("phase") != "Running":
            return False
        statuses = item["status"].get("containerStatuses", [])
        if not statuses or not all(status.get("ready") for status in statuses):
            return False
    return True


def verify() -> None:
    deployment = load_deployment()
    if not systemd_active("k3s"):
        raise Failure("k3s is not active.")
    if not systemd_active("cloudflared"):
        raise Failure("cloudflared is not active.")
    if "deployed" not in command_output(["helm", "status", RELEASE, "-n", NAMESPACE]):
        raise Failure("The Matrix Helm release is not deployed.")
    if not ready_pods():
        raise Failure("At least one Matrix pod is not ready.")
    versions = request("GET", deployment["urls"]["matrix"] + "/_matrix/client/versions")
    if "versions" not in versions:
        raise Failure("The Matrix client endpoint returned an invalid response.")
    config = request("GET", deployment["urls"]["chat"] + "/config.json")
    if (
        config.get("brand") != deployment["brand"]
        or config.get("default_server_config", {})
        .get("m.homeserver", {})
        .get("base_url")
        != deployment["urls"]["matrix"]
        or config.get("setting_defaults", {}).get("language") != "es"
        or config.get("custom_translations_url")
        != deployment["urls"]["chat"] + "/custom-translations.json"
    ):
        raise Failure("Element does not expose the expected deployment configuration.")
    if '<html lang="es">' not in request("GET", deployment["urls"]["account"]):
        raise Failure("MAS does not serve the Spanish interface.")
    request("GET", deployment["urls"]["admin"])


def install(resume: bool) -> None:
    if resume:
        state = load_json(STATE_FILE)
        if state.get("status") == "complete":
            raise Failure(
                "Element Chat is already installed. Run ./element verify instead."
            )
    else:
        if STATE_FILE.exists():
            raise Failure(
                "An installation already started. Run ./element install --resume to continue it "
                "or ./element verify to check it."
            )
        state = {
            "status": "installing",
            "started_at": timestamp(),
            "completed_phases": [],
        }
        print("[preflight] running", flush=True)
        phase_preflight(state)
        state["completed_phases"].append("preflight")
        write_json(STATE_FILE, state)
        print("[preflight] complete", flush=True)
    handlers: dict[str, Callable[[State], None]] = {
        "preflight": phase_preflight,
        "tools": phase_tools,
        "k3s": phase_k3s,
        "tunnel": phase_tunnel,
        "application": phase_application,
        "organization": phase_organization,
        "verify": lambda _: verify(),
    }
    completed = set(state["completed_phases"])
    phases = PHASES if resume else PHASES[1:]
    for phase in phases:
        if phase in completed:
            print(f"[{phase}] already complete")
            continue
        print(f"[{phase}] running", flush=True)
        handlers[phase](state)
        state["completed_phases"].append(phase)
        save_install_state(state)
        print(f"[{phase}] complete", flush=True)
    state["status"] = "complete"
    state["completed_at"] = timestamp()
    save_install_state(state)
    print(
        f"Element Chat is installed. Bootstrap credentials: {state['organization']['administrator']['credentials']}"
    )
