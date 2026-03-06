from typing import Any

import httpx

from .settings import settings


class BokioError(Exception):
    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self.body = body
        code = body.get("code", "") if isinstance(body, dict) else ""
        message = body.get("message", str(body)) if isinstance(body, dict) else str(body)
        super().__init__(f"HTTP {status_code} [{code}]: {message}")


class BokioClient:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            base_url=settings.base_url,
            headers={
                "Authorization": f"Bearer {settings.api_token}",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    async def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_error:
            try:
                body = response.json()
            except Exception:
                body = response.text
            raise BokioError(response.status_code, body)

    async def get(self, path: str, params: dict | None = None) -> Any:
        response = await self._http.get(path, params=params)
        await self._raise_for_status(response)
        return response.json()

    async def post(self, path: str, json: Any = None) -> Any:
        response = await self._http.post(path, json=json)
        await self._raise_for_status(response)
        if response.status_code == 204:
            return None
        return response.json()

    async def put(self, path: str, json: Any = None) -> Any:
        response = await self._http.put(path, json=json)
        await self._raise_for_status(response)
        return response.json()

    async def delete(self, path: str) -> None:
        response = await self._http.delete(path)
        await self._raise_for_status(response)

    async def post_multipart(self, path: str, file_bytes: bytes, filename: str, content_type: str, fields: dict | None = None) -> Any:
        """Upload a file via multipart/form-data."""
        files = {"file": (filename, file_bytes, content_type)}
        data = {k: v for k, v in (fields or {}).items() if v is not None}
        response = await self._http.post(path, files=files, data=data)
        await self._raise_for_status(response)
        return response.json()

    async def get_bytes(self, path: str) -> tuple[bytes, str]:
        """Download binary content. Returns (data, content_type)."""
        response = await self._http.get(path)
        await self._raise_for_status(response)
        return response.content, response.headers.get("content-type", "application/octet-stream")

    async def aclose(self) -> None:
        await self._http.aclose()


client = BokioClient()
