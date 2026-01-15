"""
Forecast Skill - Predictive analytics for sales projections.
"""
from .base_skill import BaseSkill


class ForecastSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "forecast_analyst"
    
    @property
    def description(self) -> str:
        return "Generate sales forecasts, projections, and seasonal pattern analysis"
    
    @property
    def triggers(self) -> list[str]:
        return [
            # Core forecast keywords (high priority)
            r"\bforecast",  # matches forecast, forecasts, forecasting
            r"\bpredict",   # matches predict, prediction, predicted
            r"\bprojection",
            r"\bproject\b",
            
            # Future-oriented patterns
            r"(next|upcoming|future).*(month|quarter|year)",
            r"(will|expect|should).*(be|hit|reach)",
            r"(what|how much).*(will|expect|likely)",
            
            # Seasonal patterns
            r"\bseason",  # matches season, seasonal, seasonality
            r"(peak|slow|busy).*(time|period|month)",
            r"(busiest|slowest)",
            
            # Projection patterns
            r"(year.end|annual).*(projection|estimate)",
            r"(run.rate|pace|trajectory)",
            r"(on track|ahead|behind)",
        ]
    
    @property
    def tools(self) -> list[str]:
        return ["get_sales_forecast"]
    
    @property
    def system_prompt(self) -> str:
        return """You are a STIHL forecasting analyst. Provide data-driven predictions with uncertainty ranges and assumptions."""
    
    @property
    def priority(self) -> int:
        return 24  # Very high - forecast keyword should win
