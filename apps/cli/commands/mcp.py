"""MCP server commands for modellens CLI.

Exposes model lens features as MCP (Model Context Protocol) tools
for use with MCP clients (Claude Desktop, VS Code extensions, etc.).

Usage:
    modellens mcp serve                          # stdio mode (default)
    modellens mcp serve --transport sse --port 8765
    modellens mcp serve --provider ollama --models llama3.2
"""

import sys
import signal

import click

from .utils import _echo


@click.group()
def mcp():
    """Model Context Protocol server — expose models as MCP tools.

    \b
    Examples:
      modellens mcp serve                            # stdio (for Claude Desktop)
      modellens mcp serve --transport sse --port 8765 # HTTP SSE
      modellens mcp serve --provider ollama --models llama3.2
    """
    pass


@mcp.command()
@click.option(
    "--transport", "-t",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    show_default=True,
    help="MCP transport protocol: stdio (stdin/stdout JSON-RPC) or sse (HTTP SSE)",
)
@click.option(
    "--port", "-p",
    type=int,
    default=8765,
    show_default=True,
    help="Port for SSE transport (ignored in stdio mode)",
)
@click.option("--host", default="127.0.0.1", show_default=True, help="Host for SSE transport")
@click.option(
    "--api-base", default=None,
    help="Provider base URL (auto-detected if omitted)",
)
@click.option(
    "--api-key", default=None,
    help="Provider API key (auto-detected if omitted)",
)
@click.option(
    "--provider", "-P",
    type=click.Choice(["lm-studio", "ollama", "open-webui", "jan", "llama.cpp", "vllm"]),
    default=None,
    help="Provider to use (auto-detected if omitted)",
)
@click.option(
    "--model", "-m",
    default="",
    help="Default model name for completions",
)
@click.option("--verbose", "-v", is_flag=True, help="Show debug information")
def serve(transport, port, host, api_base, api_key, provider, model, verbose):
    """Start an MCP server exposing model tools.

    \b
    Examples:
      modellens mcp serve
      modellens mcp serve --transport sse --port 8765
      modellens mcp serve --provider ollama --models llama3.2 --transport stdio
    """
    from providers.mcp.server import create_mcp_server

    # Resolve provider
    from .utils import _resolve_provider

    if provider is None:
        provider, detected_base, detected_key = _resolve_provider()
        api_base = api_base or detected_base
        api_key = api_key or detected_key
    else:
        from providers import get_provider_config

        url, key = get_provider_config(provider)
        api_base = api_base or url
        api_key = api_key or key

    # Validate connection
    from .utils import validate_provider_connection

    try:
        validate_provider_connection(provider, api_base)
    except SystemExit:
        _echo(f"⚠ Could not connect to {provider} at {api_base}. MCP server will start but model tools may fail.", "yellow")
        # Continue anyway — some MCP operations don't need a model

    if transport == "stdio":
        _echo(f"🔌 Starting MCP server (stdio transport)", "bold blue")
        if verbose:
            _echo(f"   Provider: {provider}  |  API: {api_base}  |  Model: {model or '(auto)'}", "dim")
            _echo(f"   Waiting for JSON-RPC on stdin...", "dim")
            _echo(f"   Tools: list_models, run_prompt, chat_completion, ping", "dim")

        server = create_mcp_server(
            transport="stdio",
            api_base=api_base,
            api_key=api_key,
            model=model,
        )

        # Handle SIGINT gracefully
        def _handle_sigint(sig, frame):
            server.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, _handle_sigint)
        server.serve()

    elif transport == "sse":
        _echo(f"🔌 Starting MCP server (SSE transport)", "bold blue")
        if verbose:
            _echo(f"   Provider: {provider}  |  API: {api_base}  |  Model: {model or '(auto)'}", "dim")
            _echo(f"   Endpoint: http://{host}:{port}/sse", "dim")
            _echo(f"   Messages: POST http://{host}:{port}/messages", "dim")
            _echo(f"   Tools:    POST http://{host}:{port}/tools/call", "dim")
            _echo(f"   Health:   GET  http://{host}:{port}/health", "dim")
        else:
            print(f"MCP SSE server running on http://{host}:{port}")
            print(f"SSE endpoint: http://{host}:{port}/sse")
            print(f"POST messages: http://{host}:{port}/messages")

        server = create_mcp_server(
            transport="sse",
            api_base=api_base,
            api_key=api_key,
            model=model,
            port=port,
            host=host,
        )

        actual_port = server.start()
        if actual_port != port:
            print(f"Actual port: {actual_port}")

        _echo(f"✓ MCP server started. Press Ctrl+C to stop.", "green")

        try:
            # Block until interrupted
            import time as _time
            while True:
                _time.sleep(1)
        except KeyboardInterrupt:
            _echo(f"\nStopping MCP server...", "yellow")
            server.stop()
            _echo(f"✓ MCP server stopped.", "green")
