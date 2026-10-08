"""Private original-document storage using the Cloudflare R2 S3 API."""

from collections.abc import Iterator
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, BinaryIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from dotenv import load_dotenv
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

load_dotenv()

R2_BUCKET = "mynotebook"
MAX_DOCUMENT_BYTES = 300_000_000
READ_SIZE = 1024 * 1024
DOCUMENT_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain; charset=utf-8",
}


class StorageError(RuntimeError):
    """An R2 operation failed without exposing provider credentials."""


class CloudflareR2:
    """Upload originals and open authenticated streams from one private bucket."""

    def __init__(self) -> None:
        self.bucket = R2_BUCKET
        self._account_id = os.getenv("CF_ACC_ID")
        self._api_key = os.getenv("S3_API_KEY")
        self._endpoint = os.getenv("S3_API_URL")
        self._client: Any = None
        if not self._account_id or not self._api_key:
            raise ValueError("S3_API_KEY and CF_ACC_ID are required for R2 storage.")
        if not self._endpoint:
            self._endpoint = f"https://{self._account_id}.r2.cloudflarestorage.com"
        endpoint = urlparse(self._endpoint)
        if (
            endpoint.scheme != "https" or not endpoint.hostname
            or not endpoint.hostname.endswith(".r2.cloudflarestorage.com")
            or endpoint.hostname.split(".")[0] != self._account_id
            or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment
            or endpoint.params
            or endpoint.path not in ("", "/", f"/{self.bucket}", f"/{self.bucket}/")
        ):
            raise ValueError("S3_API_URL must be the HTTPS R2 endpoint for CF_ACC_ID.")
        # Dashboard bucket URLs include the bucket; the S3 SDK appends it itself.
        self._endpoint = endpoint._replace(path="").geturl()

    def _s3_credentials(self) -> tuple[str, str]:
        """Resolve the token ID and derive its S3 secret as documented by R2."""
        paths = (
            f"/accounts/{self._account_id}/tokens/verify", "/user/tokens/verify",
        )
        last_error = None
        for path in paths:
            request = Request(
                "https://api.cloudflare.com/client/v4" + path,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            try:
                with urlopen(request, timeout=15) as response:
                    payload = json.load(response)
            except HTTPError as exc:
                if exc.code in (400, 401, 403, 404):
                    last_error = exc
                    continue
                raise StorageError("Unable to verify the Cloudflare R2 API token.") from exc
            except (URLError, TimeoutError) as exc:
                raise StorageError("Unable to verify the Cloudflare R2 API token.") from exc
            result = payload.get("result") or {}
            if payload.get("success") and result.get("status") == "active" and result.get("id"):
                return result["id"], sha256(self._api_key.encode()).hexdigest()
        raise StorageError("Cloudflare R2 API token verification failed.") from last_error

    @property
    def client(self) -> Any:
        """Reuse a client signing requests to the configured S3 endpoint."""
        if self._client is None:
            access_key_id, secret_access_key = self._s3_credentials()
            self._client = boto3.client(
                "s3", endpoint_url=self._endpoint, region_name="auto",
                aws_access_key_id=access_key_id, aws_secret_access_key=secret_access_key,
                config=Config(
                    signature_version="s3v4", connect_timeout=10, read_timeout=60,
                    retries={"max_attempts": 2, "mode": "standard"},
                    s3={"addressing_style": "path"},
                    request_checksum_calculation="when_required",
                    response_checksum_validation="when_required",
                ),
            )
        return self._client

    def upload_document(self, path: Path, document_id: str) -> dict[str, Any]:
        """Upload the exact file bytes and return persistent SQL metadata."""
        extension = path.suffix.lower()
        if extension not in DOCUMENT_CONTENT_TYPES:
            raise ValueError("Unsupported original document type.")
        size = path.stat().st_size
        if not 0 < size <= MAX_DOCUMENT_BYTES:
            raise ValueError("Document size must be between 1 byte and 300 MB.")
        key = f"documents/{UUID(document_id)}{extension}"
        digest = sha256()
        with path.open("rb") as body:
            for block in iter(lambda: body.read(READ_SIZE), b""):
                digest.update(block)
            body.seek(0)
            try:
                result = self.client.put_object(
                    Bucket=self.bucket, Key=key, Body=body,
                    ContentType=DOCUMENT_CONTENT_TYPES[extension], ContentLength=size,
                )
            except (BotoCoreError, ClientError) as exc:
                raise StorageError("Unable to upload the original document to R2.") from exc
        return {
            "storage_bucket": self.bucket,
            "storage_key": key,
            "content_type": DOCUMENT_CONTENT_TYPES[extension],
            "file_size": size,
            "sha256": digest.hexdigest(),
            "etag": result.get("ETag"),
        }

    def open_document(self, key: str) -> BinaryIO:
        """Open an object only after the caller has checked document ownership."""
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "NotFound", "404"):
                raise FileNotFoundError("Original document not found in R2.") from exc
            raise StorageError("Unable to read the original document from R2.") from exc
        except BotoCoreError as exc:
            raise StorageError("Unable to read the original document from R2.") from exc


def iter_document_bytes(body: BinaryIO) -> Iterator[bytes]:
    """Stream bounded blocks and close the provider connection on completion."""
    try:
        while block := body.read(READ_SIZE):
            yield block
    finally:
        body.close()
