import asyncio
import csv
import io
import threading
from concurrent.futures import TimeoutError as FutureTimeout

import httpx
import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app import api, storage
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Listing
from app.storage import LocalStorage
from tests.test_api import PNG_BYTES, client
from tests.test_data_portability import auth_headers


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def csv_bytes(description="CSV description"):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=api.LISTING_CSV_FIELDS)
    writer.writeheader()
    writer.writerow({"title": "CSV chair", "description": description})
    return output.getvalue().encode("utf-8")


@pytest.mark.parametrize("operation", ["upload", "csv"])
def test_health_completes_while_synchronous_request_work_is_blocked(monkeypatch, operation):
    headers = auth_headers(f"responsive-{operation}")
    created = client.post("/api/listings", headers=headers, json={"title": "Responsive upload"})
    assert created.status_code == 200, created.text
    listing_id = created.json()["id"]
    entered = threading.Event()
    release = threading.Event()
    observation = {}
    original = LocalStorage.save_listing_image if operation == "upload" else api._listing_from_csv_row

    def blocked_work(*args, **kwargs):
        observation["work_thread"] = threading.get_ident()
        entered.set()
        assert release.wait(10), "Test controller failed to release request work"
        return original(*args, **kwargs)

    if operation == "upload":
        monkeypatch.setattr(LocalStorage, "save_listing_image", blocked_work)
    else:
        monkeypatch.setattr(api, "_listing_from_csv_row", blocked_work)

    async def exercise():
        loop = asyncio.get_running_loop()
        observation["loop_thread"] = threading.get_ident()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as http:
            def probe_health():
                try:
                    assert entered.wait(10), "Target work did not start"
                    future = asyncio.run_coroutine_threadsafe(http.get("/api/health"), loop)
                    try:
                        response = future.result(timeout=2)
                        observation["health_before_release"] = response.status_code == 200
                    except FutureTimeout:
                        observation["health_before_release"] = False
                        future.cancel()
                except BaseException as exc:
                    observation["probe_error"] = exc
                finally:
                    release.set()

            controller = threading.Thread(target=probe_health)
            controller.start()
            try:
                if operation == "upload":
                    response = await http.post(f"/api/listings/{listing_id}/images", headers=headers,
                                               files={"file": ("image.png", PNG_BYTES, "image/png")})
                else:
                    response = await http.post("/api/import/listings.csv", headers=headers,
                                               files={"file": ("listings.csv", csv_bytes(), "text/csv")})
                assert response.status_code == 200, response.text
            finally:
                release.set()
                controller.join(timeout=5)
            assert not controller.is_alive()
    asyncio.run(exercise())
    assert "probe_error" not in observation, observation.get("probe_error")
    assert observation["health_before_release"], "Slow request work blocked the API event loop and health request"
    assert observation["work_thread"] != observation["loop_thread"]


@pytest.mark.parametrize(
    "content,expected", [
        (csv_bytes("x" * 2_000_000), 413),
        (b"\xff\xfeinvalid", 422),
        (csv_bytes("x" * 132_000), 422),
        (csv_bytes() + b'"unterminated', 422),
    ],
    ids=["oversized", "non-utf8", "parser-field-limit", "unterminated-quote"],
)
def test_csv_rejects_oversized_or_non_utf8_input_without_creating_listings(content, expected):
    headers = auth_headers("invalid-csv")
    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/import/listings.csv", headers=headers, files={"file": ("input.csv", content, "text/csv")}
    )
    assert response.status_code == expected, response.text[:300]
    with SessionLocal() as db:
        assert db.query(Listing).count() == 0


@pytest.mark.parametrize("extra,expected", [(0, 200), (1, 413)])
def test_csv_byte_limit_boundary(extra, expected):
    content = csv_bytes()
    content += b"\n" * (2_000_000 + extra - len(content))
    headers = auth_headers("csv-boundary")
    response = client.post("/api/import/listings.csv", headers=headers,
                           files={"file": ("input.csv", content, "text/csv")})
    assert response.status_code == expected, response.text[:300]
    with SessionLocal() as db:
        assert db.query(Listing).count() == int(expected == 200)


def test_async_storage_helpers_offload_read_validation_and_write(monkeypatch):
    threads = {}
    original_read = storage.read_validated_image_sync
    original_store = storage.store_validated_image

    def observed_read(*args, **kwargs):
        threads["read"] = threading.get_ident()
        return original_read(*args, **kwargs)

    def observed_store(*args, **kwargs):
        threads["store"] = threading.get_ident()
        return original_store(*args, **kwargs)

    monkeypatch.setattr(storage, "read_validated_image_sync", observed_read)
    monkeypatch.setattr(storage, "store_validated_image", observed_store)

    async def exercise():
        threads["loop"] = threading.get_ident()
        upload = UploadFile(io.BytesIO(PNG_BYTES), filename="helper.png")
        stored = await storage.validate_and_store_image(upload, 1)
        assert stored.file_size == len(PNG_BYTES)
        assert storage.local_storage_path(stored.storage_path).read_bytes() == PNG_BYTES

    asyncio.run(exercise())
    assert threads["read"] != threads["loop"]
    assert threads["store"] != threads["loop"]
