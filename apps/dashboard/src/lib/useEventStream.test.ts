// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useEventStream } from "./useEventStream";
import type { SSEEvent } from "./useEventStream";

// ── Mock EventSource ──────────────────────────────────────────────

let mockEsRegistry: {
  onmessage: ((event: MessageEvent) => void) | null;
  onerror: (() => void) | null;
  close: ReturnType<typeof vi.fn>;
  url: string;
} | null = null;

class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  CONNECTING = 0;
  OPEN = 1;
  CLOSED = 2;
  readyState = 1;
  url: string;
  withCredentials = false;
  close = vi.fn();
  addEventListener = vi.fn();
  removeEventListener = vi.fn();

  constructor(url: string) {
    this.url = url;
    const reg = {
      onmessage: null as ((event: MessageEvent) => void) | null,
      onerror: null as (() => void) | null,
      close: this.close,
      url,
    };
    mockEsRegistry = reg;

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
  if (mockEsRegistry?.onmessage) {
    const event = new MessageEvent("message", { data: JSON.stringify(data) });
    mockEsRegistry.onmessage(event);
  }
}

function triggerSSEError() {
  if (mockEsRegistry?.onerror) {
    mockEsRegistry.onerror();
  }
}

// ── Test helpers ─────────────────────────────────────────────────

const makeTokenEvent = (overrides: Partial<SSEEvent> = {}): Record<string, unknown> => ({
  _event_type: "TokenGeneratedEvent",
  token: "test",
  index: 0,
  timing_ms: 10,
  model: "test-model",
  ...overrides,
});

const makeMetricEvent = (overrides: Partial<SSEEvent> = {}): Record<string, unknown> => ({
  _event_type: "MetricEvent",
  name: "devbench.score",
  value: 0.85,
  ...overrides,
});

// ── Setup / teardown ─────────────────────────────────────────────

beforeEach(() => {
  mockEsRegistry = null;
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  mockEsRegistry = null;
});

// ══════════════════════════════════════════════════════════════════
// Initial state
// ══════════════════════════════════════════════════════════════════

describe("initial state", () => {
  it("starts disconnected with no events", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    expect(result.current.connected).toBe(false);
    expect(result.current.events).toEqual([]);
    expect(result.current.eventCount).toBe(0);
    expect(result.current.latestByType).toEqual({});
  });

  it("returns an empty array from getEventsByType", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    expect(result.current.getEventsByType("TokenGeneratedEvent")).toEqual([]);
  });

  it("clearEvents is a stable function reference", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result, rerender } = renderHook(() => useEventStream());

    const firstRef = result.current.clearEvents;
    rerender();
    expect(result.current.clearEvents).toBe(firstRef);
  });
});

// ══════════════════════════════════════════════════════════════════
// Connect / disconnect
// ══════════════════════════════════════════════════════════════════

describe("connect / disconnect", () => {
  it("sets connected=true on _status event with connected: true", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      sendSSEEvent({ _event_type: "_status", connected: true, port: 9090 });
    });

    await waitFor(() => {
      expect(result.current.connected).toBe(true);
    });
  });

  it("sets connected=false on onerror", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    // First connect
    act(() => {
      sendSSEEvent({ _event_type: "_status", connected: true, port: 9090 });
    });

    await waitFor(() => {
      expect(result.current.connected).toBe(true);
    });

    // Then error
    act(() => {
      triggerSSEError();
    });

    await waitFor(() => {
      expect(result.current.connected).toBe(false);
    });
  });

  it("sets connected=false on _status with connected: false", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      sendSSEEvent({ _event_type: "_status", connected: true, port: 9090 });
    });

    await waitFor(() => {
      expect(result.current.connected).toBe(true);
    });

    act(() => {
      sendSSEEvent({
        _event_type: "_status",
        connected: false,
        message: "Benchmark finished",
      });
    });

    await waitFor(() => {
      expect(result.current.connected).toBe(false);
    });
  });

  it("does not add _status events with connected field to the events array", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      sendSSEEvent({ _event_type: "_status", connected: true, port: 9090 });
    });

    await waitFor(() => {
      // Event count stays 0 because _status with connected is internal
      expect(result.current.eventCount).toBe(0);
    });
  });
});

