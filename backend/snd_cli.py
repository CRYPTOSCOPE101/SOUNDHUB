#!/usr/bin/env python3
"""snd — the SoundHub command shell + localhost Agent.

`snd push <project-dir>` scans the folder for DAW project files (.als/.rpp/
.flp/.cpr), parses them locally (tracks, instruments, plugins AND their
settings where the format stores them — REAPER PARAM lines, Ableton preset
refs), and pushes the whole snapshot as one versioned commit with a
SOUNDHUB-MANIFEST.json describing the structure.

`snd push <mix.als>` pushes a single DAW project file (fast mode: project +
extracted DAW metadata). With `--audio <master.wav> --stems <dir>` the push
also opens a review version (gapless A/B + stems) and returns the review URL.

    snd login --user producer --password '…'
    snd status                                  # login state + agent cache
    snd push ~/Projects/Neon --project "Neon Warehouse" --message "v12 bounce"
    snd review --session neon --open            # list sessions / open a review
    snd assets search --q "dark bass" --bpm-min 126
    snd assets install 2 --dir ~/SoundHub/      # download asset to the cache
    snd agent                                   # localhost Agent (127.0.0.1:8765)

`snd agent` (alias: `snd serve`) runs the **SoundHub Agent**: a localhost
JSON service on 127.0.0.1 that holds the token, talks to the API, runs the
same push pipeline, downloads/caches assets and opens review URLs in the
browser — the single integration point for the JUCE VST3 companion panels
(Cubase, FL Studio and other VST3 DAWs), the Max for Live device and the
REAPER ReaScript panel. Endpoints:

    GET  /health                          → {"ok": true, "service": "snd-agent"}
    GET  /status                          → user, api, cache stats
    POST /push                            → snd push pipeline (JSON contract)
    GET  /comments?token=…&format=…       → open review comments (markdown/csv)
    GET  /reviews                         → the user's review sessions + links
    GET  /assets?q=&genre=&bpm_min=…      → marketplace catalog search
    GET  /assets/{id}/token               → short-lived download token
    GET  /assets/{id}/download64?token=   → text-safe (base64) asset payload
    POST /assets/{id}/install {"dir": …}  → download asset into the cache
    POST /open {"url": …}                 → open a review URL in the browser

Preflight before upload: file existence, size, extension, .als readability,
and — in review mode — at least one listenable audio file. The upload itself
is atomic: blobs first (content-addressed → dedup), then commit + review
version in one transaction, so a failed push never leaves a half-pushed
version. `--json` prints a stable contract for automation (M4L panel etc.):

    {"ok": true, "project_id": 1, "branch": "review/v12", "version_id": 3,
     "review_url": "http://localhost:5173/r/…",
     "uploaded": {"als": true, "master": true, "stems": 12},
     "deduplicated": 4}

Reuses the same config/token as the `soundhub` CLI (~/.soundhub.json,
SOUNDHUB_TOKEN, --api/--token).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from soundhub_cli import (
    CONFIG_PATH,
    CliError,
    api_base,
    cmd_login,
    find_session,
    http_json,
    load_config,
    resolve_token,
)

# DAW project files we can parse locally for the manifest.
DAW_EXTS = {".als", ".rpp", ".flp", ".cpr"}
# Media / preview files excluded unless --include-media.
MEDIA_EXTS = {
    ".wav", ".aif", ".aiff", ".mp3", ".flac", ".ogg", ".oga", ".m4a", ".mp4",
    ".wma", ".aac", ".wv", ".opus", ".mov", ".avi", ".mkv", ".png", ".jpg",
    ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff",
}
SKIP_NAMES = {".ds_store", "thumbs.db", ".git", ".svn", "__pycache__"}

ALLOWED_AUDIO = {"wav", "mp3", "flac", "ogg", "aif", "aiff", "m4a"}
ALLOWED_STEM_AUDIO = {"wav", "mp3", "flac", "aif", "aiff", "m4a", "ogg"}

AGENT_HOST = "127.0.0.1"
AGENT_PORT = 8765


def _agent_cache_dir() -> str:
    """Where the Agent stores downloaded assets (~/.soundhub/cache)."""
    return os.path.join(os.path.expanduser("~"), ".soundhub", "cache")


def _cached_asset_count() -> int:
    cache = _agent_cache_dir()
    try:
        return len([f for f in os.listdir(cache) if os.path.isfile(os.path.join(cache, f))])
    except OSError:
        return 0


def _frontend_url() -> str:
    return os.environ.get("SOUNDHUB_FRONTEND_URL", "http://localhost:5173").rstrip("/")


def _raw_get(url: str, *, token: str, http=None) -> bytes:
    """Fetch raw bytes (asset download). `http` is injectable for tests."""
    if http is not None:
        status, body = http("GET", url, token=token)
        if status >= 400:
            raise CliError(f"HTTP {status}: {body.decode(errors='replace')[:300]}")
        return body
    headers = {"Accept": "*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def agent_install_asset(api: str, token: str, listing_id: int, dest_dir: str | None = None, http=None) -> dict:
    """Download an asset through the Agent's cache (VST3 panel / CLI path).

    Issues a short-lived download token, fetches the payload, stores it under
    ~/.soundhub/cache (or `dest_dir`) as `<listing_id>-<filename>` and returns
    the local path + license info. The plugin panel asks the Agent to install
    and then loads the file from disk itself — the Agent never holds DAW state.
    """
    info = http_json("GET", f"{api}/api/assets/{listing_id}/token", token=token, http=http)
    dl_token = info.get("token") or ""
    if not dl_token:
        raise CliError("Asset token endpoint returned no token")
    data = _raw_get(f"{api}/api/assets/{listing_id}/download?token={dl_token}", token=token, http=http)
    filename = info.get("filename") or f"asset-{listing_id}.bin"
    dest = os.path.abspath(dest_dir) if dest_dir else _agent_cache_dir()
    os.makedirs(dest, exist_ok=True)
    path = os.path.join(dest, f"{listing_id}-{filename}")
    with open(path, "wb") as f:
        f.write(data)
    return {
        "ok": True,
        "listing_id": listing_id,
        "filename": filename,
        "cached_path": path,
        "license": info.get("license", ""),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }

def find_project_files(root: str, include_media: bool) -> list[str]:
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_NAMES]
        for fn in sorted(filenames):
            if fn.lower() in SKIP_NAMES or fn.startswith("."):
                continue
            ext = os.path.splitext(fn)[1].lower()
            if not include_media and ext in MEDIA_EXTS:
                continue
            out.append(os.path.join(dirpath, fn))
    return out


def build_manifest(project_name: str, files: list[str], root: str, include_media: bool) -> dict:
    """Parse every DAW file and describe tracks / instruments / plugins / settings."""
    from app.services.daw.registry import detect_format, get_daw_info

    daws: list[dict] = []
    for path in files:
        ext = os.path.splitext(path)[1].lower()
        if ext not in DAW_EXTS:
            continue
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            continue
        fmt = detect_format(path, data)
        if fmt is None:
            continue
        info = get_daw_info(path, data)
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        daws.append(
            {
                "path": rel,
                "format": fmt,
                "info": info.to_dict() if info else {"format_key": fmt, "unparsed": True},
            }
        )
    return {
        "project": project_name,
        "pushed_by": "snd",
        "include_media": include_media,
        "files": [os.path.relpath(p, root).replace(os.sep, "/") for p in files],
        "daws": daws,
        "settings_note": (
            "Settings are extracted where the DAW format stores them in the project file "
            "(REAPER PARAM lines, Ableton preset refs); the full plugin state lives in the "
            "pushed project files themselves."
        ),
    }


def _summary(daws: list[dict]) -> str:
    lines: list[str] = []
    for d in daws:
        info = d.get("info") or {}
        tracks = info.get("tracks") or []
        plugins = info.get("plugins") or []
        params = (info.get("extra") or {}).get("plugin_params") or {}
        presets = (info.get("extra") or {}).get("presets") or []
        bits = [
            f"{len(tracks)} tracks",
            f"{len(plugins)} plugins",
            f"{len(params)} plugins with settings" if params else "",
            f"{len(presets)} presets" if presets else "",
        ]
        bpm = info.get("bpm")
        lines.append(f"  {d['format'].upper()}: {d['path']} — {', '.join(b for b in bits if b)}{f' @ {bpm:g} BPM' if bpm else ''}")
    return "\n".join(lines)


def _find_project(http, api: str, token: str, name: str) -> dict | None:
    rows = http_json("GET", f"{api}/api/projects", token=token, http=http)
    needle = name.strip().lower()
    for p in rows:
        if p.get("name", "").strip().lower() == needle or str(p.get("id")) == name.strip():
            return p
    return None


def _preflight_size(path: str, max_size: int) -> None:
    size = os.path.getsize(path)
    if size > max_size:
        raise CliError(f"File too large: {path} ({size} bytes > {max_size} max)")


def _preflight_daw_readable(path: str) -> None:
    """Check a single DAW file can actually be parsed before uploading it."""
    from app.services.daw.registry import detect_format, get_daw_info

    with open(path, "rb") as f:
        data = f.read()
    fmt = detect_format(path, data)
    if fmt is None:
        raise CliError(f"Cannot read {path} as a DAW project file — unknown format")
    if get_daw_info(path, data) is None:
        raise CliError(f"Cannot parse {path} as {fmt.upper()} — the file looks corrupt or truncated")


def _preflight_audio(path: str, allowed: set[str], kind: str, max_size: int) -> None:
    if not os.path.isfile(path):
        raise CliError(f"{kind.capitalize()} file not found: {path}")
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext not in allowed:
        raise CliError(f"Unsupported {kind} audio format '{ext}'. Allowed: {', '.join(sorted(allowed))}")
    _preflight_size(path, max_size)


def _preflight_stems_dir(path: str, max_size: int) -> list[str]:
    if not os.path.isdir(path):
        raise CliError(f"Stems directory not found: {path}")
    stems: list[str] = []
    for fn in sorted(os.listdir(path)):
        full = os.path.join(path, fn)
        if not os.path.isfile(full):
            continue
        ext = os.path.splitext(fn)[1].lower().lstrip(".")
        if ext not in ALLOWED_STEM_AUDIO:
            continue
        _preflight_size(full, max_size)
        stems.append(full)
    if not stems:
        raise CliError(
            f"No audio stems found in {path} (allowed: {', '.join(sorted(ALLOWED_STEM_AUDIO))})"
        )
    return stems


def run_push(opts: dict, *, api: str, token: str, http=None) -> dict:
    """Shared push pipeline: preflight → multipart upload → contract dict.

    `opts` keys: target (DAW file or dir), include_media, audio, stems,
    project, branch, round, message. Returns the JSON contract exactly as
    the server replied. Used by `snd push` (CLI) and `snd serve` (the local
    bridge the Max for Live device talks to).
    """
    from app.config import MAX_UPLOAD_SIZE

    target = os.path.abspath(opts["target"])
    include_media = bool(opts.get("include_media"))

    # ---- resolve what to push: a DAW file or a project directory ----
    if os.path.isdir(target):
        root = target
        project_files = find_project_files(root, include_media)
        if not project_files:
            raise CliError(f"No project files found in {root} (add --include-media to upload audio too)")
        # the same readability preflight as single-file mode applies to every
        # DAW project file inside the folder — a corrupt .als must never slip
        # through the directory path and end up on the server
        for p in project_files:
            if os.path.splitext(p)[1].lower() in DAW_EXTS:
                _preflight_daw_readable(p)
    elif os.path.isfile(target):
        ext = os.path.splitext(target)[1].lower()
        if ext not in DAW_EXTS:
            raise CliError(f"Unsupported project file type '{ext}' — expected one of: {', '.join(sorted(DAW_EXTS))}")
        _preflight_size(target, MAX_UPLOAD_SIZE)
        _preflight_daw_readable(target)
        root = os.path.dirname(target) or "."
        project_files = [target]
    else:
        raise CliError(f"Not found: {target}")

    for p in project_files:
        _preflight_size(p, MAX_UPLOAD_SIZE)

    # ---- review materials preflight ----
    audio_path = os.path.abspath(opts["audio"]) if opts.get("audio") else None
    if audio_path:
        _preflight_audio(audio_path, ALLOWED_AUDIO, "master", MAX_UPLOAD_SIZE)
    stem_files = _preflight_stems_dir(opts["stems"], MAX_UPLOAD_SIZE) if opts.get("stems") else []
    if (audio_path or stem_files) and audio_path is None:
        raise CliError("Review mode requires --audio (the master) — stems attach to the master version")

    project_name = opts.get("project") or os.path.basename(root.rstrip(os.sep)) or "SoundHub project"
    project = None
    if opts.get("project"):
        project = _find_project(http, api, token, opts["project"])
        if project is None and not opts["project"].isdigit():
            # First push: auto-create the project with the requested name.
            project = http_json(
                "POST",
                f"{api}/api/projects",
                token=token,
                json_body={"name": opts["project"], "description": "pushed via snd"},
                http=http,
            )
    if project is None:
        created = http_json(
            "POST",
            f"{api}/api/projects",
            token=token,
            json_body={"name": project_name, "description": "pushed via snd"},
            http=http,
        )
        project = created

    manifest = build_manifest(project_name, project_files, root, include_media)
    boundary = "----snd" + uuid.uuid4().hex
    body = bytearray()
    fields = [("message", opts.get("message") or "snd push"), ("manifest", json.dumps(manifest)), ("branch", opts.get("branch") or "main")]
    if opts.get("round"):
        fields.append(("round", str(opts["round"])))
    for key, value in fields:
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()

    def _add_file(field: str, path: str, rel: str | None = None) -> None:
        with open(path, "rb") as f:
            data = f.read()
        name = rel or os.path.basename(path)
        body.extend(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n".encode()
        )
        body.extend(data)
        body.extend(b"\r\n")

    for path in project_files:
        _add_file("files", path, rel=os.path.relpath(path, root).replace(os.sep, "/"))
    if audio_path:
        _add_file("audio", audio_path)
    for p in stem_files:
        _add_file("stems", p)
    body += f"--{boundary}--\r\n".encode()

    return http_json(
        "POST",
        f"{api}/api/projects/{project['id']}/push",
        token=token,
        raw_data=bytes(body),
        content_type=f"multipart/form-data; boundary={boundary}",
        http=http,
    )


def cmd_push(args, http=None) -> int:
    cfg = load_config()
    token = resolve_token(args, cfg)
    api = api_base(args)

    target = os.path.abspath(args.target)
    root = target if os.path.isdir(target) else os.path.dirname(target) or "."
    project_name = args.project or os.path.basename(root.rstrip(os.sep)) or "SoundHub project"

    result = run_push(
        {
            "target": args.target,
            "include_media": args.include_media,
            "audio": args.audio,
            "stems": args.stems,
            "project": args.project,
            "branch": args.branch,
            "round": args.round,
            "message": args.message,
        },
        api=api,
        token=token,
        http=http,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"✓ pushed “{project_name}” — commit #{result.get('commit_id', '?')} · {result.get('file_count', '?')} files · {result.get('branch', '?')}")
    if result.get("review_url"):
        print(f"  review: {result['review_url']}")
        if args.open:
            webbrowser.open(result["review_url"])
    print("  (DAW metadata parsed locally — see the commit tree for the manifest)")
    return 0


def start_bridge(*, api: str, token: str, host: str = AGENT_HOST, port: int = AGENT_PORT,
                 http=None, user: str = "", frontend: str = "") -> ThreadingHTTPServer:
    """Create (but don't serve) the localhost SoundHub Agent.

    Separate from `cmd_serve` so tests can start it with port=0 (OS-assigned)
    and read `server.server_address[1]` instead of racing for a fixed port.
    The Agent holds the token and proxies to the backend, so the VST3
    companion panels / M4L device / ReaScript never see the API URL or the
    token — they only ever talk to 127.0.0.1.
    """
    frontend = frontend or _frontend_url()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep the console quiet
            pass

        def _send(self, code: int, payload: dict) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _bad(self, msg: str, code: int = 400) -> None:
            self._send(code, {"ok": False, "error": msg})

        # ---- GET routes ----

        def _proxy_catalog(self, qs: dict) -> None:
            allowed = ("q", "genre", "bpm_min", "bpm_max", "key", "license", "format", "plugin", "limit")
            params = {k: v[0] for k, v in qs.items() if k in allowed and v}
            query = urllib.parse.urlencode(params)
            try:
                items = http_json("GET", f"{api}/api/assets?{query}", token=token, http=http)
            except CliError as exc:
                self._bad(str(exc), 502)
                return
            self._send(200, {"ok": True, "count": len(items), "items": items})

        def _asset_route(self, parts: list[str], qs: dict) -> None:
            # parts like ["", "assets", "<id>", "token"]
            try:
                listing_id = int(parts[2])
            except (IndexError, ValueError):
                self._bad("asset id must be an integer")
                return
            kind = parts[3] if len(parts) > 3 else ""
            try:
                if kind == "token":
                    info = dict(http_json("GET", f"{api}/api/assets/{listing_id}/token", token=token, http=http))
                    info["ok"] = True
                    self._send(200, info)
                elif kind == "download64":
                    dl = (qs.get("token") or [""])[0]
                    if not dl:
                        self._bad("missing ?token=… (issue one via /assets/{id}/token)")
                        return
                    info = dict(http_json("GET", f"{api}/api/assets/{listing_id}/download64?token={dl}", token=token, http=http))
                    info["ok"] = True
                    self._send(200, info)
                else:
                    self._bad("unknown asset action — use /assets/{id}/token or /assets/{id}/download64", 404)
            except CliError as exc:
                self._bad(str(exc), 502)

        def _reviews(self) -> None:
            try:
                rows = http_json("GET", f"{api}/api/sessions", token=token, http=http)
            except CliError as exc:
                self._bad(str(exc), 502)
                return
            for r in rows:
                tok = r.get("share_token") or ""
                r["review_url"] = f"{frontend}/r/{tok}" if tok else ""
            self._send(200, {"ok": True, "count": len(rows), "items": rows})

        def _comments(self, qs: dict) -> None:
            # GET /comments?token=<share_token>&format=markdown|csv — DAW-side
            # panels (VST3, REAPER ReaScript, M4L fallback) pull open review
            # comments through the same local Agent.
            tok = (qs.get("token") or [""])[0]
            if not tok:
                self._bad("missing share token (?token=…)")
                return
            fmt = (qs.get("format") or ["markdown"])[0]
            if fmt not in ("markdown", "csv"):
                self._bad("format must be markdown or csv")
                return
            try:
                url = f"{api}/api/sessions/public/{tok}/requests/export?format={fmt}"
                if http is not None:
                    # test double: returns (status, body_bytes)
                    status, body = http("GET", url, token=None)
                    if status >= 400:
                        raise CliError(f"HTTP {status}: {body.decode(errors='replace')[:300]}")
                    text = body.decode(errors="replace")
                else:
                    with urllib.request.urlopen(url, timeout=30) as resp:
                        text = resp.read().decode(errors="replace")
            except CliError as exc:
                self._bad(str(exc), 404)
                return
            except OSError as exc:
                self._bad(str(exc), 404)
                return
            data = text.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            from urllib.parse import parse_qs, urlparse

            path = self.path.split("?", 1)[0].rstrip("/")
            qs = parse_qs(urlparse(self.path).query)
            if path == "/health":
                self._send(200, {"ok": True, "service": "snd-agent"})
            elif path == "/status":
                self._send(
                    200,
                    {
                        "ok": True,
                        "service": "snd-agent",
                        "api": api,
                        "user": user or "",
                        "cache_dir": _agent_cache_dir(),
                        "cached_assets": _cached_asset_count(),
                    },
                )
            elif path == "/assets":
                self._proxy_catalog(qs)
            elif path.startswith("/assets/"):
                self._asset_route(path.split("/"), qs)
            elif path == "/reviews":
                self._reviews()
            elif path == "/comments":
                self._comments(qs)
            else:
                self._send(404, {"ok": False, "error": "not found"})

        def do_POST(self):
            path = self.path.split("?", 1)[0].rstrip("/")
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                opts = json.loads(raw or b"{}")
            except ValueError as exc:
                self._send(400, {"ok": False, "error": f"bad JSON body: {exc}"})
                return

            if path == "/open":
                url = (opts.get("url") or "").strip()
                if not url.startswith(("http://", "https://")):
                    self._bad("url must be http(s)")
                    return
                webbrowser.open(url)
                self._send(200, {"ok": True, "opened": url})
                return

            if path.startswith("/assets/") and path.endswith("/install"):
                parts = path.split("/")
                try:
                    listing_id = int(parts[2])
                except (IndexError, ValueError):
                    self._bad("asset id must be an integer")
                    return
                try:
                    result = agent_install_asset(api, token, listing_id, opts.get("dir"), http=http)
                    self._send(200, result)
                except CliError as exc:
                    self._bad(str(exc))
                except OSError as exc:
                    self._bad(str(exc))
                return

            if not path.endswith("/push"):
                self._send(404, {"ok": False, "error": "not found"})
                return
            try:
                result = run_push(opts, api=api, token=token, http=http)
                self._send(200, result)
            except CliError as exc:
                self._bad(str(exc))
            except OSError as exc:
                self._bad(str(exc))

    return ThreadingHTTPServer((host, port), Handler)


def cmd_serve(args, http=None) -> int:
    """Run the localhost SoundHub Agent.

    The VST3 companion panels (Cubase / FL Studio / other VST3 DAWs), the Max
    for Live device and the REAPER ReaScript talk to this local service — it
    holds the token, runs the `snd push` pipeline (preflight → atomic upload →
    review), proxies the catalog, caches assets and opens review URLs in the
    browser. Only ever listens on 127.0.0.1.
    """
    cfg = load_config()
    token = resolve_token(args, cfg)
    api = api_base(args)
    frontend = getattr(args, "frontend", None) or _frontend_url()

    srv = start_bridge(api=api, token=token, host=args.host, port=args.port,
                       http=http, user=cfg.get("user", ""), frontend=frontend)
    port = srv.server_address[1]
    print(f"✓ SoundHub Agent on http://{args.host}:{port} — point the VST3 panel / M4L device at it", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


def cmd_status(args, http=None) -> int:
    """`snd status` — login state, agent cache, whether the Agent is running."""
    cfg = load_config()
    api = api_base(args)
    token = cfg.get("token", "")
    print(f"SoundHub · api: {api}")
    print(f"  user:      {cfg.get('user') or '(not logged in — run `snd login`)'}")
    print(f"  token:     {'saved → ' + CONFIG_PATH if token else 'missing — run `snd login`'}")
    print(f"  cache:     {_agent_cache_dir()} ({_cached_asset_count()} asset(s))")
    running = False
    try:
        with urllib.request.urlopen(f"http://{AGENT_HOST}:{AGENT_PORT}/health", timeout=2) as r:
            running = r.status == 200
    except OSError:
        pass
    print(
        f"  agent:     {'running on http://' + AGENT_HOST + ':' + str(AGENT_PORT)}"
        if running
        else f"  agent:     not running — `snd agent` starts it (the VST3 panel needs it)"
    )
    return 0


def cmd_review(args, http=None) -> int:
    """`snd review` — list the user's review sessions, or open one by name."""
    cfg = load_config()
    token = resolve_token(args, cfg)
    api = api_base(args)
    if args.session:
        session = find_session(http, api, token, args.session)
        url = _frontend_url() + "/r/" + (session.get("share_token") or "") if session.get("share_token") else ""
        print(f"{session.get('name')} · {session.get('status')} · {session.get('version_count', 0)} version(s)")
        if url:
            print(f"  review: {url}")
            if args.open:
                webbrowser.open(url)
        else:
            print("  (no share link on this session)")
        return 0
    rows = http_json("GET", f"{api}/api/sessions", token=token, http=http)
    if not rows:
        print("No review sessions yet — `snd push --audio master.wav` opens one.")
        return 0
    print(f"{'ID':>4}  {'NAME':<28} {'STATUS':<13} {'VERSIONS':>8}  REVIEW LINK")
    for s in rows:
        tok = s.get("share_token") or ""
        url = f"{_frontend_url()}/r/{tok}" if tok else "—"
        print(f"{s.get('id', 0):>4}  {(s.get('name') or '')[:28]:<28} {(s.get('status') or ''):<13} {s.get('version_count', 0):>8}  {url}")
    return 0


def cmd_assets_search(args, http=None) -> int:
    """`snd assets search` — search the marketplace catalog."""
    cfg = load_config()
    token = resolve_token(args, cfg)
    api = api_base(args)
    params = {
        "q": args.q, "genre": args.genre, "bpm_min": args.bpm_min, "bpm_max": args.bpm_max,
        "key": args.key, "license": args.license, "format": args.format, "plugin": args.plugin,
        "limit": args.limit,
    }
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    rows = http_json("GET", f"{api}/api/assets?{qs}", token=token, http=http)
    if not rows:
        print("No matching assets — try fewer filters.")
        return 0
    print(f"{'ID':>3}  {'NAME':<34} {'FMT':<6} {'BPM':<10} {'KEY':<10} {'LICENSE':<10} {'SND':>6}")
    for a in rows:
        bpm = a.get("bpm")
        bpm_s = f"{bpm[0]}–{bpm[1]}" if bpm else "—"
        print(
            f"{a.get('listing_id', 0):>3}  {(a.get('name') or '')[:34]:<34} {(a.get('format') or '—'):<6} "
            f"{bpm_s:<10} {(a.get('key') or '—'):<10} {(a.get('license') or '—'):<10} {a.get('price_snd', '—'):>6}"
        )
    print("\ninstall: `snd assets install <ID> --dir /path/to/library`")
    return 0


def cmd_assets_install(args, http=None) -> int:
    """`snd assets install` — download an asset into the agent cache (or --dir)."""
    cfg = load_config()
    token = resolve_token(args, cfg)
    api = api_base(args)
    result = agent_install_asset(api, token, args.listing_id, args.dir, http=http)
    print(f"✓ {result['filename']} ({result['size']} bytes) → {result['cached_path']}")
    print(f"  license: {result['license'] or '—'} · sha256: {result['sha256']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="snd", description="SoundHub command shell + localhost Agent.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--api", help="API base url (default ~/.soundhub.json or SOUNDHUB_API_URL)")
    common.add_argument("--token", help="auth token (or SOUNDHUB_TOKEN, or saved by `login`)")
    p.add_argument("--api", help=argparse.SUPPRESS)
    p.add_argument("--token", help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", parents=[common], help="save api url + token")
    login.add_argument("--user", required=True)
    login.add_argument("--password", required=True)

    push = sub.add_parser(
        "push",
        parents=[common],
        help="push a DAW project file (.als/.rpp/.flp/.cpr) or a project directory as one versioned commit",
    )
    push.add_argument("target", help="DAW project file, or a project directory with DAW files")
    push.add_argument("--project", help="existing project name/id, or a name to auto-create")
    push.add_argument("--message", default="snd push", help="commit message, e.g. \"v12 bounce\"")
    push.add_argument("--branch", default="main", help="branch to commit to")
    push.add_argument("--include-media", action="store_true", help="also upload audio/video/image files (directory mode)")
    push.add_argument("--audio", help="master audio export (wav/mp3/…) — opens a review version for gapless A/B")
    push.add_argument("--stems", help="directory of stem renders to attach to the review version")
    push.add_argument("--round", type=int, default=0, help="review round number for the version (default: session round)")
    push.add_argument("--open", action="store_true", help="open the review URL in the browser after a successful push")
    push.add_argument("--json", action="store_true", help="machine-readable JSON output (stable contract for automation)")

    serve = sub.add_parser("serve", parents=[common], help="run the localhost SoundHub Agent (VST3 panels / M4L / ReaScript)")
    serve.add_argument("--host", default=AGENT_HOST, help=f"bind address (default {AGENT_HOST})")
    serve.add_argument("--port", type=int, default=AGENT_PORT, help=f"port (default {AGENT_PORT})")
    serve.add_argument("--frontend", default=None, help="frontend base url for review links (default SOUNDHUB_FRONTEND_URL or http://localhost:5173)")

    agent = sub.add_parser("agent", parents=[common], help="run the localhost SoundHub Agent (alias of `serve`)")
    agent.add_argument("--host", default=AGENT_HOST, help=f"bind address (default {AGENT_HOST})")
    agent.add_argument("--port", type=int, default=AGENT_PORT, help=f"port (default {AGENT_PORT})")
    agent.add_argument("--frontend", default=None, help="frontend base url for review links (default SOUNDHUB_FRONTEND_URL or http://localhost:5173)")

    status = sub.add_parser("status", parents=[common], help="show login state, agent cache and whether the Agent is running")

    review = sub.add_parser("review", parents=[common], help="list review sessions, or print/open one session's share link")
    review.add_argument("--session", help="session name or id (omit to list all)")
    review.add_argument("--open", action="store_true", help="open the review URL in the browser")

    assets = sub.add_parser("assets", parents=[common], help="marketplace catalog: search + install")
    asub = assets.add_subparsers(dest="assets_command", required=True)
    search = asub.add_parser("search", parents=[common], help="search the asset catalog")
    search.add_argument("--q", help="free-text search")
    search.add_argument("--genre", help="genre, e.g. techno, house")
    search.add_argument("--bpm-min", type=float)
    search.add_argument("--bpm-max", type=float)
    search.add_argument("--key", help="musical key, e.g. \"A minor\"")
    search.add_argument("--license", help="Personal | Commercial | Sync | Exclusive")
    search.add_argument("--format", help="als | cpr | rpp | flp | wav | midi | adg")
    search.add_argument("--plugin", help="plugin name, e.g. Serum")
    search.add_argument("--limit", type=int, default=10)
    install = asub.add_parser("install", parents=[common], help="download an asset to the agent cache (or --dir)")
    install.add_argument("listing_id", type=int, help="catalog listing id from `snd assets search`")
    install.add_argument("--dir", help="target directory (default ~/.soundhub/cache)")
    return p


def main(argv: list[str] | None = None, http=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "login":
            return cmd_login(args, http=http)
        if args.command == "push":
            return cmd_push(args, http=http)
        if args.command in ("serve", "agent"):
            return cmd_serve(args, http=http)
        if args.command == "status":
            return cmd_status(args, http=http)
        if args.command == "review":
            return cmd_review(args, http=http)
        if args.command == "assets":
            if args.assets_command == "search":
                return cmd_assets_search(args, http=http)
            if args.assets_command == "install":
                return cmd_assets_install(args, http=http)
    except CliError as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
