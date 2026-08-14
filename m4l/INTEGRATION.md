# SoundHub × Ableton Live — integration overview

> **SoundHub inside Ableton = the fastest way to buy finished sound assets
> while you're actually making music.**

This branch (`feat/ableton-integration`) holds everything about embedding
the SoundHub marketplace into Ableton Live: the architecture, the Max for
Live device, and the backend services that power it.

## What's here

| Piece | Location | Status |
|---|---|---|
| Integration architecture (layers, flows, constraints) | [`ARCHITECTURE.md`](../ARCHITECTURE.md) | ✅ |
| Max for Live device (catalog, suggest, load) | [`SoundHub.amxd`](SoundHub.amxd) + [`soundhub-device.js`](soundhub-device.js) | ✅ prototype |
| Device build script | [`build_amxd.py`](build_amxd.py) | ✅ |
| Device install/usage guide | [`README.md`](README.md) | ✅ |
| Recommendation service + catalog metadata | `backend/app/services/catalog.py` | ✅ |
| Asset endpoints (catalog / recommend / token / download) | `backend/app/routers/assets.py` | ✅ |
| This overview | [`INTEGRATION.md`](INTEGRATION.md) | ✅ |

## The loop (end-to-end)

```
Ableton Live (SoundHub.amxd)          SoundHub backend / chain
─────────────────────────────         ────────────────────────
refresh ──► market catalog (RPC)      SoundHubMarket (Base Sepolia)
suggest ──► BPM → /api/assets/        recommend scores genre + BPM
             recommend (ranked)       + key + device overlap
load    ──► /api/assets/{id}/token    short-lived HMAC token
             → /download              asset bytes + license headers
purchase    (web app, wallet)         approve SND → market.buy → escrow
```

## How to run it

1. **Backend** (needed for suggest/load):
   ```bash
   cd backend
   .venv/bin/uvicorn app.main:app --port 8000
   ```
2. **Device**: copy `SoundHub.amxd` + `soundhub-device.js` into your User
   Library, drag the device onto a MIDI track, point it at the backend
   (`backend http://127.0.0.1:8000`).
3. Buttons: **refresh** (catalog from chain), **suggest** (BPM-aware
   recommendations), **load** (fetch the suggested asset).

## Status & next steps

- ✅ Prototype device, recommendation service, signed asset delivery
- ⏳ Token gating: issue download tokens only after an on-chain purchase
  check (buyer == wallet, escrowed > 0)
- ⏳ Full Live import (browser refresh / rack insert), key/tracks/devices
  context from the Live API
- ⏳ WalletConnect signing inside M4L / relayer; FL Studio, Cubase, REAPER
  equivalents

See [`ARCHITECTURE.md`](../ARCHITECTURE.md) for the full design.
