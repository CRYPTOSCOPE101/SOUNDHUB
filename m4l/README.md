# SoundHub for Ableton Live (Max for Live prototype)

> **References from Ableton's own GitHub org** (all MIT, studied for the
> future DAW bridge — nothing integrated yet):
> - [`Ableton/m4l-connection-kit`](https://github.com/Ableton/m4l-connection-kit)
>   — example M4L devices connecting Live to the outside world via **OSC**
>   (`udpsend`/`udpreceive`) and **JSON APIs**; the natural transport pattern
>   for the future “review comments in the DAW” panel.
> - [`Ableton/maxdevtools`](https://github.com/Ableton/maxdevtools) — Python
>   tooling to build/install Max packages from CI; candidate to replace the
>   hand-rolled `build_amxd.py` packaging when we ship a real panel.
> - [`Ableton/web-audio-sequencing`](https://github.com/Ableton/web-audio-sequencing)
>   — lookahead scheduling on the Web Audio clock; **already applied** to the
>   frontend A/B + reference players (gapless loop regions, see
>   `frontend/src/components/ABCompare.tsx` / `ReferenceCompare.tsx`).
> - `Ableton/Link` — tempo sync between devices — **not** used: it requires a
>   licensing agreement and is out of scope for review/delivery.

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
  browser/rack import is the next iteration);
- **pushes the current export** to SoundHub as a versioned commit (+ review
  session for the master) via the local `snd serve` bridge — the DAW-to-
  review pipeline from the Phase 16 contract, one button away from Live.

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
- **load** — auto-imports the suggested asset into the Live **User Library**: fetches it through the backend's short-lived signed-token endpoint (`/api/assets/{id}/token` → `/download64`), decodes the base64 payload and writes it to `User Library/SoundHub/` with the Max `file` object, then refreshes Live's file browser (`live.browser`);
- **push** — pushes the **current Live set** (`.als`) to SoundHub as one
  versioned commit; if you also run `snd serve` locally it posts the JSON
  payload to the bridge, which runs the full Phase 16 pipeline (preflight →
  atomic upload → review session) and shows the **review URL** in the panel.

### Push current export — how it works

`shell` is blocked inside Live and `httprequest` mangles binary multipart, so
push goes through a tiny localhost JSON bridge (a thin client over the
already-tested `snd push --json` contract):

```
[push] button → live_set.current_song_path (.als)
  → POST {target, project, branch, message} → http://127.0.0.1:8765/push
  → snd serve runs the real push pipeline (preflight + dedup + atomic commit
    + review session/version) → returns the stable JSON contract
  → panel shows "✓ pushed commit #N" + the review URL
```

Run the bridge once (any terminal), then press **push** in Live:

```bash
cd backend
./snd login --user demo --password demo123   # once
./snd serve                                  # localhost:8765, keeps running
```

Configure via messages to the `js` object (optional — defaults use the Live
set name as project and branch `main`):

```
bridge       http://127.0.0.1:8765
pushProject  artist-track
pushBranch   review/v12
pushMessage  "Round 3 candidate"
```

A fast push (just the `.als`) creates the versioned commit; adding a master
render path (`audio`) opens the review session so the client can do gapless
A/B — see the Phase 16 contract in the README.

## Backend endpoints the device uses

| Endpoint | Purpose |
|---|---|
| `GET /api/assets` | catalog enriched with DAW metadata (public) |
| `GET /api/assets/recommend?bpm=&key=&genre=&devices=` | context-aware ranking (public) |
| `GET /api/assets/{id}/token` | short-lived download token + asset metadata (prototype: public) |
| `GET /api/assets/{id}/download?token=` | asset bytes with license headers |
| `GET /api/assets/{id}/download64?token=` | text-safe base64 JSON variant (for M4L import) |
| `POST /push` (local bridge, port 8765) | JSON `{target, audio?, stems?, project?, branch?, round?, message?}` → Phase 16 push contract |

Run the backend locally for suggestions/loads: `cd backend && .venv/bin/uvicorn
app.main:app --port 8000`, and point the device at it (`backend` message).

## Auto-import — how it works

`shell` is blocked inside Live, and `httprequest` can mangle raw binary — so
import uses a text-safe path:

```
token (JSON, with filename/format/license)
  → /download64 (base64 JSON payload)
  → decode base64 in JS
  → `file` object writes bytes to User Library/SoundHub/<filename>
  → `live.browser` refresh (fallback: F5)
```

The file lands in Live's browser under **SoundHub** and can be dropped into
the rack. If the browser doesn't refresh automatically, press **F5**.

Configure the library folder if it's not the default macOS path:
`libraryDir /path/to/User Library`.

## Troubleshooting (Live user)

| Symptom in the panel | Cause | Fix |
|---|---|---|
| `Push failed (bridge unreachable? run snd serve)` | `snd serve` isn't running | run `./snd serve` in a terminal and keep it open |
| `Push failed: bad JSON body` | device ↔ bridge mismatch (shouldn't happen with the shipped patch) | reload the device, check `bridge` message points at `http://127.0.0.1:8765` |
| `Push failed: save the Live set first` | set was never saved | save the Live set (Cmd/Ctrl+S) before pushing |
| `Push failed: … Master file not found` | `audio` path configured but file missing | point `audio` at the real render path, or drop it to do a fast push |
| `Push failed: HTTP 401/403` | no valid session | run `./snd login --user … --password …` once |
| `Push failed: File too large` | .als above the upload limit | raise `MAX_UPLOAD_SIZE` in `backend/app/config.py` or trim media from the project |
| panel says `fast push (no review)` | no master render attached | add an `audio <path>` message so the push opens a review session for A/B |

Quick end-to-end check (without opening Live):

```bash
cd backend
./snd login --user demo --password demo123      # 1. auth
./snd serve &                                    # 2. bridge on :8765
curl -s http://127.0.0.1:8765/health             # 3. {"ok": true, "service": "snd-bridge"}
curl -s -X POST http://127.0.0.1:8765/push \
  -H 'Content-Type: application/json' \
  -d '{"target": "/path/to/Track.als", "project": "smoke", "branch": "main"}'
# 4. {"ok": true, "commit_id": N, …} — then open the returned review_url
```

If step 4 fails, re-run with `--json` for the machine-readable error:
`./snd push /path/to/Track.als --project smoke --json`.

## What's stubbed (honest)

- **Push current export needs `snd serve` running** — the bridge is a thin
  local process (`backend/snd serve`, stdlib only); the device shows a clear
  error if it's not up. A bundled/sidecar process inside the device is the
  next iteration.
- **Push uploads the `.als` of the current set** (plus master/stems only if
  paths are configured) — Live's own render-to-disk automation (export the
  current scene as a master WAV before pushing) is the natural next step.
- **One-click insert into a device** — the file is imported into the User
  Library and the browser, but dropping it onto a specific device/simpler
  still needs a drag (or a `live.object` insert step, next iteration).
- **Purchase tx signing** — the actual escrow purchase (approve SND →
  `market.buy`) happens in the web app with the user's wallet. A full
  EIP-1559 signer inside M4L, or a relayer, is the next step.
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
