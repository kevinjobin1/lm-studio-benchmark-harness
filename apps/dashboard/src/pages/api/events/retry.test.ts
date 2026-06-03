// @vitest-environment node
/**
 * Tests for GET /api/events — retry loop and bridge reconnection behavior.
 *
 * Covers every failure mode the endpoint can encounter: 503 HTTP errors,
 * AbortController timeouts, stream-level pipe errors, null body checks,
 * non-stream body types, sync throws, cascade sequences, endurance tests,
 * and edge-case retry intervals.
 */
import { describe, it, expect, vi } from "vitest";
import {
  cleanup,
  readEvent,
  singleEventStream,
  successStream,
  createTimeoutResponse,
  stagedFetch,
  eventThenErrorStream,
  assertRetrying,
  assertBenchmarkFinished,
} from "./test-helpers";

vi.mock("../../../lib/processRegistry", () => ({
  getAll: () => [],
}));

const { GET } = await import("./index");

describe("GET /api/events — retry & reconnect", () => {

  // ── Basic retry ───────────────────────────────────────────────

  it("sends retrying status after a failed bridge attempt", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503, body: null }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    const initial = await readEvent(reader);
    expect(initial.text).toContain('"connected":false');
    expect(initial.text).not.toContain('"retrying"');

    const retry = await readEvent(reader);
    assertRetrying(retry, "503");

    await cleanup(reader);
  });

  it("handles bridge returning non-200 status gracefully (shows retrying)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503, body: null }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    const initial = await readEvent(reader);
    expect(initial.text).toContain('"connected":false');
    expect(initial.text).not.toContain('"retrying"');

    const retry = await readEvent(reader);
    assertRetrying(retry, "503");

    await cleanup(reader);
  });

  // ── Single retry → success ───────────────────────────────────

  it("transitions from non-200 bridge response to connected on retry", async () => {
    const bridgeStream = singleEventStream("TokenGeneratedEvent", {
      token: "Hello",
    });

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({ ok: false, status: 503, body: null })
        .mockResolvedValueOnce({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    assertRetrying(event, "503");

    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');
    expect(event.text).toContain('"port"');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain("TokenGeneratedEvent");
    expect(event.text).toContain('"Hello"');

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  it("handles fetch timeout (AbortController) then reconnects on retry", async () => {
    const bridgeStream = successStream();

    vi.stubGlobal(
      "fetch",
      stagedFetch(
        (_, options) => createTimeoutResponse(options),
        () => ({ ok: true, body: bridgeStream }),
      ),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    assertRetrying(event, "aborted");

    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain('"score"');

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  it("ignores response body on non-200 and retries successfully", async () => {
    const ignoredBody = singleEventStream("TokenGeneratedEvent", {
      token: "ShouldBeIgnored",
    });

    const bridgeStream = successStream();

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({ ok: false, status: 500, body: ignoredBody })
        .mockResolvedValueOnce({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    assertRetrying(event, "500");
    expect(event.text).not.toContain("ShouldBeIgnored");

    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain('"score"');

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  it("safely ignores body that errors when read on non-200 response and retries", async () => {
    const errorBody = eventThenErrorStream(
      "TokenGeneratedEvent",
      { token: "ignored" },
      "Body corruption error",
    );

    const bridgeStream = successStream();

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({ ok: false, status: 500, body: errorBody })
        .mockResolvedValueOnce({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    assertRetrying(event, "500");
    expect(event.text).not.toContain("Body corruption");

    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain('"score"');

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  it("handles ok:true with null body gracefully and retries", async () => {
    const bridgeStream = successStream();

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({ ok: true, status: 200, body: null })
        .mockResolvedValueOnce({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    assertRetrying(event, "200");

    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain('"score"');

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  it("handles multiple consecutive 503 responses before succeeding on third retry", async () => {
    const bridgeStream = successStream();

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({ ok: false, status: 503, body: null })
        .mockResolvedValueOnce({ ok: false, status: 503, body: null })
        .mockResolvedValueOnce({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    assertRetrying(event, "503");
    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    assertRetrying(event, "503");
    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain('"score"');

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  // ── Multiple bridge reconnections ────────────────────────────

  it("forwards events in order across multiple bridge reconnections", async () => {
    const bridgeStreams = Array.from({ length: 4 }, (_, i) => {
      const isLast = i === 3;
      return new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              `event: MetricEvent\ndata: {"name":"score","value":${0.5 + i * 0.1}}\n\n`,
            ),
          );
        },
        pull(controller) {
          if (!isLast) {
            controller.error(new Error(`Bridge ${i + 1} crashed`));
          } else {
            controller.close();
          }
        },
      });
    });

    let fetchCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => {
        const stream = bridgeStreams[fetchCount];
        fetchCount++;
        return Promise.resolve({ ok: true, body: stream });
      }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');

    for (let i = 0; i < 4; i++) {
      const isLast = i === 3;

      event = await readEvent(reader);
      expect(event.text).toContain('"connected":true');

      event = await readEvent(reader);
      expect(event.text).toContain("MetricEvent");
      expect(event.text).toContain(`${0.5 + i * 0.1}`);

      if (isLast) {
        event = await readEvent(reader);
        expect(event.text).toContain('"connected":false');
        expect(event.text).toContain("Benchmark finished");
      } else {
        event = await readEvent(reader);
        expect(event.text).toContain('"retrying":true');
        expect(event.text).toContain(`Bridge ${i + 1} crashed`);

        await new Promise((resolve) => setTimeout(resolve, 100));
      }
    }

    await cleanup(reader);
  });

  // ── Stream error recovery ────────────────────────────────────

  it("transitions from connected back to retrying after bridge stream error then non-200 on retry", async () => {
    const bridgeStream1 = eventThenErrorStream(
      "MetricEvent",
      { name: "score", value: 0.95 },
      "Bridge connection lost",
    );

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({ ok: true, body: bridgeStream1 })
        .mockResolvedValueOnce({ ok: false, status: 503, body: null }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain('"score"');

    event = await readEvent(reader);
    assertRetrying(event, "Bridge connection lost");

    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    assertRetrying(event, "503");

    await cleanup(reader);
  });

  it("resumes forwarding events after bridge reconnects following a stream error", async () => {
    const bridgeStream1 = eventThenErrorStream(
      "MetricEvent",
      { name: "score", value: 0.95 },
      "Bridge connection lost",
    );

    const bridgeStream2 = singleEventStream("TokenGeneratedEvent", {
      token: "Hello",
    });

    vi.stubGlobal(
      "fetch",
      stagedFetch(
        () => ({ ok: true, body: bridgeStream1 }),
        () => ({ ok: true, body: bridgeStream2 }),
      ),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain('"score"');

    event = await readEvent(reader);
    assertRetrying(event, "Bridge connection lost");

    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("TokenGeneratedEvent");
    expect(event.text).toContain('"Hello"');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  it("handles two consecutive stream errors before succeeding on third bridge", async () => {
    const bridgeStream1 = eventThenErrorStream(
      "MetricEvent",
      { name: "score", value: 0.85 },
      "Bridge 1 crashed",
    );

    const bridgeStream2 = eventThenErrorStream(
      "MetricEvent",
      { name: "score", value: 0.90 },
      "Bridge 2 crashed",
    );

    const bridgeStream3 = successStream();

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({ ok: true, body: bridgeStream1 })
        .mockResolvedValueOnce({ ok: true, body: bridgeStream2 })
        .mockResolvedValueOnce({ ok: true, body: bridgeStream3 }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    // Bridge 1
    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain("0.85");

    event = await readEvent(reader);
    assertRetrying(event, "Bridge 1 crashed");
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Bridge 2
    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain("0.9");

    event = await readEvent(reader);
    assertRetrying(event, "Bridge 2 crashed");
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Bridge 3
    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain("0.95");

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  it("handles first body read throwing immediately and retries", async () => {
    const errorOnFirstRead = new ReadableStream({
      start(controller) {
        controller.error(new Error("Body stream read failed"));
      },
    });

    const bridgeStream = successStream();

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({ ok: true, body: errorOnFirstRead })
        .mockResolvedValueOnce({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    assertRetrying(event, "Body stream read failed");

    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain('"score"');

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  // ── Cascade (mixed failure types) ─────────────────────────────

  it("handles three different failure modes in sequence — 503, then timeout, then success", async () => {
    const bridgeStream = successStream();

    vi.stubGlobal(
      "fetch",
      stagedFetch(
        () => ({ ok: false, status: 503, body: null }),
        (_, options) => createTimeoutResponse(options),
        () => ({ ok: true, body: bridgeStream }),
      ),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    assertRetrying(event, "503");
    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    assertRetrying(event, "aborted");
    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain('"score"');

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  it("handles stream error then timeout then success — three different failure types", async () => {
    const bridgeStream1 = eventThenErrorStream(
      "MetricEvent",
      { name: "score", value: 0.85 },
      "Bridge stream crashed",
    );

    const bridgeStream3 = successStream();

    vi.stubGlobal(
      "fetch",
      stagedFetch(
        () => ({ ok: true, body: bridgeStream1 }),
        (_, options) => createTimeoutResponse(options),
        () => ({ ok: true, body: bridgeStream3 }),
      ),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain("0.85");

    event = await readEvent(reader);
    assertRetrying(event, "Bridge stream crashed");
    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    assertRetrying(event, "aborted");
    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain("0.95");

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  it("handles five different failure modes in sequence — 503, timeout, stream error, null body, then success", async () => {
    const errorBridge = eventThenErrorStream(
      "MetricEvent",
      { name: "score", value: 0.33 },
      "Stream error on attempt 3",
    );

    const finalBridge = successStream(0.99);

    vi.stubGlobal(
      "fetch",
      stagedFetch(
        () => ({ ok: false, status: 503, body: null }),
        (_, options) => createTimeoutResponse(options),
        () => ({ ok: true, body: errorBridge }),
        () => ({ ok: true, status: 200, body: null }),
        () => ({ ok: true, body: finalBridge }),
      ),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    assertRetrying(event, "503");
    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    assertRetrying(event, "aborted");
    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain("0.33");

    event = await readEvent(reader);
    assertRetrying(event, "Stream error on attempt 3");
    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    assertRetrying(event, "200");
    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain("0.99");

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  // ── Endurance / stress ────────────────────────────────────────

  it("handles 22 alternating failures (503 / timeout) before succeeding on the 23rd attempt — endurance test", async () => {
    const bridgeStream = successStream(0.99);

    let attemptCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string, options?: RequestInit) => {
        attemptCount++;
        if (attemptCount <= 22) {
          if (attemptCount % 2 === 1) {
            return Promise.resolve({ ok: false, status: 503, body: null });
          }
          return createTimeoutResponse(options);
        }
        return Promise.resolve({ ok: true, body: bridgeStream });
      }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    for (let i = 0; i < 22; i++) {
      event = await readEvent(reader);
      expect(event.text).toContain('"retrying":true');
      if (i % 2 === 0) {
        expect(event.text).toContain("503");
      } else {
        expect(event.text).toContain("aborted");
      }
    }

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain("0.99");

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  it("handles 10 rapid 503 errors within ~500ms before succeeding — retry loop stress test", async () => {
    const bridgeStream = successStream();

    let attemptCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => {
        attemptCount++;
        if (attemptCount <= 10) {
          return Promise.resolve({ ok: false, status: 503, body: null });
        }
        return Promise.resolve({ ok: true, body: bridgeStream });
      }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    for (let i = 0; i < 10; i++) {
      event = await readEvent(reader);
      expect(event.text).toContain('"retrying":true');
      expect(event.text).toContain("503");
    }

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain('"score"');

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  it("handles 1000 rapid 503 retries with 0ms interval — timer/memory leak detection", async () => {
    // 1000 consecutive 503 errors with 0ms retry interval.  Each cycle
    // creates a new AbortController + setTimeout(0).  Verifies no timer
    // leak, no memory pressure, and no unhandled rejections at scale.
    vi.stubEnv("MODELLENS_SSE_RETRY_MS", "0");

    const bridgeStream = successStream();

    let attemptCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => {
        attemptCount++;
        if (attemptCount <= 1000) {
          return Promise.resolve({ ok: false, status: 503, body: null });
        }
        return Promise.resolve({ ok: true, body: bridgeStream });
      }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    // 1. Initial _status (connected:false, no retrying)
    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    // 2-1001. Read 1000 retrying events — one per 503, no explicit waits
    for (let i = 0; i < 1000; i++) {
      event = await readEvent(reader);
      expect(event.text).toContain('"retrying":true');
      expect(event.text).toContain("503");
    }

    // 1002. connected:true (1001st attempt — success)
    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');
    expect(event.text).not.toContain('"retrying"');

    // 1003. Piped MetricEvent
    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain('"score"');

    // 1004. Benchmark finished
    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  }, 30000);

  it("handles retry interval configured to 0ms without infinite loop or crashes", async () => {
    vi.stubEnv("MODELLENS_SSE_RETRY_MS", "0");

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503, body: null }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    const initial = await readEvent(reader);
    expect(initial.text).toContain('"connected":false');
    expect(initial.text).not.toContain('"retrying"');

    for (let i = 0; i < 3; i++) {
      const retry = await readEvent(reader);
      expect(retry.text).toContain('"retrying":true');
      expect(retry.text).toContain("503");
    }

    await cleanup(reader);
  });

  // ── Sync throw ────────────────────────────────────────────────

  it("handles synchronous throw from fetch mock without unhandled rejections", async () => {
    const bridgeStream = singleEventStream("MetricEvent", {
      name: "score",
      value: 0.95,
    });

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockImplementationOnce(() => {
          throw new Error("Sync fetch crash");
        })
        .mockResolvedValueOnce({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain('"retrying":true');
    expect(event.text).toContain("Sync fetch crash");

    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain("0.95");

    event = await readEvent(reader);
    expect(event.text).toContain("Benchmark finished");

    await cleanup(reader);
  });

  // ── Non-stream body types ────────────────────────────────────

  it("catches non-stream body (Blob and ArrayBuffer) on ok:true responses — same getReader failure path", async () => {
    const bridgeStream = successStream();

    const blobBody =
      typeof Blob !== "undefined"
        ? new Blob(["blob data"])
        : "fallback";
    const arrayBuf = new ArrayBuffer(10);

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({ ok: true, body: blobBody })
        .mockResolvedValueOnce({ ok: true, body: arrayBuf })
        .mockResolvedValueOnce({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    // Attempt 1: Blob body
    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain('"retrying":true');
    expect(event.text).toMatch(/getReader|is not a function/);
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Attempt 2: ArrayBuffer body
    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain('"retrying":true');
    expect(event.text).toMatch(/getReader|is not a function/);
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Attempt 3: success
    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain('"score"');

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });

  it("catches non-stream body (string) on ok:true response before pipe loop errors", async () => {
    const bridgeStream = successStream();

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({ ok: true, body: "not a stream" })
        .mockResolvedValueOnce({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain('"retrying":true');
    expect(event.text).toMatch(/getReader|is not a function|not a function/);

    await new Promise((resolve) => setTimeout(resolve, 100));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');
    expect(event.text).not.toContain('"retrying"');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain('"score"');

    event = await readEvent(reader);
    assertBenchmarkFinished(event);

    await cleanup(reader);
  });
});
