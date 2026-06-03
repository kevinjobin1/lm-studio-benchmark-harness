// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import LiveBenchmarkStatus from "./LiveBenchmarkStatus";

beforeEach(() => {
  // jsdom does not implement scrollIntoView
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  mockEventSourceRegistry = null;
});

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
    mockEventSourceRegistry.onmessage({ data: JSON.stringify(data) } as MessageEvent);
  }
}

function triggerSSEError() {
  if (mockEventSourceRegistry?.onerror) {
    mockEventSourceRegistry.onerror();
  }
}

// ── Tests ─────────────────────────────────────────────────────────

describe("LiveBenchmarkStatus", () => {
  it('shows "Disconnected" when SSE is not connected', async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeTruthy();
      expect(screen.getByText("0 events")).toBeTruthy();
    });
  });

  it("shows the model name when a CompletionEvent arrives", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    sendSSEEvent({
      _event_type: "CompletionEvent",
      model: "test-model-v2",
      success: true,
      response: "Hello world",
      tokens_used: 42,
      latency_ms: 1500,
      ttft_ms: 320,
      tokens_per_second: 28.0,
      provider: "test",
    });

    await waitFor(() => {
      expect(screen.getByText("test-model-v2")).toBeTruthy();
    });
  });

  it("shows token stream from TokenGeneratedEvent", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    sendSSEEvent({ _event_type: "TokenGeneratedEvent", token: "Hello", index: 0, timing_ms: 12.5, model: "m1" });
    sendSSEEvent({ _event_type: "TokenGeneratedEvent", token: " world", index: 1, timing_ms: 15.0, model: "m1" });
    sendSSEEvent({ _event_type: "TokenGeneratedEvent", token: "!", index: 2, timing_ms: 10.0, model: "m1" });

    await waitFor(() => {
      expect(screen.getByText("Hello world!")).toBeTruthy();
    });
  });

  it("shows TTFT and tokens/sec from CompletionEvent", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    sendSSEEvent({
      _event_type: "CompletionEvent",
      model: "perf-test",
      success: true,
      response: "x",
      tokens_used: 100,
      latency_ms: 2500,
      ttft_ms: 450,
      tokens_per_second: 40.0,
    });

    await waitFor(() => {
      expect(screen.getByText("450ms")).toBeTruthy();
      expect(screen.getByText("40.0")).toBeTruthy();
    });
  });

  it("shows score percentage from MetricEvent", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    sendSSEEvent({ _event_type: "MetricEvent", name: "devbench.developer_score", value: 0.785 });

    await waitFor(() => {
      expect(screen.getByText("78.5%")).toBeTruthy();
    });
  });

  it("shows running lifecycle status", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    sendSSEEvent({ _event_type: "RunLifecycleEvent", status: "started", model: "bench-model", workload: "devbench/code" });

    await waitFor(() => {
      expect(screen.getByText("Running")).toBeTruthy();
    });
  });

  it("shows an error banner on ErrorEvent", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    sendSSEEvent({ _event_type: "ErrorEvent", message: "Connection refused", exception: "ConnectionError", component: "workload_runner" });

    await waitFor(() => {
      expect(screen.getByText("ConnectionError")).toBeTruthy();
      expect(screen.getByText("Connection refused")).toBeTruthy();
    });
  });

  it("shows completion summary when a successful completion arrives", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    sendSSEEvent({
      _event_type: "CompletionEvent",
      model: "summ-model",
      success: true,
      response: "Generated code",
      tokens_used: 150,
      latency_ms: 3200,
      ttft_ms: 500,
      tokens_per_second: 46.9,
    });

    await waitFor(() => {
      expect(screen.getByText("Response generated")).toBeTruthy();
      expect(screen.getByText(/150 tokens/)).toBeTruthy();
    });
  });

  it("shows lifecycle chips for multiple lifecycle events", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    sendSSEEvent({ _event_type: "RunLifecycleEvent", status: "started", model: "m2" });
    sendSSEEvent({ _event_type: "RunLifecycleEvent", status: "completed", model: "m2", duration_ms: 5000 });

    await waitFor(() => {
      expect(screen.getAllByText("started").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("completed").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows event count increasing", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    sendSSEEvent({ _event_type: "TokenGeneratedEvent", token: "a", index: 0, timing_ms: 1, model: "m" });
    sendSSEEvent({ _event_type: "TokenGeneratedEvent", token: "b", index: 1, timing_ms: 1, model: "m" });
    sendSSEEvent({ _event_type: "MetricEvent", name: "test", value: 1.0 });

    await waitFor(() => {
      expect(screen.getByText("3 events")).toBeTruthy();
    });
  });

  it("clear button resets event count", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    sendSSEEvent({ _event_type: "MetricEvent", name: "test", value: 0.5 });

    await waitFor(() => {
      expect(screen.getByText("1 events")).toBeTruthy();
    });

    const clearBtn = screen.getByLabelText("Clear events");
    clearBtn.click();

    await waitFor(() => {
      expect(screen.getByText("0 events")).toBeTruthy();
    });
  });

  it("shows token count in metrics", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    sendSSEEvent({ _event_type: "TokenGeneratedEvent", token: "a", index: 0, timing_ms: 1, model: "m" });
    sendSSEEvent({ _event_type: "TokenGeneratedEvent", token: "b", index: 1, timing_ms: 1, model: "m" });
    sendSSEEvent({ _event_type: "TokenGeneratedEvent", token: "c", index: 2, timing_ms: 1, model: "m" });

    await waitFor(() => {
      expect(screen.getByText("3")).toBeTruthy();
    });
  });

  it("shows placeholder text when disconnected with no tokens", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    triggerSSEError();

    await waitFor(() => {
      expect(screen.getByText(/Connect to a running benchmark/)).toBeTruthy();
    });
  });

  it("updates model name from RunLifecycleEvent when CompletionEvent absent", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    sendSSEEvent({ _event_type: "RunLifecycleEvent", status: "started", model: "lifecycle-model", workload: "devbench/test" });

    await waitFor(() => {
      expect(screen.getByText("lifecycle-model")).toBeTruthy();
    });
  });

  it("gracefully handles empty events array", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    render(<LiveBenchmarkStatus />);

    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeTruthy();
      expect(screen.getByText("0 events")).toBeTruthy();
    });
  });
});
