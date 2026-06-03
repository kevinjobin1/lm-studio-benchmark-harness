// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ReplaySidebarBadge from "./ReplaySidebarBadge";

// ── Helpers ──────────────────────────────────────────────────────

/** Clear sessionStorage keys used by the badge. */
function clearBadgeStorage() {
  try {
    sessionStorage.removeItem("replay-badge-count");
    sessionStorage.removeItem("replay-badge-notified");
  } catch {
    // not available
  }
}

// ── Mock EventSource ──────────────────────────────────────────────

let mockEventSourceRegistry: {
  onmessage: ((event: MessageEvent) => void) | null;
  onerror: (() => void) | null;
  close: ReturnType<typeof vi.fn>;
  addEventListener: ReturnType<typeof vi.fn>;
  removeEventListener: ReturnType<typeof vi.fn>;
} | null = null;

class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  CONNECTING = 0;
  OPEN = 1;
  CLOSED = 2;
  readyState = 1;
  url = "";
  withCredentials = false;
  onopen: (() => void) | null = null;
  close = vi.fn();
  addEventListener = vi.fn();
  removeEventListener = vi.fn();
  dispatchEvent = vi.fn();

  constructor(url: string) {
    this.url = url;
    const reg = {
      onmessage: null as ((event: MessageEvent) => void) | null,
      onerror: null as (() => void) | null,
      close: this.close,
      addEventListener: this.addEventListener,
      removeEventListener: this.removeEventListener,
    };
    mockEventSourceRegistry = reg;

    Object.defineProperty(this, "onmessage", {
      get: () => reg.onmessage,
      set: (fn) => {
        reg.onmessage = fn;
      },
      configurable: true,
    });

    Object.defineProperty(this, "onerror", {
      get: () => reg.onerror,
      set: (fn) => {
        reg.onerror = fn;
      },
      configurable: true,
    });
  }
}

function sendSSEEvent(data: Record<string, unknown>) {
  if (mockEventSourceRegistry?.onmessage) {
    mockEventSourceRegistry.onmessage({
      data: JSON.stringify(data),
    } as MessageEvent);
  }
}

// ── Tests ─────────────────────────────────────────────────────────

describe("ReplaySidebarBadge", () => {
  beforeEach(() => {
    vi.stubGlobal("EventSource", MockEventSource);
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    mockEventSourceRegistry = null;
    clearBadgeStorage();
  });

  it("renders nothing when no events have arrived", () => {
    const { container } = render(<ReplaySidebarBadge />);
    expect(container.innerHTML).toBe("");
  });

  it("shows count 1 after a completed lifecycle event", async () => {
    render(<ReplaySidebarBadge />);

    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "qwen3.5-9b-coder",
      run_id: "run-abc-123",
      duration_ms: 5000,
    });

    await waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument();
    });

    expect(screen.getByLabelText("1 new replays")).toBeInTheDocument();
  });

  it("shows count after a failed lifecycle event", async () => {
    render(<ReplaySidebarBadge />);

    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "failed",
      model: "llama3.2-3b",
      run_id: "run-def-456",
    });

    await waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument();
    });
  });

  it("does not count started events", async () => {
    const { container } = render(<ReplaySidebarBadge />);

    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "started",
      model: "test-model",
      run_id: "run-started-1",
    });

    await waitFor(() => {
      expect(container.innerHTML).toBe("");
    });
  });

  it("increments count for each new run_id", async () => {
    render(<ReplaySidebarBadge />);

    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "model-a",
      run_id: "run-a",
    });

    await waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument();
    });

    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "model-b",
      run_id: "run-b",
    });

    await waitFor(() => {
      expect(screen.getByText("2")).toBeInTheDocument();
    });
  });

  it("does not increment for duplicate run_id", async () => {
    render(<ReplaySidebarBadge />);

    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "test-model",
      run_id: "run-dup-1",
    });

    await waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument();
    });

    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "test-model",
      run_id: "run-dup-1",
    });

    // Wait a tick — count should still be 1
    await waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument();
    });
  });

  it("does not count non-lifecycle events", async () => {
    const { container } = render(<ReplaySidebarBadge />);

    sendSSEEvent({ _event_type: "TokenGeneratedEvent", token: "Hello", model: "m" });
    sendSSEEvent({ _event_type: "MetricEvent", name: "score", value: 0.9, model: "m" });
    sendSSEEvent({ _event_type: "CompletionEvent", success: true, tokens_used: 50, model: "m" });

    await waitFor(() => {
      expect(container.innerHTML).toBe("");
    });
  });

  it("persists count across component remount via sessionStorage", async () => {
    // First mount: send an event
    const { unmount } = render(<ReplaySidebarBadge />);

    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "test-model",
      run_id: "run-persist-1",
    });

    await waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument();
    });

    // Verify sessionStorage was written
    expect(sessionStorage.getItem("replay-badge-count")).toBe("1");

    // Unmount the component (simulates page navigation)
    unmount();

    // Re-mount — should read from sessionStorage
    render(<ReplaySidebarBadge />);

    await waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument();
    });

    // Send a second different run_id — should increment to 2
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "test-model",
      run_id: "run-persist-2",
    });

    await waitFor(() => {
      expect(screen.getByText("2")).toBeInTheDocument();
    });

    expect(sessionStorage.getItem("replay-badge-count")).toBe("2");
  });
});
