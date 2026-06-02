import { describe, it, expect } from "vitest";
import { GET } from "./health";

// Minimal mock APIContext — the handler doesn't use any context properties
const mockContext = {} as any;

describe("GET /api/health", () => {
  it("returns 200 OK", async () => {
    const response = await GET(mockContext);
    expect(response.status).toBe(200);
  });

  it("sets Content-Type to application/json", async () => {
    const response = await GET(mockContext);
    expect(response.headers.get("Content-Type")).toBe("application/json");
  });

  it("has all required fields in the response body", async () => {
    const response = await GET(mockContext);
    const body = await response.json();

    expect(body).toHaveProperty("status");
    expect(body).toHaveProperty("uptime");
    expect(body).toHaveProperty("uptime_seconds");
    expect(body).toHaveProperty("started_at");
    expect(body).toHaveProperty("timestamp");
    expect(body).toHaveProperty("version");
  });

  it('has status "ok"', async () => {
    const response = await GET(mockContext);
    const body = await response.json();
    expect(body.status).toBe("ok");
  });

  it("has uptime_seconds as a non-negative integer", async () => {
    const response = await GET(mockContext);
    const body = await response.json();
    expect(body.uptime_seconds).toBeGreaterThanOrEqual(0);
    expect(Number.isInteger(body.uptime_seconds)).toBe(true);
  });

  it("has uptime in 'Xm Xs' format (e.g. '0m 5s' or '60m 0s')", async () => {
    const response = await GET(mockContext);
    const body = await response.json();
    expect(body.uptime).toMatch(/^\d+m \d+s$/);
  });

  it("has started_at as a valid ISO 8601 date string", async () => {
    const response = await GET(mockContext);
    const body = await response.json();
    const date = new Date(body.started_at);
    expect(date.toISOString()).toBe(body.started_at);
  });

  it("has timestamp as a valid ISO 8601 date string", async () => {
    const response = await GET(mockContext);
    const body = await response.json();
    const date = new Date(body.timestamp);
    expect(date.toISOString()).toBe(body.timestamp);
  });

  it('has version "1.0.0"', async () => {
    const response = await GET(mockContext);
    const body = await response.json();
    expect(body.version).toBe("1.0.0");
  });

  it("uptime_seconds increases monotonically between calls", async () => {
    const res1 = await GET(mockContext);
    const body1 = await res1.json();

    // Small delay to ensure uptime ticks forward
    await new Promise((r) => setTimeout(r, 10));

    const res2 = await GET(mockContext);
    const body2 = await res2.json();

    expect(body2.uptime_seconds).toBeGreaterThanOrEqual(body1.uptime_seconds);
  });
});
