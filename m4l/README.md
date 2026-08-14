# SoundHub for Ableton Live (Max for Live prototype)

> **SoundHub inside Ableton = the fastest way to buy finished sound assets
> while you're actually making music.** Buy-ready presets, loops and packs,
> paid with SND, loaded straight into your Live set.

This is a prototype **Max for Live device** that embeds the SoundHub
marketplace into Ableton Live:

- reads the `SoundHubMarket` catalog **directly from the chain** (public
  Base Sepolia RPC, no backend needed);
- reads the **current Live set BPM** and suggests relevant assets
  (context-aware, the first step toward a full recommendation engine);
- starts a **purchase** with SND (testnet); the escrow contract already
  handles payment + dispute window;
- **loads** the purchased asset into the project (drag-in; full
  browser/rack import is the next iteration).

## Files

| File | What it is |
|---|---|
| `SoundHub.amxd` | the device — drag into a Live track (Max for Live required) |
| `soundhub-device.js` | all device logic (catalog decoding, RPC, buying, BPM matching) |
| `build_amxd.py` | regenerates `SoundHub.amxd` from the patch definition (gzip JSON) |

## Install

1. Copy `SoundHub.amxd` + `soundhub-device.js` into your **User Library**
   (`~/Music/Ableton/User Library/Max for Live`).
2. In Ableton Live, drag `SoundHub.amxd` onto a **MIDI track**.
3. Open the device panel — you should see the three buttons and displays.

## Configure (testnet)

Send messages to the `js` object (or edit the `config` at the top of
`soundhub-device.js`):

```
rpc   https://sepolia.base.org      # Base Sepolia public RPC
market 0x396d6ad9D5EA19eE56318624b05bC6EEEa2d1F5C
token  0x37a6B3aD766ffb98673290A634490C8bF952DB2F
key    <your-testnet-private-key>   # testnet only — never a mainnet key
```

Current on-chain demo listing: **"Neon Dreams — Serum Preset Pack", 50 SND,
Commercial license** (listing #1). The catalog also carries metadata-only
entries (not yet on-chain) so recommendations are meaningful.

## Using it

- **refresh** — pulls the catalog from the market contract and shows it in
  the panel (name, price, license, seller);
- **suggest** — reads the Live set BPM and asks the SoundHub backend
  (`/api/assets/recommend`) for ranked matches — genre + BPM fit + device
  overlap, scored from DAW-verified asset metadata (see
  `backend/app/services/catalog.py`);
- **load** — fetches the suggested asset through the backend's short-lived
  signed-token endpoint (`/api/assets/{id}/token` → `/download`) so the
  loop can be tested end-to-end.

## Backend endpoints the device uses

| Endpoint | Purpose |
|---|---|
| `GET /api/assets` | catalog enriched with DAW metadata (public) |
| `GET /api/assets/recommend?bpm=&key=&genre=&devices=` | context-aware ranking (public) |
| `GET /api/assets/{id}/token` | short-lived download token (prototype: public) |
| `GET /api/assets/{id}/download?token=` | asset bytes with license headers |

Run the backend locally for suggestions/loads: `cd backend && .venv/bin/uvicorn
app.main:app --port 8000`, and point the device at it (`backend` message).

## What's stubbed (honest)

- **Purchase tx signing** — the actual escrow purchase (approve SND →
  `market.buy`) happens in the web app with the user's wallet. A full
  EIP-1559 signer inside M4L, or a relayer, is the next step.
- **Asset import** — downloads to a temp path and tells you to drag it in.
  Full import via Live's browser/rack API (`live.groove`, file browser
  refresh) is the next iteration.
- **Token gating** — the download token endpoint is public for the
  prototype; production checks the on-chain purchase (buyer == wallet,
  escrowed > 0) before issuing.
- **Recommendation features** — the engine scores BPM/genre/devices today;
  key is parsed but the M4L device sends BPM only for now (key/tracks/devices
  from Live API come next).

## Security

The `key` message configures a **testnet-only** private key. Never point
this device at a mainnet wallet. A production build must sign via
WalletConnect or a relayer, and the web3 layer should stay invisible to the
user (per the product principle).
