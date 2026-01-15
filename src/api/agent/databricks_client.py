"""
Databricks SQL connection utilities.
Provides connection management and query execution for agent tools.
"""

import json
from contextlib import contextmanager
from typing import Any, Generator, Optional
from databricks import sql
from databricks.sql.client import Connection, Cursor

from config.settings import get_config, DatabricksConfig


class DatabricksClient:
    """Client for executing queries against Databricks SQL warehouse."""

    def __init__(self, config: Optional[DatabricksConfig] = None):
        self.config = config or get_config().databricks

    @contextmanager
    def connection(self) -> Generator[Connection, None, None]:
        """Context manager for database connections."""
        conn = sql.connect(
            server_hostname=self.config.host,
            http_path=self.config.http_path,
            access_token=self.config.token,
        )
        try:
            yield conn
        finally:
            conn.close()

    def execute_query(
        self,
        query: str,
        params: Optional[dict] = None,
        max_rows: int = 100
    ) -> dict[str, Any]:
        """
        Execute a SQL query and return results as JSON-serializable dict.

        Args:
            query: SQL query to execute
            params: Optional query parameters
            max_rows: Maximum rows to return (default 100)

        Returns:
            Dict with success status, row_count, columns, and data
        """
        try:
            with self.connection() as conn:
                cursor: Cursor = conn.cursor()
                cursor.execute(query, params)

                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchmany(max_rows)
                data = [dict(zip(columns, row)) for row in rows]
                has_more = cursor.fetchone() is not None

                return {
                    "success": True,
                    "row_count": len(data),
                    "has_more": has_more,
                    "columns": columns,
                    "data": data
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def get_table_schema(self, table_name: str) -> dict[str, Any]:
        """Get schema information for a table."""
        return self.execute_query(f"DESCRIBE TABLE {table_name}", max_rows=50)

    def list_tables(self, schema: str) -> dict[str, Any]:
        """List all tables in a schema."""
        return self.execute_query(
            f"SHOW TABLES IN {self.config.catalog}.{schema}",
            max_rows=100
        )


# Singleton instance
_client: Optional[DatabricksClient] = None


def get_databricks_client() -> DatabricksClient:
    """Get singleton Databricks client instance."""
    global _client
    if _client is None:
        _client = DatabricksClient()
    return _client


def execute_query(query: str, max_rows: int = 100) -> dict[str, Any]:
    """Convenience function to execute a query."""
    return get_databricks_client().execute_query(query, max_rows=max_rows)
