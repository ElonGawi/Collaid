# Collaid — AI-Powered Data Governance Query Engine

Collaid is an intelligent data query system that bridges business glossaries with physical databases. It lets users ask data questions in business terms rather than SQL, leveraging AI agents and data governance metadata to discover, understand, and query data safely.

## Overview

Collaid integrates:
- **Collibra** data governance platform for business term definitions and data lineage
- **Databricks Delta Sharing** for secure data access
- **DuckDB** for in-memory SQL execution
- **Claude AI** agent for natural language understanding and query generation

### Key Features

- **Business Glossary Search**: Find governed business terms, metrics, and data entities
- **Data Lineage Tracing**: Follow relations from business terms → logical layer → physical columns
- **Schema Discovery**: View physical database schemas with Collibra-governed descriptions
- **Natural Language Queries**: Ask questions in plain English; the agent translates them to SQL
- **Secure Query Execution**: SQL is validated and executed against an in-memory DuckDB instance

## Project Structure

```
app/
├── agent/           # AI agent tools and dispatch logic
├── collibra/        # Collibra API integration and data models
├── data/            # Data loading and database engine
│   ├── delta_loader.py      # Loads data from Databricks Delta Sharing
│   └── duckdb_engine.py     # In-memory SQL execution with query validation
└── api/             # REST API endpoints
```

## Getting Started

### Prerequisites

- Python 3.10+
- Access to a Databricks workspace with Delta Sharing enabled
- Access to a Collibra instance
- Environment with `pandas`, `delta-sharing`, `duckdb`, and Claude SDK packages

### Installation

1. Clone the repository
2. Create a Python virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Configuration

**⚠️ IMPORTANT: Do NOT commit credentials to version control.**

Create a `config.json` file in the project root (add to `.gitignore`):

```json
{
  "shareCredentialsVersion": 1,
  "bearerToken": "<your-databricks-bearer-token>",
  "endpoint": "<your-delta-sharing-endpoint>",
  "expirationTime": "<token-expiration-date>"
}
```

Alternatively, set environment variables:
- `DATABRICKS_BEARER_TOKEN`
- `DATABRICKS_ENDPOINT`

## Usage

### Loading Data

The `delta_loader.py` module loads Centercode project data from Databricks:

```python
from app.data.delta_loader import load_all_tables

tables = await load_all_tables("config.json", limit=1000)
```

Available tables:
- `zcc_act_stat` — Activity status
- `zcc_knt_mstr` — Contact master
- `zcc_prj_hdr` — Project header
- `zcc_prt_mtrc` — Port metrics
- `zcc_ptm_lnk` — Project/test item links
- `zcc_qa_sat` — QA satisfaction
- `zcc_tkt_itm` — Ticket items
- `zcc_usr_mstr` — User master

### Agent Tools

The AI agent has access to these tools:

- **`search_business_terms(query)`** — Search for governed definitions
- **`get_asset_definition(asset_id)`** — Fetch full asset metadata
- **`get_asset_relations(asset_id)`** — Trace data lineage
- **`get_physical_schema()`** — View all tables and columns
- **`execute_sql(sql)`** — Run DuckDB queries (with safety validation)

### Example Workflow

```python
from app.agent.tools import dispatch_tool
from app.collibra.cache import CollibraCache
from app.data.duckdb_engine import DuckDBEngine

# Search for a business term
result = await dispatch_tool(
    "search_business_terms",
    {"query": "active tester"},
    cache,
    engine
)

# Get the definition
result = await dispatch_tool(
    "get_asset_definition",
    {"asset_id": result["results"][0]["id"]},
    cache,
    engine
)

# Execute a SQL query
result = await dispatch_tool(
    "execute_sql",
    {"sql": "SELECT COUNT(*) FROM zcc_usr_mstr"},
    cache,
    engine
)
```

## Safety & Validation

- SQL queries are validated to prevent dangerous operations (DROP, DELETE, INSERT, UPDATE, etc.)
- Queries execute against an **in-memory DuckDB instance only** — no changes to production data
- Collibra asset lookups ensure queries are semantically aligned with governed definitions

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

This project follows PEP 8. Use:
```bash
black app/
flake8 app/
```

## Security Considerations

- **Never commit `config.json`** — it contains authentication tokens
- Add `config.json` to `.gitignore`
- Bearer tokens should be rotated regularly
- Only share DuckDB connection with trusted components
- SQL validation prevents but does not guarantee all injection attacks

## Authors

Team 30 — NextChallenge 2026

---

**Note**: This project was developed as part of the NextChallenge 2026 competition. It demonstrates integration of AI agents, data governance, and secure query execution.
