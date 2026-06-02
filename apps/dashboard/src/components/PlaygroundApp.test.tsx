// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import PlaygroundApp from "./PlaygroundApp";

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

// Helper to find the run button reliably
function getRunBtn() {
  return screen.getByRole("button", { name: /run agentic evaluation/i });
}

// ─── Real-timer tests ─────────────────────────────────────────────

describe("PlaygroundApp — initial render & interactions", () => {
  it("renders the playground-app container", () => {
    const { container } = render(<PlaygroundApp />);
    expect(container.querySelector(".playground-app")).toBeTruthy();
  });

  it("shows all 8 skill chips", () => {
    render(<PlaygroundApp />);
    expect(screen.getByText("read_file")).toBeTruthy();
    expect(screen.getByText("write_file")).toBeTruthy();
    expect(screen.getByText("json_parse")).toBeTruthy();
    expect(screen.getByText("diff")).toBeTruthy();
    expect(screen.getByText("nestjs_prisma_service")).toBeTruthy();
    expect(screen.getByText("nestjs_jwt_guard")).toBeTruthy();
    expect(screen.getByText("nestjs_cache_interceptor")).toBeTruthy();
    expect(screen.getByText("nestjs_validation_pipe")).toBeTruthy();
  });

  it("shows 4 selected skill chips by default", () => {
    const { container } = render(<PlaygroundApp />);
    const selectedChips = container.querySelectorAll(".skill-chip.selected");
    expect(selectedChips.length).toBe(4);
  });

  it("toggles a skill off on click (removes selected class)", () => {
    const { container } = render(<PlaygroundApp />);
    const firstChip = container.querySelectorAll(".skill-chip")[0];
    fireEvent.click(firstChip);
    expect(firstChip?.classList.contains("selected")).toBe(false);
    const selectedChips = container.querySelectorAll(".skill-chip.selected");
    expect(selectedChips.length).toBe(3);
  });

  it("toggles a skill back on after second click", () => {
    const { container } = render(<PlaygroundApp />);
    const chips = container.querySelectorAll(".skill-chip");

    fireEvent.click(chips[0]);
    expect(chips[0].classList.contains("selected")).toBe(false);

    fireEvent.click(chips[0]);
    expect(chips[0].classList.contains("selected")).toBe(true);
    expect(container.querySelectorAll(".skill-chip.selected").length).toBe(4);
  });

  it("shows skill count as '4 skills selected'", () => {
    render(<PlaygroundApp />);
    expect(screen.getByText("4 skills selected")).toBeTruthy();
  });

  it("updates skill count after toggling one off", () => {
    render(<PlaygroundApp />);
    const firstChip = document.querySelector(".skill-chip")!;
    fireEvent.click(firstChip);
    expect(screen.getByText("3 skills selected")).toBeTruthy();
  });

  it("shows 5 template cards in template mode", () => {
    render(<PlaygroundApp />);
    expect(screen.getByText("Read & Fix Bug")).toBeTruthy();
    expect(screen.getByText("JSON Transform")).toBeTruthy();
    expect(screen.getByText("Code Review Diff")).toBeTruthy();
    expect(screen.getByText("Auth Guard Debug")).toBeTruthy();
    expect(screen.getByText("Cache Race Fix")).toBeTruthy();
  });

  it("applies a template on click (sets prompt text)", () => {
    render(<PlaygroundApp />);
    const textarea = screen.getByPlaceholderText(
      /Describe the task/,
    ) as HTMLTextAreaElement;
    expect(textarea.value).toBe("");

    fireEvent.click(screen.getByText("Read & Fix Bug"));
    expect(textarea.value).toContain("Read the file src/buggy.ts");
  });

  it("highlights the selected template with active class", () => {
    render(<PlaygroundApp />);
    const firstTemplate = screen.getByText("Read & Fix Bug").closest("button");
    expect(firstTemplate?.classList.contains("active")).toBe(true);

    fireEvent.click(screen.getByText("JSON Transform"));
    expect(firstTemplate?.classList.contains("active")).toBe(false);
    const secondTemplate = screen.getByText("JSON Transform").closest("button");
    expect(secondTemplate?.classList.contains("active")).toBe(true);
  });

  it("switches to custom tab when clicking 'Custom Task'", () => {
    render(<PlaygroundApp />);
    expect(screen.getByText("Templates").classList.contains("active")).toBe(true);
    expect(screen.getByText("Custom Task").classList.contains("active")).toBe(false);

    fireEvent.click(screen.getByText("Custom Task"));
    expect(screen.getByText("Custom Task").classList.contains("active")).toBe(true);
    expect(screen.getByText("Templates").classList.contains("active")).toBe(false);
  });

  it("hides template cards in custom mode", () => {
    render(<PlaygroundApp />);
    expect(screen.getByText("Read & Fix Bug")).toBeTruthy();

    fireEvent.click(screen.getByText("Custom Task"));
    expect(screen.queryByText("Read & Fix Bug")).toBeNull();
  });

  it("typing in textarea updates the prompt", () => {
    render(<PlaygroundApp />);
    const textarea = screen.getByPlaceholderText(
      /Describe the task/,
    ) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "Custom prompt here" } });
    expect(textarea.value).toBe("Custom prompt here");
  });

  it("typing in textarea switches mode to custom", () => {
    render(<PlaygroundApp />);
    fireEvent.click(screen.getByText("Read & Fix Bug"));
    expect(screen.getByText("Templates").classList.contains("active")).toBe(true);

    const textarea = screen.getByPlaceholderText(
      /Describe the task/,
    ) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "Custom" } });
    expect(screen.getByText("Custom Task").classList.contains("active")).toBe(true);
  });

  it("run button is disabled when prompt is empty", () => {
    render(<PlaygroundApp />);
    expect((getRunBtn() as HTMLButtonElement).disabled).toBe(true);
  });

  it("run button is enabled when prompt has text", () => {
    render(<PlaygroundApp />);
    const textarea = screen.getByPlaceholderText(
      /Describe the task/,
    ) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "Test prompt" } });
    expect((getRunBtn() as HTMLButtonElement).disabled).toBe(false);
  });
});

