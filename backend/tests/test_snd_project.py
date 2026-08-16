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


# ---------- Phase 16: snd push review contract ----------


def _make_als() -> bytes:
    return gzip.compress(b"<Ableton/>")


# ---------- backend: push opens a review version for A/B ----------


def test_push_fast_mode_returns_commit_contract(client):
    """`snd push mix.als` (no audio) creates a commit and returns the contract."""
    token = _register(client)
    pid = client.post("/api/projects", json={"name": "Neon"}, headers=_auth(token)).json()["id"]

    r = client.post(
        f"/api/projects/{pid}/push",
        headers=_auth(token),
        data={"message": "v12", "branch": "main"},
        files=[("files", ("Neon.als", _make_als(), "application/xml"))],
    )
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["ok"] is True
    assert res["commit_id"] and res["branch"] == "main"
    assert res["version_id"] is None and res["session_id"] is None
    assert res["review_url"] is None
    assert res["uploaded"] == {"als": True, "master": False, "stems": 0}
    assert res["deduplicated"] == 0


def test_push_audio_opens_review_version_for_ab(client):
    """`--audio` attaches the master to a review version available for gapless A/B."""
    token = _register(client)
    pid = client.post("/api/projects", json={"name": "Neon"}, headers=_auth(token)).json()["id"]

    manifest = json.dumps({"project": "Neon", "daws": [{"path": "Neon.als", "format": "als", "info": {"bpm": 128.0, "tracks": [{"name": "Synth Lead"}]}}]})
    r = client.post(
        f"/api/projects/{pid}/push",
        headers=_auth(token),
        data={"message": "v12 bounce", "manifest": manifest, "branch": "review/v12", "round": "3"},
        files=[
            ("files", ("Neon.als", _make_als(), "application/xml")),
            ("audio", ("master_v12.wav", make_wav(), "audio/wav")),
        ],
    )
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["ok"] is True
    assert res["version_id"] and res["session_id"] and res["share_token"]
    assert res["review_url"] and res["review_url"].endswith(f"/r/{res['share_token']}")
    assert res["branch"] == "review/v12"
    assert res["manifest_stored"] is True
    assert res["uploaded"] == {"als": True, "master": True, "stems": 0}

    # the review session holds the version with a waveform → gapless A/B source
    session = client.get(f"/api/sessions/{res['session_id']}", headers=_auth(token)).json()
    v = session["versions"][0]
    assert v["label"] == "v1" and v["audio_format"] == "wav"
    assert v["round_number"] == 3
    assert v["waveform"]
    # master audio is downloadable from the session
    r = client.get(f"/api/sessions/{res['session_id']}/versions/{v['id']}/audio", headers=_auth(token))
    assert r.status_code == 200 and r.content == make_wav()
    # and from the public share link
    r = client.get(f"/api/sessions/public/{res['share_token']}/versions/{v['id']}/audio")
    assert r.status_code == 200


