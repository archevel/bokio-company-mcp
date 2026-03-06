import httpx
import pytest

from bokio_mcp import server
from bokio_mcp.client import BokioError

from .conftest import COMPANY_ID, api

CREDIT_NOTE_ID = "b529df79-eb7f-5ef0-a8dc-c2b71f953554"
INVOICE_ID = "a419cf69-db6f-4de9-992c-b1a60942a443"
CUSTOMER_ID = "55c899c5-82b2-47fa-9c51-e35fc9b26443"

DRAFT_CREDIT_NOTE = {
    "id": CREDIT_NOTE_ID,
    "status": "draft",
    "invoiceRef": {"id": INVOICE_ID, "invoiceNumber": "IN-2024-001"},
    "customerRef": {"id": CUSTOMER_ID, "name": "Acme Corp"},
    "currency": "SEK",
    "currencyRate": 1,
    "totalAmount": 200.0,
    "totalTax": 50.0,
    "creditDate": "2024-10-15",
    "dueDate": "2024-11-15",
    "lineItems": [
        {
            "id": 1,
            "description": "Widget Pro",
            "itemType": "salesItem",
            "quantity": 2,
            "unitPrice": 100.0,
            "taxRate": 25,
        }
    ],
}


async def test_list_credit_notes(mock_api):
    page = {
        "totalItems": 1,
        "totalPages": 1,
        "currentPage": 1,
        "data": [DRAFT_CREDIT_NOTE],
    }
    mock_api.get(api(f"/companies/{COMPANY_ID}/credit-notes")).mock(
        return_value=httpx.Response(200, json=page)
    )

    result = await server.list_credit_notes()

    assert result["totalItems"] == 1
    assert result["data"][0]["id"] == CREDIT_NOTE_ID


async def test_list_credit_notes_filter_by_status(mock_api):
    page = {"totalItems": 0, "totalPages": 0, "currentPage": 1, "data": []}
    route = mock_api.get(api(f"/companies/{COMPANY_ID}/credit-notes")).mock(
        return_value=httpx.Response(200, json=page)
    )

    await server.list_credit_notes(query="status==draft")

    assert route.calls.last.request.url.params["query"] == "status==draft"


async def test_get_credit_note(mock_api):
    mock_api.get(api(f"/companies/{COMPANY_ID}/credit-notes/{CREDIT_NOTE_ID}")).mock(
        return_value=httpx.Response(200, json=DRAFT_CREDIT_NOTE)
    )

    result = await server.get_credit_note(
        credit_note_id=CREDIT_NOTE_ID
    )

    assert result["status"] == "draft"
    assert result["invoiceRef"]["id"] == INVOICE_ID


async def test_update_credit_note(mock_api):
    updated_body = {
        **DRAFT_CREDIT_NOTE,
        "lineItems": [{**DRAFT_CREDIT_NOTE["lineItems"][0], "quantity": 1}],
    }
    mock_api.put(api(f"/companies/{COMPANY_ID}/credit-notes/{CREDIT_NOTE_ID}")).mock(
        return_value=httpx.Response(200, json=updated_body)
    )

    result = await server.update_credit_note(
        credit_note_id=CREDIT_NOTE_ID,
        body=updated_body,
        
    )

    assert result["lineItems"][0]["quantity"] == 1


async def test_publish_credit_note(mock_api):
    published = {**DRAFT_CREDIT_NOTE, "status": "published"}
    mock_api.post(
        api(f"/companies/{COMPANY_ID}/credit-notes/{CREDIT_NOTE_ID}/publish")
    ).mock(return_value=httpx.Response(200, json=published))

    result = await server.publish_credit_note(
        credit_note_id=CREDIT_NOTE_ID
    )

    assert result["status"] == "published"


async def test_get_credit_note_not_found(mock_api):
    mock_api.get(api(f"/companies/{COMPANY_ID}/credit-notes/{CREDIT_NOTE_ID}")).mock(
        return_value=httpx.Response(
            404, json={"code": "not-found", "message": "Credit note not found"}
        )
    )

    with pytest.raises(BokioError) as exc_info:
        await server.get_credit_note(
            credit_note_id=CREDIT_NOTE_ID
        )

    assert exc_info.value.status_code == 404


async def test_publish_credit_note_already_published(mock_api):
    mock_api.post(
        api(f"/companies/{COMPANY_ID}/credit-notes/{CREDIT_NOTE_ID}/publish")
    ).mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "validation-error",
                "message": "Credit note is not in draft status",
            },
        )
    )

    with pytest.raises(BokioError) as exc_info:
        await server.publish_credit_note(
            credit_note_id=CREDIT_NOTE_ID
        )

    assert exc_info.value.status_code == 400
