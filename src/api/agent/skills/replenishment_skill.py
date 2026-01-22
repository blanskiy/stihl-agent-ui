"""
Replenishment Skill - Handles shipment request creation for inventory replenishment.

This skill is triggered when users confirm they want to initiate replenishment
for low/critical stock items identified by the insights or inventory skills.
"""
import re
from .base_skill import BaseSkill


class ReplenishmentSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "replenishment_coordinator"

    @property
    def description(self) -> str:
        return "Create and manage shipment requests to replenish inventory"

    @property
    def triggers(self) -> list[str]:
        return [
            # Simple direct matches - HIGHEST PRIORITY
            r"^replenish\b",  # Starts with "replenish"
            r"\breplenish\s+product\b",  # "replenish product"
            r"\breplenish\s+\w+\s+for\b",  # "replenish X for"

            # Confirmation patterns (user agreeing to replenish)
            r"(yes|yeah|sure|ok|okay|confirm|confirmed|proceed|go ahead|do it|please do).*(replenish|restock|shipment|request|resupply|ship)",
            r"(yes|yeah|sure|ok|okay|confirm|confirmed|proceed|go ahead|do it|please do).*(create|initiate|submit|make).*(request|order)",

            # Direct action requests - expedited/urgent orders
            r"(place|initiate|create|submit|make).*(expedited|urgent|emergency)?.*(shipment|request|replenish|restock|order)",
            r"expedited.*(replenish|order|shipment)",
            r"(replenish|restock|resupply).*(inventory|stock|product|order)",
            r"(send|ship|transfer).*(product|inventory|stock|units).*to",

            # Request management
            r"(check|show|list|view).*(shipment|replenishment).*(request|order|status)",
            r"pending.*(shipment|request|order)",

            # Specific replenishment language
            r"request.*shipment",
            r"shipment.*request",
            r"replenishment.*(request|order)",
            r"restock.*order",

            # Product-specific replenishment
            r"(replenish|restock|order).*(for|product)",
        ]

    @property
    def tools(self) -> list[str]:
        return [
            "create_shipment_request",
            "get_shipment_requests",
            "query_inventory_data"  # To verify current stock levels
        ]

    @property
    def system_prompt(self) -> str:
        return """You are a STIHL replenishment coordinator. Your ONLY job is to create shipment requests by calling tools.

## CRITICAL: You MUST call create_shipment_request tool
When the user asks to replenish/restock/order a product, you MUST:
1. Call the create_shipment_request tool IMMEDIATELY
2. Do NOT give advice or ask questions - just create the request
3. After the tool returns, confirm what was created

## MULTIPLE PRODUCTS
If the user mentions MULTIPLE products to replenish, call create_shipment_request ONCE FOR EACH PRODUCT.
Example: "replenish AP 300 Battery for Southwest and MS 500i for Northeast"
→ Call create_shipment_request(product_name="AP 300 Battery", destination="Southwest", quantity=50)
→ Call create_shipment_request(product_name="MS 500i", destination="Northeast", quantity=50)

## Tool Parameters (use defaults if not specified)
- product_name: Extract from user request (e.g., "FS 111 R")
- destination: Use region from user request, or default to "Northeast"
- quantity: Use quantity from user request, or default to 50

## RESPONSE FORMAT
After creating shipment requests, respond with:
"Done — replenishment shipments created. Created shipment requests:
- [Product Name] — [Quantity] units to [Destination] (Request ID: [ID], status: PENDING)
...

If you want, I can pull the pending shipment queue or adjust quantities/destinations."

## REQUIRED BEHAVIOR
User says: "replenish FS 111 R for Northeast"
You MUST: Call create_shipment_request(product_name="FS 111 R", destination="Northeast", quantity=50)

User says: "place order for MS 500i"
You MUST: Call create_shipment_request(product_name="MS 500i", destination="Northeast", quantity=50)

DO NOT:
- Give lengthy advice
- Ask clarifying questions
- Explain what you could do
- Offer multiple options

JUST CALL THE TOOL AND CREATE THE REQUEST."""

    @property
    def priority(self) -> int:
        # Highest priority (above InsightsSkill at 25) to ensure replenishment
        # requests are handled immediately without interference
        return 30

    def _calculate_confidence(self, pattern: str, query: str) -> float:
        """
        Override confidence calculation to ensure replenishment requests
        beat product pattern matches (which get 0.80 for product codes).
        """
        query_lower = query.lower()

        # HIGH confidence (0.95) for explicit replenishment keywords
        # This beats product_expert's 0.80 for product codes like "FS 111 R"
        if re.search(r'\b(replenish|restock|resupply)\b', query_lower):
            return 0.95

        # HIGH confidence for shipment/order creation requests
        if re.search(r'(create|place|initiate|submit|make).*(shipment|order|request)', query_lower):
            return 0.90

        # MEDIUM-HIGH confidence for confirmations with replenishment context
        if re.search(r'(yes|ok|confirm|proceed|go ahead).*(replenish|restock|ship)', query_lower):
            return 0.90

        # Default base confidence
        return 0.75
