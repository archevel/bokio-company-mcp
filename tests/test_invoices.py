import httpx
import pytest

from bokio_mcp import server
from bokio_mcp.client import BokioError

from .conftest import COMPANY_ID, api

CUSTOMER_ID = "55c899c5-82b2-47fa-9c51-e35fc9b26443"
INVOICE_ID = "a419cf69-db6f-4de9-992c-b1a60942a443"
ITEM_ID = "835ba700-b306-4bd9-8447-59207b6b0002"
PAYMENT_ID = "b529df79-eb7f-5ef0-a8dc-c2b71f953554"
SETTLEMENT_ID = "c529df79-eb7f-5ef0-a8dc-c2b71f953554"
CREDIT_NOTE_ID = "d629df79-eb7f-5ef0-a8dc-c2b71f953554"

DRAFT_INVOICE = {
    "id": INVOICE_ID,
    "type": "invoice",
    "status": "draft",
    "customerRef": {"id": CUSTOMER_ID, "name": "Acme Corp"},
    "invoiceNumber": "1234",
    "currency": "SEK",
    "currencyRate": 1,
    "totalAmount": 250.0,
    "totalTax": 50.0,
    "paidAmount": 0,
    "invoiceDate": "2024-10-10",
    "dueDate": "2024-11-10",
    "lineItems": [
        {
            "id": 1,
            "description": "Widget Pro",
            "itemType": "salesItem",
            "productType": "goods",
            "unitType": "piece",
            "quantity": 2,
            "unitPrice": 100.0,
            "taxRate": 25,
        }
    ],
    "billingAddress": {
        "line1": "Älvsborgsvägen 10",
        "city": "Göteborg",
        "postalCode": "123 45",
        "country": "SE",
    },
    "metadata": {},
}

PUBLISHED_INVOICE = {**DRAFT_INVOICE, "status": "notPaid"}

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

CREDIT_NOTE = {
    "id": CREDIT_NOTE_ID,
    "status": "draft",
    "invoiceRef": {"id": INVOICE_ID, "invoiceNumber": "1234"},
    "customerRef": {"id": CUSTOMER_ID, "name": "Acme Corp"},
    "currency": "SEK",
    "totalAmount": 250.0,
    "lineItems": DRAFT_INVOICE["lineItems"],
}


# ---------------------------------------------------------------------------
# Basic CRUD
# ---------------------------------------------------------------------------


async def test_create_invoice(mock_api):
    mock_api.post(api(f"/companies/{COMPANY_ID}/invoices")).mock(
        return_value=httpx.Response(200, json=DRAFT_INVOICE)
    )

    result = await server.create_invoice(
        invoice_date="2024-10-10",
        line_items=[
            {
                "description": "Widget Pro",
                "itemType": "salesItem",
                "productType": "goods",
                "unitType": "piece",
                "quantity": 2,
                "unitPrice": 100.0,
                "taxRate": 25,
            }
        ],
        customer_ref={"id": CUSTOMER_ID, "name": "Acme Corp"},
        due_date="2024-11-10",
        currency="SEK",
        
    )

    assert result["id"] == INVOICE_ID
    assert result["status"] == "draft"


async def test_list_invoices(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [DRAFT_INVOICE]}
    mock_api.get(api(f"/companies/{COMPANY_ID}/invoices")).mock(
        return_value=httpx.Response(200, json=page)
    )

    result = await server.list_invoices()

    assert result["items"][0]["id"] == INVOICE_ID


async def test_list_invoices_filter_by_status(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [DRAFT_INVOICE]}
    route = mock_api.get(api(f"/companies/{COMPANY_ID}/invoices")).mock(
        return_value=httpx.Response(200, json=page)
    )

    await server.list_invoices(query="status==draft")

    assert route.calls.last.request.url.params["query"] == "status==draft"


async def test_get_invoice(mock_api):
    mock_api.get(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}")).mock(
        return_value=httpx.Response(200, json=DRAFT_INVOICE)
    )

    result = await server.get_invoice(invoice_id=INVOICE_ID)

    assert result["status"] == "draft"


