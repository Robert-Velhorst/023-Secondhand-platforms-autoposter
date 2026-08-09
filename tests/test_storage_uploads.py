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


def test_s3_storage_writes_metadata_and_deletes_objects(monkeypatch):
    calls = []

    class FakeS3Client:
        def put_object(self, **kwargs):
            calls.append(("put", kwargs))

        def delete_object(self, **kwargs):
            calls.append(("delete", kwargs))

        def get_object(self, **kwargs):
            calls.append(("get", kwargs))
            return {"Body": SimpleNamespace(read=lambda: PNG_BYTES)}

    def fake_client(service, region_name=None, endpoint_url=None):
        assert service == "s3"
        assert region_name == "eu-west-1"
        assert endpoint_url == "https://s3.example.test"
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
