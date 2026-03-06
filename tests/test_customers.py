import httpx
import pytest

from bokio_mcp import server
from bokio_mcp.client import BokioError

from .conftest import COMPANY_ID, api

CUSTOMER_ID = "55c899c5-82b2-47fa-9c51-e35fc9b26443"

CUSTOMER = {
    "id": CUSTOMER_ID,
    "name": "Acme Corp",
    "type": "company",
    "vatNumber": "SE1234567890",
    "orgNumber": "123456-7890",
    "paymentTerms": "30",
    "contactsDetails": [
        {
            "id": "240a4af0-edfd-47b1-b4ab-f30450eaac19",
            "name": "John Doe",
            "email": "john@acme.com",
            "phone": "0927-5631505",
            "isDefault": True,
        }
    ],
    "address": {
        "line1": "Älvsborgsvägen 10",
        "line2": None,
        "city": "Göteborg",
        "postalCode": "123 45",
        "country": "SE",
    },
    "language": "sv",
    "modifiedDateTime": "2024-10-10T00:00:00Z",
}


async def test_create_customer(mock_api):
    mock_api.post(api(f"/companies/{COMPANY_ID}/customers")).mock(
        return_value=httpx.Response(200, json=CUSTOMER)
    )

    result = await server.create_customer(
        name="Acme Corp",
        type="company",
        
        vat_number="SE1234567890",
        org_number="123456-7890",
        payment_terms="30",
        language="sv",
        address={
            "line1": "Älvsborgsvägen 10",
            "city": "Göteborg",
            "postalCode": "123 45",
            "country": "SE",
        },
        contacts_details=[
            {"name": "John Doe", "email": "john@acme.com", "isDefault": True}
        ],
    )

    assert result["id"] == CUSTOMER_ID
    assert result["name"] == "Acme Corp"


async def test_list_customers(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [CUSTOMER]}
    mock_api.get(api(f"/companies/{COMPANY_ID}/customers")).mock(
        return_value=httpx.Response(200, json=page)
    )

    result = await server.list_customers()

    assert result["totalItems"] == 1
    assert result["items"][0]["name"] == "Acme Corp"


async def test_list_customers_with_query(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [CUSTOMER]}
    route = mock_api.get(api(f"/companies/{COMPANY_ID}/customers")).mock(
        return_value=httpx.Response(200, json=page)
    )

    await server.list_customers(query="name==Acme Corp")

    assert route.calls.last.request.url.params["query"] == "name==Acme Corp"


async def test_get_customer(mock_api):
    mock_api.get(api(f"/companies/{COMPANY_ID}/customers/{CUSTOMER_ID}")).mock(
        return_value=httpx.Response(200, json=CUSTOMER)
    )

    result = await server.get_customer(customer_id=CUSTOMER_ID)

    assert result["id"] == CUSTOMER_ID


async def test_update_customer(mock_api):
    updated = {**CUSTOMER, "name": "Acme Corp Updated", "paymentTerms": "60"}
    mock_api.put(api(f"/companies/{COMPANY_ID}/customers/{CUSTOMER_ID}")).mock(
        return_value=httpx.Response(200, json=updated)
    )

    result = await server.update_customer(
        customer_id=CUSTOMER_ID,
        name="Acme Corp Updated",
        type="company",
        payment_terms="60",
        
    )

    assert result["name"] == "Acme Corp Updated"
    assert result["paymentTerms"] == "60"


async def test_delete_customer(mock_api):
    mock_api.delete(api(f"/companies/{COMPANY_ID}/customers/{CUSTOMER_ID}")).mock(
        return_value=httpx.Response(204)
    )

    result = await server.delete_customer(
        customer_id=CUSTOMER_ID
    )

    assert "deleted" in result.lower()


async def test_get_customer_not_found(mock_api):
    mock_api.get(api(f"/companies/{COMPANY_ID}/customers/{CUSTOMER_ID}")).mock(
        return_value=httpx.Response(
            404, json={"code": "not-found", "message": "Customer not found"}
        )
    )

    with pytest.raises(BokioError) as exc_info:
        await server.get_customer(customer_id=CUSTOMER_ID)

    assert exc_info.value.status_code == 404


async def test_create_customer_validation_error(mock_api):
    mock_api.post(api(f"/companies/{COMPANY_ID}/customers")).mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "validation-error",
                "message": "Validation failed with 2 errors",
                "errors": [
                    {"field": "#/name", "message": "The name field is required"},
                    {"field": "#/address/country", "message": "Invalid country code: XX"},
                ],
            },
        )
    )

    with pytest.raises(BokioError) as exc_info:
        await server.create_customer(name="", type="company")

    assert exc_info.value.status_code == 400


async def test_create_customer_minimal_fields(mock_api):
    """Agent should be able to create a customer with just required fields."""
    minimal = {"id": CUSTOMER_ID, "name": "Minimal Co", "type": "company"}
    mock_api.post(api(f"/companies/{COMPANY_ID}/customers")).mock(
        return_value=httpx.Response(200, json=minimal)
    )

    result = await server.create_customer(
        name="Minimal Co", type="company"
    )

    assert result["name"] == "Minimal Co"
    # Optional fields should not have been sent — verify request body
    request_body = mock_api.calls.last.request.content
    assert b"vatNumber" not in request_body
    assert b"address" not in request_body
