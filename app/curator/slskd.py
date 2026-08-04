from __future__ import annotations

import asyncio
from typing import Any

import httpx


class SlskdClient:
    def __init__(self, base_url: str, api_key: str = "", timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def health(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/v0/session", headers=self.headers)
            if response.status_code < 400:
                return True, "connected"
            return False, f"HTTP {response.status_code}"
        except Exception as exc:
            return False, str(exc)

    async def search(self, query: str, *, search_timeout: int, response_limit: int, file_limit: int,
                     minimum_upload_speed: int, maximum_queue_length: int) -> tuple[str, list[dict[str, Any]]]:
        payload = {
            "searchText": query,
            "searchTimeout": search_timeout,
            "responseLimit": response_limit,
            "fileLimit": file_limit,
            "minimumPeerUploadSpeed": minimum_upload_speed,
            "maximumPeerQueueLength": maximum_queue_length,
            "filterResponses": True,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v0/searches",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            search = response.json()
            search_id = search.get("id") or search.get("Id") or ""
            await asyncio.sleep(max(1, min(search_timeout, 20)))
            responses = await client.get(
                f"{self.base_url}/api/v0/searches/{search_id}/responses",
                headers=self.headers,
            )
            responses.raise_for_status()
            return str(search_id), responses.json() or []

    async def enqueue_batch(
        self,
        *,
        username: str,
        filename: str,
        size: int,
        destination: str,
        search_id: str = "",
        external_id: str = "",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "username": username,
            "files": [{"filename": filename, "size": size}],
            "options": {"destination": destination, "externalId": external_id},
        }
        if search_id:
            payload["searchId"] = search_id
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v0/transfers/downloads/batches",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json() if response.content else {}


class MockSlskdClient(SlskdClient):
    def __init__(self) -> None:
        super().__init__("mock://slskd")

    async def health(self) -> tuple[bool, str]:
        return True, "mock"

    async def search(self, query: str, **_: Any) -> tuple[str, list[dict[str, Any]]]:
        clean = query.replace("/", " ").strip()
        return "mock-search", [
            {
                "username": "demo-user",
                "hasFreeUploadSlot": True,
                "queueLength": 0,
                "uploadSpeed": 512,
                "files": [
                    {
                        "filename": f"Music/{clean}.flac",
                        "extension": "flac",
                        "size": 32100000,
                        "bitRate": None,
                        "length": 240,
                    },
                    {
                        "filename": f"Music/{clean}.mp3",
                        "extension": "mp3",
                        "size": 9000000,
                        "bitRate": 320,
                        "length": 240,
                    },
                ],
            }
        ]

    async def enqueue_batch(self, **kwargs: Any) -> dict[str, Any]:
        return {"batch": {"id": "mock-batch"}, "failures": []}

