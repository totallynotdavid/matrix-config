import csv
import secrets
import stat
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

from .config import LOCALPART, load_configuration
from .installation import compatibility_token, mas_manage, matrix_request
from .support import (
    IMPORT_DIR,
    ROOT,
    STATE_FILE,
    Failure,
    load_json,
    timestamp,
    wait_for,
    write_json,
)


def validate_worker_file(path, room_keys):
    resolved = path.resolve()
    if ROOT == resolved or ROOT in resolved.parents:
        raise Failure("Worker CSV files must be stored outside the repository.")
    mode = stat.S_IMODE(resolved.stat().st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise Failure("The worker CSV must be readable and writable only by its owner (mode 0600).")
    with resolved.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["username", "display_name", "teams"]:
            raise Failure("Worker CSV columns must be exactly: username,display_name,teams")
        rows = list(reader)
    if not rows:
        raise Failure("The worker CSV is empty.")
    seen = set()
    for line, row in enumerate(rows, 2):
        if None in row or any(value is None for value in row.values()):
            raise Failure(f"Malformed CSV row {line}.")
        username = row["username"]
        if not LOCALPART.fullmatch(username):
            raise Failure(f"Invalid username on line {line}: {username}")
        if username in seen:
            raise Failure(f"Duplicate username on line {line}: {username}")
        seen.add(username)
        row["display_name"] = row["display_name"].strip()
        if not row["display_name"]:
            raise Failure(f"Display name is required on line {line}.")
        teams = [team.strip() for team in row["teams"].split(";") if team.strip()]
        if not teams:
            raise Failure(f"At least one team is required on line {line}.")
        unknown = set(teams) - room_keys
        if unknown:
            raise Failure(f"Unknown team on line {line}: {', '.join(sorted(unknown))}")
        row["teams"] = teams
    return rows


def user_exists(deployment, token, username):
    user_id = urllib.parse.quote(f"@{username}:{deployment['hosts']['matrix']}", safe="")
    result = matrix_request(
        deployment,
        "GET",
        f"/_synapse/admin/v2/users/{user_id}",
        token=token,
        allowed=(200, 404),
    )
    return result is not None and isinstance(result, dict) and "name" in result


def join_room(deployment, token, user_id, room_id):
    matrix_request(
        deployment,
        "POST",
        f"/_synapse/admin/v1/join/{urllib.parse.quote(room_id, safe='')}",
        token=token,
        body={"user_id": user_id},
    )


def write_credentials(receipt):
    path = Path(receipt["credentials_file"])
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["username", "initial_password"])
        for worker in receipt["workers"]:
            if worker.get("account_created"):
                writer.writerow([worker["username"], worker["password"]])
    temporary.chmod(0o600)
    temporary.replace(path)


def import_users(csv_path=None, resume_path=None):
    state = load_json(STATE_FILE)
    if state.get("status") != "complete":
        raise Failure("Element Chat installation is not complete.")
    username = state["organization"]["administrator"]["username"]
    token = compatibility_token(username)
    rooms = state["organization"]["rooms"]
    deployment, organization = load_configuration()
    space_key = organization["space"]["key"]
    team_rooms = {key: value for key, value in rooms.items() if key != space_key}
    if resume_path:
        receipt_path = Path(resume_path)
        receipt = load_json(receipt_path)
        if receipt.get("status") == "complete":
            raise Failure("This user import is already complete.")
    else:
        rows = validate_worker_file(Path(csv_path), set(team_rooms))
        existing = [row["username"] for row in rows if user_exists(deployment, token, row["username"])]
        if existing:
            raise Failure("These accounts already exist: " + ", ".join(existing))
        IMPORT_DIR.mkdir(parents=True, exist_ok=True)
        import_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        receipt_path = IMPORT_DIR / f"users-{import_id}.json"
        credentials_path = IMPORT_DIR / f"credentials-{import_id}.csv"
        receipt = {
            "status": "running",
            "started_at": timestamp(),
            "source": str(Path(csv_path).resolve()),
            "credentials_file": str(credentials_path),
            "workers": [
                {
                    **row,
                    "password": "Chat!" + secrets.token_urlsafe(24),
                    "account_created": False,
                    "joined_rooms": [],
                }
                for row in rows
            ],
        }
        write_json(receipt_path, receipt)
        print(f"Import receipt: {receipt_path}")
    for worker in receipt["workers"]:
        if not worker["account_created"]:
            mas_manage(
                "register-user", "--yes", "--no-admin", "--display-name",
                worker["display_name"], "--password", worker["password"], worker["username"],
            )
            worker["account_created"] = True
            write_json(receipt_path, receipt)
            write_credentials(receipt)
    mas_manage("provision-all-users")
    for worker in receipt["workers"]:
        user_id = f"@{worker['username']}:{deployment['hosts']['matrix']}"
        wait_for(
            f"Synapse user {user_id}",
            lambda: user_exists(deployment, token, worker["username"]),
            timeout=120,
        )
        for room_key in [space_key, *worker["teams"]]:
            if room_key not in worker["joined_rooms"]:
                join_room(deployment, token, user_id, rooms[room_key])
                worker["joined_rooms"].append(room_key)
                write_json(receipt_path, receipt)
    receipt["status"] = "complete"
    receipt["completed_at"] = timestamp()
    write_json(receipt_path, receipt)
    write_credentials(receipt)
    print(f"Created {len(receipt['workers'])} users. Credentials: {receipt['credentials_file']}")
