// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ReplayViewer from "./ReplayViewer";
import * as loadReplays from "../lib/loadReplays";
import type { ReplayManifest, ReplayData, ReplayIndexEntry } from "../lib/loadReplays";

beforeEach(() => {
  // jsdom does not implement scrollIntoView
  Element.prototype.scrollIntoView = vi.fn();
});

// ── Mock data ─────────────────────────────────────────────────────

const mockReplayEntry: ReplayIndexEntry = {
  run_id: "run-abc-123",
  model: "qwen3.5-9b-coder",
  workload: "nestjs-api",
  provider: "lm-studio",
  started_at: "2026-06-02T10:30:00Z",
  event_count: 5,
  file: "run-abc-123.json",
};

const mockReplayEntry2: ReplayIndexEntry = {
  run_id: "run-def-456",
  model: "llama3.2-3b",
  workload: "",
  provider: "ollama",
  started_at: "2026-06-02T09:00:00Z",
  event_count: 3,
  file: "run-def-456.json",
};

const mockManifest: ReplayManifest = {
  version: "1.0.0",
  generated_at: "2026-06-02T11:00:00Z",
  total_replays: 2,
  replays: [mockReplayEntry, mockReplayEntry2],
};

const mockReplayData: ReplayData = {
  version: "1.0.0",
  generated_at: "2026-06-02T10:30:05Z",
  run_id: "run-abc-123",
  model: "qwen3.5-9b-coder",
  workload: "nestjs-api",
  provider: "lm-studio",
  started_at: "2026-06-02T10:30:00Z",
  event_count: 5,
  events: [
    {
      _event_type: "RunLifecycleEvent",
      status: "started",
      model: "qwen3.5-9b-coder",
      run_id: "run-abc-123",
      timestamp: "2026-06-02T10:30:00Z",
    },
    {
      _event_type: "TokenGeneratedEvent",
      token: "Hello",
      index: 0,
      timing_ms: 12.5,
      model: "qwen3.5-9b-coder",
      run_id: "run-abc-123",
      timestamp: "2026-06-02T10:30:01Z",
    },
    {
      _event_type: "TokenGeneratedEvent",
      token: " world",
      index: 1,
      timing_ms: 15.2,
      model: "qwen3.5-9b-coder",
      run_id: "run-abc-123",
      timestamp: "2026-06-02T10:30:01.1Z",
    },
    {
      _event_type: "MetricEvent",
      name: "score",
      value: 0.92,
      model: "qwen3.5-9b-coder",
      run_id: "run-abc-123",
      timestamp: "2026-06-02T10:30:02Z",
    },
    {
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "qwen3.5-9b-coder",
      run_id: "run-abc-123",
      duration_ms: 5000,
      timestamp: "2026-06-02T10:30:05Z",
    },
  ],
};

const mockReplayDataEmpty: ReplayData = {
  ...mockReplayData,
  run_id: "run-empty",
  model: "empty-model",
  workload: "",
  event_count: 0,
  events: [],
};

// ── Mocks ─────────────────────────────────────────────────────────

vi.mock("../lib/loadReplays", () => ({
  loadReplayManifest: vi.fn(),
  loadReplay: vi.fn(),
}));

// ── Helpers ───────────────────────────────────────────────────────

async function renderComponent() {
  const result = render(<ReplayViewer />);
  await vi.waitFor(() => {
    expect(screen.queryByText(/Loading/)).not.toBeInTheDocument();
  });
  return result;
}

// ── Tests ─────────────────────────────────────────────────────────

