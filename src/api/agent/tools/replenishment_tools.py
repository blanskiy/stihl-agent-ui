"""
Replenishment tools for STIHL Analytics Agent.

Handles shipment request creation for inventory replenishment.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from agent.databricks_client import execute_query
from config.settings import get_config

logger = logging.getLogger(__name__)


def create_shipment_request(
    product_name: str,
    destination: str,
    quantity: int,
    product_id: Optional[int] = None
) -> str:
    """
    Create a shipment request to replenish inventory.

    Args:
        product_name: Name of the product to replenish
        destination: Target region/warehouse (e.g., "Northeast", "Southwest")
        quantity: Number of units to ship
        product_id: Optional product ID (will be looked up if not provided)

    Returns:
        JSON with shipment request confirmation
    """
    config = get_config()
    catalog = config.databricks.catalog

    now = datetime.now()
    month = now.month
    year = now.year

    # If product_id not provided, try to look it up
    # Escape single quotes for SQL safety
    safe_product_name = product_name.replace("'", "''")

    if product_id is None:
        lookup_query = f"""
        SELECT DISTINCT product_id
        FROM {catalog}.gold.inventory_status
        WHERE product_name = '{safe_product_name}'
        LIMIT 1
        """
        lookup_result = execute_query(lookup_query)
        if lookup_result.get("success") and lookup_result.get("data"):
            product_id = lookup_result["data"][0].get("product_id")

    # Insert the shipment request
    # Handle product_id - can be string like 'FS-111' or NULL
    product_id_sql = f"'{product_id}'" if product_id is not None else 'NULL'

    # Escape destination for SQL safety
    safe_destination = destination.replace("'", "''")

    insert_query = f"""
    INSERT INTO {catalog}.silver.shipment_requests
    (shipment_request_date, month, year, product_id, product_name, quantity, destination)
    VALUES (
        CURRENT_TIMESTAMP(),
        {month},
        {year},
        {product_id_sql},
        '{safe_product_name}',
        {quantity},
        '{safe_destination}'
    )
    """

    result = execute_query(insert_query)

    if result.get("success"):
        # Get the created request ID
        id_query = f"""
        SELECT shipment_request_id, shipment_request_date
        FROM {catalog}.silver.shipment_requests
        WHERE product_name = '{safe_product_name}'
          AND destination = '{safe_destination}'
        ORDER BY shipment_request_date DESC
        LIMIT 1
        """
        id_result = execute_query(id_query)

        request_id = None
        request_date = None
        if id_result.get("success") and id_result.get("data"):
            request_id = id_result["data"][0].get("shipment_request_id")
            request_date = id_result["data"][0].get("shipment_request_date")

        return json.dumps({
            "success": True,
            "message": f"Shipment request created successfully",
            "shipment_request_id": request_id,
            "product_name": product_name,
            "product_id": product_id,
            "destination": destination,
            "quantity": quantity,
            "request_date": str(request_date) if request_date else str(now),
            "status": "PENDING"
        }, default=str)
    else:
        return json.dumps({
            "success": False,
            "error": result.get("error", "Failed to create shipment request"),
            "product_name": product_name,
            "destination": destination,
            "quantity": quantity
        }, default=str)


def get_shipment_requests(
    status: Optional[str] = None,
    destination: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Query existing shipment requests.

    Args:
        status: Filter by status (PENDING, APPROVED, SHIPPED, COMPLETED)
        destination: Filter by destination region
        limit: Maximum number of requests to return

    Returns:
        JSON with shipment requests
    """
    config = get_config()
    catalog = config.databricks.catalog

    where_clauses = []
    if status:
        where_clauses.append(f"status = '{status}'")
    if destination:
        where_clauses.append(f"destination = '{destination}'")

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    query = f"""
    SELECT
        shipment_request_id,
        shipment_request_date,
        month,
        year,
        product_id,
        product_name,
        quantity,
        destination,
        status
    FROM {catalog}.silver.shipment_requests
    {where_sql}
    ORDER BY shipment_request_date DESC
    LIMIT {limit}
    """

    result = execute_query(query)
    return json.dumps(result, default=str)


# Tool definitions for Azure OpenAI function calling
REPLENISHMENT_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "create_shipment_request",
            "description": "IMMEDIATELY create a shipment request when user asks to replenish, restock, or order inventory. Call this tool directly without asking - creates database record for the request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "Name of the product to replenish (e.g., 'FS 111 R', 'MS 271')"
                    },
                    "destination": {
                        "type": "string",
                        "description": "Target region (Northeast, Southwest, Midwest, Southeast, West)"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of units to ship (default 50 if not specified)"
                    },
                    "product_id": {
                        "type": "integer",
                        "description": "Optional product ID"
                    }
                },
                "required": ["product_name", "destination", "quantity"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_shipment_requests",
            "description": "Query existing shipment requests to check status or history of replenishment orders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["PENDING", "APPROVED", "SHIPPED", "COMPLETED"],
                        "description": "Filter by request status"
                    },
                    "destination": {
                        "type": "string",
                        "description": "Filter by destination region"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of requests to return",
                        "default": 10
                    }
                }
            }
        }
    }
]
