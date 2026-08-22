"""Tests for the pluggable object storage layer."""
import hashlib
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── LocalObjectStorage tests ────────────────────────────────────────────


class TestLocalObjectStorage:
    """Test the local filesystem storage backend."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        """Patch BLOB_DIR to a temp directory for isolation."""
        self.blob_dir = tmp_path / "blobs"
        self.blob_dir.mkdir()

        with patch("app.services.storage.local.BLOB_DIR", self.blob_dir):
            from app.services.storage.local import LocalObjectStorage

            self.storage = LocalObjectStorage()

    def test_put_and_get(self):
        data = b"hello soundhub"
        sha = self.storage.put_bytes("test", data)
        assert len(sha) == 64  # SHA-256 hex
        assert self.storage.get_bytes(sha) == data

    def test_content_addressing_dedup(self):
        data = b"duplicate content"
        sha1 = self.storage.put_bytes("a", data)
        sha2 = self.storage.put_bytes("b", data)
        assert sha1 == sha2  # same content → same address

    def test_exists(self):
        data = b"exists?"
        sha = self.storage.put_bytes("test", data)
        assert self.storage.exists(sha) is True
        assert self.storage.exists("0" * 64) is False

    def test_size(self):
        data = b"x" * 1024
        sha = self.storage.put_bytes("test", data)
        assert self.storage.size(sha) == 1024

    def test_delete(self):
        data = b"delete me"
        sha = self.storage.put_bytes("test", data)
        assert self.storage.exists(sha)
        self.storage.delete(sha)
        assert not self.storage.exists(sha)

    def test_delete_nonexistent_is_idempotent(self):
        self.storage.delete("a" * 64)  # should not raise

    def test_get_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            self.storage.get_bytes("a" * 64)

    def test_upload_url_format(self):
        url = self.storage.create_upload_url("key123", "audio/wav", expires_in=600)
        assert url.startswith("local://upload/")

    def test_download_url_format(self):
        url = self.storage.create_download_url("a" * 64, expires_in=300)
        assert url.startswith("local://download/")


# ── Legacy API backward-compatibility tests ─────────────────────────────


class TestLegacyStorageAPI:
    """Ensure the old put_blob / read_blob functions still work."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        blob_dir = tmp_path / "blobs"
        blob_dir.mkdir()
        with patch("app.services.storage.local.BLOB_DIR", blob_dir):
            yield

    def test_put_blob_returns_sha(self):
        from app.services.storage import put_blob

        sha = put_blob(b"test data")
        assert len(sha) == 64

    def test_read_blob_round_trip(self):
        from app.services.storage import put_blob, read_blob

        data = b"round trip"
        sha = put_blob(data)
        assert read_blob(sha) == data

    def test_blob_exists(self):
        from app.services.storage import blob_exists, put_blob

        sha = put_blob(b"check")
        assert blob_exists(sha) is True

    def test_blob_size(self):
        from app.services.storage import blob_size, put_blob

        sha = put_blob(b"size check")
        assert blob_size(sha) == len(b"size check")


# ── S3ObjectStorage tests (mocked) ─────────────────────────────────────


