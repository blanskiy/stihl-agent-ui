"""
Tool result truncation utilities.

Summarizes JSON tool results to reduce token usage while
preserving essential information like product names and key metrics.
"""

import json
import logging
from typing import Any, Union

logger = logging.getLogger(__name__)

# Increased limit to preserve important data (~500 tokens)
MAX_RESULT_CHARS = 2000

# Keys that should NEVER be truncated (product identifiers, names, etc.)
CRITICAL_KEYS = [
    "product_name", "product_id", "name", "id", "sku",
    "category", "region", "status", "severity",
    "days_of_supply", "units_on_hand", "units_available",
    "insight_type", "title", "description", "message",
    # Sales metrics - critical for answering sales questions
    "revenue", "units_sold", "transaction_count", "transactions",
    "units", "avg_price_per_unit", "pct_of_total",
    # Dealer info
    "dealer_name", "state",
]

# Keys for summary data
SUMMARY_KEYS = [
    "total", "count", "summary", "status", "error",
    "total_revenue", "total_units", "insight_count",
    "total_products", "critical_count", "warning_count",
    "total_transactions", "periods",
]


def truncate_tool_result(
    result: Union[str, dict, list],
    max_chars: int = MAX_RESULT_CHARS,
    preserve_keys: list[str] = None
) -> str:
    """
    Truncate a tool result while preserving essential information.

    Balances token savings with data completeness:
    - Always preserves product names, IDs, and key identifiers
    - Keeps summary metrics intact
    - Truncates only verbose description fields

    Args:
        result: The tool result (JSON string or parsed)
        max_chars: Maximum characters in output (default 2000)
        preserve_keys: Additional keys to preserve in full

    Returns:
        Truncated JSON string
    """
    all_preserve_keys = CRITICAL_KEYS + SUMMARY_KEYS
    if preserve_keys:
        all_preserve_keys = list(set(all_preserve_keys + preserve_keys))

    # Parse if string
    if isinstance(result, str):
        try:
            data = json.loads(result)
        except json.JSONDecodeError:
            # Plain string - just truncate
            if len(result) <= max_chars:
                return result
            return result[:max_chars - 20] + "... [truncated]"
    else:
        data = result

    # Truncate based on type
    truncated = _truncate_value(data, max_chars, all_preserve_keys, depth=0)

    # Convert back to JSON
    output = json.dumps(truncated, default=str)

    # Final safety truncation (but warn)
    if len(output) > max_chars:
        logger.warning(f"Tool result exceeded max_chars ({len(output)} > {max_chars})")
        output = output[:max_chars - 50] + '... [truncated for length]"}'

    return output


def _truncate_value(
    value: Any,
    max_chars: int,
    preserve_keys: list[str],
    depth: int = 0
) -> Any:
    """Recursively truncate a value."""

    if depth > 4:
        # Too deep - summarize
        return "[nested data]"

    if isinstance(value, dict):
        return _truncate_dict(value, max_chars, preserve_keys, depth)

    if isinstance(value, list):
        return _truncate_list(value, max_chars, preserve_keys, depth)

    if isinstance(value, str):
        # More generous string limit
        if len(value) > 300:
            return value[:300] + "..."
        return value

    return value


def _truncate_dict(
    data: dict,
    max_chars: int,
    preserve_keys: list[str],
    depth: int
) -> dict:
    """Truncate a dictionary while preserving critical keys."""
    result = {}
    char_budget = max_chars

    # First pass: include ALL preserved/critical keys (never truncate these)
    for key in preserve_keys:
        if key in data:
            value = data[key]
            # Keep critical values intact (only truncate very long strings)
            if isinstance(value, str) and len(value) > 500:
                value = value[:500] + "..."
            result[key] = value
            char_budget -= len(str(value)) + len(key) + 10

    # Second pass: include other keys until budget exhausted
    for key, value in data.items():
        if key in result:
            continue

        if char_budget <= 200:
            # Add indicator of truncation
            remaining = len(data) - len(result)
            if remaining > 0:
                result["_more_fields"] = remaining
            break

        truncated_value = _truncate_value(value, min(500, char_budget), preserve_keys, depth + 1)
        value_len = len(str(truncated_value)) + len(key) + 10

        if value_len < char_budget:
            result[key] = truncated_value
            char_budget -= value_len

    return result


def _truncate_list(
    data: list,
    max_chars: int,
    preserve_keys: list[str],
    depth: int
) -> Union[list, dict]:
    """Truncate a list while keeping enough items for useful answers."""
    if not data:
        return []

    total_count = len(data)

    # For short lists (up to 5), keep all items
    if total_count <= 5:
        return [
            _truncate_value(item, max_chars // max(1, total_count), preserve_keys, depth + 1)
            for item in data
        ]

    # For longer lists, keep more items (up to 8) to provide complete answers
    max_items = min(8, total_count)
    per_item_budget = (max_chars - 100) // max_items

    truncated = [
        _truncate_value(item, per_item_budget, preserve_keys, depth + 1)
        for item in data[:max_items]
    ]

    # Return as list with note if truncated
    if total_count > max_items:
        return {
            "items": truncated,
            "total_count": total_count,
            "showing": max_items,
        }

    return truncated


def summarize_sql_result(result: str, query_type: str = None) -> str:
    """
    Create a concise summary of SQL query results.

    Specialized for common STIHL query types.
    """
    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        return truncate_tool_result(result)

    summary_parts = []

    # Extract key metrics based on query type
    if isinstance(data, dict):
        # Look for common summary fields
        if "total_revenue" in data:
            summary_parts.append(f"Revenue: ${data['total_revenue']:,.0f}")
        if "total_units" in data:
            summary_parts.append(f"Units: {data['total_units']:,}")
        if "count" in data or "total" in data:
            count = data.get("count") or data.get("total")
            summary_parts.append(f"Count: {count}")

        # Handle results lists
        if "results" in data and isinstance(data["results"], list):
            results = data["results"]
            summary_parts.append(f"{len(results)} items returned")

            # Preview first item
            if results:
                first = results[0]
                if isinstance(first, dict):
                    preview_keys = list(first.keys())[:3]
                    summary_parts.append(f"Fields: {', '.join(preview_keys)}")

    if summary_parts:
        return json.dumps({
            "summary": " | ".join(summary_parts),
            "data": truncate_tool_result(data, max_chars=1500)
        })

    return truncate_tool_result(result)
