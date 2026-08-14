# SoundHub inside Ableton Live — integration architecture

> **Positioning:** *SoundHub inside Ableton = the fastest way to buy finished
> sound assets while you're actually making music.* The marketplace stops
> being a website you visit and becomes a panel that lives in the producer's
> workflow. Purchase becomes a 1–2 click action at the moment of intent.

This document describes the architecture for embedding SoundHub into
Ableton Live (and, later, FL Studio / Cubase / REAPER). The first working
piece is the **Max for Live prototype** in `m4l/`.

## Why Max for Live (not a VST)

A VST3 plugin is an audio processor — it has no access to the Live browser,
the project, BPM, or device rack, and cannot "import a preset". The only
native path into Live's API (`live_set`: tempo, key, tracks, devices,
browser, drag-and-drop) is **Max for Live**: a JS runtime embedded in Live
(`js` objects, `live.object`, `live.thisdevice`). "Ableton plugin" therefore
means M4L.

## Components

```
┌─────────────────────── Ableton Live ───────────────────────┐
│  SoundHub.amxd (Max for Live device)                       │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐    │
│  │  UI panel    │   │  context     │   │  loader      │    │
│  │  catalog,    │◄──┤  BPM / key / │   │  fetch asset │    │
│  │  buy, load   │   │  tracks/dev  │   │  import to   │    │
│  └──────┬───────┘   └──────┬───────┘   │  browser/rack│    │
│         │                  │           └──────┬───────┘    │
└─────────┼──────────────────┼──────────────────┼────────────┘
          │ RPC (eth_call)   │                  │ HTTP
          ▼                  ▼                  ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  SoundHubMarket  │  │  DAW engine      │  │  SoundHub backend│
│  (on-chain,      │  │  (existing)      │  │  (existing)      │
│  Base Sepolia)   │  │  .als/.cpr/.rpp/ │  │  auth, repos,    │
│  listings, escrow│  │  .flp parsers    │  │  blobs, files    │
└──────────────────┘  └──────────────────┘  └──────────────────┘
          ▲                    ▲
          │ SND (ERC-20)       │ recommendations
          ▼                    │
┌──────────────────┐           │
│ signer / relayer │           │
│ WalletConnect or │           │
│ backend relayer  │           │
└──────────────────┘           │
```

### Layer 1 — Device (M4L, `m4l/`)
- **Catalog** — read `SoundHubMarket.listings()` + `nextListingId()` via
  public RPC (`eth_call`); decode Solidity structs in JS; no backend needed
  for browsing.
- **Context** — read `live_set.tempo` (and later key, track/device names)
  from the Live API; send to the recommendation service.
- **Buy** — approve SND → `market.buy(id)` → SND in escrow. Signing:
  WalletConnect (user wallet) or a backend relayer (invisible web3).
- **Load** — fetch the purchased asset bytes, save to the User Library,
  trigger Live browser refresh / rack import.

### Layer 2 — Recommendation service (backend, new)
- Input: project context from the device (BPM, key, genre, devices).
- Output: ranked catalog items.
- Engine: reuse the **DAW engine** (`backend/app/services/daw/`) — the same
  parsers that power smart diffs verify asset contents ("24 Serum presets
  inside, verified") and match context to assets.
- The M4L prototype ships with a stub BPM→genre mapping; this service is
  the production version.

### Layer 3 — Settlement (on-chain, done)
| Contract | Role in the flow |
|---|---|
| `SND` | payment rail; every purchase is denominated in it |
| `SoundHubMarket` | listings, escrow, dispute window (2d), refunds; arbiter = owner today, DAO later |
| `SoundHubRelease` | (optional) mint a Release NFT per listed pack: royalties, collaborator splits |
| `SoundHubGovernor` | platform governance: fees, curation, grants |

### Layer 4 — Asset delivery (backend, existing + new)
- Purchased asset bytes live in the content-addressed blob store (SHA-256
  dedup already implemented).
- New endpoint: authenticated, license-scoped download for the device
  (`GET /api/assets/{id}/download` with a short-lived token).
- For the demo, `assetUri` is a `soundhub://` repo path; production adds
  IPFS pinning.

## Purchase flow (happy path)

1. User opens Live, SoundHub panel shows the catalog (from RPC).
2. Panel reads BPM 128 → suggests techno/house assets ranked for context.
3. User clicks **Buy & Load** on "Dark Bass Patch (Serum)", 50 SND.
4. SND approved → `market.buy` → funds in escrow; panel shows "purchased".
5. Asset is fetched from the backend (license-scoped download).
6. File lands in the User Library → Live browser → user drags it into the
   rack (full auto-import: next iteration).
7. User confirms receipt (or the 2-day window passes) → seller paid.
   No spreadsheets, no DMs, no manual payouts.

## What "web3 invisible" means here

The user sees **Buy & Load** — not `approve`, not gas, not RPC. Details:

- Wallet pairing once via WalletConnect; key never leaves the user's wallet.
- Relayer option: backend signs on behalf of the wallet after an EIP-712
  intent (for users who don't want any wallet interaction).
- License tier shown before purchase: Personal / Commercial / Sync /
  Exclusive — bound to the purchase on-chain.

## Work streams (proposed order)

| # | Stream | Status |
|---|---|---|
| 1 | M4L device: catalog + BPM context + buy intent + load stub | ✅ prototype in `m4l/` |
| 2 | Recommendation service (DAW-engine backed) + `/api/recommend` | ⏳ next |
| 3 | Asset delivery endpoint (license-scoped download for the device) | ⏳ next |
| 4 | Full Live import (browser refresh, rack insert) | ⏳ |
| 5 | WalletConnect signing inside M4L / relayer | ⏳ |
| 6 | FL Studio / Cubase / REAPER equivalents | ⏳ later |

## Constraints

- **Don't break the producer's flow** — panel must be lightweight, no UI
  lock-ups; all RPC work async in the JS thread.
- **Don't break Live performance** — no polling loops; refresh on demand.
- **Rights must be legible** — license tier + "can I use this in a
  commercial release?" answered before purchase.
- **Blockchain invisible** — a user who never opens a wallet must still be
  able to buy (relayer path) and load (backend path).
