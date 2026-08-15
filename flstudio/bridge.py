#!/usr/bin/env python3
"""
SoundHub × FL Studio — bridge between the device script and the backend.

The FL Studio MIDI scripting environment has no reliable network access, so
this small script runs *outside* FL Studio (any Python 3 with `requests` or
`urllib`) and does the HTTP for the device:

    FL Studio device ──writes──►  context.json
    bridge.py        ◄─reads───┘
    bridge.py        ──calls──►  GET {BACKEND}/api/assets/recommend?bpm=…
    bridge.py        ──writes──►  suggestions.json
    FL Studio device ◄─reads───┘  (ui.setHintMsg)

Usage:
    python3 bridge.py [--backend http://127.0.0.1:8000] [--watch <dir>]

The watch dir defaults to this script's folder (same place as
device_soundhub.py). Run it after starting the SoundHub backend.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONTEXT_FILE = os.path.join(HERE, "context.json")
SUGGESTIONS_FILE = os.path.join(HERE, "suggestions.json")
POLL_INTERVAL = 1.0


def recommend(backend: str, context: dict) -> dict:
    """Call the SoundHub recommendation endpoint with the project context."""
    params = {"bpm": context.get("bpm", 0)}
    if context.get("position"):
        params["position"] = context["position"]
    url = f"{backend}/api/assets/recommend?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def write_suggestions(payload: dict, bpm: float) -> None:
    """Merge the API response with the bpm it was scored for and persist it."""
    out = dict(payload)
    out["bpm"] = bpm
    out["generated_at"] = time.time()
    with open(SUGGESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {SUGGESTIONS_FILE} ({len(out.get('items', []))} items)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    parser.add_argument("--watch", default=HERE, help="folder with context.json")
    args = parser.parse_args()

    context_file = os.path.join(args.watch, "context.json")
    suggestions_file = os.path.join(args.watch, "suggestions.json")
    last_mtime = 0.0

    print(f"SoundHub bridge watching {context_file} → {args.backend}")
    while True:
        try:
            mtime = os.path.getmtime(context_file)
        except OSError:
            time.sleep(POLL_INTERVAL)
            continue

        if mtime > last_mtime:
            last_mtime = mtime
            try:
                with open(context_file, "r", encoding="utf-8") as f:
                    context = json.load(f)
                payload = recommend(args.backend, context)
                write_suggestions(payload, context.get("bpm", 0))
            except (OSError, ValueError, urllib.error.URLError) as exc:
                print(f"error: {exc}", file=sys.stderr)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
