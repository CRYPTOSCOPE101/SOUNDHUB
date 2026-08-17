# Changelog

All notable changes to SoundHub. Format: keep-it-simple — **what changed,
how to test, known limits**. Versioning follows `git tag` (see
[Releases in the README](README.md#releases)).

## [v0.2.0] — 2026-08-16 — DAW-to-review pipeline (`snd push` + bridge)

### What changed

- **`snd push`** — a CLI that pushes a DAW project to SoundHub as one
  versioned commit:
  - Fast mode: `.als`/`.cpr`/`.rpp`/`.flp` (or a project folder) + parsed
    DAW metadata (`SOUNDHUB-MANIFEST.json` in the commit tree).
  - Full review mode: `--audio master.wav --stems stems/` opens a public
    review session with gapless A/B and structured `StemAsset`s matched by
    logical name.
  - Preflight before upload (file exists, size, extension, `.als`
    readability); atomic commit/review creation (no half-pushed versions);
    content-addressed blobs → re-pushes deduplicate (`deduplicated` in the
    JSON output).
  - Stable `--json` contract: `{ok, project_id, branch, commit_id,
    version_id, session_id, share_token, review_url, uploaded, deduplicated}`.
- **`snd serve`** — localhost JSON bridge (port 8765) for the Max for Live
  push button: `GET /health`, `POST /push` with the same pipeline and
  contract. Error codes documented in the README.
- **Smart diff in review** — versions pushed from the DAW carry their commit;
  a «what changed» panel (owner + public) shows `BPM 128 → 132`, `+Pad`,
  `+Vital` instead of «binary file changed».
- **M4L push button UX spec** — Idle / Pushing / Success / Error states,
  documented in `m4l/README.md`.
- **CI** — backend (116 tests), contracts (hardhat), frontend build, plus a
  dedicated bridge smoke (`pytest -k bridge`).

### How to test

```bash
cd backend
./snd login --user demo --password demo123     # once
./snd push ./Track_v12.als --audio ./master.wav --stems ./stems \
    --project "artist-track" --branch review/v12 --round 3 --json
# → review_url; open it, add a note, compare versions, approve

./snd serve                                    # bridge on :8765
curl -s http://127.0.0.1:8765/health           # {"ok": true, "service": "snd-bridge"}
curl -s -X POST http://127.0.0.1:8765/push -H "Content-Type: application/json" \
  -d '{"target": "/abs/path/Track_v12.als"}'   # {"ok": true, "commit_id": N}
```

### Known limits

- **Bridge is a local process** — the M4L device needs `snd serve` running
  (Live blocks `shell`; `httprequest` mangles binary multipart). A native
  sidecar is the next step.
- **Not audited** — smart contracts pass the test suite but no professional
  security audit yet; testnet only.
- **Parser coverage is best-effort** — DAW formats are reverse-engineered;
  `.flp` currently reads header/tempo/channels (deep event parsing pending).
- **Review A/B needs ≥ 2 versions** — the first push with `--audio` opens
  the session; gapless A/B appears once a second version exists.

### Release checklist

Run before tagging a release (same cases CI covers in `pytest -k bridge`):

1. **Bridge up** — `./snd serve` starts and stays on `:8765`.
2. **Health OK** — `curl -s http://127.0.0.1:8765/health` → `{"ok": true, "service": "snd-bridge"}`.
3. **Fast push OK** — `POST /push` with a real `.als` → `{"ok": true, "commit_id": N}`.
4. **Idempotent re-push deduped** — same payload again → same `commit_id`, `deduplicated` > 0, no new blobs.
5. **Negative JSON fails as expected** — missing target / malformed body → `400` + `{"ok": false, "error": …}`.
6. **CI green** — backend (incl. bridge smoke), contracts, frontend build.

All five bridge checks are automated in `tests/test_snd_project.py` (`-k bridge`),
so the checklist is a manual confirmation of what CI already asserts.

## [Unreleased] — Native sidecar (in-Live push)

### What changed

- **`m4l/sidecar.js` — native Node.js sidecar for the push button.** Max
  8.5+ ships a Node.js runtime for `node.script`, so the device now runs the
  push pipeline **inside Live**: the sidecar reads the `.als` from disk and
  posts a real multipart body straight to the backend. No external `snd
  serve` process, no `shell` (blocked in Live), no binary-mangling
  `httprequest`. On older Max it falls back to the `snd serve` bridge
  (unchanged).
- The sidecar doubles as a plain CLI (`node sidecar.js push …`) with the
  same stable contract (`ok / project_id / commit_id / version_id /
  session_id / share_token / review_url / uploaded / deduplicated`) and the
  same client-side preflight (missing file, size, extension, `.als`
  readability, review-mode master gate, stems-without-master).
- Honest limit: the sidecar does **not** build the local
  `SOUNDHUB-MANIFEST.json` (that needs the Python parsers) — the backend
  re-parses pushed DAW files itself, so smart diff / tree analysis still
  work.
- Patch `SoundHub.amxd` rebuilt with a `node.script` object (`sidecar`),
  device JS tries the sidecar first, falls back to the bridge.
- **Deep `.flp` parsing** — the FL parser now reads the `FLdt` event stream
  instead of just the header: per-channel names/types (instrument, sampler,
  layer, …), plugins per channel (including VST factory names from the
  `Plugin.Data` blob), and patterns with note counts. Smart diff on `.flp`
  now shows `+Pad`, `+Vital`, `BPM 140 → 150` instead of only a binary
  hexdump.
- **Smart diff UI polish** — the review diff panel now badges bpm/time-
  signature changes as `~ changed` (not `+ added`), shows a change counter in
  the header, and colorizes raw diff lines (`+` green, `−` red, `@@` hunks
  blue).
- **Engineer reputation & verification** — public portfolios now carry a
  reputation block computed from **real platform data** (delivered packages,
  approved sessions, avg rounds to approval, on-time rate) — nothing
  self-reported except the profile text. `✓ Verified` appears only for
  wallet-linked accounts (signature-checked at login). Engineers edit their
  bio / specialty / location via `PATCH /api/auth/me`.
- **USDC checkout on Base** — a second payment layer beside Stripe, no
  custodial step: the client gets payment terms (payee wallet, exact USDC
  amount, token + chain), sends USDC from their own wallet, then the
  transfer is verified on-chain by tx hash (`POST /webhooks/usdc` reads the
  receipt over JSON-RPC, checks the `Transfer` log amount + payee,
  idempotently marks the invoice / deposit / extra round paid). Works on the
  public delivery page and the owner view; `delivery_token` or `package_id`
  both accepted for verification. Disabled (503) until `SOUNDHUB_BASE_RPC_URL`
  is set.
- **Review comments in the DAW** — the M4L device now pulls **open review
  comments** straight into Live (fourth button, `shareToken` config): it
  reads the public export endpoint (`GET /api/sessions/public/{token}/requests/export`,
  new, share-token based — no login) and shows the current request plus the
  full list on the panel. The `snd serve` bridge gained the same
  `GET /comments?token=…` proxy.
- **REAPER integration** (`reaper/`) — a ReaScript (Lua) panel mirroring the
  M4L device: push the current `.rpp` via the `snd` CLI, pull open comments
  into the console via `reaper.URL_Get`. Install notes + config in
  `reaper/README.md`.
- **Style cleanup** — removed dead `[data-theme=…]` override blocks that
  duplicated the base (variable-driven) rules and hardcoded dark colors that
  fought the CSS variables; `.btn` now follows the theme instead of being
  near-black (invisible on dark mode).
- **Marketplace previews + license receipts** (merged from the pre-move
  worktree) — the catalog endpoint gained server-side filters (q / genre /
  bpm range / key / license / format / plugin) and every asset carries
  `duration_seconds` + a downsampled `waveform`; the marketplace page has an
  inline audio preview player and a catalog section with filters; purchases
  now issue a **signed license receipt** (`POST /api/assets/{id}/receipt`,
  `services/licenses.py`, verifiable client-side). The M4L device also
  gained genre/key set-context suggestions + a Node test hook.

### How to test

```bash
cd backend && .venv/bin/python -m pytest tests/test_usdc.py tests/test_reputation.py tests/test_parsers.py tests/test_daw_bridge.py -q
cd backend && .venv/bin/python -m pytest tests/test_snd_sidecar.py tests/test_snd_project.py -q   # needs node
cd frontend && npm run build
cd m4l && python3 build_amxd.py
```

### Known limits

- Sidecar requires **Max 8.5+** (first release with `node.script`); older
  Max uses the bridge fallback.
- No local manifest from the sidecar (`manifest_stored: false`) — server
  re-parse covers diff/tree.

## After v0.2.0 — post-release note

### What the smoke showed

Run against the live stack (backend :8000 + frontend :5173, Base Sepolia):

- **`snd push` fast + full** — `.als` + master + 3 stems → complete JSON
  contract (`ok`, `commit_id`, `version_id`, `review_url`, `uploaded`),
  review URL returns 200, stems attached.
- **Idempotency** — re-push of the same export → `deduplicated: 6`, no new
  blobs.
- **Smart diff** — v1 (128 BPM) → v2 (132, +Pad, +Vital) shows
  `BPM 128 → 132`, `+Pad`, `+Vital` on both the owner and public endpoints.
- **Bridge** — `GET /health`, `POST /push` golden path and all negative
  cases (bad JSON, missing target/master, stems w/o master) behave as
  documented; CI bridge smoke green.
- **Landing / integrations** — full-res MP4 demo frames, Cubase/FL Studio
  pages, footer wordmark render correctly; frontend build green.

### Planned for v0.2.1

- **Native sidecar / in-Live bridge** — remove the `snd serve` external
  process requirement (Live blocks `shell`; multipart via `httprequest`
  mangles binaries).
- **Deep `.flp` parsing** — per-channel plugins and patterns (currently
  header / tempo / channels only).
- **Smart diff in review UI polish** — richer raw-diff rendering and
  per-version «what changed» on the public page.
- **Seller reputation & verification badges** — trust layer on top of the
  DAW engine.

### Remaining limits (unchanged)

- Contracts are **not professionally audited** — testnet only.
- Parser coverage is best-effort (reverse-engineered formats).
- A/B needs ≥ 2 versions (first `--audio` push opens the session).
