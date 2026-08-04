from __future__ import annotations

import asyncio
from typing import Any

import httpx


def search_timeout_milliseconds(seconds: int) -> int:
    return max(1, int(seconds)) * 1000


class SlskdClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        username: str = "",
        password: str = "",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.username = username
        self.password = password
        self.timeout = timeout
        self._bearer_token = ""

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        return headers

    async def ensure_auth(self) -> None:
        if self.api_key or self._bearer_token or not (self.username and self.password):
            return
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v0/session",
                headers={"Accept": "application/json"},
                json={"username": self.username, "password": self.password},
            )
            response.raise_for_status()
            payload = response.json()
            self._bearer_token = payload.get("accessToken") or payload.get("token") or ""

    async def health(self) -> tuple[bool, str]:
        try:
            await self.ensure_auth()
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/v0/session", headers=self.headers)
            if response.status_code < 400:
                return True, "connected"
            return False, f"HTTP {response.status_code}"
        except Exception as exc:
            return False, str(exc)

    async def search(self, query: str, *, search_timeout: int, response_limit: int, file_limit: int,
                     minimum_upload_speed: int, maximum_queue_length: int) -> tuple[str, list[dict[str, Any]]]:
        search_id = await self.start_search(
            query,
            search_timeout=search_timeout,
            response_limit=response_limit,
            file_limit=file_limit,
            minimum_upload_speed=minimum_upload_speed,
            maximum_queue_length=maximum_queue_length,
        )
        await asyncio.sleep(max(1, min(search_timeout, 20)))
        responses = await self.search_responses(search_id)
        return search_id, responses

    async def start_search(
        self,
        query: str,
        *,
        search_timeout: int,
        response_limit: int,
        file_limit: int,
        minimum_upload_speed: int,
        maximum_queue_length: int,
    ) -> str:
        await self.ensure_auth()
        payload = {
            "searchText": query,
            "searchTimeout": search_timeout_milliseconds(search_timeout),
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
            return str(search.get("id") or search.get("Id") or "")

    async def search_responses(self, search_id: str) -> list[dict[str, Any]]:
        await self.ensure_auth()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            responses = await client.get(
                f"{self.base_url}/api/v0/searches/{search_id}/responses",
                headers=self.headers,
            )
            responses.raise_for_status()
            return responses.json() or []

    async def stop_search(self, search_id: str) -> bool:
        if not search_id:
            return False
        await self.ensure_auth()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.put(
                f"{self.base_url}/api/v0/searches/{search_id}",
                headers=self.headers,
            )
            if response.status_code == 404:
                return False
            response.raise_for_status()
            return True

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
        await self.ensure_auth()
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

    async def start_search(self, query: str, **_: Any) -> str:
        return f"mock-search-{query.replace(' ', '-').lower()}"

    async def search_responses(self, search_id: str) -> list[dict[str, Any]]:
        clean = search_id.replace("mock-search-", "").replace("-", " ")
        _, responses = await self.search(clean)
        return responses

    async def stop_search(self, search_id: str) -> bool:
        return bool(search_id)

    async def enqueue_batch(self, **kwargs: Any) -> dict[str, Any]:
        return {"batch": {"id": "mock-batch"}, "failures": []}
