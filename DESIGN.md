---
name: Kinetic Logic
colors:
  surface: '#12131a'
  surface-dim: '#12131a'
  surface-bright: '#383941'
  surface-container-lowest: '#0d0e15'
  surface-container-low: '#1a1b22'
  surface-container: '#1e1f26'
  surface-container-high: '#292931'
  surface-container-highest: '#33343c'
  on-surface: '#e3e1ec'
  on-surface-variant: '#c2c6d6'
  inverse-surface: '#e3e1ec'
  inverse-on-surface: '#2f3038'
  outline: '#8c909f'
  outline-variant: '#424754'
  surface-tint: '#adc6ff'
  primary: '#adc6ff'
  on-primary: '#002e6a'
  primary-container: '#4d8eff'
  on-primary-container: '#00285d'
  inverse-primary: '#005ac2'
  secondary: '#4edea3'
  on-secondary: '#003824'
  secondary-container: '#00a572'
  on-secondary-container: '#00311f'
  tertiary: '#ffb2b7'
  on-tertiary: '#67001b'
  tertiary-container: '#ff516a'
  on-tertiary-container: '#5b0017'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#adc6ff'
  on-primary-fixed: '#001a42'
  on-primary-fixed-variant: '#004395'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#ffdadb'
  tertiary-fixed-dim: '#ffb2b7'
  on-tertiary-fixed: '#40000d'
  on-tertiary-fixed-variant: '#92002a'
  background: '#12131a'
  on-background: '#e3e1ec'
  surface-variant: '#33343c'
typography:
  display:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  mono-label:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
  mono-data:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  container-padding: 1.5rem
  gutter: 1rem
  stack-sm: 0.5rem
  stack-md: 1rem
---

## Brand & Style
The design system focuses on extreme precision and information density for the developer ecosystem. The brand personality is clinical, reliable, and utilitarian, designed to recede and allow complex performance data to take center stage. 

The aesthetic is **Minimalist-Technical**, drawing from the visual language of IDEs and observability platforms. It prioritizes rapid data scanning and cognitive efficiency over decorative flair. 

**Key Principles:**
- **Objectivity:** Every pixel must serve a functional purpose.
- **Density:** Information is presented in high-fidelity clusters without sacrificing legibility.
- **Clarity:** Clear delineations between data states (success, failure, pending) using a disciplined color system.

## Colors
The palette is rooted in a "Zinc" neutral scale to provide a low-fatigue environment for long-duration monitoring.

- **Primary (Blue-500):** Used exclusively for interactive states, primary actions, and "Active" status.
- **Success (Emerald-500):** Indicates passing benchmarks, healthy nodes, and positive performance deltas.
- **Failure (Rose-500):** Highlights regressions, failed runs, and critical errors.
- **Warning (Amber-500):** Used for soft regressions or non-breaking performance dips.
- **Backgrounds:** A layered dark approach. Base surface is `#12131a`, with container surfaces at `#1e1f26` (see YAML for exact hex values).
- **Borders:** A consistent `#424754` for all structural dividers and component edges.

## Typography
The typography system uses a dual-font approach to distinguish between UI orchestration and raw data output.

- **Inter:** Used for all interface elements, navigation, and labels. It is chosen for its neutrality and excellent legibility at small scales.
- **JetBrains Mono:** Used for all "Terminal" content, code snippets, log streams, and tabular numeric data (ensuring character alignment in performance columns).

**Usage Rules:**
- Use `mono-data` for any value derived from a benchmark run.
- Headers should be kept small to maximize vertical space for data.
- Uppercase styling is reserved for `mono-label` elements to denote metadata keys.

## Layout & Spacing
The layout uses a **Fluid-Fixed Hybrid** model. Navigation and sidebars are fixed-width to maintain consistent tool access, while the main content area (The Dashboard) is fluid to accommodate wide tables and multi-pane traces.

- **Grid:** A 12-column grid is used for high-level dashboard layouts.
- **Density:** Elements are packed tightly using a 4px base unit. 
- **Breakpoints:**
  - Desktop (1440px+): Full multi-column view with expanded sidebars.
  - Laptop (1024px): Collapsed sidebars, single-pane focus.
  - Tablet/Mobile: Critical status only; benchmark execution is disabled.
- **Margins:** 24px (1.5rem) standard container padding for all primary views.

## Elevation & Depth
This design system rejects traditional shadows in favor of **Tonal Layering** and **1px Borders**. Depth is communicated through color value shifts rather than light simulation.

- **Level 0 (Background):** `#12131a` — The application canvas.
- **Level 1 (Card/Container):** `#1e1f26` — The primary surface for widgets and tables.
- **Level 2 (Hover/Active):** `#292931` — Hover states and active elements use a slightly lighter fill.
- **Level 3 (Popover/Modal):** `#33343c` — Floating elements use the highest surface level and a more prominent border.
- **Interaction:** Hover states utilize a subtle background highlight (`#292931`) rather than a lift or shadow.

## Shapes
Shapes are intentionally conservative to maintain a "scientific" look. 

- **Components:** Buttons, inputs, and cards use a 4px (`0.25rem`) radius. This provides just enough softness to prevent a "raw code" look while maintaining high-density alignment.
- **Status Indicators:** Small 6px circles are used for status pips (running, idle, error).
- **Charts:** Line graphs use 0px smoothing (linear interpolation) to represent data accurately without artificial "prettification."

## Components
- **Data Tables:** High-density with 1px borders between rows. Use `mono-data` for cell values. Heatmap cells use background-color opacity based on value percentile.
- **Buttons:** Low-profile. Outline style for secondary actions, solid Blue-500 for primary. Height is capped at 32px for most UI contexts.
- **Input Fields:** Dark background (`#0d0e15` lowest surface), `#424754` border, mono-font text.
- **Trace Timelines:** Horizontal stacked bars using the primary/success/failure palette. 1px vertical markers for "Time to First Token" (TTFT).
- **Code Diff:** Standard GitHub-inspired green/red line highlights, using JetBrains Mono at 13px.
- **Charts:** All axes should use Zinc-500 labels. Avoid fills under line charts to keep the visual field clear for multiple overlapping data series.
- **Chips/Tags:** Rectangular with 2px radius, used for model names (e.g., `llama-3-70b`) or environment tags.