// @vitest-environment node
/**
 * Tests for GET /api/events — response structure, initial status, SSE wire
 * format, and edge-case bridge streams (empty, hanging).
 */
import { describe, it, expect, vi } from "vitest";
import {
  cleanup,
  readEvent,
  hangingStream,
} from "./test-helpers";

vi.mock("../../../lib/processRegistry", () => ({
  getAll: () => [],
}));

const { GET } = await import("./index");

describe("GET /api/events — response format", () => {

  it("returns 200 with SSE headers and a readable body", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("no bridge")));

    const response = await GET({} as any);
    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toBe("text/event-stream");
    expect(response.headers.get("Cache-Control")).toBe("no-cache");
    expect(response.headers.get("Connection")).toBe("keep-alive");
    expect(response.body).toBeTruthy();

    await cleanup(response.body!.getReader());
  });

  it("sends initial _status event with connected:false and port", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("no bridge")));

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    const { text } = await readEvent(reader);
    expect(text).toContain("event: _status");
    expect(text).toContain('"connected":false');
    expect(text).toContain('"port"');
    // Initial status is sent BEFORE the retry loop, so no "retrying"
    expect(text).not.toContain('"retrying"');

    await cleanup(reader);
  });

  it("sends events in proper SSE wire format with double newline terminator", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("bridge down")));

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    const { text } = await readEvent(reader);
    // SSE format: "event: <type>\ndata: <json>\n\n"
    expect(text).toMatch(/^event: _status\ndata: .+\n\n$/);

    await cleanup(reader);
  });

  it("handles a bridge stream that closes immediately without any events", async () => {
    const emptyStream = new ReadableStream({
      start(controller) {
        controller.close();
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, body: emptyStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("Benchmark finished");

    const final = await readEvent(reader);
    expect(final.done).toBe(true);

    await cleanup(reader);
  });

  it("handles a bridge stream that never closes after sending events", async () => {
    const bridgeStream = hangingStream("MetricEvent", {
      name: "score",
      value: 0.95,
    });

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({ ok: true, body: bridgeStream })
        .mockRejectedValue(new Error("cleanup")),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("MetricEvent");
    expect(event.text).toContain('"score"');

    await cleanup(reader);
  });
});
