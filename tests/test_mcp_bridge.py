"""Tests for the MCP bridge — skill exposure and tool invocation."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from providers.mcp.bridge import MCPBridge, MCPServer, MCPToolDefinition
from skills.types import Skill, SkillManifest, SkillInput, SkillContext, SkillOutput
from skills.registry import SkillRegistry


class FakeSkill(Skill):
    """A fake skill for testing."""

    def __init__(self, name: str = "fake", version: str = "1.0.0"):
        self._name = name
        self._version = version

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name=self._name,
            description=f"Fake {self._name} skill for testing",
            version=self._version,
            input_schema={"type": "object", "required": ["value"]},
        )

    async def run(self, input_data: SkillInput, ctx: SkillContext) -> SkillOutput:
        value = input_data.raw.get("value", "")
        return SkillOutput(
            success=True,
            data={"result": value.upper()},
        )


class FakeSkillRegistry(SkillRegistry):
    """A fake registry that returns our test skills."""

    def __init__(self, skills=None):
        self._skills = skills or []

    def list_all(self):
        return self._skills

    def list_names(self):
        return [s.manifest.name for s in self._skills]

    def get(self, name: str):
        for s in self._skills:
            if s.manifest.name == name:
                return s
        return None


class TestMCPBridge(unittest.TestCase):
    def setUp(self):
        self.skill_a = FakeSkill(name="uppercase")
        self.skill_b = FakeSkill(name="reverse")
        self.registry = FakeSkillRegistry([self.skill_a, self.skill_b])
        self.bridge = MCPBridge(self.registry)

    def test_list_tools(self):
        tools = self.bridge.list_tools()
        self.assertEqual(len(tools), 2)
        names = {t["name"] for t in tools}
        self.assertEqual(names, {"uppercase", "reverse"})

    def test_get_tool_exists(self):
        tool = self.bridge.get_tool("uppercase")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "uppercase")
        self.assertEqual(tool.description, "Fake uppercase skill for testing")

    def test_get_tool_missing(self):
        tool = self.bridge.get_tool("nonexistent")
        self.assertIsNone(tool)

    def test_invoke_tool_success(self):
        result = asyncio.run(
            self.bridge.invoke_tool("uppercase", {"value": "hello"})
        )
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("data", {}).get("result"), "HELLO")

    def test_invoke_tool_not_found(self):
        result = asyncio.run(
            self.bridge.invoke_tool("missing", {"value": "hello"})
        )
        self.assertFalse(result.get("success"))
        self.assertIn("not found", result.get("error", "").lower())

    def test_invoke_tool_error(self):
        """Tool that raises an exception should return error dict."""
        bad_skill = MagicMock()
        bad_skill.manifest = SkillManifest(
            name="bad",
            description="Bad skill",
            version="1.0.0",
            input_schema={},
        )

        async def raise_error(inp, ctx):
            raise ValueError("boom")

        bad_skill.run = raise_error
        registry = FakeSkillRegistry([bad_skill])
        bridge = MCPBridge(registry)

        result = asyncio.run(bridge.invoke_tool("bad", {}))
        self.assertFalse(result.get("success"))
        self.assertIn("boom", result.get("error", ""))


class TestMCPServer(unittest.TestCase):
    def test_init(self):
        registry = FakeSkillRegistry([FakeSkill("echo")])
        server = MCPServer(registry, port=9999)
        self.assertEqual(server.port, 9999)
        self.assertFalse(server._running)

    def test_start_stop(self):
        registry = FakeSkillRegistry([FakeSkill("echo")])
        server = MCPServer(registry, port=9999)
        # start() is a placeholder, just verify it doesn't crash
        server.start()
        server.stop()
        self.assertFalse(server._running)


if __name__ == "__main__":
    unittest.main()
