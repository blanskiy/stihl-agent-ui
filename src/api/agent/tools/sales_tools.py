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
    state: Optional[str] = None,
    top_n: int = 10
) -> str:
    """
    Query STIHL sales data to answer questions about revenue, units sold, and trends.

    Args:
        query_type: Type of analysis. Options:
            - "summary": Overall sales metrics for period
            - "top_products": Best selling products by revenue (supports all filters)
            - "top_dealers": Best performing dealers
            - "trend": Month-over-month trends
            - "by_category": Sales broken down by product category
            - "by_region": Sales broken down by region
        time_period: Time filter (last_month, last_quarter, last_year, ytd, 2024, 2025, 2024-Q1, 2024-06)
        category: Filter by category (Chainsaws, Blowers, Trimmers, etc.)
        region: Filter by region (Southwest, Northeast, Midwest, etc.)
        state: Filter by state (California, Texas, Florida, etc.)
        top_n: Number of results for ranking queries (default 10)

    Returns:
        JSON string with query results including revenue, units_sold, and transaction_count
    """
    config = get_config()
    catalog = config.databricks.catalog
    monthly_sales = f"{catalog}.gold.monthly_sales"
    product_perf = f"{catalog}.gold.product_performance"
    dealer_perf = f"{catalog}.gold.dealer_performance"
    # Use silver layer for granular product+state+time data
    sales_transactions = f"{catalog}.silver.sales_transactions"

    time_clause = _build_time_clause(time_period)

    filters = []
    if category:
        filters.append(f"category = '{category}'")
    if region:
        filters.append(f"region = '{region}'")
    if state:
        filters.append(f"state = '{state}'")
    filter_clause = " AND ".join(filters) if filters else "1=1"

    # Build product query - use silver layer when state/time filters are needed
    has_granular_filters = state is not None or time_period is not None
    if has_granular_filters:
        # Use silver.sales_transactions for granular filtering
        top_products_query = f"""
            SELECT
                product_name,
                category,
                SUM(total_amount) as revenue,
                SUM(quantity) as units_sold,
                COUNT(*) as transaction_count
            FROM {sales_transactions}
            WHERE {time_clause} AND {filter_clause}
            GROUP BY product_name, category
            ORDER BY revenue DESC
            LIMIT {top_n}
        """
    else:
        # Use aggregate table when no granular filters needed
        top_products_query = f"""
            SELECT
                product_name,
                category,
                total_revenue as revenue,
                total_units_sold as units_sold,
                transaction_count
            FROM {product_perf}
            ORDER BY total_revenue DESC
            LIMIT {top_n}
        """

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
        "top_products": top_products_query,
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

    # If top_products with granular filters failed, try fallback to aggregate table
    if query_type == "top_products" and has_granular_filters and not result.get("success"):
        # Fallback: use aggregate table but note that filters couldn't be applied
        fallback_query = f"""
            SELECT
                product_name,
                category,
                total_revenue as revenue,
                total_units_sold as units_sold,
                transaction_count
            FROM {product_perf}
            ORDER BY total_revenue DESC
            LIMIT {top_n}
        """
        result = execute_query(fallback_query)
        result["note"] = f"State/time filters not available for product-level data. Showing overall top products."

    result["query_type"] = query_type
    result["filters_applied"] = {
        "time_period": time_period,
        "category": category,
        "region": region,
        "state": state
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
        "description": "Query STIHL sales data for revenue, units sold, transaction counts, and performance analysis. Use top_products with state/time_period filters to get best selling products for specific states or years.",
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["summary", "top_products", "top_dealers", "trend", "by_category", "by_region"],
                    "description": "Type of sales analysis. Use 'top_products' for best selling products with full metrics."
                },
                "time_period": {
                    "type": "string",
                    "description": "Time filter: last_month, last_quarter, last_year, ytd, 2024, 2025, 2024-Q1, 2024-06"
                },
                "category": {"type": "string", "description": "Filter by product category"},
                "region": {"type": "string", "description": "Filter by region (Northeast, Southeast, Midwest, Southwest, West)"},
                "state": {"type": "string", "description": "Filter by US state (California, Texas, Florida, etc.)"},
                "top_n": {"type": "integer", "description": "Number of results for ranking queries (default 10)"}
            },
            "required": ["query_type"]
        }
    }
}
