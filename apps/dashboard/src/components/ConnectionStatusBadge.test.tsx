// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ConnectionStatusBadge from "./ConnectionStatusBadge";

const connectedResponse = {
  connected: true,
  models: ["google/gemma-4-e4b"],
  provider: "LM Studio",
  hardware: {
    cpu: { model: "Apple M3 Pro", cores_physical: 14, cores_logical: 14 },
    memory: { ram_total_mb: 18432, ram_available_mb: 8249.2 },
    gpu: { model: "Apple M3 Pro", available: true },
    os: { name: "Darwin", version: "15.6.1", architecture: "arm64" },
    apple_silicon: true,
    unified_memory: true,
  },
};

const connectedNoHardware = {
  connected: true,
  models: ["gemma-4-e4b"],
  provider: "LM Studio",
};

const multiModelResponse = {
  connected: true,
  models: ["gemma-4-e4b", "qwen3.5", "llama-3.2"],
  provider: "LM Studio",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ConnectionStatusBadge", () => {
  it('shows "Disconnected" when the API returns connected=false', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ connected: false, models: [], provider: "" }),
    });
    render(<ConnectionStatusBadge />);
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeTruthy();
    });
  });

  it('shows "Disconnected" on network error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network error"));
    render(<ConnectionStatusBadge />);
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeTruthy();
    });
  });

  it("shows the model name and provider when connected with a single model", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(connectedResponse),
    });
    render(<ConnectionStatusBadge />);
    await waitFor(() => {
      expect(screen.getByText(/gemma-4-e4b/)).toBeTruthy();
    });
    expect(screen.getByText(/LM Studio/)).toBeTruthy();
  });

  it("shows model count when multiple models are loaded", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(multiModelResponse),
    });
    render(<ConnectionStatusBadge />);
    await waitFor(() => {
      expect(screen.getByText(/3 models/)).toBeTruthy();
    });
    expect(screen.getByText(/LM Studio/)).toBeTruthy();
  });

  it("shows the connected dot with the connected class", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(connectedResponse),
    });
    render(<ConnectionStatusBadge />);
    await waitFor(() => {
      const dot = document.querySelector(".connection-dot.connected");
      expect(dot).toBeTruthy();
    });
  });

  it("shows the disconnected dot when not connected", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ connected: false, models: [], provider: "" }),
    });
    render(<ConnectionStatusBadge />);
    await waitFor(() => {
      const dot = document.querySelector(".connection-dot.disconnected");
      expect(dot).toBeTruthy();
    });
  });

  it("calls fetch on mount with /api/status", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(connectedResponse),
    });
    render(<ConnectionStatusBadge />);
    await waitFor(() => {
      expect(screen.getByText(/gemma-4-e4b/)).toBeTruthy();
    });
    expect(global.fetch).toHaveBeenCalledWith("/api/status");
  });

  it("includes hardware info in the display when available", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(connectedResponse),
    });
    render(<ConnectionStatusBadge />);
    await waitFor(() => {
      // Hardware string: "M3 PRO • 18GB • Darwin (15.6.1)"
      expect(screen.getByText(/M3 Pro/)).toBeTruthy();
    });
    expect(screen.getByText(/18GB/)).toBeTruthy();
  });

  it("does not show hardware info when hardware is not provided", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(connectedNoHardware),
    });
    render(<ConnectionStatusBadge />);

    // Wait for connected state
    await waitFor(() => {
      expect(screen.getByText(/gemma-4-e4b/)).toBeTruthy();
    });

    // Should not show any hardware-related text
    expect(screen.queryByText(/GB/)).toBeNull();
    expect(screen.queryByText(/M3/)).toBeNull();
  });

  it("sets the title attribute with combined info", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(connectedResponse),
    });
    render(<ConnectionStatusBadge />);
    await waitFor(() => {
      const badge = document.querySelector(".connection-badge");
      expect(badge?.getAttribute("title")).toContain("gemma-4-e4b");
      expect(badge?.getAttribute("title")).toContain("M3 Pro");
    });
  });

  it("cleans up the polling interval on unmount", () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(connectedResponse),
    });
    const clearIntervalSpy = vi.spyOn(global, "clearInterval");
    const { unmount } = render(<ConnectionStatusBadge />);
    unmount();
    expect(clearIntervalSpy).toHaveBeenCalled();
  });
});
