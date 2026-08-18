# SoundHub for FL Studio (prototype)

> **SoundHub inside FL Studio = the fastest way to buy finished sound assets
> while you're actually making music.**

FL Studio has no Max for Live, but it ships a **Python scripting API**
(MIDI controller scripts, FL Studio 20.7+). This branch turns that into a
SoundHub panel: the script reads the **project context** (BPM, position,
play state) and shows **BPM-matched recommendations** from the SoundHub
backend.

FL Studio's embedded Python has no reliable network stack, so the device and
the backend are connected by a **file bridge**:

```
FL Studio (device_soundhub.py)          bridge.py (terminal)     SoundHub backend
─────────────────────────────           ──────────────────       ───────────────
CC 20 → read BPM/position  ──write──►   context.json
                                        ◄─read───┘
                                        ──GET──►  /api/assets/recommend
                                        ◄─items──┘
                                        ──write──► suggestions.json
OnIdle poll ◄─read───┘  → ui.setHintMsg
```

## Files

| File | What it is |
|---|---|
| `device_soundhub.py` | FL Studio MIDI scripting device — reads context, shows suggestions via `ui.setHintMsg` |
| `bridge.py` | terminal helper — watches `context.json`, calls the backend, writes `suggestions.json` |
| `INTEGRATION.md` | architecture, constraints and honest limitations |

## Install

1. **Backend** (needed for suggestions):
   ```bash
   cd backend
   .venv/bin/uvicorn app.main:app --port 8000
   ```
2. **Bridge** (new terminal, keep running):
   ```bash
   cd flstudio
   python3 bridge.py
   ```
3. **Device**: create
   `Documents/Image-Line/FL Studio/Settings/Hardware/SoundHub/` and copy
   `device_soundhub.py` there as `device_soundhub.py`.
4. In FL Studio: **Options → MIDI Settings → Input** → select *SoundHub* →
   **Enable**. Assign MIDI CC **20** (or change `REFRESH_CC` in the script)
   to any button/knob you like.

## Using it

- Press the refresh button (CC 20) — the device writes the current project
  BPM/position, the bridge fetches ranked recommendations, and the hint bar
  shows up to 4 matches with prices.
- New suggestions appear automatically (the device polls
  `suggestions.json` every 2 s).

## What's stubbed (honest)

- **Display** — results go to the FL Studio hint bar (`ui.setHintMsg`);
  a proper plugin window needs FL's newer UI APIs, out of scope for the
  prototype.
- **Purchase & load** — buying happens in the web app with the user's
  wallet; auto-import of a preset into a channel needs a file-write path
  from the script (possible via the same bridge: backend writes the asset
  next to `context.json`, device copies it into the project folder).
- **Context** — only tempo/position/play state today; key and device/plugin
  names are parsed by the DAW engine but not yet sent by the device.
- **Bridge** — the helper polls `context.json` every 1 s; a filesystem
  watcher (`watchdog`) would be snappier but adds a dependency.

## Security

The device only reads project metadata and shows suggestions. It never
signs transactions — purchases stay in the web app (testnet SND).
