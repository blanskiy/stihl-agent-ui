"""
Base Skill class for STIHL Analytics Agent.

Skills encapsulate domain-specific capabilities with:
- Pattern matching for query routing
- Dedicated tools
- Focused system prompts

This enables modular, testable, and extensible agent behavior.
"""
import re
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class SkillMatch:
    """Result of matching a query against a skill."""
    skill_name: str
    confidence: float  # 0.0 to 1.0
    matched_pattern: Optional[str] = None
    tools_available: list[str] = field(default_factory=list)


class BaseSkill(ABC):
    """
    Abstract base class for all agent skills.
    
    Each skill defines:
    - name: Unique identifier
    - description: What this skill does
    - triggers: Regex patterns that activate this skill
    - tools: List of tool names this skill can use
    - system_prompt: Skill-specific prompt enhancement
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill identifier."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of skill capabilities."""
        pass
    
    @property
    @abstractmethod
    def triggers(self) -> list[str]:
        """Regex patterns that trigger this skill."""
        pass
    
    @property
    @abstractmethod
    def tools(self) -> list[str]:
        """List of tool names this skill can use."""
        pass
    
    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Skill-specific system prompt enhancement."""
        pass
    
    @property
    def priority(self) -> int:
        """
        Skill priority for routing (higher = checked first).
        Override in subclass if needed. Default is 10.
        """
        return 10
    
    def matches(self, query: str) -> Optional[SkillMatch]:
        """
        Check if this skill matches the given query.
        
        Args:
            query: User's natural language query
            
        Returns:
            SkillMatch if triggered, None otherwise
        """
        query_lower = query.lower()
        
        for pattern in self.triggers:
            if re.search(pattern, query_lower, re.IGNORECASE):
                # Calculate confidence based on pattern specificity
                confidence = self._calculate_confidence(pattern, query_lower)
                return SkillMatch(
                    skill_name=self.name,
                    confidence=confidence,
                    matched_pattern=pattern,
                    tools_available=self.tools
                )
        
        return None
    
    def _calculate_confidence(self, pattern: str, query: str) -> float:
        """
        Calculate confidence score based on pattern match quality.
        
        Higher scores for:
        - Longer pattern matches
        - Multiple keyword matches
        - Exact phrase matches
        """
        # Base confidence
        confidence = 0.7
        
        # Boost for longer patterns (more specific)
        if len(pattern) > 30:
            confidence += 0.1
        
        # Boost for multiple keywords in query matching pattern
        pattern_keywords = re.findall(r'\w+', pattern.lower())
        query_keywords = set(re.findall(r'\w+', query.lower()))
        
        keyword_overlap = len(set(pattern_keywords) & query_keywords)
        if keyword_overlap >= 2:
            confidence += 0.1
        if keyword_overlap >= 3:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def get_enhanced_prompt(self, base_prompt: str) -> str:
        """
        Combine base system prompt with skill-specific enhancements.
        
        Args:
            base_prompt: The agent's base system prompt
            
        Returns:
            Enhanced prompt with skill context
        """
        return f"""{base_prompt}

## Active Skill: {self.name}
{self.system_prompt}

Available tools for this query: {', '.join(self.tools)}
"""
    
    def __repr__(self) -> str:
        return f"<Skill: {self.name} ({len(self.triggers)} triggers, {len(self.tools)} tools)>"
