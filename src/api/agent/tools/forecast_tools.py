"""
Forecast Tools - Predictive analytics for sales projections.

Provides:
- Monthly/quarterly sales forecasts using moving averages
- Seasonal pattern analysis
- Year-end projections
- Category and regional forecasts
"""

import json
from agent.databricks_client import DatabricksClient


def get_sales_forecast(
    forecast_type: str = "monthly",
    category: str = None,
    region: str = None,
    periods_ahead: int = 3,
    method: str = "moving_avg"
) -> str:
    """
    Generate sales forecasts based on historical patterns.
    
    Args:
        forecast_type: Type of forecast - monthly, quarterly, year_end, seasonal
        category: Filter by product category
        region: Filter by region
        periods_ahead: Number of periods to forecast (1-6)
        method: Forecasting method - moving_avg, trend_projection, seasonal_decomp
        
    Returns:
        JSON string with forecast results
    """
    client = DatabricksClient()
    
    # Validate periods
    periods_ahead = min(max(periods_ahead, 1), 6)
    
    # Build filters
    filters = []
    if category:
        filters.append(f"category = '{category}'")
    if region:
        filters.append(f"region = '{region}'")
    
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    group_cols = []
    if category:
        group_cols.append("category")
    if region:
        group_cols.append("region")
    
    if forecast_type == "monthly":
        # Monthly forecast using 3-month moving average
        query = f"""
        WITH monthly_data AS (
            SELECT 
                year,
                month,
                {', '.join(group_cols) + ',' if group_cols else ''}
                SUM(total_revenue) as revenue,
                SUM(total_units) as units
            FROM dbw_stihl_analytics.gold.monthly_sales
            {where_clause}
            GROUP BY year, month{', ' + ', '.join(group_cols) if group_cols else ''}
            ORDER BY year DESC, month DESC
            LIMIT 12
        ),
        recent_avg AS (
            SELECT 
                {', '.join(group_cols) + ',' if group_cols else ''}
                AVG(revenue) as avg_monthly_revenue,
                AVG(units) as avg_monthly_units,
                STDDEV(revenue) as revenue_stddev,
                MAX(year * 100 + month) as last_period
            FROM monthly_data
            WHERE (year * 12 + month) >= (
                SELECT MAX(year * 12 + month) - 2 FROM monthly_data
            )
            {('GROUP BY ' + ', '.join(group_cols)) if group_cols else ''}
        )
        SELECT 
            {', '.join(group_cols) + ',' if group_cols else ''}
            last_period,
            ROUND(avg_monthly_revenue, 2) as forecast_monthly_revenue,
            ROUND(avg_monthly_units, 0) as forecast_monthly_units,
            ROUND(revenue_stddev, 2) as revenue_uncertainty,
            ROUND(avg_monthly_revenue * {periods_ahead}, 2) as total_forecast_revenue,
            {periods_ahead} as periods_forecast
        FROM recent_avg
        """
        
    elif forecast_type == "quarterly":
        # Quarterly forecast with trend
        query = f"""
        WITH quarterly_data AS (
            SELECT 
                year,
                CEIL(month / 3.0) as quarter,
                {', '.join(group_cols) + ',' if group_cols else ''}
                SUM(total_revenue) as revenue,
                SUM(total_units) as units
            FROM dbw_stihl_analytics.gold.monthly_sales
            {where_clause}
            GROUP BY year, CEIL(month / 3.0){', ' + ', '.join(group_cols) if group_cols else ''}
        ),
        quarterly_trend AS (
            SELECT 
                {', '.join(group_cols) + ',' if group_cols else ''}
                year,
                quarter,
                revenue,
                units,
                LAG(revenue) OVER (
                    {('PARTITION BY ' + ', '.join(group_cols)) if group_cols else ''} 
                    ORDER BY year, quarter
                ) as prev_revenue,
                AVG(revenue) OVER (
                    {('PARTITION BY ' + ', '.join(group_cols)) if group_cols else ''} 
                    ORDER BY year, quarter ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
                ) as ma_4q_revenue
            FROM quarterly_data
        )
        SELECT 
            {', '.join(group_cols) + ',' if group_cols else ''}
            year,
            CAST(quarter AS INT) as quarter,
            ROUND(revenue, 2) as actual_revenue,
            ROUND(ma_4q_revenue, 2) as moving_avg_4q,
            ROUND((revenue - prev_revenue) / NULLIF(prev_revenue, 0) * 100, 1) as qoq_growth_pct,
            ROUND(ma_4q_revenue * 1.0, 2) as next_quarter_forecast
        FROM quarterly_trend
        WHERE year >= 2024
        ORDER BY year DESC, quarter DESC
        LIMIT 8
        """
        
    elif forecast_type == "year_end":
        # Year-end projection based on YTD run rate
        query = f"""
        WITH ytd_data AS (
            SELECT 
                year,
                {', '.join(group_cols) + ',' if group_cols else ''}
                SUM(total_revenue) as ytd_revenue,
                SUM(total_units) as ytd_units,
                MAX(month) as months_complete
            FROM dbw_stihl_analytics.gold.monthly_sales
            {where_clause}
            GROUP BY year{', ' + ', '.join(group_cols) if group_cols else ''}
        )
        SELECT 
            year,
            {', '.join(group_cols) + ',' if group_cols else ''}
            ROUND(ytd_revenue, 2) as ytd_revenue,
            ytd_units,
            months_complete,
            ROUND(ytd_revenue / months_complete * 12, 2) as projected_annual_revenue,
            ROUND(ytd_units / months_complete * 12, 0) as projected_annual_units,
            ROUND((ytd_revenue / months_complete * 12) - ytd_revenue, 2) as remaining_forecast
        FROM ytd_data
        WHERE months_complete > 0
        ORDER BY year DESC
        """
        
    elif forecast_type == "seasonal":
        # Seasonal pattern analysis
        query = f"""
        WITH monthly_patterns AS (
            SELECT 
                month,
                {', '.join(group_cols) + ',' if group_cols else ''}
                AVG(total_revenue) as avg_revenue,
                MIN(total_revenue) as min_revenue,
                MAX(total_revenue) as max_revenue,
                STDDEV(total_revenue) as revenue_stddev,
                COUNT(*) as data_points
            FROM dbw_stihl_analytics.gold.monthly_sales
            {where_clause}
            GROUP BY month{', ' + ', '.join(group_cols) if group_cols else ''}
        ),
        annual_avg AS (
            SELECT 
                {', '.join(group_cols) + ',' if group_cols else ''}
                AVG(avg_revenue) as overall_monthly_avg
            FROM monthly_patterns
            {('GROUP BY ' + ', '.join(group_cols)) if group_cols else ''}
        )
        SELECT 
            mp.month,
            {', '.join(['mp.' + c for c in group_cols]) + ',' if group_cols else ''}
            ROUND(mp.avg_revenue, 2) as avg_revenue,
            ROUND(mp.avg_revenue / aa.overall_monthly_avg * 100, 1) as seasonal_index,
            CASE 
                WHEN mp.avg_revenue > aa.overall_monthly_avg * 1.15 THEN 'Peak Season'
                WHEN mp.avg_revenue < aa.overall_monthly_avg * 0.85 THEN 'Low Season'
                ELSE 'Normal'
            END as season_type,
            ROUND(mp.revenue_stddev, 2) as variability,
            mp.data_points
        FROM monthly_patterns mp
        CROSS JOIN annual_avg aa
        ORDER BY mp.month
        """
        
    else:
        return json.dumps({
            "error": f"Unknown forecast_type: {forecast_type}",
            "valid_types": ["monthly", "quarterly", "year_end", "seasonal"]
        })
    
    try:
        result = client.execute_query(query)
        return json.dumps({
            "forecast_type": forecast_type,
            "method": method,
            "periods_ahead": periods_ahead,
            "filters": {"category": category, "region": region},
            "data": result,
            "record_count": result.get("row_count", 0),
            "disclaimer": "Forecasts based on historical patterns. Actual results may vary."
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# Tool definition for Azure OpenAI
FORECAST_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "get_sales_forecast",
        "description": "Generate sales forecasts and projections based on historical patterns. Use for questions about future sales, projections, predictions, or seasonal patterns.",
        "parameters": {
            "type": "object",
            "properties": {
                "forecast_type": {
                    "type": "string",
                    "enum": ["monthly", "quarterly", "year_end", "seasonal"],
                    "description": "Type of forecast: monthly (next months), quarterly (Q trends), year_end (annual projection), seasonal (pattern analysis)"
                },
                "category": {
                    "type": "string",
                    "description": "Filter by product category"
                },
                "region": {
                    "type": "string",
                    "description": "Filter by region"
                },
                "periods_ahead": {
                    "type": "integer",
                    "description": "Number of periods to forecast (1-6)",
                    "default": 3
                }
            },
            "required": ["forecast_type"]
        }
    }
}
