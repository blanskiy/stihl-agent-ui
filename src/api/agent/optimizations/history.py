"""
Conversation history management with pruning and summarization.

Keeps conversations within token limits while preserving context.
"""

import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HistoryConfig:
    """Configuration for conversation history management."""
    max_turns: int = 10  # Maximum conversation turns to keep
    summarize_after: int = 5  # Summarize turns older than this
    max_tool_result_tokens: int = 500  # Max tokens per tool result
    preserve_system_prompt: bool = True  # Always keep system prompt


class ConversationHistoryManager:
    """
    Manages conversation history to optimize token usage.

    Strategies:
    1. Keeps last N turns in full detail
    2. Summarizes older turns to reduce tokens
    3. Truncates long tool results
    4. Maintains context while reducing size

    Usage:
        manager = ConversationHistoryManager(max_turns=10)

        # Before sending to LLM
        optimized = manager.optimize(conversation_history)

        # After response, prune old entries
        manager.prune(conversation_history)
    """

    def __init__(self, config: Optional[HistoryConfig] = None):
        """
        Initialize the history manager.

        Args:
            config: History configuration (uses defaults if None)
        """
        self.config = config or HistoryConfig()
        self._summary_cache: dict[str, str] = {}

    def _count_turns(self, history: list[dict]) -> int:
        """Count user/assistant turn pairs in history."""
        user_messages = sum(1 for m in history if m.get("role") == "user")
        return user_messages

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate (4 chars per token)."""
        return len(text) // 4

    def _truncate_content(self, content: str, max_tokens: int) -> str:
        """Truncate content to approximate token limit."""
        max_chars = max_tokens * 4
        if len(content) <= max_chars:
            return content
        return content[:max_chars - 20] + "... [truncated]"

    def _summarize_message(self, message: dict) -> dict:
        """
        Create a summarized version of a message.

        Keeps the essential information while reducing size.
        """
        role = message.get("role", "")
        content = message.get("content", "")

        if role == "system":
            # Never summarize system prompts
            return message

        if role == "tool":
            # Heavily summarize tool results
            return {
                "role": "tool",
                "tool_call_id": message.get("tool_call_id", ""),
                "content": self._truncate_content(content, 150)
            }

        if role == "assistant" and message.get("tool_calls"):
            # Keep tool calls but summarize content
            return {
                "role": "assistant",
                "content": self._truncate_content(content or "", 100) if content else None,
                "tool_calls": message["tool_calls"]
            }

        if role == "user":
            # Keep user messages mostly intact (they're usually short)
            return {
                "role": "user",
                "content": self._truncate_content(content, 200)
            }

        if role == "assistant":
            # Summarize long assistant responses
            return {
                "role": "assistant",
                "content": self._truncate_content(content, 300)
            }

        return message

    def optimize(self, history: list[dict]) -> list[dict]:
        """
        Optimize conversation history for token efficiency.

        Args:
            history: Full conversation history

        Returns:
            Optimized history with reduced tokens
        """
        if not history:
            return history

        turns = self._count_turns(history)
        if turns <= self.config.max_turns:
            # Still within limits, just truncate tool results
            return self._truncate_tool_results(history)

        logger.info(f"Optimizing history: {turns} turns -> {self.config.max_turns}")

        optimized = []
        messages_to_summarize = []
        recent_start_idx = None

        # Find where recent (full-detail) messages start
        user_count = 0
        for i in range(len(history) - 1, -1, -1):
            if history[i].get("role") == "user":
                user_count += 1
                if user_count == self.config.summarize_after:
                    recent_start_idx = i
                    break

        if recent_start_idx is None:
            recent_start_idx = 0

        # Process messages
        for i, message in enumerate(history):
            if message.get("role") == "system":
                # Always keep system prompt
                optimized.append(message)
            elif i < recent_start_idx:
                # Summarize older messages
                messages_to_summarize.append(message)
            else:
                # Keep recent messages with truncated tool results
                if message.get("role") == "tool":
                    optimized.append({
                        "role": "tool",
                        "tool_call_id": message.get("tool_call_id", ""),
                        "content": self._truncate_content(
                            message.get("content", ""),
                            self.config.max_tool_result_tokens
                        )
                    })
                else:
                    optimized.append(message)

        # Add summary of older messages if any
        if messages_to_summarize:
            summary = self._create_summary(messages_to_summarize)
            # Insert after system message
            insert_idx = 1 if optimized and optimized[0].get("role") == "system" else 0
            optimized.insert(insert_idx, {
                "role": "assistant",
                "content": f"[Previous conversation summary: {summary}]"
            })

        return optimized

    def _truncate_tool_results(self, history: list[dict]) -> list[dict]:
        """Truncate just the tool results without other optimizations."""
        result = []
        for message in history:
            if message.get("role") == "tool":
                result.append({
                    "role": "tool",
                    "tool_call_id": message.get("tool_call_id", ""),
                    "content": self._truncate_content(
                        message.get("content", ""),
                        self.config.max_tool_result_tokens
                    )
                })
            else:
                result.append(message)
        return result

    def _create_summary(self, messages: list[dict]) -> str:
        """
        Create a brief summary of messages.

        For now, creates a simple topic list.
        Could be enhanced with LLM-based summarization.
        """
        topics = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user" and content:
                # Extract key topic from user message
                topic = content[:100].strip()
                if len(content) > 100:
                    topic += "..."
                topics.append(f"User asked: {topic}")
            elif role == "assistant" and content and not msg.get("tool_calls"):
                # Get gist of assistant response
                first_line = content.split("\n")[0][:80]
                topics.append(f"Answered: {first_line}")

        if not topics:
            return "Earlier conversation about STIHL analytics"

        # Keep last few topics
        return " | ".join(topics[-3:])

    def prune(self, history: list[dict], max_messages: int = 50) -> list[dict]:
        """
        Prune history to maximum message count.

        Removes oldest messages while keeping system prompt.

        Args:
            history: Conversation history
            max_messages: Maximum messages to keep

        Returns:
            Pruned history
        """
        if len(history) <= max_messages:
            return history

        # Always keep system prompt
        if history and history[0].get("role") == "system":
            system_prompt = history[0]
            rest = history[1:]
            pruned = rest[-(max_messages - 1):]
            return [system_prompt] + pruned

        return history[-max_messages:]

    def get_stats(self, history: list[dict]) -> dict:
        """Get statistics about the conversation history."""
        total_chars = sum(len(m.get("content", "") or "") for m in history)
        tool_results = [m for m in history if m.get("role") == "tool"]
        tool_chars = sum(len(m.get("content", "")) for m in tool_results)

        return {
            "message_count": len(history),
            "turn_count": self._count_turns(history),
            "estimated_tokens": total_chars // 4,
            "tool_result_count": len(tool_results),
            "tool_result_tokens": tool_chars // 4
        }
