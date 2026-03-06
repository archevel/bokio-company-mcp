import os

# Must be set before bokio_mcp is imported, so the pydantic-settings singleton
# can be initialised without a real .env file.
os.environ.setdefault("BOKIO_API_TOKEN", "test-token")
os.environ.setdefault("BOKIO_BASE_URL", "https://test.bokio.localhost/v1")
os.environ.setdefault("BOKIO_COMPANY_ID", "ea9ee4dd-fae3-4aec-a7db-6fc9cc1f8135")

import pytest
import respx

from bokio_mcp import server
from bokio_mcp.client import BokioClient

COMPANY_ID = "ea9ee4dd-fae3-4aec-a7db-6fc9cc1f8135"
BASE_URL = "https://test.bokio.localhost/v1"


@pytest.fixture()
def bokio_client(monkeypatch):
    """Create a real BokioClient and inject it so all server tools use it."""
    client = BokioClient()
    monkeypatch.setattr(server, "_bokio", lambda: client)
    return client


@pytest.fixture()
def mock_api(bokio_client):
    """respx router that intercepts all httpx traffic; auto-injected client included."""
    with respx.mock(assert_all_called=False) as router:
        yield router


def api(path: str) -> str:
    return f"{BASE_URL}{path}"
