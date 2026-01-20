"""
STIHL Analytics Agent - Real Function Calling Orchestrator

Uses Azure OpenAI chat completions with tools to execute live queries
against Databricks SQL warehouse.

Enhanced with:
- SkillRouter for intelligent query routing
- Token optimization (caching, truncation, history pruning)
- Compact tool definitions
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
from agent.tools import TOOL_FUNCTIONS
from agent.tools.definitions_compact import TOOL_DEFINITIONS_COMPACT, get_compact_tools

# Import skill router
from agent.skills import get_router, SkillMatch

# Import optimizations
from agent.optimizations import (
    QueryCache,
    SemanticCache,
    ConversationHistoryManager,
    truncate_tool_result,
)
from agent.optimizations.history import HistoryConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Compact system prompt (~200 tokens vs ~850)
BASE_SYSTEM_PROMPT = """You are STIHL's Analytics Agent helping analysts understand sales, inventory, products, and trends.

## Capabilities
- Proactive insights and alerts
- Sales & inventory analysis
- Product search and recommendations
- Trend detection and forecasting

## Behavior
- For greetings → call get_daily_briefing
- For sales/revenue → call query_sales_data
- For inventory/stock → call query_inventory_data
- For alerts/anomalies → call get_proactive_insights
- For products → use search_products or compare_products
- For dealers → call query_dealer_data
- For trends → call analyze_trends
- For forecasts → call get_sales_forecast

