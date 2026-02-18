#!/usr/bin/env python3
"""
Authentication Key Management Script for CeloFlow.

CRUD operations for JWT secrets and API keys.

Usage:
    uv run scripts/manage_auth_keys.py generate-secret
    uv run scripts/manage_auth_keys.py generate-api-key [--name NAME]
    uv run scripts/manage_auth_keys.py rotate-secret [--backup]
    uv run scripts/manage_auth_keys.py list-keys
    uv run scripts/manage_auth_keys.py revoke-key KEY
    uv run scripts/manage_auth_keys.py validate-config
"""

import argparse
import hashlib
import json
import os
import secrets
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv, set_key

load_dotenv()

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
KEYS_FILE = Path(__file__).resolve().parent.parent / "data" / "auth_keys.json"


def _load_keys_store() -> dict:
    """Load the keys store from disk."""
    if KEYS_FILE.exists():
        with open(KEYS_FILE, "r") as f:
            return json.load(f)
    return {"api_keys": [], "rotations": []}


def _save_keys_store(store: dict) -> None:
    """Save the keys store to disk."""
    KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(KEYS_FILE, "w") as f:
        json.dump(store, f, indent=2)


def generate_secret(args: argparse.Namespace) -> None:
    """Generate a new JWT secret."""
    secret = secrets.token_hex(32)
    print(f"Generated JWT secret: {secret}")
    print(f"\nAdd to .env:")
    print(f"  JWT_SECRET={secret}")

    if args.write and ENV_FILE.exists():
        set_key(str(ENV_FILE), "JWT_SECRET", secret)
        print(f"\n✓ Written to {ENV_FILE}")


def generate_api_key(args: argparse.Namespace) -> None:
    """Generate a new API key."""
    key = f"cflw_{secrets.token_hex(24)}"
    name = args.name or f"key_{int(time.time())}"

    store = _load_keys_store()
    store["api_keys"].append({
        "name": name,
        "key_hash": hashlib.sha256(key.encode()).hexdigest(),
        "created_at": time.time(),
        "active": True,
    })
    _save_keys_store(store)

    print(f"Generated API key: {key}")
    print(f"Name: {name}")
    print(f"\nAdd to AUTH_API_KEYS in .env (comma-separated with existing keys)")
    print(f"\n⚠ Store this key securely — it cannot be recovered.")


def rotate_secret(args: argparse.Namespace) -> None:
    """Rotate the JWT secret."""
    old_secret = os.getenv("JWT_SECRET", "")
    new_secret = secrets.token_hex(32)

    store = _load_keys_store()
    store["rotations"].append({
        "old_hash": hashlib.sha256(old_secret.encode()).hexdigest() if old_secret else None,
        "new_hash": hashlib.sha256(new_secret.encode()).hexdigest(),
        "rotated_at": time.time(),
    })
    _save_keys_store(store)

    print(f"New JWT secret: {new_secret}")
    print(f"\n⚠ All existing tokens will be invalidated after rotation.")

    if args.write and ENV_FILE.exists():
        set_key(str(ENV_FILE), "JWT_SECRET", new_secret)
        print(f"\n✓ Written to {ENV_FILE}")


def list_keys(args: argparse.Namespace) -> None:
    """List all registered API keys."""
    store = _load_keys_store()
    keys = store.get("api_keys", [])

    if not keys:
        print("No API keys registered.")
        return

    print(f"{'Name':<20} {'Status':<10} {'Created':<25} {'Hash (first 12)':<15}")
    print("-" * 70)
    for k in keys:
        status = "active" if k.get("active") else "revoked"
        created = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(k["created_at"]))
        print(f"{k['name']:<20} {status:<10} {created:<25} {k['key_hash'][:12]}")


def revoke_key(args: argparse.Namespace) -> None:
    """Revoke an API key by name."""
    store = _load_keys_store()
    found = False
    for k in store.get("api_keys", []):
        if k["name"] == args.key_name:
            k["active"] = False
            k["revoked_at"] = time.time()
            found = True
            break

    if found:
        _save_keys_store(store)
        print(f"✓ Key '{args.key_name}' revoked.")
    else:
        print(f"✗ Key '{args.key_name}' not found.")
        sys.exit(1)


def validate_config(args: argparse.Namespace) -> None:
    """Validate the current authentication configuration."""
    issues = []

    jwt_secret = os.getenv("JWT_SECRET")
    if not jwt_secret:
        issues.append("⚠ JWT_SECRET not set — ephemeral secret will be generated at runtime")
    elif len(jwt_secret) < 32:
        issues.append("⚠ JWT_SECRET is short (< 32 chars) — consider a longer secret")

    origins = os.getenv("AUTH_ALLOWED_ORIGINS", "")
    if not origins:
        issues.append("⚠ AUTH_ALLOWED_ORIGINS not set — defaults will be used")

    tee = os.getenv("ENABLE_TEE_ATTESTATION", "false")
    if tee.lower() == "true":
        if not os.getenv("TEE_ENDPOINT") and not os.getenv("USE_TEE"):
            issues.append("⚠ ENABLE_TEE_ATTESTATION=true but TEE_ENDPOINT/USE_TEE not configured")

    if issues:
        print("Configuration issues found:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✓ Authentication configuration looks good.")

    print(f"\nCurrent settings:")
    print(f"  JWT_SECRET: {'set' if jwt_secret else 'not set'}")
    print(f"  JWT_ALGORITHM: {os.getenv('JWT_ALGORITHM', 'HS256')}")
    print(f"  JWT_ACCESS_TOKEN_EXPIRY: {os.getenv('JWT_ACCESS_TOKEN_EXPIRY', '3600')}s")
    print(f"  ENABLE_TEE_ATTESTATION: {tee}")
    print(f"  AUTH_ALLOWED_ORIGINS: {origins or '(defaults)'}")
    print(f"  AUTH_RATE_LIMIT_REQUESTS: {os.getenv('AUTH_RATE_LIMIT_REQUESTS', '100')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CeloFlow Auth Key Management")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # generate-secret
    sp = subparsers.add_parser("generate-secret", help="Generate a new JWT secret")
    sp.add_argument("--write", action="store_true", help="Write to .env file")

    # generate-api-key
    sp = subparsers.add_parser("generate-api-key", help="Generate a new API key")
    sp.add_argument("--name", help="Name for the API key")

    # rotate-secret
    sp = subparsers.add_parser("rotate-secret", help="Rotate the JWT secret")
    sp.add_argument("--write", action="store_true", help="Write to .env file")

    # list-keys
    subparsers.add_parser("list-keys", help="List all API keys")

    # revoke-key
    sp = subparsers.add_parser("revoke-key", help="Revoke an API key")
    sp.add_argument("key_name", help="Name of the key to revoke")

    # validate-config
    subparsers.add_parser("validate-config", help="Validate auth configuration")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "generate-secret": generate_secret,
        "generate-api-key": generate_api_key,
        "rotate-secret": rotate_secret,
        "list-keys": list_keys,
        "revoke-key": revoke_key,
        "validate-config": validate_config,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
