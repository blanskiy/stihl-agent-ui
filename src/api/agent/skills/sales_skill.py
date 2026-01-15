"""
Sales Skill - SQL-based sales analytics.
"""
from .base_skill import BaseSkill


class SalesSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "sales_analyst"

    @property
    def description(self) -> str:
        return "Analyze sales performance including revenue, trends, rankings, and regional breakdowns"

    @property
    def triggers(self) -> list[str]:
        return [
            # Revenue patterns (flexible order)
            r"\brevenue\b",
            r"\bsales\b(?!.*forecast)",  # sales but not "sales forecast"
            r"\bsold\b",
            r"how much.*(made|earned)",
            
            # Ranking patterns (exclude dealer)
            r"(top|best|worst|bottom).*(product|region|category|seller)(?!.*dealer)",
            r"(rank|ranking|leaderboard)",

            # Time period with sales context
            r"(ytd|year.to.date|mtd|qtd)",
            r"(last|previous|this).*(month|quarter|year).*(revenue|sales|total)",
            r"(2024|2025|q1|q2|q3|q4).*(revenue|sales|total)",

            # Breakdown patterns (flexible order)
            r"(breakdown|split|distribution).*(by|of)",
            r"(by|per).*(region|category|product).*(sales|revenue)?",
            r"(regional|category).*(breakdown|performance|sales)",
        ]

    @property
    def tools(self) -> list[str]:
        return ["query_sales_data"]

    @property
    def system_prompt(self) -> str:
        return """You are a STIHL sales analyst. Provide data-driven sales insights with context and recommendations."""

    @property
    def priority(self) -> int:
        return 15
