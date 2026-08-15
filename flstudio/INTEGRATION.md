# SoundHub × FL Studio — integration overview

> **SoundHub inside FL Studio = the fastest way to buy finished sound assets
> while you're actually making music.**

This branch (`feat/flstudio-integration`) holds the FL Studio prototype of
the SoundHub-in-DAW experience: a MIDI scripting device plus a small bridge
that connects it to the existing SoundHub backend.

## What's here

| Piece | Location | Status |
|---|---|---|
| Integration architecture (layers, flows, constraints) | [`ARCHITECTURE.md`](../ARCHITECTURE.md) | ✅ |
| FL Studio MIDI scripting device (context → suggestions) | [`device_soundhub.py`](device_soundhub.py) | ✅ prototype |
| File bridge to the backend (recommend API) | [`bridge.py`](bridge.py) | ✅ |
| Install/usage guide | [`README.md`](README.md) | ✅ |
| This overview | [`INTEGRATION.md`](INTEGRATION.md) | ✅ |
| Recommendation service + catalog metadata | `backend/app/services/catalog.py` | ✅ (shared) |
| Asset endpoints (catalog / recommend / token / download) | `backend/app/routers/assets.py` | ✅ (shared) |

## Why a file bridge (and not HTTP from the script)

FL Studio executes MIDI scripts inside its embedded Python. It gives you
project state (`general.processRECEvent`, `transport`, `channels`, …) and
UI hints (`ui.setHintMsg`) — but reliable network access from scripts is
**not guaranteed** by Image-Line. Rather than fight that, the prototype uses
the same pattern that worked for Ableton's `shell`-blocked auto-import:
a **text-safe file bridge**.

```
FL Studio (device_soundhub.py)      bridge.py (terminal)   SoundHub backend
──────────────────────────────      ──────────────────      ────────────────
CC 20 ─► read BPM/position   ──write──► context.json
                                     ◄─read──┘
                                     ──GET──► /api/assets/recommend?bpm=…
                                     ◄─items─┘
                                     ──write──► suggestions.json
OnIdle poll ◄─read──┘ ─► ui.setHintMsg (hint bar)
```

The bridge is plain Python 3 with only the standard library — no extra
dependencies, runs anywhere the backend does.

## API surface used

| Function | Purpose |
|---|---|
| `general.processRECEvent(midi.REC_Tempo, -1, midi.REC_GetValue)` | project tempo (stored as 1000 × BPM) |
| `transport.getSongPosHint()` | playback position |
| `transport.isPlaying()` / `transport.getLoopMode()` | transport state |
| `ui.setHintMsg(msg)` | show results in the FL Studio hint bar |
| `GET /api/assets/recommend` | BPM-matched, genre/devices-scored rankings |

## The loop (end-to-end)

1. Producer presses the refresh button (CC 20) in FL Studio.
2. Device writes `context.json` (BPM, position, play state).
3. Bridge reads it, asks `/api/assets/recommend` for ranked matches.
4. Bridge writes `suggestions.json`; the device polls it and shows the top
   matches in the hint bar with prices.
5. Purchase happens in the web app (testnet SND, escrow contract). Loading
   the bought preset into a channel is the next iteration (via the bridge,
   the backend can drop the asset file next to the bridge folder).

## Status & next steps

- ✅ Device reads context and shows ranked recommendations (hint bar)
- ✅ Bridge is dependency-free and reuses the existing recommend endpoint
- ⏳ Load: bridge downloads the purchased asset to the project folder,
  device refreshes FL Studio's browser
- ⏳ Richer context: key, device/plugin names from the DAW engine
- ⏳ Purchase signing inside FL (relayer) — same pattern as Ableton

See [`ARCHITECTURE.md`](../ARCHITECTURE.md) for the shared design.
