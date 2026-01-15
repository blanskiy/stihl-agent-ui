"""
Proactive Insights tools for STIHL Analytics Agent.
Updated to match actual Databricks schema.
"""

import json
from typing import Optional
from datetime import datetime

from agent.databricks_client import execute_query
from config.settings import get_config


def get_proactive_insights(
    insight_types: Optional[list[str]] = None,
    severity_filter: Optional[str] = None,
    max_insights: int = 5
) -> str:
    """
    Retrieve proactive insights - anomalies, alerts, and trends worth attention.

    IMPORTANT: Call this at the START of conversations when the user asks
    general questions like "What should I know?" or "Any updates?" or just "Hi".

    Args:
        insight_types: Filter by type (anomaly, stockout_risk, trend, forecast_alert, opportunity)
        severity_filter: Filter by urgency (critical, warning, info)
        max_insights: Maximum insights to return (default 5)

    Returns:
        JSON with prioritized insights
    """
    config = get_config()
    catalog = config.databricks.catalog
    
    # Check if proactive_insights table exists, if not generate insights on-the-fly
    try:
        insights_table = f"{catalog}.gold.proactive_insights"
        
        filters = ["is_active = true"]
        if insight_types:
            types_str = ", ".join([f"'{t}'" for t in insight_types])
            filters.append(f"insight_type IN ({types_str})")
        if severity_filter:
            filters.append(f"severity = '{severity_filter}'")
        filter_clause = " AND ".join(filters)

        query = f"""
        SELECT 
            insight_id, insight_type, severity, title, description,
            affected_entity, metric_name, metric_value, expected_value,
            deviation_pct, detected_at, recommended_action
        FROM {insights_table}
        WHERE {filter_clause}
        ORDER BY 
            CASE severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
            ABS(deviation_pct) DESC
        LIMIT {max_insights}
        """

        result = execute_query(query)
        
        if result.get("success") and result.get("data"):
            result["narrative_summary"] = _format_insights_narrative(result["data"])
            return json.dumps(result, default=str)
    except:
        pass
    
    # Fallback: Generate insights from current data
    return _generate_realtime_insights(max_insights)


def _generate_realtime_insights(max_insights: int = 5) -> str:
    """Generate insights on-the-fly from current data."""
    config = get_config()
    catalog = config.databricks.catalog
    
    insights = []
    
    # Check for stockouts
    stockout_query = f"""
    SELECT product_name, category, region, COUNT(*) as locations
    FROM {catalog}.gold.inventory_status
    WHERE quantity_on_hand = 0
    GROUP BY product_name, category, region
    ORDER BY locations DESC
    LIMIT 3
    """
    stockout_result = execute_query(stockout_query)
    if stockout_result.get("success") and stockout_result.get("data"):
        for row in stockout_result["data"]:
            insights.append({
                "insight_type": "stockout_risk",
                "severity": "critical",
                "title": f"STOCKOUT: {row['product_name']}",
                "description": f"{row['product_name']} is out of stock in {row['region']}",
                "affected_entity": row["product_name"],
                "recommended_action": f"Reorder {row['product_name']} immediately"
            })
    
    # Check for critical inventory (using uppercase status)
    critical_query = f"""
    SELECT product_name, category, region, days_of_supply, quantity_on_hand
    FROM {catalog}.gold.inventory_status
    WHERE status = 'CRITICAL' AND quantity_on_hand > 0
    ORDER BY days_of_supply ASC
    LIMIT 3
    """
    critical_result = execute_query(critical_query)
    if critical_result.get("success") and critical_result.get("data"):
        for row in critical_result["data"]:
            insights.append({
                "insight_type": "stockout_risk",
                "severity": "warning",
                "title": f"Critical Stock: {row['product_name']}",
                "description": f"{row['product_name']} has only {row['days_of_supply']:.0f} days of supply in {row['region']}",
                "affected_entity": row["product_name"],
                "metric_value": row["days_of_supply"],
                "recommended_action": f"Review reorder for {row['product_name']}"
            })
    
    # Check for sales anomalies - get most recent month with data
    sales_query = f"""
    WITH recent_month AS (
        SELECT MAX(year * 100 + month) as max_period FROM {catalog}.gold.monthly_sales
    )
    SELECT category, region, SUM(total_revenue) as revenue, SUM(total_units) as units
    FROM {catalog}.gold.monthly_sales m, recent_month r
    WHERE m.year * 100 + m.month = r.max_period
    GROUP BY category, region
    ORDER BY revenue DESC
    LIMIT 2
    """
    sales_result = execute_query(sales_query)
    if sales_result.get("success") and sales_result.get("data"):
        for row in sales_result["data"]:
            insights.append({
                "insight_type": "opportunity",
                "severity": "info",
                "title": f"Strong Sales: {row['category']} in {row['region']}",
                "description": f"{row['category']} generated ${row['revenue']:,.0f} in {row['region']}",
                "affected_entity": row["category"],
                "metric_value": row["revenue"],
                "recommended_action": "Consider increasing inventory for this category"
            })
    
    # Limit and format
    insights = insights[:max_insights]
    
    return json.dumps({
        "success": True,
        "row_count": len(insights),
        "data": insights,
        "narrative_summary": _format_insights_narrative(insights),
        "source": "realtime_analysis"
    }, default=str)


