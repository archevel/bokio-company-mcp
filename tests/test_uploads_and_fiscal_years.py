import base64

import httpx
import pytest

from bokio_mcp import server

from .conftest import COMPANY_ID, api

UPLOAD_ID = "a419cf69-db6f-4de9-992c-b1a60942a443"
JOURNAL_ENTRY_ID = "835ba700-b306-4bd9-8447-59207b6b0002"

UPLOAD = {
    "id": UPLOAD_ID,
    "description": "Receipt for invoice 1234",
    "contentType": "image/png",
    "journalEntryId": JOURNAL_ENTRY_ID,
}

FISCAL_YEAR = {
    "id": "fy-2024",
    "startDate": "2024-01-01",
    "endDate": "2024-12-31",
    "status": "open",
    "accountingMethod": "accrual",
}


# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------


async def test_list_uploads(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [UPLOAD]}
    mock_api.get(api(f"/companies/{COMPANY_ID}/uploads")).mock(
        return_value=httpx.Response(200, json=page)
    )

    result = await server.list_uploads()

    assert result["items"][0]["id"] == UPLOAD_ID


async def test_list_uploads_filtered_by_journal_entry(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [UPLOAD]}
    route = mock_api.get(api(f"/companies/{COMPANY_ID}/uploads")).mock(
        return_value=httpx.Response(200, json=page)
    )

    await server.list_uploads(
        query=f"journalEntryId=={JOURNAL_ENTRY_ID}"
    )

    assert "journalEntryId" in route.calls.last.request.url.params["query"]


async def test_get_upload(mock_api):
    mock_api.get(api(f"/companies/{COMPANY_ID}/uploads/{UPLOAD_ID}")).mock(
        return_value=httpx.Response(200, json=UPLOAD)
    )

    result = await server.get_upload(upload_id=UPLOAD_ID)

    assert result["id"] == UPLOAD_ID
    assert result["contentType"] == "image/png"


# ---------------------------------------------------------------------------
# add_upload — file_data mode validation
# ---------------------------------------------------------------------------


async def test_add_upload_invalid_content_type(mock_api):
    with pytest.raises(ValueError, match="Unsupported content_type"):
        await server.add_upload(
            file_data=base64.b64encode(b"data").decode(),
            filename="file.txt",
            content_type="text/plain",
        )


async def test_add_upload_invalid_base64(mock_api):
    with pytest.raises(ValueError, match="not valid base64"):
        await server.add_upload(
            file_data="not-valid-base64!!!",
            filename="file.jpg",
            content_type="image/jpeg",
        )


async def test_resource_store_lru_eviction(mock_api):
    from bokio_mcp.server import _RESOURCE_STORE_MAX, _register_resource, _resource_store

    _resource_store.clear()
    for i in range(_RESOURCE_STORE_MAX + 5):
        _register_resource(f"bokio://upload/id-{i}", b"data", "image/jpeg", f"file-{i}.jpg")

    assert len(_resource_store) == _RESOURCE_STORE_MAX
    # oldest entries should have been evicted
    assert "bokio://upload/id-0" not in _resource_store
    # newest entries should still be present
    assert f"bokio://upload/id-{_RESOURCE_STORE_MAX + 4}" in _resource_store


async def test_add_upload_file_data_success(mock_api):
    mock_api.post(api(f"/companies/{COMPANY_ID}/uploads")).mock(
        return_value=httpx.Response(200, json={"id": "new-upload-id"})
    )
    image_bytes = b"\xff\xd8\xff"  # minimal JPEG header
    result = await server.add_upload(
        file_data=base64.b64encode(image_bytes).decode(),
        filename="photo.jpg",
        content_type="image/jpeg",
    )
    assert result["id"] == "new-upload-id"


# ---------------------------------------------------------------------------
# Fiscal Years
# ---------------------------------------------------------------------------


async def test_list_fiscal_years(mock_api):
    page = {
        "totalItems": 1,
        "totalPages": 1,
        "currentPage": 1,
        "items": [FISCAL_YEAR],
    }
    mock_api.get(api(f"/companies/{COMPANY_ID}/fiscal-years")).mock(
        return_value=httpx.Response(200, json=page)
    )

    result = await server.list_fiscal_years()

    assert result["items"][0]["status"] == "open"


async def test_list_fiscal_years_filter_open(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [FISCAL_YEAR]}
    route = mock_api.get(api(f"/companies/{COMPANY_ID}/fiscal-years")).mock(
        return_value=httpx.Response(200, json=page)
    )

    await server.list_fiscal_years(query="status==open")

    assert route.calls.last.request.url.params["query"] == "status==open"


async def test_list_fiscal_years_pagination(mock_api):
    page = {"totalItems": 3, "totalPages": 2, "currentPage": 2, "items": [FISCAL_YEAR]}
    route = mock_api.get(api(f"/companies/{COMPANY_ID}/fiscal-years")).mock(
        return_value=httpx.Response(200, json=page)
    )

    await server.list_fiscal_years(page=2, page_size=2)

    assert b"page=2" in route.calls.last.request.url.query
    assert b"pageSize=2" in route.calls.last.request.url.query
