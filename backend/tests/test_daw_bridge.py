import io
import json
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import config
    from app import database

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "BLOB_DIR", tmp_path / "blobs")
    monkeypatch.setattr(config, "TMP_DIR", tmp_path / "tmp")
    config.ensure_dirs()

    test_db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(config, "DATABASE_URL", test_db_url)
    test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(
        database,
        "SessionLocal",
        sessionmaker(bind=test_engine, autoflush=False, autocommit=False),
    )
    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as c:
        yield c


def make_wav(seconds: float = 1.0, sample_rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    n = int(seconds * sample_rate)
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        frames = b"".join(
            struct.pack("<h", int(8000 * (0.5 + 0.5 * ((i // 400) % 2)))) for i in range(n)
        )
        w.writeframes(frames)
    return buf.getvalue()


def _register(client, username="producer") -> str:
    r = client.post("/api/auth/register", json={"username": username, "password": "secret1"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_session(client, token, name="Neon Warehouse"):
    r = client.post("/api/sessions", json={"name": name}, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()


def _upload(client, token, sid, wav, message="v1"):
    r = client.post(
        f"/api/sessions/{sid}/versions",
        headers=_auth(token),
        data={"message": message},
        files=[("file", ("track.wav", wav, "audio/wav"))],
    )
    assert r.status_code == 201, r.text
    return r.json()


def _open_requests(client, token, sid, share_token, version_id, bodies):
    for i, body in enumerate(bodies):
        r = client.post(
            f"/api/sessions/public/{share_token}/versions/{version_id}/comments",
            json={"time_s": float(i * 10 + 1.5), "body": body, "author_name": "aisha@label.com"},
        )
        assert r.status_code == 201, r.text
    r = client.post(
        f"/api/sessions/public/{share_token}/submit-feedback",
        params={"actor": "aisha@label.com"},
        json={"note": "round 1"},
    )
    assert r.status_code == 200, r.text


# ---------- export endpoint ----------


def test_export_markdown_and_csv(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav())
    _open_requests(client, token, s["id"], s["share_token"], v["id"], ["bass masks the vocal", "hats are great"])

    r = client.get(f"/api/sessions/{s['id']}/requests/export", headers=_auth(token))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    md = r.text
    assert "# Open requests" in md and "Neon Warehouse" in md
    assert "bass masks the vocal" in md
    assert "0:01.500" in md  # clock format MM:SS.mmm

    r = client.get(f"/api/sessions/{s['id']}/requests/export?format=csv", headers=_auth(token))
    assert r.status_code == 200
    assert "version,time_s,clock,author,status,body" in r.text
    assert "bass masks the vocal" in r.text


def test_export_includes_drafts_only_with_flag(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav())
    # a guest draft, never submitted
    client.post(
        f"/api/sessions/public/{s['share_token']}/versions/{v['id']}/comments",
        json={"time_s": 5.0, "body": "unsubmitted note", "author_name": "aisha@label.com"},
    )
    md = client.get(f"/api/sessions/{s['id']}/requests/export", headers=_auth(token)).text
    assert "unsubmitted note" not in md
    md = client.get(
        f"/api/sessions/{s['id']}/requests/export?include_drafts=true", headers=_auth(token)
    ).text
    assert "unsubmitted note" in md


def test_export_requires_owner(client):
    token = _register(client)
    other = _register(client, "other")
    s = _create_session(client, token)
    r = client.get(f"/api/sessions/{s['id']}/requests/export", headers=_auth(other))
    assert r.status_code == 404


def test_public_export_share_token(client):
    """The M4L device pulls open comments via the share token — no login."""
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav())
    _open_requests(client, token, s["id"], s["share_token"], v["id"], ["bass masks the vocal"])

    r = client.get(f"/api/sessions/public/{s['share_token']}/requests/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert "bass masks the vocal" in r.text

    r = client.get(f"/api/sessions/public/{s['share_token']}/requests/export?format=csv")
    assert r.status_code == 200
    assert "version,time_s,clock,author,status,body" in r.text
    assert "bass masks the vocal" in r.text

    # unknown token → 404
    assert client.get("/api/sessions/public/nope/requests/export").status_code == 404


# ---------- CLI ----------


class FakeHttp:
    """Injectable http for the CLI: map url fragment -> (status, bytes)."""

    def __init__(self):
        self.routes: list[tuple[str, str, dict]] = []
        self.requests: list[tuple[str, str, bytes, str]] = []

    def __call__(self, method, url, token="", data=None, content_type=""):
        self.requests.append((method, url, data or b"", content_type))
        # most specific route wins (e.g. /api/sessions/7 beats /api/sessions)
        hits = [(len(frag), status, body) for frag, status, body in self.routes if frag in url]
        if not hits:
            raise AssertionError(f"no fake route for {method} {url}")
        _, status, body = max(hits, key=lambda h: h[0])
        if isinstance(body, bytes):
            return status, body
        if isinstance(body, (dict, list)):
            return status, json.dumps(body).encode()
        return status, body.encode()


def _fake_detail(version_label="v14", comments=()):
    return {
        "id": 1,
        "name": "Neon Warehouse",
        "round_number": 2,
        "versions": [
            {"id": 2, "label": version_label, "comments": list(comments)},
        ],
    }


def test_cli_login_saves_config(tmp_path, monkeypatch):
    import soundhub_cli

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", str(tmp_path / "cfg.json"))
    fake = FakeHttp()
    fake.routes.append(
        (
            "/api/auth/login",
            200,
            {"access_token": "tok123", "user": {"username": "producer"}},
        )
    )
    assert soundhub_cli.main(["login", "--user", "producer", "--password", "x", "--api", "http://x"], http=fake) == 0
    cfg = soundhub_cli.load_config()
    assert cfg["token"] == "tok123"
    assert cfg["api"] == "http://x"


def test_cli_find_session_by_name_and_id():
    import soundhub_cli

    fake = FakeHttp()
    fake.routes.append(("/api/sessions", 200, [{"id": 7, "name": "Neon Warehouse"}]))
    s = soundhub_cli.find_session(fake, "http://x", "t", "neon warehouse")
    assert s["id"] == 7
    fake2 = FakeHttp()
    fake2.routes.append(("/api/sessions/7", 200, {"id": 7, "name": "Neon Warehouse"}))
    s = soundhub_cli.find_session(fake2, "http://x", "t", "7")
    assert s["id"] == 7


def test_cli_requests_exports_markdown(monkeypatch, capsys):
    import soundhub_cli

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", "/nonexistent")
    fake = FakeHttp()
    fake.routes.append(("/api/sessions", 200, [{"id": 7, "name": "Neon Warehouse"}]))
    fake.routes.append(("/requests/export", 200, "# Open requests — Neon Warehouse\n- [0:01.500] aisha — kick\n"))
    rc = soundhub_cli.main(["requests", "--session", "neon", "--api", "http://x", "--token", "t"], http=fake)
    assert rc == 0
    out = capsys.readouterr().out
    assert "kick" in out


def test_cli_push_uploads_multipart(tmp_path, monkeypatch):
    import soundhub_cli

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", "/nonexistent")
    wav = tmp_path / "mix.wav"
    wav.write_bytes(b"RIFF fake-wav")
    fake = FakeHttp()
    fake.routes.append(("/api/sessions", 200, [{"id": 7, "name": "Neon Warehouse"}]))
    fake.routes.append(("/sessions/7/versions", 201, {"label": "v14", "message": "kick revised"}))
    fake.routes.append(("/api/sessions/7", 200, _fake_detail("v14")))
    rc = soundhub_cli.main(
        ["push", str(wav), "--session", "neon", "--message", "v14: kick revised", "--api", "http://x", "--token", "t"],
        http=fake,
    )
    assert rc == 0
    method, url, data, ctype = fake.requests[1]
    assert method == "POST" and "/api/sessions/7/versions" in url
    assert b"mix.wav" in data and b"v14: kick revised" in data
    assert ctype.startswith("multipart/form-data; boundary=")


def test_cli_locator_lists_open_requests(capsys, monkeypatch):
    import soundhub_cli

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", "/nonexistent")
    fake = FakeHttp()
    fake.routes.append(("/api/sessions", 200, [{"id": 7, "name": "Neon Warehouse"}]))
    fake.routes.append(
        ("/api/sessions/7",
         200,
         _fake_detail(
             "v14",
             comments=[
                 {"time_s": 84.5, "body": "bass masks the vocal", "status": "open", "author_name": "aisha@label.com"},
                 {"time_s": 45.0, "body": "hats great", "status": "fixed", "author_name": "aisha@label.com"},
             ],
         )),
    )
    rc = soundhub_cli.main(["locator", "--session", "neon", "--api", "http://x", "--token", "t"], http=fake)
    assert rc == 0
    out = capsys.readouterr().out
    assert 'Locator 1: "bass masks the vocal" @ 1:24.500' in out
    assert "hats great" not in out  # fixed requests are excluded


def test_cli_help_exits_zero():
    import soundhub_cli

    with pytest.raises(SystemExit) as exc:
        soundhub_cli.main(["--help"])
    assert exc.value.code == 0
