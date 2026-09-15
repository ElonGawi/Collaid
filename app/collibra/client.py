import asyncio
import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger(__name__)


def strip_html(value) -> str:
    if value is None:
        return ""
    text = str(value) if not isinstance(value, str) else value
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return re.sub(r"\s+", " ", soup.get_text()).strip()


class CollibraClient:
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=settings.collibra_base_url,
            auth=(settings.collibra_username, settings.collibra_password),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )

    async def close(self):
        await self._client.aclose()

    async def _get(self, path: str, params: dict | None = None) -> dict:
        resp = await self._client.get(path, params=params or {})
        resp.raise_for_status()
        return resp.json()

    async def list_assets(self, domain_id: str) -> list[dict]:
        """Paginate through all assets in a domain."""
        results = []
        offset = 0
        limit = 500
        while True:
            data = await self._get(
                "/assets",
                params={
                    "domainId": domain_id,
                    "offset": offset,
                    "limit": limit,
                    "sortField": "NAME",
                    "sortOrder": "ASC",
                    "excludeMeta": "true",
                },
            )
            batch = data.get("results", [])
            results.extend(batch)
            total = data.get("total", 0)
            offset += limit
            if offset >= total or not batch:
                break
            await asyncio.sleep(0.05)  # gentle rate limiting
        return results

    async def get_attributes(self, asset_id: str) -> list[dict]:
        """Fetch all attributes for an asset (definition, description, synonyms)."""
        try:
            data = await self._get("/attributes", params={"assetId": asset_id, "limit": 200})
            return data.get("results", [])
        except httpx.HTTPStatusError as e:
            logger.warning("Failed to fetch attributes for %s: %s", asset_id, e)
            return []

    async def get_relations_by_source(self, asset_id: str) -> list[dict]:
        try:
            data = await self._get("/relations", params={"sourceId": asset_id, "limit": 200})
            return data.get("results", [])
        except httpx.HTTPStatusError as e:
            logger.warning("Failed to fetch relations (source) for %s: %s", asset_id, e)
            return []

    async def get_relations_by_target(self, asset_id: str) -> list[dict]:
        try:
            data = await self._get("/relations", params={"targetId": asset_id, "limit": 200})
            return data.get("results", [])
        except httpx.HTTPStatusError as e:
            logger.warning("Failed to fetch relations (target) for %s: %s", asset_id, e)
            return []
