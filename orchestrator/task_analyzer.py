"""
Task analyzer using Claude API for intelligent task decomposition.
Breaks down complex tasks into subtasks with dependencies.
"""
import re
import json
from typing import List

from shared.models import SubTask, AgentCapability
from shared.config import settings
from shared.auth_client import HybridClaudeClient, AuthConfig


class TaskAnalyzer:
    """Analyzes and decomposes tasks using Claude API"""

    def __init__(self):
        # Use HybridClaudeClient for automatic auth detection
        self.client = HybridClaudeClient(
            config=AuthConfig(
                model=settings.CLAUDE_MODEL,
                max_tokens=2048,
                temperature=0.0
            )
        )
        self.capabilities = [cap.value for cap in AgentCapability]

    async def decompose_task(self, description: str) -> List[SubTask]:
        """
        Decompose task into subtasks using Claude AI.
        Returns list of SubTask objects with dependencies and capabilities.
        """
        prompt = self._build_prompt(description)

        try:
            # Call Claude via HybridClaudeClient
            response = await self.client.query(prompt)

            # Extract JSON from response
            subtasks_data = self._extract_json(response)

            if not subtasks_data:
                # Fallback: create single subtask
                return [self._create_fallback_subtask(description)]

            # Convert to SubTask objects
            subtasks = []
            subtask_map = {}  # Map index to generated ID

            for idx, st_data in enumerate(subtasks_data):
                subtask = SubTask(
                    description=st_data.get("description", description),
                    required_capabilities=[
                        AgentCapability(cap)
                        for cap in st_data.get("required_capabilities", ["code_generation"])
                        if cap in self.capabilities
                    ] or [AgentCapability.CODE_GENERATION],
                    dependencies=[],  # Will be set after mapping
                    priority=st_data.get("priority", 5),
                    estimated_duration=st_data.get("estimated_duration")
                )
                subtasks.append(subtask)
                subtask_map[idx] = subtask.id

            # Map dependencies from indices to IDs
            for idx, st_data in enumerate(subtasks_data):
                dep_indices = st_data.get("dependencies", [])
                subtasks[idx].dependencies = [
                    subtask_map[dep_idx]
                    for dep_idx in dep_indices
                    if dep_idx in subtask_map and dep_idx != idx
                ]

            return subtasks if subtasks else [self._create_fallback_subtask(description)]

        except Exception as e:
            print(f"[TaskAnalyzer] Error decomposing task: {e}")
            # Fallback: create single subtask
            return [self._create_fallback_subtask(description)]

    def _build_prompt(self, description: str) -> str:
        """Build prompt for Claude API"""
        return f"""Analyze and decompose this task into subtasks suitable for parallel execution by AI agents.

Task: {description}

Available agent capabilities:
{', '.join(self.capabilities)}

For each subtask, specify:
1. description (clear, specific, actionable)
2. required_capabilities (array of 1-3 capabilities from the list above)
3. dependencies (array of 0-based subtask indices that must complete first, empty array if none)
4. priority (0-10, higher = more urgent, default 5)
5. estimated_duration (estimated seconds, or null if unknown)

Respond with a JSON array ONLY. Example format:
[
  {{
    "description": "Fetch data from API endpoint",
    "required_capabilities": ["api_integration"],
    "dependencies": [],
    "priority": 7,
    "estimated_duration": 10
  }},
  {{
    "description": "Analyze fetched data statistically",
    "required_capabilities": ["data_analysis"],
    "dependencies": [0],
    "priority": 5,
    "estimated_duration": 15
  }}
]

Important:
- For simple tasks, return a single subtask
- Dependencies are 0-based indices in the response array
- Only use capabilities from the available list
- Keep descriptions concise but actionable
- Respond with ONLY the JSON array, no explanation"""

    def _extract_json(self, text: str) -> List[dict]:
        """Extract JSON array from Claude response"""
        # Try to find JSON array in the text
        json_match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # Try parsing the whole text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return []

    def _create_fallback_subtask(self, description: str) -> SubTask:
        """Create a fallback subtask when decomposition fails"""
        return SubTask(
            description=description[:1000],  # Truncate if too long
            required_capabilities=[AgentCapability.CODE_GENERATION],
            dependencies=[],
            priority=5,
            estimated_duration=None
        )
