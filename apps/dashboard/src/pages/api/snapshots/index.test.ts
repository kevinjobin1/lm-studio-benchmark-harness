// @vitest-environment node
import { describe, it, expect, vi, beforeAll } from "vitest";

// Mock loadSnapshotManifest and saveSnapshot
vi.mock("../../../lib/loadSnapshots", () => ({
  loadSnapshotManifest: vi.fn(),
  saveSnapshot: vi.fn(),
}));

import { loadSnapshotManifest, saveSnapshot } from "../../../lib/loadSnapshots";

// Import the route handler directly
const { GET, POST } = await import("./index");

describe("GET /api/snapshots", () => {
  it("returns snapshot list from manifest", async () => {
    const mockSnapshots = [
      { snapshot_id: "snap-a1b2", model: "test-model", timestamp: "2026-01-01" },
    ];
    vi.mocked(loadSnapshotManifest).mockResolvedValue({
      version: "1.0.0",
      generated_at: "2026-01-01",
      total_snapshots: 1,
      snapshots: mockSnapshots as any,
    });

    const response = await GET({} as any);
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data).toEqual(mockSnapshots);
  });

  it("returns empty array when no snapshots", async () => {
    vi.mocked(loadSnapshotManifest).mockResolvedValue({
      version: "1.0.0",
      generated_at: "2026-01-01",
      total_snapshots: 0,
      snapshots: [],
    });

    const response = await GET({} as any);
    const data = await response.json();

    expect(data).toEqual([]);
  });
});

describe("POST /api/snapshots", () => {
  it("creates a snapshot and returns 201 with id and url", async () => {
    const mockBody = {
      snapshot_id: "snap-test",
      model: "test-model",
      trace: { id: "trace-1" },
      prompt: "test",
      pack: "default",
      timestamp: "2026-01-01",
      metrics: { ttft_ms: 100, tokens_per_second: 50, total_tokens: 100 },
      response: "test response",
    };

    const mockRequest = new Request("http://localhost/api/snapshots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(mockBody),
    });

    vi.mocked(saveSnapshot).mockResolvedValue({
      snapshot_id: "snap-test",
      url: "/runs/snap-test",
    });

    const response = await POST({ request: mockRequest } as any);
    const data = await response.json();

    expect(response.status).toBe(201);
    expect(data.snapshot_id).toBe("snap-test");
    expect(data.url).toBe("/runs/snap-test");
  });

  it("returns 400 when required fields are missing", async () => {
    const mockRequest = new Request("http://localhost/api/snapshots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    const response = await POST({ request: mockRequest } as any);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.error).toContain("Missing required fields");
  });

  it("returns 500 when save fails", async () => {
    const mockBody = {
      snapshot_id: "snap-error",
      model: "test",
      trace: { id: "t1" },
      prompt: "test",
      pack: "default",
      timestamp: "2026-01-01",
      metrics: { ttft_ms: 100, tokens_per_second: 50, total_tokens: 100 },
      response: "test",
    };

    const mockRequest = new Request("http://localhost/api/snapshots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(mockBody),
    });

    vi.mocked(saveSnapshot).mockRejectedValue(new Error("Disk full"));

    const response = await POST({ request: mockRequest } as any);
    const data = await response.json();

    expect(response.status).toBe(500);
    expect(data.error).toContain("Disk full");
  });
});
