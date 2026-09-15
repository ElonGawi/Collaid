"""
Quick connectivity check for Collibra and Delta Sharing.
Run before starting the server:
    python scripts/verify_connections.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import delta_sharing
from app.config import settings


async def check_collibra():
    print("\n[1/2] Checking Collibra connectivity...")
    glossary_domain = "019c907a-40d8-74d9-84c5-83abd6ae4d4e"
    async with httpx.AsyncClient(
        auth=(settings.collibra_username, settings.collibra_password),
        timeout=10,
    ) as client:
        resp = await client.get(f"{settings.collibra_base_url}/domains/{glossary_domain}")
        resp.raise_for_status()
        data = resp.json()
        print(f"  OK — domain: {data['name']}")
        # Count assets
        resp2 = await client.get(
            f"{settings.collibra_base_url}/assets",
            params={"domainId": glossary_domain, "limit": 1},
        )
        total = resp2.json().get("total", "?")
        print(f"  OK — Glossary has {total} assets")


def check_delta_sharing():
    print("\n[2/2] Checking Delta Sharing connectivity...")
    client = delta_sharing.SharingClient(settings.delta_sharing_config_path)
    tables = client.list_all_tables()
    print(f"  OK — {len(tables)} tables available:")
    for t in tables:
        print(f"       {t.share}.{t.schema}.{t.name}")


async def main():
    print("=" * 50)
    print("Ask Your Data — Connection Verification")
    print("=" * 50)
    try:
        await check_collibra()
    except Exception as e:
        print(f"  FAIL — Collibra: {e}")

    try:
        check_delta_sharing()
    except Exception as e:
        print(f"  FAIL — Delta Sharing: {e}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
