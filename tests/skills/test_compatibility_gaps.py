from openjarvis.skills.importer import _dangerous_tools
from openjarvis.skills.tool_translator import ToolTranslator
from openjarvis.skills.types import SkillManifest


def test_parameterized_and_snake_case_declared_tools_are_classified():
    manifest = SkillManifest(name="fixture", description="Fixture")
    caps = _dangerous_tools(
        {"allowed-tools": "Bash(git:*) Write(**), terminal"}, manifest
    )
    assert "shell:execute" in caps
    assert "filesystem:write" in caps


def test_unsupported_hermes_tools_are_reported():
    _, missing = ToolTranslator().translate_markdown(
        "Use web_extract, browser_navigate and unknown_tool."
    )
    assert {"web_extract", "browser_navigate", "unknown_tool"} <= set(missing)
