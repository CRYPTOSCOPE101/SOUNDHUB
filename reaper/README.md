# SoundHub for REAPER

The REAPER side of the DAW bridge — the same two actions the Max for Live
device gives Ableton users, for REAPER:

1. **Push** — commit the current REAPER project (`.rpp`) to SoundHub as a
   versioned snapshot (same pipeline as `snd push`: local parse → manifest →
   atomic upload → optional review version).
2. **Comments** — pull the **open review comments** (timestamped change
   requests) from the review session into the REAPER console, so the
   engineer's todo list lives in the DAW.

No plugin install, no compiled extension — it's a ReaScript (Lua) plus the
existing `snd` CLI / bridge.

## Install

1. Copy `soundhub_panel.lua` to your REAPER Scripts folder
   (`Options → Show REAPER resource path … → Scripts`).
2. `Actions → Show action list → New action → Load reascript…` and pick the
   file. REAPER registers two actions (the first script argument selects the
   mode); bind keys or add to a toolbar:
   - `soundhub_panel.lua` — **push** current project
   - `soundhub_panel.lua comments` — **load open comments**
3. Install the CLI + start the local **SoundHub Agent** once (the push path
   uses the same `snd push` pipeline the M4L sidecar uses):

   ```bash
   cd backend
   ./snd login --user demo --password demo123     # once
   ./snd agent                                    # localhost:8765 (alias: `snd serve`)
   ```

## Configure

Edit the `cfg` table at the top of the script (or call the exported
`extensions.snd_set_config(key, value)` from any other script):

```lua
cfg.bridge      = "http://127.0.0.1:8765"  -- local `snd serve`
cfg.backend     = "http://127.0.0.1:8000"  -- SoundHub backend
cfg.shareToken  = "AbC123…"                -- /r/<token> part of the review link
cfg.projectName = ""                       -- SoundHub project (default: .rpp name)
cfg.branch      = "main"
```

- **Push** — runs `snd push <current.rpp> --json` via `reaper.ExecProcess`
  (full preflight + local manifest, exactly the CLI contract). Save the
  project first; untitled sets can't be pushed (no path yet).
- **Comments** — `GET {backend}/api/sessions/public/{shareToken}/requests/export`
  — the same public endpoint the review page uses, no login. Output is the
  export markdown in the console plus a one-line summary:
  `[SoundHub] 3 open comment(s)`.

## How it differs from the Ableton/M4L device

| | Ableton (M4L) | REAPER |
|---|---|---|
| Push transport | native `node.script` sidecar inside Live | `snd push` CLI via `reaper.ExecProcess` |
| Comments | CSV parsed in the device, panel display | public export markdown in the console |
| HTTP | `httprequest` + `node.script` | `reaper.URL_Get` (async) |

Both talk to the same backend contract (`/api/projects/{id}/push`,
`/api/sessions/public/{token}/requests/export`) and the same bridge
(`snd serve` → `GET /comments?token=…&format=…`).

## Test

The backend side (public export + bridge `/comments`) is covered by
`tests/test_daw_bridge.py` and `tests/test_snd_project.py`; the Lua script
itself needs a REAPER install to run.