// ══════════════════════════════════════════════════════════════════
// Event accumulation
// ══════════════════════════════════════════════════════════════════

describe("event accumulation", () => {
  it("collects regular events in order", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      sendSSEEvent(makeTokenEvent({ token: "Hello", index: 0 }));
      sendSSEEvent(makeTokenEvent({ token: " world", index: 1 }));
    });

    await waitFor(() => {
      expect(result.current.eventCount).toBe(2);
      expect(result.current.events[0].token).toBe("Hello");
      expect(result.current.events[1].token).toBe(" world");
    });
  });

  it("increments eventCount as events arrive", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      sendSSEEvent(makeTokenEvent());
    });
    await waitFor(() => {
      expect(result.current.eventCount).toBe(1);
    });

    act(() => {
      sendSSEEvent(makeMetricEvent());
    });
    await waitFor(() => {
      expect(result.current.eventCount).toBe(2);
    });

    act(() => {
      sendSSEEvent(makeTokenEvent({ index: 1 }));
    });
    await waitFor(() => {
      expect(result.current.eventCount).toBe(3);
    });
  });

  it("collects events of different types interleaved", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      sendSSEEvent(makeTokenEvent({ token: "a", index: 0 }));
      sendSSEEvent(makeMetricEvent({ name: "score", value: 0.9 }));
      sendSSEEvent(makeTokenEvent({ token: "b", index: 1 }));
    });

    await waitFor(() => {
      expect(result.current.eventCount).toBe(3);
      expect(result.current.getEventsByType("TokenGeneratedEvent").length).toBe(2);
      expect(result.current.getEventsByType("MetricEvent").length).toBe(1);
    });
  });

  it("adds _status events without connected field to events array", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      // _status with connected field — internal, not added
      sendSSEEvent({ _event_type: "_status", connected: true, port: 9090 });
      // _status without connected field — should be added
      sendSSEEvent({ _event_type: "_status", message: "custom status update" });
    });

    await waitFor(() => {
      // Only the second one should be in the array
      expect(result.current.eventCount).toBe(1);
      expect(result.current.events[0]._event_type).toBe("_status");
    });
  });
});

// ══════════════════════════════════════════════════════════════════
// getEventsByType
// ══════════════════════════════════════════════════════════════════

describe("getEventsByType", () => {
  it("returns all events of the requested type", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      sendSSEEvent(makeTokenEvent({ token: "a", index: 0 }));
      sendSSEEvent(makeMetricEvent({ name: "m1", value: 0.5 }));
      sendSSEEvent(makeTokenEvent({ token: "b", index: 1 }));
      sendSSEEvent(makeMetricEvent({ name: "m2", value: 0.9 }));
    });

    await waitFor(() => {
      const tokens = result.current.getEventsByType("TokenGeneratedEvent");
      expect(tokens.length).toBe(2);
      expect(tokens[0].token).toBe("a");
      expect(tokens[1].token).toBe("b");
    });
  });

  it("returns empty array when no events of that type exist", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      sendSSEEvent(makeTokenEvent());
    });

    await waitFor(() => {
      expect(result.current.getEventsByType("CompletionEvent")).toEqual([]);
      expect(result.current.getEventsByType("RunLifecycleEvent")).toEqual([]);
    });
  });

  it("returns empty array when no events at all", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    expect(result.current.getEventsByType("TokenGeneratedEvent")).toEqual([]);
  });


});

// ══════════════════════════════════════════════════════════════════
// latestByType
// ══════════════════════════════════════════════════════════════════

