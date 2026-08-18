#!/usr/bin/env python3
"""soundhub — the desktop bridge CLI.

Minimal, honest DAW bridge: pull the open change requests, fix them in the
DAW, push the new bounce back — a new version is created and the fixed
requests are linked automatically (the same flow as the web upload).

    soundhub login --user producer --password '…'
    soundhub requests --session neon                      # open requests (markdown)
    soundhub requests --session neon --format csv --include-drafts
    soundhub locator --session neon                      # Ableton locator helper
    soundhub push mix.wav --session neon --message "v14: kick revised"

Config lives in ~/.soundhub.json (api url + token). Token can also come from
SOUNDHUB_TOKEN or --token. Uses only the standard library.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

CONFIG_PATH = os.path.expanduser("~/.soundhub.json")
DEFAULT_API = os.environ.get("SOUNDHUB_API_URL", "http://localhost:8000")


class CliError(Exception):
    pass


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def api_base(args) -> str:
    return (getattr(args, "api", None) or "").rstrip("/") or DEFAULT_API


def resolve_token(args, cfg: dict) -> str:
    token = getattr(args, "token", None) or os.environ.get("SOUNDHUB_TOKEN") or cfg.get("token") or ""
    if not token:
        raise CliError("No token — run `soundhub login` or set SOUNDHUB_TOKEN")
    return token


def http_json(method: str, url: str, *, token: str = "", json_body: dict | None = None,
              raw_data: bytes | None = None, content_type: str = "application/json",
              http=None) -> dict:
    """HTTP helper; `http` is injectable for tests (callable returning (status, body_bytes))."""
    if http is not None:
        status, body = http(method, url, token=token, data=raw_data, content_type=content_type)
        if status >= 400:
            raise CliError(f"HTTP {status}: {body.decode(errors='replace')[:300]}")
        return json.loads(body or b"{}")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif raw_data is not None:
        data = raw_data
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:300]
        raise CliError(f"HTTP {exc.code}: {body}")


def find_session(http, api: str, token: str, session: str) -> dict:
    """Resolve --session by id or name (case-insensitive) for the current user."""
    if session.isdigit():
        s = http_json("GET", f"{api}/api/sessions/{session}", token=token, http=http)
        return s
    rows = http_json("GET", f"{api}/api/sessions", token=token, http=http)
    needle = session.strip().lower()
    for s in rows:  # exact first, then prefix, then substring
        if s.get("name", "").strip().lower() == needle:
            return s
    for s in rows:
        if s.get("name", "").strip().lower().startswith(needle):
            return s
    for s in rows:
        if needle in s.get("name", "").strip().lower():
            return s
    raise CliError(f"Session '{session}' not found — check the name or use the numeric id")


def _multipart(fields: dict, file_field: str, filename: str, file_bytes: bytes, content_type: str) -> tuple[bytes, str]:
    boundary = "----soundhub" + uuid.uuid4().hex
    parts: list[bytes] = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n".encode()
    )
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(parts), boundary


def push_version(http, api: str, token: str, session_id: int, filepath: str, message: str) -> dict:
    with open(filepath, "rb") as f:
        data = f.read()
    body, boundary = _multipart({"message": message}, "file", os.path.basename(filepath), data, "audio/wav")
    return http_json(
        "POST",
        f"{api}/api/sessions/{session_id}/versions",
        token=token,
        raw_data=body,
        content_type=f"multipart/form-data; boundary={boundary}",
        http=http,
    )


def open_request_count(http, api: str, token: str, session_id: int) -> int:
    detail = http_json("GET", f"{api}/api/sessions/{session_id}", token=token, http=http)
    count = 0
    for v in detail.get("versions", []):
        for c in v.get("comments", []):
            if c.get("status") in ("open", "acknowledged", "in_progress"):
                count += 1
    return count


def _clock(ts: float) -> str:
    m = int(ts // 60)
    s = ts - m * 60
    return f"{m}:{s:06.3f}"


# ---------- commands ----------


def cmd_login(args, http=None) -> int:
    url = f"{api_base(args)}/api/auth/login"
    resp = http_json("POST", url, json_body={"username": args.user, "password": args.password}, http=http)
    save_config({
        "api": api_base(args),
        "token": resp["access_token"],
        "user": resp.get("user", {}).get("username", args.user),
    })
    print(f"✓ logged in as {resp['user']['username']} — token saved to {CONFIG_PATH}")
    return 0


def cmd_requests(args, http=None) -> int:
    cfg = load_config()
    token = resolve_token(args, cfg)
    api = api_base(args)
    session = find_session(http, api, token, args.session)
    qs = urllib.parse.urlencode({"format": args.format, "include_drafts": "true" if args.include_drafts else "false"})
    if http is not None:
        status, body = http("GET", f"{api}/api/sessions/{session['id']}/requests/export?{qs}", token=token)
        if status >= 400:
            raise CliError(f"HTTP {status}: {body.decode(errors='replace')[:300]}")
        sys.stdout.write(body.decode(errors="replace"))
    else:
        url = f"{api}/api/sessions/{session['id']}/requests/export?{qs}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            sys.stdout.write(resp.read().decode(errors="replace"))
    return 0


def cmd_push(args, http=None) -> int:
    cfg = load_config()
    token = resolve_token(args, cfg)
    api = api_base(args)
    session = find_session(http, api, token, args.session)
    version = push_version(http, api, token, session["id"], args.file, args.message)
    remaining = open_request_count(http, api, token, session["id"])
    print(f"✓ {version['label']} uploaded to “{session['name']}” — {version['message'] or 'no message'}")
    print(f"  open requests now: {remaining}  (fixed ones were linked automatically)")
    return 0


def cmd_locator(args, http=None) -> int:
    cfg = load_config()
    token = resolve_token(args, cfg)
    api = api_base(args)
    session = find_session(http, api, token, args.session)
    detail = http_json("GET", f"{api}/api/sessions/{session['id']}", token=token, http=http)
    print(f"# Ableton locator helper — {session['name']} (Round {detail.get('round_number', 1)})")
    print("# Drop a locator at each timestamp, then bounce the region.")
    n = 0
    for v in detail.get("versions", []):
        for c in v.get("comments", []):
            if c.get("status") not in ("open", "acknowledged", "in_progress"):
                continue
            n += 1
            body = c.get("body", "").replace('"', "'").replace("\n", " ")[:60]
            print(f'Locator {n}: "{body}" @ {_clock(c.get("time_s", 0))}   ({v["label"]} · {c.get("status")} · {c.get("author_name", "")})')
    if n == 0:
        print("No open requests — the list is clear.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="soundhub", description="Desktop bridge for SoundHub review sessions.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--api", help=f"API base url (default {DEFAULT_API} or SOUNDHUB_API_URL)")
    common.add_argument("--token", help="auth token (or SOUNDHUB_TOKEN, or saved by `login`)")
    p.add_argument("--api", help=argparse.SUPPRESS)
    p.add_argument("--token", help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", parents=[common], help="save api url + token to ~/.soundhub.json")
    login.add_argument("--user", required=True)
    login.add_argument("--password", required=True)

    req = sub.add_parser("requests", parents=[common], help="export open change requests")
    req.add_argument("--session", required=True, help="session name or id")
    req.add_argument("--format", choices=["markdown", "csv"], default="markdown")
    req.add_argument("--include-drafts", action="store_true", help="also list unsubmitted draft notes")

    push = sub.add_parser("push", parents=[common], help="upload a new bounce; fixed requests are linked automatically")
    push.add_argument("file", help="audio file (wav/mp3/…) to upload")
    push.add_argument("--session", required=True, help="session name or id")
    push.add_argument("--message", default="", help="changelog message, e.g. \"v14: kick revised\"")

    loc = sub.add_parser("locator", parents=[common], help="open requests as Ableton locator lines")
    loc.add_argument("--session", required=True, help="session name or id")
    return p


def main(argv: list[str] | None = None, http=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "login":
            return cmd_login(args, http=http)
        if args.command == "requests":
            return cmd_requests(args, http=http)
        if args.command == "push":
            return cmd_push(args, http=http)
        if args.command == "locator":
            return cmd_locator(args, http=http)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
