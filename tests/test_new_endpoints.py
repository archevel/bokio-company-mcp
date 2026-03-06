"""Tests for endpoints added in the second batch:
download_upload, invoice attachments, invoice settlements (read/delete),
get_invoice_payment, record operations, bank payments, chart of accounts,
company information, SIE download, get_fiscal_year.
"""
import httpx
import pytest

from bokio_mcp import server
from bokio_mcp.client import BokioError

from .conftest import COMPANY_ID, api

INVOICE_ID = "a419cf69-db6f-4de9-992c-b1a60942a443"
UPLOAD_ID = "a419cf69-db6f-4de9-992c-b1a60942a443"
ATTACHMENT_ID = "240a4af0-edfd-47b1-b4ab-f30450eaac19"
PAYMENT_ID = "b529df79-eb7f-5ef0-a8dc-c2b71f953554"
SETTLEMENT_ID = "c529df79-eb7f-5ef0-a8dc-c2b71f953554"
CREDIT_NOTE_ID = "d629df79-eb7f-5ef0-a8dc-c2b71f953554"
BANK_PAYMENT_ID = "835ba700-b306-4bd9-8447-59207b6b0002"
FISCAL_YEAR_ID = "fd5cf0c4-d68f-48d7-b01d-ed478c268d9e"

ATTACHMENT = {
    "id": ATTACHMENT_ID,
    "invoiceId": INVOICE_ID,
    "fileName": "receipt.pdf",
}

PAYMENT = {
    "id": PAYMENT_ID,
    "date": "2024-10-15",
    "sumBaseCurrency": 250.0,
    "bookkeepingAccountNumber": 1930,
}

SETTLEMENT = {
    "id": SETTLEMENT_ID,
    "invoiceId": INVOICE_ID,
    "type": "bankFee",
    "invoiceSettlementDetails": {"date": "2024-10-15", "sumBaseCurrency": 5.0},
}

BANK_PAYMENT = {
    "id": BANK_PAYMENT_ID,
    "status": "readyToSign",
    "amount": 1200.0,
    "createdDateTime": "2025-08-25T08:15:00Z",
    "paymentDate": "2025-08-25",
    "ownNote": "Rent payment",
    "recipientRef": {
        "kind": "transfer",
        "recipientName": "Property Management Co",
        "recipientReference": "RENT-2025-08",
        "clearingNumber": "5011",
        "accountNumber": "0379101",
    },
}

FISCAL_YEAR = {
    "id": FISCAL_YEAR_ID,
    "startDate": "2024-01-01",
    "endDate": "2024-12-31",
    "status": "open",
    "accountingMethod": "accrual",
}

FAKE_IMAGE = b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


# ---------------------------------------------------------------------------
# Upload download
# ---------------------------------------------------------------------------


UPLOAD_META = {
    "id": UPLOAD_ID,
    "description": "Receipt for invoice 1234",
    "contentType": "image/png",
    "journalEntryId": None,
}


def _mock_download_upload(mock_api, content=FAKE_IMAGE, content_type="image/png", meta=UPLOAD_META):
    mock_api.get(api(f"/companies/{COMPANY_ID}/uploads/{UPLOAD_ID}")).mock(
        return_value=httpx.Response(200, json=meta)
    )
    mock_api.get(api(f"/companies/{COMPANY_ID}/uploads/{UPLOAD_ID}/download")).mock(
        return_value=httpx.Response(200, content=content, headers={"content-type": content_type})
    )


async def test_download_upload_returns_resource_uri(mock_api):
    _mock_download_upload(mock_api)

    result = await server.download_upload(upload_id=UPLOAD_ID)

    assert result["resource_uri"] == f"bokio://upload/{UPLOAD_ID}"
    assert result["description"] == "Receipt for invoice 1234"
    data, ct, _ = server._resource_store[result["resource_uri"]]
    assert data == FAKE_IMAGE
    assert ct == "image/png"


async def test_download_upload_pdf(mock_api):
    fake_pdf = b"%PDF-1.4 fake pdf content"
    _mock_download_upload(mock_api, content=fake_pdf, content_type="application/pdf")

    result = await server.download_upload(upload_id=UPLOAD_ID)

    data, _, _ = server._resource_store[result["resource_uri"]]
    assert data == fake_pdf


async def test_download_upload_not_found(mock_api):
    mock_api.get(api(f"/companies/{COMPANY_ID}/uploads/{UPLOAD_ID}")).mock(
        return_value=httpx.Response(404, json={"code": "not-found", "message": "upload not found"})
    )
    mock_api.get(api(f"/companies/{COMPANY_ID}/uploads/{UPLOAD_ID}/download")).mock(
        return_value=httpx.Response(404, json={"code": "not-found", "message": "upload not found"})
    )

    with pytest.raises(BokioError) as exc_info:
        await server.download_upload(upload_id=UPLOAD_ID)

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Invoice attachments
# ---------------------------------------------------------------------------


