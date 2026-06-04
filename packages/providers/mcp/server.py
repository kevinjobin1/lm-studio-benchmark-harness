"""
MCP Server — Model Context Protocol implementation.

Provides two transport modes:
- ``stdio``: JSON-RPC 2.0 over stdin/stdout (for MCP clients like Claude Desktop)
- ``sse``: HTTP Server-Sent Events + POST endpoint (for web clients)

Exposed tools:
- ``list_models`` — list available models from the provider
- ``run_prompt`` — send a prompt to a model and get the response
- ``chat_completion`` — full chat completion with message history

Usage:
    from providers.mcp.server import create_mcp_stdio_server

    server = create_mcp_stdio_server(api_base="http://localhost:1234/v1", api_key="lm-studio")
    server.serve()  # Reads JSON-RPC from stdin, writes to stdout
"""

from __future__ import annotations

import json
import sys
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Awaitable
from pathlib import Path


# ── JSON-RPC Types ────────────────────────────────────────────────


@dataclass
class JSONRPCRequest:
    """A JSON-RPC 2.0 request."""

    jsonrpc: str = "2.0"
    method: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int | str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONRPCRequest":
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            method=data.get("method", ""),
            params=data.get("params", {}),
            id=data.get("id"),
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params,
        }
        if self.id is not None:
            result["id"] = self.id
        return result


@dataclass
class JSONRPCResponse:
    """A JSON-RPC 2.0 response."""

    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[int | str] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"jsonrpc": self.jsonrpc}
        if self.result is not None:
            result["result"] = self.result
        if self.error is not None:
            result["error"] = self.error
        if self.id is not None:
            result["id"] = self.id
        return result


# ── Notification (no id — fire-and-forget) ────────────────────────


def make_notification(method: str, params: Dict[str, Any]) -> str:
    """Create a JSON-RPC notification string (no id)."""
    return json.dumps({"jsonrpc": "2.0", "method": method, "params": params})


def make_error(code: int, message: str, data: Any = None, req_id: Any = None) -> str:
    """Create a JSON-RPC error response string."""
    error: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return json.dumps(JSONRPCResponse(error=error, id=req_id).to_dict())


# ── Tool Handlers ─────────────────────────────────────────────────


