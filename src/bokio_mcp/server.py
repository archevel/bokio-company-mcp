import asyncio
import base64
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.resources import FunctionResource

from .client import BokioClient, BokioError
from .settings import settings


# In-memory store for downloaded file content, keyed by resource URI.
# Allows add_upload to read back content that was downloaded in the same session.
_resource_store: dict[str, tuple[bytes, str, str]] = {}  # uri -> (data, content_type, filename)


def _register_resource(uri: str, data: bytes, content_type: str, filename: str) -> None:
    """Store downloaded bytes and register them as an MCP resource."""
    _resource_store[uri] = (data, content_type, filename)
    mcp.add_resource(
        FunctionResource.from_function(
            fn=lambda: data,
            uri=uri,
            name=filename,
            mime_type=content_type,
        )
    )


_client: BokioClient | None = None


@asynccontextmanager
async def lifespan(server: FastMCP):
    global _client
    _client = BokioClient()
    try:
        yield
    finally:
        await _client.aclose()
        _client = None


mcp = FastMCP("Bokio Company API", lifespan=lifespan)


def _cid() -> str:
    if not settings.company_id:
        raise ValueError("BOKIO_COMPANY_ID is required. Set it in your environment or .env file.")
    return settings.company_id


def _bokio() -> BokioClient:
    if _client is None:
        raise RuntimeError("BokioClient not initialized — server lifespan not started.")
    return _client


def _params(**kwargs: Any) -> dict:
    return {k: v for k, v in kwargs.items() if v is not None}


# ---------------------------------------------------------------------------
# Journal Entries
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_journal_entries(
    page: int = 1,
    page_size: int = 25,
    query: str | None = None,
) -> dict:
    """List journal entries for the company.

    The query parameter supports filtering on: title, journalEntryNumber, date,
    reversingJournalEntryId, reversedByJournalEntryId.
    Example: title~invoice 1234
    """
    cid = _cid()
    return await _bokio().get(
        f"/companies/{cid}/journal-entries",
        params=_params(page=page, pageSize=page_size, query=query),
    )


@mcp.tool()
async def get_journal_entry(journal_entry_id: str) -> dict:
    """Get a single journal entry by ID."""
    return await _bokio().get(f"/companies/{_cid()}/journal-entries/{journal_entry_id}")


@mcp.tool()
async def create_journal_entry(title: str, date: str, items: list[dict]) -> dict:
    """Create a journal entry.

    Each item in `items` must have: account (int), debit (number), credit (number).
    Debits and credits must balance. Date format: YYYY-MM-DD.

    Example items: [{"account": 1930, "debit": 200, "credit": 0},
                    {"account": 3011, "debit": 0, "credit": 200}]
    """
    return await _bokio().post(
        f"/companies/{_cid()}/journal-entries",
        json={"title": title, "date": date, "items": items},
    )


@mcp.tool()
async def reverse_journal_entry(journal_entry_id: str) -> dict:
    """Reverse a journal entry. Returns the new reversing journal entry.

    Constraints:
    - Only journal entries created through the API can be reversed (not UI-created ones).
    - Journal entries linked to a Bokio invoice or similar cannot be reversed.
    - Journal entries that have already been reversed cannot be reversed again.
    """
    return await _bokio().post(
        f"/companies/{_cid()}/journal-entries/{journal_entry_id}/reverse"
    )


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_customers(
    page: int = 1,
    page_size: int = 25,
    query: str | None = None,
) -> dict:
    """List customers for the company.

    The query parameter supports filtering on: name, type, vatNumber, orgNumber,
    modifiedDateTime. Example: name==Acme Corp
    """
    return await _bokio().get(
        f"/companies/{_cid()}/customers",
        params=_params(page=page, pageSize=page_size, query=query),
    )


@mcp.tool()
async def get_customer(customer_id: str) -> dict:
    """Get a single customer by ID."""
    return await _bokio().get(f"/companies/{_cid()}/customers/{customer_id}")


