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
Commercial license** (listing #1).

## Using it

- **refresh** — pulls the catalog from the market contract and shows it in
  the panel (name, price, license, seller);
- **suggest** — reads the Live set BPM and posts a genre tag to match
  assets (e.g. 128–132 BPM → `techno`; production version adds key, tracks,
  devices via the DAW engine);
- **buy** — sends the SND approve + market `buy` transaction; on testnet
  the same wallet can finish the flow in the web app, then **Load** brings
  the file into the project.

## What's stubbed (honest)

- **Purchase tx signing** — the device shows intent and defers the signed
  tx to the web app (same wallet). A full EIP-1559 signer inside M4L is the
  next step (or a backend relayer so the user never touches keys).
- **Asset import** — downloads to a temp path and tells you to drag it in.
  Full import via Live's browser/rack API (`live.groove`, file browser
  refresh) is the next iteration.
- **Recommendation engine** — BPM→genre mapping is a stub; the real one
  reuses the DAW engine (`.als` parse: BPM, key, tracks, devices, samples).

## Security

The `key` message configures a **testnet-only** private key. Never point
this device at a mainnet wallet. A production build must sign via
WalletConnect or a relayer, and the web3 layer should stay invisible to the
user (per the product principle).