async def test_list_invoice_attachments(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [ATTACHMENT]}
    mock_api.get(
        api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/attachments")
    ).mock(return_value=httpx.Response(200, json=page))

    result = await server.list_invoice_attachments(invoice_id=INVOICE_ID)

    assert result["items"][0]["fileName"] == "receipt.pdf"


async def test_get_invoice_attachment(mock_api):
    mock_api.get(
        api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/attachments/{ATTACHMENT_ID}")
    ).mock(return_value=httpx.Response(200, json=ATTACHMENT))

    result = await server.get_invoice_attachment(
        invoice_id=INVOICE_ID, attachment_id=ATTACHMENT_ID
    )

    assert result["id"] == ATTACHMENT_ID


async def test_download_invoice_attachment(mock_api):
    mock_api.get(
        api(
            f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}"
            f"/attachments/{ATTACHMENT_ID}/download"
        )
    ).mock(
        return_value=httpx.Response(
            200,
            content=FAKE_IMAGE,
            headers={"content-type": "image/png"},
        )
    )

    result = await server.download_invoice_attachment(
        invoice_id=INVOICE_ID, attachment_id=ATTACHMENT_ID
    )

    assert result["content_type"] == "image/png"
    assert result["resource_uri"] == f"bokio://invoice/{INVOICE_ID}/attachment/{ATTACHMENT_ID}"
    data, _, _ = server._resource_store[result["resource_uri"]]
    assert data == FAKE_IMAGE


async def test_delete_invoice_attachment(mock_api):
    mock_api.delete(
        api(
            f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}"
            f"/attachments/{ATTACHMENT_ID}"
        )
    ).mock(return_value=httpx.Response(204))

    result = await server.delete_invoice_attachment(
        invoice_id=INVOICE_ID, attachment_id=ATTACHMENT_ID
    )

    assert "deleted" in result.lower()


# ---------------------------------------------------------------------------
# Invoice settlements (read / delete)
# ---------------------------------------------------------------------------


async def test_list_invoice_settlements(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [SETTLEMENT]}
    mock_api.get(
        api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/settlements")
    ).mock(return_value=httpx.Response(200, json=page))

    result = await server.list_invoice_settlements(invoice_id=INVOICE_ID)

    assert result["items"][0]["type"] == "bankFee"


async def test_get_invoice_settlement(mock_api):
    mock_api.get(
        api(
            f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}"
            f"/settlements/{SETTLEMENT_ID}"
        )
    ).mock(return_value=httpx.Response(200, json=SETTLEMENT))

    result = await server.get_invoice_settlement(
        invoice_id=INVOICE_ID, settlement_id=SETTLEMENT_ID
    )

    assert result["id"] == SETTLEMENT_ID


async def test_delete_invoice_settlement(mock_api):
    mock_api.delete(
        api(
            f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}"
            f"/settlements/{SETTLEMENT_ID}"
        )
    ).mock(return_value=httpx.Response(204))

    result = await server.delete_invoice_settlement(
        invoice_id=INVOICE_ID, settlement_id=SETTLEMENT_ID
    )

    assert "deleted" in result.lower()


# ---------------------------------------------------------------------------
# Invoice payment (single get)
# ---------------------------------------------------------------------------


async def test_get_invoice_payment(mock_api):
    mock_api.get(
        api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/payments/{PAYMENT_ID}")
    ).mock(return_value=httpx.Response(200, json=PAYMENT))

    result = await server.get_invoice_payment(
        invoice_id=INVOICE_ID, payment_id=PAYMENT_ID
    )

    assert result["sumBaseCurrency"] == 250.0


# ---------------------------------------------------------------------------
# Record operations
# ---------------------------------------------------------------------------


async def test_record_invoice(mock_api):
    recorded = {"id": INVOICE_ID, "status": "published"}
    mock_api.post(
        api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/record")
    ).mock(return_value=httpx.Response(200, json=recorded))

    result = await server.record_invoice(invoice_id=INVOICE_ID)

    assert result["status"] == "published"


async def test_record_invoice_payment(mock_api):
    recorded = {**PAYMENT, "journalEntryRef": {"id": "some-je-id"}}
    mock_api.post(
        api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/payments/{PAYMENT_ID}/record")
    ).mock(return_value=httpx.Response(200, json=recorded))

    result = await server.record_invoice_payment(
        invoice_id=INVOICE_ID, payment_id=PAYMENT_ID
    )

    assert "journalEntryRef" in result


