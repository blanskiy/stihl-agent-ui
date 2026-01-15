"""
Product Skill - RAG-based product search and recommendations.
"""
from .base_skill import BaseSkill


class ProductSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "product_expert"

    @property
    def description(self) -> str:
        return "Answer questions about product features, recommendations, and comparisons using semantic search"

    @property
    def triggers(self) -> list[str]:
        return [
            # Product type keywords
            r"\bchainsaw",
            r"\btrimmer",
            r"\bblower",
            r"\bhedge",
            r"\bpressure.washer",
            r"\bsprayer",
            
            # Model number patterns
            r"\b(ms|fs|bg|hs|rb|re|sr)\s*[-]?\s*\d{2,4}\b",
            
            # Recommendation patterns
            r"(best|recommend|suggest|ideal).*(for|to)",
            r"(which|what).*(should|would|could).*(buy|use|get)",
            r"(looking for|need).*(equipment|tool)",
            r"recommendation",

            # Comparison patterns
            r"(compare|vs|versus|difference|better).*(ms|fs|bg|hs)",
            r"(ms|fs|bg|hs)\s*\d+.*(vs|versus|or|compared)",

            # Feature patterns
            r"(feature|specification|spec|weight|power|engine|battery)",
            r"(anti.?vibration|easy.?start|m.?tronic|intellicarb)",

            # Use case patterns
            r"(professional|homeowner|commercial|residential).*(use|grade)",
            r"(heavy|light).*(duty)",
            r"(logging|firewood|yard|lawn|garden)",
            r"(battery.powered|gas.powered|electric|cordless)",
        ]

    @property
    def tools(self) -> list[str]:
        return ["search_products", "compare_products", "get_product_recommendations"]

    @property
    def system_prompt(self) -> str:
        return """You are a STIHL product expert. Match products to user needs based on features and use cases."""

    @property
    def priority(self) -> int:
        return 20
