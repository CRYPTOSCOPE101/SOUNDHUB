"""Native sidecar (`m4l/sidecar.js`) — the in-Live push bridge for Max 8.5+.

The sidecar runs inside Ableton Live via `node.script` (Max ships a Node.js
runtime), reading the .als from disk and posting a real multipart body to the
backend — no external `snd serve` process, no `shell` (blocked in Live), no
binary-mangling `httprequest`. The same code works as a CLI (`node sidecar.js
push …`), which is how these tests drive it against a live uvicorn server.

Run:  cd backend && .venv/bin/python -m pytest tests/test_snd_sidecar.py -q
"""

import json
import shutil
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from app.services.daw import fixtures  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent
SIDECAR = BACKEND_DIR.parent / "m4l" / "sidecar.js"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node.js not installed — sidecar tests need `node`",
)


@pytest.fixture()
def live_api(tmp_path, monkeypatch):
    """Boot the real FastAPI app on an OS-assigned port with a throwaway DB.

    Function-scoped (fresh DB per test) so blob-dedup counts are predictable:
    a shared module-scoped server would reuse blobs across tests. Returns
    (base_url, token) after registering a user. The server runs in a
    background thread and is shut down at teardown.
    """
    import uvicorn

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import config
    from app import database
    from app.services import storage as storage_svc

    blob_dir = tmp_path / "blobs"
    tmp_dir = tmp_path / "tmp"
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "BLOB_DIR", blob_dir)
    monkeypatch.setattr(config, "TMP_DIR", tmp_dir)
    config.ensure_dirs()
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path / 'sidecar.db'}")

    # storage.py binds BLOB_DIR/TMP_DIR at import time (from ..config import …),
    # so patching the config module alone would leave every test writing into
    # the shared backend/data/blobs dir — patch the service too.
    monkeypatch.setattr(storage_svc, "BLOB_DIR", blob_dir)
    monkeypatch.setattr(storage_svc, "TMP_DIR", tmp_dir)

    test_engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(
        database,
        "SessionLocal",
        sessionmaker(bind=test_engine, autoflush=False, autocommit=False),
    )

    from app.database import Base
    from app.main import app

    Base.metadata.create_all(bind=test_engine)

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        import time

        time.sleep(0.05)
    assert server.started, "uvicorn did not start"
    port = server.servers[0].sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}"

    # register a user over real HTTP
    import urllib.error
    import urllib.request

    body = json.dumps({"username": "producer", "password": "secret1"}).encode()
    req = urllib.request.Request(
        f"{base}/api/auth/register",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            token = json.loads(r.read())["access_token"]
    except urllib.error.HTTPError as exc:
        raise AssertionError(f"register failed: {exc.read().decode()}") from exc

    yield base, token
    server.should_exit = True
    thread.join(timeout=10)


def _run_sidecar(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["node", str(SIDECAR)] + args,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(BACKEND_DIR),
    )
    return proc.returncode, proc.stdout, proc.stderr


def _write_als(tmp_path: Path, name: str = "Track_v12.als") -> Path:
    p = tmp_path / name
    p.write_bytes(fixtures.make_als(tracks=[("MidiTrack", "Synth Lead", ["Plugin:Serum"])]))
    return p


def test_sidecar_push_creates_commit_and_review_url(live_api, tmp_path):
    """Golden path: node sidecar.js push .als + master → full contract."""
    base, token = live_api
    als = _write_als(tmp_path)
    master = tmp_path / "master.wav"
    master.write_bytes(
        _wav_bytes()
    )

    rc, out, err = _run_sidecar(
        [
            "push",
            "--target", str(als),
            "--audio", str(master),
            "--project", "Neon Warehouse",
            "--branch", "review/v12",
            "--message", "Round 3 candidate",
            "--round", "3",
            "--api", base,
            "--token", token,
            "--json",
        ]
    )
    assert rc == 0, f"rc={rc}\nstdout={out}\nstderr={err}"
    res = json.loads(out)
    assert res["ok"] is True
    assert res["project_id"] and res["commit_id"]
    assert res["branch"] == "review/v12"
    assert res["version_id"] and res["session_id"] and res["share_token"]
    assert res["review_url"] and res["review_url"].endswith(f"/r/{res['share_token']}")
    assert res["uploaded"] == {"als": True, "master": True, "stems": 0}
    assert res["deduplicated"] == 0

    # the pushed version is a real review version with a waveform (A/B source)
    import urllib.request

    req = urllib.request.Request(
        f"{base}/api/sessions/{res['session_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        session = json.loads(r.read())
    v = session["versions"][0]
    assert v["label"] == "v1" and v["round_number"] == 3
    assert v["waveform"]


def test_sidecar_idempotent_repush_dedups(live_api, tmp_path):
    """Re-pushing the same export creates a new commit but the blobs dedup."""
    base, token = live_api
    als = _write_als(tmp_path, "Idem.als")

    args = [
        "push",
        "--target", str(als),
        "--project", "Idem Project",
        "--api", base,
        "--token", token,
        "--json",
    ]
    rc1, out1, _ = _run_sidecar(args)
    rc2, out2, _ = _run_sidecar(args)
    assert rc1 == 0 and rc2 == 0
    r1, r2 = json.loads(out1), json.loads(out2)
    assert r1["ok"] and r2["ok"]
    # a new commit row is created (new version history), but the content-
    # addressed blobs are reused — nothing new lands on disk
    assert r2["commit_id"] != r1["commit_id"]
    assert r2["deduplicated"] >= 1


def test_sidecar_preflight_rejects_missing_and_corrupt(live_api, tmp_path):
    """Preflight runs client-side: missing file and corrupt .als → rc 1 + error, no server hit."""
    base, token = live_api

    rc, out, _ = _run_sidecar(
        ["push", "--target", str(tmp_path / "nope.als"), "--api", base, "--token", token, "--json"]
    )
    assert rc == 1
    assert json.loads(out)["ok"] is False
    assert "Not found" in json.loads(out)["error"]

    bad = tmp_path / "broken.als"
    bad.write_bytes(b"<Ableton MajorVersion=\"12\"")  # truncated — not gzip, no <LiveSet close
    rc, out, _ = _run_sidecar(
        ["push", "--target", str(bad), "--api", base, "--token", token, "--json"]
    )
    assert rc == 1
    err = json.loads(out)["error"]
    assert "Cannot read" in err and "corrupt" in err


def test_sidecar_review_requires_master(live_api, tmp_path):
    """Stems without a master are rejected in preflight (review mode gate)."""
    base, token = live_api
    als = _write_als(tmp_path)
    stems = tmp_path / "stems"
    stems.mkdir()
    (stems / "Kick.wav").write_bytes(_wav_bytes())

    rc, out, _ = _run_sidecar(
        [
            "push",
            "--target", str(als),
            "--stems", str(stems),
            "--api", base,
            "--token", token,
            "--json",
        ]
    )
    assert rc == 1
    assert "requires --audio" in json.loads(out)["error"]


def test_sidecar_directory_mode_pushes_daw_files(live_api, tmp_path):
    """Directory target: all DAW files inside are pushed as one commit."""
    base, token = live_api
    proj = tmp_path / "Neon"
    proj.mkdir()
    (proj / "Neon.als").write_bytes(fixtures.make_als())
    (proj / "Master.rpp").write_bytes(
        b"<REAPER_PROJECT 0.1 \"6.83/x64\" 1\n  <TEMPO 128 4 4\n  <TRACK\n    <NAME \"A\"\n  >\n"
    )

    rc, out, _ = _run_sidecar(
        [
            "push",
            "--target", str(proj),
            "--project", "Neon",
            "--api", base,
            "--token", token,
            "--json",
        ]
    )
    assert rc == 0, out
    res = json.loads(out)
    assert res["ok"] is True
    assert res["file_count"] >= 2  # both DAW files land in the commit tree


def _wav_bytes() -> bytes:
    import io
    import struct
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * 0.5)) for _ in range(8000)))
    return buf.getvalue()
