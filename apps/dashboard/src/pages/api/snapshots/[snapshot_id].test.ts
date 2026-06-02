// @vitest-environment node
import { describe, it, expect, vi } from "vitest";

// Mock loadSnapshot
vi.mock("../../../lib/loadSnapshots", () => ({
  loadSnapshot: vi.fn(),
}));

import { loadSnapshot } from "../../../lib/loadSnapshots";
import { GET } from "./[snapshot_id]";

describe("GET /api/snapshots/[snapshot_id]", () => {
  it("returns snapshot data when found", async () => {
    const mockSnapshot = {
      snapshot_id: "snap-found",
      model: "qwen",
      trace: { id: "trace-1", steps: [] },
      timestamp: "2026-01-01",
    };

    vi.mocked(loadSnapshot).mockResolvedValue(mockSnapshot as any);

    const response = await GET({ params: { snapshot_id: "snap-found" } } as any);
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.snapshot_id).toBe("snap-found");
  });

  it("returns 404 when snapshot not found", async () => {
    vi.mocked(loadSnapshot).mockResolvedValue(null);

    const response = await GET({ params: { snapshot_id: "nonexistent" } } as any);
    const data = await response.json();

    expect(response.status).toBe(404);
    expect(data.error).toContain("not found");
  });

  it("returns 400 when snapshot_id is missing", async () => {
    const response = await GET({ params: {} } as any);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.error).toContain("Missing");
  });
});
