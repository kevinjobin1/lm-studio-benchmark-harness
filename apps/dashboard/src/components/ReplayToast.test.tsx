// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import ReplayToast from "./ReplayToast";

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

describe("ReplayToast", () => {
  beforeEach(() => {
    vi.stubGlobal("EventSource", MockEventSource);
    // Use shouldAdvanceTime so waitFor polling (which uses setTimeout
    // internally) still works — timers advance with real wall-clock time
    // while vi.advanceTimersByTime still works for controlled advancement.
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    mockEventSourceRegistry = null;
  });

  it("does not render when no events have arrived", async () => {
    const { container } = render(<ReplayToast />);
    // Should be empty — no toast visible
    expect(container.innerHTML).toBe("");
  });

  it("shows toast on RunLifecycleEvent with status=completed", async () => {
    render(<ReplayToast />);

    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "qwen3.5-9b-coder",
      run_id: "run-abc-123",
      duration_ms: 5000,
    });

    await waitFor(() => {
      expect(screen.getByText("Replay recorded")).toBeInTheDocument();
      expect(screen.getByText(/qwen3.5-9b-coder/)).toBeInTheDocument();
      expect(screen.getByText(/completed/)).toBeInTheDocument();
    });

    // Toast links to /replays?run_id=...
    const link = screen.getByRole("status").closest("a");
    expect(link?.getAttribute("href")).toBe("/replays?run_id=run-abc-123");
  });

  it("shows toast on RunLifecycleEvent with status=failed", async () => {
    render(<ReplayToast />);

    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "failed",
      model: "llama3.2-3b",
      run_id: "run-def-456",
    });

    await waitFor(() => {
      expect(screen.getByText("Replay failed")).toBeInTheDocument();
      expect(screen.getByText(/llama3.2-3b/)).toBeInTheDocument();
    });
  });

  it("does not show toast for RunLifecycleEvent with status=started", async () => {
    const { container } = render(<ReplayToast />);

    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "started",
      model: "test-model",
      run_id: "run-started-1",
    });

    // No toast should appear — wait a tick to ensure no state change
    await waitFor(() => {
      expect(container.innerHTML).toBe("");
    });
  });

  it("does not show duplicate toasts for the same run_id", async () => {
    render(<ReplayToast />);

    // First completion
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "test-model",
      run_id: "run-dup-1",
    });

    await waitFor(() => {
      expect(screen.getByText("Replay recorded")).toBeInTheDocument();
    });

    // Dismiss the current toast by advancing past the timeout
    act(() => {
      vi.advanceTimersByTime(6000);
    });

    await waitFor(() => {
      expect(screen.queryByText("Replay recorded")).not.toBeInTheDocument();
    });

    // Send the same run_id again — should still not show (already notified)
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "test-model",
      run_id: "run-dup-1",
    });

    await waitFor(() => {
      expect(screen.queryByText("Replay recorded")).not.toBeInTheDocument();
    });
  });

  it("shows toast for a new run_id after a different one was dismissed", async () => {
    render(<ReplayToast />);

    // First completion
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "model-a",
      run_id: "run-a",
    });

    await waitFor(() => {
      expect(screen.getByText("Replay recorded")).toBeInTheDocument();
    });

    // Dismiss by advancing past timeout
    act(() => {
      vi.advanceTimersByTime(6000);
    });

    await waitFor(() => {
      expect(screen.queryByText("Replay recorded")).not.toBeInTheDocument();
    });

    // Second completion with different run_id
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "model-b",
      run_id: "run-b",
    });

    await waitFor(() => {
      expect(screen.getByText("Replay recorded")).toBeInTheDocument();
      expect(screen.getByText(/model-b/)).toBeInTheDocument();
    });
  });

  it("auto-dismisses the toast after 6 seconds", async () => {
    render(<ReplayToast />);

    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "test-model",
      run_id: "run-auto-1",
    });

    await waitFor(() => {
      expect(screen.getByText("Replay recorded")).toBeInTheDocument();
    });

    // Advance past the 6-second auto-dismiss
    act(() => {
      vi.advanceTimersByTime(6000);
    });

    await waitFor(() => {
      expect(screen.queryByText("Replay recorded")).not.toBeInTheDocument();
    });
  });

  it("does not toast for non-lifecycle events", async () => {
    const { container } = render(<ReplayToast />);

    sendSSEEvent({ _event_type: "TokenGeneratedEvent", token: "Hello", index: 0, timing_ms: 12, model: "m" });
    sendSSEEvent({ _event_type: "MetricEvent", name: "score", value: 0.9, model: "m" });
    sendSSEEvent({ _event_type: "CompletionEvent", success: true, tokens_used: 50, model: "m" });

    await waitFor(() => {
      expect(container.innerHTML).toBe("");
    });
  });

  it("shows truncated run_id in toast description", async () => {
    render(<ReplayToast />);

    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "test-model",
      run_id: "run-very-long-id-that-should-be-truncated",
    });

    await waitFor(() => {
      // Should show first 12 characters: "run-very-lon"
      const desc = screen.getByText(/run-very-lon/);
      expect(desc).toBeInTheDocument();
    });
  });
});
