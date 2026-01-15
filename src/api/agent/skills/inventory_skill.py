"""
Inventory Skill - SQL-based inventory analytics.
"""
from .base_skill import BaseSkill


class InventorySkill(BaseSkill):
    @property
    def name(self) -> str:
        return "inventory_analyst"

    @property
    def description(self) -> str:
        return "Analyze inventory levels, stockouts, and days of supply"

    @property
    def triggers(self) -> list[str]:
        return [
            # Core inventory keywords
            r"\binventory",
            r"\bstock\b",
            r"\bstockout",
            r"\bstock.?out",
            
            # Stock level patterns - more specific
            r"(low|critical|out of).*(stock|inventory)",
            r"running low",
            r"(in stock|on hand)",
            r"how (much|many).*(inventory|stock|left|remaining)",
            
            # Days of supply
            r"days.*(of)?.*(supply|inventory)",
            r"(how long|when).*(last|run out)",
            
            # Warehouse patterns
            r"warehouse",
            r"distribution.center",
            
            # Alert patterns
            r"(restock|reorder|replenish)",
            r"(critical|low|normal).*(status|level)",
        ]

    @property
    def tools(self) -> list[str]:
        return ["query_inventory_data"]

    @property
    def system_prompt(self) -> str:
        return """You are a STIHL inventory analyst. Monitor stock health, identify risks, and suggest reorder actions."""

    @property
    def priority(self) -> int:
        return 17
