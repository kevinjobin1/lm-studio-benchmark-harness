// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ServerUptimeBadge, { fmtUptime } from "./ServerUptimeBadge";

const mockHealthResponse = {
  status: "ok",
  uptime: "5m 30s",
  uptime_seconds: 330,
  started_at: "2026-06-02T02:25:52.205Z",
  timestamp: "2026-06-02T02:31:22.205Z",
  version: "1.0.0",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("fmtUptime", () => {
  it('formats seconds as "Xs"', () => {
    expect(fmtUptime(0)).toBe("0s");
    expect(fmtUptime(5)).toBe("5s");
    expect(fmtUptime(59)).toBe("59s");
  });

  it('formats minutes as "Xm Xs"', () => {
    expect(fmtUptime(60)).toBe("1m 0s");
    expect(fmtUptime(90)).toBe("1m 30s");
    expect(fmtUptime(3599)).toBe("59m 59s");
  });

  it('formats hours as "Xh Xm Xs"', () => {
    expect(fmtUptime(3600)).toBe("1h 0m 0s");
    expect(fmtUptime(3661)).toBe("1h 1m 1s");
    expect(fmtUptime(7384)).toBe("2h 3m 4s");
  });
});

describe("ServerUptimeBadge", () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(mockHealthResponse),
    });
  });

  it("renders nothing before the first fetch completes", () => {
    global.fetch = vi.fn().mockImplementation(
      () =>
        new Promise(() => {
          /* never resolves */
        }),
    );
    const { container } = render(<ServerUptimeBadge />);
    expect(container.innerHTML).toBe("");
  });

  it("shows formatted uptime after successful fetch", async () => {
    render(<ServerUptimeBadge />);
    await waitFor(() => {
      expect(screen.getByText("5m 30s")).toBeTruthy();
    });
  });

  it("shows the schedule icon", async () => {
    render(<ServerUptimeBadge />);
    await waitFor(() => {
      const icon = screen.getByText("schedule");
      expect(icon.className).toContain("uptime-icon");
    });
  });

  it("sets the tooltip to the server start time", async () => {
    render(<ServerUptimeBadge />);
    await waitFor(() => {
      const badge = screen.getByText("5m 30s").parentElement;
      expect(badge?.getAttribute("title")).toContain("Server started");
    });
  });

  it("returns null when fetch fails", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network error"));
    const { container } = render(<ServerUptimeBadge />);
    await waitFor(() => {
      expect(container.innerHTML).toBe("");
    });
  });

  it("calls fetch on mount with the correct URL", async () => {
    render(<ServerUptimeBadge />);
    await waitFor(() => {
      expect(screen.getByText("5m 30s")).toBeTruthy();
    });
    expect(global.fetch).toHaveBeenCalledWith("/api/health");
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("cleans up the interval on unmount", () => {
    const clearIntervalSpy = vi.spyOn(global, "clearInterval");
    const { unmount } = render(<ServerUptimeBadge />);
    unmount();
    expect(clearIntervalSpy).toHaveBeenCalled();
  });

  it("does not throw when unmounted before fetch resolves", async () => {
    let resolveFetch!: (value: any) => void;
    global.fetch = vi.fn().mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    const { unmount } = render(<ServerUptimeBadge />);
    unmount();

    await expect(async () => {
      resolveFetch({ json: () => Promise.resolve(mockHealthResponse) });
      await new Promise((r) => setTimeout(r, 0));
    }).not.toThrow();
  });
});
