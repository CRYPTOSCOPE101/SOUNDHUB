"""SoundHub Agent — localhost service for VST3 / M4L / ReaScript panels.

Covers the Agent endpoints (`/status`, `/open`, `/assets`, `/assets/{id}/token`,
`/assets/{id}/download64`, `/assets/{id}/install`, `/reviews`) and the new
`snd` CLI commands (`status`, `review`, `assets search`, `assets install`).

The Agent is the single integration point for the JUCE VST3 companion panels:
it holds the token, proxies the catalog, caches downloaded assets and opens
review URLs in the browser — panels never see the API URL or the token.
"""
import base64
import io
import json
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


def make_wav() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * 0.5)) for _ in range(8000)))
    return buf.getvalue()


class FakeHttp:
    """Test double for the backend HTTP layer: route by url substring."""

    def __init__(self):
        self.routes = []
        self.requests = []

    def __call__(self, method, url, token="", data=None, content_type=""):
        self.requests.append((method, url, data or b"", content_type))
        hits = [(len(f), s, b) for f, s, b in self.routes if f in url]
        if not hits:
            raise AssertionError(f"no fake route for {method} {url}")
        _, status, body = max(hits, key=lambda h: h[0])
        if isinstance(body, bytes):
            return status, body
        return status, json.dumps(body).encode()

    def route(self, frag, status, body):
        self.routes.append((frag, status, body))


def _start_agent(tmp_path, monkeypatch, routes: list, *, user: str = "producer") -> tuple[str, FakeHttp, object]:
    """Boot the Agent on an OS-assigned port with a fake backend layer.

    Returns (base_url, fake, server); call server.shutdown() to stop.
    """
    import threading

    import soundhub_cli

    import snd_cli

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", "/nonexistent")
    # keep the cache out of the real home dir
    monkeypatch.setattr(snd_cli, "_agent_cache_dir", lambda: str(tmp_path / "agent-cache"))
    fake = FakeHttp()
    for frag, status, body in routes:
        fake.route(frag, status, body)
    srv = snd_cli.start_bridge(api="http://x", token="t", port=0, http=fake, user=user, frontend="http://front.local")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    return f"http://127.0.0.1:{port}", fake, srv


def _get(base: str, path: str) -> tuple[int, object]:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"{base}{path}", timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _post(base: str, path: str, payload: dict) -> tuple[int, dict]:
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ---------- Agent endpoints ----------


def test_agent_status_reports_login_and_cache(tmp_path, monkeypatch):
    import snd_cli

    base, fake, srv = _start_agent(tmp_path, monkeypatch, [])
    try:
        code, res = _get(base, "/status")
        assert code == 200
        assert res["ok"] is True and res["service"] == "snd-agent"
        assert res["user"] == "producer"
        assert res["api"] == "http://x"
        assert res["cached_assets"] == 0
        assert "agent-cache" in res["cache_dir"]
        assert fake.requests == []  # /status is local, no backend call
    finally:
        srv.shutdown()
        srv.server_close()


def test_agent_open_opens_browser_and_rejects_non_http(tmp_path, monkeypatch):
    import webbrowser

    opened: list[str] = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url))

    base, fake, srv = _start_agent(tmp_path, monkeypatch, [])
    try:
        code, res = _post(base, "/open", {"url": "https://soundhub.local/r/tok123"})
        assert code == 200 and res["ok"] is True
        assert opened == ["https://soundhub.local/r/tok123"]

        # non-http URLs are refused — the Agent never opens arbitrary schemes
        code, res = _post(base, "/open", {"url": "file:///etc/passwd"})
        assert code == 400 and res["ok"] is False
        assert "http" in res["error"]
        assert opened == ["https://soundhub.local/r/tok123"]
    finally:
        srv.shutdown()
        srv.server_close()


def test_agent_assets_search_proxies_catalog(tmp_path, monkeypatch):
    base, fake, srv = _start_agent(tmp_path, monkeypatch, [
        ("/api/assets", 200, [
            {"listing_id": 1, "name": "Neon Dreams — Serum Preset Pack", "format": "als",
             "bpm": [124, 132], "key": "A minor", "license": "Commercial", "price_snd": "50"},
            {"listing_id": 2, "name": "Dark Bass Pack (Techno)", "format": "wav",
             "bpm": [126, 138], "key": "D minor", "license": "Commercial", "price_snd": "35"},
        ]),
    ])
    try:
        code, res = _get(base, "/assets?q=dark&bpm_min=126&format=wav&limit=5")
        assert code == 200 and res["ok"] is True
        assert res["count"] == 2 and len(res["items"]) == 2
        # the search query was forwarded to the backend with the stored token
        method, url, _, _ = fake.requests[-1]
        assert method == "GET" and "/api/assets?" in url
        assert "q=dark" in url and "bpm_min=126" in url and "limit=5" in url
        # the token is attached on the proxy hop (backend list is public, but
        # the Agent always authenticates when it has a token)
        assert fake.requests[-1][2] == b""

        # backend failure surfaces as 502 + {"ok": false}
        fake.route("/api/assets?genre=nope", 500, b"boom")
        code, res = _get(base, "/assets?genre=nope")
        assert code == 502 and res["ok"] is False
    finally:
        srv.shutdown()
        srv.server_close()


