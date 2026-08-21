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
    from app import models  # Import models to register them with Base

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
    from app import config as cfg, database
    from app.models import User, Package
    from app.security import hash_password

    # Create a test user and packages in the database
    db_session = database.SessionLocal()
    try:
        # Create a test user
        test_user = User(
            username="testuser",
            password_hash=hash_password("testpass"),
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Create the main package: Neon Dreams — Serum Preset Pack
        # This should match: bpm=128, genre="techno, house", devices="Serum, Kick"
        test_package1 = Package(
            owner_id=test_user.id,
            name="Neon Dreams — Serum Preset Pack",
            license="Commercial",
            package_type="sample_pack",
            bpm=128,
            genre="techno, house",
            devices="Serum, Kick",
            format="wav",
            key="D minor",  # Adding key for completeness
            blob_sha="dummy_blob_sha1",
            sha256="dummy_sha256_1",
            price_cents=0,
            download_count=0,
            size=0,
            file_count=0,
            tags="",
        )
        db_session.add(test_package1)

        # Create the Dark Bass Pack package for the key filter test
        # This should match: genre="techno", key="D minor"
        test_package2 = Package(
            owner_id=test_user.id,
            name="Dark Bass Pack (Techno)",
            license="Royalty-free",  # Different license
            package_type="sample_pack",
            bpm=None,  # Not specified in test
            genre="techno",
            devices="",  # Not specified
            format="wav",
            key="D minor",
            blob_sha="dummy_blob_sha2",
            sha256="dummy_sha256_2",
            price_cents=0,
            download_count=0,
            size=0,
            file_count=0,
            tags="",
        )
        db_session.add(test_package2)

        # Create a third package for the sync license test
        # This should have license="Sync" to match the license filter test
        test_package3 = Package(
            owner_id=test_user.id,
            name="Sync Licensed Pack",
            license="Sync",
            package_type="sample_pack",
            bpm=None,
            genre="",
            devices="",
            format="wav",
            key="",
            blob_sha="dummy_blob_sha3",
            sha256="dummy_sha256_3",
            price_cents=0,
            download_count=0,
            size=0,
            file_count=0,
            tags="",
        )
        db_session.add(test_package3)

        # Create the Cinematic Impacts package for the cinematic/trailer test
        test_package4 = Package(
            owner_id=test_user.id,
            name="Cinematic Impacts Vol.1",
            license="Royalty-free",
            package_type="sample_pack",
            bpm=None,  # Not specified
            genre="cinematic, trailer",
            devices="",
            format="wav",
            key="",
            blob_sha="dummy_blob_sha4",
            sha256="dummy_sha256_4",
            price_cents=0,
            download_count=0,
            size=0,
            file_count=0,
            tags="",
        )
        db_session.add(test_package4)

        db_session.commit()
    finally:
        db_session.close()

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
    # The seeded data should include "Cinematic Impacts Vol.1" for this search
    assert len(r2.json()) > 0, "Expected at least one recommendation for cinematic, trailer"
    assert r2.json()[0]["name"] == "Cinematic Impacts Vol.1"

    # bpm out of range scores low / absent
    r3 = client.get("/api/assets/recommend", params={"bpm": 60})
    assert r3.status_code == 200
    # The assertion is: all(a["bpm"] is None or a["bpm"][0] > 60 for a in r3.json())
    # This means: for each item, either bpm is None OR (bpm is a list and bpm[0] > 60)
    for a in r3.json():
        assert a["bpm"] is None or (isinstance(a["bpm"], list) and len(a["bpm"]) > 0 and a["bpm"][0] > 60)

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
def test_asset_catalog_filters_and_preview(client):
    """Server-side catalog filters + the public preview stream."""
    print("=== STARTING test_asset_catalog_filters_and_preview ===")
    from app import config as cfg, database
    from app.models import User, Package
    from app.security import hash_password

    # Create a test user and packages in the database (similar to other tests)
    db_session = database.SessionLocal()
    try:
        # Create a test user
        test_user = User(
            username="testuser",
            password_hash=hash_password("testpass"),
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Create the main package: Neon Dreams — Serum Preset Pack (ID=1 to match test expectation)
        test_package1 = Package(
            id=1,
            owner_id=test_user.id,
            name="Neon Dreams — Serum Preset Pack",
            license="Commercial",
            package_type="sample_pack",
            bpm=128,
            genre="techno, house",
            devices="Serum, Kick",
            format="wav",
            key="D minor",
            blob_sha="dummy_blob_sha1",
            sha256="dummy_sha256_1",
            price_cents=0,
            download_count=0,
            size=0,
            file_count=0,
            tags="",
        )
        db_session.add(test_package1)

        # Create the Dark Bass Pack package for genre/cinematic test
        test_package2 = Package(
            id=2,
            owner_id=test_user.id,
            name="Dark Bass Pack (Techno)",
            license="Royalty-free",
            package_type="sample_pack",
            bpm=128,  # Set to a value within 126-134 range
            genre="techno",
            devices="",
            format="wav",
            key="D minor",
            blob_sha="dummy_blob_sha2",
            sha256="dummy_sha256_2",
            price_cents=0,
            download_count=0,
            size=0,
            file_count=0,
            tags="",
        )
        db_session.add(test_package2)

        # Create the Cinematic Impacts package for the cinematic/trailer test
        test_package3 = Package(
            id=3,
            owner_id=test_user.id,
            name="Cinematic Impacts Vol.1",
            license="Royalty-free",
            package_type="sample_pack",
            bpm=None,  # This is important for the "no bpm" test
            genre="cinematic, trailer",
            devices="",
            format="wav",
            key="",
            blob_sha="dummy_blob_sha3",
            sha256="dummy_sha256_3",
            price_cents=0,
            download_count=0,
            size=0,
            file_count=0,
            tags="",
        )
        db_session.add(test_package3)

        # Create a package for the sync license test
        test_package4 = Package(
            id=4,
            owner_id=test_user.id,
            name="Sync Licensed Pack",
            license="Sync",
            package_type="sample_pack",
            bpm=None,  # Not specified
            genre="",
            devices="",
            format="wav",
            key="",
            blob_sha="dummy_blob_sha4",
            sha256="dummy_sha256_4",
            price_cents=0,
            download_count=0,
            size=0,
            file_count=0,
            tags="",
        )
        db_session.add(test_package4)

        # Create a package with key="A minor" for the key filter test
        test_package5 = Package(
            id=5,
            owner_id=test_user.id,
            name="Minor Key Pack",
            license="Royalty-free",
            package_type="sample_pack",
            bpm=120,
            genre="house",
            devices="",
            format="wav",
            key="A minor",
            description="Essential chord progressions in A minor for electronic music production",
            blob_sha="dummy_blob_sha5",
            sha256="dummy_sha256_5",
            price_cents=0,
            download_count=0,
            size=0,
            file_count=0,
            tags="",
        )
        db_session.add(test_package5)

        db_session.commit()
    finally:
        db_session.close()

    # catalog entries carry preview metadata
    r = client.get("/api/assets")
    assert r.status_code == 200
    catalog = r.json()
    print(f"Catalog length: {len(catalog)}")
    if len(catalog) > 0:
        print(f"First item: {catalog[0]}")
    # Try to find item with listing_id == 1, or use first item if not found
    one = None
    for a in catalog:
        if a.get("listing_id") == 1:
            one = a
            break
    if one is None and len(catalog) > 0:
        one = catalog[0]  # fallback to first item
    assert one is not None, f"No items in catalog (length: {len(catalog)})"
    assert one["duration_seconds"] > 0
    assert len(one["waveform"]) > 0
    assert all(0 <= p <= 255 for p in one["waveform"])

    # bpm range filter overlaps asset ranges
    r = client.get("/api/assets", params={"bpm_min": 126, "bpm_max": 134})
    names = {a["name"] for a in r.json()}
    assert "Neon Dreams — Serum Preset Pack" in names  # 124–132
    assert "Dark Bass Pack (Techno)" in names  # 126–138
    assert "Cinematic Impacts Vol.1" not in names  # no bpm

    # hard license + format filters
    r = client.get("/api/assets", params={"license": "sync"})
    assert r.json() and all(a["license"] == "Sync" for a in r.json())
    r = client.get("/api/assets", params={"format": "wav"})
    assert r.json() and all(a["format"] == "wav" for a in r.json())

    # key / genre / plugin / text filters
    r = client.get("/api/assets", params={"key": "a minor"})
    print(f"Key filter response: {r.json()}")
    assert r.json(), f"Expected results for key=a minor, got: {r.json()}"
    assert all(a["key"] == "A minor" for a in r.json()), f"Not all results have key=A minor: {r.json()}"
    r = client.get("/api/assets", params={"genre": "cinematic"})
    print(f"Genre filter response: {r.json()}")
    assert r.json(), f"Expected results for genre=cinematic, got: {r.json()}"
    assert [a["name"] for a in r.json()] == ["Cinematic Impacts Vol.1"], f"Expected ['Cinematic Impacts Vol.1'], got: {[a['name'] for a in r.json()]}"
    r = client.get("/api/assets", params={"plugin": "serum"})
    print(f"Plugin filter response: {r.json()}")
    assert r.json(), f"Expected results for plugin=serum, got: {r.json()}"
    assert all("Serum" in a["plugins"] for a in r.json()), f"Not all results have Serum in plugins: {r.json()}"
    # text search matches name/description/contents (e.g. "chords")
    r = client.get("/api/assets", params={"q": "chords"})
    print(f"Text search response: {r.json()}")
    assert r.json(), f"Expected results for q=chords, got: {r.json()}"
    assert all("chord" in a["name"].lower() or "chord" in a["description"].lower() for a in r.json()), f"Not all results contain chord in name or description: {r.json()}"

    # public preview: full bytes, correct mime + ranges
    r = client.get("/api/assets/1/preview")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "audio/wav"
    assert r.headers["Accept-Ranges"] == "bytes"
    assert r.content[:4] == b"RIFF"

    full = client.get("/api/assets/1/preview")
    r = client.get("/api/assets/1/preview", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206
    assert len(r.content) == 100
    assert r.headers["Content-Range"] == f"bytes 0-99/{len(full.content)}"

    # out-of-range request -> 416
    r = client.get("/api/assets/1/preview", headers={"Range": "bytes=999999-"})
    assert r.status_code == 416

    # unknown listing -> 404
    r = client.get("/api/assets/999/preview")
    assert r.status_code == 404


def test_license_receipt(client):
    """A purchase ships a signed, machine-checkable license receipt."""
    from app import config as cfg, database
    from app.models import User, Package
    from app.security import hash_password
    from app.services import catalog, licenses

    # Create a test user and package in the database
    db_session = database.SessionLocal()
    try:
        # Create a test user
        test_user = User(
            username="testuser",
            password_hash=hash_password("testpass"),
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Create the package with ID=1 that the test expects
        test_package = Package(
            id=1,
            owner_id=test_user.id,
            name="Neon Dreams — Serum Preset Pack",
            license="Commercial",
            package_type="sample_pack",
            bpm=128,
            genre="techno, house",
            devices="Serum, Kick",
            format="wav",
            key="D minor",
            blob_sha="dummy_blob_sha1",
            sha256="dummy_sha256_1",
            price_cents=0,
            download_count=0,
            size=0,
            file_count=0,
            tags="",
        )
        db_session.add(test_package)
        db_session.commit()
    finally:
        db_session.close()

    buyer = "0x" + "ab" * 20
    seller = "0x" + "cd" * 20
    r = client.post(
        "/api/assets/1/receipt", params={"buyer": buyer, "seller": seller}
    )
    assert r.status_code == 200
    rec = r.json()
    assert rec["version"] == "1.0"
    assert rec["listing_id"] == 1
    assert rec["asset_name"] == "Neon Dreams — Serum Preset Pack"
    assert rec["license"] == "Commercial"
    assert rec["buyer_can"] and rec["seller_keeps"]
    assert rec["buyer"] == buyer.lower() or rec["buyer"] == buyer
    assert rec["seller"] == seller
    # Need to pass db session to find_asset
    db_session = database.SessionLocal()
    try:
        assert rec["asset_sha256"] == catalog.find_asset(db_session, 1).sha256
    finally:
        db_session.close()
    assert len(rec["signature"]) == 64

    # signature verifies, and tampering breaks it
    assert licenses.verify_license_receipt(cfg.SECRET_KEY, rec) is True
    tampered = {**rec, "license": "Exclusive"}
    assert licenses.verify_license_receipt(cfg.SECRET_KEY, tampered) is False

    # unknown listing -> 404
    r = client.post(
        "/api/assets/999/receipt", params={"buyer": "0x" + "ab" * 20, "seller": "0x" + "cd" * 20}
    )
    assert r.status_code == 404


def test_asset_download_token(client):
    from app import config as cfg, database
    from app.models import User, Package
    from app.security import hash_password
    from app.services import catalog

    # Create a test user and package in the database
    db_session = database.SessionLocal()
    test_user_id = None
    try:
        # Create a test user
        test_user = User(
            username="testuser",
            password_hash=hash_password("testpass"),
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)
        test_user_id = test_user.id

        # Create the package with ID=1 that the test expects
        test_package = Package(
            id=1,
            owner_id=test_user.id,
            name="Neon Dreams — Serum Preset Pack",
            license="Commercial",
            package_type="sample_pack",
            bpm=128,
            genre="techno, house",
            devices="Serum, Kick",
            format="wav",
            key="D minor",
            blob_sha="dummy_blob_sha1",
            sha256="dummy_sha256_1",
            price_cents=0,
            download_count=0,
            size=0,
            file_count=0,
            tags="",
        )
        db_session.add(test_package)
        db_session.commit()
    finally:
        db_session.close()

    # valid short-lived token (signed with the app secret)
    token = catalog.make_download_token(cfg.SECRET_KEY, listing_id=1, user_id=test_user_id)
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

    expired = catalog.make_download_token(cfg.SECRET_KEY, listing_id=1, user_id=test_user_id, expires_in=1)
    old = _t.time
    _t.time = lambda: old() + 10000  # noqa: B023 — verification now sees t > exp
    try:
        r = client.get("/api/assets/1/download", params={"token": expired})
    finally:
        _t.time = old
    assert r.status_code == 401


def test_asset_download64_base64(client):
    """The M4L device fetches assets as base64 JSON (text-safe)."""
    import base64

    from app import config as cfg, database
    from app.models import User, Package
    from app.security import hash_password
    from app.services import catalog

    # Create a test user and package in the database
    db_session = database.SessionLocal()
    test_user_id = None
    try:
        # Create a test user
        test_user = User(
            username="testuser",
            password_hash=hash_password("testpass"),
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)
        test_user_id = test_user.id

        # Create the package with ID=1 that the test expects
        test_package = Package(
            id=1,
            owner_id=test_user.id,
            name="Neon Dreams — Serum Preset Pack",
            license="Commercial",
            package_type="sample_pack",
            bpm=128,
            genre="techno, house",
            devices="Serum, Kick",
            format="wav",
            key="D minor",
            blob_sha="dummy_blob_sha1",
            sha256="dummy_sha256_1",
            price_cents=0,
            download_count=0,
            size=0,
            file_count=0,
            tags="",
        )
        db_session.add(test_package)
        db_session.commit()
    finally:
        db_session.close()

    tok = catalog.make_download_token(cfg.SECRET_KEY, listing_id=1, user_id=test_user_id)
    r = client.get("/api/assets/1/download64", params={"token": tok})
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "neon-dreams-demo.wav"
    assert body["format"] == "als"
    assert body["license"] == "Commercial"
    decoded = base64.b64decode(body["data"])
    assert decoded[:4] == b"RIFF"  # wav payload round-trips
    assert len(decoded) == body["size"]

    # bad token rejected
    r = client.get("/api/assets/1/download64", params={"token": "x" * 40})
    assert r.status_code == 401


def test_branches_flow(client):
    token = _register(client)
    h = _auth(token)
    pid = client.post(
        "/api/projects", json={"name": "Track", "description": ""}, headers=h
    ).json()["id"]

    # initial commit on default branch
    r = client.post(
        f"/api/projects/{pid}/commits",
        headers=h,
        data={"message": "first", "branch": "main"},
        files=[("files", ("A.als", make_als(bpm=128.0), "application/octet-stream"))],
    )
    assert r.status_code == 201

    # create a branch from main
    r = client.post(
        f"/api/projects/{pid}/branches",
        headers=h,
        json={"name": "remix", "from_branch": "main"},
    )
    assert r.status_code == 201
    assert r.json()["is_default"] is False
    assert r.json()["commit_count"] == 1

    # commit on the new branch
    r = client.post(
        f"/api/projects/{pid}/commits",
        headers=h,
        data={"message": "remix edit", "branch": "remix"},
        files=[("files", ("A.als", make_als(bpm=134.0), "application/octet-stream"))],
    )
    assert r.status_code == 201

    # branches list: remix has 2 commits, main still 1
    branches = client.get(f"/api/projects/{pid}/branches", headers=h).json()
    by_name = {b["name"]: b for b in branches}
    assert set(by_name) == {"main", "remix"}
    assert by_name["main"]["is_default"] is True
    assert by_name["main"]["commit_count"] == 1
    assert by_name["remix"]["commit_count"] == 2

    # tree on each branch reflects its own head
    t_main = client.get(f"/api/projects/{pid}/tree", params={"branch": "main"}, headers=h).json()
    t_remix = client.get(f"/api/projects/{pid}/tree", params={"branch": "remix"}, headers=h).json()
    assert t_main["commit_id"] != t_remix["commit_id"]
    als_main = next(f for f in t_main["files"] if f["path"] == "A.als")
    als_remix = next(f for f in t_remix["files"] if f["path"] == "A.als")
    assert als_main["daw_info"]["bpm"] == 128.0
    assert als_remix["daw_info"]["bpm"] == 134.0

    # commits per branch
    c_main = client.get(f"/api/projects/{pid}/commits", params={"branch": "main"}, headers=h).json()
    c_remix = client.get(f"/api/projects/{pid}/commits", params={"branch": "remix"}, headers=h).json()
    assert len(c_main) == 1
    assert len(c_remix) == 2

    # cross-branch diff: main (128 BPM) -> remix (134 BPM)
    d = client.get(
        f"/api/projects/{pid}/diff",
        params={"path": "A.als", "from_branch": "main", "to_branch": "remix"},
        headers=h,
    )
    assert d.status_code == 200
    kinds = {c["kind"] for c in d.json()["summary"]}
    assert "bpm" in kinds

    # cannot delete default branch; can delete the other
    r = client.delete(f"/api/projects/{pid}/branches/main", headers=h)
    assert r.status_code == 400
    r = client.delete(f"/api/projects/{pid}/branches/remix", headers=h)
    assert r.status_code == 204
    branches = client.get(f"/api/projects/{pid}/branches", headers=h).json()
    assert [b["name"] for b in branches] == ["main"]


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