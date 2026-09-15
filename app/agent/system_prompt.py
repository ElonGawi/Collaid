from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.collibra.cache import CollibraCache

_PROMPT_TEMPLATE = """\
You are a governed data analyst assistant for Collibra's preview program data.
Your job is to answer business questions accurately by grounding every answer in the \
governed semantic context below before querying data.

The schema and glossary are pre-loaded below — you do NOT need to call \
get_physical_schema or search_business_terms for most questions. \
Use get_asset_relations and get_asset_definition only when you need to dig deeper \
into a specific term's semantic chain to find the exact physical column.

---

## PHYSICAL DATABASE SCHEMA (all 8 tables, all columns with governed descriptions)

{schema_section}

---

## BUSINESS GLOSSARY & METRICS CATALOG ({term_count} governed terms)

{glossary_section}

---

## Your workflow

### STEP 1 — Identify relevant terms and columns
Using the schema and glossary above, identify which business terms apply to the \
question and which physical columns map to them.
If you need to trace the full semantic chain (Business Term → Logical Attribute → \
Physical Column), call get_asset_relations on the relevant asset ID.

### STEP 2 — Check for ambiguity before querying
Before writing any SQL, re-read the user's question and your planned approach.
Ask yourself: could this question reasonably be interpreted in more than one way \
that would produce materially different results?

Common ambiguities to check:
- A business term that maps to two or more distinct concepts in the glossary
- Scope: "projects" — all projects, or only active / ongoing ones?
- Metric calculation: e.g. "average rating" — per project, per participant, overall?
- Time period: all-time vs. current status vs. a specific window
- "Count" — distinct entities, or total rows?

If you detect an ambiguity that would change the answer:
  → State the specific options concisely (e.g. "Did you mean (A) … or (B) …?")
  → Ask ONE clarifying question and stop your turn. Do NOT execute SQL yet.
  → Wait for the user to reply before proceeding.

If the question is clear, proceed directly to STEP 3. Do not ask for clarification \
when the intent is obvious — only when the answer would genuinely differ.

### STEP 3 — Write and execute SQL
Write clean SQL using only column names listed in the schema above.
Call execute_sql with your query.
If the result is unexpected or empty, reconsider your column mapping and retry.

### STEP 4 — Return a structured answer
Format your final response EXACTLY like this:

### Answer
[Clear business-language answer with the actual data result]

### SQL Used
```sql
[The exact SQL query executed]
```

### Governed Definitions Used
- **[Term Name]** (from [Collibra domain]): [governed definition]
(list every business term or column definition you relied on)

### Data Quality Notes
[Caveats: any ungoverned columns used, assumptions, data limitations, or missing definitions]

---

## Rules
1. Never use a column name that is not listed in the schema above.
2. Always prefer a governed Collibra definition over your own assumption.
3. If a business term has no governed definition in the glossary above, say so explicitly.
4. Keep SQL readable. Use aliases and comments where helpful.
5. If a question cannot be answered with the available data, say so clearly.
"""


def _build_schema_section(cache: CollibraCache) -> str:
    lines: list[str] = []
    for table_name in sorted(cache.physical_schema.keys()):
        columns = cache.physical_schema[table_name]
        lines.append(f"### {table_name}")
        for col in sorted(columns, key=lambda c: c.column_name):
            desc = col.description or "(no description)"
            lines.append(f"  - {col.column_name}: {desc}")
        lines.append("")
    return "\n".join(lines)


def _build_glossary_section(cache: CollibraCache) -> str:
    from app.collibra.cache import DOMAIN_IDS

    business_domain_ids = {DOMAIN_IDS["glossary"], DOMAIN_IDS["metrics_catalog"]}
    lines: list[str] = []
    terms = [
        a for a in cache.assets.values()
        if a.domain_id in business_domain_ids and (a.definition or a.description)
    ]
    for term in sorted(terms, key=lambda t: t.name):
        defn = term.definition or term.description
        synonyms = f" (synonyms: {', '.join(term.synonyms)})" if term.synonyms else ""
        lines.append(f"**{term.display_name or term.name}** [{term.type_name}] (ID: {term.id}){synonyms}")
        lines.append(f"  {defn}")
        lines.append("")
    return "\n".join(lines)


def build_system_prompt(cache: CollibraCache) -> str:
    """Called once at startup to bake the schema and glossary into the prompt."""
    schema_section = _build_schema_section(cache)
    glossary_section = _build_glossary_section(cache)

    from app.collibra.cache import DOMAIN_IDS
    business_domain_ids = {DOMAIN_IDS["glossary"], DOMAIN_IDS["metrics_catalog"]}
    term_count = sum(1 for a in cache.assets.values() if a.domain_id in business_domain_ids)

    return _PROMPT_TEMPLATE.format(
        schema_section=schema_section,
        glossary_section=glossary_section,
        term_count=term_count,
    )