def _format_insights_narrative(insights: list[dict]) -> str:
    """Convert insights to natural language summary."""
    if not insights:
        return "No significant insights requiring attention at this time."

    narratives = []
    for insight in insights:
        emoji = {"critical": "🔴", "warning": "🟡", "info": "🟢"}.get(insight.get("severity", "info"), "ℹ️")
        narratives.append(f"{emoji} **{insight.get('title', 'Insight')}**: {insight.get('description', '')}")

    return "\n".join(narratives)


def _parse_time_period(time_period: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """
    Parse a time period string into year and month.
    
    Supports formats:
    - "2024-03" or "2024-3"
    - "March 2024" or "Mar 2024"
    - "3/2024"
    
    Returns:
        Tuple of (year, month) or (None, None) if not parseable
    """
    if not time_period:
        return None, None
    
    time_period = time_period.strip()
    
    # Try YYYY-MM format
    if "-" in time_period:
        parts = time_period.split("-")
        if len(parts) == 2:
            try:
                year = int(parts[0])
                month = int(parts[1])
                if 1 <= month <= 12 and 2000 <= year <= 2100:
                    return year, month
            except ValueError:
                pass
    
    # Try MM/YYYY format
    if "/" in time_period:
        parts = time_period.split("/")
        if len(parts) == 2:
            try:
                month = int(parts[0])
                year = int(parts[1])
                if 1 <= month <= 12 and 2000 <= year <= 2100:
                    return year, month
            except ValueError:
                pass
    
    # Try "Month YYYY" format
    month_names = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12,
    }
    
    words = time_period.lower().split()
    for word in words:
        if word in month_names:
            month = month_names[word]
            # Find year
            for other_word in words:
                try:
                    year = int(other_word)
                    if 2000 <= year <= 2100:
                        return year, month
                except ValueError:
                    continue
    
    return None, None


