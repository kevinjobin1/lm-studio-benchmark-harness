// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import BenchmarkStatusBadge from "./BenchmarkStatusBadge";

const idleResponse = {
  active: false,
  processes: [],
};

const runningResponse = {
  active: true,
  processes: [
    {
      pid: 12345,
      model: "gemma-4-e4b",
      quick: true,
      startTime: "2026-06-02T02:25:52.205Z",
    },
  ],
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("BenchmarkStatusBadge", () => {
  it('shows "NODE: IDLE" when no processes are running', async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(idleResponse),
      });
    render(<BenchmarkStatusBadge />);
    await waitFor(() => {
      expect(screen.getByText("NODE: IDLE")).toBeTruthy();
    });
  });

  it("shows the running model name when a benchmark is active", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(runningResponse),
      });
    render(<BenchmarkStatusBadge />);
    await waitFor(() => {
      expect(screen.getByText(/BENCHMARK RUNNING/)).toBeTruthy();
    });
    expect(screen.getByText(/gemma-4-e4b/)).toBeTruthy();
  });

  it("calls fetch on mount with the correct URL", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(idleResponse),
      });
    render(<BenchmarkStatusBadge />);
    await waitFor(() => {
      expect(screen.getByText("NODE: IDLE")).toBeTruthy();
    });
    expect(global.fetch).toHaveBeenCalledWith("/api/run-benchmark/active");
  });

  it("shows a kill button when a benchmark is running", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(runningResponse),
      });
    render(<BenchmarkStatusBadge />);
    await waitFor(() => {
      expect(screen.getByLabelText("Stop benchmark")).toBeTruthy();
    });
  });

  it("calls the kill endpoint when the kill button is clicked", async () => {
    const user = userEvent.setup();

    global.fetch = vi
      .fn()
      .mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(runningResponse),
      });
    render(<BenchmarkStatusBadge />);

    await waitFor(() => {
      expect(screen.getByLabelText("Stop benchmark")).toBeTruthy();
    });

    await user.click(screen.getByLabelText("Stop benchmark"));

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/run-benchmark/kill?pid=12345",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("falls back to idle state when the API is unreachable", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network error"));
    render(<BenchmarkStatusBadge />);
    await waitFor(() => {
      expect(screen.getByText("NODE: IDLE")).toBeTruthy();
    });
  });

  it("cleans up the polling interval on unmount", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(idleResponse),
      });
    const clearIntervalSpy = vi.spyOn(global, "clearInterval");
    const { unmount } = render(<BenchmarkStatusBadge />);
    unmount();
    expect(clearIntervalSpy).toHaveBeenCalled();
  });

  it("shows a flyout with process details when clicked", async () => {
    const user = userEvent.setup();
    global.fetch = vi
      .fn()
      .mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(runningResponse),
      });
    render(<BenchmarkStatusBadge />);

    await waitFor(() => {
      expect(screen.getByText(/BENCHMARK RUNNING/)).toBeTruthy();
    });

    await user.click(screen.getByText("APPLE M3 PRO"));

    expect(screen.getByText("gemma-4-e4b")).toBeTruthy();
    expect(screen.getByText("12345")).toBeTruthy();
  });
});