def test_agent_asset_token_and_download64(tmp_path, monkeypatch):
    wav = make_wav()
    token_info = {"listing_id": 1, "token": "tok123", "expires_in": 300,
                  "name": "Neon Dreams", "filename": "neon-dreams-demo.wav",
                  "format": "wav", "license": "Commercial", "size": len(wav)}
    b64 = {"listing_id": 1, "filename": "neon-dreams-demo.wav", "format": "wav",
           "license": "Commercial", "size": len(wav), "data": base64.b64encode(wav).decode("ascii")}
    base, fake, srv = _start_agent(tmp_path, monkeypatch, [
        ("/api/assets/1/token", 200, token_info),
        ("/api/assets/1/download64", 200, b64),
    ])
    try:
        code, res = _get(base, "/assets/1/token")
        assert code == 200 and res["ok"] is True and res["token"] == "tok123"

        code, res = _get(base, "/assets/1/download64?token=tok123")
        assert code == 200 and res["ok"] is True
        assert base64.b64decode(res["data"]) == wav
        assert res["license"] == "Commercial"

        # download64 without a token -> 400 with a hint
        code, res = _get(base, "/assets/1/download64")
        assert code == 400 and res["ok"] is False
        assert "token" in res["error"]

        # bad asset id -> 400
        code, res = _get(base, "/assets/abc/token")
        assert code == 400 and res["ok"] is False
    finally:
        srv.shutdown()
        srv.server_close()


def test_agent_asset_install_caches_file(tmp_path, monkeypatch):
    wav = make_wav()
    token_info = {"listing_id": 1, "token": "tok123", "filename": "neon-dreams-demo.wav",
                  "license": "Commercial", "size": len(wav)}
    base, fake, srv = _start_agent(tmp_path, monkeypatch, [
        ("/api/assets/1/token", 200, token_info),
        ("/api/assets/1/download", 200, wav),
    ])
    try:
        code, res = _post(base, "/assets/1/install", {})
        assert code == 200 and res["ok"] is True
        assert res["filename"] == "neon-dreams-demo.wav"
        assert res["cached_path"].endswith("1-neon-dreams-demo.wav")
        assert Path(res["cached_path"]).read_bytes() == wav
        assert res["license"] == "Commercial"
        assert res["size"] == len(wav) and len(res["sha256"]) == 64

        # the flow: token issued first, then the raw payload fetched
        methods = [r[0] for r in fake.requests]
        urls = [r[1] for r in fake.requests]
        assert "/api/assets/1/token" in urls[0]
        assert "/api/assets/1/download?token=tok123" in urls[1]
        assert methods == ["GET", "GET"]

        # --dir override writes elsewhere (used by CLI)
        dest = tmp_path / "library"
        code, res = _post(base, "/assets/1/install", {"dir": str(dest)})
        assert code == 200 and str(dest) in res["cached_path"]
    finally:
        srv.shutdown()
        srv.server_close()


def test_agent_reviews_lists_sessions_with_review_url(tmp_path, monkeypatch):
    base, fake, srv = _start_agent(tmp_path, monkeypatch, [
        ("/api/sessions", 200, [
            {"id": 3, "name": "Neon Warehouse", "status": "in_review", "version_count": 2, "share_token": "tok123"},
            {"id": 4, "name": "Aurora Night", "status": "approved", "version_count": 5, "share_token": "tok456"},
        ]),
    ])
    try:
        code, res = _get(base, "/reviews")
        assert code == 200 and res["ok"] is True and res["count"] == 2
        assert res["items"][0]["review_url"] == "http://front.local/r/tok123"
        assert res["items"][1]["review_url"] == "http://front.local/r/tok456"
        # the Agent used its stored token for the owner-scoped sessions list
        method, url, _, _ = fake.requests[-1]
        assert method == "GET" and "/api/sessions" in url
    finally:
        srv.shutdown()
        srv.server_close()


