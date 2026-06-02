// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RunBenchmarkButton from "./RunBenchmarkButton";

const connectedStatus = {
  connected: true,
  models: ["gemma-4-e4b", "qwopus3.5-9b-coder", "lfm2.5-8b-a1b"],
};

const disconnectedStatus = {
  connected: false,
  models: [],
  error: "LM Studio not reachable",
};

beforeEach(() => {
  // jsdom doesn't implement scrollIntoView — the component uses it for log auto-scroll
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RunBenchmarkButton", () => {
  it("renders the trigger button", () => {
    render(<RunBenchmarkButton />);
    expect(screen.getByText("Run new benchmark")).toBeTruthy();
  });

  it("opens the modal when trigger button is clicked", async () => {
    const user = userEvent.setup();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(connectedStatus),
    });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText("Run New Benchmark")).toBeTruthy();
    });
  });

  it("shows 'Checking...' status when modal first opens", async () => {
    const user = userEvent.setup();
    global.fetch = vi.fn().mockImplementation(
      () => new Promise(() => {}),
    );

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText(/Checking.../)).toBeTruthy();
    });
  });

  it("shows 'Connected' status when API returns connected=true", async () => {
    const user = userEvent.setup();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(connectedStatus),
    });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeTruthy();
    });
  });

  it("shows 'Not connected' when API returns connected=false", async () => {
    const user = userEvent.setup();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(disconnectedStatus),
    });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText(/Not connected/)).toBeTruthy();
    });
  });

  it("shows error message when LM Studio is not reachable", async () => {
    const user = userEvent.setup();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(disconnectedStatus),
    });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText(/LM Studio not reachable/)).toBeTruthy();
    });
  });

  it("shows loaded models list when connected", async () => {
    const user = userEvent.setup();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(connectedStatus),
    });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText("gemma-4-e4b")).toBeTruthy();
      expect(screen.getByText("qwopus3.5-9b-coder")).toBeTruthy();
      expect(screen.getByText("lfm2.5-8b-a1b")).toBeTruthy();
    });
  });

  it("shows the quick mode checkbox", async () => {
    const user = userEvent.setup();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(connectedStatus),
    });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText("Quick mode (fewer samples, faster)")).toBeTruthy();
    });
  });

  it("enables the Run Benchmark button when connected", async () => {
    const user = userEvent.setup();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(connectedStatus),
    });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      const runBtn = screen.getByText("Run Benchmark").closest("button") as HTMLButtonElement;
      expect(runBtn.disabled).toBe(false);
    });
  });

  it("disables the Run button while checking", async () => {
    const user = userEvent.setup();
    global.fetch = vi.fn().mockImplementation(
      () => new Promise(() => {}),
    );

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      const btn = screen.getByText("Run Benchmark").closest("button") as HTMLButtonElement;
      expect(btn.disabled).toBe(true);
    });
  });

  it("closes the modal when close button is clicked", async () => {
    const user = userEvent.setup();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(connectedStatus),
    });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText("Run New Benchmark")).toBeTruthy();
    });

    // The close button has aria-label "Close" on the icon button in the modal header
    const closeBtn = screen.getByText("close").closest("button");
    expect(closeBtn).toBeTruthy();
    await user.click(closeBtn!);
    await waitFor(() => {
      expect(screen.queryByText("Run New Benchmark")).toBeNull();
    });
  });

  it("sends POST request to /api/run-benchmark when Run Benchmark is clicked", async () => {
    const user = userEvent.setup();

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(connectedStatus),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          pid: 54321,
          message: "Benchmark started",
        }),
      });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeTruthy();
    });

    await user.click(screen.getByText("Run Benchmark"));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/run-benchmark",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ quick: true }),
        }),
      );
    });
  });

  it("shows PID after benchmark starts", async () => {
    const user = userEvent.setup();

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(connectedStatus),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          pid: 54321,
          message: "Benchmark started",
        }),
      });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeTruthy();
    });

    await user.click(screen.getByText("Run Benchmark"));

    await waitFor(() => {
      expect(screen.getByText(/PID 54321/)).toBeTruthy();
    });
  });

  it("shows 'Starting benchmark...' message when run starts", async () => {
    const user = userEvent.setup();

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(connectedStatus),
      })
      .mockImplementationOnce(
        () => new Promise(() => {}),
      );

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeTruthy();
    });

    await user.click(screen.getByText("Run Benchmark"));

    await waitFor(() => {
      expect(screen.getByText("Starting benchmark...")).toBeTruthy();
    });
  });

  it("shows success message after benchmark completes", async () => {
    const user = userEvent.setup();

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(connectedStatus),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          pid: 54321,
          message: "Benchmark started",
        }),
      });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeTruthy();
    });

    await user.click(screen.getByText("Run Benchmark"));

    await waitFor(() => {
      expect(screen.getByText("Benchmark started")).toBeTruthy();
    });
  });

  it("shows error message when benchmark fails to start", async () => {
    const user = userEvent.setup();

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(connectedStatus),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: false,
          message: "No model loaded",
        }),
      });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeTruthy();
    });

    await user.click(screen.getByText("Run Benchmark"));

    await waitFor(() => {
      expect(screen.getByText("No model loaded")).toBeTruthy();
    });
  });

  it("shows network error when run fetch fails", async () => {
    const user = userEvent.setup();

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(connectedStatus),
      })
      .mockRejectedValueOnce(new Error("Network error"));

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeTruthy();
    });

    await user.click(screen.getByText("Run Benchmark"));

    await waitFor(() => {
      expect(screen.getByText("Failed to start benchmark. Is the server running?")).toBeTruthy();
    });
  });

  it("shows the Close button after benchmark completes", async () => {
    const user = userEvent.setup();

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(connectedStatus),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          pid: 54321,
          message: "Benchmark started",
        }),
      });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeTruthy();
    });

    await user.click(screen.getByText("Run Benchmark"));

    await waitFor(() => {
      // "Close" button appears in the modal footer after done state
      // "Cancel" also appears — use the button that's specifically "Close"
      const footer = document.querySelector(".modal-footer");
      expect(footer?.textContent).toContain("Close");
    });
  });

  it("shows Live Output toggle after benchmark starts", async () => {
    const user = userEvent.setup();

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(connectedStatus),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          pid: 54321,
          message: "Benchmark started",
        }),
      });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeTruthy();
    });

    await user.click(screen.getByText("Run Benchmark"));

    await waitFor(() => {
      expect(screen.getByText("Live Output")).toBeTruthy();
    });
  });

  it("shows 'Waiting for output...' after benchmark starts with no output yet", async () => {
    const user = userEvent.setup();

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(connectedStatus),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          pid: 54321,
          message: "Benchmark started",
        }),
      });

    render(<RunBenchmarkButton />);
    await user.click(screen.getByText("Run new benchmark"));

    await waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeTruthy();
    });

    await user.click(screen.getByText("Run Benchmark"));

    // After benchmark starts, showLogs is set to true automatically AND
    // the Live Output button text is visible. The terminal shows
    // "Waiting for output..." because stdout is empty.
    await waitFor(() => {
      expect(screen.getByText("Live Output")).toBeTruthy();
      expect(screen.getByText("Waiting for output...")).toBeTruthy();
    });
  });
});