async def test_record_invoice_settlement(mock_api):
    recorded = {**SETTLEMENT, "journalEntryRef": {"id": "some-je-id"}}
    mock_api.post(
        api(
            f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}"
            f"/settlements/{SETTLEMENT_ID}/record"
        )
    ).mock(return_value=httpx.Response(200, json=recorded))

    result = await server.record_invoice_settlement(
        invoice_id=INVOICE_ID, settlement_id=SETTLEMENT_ID
    )

    assert "journalEntryRef" in result


async def test_record_credit_note(mock_api):
    recorded = {"id": CREDIT_NOTE_ID, "status": "published"}
    mock_api.post(
        api(f"/companies/{COMPANY_ID}/credit-notes/{CREDIT_NOTE_ID}/record")
    ).mock(return_value=httpx.Response(200, json=recorded))

    result = await server.record_credit_note(credit_note_id=CREDIT_NOTE_ID)

    assert result["status"] == "published"


# ---------------------------------------------------------------------------
# Bank payments
# ---------------------------------------------------------------------------


async def test_create_bank_payment(mock_api):
    mock_api.post(api(f"/companies/{COMPANY_ID}/bank-payments")).mock(
        return_value=httpx.Response(200, json=BANK_PAYMENT)
    )

    result = await server.create_bank_payment(
        amount=1200.0,
        payment_date="2025-08-25",
        recipient_ref={
            "kind": "transfer",
            "recipientName": "Property Management Co",
            "recipientReference": "RENT-2025-08",
            "clearingNumber": "5011",
            "accountNumber": "0379101",
        },
        own_note="Rent payment",
    )

    assert result["id"] == BANK_PAYMENT_ID
    assert result["status"] == "readyToSign"


async def test_list_bank_payments(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [BANK_PAYMENT]}
    mock_api.get(api(f"/companies/{COMPANY_ID}/bank-payments")).mock(
        return_value=httpx.Response(200, json=page)
    )

    result = await server.list_bank_payments()

    assert result["items"][0]["id"] == BANK_PAYMENT_ID


async def test_get_bank_payment(mock_api):
    mock_api.get(api(f"/companies/{COMPANY_ID}/bank-payments/{BANK_PAYMENT_ID}")).mock(
        return_value=httpx.Response(200, json=BANK_PAYMENT)
    )

    result = await server.get_bank_payment(bank_payment_id=BANK_PAYMENT_ID)

    assert result["amount"] == 1200.0


async def test_get_bank_payment_not_found(mock_api):
    mock_api.get(api(f"/companies/{COMPANY_ID}/bank-payments/{BANK_PAYMENT_ID}")).mock(
        return_value=httpx.Response(
            404, json={"code": "not-found", "message": "Bank payment not found"}
        )
    )

    with pytest.raises(BokioError) as exc_info:
        await server.get_bank_payment(bank_payment_id=BANK_PAYMENT_ID)

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Chart of accounts
# ---------------------------------------------------------------------------


async def test_get_chart_of_accounts(mock_api):
    accounts = [
        {"account": 1930, "name": "Företagskonto / Affärskonto", "accountType": "basePlanAccount"},
        {"account": 3001, "name": "Försäljning varor, 25% moms", "accountType": "basePlanAccount"},
    ]
    mock_api.get(api(f"/companies/{COMPANY_ID}/chart-of-accounts")).mock(
        return_value=httpx.Response(200, json=accounts)
    )

    result = await server.get_chart_of_accounts()

    assert len(result) == 2
    assert result[0]["account"] == 1930


async def test_get_chart_of_accounts_filtered(mock_api):
    accounts = [{"account": 1930, "name": "Företagskonto", "accountType": "basePlanAccount"}]
    route = mock_api.get(api(f"/companies/{COMPANY_ID}/chart-of-accounts")).mock(
        return_value=httpx.Response(200, json=accounts)
    )

    await server.get_chart_of_accounts(query="account==1930")

    assert route.calls.last.request.url.params["query"] == "account==1930"


async def test_get_account(mock_api):
    account = {
        "account": 1930,
        "name": "Företagskonto / Affärskonto",
        "accountType": "basePlanAccount",
        "accountBalance": 15000.75,
    }
    mock_api.get(api(f"/companies/{COMPANY_ID}/chart-of-accounts/1930")).mock(
        return_value=httpx.Response(200, json=account)
    )

    result = await server.get_account(account_number=1930)

    assert result["accountBalance"] == 15000.75