describe("latestByType", () => {
  it("maps the latest event of each type", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      sendSSEEvent(makeTokenEvent({ index: 0, token: "first" }));
      sendSSEEvent(makeMetricEvent({ name: "m1", value: 0.5 }));
      sendSSEEvent(makeTokenEvent({ index: 1, token: "latest" }));
    });

    await waitFor(() => {
      expect(result.current.latestByType.TokenGeneratedEvent?.token).toBe("latest");
      expect(result.current.latestByType.MetricEvent?.value).toBe(0.5);
    });
  });

  it("is empty when no events have been received", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    expect(result.current.latestByType).toEqual({});
  });

  it("later events override earlier ones of the same type", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      sendSSEEvent(makeMetricEvent({ name: "score", value: 0.3 }));
      sendSSEEvent(makeMetricEvent({ name: "score", value: 0.9 }));
    });

    await waitFor(() => {
      expect(result.current.latestByType.MetricEvent?.value).toBe(0.9);
    });
  });
});

// ══════════════════════════════════════════════════════════════════
// clearEvents
// ══════════════════════════════════════════════════════════════════

describe("clearEvents", () => {
  it("resets events to empty array", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      sendSSEEvent(makeTokenEvent());
      sendSSEEvent(makeMetricEvent());
    });

    await waitFor(() => {
      expect(result.current.eventCount).toBe(2);
    });

    act(() => {
      result.current.clearEvents();
    });

    await waitFor(() => {
      expect(result.current.events).toEqual([]);
      expect(result.current.eventCount).toBe(0);
      expect(result.current.latestByType).toEqual({});
    });
  });

  it("new events still accumulate after clear", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      sendSSEEvent(makeTokenEvent({ index: 0 }));
    });

    await waitFor(() => {
      expect(result.current.eventCount).toBe(1);
    });

    act(() => {
      result.current.clearEvents();
    });

    await waitFor(() => {
      expect(result.current.eventCount).toBe(0);
    });

    act(() => {
      sendSSEEvent(makeTokenEvent({ index: 1 }));
    });

    await waitFor(() => {
      expect(result.current.eventCount).toBe(1);
      expect(result.current.events[0].index).toBe(1);
    });
  });

  it("clearEvents is referentially stable across renders", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result, rerender } = renderHook(() => useEventStream());

    const firstRef = result.current.clearEvents;
    rerender();
    expect(result.current.clearEvents).toBe(firstRef);
  });
});

// ══════════════════════════════════════════════════════════════════
// Edge cases
// ══════════════════════════════════════════════════════════════════

describe("edge cases", () => {
  it("silently ignores malformed JSON", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      // Valid event
      sendSSEEvent(makeTokenEvent());
      // Malformed — should be ignored
      if (mockEsRegistry?.onmessage) {
        mockEsRegistry.onmessage({ data: "not valid json" } as unknown as MessageEvent);
      }
      // Valid event after malformed one
      sendSSEEvent(makeTokenEvent({ index: 1 }));
    });

    await waitFor(() => {
      // Only the two valid events should be counted
      expect(result.current.eventCount).toBe(2);
    });
  });

  it("handles empty data string gracefully", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      if (mockEsRegistry?.onmessage) {
        mockEsRegistry.onmessage({ data: "" } as unknown as MessageEvent);
      }
    });

    // No crash — eventCount stays 0
    expect(result.current.eventCount).toBe(0);
  });

  it("trims events at MAX_BUFFERED_EVENTS (5000)", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      // Send 5001 events
      for (let i = 0; i < 5001; i++) {
        sendSSEEvent(makeTokenEvent({ index: i, token: `t${i}` }));
      }
    });

    await waitFor(() => {
      expect(result.current.eventCount).toBe(5000);
      // The first event (index 0) should have been trimmed
      expect(result.current.events[0].index).toBe(1);
      // The last event should be index 5000
      expect(result.current.events[4999].index).toBe(5000);
    });
  });

  it("closes the previous EventSource when url changes", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result, rerender } = renderHook(
      (url: string = "/api/events") => useEventStream(url),
    );

    // Initial mount creates EventSource
    const firstClose = mockEsRegistry?.close;
    expect(firstClose).toBeDefined();

    // Rerender with new url
    rerender("/api/events-custom");

    await waitFor(() => {
      // Old EventSource should be closed
      expect(firstClose).toHaveBeenCalledTimes(1);
    });
  });

  it("cleanup on unmount closes the EventSource", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result, unmount } = renderHook(() => useEventStream());

    const closeSpy = mockEsRegistry?.close;

    unmount();

    expect(closeSpy).toHaveBeenCalledTimes(1);
  });

  it("does not update state after unmount", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result, unmount } = renderHook(() => useEventStream());

    unmount();

    // Sending an event after unmount should not cause state updates
    act(() => {
      sendSSEEvent(makeTokenEvent());
    });

    // The hook should not have updated
    expect(result.current.eventCount).toBe(0);
  });

  it("handles events with unexpected extra fields", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    act(() => {
      sendSSEEvent({
        _event_type: "CustomEvent",
        arbitraryField: "value",
        nested: { key: "val" },
        numberField: 42,
      });
    });

    await waitFor(() => {
      expect(result.current.eventCount).toBe(1);
      expect(result.current.events[0].arbitraryField).toBe("value");
      expect(result.current.events[0].numberField).toBe(42);
    });
  });
});

