// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PackCard from "./PackCard";

const mockPacks = [
  {
    name: "nestjs-pack",
    version: "1.0.0",
    description: "NestJS backend development prompts",
    tags: ["backend", "nestjs", "typescript"],
    categories: [
      { id: "di", label: "Dependency Injection", difficulty: ["easy", "medium"], count: 5 },
      { id: "service", label: "Services", difficulty: ["medium", "hard"], count: 8 },
    ],
    skills: [
      { name: "nestjs_di", version: "1.0", description: "Dependency injection patterns" },
      { name: "nestjs_service", description: "Service layer patterns" },
    ],
    total_prompts: 13,
    author: "Team",
    license: "MIT",
  },
  {
    name: "react-pack",
    version: "2.1.0",
    description: "React frontend development prompts with hooks and state",
    tags: ["frontend", "react", "typescript"],
    categories: [
      { id: "hooks", label: "Hooks", difficulty: ["easy"], count: 6 },
    ],
    skills: [
      { name: "react_hooks", description: "React hooks patterns" },
    ],
    total_prompts: 6,
  },
  {
    name: "debugging-pack",
    version: "0.5.0",
    description: "Debugging scenarios for various frameworks",
    tags: ["debugging", "race-condition", "typescript"],
    categories: [
      { id: "races", label: "Race Conditions", difficulty: ["hard"], count: 4 },
    ],
    skills: [
      { name: "race_debug", description: "Race condition debugging" },
    ],
    total_prompts: 4,
  },
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe("PackCard", () => {
  it("renders all pack names", () => {
    render(<PackCard packs={mockPacks} />);
    expect(screen.getByText("nestjs-pack")).toBeTruthy();
    expect(screen.getByText("react-pack")).toBeTruthy();
    expect(screen.getByText("debugging-pack")).toBeTruthy();
  });

  it("renders pack descriptions", () => {
    render(<PackCard packs={mockPacks} />);
    expect(screen.getByText("NestJS backend development prompts")).toBeTruthy();
    expect(screen.getByText("React frontend development prompts with hooks and state")).toBeTruthy();
  });

  it("renders version badges", () => {
    render(<PackCard packs={mockPacks} />);
    expect(screen.getByText("v1.0.0")).toBeTruthy();
    expect(screen.getByText("v2.1.0")).toBeTruthy();
    expect(screen.getByText("v0.5.0")).toBeTruthy();
  });

  it("renders pack tags (tags also appear as filter chips)", () => {
    render(<PackCard packs={mockPacks} />);
    // "backend", "react", and "debugging" each appear as PACK TAGS + FILTER CHIPS
    expect(screen.getAllByText("backend").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("react").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("debugging").length).toBeGreaterThanOrEqual(1);
  });

  it("renders prompt count stats", () => {
    render(<PackCard packs={mockPacks} />);
    expect(screen.getByText("13 prompts")).toBeTruthy();
    expect(screen.getByText("6 prompts")).toBeTruthy();
    expect(screen.getByText("4 prompts")).toBeTruthy();
  });

  it("renders skill count stats", () => {
    render(<PackCard packs={mockPacks} />);
    expect(screen.getByText("2 skills")).toBeTruthy();
    expect(screen.getAllByText("1 skills").length).toBe(2);
  });

  it("renders category count stats", () => {
    render(<PackCard packs={mockPacks} />);
    expect(screen.getByText("2 categories")).toBeTruthy();
  });

  it("shows the pack count in the sidebar", () => {
    render(<PackCard packs={mockPacks} />);
    expect(screen.getByText("3")).toBeTruthy();
  });

  it("expands a pack card to show categories and skills on click", async () => {
    const user = userEvent.setup();
    render(<PackCard packs={mockPacks} />);
    await user.click(screen.getByText("nestjs-pack"));
    await waitFor(() => {
      expect(screen.getByText("Dependency Injection")).toBeTruthy();
      expect(screen.getByText("Dependency injection patterns")).toBeTruthy();
    });
  });

  it("expanded pack shows difficulty badges", async () => {
    const user = userEvent.setup();
    render(<PackCard packs={mockPacks} />);
    await user.click(screen.getByText("nestjs-pack"));
    await waitFor(() => {
      // "easy" and "medium" appear as both sidebar chips + pack badges
      expect(screen.getAllByText("easy").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("medium").length).toBeGreaterThanOrEqual(1);
      // "hard" appears once as a pack badge (sidebar has "Hard" capitalized)
      expect(screen.getByText("hard")).toBeTruthy();
    });
  });

  it("expanded pack shows skill names", async () => {
    const user = userEvent.setup();
    render(<PackCard packs={mockPacks} />);
    await user.click(screen.getByText("nestjs-pack"));
    await waitFor(() => {
      expect(screen.getByText("nestjs_di")).toBeTruthy();
      expect(screen.getByText("nestjs_service")).toBeTruthy();
    });
  });

  it("shows author and license metadata when expanded", async () => {
    const user = userEvent.setup();
    render(<PackCard packs={mockPacks} />);
    await user.click(screen.getByText("nestjs-pack"));
    await waitFor(() => {
      expect(screen.getByText(/Team/)).toBeTruthy();
      expect(screen.getByText(/MIT/)).toBeTruthy();
    });
  });

  it("collapses an expanded pack on second click", async () => {
    const user = userEvent.setup();
    render(<PackCard packs={mockPacks} />);
    await user.click(screen.getByText("nestjs-pack"));
    await waitFor(() => {
      expect(screen.getByText("Dependency Injection")).toBeTruthy();
    });
    await user.click(screen.getByText("nestjs-pack"));
    await waitFor(() => {
      expect(screen.queryByText("Dependency Injection")).toBeNull();
    });
  });

  it("filters packs by tag (clicking sidebar chip using container scope)", async () => {
    const user = userEvent.setup();
    const { container } = render(<PackCard packs={mockPacks} />);

    // Find the filter chip within the sidebar only (tags also appear on cards)
    const sidebar = container.querySelector(".packs-sidebar") as HTMLElement;
    const frontendChip = within(sidebar).getByText("frontend");
    await user.click(frontendChip);
    await waitFor(() => {
      expect(screen.getByText("react-pack")).toBeTruthy();
      expect(screen.queryByText("nestjs-pack")).toBeNull();
      expect(screen.queryByText("debugging-pack")).toBeNull();
    });
  });

  it("filters packs by difficulty", async () => {
    const user = userEvent.setup();
    const { container } = render(<PackCard packs={mockPacks} />);

    // "Medium" difficulty only matches nestjs-pack (DI: easy/medium, Services: medium/hard)
    const sidebar = container.querySelector(".packs-sidebar") as HTMLElement;
    await user.click(within(sidebar).getByText("Medium"));
    await waitFor(() => {
      expect(screen.getByText("nestjs-pack")).toBeTruthy();
      expect(screen.queryByText("react-pack")).toBeNull();
      expect(screen.queryByText("debugging-pack")).toBeNull();
    });
  });

  it("shows empty state when no packs match filters", async () => {
    const user = userEvent.setup();
    const { container } = render(<PackCard packs={mockPacks} />);

    // Click a tag chip that no pack has
    const sidebar = container.querySelector(".packs-sidebar") as HTMLElement;
    await user.click(within(sidebar).getByText("agentic"));
    await waitFor(() => {
      expect(screen.getByText("No packs match the selected filters.")).toBeTruthy();
    });
  });

  it("resets to all packs when changing to 'All Packs'", async () => {
    const user = userEvent.setup();
    const { container } = render(<PackCard packs={mockPacks} />);

    // Filter by frontend, then reset
    const sidebar = container.querySelector(".packs-sidebar") as HTMLElement;
    await user.click(within(sidebar).getByText("frontend"));
    await waitFor(() => {
      expect(screen.queryByText("nestjs-pack")).toBeNull();
    });

    await user.click(within(sidebar).getByText("All Packs"));
    await waitFor(() => {
      expect(screen.getByText("nestjs-pack")).toBeTruthy();
    });
  });

  it("shows category count when expanded", async () => {
    const user = userEvent.setup();
    const { container } = render(<PackCard packs={mockPacks} />);
    await user.click(screen.getByText("react-pack"));
    await waitFor(() => {
      // Check the specific category count element (not the "6 prompts" stat)
      const catCount = container.querySelector(".pack-cat-count");
      expect(catCount?.textContent).toBe("6");
    });
  });
});
