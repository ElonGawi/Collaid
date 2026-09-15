import json
import logging
from typing import Any

from app.collibra.cache import CollibraCache
from app.data.duckdb_engine import DuckDBEngine

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "name": "search_business_terms",
        "description": (
            "Search the Collibra business glossary and metrics catalog for governed business terms, "
            "metrics, data entities, or data attributes matching a query. "
            "Returns up to 10 matching assets with their IDs, names, type, and domain. "
            "Use this to discover governed definitions before writing SQL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Plain-English search term, e.g. 'active tester' or 'satisfaction score'",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_asset_definition",
        "description": (
            "Fetch the full governed definition, description, and synonyms for a specific Collibra asset by ID. "
            "Call this after search_business_terms to get precise business meaning."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_id": {
                    "type": "string",
                    "description": "The Collibra asset UUID returned by search_business_terms",
                }
            },
            "required": ["asset_id"],
        },
    },
    {
        "name": "get_asset_relations",
        "description": (
            "Get all inbound and outbound semantic relations for a Collibra asset. "
            "Use this to trace from Business Term → Logical Data Attribute → Physical Column. "
            "The domain names on each side reveal which layer the relation crosses."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_id": {
                    "type": "string",
                    "description": "The Collibra asset UUID",
                }
            },
            "required": ["asset_id"],
        },
    },
    {
        "name": "get_physical_schema",
        "description": (
            "Return the complete physical database schema: all tables with their columns and "
            "Collibra-governed descriptions. Call this first to understand what data is available "
            "and what cryptic column names (like Z_ENG_ST) actually mean."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "execute_sql",
        "description": (
            "Execute a SQL query against the DuckDB in-memory database containing all 8 Centercode tables. "
            "Returns column names, rows (max 500), and total row count. "
            "Available tables: zcc_act_stat, zcc_knt_mstr, zcc_prj_hdr, zcc_prt_mtrc, "
            "zcc_ptm_lnk, zcc_qa_sat, zcc_tkt_itm, zcc_usr_mstr"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Valid DuckDB SQL query using only verified column names",
                }
            },
            "required": ["sql"],
        },
    },
]


def _search_business_terms(query: str, cache: CollibraCache) -> dict:
    query_tokens = set(query.lower().split())
    scores: list[tuple[float, str]] = []

    for asset_id, asset in cache.assets.items():
        name_tokens = set(asset.name.lower().split())
        # Score: token overlap on name (weighted 2x) + token overlap in definition
        name_overlap = len(query_tokens & name_tokens)
        # Also check if query appears as substring in the name
        substring_bonus = 2 if query.lower() in asset.name.lower() else 0
        definition_overlap = sum(
            1 for t in query_tokens if t in asset.definition.lower()
        ) if asset.definition else 0
        score = name_overlap * 2 + substring_bonus + definition_overlap * 0.5
        if score > 0:
            scores.append((score, asset_id))

    scores.sort(key=lambda x: x[0], reverse=True)
    top = scores[:10]

    results = []
    for score, asset_id in top:
        a = cache.assets[asset_id]
        results.append({
            "id": a.id,
            "name": a.display_name or a.name,
            "type": a.type_name,
            "domain": a.domain_name,
            "status": a.status,
            "definition_preview": a.definition[:200] if a.definition else "(no definition)",
        })

    return {
        "query": query,
        "count": len(results),
        "results": results,
    }


def _get_asset_definition(asset_id: str, cache: CollibraCache) -> dict:
    asset = cache.assets.get(asset_id)
    if not asset:
        return {"error": f"Asset {asset_id} not found in cache"}
    return {
        "id": asset.id,
        "name": asset.display_name or asset.name,
        "type": asset.type_name,
        "domain": asset.domain_name,
        "status": asset.status,
        "definition": asset.definition or "(no governed definition)",
        "description": asset.description or "(no description)",
        "synonyms": asset.synonyms,
    }


def _get_asset_relations(asset_id: str, cache: CollibraCache) -> dict:
    asset = cache.assets.get(asset_id)
    asset_name = asset.name if asset else asset_id

    def enrich(rel, direction: str) -> dict:
        related_id = rel.target_id if direction == "outbound" else rel.source_id
        related_name = rel.target_name if direction == "outbound" else rel.source_name
        related_domain = rel.target_domain_name if direction == "outbound" else rel.source_domain_name
        related_asset = cache.assets.get(related_id)
        return {
            "related_asset_id": related_id,
            "related_asset_name": related_name,
            "related_asset_type": related_asset.type_name if related_asset else "unknown",
            "related_asset_domain": related_domain,
            "relation_type": rel.type_name or "(untyped)",
        }

    outbound = [enrich(r, "outbound") for r in cache.relations_by_source.get(asset_id, [])]
    inbound = [enrich(r, "inbound") for r in cache.relations_by_target.get(asset_id, [])]

    return {
        "asset_id": asset_id,
        "asset_name": asset_name,
        "outbound_relations": outbound,
        "inbound_relations": inbound,
        "tip": (
            "Outbound = this asset points to others. "
            "Inbound = other assets point to this one. "
            "Follow domain names to trace: Glossary → Logical Layer → Physical Data Layer"
        ),
    }


def _get_physical_schema(cache: CollibraCache) -> dict:
    schema: dict[str, Any] = {}
    for table_name, columns in cache.physical_schema.items():
        schema[table_name] = [
            {
                "column": col.column_name,
                "description": col.description or "(no description)",
                "collibra_asset_id": col.asset_id,
            }
            for col in sorted(columns, key=lambda c: c.column_name)
        ]
    return {
        "tables": schema,
        "table_count": len(schema),
        "note": "These are all physically governed columns. Column names are cryptic — use descriptions to understand their meaning.",
    }


async def dispatch_tool(
    tool_name: str,
    tool_input: dict,
    cache: CollibraCache,
    engine: DuckDBEngine,
) -> dict:
    logger.debug("Tool call: %s(%s)", tool_name, json.dumps(tool_input)[:200])
    match tool_name:
        case "search_business_terms":
            return _search_business_terms(tool_input["query"], cache)
        case "get_asset_definition":
            return _get_asset_definition(tool_input["asset_id"], cache)
        case "get_asset_relations":
            return _get_asset_relations(tool_input["asset_id"], cache)
        case "get_physical_schema":
            return _get_physical_schema(cache)
        case "execute_sql":
            return engine.execute_query(tool_input["sql"])
        case _:
            return {"error": f"Unknown tool: {tool_name}"}
