import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.daw.fixtures import make_als, make_rpp  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Isolate data dir + database per test run
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import config, database

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "BLOB_DIR", tmp_path / "blobs")
    monkeypatch.setattr(config, "TMP_DIR", tmp_path / "tmp")
    config.ensure_dirs()

    test_db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(config, "DATABASE_URL", test_db_url)
    test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(
        database, "SessionLocal", sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    )
    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as c:
        yield c


def _register(client) -> str:
    r = client.post("/api/auth/register", json={"username": "producer", "password": "secret1"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_auth_flow(client):
    token = _register(client)
    me = client.get("/api/auth/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["username"] == "producer"

    bad = client.post("/api/auth/login", json={"username": "producer", "password": "wrong"})
    assert bad.status_code == 401


def test_project_and_commit_flow(client):
    token = _register(client)
    h = _auth(token)

    proj = client.post("/api/projects", json={"name": "My Track", "description": "dub techno"}, headers=h)
    assert proj.status_code == 201
    pid = proj.json()["id"]
    assert proj.json()["slug"] == "my-track"

    # upload commit with two files
    r = client.post(
        f"/api/projects/{pid}/commits",
        headers=h,
        data={"message": "first sketch"},
        files=[
            ("files", ("Project.als", make_als(bpm=128.0), "application/octet-stream")),
            ("files", ("Project.rpp", make_rpp(bpm=128.0), "application/octet-stream")),
        ],
    )
    assert r.status_code == 201, r.text
    assert r.json()["file_count"] == 2

    # tree
    tree = client.get(f"/api/projects/{pid}/tree", headers=h)
    assert tree.status_code == 200
    paths = [f["path"] for f in tree.json()["files"]]
    assert "Project.als" in paths and "Project.rpp" in paths
    als_entry = next(f for f in tree.json()["files"] if f["path"] == "Project.als")
    assert als_entry["daw_format"] == "als"
    assert als_entry["daw_info"]["bpm"] == 128.0

    # second commit with changes
    r2 = client.post(
        f"/api/projects/{pid}/commits",
        headers=h,
        data={"message": "bpm up"},
        files=[("files", ("Project.als", make_als(bpm=132.0), "application/octet-stream"))],
    )
    assert r2.status_code == 201
    c2 = r2.json()["id"]

    # diff between commits
    d = client.get(f"/api/projects/{pid}/diff", params={"path": "Project.als", "to_commit": c2}, headers=h)
    assert d.status_code == 200
    kinds = {c["kind"] for c in d.json()["summary"]}
    assert "bpm" in kinds
    assert d.json()["raw"] != ""

    # download
    dl = client.get(f"/api/projects/{pid}/files/Project.als", headers=h)
    assert dl.status_code == 200
    assert dl.content[:2] == b"\x1f\x8b"

    # commits list
    commits = client.get(f"/api/projects/{pid}/commits", headers=h)
    assert commits.status_code == 200
    assert len(commits.json()) == 2


def test_wallet_login_flow(client):
    from eth_account import Account
    from eth_account.messages import encode_defunct

    acct = Account.create()
    r = client.post("/api/auth/wallet/nonce", json={"address": acct.address})
    assert r.status_code == 200
    msg = r.json()["message"]
    assert "Nonce:" in msg

    sig = acct.sign_message(encode_defunct(text=msg)).signature.hex()
    r = client.post(
        "/api/auth/wallet/login",
        json={"address": acct.address, "message": msg, "signature": sig},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["wallet_address"].lower() == acct.address.lower()

    # invalid signature
    bad = client.post(
        "/api/auth/wallet/login",
        json={"address": acct.address, "message": msg, "signature": "0x" + "00" * 65},
    )
    assert bad.status_code == 401

    # nonce is single-use
    again = client.post(
        "/api/auth/wallet/login",
        json={"address": acct.address, "message": msg, "signature": sig},
    )
    assert again.status_code == 401


def test_asset_catalog_and_recommend(client):
    # catalog is public (the M4L device browses without auth)
    r = client.get("/api/assets")
    assert r.status_code == 200
    catalog = r.json()
    assert any(a["listing_id"] == 1 for a in catalog)  # seeded demo listing
    assert all("verified" in a for a in catalog)

    # context-aware recommendations: 128 BPM + techno + Serum
    r = client.get(
        "/api/assets/recommend",
        params={"bpm": 128, "genre": "techno, house", "devices": "Serum, Kick"},
    )
    assert r.status_code == 200
    recs = r.json()
    assert recs, "expected at least one recommendation"
    top = recs[0]
    assert top["match_score"] >= 4.0, top  # genre + bpm + device overlap
    assert "genre match" in top["match_reasons"]
    # ranking is stable: BPM-fit first for a 128 BPM techno context
    assert top["name"] == "Neon Dreams — Serum Preset Pack"

    # wrong context -> different top pick (cinematic impact for a trailer)
    r2 = client.get("/api/assets/recommend", params={"genre": "cinematic, trailer"})
    assert r2.status_code == 200
    assert r2.json()[0]["name"] == "Cinematic Impacts Vol.1"

    # bpm out of range scores low / absent
    r3 = client.get("/api/assets/recommend", params={"bpm": 60})
    assert r3.status_code == 200
    assert all(a["bpm"] is None or a["bpm"][0] > 60 for a in r3.json())

    # hard filters: license + format
    r4 = client.get("/api/assets/recommend", params={"license": "sync"})
    assert r4.status_code == 200
    assert r4.json() and all(a["license"] == "Sync" for a in r4.json())
    r5 = client.get(
        "/api/assets/recommend", params={"genre": "techno", "format": "wav"}
    )
    assert r5.status_code == 200
    assert r5.json() and all(a["format"] == "wav" for a in r5.json())
    # key filter narrows to the right asset
    r6 = client.get(
        "/api/assets/recommend", params={"genre": "techno", "key": "D minor"}
    )
    assert r6.status_code == 200
    names = [a["name"] for a in r6.json()]
    assert "Dark Bass Pack (Techno)" in names


def test_asset_download_token(client):
    from app import config
    from app.services import catalog

    # valid short-lived token (signed with the app secret)
    token = catalog.make_download_token(config.SECRET_KEY, listing_id=1)
    r = client.get("/api/assets/1/download", params={"token": token})
    assert r.status_code == 200
    assert r.headers["X-License"] == "Commercial"
    assert r.content[:4] == b"RIFF"  # wav payload

    # token for another listing is rejected
    r = client.get("/api/assets/2/download", params={"token": token})
    assert r.status_code == 401

    # garbage token is rejected
    r = client.get("/api/assets/1/download", params={"token": "x" * 40})
    assert r.status_code == 401

    # expired token is rejected: sign at real time with a 1s lifetime, then
    # verify after time has moved beyond the expiry
    import time as _t

    expired = catalog.make_download_token(config.SECRET_KEY, listing_id=1, expires_in=1)
    old = _t.time
    _t.time = lambda: old() + 10000  # noqa: B023 — verification now sees t > exp
    try:
        r = client.get("/api/assets/1/download", params={"token": expired})
    finally:
        _t.time = old
    assert r.status_code == 401


def test_ownership_isolation(client):
    token_a = _register(client)
    r = client.post(
        "/api/auth/register", json={"username": "other", "password": "secret2"}
    )
    token_b = r.json()["access_token"]
    pid = client.post(
        "/api/projects", json={"name": "A's project"}, headers=_auth(token_a)
    ).json()["id"]
    got = client.get(f"/api/projects/{pid}", headers=_auth(token_b))
    assert got.status_code == 404
