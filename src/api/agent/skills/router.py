"""
Skill Router - Routes queries to appropriate skills.

The router evaluates user queries against all registered skills
and returns the best match based on pattern matching and confidence scores.

Routing Strategy:
1. Check all skills for pattern matches
2. Sort by confidence and priority
3. Return best match or None (falls back to general agent)
"""
import logging
from typing import Optional
from .base_skill import BaseSkill, SkillMatch
from .product_skill import ProductSkill
from .sales_skill import SalesSkill
from .inventory_skill import InventorySkill
from .insights_skill import InsightsSkill
from .dealer_skill import DealerSkill
from .forecast_skill import ForecastSkill
from .trend_skill import TrendSkill
from .replenishment_skill import ReplenishmentSkill

logger = logging.getLogger(__name__)


class SkillRouter:
    """
    Routes user queries to the most appropriate skill.

    Usage:
        router = SkillRouter()
        match = router.route("What chainsaw is best for professionals?")
        if match:
            skill = router.get_skill(match.skill_name)
            # Use skill.tools and skill.system_prompt
    """

    def __init__(self):
        """Initialize router with all available skills."""
        self._skills: dict[str, BaseSkill] = {}
        self._register_default_skills()

    def _register_default_skills(self):
        """Register the default set of STIHL Analytics skills."""
        # Core skills
        self.register(ProductSkill())
        self.register(SalesSkill())
        self.register(InventorySkill())
        self.register(InsightsSkill())
        
        # Extended skills
        self.register(DealerSkill())
        self.register(ForecastSkill())
        self.register(TrendSkill())
        self.register(ReplenishmentSkill())

    def register(self, skill: BaseSkill):
        """
        Register a skill with the router.

        Args:
            skill: Skill instance to register
        """
        self._skills[skill.name] = skill
        logger.debug(f"Registered skill: {skill.name}")

    def unregister(self, skill_name: str):
        """
        Remove a skill from the router.

        Args:
            skill_name: Name of skill to remove
        """
        if skill_name in self._skills:
            del self._skills[skill_name]
            logger.debug(f"Unregistered skill: {skill_name}")

    def get_skill(self, skill_name: str) -> Optional[BaseSkill]:
        """
        Get a skill by name.

        Args:
            skill_name: Name of the skill

        Returns:
            Skill instance or None if not found
        """
        return self._skills.get(skill_name)

    @property
    def skills(self) -> list[BaseSkill]:
        """Get all registered skills sorted by priority."""
        return sorted(
            self._skills.values(),
            key=lambda s: s.priority,
            reverse=True
        )

    def route(self, query: str) -> Optional[SkillMatch]:
        """
        Route a query to the best matching skill.

        Args:
            query: User's natural language query

        Returns:
            SkillMatch with skill info, or None if no match
        """
        matches: list[SkillMatch] = []

        # Check all skills for matches
        for skill in self.skills:
            match = skill.matches(query)
            if match:
                matches.append(match)
                print(f"  📋 Matched: {skill.name} (confidence: {match.confidence:.2f}, priority: {skill.priority})")
                logger.debug(f"Query matched {skill.name} with confidence {match.confidence}")

        if not matches:
            logger.debug(f"No skill match for query: {query[:50]}...")
            return None

        # Sort by confidence (primary) and priority (secondary)
        matches.sort(
            key=lambda m: (m.confidence, self._skills[m.skill_name].priority),
            reverse=True
        )

        best_match = matches[0]
        logger.info(f"Routed to {best_match.skill_name} (confidence: {best_match.confidence:.2f})")

        return best_match

    def route_with_fallback(self, query: str, fallback_skill: str = "sales_analyst") -> SkillMatch:
        """
        Route a query with a guaranteed fallback.

        Args:
            query: User's natural language query
            fallback_skill: Skill to use if no match found

        Returns:
            SkillMatch (guaranteed)
        """
        match = self.route(query)
        if match:
            return match

        # Return fallback with low confidence
        fallback = self.get_skill(fallback_skill)
        return SkillMatch(
            skill_name=fallback_skill,
            confidence=0.3,
            matched_pattern=None,
            tools_available=fallback.tools if fallback else []
        )

    def explain_routing(self, query: str) -> str:
        """
        Explain how a query would be routed (for debugging).

        Args:
            query: User's natural language query

        Returns:
            Human-readable explanation
        """
        lines = [f"Query: {query}", ""]

        matches = []
        for skill in self.skills:
            match = skill.matches(query)
            if match:
                matches.append((skill, match))

        if not matches:
            lines.append("❌ No skill matched this query")
            lines.append("   → Would use general agent without skill enhancement")
        else:
            lines.append("Matches found:")
            for skill, match in sorted(matches, key=lambda x: x[1].confidence, reverse=True):
                lines.append(f"  • {skill.name}: {match.confidence:.2f} confidence (priority: {skill.priority})")
                lines.append(f"    Pattern: {match.matched_pattern}")
                lines.append(f"    Tools: {', '.join(match.tools_available)}")

            best = max(matches, key=lambda x: (x[1].confidence, x[0].priority))
            lines.append(f"\n✅ Selected: {best[0].name}")

        return "\n".join(lines)

    def get_tools_for_skill(self, skill_name: str) -> list[str]:
        """Get the list of tools available for a skill."""
        skill = self.get_skill(skill_name)
        return skill.tools if skill else []

    def get_prompt_for_skill(self, skill_name: str, base_prompt: str) -> str:
        """Get enhanced prompt for a skill."""
        skill = self.get_skill(skill_name)
        if skill:
            return skill.get_enhanced_prompt(base_prompt)
        return base_prompt

    def list_skills(self) -> list[dict]:
        """
        List all registered skills with their info.

        Returns:
            List of skill info dictionaries
        """
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "priority": skill.priority,
                "tools": skill.tools,
                "trigger_count": len(skill.triggers)
            }
            for skill in self.skills
        ]


# Global router instance
_router: Optional[SkillRouter] = None


def get_router() -> SkillRouter:
    """Get the global skill router instance."""
    global _router
    if _router is None:
        _router = SkillRouter()
    return _router


def route_query(query: str) -> Optional[SkillMatch]:
    """Convenience function to route a query using the global router."""
    return get_router().route(query)