async def test_update_invoice(mock_api):
    updated = {**DRAFT_INVOICE, "dueDate": "2024-12-10"}
    mock_api.put(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}")).mock(
        return_value=httpx.Response(200, json=updated)
    )

    result = await server.update_invoice(
        invoice_id=INVOICE_ID,
        invoice_date="2024-10-10",
        line_items=DRAFT_INVOICE["lineItems"],
        due_date="2024-12-10",
        
    )

    assert result["dueDate"] == "2024-12-10"


async def test_publish_invoice(mock_api):
    mock_api.post(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/publish")).mock(
        return_value=httpx.Response(200, json=PUBLISHED_INVOICE)
    )

    result = await server.publish_invoice(invoice_id=INVOICE_ID)

    assert result["status"] == "notPaid"


async def test_add_invoice_line_item(mock_api):
    new_line = {
        "id": 2,
        "description": "Extra Service",
        "itemType": "salesItem",
        "productType": "services",
        "unitType": "hour",
        "quantity": 1,
        "unitPrice": 500.0,
        "taxRate": 25,
    }
    mock_api.post(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/line-items")).mock(
        return_value=httpx.Response(200, json=new_line)
    )

    result = await server.add_invoice_line_item(
        invoice_id=INVOICE_ID,
        item_type="salesItem",
        description="Extra Service",
        product_type="services",
        unit_type="hour",
        quantity=1,
        unit_price=500.0,
        tax_rate=25,
        
    )

    assert result["id"] == 2
    assert result["unitPrice"] == 500.0


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


async def test_create_invoice_payment(mock_api):
    mock_api.post(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/payments")).mock(
        return_value=httpx.Response(200, json=PAYMENT)
    )

    result = await server.create_invoice_payment(
        invoice_id=INVOICE_ID,
        date="2024-10-15",
        sum_base_currency=250.0,
        
    )

    assert result["id"] == PAYMENT_ID
    assert result["sumBaseCurrency"] == 250.0


async def test_list_invoice_payments(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [PAYMENT]}
    mock_api.get(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/payments")).mock(
        return_value=httpx.Response(200, json=page)
    )

    result = await server.list_invoice_payments(
        invoice_id=INVOICE_ID
    )

    assert result["items"][0]["id"] == PAYMENT_ID


async def test_delete_invoice_payment(mock_api):
    mock_api.delete(
        api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/payments/{PAYMENT_ID}")
    ).mock(return_value=httpx.Response(204))

    result = await server.delete_invoice_payment(
        invoice_id=INVOICE_ID, payment_id=PAYMENT_ID
    )

    assert "deleted" in result.lower()


# ---------------------------------------------------------------------------
# Settlements
# ---------------------------------------------------------------------------


async def test_create_invoice_settlement(mock_api):
    mock_api.post(
        api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/settlements")
    ).mock(return_value=httpx.Response(200, json=SETTLEMENT))

    result = await server.create_invoice_settlement(
        invoice_id=INVOICE_ID,
        type="bankFee",
        date="2024-10-15",
        sum_base_currency=5.0,
        
    )

    assert result["id"] == SETTLEMENT_ID
    assert result["type"] == "bankFee"


# ---------------------------------------------------------------------------
# Credit notes from invoice
# ---------------------------------------------------------------------------


async def test_create_credit_note_from_invoice(mock_api):
    mock_api.post(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/credit")).mock(
        return_value=httpx.Response(200, json=CREDIT_NOTE)
    )

    result = await server.create_credit_note_from_invoice(
        invoice_id=INVOICE_ID
    )

    assert result["id"] == CREDIT_NOTE_ID
    assert result["status"] == "draft"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


async def test_get_invoice_not_found(mock_api):
    mock_api.get(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}")).mock(
        return_value=httpx.Response(
            404, json={"code": "not-found", "message": "invoice not found"}
        )
    )

    with pytest.raises(BokioError) as exc_info:
        await server.get_invoice(invoice_id=INVOICE_ID)

    assert exc_info.value.status_code == 404


