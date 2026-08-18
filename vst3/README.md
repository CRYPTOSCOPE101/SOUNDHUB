# SoundHub VST3 Companion — JUCE client for Cubase / FL Studio / any VST3 DAW

One JUCE-based VST3 plugin, shared across **Cubase, FL Studio and every other
VST3 host**. It is a *companion panel*, not a deep project integration: the
plugin talks to the local **SoundHub Agent** (`snd agent`, 127.0.0.1:8765),
which holds the token, talks to the SoundHub API, runs the `snd push`
pipeline, caches downloaded assets and opens review URLs in the browser.

```
Cubase / FL Studio / any VST3 DAW
   │  SoundHub.vst3 (JUCE panel)
   ▼  HTTP JSON on 127.0.0.1:8765
SoundHub Agent  (snd agent / snd serve)
   │  holds the token, runs snd push, caches assets, opens the browser
   ▼
SoundHub backend / review sessions
```

The plugin never sees the API URL or the auth token. All audio stays in the
host — the plugin does **no** audio processing (it is an `AudioProcessor`
skeleton with a pass-through processBlock) and never promises to parse or
diff the closed `.cpr` / `.flp` project format. Smart diffs come from the
`SOUNDHUB-MANIFEST.json` that `snd push` builds from the exported project +
renders, exactly as the CLI already does.

## Agent contract the panel uses

| Endpoint | What the panel gets |
|---|---|
| `GET /health` | `{"ok": true, "service": "snd-agent"}` |
| `GET /status` | api, user, cache stats — shown in the header |
| `POST /push` | `{"target": "/abs/path/Track.cpr", "project": "…", "branch": "…", "message": "…", "audio": "/abs/path/master.wav", "stems": "/abs/path/stems"}` → stable push contract (`commit_id`, `review_url`, `uploaded`, `deduplicated`) |
| `GET /comments?token=…&format=markdown` | open review comments (markdown) — the panel's todo list |
| `GET /reviews` | the user's review sessions with `review_url` (open one via `/open`) |
| `GET /assets?q=&genre=&bpm_min=…` | marketplace catalog search |
| `GET /assets/{id}/token` | short-lived download token |
| `GET /assets/{id}/download64?token=…` | base64 payload (text-safe for C++) |
| `POST /assets/{id}/install {"dir": …}` | download the asset into the Agent cache → local path |
| `POST /open {"url": …}` | open a review URL in the default browser (the plugin can't) |

All responses are `{"ok": true/false, …}`; errors carry `"error"`.

## Build (JUCE + CMake)

Requires CMake ≥ 3.22 and a C++17 compiler. The `CMakeLists.txt` fetches
JUCE 8.0.9 automatically, or uses a local checkout via `JUCE_ROOT`:

```bash
cd vst3
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j
# → build/SoundHub_artefacts/Release/VST3/SoundHub.vst3
```

Copy `SoundHub.vst3` into the host's VST3 folder:

- **Cubase**: `~/Library/Audio/Plug-Ins/VST3` (macOS) or
  `C:\Program Files\Common Files\VST3` (Windows)
- **FL Studio**: Options → Manage plugins → rescan, or drop the `.vst3`
  into `C:\Program Files\Common Files\VST3`

## Use

1. Start the backend + Agent once (from `backend/`):
   ```bash
   ./snd login --user demo --password demo123
   ./snd agent                                   # 127.0.0.1:8765
   ```
2. Insert **SoundHub** on any track in Cubase/FL Studio. The panel opens:
   - **Status** — Agent connection, logged-in user, cached assets.
   - **Push** — pick the current project file (`.cpr` / `.flp`), optionally
     the rendered master and a stems folder; the Agent runs the full
     `snd push` pipeline and the panel shows `commit_id` + the review URL.
   - **Open review** — pasted `/r/…` URL (or from the session list) is
     opened in the browser by the Agent (`POST /open`).
   - **Comments** — the open change requests for a share token, as the
     engineer's in-DAW todo list.
   - **Catalog / Install** — search assets, install into the Agent cache
     (or a chosen folder); load the file into the host from there.

The heavy lifting — multipart upload, preflight, atomic commit, review
session, stem matching, dedup — all happens in the Agent, so the realtime
audio thread in the plugin is never touched.

## Layout

```
CMakeLists.txt          JUCE project (VST3 format, FetchContent 8.0.9 / JUCE_ROOT)
Source/PluginProcessor  AudioProcessor skeleton (pass-through) + AgentClient
Source/PluginEditor     The SoundHub panel UI
Source/AgentClient      Thin HTTP/JSON client over juce::URL + WebInputStream
README.md               this file
```

## Honest limits

- **No project parsing inside the host.** VST3 gives the plugin transport,
  tempo and automation parameters — not the `.cpr`/`.flp` internals. The
  smart diff is built from the pushed manifest (tracks, plugins, renders,
  stems, notes), not from promising a full project diff of closed formats.
- **No audio processing** — this is a UI companion; keep the host audio
  thread untouched (all network I/O runs on `juce::ThreadPool` workers).
- **File selection** uses the host's native file dialog (`FileChooser`);
  the DAW's own export/render workflow stays standard.
