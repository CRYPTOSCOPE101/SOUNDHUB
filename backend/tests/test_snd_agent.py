"""Tests for the snd CLI agent — bridge server, parser, and push pipeline."""
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest


def _start_bridge_bg(*args, **kwargs):
    """Start bridge in a background thread, wait until it's listening."""
    from snd_cli import start_bridge

    srv = start_bridge(*args, **kwargs)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)  # let the server accept connections
    return srv


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

class TestParser:
    def _parse(self, argv: list[str]):
        from snd_cli import build_parser
        return build_parser().parse_args(argv)

    def test_login_subcommand(self):
        args = self._parse(["login", "--user", "alice", "--password", "secret"])
        assert args.command == "login"
        assert args.user == "alice"
        assert args.password == "secret"

    def test_push_subcommand_defaults(self):
        args = self._parse(["push", "track.als"])
        assert args.command == "push"
        assert args.target == "track.als"
        assert args.branch == "main"
        assert args.include_media is False
        assert args.audio is None

    def test_serve_subcommand_defaults(self):
        args = self._parse(["serve"])
        assert args.command == "serve"
        assert args.host == "127.0.0.1"
        assert args.port == 8765

    def test_push_help_exits_cleanly(self):
        from snd_cli import build_parser
        with pytest.raises(SystemExit) as exc:
            build_parser().parse_args(["push", "--help"])
        assert exc.value.code == 0


# ---------------------------------------------------------------------------
# Bridge health endpoint
# ---------------------------------------------------------------------------

class TestBridgeHealth:
    def test_health_returns_200(self):
        import urllib.request

        srv = _start_bridge_bg(
            api="http://localhost:9999", token="t", host="127.0.0.1", port=0
        )
        port = srv.server_address[1]
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=5
            ) as resp:
                body = json.loads(resp.read())
                assert resp.status == 200
                assert body["ok"] is True
                assert body["service"] == "snd-bridge"
        finally:
            srv.shutdown()
            srv.server_close()

    def test_unknown_path_returns_404(self):
        import urllib.request

        srv = _start_bridge_bg(
            api="http://localhost:9999", token="t", host="127.0.0.1", port=0
        )
        port = srv.server_address[1]
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/nonexistent", timeout=5
            ) as resp:
                pass  # Would raise if non-2xx
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
            body = json.loads(exc.read())
            assert body["error"] == "not found"
        finally:
            srv.shutdown()
            srv.server_close()


# ---------------------------------------------------------------------------
# Bridge comments endpoint
# ---------------------------------------------------------------------------

class TestBridgeComments:
    def test_missing_token_returns_400(self):
        import urllib.request

        srv = _start_bridge_bg(
            api="http://localhost:9999", token="t", host="127.0.0.1", port=0
        )
        port = srv.server_address[1]
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/comments?format=markdown"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                pass
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            body = json.loads(exc.read())
            assert "missing share token" in body["error"]
        finally:
            srv.shutdown()
            srv.server_close()

    def test_bad_format_returns_400(self):
        import urllib.request

        srv = _start_bridge_bg(
            api="http://localhost:9999", token="t", host="127.0.0.1", port=0
        )
        port = srv.server_address[1]
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/comments?token=abc&format=yaml"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                pass
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            body = json.loads(exc.read())
            assert "format must be markdown or csv" in body["error"]
        finally:
            srv.shutdown()
            srv.server_close()

    def test_comments_proxies_to_backend(self):
        def fake_http(method, url, token=None):
            return 200, b"v12: Kick and bass clash at the drop"

        srv = _start_bridge_bg(
            api="http://backend:8000",
            token="t",
            host="127.0.0.1",
            port=0,
            http=fake_http,
        )
        port = srv.server_address[1]
        try:
            import urllib.request

            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/comments?token=demo-review-token&format=markdown"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = resp.read().decode()
                assert resp.status == 200
                assert "Kick and bass" in body
        finally:
            srv.shutdown()
            srv.server_close()


# ---------------------------------------------------------------------------
# find_project_files
# ---------------------------------------------------------------------------

class TestFindProjectFiles:
    def test_finds_daw_files(self):
        from snd_cli import find_project_files

        with tempfile.TemporaryDirectory() as d:
            Path(d, "track.als").write_bytes(b"\x00" * 100)
            Path(d, "track.rpp").write_bytes(b"REAPER")
            Path(d, "track.wav").write_bytes(b"\xff" * 100)
            files = find_project_files(d, include_media=False)
            exts = {os.path.splitext(f)[1] for f in files}
            assert ".als" in exts
            assert ".rpp" in exts
            assert ".wav" not in exts  # media excluded

    def test_include_media(self):
        from snd_cli import find_project_files

        with tempfile.TemporaryDirectory() as d:
            Path(d, "track.als").write_bytes(b"\x00")
            Path(d, "master.wav").write_bytes(b"\xff" * 100)
            files = find_project_files(d, include_media=True)
            exts = {os.path.splitext(f)[1] for f in files}
            assert ".wav" in exts
