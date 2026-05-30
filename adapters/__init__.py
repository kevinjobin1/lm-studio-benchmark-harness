"""Optional adapter layers for LM Studio Benchmark Harness.

Adapters NEVER affect benchmark scoring. They are only used in:
- Demo mode
- Interactive playground
- Debugging/exploration
"""

from .mcp.bridge import MCPBridge, MCPServer, create_mcp_playground

__all__ = [
    "MCPBridge",
    "MCPServer",
    "create_mcp_playground",
]
