# SoundHub for Cubase (prototype)

> **SoundHub inside Cubase = the fastest way to buy finished sound assets
> while you're actually making music.**

Cubase has no Max for Live, and its **MIDI Remote API** (ES5 JavaScript)
deliberately has **no file or HTTP access** — Steinberg blocks external
process communication. So this branch splits the integration the only way
that works:

1. **`midiremote/soundhub.js`** — a MIDI Remote API script that streams the
   project context Cubase exposes (tempo changes, transport running state,
   metronome) out over MIDI.
2. **`panel/`** — a standalone web panel that reads those MIDI messages,
   asks the SoundHub backend for BPM-matched recommendations and shows the
   catalog. The panel is the actual marketplace UI.

```
Cubase (soundhub.js)         MIDI          SoundHub panel (panel/)     SoundHub backend
────────────────────         ────          ──────────────────────       ────────────────
tempo change ──► CC 20  ──────────────►  read BPM (Web MIDI)
running      ──► CC 21  ──────────────►  transport badge
metronome    ──► CC 22  ──────────────►
                                        ──GET──► /api/assets/recommend
                                        ◄─items─┘  (ranked, BPM-scored)
                                        show catalog + prices
```

## Files

| File | What it is |
|---|---|
| `midiremote/soundhub.js` | Cubase MIDI Remote script — streams tempo/transport over MIDI |
| `panel/index.html` | the SoundHub panel UI |
| `panel/app.js` | Web MIDI listener + backend calls + rendering |
| `INTEGRATION.md` | architecture, API constraints, honest limitations |

## Install

1. **Backend** (needed for recommendations):
   ```bash
   cd backend
   .venv/bin/uvicorn app.main:app --port 8000
   ```
2. **MIDI Remote script**: Cubase → Studio → Studio Setup → MIDI Remote →
   right-click the info line → activate **Scripting Tools** → **Open MIDI
   Remote Script Directory**. Copy `midiremote/soundhub.js` to
   `<that dir>/SoundHub/soundhub.js`, reload scripts, and assign it to a
   (virtual) MIDI port pair.
3. **Panel**: serve `panel/` (e.g. `python3 -m http.server 8080 -d panel`)
   and open `http://localhost:8080` in Chrome/Edge (Web MIDI). Connect the
   SoundHub MIDI port, set the backend URL, click **Suggest**.

## Using it

- The panel auto-updates the BPM field when Cubase reports a tempo change
  (CC 20) and shows the transport state (CC 21/22).
- **Suggest** fetches ranked recommendations for the current BPM from the
  SoundHub backend and shows name / genre / license / price.

## What's stubbed (honest)

- **Tempo granularity** — the MIDI Remote API only reports tempo *changes*
  as an event (`mOnChangeTempoBPM`); there is no bindable `mTempo` value, so
  the panel may start with the manual BPM until Cubase reports a change.
- **Buy & load** — buying happens in the web app with the user's wallet.
  Importing the purchased preset into a Cubase track is a future step
  (the panel can download it; placing it needs the user or a later API).
- **One-way** — the MIDI Remote API can't receive arbitrary data from the
  panel, so the panel is display-only for now.
- **Web MIDI** — needs Chrome/Edge; Firefox lacks `requestMIDIAccess`.

## Security

The script only *reads* transport/tempo state and never signs anything.
Purchases stay in the web app on testnet SND.
