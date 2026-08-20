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


# ---------- submit-feedback lifecycle ----------


def test_submit_feedback_idempotent(client):
    """Double submit on the same round must fail with 409, not create a second round."""
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav())
    _open_requests(client, token, s["id"], s["share_token"], v["id"], ["first note"])

    # Second submit on already-closed round → 409
    r = client.post(
        f"/api/sessions/public/{s['share_token']}/submit-feedback",
        params={"actor": "aisha@label.com"},
        json={"note": "duplicate"},
    )
    assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"
    assert "No open review round" in r.json()["detail"]


def test_submit_feedback_invalid_token(client):
    """submit-feedback with a non-existent share_token must return 404, not create a round."""
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav())

    r = client.post(
        "/api/sessions/public/nonexistent-token/submit-feedback",
        params={"actor": "aisha@label.com"},
        json={"note": "nope"},
    )
    assert r.status_code == 404


def test_submit_feedback_no_round_returns_409(client):
    """submit-feedback on a session with rounds_open=False (no upload yet) → 409."""
    token = _register(client)
    s = _create_session(client, token)
    # No upload → no round → rounds_open defaults to False

    r = client.post(
        f"/api/sessions/public/{s['share_token']}/submit-feedback",
        params={"actor": "aisha@label.com"},
        json={"note": "nothing to submit"},
    )
    assert r.status_code == 409


# ---------- export isolation ----------


def test_public_export_scoped_to_session(client):
    """Export via share_token only returns comments from THAT session, not others."""
    token = _register(client)

    # Session A — with a comment
    s_a = _create_session(client, token, name="Session A")
    v_a = _upload(client, token, s_a["id"], make_wav())
    _open_requests(client, token, s_a["id"], s_a["share_token"], v_a["id"], ["comment in A"])

    # Session B — with a different comment
    s_b = _create_session(client, token, name="Session B")
    v_b = _upload(client, token, s_b["id"], make_wav())
    _open_requests(client, token, s_b["id"], s_b["share_token"], v_b["id"], ["comment in B"])

    # Export A → should only contain "comment in A"
    r = client.get(f"/api/sessions/public/{s_a['share_token']}/requests/export")
    assert r.status_code == 200
    assert "comment in A" in r.text
    assert "comment in B" not in r.text

    # Export B → should only contain "comment in B"
    r = client.get(f"/api/sessions/public/{s_b['share_token']}/requests/export")
    assert r.status_code == 200
    assert "comment in B" in r.text
    assert "comment in A" not in r.text


# ---------- export escaping ----------


def test_export_csv_special_characters(client):
    """CSV export must correctly handle commas, quotes, newlines, and special chars in comment bodies."""
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav())

    # Post comments with tricky characters
    tricky_bodies = [
        'comma, separated, values',
        'quote "inside" quotes',
        'line\none\nthree',
        'pipe | ampersand & angle <brackets>',
        'unicode — «tags» — €¥£',
    ]
    for i, body in enumerate(tricky_bodies):
        r = client.post(
            f"/api/sessions/public/{s['share_token']}/versions/{v['id']}/comments",
            json={"time_s": float(i + 1), "body": body, "author_name": "tester"},
        )
        assert r.status_code == 201, r.text

    # Submit the round so comments are not drafts
    r = client.post(
        f"/api/sessions/public/{s['share_token']}/submit-feedback",
        params={"actor": "tester"},
        json={"note": "test"},
    )
    assert r.status_code == 200, r.text

    # Export as CSV
    r = client.get(f"/api/sessions/{s['id']}/requests/export?format=csv", headers=_auth(token))
    assert r.status_code == 200
    csv_text = r.text

    # Verify it parses as valid CSV — csv module must round-trip every body
    import csv as csv_mod
    import io
    reader = csv_mod.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) == 5
    assert rows[0]["body"] == 'comma, separated, values'
    assert rows[1]["body"] == 'quote "inside" quotes'
    assert rows[2]["body"] == 'line\none\nthree'
    assert rows[3]["body"] == 'pipe | ampersand & angle <brackets>'
    assert rows[4]["body"] == 'unicode \u2014 \u00abtags\u00bb \u2014 \u20ac\u00a5\u00a3'

    # Non-quoted fields appear verbatim in raw CSV
    assert 'pipe | ampersand' in csv_text


def test_export_markdown_special_characters(client):
    """Markdown export must include special characters verbatim (no HTML injection)."""
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav())

    body = '<script>alert(1)</script> & "quotes" | pipes'
    r = client.post(
        f"/api/sessions/public/{s['share_token']}/versions/{v['id']}/comments",
        json={"time_s": 2.0, "body": body, "author_name": "tester"},
    )
    assert r.status_code == 201

    # Submit
    client.post(
        f"/api/sessions/public/{s['share_token']}/submit-feedback",
        params={"actor": "tester"},
        json={"note": ""},
    )

    r = client.get(f"/api/sessions/{s['id']}/requests/export", headers=_auth(token))
    assert r.status_code == 200
    md = r.text
    assert body in md, f"Body '{body}' missing from Markdown export"


# ---------- full lifecycle E2E ----------


