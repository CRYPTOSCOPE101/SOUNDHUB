"""Tests for job result persistence — outputs written to domain models."""
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.database import Base
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import config, database
    from app.services import job_queue

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "BLOB_DIR", tmp_path / "blobs")
    monkeypatch.setattr(config, "TMP_DIR", tmp_path / "tmp")
    config.ensure_dirs()

    test_db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(config, "DATABASE_URL", test_db_url)
    monkeypatch.setattr(database, "DATABASE_URL", test_db_url)

    test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(
        database,
        "SessionLocal",
        sessionmaker(bind=test_engine, autoflush=False, autocommit=False),
    )

    jq_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    monkeypatch.setattr(job_queue, "_engine", jq_engine)
    monkeypatch.setattr(job_queue, "_SessionFactory", sessionmaker(bind=jq_engine))

    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as c:
        yield c


def _register_and_login(client) -> str:
    import time as _t
    name = f"persist_{_t.time_ns()}"
    resp = client.post(
        "/api/auth/register",
        json={"username": name, "password": "testpass123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestJobResultPersistence:
    """Verify job results are persisted into StorageObject.metadata_json."""

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        self.client = client
        self.token = _register_and_login(client)
        self.headers = _auth(self.token)

    def test_parse_daw_persists_metadata(self):
        """parse_daw job result is written to StorageObject.metadata_json['daw_metadata']."""
        from app.services.daw.fixtures import make_als
        from app.services.storage import put_blob
        from sqlalchemy import select
        from app.database import SessionLocal
        from app.models import StorageObject

        als_data = make_als(bpm=128.0)
        sha = put_blob(als_data)

        # Create a StorageObject for the DAW file
        db = SessionLocal()
        try:
            so = StorageObject(
                sha256=sha,
                storage_provider="local",
                storage_key=f"blobs/sha256/{sha[:2]}/{sha[2:4]}/{sha}",
                original_filename="Test.als",
                content_type="application/octet-stream",
                byte_size=len(als_data),
                kind="daw_project",
                status="uploaded",
            )
            db.add(so)
            db.commit()
            db.refresh(so)
            so_id = so.id
        finally:
            db.close()

        with patch("app.services.daw.registry.get_daw_info", return_value={"bpm": 128.0, "tracks": []}):
            resp = self.client.post(
                "/api/jobs",
                json={
                    "type": "parse_daw",
                    "storage_object_id": so_id,
                    "input_json": {"sha256": sha, "filename": "Test.als"},
                },
                headers=self.headers,
            )
            assert resp.status_code == 202
            job_id = resp.json()["id"]

            # Wait for completion
            for _ in range(30):
                time.sleep(0.3)
                s = self.client.get(f"/api/jobs/{job_id}", headers=self.headers).json()["status"]
                if s in ("completed", "failed"):
                    break

            assert s == "completed", f"Job ended in {s}"

        # Verify metadata persisted on StorageObject
        db = SessionLocal()
        try:
            obj = db.get(StorageObject, so_id)
            assert obj.metadata_json is not None
            assert "daw_metadata" in obj.metadata_json
            assert obj.metadata_json["daw_metadata"]["bpm"] == 128.0
            assert obj.processed_at is not None
        finally:
            db.close()

    def test_loudness_persists_result(self):
        """analyze_loudness job result is written to StorageObject.metadata_json['loudness']."""
        import struct
        import io
        import wave

        from app.services.storage import put_blob
        from app.database import SessionLocal
        from app.models import StorageObject

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(struct.pack("<h", 1000) * 16000)
        wav_data = buf.getvalue()
        sha = put_blob(wav_data)

        db = SessionLocal()
        try:
            so = StorageObject(
                sha256=sha,
                storage_provider="local",
                storage_key=f"blobs/sha256/{sha[:2]}/{sha[2:4]}/{sha}",
                original_filename="test.wav",
                content_type="audio/wav",
                byte_size=len(wav_data),
                kind="master",
                status="uploaded",
            )
            db.add(so)
            db.commit()
            db.refresh(so)
            so_id = so.id
        finally:
            db.close()

        with patch("app.services.storage.read_blob", return_value=wav_data):
            resp = self.client.post(
                "/api/jobs",
                json={
                    "type": "analyze_loudness",
                    "input_json": {"sha256": sha, "filename": "test.wav"},
                },
                headers=self.headers,
            )
            assert resp.status_code == 202
            job_id = resp.json()["id"]

            for _ in range(30):
                time.sleep(0.3)
                s = self.client.get(f"/api/jobs/{job_id}", headers=self.headers).json()["status"]
                if s in ("completed", "failed"):
                    break

            assert s == "completed", f"Job ended in {s}"

        db = SessionLocal()
        try:
            obj = db.get(StorageObject, so_id)
            assert obj.metadata_json is not None
            assert "loudness" in obj.metadata_json
            # Loudness result should have sample_rate and channels at minimum
            loudness = obj.metadata_json["loudness"]
            assert "sample_rate" in loudness or "integrated_lufs" in loudness
        finally:
            db.close()

    def test_persistence_is_idempotent(self):
        """Calling persist_job_result twice produces the same result."""
        from app.services.job_result_persistence import persist_job_result
        from app.services.storage import put_blob
        from app.database import SessionLocal
        from app.models import Job, StorageObject
        from datetime import datetime, timezone

        sha = put_blob(b"test data")

        db = SessionLocal()
        try:
            so = StorageObject(
                sha256=sha,
                storage_provider="local",
                storage_key=f"blobs/sha256/{sha[:2]}/{sha[2:4]}/{sha}",
                original_filename="test.wav",
                content_type="audio/wav",
                byte_size=9,
                kind="master",
                status="uploaded",
            )
            db.add(so)
            db.flush()

            job = Job(
                type="analyze_loudness",
                status="completed",
                progress=100,
                input_json={"sha256": sha, "filename": "test.wav"},
                output_json={"integrated_lufs": -14.0, "true_peak_dbtp": -0.5},
                created_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
            db.add(job)
            db.flush()

            result = {"integrated_lufs": -14.0, "true_peak_dbtp": -0.5}

            # First persist
            persist_job_result(job, result, db)
            db.commit()
            db.refresh(so)

            first_meta = dict(so.metadata_json) if so.metadata_json else {}
            assert "loudness" in first_meta
            assert first_meta["loudness"]["integrated_lufs"] == -14.0

            # Second persist (idempotent)
            persist_job_result(job, result, db)
            db.commit()
            db.refresh(so)

            second_meta = dict(so.metadata_json) if so.metadata_json else {}
            assert second_meta == first_meta, "Metadata should be identical after second persist"
        finally:
            db.close()
