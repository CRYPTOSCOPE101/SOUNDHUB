# SoundHub × Cubase — integration overview

> **SoundHub inside Cubase = the fastest way to buy finished sound assets
> while you're actually making music.**

This branch (`feat/cubase-integration`) holds the Cubase prototype of the
SoundHub-in-DAW experience. Cubase has no Max for Live and its scripting
surface is the **MIDI Remote API** (ES5 JavaScript), so the prototype is a
two-piece design: a MIDI Remote script for the context Cubase exposes, and a
standalone web panel for the marketplace UI.

## What's here

| Piece | Location | Status |
|---|---|---|
| Integration architecture (layers, flows, constraints) | [`ARCHITECTURE.md`](../ARCHITECTURE.md) | ✅ |
| Cubase MIDI Remote script (tempo/transport → MIDI) | [`midiremote/soundhub.js`](midiremote/soundhub.js) | ✅ prototype |
| SoundHub web panel (Web MIDI + backend) | [`panel/`](panel/) | ✅ prototype |
| Install/usage guide | [`README.md`](README.md) | ✅ |
| This overview | [`INTEGRATION.md`](INTEGRATION.md) | ✅ |
| Recommendation service + catalog metadata | `backend/app/services/catalog.py` | ✅ (shared) |
| Asset endpoints (catalog / recommend / token / download) | `backend/app/routers/assets.py` | ✅ (shared) |

## Why not "inside Cubase" like Ableton

The Ableton path works because Max for Live is a full JS runtime *inside*
Live with `live.object` access to the set. Cubase offers nothing equivalent:

- **No file I/O and no HTTP/IPC** in the MIDI Remote API — Steinberg
  explicitly blocks external process communication.
- **No project-tempo value binding** — tempo only arrives as a change
  callback (`mOnChangeTempoBPM`), transport state is bindable.
- Scripts are ES5 and run sandboxed against the MIDI Remote surface model.

So "SoundHub inside Cubase" cannot be a self-contained device the way it is
in Ableton. The honest prototype is:

```
Cubase (soundhub.js)          MIDI (CC)         SoundHub panel (web)      SoundHub backend
────────────────────          ─────────         ───────────────────        ────────────────
mOnChangeTempoBPM ──► CC 20 ────────────────►  Web MIDI → BPM field
mValue.mStart     ──► CC 21 ────────────────►  transport badge
mValue.mMetronome ──► CC 22 ────────────────►
                                               ──GET──► /api/assets/recommend?bpm=
                                               ◄─ranked items──┘
                                               catalog + prices rendered
```

## API surface used (all verified against the v1.3 reference)

| API | Purpose |
|---|---|
| `transport.mTimeDisplay.mOnChangeTempoBPM` | tempo change events (scaled 40-240 → 0-127) |
| `transport.mValue.mStart` | running state (value binding) |
| `transport.mValue.mMetronomeActive` | metronome state (value binding) |
| `makeCustomValueVariable(...).mMidiBinding.bindToControlChange(...)` | stream values to the panel over MIDI |
| `Web MIDI API` (`navigator.requestMIDIAccess`) | panel reads the CCs (Chrome/Edge) |
| `GET /api/assets/recommend` | BPM-matched, genre/devices-scored rankings |

## The loop (end-to-end)

1. Producer works in Cubase; the MIDI Remote script streams tempo and
   transport state over a virtual MIDI port.
2. The SoundHub panel (open in a browser next to Cubase) reads the port,
   keeps the BPM field live, and shows the transport badge.
3. **Suggest** asks the backend for ranked assets for that BPM; the panel
   shows name / genre / license / price.
4. Purchase happens in the web app (testnet SND, escrow). Loading the
   bought preset into a Cubase track is a future step.

## Status & next steps

- ✅ MIDI Remote script streams tempo (change callback) and transport state
- ✅ Web panel reads the port, recommends against the existing backend
- ⏳ Two-way: the MIDI Remote API can't receive data from the panel — panel
  is display-only; a relayer/HTTP bridge would need to live outside Cubase
- ⏳ Buy & load: panel downloads the purchased asset; placing it in a track
  needs a future path (user drag or a Cubase scripting evolution)
- ⏳ REAPER equivalent: REAPER has ReaScript (Lua/Python) with real file and
  HTTP access, so its branch will be closer to the FL Studio design

See [`ARCHITECTURE.md`](../ARCHITECTURE.md) for the shared design.
