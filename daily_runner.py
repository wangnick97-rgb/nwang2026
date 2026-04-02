#!/usr/bin/env python3
"""
daily_runner.py — Master cron entry point.
  - Every day:        run ai_trends.py  (push top 2 viral trends to HeyGen)
  - Every other day:  run video_pipeline.py  (push 2 script options for manual selection)
"""

import subprocess
import sys
import os
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run(script_name):
    path = os.path.join(SCRIPT_DIR, script_name)
    print(f"\n{'=' * 60}")
    print(f"Running {script_name}...")
    print(f"{'=' * 60}")
    result = subprocess.run([sys.executable, path])
    if result.returncode != 0:
        print(f"[ERROR] {script_name} exited with code {result.returncode}", file=sys.stderr)


def main():
    day_of_year = datetime.now(timezone.utc).timetuple().tm_yday

    # Always run trend discovery
    run("ai_trends.py")

    # Run video pipeline every other day (even days)
    if day_of_year % 2 == 0:
        run("video_pipeline.py")
    else:
        print("\n[SKIP] video_pipeline.py — not scheduled today (runs every other day)")


if __name__ == "__main__":
    main()
