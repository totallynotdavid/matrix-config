#!/usr/bin/env python3

import argparse
import os
import sys
import urllib.error

from element_chat.installation import install, verify
from element_chat.support import Failure, require_root
from element_chat.users import import_users

os.environ.setdefault("KUBECONFIG", "/etc/rancher/k3s/k3s.yaml")
os.environ["PATH"] = f"/usr/local/bin:{os.environ['PATH']}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install and operate Element Chat")
    commands = parser.add_subparsers(dest="command", required=True)
    install_parser = commands.add_parser("install")
    install_parser.add_argument("--resume", action="store_true")
    commands.add_parser("verify")
    users_parser = commands.add_parser("users")
    users_parser.add_argument("csv", nargs="?")
    users_parser.add_argument("--resume", metavar="RECEIPT")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "install":
        require_root()
        install(args.resume)
    elif args.command == "verify":
        require_root()
        verify()
        print("Element Chat verification passed.")
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
        raise SystemExit(1) from error
