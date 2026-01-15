"""
Bridge between existing TOOL_DEFINITIONS and Azure AI Agent Service format.
Converts OpenAI function calling format to Agent Service FunctionTool format.
"""

from typing import List, Dict, Any, Callable
import json
import logging

# Import your existing tools
from agent.tools import TOOL_FUNCTIONS, TOOL_DEFINITIONS

logger = logging.getLogger(__name__)


def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    Return tool definitions in Azure AI Agent Service format.
    The Agent Service expects a list of tool definitions with type, function name,
    description, and parameters.
    """
    return TOOL_DEFINITIONS


def get_tool_functions() -> Dict[str, Callable]:
    """
    Return the mapping of tool names to their implementation functions.
    """
    return TOOL_FUNCTIONS


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool by name with the given arguments.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Dictionary of arguments to pass to the tool
        
    Returns:
        Tool execution result as a dictionary
    """
    if tool_name not in TOOL_FUNCTIONS:
        logger.error(f"Unknown tool: {tool_name}")
        return {
            "status": "error",
            "error": f"Unknown tool: {tool_name}",
            "available_tools": list(TOOL_FUNCTIONS.keys())
        }
    
    try:
        logger.info(f"Executing tool: {tool_name} with args: {json.dumps(arguments, default=str)[:200]}")
        result = TOOL_FUNCTIONS[tool_name](**arguments)
        logger.info(f"Tool {tool_name} completed successfully")
        return result
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "tool": tool_name
        }


def get_tools_for_skill(skill_name: str) -> List[str]:
    """
    Get the list of tools associated with a specific skill.
    Used by the SkillRouter to determine which tools to make available.
    """
    skill_tool_mapping = {
        "insights_advisor": [
            "get_proactive_insights",
            "detect_anomalies_realtime", 
            "get_daily_briefing"
        ],
        "product_expert": [
            "search_products",
            "compare_products",
            "get_product_recommendations"
        ],
        "sales_analyst": ["query_sales_data"],
        "inventory_analyst": ["query_inventory_data"],
        "dealer_analyst": ["query_dealer_data"],
        "forecast_analyst": ["get_sales_forecast"],
        "trend_analyst": ["analyze_trends"]
    }
    
    return skill_tool_mapping.get(skill_name, [])


# Convenience exports
__all__ = [
    "get_tool_definitions",
    "get_tool_functions", 
    "execute_tool",
    "get_tools_for_skill",
    "TOOL_FUNCTIONS",
    "TOOL_DEFINITIONS"
]