# ---------------------------------------------------------------------------
# Company information
# ---------------------------------------------------------------------------


async def test_get_company_information(mock_api):
    info = {
        "companyInformation": {
            "name": "Bokio AB",
            "orgNumber": "556789-0123",
            "vatNumber": "SE556789012301",
            "address": {"line1": "Storgatan 1", "city": "Stockholm", "country": "SE"},
        }
    }
    mock_api.get(api(f"/companies/{COMPANY_ID}/company-information")).mock(
        return_value=httpx.Response(200, json=info)
    )

    result = await server.get_company_information()

    assert result["companyInformation"]["name"] == "Bokio AB"


# ---------------------------------------------------------------------------
# SIE file download
# ---------------------------------------------------------------------------


async def test_download_sie_file(mock_api):
    # Encode with CP437 as the real Bokio API does
    fake_sie_text = "#FLAGGA 0\n#PROGRAM Bokio 1.0\n#KONTO 1930 F\xf6retagskonto\n"
    fake_sie = fake_sie_text.encode("cp437")
    mock_api.get(
        api(f"/companies/{COMPANY_ID}/sie/{FISCAL_YEAR_ID}/download")
    ).mock(
        return_value=httpx.Response(
            200,
            content=fake_sie,
            headers={"content-type": "application/octet-stream"},
        )
    )

    result = await server.download_sie_file(fiscal_year_id=FISCAL_YEAR_ID)

    assert result["content_type"] == "application/octet-stream"
    assert result["charset"] == "cp437"
    assert result["resource_uri"] == f"bokio://sie/{FISCAL_YEAR_ID}"
    raw, _, _ = server._resource_store[result["resource_uri"]]
    assert "Företagskonto" in raw.decode("cp437")
    # Confirm that decoding as UTF-8 would corrupt Swedish characters
    assert raw.decode("cp437") != raw.decode("latin-1")


async def test_download_sie_file_fiscal_year_not_found(mock_api):
    mock_api.get(
        api(f"/companies/{COMPANY_ID}/sie/{FISCAL_YEAR_ID}/download")
    ).mock(
        return_value=httpx.Response(
            404, json={"code": "not-found", "message": "Fiscal year not found"}
        )
    )

    with pytest.raises(BokioError) as exc_info:
        await server.download_sie_file(fiscal_year_id=FISCAL_YEAR_ID)

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Fiscal year (single)
# ---------------------------------------------------------------------------


async def test_get_fiscal_year(mock_api):
    mock_api.get(
        api(f"/companies/{COMPANY_ID}/fiscal-years/{FISCAL_YEAR_ID}")
    ).mock(return_value=httpx.Response(200, json={"fiscalYear": FISCAL_YEAR}))

    result = await server.get_fiscal_year(fiscal_year_id=FISCAL_YEAR_ID)

    assert result["fiscalYear"]["status"] == "open"


# ---------------------------------------------------------------------------
# Agent workflow: inspect receipt then record journal entry
# ---------------------------------------------------------------------------


async def test_receipt_to_journal_entry_workflow(mock_api):
    """Agent workflow: download a receipt, inspect it, create a matching journal entry."""
    fake_receipt = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    je_id = "new-je-id-1234"
    journal_entry = {
        "id": je_id,
        "title": "Receipt: Office supplies",
        "journalEntryNumber": "V100",
        "date": "2024-11-01",
        "items": [
            {"id": 1, "account": 6100, "debit": 500, "credit": 0},
            {"id": 2, "account": 2640, "debit": 125, "credit": 0},
            {"id": 3, "account": 1930, "debit": 0, "credit": 625},
        ],
    }

    _mock_download_upload(mock_api, content=fake_receipt)
    mock_api.post(api(f"/companies/{COMPANY_ID}/journal-entries")).mock(
        return_value=httpx.Response(200, json=journal_entry)
    )

    # Step 1: agent downloads the receipt — gets metadata + resource URI to inspect
    receipt = await server.download_upload(upload_id=UPLOAD_ID)
    assert receipt["resource_uri"] == f"bokio://upload/{UPLOAD_ID}"
    raw, _, _ = server._resource_store[receipt["resource_uri"]]
    assert raw == fake_receipt

    # Step 2: agent creates journal entry based on what it saw
    je = await server.create_journal_entry(
        title="Receipt: Office supplies",
        date="2024-11-01",
        items=[
            {"account": 6100, "debit": 500, "credit": 0},
            {"account": 2640, "debit": 125, "credit": 0},
            {"account": 1930, "debit": 0, "credit": 625},
        ],
    )

    assert je["id"] == je_id
    assert len(je["items"]) == 3
