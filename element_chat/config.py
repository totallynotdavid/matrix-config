import re

from .support import DEPLOYMENT, ORGANIZATION, Failure, load_json


def load_deployment():
    deployment = load_json(DEPLOYMENT)
    expected_hosts = {"chat", "matrix", "account", "admin"}
    if set(deployment) != {"brand", "hosts"} or set(deployment["hosts"]) != expected_hosts:
        raise Failure(
            "deployment.json must contain brand and chat, matrix, account, and admin hosts."
        )
    if not isinstance(deployment["brand"], str) or not deployment["brand"].strip():
        raise Failure("deployment.json brand must be a non-empty string.")
    hostname = re.compile(
        r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
    )
    if any(
        not isinstance(host, str) or not hostname.fullmatch(host)
        for host in deployment["hosts"].values()
    ):
        raise Failure("deployment.json hosts must be lowercase public DNS names.")
    if len(set(deployment["hosts"].values())) != len(expected_hosts):
        raise Failure("deployment.json hosts must be unique.")
    deployment["brand"] = deployment["brand"].strip()
    deployment["urls"] = {
        name: f"https://{host}" for name, host in deployment["hosts"].items()
    }
    return deployment


def load_configuration():
    return load_deployment(), load_json(ORGANIZATION)
