import httpx
import pytest

from bokio_mcp import server
from bokio_mcp.client import BokioError

from .conftest import COMPANY_ID, api

ITEM_ID = "835ba700-b306-4bd9-8447-59207b6b0002"

ITEM = {
    "id": ITEM_ID,
    "description": "Widget Pro",
    "itemType": "salesItem",
    "productType": "goods",
    "unitType": "piece",
    "unitPrice": 100.0,
    "taxRate": 25,
}


async def test_create_item(mock_api):
    mock_api.post(api(f"/companies/{COMPANY_ID}/items")).mock(
        return_value=httpx.Response(200, json=ITEM)
    )

    result = await server.create_item(
        description="Widget Pro",
        item_type="salesItem",
        unit_price=100.0,
        product_type="goods",
        unit_type="piece",
        tax_rate=25,
        
    )

    assert result["id"] == ITEM_ID
    assert result["taxRate"] == 25


async def test_list_items(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [ITEM]}
    mock_api.get(api(f"/companies/{COMPANY_ID}/items")).mock(
        return_value=httpx.Response(200, json=page)
    )

    result = await server.list_items()

    assert result["items"][0]["id"] == ITEM_ID


async def test_list_items_filtered(mock_api):
    page = {"totalItems": 1, "totalPages": 1, "currentPage": 1, "items": [ITEM]}
    route = mock_api.get(api(f"/companies/{COMPANY_ID}/items")).mock(
        return_value=httpx.Response(200, json=page)
    )

    await server.list_items(query="itemType==salesItem")

    assert route.calls.last.request.url.params["query"] == "itemType==salesItem"


async def test_get_item(mock_api):
    mock_api.get(api(f"/companies/{COMPANY_ID}/items/{ITEM_ID}")).mock(
        return_value=httpx.Response(200, json=ITEM)
    )

    result = await server.get_item(item_id=ITEM_ID)

    assert result["description"] == "Widget Pro"


async def test_update_item(mock_api):
    updated = {**ITEM, "unitPrice": 120.0}
    mock_api.put(api(f"/companies/{COMPANY_ID}/items/{ITEM_ID}")).mock(
        return_value=httpx.Response(200, json=updated)
    )

    result = await server.update_item(
        item_id=ITEM_ID,
        description="Widget Pro",
        item_type="salesItem",
        unit_price=120.0,
        tax_rate=25,
        
    )

    assert result["unitPrice"] == 120.0


async def test_delete_item(mock_api):
    mock_api.delete(api(f"/companies/{COMPANY_ID}/items/{ITEM_ID}")).mock(
        return_value=httpx.Response(204)
    )

    result = await server.delete_item(item_id=ITEM_ID)

    assert "deleted" in result.lower()


async def test_get_item_not_found(mock_api):
    mock_api.get(api(f"/companies/{COMPANY_ID}/items/{ITEM_ID}")).mock(
        return_value=httpx.Response(
            404, json={"code": "not-found", "message": "Item not found"}
        )
    )

    with pytest.raises(BokioError) as exc_info:
        await server.get_item(item_id=ITEM_ID)

    assert exc_info.value.status_code == 404


async def test_create_item_invalid_tax_rate(mock_api):
    mock_api.post(api(f"/companies/{COMPANY_ID}/items")).mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "validation-error",
                "message": "Validation failed with 1 error",
                "errors": [
                    {
                        "field": "#/taxRate",
                        "message": "Invalid tax rate. Must be one of: 0%, 6%, 12%, 25%",
                    }
                ],
            },
        )
    )

    with pytest.raises(BokioError) as exc_info:
        await server.create_item(
            description="Bad Item",
            item_type="salesItem",
            unit_price=50.0,
            tax_rate=15,  # not a valid Swedish VAT rate
            
        )

    assert exc_info.value.status_code == 400
