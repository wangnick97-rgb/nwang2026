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
# Select 2 scripts to offer as options (rotates every run)
# ---------------------------------------------------------------------------

def pick_two_scripts(scripts):
    day_of_year = datetime.now(timezone.utc).timetuple().tm_yday
    n = len(scripts)
    idx1 = day_of_year % n
    idx2 = (day_of_year + 1) % n
    return scripts[idx1], scripts[idx2]

# ---------------------------------------------------------------------------
# Send to Zapier — 2 options for manual selection
# ---------------------------------------------------------------------------

def send_to_zapier(option_1, option_2):
    payload = json.dumps({
        "option_1":  option_1,
        "option_2":  option_2,
        "avatar_id": HEYGEN_AVATAR_ID,
        "date":      datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "note":      "请选择其中一条脚本发给 HeyGen 生成视频",
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

    option_1, option_2 = pick_two_scripts(scripts)
    print(f"Option 1 preview: {option_1[:80]}...")
    print(f"Option 2 preview: {option_2[:80]}...")

    print("Sending 2 options to Zapier for manual selection...")
    status = send_to_zapier(option_1, option_2)
    print(f"Done. Status: {status}")

if __name__ == "__main__":
    main()
