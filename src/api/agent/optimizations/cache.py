"""
Caching utilities for query responses.

Implements:
1. QueryCache - Exact match caching for repeated queries
2. SemanticCache - Similarity-based caching using embeddings
"""

import hashlib
import time
import logging
from typing import Optional
from dataclasses import dataclass
from collections import OrderedDict

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached query response."""
    query: str
    response: str
    skill_name: Optional[str]
    created_at: float
    hit_count: int = 0


class QueryCache:
    """
    Exact-match query cache with TTL and LRU eviction.

    Caches responses for identical queries to avoid redundant LLM calls.

    Usage:
        cache = QueryCache(max_size=100, ttl_seconds=3600)

        # Check cache
        cached = cache.get(query)
        if cached:
            return cached.response

        # After getting response
        cache.set(query, response, skill_name)
    """

    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        """
        Initialize the cache.

        Args:
            max_size: Maximum number of entries (default 100)
            ttl_seconds: Time-to-live in seconds (default 1 hour)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = {"hits": 0, "misses": 0}

    def _normalize_query(self, query: str) -> str:
        """Normalize query for cache key."""
        return query.strip().lower()

    def _make_key(self, query: str) -> str:
        """Create cache key from query."""
        normalized = self._normalize_query(query)
        return hashlib.md5(normalized.encode()).hexdigest()

    def get(self, query: str) -> Optional[CacheEntry]:
        """
        Get cached response for query.

        Args:
            query: The user's query

        Returns:
            CacheEntry if found and valid, None otherwise
        """
        key = self._make_key(query)

        if key not in self._cache:
            self._stats["misses"] += 1
            return None

        entry = self._cache[key]

        # Check TTL
        if time.time() - entry.created_at > self.ttl_seconds:
            del self._cache[key]
            self._stats["misses"] += 1
            logger.debug(f"Cache entry expired for query: {query[:50]}...")
            return None

        # Move to end (LRU)
        self._cache.move_to_end(key)
        entry.hit_count += 1
        self._stats["hits"] += 1

        logger.info(f"Cache hit for query: {query[:50]}... (hits: {entry.hit_count})")
        return entry

    def set(self, query: str, response: str, skill_name: Optional[str] = None):
        """
        Cache a response.

        Args:
            query: The user's query
            response: The agent's response
            skill_name: Optional skill that handled the query
        """
        key = self._make_key(query)

        # Evict oldest if at capacity
        while len(self._cache) >= self.max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug("Evicted oldest cache entry")

        self._cache[key] = CacheEntry(
            query=query,
            response=response,
            skill_name=skill_name,
            created_at=time.time()
        )
        logger.debug(f"Cached response for query: {query[:50]}...")

    def invalidate(self, query: str):
        """Remove a specific query from cache."""
        key = self._make_key(query)
        if key in self._cache:
            del self._cache[key]

    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()
        logger.info("Query cache cleared")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": f"{hit_rate:.1%}"
        }


class SemanticCache:
    """
    Semantic similarity cache using embeddings.

    Caches responses and finds similar queries using cosine similarity.
    Falls back to QueryCache if embeddings unavailable.

    Usage:
        cache = SemanticCache(similarity_threshold=0.92)

        # Check for similar cached queries
        cached = cache.get_similar(query)
        if cached:
            return cached.response

        # After getting response
        cache.set(query, response, embedding)
    """

    def __init__(
        self,
        similarity_threshold: float = 0.92,
        max_size: int = 200,
        ttl_seconds: int = 7200
    ):
        """
        Initialize semantic cache.

        Args:
            similarity_threshold: Minimum similarity for cache hit (0-1)
            max_size: Maximum entries
            ttl_seconds: Time-to-live (default 2 hours)
        """
        self.similarity_threshold = similarity_threshold
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._entries: list[dict] = []
        self._stats = {"hits": 0, "misses": 0, "similarity_scores": []}

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = sum(x * x for x in a) ** 0.5
        magnitude_b = sum(x * x for x in b) ** 0.5

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)

    def get_similar(
        self,
        query: str,
        query_embedding: list[float]
    ) -> Optional[CacheEntry]:
        """
        Find a cached response for a semantically similar query.

        Args:
            query: The user's query
            query_embedding: Embedding vector for the query

        Returns:
            CacheEntry if similar query found, None otherwise
        """
        if not self._entries or not query_embedding:
            self._stats["misses"] += 1
            return None

        current_time = time.time()
        best_match = None
        best_similarity = 0.0

        # Find most similar non-expired entry
        valid_entries = []
        for entry in self._entries:
            # Skip expired
            if current_time - entry["created_at"] > self.ttl_seconds:
                continue
            valid_entries.append(entry)

            similarity = self._cosine_similarity(query_embedding, entry["embedding"])
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = entry

        # Update entries list (remove expired)
        self._entries = valid_entries

        # Track similarity scores for tuning
        if best_similarity > 0:
            self._stats["similarity_scores"].append(best_similarity)
            # Keep only last 100 scores
            self._stats["similarity_scores"] = self._stats["similarity_scores"][-100:]

        if best_match and best_similarity >= self.similarity_threshold:
            self._stats["hits"] += 1
            logger.info(
                f"Semantic cache hit (similarity: {best_similarity:.3f}) "
                f"for query: {query[:50]}..."
            )
            return CacheEntry(
                query=best_match["query"],
                response=best_match["response"],
                skill_name=best_match.get("skill_name"),
                created_at=best_match["created_at"],
                hit_count=best_match.get("hit_count", 0) + 1
            )

        self._stats["misses"] += 1
        if best_similarity > 0:
            logger.debug(
                f"Semantic cache miss (best similarity: {best_similarity:.3f}, "
                f"threshold: {self.similarity_threshold})"
            )
        return None

    def set(
        self,
        query: str,
        response: str,
        embedding: list[float],
        skill_name: Optional[str] = None
    ):
        """
        Cache a response with its embedding.

        Args:
            query: The user's query
            response: The agent's response
            embedding: Query embedding vector
            skill_name: Optional skill name
        """
        # Evict oldest if at capacity
        while len(self._entries) >= self.max_size:
            self._entries.pop(0)

        self._entries.append({
            "query": query,
            "response": response,
            "embedding": embedding,
            "skill_name": skill_name,
            "created_at": time.time(),
            "hit_count": 0
        })
        logger.debug(f"Semantic cached response for query: {query[:50]}...")

    def clear(self):
        """Clear all entries."""
        self._entries.clear()
        logger.info("Semantic cache cleared")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0
        avg_similarity = (
            sum(self._stats["similarity_scores"]) / len(self._stats["similarity_scores"])
            if self._stats["similarity_scores"] else 0
        )
        return {
            "size": len(self._entries),
            "max_size": self.max_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": f"{hit_rate:.1%}",
            "avg_similarity": f"{avg_similarity:.3f}",
            "threshold": self.similarity_threshold
        }