def detect_anomalies_realtime(
    metric: str,
    entity_type: str,
    time_period: Optional[str] = None,
    threshold_std: float = 2.0
) -> str:
    """
    Run real-time anomaly detection on specified metrics.
    
    Compares a specific month's values against historical monthly averages
    to detect statistically significant deviations.

    Args:
        metric: Metric to analyze (revenue, units_sold, stock_level)
        entity_type: Grouping dimension (category, region)
        time_period: Month to analyze (e.g., "2024-03", "March 2024"). Defaults to most recent month.
        threshold_std: Standard deviations for anomaly (default 2.0)

    Returns:
        JSON with detected anomalies ranked by deviation
    """
    config = get_config()
    catalog = config.databricks.catalog

    # For stock_level, use inventory table (point-in-time, not monthly)
    if metric == "stock_level":
        return _detect_inventory_anomalies(catalog, entity_type, threshold_std)
    
    # Parse time_period if provided
    target_year, target_month = _parse_time_period(time_period)

    # For revenue and units_sold, use monthly_sales with proper time comparison
    metric_column = "total_revenue" if metric == "revenue" else "total_units"
    
    # Support category, region, or combined category_region
    if entity_type == "category_region":
        group_col = "category || ' in ' || region"
        group_by = "category, region"
    elif entity_type == "category":
        group_col = "category"
        group_by = "category"
    else:
        group_col = "region"
        group_by = "region"

    # Build the target month clause
    if target_year and target_month:
        target_clause = f"m.year = {target_year} AND m.month = {target_month}"
        historical_clause = f"(m.year < {target_year} OR (m.year = {target_year} AND m.month < {target_month}))"
        period_desc = f"{target_year}-{target_month:02d}"
    else:
        # Default to most recent month
        target_clause = "m.year * 100 + m.month = (SELECT MAX(year * 100 + month) FROM monthly_data)"
        historical_clause = "m.year * 100 + m.month < (SELECT MAX(year * 100 + month) FROM monthly_data)"
        period_desc = "most recent month"

    query = f"""
    WITH monthly_data AS (
        -- Get monthly aggregates by entity
        SELECT 
            {group_col} as entity,
            year,
            month,
            SUM({metric_column}) as monthly_value
        FROM {catalog}.gold.monthly_sales
        GROUP BY {group_by}, year, month
    ),
    historical_stats AS (
        -- Calculate baseline from months BEFORE the target month
        SELECT 
            entity,
            AVG(monthly_value) as mean_value,
            STDDEV(monthly_value) as std_value,
            COUNT(*) as num_months
        FROM monthly_data m
        WHERE {historical_clause}
        GROUP BY entity
        HAVING COUNT(*) >= 2  -- Need at least 2 months of history
    ),
    target_month_data AS (
        -- Get the target month's values
        SELECT 
            entity,
            monthly_value as current_value,
            year as target_year,
            month as target_month
        FROM monthly_data m
        WHERE {target_clause}
    )
    SELECT 
        t.entity,
        t.target_year,
        t.target_month,
        t.current_value,
        h.mean_value as historical_avg,
        h.std_value as historical_std,
        h.num_months as months_of_history,
        ROUND((t.current_value - h.mean_value) / NULLIF(h.std_value, 0), 2) as z_score,
        ROUND((t.current_value - h.mean_value) / NULLIF(h.mean_value, 0) * 100, 1) as pct_deviation,
        CASE 
            WHEN (t.current_value - h.mean_value) / NULLIF(h.std_value, 0) > {threshold_std * 1.5} THEN 'critical_high'
            WHEN (t.current_value - h.mean_value) / NULLIF(h.std_value, 0) < -{threshold_std * 1.5} THEN 'critical_low'
            WHEN (t.current_value - h.mean_value) / NULLIF(h.std_value, 0) > {threshold_std} THEN 'warning_high'
            WHEN (t.current_value - h.mean_value) / NULLIF(h.std_value, 0) < -{threshold_std} THEN 'warning_low'
            ELSE 'normal'
        END as anomaly_status
    FROM target_month_data t
    JOIN historical_stats h ON t.entity = h.entity
    WHERE ABS((t.current_value - h.mean_value) / NULLIF(h.std_value, 0)) > {threshold_std}
    ORDER BY ABS((t.current_value - h.mean_value) / NULLIF(h.std_value, 0)) DESC
    LIMIT 10
    """

    result = execute_query(query)
    result["metric_analyzed"] = metric
    result["entity_type"] = entity_type
    result["time_period"] = period_desc
    result["threshold_std"] = threshold_std
    result["comparison"] = f"{period_desc} vs historical monthly average"
    return json.dumps(result, default=str)


def _detect_inventory_anomalies(catalog: str, entity_type: str, threshold_std: float) -> str:
    """Detect anomalies in current inventory levels."""
    group_col = "category" if entity_type == "category" else "region"
    
    query = f"""
    WITH entity_stats AS (
        SELECT 
            {group_col} as entity,
            SUM(quantity_on_hand) as total_stock,
            AVG(days_of_supply) as avg_dos,
            COUNT(*) as num_items,
            SUM(CASE WHEN status = 'CRITICAL' THEN 1 ELSE 0 END) as critical_count,
            SUM(CASE WHEN status = 'LOW' THEN 1 ELSE 0 END) as low_count
        FROM {catalog}.gold.inventory_status
        GROUP BY {group_col}
    ),
    overall_stats AS (
        SELECT 
            AVG(total_stock) as mean_stock,
            STDDEV(total_stock) as std_stock,
            AVG(avg_dos) as mean_dos,
            STDDEV(avg_dos) as std_dos
        FROM entity_stats
    )
    SELECT 
        e.entity,
        e.total_stock as current_stock,
        o.mean_stock as avg_stock_across_entities,
        e.avg_dos as days_of_supply,
        o.mean_dos as avg_dos_across_entities,
        e.critical_count,
        e.low_count,
        ROUND((e.total_stock - o.mean_stock) / NULLIF(o.std_stock, 0), 2) as stock_z_score,
        ROUND((e.avg_dos - o.mean_dos) / NULLIF(o.std_dos, 0), 2) as dos_z_score,
        CASE 
            WHEN e.avg_dos < 7 THEN 'critical_low'
            WHEN e.avg_dos < 14 THEN 'warning_low'
            WHEN e.avg_dos > 60 THEN 'warning_high'
            ELSE 'normal'
        END as anomaly_status
    FROM entity_stats e, overall_stats o
    WHERE e.avg_dos < 14 OR e.avg_dos > 60 OR e.critical_count > 0
    ORDER BY e.avg_dos ASC
    LIMIT 10
    """
    
    result = execute_query(query)
    result["metric_analyzed"] = "stock_level"
    result["entity_type"] = entity_type
    result["threshold_std"] = threshold_std
    result["comparison"] = "Current inventory levels across entities"
    return json.dumps(result, default=str)


