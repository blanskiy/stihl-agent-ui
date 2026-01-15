"""
Inventory data query tools for STIHL Analytics Agent.
Updated to match actual Databricks schema.
"""

import json
from typing import Optional

from agent.databricks_client import execute_query
from config.settings import get_config


def query_inventory_data(
    query_type: str,
    category: Optional[str] = None,
    region: Optional[str] = None,
    status_filter: Optional[str] = None,
    top_n: int = 10
) -> str:
    """
    Query STIHL inventory data for stock levels, stockouts, and supply analysis.

    Args:
        query_type: Type of analysis. Options:
            - "summary": Overall inventory metrics
            - "low_stock": Products with low days of supply
            - "stockouts": Products with zero inventory
            - "by_category": Inventory by product category
            - "by_region": Inventory by region
            - "days_of_supply": Products sorted by days of supply
            - "by_status": Inventory grouped by status
        status_filter: Filter by status (Critical, Low, Healthy, Overstocked)
        category: Filter by category
        region: Filter by region
        top_n: Number of results (default 10)

    Returns:
        JSON string with query results
    """
    config = get_config()
    catalog = config.databricks.catalog
    inventory_status = f"{catalog}.gold.inventory_status"

    filters = []
    if category:
        filters.append(f"category = '{category}'")
    if region:
        filters.append(f"region = '{region}'")
    if status_filter:
        filters.append(f"status = '{status_filter}'")
    filter_clause = " AND ".join(filters) if filters else "1=1"

    queries = {
        "summary": f"""
            SELECT 
                COUNT(DISTINCT product_id) as total_products,
                COUNT(DISTINCT warehouse_id) as total_warehouses,
                SUM(quantity_on_hand) as total_units_on_hand,
                SUM(quantity_available) as total_units_available,
                ROUND(AVG(days_of_supply), 1) as avg_days_of_supply,
                SUM(CASE WHEN quantity_on_hand = 0 THEN 1 ELSE 0 END) as stockout_count,
                SUM(CASE WHEN status = 'Critical' THEN 1 ELSE 0 END) as critical_count,
                SUM(CASE WHEN status = 'Low' THEN 1 ELSE 0 END) as low_count
            FROM {inventory_status}
            WHERE {filter_clause}
        """,
        "low_stock": f"""
            SELECT 
                product_name,
                category,
                warehouse_id,
                region,
                quantity_on_hand,
                quantity_available,
                days_of_supply,
                status
            FROM {inventory_status}
            WHERE status IN ('Critical', 'Low') AND quantity_on_hand > 0 AND {filter_clause}
            ORDER BY days_of_supply ASC
            LIMIT {top_n}
        """,
        "stockouts": f"""
            SELECT 
                product_name,
                category,
                warehouse_id,
                region,
                quantity_on_hand,
                status
            FROM {inventory_status}
            WHERE quantity_on_hand = 0 AND {filter_clause}
            ORDER BY product_name
            LIMIT {top_n}
        """,
        "by_category": f"""
            SELECT 
                category,
                COUNT(DISTINCT product_id) as products,
                SUM(quantity_on_hand) as total_units,
                ROUND(AVG(days_of_supply), 1) as avg_days_of_supply,
                SUM(CASE WHEN quantity_on_hand = 0 THEN 1 ELSE 0 END) as stockouts,
                SUM(CASE WHEN status = 'Critical' THEN 1 ELSE 0 END) as critical_items
            FROM {inventory_status}
            WHERE {filter_clause}
            GROUP BY category
            ORDER BY total_units DESC
        """,
        "by_region": f"""
            SELECT 
                region,
                COUNT(DISTINCT warehouse_id) as warehouses,
                COUNT(DISTINCT product_id) as products,
                SUM(quantity_on_hand) as total_units,
                ROUND(AVG(days_of_supply), 1) as avg_days_of_supply,
                SUM(CASE WHEN quantity_on_hand = 0 THEN 1 ELSE 0 END) as stockouts
            FROM {inventory_status}
            WHERE {filter_clause}
            GROUP BY region
            ORDER BY total_units DESC
        """,
        "days_of_supply": f"""
            SELECT 
                product_name,
                category,
                region,
                quantity_on_hand,
                quantity_available,
                days_of_supply,
                status
            FROM {inventory_status}
            WHERE {filter_clause}
            ORDER BY days_of_supply ASC
            LIMIT {top_n}
        """,
        "by_status": f"""
            SELECT 
                status,
                COUNT(*) as count,
                SUM(quantity_on_hand) as total_units,
                ROUND(AVG(days_of_supply), 1) as avg_days_of_supply
            FROM {inventory_status}
            WHERE {filter_clause}
            GROUP BY status
            ORDER BY 
                CASE status 
                    WHEN 'Critical' THEN 1 
                    WHEN 'Low' THEN 2 
                    WHEN 'Healthy' THEN 3 
                    WHEN 'Overstocked' THEN 4 
                    ELSE 5 
                END
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
        "category": category,
        "region": region,
        "status_filter": status_filter
    }
    return json.dumps(result, default=str)


# Tool definition for Azure AI Foundry
INVENTORY_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "query_inventory_data",
        "description": "Query STIHL inventory data for stock levels, stockouts, and supply chain analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["summary", "low_stock", "stockouts", "by_category", "by_region", "days_of_supply", "by_status"],
                    "description": "Type of inventory analysis to perform"
                },
                "status_filter": {
                    "type": "string",
                    "enum": ["Critical", "Low", "Healthy", "Overstocked"],
                    "description": "Filter by inventory status"
                },
                "category": {"type": "string", "description": "Filter by product category"},
                "region": {"type": "string", "description": "Filter by region"},
                "top_n": {"type": "integer", "description": "Number of results"}
            },
            "required": ["query_type"]
        }
    }
}
