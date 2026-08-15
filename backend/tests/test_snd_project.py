import gzip
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


def _register(client, username="producer") -> str:
    r = client.post("/api/auth/register", json={"username": username, "password": "secret1"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_wav() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * 0.5)) for _ in range(8000)))
    return buf.getvalue()


# ---------- parser extensions ----------


def test_rpp_parser_extracts_plugin_params():
    from app.services.daw.rpp_parser import parse_rpp

    rpp = (
        b"<REAPER_PROJECT 0.1 \"6.83/x64\" 1\n"
        b"  <TRACK\n"
        b"    <NAME \"Synth Lead\"\n"
        b"    <FXCHAIN\n"
        b"      <VST \"VST3:Serum (Xfer Records)\" serum.vst3 0 \"\" 1 0\n"
        b"        <PARAM name=\"1\" val=\"0.500000\"/>\n"
        b"        <PARAM name=\"2\" val=\"0.250000\"/>\n"
        b"      >\n"
        b"      <VST \"VST3:ReaComp (Cockos)\" reacomp.vst3 0 \"\" 1 0\n"
        b"        <PARAM name=\"thresh\" val=\"-12.0\"/>\n"
        b"      >\n"
        b"    >\n"
        b"  >\n"
        b">\n"
    )
    info = parse_rpp(rpp)
    params = info.extra["plugin_params"]
    assert params["VST: VST3:Serum (Xfer Records)"] == {"1": "0.500000", "2": "0.250000"}
    assert params["VST: VST3:ReaComp (Cockos)"] == {"thresh": "-12.0"}
    assert "VST: VST3:Serum (Xfer Records)" in info.plugin_set


def test_rpp_parser_reads_tempo_without_closing_bracket():
    """Real REAPER writes `<TEMPO 128 4 4` with no `>` — must still parse."""
    from app.services.daw.rpp_parser import parse_rpp

    rpp = (
        b"<REAPER_PROJECT 0.1 \"6.83/x64\" 1\n"
        b"  <TEMPO 128 4 4\n"
        b"  <TRACK\n    <NAME \"A\"\n  >\n"
    )
    info = parse_rpp(rpp)
    assert info.bpm == 128.0
    assert info.time_signature == "4/4"


def test_als_parser_extracts_preset_refs():
    from app.services.daw.als_parser import parse_als

    xml = (
        b"<Ableton MajorVersion=\"12\" MinorVersion=\"0\"><LiveSet>"
        b"<Tracks><MidiTrack><Name><EffectiveName Value=\"Keys\"/></Name>"
        b"<DeviceChain><DeviceChain><Devices>"
        b"<PluginDevice><PluginDesc><VstPluginInfo><PlugName Value=\"Serum\"/>"
        b"</VstPluginInfo></PluginDesc><PresetRef><FileRef><Path>"
        b"<RelativePathElement Dir=\"Presets\" Name=\"Neon Lead.xvl\"/>"
        b"</Path></FileRef></PresetRef></PluginDevice>"
        b"</Devices></DeviceChain></DeviceChain></MidiTrack></Tracks>"
        b"<Tempo><Manual Value=\"128\"/></Tempo></LiveSet></Ableton>"
    )
    info = parse_als(gzip.compress(xml))
    assert info.extra["presets"] == ["Presets/Neon Lead.xvl"]
    assert "Serum" in info.plugin_set


# ---------- push endpoint ----------


def test_push_project_creates_commit_with_manifest(client):
    token = _register(client)
    r = client.post("/api/projects", json={"name": "Neon"}, headers=_auth(token))
    pid = r.json()["id"]

    manifest = json.dumps({"project": "Neon", "daws": [{"path": "Neon.als", "format": "als"}]})
    r = client.post(
        f"/api/projects/{pid}/push",
        headers=_auth(token),
        data={"message": "v12 bounce", "manifest": manifest, "branch": "main"},
        files=[
            ("files", ("Neon.als", gzip.compress(b"<Ableton/>"), "application/xml")),
            ("files", ("Samples/Kick.wav", make_wav(), "audio/wav")),
        ],
    )
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["file_count"] == 3  # 2 files + SOUNDHUB-MANIFEST.json
    assert res["manifest_stored"] is True

    # manifest lives in the tree
    r = client.get(f"/api/projects/{pid}/tree", headers=_auth(token))
    paths = [f["path"] for f in r.json()["files"]]
    assert "Neon.als" in paths and "Samples/Kick.wav" in paths
    assert "SOUNDHUB-MANIFEST.json" in paths


