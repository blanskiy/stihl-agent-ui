"""
Dealer Skill - SQL-based dealer network analytics.
"""
from .base_skill import BaseSkill


class DealerSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "dealer_analyst"
    
    @property
    def description(self) -> str:
        return "Analyze dealer network including performance, coverage, dealer types, and territory gaps"
    
    @property
    def triggers(self) -> list[str]:
        return [
            # Core dealer keywords (high priority)
            r"\bdealer",  # matches dealer, dealers, dealership
            r"\breseller",
            r"\bdistributor",
            r"\bpartner\b(?!.*product)",  # partner but not "partner product"
            
            # Network patterns
            r"(network|coverage|territory|gap)",
            r"(flagship|authorized|service.center)",
            
            # Performance with dealer context
            r"(top|best|worst).*(dealer|partner|reseller)",
            r"(dealer|partner).*(performance|ranking|tier)",
        ]
    
    @property
    def tools(self) -> list[str]:
        return ["query_dealer_data"]
    
    @property
    def system_prompt(self) -> str:
        return """You are a STIHL dealer network analyst. Analyze dealer performance, coverage, and identify opportunities."""
    
    @property
    def priority(self) -> int:
        return 22  # Higher than most to catch dealer queries