@mcp.tool()
async def create_customer(
    name: str,
    type: str,
    vat_number: str | None = None,
    org_number: str | None = None,
    payment_terms: str | None = None,
    language: str | None = None,
    address: dict | None = None,
    contacts_details: list[dict] | None = None,
) -> dict:
    """Create a customer.

    type: "company" or "person"
    address fields: line1, line2, city, postalCode, country (ISO 3166-1 alpha-2)
    contacts_details items: name, email, phone, isDefault
    """
    body: dict[str, Any] = {"name": name, "type": type}
    if vat_number is not None:
        body["vatNumber"] = vat_number
    if org_number is not None:
        body["orgNumber"] = org_number
    if payment_terms is not None:
        body["paymentTerms"] = payment_terms
    if language is not None:
        body["language"] = language
    if address is not None:
        body["address"] = address
    if contacts_details is not None:
        body["contactsDetails"] = contacts_details
    return await _bokio().post(f"/companies/{_cid()}/customers", json=body)


@mcp.tool()
async def update_customer(
    customer_id: str,
    name: str,
    type: str,
    vat_number: str | None = None,
    org_number: str | None = None,
    payment_terms: str | None = None,
    language: str | None = None,
    address: dict | None = None,
    contacts_details: list[dict] | None = None,
) -> dict:
    """Update an existing customer. Performs a full replacement of all fields."""
    body: dict[str, Any] = {"id": customer_id, "name": name, "type": type}
    if vat_number is not None:
        body["vatNumber"] = vat_number
    if org_number is not None:
        body["orgNumber"] = org_number
    if payment_terms is not None:
        body["paymentTerms"] = payment_terms
    if language is not None:
        body["language"] = language
    if address is not None:
        body["address"] = address
    if contacts_details is not None:
        body["contactsDetails"] = contacts_details
    return await _bokio().put(f"/companies/{_cid()}/customers/{customer_id}", json=body)


@mcp.tool()
async def delete_customer(customer_id: str) -> str:
    """Delete a customer. Only customers created through the API can be deleted."""
    await _bokio().delete(f"/companies/{_cid()}/customers/{customer_id}")
    return "Customer deleted."


# ---------------------------------------------------------------------------
# Items (inventory/product catalog)
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_items(
    page: int = 1,
    page_size: int = 25,
    query: str | None = None,
) -> dict:
    """List inventory items for the company.

    The query parameter supports filtering on: description, itemType, productType,
    unitType, unitPrice, taxRate. Example: description~Product 1
    """
    return await _bokio().get(
        f"/companies/{_cid()}/items",
        params=_params(page=page, pageSize=page_size, query=query),
    )


@mcp.tool()
async def get_item(item_id: str) -> dict:
    """Get a single inventory item by ID."""
    return await _bokio().get(f"/companies/{_cid()}/items/{item_id}")


@mcp.tool()
async def create_item(
    description: str,
    item_type: str,
    unit_price: float,
    product_type: str | None = None,
    unit_type: str | None = None,
    tax_rate: float | None = None,
) -> dict:
    """Create an inventory item.

    item_type: "salesItem" or "purchaseItem"
    product_type: "goods" or "services"
    unit_type: "piece", "hour", etc.
    tax_rate: 0, 6, 12, or 25
    """
    body: dict[str, Any] = {
        "description": description,
        "itemType": item_type,
        "unitPrice": unit_price,
    }
    if product_type is not None:
        body["productType"] = product_type
    if unit_type is not None:
        body["unitType"] = unit_type
    if tax_rate is not None:
        body["taxRate"] = tax_rate
    return await _bokio().post(f"/companies/{_cid()}/items", json=body)


@mcp.tool()
async def update_item(
    item_id: str,
    description: str,
    item_type: str,
    unit_price: float,
    product_type: str | None = None,
    unit_type: str | None = None,
    tax_rate: float | None = None,
) -> dict:
    """Update an existing inventory item."""
    body: dict[str, Any] = {
        "id": item_id,
        "description": description,
        "itemType": item_type,
        "unitPrice": unit_price,
    }
    if product_type is not None:
        body["productType"] = product_type
    if unit_type is not None:
        body["unitType"] = unit_type
    if tax_rate is not None:
        body["taxRate"] = tax_rate
    return await _bokio().put(f"/companies/{_cid()}/items/{item_id}", json=body)


