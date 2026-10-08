import re

from .support import DEPLOYMENT, ORGANIZATION, Failure, load_json


LOCALPART = re.compile(r"[a-z0-9._=-]+")


def has_keys(value, keys):
    return isinstance(value, dict) and set(value) == keys


def non_empty_string(value):
    return isinstance(value, str) and bool(value.strip())


def load_deployment(path=DEPLOYMENT):
    deployment = load_json(path)
    expected_hosts = {"chat", "matrix", "account", "admin"}
    if not has_keys(deployment, {"brand", "hosts"}) or not has_keys(
        deployment["hosts"], expected_hosts
    ):
        raise Failure(
            f"{path.name} must contain brand and chat, matrix, account, and admin hosts."
        )
    if not non_empty_string(deployment["brand"]):
        raise Failure(f"{path.name} brand must be a non-empty string.")
    hostname = re.compile(
        r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
    )
    if any(
        not isinstance(host, str) or not hostname.fullmatch(host)
        for host in deployment["hosts"].values()
    ):
        raise Failure(f"{path.name} hosts must be lowercase public DNS names.")
    if len(set(deployment["hosts"].values())) != len(expected_hosts):
        raise Failure(f"{path.name} hosts must be unique.")
    deployment["brand"] = deployment["brand"].strip()
    deployment["urls"] = {
        name: f"https://{host}" for name, host in deployment["hosts"].items()
    }
    return deployment


def load_organization(path=ORGANIZATION):
    organization = load_json(path)
    name = path.name
    if not has_keys(organization, {"administrator", "space", "rooms"}):
        raise Failure(f"{name} must contain administrator, space, and rooms.")
    administrator = organization["administrator"]
    if not has_keys(administrator, {"username", "display_name"}):
        raise Failure(f"{name} administrator must contain username and display_name.")
    if not non_empty_string(administrator["display_name"]):
        raise Failure(f"{name} administrator display_name must be a non-empty string.")
    if not has_keys(organization["space"], {"key"}):
        raise Failure(f"{name} space must contain key.")
    rooms = organization["rooms"]
    if not isinstance(rooms, list) or not rooms:
        raise Failure(f"{name} rooms must be a non-empty list.")
    for position, room in enumerate(rooms):
        if not has_keys(room, {"key", "name"}):
            raise Failure(f"{name} rooms[{position}] must contain key and name.")
        if not non_empty_string(room["name"]):
            raise Failure(f"{name} rooms[{position}] name must be a non-empty string.")
    keys = {
        f"{name} administrator username": administrator["username"],
        f"{name} space key": organization["space"]["key"],
        **{f"{name} rooms[{n}] key": room["key"] for n, room in enumerate(rooms)},
    }
    for label, key in keys.items():
        if not isinstance(key, str) or not LOCALPART.fullmatch(key):
            raise Failure(f"{label} must use only a-z, 0-9, and . _ = -")
    aliases = [organization["space"]["key"], *(room["key"] for room in rooms)]
    if len(set(aliases)) != len(aliases):
        raise Failure(f"{name} space and room keys must be unique.")
    return organization


def load_configuration():
    return load_deployment(), load_organization()
