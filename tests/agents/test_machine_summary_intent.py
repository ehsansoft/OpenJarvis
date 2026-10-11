"""Workstation questions must use inventory, including governance denials."""

import json
from unittest.mock import MagicMock

import pytest

from openjarvis.agents.orchestrator import OrchestratorAgent
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


class Inventory(BaseTool):
    tool_id = "machine_inventory"

    @property
    def spec(self):
        return ToolSpec(name=self.tool_id, description="inventory", parameters={})

    def execute(self, **params):
        assert params == {"section": "summary"}
        return ToolResult(
            tool_name=self.tool_id,
            success=True,
            content=json.dumps(
                {
                    "generated_at": "2026-10-11T10:00:00Z",
                    "platform": "Windows",
                    "ollama_models": 3,
                    "total_memory_bytes": 16 * 2**30,
                    "tools_detected": 12,
                    "gpus": ["Local GPU"],
                    "voicebox_reachable": False,
                }
            ),
        )


@pytest.mark.parametrize("mode", ["structured", "function_calling"])
def test_system_question_returns_factual_summary_without_model_guessing(mode):
    engine = MagicMock()
    engine.generate.return_value = {"content": '[{"project":"vendor"}]'}
    agent = OrchestratorAgent(engine, "test", tools=[Inventory()], mode=mode)
    result = agent.run("What do you got information about my system?")
    assert "Windows" in result.content
    assert "16.0 GiB" in result.content
    assert "3 Ollama models" in result.content
    assert "2026-10-11T10:00:00Z" in result.content
    assert "vendor" not in result.content
    engine.generate.assert_not_called()
    assert result.tool_results[0].tool_name == "machine_inventory"


def test_system_shortcut_does_not_bypass_governance():
    engine = MagicMock()
    agent = OrchestratorAgent(
        engine, "test", tools=[Inventory()], before_tool_call=lambda *_: False
    )
    result = agent.run("/system")
    assert not result.tool_results[0].success
    assert "not approved" in result.content
    assert "Local GPU" not in result.content
    engine.generate.assert_not_called()


def test_mutating_or_unrelated_request_retains_normal_agent_routing():
    engine = MagicMock()
    engine.generate.return_value = {"content": "normal response"}
    agent = OrchestratorAgent(engine, "test", tools=[Inventory()])
    assert agent.run("Delete my system caches").content == "normal response"
    engine.generate.assert_called_once()