@mcp.tool()
async def delete_item(item_id: str) -> str:
    """Delete an inventory item."""
    await _bokio().delete(f"/companies/{_cid()}/items/{item_id}")
    return "Item deleted."


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_invoices(
    page: int = 1,
    page_size: int = 25,
    query: str | None = None,
) -> dict:
    """List invoices for the company.

    The query parameter supports filtering on: type, customerRef, orderNumberReference,
    currency, totalAmount, status, invoiceDate, dueDate, metadata.
    Example: dueDate==2024-10-10&&currency==SEK
    """
    return await _bokio().get(
        f"/companies/{_cid()}/invoices",
        params=_params(page=page, pageSize=page_size, query=query),
    )


@mcp.tool()
async def get_invoice(invoice_id: str) -> dict:
    """Get a single invoice by ID."""
    return await _bokio().get(f"/companies/{_cid()}/invoices/{invoice_id}")


@mcp.tool()
async def create_invoice(
    invoice_date: str,
    line_items: list[dict],
    customer_ref: dict | None = None,
    type: str = "invoice",
    invoice_number: str | None = None,
    order_number_reference: str | None = None,
    currency: str | None = None,
    currency_rate: float | None = None,
    due_date: str | None = None,
    delivery_address: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    """Create a draft invoice.

    invoice_date and due_date format: YYYY-MM-DD
    customer_ref: {"id": "<uuid>", "name": "<name>"}
    line_items: list of salesItem or descriptionOnlyItem dicts.
      salesItem fields: description, itemType="salesItem", productType, unitType,
                        quantity, unitPrice, taxRate, itemRef (optional)
      descriptionOnlyItem fields: description, itemType="descriptionOnlyItem"
    metadata: arbitrary key-value string pairs for tagging
    """
    body: dict[str, Any] = {
        "type": type,
        "invoiceDate": invoice_date,
        "lineItems": line_items,
    }
    if customer_ref is not None:
        body["customerRef"] = customer_ref
    if invoice_number is not None:
        body["invoiceNumber"] = invoice_number
    if order_number_reference is not None:
        body["orderNumberReference"] = order_number_reference
    if currency is not None:
        body["currency"] = currency
    if currency_rate is not None:
        body["currencyRate"] = currency_rate
    if due_date is not None:
        body["dueDate"] = due_date
    if delivery_address is not None:
        body["deliveryAddress"] = delivery_address
    if metadata is not None:
        body["metadata"] = metadata
    return await _bokio().post(f"/companies/{_cid()}/invoices", json=body)


@mcp.tool()
async def update_invoice(
    invoice_id: str,
    invoice_date: str,
    line_items: list[dict],
    customer_ref: dict | None = None,
    type: str = "invoice",
    invoice_number: str | None = None,
    order_number_reference: str | None = None,
    currency: str | None = None,
    currency_rate: float | None = None,
    due_date: str | None = None,
    delivery_address: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    """Update a draft invoice. Only invoices in draft status can be updated.

    Performs a full replacement — fetch the invoice first to preserve existing fields.
    """
    body: dict[str, Any] = {
        "id": invoice_id,
        "type": type,
        "invoiceDate": invoice_date,
        "lineItems": line_items,
    }
    if customer_ref is not None:
        body["customerRef"] = customer_ref
    if invoice_number is not None:
        body["invoiceNumber"] = invoice_number
    if order_number_reference is not None:
        body["orderNumberReference"] = order_number_reference
    if currency is not None:
        body["currency"] = currency
    if currency_rate is not None:
        body["currencyRate"] = currency_rate
    if due_date is not None:
        body["dueDate"] = due_date
    if delivery_address is not None:
        body["deliveryAddress"] = delivery_address
    if metadata is not None:
        body["metadata"] = metadata
    return await _bokio().put(f"/companies/{_cid()}/invoices/{invoice_id}", json=body)


@mcp.tool()
async def publish_invoice(invoice_id: str) -> dict:
    """Publish a draft invoice, making it official and ready to send to the customer."""
    return await _bokio().post(f"/companies/{_cid()}/invoices/{invoice_id}/publish")


@mcp.tool()
async def add_invoice_line_item(
    invoice_id: str,
    item_type: str,
    description: str,
    item_ref: dict | None = None,
    product_type: str | None = None,
    unit_type: str | None = None,
    quantity: float | None = None,
    unit_price: float | None = None,
    tax_rate: float | None = None,
) -> dict:
    """Add a line item to an existing draft invoice.

    item_type: "salesItem" or "descriptionOnlyItem"
    item_ref: {"id": "<uuid>"} to reference an existing inventory item
    """
    body: dict[str, Any] = {"itemType": item_type, "description": description}
    if item_ref is not None:
        body["itemRef"] = item_ref
    if product_type is not None:
        body["productType"] = product_type
    if unit_type is not None:
        body["unitType"] = unit_type
    if quantity is not None:
        body["quantity"] = quantity
    if unit_price is not None:
        body["unitPrice"] = unit_price
    if tax_rate is not None:
        body["taxRate"] = tax_rate
    return await _bokio().post(
        f"/companies/{_cid()}/invoices/{invoice_id}/line-items", json=body
    )


@mcp.tool()
async def create_invoice_payment(
    invoice_id: str,
    date: str,
    sum_base_currency: float,
    bookkeeping_account_number: int = 1930,
) -> dict:
    """Create a payment record for an invoice.

    date format: YYYY-MM-DD
    sum_base_currency: amount paid in the company's base currency
    bookkeeping_account_number: accounting account to use (default 1930)

    Note: creating the payment record and recording it in bookkeeping are separate
    steps. Use record_invoice_payment to trigger the bookkeeping journal entry.
    """
    return await _bokio().post(
        f"/companies/{_cid()}/invoices/{invoice_id}/payments",
        json={
            "date": date,
            "sumBaseCurrency": sum_base_currency,
            "bookkeepingAccountNumber": bookkeeping_account_number,
        },
    )


@mcp.tool()
async def list_invoice_payments(
    invoice_id: str,
    page: int = 1,
    page_size: int = 25,
    query: str | None = None,
) -> dict:
    """List all payment records for an invoice.

    The query parameter supports filtering on: date, sumBaseCurrency.
    Example: date>2025-01-01
    """
    return await _bokio().get(
        f"/companies/{_cid()}/invoices/{invoice_id}/payments",
        params=_params(page=page, pageSize=page_size, query=query),
    )


@mcp.tool()
async def delete_invoice_payment(invoice_id: str, payment_id: str) -> str:
    """Delete a payment record from an invoice."""
    await _bokio().delete(
        f"/companies/{_cid()}/invoices/{invoice_id}/payments/{payment_id}"
    )
    return "Payment deleted."


@mcp.tool()
async def create_invoice_settlement(
    invoice_id: str,
    type: str,
    date: str,
    sum_base_currency: float,
) -> dict:
    """Create a settlement that adjusts the outstanding amount of an invoice.

    type: "currency" (exchange gain/loss) or "bankFee"
    date format: YYYY-MM-DD
    sum_base_currency: positive reduces the outstanding amount, negative increases it
      (e.g. use a negative value for a currency exchange gain)
    """
    return await _bokio().post(
        f"/companies/{_cid()}/invoices/{invoice_id}/settlements",
        json={
            "type": type,
            "invoiceSettlementDetails": {
                "date": date,
                "sumBaseCurrency": sum_base_currency,
            },
        },
    )


@mcp.tool()
async def create_credit_note_from_invoice(invoice_id: str) -> dict:
    """Create a draft credit note for a published invoice.

    After creation you can update the credit note (e.g. partial quantities) via
    update_credit_note, then publish it via publish_credit_note.
    """
    return await _bokio().post(f"/companies/{_cid()}/invoices/{invoice_id}/credit")


# ---------------------------------------------------------------------------
# Credit Notes
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_credit_notes(
    page: int = 1,
    page_size: int = 25,
    query: str | None = None,
) -> dict:
    """List credit notes for the company.

    The query parameter supports filtering on: type, customerRef, currency,
    totalAmount, status, invoiceDate, dueDate, metadata.
    Example: status==draft
    """
    return await _bokio().get(
        f"/companies/{_cid()}/credit-notes",
        params=_params(page=page, pageSize=page_size, query=query),
    )


@mcp.tool()
async def get_credit_note(credit_note_id: str) -> dict:
    """Get a single credit note by ID."""
    return await _bokio().get(f"/companies/{_cid()}/credit-notes/{credit_note_id}")


@mcp.tool()
async def update_credit_note(credit_note_id: str, body: dict) -> dict:
    """Update a draft credit note. Pass the full credit note body (fetch first via get_credit_note).

    Useful for partial credits: modify line item quantities before publishing.
    """
    return await _bokio().put(
        f"/companies/{_cid()}/credit-notes/{credit_note_id}", json=body
    )


@mcp.tool()
async def publish_credit_note(credit_note_id: str) -> dict:
    """Publish a draft credit note, making it official and immutable."""
    return await _bokio().post(
        f"/companies/{_cid()}/credit-notes/{credit_note_id}/publish"
    )


# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_uploads(
    page: int = 1,
    page_size: int = 25,
    query: str | None = None,
) -> dict:
    """List file uploads for the company. Always call this first to get valid
    upload IDs before calling get_upload or download_upload.

    The query parameter supports filtering on: description, journalEntryId.
    Example: description~Receipt
    """
    return await _bokio().get(
        f"/companies/{_cid()}/uploads",
        params=_params(page=page, pageSize=page_size, query=query),
    )


@mcp.tool()
async def get_upload(upload_id: str) -> dict:
    """Get metadata for a single upload by ID (description, contentType, journalEntryId).
    Use list_uploads to get valid IDs. To also fetch the file content, use
    download_upload instead — it returns metadata and registers the file as a resource
    in one call.
    """
    return await _bokio().get(f"/companies/{_cid()}/uploads/{upload_id}")


@mcp.tool()
async def add_upload(
    description: str | None = None,
    journal_entry_id: str | None = None,
    file_path: str | None = None,
    resource_uri: str | None = None,
    file_data: str | None = None,
    filename: str | None = None,
    content_type: str | None = None,
) -> dict:
    """Upload a file (image or PDF) to the company's uploads.

    Provide exactly one source:

    **file_path** (preferred for local files): absolute path to the file on disk.
      The server reads it directly — no encoding needed. Content type is inferred
      from the file extension. Example: file_path="/home/user/receipt.jpg"

    **resource_uri**: a bokio:// URI returned by download_upload or
      download_invoice_attachment, to re-upload a previously downloaded file.

    **file_data + filename + content_type**: base64-encoded content for remote
      server setups where the server cannot access the local filesystem.

    Optional for all modes:
      description: label for the upload; defaults to the filename if omitted
      journal_entry_id: UUID to attach the upload to a journal entry
    """
    if file_path is not None:
        path = Path(file_path)
        data = path.read_bytes()
        filename = path.name
        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    elif resource_uri is not None:
        if resource_uri not in _resource_store:
            raise ValueError(
                f"Resource not found in session store: {resource_uri}. "
                "Call download_upload or download_invoice_attachment first."
            )
        data, content_type, filename = _resource_store[resource_uri]
    elif file_data is not None and filename is not None and content_type is not None:
        data = base64.b64decode(file_data)
    else:
        raise ValueError(
            "Provide one of: file_path, resource_uri, or file_data+filename+content_type."
        )
    return await _bokio().post_multipart(
        f"/companies/{_cid()}/uploads",
        file_bytes=data,
        filename=filename,
        content_type=content_type,
        fields=_params(description=description, journalEntryId=journal_entry_id),
    )


@mcp.tool()
async def download_upload(upload_id: str) -> dict:
    """Fetch metadata AND file content for an upload in one call.

    Use list_uploads first to get valid IDs — do not guess or reuse IDs from
    earlier in the conversation as they may no longer exist.

    Returns the upload metadata (description, journalEntryId, etc.) plus a
    resource_uri the client can read to inspect the file content. The resource_uri
    can also be passed to add_upload to re-upload the file.
    Supported content types: image/png, image/jpeg, application/pdf.
    """
    metadata, (data, content_type) = await asyncio.gather(
        _bokio().get(f"/companies/{_cid()}/uploads/{upload_id}"),
        _bokio().get_bytes(f"/companies/{_cid()}/uploads/{upload_id}/download"),
    )
    uri = f"bokio://upload/{upload_id}"
    _register_resource(uri, data, content_type, f"{upload_id}")
    return {**metadata, "resource_uri": uri}


# ---------------------------------------------------------------------------
# Invoice attachments
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_invoice_attachments(
    invoice_id: str,
    page: int = 1,
    page_size: int = 25,
    query: str | None = None,
) -> dict:
    """List attachments for an invoice.

    The query parameter supports filtering on: fileName. Example: fileName~faktura
    """
    return await _bokio().get(
        f"/companies/{_cid()}/invoices/{invoice_id}/attachments",
        params=_params(page=page, pageSize=page_size, query=query),
    )


@mcp.tool()
async def get_invoice_attachment(invoice_id: str, attachment_id: str) -> dict:
    """Get metadata for a single invoice attachment."""
    return await _bokio().get(
        f"/companies/{_cid()}/invoices/{invoice_id}/attachments/{attachment_id}"
    )


@mcp.tool()
async def download_invoice_attachment(invoice_id: str, attachment_id: str) -> dict:
    """Download the file content of an invoice attachment.

    Registers the file as an MCP resource and returns its resource URI.
    The client can fetch the resource to inspect the content.
    """
    data, content_type = await _bokio().get_bytes(
        f"/companies/{_cid()}/invoices/{invoice_id}/attachments/{attachment_id}/download"
    )
    uri = f"bokio://invoice/{invoice_id}/attachment/{attachment_id}"
    _register_resource(uri, data, content_type, attachment_id)
    return {"resource_uri": uri, "content_type": content_type}


@mcp.tool()
async def delete_invoice_attachment(invoice_id: str, attachment_id: str) -> str:
    """Delete an attachment from a draft invoice."""
    await _bokio().delete(
        f"/companies/{_cid()}/invoices/{invoice_id}/attachments/{attachment_id}"
    )
    return "Attachment deleted."


# ---------------------------------------------------------------------------
# Invoice settlements (read/delete)
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_invoice_settlements(
    invoice_id: str,
    page: int = 1,
    page_size: int = 25,
    query: str | None = None,
) -> dict:
    """List all settlements for an invoice.

    The query parameter supports filtering on: date, sumBaseCurrency.
    Example: date>2025-01-01
    """
    return await _bokio().get(
        f"/companies/{_cid()}/invoices/{invoice_id}/settlements",
        params=_params(page=page, pageSize=page_size, query=query),
    )


@mcp.tool()
async def get_invoice_settlement(invoice_id: str, settlement_id: str) -> dict:
    """Get a single settlement for an invoice."""
    return await _bokio().get(
        f"/companies/{_cid()}/invoices/{invoice_id}/settlements/{settlement_id}"
    )


@mcp.tool()
async def delete_invoice_settlement(invoice_id: str, settlement_id: str) -> str:
    """Delete a settlement from an invoice."""
    await _bokio().delete(
        f"/companies/{_cid()}/invoices/{invoice_id}/settlements/{settlement_id}"
    )
    return "Settlement deleted."


# ---------------------------------------------------------------------------
# Invoice payment (single get)
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_invoice_payment(invoice_id: str, payment_id: str) -> dict:
    """Get a single payment record for an invoice."""
    return await _bokio().get(
        f"/companies/{_cid()}/invoices/{invoice_id}/payments/{payment_id}"
    )


# ---------------------------------------------------------------------------
# Record operations (trigger bookkeeping for unrecorded items)
# ---------------------------------------------------------------------------


@mcp.tool()
async def record_invoice(invoice_id: str) -> dict:
    """Record an invoice, triggering bookkeeping journal entry creation."""
    return await _bokio().post(f"/companies/{_cid()}/invoices/{invoice_id}/record")


@mcp.tool()
async def record_invoice_payment(invoice_id: str, payment_id: str) -> dict:
    """Record an invoice payment, triggering bookkeeping journal entry creation."""
    return await _bokio().post(
        f"/companies/{_cid()}/invoices/{invoice_id}/payments/{payment_id}/record"
    )


@mcp.tool()
async def record_invoice_settlement(invoice_id: str, settlement_id: str) -> dict:
    """Record an invoice settlement, triggering bookkeeping journal entry creation."""
    return await _bokio().post(
        f"/companies/{_cid()}/invoices/{invoice_id}/settlements/{settlement_id}/record"
    )


@mcp.tool()
async def record_credit_note(credit_note_id: str) -> dict:
    """Record a credit note, triggering bookkeeping journal entry creation."""
    return await _bokio().post(
        f"/companies/{_cid()}/credit-notes/{credit_note_id}/record"
    )


# ---------------------------------------------------------------------------
# Bank Payments
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_bank_payments(
    page: int = 1,
    page_size: int = 25,
    query: str | None = None,
) -> dict:
    """List bank payments created by this integration.

    The query parameter supports filtering on: amount, status, paymentDate,
    createdDateTime. Example: status==readyToSign
    """
    return await _bokio().get(
        f"/companies/{_cid()}/bank-payments",
        params=_params(page=page, pageSize=page_size, query=query),
    )


@mcp.tool()
async def get_bank_payment(bank_payment_id: str) -> dict:
    """Get a single bank payment by ID.

    Note: only returns bank payments that were created by this API integration,
    not all bank payments visible in the Bokio UI.
    """
    return await _bokio().get(f"/companies/{_cid()}/bank-payments/{bank_payment_id}")


@mcp.tool()
async def create_bank_payment(
    amount: float,
    payment_date: str,
    recipient_ref: dict,
    own_note: str | None = None,
) -> dict:
    """Create a bank payment.

    payment_date format: YYYY-MM-DD
    recipient_ref for account transfer:
      {"kind": "transfer", "recipientName": "...", "recipientReference": "...",
       "clearingNumber": "5011", "accountNumber": "0379101"}
    recipient_ref for bankgiro:
      {"kind": "bankgiro", "recipientName": "...", "bankgiroNumber": "123-4567",
       "ocr": "..."}
    """
    body: dict[str, Any] = {
        "amount": amount,
        "paymentDate": payment_date,
        "recipientRef": recipient_ref,
    }
    if own_note is not None:
        body["ownNote"] = own_note
    return await _bokio().post(f"/companies/{_cid()}/bank-payments", json=body)


# ---------------------------------------------------------------------------
# Chart of Accounts
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_chart_of_accounts(query: str | None = None) -> list:
    """Get the company's chart of accounts, merging bookkeeping accounts with their
    associated money account details.

    The query parameter supports filtering on: account, name, accountType.
    Example: account==1930
    Useful for finding the right account number when creating journal entries.
    """
    return await _bokio().get(
        f"/companies/{_cid()}/chart-of-accounts",
        params=_params(query=query),
    )


@mcp.tool()
async def get_account(account_number: int) -> dict:
    """Get details and current balance for a specific account by number.

    Useful for checking the balance of e.g. account 1930 (bank) before posting.
    """
    return await _bokio().get(
        f"/companies/{_cid()}/chart-of-accounts/{account_number}"
    )


# ---------------------------------------------------------------------------
# Company Information
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_company_information() -> dict:
    """Get information about the company (name, address, org number, VAT number, etc.)."""
    return await _bokio().get(f"/companies/{_cid()}/company-information")


# ---------------------------------------------------------------------------
# SIE Files
# ---------------------------------------------------------------------------


@mcp.tool()
async def download_sie_file(fiscal_year_id: str) -> dict:
    """Download the SIE accounting file for a fiscal year.

    Registers the file as an MCP resource and returns its resource URI. SIE is
    the standard Swedish accounting data exchange format, used for importing into
    accounting software.

    **IMPORTANT — character encoding:** SIE files are encoded in CP437 (DOS
    Code Page 437), NOT UTF-8. Decode the file with CP437 to avoid mangling
    Swedish characters (å, ä, ö etc.).
    """
    data, content_type = await _bokio().get_bytes(
        f"/companies/{_cid()}/sie/{fiscal_year_id}/download"
    )
    uri = f"bokio://sie/{fiscal_year_id}"
    _register_resource(uri, data, content_type, f"{fiscal_year_id}.sie")
    return {"resource_uri": uri, "content_type": content_type, "charset": "cp437"}


# ---------------------------------------------------------------------------
# Fiscal Years
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_fiscal_years(
    page: int = 1,
    page_size: int = 25,
    query: str | None = None,
) -> dict:
    """List fiscal years for the company.

    The query parameter supports filtering on: startDate, endDate,
    accountingMethod, status. Example: status==open
    """
    return await _bokio().get(
        f"/companies/{_cid()}/fiscal-years",
        params=_params(page=page, pageSize=page_size, query=query),
    )


@mcp.tool()
async def get_fiscal_year(fiscal_year_id: str) -> dict:
    """Get a single fiscal year by ID."""
    return await _bokio().get(f"/companies/{_cid()}/fiscal-years/{fiscal_year_id}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
