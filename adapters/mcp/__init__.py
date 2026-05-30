"""MCP (Model Context Protocol) Adapter.

Wraps skills as MCP tools for interactive use.
Does NOT affect benchmark scoring.
"""

from .bridge import MCPBridge, MCPServer, create_mcp_playground

__all__ = [
    "MCPBridge",
    "MCPServer",
    "create_mcp_playground",
]
