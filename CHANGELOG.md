# Changelog

All notable changes to SoundHub. Format: keep-it-simple — **what changed,
how to test, known limits**. Versioning follows `git tag` (see
[Releases in the README](README.md#releases)).

## [Unreleased] — DAW-to-review pipeline (`snd push` + bridge)

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
