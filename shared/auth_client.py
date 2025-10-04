"""
Hybrid Claude authentication client supporting both Claude Code tokens and API keys.
"""
import os
import asyncio
from typing import Optional
from dataclasses import dataclass

import anthropic
from shared.config import settings


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    def __init__(self, message: str, auth_method: str, suggestion: str):
        self.message = message
        self.auth_method = auth_method
        self.suggestion = suggestion
        super().__init__(message)


@dataclass
class AuthConfig:
    """Configuration for authentication client."""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.0
    system_prompt: Optional[str] = None
    max_retries: int = 3
    timeout: float = 30.0

    @classmethod
    def from_settings(cls) -> "AuthConfig":
        """Create from global settings."""
        return cls(model=settings.CLAUDE_MODEL)


class HybridClaudeClient:
    """
    Unified Claude client that automatically detects and uses either:
    - Claude Code integrated authentication (when CLAUDECODE=1)
    - Direct Anthropic API (when ANTHROPIC_API_KEY is set)
    """

    def __init__(self, config: Optional[AuthConfig] = None):
        """Initialize with automatic authentication detection."""
        self.config = config or AuthConfig.from_settings()
        self.auth_method = self._detect_auth_method()

    def _detect_auth_method(self) -> str:
        """
        Detect which authentication method to use.
        Priority: CLAUDECODE=1 > ANTHROPIC_API_KEY
        """
        if settings.CLAUDECODE == "1":
            return "claude_code"
        elif settings.ANTHROPIC_API_KEY:
            return "direct_api"
        else:
            raise AuthenticationError(
                message="No authentication method configured",
                auth_method="none",
                suggestion="Set CLAUDECODE=1 or provide ANTHROPIC_API_KEY in .env"
            )

    async def query(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Execute Claude query using detected authentication method.

        Args:
            prompt: User prompt for Claude
            system_prompt: Optional system prompt override

        Returns:
            Claude response text

        Raises:
            AuthenticationError: Authentication failed
            ValueError: Invalid prompt
        """
        # Validate inputs
        if not prompt or len(prompt) < 10:
            raise ValueError("Prompt must be at least 10 characters")
        if len(prompt) > 100000:
            raise ValueError("Prompt too long (max 100,000 characters)")

        # Use provided system prompt or default from config
        sys_prompt = system_prompt or self.config.system_prompt

        # Execute with retry logic
        for attempt in range(self.config.max_retries):
            try:
                if self.auth_method == "claude_code":
                    return await self._query_claude_code(prompt, sys_prompt)
                else:
                    return await self._query_direct_api(prompt, sys_prompt)
            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                raise

    async def _query_claude_code(
        self,
        prompt: str,
        system_prompt: Optional[str]
    ) -> str:
        """
        Query using Claude Code SDK.
        Temporarily removes ANTHROPIC_API_KEY to force integrated auth.
        """
        # Import here to avoid dependency when not using Claude Code
        try:
            from claude_code_sdk import ClaudeSDKClient, ClaudeCodeOptions
        except ImportError:
            raise AuthenticationError(
                message="claude-code-sdk not installed",
                auth_method="claude_code",
                suggestion="Install with: pip install claude-code-sdk"
            )

        # Temporarily remove API key to force Claude Code auth
        original_api_key = os.environ.pop("ANTHROPIC_API_KEY", None)

        try:
            options = ClaudeCodeOptions(
                system_prompt=system_prompt,
                model=self.config.model,
                permission_mode=settings.SDK_PERMISSION_MODE
            )

            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)

                # Collect response
                response_text = ""
                async for message in client.receive_response():
                    if hasattr(message, "content"):
                        for block in message.content:
                            if hasattr(block, "text"):
                                response_text += block.text

                return response_text.strip()

        finally:
            # Restore API key
            if original_api_key:
                os.environ["ANTHROPIC_API_KEY"] = original_api_key

    async def _query_direct_api(
        self,
        prompt: str,
        system_prompt: Optional[str]
    ) -> str:
        """Query using direct Anthropic API."""
        if not settings.ANTHROPIC_API_KEY:
            raise AuthenticationError(
                message="ANTHROPIC_API_KEY not set",
                auth_method="direct_api",
                suggestion="Set ANTHROPIC_API_KEY in .env or set CLAUDECODE=1"
            )

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        try:
            response = await client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=system_prompt if system_prompt else "",
                messages=[{"role": "user", "content": prompt}]
            )

            if response.content:
                return response.content[0].text
            return ""

        except anthropic.RateLimitError:
            raise AuthenticationError(
                message="Rate limit exceeded",
                auth_method="direct_api",
                suggestion="Wait before retrying or set CLAUDECODE=1 to use Claude Code tokens"
            )
        except anthropic.AuthenticationError:
            raise AuthenticationError(
                message="Invalid API key",
                auth_method="direct_api",
                suggestion="Check your ANTHROPIC_API_KEY or set CLAUDECODE=1"
            )
