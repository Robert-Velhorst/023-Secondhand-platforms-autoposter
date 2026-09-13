from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from app.static import RevalidatingStaticFiles
from tests.test_api import client


@pytest.mark.parametrize("path", ["/", "/index.html", "/app.js", "/styles.css", "/favicon.svg"])
def test_frontend_revalidates_cached_files_without_redownloading_unchanged_content(path):
    first = client.get(path)
    assert first.status_code == 200
    assert first.headers.get("cache-control") == "no-cache"
    directives = {part.strip() for part in first.headers["content-security-policy"].split(";")}
    assert "style-src 'self'" in directives
    assert "script-src 'self'" in directives
    cached = client.get(path, headers={"If-None-Match": first.headers["etag"]})
    assert cached.status_code == 304
    assert cached.content == b""
    assert cached.headers.get("cache-control") == "no-cache"
    head = client.head(path)
    assert head.status_code == 200
    assert head.content == b""
    assert head.headers.get("cache-control") == "no-cache"


def test_changed_frontend_file_replaces_the_cached_release(tmp_path):
    asset = tmp_path / "app.js"
    asset.write_text("old release", encoding="utf-8")
    file_client = TestClient(RevalidatingStaticFiles(directory=tmp_path))
    try:
        old = file_client.get("/app.js")
        asset.write_text("new release with updated behavior", encoding="utf-8")
        updated = file_client.get("/app.js", headers={
            "If-None-Match": old.headers["etag"],
            "If-Modified-Since": old.headers["last-modified"],
        })
        assert updated.status_code == 200
        assert updated.text == "new release with updated behavior"
        assert updated.headers["etag"] != old.headers["etag"]
        assert updated.headers["cache-control"] == "no-cache"
    finally:
        file_client.close()


def test_browser_icon_link_resolves_to_a_real_same_origin_image():
    class Icons(HTMLParser):
        urls = []

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == "link" and values.get("rel") == "icon":
                self.urls.append(values["href"])

    icons = Icons()
    icons.feed(client.get("/").text)
    assert icons.urls, "The browser needs an explicit icon instead of a missing favicon.ico"
    for url in icons.urls:
        assert url.startswith("/") and not url.startswith("//")
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/")
        assert response.content
