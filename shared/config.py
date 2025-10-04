"""
Configuration settings for the Multi-Agent Task Execution System.
Loads settings from environment variables with defaults.
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, model_validator


class Settings(BaseSettings):
    """Application settings loaded from environment"""

    # Claude Code Integration
    CLAUDECODE: str = Field(
        default="0",
        description="Claude Code environment flag (1=enabled, 0=disabled)"
    )

    # Anthropic API (optional when using Claude Code)
    ANTHROPIC_API_KEY: Optional[str] = Field(
        default=None,
        description="Anthropic API key for Claude (required if CLAUDECODE=0)"
    )

    # Database
    POSTGRES_URL: str = Field(
        default="postgresql://postgres:postgres@192.168.1.33:5432/multi_agent_db",
        description="PostgreSQL connection URL"
    )

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )

    # Claude SDK
    SDK_PERMISSION_MODE: str = Field(
        default="bypassPermissions",
        description="Claude SDK permission mode (acceptEdits, bypassPermissions, default, plan)"
    )

    CLAUDE_MODEL: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model to use"
    )

    # Agent Configuration (for agent services)
    AGENT_ID: str = Field(default="agent_1", description="Unique agent identifier")
    AGENT_PORT: int = Field(default=8001, description="Agent service port")
    AGENT_CAPABILITIES: str = Field(
        default="data_analysis,code_generation",
        description="Comma-separated list of agent capabilities"
    )

    # Orchestrator Configuration
    ORCHESTRATOR_URL: str = Field(
        default="http://localhost:8000",
        description="Orchestrator API base URL"
    )

    @model_validator(mode='after')
    def validate_auth_method(self):
        """Ensure at least one authentication method is available"""
        if self.CLAUDECODE != "1" and not self.ANTHROPIC_API_KEY:
            raise ValueError(
                "No authentication method configured. "
                "Either set CLAUDECODE=1 (for Claude Code tokens) "
                "or provide ANTHROPIC_API_KEY (for direct API)"
            )

        # Validate API key format if provided
        if self.ANTHROPIC_API_KEY and self.ANTHROPIC_API_KEY == "sk-ant-xxxxxxxxxxxxx":
            raise ValueError("ANTHROPIC_API_KEY must be set to a valid API key (not placeholder)")

        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Singleton instance
settings = Settings()