def test_full_round_lifecycle(client):
    """Full lifecycle:
    1. Owner creates session
    2. Owner uploads Version 1 → ReviewRound #1 created (open)
    3. Guest leaves comments on Version 1
    4. Guest submits feedback → round #1 submitted, round_number → 2
    5. Repeat submission → 409
    6. Owner uploads Version 2 → ReviewRound #2 created (open)
    7. Export comments for round #1 only
    """
    from sqlalchemy import select as sa_select
    from app.models import ReviewRound, ReviewSession, ReviewVersion

    token = _register(client, "owner")
    guest_name = "aisha@label.com"

    # ── 1. Owner creates session ──
    s = _create_session(client, token, name="Full Lifecycle Test")
    sid = s["id"]
    st = s["share_token"]

    detail = client.get(f"/api/sessions/{sid}", headers=_auth(token)).json()
    assert detail["round_number"] == 1, "Fresh session should start at round 1"

    # No ReviewRound exists yet
    db = client.app.dependency_overrides  # just for reading; we'll query below
    # (direct DB access not possible via TestClient, so verify via API responses)

    # ── 2. Owner uploads Version 1 → ReviewRound #1 created (open) ──
    v1 = _upload(client, token, sid, make_wav(2.0), message="initial mix")
    assert v1["label"] == "v1"

    detail = client.get(f"/api/sessions/{sid}", headers=_auth(token)).json()
    rounds = detail["rounds"]
    assert len(rounds) == 1, f"Expected 1 round after upload, got {len(rounds)}"
    assert rounds[0]["number"] == 1
    assert rounds[0]["status"] == "open"
    assert detail["rounds_open"] is True
    assert detail["round_number"] == 1

    # ── 3. Guest leaves comments on Version 1 ──
    c1 = client.post(
        f"/api/sessions/public/{st}/versions/{v1['id']}/comments",
        json={"time_s": 10.0, "body": "bass is too loud", "author_name": guest_name},
    )
    assert c1.status_code == 201, c1.text
    c1_data = c1.json()
    assert c1_data["body"] == "bass is too loud"

    c2 = client.post(
        f"/api/sessions/public/{st}/versions/{v1['id']}/comments",
        json={"time_s": 45.0, "body": "hats sit nicely", "author_name": guest_name},
    )
    assert c2.status_code == 201, c2.text

    # ── 4. Guest submits feedback → round #1 submitted, round_number → 2 ──
    submit = client.post(
        f"/api/sessions/public/{st}/submit-feedback",
        params={"actor": guest_name},
        json={"note": "round 1 feedback"},
    )
    assert submit.status_code == 200, submit.text
    submit_data = submit.json()
    assert submit_data["ok"] is True
    assert submit_data["round_number"] == 2

    detail = client.get(f"/api/sessions/{sid}", headers=_auth(token)).json()
    assert detail["rounds_open"] is False, "Round should be closed after submit"
    assert detail["round_number"] == 2, "round_number should advance to 2"
    assert len(detail["rounds"]) == 1
    assert detail["rounds"][0]["status"] == "submitted"
    assert detail["rounds"][0]["note"] == "round 1 feedback"

    # ── 5. Repeat submission → 409 ──
    dup = client.post(
        f"/api/sessions/public/{st}/submit-feedback",
        params={"actor": guest_name},
        json={"note": "duplicate"},
    )
    assert dup.status_code == 409, f"Expected 409 for duplicate submit, got {dup.status_code}"
    assert "No open review round" in dup.json()["detail"]

    # ── 6. Owner uploads Version 2 → ReviewRound #2 created (open) ──
    v2 = _upload(client, token, sid, make_wav(3.0), message="revised mix")
    assert v2["label"] == "v2"

    detail = client.get(f"/api/sessions/{sid}", headers=_auth(token)).json()
    rounds = detail["rounds"]
    assert len(rounds) == 2, f"Expected 2 rounds after v2 upload, got {len(rounds)}"
    # Rounds are ordered desc by number in the API
    round_numbers = sorted([r["number"] for r in rounds])
    assert round_numbers == [1, 2]
    # The new round (#2) should be open
    open_rounds = [r for r in rounds if r["status"] == "open"]
    assert len(open_rounds) == 1, "Exactly one round should be open"
    assert open_rounds[0]["number"] == 2
    assert detail["rounds_open"] is True
    assert detail["round_number"] == 2

    # ── 7. Export comments for round #1 only ──
    # Default export (exclude drafts) — round #1 comments are submitted, round #2 has none
    md = client.get(f"/api/sessions/{sid}/requests/export", headers=_auth(token)).text
    assert "bass is too loud" in md, "Round 1 comment should appear in export"
    assert "hats sit nicely" in md, "Round 1 comment should appear in export"
    assert "# Open requests" in md
    assert "Full Lifecycle Test" in md

    # CSV export
    csv_text = client.get(f"/api/sessions/{sid}/requests/export?format=csv", headers=_auth(token)).text
    assert "bass is too loud" in csv_text
    assert "hats sit nicely" in csv_text

    # Verify clock format
    assert "0:10.000" in md  # 10.0s → 0:10.000
    assert "0:45.000" in md  # 45.0s → 0:45.000


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
