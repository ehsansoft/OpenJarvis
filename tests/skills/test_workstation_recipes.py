"""The first practical pipeline reads inventory through the standard executor."""

import json
from pathlib import Path

from openjarvis.core.events import EventBus
from openjarvis.core.types import ToolResult
from openjarvis.skills.manager import SkillManager
from openjarvis.tools._stubs import BaseTool, ToolExecutor, ToolSpec


class ReadInventory(BaseTool):
    def __init__(self, name, calls):
        self.tool_id = name
        self.calls = calls

    @property
    def spec(self):
        return ToolSpec(
            name=self.tool_id, description="Read cached inventory", parameters={}
        )

    def execute(self, **params):
        self.calls.append((self.tool_id, params))
        return ToolResult(
            tool_name=self.tool_id, success=True, content=json.dumps({"cached": True})
        )


def test_workstation_recipe_executes_only_two_read_tools():
    root = Path(__file__).resolve().parents[2]
    manager = SkillManager(EventBus())
    manager.discover([root / "skills"])
    calls = []
    manager.set_tool_executor(
        ToolExecutor(
            [
                ReadInventory("drive_inventory", calls),
                ReadInventory("machine_inventory", calls),
            ]
        )
    )
    result = manager.execute("workstation-brief", {})
    assert result.success
    assert calls == [
        ("drive_inventory", {"section": "summary"}),
        ("machine_inventory", {"section": "summary"}),
    ]
    assert len(result.step_results) == 2
    assert {"private-project-plan", "local-research-note"} <= set(manager.skill_names())
