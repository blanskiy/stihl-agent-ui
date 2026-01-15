"""
Trend Tools - Analysis for growth patterns and comparisons.

Provides:
- Year-over-year comparisons
- Month-over-month trends
- Growth rate analysis
- Momentum indicators
- Trend direction classification
"""

import json
from agent.databricks_client import DatabricksClient


def analyze_trends(
    trend_type: str,
    metric: str = "revenue",
    category: str = None,
    region: str = None,
    comparison_periods: int = 12
) -> str:
    """
    Analyze sales trends and growth patterns.
    
    Args:
        trend_type: Type of analysis - yoy (year-over-year), mom (month-over-month),
                    growth_rates, momentum, category_trends, regional_trends
        metric: Metric to analyze - revenue, units, transactions
        category: Filter by product category
        region: Filter by region
        comparison_periods: Number of periods to analyze
        
    Returns:
        JSON string with trend analysis results
    """
    client = DatabricksClient()
    
    # Build filters
    filters = []
    if category:
        filters.append(f"category = '{category}'")
    if region:
        filters.append(f"region = '{region}'")
    
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    
    # Map metric to column
    metric_map = {
        "revenue": "total_revenue",
        "units": "total_units",
        "transactions": "transaction_count"
    }
    metric_col = metric_map.get(metric, "total_revenue")
    
    if trend_type == "yoy":
        # Year-over-year comparison
        query = f"""
        WITH yearly_data AS (
            SELECT 
                year,
                month,
                SUM({metric_col}) as value
            FROM dbw_stihl_analytics.gold.monthly_sales
            {where_clause}
            GROUP BY year, month
        ),
        yoy_comparison AS (
            SELECT 
                curr.year,
                curr.month,
                curr.value as current_value,
                prev.value as prior_year_value,
                curr.value - prev.value as yoy_change,
                (curr.value - prev.value) / NULLIF(prev.value, 0) * 100 as yoy_change_pct
            FROM yearly_data curr
            LEFT JOIN yearly_data prev 
                ON curr.year = prev.year + 1 AND curr.month = prev.month
        )
        SELECT 
            year,
            month,
            ROUND(current_value, 2) as current_{metric},
            ROUND(prior_year_value, 2) as prior_year_{metric},
            ROUND(yoy_change, 2) as yoy_change,
            ROUND(yoy_change_pct, 1) as yoy_change_pct,
            CASE 
                WHEN yoy_change_pct > 20 THEN 'Strong Growth'
                WHEN yoy_change_pct > 5 THEN 'Moderate Growth'
                WHEN yoy_change_pct > -5 THEN 'Flat'
                WHEN yoy_change_pct > -20 THEN 'Moderate Decline'
                ELSE 'Sharp Decline'
            END as trend_direction
        FROM yoy_comparison
        WHERE prior_year_value IS NOT NULL
        ORDER BY year DESC, month DESC
        LIMIT {comparison_periods}
        """
        
    elif trend_type == "mom":
        # Month-over-month trends
        query = f"""
        WITH monthly_data AS (
            SELECT 
                year,
                month,
                SUM({metric_col}) as value
            FROM dbw_stihl_analytics.gold.monthly_sales
            {where_clause}
            GROUP BY year, month
            ORDER BY year, month
        ),
        mom_analysis AS (
            SELECT 
                year,
                month,
                value,
                LAG(value) OVER (ORDER BY year, month) as prev_month_value,
                value - LAG(value) OVER (ORDER BY year, month) as mom_change,
                (value - LAG(value) OVER (ORDER BY year, month)) / 
                    NULLIF(LAG(value) OVER (ORDER BY year, month), 0) * 100 as mom_change_pct
            FROM monthly_data
        )
        SELECT 
            year,
            month,
            ROUND(value, 2) as {metric},
            ROUND(prev_month_value, 2) as prev_month,
            ROUND(mom_change, 2) as mom_change,
            ROUND(mom_change_pct, 1) as mom_change_pct,
            CASE 
                WHEN mom_change_pct > 15 THEN 'Surge'
                WHEN mom_change_pct > 5 THEN 'Growth'
                WHEN mom_change_pct > -5 THEN 'Stable'
                WHEN mom_change_pct > -15 THEN 'Decline'
                ELSE 'Drop'
            END as momentum
        FROM mom_analysis
        WHERE prev_month_value IS NOT NULL
        ORDER BY year DESC, month DESC
        LIMIT {comparison_periods}
        """
        
    elif trend_type == "growth_rates":
        # Calculate various growth rates
        query = f"""
        WITH period_data AS (
            SELECT 
                year,
                month,
                SUM({metric_col}) as value
            FROM dbw_stihl_analytics.gold.monthly_sales
            {where_clause}
            GROUP BY year, month
        ),
        growth_calcs AS (
            SELECT 
                year,
                month,
                value,
                -- 3-month moving average
                AVG(value) OVER (ORDER BY year, month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as ma_3m,
                -- 6-month moving average
                AVG(value) OVER (ORDER BY year, month ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) as ma_6m,
                -- Cumulative YTD
                SUM(value) OVER (PARTITION BY year ORDER BY month) as ytd_cumulative,
                -- Prior year same month
                LAG(value, 12) OVER (ORDER BY year, month) as py_value
            FROM period_data
        )
        SELECT 
            year,
            month,
            ROUND(value, 2) as current_{metric},
            ROUND(ma_3m, 2) as moving_avg_3m,
            ROUND(ma_6m, 2) as moving_avg_6m,
            ROUND(ytd_cumulative, 2) as ytd_total,
            ROUND((value - py_value) / NULLIF(py_value, 0) * 100, 1) as yoy_growth_pct,
            ROUND((ma_3m - ma_6m) / NULLIF(ma_6m, 0) * 100, 1) as short_vs_long_trend
        FROM growth_calcs
        ORDER BY year DESC, month DESC
        LIMIT {comparison_periods}
        """
        
    elif trend_type == "momentum":
        # Momentum indicators
        query = f"""
        WITH monthly_data AS (
            SELECT 
                year,
                month,
                SUM({metric_col}) as value
            FROM dbw_stihl_analytics.gold.monthly_sales
            {where_clause}
            GROUP BY year, month
        ),
        momentum_calc AS (
            SELECT 
                year,
                month,
                value,
                AVG(value) OVER (ORDER BY year, month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as ma_3m,
                AVG(value) OVER (ORDER BY year, month ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) as ma_6m,
                LAG(value, 3) OVER (ORDER BY year, month) as value_3m_ago,
                LAG(value, 6) OVER (ORDER BY year, month) as value_6m_ago
            FROM monthly_data
        )
        SELECT 
            year,
            month,
            ROUND(value, 2) as current_{metric},
            ROUND(ma_3m, 2) as short_term_avg,
            ROUND(ma_6m, 2) as long_term_avg,
            CASE WHEN ma_3m > ma_6m THEN 'Bullish' ELSE 'Bearish' END as trend_signal,
            ROUND((value - value_3m_ago) / NULLIF(value_3m_ago, 0) * 100, 1) as momentum_3m_pct,
            ROUND((value - value_6m_ago) / NULLIF(value_6m_ago, 0) * 100, 1) as momentum_6m_pct,
            CASE 
                WHEN ma_3m > ma_6m AND value > ma_3m THEN 'Strong Uptrend'
                WHEN ma_3m > ma_6m THEN 'Uptrend'
                WHEN ma_3m < ma_6m AND value < ma_3m THEN 'Strong Downtrend'
                WHEN ma_3m < ma_6m THEN 'Downtrend'
                ELSE 'Consolidating'
            END as momentum_signal
        FROM momentum_calc
        WHERE value_3m_ago IS NOT NULL
        ORDER BY year DESC, month DESC
        LIMIT {comparison_periods}
        """
        
    elif trend_type == "category_trends":
        # Trends by category
        query = f"""
        WITH category_monthly AS (
            SELECT 
                category,
                year,
                month,
                SUM({metric_col}) as value
            FROM dbw_stihl_analytics.gold.monthly_sales
            {where_clause if where_clause else ''}
            GROUP BY category, year, month
        ),
        category_trends AS (
            SELECT 
                category,
                year,
                month,
                value,
                LAG(value, 12) OVER (PARTITION BY category ORDER BY year, month) as py_value,
                AVG(value) OVER (PARTITION BY category ORDER BY year, month 
                    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as ma_3m
            FROM category_monthly
        )
        SELECT 
            category,
            year,
            month,
            ROUND(value, 2) as current_{metric},
            ROUND((value - py_value) / NULLIF(py_value, 0) * 100, 1) as yoy_change_pct,
            ROUND(ma_3m, 2) as trend_3m_avg,
            CASE 
                WHEN (value - py_value) / NULLIF(py_value, 0) * 100 > 10 THEN 'Growing'
                WHEN (value - py_value) / NULLIF(py_value, 0) * 100 < -10 THEN 'Declining'
                ELSE 'Stable'
            END as category_trend
        FROM category_trends
        WHERE py_value IS NOT NULL
        ORDER BY year DESC, month DESC, value DESC
        LIMIT 50
        """
        
    elif trend_type == "regional_trends":
        # Trends by region
        query = f"""
        WITH regional_monthly AS (
            SELECT 
                region,
                year,
                month,
                SUM({metric_col}) as value
            FROM dbw_stihl_analytics.gold.monthly_sales
            {where_clause if where_clause else ''}
            GROUP BY region, year, month
        ),
        regional_trends AS (
            SELECT 
                region,
                year,
                month,
                value,
                LAG(value, 12) OVER (PARTITION BY region ORDER BY year, month) as py_value,
                SUM(value) OVER (PARTITION BY region, year ORDER BY month) as ytd_value
            FROM regional_monthly
        )
        SELECT 
            region,
            year,
            month,
            ROUND(value, 2) as current_{metric},
            ROUND(py_value, 2) as prior_year_{metric},
            ROUND((value - py_value) / NULLIF(py_value, 0) * 100, 1) as yoy_change_pct,
            ROUND(ytd_value, 2) as ytd_total,
            CASE 
                WHEN (value - py_value) / NULLIF(py_value, 0) * 100 > 15 THEN 'Hot Market'
                WHEN (value - py_value) / NULLIF(py_value, 0) * 100 > 5 THEN 'Growing'
                WHEN (value - py_value) / NULLIF(py_value, 0) * 100 > -5 THEN 'Stable'
                ELSE 'Needs Attention'
            END as market_status
        FROM regional_trends
        WHERE py_value IS NOT NULL
        ORDER BY year DESC, month DESC, yoy_change_pct DESC
        LIMIT 50
        """
        
    else:
        return json.dumps({
            "error": f"Unknown trend_type: {trend_type}",
            "valid_types": ["yoy", "mom", "growth_rates", "momentum", 
                          "category_trends", "regional_trends"]
        })
    
    try:
        result = client.execute_query(query)
        return json.dumps({
            "trend_type": trend_type,
            "metric": metric,
            "filters": {"category": category, "region": region},
            "periods_analyzed": comparison_periods,
            "data": result,
            "record_count": result.get("row_count", 0)
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# Tool definition for Azure OpenAI
TREND_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "analyze_trends",
        "description": "Analyze sales trends including year-over-year comparisons, month-over-month changes, growth rates, and momentum indicators. Use for questions about trends, growth, comparisons, or market direction.",
        "parameters": {
            "type": "object",
            "properties": {
                "trend_type": {
                    "type": "string",
                    "enum": ["yoy", "mom", "growth_rates", "momentum", 
                            "category_trends", "regional_trends"],
                    "description": "Type of trend analysis: yoy (year-over-year), mom (month-over-month), growth_rates, momentum, category_trends, regional_trends"
                },
                "metric": {
                    "type": "string",
                    "enum": ["revenue", "units", "transactions"],
                    "description": "Metric to analyze",
                    "default": "revenue"
                },
                "category": {
                    "type": "string",
                    "description": "Filter by product category"
                },
                "region": {
                    "type": "string",
                    "description": "Filter by region"
                },
                "comparison_periods": {
                    "type": "integer",
                    "description": "Number of periods to analyze",
                    "default": 12
                }
            },
            "required": ["trend_type"]
        }
    }
}
