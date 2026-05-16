"""Local sync jobs that push Mac-only data to GitHub Secrets before the cloud digest runs."""

import base64
import json
import subprocess
import sys

from . import screentime, config


def push_screentime(cfg: dict) -> None:
    print("Fetching screen time...")
    data = screentime.fetch(cfg)
    if data.get("error"):
        print(f"Screen time unavailable: {data['error']}", file=sys.stderr)
        return

    encoded = base64.b64encode(json.dumps(data).encode()).decode()

    print("Pushing to GitHub Secrets...")
    result = subprocess.run(
        ["gh", "secret", "set", "SCREENTIME_CACHE_B64",
         "--repo", "joshuajet23/movere",
         "--body", encoded],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Failed to push: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("✓ Screen time pushed.")