def get_daily_briefing() -> str:
    """
    Generate comprehensive daily briefing for the user.
    Call when user starts conversation or asks for overview.

    Returns:
        JSON with structured daily briefing
    """
    config = get_config()
    catalog = config.databricks.catalog

    # Get key metrics
    metrics_query = f"""
    SELECT 'total_revenue' as metric, SUM(total_revenue) as value
    FROM {catalog}.gold.monthly_sales
    UNION ALL
    SELECT 'stockouts' as metric, COUNT(*) as value
    FROM {catalog}.gold.inventory_status WHERE quantity_on_hand = 0
    UNION ALL
    SELECT 'critical_stock' as metric, COUNT(*) as value
    FROM {catalog}.gold.inventory_status WHERE status = 'CRITICAL' AND quantity_on_hand > 0
    UNION ALL
    SELECT 'low_stock' as metric, COUNT(*) as value
    FROM {catalog}.gold.inventory_status WHERE status = 'LOW'
    """

    metrics_result = execute_query(metrics_query)
    insights_result = json.loads(get_proactive_insights(max_insights=3))

    briefing = {
        "generated_at": datetime.now().isoformat(),
        "key_metrics": metrics_result.get("data", []),
        "top_insights": insights_result.get("data", []),
        "narrative": _generate_briefing_narrative(
            metrics_result.get("data", []),
            insights_result.get("data", [])
        )
    }
    return json.dumps(briefing, default=str)


def _generate_briefing_narrative(metrics: list, insights: list) -> str:
    """Generate natural language briefing."""
    parts = ["**Daily Briefing**\n"]

    metrics_dict = {m.get("metric"): m.get("value", 0) for m in metrics}
    
    if metrics_dict.get("stockouts", 0) > 0:
        parts.append(f"⚠️ {int(metrics_dict['stockouts'])} products currently out of stock")
    if metrics_dict.get("critical_stock", 0) > 0:
        parts.append(f"🔴 {int(metrics_dict['critical_stock'])} products with critical inventory")
    if metrics_dict.get("low_stock", 0) > 0:
        parts.append(f"🟡 {int(metrics_dict['low_stock'])} products with low inventory")
    if metrics_dict.get("total_revenue", 0) > 0:
        parts.append(f"💰 Total revenue: ${metrics_dict['total_revenue']:,.0f}")

    if insights:
        parts.append(f"\n**Top Priority:** {insights[0].get('title', 'No urgent items')}")

    return "\n".join(parts)


# Tool definitions for Azure AI Foundry
PROACTIVE_INSIGHTS_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "get_proactive_insights",
        "description": "Get proactive insights - anomalies, alerts, and trends. Call at conversation START.",
        "parameters": {
            "type": "object",
            "properties": {
                "insight_types": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["anomaly", "stockout_risk", "trend", "forecast_alert", "opportunity"]}
                },
                "severity_filter": {"type": "string", "enum": ["critical", "warning", "info"]},
                "max_insights": {"type": "integer"}
            }
        }
    }
}

DETECT_ANOMALIES_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "detect_anomalies_realtime",
        "description": "Run anomaly detection comparing a specific month vs historical average. Can analyze any month in the data. Use category_region for most detailed analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "enum": ["revenue", "units_sold", "stock_level"], "description": "Metric to analyze"},
                "entity_type": {"type": "string", "enum": ["category", "region", "category_region"], "description": "How to group: 'category', 'region', or 'category_region' for detailed analysis like 'Chainsaws in Southwest'"},
                "time_period": {"type": "string", "description": "Month to analyze (e.g., '2024-03', 'March 2024'). Defaults to most recent month if not specified."},
                "threshold_std": {"type": "number", "description": "Standard deviations threshold (default 2.0)"}
            },
            "required": ["metric", "entity_type"]
        }
    }
}

DAILY_BRIEFING_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "get_daily_briefing",
        "description": "Generate comprehensive daily briefing with key metrics and insights.",
        "parameters": {"type": "object", "properties": {}}
    }
}
