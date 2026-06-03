// @vitest-environment node
/**
 * Tests for GET /api/events — client disconnect handling.
 *
 * Covers canceling the reader during retry, while streaming from a bridge,
 * and without reading any prior events.
 */
import { describe, it, expect, vi } from "vitest";
import {
  cleanup,
  readEvent,
  createBridgeStream,
} from "./test-helpers";

vi.mock("../../../lib/processRegistry", () => ({
  getAll: () => [],
}));

const { GET } = await import("./index");

describe("GET /api/events — disconnect", () => {

  it("handles client disconnect during retry without unhandled rejections", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("connection refused")),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    await readEvent(reader);
    await cleanup(reader);
  });

  it("disconnect in retry loop shows no errors even without reading any events", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("bridge down")));

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    await cleanup(reader);
  });

  it("handles client disconnect while streaming bridge data without errors", async () => {
    const encoder = new TextEncoder();
    const bridgeData = encoder.encode(
      'event: TokenGeneratedEvent\ndata: {"token":"Hello"}\n\n',
    );

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          body: createBridgeStream([bridgeData]),
        })
        .mockRejectedValue(new Error("cleanup")),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    await readEvent(reader);
    await new Promise((resolve) => setTimeout(resolve, 10));
    await readEvent(reader);
    await readEvent(reader);

    await cleanup(reader);
  });

  it("handles client disconnect during streaming without ever being connected", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("bridge down")));

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    const initial = await readEvent(reader);
    expect(initial.text).toContain('"connected":false');

    const retry = await readEvent(reader);
    expect(retry.text).toContain('"retrying":true');

    await cleanup(reader);
  });
});
