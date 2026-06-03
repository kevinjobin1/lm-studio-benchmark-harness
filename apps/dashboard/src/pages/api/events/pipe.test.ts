// @vitest-environment node
/**
 * Tests for GET /api/events — data piping through the TransformStream.
 *
 * Covers binary passthrough, large chunks, multi-chunk ordering, async
 * pull() delivery, connected:true ordering, mid-pull errors, and large
 * SSE event lines.
 */
import { describe, it, expect, vi } from "vitest";
import {
  cleanup,
  readEvent,
  createBridgeStream,
  successStream,
} from "./test-helpers";

vi.mock("../../../lib/processRegistry", () => ({
  getAll: () => [],
}));

const { GET } = await import("./index");

const decoder = new TextDecoder();

describe("GET /api/events — pipe", () => {

  // ── Basic forwarding ──────────────────────────────────────────

  it("forwards bridge events through the stream", async () => {
    const encoder = new TextEncoder();
    const bridgeEvent = encoder.encode(
      'event: MetricEvent\ndata: {"name":"score","value":0.95}\n\n',
    );

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: createBridgeStream([bridgeEvent]),
      }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    await readEvent(reader);
    await new Promise((resolve) => setTimeout(resolve, 10));

    const connectedEvent = await readEvent(reader);
    expect(connectedEvent.text).toContain('"connected":true');

    const forwarded = await readEvent(reader);
    expect(forwarded.text).toContain("MetricEvent");
    expect(forwarded.text).toContain('"score"');
    expect(forwarded.text).toContain("0.95");

    const finished = await readEvent(reader);
    expect(finished.text).toContain("Benchmark finished");

    await cleanup(reader);
  });

  // ── Binary passthrough ────────────────────────────────────────

  it("pipes binary data from the bridge through the SSE stream unchanged", async () => {
    const binaryData = new Uint8Array([
      0x00, 0xFF, 0xAB, 0x7F, 0x00, 0x01, 0x02, 0x80, 0xDE, 0xAD, 0xBE, 0xEF,
    ]);

    const bridgeStream = new ReadableStream({
      start(controller) {
        controller.enqueue(binaryData);
        controller.close();
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    const { done, value } = await reader.read();
    expect(done).toBe(false);
    expect(value).toBeDefined();
    expect(Array.from(value!)).toEqual(Array.from(binaryData));

    event = await readEvent(reader);
    expect(event.text).toContain("Benchmark finished");

    await cleanup(reader);
  });

  // ── Large chunks ──────────────────────────────────────────────

  it("handles a very large bridge chunk (100KB) without issues", async () => {
    const size = 100 * 1024;
    const largeData = new Uint8Array(size);
    for (let i = 0; i < size; i++) {
      largeData[i] = i % 256;
    }

    const bridgeStream = new ReadableStream({
      start(controller) {
        controller.enqueue(largeData);
        controller.close();
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    const { done, value } = await reader.read();
    expect(done).toBe(false);
    expect(value).toBeDefined();
    expect(value!.length).toBe(size);
    expect(value![0]).toBe(0);
    expect(value![255]).toBe(255);
    expect(value![256]).toBe(0);
    expect(value![size - 1]).toBe((size - 1) % 256);

    event = await readEvent(reader);
    expect(event.text).toContain("Benchmark finished");

    await cleanup(reader);
  });

  it("handles three large bridge chunks (3 × 100KB) in order through the pipe loop", async () => {
    const size = 100 * 1024;

    const chunk1 = new Uint8Array(size);
    for (let i = 0; i < size; i++) chunk1[i] = i % 256;

    const chunk2 = new Uint8Array(size);
    for (let i = 0; i < size; i++) chunk2[i] = (i + 128) % 256;

    const chunk3 = new Uint8Array(size);
    for (let i = 0; i < size; i++) chunk3[i] = (i * 2) % 256;

    const bridgeStream = createBridgeStream([chunk1, chunk2, chunk3]);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    const r1 = await reader.read();
    expect(r1.done).toBe(false);
    expect(r1.value!.length).toBe(size);
    expect(r1.value![0]).toBe(0);
    expect(r1.value![255]).toBe(255);

    const r2 = await reader.read();
    expect(r2.done).toBe(false);
    expect(r2.value!.length).toBe(size);
    expect(r2.value![0]).toBe(128);
    expect(r2.value![255]).toBe(127);

    const r3 = await reader.read();
    expect(r3.done).toBe(false);
    expect(r3.value!.length).toBe(size);
    expect(r3.value![0]).toBe(0);
    expect(r3.value![255]).toBe(254);

    event = await readEvent(reader);
    expect(event.text).toContain("Benchmark finished");

    await cleanup(reader);
  });

  it("pipes a 100KB SSE event line (large JSON data payload) through intact", async () => {
    const payloadSize = 100 * 1024;
    const bigField = "x".repeat(payloadSize);
    const sseEvent = `event: MetricEvent\ndata: ${JSON.stringify({ bigField })}\n\n`;

    const encoder = new TextEncoder();
    const bridgeStream = createBridgeStream([encoder.encode(sseEvent)]);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    event = await readEvent(reader);
    expect(event.text).toContain("event: MetricEvent");
    expect(event.text).toContain('"bigField"');
    expect(event.text).toContain('"xxxxx');
    expect(event.text).toMatch(/\n\n$/);
    expect(event.text.length).toBeGreaterThan(payloadSize);
    expect(event.text.length).toBeLessThan(payloadSize + 200);

    event = await readEvent(reader);
    expect(event.text).toContain("Benchmark finished");

    await cleanup(reader);
  });

  // ── Async pull() delivery ─────────────────────────────────────

  it("delivers chunks across multiple async pull() calls in order through the pipe loop", async () => {
    const encoder = new TextEncoder();
    const chunk1 = encoder.encode("async-chunk-one:");
    const chunk2 = encoder.encode("async-chunk-two:");
    const chunk3 = encoder.encode("async-chunk-three");

    let pullIndex = 0;
    const bridgeStream = new ReadableStream({
      async pull(controller) {
        pullIndex++;
        await new Promise((resolve) => setTimeout(resolve, 5));
        if (pullIndex === 1) {
          controller.enqueue(chunk1);
        } else if (pullIndex === 2) {
          controller.enqueue(chunk2);
        } else if (pullIndex === 3) {
          controller.enqueue(chunk3);
          controller.close();
        }
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    const r1 = await reader.read();
    expect(r1.done).toBe(false);
    expect(Array.from(r1.value!)).toEqual(Array.from(chunk1));

    const r2 = await reader.read();
    expect(r2.done).toBe(false);
    expect(Array.from(r2.value!)).toEqual(Array.from(chunk2));

    const r3 = await reader.read();
    expect(r3.done).toBe(false);
    expect(Array.from(r3.value!)).toEqual(Array.from(chunk3));

    event = await readEvent(reader);
    expect(event.text).toContain("Benchmark finished");

    await cleanup(reader);
  });

  it("preserves ordering and boundaries across 150 tiny bridge chunks through the pipe loop", async () => {
    const chunkCount = 150;
    const chunkSize = 16;
    const chunks: Uint8Array[] = [];

    for (let i = 0; i < chunkCount; i++) {
      const chunk = new Uint8Array(chunkSize);
      chunk[0] = i % 256;
      for (let j = 1; j < chunkSize; j++) {
        chunk[j] = 0xBB;
      }
      chunks.push(chunk);
    }

    const bridgeStream = createBridgeStream(chunks);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    for (let i = 0; i < chunkCount; i++) {
      const { done, value } = await reader.read();
      expect(done).toBe(false);
      expect(value).toBeDefined();
      expect(value!.length).toBe(chunkSize);
      expect(value![0]).toBe(i % 256);
      expect(value![1]).toBe(0xBB);
    }

    event = await readEvent(reader);
    expect(event.text).toContain("Benchmark finished");

    await cleanup(reader);
  });

  it("preserves multiple small bridge chunks in order through the pipe loop", async () => {
    const encoder = new TextEncoder();
    const chunk1 = encoder.encode("first-chunk:");
    const chunk2 = encoder.encode("second-chunk:");
    const chunk3 = encoder.encode("third-chunk");

    const bridgeStream = createBridgeStream([chunk1, chunk2, chunk3]);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    const r1 = await reader.read();
    expect(r1.done).toBe(false);
    expect(Array.from(r1.value!)).toEqual(Array.from(chunk1));

    const r2 = await reader.read();
    expect(r2.done).toBe(false);
    expect(Array.from(r2.value!)).toEqual(Array.from(chunk2));

    const r3 = await reader.read();
    expect(r3.done).toBe(false);
    expect(Array.from(r3.value!)).toEqual(Array.from(chunk3));

    event = await readEvent(reader);
    expect(event.text).toContain("Benchmark finished");

    await cleanup(reader);
  });

  // ── Ordering edge cases ───────────────────────────────────────

  it("sends connected:true before bridge data even when bridge data is immediately available", async () => {
    const bridgeMarker = new Uint8Array([0xDE, 0xAD, 0xBE, 0xEF]);

    const bridgeStream = new ReadableStream({
      start(controller) {
        controller.enqueue(bridgeMarker);
        controller.close();
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, body: bridgeStream }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    // 1. Initial _status
    const r1 = await reader.read();
    expect(r1.done).toBe(false);
    const text1 = decoder.decode(r1.value!, { stream: true });
    expect(text1).toContain('"connected":false');
    expect(text1).not.toContain('"retrying"');
    expect(text1).toMatch(/^event: _status/);

    // 2. connected:true — arrives BEFORE bridge data
    const r2 = await reader.read();
    expect(r2.done).toBe(false);
    const text2 = decoder.decode(r2.value!, { stream: true });
    expect(text2).toContain('"connected":true');
    expect(text2).not.toContain(String.fromCharCode(0xDE, 0xAD, 0xBE, 0xEF));

    // 3. Piped bridge data
    const r3 = await reader.read();
    expect(r3.done).toBe(false);
    expect(Array.from(r3.value!)).toEqual(Array.from(bridgeMarker));

    // 4. Benchmark finished
    const r4 = await reader.read();
    const text4 = decoder.decode(r4.value!, { stream: true });
    expect(text4).toContain("Benchmark finished");

    await cleanup(reader);
  });

  // ── Mid-pull crash ────────────────────────────────────────────

  it("transitions from connected to retrying after bridge stream errors mid-pull between chunks", async () => {
    const encoder = new TextEncoder();
    const chunk1 = encoder.encode("data-chunk-one:");
    const chunk2 = encoder.encode("data-chunk-two:");

    let pullIndex = 0;
    const bridgeStream1 = new ReadableStream({
      async pull(controller) {
        pullIndex++;
        await new Promise((resolve) => setTimeout(resolve, 5));
        if (pullIndex === 1) {
          controller.enqueue(chunk1);
        } else if (pullIndex === 2) {
          controller.enqueue(chunk2);
        } else if (pullIndex === 3) {
          controller.error(new Error("Bridge crashed mid-stream"));
        }
      },
    });

    const bridgeStream2 = encoder.encode
      ? new ReadableStream({
          start(controller) {
            controller.enqueue(
              encoder.encode(
                'event: MetricEvent\ndata: {"name":"score","value":0.95}\n\n',
              ),
            );
            controller.close();
          },
        })
      : successStream();

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({ ok: true, body: bridgeStream1 })
        .mockResolvedValueOnce({ ok: true, body: bridgeStream2 }),
    );

    const response = await GET({} as any);
    const reader = response.body!.getReader();

    let event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":true');

    const r1 = await reader.read();
    expect(r1.done).toBe(false);
    expect(Array.from(r1.value!)).toEqual(Array.from(chunk1));

    const r2 = await reader.read();
    expect(r2.done).toBe(false);
    expect(Array.from(r2.value!)).toEqual(Array.from(chunk2));

    event = await readEvent(reader);
    expect(event.text).toContain('"connected":false');
    expect(event.text).toContain('"retrying":true');
    expect(event.text).toContain("Bridge crashed mid-stream");

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
});
