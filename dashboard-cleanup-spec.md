# Dashboard Cleanup & Docs Consolidation — Specification

> **Created:** 2026-05-30
> **Status:** Approved — ready for implementation
> **Based on:** ChatGPT design review + user interviews (4 rounds)

---

## Overview

Three parallel workstreams that clean up the dashboard codebase, consolidate documentation, and remove unnecessary artefacts — all without changing any runtime behavior or visual appearance.

| # | Workstream | Scope |
|---|---|---|
| 1 | **Component extraction** | Break `index.astro` (~150 lines inline) into 6 reusable Astro components |
| 2 | **CSS deduplication** | Remove duplicate `.compare-table` styles from `compare.astro` scoped block |
| 3 | **Docs & artefacts cleanup** | Delete 3 redundant READMEs, move DESIGN.md, remove stale files, git hygiene |

---

## Workstream 1 — Component Extraction from `index.astro`

### Goal

Extract all 5 inline dashboard sections plus a `DashboardShell` wrapper into dedicated `.astro` components. `index.astro` should become a thin orchestration layer.

### Decision log

| Decision | Rationale |
|---|---|
| Astro `.astro` for all components | User choice. Less client JS, better perf. Existing React chart components (`RadarChart.tsx`, `SpeedChart.tsx`, `FailureHeatmap.tsx`) are imported by the new `.astro` wrappers — no React refactor needed. |
| DashboardShell stays minimal | Sidebar/topbar/node badge remain in `BaseLayout.astro` (app chrome). DashboardShell is page-level grid layout only. This keeps separation of concerns clean: layout = app shell, DashboardShell = page structure. |
| All 5 sections extracted | User choice ("all 5 + DashboardShell"). Each section becomes a self-contained, reusable component. |

### Component architecture

```
index.astro (thin: imports + data loading + <DashboardShell>)
  └── DashboardShell.astro (page-level grid wrapper)
        ├── DashboardHeader.astro     (title, subtitle, filter/export buttons)
        ├── RadarPanel.astro          (model capabilities radar chart card)
        ├── ThroughputPanel.astro     (throughput-over-time speed chart card)
        ├── BenchmarkMatrix.astro     (benchmark matrix table card)
        ├── FailureHeatmapPanel.astro (failure breakdown section + heatmap)
        └── SystemResources.astro     (GPU memory, latency, samples cards)
```

### Per-component details

#### `DashboardShell.astro`
- **Props:** `models: ModelSummary[]`, `results: BenchmarkResult[]`, `uniqueModels: string[]`, `avgLatencyMs: string`, `topModels: ModelSummary[]`
- **Output:** Wraps the 6 child panels in the dashboard layout grid. No sidebar/topbar — those stay in BaseLayout.
- **CSS:** Reuses existing `.dashboard-charts`, `.dashboard-table`, `.dashboard-failures`, `.dashboard-resources` classes from BaseLayout.

#### `DashboardHeader.astro`
- **Props:** `title: string`, `subtitle: string`
- **Output:** The `.dashboard-header` div with title, subtitle, and filter/export action buttons.
- **Renders inline HTML only** — no React needed.

#### `RadarPanel.astro`
- **Props:** `models: ModelSummary[]`, `topModels: ModelSummary[]`
- **Output:** The `.chart-card-radar` card with chart header, model legend dots, and `<RadarChart client:load models={models} />`.
- **Imports:** `RadarChart` from `../components/RadarChart.tsx`.

#### `ThroughputPanel.astro`
- **Props:** `models: ModelSummary[]`
- **Output:** The `.chart-card-throughput` card with chart header, context window badge, `<SpeedChart client:load models={models} />`, and context ticks.
- **Imports:** `SpeedChart` from `../components/SpeedChart.tsx`.

#### `BenchmarkMatrix.astro`
- **Props:** `models: ModelSummary[]`
- **Output:** The `.dashboard-table` section with card wrapper, table header ("Benchmark Matrix"), and `<ModelTable client:load models={models} />`.
- **Imports:** `ModelTable` from `../components/ModelTable.tsx`.

#### `FailureHeatmapPanel.astro`
- **Props:** `results: BenchmarkResult[]`
- **Output:** The `.dashboard-failures` section with section header (title + subtitle) and `<FailureHeatmap client:load results={results} />` inside a fixed-height card.
- **Imports:** `FailureHeatmap` from `../components/FailureHeatmap.tsx`.

#### `SystemResources.astro`
- **Props:** `avgLatencyMs: string`, `resultsCount: number`
- **Output:** The `.dashboard-resources` grid with 3 resource cards (GPU Memory, Average Latency, Benchmark Database).
- **Renders inline HTML only** — no React needed.