class MCPToolHandler:
    """Registry of MCP tool handlers.

    Each handler is a callable that takes a JSON-RPC params dict and
    returns a result dict (or raises an exception for error responses).
    """

    def __init__(self, api_base: str, api_key: str, model: str = ""):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.default_model = model
        self._handlers: Dict[str, Callable[..., Any]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register("list_models", self._handle_list_models)
        self.register("run_prompt", self._handle_run_prompt)
        self.register("chat_completion", self._handle_chat_completion)
        self.register("ping", self._handle_ping)

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        self._handlers[name] = handler

    def get_handlers(self) -> Dict[str, Callable[..., Any]]:
        return dict(self._handlers)

    def get_tool_list(self) -> List[Dict[str, Any]]:
        """Return MCP tool definitions for all registered handlers."""
        return [
            {
                "name": "list_models",
                "description": "List all available models from the connected provider",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "run_prompt",
                "description": "Send a text prompt to a model and get a completion response",
                "inputSchema": {
                    "type": "object",
                    "required": ["prompt"],
                    "properties": {
                        "prompt": {"type": "string", "description": "The prompt text"},
                        "model": {"type": "string", "description": "Model name (optional, uses default)"},
                        "max_tokens": {"type": "number", "description": "Max tokens (default: 500)"},
                        "temperature": {"type": "number", "description": "Temperature (default: 0.7)"},
                    },
                },
            },
            {
                "name": "chat_completion",
                "description": "Full chat completion with message history",
                "inputSchema": {
                    "type": "object",
                    "required": ["messages"],
                    "properties": {
                        "messages": {
                            "type": "array",
                            "description": "Array of {role, content} message objects",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                                    "content": {"type": "string"},
                                },
                            },
                        },
                        "model": {"type": "string", "description": "Model name (optional)"},
                        "max_tokens": {"type": "number", "description": "Max tokens (default: 1000)"},
                        "temperature": {"type": "number", "description": "Temperature (default: 0.7)"},
                    },
                },
            },
            {
                "name": "ping",
                "description": "Health check — returns pong",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

    # ── Handler implementations ─────────────────────────────────

    def _handle_list_models(self, params: Dict[str, Any]) -> Any:
        """List available models from the provider."""
        import urllib.request
        import urllib.error

        try:
            req = urllib.request.Request(f"{self.api_base}/models")
            req.add_header("Authorization", f"Bearer {self.api_key}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            models = data.get("data", [])
            return {
                "models": [{"id": m.get("id", ""), "object": m.get("object", "model")} for m in models],
                "provider": self.api_base,
            }
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to connect to provider: {e.reason}") from e
        except Exception as e:
            raise RuntimeError(f"Error listing models: {e}") from e

    def _handle_run_prompt(self, params: Dict[str, Any]) -> Any:
        """Send a text prompt and return the completion."""
        import urllib.request
        import urllib.error

        prompt = params.get("prompt", "")
        if not prompt:
            raise ValueError("Missing required param: prompt")

        model = params.get("model", self.default_model)
        if not model:
            raise ValueError("No model specified. Provide a model name or configure a default.")

        max_tokens = params.get("max_tokens", 500)
        temperature = params.get("temperature", 0.7)

        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }).encode()

        try:
            req = urllib.request.Request(
                f"{self.api_base}/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())

            choice = data.get("choices", [{}])[0]
            usage = data.get("usage", {})

            return {
                "response": choice.get("message", {}).get("content", ""),
                "model": data.get("model", model),
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                "finish_reason": choice.get("finish_reason", ""),
            }
        except urllib.error.URLError as e:
            raise RuntimeError(f"Provider request failed: {e.reason}") from e
        except Exception as e:
            raise RuntimeError(f"Completion failed: {e}") from e

    def _handle_chat_completion(self, params: Dict[str, Any]) -> Any:
        """Full chat completion with message history."""
        messages = params.get("messages", [])
        if not messages:
            raise ValueError("Missing required param: messages")

        model = params.get("model", self.default_model)
        if not model:
            raise ValueError("No model specified.")

        max_tokens = params.get("max_tokens", 1000)
        temperature = params.get("temperature", 0.7)

        # Delegate to run_prompt logic but with the passed messages
        import urllib.request
        import urllib.error

        body = json.dumps({
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }).encode()

        try:
            req = urllib.request.Request(
                f"{self.api_base}/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())

            choice = data.get("choices", [{}])[0]
            usage = data.get("usage", {})

            return {
                "response": choice.get("message", {}).get("content", ""),
                "role": choice.get("message", {}).get("role", "assistant"),
                "model": data.get("model", model),
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                "finish_reason": choice.get("finish_reason", ""),
            }
        except urllib.error.URLError as e:
            raise RuntimeError(f"Provider request failed: {e.reason}") from e
        except Exception as e:
            raise RuntimeError(f"Chat completion failed: {e}") from e

    def _handle_ping(self, params: Dict[str, Any]) -> Any:
        return {"pong": True, "timestamp": time.time()}


# ── Stdio Server ──────────────────────────────────────────────────


class MCPServerStdio:
    """MCP server over stdio transport.

    Reads JSON-RPC 2.0 requests from stdin, dispatches them to the
    registered tool handlers, and writes responses to stdout.

    Usage:
        server = MCPServerStdio(api_base="http://localhost:1234/v1", ...)
        server.serve()  # Blocks, reading stdin until EOF
    """

    def __init__(
        self,
        api_base: str = "http://localhost:1234/v1",
        api_key: str = "lm-studio",
        model: str = "",
    ):
        self.handler = MCPToolHandler(api_base=api_base, api_key=api_key, model=model)
        self._running = False

    def serve(self) -> None:
        """Read JSON-RPC from stdin, process, write to stdout."""
        self._running = True

        # Send initialized notification
        sys.stdout.write(make_notification("initialized", {}) + "\n")
        sys.stdout.flush()

        for line in sys.stdin:
            if not self._running:
                break

            line = line.strip()
            if not line:
                continue

            try:
                request = JSONRPCRequest.from_dict(json.loads(line))
                response = self._dispatch(request)
                if response is not None:
                    sys.stdout.write(json.dumps(response.to_dict()) + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError:
                sys.stdout.write(make_error(-32700, "Parse error", req_id=None) + "\n")
                sys.stdout.flush()
            except Exception as e:
                sys.stdout.write(make_error(-32603, f"Internal error: {e}", req_id=None) + "\n")
                sys.stdout.flush()

        self._running = False

    def stop(self) -> None:
        """Signal the server to stop."""
        self._running = False

    def _dispatch(self, request: JSONRPCRequest) -> Optional[JSONRPCResponse]:
        """Dispatch a JSON-RPC request using the shared dispatcher."""
        return _dispatch_mcp(request, self.handler)


# ── MCP Server HTTP (SSE transport) ───────────────────────────────


class MCPServerHTTP:
    """MCP server over HTTP SSE transport.

    Serves:
    - ``GET /sse`` — SSE stream for MCP events
    - ``POST /messages`` — Receive JSON-RPC messages
    - ``GET /health`` — Health check

    Usage:
        server = MCPServerHTTP(port=8765, ...)
        thread = server.start()  # Starts in daemon thread
        ...
        server.stop()
    """

    def __init__(
        self,
        api_base: str = "http://localhost:1234/v1",
        api_key: str = "lm-studio",
        model: str = "",
        port: int = 8765,
        host: str = "127.0.0.1",
    ):
        self.handler = MCPToolHandler(api_base=api_base, api_key=api_key, model=model)
        self.port = port
        self.host = host
        self._server = None
        self._thread = None

    def start(self) -> int:
        """Start the HTTP server in a daemon thread. Returns the actual port."""
        from http.server import HTTPServer, BaseHTTPRequestHandler

        handler = self.handler

        class MCPHTTPHandler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                pass  # Suppress HTTP log output

            def _send_json(self, data: Any, status: int = 200) -> None:
                body = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                if self.path == "/sse":
                    self._handle_sse()
                elif self.path in ("/health", "/"):
                    self._send_json({
                        "status": "ok",
                        "server": "modellens-mcp",
                        "version": "0.1.0",
                        "tools": [t["name"] for t in handler.get_tool_list()],
                    })
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self) -> None:
                if self.path == "/messages":
                    self._handle_message()
                elif self.path == "/tools/call":
                    self._handle_tool_call()
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_OPTIONS(self) -> None:
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
                self.end_headers()

            def _handle_sse(self) -> None:
                """Handle SSE connection."""
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                # Send initialized event
                self.wfile.write(b"event: initialized\ndata: {}\n\n")
                self.wfile.flush()

                # Keep connection alive
                while True:
                    try:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        time.sleep(15)
                    except (BrokenPipeError, ConnectionResetError):
                        break

            def _handle_message(self) -> None:
                """Handle incoming JSON-RPC message."""
                cl = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(cl)
                if not body:
                    self._send_json({"error": "Empty request body"}, 400)
                    return

                try:
                    data = json.loads(body)
                    req = JSONRPCRequest.from_dict(data)
                    response = self._dispatch_mcp(req, handler)
                    if response is not None:
                        self._send_json(response.to_dict())
                    else:
                        self._send_json({"jsonrpc": "2.0"})
                except json.JSONDecodeError:
                    self._send_json({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}, 400)
                except Exception as e:
                    self._send_json({"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}, 500)

            def _handle_tool_call(self) -> None:
                """Direct POST endpoint for tool calls (simpler than full JSON-RPC)."""
                cl = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(cl)
                if not body:
                    self._send_json({"error": "Empty body"}, 400)
                    return

                try:
                    data = json.loads(body)
                    tool_name = data.get("tool", "")
                    args = data.get("arguments", {})

                    handlers = handler.get_handlers()
                    h = handlers.get(tool_name)
                    if not h:
                        self._send_json({"error": f"Tool not found: {tool_name}"}, 404)
                        return

                    result = h(args)
                    self._send_json(result)
                except Exception as e:
                    self._send_json({"error": str(e)}, 500)

        server = HTTPServer((self.host, self.port), MCPHTTPHandler)
        self._server = server
        actual_port = server.server_address[1]

        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()

        return actual_port

    def stop(self) -> None:
        """Stop the HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._thread:
            self._thread = None


def _dispatch_mcp(req: JSONRPCRequest, handler: MCPToolHandler) -> Optional[JSONRPCResponse]:
    """Dispatch an MCP JSON-RPC request (shared by both transports)."""
    method = req.method

    if method == "initialize":
        return JSONRPCResponse(
            result={
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "modellens-mcp", "version": "0.1.0"},
            },
            id=req.id,
        )

    if method in ("notifications/initialized",):
        return None

    if method == "tools/list":
        return JSONRPCResponse(result={"tools": handler.get_tool_list()}, id=req.id)

    if method == "tools/call":
        tool_name = req.params.get("name", "")
        tool_args = req.params.get("arguments", {})
        h = handler.get_handlers().get(tool_name)
        if not h:
            return JSONRPCResponse(
                error={"code": -32601, "message": f"Tool not found: {tool_name}"},
                id=req.id,
            )
        try:
            return JSONRPCResponse(result=h(tool_args), id=req.id)
        except Exception as e:
            return JSONRPCResponse(
                error={"code": -32603, "message": str(e)},
                id=req.id,
            )

    if method == "ping":
        return JSONRPCResponse(result={"pong": True}, id=req.id)

    if req.id is not None:
        return JSONRPCResponse(
            error={"code": -32601, "message": f"Method not found: {method}"},
            id=req.id,
        )
    return None


# ── Factory function ──────────────────────────────────────────────


def create_mcp_server(
    transport: str = "stdio",
    api_base: str = "http://localhost:1234/v1",
    api_key: str = "lm-studio",
    model: str = "",
    port: int = 8765,
    host: str = "127.0.0.1",
) -> Any:
    """Create an MCP server with the specified transport.

    Args:
        transport: ``"stdio"`` (stdin/stdout JSON-RPC) or ``"sse"`` (HTTP SSE).
        api_base: Provider base URL.
        api_key: Provider API key.
        model: Default model name.
        port: Port for SSE transport.
        host: Host for SSE transport.

    Returns:
        MCPServerStdio or MCPServerHTTP instance.
    """
    if transport == "stdio":
        return MCPServerStdio(api_base=api_base, api_key=api_key, model=model)
    elif transport == "sse":
        return MCPServerHTTP(api_base=api_base, api_key=api_key, model=model, port=port, host=host)
    else:
        raise ValueError(f"Unknown transport: {transport}. Use 'stdio' or 'sse'.")
