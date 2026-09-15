import logging
import re

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

_BLOCKED = re.compile(r"\b(DROP|DELETE|INSERT|UPDATE|ATTACH|DETACH|COPY|EXPORT)\b", re.IGNORECASE)


class DuckDBEngine:
    def __init__(self):
        self._conn: duckdb.DuckDBPyConnection | None = None
        self.table_names: list[str] = []

    def setup(self, tables: dict[str, pd.DataFrame]) -> None:
        self._conn = duckdb.connect(":memory:")
        for name, df in tables.items():
            self._conn.register(name, df)
            self.table_names.append(name)
        logger.info("DuckDB ready with tables: %s", self.table_names)

    def execute_query(self, sql: str) -> dict:
        if self._conn is None:
            return {"error": "Database not initialized"}
        if _BLOCKED.search(sql):
            return {"error": "Query contains disallowed SQL operation"}
        try:
            result_df = self._conn.execute(sql).fetchdf()
            rows = result_df.head(500).values.tolist()
            # Convert non-serializable types to strings
            serializable_rows = []
            for row in rows:
                serializable_rows.append([
                    str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v
                    for v in row
                ])
            return {
                "columns": list(result_df.columns),
                "rows": serializable_rows,
                "row_count": len(result_df),
            }
        except Exception as e:
            logger.warning("SQL execution error: %s\nSQL: %s", e, sql)
            return {"error": str(e)}
