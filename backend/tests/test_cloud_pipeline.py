"""Integration tests for the cloud asset pipeline.

Tests the full flow:
  upload → StorageObject record → background jobs → webhook events
"""
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.database import Base
from app.main import app


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import config
    from app import database
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

    # Patch job_queue to use the same test DB
    jq_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    monkeypatch.setattr(job_queue, "_engine", jq_engine)
    monkeypatch.setattr(job_queue, "_SessionFactory", sessionmaker(bind=jq_engine))

    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as c:
        yield c


def _register_and_login(client) -> str:
    import time as _t
    name = f"pipe_{_t.time_ns()}"
    resp = client.post(
        "/api/auth/register",
        json={"username": name, "password": "testpass123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Tests ──────────────────────────────────────────────────────────────


class TestCloudAssetPipeline:
    """End-to-end: push files → StorageObject created → jobs enqueued."""

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        self.client = client
        self.token = _register_and_login(client)
        self.headers = _auth(self.token)

        resp = client.post(
            "/api/projects",
            json={"name": "Pipeline Test"},
            headers=self.headers,
        )
        self.project_id = resp.json()["id"]

    def test_push_creates_storage_objects(self):
        """Pushing DAW files creates StorageObject records."""
        from app.services.daw.fixtures import make_als

        resp = self.client.post(
            f"/api/projects/{self.project_id}/push",
            headers=self.headers,
            data={"message": "initial commit", "branch": "main"},
            files=[("files", ("Track.als", make_als(), "application/octet-stream"))],
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["ok"] is True

        from sqlalchemy import select
        from app.database import SessionLocal
        from app.models import StorageObject

        db = SessionLocal()
        try:
            project_objs = db.scalars(
                select(StorageObject).where(StorageObject.project_id == self.project_id)
            ).all()
            assert len(project_objs) >= 1, "At least one StorageObject should exist"
            assert project_objs[0].status == "uploaded"
            assert project_objs[0].sha256
            assert project_objs[0].kind == "daw_project"
        finally:
            db.close()

    def test_push_daw_enqueues_parse_job(self):
        """Pushing a DAW file enqueues a parse_daw background job."""
        from app.services.daw.fixtures import make_als

        resp = self.client.post(
            f"/api/projects/{self.project_id}/push",
            headers=self.headers,
            data={"message": "daw push", "branch": "main"},
            files=[("files", ("Track.als", make_als(), "application/octet-stream"))],
        )
        assert resp.status_code == 200, resp.text

        # Wait for background jobs to be enqueued
        time.sleep(2)

        from sqlalchemy import select
        from app.database import SessionLocal
        from app.models import Job

        db = SessionLocal()
        try:
            jobs = db.scalars(select(Job)).all()
            job_types = {j.type for j in jobs}
            assert len(jobs) >= 1, f"Expected at least 1 job, got {len(jobs)}"
            assert "parse_daw" in job_types, f"Expected parse_daw job, got {job_types}"
        finally:
            db.close()

    def test_storage_upload_intent_creates_pending_object(self):
        """Upload intent without sha256 creates a pending_upload StorageObject."""
        resp = self.client.post(
            "/api/storage/uploads",
            json={
                "filename": "test.wav",
                "content_type": "audio/wav",
                "byte_size": 1024,
                "sha256": "",  # Empty — file not yet uploaded
                "kind": "master",
            },
            headers=self.headers,
        )
        assert resp.status_code == 201, resp.text
        obj_id = resp.json()["object_id"]

        from app.database import SessionLocal
        from app.models import StorageObject

        db = SessionLocal()
        try:
            obj = db.get(StorageObject, obj_id)
            assert obj is not None
            assert obj.status == "pending_upload"
            assert obj.kind == "master"
        finally:
            db.close()

    def test_storage_upload_intent_with_sha_dedup(self):
        """Upload intent with sha256 returns existing object if already stored."""
        from app.services.storage import put_blob

        sha = put_blob(b"dedup test data")

        resp = self.client.post(
            "/api/storage/uploads",
            json={
                "filename": "dedup.wav",
                "content_type": "audio/wav",
                "byte_size": len(b"dedup test data"),
                "sha256": sha,
                "kind": "master",
            },
            headers=self.headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["sha256"] == sha
        assert data["object_id"]  # Should return an ID

    def test_storage_usage_endpoint(self):
        """GET /api/storage/usage returns correct counts."""
        resp = self.client.get("/api/storage/usage", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_objects" in data
        assert "total_bytes" in data
        assert "by_kind" in data

    def test_job_lifecycle_api(self):
        """Jobs API: create → get → list → complete flow."""
        import struct
        import io
        import wave

        # Create a real WAV so the handler can process it
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            frames = struct.pack("<h", 1000) * 16000
            w.writeframes(frames)
        wav_data = buf.getvalue()

        from app.services.storage import put_blob
        fake_sha = put_blob(wav_data)

        with patch("app.services.storage.read_blob", return_value=wav_data):
            resp = self.client.post(
                "/api/jobs",
                json={
                    "type": "extract_audio_metadata",
                    "input_json": {"sha256": fake_sha, "filename": "test.wav"},
                },
                headers=self.headers,
            )
            assert resp.status_code == 202, resp.text
            job_id = resp.json()["id"]

            resp = self.client.get(f"/api/jobs/{job_id}", headers=self.headers)
            assert resp.status_code == 200
            assert resp.json()["id"] == job_id

            resp = self.client.get("/api/jobs", headers=self.headers)
            assert resp.status_code == 200
            assert resp.json()["total"] >= 1

            for _ in range(30):
                time.sleep(0.3)
                status_resp = self.client.get(
                    f"/api/jobs/{job_id}", headers=self.headers
                )
                if status_resp.json()["status"] in ("completed", "failed"):
                    break

            final = self.client.get(f"/api/jobs/{job_id}", headers=self.headers).json()
            assert final["status"] in ("completed", "failed")

    def test_webhook_event_types_include_storage(self):
        """The webhook event types list includes storage and job events."""
        resp = self.client.get("/api/integrations/events")
        assert resp.status_code == 200
        events = {e["key"] for e in resp.json()["events"]}
        assert "storage.object.uploaded" in events
        assert "storage.object.ready" in events
        assert "job.completed" in events
        assert "job.failed" in events

    def test_cleanup_removes_stale_pending_uploads(self):
        """POST /api/storage/cleanup removes stale pending uploads."""
        # Create a pending upload (no sha256 → pending_upload status)
        resp = self.client.post(
            "/api/storage/uploads",
            json={
                "filename": "stale.bin",
                "content_type": "application/octet-stream",
                "byte_size": 100,
                "sha256": "",
                "kind": "artifact",
            },
            headers=self.headers,
        )
        assert resp.status_code == 201

        # Cleanup with TTL=0 should remove pending uploads
        resp = self.client.post(
            "/api/storage/cleanup?ttl_minutes=0",
            headers=self.headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["removed"] >= 1
        assert data["ttl_minutes"] == 0
