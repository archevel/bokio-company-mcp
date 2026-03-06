import httpx
import pytest

from bokio_mcp import server
from bokio_mcp.client import BokioError

from .conftest import COMPANY_ID, api

JOURNAL_ENTRY_ID = "a419cf69-db6f-4de9-992c-b1a60942a443"
REVERSING_ID = "835ba700-b306-4bd9-8447-59207b6b0002"

JOURNAL_ENTRY = {
    "id": JOURNAL_ENTRY_ID,
    "title": "invoice 1234",
    "journalEntryNumber": "V342",
    "date": "2024-10-10",
    "items": [
        {"id": 1, "debit": 200, "credit": 0, "account": 1930},
        {"id": 2, "debit": 0, "credit": 40, "account": 3011},
        {"id": 3, "debit": 0, "credit": 160, "account": 2611},
    ],
}

REVERSED_JOURNAL_ENTRY = {
    "id": REVERSING_ID,
    "title": "invoice 1234",
    "journalEntryNumber": "V343",
    "date": "2024-10-10",
    "items": [
        {"id": 1, "debit": 0, "credit": 200, "account": 1930},
        {"id": 2, "debit": 40, "credit": 0, "account": 3011},
        {"id": 3, "debit": 160, "credit": 0, "account": 2611},
    ],
    "reversingJournalEntryId": JOURNAL_ENTRY_ID,
}


async def test_create_journal_entry(mock_api):
    mock_api.post(api(f"/companies/{COMPANY_ID}/journal-entries")).mock(
        return_value=httpx.Response(200, json=JOURNAL_ENTRY)
    )

    result = await server.create_journal_entry(
        title="invoice 1234",
        date="2024-10-10",
        items=[
            {"account": 1930, "debit": 200, "credit": 0},
            {"account": 3011, "debit": 0, "credit": 40},
            {"account": 2611, "debit": 0, "credit": 160},
        ],
        
    )

    assert result["id"] == JOURNAL_ENTRY_ID
    assert result["journalEntryNumber"] == "V342"
    assert len(result["items"]) == 3


async def test_list_journal_entries(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [JOURNAL_ENTRY]}
    mock_api.get(api(f"/companies/{COMPANY_ID}/journal-entries")).mock(
        return_value=httpx.Response(200, json=page)
    )

    result = await server.list_journal_entries()

    assert result["totalItems"] == 1
    assert result["items"][0]["id"] == JOURNAL_ENTRY_ID


async def test_list_journal_entries_with_query(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [JOURNAL_ENTRY]}
    route = mock_api.get(api(f"/companies/{COMPANY_ID}/journal-entries")).mock(
        return_value=httpx.Response(200, json=page)
    )

    await server.list_journal_entries(
        query="title~invoice 1234", page=2, page_size=10
    )

    params = route.calls.last.request.url.params
    assert "title~invoice 1234" in params["query"]
    assert params["page"] == "2"
    assert params["pageSize"] == "10"


async def test_get_journal_entry(mock_api):
    mock_api.get(api(f"/companies/{COMPANY_ID}/journal-entries/{JOURNAL_ENTRY_ID}")).mock(
        return_value=httpx.Response(200, json=JOURNAL_ENTRY)
    )

    result = await server.get_journal_entry(
        journal_entry_id=JOURNAL_ENTRY_ID
    )

    assert result["id"] == JOURNAL_ENTRY_ID


async def test_reverse_journal_entry(mock_api):
    mock_api.post(
        api(f"/companies/{COMPANY_ID}/journal-entries/{JOURNAL_ENTRY_ID}/reverse")
    ).mock(return_value=httpx.Response(200, json=REVERSED_JOURNAL_ENTRY))

    result = await server.reverse_journal_entry(
        journal_entry_id=JOURNAL_ENTRY_ID
    )

    assert result["id"] == REVERSING_ID
    assert result["reversingJournalEntryId"] == JOURNAL_ENTRY_ID


async def test_create_then_reverse_workflow(mock_api):
    """Agent workflow: create a journal entry and immediately reverse it."""
    mock_api.post(api(f"/companies/{COMPANY_ID}/journal-entries")).mock(
        return_value=httpx.Response(200, json=JOURNAL_ENTRY)
    )
    mock_api.post(
        api(f"/companies/{COMPANY_ID}/journal-entries/{JOURNAL_ENTRY_ID}/reverse")
    ).mock(return_value=httpx.Response(200, json=REVERSED_JOURNAL_ENTRY))

    created = await server.create_journal_entry(
        title="invoice 1234",
        date="2024-10-10",
        items=[{"account": 1930, "debit": 200, "credit": 0}],
        
    )
    reversed_entry = await server.reverse_journal_entry(
        journal_entry_id=created["id"]
    )

    assert reversed_entry["reversingJournalEntryId"] == created["id"]
    # Credits and debits are swapped
    assert reversed_entry["items"][0]["credit"] == 200
    assert reversed_entry["items"][0]["debit"] == 0


async def test_get_journal_entry_not_found(mock_api):
    mock_api.get(
        api(f"/companies/{COMPANY_ID}/journal-entries/{JOURNAL_ENTRY_ID}")
    ).mock(
        return_value=httpx.Response(
            404,
            json={"code": "not-found", "message": "journal entry not found"},
        )
    )

    with pytest.raises(BokioError) as exc_info:
        await server.get_journal_entry(
            journal_entry_id=JOURNAL_ENTRY_ID
        )

    assert exc_info.value.status_code == 404
    assert "not-found" in str(exc_info.value)


async def test_create_journal_entry_validation_error(mock_api):
    mock_api.post(api(f"/companies/{COMPANY_ID}/journal-entries")).mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "validation-error",
                "message": "Validation failed with 1 error",
                "errors": [{"field": "#/title", "message": "The title field is required"}],
            },
        )
    )

    with pytest.raises(BokioError) as exc_info:
        await server.create_journal_entry(
            title="",
            date="2024-10-10",
            items=[],
            
        )

    assert exc_info.value.status_code == 400


async def test_missing_company_id_raises():
    """Without a company_id and without BOKIO_COMPANY_ID env var, tools must raise."""
    original = server.settings.company_id
    server.settings.company_id = None
    try:
        with pytest.raises(ValueError, match="BOKIO_COMPANY_ID is required"):
            await server.list_journal_entries()
    finally:
        server.settings.company_id = original