### `index.astro` after extraction

```astro
---
import BaseLayout from '../layouts/BaseLayout.astro';
import DashboardShell from '../components/DashboardShell.astro';
import { loadResults, buildLeaderboard } from '../lib/loadResults';
import type { BenchmarkResult } from '../lib/loadResults';

const results: BenchmarkResult[] = await loadResults();
const { leaderboard } = buildLeaderboard(results);

const uniqueModels = [...new Set(results.map(r => r.model))];
const avgLatencyMs = leaderboard.length > 0
  ? (leaderboard.reduce((s, m) => s + m.performance.ttft_ms, 0) / leaderboard.length).toFixed(0)
  : '—';
const topModels = leaderboard.slice(0, 3);
---

<BaseLayout title="Dashboard" description="...">
  {
    results.length === 0
    ? <div class="empty-state">...</div>
    : <DashboardShell
        models={leaderboard}
        results={results}
        uniqueModels={uniqueModels}
        avgLatencyMs={avgLatencyMs}
        topModels={topModels}
      />
  }
</BaseLayout>
```

### Files to create

| File | Type |
|---|---|
| `dashboard/src/components/DashboardShell.astro` | New |
| `dashboard/src/components/DashboardHeader.astro` | New |
| `dashboard/src/components/RadarPanel.astro` | New |
| `dashboard/src/components/ThroughputPanel.astro` | New |
| `dashboard/src/components/BenchmarkMatrix.astro` | New |
| `dashboard/src/components/FailureHeatmapPanel.astro` | New |
| `dashboard/src/components/SystemResources.astro` | New |

### Files to modify

| File | Change |
|---|---|
| `dashboard/src/pages/index.astro` | Replace inline sections with `<DashboardShell>` |

### Imports cleanup in `index.astro`

**Removed imports (no longer directly used):**
- `ModelTable` (moved to `BenchmarkMatrix.astro`)
- `RadarChartWrapper` (superseded by `RadarPanel.astro` which directly uses `RadarChart.tsx`)
- `SpeedChart` (moved to `ThroughputPanel.astro`)
- `FailureHeatmap` (moved to `FailureHeatmapPanel.astro`)

**New import:**
- `DashboardShell`

---

## Workstream 2 — CSS Deduplication

### Problem

`.compare-table` CSS rules are defined in TWO places:
1. `BaseLayout.astro` — global `:global` styles (~40 lines)
2. `compare.astro` — scoped `<style>` block (~40 lines)

The scoped version in `compare.astro` silently overrides the global version, making the global version dead code.

### Decision

Keep the global version in `BaseLayout.astro` (user choice). Remove the duplicated `.compare-table` rules from `compare.astro`'s scoped block.

### What stays in `compare.astro` scoped styles

These page-specific styles are NOT duplicated and stay scoped:
- `.winner-summary`, `.winner-card`, `.winner-label`, `.winner-row`, `.winner-model`
- `.methodology-section`, `.methodology-grid`, `.methodology-card`

Rationale: These are unique to the compare page. Colocating them with the page keeps BaseLayout from bloating with single-use styles. Scoped styles prevent leakage to other pages.

### What gets removed from `compare.astro` scoped styles

- Entire `.compare-table` block (~25 lines):
  - `.compare-table` base
  - `.compare-table thead th` (all variants)
  - `.compare-table tbody td` (all variants)
  - `.compare-table tbody tr` + `:hover`
  - `.compare-table .row-separator td`
  - `.cell-best` + `.cell-best .best-badge`

These all exist identically in `BaseLayout.astro`.

### Verification

After removal, `compare.astro`'s `<style>` block should contain only:
- `.winner-summary` family (~5 rules)
- `.methodology-section` family (~3 rules)

---

## Workstream 3 — Docs Consolidation & Artefact Cleanup

### 3a. README consolidation

**Decision:** Keep `README.md`, delete the 3 overlapping files. (User choice: "Keep README.md + delete 3")

| File | Action | Rationale |
|---|---|---|
| `README.md` | **Keep** | Already comprehensive — covers all DevBench variants |
| `README_V1.md` | **Delete** | DevBench v1 legacy doc — content already covered in README.md |
| `README_APPLE_SILICON.md` | **Delete** | Apple Silicon-specific angle — content already covered in README.md |
| `README_DEVBENCH.md` | **Delete** | DevBench v2 detailed — content already covered in README.md |
| `knowledge.md` | **Keep** | Separate purpose: AI agent context for Codebuff (project goals, commands, conventions, gotchas) |

### 3b. DESIGN.md relocation