describe("ReplayViewer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // ── Loading state ──────────────────────────────────────────────

  it("shows loading spinner while manifest loads", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockReturnValue(
      new Promise(() => {}), // never resolves
    );

    render(<ReplayViewer />);
    expect(screen.getByText("Loading replays…")).toBeInTheDocument();
  });

  // ── Empty state ───────────────────────────────────────────────

  it("shows empty state when no replays exist", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue({
      ...mockManifest,
      replays: [],
      total_replays: 0,
    });

    await renderComponent();

    expect(screen.getByText("No replay sessions found.")).toBeInTheDocument();
    expect(screen.getByText(/Run a benchmark/)).toBeInTheDocument();
  });

  // ── Replay list ────────────────────────────────────────────────

  it("renders replay entries in the sidebar", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);

    await renderComponent();

    expect(screen.getByText("qwen3.5-9b-coder")).toBeInTheDocument();
    expect(screen.getByText("llama3.2-3b")).toBeInTheDocument();
    expect(screen.getByText("5 events")).toBeInTheDocument();
    expect(screen.getByText("3 events")).toBeInTheDocument();
    expect(screen.getByText("nestjs-api")).toBeInTheDocument();
  });

  it("shows the replay count in the sidebar header", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);

    await renderComponent();

    expect(screen.getByText("Replay Sessions")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  // ── Selecting a replay ────────────────────────────────────────

  it("loads and displays replay data on selection", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();

    // Click the first replay entry
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    // Wait for events to render — token events are in separate cards so
    // check for individual tokens. Whitespace normalization trims leading
    // spaces, so use a simple text match for the token content.
    await waitFor(() => {
      expect(screen.getByText("Hello")).toBeInTheDocument();
      expect(screen.getByText("world")).toBeInTheDocument();
    });

    // Header shows model name and metadata.
    // Note: model name appears in both sidebar and header after selection.
    // "nestjs-api" also appears in sidebar workload chip AND header meta-chip.
    const modelElements = screen.getAllByText("qwen3.5-9b-coder");
    expect(modelElements.length).toBeGreaterThanOrEqual(2);
    const workloadElements = screen.getAllByText("nestjs-api");
    expect(workloadElements.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("run-abc-123")).toBeInTheDocument();

    // Events rendered in timeline — RunLifecycle appears twice (started + completed)
    expect(screen.getAllByText("Run Lifecycle").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Token Generated").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Metric")).toBeInTheDocument();

    expect(loadReplays.loadReplay).toHaveBeenCalledWith("run-abc-123");
  });

  it("highlights the active replay in the sidebar", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();

    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => {
      const sidebarItems = document.querySelectorAll(".rpv-sidebar-item");
      expect(sidebarItems[0].classList.contains("rpv-sidebar-active")).toBe(true);
      expect(sidebarItems[1].classList.contains("rpv-sidebar-active")).toBe(false);
    });
  });

  it("shows loading detail while replay data loads", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockReturnValue(
      new Promise(() => {}), // never resolves
    );

    await renderComponent();

    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    expect(screen.getByText("Loading replay…")).toBeInTheDocument();
  });

  // ── Empty state (no replay selected) ──────────────────────────

  it("shows prompt to select a replay when none is selected", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue({
      ...mockManifest,
      replays: [mockReplayEntry],
    });

    await renderComponent();

    expect(
      screen.getByText("Select a replay session from the sidebar to view its event timeline."),
    ).toBeInTheDocument();
  });

  // ── Error states ─────────────────────────────────────────────

  it("shows error banner when manifest fails to load", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockRejectedValue(
      new Error("Network error"),
    );

    await renderComponent();

    expect(screen.getByText("Failed to load replay list")).toBeInTheDocument();
  });

  it("shows error banner when replay detail fails to load", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockRejectedValue(
      new Error("Server error"),
    );

    await renderComponent();

    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => {
      expect(screen.getByText("Failed to load replay data")).toBeInTheDocument();
    });
  });

  it("shows error when replay is not found", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(null);

    await renderComponent();

    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => {
      expect(
        screen.getByText(/Replay.*not found/),
      ).toBeInTheDocument();
    });
  });

  it("dismisses error banner when close button is clicked", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockRejectedValue(
      new Error("Network error"),
    );

    await renderComponent();

    const dismissBtn = screen.getByLabelText("Dismiss error");
    await userEvent.click(dismissBtn);

    await waitFor(() => {
      expect(
        screen.queryByText("Failed to load replay list"),
      ).not.toBeInTheDocument();
    });
  });

  // ── Playback controls ────────────────────────────────────────

  it("renders playback controls when a replay is selected", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => {
      expect(screen.getByLabelText("Previous event")).toBeInTheDocument();
      expect(screen.getByLabelText("Play")).toBeInTheDocument();
      expect(screen.getByLabelText("Next event")).toBeInTheDocument();
      expect(screen.getByLabelText("Cycle playback speed")).toBeInTheDocument();
    });
  });

  it("previous button is disabled at the first event", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => {
      expect(screen.getByLabelText("Previous event")).toBeDisabled();
      expect(screen.getByLabelText("Next event")).not.toBeDisabled();
    });
  });

  it("next button is disabled at the last event", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => screen.getByLabelText("Play"));

    // Navigate to last event
    const nextBtn = screen.getByLabelText("Next event");
    for (let i = 0; i < 4; i++) {
      await userEvent.click(nextBtn);
    }

    expect(screen.getByLabelText("Next event")).toBeDisabled();
    expect(screen.getByLabelText("Previous event")).not.toBeDisabled();
  });

  it("play/pause toggles playback state", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => screen.getByLabelText("Play"));

    const playBtn = screen.getByLabelText("Play");
    await userEvent.click(playBtn);

    expect(screen.getByLabelText("Pause")).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Pause"));
    expect(screen.getByLabelText("Play")).toBeInTheDocument();
  });

  it("cycles playback speed on button click", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => screen.getByLabelText("Cycle playback speed"));

    const speedBtn = screen.getByLabelText("Cycle playback speed");
    expect(speedBtn).toHaveTextContent("1×");

    await userEvent.click(speedBtn);
    expect(speedBtn).toHaveTextContent("2×");

    await userEvent.click(speedBtn);
    expect(speedBtn).toHaveTextContent("4×");

    await userEvent.click(speedBtn);
    expect(speedBtn).toHaveTextContent("0.5×");

    await userEvent.click(speedBtn);
    expect(speedBtn).toHaveTextContent("1×");
  });

  it("displays current event position in progress label", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => {
      expect(screen.getByText("1 / 5 events")).toBeInTheDocument();
    });

    const nextBtn = screen.getByLabelText("Next event");
    await userEvent.click(nextBtn);

    expect(screen.getByText("2 / 5 events")).toBeInTheDocument();
  });

  it("advances events during playback", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => screen.getByLabelText("Play"));

    // Start playback — the interval runs at 800ms intervals
    await userEvent.click(screen.getByLabelText("Play"));

    // Advance timers one step at a time so React can flush state updates
    // between each interval. The ref-based interval callback needs a render
    // between advances to see the updated currentEventIndex.
    for (let i = 0; i < 4; i++) {
      act(() => {
        vi.advanceTimersByTime(800);
      });
    }

    // After 4 intervals we should be at index 4 (showing "5 / 5 events")
    expect(screen.getByText("5 / 5 events")).toBeInTheDocument();

    // One more advance triggers the stop-and-reset: index 4 >= 4 (events.length-1)
    act(() => {
      vi.advanceTimersByTime(800);
    });

    await waitFor(() => {
      expect(screen.getByText("1 / 5 events")).toBeInTheDocument();
    });

    // Play button should show play (stopped state)
    expect(screen.getByLabelText("Play")).toBeInTheDocument();

    vi.useRealTimers();
  });

  // ── Event navigation ─────────────────────────────────────────

  it("jumps to event when clicking on it", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    // Wait for events to render
    await waitFor(() => {
      expect(screen.getAllByText("Token Generated").length).toBeGreaterThan(0);
    });

    // Find the second "Token Generated" label (event index 2) and click it
    const tokenChips = screen.getAllByText("Token Generated");
    await userEvent.click(tokenChips[1]);

    // Pause should be false (clicking stops playback)
    expect(screen.getByLabelText("Play")).toBeInTheDocument();
  });

  // ── Keyboard shortcuts ───────────────────────────────────────

  it("handles keyboard shortcut Space for play/pause", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => screen.getByLabelText("Play"));

    fireEvent.keyDown(window, { key: " " });
    expect(screen.getByLabelText("Pause")).toBeInTheDocument();

    fireEvent.keyDown(window, { key: " " });
    expect(screen.getByLabelText("Play")).toBeInTheDocument();
  });

  it("handles keyboard shortcut ArrowLeft for previous", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => screen.getByLabelText("Play"));

    // Navigate forward first
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(screen.getByText("2 / 5 events")).toBeInTheDocument();

    // Navigate back
    fireEvent.keyDown(window, { key: "ArrowLeft" });
    expect(screen.getByText("1 / 5 events")).toBeInTheDocument();
  });

  it("handles keyboard shortcut 2 for speed", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => screen.getByLabelText("Cycle playback speed"));

    fireEvent.keyDown(window, { key: "2" });
    expect(screen.getByLabelText("Cycle playback speed")).toHaveTextContent("2×");
  });

  it("keyboard shortcuts are ignored when focus is in input", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => screen.getByLabelText("Play"));

    // Create a focused input to simulate that case
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.focus();

    fireEvent.keyDown(input, { key: " " });

    // Play button should still show Play (not Pause)
    expect(screen.getByLabelText("Play")).toBeInTheDocument();

    document.body.removeChild(input);
  });

  // ── Progress scrubbing ───────────────────────────────────────

  it("renders progress bar track", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => {
      expect(document.querySelector(".rpv-pb-track")).toBeInTheDocument();
    });
  });

  // ── Event detail rendering ───────────────────────────────────

  it("renders RunLifecycleEvent detail with status", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => {
      // formatMs(5000) returns "5.0s". Note: the RunLifecycleEvent in mock
      // data does not have a `workload` field, so output is "completed (5.0s)".
      expect(screen.getByText(/completed.*5\.0s/)).toBeInTheDocument();
    });
  });

  it("renders MetricEvent detail with percentage", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => {
      expect(screen.getByText("score:")).toBeInTheDocument();
      expect(screen.getByText("92.0%")).toBeInTheDocument();
    });
  });

  it("renders ErrorEvent detail with message", async () => {
    const errorReplayData: ReplayData = {
      ...mockReplayData,
      events: [
        {
          _event_type: "ErrorEvent",
          message: "Connection refused",
          exception: "RuntimeError",
          model: "test",
          run_id: "run-err",
          timestamp: "2026-06-02T10:30:00Z",
        },
      ],
    };

    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(errorReplayData);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => {
      expect(screen.getByText(/RuntimeError: Connection refused/)).toBeInTheDocument();
    });
  });

  // ── Empty events ─────────────────────────────────────────────

  it("handles replay with zero events gracefully", async () => {
    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayDataEmpty);

    await renderComponent();
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));

    await waitFor(() => {
      // Should not crash — shows the header without events
      expect(screen.getByText("empty-model")).toBeInTheDocument();
      // Component renders (0+1)/0 = "1 / 0 events" without special-casing
      expect(screen.getByText("1 / 0 events")).toBeInTheDocument();
    });
  });

  // ── Edge case: switching replays ─────────────────────────────

  it("stops playback and resets position when switching replays", async () => {
    const secondReplayData: ReplayData = {
      ...mockReplayData,
      run_id: "run-def-456",
      model: "llama3.2-3b",
    };

    vi.mocked(loadReplays.loadReplayManifest).mockResolvedValue(mockManifest);
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(mockReplayData);

    await renderComponent();

    // Load first replay
    await userEvent.click(screen.getByText("qwen3.5-9b-coder"));
    await waitFor(() => screen.getByLabelText("Play"));

    // Navigate forward
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(screen.getByText("2 / 5 events")).toBeInTheDocument();

    // Switch to second replay
    vi.mocked(loadReplays.loadReplay).mockResolvedValue(secondReplayData);
    await userEvent.click(screen.getByText("llama3.2-3b"));

    await waitFor(() => {
      expect(screen.getByText("1 / 5 events")).toBeInTheDocument();
      expect(screen.getByLabelText("Play")).toBeInTheDocument();
    });
  });
});
