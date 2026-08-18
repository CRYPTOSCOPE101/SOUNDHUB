# Cubase & FL Studio — VST3 companion + SoundHub Agent + CLI

> **Decision (2026):** For Cubase and FL Studio, SoundHub ships as a **VST3
> companion plugin + local SoundHub Agent + `snd` CLI**. Only Ableton gets a
> "deep" integration (Max for Live can read the Live API: tempo, key, tracks,
> devices, browser). VST3 does not expose the project internals of `.cpr` /
> `.flp`, so we do not promise a full project diff inside the host — we build
> it from the exported manifest instead.

## Why not deep integration

The VST3 standard is built for **realtime audio processing and parameter
exchange with the host** — it does not give a plugin read/write access to the
project structure, the mixer, or the browser the way the Live API does
[steinbergmedia.github.io/vst3_dev_portal]. Two tempting-looking escape
hatches are real but limited:

| API | What it actually is | Why it is not a platform |
|---|---|---|
| **Cubase MIDI Remote API** | JavaScript scripts mapping **external MIDI controllers** to Cubase | not a general service-integration API |
| **FL Studio Python MIDI scripting** | scripts translating between hardware MIDI devices and FL Studio | fine for trigger actions (export/push), not an integration platform |

So the honest architecture is a **panel-companion**: a VST3 that can talk to
the DAW's world (transport, tempo, its own parameters) plus a local **Agent**
for everything that needs the network, auth and the filesystem.

## The three pieces

```
┌────────────────── DAW (Cubase / FL Studio / any VST3 host) ──────────────────┐
│  SoundHub.vst3 — JUCE companion panel (vst3/)                                │
│  catalog · preview · buy · install · push · review · comments · auth         │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │ HTTP JSON, 127.0.0.1:8765
                               ▼
┌────────────────────────────── SoundHub Agent ────────────────────────────────┐
│  snd agent (backend/, stdlib) — owns the token, talks to the API, runs      │
│  the `snd push` pipeline, caches downloaded assets, opens review URLs        │
│  in the browser. Endpoints: /push /comments /reviews /assets /open /status   │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               ▼
                    SoundHub backend · review sessions · smart diff
```

1. **SoundHub Agent** — a localhost service on `127.0.0.1` (default port
   8765). It stores the token (`~/.soundhub.json`), proxies the API, invokes
   `snd`, downloads/caches assets (`~/.soundhub/cache`) and opens browser
   review. The plugin/panel never sees the API URL or the token.
2. **`snd` CLI** — the single command shell: `login`, `status`, `push`,
   `review`, `assets search`, `assets install`, `agent`.
3. **SoundHub VST3 (JUCE)** — one shared client for Cubase, FL Studio and
   any other VST3 host. The plugin is a UI companion; it talks only to the
   Agent and does no audio processing.

## Capability split

| Capability | Ableton + M4L | Cubase + VST3 | FL Studio + VST3 |
|---|---|---|---|
| SoundHub panel in the DAW | ✅ | ✅ | ✅ |
| Store, search, preview, buy | ✅ | ✅ | ✅ |
| Asset install (download → cache → load) | ✅ | ✅ | ✅ |
| CLI `snd push` | ✅ | ✅ | ✅ |
| BPM / transport / key/tempo context | ✅ (Live API) | ◐ host/plugin data | ◐ host/plugin data |
| Full project structure + smart diff | realistic via Live API | not guaranteed | not guaranteed |
| Review + comments | ✅ | ✅ via Agent/API | ✅ via Agent/API |

## Export & push workflow (the honest smart diff)

The user renders master/stems with the DAW's own tools, then the VST panel or
the CLI hands the exported project + renders to the Agent:

```text
VST3 panel in Cubase / FL Studio
  → localhost SoundHub Agent
  → snd push pipeline (preflight → atomic upload → review version)
  → .cpr / .flp + master.wav + stems/ + SOUNDHUB-MANIFEST.json
```

`SOUNDHUB-MANIFEST.json` carries what the parsers extract locally — tempo,
time signature, tracks, instruments, plugins (and their settings where the
format stores them), renders, stems, user notes. **Smart diff is built from
that manifest** — never from promising to parse the closed project format
inside the host.

## Implementation status

| Piece | Where | Status |
|---|---|---|
| SoundHub Agent (localhost service) | `backend/snd_cli.py` (`snd agent` / `snd serve`) | ✅ endpoints: `/health /status /push /comments /reviews /assets /assets/{id}/token /assets/{id}/download64 /assets/{id}/install /open` |
| `snd` CLI shell | `backend/snd_cli.py` | ✅ `login · status · push · review · assets search · assets install · agent` |
| VST3 JUCE client | `vst3/` | 🚧 scaffold — panel + AgentClient, builds with CMake + JUCE 8.0.9 |
| Export workflow (render → manifest → push) | existing `snd push` | ✅ |
| Smart diff from exported manifest | existing diff engine | ✅ |

## Next steps

1. Compile `vst3/` in Cubase and FL Studio; wire the panel buttons to the
   live Agent contract (`make smoke` on the backend side).
2. Asset **preview playback** inside the panel (Agent streams `/assets/{id}/preview`,
   the plugin plays it via the host audio thread — needs a realtime-safe path).
3. Optional deep-parsing extras where formats allow it (e.g. more `.flp`
   chunks) — additive, never a dependency for the core loop.
