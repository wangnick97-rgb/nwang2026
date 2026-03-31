#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
video_pipeline.py — Daily auto-select a philosophy/mindset script,
POST to Zapier -> Zapier calls HeyGen -> generates avatar video.
No Claude API. No external dependencies.
"""

import urllib.request
import json
import sys
import os
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ZAPIER_WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/26951471/unakh8k/"
HEYGEN_AVATAR_ID   = "1450565002f64e9c86defed726b03f06"
SCRIPT_DIR         = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Load scripts from JSON
# ---------------------------------------------------------------------------

def load_scripts():
    path = os.path.join(SCRIPT_DIR, "scripts.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Select today's script (rotates daily)
# ---------------------------------------------------------------------------

def pick_script(scripts):
    day_of_year = datetime.now(timezone.utc).timetuple().tm_yday
    return scripts[day_of_year % len(scripts)]

# ---------------------------------------------------------------------------
# Send to Zapier
# ---------------------------------------------------------------------------

def send_to_zapier(script):
    payload = json.dumps({
        "script":    script,
        "avatar_id": HEYGEN_AVATAR_ID,
        "date":      datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }).encode("utf-8")

    req = urllib.request.Request(
        ZAPIER_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.getcode()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scripts = load_scripts()
    print(f"Loaded {len(scripts)} scripts.")

    script = pick_script(scripts)
    print(f"Today's script preview: {script[:80]}...")

    print("Sending to Zapier -> HeyGen...")
    status = send_to_zapier(script)
    print(f"Done. Status: {status}")

if __name__ == "__main__":
    main()
