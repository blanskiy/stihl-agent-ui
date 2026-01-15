"""
Trend Skill - Growth analysis and comparisons.
"""
from .base_skill import BaseSkill


class TrendSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "trend_analyst"
    
    @property
    def description(self) -> str:
        return "Analyze growth trends, YoY/MoM comparisons, and momentum indicators"
    
    @property
    def triggers(self) -> list[str]:
        return [
            # YoY/MoM keywords (high priority)
            r"\byoy\b",
            r"\by/y\b",
            r"\bmom\b",
            r"\bm/m\b",
            r"year.over.year",
            r"month.over.month",
            
            # Comparison patterns
            r"(compare|vs|versus).*(last|prior|previous).*(year|month)",
            r"(this|current).*(year|month).*(vs|versus|compared)",
            r"how.*(changed|different|grown|declined)",
            
            # Growth patterns
            r"\bgrowth",
            r"\bgrowing\b",
            r"\bdecline",
            r"\bdeclining\b",
            r"(up|down|increase|decrease).+\d+\s*%",
            
            # Momentum patterns
            r"\bmomentum",
            r"\btrend",  # catches trend, trends, trended, trending
            r"(accelerat|decelerat|slowing|picking up)",
        ]
    
    @property
    def tools(self) -> list[str]:
        return ["analyze_trends"]
    
    @property
    def system_prompt(self) -> str:
        return """You are a STIHL trend analyst. Provide growth insights with context and identify momentum shifts."""
    
    @property
    def priority(self) -> int:
        return 19
