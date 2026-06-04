#!/usr/bin/env python3
"""
MCP Adapter (Optional Layer)

Wraps skills as MCP (Model Context Protocol) tools for:
- Demo mode
- Interactive playground
- Debugging skill behavior

This does NOT affect benchmark scoring.
MCP is ONLY used in demo/playground contexts.
"""

from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass, field

from skills.types import Skill, SkillInput, SkillContext, SkillOutput
from skills.registry import SkillRegistry


@dataclass
class MCPToolDefinition:
    """Definition of a skill exposed as an MCP tool."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable


class MCPBridge:
    """Bridge between the skill registry and the MCP protocol.

    Exposes skills as MCP tools for interactive use.
    Does NOT affect benchmark scoring.
    """

    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self._tools: Dict[str, MCPToolDefinition] = {}
        self._setup_tools()

    def _setup_tools(self):
        """Register all skills as MCP tools."""
        for skill in self.registry.list_all():
            manifest = skill.manifest
            # Bind the skill instance to a closure now to avoid late-binding
            self._tools[manifest.name] = MCPToolDefinition(
                name=manifest.name,
                description=manifest.description,
                input_schema=manifest.input_schema,
                handler=self._make_handler(skill),
            )

    def _make_handler(self, skill: Skill) -> Callable:
        """Create a handler closure bound to a specific skill instance."""

        async def handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
            ctx = SkillContext(
                working_directory=".",
                sandbox={},
            )
            inp = SkillInput(raw=input_data)
            result = await skill.run(inp, ctx)
            return result.to_dict()

        return handler

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all available MCP tools."""
        tools = []
        for name, tool in self._tools.items():
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                }
            )
        return tools

    def get_tool(self, name: str) -> Optional[MCPToolDefinition]:
        """Get a specific tool by name."""
        return self._tools.get(name)

    async def invoke_tool(self, name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a tool by name with input data."""
        tool = self._tools.get(name)
        if not tool:
            return {"success": False, "error": f"Tool '{name}' not found"}

        try:
            return await tool.handler(input_data)
        except Exception as e:
            return {"success": False, "error": str(e)}


class MCPServer:
    """Standalone MCP server for interactive skill exploration.

    Usage:
        server = MCPServer(registry, port=8765)
        server.start()  # Starts HTTP server for MCP protocol
        server.stop()
    """

    def __init__(self, registry: SkillRegistry, port: int = 8765):
        self.bridge = MCPBridge(registry)
        self.port = port
        self._running = False

    def start(self):
        """Start the MCP server (placeholder - requires actual HTTP server)."""
        print(f"[MCP Server] Would start on port {self.port}")
        print(f"[MCP Server] Available tools: {[t['name'] for t in self.bridge.list_tools()]}")
        print("[MCP Server] MCP server requires aioprocessing or similar to run.")
        print("[MCP Server] Use the MCPBridge directly for programmatic access.")

    def stop(self):
        """Stop the MCP server."""
        self._running = False
        print("[MCP Server] Stopped.")


def create_mcp_playground(registry: SkillRegistry) -> MCPBridge:
    """Create an MCP playground bridge for interactive use.

    This is the recommended entry point for:
    - Interactive debugging
    - Skill behavior exploration
    - Demo mode
    """
    return MCPBridge(registry)


# ── Demo / Playground Mode ────────────────────────────────────────


async def run_interactive_demo():
    """Run an interactive demo of the MCP bridge with built-in skills."""
    from skills.registry import create_registry

    registry = create_registry()
    bridge = create_mcp_playground(registry)

    print("=" * 60)
    print("MCP SKILL PLAYGROUND - Interactive Demo")
    print("=" * 60)
    print(f"\nAvailable skills: {len(registry.list_names())}")
    for name in registry.list_names():
        skill = registry.get(name)
        print(f"  - {name} v{skill.manifest.version}: {skill.manifest.description}")

    print("\n--- Tool List (MCP format) ---")
    tools = bridge.list_tools()
    for tool in tools:
        print(f"\n{tool['name']}")
        print(f"  {tool['description']}")
        required = tool["inputSchema"].get("required", [])
        if required:
            print(f"  Required inputs: {', '.join(required)}")

    # Demo: invoke json_parse
    print("\n--- Demo: json_parse ---")
    result = await bridge.invoke_tool(
        "json_parse", {"json_string": '{"name": "benchmark", "version": 1}'}
    )
    print(f"  Result: {json.dumps(result, indent=2)}")

    # Demo: invoke read_file
    print("\n--- Demo: read_file (nonexistent) ---")
    result = await bridge.invoke_tool("read_file", {"path": "nonexistent.txt"})
    print(f"  Result: {json.dumps(result, indent=2)}")

    print("\n--- Playground ready! ---")
    print("Use bridge.invoke_tool(name, input_dict) to explore skills interactively.")


if __name__ == "__main__":
    import asyncio
    import json

    asyncio.run(run_interactive_demo())
