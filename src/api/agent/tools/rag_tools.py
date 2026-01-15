"""
RAG tools for semantic product search using Databricks Vector Search.

This module provides semantic search capabilities over STIHL product catalog,
enabling natural language queries about product features, recommendations,
and comparisons.

Created: Phase 5b - RAG Implementation
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Vector Search configuration
ENDPOINT_NAME = "stihl-vector-endpoint"
INDEX_NAME = "dbw_stihl_analytics.vectors.product_index"


def _get_vector_search_client():
    """
    Initialize Vector Search client with workspace authentication.
    
    Returns:
        VectorSearchClient configured for the Databricks workspace
    """
    from databricks.vector_search.client import VectorSearchClient
    from config.settings import get_config
    
    return VectorSearchClient(
        workspace_url=f"https://{get_config().databricks.host}",
        personal_access_token=get_config().databricks.token,
        disable_notice=True
    )


def search_products(
    query: str,
    category: Optional[str] = None,
    power_type: Optional[str] = None,
    max_weight: Optional[float] = None,
    max_price: Optional[float] = None,
    top_k: int = 5
) -> str:
    """
    Search products using semantic similarity with optional filters.
    
    Uses Databricks Vector Search with BGE-Large embeddings to find
    products that semantically match the query, with optional filtering
    by category, power type, weight, and price.
    
    Args:
        query: Natural language search query 
               (e.g., "professional chainsaw for logging", "lightweight battery trimmer")
        category: Filter by category (Chainsaws, Trimmers, Blowers, etc.)
        power_type: Filter by power type (Gas, Battery, Electric)
        max_weight: Maximum weight in lbs (post-filter)
        max_price: Maximum MSRP in dollars (post-filter)
        top_k: Number of results to return (default 5, max 10)
    
    Returns:
        JSON string with matching products and their details
    """
    try:
        vsc = _get_vector_search_client()
        index = vsc.get_index(ENDPOINT_NAME, INDEX_NAME)
        
        # Build filters for vector search (categorical only)
        filters = {}
        if category:
            filters["category"] = category
        if power_type:
            filters["power_type"] = power_type
        
        # Execute similarity search
        # Get extra results for post-filtering on numeric constraints
        results = index.similarity_search(
            query_text=query,
            columns=[
                "product_id", "product_name", "category", "subcategory",
                "power_type", "weight_lbs", "msrp", "description", "features_text"
            ],
            filters=filters if filters else None,
            num_results=min(top_k * 3, 30)  # Get extra for post-filtering
        )
        
        # Process results with post-filtering
        products = []
        for row in results.get('result', {}).get('data_array', []):
            product = {
                "product_id": row[0],
                "product_name": row[1],
                "category": row[2],
                "subcategory": row[3],
                "power_type": row[4],
                "weight_lbs": row[5],
                "msrp": row[6],
                "description": row[7],
                "features": row[8]
            }
            
            # Apply post-filters for numeric constraints
            if max_weight and product["weight_lbs"] and product["weight_lbs"] > max_weight:
                continue
            if max_price and product["msrp"] and product["msrp"] > max_price:
                continue
            
            products.append(product)
            if len(products) >= top_k:
                break
        
        if not products:
            return json.dumps({
                "status": "no_results",
                "message": f"No products found matching '{query}' with the specified filters.",
                "filters_applied": {
                    "category": category,
                    "power_type": power_type,
                    "max_weight": max_weight,
                    "max_price": max_price
                }
            })
        
        return json.dumps({
            "status": "success",
            "query": query,
            "result_count": len(products),
            "products": products
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Product search failed: {e}")
        return json.dumps({
            "status": "error",
            "message": str(e)
        })


def compare_products(product_ids: list[str]) -> str:
    """
    Compare multiple products by their IDs side-by-side.
    
    Retrieves full product details from the silver.products table
    for comparison purposes.
    
    Args:
        product_ids: List of product IDs to compare (2-4 products recommended)
    
    Returns:
        JSON with side-by-side comparison of product specifications
    """
    from agent.databricks_client import execute_query
    
    if len(product_ids) < 2:
        return json.dumps({
            "status": "error", 
            "message": "Need at least 2 products to compare"
        })
    
    if len(product_ids) > 4:
        product_ids = product_ids[:4]  # Limit for readability
    
    try:
        ids_str = ", ".join([f"'{pid}'" for pid in product_ids])
        query = f"""
        SELECT 
            product_id,
            product_name,
            category,
            subcategory,
            power_type,
            engine_cc,
            voltage,
            weight_lbs,
            msrp,
            cost,
            description,
            CONCAT_WS(', ', features) as features
        FROM dbw_stihl_analytics.silver.products
        WHERE product_id IN ({ids_str})
        """
        
        result = execute_query(query)
        results = result.get('data', []) if isinstance(result, dict) else result
        
        if not results:
            return json.dumps({
                "status": "error", 
                "message": f"Products not found: {product_ids}"
            })
        
        # Structure comparison data
        comparison = {
            "status": "success",
            "products_compared": len(results),
            "comparison": []
        }
        
        for row in results:
            comparison["comparison"].append({
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "category": row["category"],
                "subcategory": row["subcategory"],
                "power_type": row["power_type"],
                "engine_cc": row.get("engine_cc"),
                "voltage": row.get("voltage"),
                "weight_lbs": row["weight_lbs"],
                "msrp": row["msrp"],
                "margin": round((row["msrp"] - row["cost"]) / row["msrp"] * 100, 1) if row.get("cost") else None,
                "description": row["description"],
                "features": row["features"]
            })
        
        return json.dumps(comparison, indent=2)
        
    except Exception as e:
        logger.error(f"Product comparison failed: {e}")
        return json.dumps({
            "status": "error", 
            "message": str(e)
        })


def get_product_recommendations(
    use_case: str,
    budget: Optional[float] = None,
    experience_level: Optional[str] = None,
    top_k: int = 3
) -> str:
    """
    Get product recommendations based on use case and user constraints.
    
    Higher-level recommendation tool that combines semantic search
    with business logic for better recommendations.
    
    Args:
        use_case: Description of intended use 
                  (e.g., "clearing brush on 5 acre property", "professional tree service")
        budget: Maximum budget in dollars
        experience_level: User experience (homeowner, professional, commercial)
        top_k: Number of recommendations (default 3)
    
    Returns:
        JSON with recommended products and reasoning
    """
    try:
        # Map experience level to subcategory hints
        subcategory_hints = {
            "homeowner": "Homeowner",
            "professional": "Professional", 
            "commercial": "Professional"
        }
        
        # Enhance query with experience context
        enhanced_query = use_case
        if experience_level and experience_level.lower() in subcategory_hints:
            enhanced_query = f"{subcategory_hints[experience_level.lower()]} {use_case}"
        
        # Use search_products with budget constraint
        search_result = search_products(
            query=enhanced_query,
            max_price=budget,
            top_k=top_k
        )
        
        result = json.loads(search_result)
        
        if result["status"] == "success":
            # Add recommendation context
            result["recommendation_context"] = {
                "use_case": use_case,
                "budget": budget,
                "experience_level": experience_level
            }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Product recommendation failed: {e}")
        return json.dumps({
            "status": "error",
            "message": str(e)
        })


# Tool definitions for Azure OpenAI function calling
RAG_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search for STIHL products using natural language queries. Use this for questions about product features, recommendations, finding products by characteristics, or 'which product is best for...' questions. NOT for sales numbers, revenue, or inventory counts - use SQL tools for those.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query describing desired product characteristics, use case, or features. Examples: 'professional chainsaw for heavy logging', 'lightweight battery trimmer for residential use', 'quiet blower for suburban neighborhood', 'products with anti-vibration feature'"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["Chainsaws", "Trimmers", "Blowers", "Hedge Trimmers", "Pressure Washers", "Sprayers", "Multi-Task Tools"],
                        "description": "Optional: Filter by product category"
                    },
                    "power_type": {
                        "type": "string",
                        "enum": ["Gas", "Battery", "Electric"],
                        "description": "Optional: Filter by power source type"
                    },
                    "max_weight": {
                        "type": "number",
                        "description": "Optional: Maximum weight in pounds"
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Optional: Maximum MSRP in dollars"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default 5, max 10)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_products",
            "description": "Compare 2-4 STIHL products side-by-side by their product IDs. Use after search_products to compare specific models the user is interested in. Returns detailed specifications for comparison.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of 2-4 product IDs to compare (e.g., ['MS-362', 'MS-400', 'MS-462'])",
                        "minItems": 2,
                        "maxItems": 4
                    }
                },
                "required": ["product_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_recommendations",
            "description": "Get personalized product recommendations based on use case, budget, and experience level. Use when user describes their situation and needs guidance on which products to consider.",
            "parameters": {
                "type": "object",
                "properties": {
                    "use_case": {
                        "type": "string",
                        "description": "Description of intended use (e.g., 'clearing brush on 5 acre property', 'professional tree service daily use', 'weekend yard maintenance')"
                    },
                    "budget": {
                        "type": "number",
                        "description": "Optional: Maximum budget in dollars"
                    },
                    "experience_level": {
                        "type": "string",
                        "enum": ["homeowner", "professional", "commercial"],
                        "description": "Optional: User's experience level"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of recommendations (default 3)",
                        "default": 3
                    }
                },
                "required": ["use_case"]
            }
        }
    }
]

# Export tool functions mapping
RAG_TOOL_FUNCTIONS = {
    "search_products": search_products,
    "compare_products": compare_products,
    "get_product_recommendations": get_product_recommendations
}
