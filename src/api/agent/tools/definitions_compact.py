"""
Compact tool definitions for Azure OpenAI function calling.

Optimized versions with shorter descriptions to reduce token usage.
~40% fewer tokens than verbose definitions.
"""

# Compact Sales Tool Definition (~60% shorter)
SALES_TOOL_COMPACT = {
    "type": "function",
    "function": {
        "name": "query_sales_data",
        "description": "Query sales data: revenue, units, trends, rankings",
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["summary", "top_products", "top_dealers", "trend", "by_category", "by_region"]
                },
                "time_period": {"type": "string"},
                "category": {"type": "string"},
                "region": {"type": "string"},
                "top_n": {"type": "integer", "default": 10}
            },
            "required": ["query_type"]
        }
    }
}

# Compact Inventory Tool Definition
INVENTORY_TOOL_COMPACT = {
    "type": "function",
    "function": {
        "name": "query_inventory_data",
        "description": "Query inventory: stock levels, critical products, days of supply. Use 'critical_products' for critical items, 'days_of_supply' with max_days_of_supply for low supply products.",
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["summary", "low_stock", "stockouts", "by_category", "by_region", "days_of_supply", "by_status", "critical_products"]
                },
                "category": {"type": "string"},
                "region": {"type": "string"},
                "status_filter": {"type": "string", "enum": ["Critical", "Low", "Healthy", "Overstocked"]},
                "max_days_of_supply": {"type": "integer", "description": "Filter products with <= this many days of supply"},
                "top_n": {"type": "integer", "default": 10}
            },
            "required": ["query_type"]
        }
    }
}

# Compact Insights Tool Definitions
INSIGHTS_TOOLS_COMPACT = [
    {
        "type": "function",
        "function": {
            "name": "get_proactive_insights",
            "description": "Get alerts, anomalies, and proactive insights",
            "parameters": {
                "type": "object",
                "properties": {
                    "insight_types": {"type": "array", "items": {"type": "string"}},
                    "severity_filter": {"type": "string", "enum": ["critical", "warning", "info"]},
                    "max_insights": {"type": "integer", "default": 5}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_anomalies_realtime",
            "description": "Run anomaly detection on metrics",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "enum": ["revenue", "units", "transactions"]},
                    "group_by": {"type": "string", "enum": ["category", "region", "product"]},
                    "time_period": {"type": "string"},
                    "z_threshold": {"type": "number", "default": 2.0}
                },
                "required": ["metric", "group_by"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_briefing",
            "description": "Get daily business briefing",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

# Compact RAG Tool Definitions
RAG_TOOLS_COMPACT = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Semantic search for products by features/use case",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "category": {"type": "string"},
                    "power_type": {"type": "string", "enum": ["Gas", "Battery", "Electric"]},
                    "top_k": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_products",
            "description": "Compare 2-4 products side by side",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_ids": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["product_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_recommendations",
            "description": "Get product recommendations for use case",
            "parameters": {
                "type": "object",
                "properties": {
                    "use_case": {"type": "string"},
                    "preferences": {"type": "object"}
                },
                "required": ["use_case"]
            }
        }
    }
]

# Compact Dealer Tool Definition
DEALER_TOOL_COMPACT = {
    "type": "function",
    "function": {
        "name": "query_dealer_data",
        "description": "Query dealer performance data",
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {"type": "string", "enum": ["summary", "top_dealers", "by_region", "by_tier"]},
                "region": {"type": "string"},
                "tier": {"type": "string"},
                "time_period": {"type": "string"},
                "top_n": {"type": "integer", "default": 10}
            },
            "required": ["query_type"]
        }
    }
}

# Compact Forecast Tool Definition
FORECAST_TOOL_COMPACT = {
    "type": "function",
    "function": {
        "name": "get_sales_forecast",
        "description": "Get sales forecast for future periods",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "region": {"type": "string"},
                "periods_ahead": {"type": "integer", "default": 3}
            }
        }
    }
}

# Compact Trend Tool Definition
TREND_TOOL_COMPACT = {
    "type": "function",
    "function": {
        "name": "analyze_trends",
        "description": "Analyze sales trends and patterns",
        "parameters": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "enum": ["revenue", "units", "avg_price"]},
                "group_by": {"type": "string", "enum": ["category", "region", "product"]},
                "time_granularity": {"type": "string", "enum": ["monthly", "quarterly"]},
                "periods": {"type": "integer", "default": 12}
            },
            "required": ["metric"]
        }
    }
}

# Compact Replenishment Tool Definitions
REPLENISHMENT_TOOLS_COMPACT = [
    {
        "type": "function",
        "function": {
            "name": "create_shipment_request",
            "description": "IMMEDIATELY create shipment request when user asks to replenish/restock/order. Call directly without asking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string"},
                    "destination": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "product_id": {"type": "integer"}
                },
                "required": ["product_name", "destination", "quantity"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_shipment_requests",
            "description": "Query existing shipment requests",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["PENDING", "APPROVED", "SHIPPED", "COMPLETED"]},
                    "destination": {"type": "string"},
                    "limit": {"type": "integer", "default": 10}
                }
            }
        }
    }
]


# Mapping from tool names to compact definitions
COMPACT_TOOL_MAP = {
    "query_sales_data": SALES_TOOL_COMPACT,
    "query_inventory_data": INVENTORY_TOOL_COMPACT,
    "get_proactive_insights": INSIGHTS_TOOLS_COMPACT[0],
    "detect_anomalies_realtime": INSIGHTS_TOOLS_COMPACT[1],
    "get_daily_briefing": INSIGHTS_TOOLS_COMPACT[2],
    "search_products": RAG_TOOLS_COMPACT[0],
    "compare_products": RAG_TOOLS_COMPACT[1],
    "get_product_recommendations": RAG_TOOLS_COMPACT[2],
    "query_dealer_data": DEALER_TOOL_COMPACT,
    "get_sales_forecast": FORECAST_TOOL_COMPACT,
    "analyze_trends": TREND_TOOL_COMPACT,
    "create_shipment_request": REPLENISHMENT_TOOLS_COMPACT[0],
    "get_shipment_requests": REPLENISHMENT_TOOLS_COMPACT[1],
}

# All compact definitions combined
TOOL_DEFINITIONS_COMPACT = [
    SALES_TOOL_COMPACT,
    INVENTORY_TOOL_COMPACT,
    *INSIGHTS_TOOLS_COMPACT,
    *RAG_TOOLS_COMPACT,
    DEALER_TOOL_COMPACT,
    FORECAST_TOOL_COMPACT,
    TREND_TOOL_COMPACT,
    *REPLENISHMENT_TOOLS_COMPACT,
]


def get_compact_tools(tool_names: list[str]) -> list[dict]:
    """
    Get compact tool definitions for specified tools.

    Args:
        tool_names: List of tool names to include

    Returns:
        List of compact tool definitions
    """
    return [
        COMPACT_TOOL_MAP[name]
        for name in tool_names
        if name in COMPACT_TOOL_MAP
    ]