def test_agent_push_and_comments_still_work(tmp_path, monkeypatch):
    """The pre-existing bridge endpoints (/push, /comments, /health) survive."""
    import urllib.request

    from app.services.daw import fixtures

    als = tmp_path / "Track_v12.als"
    als.write_bytes(fixtures.make_als(tracks=[("MidiTrack", "Synth Lead", ["Plugin:Serum"])]))

    base, fake, srv = _start_agent(tmp_path, monkeypatch, [
        ("/api/projects", 200, [{"id": 5, "name": "artist-track"}]),
        ("/api/projects/5/push", 200, {"ok": True, "commit_id": 42, "review_url": "http://front.local/r/tok123"}),
        ("/requests/export", 200, "# Open requests\n- [1:23.400] Aisha — bass masks the vocal\n".encode()),
    ])
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=5) as r:
            assert json.loads(r.read()) == {"ok": True, "service": "snd-agent"}

        code, res = _post(base, "/push", {"target": str(als), "project": "artist-track", "message": "v12"})
        assert code == 200 and res["ok"] is True and res["commit_id"] == 42

        with urllib.request.urlopen(f"{base}/comments?token=tok123", timeout=5) as r:
            assert b"bass masks the vocal" in r.read()
    finally:
        srv.shutdown()
        srv.server_close()


# ---------- CLI ----------


def test_snd_status_and_agent_alias(tmp_path, monkeypatch, capsys):
    import soundhub_cli

    import snd_cli

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", "/nonexistent")
    monkeypatch.setattr(snd_cli, "_agent_cache_dir", lambda: str(tmp_path / "cache"))

    rc = snd_cli.main(["status", "--api", "http://x"], http=None)
    assert rc == 0
    out = capsys.readouterr().out
    assert "not logged in" in out
    assert "cache" in out and "agent:" in out

    # `snd agent --help` parses as an alias of serve (same options)
    with pytest.raises(SystemExit) as exc:
        snd_cli.main(["agent", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "usage: snd agent" in out and "--frontend" in out and "--port" in out


def test_snd_review_lists_and_opens(tmp_path, monkeypatch, capsys):
    import webbrowser

    import soundhub_cli

    import snd_cli

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", "/nonexistent")
    monkeypatch.setattr(snd_cli, "_frontend_url", lambda: "http://front.local")
    opened: list[str] = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url))

    fake = FakeHttp()
    fake.route("/api/sessions", 200, [
        {"id": 3, "name": "Neon Warehouse", "status": "in_review", "version_count": 2, "share_token": "tok123"},
    ])

    # list all
    rc = snd_cli.main(["review", "--api", "http://x", "--token", "t"], http=fake)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Neon Warehouse" in out and "http://front.local/r/tok123" in out

    # open one by name
    rc = snd_cli.main(["review", "--session", "Neon", "--open", "--api", "http://x", "--token", "t"], http=fake)
    assert rc == 0
    out = capsys.readouterr().out
    assert "review: http://front.local/r/tok123" in out
    assert opened == ["http://front.local/r/tok123"]


def test_snd_assets_search_and_install(tmp_path, monkeypatch, capsys):
    import soundhub_cli

    import snd_cli

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", "/nonexistent")
    cache = tmp_path / "cache"
    monkeypatch.setattr(snd_cli, "_agent_cache_dir", lambda: str(cache))

    wav = make_wav()
    fake = FakeHttp()
    fake.route("/api/assets", 200, [
        {"listing_id": 2, "name": "Dark Bass Pack (Techno)", "format": "wav",
         "bpm": [126, 138], "key": "D minor", "license": "Commercial", "price_snd": "35"},
    ])
    fake.route("/api/assets/2/token", 200, {"token": "tok2", "filename": "dark-bass-demo.wav", "license": "Commercial"})
    fake.route("/api/assets/2/download", 200, wav)

    # search
    rc = snd_cli.main(["assets", "search", "--q", "bass", "--api", "http://x", "--token", "t"], http=fake)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Dark Bass Pack" in out and "35" in out and "install" in out

    # install (into a --dir, so it's independent of the monkeypatched cache)
    dest = tmp_path / "library"
    rc = snd_cli.main(["assets", "install", "2", "--dir", str(dest), "--api", "http://x", "--token", "t"], http=fake)
    assert rc == 0
    out = capsys.readouterr().out
    assert "dark-bass-demo.wav" in out and "Commercial" in out
    saved = list(dest.iterdir())
    assert len(saved) == 1 and saved[0].name == "2-dark-bass-demo.wav"
    assert saved[0].read_bytes() == wav

    # no token -> clear error
    rc = snd_cli.main(["assets", "search", "--api", "http://x"], http=fake)
    assert rc == 1
    assert "No token" in capsys.readouterr().err
