#!/usr/bin/env python3

import argparse
import os
import sys
import urllib.error

from element_chat.chart import validate
from element_chat.config import load_configuration
from element_chat.installation import install, verify
from element_chat.support import CHART, Failure, require_root
from element_chat.users import import_users


os.environ.setdefault("KUBECONFIG", "/etc/rancher/k3s/k3s.yaml")
os.environ["PATH"] = f"/usr/local/bin:{os.environ['PATH']}"


def check():
    deployment, organization = load_configuration()
    compile(
        (CHART / "files" / "room_creation_policy.py").read_text(),
        "room_creation_policy.py",
        "exec",
    )
    validate(deployment, organization)
    print("Repository checks passed.")


def parse_args():
    parser = argparse.ArgumentParser(description="Install and operate Element Chat")
    commands = parser.add_subparsers(dest="command", required=True)
    install_parser = commands.add_parser("install")
    install_parser.add_argument("--resume", action="store_true")
    commands.add_parser("verify")
    commands.add_parser("check")
    users_parser = commands.add_parser("users")
    users_parser.add_argument("csv", nargs="?")
    users_parser.add_argument("--resume", metavar="RECEIPT")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.command == "install":
        require_root()
        install(args.resume)
    elif args.command == "verify":
        require_root()
        verify()
        print("Element Chat verification passed.")
    elif args.command == "check":
        check()
    elif args.command == "users":
        if bool(args.csv) == bool(args.resume):
            raise Failure("Provide either a worker CSV or --resume RECEIPT.")
        require_root()
        import_users(args.csv, args.resume)


if __name__ == "__main__":
    try:
        main()
    except (Failure, OSError, urllib.error.URLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
