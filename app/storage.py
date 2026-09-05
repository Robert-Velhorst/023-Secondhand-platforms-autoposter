import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fastapi import HTTPException, UploadFile

from app.config import Settings, get_settings

IMAGE_SIGNATURES = {
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/gif": (b"GIF87a", ".gif"),
    "image/webp": (b"RIFF", ".webp"),
}


@dataclass(frozen=True)
class StoredFile:
    original_filename: str
    storage_path: str
    content_type: str
    file_size: int
    checksum_sha256: str


@dataclass(frozen=True)
class ValidatedUpload:
    original_filename: str
    content: bytes
    content_type: str
    file_size: int
    checksum_sha256: str
    extension: str


class StorageBackend(Protocol):
    def save_listing_image(self, listing_id: int, filename: str, upload: ValidatedUpload) -> str:
        raise NotImplementedError

    def delete(self, storage_path: str) -> None:
        raise NotImplementedError

    def read_local_file(self, storage_path: str) -> Path | None:
        raise NotImplementedError

    def read_bytes(self, storage_path: str) -> bytes | None:
        raise NotImplementedError


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def save_listing_image(self, listing_id: int, filename: str, upload: ValidatedUpload) -> str:
        listing_dir = self.root / str(listing_id)
        listing_dir.mkdir(parents=True, exist_ok=True)
        target = listing_dir / filename
        target.write_bytes(upload.content)
        return str(target)

    def delete(self, storage_path: str) -> None:
        remove_local_file(storage_path)

    def read_local_file(self, storage_path: str) -> Path | None:
        target = Path(storage_path).resolve()
        upload_root = self.root.resolve()
        try:
            target.relative_to(upload_root)
        except ValueError:
            return None
        if not target.exists():
            return None
        return target

    def read_bytes(self, storage_path: str) -> bytes | None:
        target = self.read_local_file(storage_path)
        return target.read_bytes() if target else None


class S3Storage:
    def __init__(self, settings: Settings):
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - dependency is present in supported installs
            raise RuntimeError("boto3 is required when STORAGE_BACKEND=s3") from exc
        self.bucket = settings.s3_bucket
        self.prefix = settings.s3_key_prefix.strip("/")
        self.client = boto3.client(
            "s3",
            region_name=settings.s3_region or None,
            endpoint_url=settings.s3_endpoint_url or None,
        )

    def save_listing_image(self, listing_id: int, filename: str, upload: ValidatedUpload) -> str:
        key = self._key(listing_id, filename)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=upload.content,
            ContentType=upload.content_type,
            Metadata={
                "original-filename": upload.original_filename,
                "checksum-sha256": upload.checksum_sha256,
            },
        )
        return f"s3://{self.bucket}/{key}"

    def delete(self, storage_path: str) -> None:
        parsed = parse_s3_uri(storage_path)
        if not parsed:
            return
        bucket, key = parsed
        if bucket != self.bucket:
            return
        self.client.delete_object(Bucket=bucket, Key=key)

    def read_local_file(self, storage_path: str) -> Path | None:
        return None

    def read_bytes(self, storage_path: str) -> bytes | None:
        parsed = parse_s3_uri(storage_path)
        if not parsed:
            return None
        bucket, key = parsed
        if bucket != self.bucket:
            return None
        response = self.client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    def _key(self, listing_id: int, filename: str) -> str:
        key = f"{listing_id}/{filename}"
        if self.prefix:
            return f"{self.prefix}/{key}"
        return key


def get_storage(settings: Settings | None = None) -> StorageBackend:
    settings = settings or get_settings()
    backend = settings.storage_backend.lower()
    if backend == "local":
        return LocalStorage(settings.upload_path)
    if backend == "s3":
        return S3Storage(settings)
    else:
        raise RuntimeError(f"Unsupported storage backend: {settings.storage_backend}")


async def validate_and_store_image(
    file: UploadFile,
    listing_id: int,
    settings: Settings | None = None,
) -> StoredFile:
    validated = await read_validated_image(file, settings)
    return store_validated_image(validated, listing_id, settings)


async def read_validated_image(
    file: UploadFile,
    settings: Settings | None = None,
) -> ValidatedUpload:
    settings = settings or get_settings()
    content = await file.read(settings.max_upload_bytes + 1)
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded image is empty")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"Image exceeds {settings.max_upload_size_mb} MB limit")

    detected_type, extension = detect_image_type(content)
    if detected_type not in settings.allowed_image_type_set:
        raise HTTPException(status_code=415, detail=f"Unsupported image type: {detected_type}")

    declared_type = (file.content_type or "").lower()
    if declared_type and declared_type not in settings.allowed_image_type_set:
        raise HTTPException(status_code=415, detail=f"Unsupported image type: {declared_type}")

    original = safe_filename(file.filename or f"upload{extension}")
    checksum = hashlib.sha256(content).hexdigest()

    return ValidatedUpload(
        original_filename=original,
        content=content,
        content_type=detected_type,
        file_size=len(content),
        checksum_sha256=checksum,
        extension=extension,
    )


def store_validated_image(
    upload: ValidatedUpload,
    listing_id: int,
    settings: Settings | None = None,
) -> StoredFile:
    stem = Path(upload.original_filename).stem or "image"
    stored_name = f"{stem}-{uuid.uuid4().hex}{upload.extension}"
    storage_path = get_storage(settings).save_listing_image(listing_id, stored_name, upload)
    return StoredFile(
        original_filename=upload.original_filename,
        storage_path=storage_path,
        content_type=upload.content_type,
        file_size=upload.file_size,
        checksum_sha256=upload.checksum_sha256,
    )


def detect_image_type(content: bytes) -> tuple[str, str]:
    if content.startswith(IMAGE_SIGNATURES["image/jpeg"][0]):
        return "image/jpeg", ".jpg"
    if content.startswith(IMAGE_SIGNATURES["image/png"][0]):
        return "image/png", ".png"
    if content.startswith(IMAGE_SIGNATURES["image/gif"][0]):
        return "image/gif", ".gif"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise HTTPException(status_code=415, detail="Unsupported image type")


def safe_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return name[:180] or "upload"


def remove_local_file(path: str) -> None:
    if not path:
        return
    try:
        target = Path(path)
        target.unlink(missing_ok=True)
        parent = target.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        return


def delete_stored_file(storage_path: str, settings: Settings | None = None) -> None:
    get_storage(settings).delete(storage_path)


def local_storage_path(storage_path: str, settings: Settings | None = None) -> Path | None:
    return get_storage(settings).read_local_file(storage_path)


def stored_file_bytes(storage_path: str, settings: Settings | None = None) -> bytes | None:
    return get_storage(settings).read_bytes(storage_path)


def parse_s3_uri(storage_path: str) -> tuple[str, str] | None:
    if not storage_path.startswith("s3://"):
        return None
    remainder = storage_path[5:]
    if "/" not in remainder:
        return None
    bucket, key = remainder.split("/", 1)
    if not bucket or not key:
        return None
    return bucket, key
