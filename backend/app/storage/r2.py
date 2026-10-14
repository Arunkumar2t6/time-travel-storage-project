from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import Settings


class BlockStore:
    """Content-addressed block storage backed by Cloudflare R2 (or local disk)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.bucket = settings.r2_bucket_name
        self._local = settings.use_local_storage or not settings.resolved_r2_endpoint
        self._local_root = Path(settings.local_storage_path)

        if self._local:
            self._local_root.mkdir(parents=True, exist_ok=True)
            self._client = None
        else:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.resolved_r2_endpoint,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                region_name="auto",
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "path"},
                ),
            )

    def object_key(self, block_hash: str) -> str:
        # Shard keys to avoid flat-prefix hotspots
        return f"blocks/{block_hash[:2]}/{block_hash[2:4]}/{block_hash}"

    def exists(self, block_hash: str) -> bool:
        key = self.object_key(block_hash)
        if self._local:
            return (self._local_root / key).is_file()
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def put(self, block_hash: str, data: bytes) -> str:
        key = self.object_key(block_hash)
        if self._local:
            path = self._local_root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(data)
            return key

        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType="application/octet-stream",
        )
        return key

    def get(self, block_hash: str) -> bytes:
        key = self.object_key(block_hash)
        if self._local:
            path = self._local_root / key
            if not path.is_file():
                raise FileNotFoundError(f"Block missing: {block_hash}")
            return path.read_bytes()

        response = self._client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def delete(self, block_hash: str) -> None:
        key = self.object_key(block_hash)
        if self._local:
            path = self._local_root / key
            if path.is_file():
                path.unlink()
            return
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def get_stream(self, block_hash: str):
        """Return a file-like body for streaming reconstruction."""
        key = self.object_key(block_hash)
        if self._local:
            path = self._local_root / key
            if not path.is_file():
                raise FileNotFoundError(f"Block missing: {block_hash}")
            return path.open("rb")

        response = self._client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"]