// ─── Fake-timer tests (async evaluation) ─────────────────────────

describe("PlaygroundApp — async evaluation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("shows spinner after clicking run, then results after timeout", async () => {
    render(<PlaygroundApp />);

    // Apply a template to set the prompt
    fireEvent.click(screen.getByText("Read & Fix Bug"));
    expect(getRunBtn()).toBeTruthy();

    // Click run — button content changes to spinner, text disappears
    fireEvent.click(getRunBtn());
    expect(document.querySelector(".spinner")).toBeTruthy();

    // Advance timers past the 1200ms delay
    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    // Results should now be visible
    expect(screen.getByText("📊 Evaluation Results")).toBeTruthy();
  });

  it("shows action cards after evaluation completes", async () => {
    render(<PlaygroundApp />);
    fireEvent.click(screen.getByText("Read & Fix Bug"));
    fireEvent.click(getRunBtn());

    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    // Skill names appear BOTH as skill chips AND as action card headers
    // Use getAllByText to confirm they appear at least once in results
    const actionsSection = document.querySelector(".actions-list")!;
    expect(actionsSection.textContent).toContain("read_file");
    expect(actionsSection.textContent).toContain("write_file");
    expect(actionsSection.textContent).toContain("json_parse");
    expect(actionsSection.textContent).toContain("diff");
  });  it("shows action card inputs as JSON", async () => {
    render(<PlaygroundApp />);
    fireEvent.click(screen.getByText("Read & Fix Bug"));
    fireEvent.click(getRunBtn());

    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    // Action inputs appear as JSON in <pre> elements within .actions-list
    const actionsSection = document.querySelector(".actions-list")!;
    expect(actionsSection.textContent).toContain("src/index.ts");
  });

  it("shows action order numbers", async () => {
    render(<PlaygroundApp />);
    fireEvent.click(screen.getByText("Read & Fix Bug"));
    fireEvent.click(getRunBtn());

    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    // Action order numbers rendered as: 1, 2, 3, 4
    expect(document.querySelectorAll(".action-order").length).toBe(4);
    const orders = Array.from(document.querySelectorAll(".action-order")).map(
      (el) => el.textContent,
    );
    expect(orders).toEqual(["1", "2", "3", "4"]);
  });

  it("shows empty state when no skills selected and no prompt matches", async () => {
    render(<PlaygroundApp />);

    // Deselect all 4 default selected skills
    const selected = document.querySelectorAll(".skill-chip.selected");
    selected.forEach((chip) => fireEvent.click(chip));

    fireEvent.click(screen.getByText("Read & Fix Bug"));
    fireEvent.click(getRunBtn());

    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    expect(
      screen.getByText(
        "No actions returned. Model may have failed to produce valid JSON.",
      ),
    ).toBeTruthy();
  });

  it("switches to scores tab and shows computed scores", async () => {
    render(<PlaygroundApp />);
    fireEvent.click(screen.getByText("Read & Fix Bug"));
    fireEvent.click(getRunBtn());

    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    fireEvent.click(screen.getByText("Scores"));

    // With 4 skills: overall = 0.25 + 0.2 + 0.3 + 0.2 = 0.95 → 95%
    expect(screen.getByText("Overall")).toBeTruthy();
    expect(screen.getByText("95%")).toBeTruthy();
    expect(screen.getByText("Validity")).toBeTruthy();
    expect(screen.getByText("Planning")).toBeTruthy();
    expect(screen.getByText("Skill Correctness")).toBeTruthy();
    expect(screen.getByText("Constraint Adherence")).toBeTruthy();
  });

  it("shows score percentages for each category", async () => {
    render(<PlaygroundApp />);
    fireEvent.click(screen.getByText("Read & Fix Bug"));
    fireEvent.click(getRunBtn());

    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    fireEvent.click(screen.getByText("Scores"));

    // validity=100%, planning=80%, correctness=100%, constraints=100%
    // "100%" appears 3 times, "80%" appears once
    expect(screen.getAllByText("100%").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("80%")).toBeTruthy();
  });

  it("shows score-value with good CSS class when overall >= 0.8", async () => {
    render(<PlaygroundApp />);
    fireEvent.click(screen.getByText("Read & Fix Bug"));
    fireEvent.click(getRunBtn());

    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    fireEvent.click(screen.getByText("Scores"));
    const scoreValue = document.querySelector(".score-value");
    expect(scoreValue?.classList.contains("good")).toBe(true);
  });

  it("switches to raw JSON tab and shows raw response", async () => {
    render(<PlaygroundApp />);
    fireEvent.click(screen.getByText("Read & Fix Bug"));
    fireEvent.click(getRunBtn());

    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    fireEvent.click(screen.getByText("Raw JSON"));
    const rawOutput = document.querySelector(".raw-output");
    expect(rawOutput).toBeTruthy();
    expect(rawOutput?.textContent).toContain("read_file");
    expect(rawOutput?.textContent).toContain("src/index.ts");
  });

  it("does not show results section before evaluation completes", () => {
    render(<PlaygroundApp />);
    expect(screen.queryByText("📊 Evaluation Results")).toBeNull();
  });

  it("re-enables the run button after evaluation completes", async () => {
    render(<PlaygroundApp />);
    fireEvent.click(screen.getByText("Read & Fix Bug"));
    fireEvent.click(getRunBtn());

    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    // Loading is false — button re-renders with text
    expect((getRunBtn() as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows nestjs skills when prompt matches condition", async () => {
    render(<PlaygroundApp />);

    // Select nestjs_jwt_guard skill
    const jwtGuardChip = Array.from(document.querySelectorAll(".skill-chip")).find(
      (c) => c.textContent?.includes("nestjs_jwt_guard"),
    );
    fireEvent.click(jwtGuardChip!);

    // Apply "Auth Guard Debug" template — prompt contains "auth"
    fireEvent.click(screen.getByText("Auth Guard Debug"));
    fireEvent.click(getRunBtn());

    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    // "nestjs_jwt_guard" appears as both a skill chip AND an action header
    // Scope to the results section
    const resultsSection = document.querySelector(".results-section")!;
    expect(resultsSection.textContent).toContain("nestjs_jwt_guard");
  });

  // ── V2: Trace capture ─────────────────────────────────────────

  it("shows View Trace button after evaluation completes", async () => {
    render(<PlaygroundApp />);
    fireEvent.click(screen.getByText("Read & Fix Bug"));
    fireEvent.click(getRunBtn());

    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    expect(screen.getByText("View Trace")).toBeTruthy();
  });

  it("View Trace link points to the trace explorer with trace_id", async () => {
    render(<PlaygroundApp />);
    fireEvent.click(screen.getByText("Read & Fix Bug"));
    fireEvent.click(getRunBtn());

    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    const viewTrace = screen.getByText("View Trace");
    const href = viewTrace.closest("a")?.getAttribute("href");
    expect(href).toContain("/traces?trace_id=pg-");
  });

  it("saves captured trace to localStorage after evaluation", async () => {
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");

    render(<PlaygroundApp />);
    fireEvent.click(screen.getByText("Read & Fix Bug"));
    fireEvent.click(getRunBtn());

    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    expect(setItemSpy).toHaveBeenCalled();
    const [key, value] = setItemSpy.mock.calls[0];
    expect(key).toBe("model-lens-playground-traces");
    const parsed = JSON.parse(value as string);
    expect(Array.isArray(parsed)).toBe(true);
    expect(parsed.length).toBeGreaterThanOrEqual(1);
    expect(parsed[0].id).toContain("pg-");
    expect(parsed[0].steps.length).toBeGreaterThan(0);
  });

  it("trace includes system, prompt, tool_call, reasoning, and response steps", async () => {
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");

    render(<PlaygroundApp />);
    fireEvent.click(screen.getByText("Read & Fix Bug"));
    fireEvent.click(getRunBtn());

    await act(async () => {
      vi.advanceTimersByTime(1200);
    });

    const [, value] = setItemSpy.mock.calls[0];
    const parsed = JSON.parse(value as string);
    const trace = parsed[0];
    const types = trace.steps.map((s: any) => s.type);
    expect(types).toContain("system");
    expect(types).toContain("prompt");
    expect(types).toContain("tool_call");
    expect(types).toContain("reasoning");
    expect(types).toContain("response");
  });
});
