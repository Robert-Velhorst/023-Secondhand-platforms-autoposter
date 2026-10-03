import uuid
from pathlib import Path
from types import SimpleNamespace

from app.config import Settings
from app.database import SessionLocal
from app.models import ListingImage
from app.storage import S3Storage, ValidatedUpload, parse_s3_uri
from tests.test_api import client

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
)
PNG_BYTES_2 = PNG_BYTES + b"\x00"


def auth_headers():
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"storage-{uuid.uuid4().hex}@example.com",
            "password": "correct-password",
            "name": "Storage User",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def create_listing(headers):
    response = client.post(
        "/api/listings",
        headers=headers,
        json={
            "title": "Storage test listing",
            "description": "Image upload test.",
            "price_cents": 1000,
            "category": "Other",
            "location": "Arnhem",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_upload_sanitizes_and_records_image_metadata():
    headers = auth_headers()
    listing_id = create_listing(headers)

    response = client.post(
        f"/api/listings/{listing_id}/images",
        headers=headers,
        files={"file": ("..\\bad name.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 200, response.text
    image = response.json()["images"][0]
    assert image["filename"] == "bad-name.png"
    assert image["content_type"] == "image/png"
    assert image["file_size"] == len(PNG_BYTES)
    assert len(image["checksum_sha256"]) == 64
    assert "storage_path" not in image

    content_response = client.get(
        f"/api/listings/{listing_id}/images/{image['id']}/content",
        headers=headers,
    )
    assert content_response.status_code == 200
    assert content_response.content == PNG_BYTES
    assert content_response.headers["cache-control"].startswith("private")
    assert content_response.headers["content-length"] == str(len(PNG_BYTES))


def test_image_content_streams_bounded_chunks_and_closes_storage(monkeypatch):
    from app import api
    from app.storage import StoredRead

    headers = auth_headers()
    listing_id = create_listing(headers)
    upload = client.post(
        f"/api/listings/{listing_id}/images",
        headers=headers,
        files={"file": ("stream.png", PNG_BYTES, "image/png")},
    )
    assert upload.status_code == 200, upload.text
    image_id = upload.json()["images"][0]["id"]

    class TrackingBody:
        def __init__(self, content):
            self.content = content
            self.offset = 0
            self.read_sizes = []
            self.closed = False

        def read(self, amount=-1):
            self.read_sizes.append(amount)
            if amount < 0:
                amount = len(self.content)
            chunk = self.content[self.offset:self.offset + amount]
            self.offset += len(chunk)
            return chunk

        def close(self):
            self.closed = True

    expected = b"x" * (150 * 1024)
    body = TrackingBody(expected)
    monkeypatch.setattr(api, "open_stored_file", lambda *_args: StoredRead(body, len(expected)))

    def reject_full_listing_load(*_args, **_kwargs):
        raise AssertionError("image content requests must not load every listing relation")

    monkeypatch.setattr(api, "_load_listing", reject_full_listing_load)

    response = client.get(
        f"/api/listings/{listing_id}/images/{image_id}/content",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.content == expected
    assert body.read_sizes == [64 * 1024, 64 * 1024, 64 * 1024, 64 * 1024]
    assert body.closed


def test_image_content_reports_missing_local_object():
    headers = auth_headers()
    listing_id = create_listing(headers)
    upload = client.post(
        f"/api/listings/{listing_id}/images",
        headers=headers,
        files={"file": ("missing.png", PNG_BYTES, "image/png")},
    )
    assert upload.status_code == 200, upload.text
    image_id = upload.json()["images"][0]["id"]
    with SessionLocal() as db:
        path = db.query(ListingImage.storage_path).filter(ListingImage.id == image_id).scalar()
    Path(path).unlink()

    response = client.get(
        f"/api/listings/{listing_id}/images/{image_id}/content",
        headers=headers,
    )

    assert response.status_code == 404


def test_duplicate_image_is_not_added_twice():
    headers = auth_headers()
    listing_id = create_listing(headers)

    for _ in range(2):
        response = client.post(
            f"/api/listings/{listing_id}/images",
            headers=headers,
            files={"file": ("photo.png", PNG_BYTES, "image/png")},
        )
        assert response.status_code == 200, response.text

    assert len(response.json()["images"]) == 1


def test_upload_rejects_non_image_content():
    headers = auth_headers()
    listing_id = create_listing(headers)

    response = client.post(
        f"/api/listings/{listing_id}/images",
        headers=headers,
        files={"file": ("notes.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_images_can_be_reordered():
    headers = auth_headers()
    listing_id = create_listing(headers)

    first_response = client.post(
        f"/api/listings/{listing_id}/images",
        headers=headers,
        files={"file": ("first.png", PNG_BYTES, "image/png")},
    )
    assert first_response.status_code == 200, first_response.text
    second_response = client.post(
        f"/api/listings/{listing_id}/images",
        headers=headers,
        files={"file": ("second.png", PNG_BYTES_2, "image/png")},
    )
    assert second_response.status_code == 200, second_response.text
    image_ids = [image["id"] for image in second_response.json()["images"]]

    reorder_response = client.patch(
        f"/api/listings/{listing_id}/images/order",
        headers=headers,
        json={"image_ids": list(reversed(image_ids))},
    )

    assert reorder_response.status_code == 200, reorder_response.text
    reordered = reorder_response.json()["images"]
    assert [image["id"] for image in reordered] == list(reversed(image_ids))
    assert [image["position"] for image in reordered] == [0, 1]


def test_delete_image_removes_local_file():
    headers = auth_headers()
    listing_id = create_listing(headers)
    upload_response = client.post(
        f"/api/listings/{listing_id}/images",
        headers=headers,
        files={"file": ("delete-me.png", PNG_BYTES, "image/png")},
    )
    assert upload_response.status_code == 200, upload_response.text
    image = upload_response.json()["images"][0]
    with SessionLocal() as db:
        storage_path = db.query(ListingImage.storage_path).filter(ListingImage.id == image["id"]).scalar()
    assert storage_path

    delete_response = client.delete(f"/api/listings/{listing_id}/images/{image['id']}", headers=headers)

    assert delete_response.status_code == 200, delete_response.text
    assert not Path(storage_path).exists()


def test_image_content_is_owner_scoped_and_duplicates_use_independent_files():
    owner_headers = auth_headers()
    other_headers = auth_headers()
    listing_id = create_listing(owner_headers)
    upload_response = client.post(
        f"/api/listings/{listing_id}/images",
        headers=owner_headers,
        files={"file": ("original.png", PNG_BYTES, "image/png")},
    )
    image = upload_response.json()["images"][0]

    forbidden = client.get(
        f"/api/listings/{listing_id}/images/{image['id']}/content",
        headers=other_headers,
    )
    assert forbidden.status_code == 404

    duplicate_response = client.post(f"/api/listings/{listing_id}/duplicate", headers=owner_headers)
    assert duplicate_response.status_code == 200, duplicate_response.text
    duplicate = duplicate_response.json()
    duplicate_image = duplicate["images"][0]
    with SessionLocal() as db:
        paths = {
            row.id: row.storage_path
            for row in db.query(ListingImage).filter(ListingImage.id.in_([image["id"], duplicate_image["id"]])).all()
        }
    assert paths[image["id"]] != paths[duplicate_image["id"]]

    client.delete(
        f"/api/listings/{duplicate['id']}/images/{duplicate_image['id']}",
        headers=owner_headers,
    )
    original_content = client.get(
        f"/api/listings/{listing_id}/images/{image['id']}/content",
        headers=owner_headers,
    )
    assert original_content.status_code == 200
    assert original_content.content == PNG_BYTES


def test_storage_quota_applies_to_upload_and_listing_image_copies(monkeypatch):
    from app import api
    from app.config import Settings

    headers = auth_headers()
    listing_id = create_listing(headers)
    monkeypatch.setattr(api, "get_settings", lambda: Settings(max_user_storage_mb=0))
    upload_response = client.post(
        f"/api/listings/{listing_id}/images",
        headers=headers,
        files={"file": ("too-large-for-account.png", PNG_BYTES, "image/png")},
    )
    assert upload_response.status_code == 413
    assert upload_response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert client.get("/api/listings", headers=headers).json()[0]["images"] == []

    # Existing images may predate a newly lowered operator quota; duplication
    # still checks the exact bytes before writing any copies.
    monkeypatch.undo()
    upload_response = client.post(
        f"/api/listings/{listing_id}/images",
        headers=headers,
        files={"file": ("source.png", PNG_BYTES, "image/png")},
    )
    assert upload_response.status_code == 200, upload_response.text
    monkeypatch.setattr(api, "get_settings", lambda: Settings(max_user_storage_mb=0))
    duplicate_response = client.post(f"/api/listings/{listing_id}/duplicate", headers=headers)
    assert duplicate_response.status_code == 413
    assert len(client.get("/api/listings", headers=headers).json()) == 1


def test_s3_storage_writes_metadata_and_deletes_objects(monkeypatch):
    calls = []

    class FakeS3Client:
        def put_object(self, **kwargs):
            calls.append(("put", kwargs))

        def delete_object(self, **kwargs):
            calls.append(("delete", kwargs))

        def get_object(self, **kwargs):
            calls.append(("get", kwargs))
            return {
                "Body": SimpleNamespace(read=lambda: PNG_BYTES, close=lambda: None),
                "ContentLength": len(PNG_BYTES),
            }

    def fake_client(service, region_name=None, endpoint_url=None, config=None):
        assert service == "s3"
        assert region_name == "eu-west-1"
        assert endpoint_url == "https://s3.example.test"
        assert config.connect_timeout == 3
        assert config.read_timeout == 5
        assert config.retries == {"mode": "standard", "total_max_attempts": 2}
        return FakeS3Client()

    monkeypatch.setitem(
        __import__("sys").modules,
        "boto3",
        SimpleNamespace(client=fake_client),
    )
    settings = Settings(
        storage_backend="s3",
        s3_bucket="autoposter-images",
        s3_region="eu-west-1",
        s3_endpoint_url="https://s3.example.test",
        s3_key_prefix="tenant-a/uploads",
    )
    upload = ValidatedUpload(
        original_filename="chair.png",
        content=PNG_BYTES,
        content_type="image/png",
        file_size=len(PNG_BYTES),
        checksum_sha256="a" * 64,
        extension=".png",
    )
    storage = S3Storage(settings)

    uri = storage.save_listing_image(42, "chair-uuid.png", upload)
    assert storage.read_bytes(uri) == PNG_BYTES
    storage.delete(uri)

    assert uri == "s3://autoposter-images/tenant-a/uploads/42/chair-uuid.png"
    assert parse_s3_uri(uri) == ("autoposter-images", "tenant-a/uploads/42/chair-uuid.png")
    assert calls[0] == (
        "put",
        {
            "Bucket": "autoposter-images",
            "Key": "tenant-a/uploads/42/chair-uuid.png",
            "Body": PNG_BYTES,
            "ContentType": "image/png",
            "Metadata": {
                "original-filename": "chair.png",
                "checksum-sha256": "a" * 64,
            },
        },
    )
    assert calls[1] == (
        "get",
        {
            "Bucket": "autoposter-images",
            "Key": "tenant-a/uploads/42/chair-uuid.png",
        },
    )
    assert calls[2] == (
        "delete",
        {
            "Bucket": "autoposter-images",
            "Key": "tenant-a/uploads/42/chair-uuid.png",
        },
    )


def test_s3_open_read_is_lazy_and_restricted_to_configured_prefix(monkeypatch):
    reads = []
    requests = []

    class TrackingBody:
        def read(self, amount=-1):
            reads.append(amount)
            return PNG_BYTES[:amount] if amount >= 0 else PNG_BYTES

        def close(self):
            pass

    class FakeS3Client:
        def get_object(self, **kwargs):
            requests.append(kwargs)
            return {"Body": TrackingBody(), "ContentLength": len(PNG_BYTES)}

    monkeypatch.setitem(
        __import__("sys").modules,
        "boto3",
        SimpleNamespace(client=lambda *_args, **_kwargs: FakeS3Client()),
    )
    storage = S3Storage(Settings(storage_backend="s3", s3_bucket="images", s3_key_prefix="private/uploads"))

    opened = storage.open_read("s3://images/private/uploads/1/photo.png")

    assert opened is not None
    assert opened.content_length == len(PNG_BYTES)
    assert reads == [], "Opening an S3 object must not eagerly read its bytes"
    assert opened.body.read(4) == PNG_BYTES[:4]
    opened.body.close()
    assert storage.open_read("s3://images/other-tenant/photo.png") is None
    assert requests == [{"Bucket": "images", "Key": "private/uploads/1/photo.png"}]
