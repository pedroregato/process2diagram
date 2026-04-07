#!/usr/bin/env python
# setup/generate_password_hash.py
# ─────────────────────────────────────────────────────────────────────────────
# Helper to generate password hashes for .streamlit/secrets.toml.
#
# Usage:
#   python setup/generate_password_hash.py
# ─────────────────────────────────────────────────────────────────────────────

import hashlib
import os
import getpass


def hash_password(password: str, salt: str | None = None) -> str:
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()
    return f"sha256${salt}${digest}"


def main():
    print("=" * 56)
    print("  Process2Diagram — Password Hash Generator")
    print("=" * 56)
    print()

    username = input("Username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    name = input(f"Display name [{username}]: ").strip() or username
    password = getpass.getpass("Password: ")
    if not password:
        print("Password cannot be empty.")
        return

    password_hash = hash_password(password)

    print()
    print("Add the following block to .streamlit/secrets.toml:")
    print()
    print(f"[auth.users.{username}]")
    print(f'name          = "{name}"')
    print(f'password_hash = "{password_hash}"')
    print()


if __name__ == "__main__":
    main()
