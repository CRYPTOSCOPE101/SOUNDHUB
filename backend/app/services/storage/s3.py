"""S3-compatible object storage backend.

Works with AWS S3, MinIO, Cloudflare R2, Backblaze B2,
and any S3-compatible service.
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


class S3ObjectStorage:
    """S3 / MinIO / R2 storage backend."""

    def __init__(
        self,
        bucket: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        self.bucket = bucket or os.environ.get("SOUNDHUB_S3_BUCKET", "soundhub-assets")
        self.region = region or os.environ.get("SOUNDHUB_S3_REGION", "us-east-1")
        self.endpoint_url = endpoint_url or os.environ.get("SOUNDHUB_S3_ENDPOINT_URL") or None
        self.access_key = access_key or os.environ.get("SOUNDHUB_S3_ACCESS_KEY", "")
        self.secret_key = secret_key or os.environ.get("SOUNDHUB_S3_SECRET_KEY", "")
        self._client: S3Client | None = None

    def _get_client(self) -> "S3Client":
        if self._client is None:
            import boto3

            kwargs: dict = {
                "service_name": "s3",
                "region_name": self.region,
                "aws_access_key_id": self.access_key or None,
                "aws_secret_access_key": self.secret_key or None,
            }
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            self._client = boto3.client(**kwargs)
        return self._client

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _content_key(data: bytes) -> str:
        """Build a content-addressed S3 key from raw bytes."""
        sha = hashlib.sha256(data).hexdigest()
        return f"blobs/{sha[:2]}/{sha[2:4]}/{sha}"

    @staticmethod
    def _key_from_sha(sha: str) -> str:
        """Convert a SHA-256 hash to an S3 key."""
        return f"blobs/{sha[:2]}/{sha[2:4]}/{sha}"

    # ── protocol ─────────────────────────────────────────────────────────

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        sha = hashlib.sha256(data).hexdigest()
        s3_key = self._key_from_sha(sha)

        client = self._get_client()
        put_kwargs: dict = {
            "Bucket": self.bucket,
            "Key": s3_key,
            "Body": data,
        }
        if content_type:
            put_kwargs["ContentType"] = content_type

        # Don't fail if already exists (idempotent)
        if not self.exists(sha):
            client.put_object(**put_kwargs)

        return sha

    def get_bytes(self, key: str) -> bytes:
        client = self._get_client()
        s3_key = self._key_from_sha(key)
        resp = client.get_object(Bucket=self.bucket, Key=s3_key)
        return resp["Body"].read()  # type: ignore[no-any-return]

    def delete(self, key: str) -> None:
        client = self._get_client()
        s3_key = self._key_from_sha(key)
        try:
            client.delete_object(Bucket=self.bucket, Key=s3_key)
        except Exception:
            pass  # idempotent

    def exists(self, key: str) -> bool:
        client = self._get_client()
        s3_key = self._key_from_sha(key)
        try:
            client.head_object(Bucket=self.bucket, Key=s3_key)
            return True
        except client.exceptions.ClientError:  # type: ignore[attr-defined]
            return False

    def size(self, key: str) -> int:
        client = self._get_client()
        s3_key = self._key_from_sha(key)
        try:
            resp = client.head_object(Bucket=self.bucket, Key=s3_key)
            return resp["ContentLength"]  # type: ignore[no-any-return]
        except Exception:
            return 0

    def create_upload_url(self, key: str, content_type: str, expires_in: int = 900) -> str:
        """Generate a presigned PUT URL so the client can upload directly to S3."""
        client = self._get_client()
        s3_key = self._key_from_sha(key) if len(key) == 64 and all(
            c in "0123456789abcdef" for c in key
        ) else key

        return client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": s3_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )

    def create_download_url(self, key: str, expires_in: int = 900) -> str:
        """Generate a presigned GET URL for the client to download a file."""
        client = self._get_client()
        s3_key = self._key_from_sha(key)

        return client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": s3_key,
            },
            ExpiresIn=expires_in,
        )
