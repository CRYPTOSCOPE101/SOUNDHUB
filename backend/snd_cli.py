#!/usr/bin/env python3
"""snd — push a complete DAW project to SoundHub.

`snd push <project-dir>` scans the folder for DAW project files (.als/.rpp/
.flp/.cpr), parses them locally (tracks, instruments, plugins AND their
settings where the format stores them — REAPER PARAM lines, Ableton preset
refs), and pushes the whole snapshot as one versioned commit with a
SOUNDHUB-MANIFEST.json describing the structure.

    snd login --user producer --password '…'
    snd push ~/Projects/Neon --project "Neon Warehouse" --message "v12 bounce"
    snd push ~/Projects/Neon --include-media   # also upload audio/media files

Reuses the same config/token as the `soundhub` CLI (~/.soundhub.json,
SOUNDHUB_TOKEN, --api/--token).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse

from soundhub_cli import (
    CliError,
    _multipart,
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


def cmd_push(args, http=None) -> int:
    cfg = load_config()
    token = resolve_token(args, cfg)
    api = api_base(args)
    root = os.path.abspath(args.dir)
    if not os.path.isdir(root):
        raise CliError(f"Not a directory: {root}")

    files = find_project_files(root, args.include_media)
    if not files:
        raise CliError(f"No project files found in {root} (add --include-media to upload audio too)")

    project_name = args.project or os.path.basename(root.rstrip(os.sep)) or "SoundHub project"
    project = None
    if args.project:
        project = _find_project(http, api, token, args.project)
        if project is None and not args.project.isdigit():
            # First push: auto-create the project with the requested name.
            project = http_json(
                "POST",
                f"{api}/api/projects",
                token=token,
                json_body={"name": args.project, "description": "pushed via snd"},
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

    manifest = build_manifest(project_name, files, root, args.include_media)
    parts: list[tuple[bytes, str]] = []
    for path in files:
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        with open(path, "rb") as f:
            data = f.read()
        content_type = "application/octet-stream"
        if os.path.splitext(path)[1].lower() in (".als", ".cpr"):
            content_type = "application/xml"
        parts.append((rel, data, content_type))

    # multipart: message + manifest + branch + one file per part
    boundary = "----snd" + __import__("uuid").uuid4().hex
    body = bytearray()
    for key, value in (("message", args.message or "snd push"), ("manifest", json.dumps(manifest)), ("branch", args.branch)):
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
    for rel, data, ctype in parts:
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{rel}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n".encode()
        )
        body += data
        body += b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    result = http_json(
        "POST",
        f"{api}/api/projects/{project['id']}/push",
        token=token,
        raw_data=bytes(body),
        content_type=f"multipart/form-data; boundary={boundary}",
        http=http,
    )
    print(f"✓ pushed “{project_name}” — commit #{result['commit_id']} · {result['file_count']} files · {result['branch']}")
    if manifest["daws"]:
        print(_summary(manifest["daws"]))
    else:
        print("  (no DAW project files parsed — add one, or check the folder)")
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

    push = sub.add_parser("push", parents=[common], help="push a project directory as one versioned commit")
    push.add_argument("dir", help="project directory with DAW files (.als/.rpp/.flp/.cpr)")
    push.add_argument("--project", help="existing project name/id, or a name to auto-create")
    push.add_argument("--message", default="snd push", help="commit message, e.g. \"v12 bounce\"")
    push.add_argument("--branch", default="main", help="branch to commit to")
    push.add_argument("--include-media", action="store_true", help="also upload audio/video/image files")
    return p


def main(argv: list[str] | None = None, http=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "login":
            return cmd_login(args, http=http)
        if args.command == "push":
            return cmd_push(args, http=http)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
