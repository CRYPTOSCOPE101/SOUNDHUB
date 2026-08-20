#!/usr/bin/env python3
"""snd — push a complete DAW project to SoundHub.

`snd push <project-dir>` scans the folder for DAW project files (.als/.rpp/
.flp/.cpr), parses them locally (tracks, instruments, plugins AND their
settings where the format stores them — REAPER PARAM lines, Ableton preset
refs), and pushes the whole snapshot as one versioned commit with a
SOUNDHUB-MANIFEST.json describing the structure.

`snd push <mix.als>` pushes a single DAW project file (fast mode: project +
extracted DAW metadata). With `--audio <master.wav> --stems <dir>` the push
also opens a review version (gapless A/B + stems) and returns the review URL.

    snd login --user producer --password '…'
    snd push ~/Projects/Neon --project "Neon Warehouse" --message "v12 bounce"
    snd push ~/Projects/Neon --include-media   # also upload audio/media files
    snd push ./Track_v12.als --audio ./master.wav --stems ./stems \
        --project "artist-track" --branch review/v12 --round 3 \
        --message "Round 3 candidate" --open --json

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
import json
import os
import sys
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from soundhub_cli import (
    CliError,
    api_base,
    cmd_login,
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
                "info": info if info else {"format_key": fmt, "unparsed": True},
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


def start_bridge(*, api: str, token: str, host: str = "127.0.0.1", port: int = 8765,
                 http=None) -> ThreadingHTTPServer:
    """Create (but don't serve) the localhost push bridge.

    Separate from `cmd_serve` so tests can start it with port=0 (OS-assigned)
    and read `server.server_address[1]` instead of racing for a fixed port.
    """
    import json as _json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep the console quiet
            pass

        def _reject_browser_origin(self) -> bool:
            """Block cross-origin browser calls (CSRF / DNS rebinding).

            The bridge pushes local files with the user's API token, so only
            same-machine, non-browser clients (M4L device, ReaScript) may call it.
            """
            if self.headers.get("Origin") or self.headers.get("Referer"):
                self._send(403, {"ok": False, "error": "cross-origin requests are not allowed"})
                return True
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
            if host and host not in ("localhost", "127.0.0.1", "::1"):
                self._send(403, {"ok": False, "error": f"unexpected Host header: {host}"})
                return True
            return False

        def _send(self, code: int, payload: dict) -> None:
            data = _json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self._reject_browser_origin():
                return
            path = self.path.rstrip("/")
            if path == "/health":
                self._send(200, {"ok": True, "service": "snd-bridge"})
            elif path.startswith("/comments"):
                # GET /comments?token=<share_token>&format=markdown|csv — the
                # DAW-side panel (REAPER ReaScript, M4L fallback) pulls open
                # review comments through the same local bridge.
                from urllib.parse import parse_qs, urlparse

                q = parse_qs(urlparse(self.path).query)
                token = (q.get("token") or [""])[0]
                if not token:
                    self._send(400, {"ok": False, "error": "missing share token (?token=…)"})
                    return
                fmt = (q.get("format") or ["markdown"])[0]
                if fmt not in ("markdown", "csv"):
                    self._send(400, {"ok": False, "error": "format must be markdown or csv"})
                    return
                try:
                    import urllib.request

                    url = f"{api}/api/sessions/public/{token}/requests/export?format={fmt}"
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
                    self._send(404, {"ok": False, "error": str(exc)})
                    return
                except OSError as exc:
                    self._send(404, {"ok": False, "error": str(exc)})
                    return
                data = text.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self._send(404, {"ok": False, "error": "not found"})

        def do_POST(self):
            if self._reject_browser_origin():
                return
            if not self.path.rstrip("/").endswith("/push"):
                self._send(404, {"ok": False, "error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                opts = _json.loads(self.rfile.read(length) or b"{}")
            except ValueError as exc:
                self._send(400, {"ok": False, "error": f"bad JSON body: {exc}"})
                return
            try:
                result = run_push(opts, api=api, token=token, http=http)
                self._send(200, result)
            except CliError as exc:
                self._send(400, {"ok": False, "error": str(exc)})
            except OSError as exc:
                self._send(400, {"ok": False, "error": str(exc)})

    return ThreadingHTTPServer((host, port), Handler)


def cmd_serve(args, http=None) -> int:
    """Run a localhost JSON bridge the Max for Live device calls for pushes.

    M4L can't run `shell` (blocked inside Live) and its `httprequest` mangles
    binary multipart, so the device POSTs a small JSON payload here and this
    tiny stdlib server runs the same `snd push` pipeline (preflight → atomic
    upload → review) and returns the stable contract.
    """
    cfg = load_config()
    token = resolve_token(args, cfg)
    api = api_base(args)

    srv = start_bridge(api=api, token=token, host=args.host, port=args.port, http=http)
    port = srv.server_address[1]
    print(f"✓ snd bridge listening on http://{args.host}:{port} — point the M4L device at it (bridge message)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="snd", description="Push complete DAW projects to SoundHub.")
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

    serve = sub.add_parser("serve", parents=[common], help="localhost JSON bridge for the Max for Live push button")
    serve.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8765, help="port (default 8765)")
    return p


def main(argv: list[str] | None = None, http=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "login":
            return cmd_login(args, http=http)
        if args.command == "push":
            return cmd_push(args, http=http)
        if args.command == "serve":
            return cmd_serve(args, http=http)
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
