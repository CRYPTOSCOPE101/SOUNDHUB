"""
SoundHub × FL Studio — MIDI scripting device (prototype).

This is an FL Studio *MIDI controller script* (Python). FL Studio's embedded
Python has no reliable network stack, so this device does not talk to the
SoundHub backend directly. Instead it uses a **file bridge**:

    device_soundhub.py  ──writes──►  context.json   (BPM, position, playing)
    bridge.py (external)  ◄─reads───┘
    bridge.py  ──calls──►  GET /api/assets/recommend  (SoundHub backend)
    bridge.py  ──writes──►  suggestions.json
    device_soundhub.py  ◄─reads───┘   (shown via ui.setHintMsg)

Install:
  1. Create the folder
     Documents/Image-Line/FL Studio/Settings/Hardware/SoundHub/
  2. Copy this file there as  device_soundhub.py
  3. Start `bridge.py` in a terminal (needs the SoundHub backend running)
  4. In FL Studio: Options → MIDI Settings → Input: SoundHub → Enable
  5. Press the CC button (default CC 20, configurable below) to refresh

Only FL Studio's documented API is used: `general.processRECEvent` for the
project tempo (REC_Tempo), `transport` for position/play state, and
`ui.setHintMsg` to show results in the hint bar.
"""

import json
import os
import time

import channels
import device
import general
import midi
import transport
import ui

# --- config ------------------------------------------------------------------

# Bridge folder: where context.json / suggestions.json live. Point it at the
# same folder bridge.py watches (default: this script's folder).
BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTEXT_FILE = os.path.join(BRIDGE_DIR, "context.json")
SUGGESTIONS_FILE = os.path.join(BRIDGE_DIR, "suggestions.json")

# MIDI CC that triggers "refresh" (0-127). Assign it in MIDI Settings.
REFRESH_CC = 20

# How often (seconds) OnIdle re-reads suggestions.json so new results appear
# without pressing a button.
POLL_INTERVAL = 2.0


# --- context -----------------------------------------------------------------

def _read_tempo_bpm() -> float:
    """Project tempo in BPM. REC_Tempo is stored as 1000 * BPM."""
    raw = general.processRECEvent(midi.REC_Tempo, -1, midi.REC_GetValue)
    return raw / 1000.0 if raw and raw > 0 else 0.0


def _write_context() -> None:
    """Write the current project context for bridge.py to consume."""
    context = {
        "bpm": _read_tempo_bpm(),
        "position": transport.getSongPosHint(),
        "playing": transport.isPlaying(),
        "loop_mode": transport.getLoopMode(),
        "timestamp": time.time(),
    }
    try:
        with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
            json.dump(context, f, indent=2)
    except OSError as exc:
        ui.setHintMsg(f"SoundHub: cannot write {CONTEXT_FILE}: {exc}")


def _show_suggestions() -> None:
    """Read suggestions.json written by bridge.py and show a summary."""
    try:
        with open(SUGGESTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        ui.setHintMsg("SoundHub: no suggestions yet — press refresh (CC 20)")
        return

    items = data.get("items", [])
    if not items:
        ui.setHintMsg("SoundHub: no matches for this project context")
        return

    lines = [f"SoundHub — {len(items)} matches @ {data.get('bpm', '?')} BPM"]
    for it in items[:4]:
        name = it.get("name", "?")
        price = it.get("price", "?")
        lines.append(f"• {name} — {price} SND")
    ui.setHintMsg(" | ".join(lines))


# --- FL Studio callbacks ------------------------------------------------------

def OnInit() -> None:
    """Called when the script is loaded. Announce ourselves once."""
    _write_context()
    ui.setHintMsg("SoundHub device ready — press CC 20 to refresh")


def OnDeInit() -> None:
    pass


def OnMidiMsg(event) -> None:
    """MIDI CC in -> refresh context and pull suggestions."""
    if event.status == midi.MIDI_CONTROLCHANGE and event.data1 == REFRESH_CC:
        _write_context()
        _show_suggestions()
        event.handled = True


def OnIdle() -> None:
    """Poll suggestions.json so new bridge results show up automatically."""
    try:
        mtime = os.path.getmtime(SUGGESTIONS_FILE)
    except OSError:
        return
    if mtime > getattr(OnIdle, "_last_mtime", 0):
        OnIdle._last_mtime = mtime
        _show_suggestions()
