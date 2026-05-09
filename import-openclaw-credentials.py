#!/usr/bin/env python3
"""
Import OpenClaw OAuth credentials to Hermes Agent
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone

# OpenClaw auth profiles path
OPENCLAW_AUTH_PATH = (
    Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
)

# Hermes auth path
HERMES_AUTH_PATH = Path.home() / ".hermes" / "auth.json"


def import_openclaw_credentials():
    """Import OpenClaw OAuth credentials to Hermes"""

    # Check if OpenClaw auth file exists
    if not OPENCLAW_AUTH_PATH.exists():
        print(f"❌ OpenClaw auth file not found: {OPENCLAW_AUTH_PATH}")
        return False

    # Load OpenClaw credentials
    with open(OPENCLAW_AUTH_PATH, "r") as f:
        openclaw_data = json.load(f)

    print(f"✅ Loaded OpenClaw credentials from {OPENCLAW_AUTH_PATH}")

    # Find OpenAI Codex credentials
    codex_profiles = {}
    for profile_name, profile in openclaw_data.get("profiles", {}).items():
        if profile.get("provider") == "openai-codex" and profile.get("type") == "oauth":
            codex_profiles[profile_name] = profile
            print(f"  Found: {profile_name} (email: {profile.get('email', 'N/A')})")

    if not codex_profiles:
        print("❌ No OpenAI Codex OAuth credentials found in OpenClaw")
        return False

    # Create Hermes auth directory if it doesn't exist
    HERMES_AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Load existing Hermes auth or create new
    hermes_data = {"version": 1, "providers": {}}

    if HERMES_AUTH_PATH.exists():
        with open(HERMES_AUTH_PATH, "r") as f:
            hermes_data = json.load(f)
        print(f"✅ Loaded existing Hermes auth from {HERMES_AUTH_PATH}")

    # Import credentials
    for profile_name, profile in codex_profiles.items():
        provider_id = "openai-codex"

        # Convert to Hermes format
        hermes_creds = {
            "provider": provider_id,
            "mode": "oauth",
            "access_token": profile.get("access"),
            "refresh_token": profile.get("refresh"),
            "expires_at": profile.get("expires"),
            "email": profile.get("email"),
            "account_id": profile.get("accountId"),
        }

        # Store in Hermes format
        if "credentials" not in hermes_data:
            hermes_data["credentials"] = {}

        hermes_data["credentials"][provider_id] = hermes_creds
        print(f"✅ Imported {profile_name} to Hermes")

    # Save Hermes auth
    with open(HERMES_AUTH_PATH, "w") as f:
        json.dump(hermes_data, f, indent=2)

    # Set proper permissions
    os.chmod(HERMES_AUTH_PATH, 0o600)

    print(
        f"\n✅ Successfully imported {len(codex_profiles)} credential(s) to {HERMES_AUTH_PATH}"
    )
    print("\nNext steps:")
    print("1. Run: ./hermes-start.sh model  (to select GPT-5.4 or other Codex models)")
    print("2. Run: ./hermes-start.sh        (to start chatting)")

    return True


if __name__ == "__main__":
    import_openclaw_credentials()
