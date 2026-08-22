"""Tests for background job queue and jobs API."""
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
def _job_db(tmp_path, monkeypatch):
    """Create an isolated test DB and patch job_queue to use it.

    Yields (test_engine, SessionLocal) so tests can also create tables etc.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.services import job_queue

    test_db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine)

    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(job_queue, "_engine", engine)
    monkeypatch.setattr(job_queue, "_SessionFactory", factory)
    yield engine, factory


@pytest.fixture()
def client(tmp_path, monkeypatch, _job_db):
    """Isolated TestClient with patched DB and job_queue engine."""
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
    monkeypatch.setattr(database, "DATABASE_URL", test_db_url)

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


# ── Auth helpers ───────────────────────────────────────────────────────


def _register_and_login(client) -> str:
    """Register a test user and return the auth token."""
    name = f"jobtest_{time.time_ns()}"
    resp = client.post(
        "/api/auth/register",
        json={"username": name, "password": "testpass123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Handler registration tests ──────────────────────────────────────────

from app.services.job_queue import (
    _HANDLERS,
    cancel_job,
    enqueue_job,
    get_job_status,
    list_jobs,
    register_handler,
)


class TestHandlerRegistration:
    def test_builtin_handlers_registered(self):
        expected = {
            "parse_daw",
            "generate_waveform",
            "analyze_loudness",
            "extract_audio_metadata",
            "transcode_audio",
            "watermark_preview",
        }
        assert expected.issubset(set(_HANDLERS))

    def test_custom_handler_registration(self):
        @register_handler("test_custom_job")
        def my_handler(job, db):
            return {"ok": True}

        assert "test_custom_job" in _HANDLERS

        # Cleanup
        del _HANDLERS["test_custom_job"]


# ── Queue unit tests (no HTTP) ──────────────────────────────────────────


class TestJobQueue:
    def test_enqueue_and_status(self, _job_db):
        job_id = enqueue_job(
            "extract_audio_metadata",
            input_json={"sha256": "a" * 64, "filename": "test.wav"},
        )
        assert isinstance(job_id, int)
        assert job_id > 0

        # Wait for in-process worker to pick it up
        time.sleep(0.5)

        info = get_job_status(job_id)
        assert info is not None
        assert info["id"] == job_id
        assert info["type"] == "extract_audio_metadata"
        assert info["status"] in ("queued", "running", "completed", "failed")

    def test_unknown_job_type_raises(self):
        with pytest.raises(ValueError, match="Unknown job type"):
            enqueue_job("nonexistent_job_type")

    def test_list_jobs(self, _job_db):
        jobs = list_jobs(limit=10)
        assert isinstance(jobs, list)

    def test_cancel_queued_job(self, _job_db):
        result = cancel_job(999999)
        assert result is False


# ── API endpoint tests ──────────────────────────────────────────────────


class TestJobsAPI:
    @pytest.fixture(autouse=True)
    def _auth_setup(self, client):
        self.client = client
        self.token = _register_and_login(client)
        self.headers = _auth(self.token)

    def test_create_job(self):
        resp = self.client.post(
            "/api/jobs",
            json={
                "type": "extract_audio_metadata",
                "input_json": {"sha256": "a" * 64, "filename": "test.wav"},
            },
            headers=self.headers,
        )
        assert resp.status_code == 202, resp.text
        data = resp.json()
        assert data["type"] == "extract_audio_metadata"
        assert data["status"] in ("queued", "running", "completed")
        assert "id" in data

    def test_create_job_invalid_type(self):
        resp = self.client.post(
            "/api/jobs",
            json={"type": "invalid_type"},
            headers=self.headers,
        )
        assert resp.status_code == 422

    def test_list_jobs(self):
        resp = self.client.get("/api/jobs", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert "total" in data

    def test_get_job(self):
        create_resp = self.client.post(
            "/api/jobs",
            json={"type": "extract_audio_metadata", "input_json": {}},
            headers=self.headers,
        )
        assert create_resp.status_code == 202, create_resp.text
        job_id = create_resp.json()["id"]

        resp = self.client.get(f"/api/jobs/{job_id}", headers=self.headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == job_id

    def test_get_job_not_found(self):
        resp = self.client.get("/api/jobs/999999", headers=self.headers)
        assert resp.status_code == 404

    def test_cancel_job(self):
        create_resp = self.client.post(
            "/api/jobs",
            json={"type": "extract_audio_metadata", "input_json": {}},
            headers=self.headers,
        )
        job_id = create_resp.json()["id"]

        resp = self.client.delete(f"/api/jobs/{job_id}", headers=self.headers)
        assert resp.status_code in (200, 409)

    def test_retry_job_not_failed(self):
        create_resp = self.client.post(
            "/api/jobs",
            json={"type": "extract_audio_metadata", "input_json": {}},
            headers=self.headers,
        )
        job_id = create_resp.json()["id"]

        resp = self.client.post(f"/api/jobs/{job_id}/retry", headers=self.headers)
        assert resp.status_code in (202, 409)

    def test_list_jobs_with_filters(self):
        resp = self.client.get(
            "/api/jobs",
            params={"job_type": "generate_waveform", "limit": 5},
            headers=self.headers,
        )
        assert resp.status_code == 200

    def test_unauthenticated(self):
        resp = self.client.get("/api/jobs")
        assert resp.status_code in (401, 403)


# ── Integration: enqueue → wait → completed ─────────────────────────────


class TestJobIntegration:
    @pytest.fixture(autouse=True)
    def _auth_setup(self, client):
        self.client = client
        self.token = _register_and_login(client)
        self.headers = _auth(self.token)

    def test_extract_metadata_completes(self):
        """Full round-trip: create job → wait → verify completion."""
        # The handler calls storage.read_blob(), so mock it to return valid WAV
        fake_sha = "a" * 64
        fake_wav = (
            b"RIFF\x00\x00\x00\x00WAVEfmt "
            b"\x10\x00\x00\x00\x01\x00"  # PCM
            b"\x01\x00"  # mono
            b"\x80\x3e\x00\x00"  # 16000 Hz
            b"\x00\x7d\x00\x00"  # byte rate
            b"\x02\x00"  # block align
            b"\x10\x00"  # 16-bit
            + b"data" + b"\x00" * 100
        )

        with patch("app.services.storage.read_blob", return_value=fake_wav):
            resp = self.client.post(
                "/api/jobs",
                json={
                    "type": "extract_audio_metadata",
                    "input_json": {"sha256": fake_sha, "filename": "test.wav"},
                },
                headers=self.headers,
            )
            assert resp.status_code == 202
            job_id = resp.json()["id"]

            # Wait for completion (in-process worker)
            for _ in range(30):
                time.sleep(0.3)
                status_resp = self.client.get(
                    f"/api/jobs/{job_id}", headers=self.headers
                )
                status = status_resp.json()["status"]
                if status in ("completed", "failed"):
                    break

            info = self.client.get(f"/api/jobs/{job_id}", headers=self.headers).json()
            assert info["status"] == "completed"
            assert info["output_json"] is not None
