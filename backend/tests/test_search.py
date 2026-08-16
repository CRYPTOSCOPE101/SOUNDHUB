import sys
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


def _register(client, username: str) -> str:
    r = client.post("/api/auth/register", json={"username": username, "password": "secret1"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_session(client, token: str, name: str) -> dict:
    r = client.post("/api/sessions", json={"name": name}, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()


def _set_public(client, token: str, sid: int):
    r = client.patch(
        f"/api/sessions/{sid}/share",
        json={"portfolio_public": True},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text


def test_search_finds_public_engineer_and_session(client):
    token = _register(client, "neonproducer")
    # name that the seeded demo review ("Neon Warehouse — sample review") can't
    # collide with, so the count assertions stay deterministic
    _set_public(client, token, _create_session(client, token, "Aurora Night Mix")["id"])

    # engineer match by username
    r = client.get("/api/search", params={"q": "neon"})
    assert r.status_code == 200
    body = r.json()
    assert [e["username"] for e in body["engineers"]] == ["neonproducer"]
    assert body["engineers"][0]["session_count"] == 1

    # session match by name
    r = client.get("/api/search", params={"q": "aurora"})
    body = r.json()
    assert len(body["sessions"]) == 1
    s = body["sessions"][0]
    assert s["name"] == "Aurora Night Mix"
    assert s["owner_username"] == "neonproducer"
    assert s["share_token"]
    assert s["status"] == "in_review"


def test_search_never_leaks_private_sessions(client):
    token = _register(client, "quietengineer")
    _create_session(client, token, "Secret Project")  # not portfolio_public

    r = client.get("/api/search", params={"q": "secret"})
    body = r.json()
    assert body["engineers"] == []
    assert body["sessions"] == []

    # the engineer is not findable either — nothing public exists
    r = client.get("/api/search", params={"q": "quiet"})
    assert r.json()["engineers"] == []


def test_search_empty_and_limits(client):
    r = client.get("/api/search", params={"q": ""})
    assert r.json() == {"query": "", "engineers": [], "sessions": []}

    token = _register(client, "a" * 60)  # long username still fine
    r = client.get("/api/search", params={"q": "x" * 100})
    assert r.status_code == 422  # max_length enforced by FastAPI
