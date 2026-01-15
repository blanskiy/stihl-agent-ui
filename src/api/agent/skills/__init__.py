"""
Skills package for STIHL Analytics Agent.

Skills provide domain-specific query routing and prompt enhancement.
"""
from .base_skill import BaseSkill, SkillMatch
from .router import SkillRouter, get_router, route_query

# Import all skills for registration
from .product_skill import ProductSkill
from .sales_skill import SalesSkill
from .inventory_skill import InventorySkill
from .insights_skill import InsightsSkill
from .dealer_skill import DealerSkill
from .forecast_skill import ForecastSkill
from .trend_skill import TrendSkill

__all__ = [
    # Base classes
    "BaseSkill",
    "SkillMatch",
    
    # Router
    "SkillRouter",
    "get_router",
    "route_query",
    
    # Skills
    "ProductSkill",
    "SalesSkill",
    "InventorySkill",
    "InsightsSkill",
    "DealerSkill",
    "ForecastSkill",
    "TrendSkill",
]
