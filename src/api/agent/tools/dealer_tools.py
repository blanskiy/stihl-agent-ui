"""
Dealer Tools - SQL queries for dealer network analysis.

Provides analytics on:
- Dealer performance rankings
- Regional dealer distribution
- Performance tiers
"""

import json
from agent.databricks_client import DatabricksClient


def query_dealer_data(
    query_type: str,
    region: str = None,
    top_n: int = 10
) -> str:
    """
    Query dealer network data from Databricks.
    
    Args:
        query_type: Type of analysis - summary, top_dealers, by_region, 
                    performance_tiers
        region: Filter by region
        top_n: Number of results for rankings
        
    Returns:
        JSON string with query results
    """
    client = DatabricksClient()
    
    # Build base filters
    filters = []
    if region:
        filters.append(f"region = '{region}'")
    
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    
    if query_type == "summary":
        # Overall dealer network summary
        query = f"""
        SELECT 
            COUNT(DISTINCT dealer_id) as total_dealers,
            COUNT(DISTINCT region) as regions_covered,
            COUNT(DISTINCT state) as states_covered,
            SUM(total_revenue) as total_revenue,
            SUM(total_units_sold) as total_units,
            SUM(transaction_count) as total_transactions
        FROM dbw_stihl_analytics.gold.dealer_performance
        {where_clause}
        """
        
    elif query_type == "top_dealers":
        # Top performing dealers by revenue
        query = f"""
        SELECT 
            dealer_id,
            dealer_name,
            region,
            state,
            total_revenue,
            total_units_sold,
            transaction_count,
            ROUND(total_revenue / NULLIF(transaction_count, 0), 2) as avg_transaction_value
        FROM dbw_stihl_analytics.gold.dealer_performance
        {where_clause}
        ORDER BY total_revenue DESC
        LIMIT {top_n}
        """
        
    elif query_type == "by_region":
        # Dealer distribution and performance by region
        query = f"""
        SELECT 
            region,
            COUNT(DISTINCT dealer_id) as dealer_count,
            SUM(total_revenue) as total_revenue,
            SUM(total_units_sold) as total_units,
            AVG(total_revenue) as avg_revenue_per_dealer,
            AVG(total_revenue / NULLIF(transaction_count, 0)) as avg_transaction_value
        FROM dbw_stihl_analytics.gold.dealer_performance
        {where_clause}
        GROUP BY region
        ORDER BY total_revenue DESC
        """
        
    elif query_type == "performance_tiers":
        # Segment dealers into performance tiers
        query = f"""
        WITH dealer_stats AS (
            SELECT 
                dealer_id,
                dealer_name,
                region,
                state,
                total_revenue,
                NTILE(4) OVER (ORDER BY total_revenue DESC) as performance_quartile
            FROM dbw_stihl_analytics.gold.dealer_performance
            {where_clause}
        )
        SELECT 
            CASE performance_quartile
                WHEN 1 THEN 'Platinum (Top 25%)'
                WHEN 2 THEN 'Gold (25-50%)'
                WHEN 3 THEN 'Silver (50-75%)'
                WHEN 4 THEN 'Bronze (Bottom 25%)'
            END as tier,
            COUNT(*) as dealer_count,
            SUM(total_revenue) as tier_revenue,
            AVG(total_revenue) as avg_revenue,
            MIN(total_revenue) as min_revenue,
            MAX(total_revenue) as max_revenue
        FROM dealer_stats
        GROUP BY performance_quartile
        ORDER BY performance_quartile
        """
        
    elif query_type == "bottom_dealers":
        # Lowest performing dealers
        query = f"""
        SELECT 
            dealer_id,
            dealer_name,
            region,
            state,
            total_revenue,
            total_units_sold,
            transaction_count
        FROM dbw_stihl_analytics.gold.dealer_performance
        {where_clause}
        ORDER BY total_revenue ASC
        LIMIT {top_n}
        """
        
    else:
        return json.dumps({
            "error": f"Unknown query_type: {query_type}",
            "valid_types": ["summary", "top_dealers", "by_region", 
                          "performance_tiers", "bottom_dealers"]
        })
    
    try:
        result = client.execute_query(query)
        return json.dumps({
            "query_type": query_type,
            "filters": {"region": region},
            "data": result,
            "record_count": result.get("row_count", 0)
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# Tool definition for Azure OpenAI
DEALER_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "query_dealer_data",
        "description": "Query STIHL dealer network data for dealer performance, regional distribution, and performance tier analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["summary", "top_dealers", "by_region", 
                            "performance_tiers", "bottom_dealers"],
                    "description": "Type of dealer analysis"
                },
                "region": {
                    "type": "string",
                    "description": "Filter by region (Northeast, Southeast, Midwest, Southwest, West)"
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of results for ranking queries",
                    "default": 10
                }
            },
            "required": ["query_type"]
        }
    }
}
