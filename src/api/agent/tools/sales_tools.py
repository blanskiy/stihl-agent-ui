"""
Sales data query tools for STIHL Analytics Agent.
Updated to match actual Databricks schema.
"""

import json
from typing import Optional
from datetime import datetime, timedelta

from agent.databricks_client import execute_query
from config.settings import get_config


def query_sales_data(
    query_type: str,
    time_period: Optional[str] = None,
    category: Optional[str] = None,
    region: Optional[str] = None,
    top_n: int = 10
) -> str:
    """
    Query STIHL sales data to answer questions about revenue, units sold, and trends.

    Args:
        query_type: Type of analysis. Options:
            - "summary": Overall sales metrics for period
            - "top_products": Best selling products by revenue
            - "top_dealers": Best performing dealers
            - "trend": Month-over-month trends
            - "by_category": Sales broken down by product category
            - "by_region": Sales broken down by region
        time_period: Time filter (last_month, last_quarter, last_year, ytd, 2024-Q1, 2024-06)
        category: Filter by category (Chainsaws, Blowers, Trimmers, etc.)
        region: Filter by region (Southwest, Northeast, Midwest, etc.)
        top_n: Number of results for ranking queries (default 10)

    Returns:
        JSON string with query results
    """
    config = get_config()
    catalog = config.databricks.catalog
    monthly_sales = f"{catalog}.gold.monthly_sales"
    product_perf = f"{catalog}.gold.product_performance"
    dealer_perf = f"{catalog}.gold.dealer_performance"

    time_clause = _build_time_clause(time_period)

    filters = []
    if category:
        filters.append(f"category = '{category}'")
    if region:
        filters.append(f"region = '{region}'")
    filter_clause = " AND ".join(filters) if filters else "1=1"

    queries = {
        "summary": f"""
            SELECT 
                COUNT(DISTINCT year || '-' || month) as periods,
                SUM(total_revenue) as total_revenue,
                SUM(total_units) as total_units,
                SUM(transaction_count) as total_transactions,
                ROUND(SUM(total_revenue) / NULLIF(SUM(total_units), 0), 2) as avg_price_per_unit
            FROM {monthly_sales}
            WHERE {time_clause} AND {filter_clause}
        """,
        "top_products": f"""
            SELECT 
                product_name,
                category,
                total_revenue as revenue,
                total_units_sold as units_sold,
                transaction_count
            FROM {product_perf}
            ORDER BY total_revenue DESC
            LIMIT {top_n}
        """,
        "top_dealers": f"""
            SELECT 
                dealer_name,
                region,
                state,
                total_revenue as revenue,
                total_units_sold as units_sold,
                transaction_count
            FROM {dealer_perf}
            ORDER BY total_revenue DESC
            LIMIT {top_n}
        """,
        "trend": f"""
            SELECT 
                year,
                month,
                SUM(total_revenue) as revenue,
                SUM(total_units) as units,
                SUM(transaction_count) as transactions
            FROM {monthly_sales}
            WHERE {time_clause} AND {filter_clause}
            GROUP BY year, month
            ORDER BY year, month
        """,
        "by_category": f"""
            SELECT 
                category,
                SUM(total_revenue) as revenue,
                SUM(total_units) as units_sold,
                SUM(transaction_count) as transactions,
                ROUND(SUM(total_revenue) * 100.0 / SUM(SUM(total_revenue)) OVER (), 1) as pct_of_total
            FROM {monthly_sales}
            WHERE {time_clause} AND {filter_clause}
            GROUP BY category
            ORDER BY revenue DESC
        """,
        "by_region": f"""
            SELECT 
                region,
                SUM(total_revenue) as revenue,
                SUM(total_units) as units_sold,
                SUM(transaction_count) as transactions,
                ROUND(SUM(total_revenue) * 100.0 / SUM(SUM(total_revenue)) OVER (), 1) as pct_of_total
            FROM {monthly_sales}
            WHERE {time_clause} AND {filter_clause}
            GROUP BY region
            ORDER BY revenue DESC
        """
    }

    if query_type not in queries:
        return json.dumps({
            "success": False,
            "error": f"Unknown query_type: {query_type}. Use: {', '.join(queries.keys())}"
        })

    result = execute_query(queries[query_type])
    result["query_type"] = query_type
    result["filters_applied"] = {
        "time_period": time_period,
        "category": category,
        "region": region
    }
    return json.dumps(result, default=str)


def _build_time_clause(time_period: Optional[str]) -> str:
    """Convert time_period string to SQL WHERE clause."""
    if not time_period:
        return "1=1"

    today = datetime.now()

    if time_period == "last_month":
        last_month = today.replace(day=1) - timedelta(days=1)
        return f"year = {last_month.year} AND month = {last_month.month}"
    elif time_period == "last_quarter":
        current_quarter = (today.month - 1) // 3 + 1
        if current_quarter == 1:
            year, quarter = today.year - 1, 4
        else:
            year, quarter = today.year, current_quarter - 1
        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3
        return f"year = {year} AND month BETWEEN {start_month} AND {end_month}"
    elif time_period == "last_year":
        return f"year = {today.year - 1}"
    elif time_period == "ytd":
        return f"year = {today.year} AND month <= {today.month}"
    elif "-Q" in time_period:
        year, quarter = time_period.split("-Q")
        quarter = int(quarter)
        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3
        return f"year = {year} AND month BETWEEN {start_month} AND {end_month}"
    elif "-" in time_period and len(time_period) == 7:
        year, month = time_period.split("-")
        return f"year = {year} AND month = {month}"
    else:
        return f"year = {time_period}"


# Tool definition for Azure AI Foundry
SALES_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "query_sales_data",
        "description": "Query STIHL sales data for revenue, units, trends, and performance analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["summary", "top_products", "top_dealers", "trend", "by_category", "by_region"],
                    "description": "Type of sales analysis to perform"
                },
                "time_period": {
                    "type": "string",
                    "description": "Time filter: last_month, last_quarter, last_year, ytd, 2024-Q1, 2024-06"
                },
                "category": {"type": "string", "description": "Filter by product category"},
                "region": {"type": "string", "description": "Filter by region"},
                "top_n": {"type": "integer", "description": "Number of results for ranking queries"}
            },
            "required": ["query_type"]
        }
    }
}
