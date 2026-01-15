"""
Configuration management for STIHL Analytics Agent.
Loads environment variables from existing project .env file.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()


@dataclass
class DatabricksConfig:
    """Databricks connection configuration."""
    host: str
    http_path: str
    token: str
    catalog: str = "dbw_stihl_analytics"
    schema_bronze: str = "bronze"
    schema_silver: str = "silver"
    schema_gold: str = "gold"

    @classmethod
    def from_env(cls) -> "DatabricksConfig":
        """Load configuration from environment variables."""
        # Support both DATABRICKS_HOST and DATABRICKS_WORKSPACE_URL
        host = os.getenv("DATABRICKS_HOST") or os.getenv("DATABRICKS_WORKSPACE_URL", "")
        # Strip https:// if present (WORKSPACE_URL includes it, HOST doesn't)
        host = host.replace("https://", "").replace("http://", "")
        
        return cls(
            host=host,
            http_path=os.environ["DATABRICKS_HTTP_PATH"],
            token=os.environ["DATABRICKS_TOKEN"],
            catalog=os.getenv("DATABRICKS_CATALOG", "dbw_stihl_analytics"),
            schema_bronze=os.getenv("DATABRICKS_SCHEMA_BRONZE", "bronze"),
            schema_silver=os.getenv("DATABRICKS_SCHEMA_SILVER", "silver"),
            schema_gold=os.getenv("DATABRICKS_SCHEMA_GOLD", "gold"),
        )

    def get_table(self, schema: str, table: str) -> str:
        """Return fully qualified table name."""
        return f"{self.catalog}.{schema}.{table}"


@dataclass
class AzureOpenAIConfig:
    """Azure OpenAI configuration."""
    endpoint: str
    api_key: str
    deployment: str
    embedding_deployment: str
    api_version: str = "2024-08-01-preview"

    @classmethod
    def from_env(cls) -> "AzureOpenAIConfig":
        """Load configuration from environment variables."""
        return cls(
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            # Support both naming conventions
            deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT") or os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT", "gpt-4o-mini"),
            embedding_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT") or os.getenv("AZURE_OPENAI_DEPLOYMENT_EMBEDDING", "text-embedding-ada-002"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
        )


@dataclass
class AIFoundryConfig:
    """Azure AI Foundry project configuration."""
    project_endpoint: Optional[str]
    subscription_id: Optional[str]
    resource_group: Optional[str]
    project_name: Optional[str]

    @classmethod
    def from_env(cls) -> "AIFoundryConfig":
        """Load configuration from environment variables."""
        return cls(
            project_endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT"),
            subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID"),
            resource_group=os.getenv("AZURE_RESOURCE_GROUP"),
            project_name=os.getenv("AZURE_AI_PROJECT_NAME"),
        )

    def get_connection_string(self) -> str:
        """Build connection string from components."""
        if self.project_endpoint:
            # Use the endpoint directly
            return self.project_endpoint
        
        if all([self.subscription_id, self.resource_group, self.project_name]):
            return f"westus2.api.azureml.ms;{self.subscription_id};{self.resource_group};{self.project_name}"
        
        raise ValueError("Either FOUNDRY_PROJECT_ENDPOINT or all of AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, AZURE_AI_PROJECT_NAME are required")


class Config:
    """Main configuration container."""

    _instance: Optional["Config"] = None

    def __init__(self):
        self.databricks = DatabricksConfig.from_env()
        self.openai = AzureOpenAIConfig.from_env()
        self.ai_foundry = AIFoundryConfig.from_env()

    @classmethod
    def get(cls) -> "Config":
        """Get singleton configuration instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset singleton (useful for testing)."""
        cls._instance = None

    def validate(self) -> list[str]:
        """Validate configuration and return list of issues."""
        issues = []

        if not self.databricks.host:
            issues.append("DATABRICKS_HOST or DATABRICKS_WORKSPACE_URL is required")
        if not self.databricks.http_path:
            issues.append("DATABRICKS_HTTP_PATH is required")
        if not self.databricks.token:
            issues.append("DATABRICKS_TOKEN is required")
        if not self.openai.endpoint:
            issues.append("AZURE_OPENAI_ENDPOINT is required")
        if not self.openai.api_key:
            issues.append("AZURE_OPENAI_API_KEY is required")

        return issues


def get_config() -> Config:
    """Convenience function to get configuration."""
    return Config.get()
