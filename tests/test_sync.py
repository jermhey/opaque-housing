from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from opaque_housing.app.sync import sync_published
from opaque_housing.metrics.publish import PublishError


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def test_sync_writes_allowlisted_files(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "git/trees" in url:
            return httpx.Response(
                200,
                json={
                    "tree": [
                        {
                            "path": "data/published/nyc/headlines.json",
                            "type": "blob",
                        },
                        {
                            "path": "data/published/nyc/readme.md",
                            "type": "blob",
                        },
                    ]
                },
            )
        if url.endswith("/data/published/nyc/headlines.json"):
            return httpx.Response(200, content=b'{"private_all_entity_only":{"parcels":1}}\n')
        return httpx.Response(404)

    dest = tmp_path / "published"
    report = sync_published(dest, http=_client(handler), repo="acme/housing", ref="main")
    assert report["ok"] is True
    assert report["files"] == ["nyc/headlines.json"]
    assert (dest / "nyc" / "headlines.json").exists()
    assert not (dest / "nyc" / "readme.md").exists()


def test_sync_refuses_parcel_file(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "git/trees" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "tree": [
                        {
                            "path": "data/published/nyc/parcels_classified.parquet",
                            "type": "blob",
                        }
                    ]
                },
            )
        return httpx.Response(404)

    with pytest.raises(PublishError, match="not a public aggregate"):
        sync_published(tmp_path / "published", http=_client(handler), repo="acme/x", ref="main")


def test_sync_refuses_owner_key_csv(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "git/trees" in url:
            return httpx.Response(
                200,
                json={"tree": [{"path": "data/published/nyc/stock_by_class.csv", "type": "blob"}]},
            )
        if url.endswith("stock_by_class.csv"):
            return httpx.Response(200, content=b"owner_key,units\nabc,1\n")
        return httpx.Response(404)

    dest = tmp_path / "published"
    with pytest.raises(PublishError, match="owner_key"):
        sync_published(dest, http=_client(handler), repo="acme/x", ref="main")
    assert not (dest / "nyc" / "stock_by_class.csv").exists()