class TestS3ObjectStorage:
    """Test S3 storage with mocked boto3 client."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        with patch.dict(os.environ, {
            "SOUNDHUB_S3_BUCKET": "test-bucket",
            "SOUNDHUB_S3_REGION": "us-east-1",
            "SOUNDHUB_S3_ACCESS_KEY": "test-key",
            "SOUNDHUB_S3_SECRET_KEY": "test-secret",
        }):
            from app.services.storage.s3 import S3ObjectStorage

            # Create a real exception class that the mocked client can raise
            class FakeClientError(Exception):
                pass

            self.FakeClientError = FakeClientError

            self.storage = S3ObjectStorage()
            self.mock_client = MagicMock()
            self.mock_client.exceptions.ClientError = FakeClientError
            self.storage._client = self.mock_client

    def test_put_bytes(self):
        data = b"s3 data"
        sha = hashlib.sha256(data).hexdigest()
        expected_key = f"blobs/{sha[:2]}/{sha[2:4]}/{sha}"

        # Simulate object not found → raises ClientError
        self.mock_client.head_object.side_effect = self.FakeClientError("Not Found")

        result = self.storage.put_bytes("test", data)
        assert result == sha
        self.mock_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key=expected_key,
            Body=data,
        )

    def test_put_bytes_dedup(self):
        data = b"dedup"
        sha = hashlib.sha256(data).hexdigest()

        # Already exists → no put_object call
        self.mock_client.head_object.return_value = {"ContentLength": len(data)}

        result = self.storage.put_bytes("test", data)
        assert result == sha
        self.mock_client.put_object.assert_not_called()

    def test_get_bytes(self):
        sha = hashlib.sha256(b"readme").hexdigest()
        key = f"blobs/{sha[:2]}/{sha[2:4]}/{sha}"

        mock_body = MagicMock()
        mock_body.read.return_value = b"readme"
        self.mock_client.get_object.return_value = {"Body": mock_body}

        result = self.storage.get_bytes(sha)
        assert result == b"readme"
        self.mock_client.get_object.assert_called_once_with(Bucket="test-bucket", Key=key)

    def test_exists_true(self):
        sha = "a" * 64
        self.mock_client.head_object.return_value = {"ContentLength": 10}
        assert self.storage.exists(sha) is True

    def test_exists_false(self):
        sha = "b" * 64
        self.mock_client.head_object.side_effect = self.FakeClientError("Not Found")
        assert self.storage.exists(sha) is False

    def test_size(self):
        sha = "c" * 64
        self.mock_client.head_object.return_value = {"ContentLength": 2048}
        assert self.storage.size(sha) == 2048

    def test_create_upload_url(self):
        self.mock_client.generate_presigned_url.return_value = "https://s3.example.com/upload"
        url = self.storage.create_upload_url("a" * 64, "audio/wav")
        assert url == "https://s3.example.com/upload"
        self.mock_client.generate_presigned_url.assert_called_once()

    def test_create_download_url(self):
        self.mock_client.generate_presigned_url.return_value = "https://s3.example.com/download"
        url = self.storage.create_download_url("a" * 64)
        assert url == "https://s3.example.com/download"


# ── Provider selection tests ────────────────────────────────────────────


class TestProviderSelection:
    """Test that the correct provider is selected based on env var."""

    def test_default_is_local(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SOUNDHUB_STORAGE_PROVIDER", None)
            from app.services.storage import get_storage
            from app.services.storage.local import LocalObjectStorage

            # Reset singleton
            import app.services.storage as storage_mod
            storage_mod._provider = None

            s = get_storage()
            assert isinstance(s, LocalObjectStorage)

    def test_s3_provider(self):
        with patch.dict(os.environ, {"SOUNDHUB_STORAGE_PROVIDER": "s3"}):
            from app.services.storage import get_storage
            from app.services.storage.s3 import S3ObjectStorage

            import app.services.storage as storage_mod
            storage_mod._provider = None

            with patch("app.services.storage.s3.S3ObjectStorage._get_client"):
                s = get_storage()
                assert isinstance(s, S3ObjectStorage)


# ── StorageObject model tests ───────────────────────────────────────────


class TestStorageObjectModel:
    """Test the StorageObject ORM model."""

    def test_model_imports(self):
        from app.models import StorageAuditEvent, StorageObject

        assert StorageObject.__tablename__ == "storage_objects"
        assert StorageAuditEvent.__tablename__ == "storage_audit_events"

    def test_model_creation(self):
        from app.models import StorageObject

        obj = StorageObject(
            sha256="a" * 64,
            storage_key="blobs/aa/bb/aaaa...",
            original_filename="test.wav",
            content_type="audio/wav",
            byte_size=1024,
            kind="stem",
            status="ready",
        )
        assert obj.sha256 == "a" * 64
        assert obj.kind == "stem"
        assert obj.status == "ready"
