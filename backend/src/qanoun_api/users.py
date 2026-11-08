"""Create an account from the command line (for servers with QANOUN_ALLOW_SIGNUP=false).

    make user EMAIL=you@example.com            # prompts for the password
    make user EMAIL=you@example.com ADMIN=1
"""

import argparse
import getpass
import sys

from qanoun_api import accounts
from qanoun_api.db import db


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qanoun-users")
    parser.add_argument("email")
    parser.add_argument("--admin", action="store_true")
    args = parser.parse_args(argv)
    password = getpass.getpass("Password (8+ characters): ")
    if len(password) < accounts.MIN_PASSWORD:
        print("too short", file=sys.stderr)
        return 1
    if password != getpass.getpass("Repeat: "):
        print("passwords differ", file=sys.stderr)
        return 1
    with db() as conn:
        accounts.ensure_app_schema(conn)
        user_id = accounts.create_user(conn, args.email, password, admin=args.admin or None)
    print(f"created user {user_id} ({accounts.normalize_email(args.email)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