Lead with insights. Be specific with numbers. Recommend actions."""


class STIHLAnalyticsAgent:
    """
    AI agent using Azure OpenAI function calling with Databricks tools.

    Features:
    - SkillRouter integration for intelligent query routing
    - Token optimization via caching and history management
    - Compact tool definitions
    """

    def __init__(
        self,
        use_skill_routing: bool = True,
        use_caching: bool = True,
        use_semantic_cache: bool = True,
        max_history_turns: int = 10
    ):
        """
        Initialize the Azure OpenAI client with optimizations.

        Args:
            use_skill_routing: Enable SkillRouter for enhanced routing
            use_caching: Enable exact-match query caching
            use_semantic_cache: Enable semantic similarity caching
            max_history_turns: Maximum conversation turns to keep
        """
        self.client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version="2024-08-01-preview",
        )
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT", "gpt-4o-mini")
        self.embedding_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_EMBEDDING", "text-embedding-ada-002")

        # Skill routing
        self.use_skill_routing = use_skill_routing
        self.router = get_router() if use_skill_routing else None

        # Initialize caches
        self.use_caching = use_caching
        self.query_cache = QueryCache(max_size=100, ttl_seconds=3600) if use_caching else None

        self.use_semantic_cache = use_semantic_cache
        self.semantic_cache = SemanticCache(
            similarity_threshold=0.92,
            max_size=200,
            ttl_seconds=7200
        ) if use_semantic_cache else None

        # History management
        self.history_manager = ConversationHistoryManager(
            config=HistoryConfig(
                max_turns=max_history_turns,
                summarize_after=5,
                max_tool_result_tokens=500
            )
        )

        # Initialize conversation
        self.conversation_history = [
            {"role": "system", "content": BASE_SYSTEM_PROMPT}
        ]

        # Track current skill
        self.current_skill: Optional[SkillMatch] = None

        # Stats tracking
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "tokens_saved": 0
        }

    def _get_tools_for_skill(self, skill_match: Optional[SkillMatch]) -> list[dict]:
        """
        Get COMPACT tool definitions with balanced filtering.

        Uses compact definitions but provides enough tools for complex queries.
        """
        # Core tools needed for most queries
        core_tools = [
            "query_sales_data",
            "query_inventory_data",
            "get_proactive_insights",
            "get_daily_briefing",
        ]

        if not skill_match:
            # No skill matched - return core + product tools
            all_tools = core_tools + ["search_products", "detect_anomalies_realtime"]
            return get_compact_tools(all_tools)

        # Get skill-specific tools
        skill_tools = set(skill_match.tools_available)

        # Always include core tools + skill tools for flexibility
        combined_tools = list(set(core_tools) | skill_tools)

        # Use compact definitions
        filtered = get_compact_tools(combined_tools)

        if filtered:
            logger.debug(f"Using {len(filtered)} compact tools for {skill_match.skill_name}: {combined_tools}")
            return filtered

        # Fallback to all compact tools
        return TOOL_DEFINITIONS_COMPACT

    def _get_enhanced_prompt(self, skill_match: Optional[SkillMatch]) -> str:
        """Get system prompt enhanced with skill-specific context."""
        if not skill_match:
            return BASE_SYSTEM_PROMPT

        return self.router.get_prompt_for_skill(skill_match.skill_name, BASE_SYSTEM_PROMPT)

    def _update_system_prompt(self, new_prompt: str):
        """Update the system prompt in conversation history."""
        if self.conversation_history and self.conversation_history[0]["role"] == "system":
            self.conversation_history[0]["content"] = new_prompt
        else:
            self.conversation_history.insert(0, {"role": "system", "content": new_prompt})

    def _get_embedding(self, text: str) -> Optional[list[float]]:
        """Get embedding for semantic caching."""
        if not self.use_semantic_cache:
            return None
        try:
            response = self.client.embeddings.create(
                model=self.embedding_deployment,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"Failed to get embedding: {e}")
            return None

    def _check_caches(self, query: str) -> Optional[str]:
        """
        Check both exact and semantic caches.

        Optimization #5: Exact match caching
        Optimization #6: Semantic caching
        """
        # Check exact cache first
        if self.query_cache:
            cached = self.query_cache.get(query)
            if cached:
                self._stats["cache_hits"] += 1
                logger.info(f"Exact cache hit for: {query[:50]}...")
                return cached.response

        # Check semantic cache
        if self.semantic_cache:
            embedding = self._get_embedding(query)
            if embedding:
                cached = self.semantic_cache.get_similar(query, embedding)
                if cached:
                    self._stats["cache_hits"] += 1
                    logger.info(f"Semantic cache hit for: {query[:50]}...")
                    return cached.response

        return None

    def _cache_response(self, query: str, response: str, skill_name: Optional[str] = None):
        """Cache the response in both caches."""
        if self.query_cache:
            self.query_cache.set(query, response, skill_name)

        if self.semantic_cache:
            embedding = self._get_embedding(query)
            if embedding:
                self.semantic_cache.set(query, response, embedding, skill_name)

    def chat(self, user_message: str, max_tool_calls: int = 5) -> str:
        """
        Send a message and get a response, with full optimization.

        Args:
            user_message: The user's message
            max_tool_calls: Maximum tool call iterations

        Returns:
            The agent's final response
        """
        self._stats["total_requests"] += 1

        # Optimization #5 & #6: Check caches first
        cached_response = self._check_caches(user_message)
        if cached_response:
            # Still add to history for context
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": cached_response})
            return cached_response

        # Route the query through SkillRouter
        if self.use_skill_routing and self.router:
            self.current_skill = self.router.route(user_message)

            if self.current_skill:
                logger.info(
                    f"🎯 Routed to skill: {self.current_skill.skill_name} "
                    f"(confidence: {self.current_skill.confidence:.2f})"
                )
                enhanced_prompt = self._get_enhanced_prompt(self.current_skill)
                self._update_system_prompt(enhanced_prompt)
            else:
                logger.info("🔄 No specific skill matched, using general agent")
                self._update_system_prompt(BASE_SYSTEM_PROMPT)

        # Optimization #1: Get filtered compact tools
        tools = self._get_tools_for_skill(self.current_skill)
        logger.debug(f"Using {len(tools)} tools: {[t['function']['name'] for t in tools]}")

        # Add user message
        self.conversation_history.append({"role": "user", "content": user_message})

        # Optimization #3: Prune and optimize history before sending
        optimized_history = self.history_manager.optimize(self.conversation_history)

        tool_call_count = 0
        final_response = None

        while tool_call_count < max_tool_calls:
            # Call Azure OpenAI with optimized history
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=optimized_history,
                tools=tools,
                tool_choice="auto",
            )

            response_message = response.choices[0].message

            # Check if we're done
            if not response_message.tool_calls:
                final_response = response_message.content
                self.conversation_history.append({
                    "role": "assistant",
                    "content": final_response
                })
                break

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
            # Also add to optimized history for this iteration
            optimized_history.append(self.conversation_history[-1])

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
                    logger.warning(f"Unknown function: {function_name}")
                    result = json.dumps({"error": f"Unknown function: {function_name}"})

                # Optimization #2: Truncate tool results (balanced - preserve product names)
                truncated_result = truncate_tool_result(result, max_chars=2000)

                # Add to both histories
                tool_message = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": truncated_result,
                }
                self.conversation_history.append(tool_message)
                optimized_history.append(tool_message)

            tool_call_count += 1

        if final_response is None:
            final_response = "I've reached the maximum number of tool calls. Please try a more specific question."

        # Optimization #3: Prune history after response
        self.conversation_history = self.history_manager.prune(
            self.conversation_history,
            max_messages=50
        )

        # Cache the response
        skill_name = self.current_skill.skill_name if self.current_skill else None
        self._cache_response(user_message, final_response, skill_name)

        return final_response

    def reset_conversation(self):
        """Clear conversation history and start fresh."""
        self.conversation_history = [
            {"role": "system", "content": BASE_SYSTEM_PROMPT}
        ]
        self.current_skill = None
        logger.info("Conversation reset")

    def clear_caches(self):
        """Clear all caches."""
        if self.query_cache:
            self.query_cache.clear()
        if self.semantic_cache:
            self.semantic_cache.clear()
        logger.info("Caches cleared")

    def get_stats(self) -> dict:
        """Get agent statistics including cache performance."""
        stats = {
            "requests": self._stats["total_requests"],
            "cache_hits": self._stats["cache_hits"],
            "cache_hit_rate": (
                f"{self._stats['cache_hits'] / self._stats['total_requests']:.1%}"
                if self._stats["total_requests"] > 0 else "0%"
            ),
            "history_stats": self.history_manager.get_stats(self.conversation_history)
        }

        if self.query_cache:
            stats["query_cache"] = self.query_cache.get_stats()
        if self.semantic_cache:
            stats["semantic_cache"] = self.semantic_cache.get_stats()

        return stats

    def get_routing_explanation(self, query: str) -> str:
        """Explain how a query would be routed."""
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
    print("🤖 STIHL Analytics Agent - Optimized")
    print("   with Caching, History Pruning, Compact Tools")
    print("=" * 60)
    print("Commands:")
    print("  'quit'    - Exit")
    print("  'reset'   - Clear conversation")
    print("  'stats'   - Show optimization stats")
    print("  'skills'  - List available skills")
    print("  'route X' - Explain routing for query X")
    print()

    agent = STIHLAnalyticsAgent(
        use_skill_routing=True,
        use_caching=True,
        use_semantic_cache=True,
        max_history_turns=10
    )

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
            if user_input.lower() == "stats":
                stats = agent.get_stats()
                print("\n📊 Agent Statistics:")
                print(json.dumps(stats, indent=2))
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