// ══════════════════════════════════════════════════════════════════
// Integration: multiple event types lifecycle
// ══════════════════════════════════════════════════════════════════

describe("event lifecycle integration", () => {
  it("simulates a complete benchmark run event sequence", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useEventStream());

    // 1. Connect
    act(() => {
      sendSSEEvent({ _event_type: "_status", connected: true, port: 9090 });
    });

    await waitFor(() => {
      expect(result.current.connected).toBe(true);
    });

    // 2. Run started
    act(() => {
      sendSSEEvent({
        _event_type: "RunLifecycleEvent",
        status: "started",
        model: "qwen-9b",
        workload: "devbench/code",
      });
    });

    // 3. Token streaming
    act(() => {
      for (let i = 0; i < 5; i++) {
        sendSSEEvent(makeTokenEvent({ index: i, token: `word${i} ` }));
      }
    });

    // 4. Score metric
    act(() => {
      sendSSEEvent(makeMetricEvent({ name: "devbench.score", value: 0.82 }));
    });

    // 5. Completion
    act(() => {
      sendSSEEvent({
        _event_type: "CompletionEvent",
        model: "qwen-9b",
        success: true,
        response: "Generated code",
        tokens_used: 150,
        latency_ms: 3200,
        ttft_ms: 450,
        tokens_per_second: 46.9,
      });
    });

    // 6. Run completed
    act(() => {
      sendSSEEvent({
        _event_type: "RunLifecycleEvent",
        status: "completed",
        model: "qwen-9b",
        duration_ms: 5000,
      });
    });

    await waitFor(() => {
      // Verify accumulated state
      // 5 tokens + 1 lifecycle(started) + 1 metric + 1 completion + 1 lifecycle(completed) = 9 total
      expect(result.current.eventCount).toBe(9);
      expect(result.current.getEventsByType("TokenGeneratedEvent").length).toBe(5);
      expect(result.current.getEventsByType("MetricEvent").length).toBe(1);
      expect(result.current.getEventsByType("CompletionEvent").length).toBe(1);
      expect(result.current.getEventsByType("RunLifecycleEvent").length).toBe(2);

      // Check latestByType
      expect(result.current.latestByType.CompletionEvent?.tokens_used).toBe(150);
      expect(result.current.latestByType.MetricEvent?.value).toBe(0.82);
      expect(result.current.latestByType.RunLifecycleEvent?.status).toBe("completed");
    });

    // 7. Disconnect
    act(() => {
      sendSSEEvent({ _event_type: "_status", connected: false, message: "Done" });
    });

    await waitFor(() => {
      expect(result.current.connected).toBe(false);
      // _status with connected still not counted — eventCount unchanged
      expect(result.current.eventCount).toBe(9);
    });
  });
});