def test_push_rejects_unsafe_path_and_bad_manifest(client):
    token = _register(client)
    r = client.post("/api/projects", json={"name": "Neon"}, headers=_auth(token))
    pid = r.json()["id"]

    r = client.post(
        f"/api/projects/{pid}/push",
        headers=_auth(token),
        data={"message": "x"},
        files=[("files", ("../../etc/passwd", b"root:x", "application/octet-stream"))],
    )
    assert r.status_code == 400

    r = client.post(
        f"/api/projects/{pid}/push",
        headers=_auth(token),
        data={"message": "x", "manifest": "{not json"},
        files=[("files", ("a.als", b"<Ableton/>", "application/xml"))],
    )
    assert r.status_code == 400


# ---------- snd CLI ----------


class FakeHttp:
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


def test_snd_push_parses_locally_and_uploads(tmp_path, monkeypatch):
    import soundhub_cli

    import snd_cli
    from app.services.daw import fixtures

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", "/nonexistent")
    # project dir with an .als + a media file (excluded without --include-media)
    proj = tmp_path / "Neon"
    proj.mkdir()
    (proj / "Neon.als").write_bytes(fixtures.make_als(tracks=[("MidiTrack", "Synth Lead", ["Plugin:Serum"])]))
    (proj / "Kick.wav").write_bytes(make_wav())
    (proj / "README.md").write_text("project notes")

    fake = FakeHttp()
    fake.route("/api/projects", 200, [{"id": 5, "name": "Neon"}])
    fake.route("/api/projects/5/push", 200, {"commit_id": 42, "file_count": 3, "branch": "main"})

    rc = snd_cli.main(
        ["push", str(proj), "--project", "Neon", "--message", "v12 bounce", "--api", "http://x", "--token", "t"],
        http=fake,
    )
    assert rc == 0

    # upload body: message + manifest + files (als + README, NOT the wav)
    method, url, data, ctype = fake.requests[-1]
    assert method == "POST" and "/api/projects/5/push" in url
    assert b"Neon.als" in data
    assert b"README.md" in data
    assert b'filename="Kick.wav"' not in data  # media excluded as an upload
    assert b'name="manifest"' in data  # manifest travels as a form field → stored as SOUNDHUB-MANIFEST.json
    assert b"v12 bounce" in data

    # manifest JSON inside the body describes the parsed structure
    body_text = data.decode("utf-8", errors="ignore")
    assert '"plugins": ["Serum"]' in body_text
    assert '"tracks"' in body_text and '"Synth Lead"' in body_text


def test_snd_push_with_include_media_uploads_wav(tmp_path, monkeypatch):
    import soundhub_cli

    import snd_cli
    from app.services.daw import fixtures

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", "/nonexistent")
    proj = tmp_path / "Neon"
    proj.mkdir()
    (proj / "Neon.als").write_bytes(fixtures.make_als())
    (proj / "Kick.wav").write_bytes(make_wav())

    fake = FakeHttp()
    fake.route("/api/projects", 200, [{"id": 5, "name": "Neon"}])
    fake.route("/api/projects/5/push", 200, {"commit_id": 1, "file_count": 4, "branch": "main"})

    rc = snd_cli.main(
        ["push", str(proj), "--project", "Neon", "--include-media", "--api", "http://x", "--token", "t"],
        http=fake,
    )
    assert rc == 0
    _, _, data, _ = fake.requests[-1]
    assert b"Kick.wav" in data