**Decision:** Move `stitch_lm_studio_forge/kinetic_logic/DESIGN.md` → `docs/DESIGN.md`. Delete the rest of `stitch_lm_studio_forge/`. (User choice: "Keep DESIGN.md only, move to /docs/")

| Path | Action |
|---|---|
| `docs/DESIGN.md` | Create — copy of kinetic_logic/DESIGN.md |
| `stitch_lm_studio_forge/` | Delete entire directory (5 HTML prototypes + kinetic_logic folder) |

**Reference strategy:** Add a short mention in both `README.md` and `knowledge.md`:

- **README.md** — Add to "Architecture" or new "Design" section: `See docs/DESIGN.md for the Kinetic Logic design system governing all dashboard UI.`
- **knowledge.md** — Add to "Conventions" section: `Dashboard UI follows the Kinetic Logic design system (see docs/DESIGN.md).`

### 3c. File artefact cleanup (safe approach)

Rule: Only delete if 100% sure the file is unnecessary.

| File | Action | Certainty | Rationale |
|---|---|---|---|
| `leaderboard.html` | **Delete** | ✅ 100% | Standalone static HTML leaderboard. Fully superseded by `compare.astro` and `index.astro` dashboard pages. |
| `stitch_lm_studio_forge/` | **Delete** | ✅ 100% | All 5 HTML prototypes adapted. DESIGN.md moved to `/docs/`. |
| `bench_apple_silicon.py` | **Keep** | ❌ Not 100% | DevBench v1 — simpler, no variance tracking. Still referenced in knowledge.md. Someone may want the simpler version. |
| `config.yaml` | **Keep** | ❌ Not 100% | General benchmark config for `benchmark.py`. Separate system from `config.json`. Knowledge.md warns "Don't mix them up." Both are actively used. |
| `skill-lock.json` | **Keep** | ❌ Not 100% | Lockfile managed by `skill_pack_sdk.py`. Like package-lock.json — needed for reproducible pack installations. |
| `.agents/` | **Keep** | ❌ Not 100% | Internal Codebuff agent type definitions. Not our domain to touch. |

### 3d. Git hygiene

| Action | Detail |
|---|---|
| `__pycache__/` | Already in `.gitignore` (line ~114: `__pycache__/`). No changes needed. |
| `.gitkeep` for `docs/` | Create `docs/.gitkeep` to ensure the new directory is tracked even if it only has one file initially. The `.gitignore` does not exclude `docs/`. |

### Summary of deleted files

```
README_V1.md                           ← redundant
README_APPLE_SILICON.md                ← redundant
README_DEVBENCH.md                     ← redundant
leaderboard.html                       ← superseded by dashboard
stitch_lm_studio_forge/                ← entire directory (DESIGN.md moved to docs/)
  ├── lm_studio_benchmark_platform.html
  ├── model_comparison_dashboard/code.html
  ├── agentic_traces_explorer/code.html
  ├── prompt_packs_registry/code.html
  ├── global_leaderboard/code.html
  ├── side_by_side_model_comparison/code.html
  └── kinetic_logic/DESIGN.md          ← moved to docs/DESIGN.md
```

### Summary of created files

```
docs/
  ├── DESIGN.md                        ← moved from stitch_lm_studio_forge/kinetic_logic/
  └── .gitkeep
```

### Summary of modified files

```
README.md                              ← add DESIGN.md reference
knowledge.md                           ← add DESIGN.md reference
```

---

## Validation Plan

After all changes, run in parallel:

| Check | Command | Expected |
|---|---|---|
| Dashboard build | `cd dashboard && npm run build` | 4 pages generated, zero errors |
| README.md exists | `ls README.md knowledge.md docs/DESIGN.md` | All 3 exist |
| Deleted files gone | `ls README_V1.md README_APPLE_SILICON.md README_DEVBENCH.md leaderboard.html 2>&1` | "No such file" for all |
| Stitch dir gone | `ls -d stitch_lm_studio_forge 2>&1` | "No such file" |
| Compare page works | Visual check: compare.astro still renders winner cards + comparison table + methodology cards | No visual regressions |
| Dashboard page works | Visual check: all 5 sections render identically to before extraction | No visual regressions |

---

## Out of Scope

- Adding new features or pages (Leaderboard, Packs Registry, Traces Explorer)
- Changing any visual appearance or CSS values
- Adding tests (no test framework exists)
- Refactoring React components (RadarChart, SpeedChart, FailureHeatmap, ModelTable)
- Migrating to shadcn/ui, TanStack Table, or Recharts
- Replacing `config.yaml` or `bench_apple_silicon.py`
