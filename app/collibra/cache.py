import asyncio
import logging
from collections import defaultdict

from app.collibra.client import CollibraClient, strip_html
from app.collibra.models import CollibraAsset, CollibraRelation, PhysicalColumn

logger = logging.getLogger(__name__)

DOMAIN_IDS = {
    "glossary": "019c907a-40d8-74d9-84c5-83abd6ae4d4e",
    "metrics_catalog": "019c9f76-2a44-7242-8f7d-cf40e16f270b",
    "logical_layer": "019c9e6d-9079-72e3-b0f9-e64c49a57ac9",
    "physical_layer": "019c9e17-b6f2-725e-9181-dbda44044df9",
}

# Concurrency limit for attribute/relation fetches
_SEM_LIMIT = 15


class CollibraCache:
    def __init__(self):
        self.assets: dict[str, CollibraAsset] = {}
        self.assets_by_name: dict[str, list[str]] = defaultdict(list)
        self.relations: list[CollibraRelation] = []
        self.relations_by_source: dict[str, list[CollibraRelation]] = defaultdict(list)
        self.relations_by_target: dict[str, list[CollibraRelation]] = defaultdict(list)
        self.physical_schema: dict[str, list[PhysicalColumn]] = defaultdict(list)

    async def build(self, client: CollibraClient) -> None:
        logger.info("Building Collibra cache — fetching assets from all domains...")
        sem = asyncio.Semaphore(_SEM_LIMIT)

        # 1. Fetch all assets from all 4 domains
        all_raw_assets: list[dict] = []
        for domain_name, domain_id in DOMAIN_IDS.items():
            logger.info("  Fetching assets from domain: %s", domain_name)
            raw = await client.list_assets(domain_id)
            logger.info("  -> %d assets", len(raw))
            all_raw_assets.extend(raw)

        logger.info("Total raw assets: %d — fetching attributes...", len(all_raw_assets))

        # 2. Fetch attributes concurrently (with semaphore)
        async def fetch_attrs(raw: dict) -> CollibraAsset:
            async with sem:
                asset_id = raw["id"]
                attrs = await client.get_attributes(asset_id)
                definition = ""
                description = ""
                synonyms = []
                for attr in attrs:
                    type_name = attr.get("type", {}).get("name", "")
                    value = strip_html(attr.get("value", ""))
                    if type_name == "Definition":
                        definition = value
                    elif type_name == "Description":
                        description = value
                    elif type_name in ("Synonym", "Abbreviation"):
                        if value:
                            synonyms.append(value)
                return CollibraAsset(
                    id=asset_id,
                    name=raw.get("name", ""),
                    display_name=raw.get("displayName", raw.get("name", "")),
                    domain_id=raw.get("domain", {}).get("id", ""),
                    domain_name=raw.get("domain", {}).get("name", ""),
                    type_name=raw.get("type", {}).get("name", ""),
                    status=raw.get("status", {}).get("name", "") if raw.get("status") else "",
                    definition=definition,
                    description=description,
                    synonyms=synonyms,
                )

        assets_list = await asyncio.gather(*[fetch_attrs(r) for r in all_raw_assets])

        for asset in assets_list:
            self.assets[asset.id] = asset
            self.assets_by_name[asset.name.lower()].append(asset.id)
            if asset.display_name and asset.display_name.lower() != asset.name.lower():
                self.assets_by_name[asset.display_name.lower()].append(asset.id)

        logger.info("Assets cached: %d — fetching relations...", len(self.assets))

        # 3. Fetch relations for all assets (source + target)
        seen_relation_ids: set[str] = set()

        async def fetch_rels(asset_id: str) -> list[CollibraRelation]:
            async with sem:
                out = []
                for batch in [
                    await client.get_relations_by_source(asset_id),
                    await client.get_relations_by_target(asset_id),
                ]:
                    for r in batch:
                        rid = r.get("id", "")
                        if rid in seen_relation_ids:
                            continue
                        seen_relation_ids.add(rid)
                        out.append(
                            CollibraRelation(
                                id=rid,
                                source_id=r.get("source", {}).get("id", ""),
                                source_name=r.get("source", {}).get("name", ""),
                                source_domain_name=r.get("source", {}).get("domain", {}).get("name", ""),
                                target_id=r.get("target", {}).get("id", ""),
                                target_name=r.get("target", {}).get("name", ""),
                                target_domain_name=r.get("target", {}).get("domain", {}).get("name", ""),
                                type_name=r.get("type", {}).get("name", ""),
                            )
                        )
                return out

        rel_batches = await asyncio.gather(*[fetch_rels(aid) for aid in self.assets])
        for batch in rel_batches:
            for rel in batch:
                self.relations.append(rel)
                self.relations_by_source[rel.source_id].append(rel)
                self.relations_by_target[rel.target_id].append(rel)

        logger.info("Relations cached: %d", len(self.relations))

        # 4. Build physical schema
        self._build_physical_schema()
        logger.info("Physical schema built: %d tables", len(self.physical_schema))

    def _build_physical_schema(self) -> None:
        """
        Reconstruct table→column hierarchy from physical layer assets and their relations.
        Column assets: type_name == "Column"
        Table assets: type_name == "Table"
        Relation: table (source) → column (target), or column (target) → table (source)
        """
        physical_domain_id = DOMAIN_IDS["physical_layer"]

        columns = {
            aid: a
            for aid, a in self.assets.items()
            if a.domain_id == physical_domain_id and a.type_name == "Column"
        }
        tables = {
            aid: a
            for aid, a in self.assets.items()
            if a.domain_id == physical_domain_id and a.type_name == "Table"
        }

        # Build column → table mapping via relations
        col_to_table: dict[str, str] = {}
        for table_id, table_asset in tables.items():
            for rel in self.relations_by_source.get(table_id, []):
                if rel.target_id in columns:
                    col_to_table[rel.target_id] = table_asset.name
            for rel in self.relations_by_target.get(table_id, []):
                if rel.source_id in columns:
                    col_to_table[rel.source_id] = table_asset.name

        for col_id, col_asset in columns.items():
            table_name = col_to_table.get(col_id, "unknown")
            # Use description, fall back to definition
            desc = col_asset.description or col_asset.definition
            self.physical_schema[table_name].append(
                PhysicalColumn(
                    asset_id=col_id,
                    table_name=table_name,
                    column_name=col_asset.name,
                    description=desc,
                )
            )
