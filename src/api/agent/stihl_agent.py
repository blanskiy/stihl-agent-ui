"""
STIHL Analytics Agent - Real Function Calling Orchestrator

Uses Azure OpenAI chat completions with tools to execute live queries
against Databricks SQL warehouse.

Enhanced with SkillRouter for intelligent query routing and
skill-specific prompt enhancement.
"""

import json
import logging
import os
from typing import Optional
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import tool registry
from agent.tools import TOOL_FUNCTIONS, TOOL_DEFINITIONS

# Import skill router
from agent.skills import get_router, SkillMatch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base system prompt for the agent
BASE_SYSTEM_PROMPT = """You are STIHL's Analytics Agent - an AI assistant that helps
analysts understand sales performance, inventory status, product information, and business trends.

## Your Key Capabilities
1. **Proactive Insights**: Surface anomalies and alerts WITHOUT being asked
2. **Natural Language Queries**: Convert questions into data analysis
3. **Product Knowledge**: Search and compare products using semantic understanding
4. **Actionable Recommendations**: Don't just show data, suggest what to do

## Conversation Behavior
- When a user starts with greetings like "Hi", "Good morning", or "What should I know?":
  → IMMEDIATELY call get_daily_briefing or get_proactive_insights
  → Lead with the most critical insight, not a generic greeting

- For sales questions → call query_sales_data with appropriate query_type
- For inventory questions → call query_inventory_data with appropriate query_type
- For anomaly detection → call detect_anomalies_realtime
- For product questions → use search_products, compare_products, or get_product_recommendations
- For dealer questions → call query_dealer_data
- For trend analysis → call analyze_trends
- For forecasting → call get_sales_forecast

## Response Style
- Lead with the key insight or answer
- Be specific with numbers and percentages
- Format currency clearly ($394.9M not $394927843)
- End with a recommended action or follow-up question
- Be conversational but professional
"""


