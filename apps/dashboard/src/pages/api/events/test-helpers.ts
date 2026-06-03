// @vitest-environment node
/**
 * Shared test helpers for GET /api/events tests.
 *
 * Provides stream builders, assertion helpers, and cleanup utilities
 * reused across the split test files (response-format, disconnect,
 * retry, pipe).
 */
import { expect, vi } from "vitest";

// ── Unhandled rejection tracking ───────────────────────────────

export const unhandledRejections: Array<{ reason: unknown }> = [];

export function onUnhandledRejection(reason: unknown) {
  unhandledRejections.push({ reason });
}

// ── Decoder ─────────────────────────────────────────────────────

export const decoder = new TextDecoder();

// ── Stream builders ─────────────────────────────────────────────

/** Read a single SSE event from the stream (waits for data). */
export async function readEvent(
  reader: ReadableStreamDefaultReader<Uint8Array>,
): Promise<{ done: boolean; text: string }> {
  const { done, value } = await reader.read();
  if (done) return { done, text: "" };
  return { done: false, text: decoder.decode(value, { stream: true }) };
}

/** Create a controlled ReadableStream for the mock SSE bridge response. */
export function createBridgeStream(
  chunks: Uint8Array[],
): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(chunk);
      }
      controller.close();
    },
  });
}

/** Create a ReadableStream backed by a single SSE event that closes cleanly. */
export function singleEventStream(
  eventType: string,
  data: Record<string, unknown>,
): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(
        encoder.encode(`event: ${eventType}\ndata: ${JSON.stringify(data)}\n\n`),
      );
      controller.close();
    },
  });
}

/**
 * Return a promise that hangs until the AbortSignal fires — simulating a
 * fetch that never responds until the endpoint's AbortController timeout.
 */
export function createTimeoutResponse(options?: RequestInit): Promise<never> {
  return new Promise<never>((_resolve, reject) => {
    if (options?.signal) {
      (options.signal as AbortSignal).addEventListener("abort", () => {
        reject(new DOMException("The operation was aborted", "AbortError"));
      });
    }
  });
}

/**
 * Create a mock fetch implementation that dispatches to different handler
 * functions based on the call count (1-indexed).  Each handler receives the
 * fetch URL and options, and should return the response (or a promise).
 */
export function stagedFetch(
  ...stages: Array<(url: string, options?: RequestInit) => unknown>
) {
  let callCount = 0;
  return vi.fn().mockImplementation((url: string, options?: RequestInit) => {
    // Repeat the last stage for any calls beyond the configured stages
    const index = Math.min(callCount, stages.length - 1);
    callCount++;
    return stages[index](url, options);
  });
}

/**
 * Create a ReadableStream that emits one SSE event, then hangs forever —
 * never closing, never erroring.  Simulates a bridge that stays connected
 * but stops producing data mid-stream.
 */
export function hangingStream(
  eventType: string,
  data: Record<string, unknown>,
): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(
        encoder.encode(`event: ${eventType}\ndata: ${JSON.stringify(data)}\n\n`),
      );
    },
    pull() {
      // Return a promise that never settles — the endpoint's reader.read()
      // will hang indefinitely, simulating a bridge that never closes.
      return new Promise<undefined>(() => {});
    },
  });
}

/** Create a standard MetricEvent bridge stream that closes cleanly. */
export function successStream(
  value = 0.95,
): ReadableStream<Uint8Array> {
  return singleEventStream("MetricEvent", { name: "score", value });
}

// ── Assertion helpers ──────────────────────────────────────────

/** Assert an event is a retrying status with an expected error message. */
export function assertRetrying(event: { text: string }, errorMsg: string) {
  expect(event.text).toContain('"retrying":true');
  expect(event.text).toContain(errorMsg);
}

/** Assert the benchmark finished event. */
export function assertBenchmarkFinished(event: { text: string }) {
  expect(event.text).toContain("Benchmark finished");
}

// ── Setup / teardown lifecycle ─────────────────────────────────

/** Call in beforeEach to set up the test environment. */
export function setupTest() {
  vi.stubEnv("MODELLENS_SSE_RETRY_MS", "50");
  unhandledRejections.length = 0;
  process.on("unhandledRejection", onUnhandledRejection);
}

/** Call in afterEach to tear down the test environment. */
export function teardownTest() {
  process.off("unhandledRejection", onUnhandledRejection);
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
}

/**
 * Cancel the reader, let async operations settle, and verify clean teardown
 * (no unhandled rejections, env/mock/global state restored).
 */
export async function cleanup(
  reader: ReadableStreamDefaultReader<Uint8Array>,
): Promise<void> {
  await reader.cancel();
  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(unhandledRejections).toHaveLength(0);
  teardownTest();
}

// ── Error stream builders ──────────────────────────────────────

/**
 * Create a ReadableStream that emits one SSE event, then errors on the next
 * read attempt — simulating a bridge crash mid-stream.
 */
export function eventThenErrorStream(
  eventType: string,
  data: Record<string, unknown>,
  errorMessage: string,
): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let pulled = false;
  return new ReadableStream({
    start(controller) {
      controller.enqueue(
        encoder.encode(`event: ${eventType}\ndata: ${JSON.stringify(data)}\n\n`),
      );
    },
    pull(controller) {
      if (!pulled) {
        pulled = true;
        controller.error(new Error(errorMessage));
      }
    },
  });
}