def test_push_two_versions_support_gapless_ab(client):
    """Two pushes into the same project land in one session → A/B compare works."""
    token = _register(client)
    pid = client.post("/api/projects", json={"name": "Neon"}, headers=_auth(token)).json()["id"]

    def push_audio():
        return client.post(
            f"/api/projects/{pid}/push",
            headers=_auth(token),
            data={"message": "bounce"},
            files=[
                ("files", ("Neon.als", _make_als(), "application/xml")),
                ("audio", ("master.wav", make_wav(), "audio/wav")),
            ],
        ).json()

    v1 = push_audio()
    v2 = push_audio()  # identical audio → blob dedup, but a NEW version row
    assert v1["session_id"] == v2["session_id"]
    assert v1["version_id"] != v2["version_id"]

    session = client.get(f"/api/sessions/{v1['session_id']}", headers=_auth(token)).json()
    assert {x["label"] for x in session["versions"]} == {"v1", "v2"}

    # gapless A/B between the pushed versions (level-matched preview graph)
    r = client.post(
        "/api/comparisons",
        headers=_auth(token),
        json={
            "base_version_id": v1["version_id"],
            "compare_version_id": v2["version_id"],
            "start_ms": 0,
            "level_match": "none",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["mode"] == "full_mix"


def test_push_stems_attached_as_set(client):
    """`--stems` attaches stems as individual logical-name assets, not a ZIP."""
    token = _register(client)
    pid = client.post("/api/projects", json={"name": "Neon"}, headers=_auth(token)).json()["id"]

    r = client.post(
        f"/api/projects/{pid}/push",
        headers=_auth(token),
        data={"message": "v13 stems"},
        files=[
            ("files", ("Neon.als", _make_als(), "application/xml")),
            ("audio", ("master_v13.wav", make_wav(), "audio/wav")),
            ("stems", ("Kick.wav", make_wav(), "audio/wav")),
            ("stems", ("Bass.wav", make_wav(), "audio/wav")),
            ("stems", ("Vocals.wav", make_wav(), "audio/wav")),
        ],
    )
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["uploaded"] == {"als": True, "master": True, "stems": 3}

    # stems are StemAsset rows with derived logical names
    stems = client.get(f"/api/versions/{res['version_id']}/stems", headers=_auth(token)).json()
    assert len(stems) == 3
    assert {s["logical_name"] for s in stems} == {"drums", "bass", "vocal"}
    assert all(s["audio_format"] == "wav" for s in stems)


def test_push_repeated_identical_file_dedups_blob(client, tmp_path, monkeypatch):
    """Re-pushing identical files stores the blob once (content-addressed)."""
    from app.services import storage

    blob_dir = tmp_path / "blobs"
    blob_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(storage, "BLOB_DIR", blob_dir)

    token = _register(client)
    pid = client.post("/api/projects", json={"name": "Neon"}, headers=_auth(token)).json()["id"]

    def push():
        return client.post(
            f"/api/projects/{pid}/push",
            headers=_auth(token),
            data={"message": "v12"},
            files=[
                ("files", ("Neon.als", _make_als(), "application/xml")),
                ("audio", ("master.wav", make_wav(), "audio/wav")),
            ],
        ).json()

    first = push()
    n_before = len(list(blob_dir.iterdir()))
    second = push()
    assert second["deduplicated"] >= 2  # .als + master already stored
    assert len(list(blob_dir.iterdir())) == n_before  # no new blob written
    assert first["version_id"] != second["version_id"]  # new version, same blobs


def test_push_mid_upload_error_leaves_no_partial_version(client):
    """A stem with an unsupported extension fails atomically — nothing is created."""
    token = _register(client)
    pid = client.post("/api/projects", json={"name": "Neon"}, headers=_auth(token)).json()["id"]

    r = client.post(
        f"/api/projects/{pid}/push",
        headers=_auth(token),
        data={"message": "v12"},
        files=[
            ("files", ("Neon.als", _make_als(), "application/xml")),
            ("audio", ("master.wav", make_wav(), "audio/wav")),
            ("stems", ("Kick.zip", b"PK", "application/zip")),
        ],
    )
    assert r.status_code == 400
    # no session, no version, no commit — nothing user-visible was half-pushed
    assert client.get("/api/sessions", headers=_auth(token)).json() == []
    assert client.get(f"/api/projects/{pid}/commits", headers=_auth(token)).json() == []


def test_push_error_cases_are_clear(client, monkeypatch):
    token = _register(client)
    pid = client.post("/api/projects", json={"name": "Neon"}, headers=_auth(token)).json()["id"]

    # bad token → 401
    r = client.post(
        f"/api/projects/{pid}/push",
        headers={"Authorization": "Bearer nope"},
        files=[("files", ("Neon.als", _make_als(), "application/xml"))],
    )
    assert r.status_code == 401

    # missing project → 404
    r = client.post(
        "/api/projects/999999/push",
        headers=_auth(token),
        files=[("files", ("Neon.als", _make_als(), "application/xml"))],
    )
    assert r.status_code == 404

    # unsupported audio extension → 400 with a clear message
    r = client.post(
        f"/api/projects/{pid}/push",
        headers=_auth(token),
        files=[
            ("files", ("Neon.als", _make_als(), "application/xml")),
            ("audio", ("master.exe", b"MZ", "application/octet-stream")),
        ],
    )
    assert r.status_code == 400
    assert "master" in r.text.lower() and "exe" in r.text.lower()

    # stems without a master → 400
    r = client.post(
        f"/api/projects/{pid}/push",
        headers=_auth(token),
        files=[
            ("files", ("Neon.als", _make_als(), "application/xml")),
            ("stems", ("Kick.wav", make_wav(), "audio/wav")),
        ],
    )
    assert r.status_code == 400

    # oversized upload → 413
    monkeypatch.setattr("app.routers.projects.MAX_UPLOAD_SIZE", 100)
    r = client.post(
        f"/api/projects/{pid}/push",
        headers=_auth(token),
        files=[("files", ("Neon.als", b"x" * 200, "application/xml"))],
    )
    assert r.status_code == 413


# ---------- CLI: single-file push + review flags + preflight + --json ----------


def test_snd_push_single_als_review_json_contract(tmp_path, monkeypatch, capsys):
    """`snd push mix.als --audio … --stems … --round 3 --json` — stable contract."""
    import soundhub_cli

    import snd_cli
    from app.services.daw import fixtures

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", "/nonexistent")
    als = tmp_path / "Track_v12.als"
    als.write_bytes(fixtures.make_als(tracks=[("MidiTrack", "Synth Lead", ["Plugin:Serum"])]))
    master = tmp_path / "master.wav"
    master.write_bytes(make_wav())
    stems = tmp_path / "stems"
    stems.mkdir()
    (stems / "Kick.wav").write_bytes(make_wav())
    (stems / "Bass.wav").write_bytes(make_wav())

    fake = FakeHttp()
    fake.route("/api/projects", 200, [{"id": 5, "name": "artist-track"}])
    fake.route("/api/projects/5/push", 200, {
        "ok": True,
        "project_id": 5,
        "branch": "review/v12",
        "commit_id": 42,
        "version_id": 7,
        "session_id": 3,
        "share_token": "tok123",
        "review_url": "http://localhost:5173/r/tok123",
        "uploaded": {"als": True, "master": True, "stems": 2},
        "deduplicated": 1,
    })

    rc = snd_cli.main(
        [
            "push", str(als),
            "--audio", str(master),
            "--stems", str(stems),
            "--project", "artist-track",
            "--branch", "review/v12",
            "--round", "3",
            "--message", "Round 3 candidate",
            "--json",
            "--api", "http://x",
            "--token", "t",
        ],
        http=fake,
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    for key in ("ok", "project_id", "branch", "version_id", "review_url", "uploaded", "deduplicated"):
        assert key in payload
    assert payload["uploaded"] == {"als": True, "master": True, "stems": 2}

    # the upload request carried: .als, master, 2 stems, round, branch, manifest
    method, url, data, ctype = fake.requests[-1]
    assert method == "POST" and "/api/projects/5/push" in url
    assert b'filename="Track_v12.als"' in data
    assert b'filename="master.wav"' in data
    assert data.count(b'name="stems"') == 2
    assert b'name="round"\r\n\r\n3\r\n' in data
    assert b"review/v12" in data
    assert b'name="manifest"' in data
    body_text = data.decode("utf-8", errors="ignore")
    assert '"plugins": ["Serum"]' in body_text


def test_snd_push_preflight_rejects_bad_inputs(tmp_path, monkeypatch, capsys):
    """Preflight fails fast with clear errors — before any HTTP request."""
    import soundhub_cli

    import snd_cli
    from app.services.daw import fixtures

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", "/nonexistent")
    fake = FakeHttp()

    # nonexistent target
    rc = snd_cli.main(["push", str(tmp_path / "nope.als"), "--api", "http://x", "--token", "t"], http=fake)
    assert rc == 1
    assert "Not found" in capsys.readouterr().err

    # unsupported extension
    txt = tmp_path / "notes.txt"
    txt.write_text("hi")
    rc = snd_cli.main(["push", str(txt), "--api", "http://x", "--token", "t"], http=fake)
    assert rc == 1
    assert "Unsupported project file type" in capsys.readouterr().err

    # corrupt .als → not readable
    bad = tmp_path / "bad.als"
    bad.write_bytes(b"this is not an als file at all")
    rc = snd_cli.main(["push", str(bad), "--api", "http://x", "--token", "t"], http=fake)
    assert rc == 1
    assert "Cannot parse" in capsys.readouterr().err

    # --audio file missing
    als = tmp_path / "ok.als"
    als.write_bytes(fixtures.make_als())
    rc = snd_cli.main(["push", str(als), "--audio", str(tmp_path / "missing.wav"), "--api", "http://x", "--token", "t"], http=fake)
    assert rc == 1
    assert "Master file not found" in capsys.readouterr().err

    # stems without a master
    stemdir = tmp_path / "stems"
    stemdir.mkdir()
    (stemdir / "Kick.wav").write_bytes(make_wav())
    rc = snd_cli.main(["push", str(als), "--stems", str(stemdir), "--api", "http://x", "--token", "t"], http=fake)
    assert rc == 1
    assert "requires --audio" in capsys.readouterr().err

    # stems dir with no audio files
    empty = tmp_path / "empty"
    empty.mkdir()
    m = tmp_path / "m.wav"
    m.write_bytes(make_wav())
    rc = snd_cli.main(["push", str(als), "--audio", str(m), "--stems", str(empty), "--api", "http://x", "--token", "t"], http=fake)
    assert rc == 1
    assert "No audio stems found" in capsys.readouterr().err

    # no HTTP requests were attempted
    assert fake.requests == []


def test_snd_push_preflight_oversized(tmp_path, monkeypatch, capsys):
    import soundhub_cli

    import snd_cli
    from app import config
    from app.services.daw import fixtures

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", "/nonexistent")
    monkeypatch.setattr(config, "MAX_UPLOAD_SIZE", 100)
    big = tmp_path / "big.als"
    big.write_bytes(fixtures.make_als())  # bigger than 100 bytes

    rc = snd_cli.main(["push", str(big), "--api", "http://x", "--token", "t"], http=FakeHttp())
    assert rc == 1
    assert "File too large" in capsys.readouterr().err


def test_snd_push_json_error_contract(tmp_path, monkeypatch, capsys):
    """--json prints {"ok": false, "error": …} on failure — stable for automation."""
    import soundhub_cli

    import snd_cli

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", "/nonexistent")
    rc = snd_cli.main(
        ["push", str(tmp_path / "nope.als"), "--json", "--api", "http://x", "--token", "t"],
        http=FakeHttp(),
    )
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "error" in payload


def test_snd_push_open_uses_review_url(tmp_path, monkeypatch):
    """--open launches the review URL in the browser after a successful push."""
    import soundhub_cli

    import snd_cli
    from app.services.daw import fixtures

    monkeypatch.setattr(soundhub_cli, "CONFIG_PATH", "/nonexistent")
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))

    als = tmp_path / "Track.als"
    als.write_bytes(fixtures.make_als())
    master = tmp_path / "master.wav"
    master.write_bytes(make_wav())

    fake = FakeHttp()
    fake.route("/api/projects", 200, [{"id": 5, "name": "artist-track"}])
    fake.route("/api/projects/5/push", 200, {
        "ok": True, "commit_id": 1, "file_count": 2, "branch": "main",
        "review_url": "http://localhost:5173/r/abc123",
    })

    rc = snd_cli.main(
        ["push", str(als), "--audio", str(master), "--project", "artist-track", "--open", "--api", "http://x", "--token", "t"],
        http=fake,
    )
    assert rc == 0
    assert opened == ["http://localhost:5173/r/abc123"]