class STIHLAnalyticsAgent:
    """
    AI agent using Azure OpenAI function calling with Databricks tools.
    
    Features:
    - SkillRouter integration for intelligent query routing
    - Skill-specific prompt enhancement
    - Tool filtering per skill
    - Comprehensive logging
    """

    def __init__(self, use_skill_routing: bool = True):
        """
        Initialize the Azure OpenAI client.
        
        Args:
            use_skill_routing: Enable SkillRouter for enhanced routing (default True)
        """
        self.client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version="2024-08-01-preview",
        )
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT", "gpt-4o-mini")
        self.use_skill_routing = use_skill_routing
        self.router = get_router() if use_skill_routing else None
        
        # Initialize with base prompt
        self.conversation_history = [
            {"role": "system", "content": BASE_SYSTEM_PROMPT}
        ]
        
        # Track current skill for the conversation
        self.current_skill: Optional[SkillMatch] = None

    def _get_tools_for_skill(self, skill_match: Optional[SkillMatch]) -> list[dict]:
        """
        Get tool definitions filtered by skill, or all tools if no skill matched.
        
        Args:
            skill_match: The matched skill, or None for all tools
            
        Returns:
            List of tool definitions for Azure OpenAI
        """
        if not skill_match:
            return TOOL_DEFINITIONS
        
        # Filter to only the skill's tools
        skill_tools = set(skill_match.tools_available)
        filtered = [
            tool for tool in TOOL_DEFINITIONS
            if tool["function"]["name"] in skill_tools
        ]
        
        # Always include at least some fallback tools if filter is too restrictive
        if len(filtered) < 2:
            return TOOL_DEFINITIONS
            
        return filtered

    def _get_enhanced_prompt(self, skill_match: Optional[SkillMatch]) -> str:
        """
        Get system prompt enhanced with skill-specific context.
        
        Args:
            skill_match: The matched skill, or None for base prompt
            
        Returns:
            Enhanced system prompt string
        """
        if not skill_match:
            return BASE_SYSTEM_PROMPT
            
        return self.router.get_prompt_for_skill(skill_match.skill_name, BASE_SYSTEM_PROMPT)

    def _update_system_prompt(self, new_prompt: str):
        """Update the system prompt in conversation history."""
        if self.conversation_history and self.conversation_history[0]["role"] == "system":
            self.conversation_history[0]["content"] = new_prompt
        else:
            self.conversation_history.insert(0, {"role": "system", "content": new_prompt})

    def chat(self, user_message: str, max_tool_calls: int = 5) -> str:
        """
        Send a message and get a response, handling function calls automatically.

        Args:
            user_message: The user's message
            max_tool_calls: Maximum number of tool call iterations (prevent infinite loops)

        Returns:
            The agent's final response
        """
        # Route the query through SkillRouter
        if self.use_skill_routing and self.router:
            self.current_skill = self.router.route(user_message)
            
            if self.current_skill:
                logger.info(
                    f"🎯 Routed to skill: {self.current_skill.skill_name} "
                    f"(confidence: {self.current_skill.confidence:.2f}, "
                    f"pattern: {self.current_skill.matched_pattern})"
                )
                # Update system prompt with skill enhancement
                enhanced_prompt = self._get_enhanced_prompt(self.current_skill)
                self._update_system_prompt(enhanced_prompt)
            else:
                logger.info("🔄 No specific skill matched, using general agent")
                self._update_system_prompt(BASE_SYSTEM_PROMPT)
        
        # Get tools for this query (filtered by skill or all)
        tools = self._get_tools_for_skill(self.current_skill)
        logger.debug(f"Available tools: {[t['function']['name'] for t in tools]}")
        
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})

        tool_call_count = 0

        while tool_call_count < max_tool_calls:
            # Call Azure OpenAI
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=self.conversation_history,
                tools=tools,
                tool_choice="auto",
            )

            response_message = response.choices[0].message

            # Check if we're done (no more tool calls)
            if not response_message.tool_calls:
                # Add assistant response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response_message.content
                })
                return response_message.content

            # Process tool calls
            self.conversation_history.append({
                "role": "assistant",
                "content": response_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in response_message.tool_calls
                ]
            })

            # Execute each tool call
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                print(f"  🔧 Calling {function_name}({function_args})")
                logger.debug(f"Tool call: {function_name} with args: {function_args}")

                # Execute the function
                if function_name in TOOL_FUNCTIONS:
                    try:
                        result = TOOL_FUNCTIONS[function_name](**function_args)
                    except Exception as e:
                        logger.error(f"Tool error: {function_name} - {e}")
                        result = json.dumps({"error": str(e)})
                else:
                    logger.warning(f"Unknown function requested: {function_name}")
                    result = json.dumps({"error": f"Unknown function: {function_name}"})

                # Add tool result to conversation
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            tool_call_count += 1

        return "I've reached the maximum number of tool calls. Please try a more specific question."

    def reset_conversation(self):
        """Clear conversation history and start fresh."""
        self.conversation_history = [
            {"role": "system", "content": BASE_SYSTEM_PROMPT}
        ]
        self.current_skill = None
        logger.info("Conversation reset")

    def get_routing_explanation(self, query: str) -> str:
        """
        Explain how a query would be routed (for debugging).
        
        Args:
            query: The query to analyze
            
        Returns:
            Human-readable routing explanation
        """
        if not self.router:
            return "Skill routing is disabled"
        return self.router.explain_routing(query)

    def list_skills(self) -> list[dict]:
        """List all available skills."""
        if not self.router:
            return []
        return self.router.list_skills()


def main():
    """Interactive chat loop for testing."""
    print("=" * 60)
    print("🤖 STIHL Analytics Agent - Live Function Calling")
    print("   with SkillRouter Integration")
    print("=" * 60)
    print("Commands:")
    print("  'quit'    - Exit")
    print("  'reset'   - Clear conversation")
    print("  'skills'  - List available skills")
    print("  'route X' - Explain routing for query X")
    print()

    agent = STIHLAnalyticsAgent(use_skill_routing=True)

    while True:
        try:
            user_input = input("\n👤 You: ").strip()

            if not user_input:
                continue
            if user_input.lower() == "quit":
                print("Goodbye!")
                break
            if user_input.lower() == "reset":
                agent.reset_conversation()
                print("Conversation reset.")
                continue
            if user_input.lower() == "skills":
                skills = agent.list_skills()
                print("\n📚 Available Skills:")
                for s in skills:
                    print(f"  • {s['name']}: {s['description']}")
                    print(f"    Tools: {', '.join(s['tools'])}")
                continue
            if user_input.lower().startswith("route "):
                query = user_input[6:]
                print(f"\n{agent.get_routing_explanation(query)}")
                continue

            print("\n🤖 Agent: ", end="")
            response = agent.chat(user_input)
            print(response)

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            logger.exception("Error in chat loop")


if __name__ == "__main__":
    main()