async def test_publish_invoice_already_published(mock_api):
    mock_api.post(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/publish")).mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "validation-error",
                "message": "Invoice is not in draft status",
            },
        )
    )

    with pytest.raises(BokioError) as exc_info:
        await server.publish_invoice(invoice_id=INVOICE_ID)

    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Full agent workflows
# ---------------------------------------------------------------------------


async def test_full_invoice_lifecycle(mock_api):
    """Agent workflow: create invoice → publish → record payment."""
    mock_api.post(api(f"/companies/{COMPANY_ID}/invoices")).mock(
        return_value=httpx.Response(200, json=DRAFT_INVOICE)
    )
    mock_api.post(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/publish")).mock(
        return_value=httpx.Response(200, json=PUBLISHED_INVOICE)
    )
    mock_api.post(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/payments")).mock(
        return_value=httpx.Response(200, json=PAYMENT)
    )

    draft = await server.create_invoice(
        invoice_date="2024-10-10",
        line_items=[
            {
                "description": "Widget Pro",
                "itemType": "salesItem",
                "quantity": 2,
                "unitPrice": 100.0,
                "taxRate": 25,
            }
        ],
        
    )
    assert draft["status"] == "draft"

    published = await server.publish_invoice(
        invoice_id=draft["id"]
    )
    assert published["status"] == "notPaid"

    payment = await server.create_invoice_payment(
        invoice_id=published["id"],
        date="2024-10-15",
        sum_base_currency=250.0,
        
    )
    assert payment["sumBaseCurrency"] == published["totalAmount"]


async def test_full_credit_note_workflow(mock_api):
    """Agent workflow: publish invoice → create credit note → update → publish credit note."""
    published_credit_note = {**CREDIT_NOTE, "status": "published"}

    mock_api.post(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/publish")).mock(
        return_value=httpx.Response(200, json=PUBLISHED_INVOICE)
    )
    mock_api.post(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/credit")).mock(
        return_value=httpx.Response(200, json=CREDIT_NOTE)
    )
    mock_api.put(api(f"/companies/{COMPANY_ID}/credit-notes/{CREDIT_NOTE_ID}")).mock(
        return_value=httpx.Response(200, json=CREDIT_NOTE)
    )
    mock_api.post(
        api(f"/companies/{COMPANY_ID}/credit-notes/{CREDIT_NOTE_ID}/publish")
    ).mock(return_value=httpx.Response(200, json=published_credit_note))

    published = await server.publish_invoice(
        invoice_id=INVOICE_ID
    )
    credit_draft = await server.create_credit_note_from_invoice(
        invoice_id=published["id"]
    )
    assert credit_draft["status"] == "draft"

    # Partially credit: reduce quantity on line item before publishing
    partial_body = {**credit_draft, "lineItems": [{**credit_draft["lineItems"][0], "quantity": 1}]}
    await server.update_credit_note(
        credit_note_id=credit_draft["id"], body=partial_body
    )

    final = await server.publish_credit_note(
        credit_note_id=credit_draft["id"]
    )
    assert final["status"] == "published"


async def test_invoice_with_bank_fee_settlement(mock_api):
    """Agent workflow: publish invoice → record payment with bank fee settlement."""
    mock_api.post(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/publish")).mock(
        return_value=httpx.Response(200, json=PUBLISHED_INVOICE)
    )
    mock_api.post(api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/payments")).mock(
        return_value=httpx.Response(200, json={**PAYMENT, "sumBaseCurrency": 245.0})
    )
    mock_api.post(
        api(f"/companies/{COMPANY_ID}/invoices/{INVOICE_ID}/settlements")
    ).mock(return_value=httpx.Response(200, json=SETTLEMENT))

    await server.publish_invoice(invoice_id=INVOICE_ID)
    payment = await server.create_invoice_payment(
        invoice_id=INVOICE_ID,
        date="2024-10-15",
        sum_base_currency=245.0,  # received less due to bank fee
        
    )
    settlement = await server.create_invoice_settlement(
        invoice_id=INVOICE_ID,
        type="bankFee",
        date="2024-10-15",
        sum_base_currency=5.0,  # covers the missing 5
        
    )

    assert payment["sumBaseCurrency"] == 245.0
    assert settlement["type"] == "bankFee"
