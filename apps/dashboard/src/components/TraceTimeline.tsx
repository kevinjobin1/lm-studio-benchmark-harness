import React, { useState, useEffect, useRef, useCallback } from "react";
import type { BenchmarkResult } from "../lib/loadResults";
import { loadPlaygroundTraces } from "../lib/playgroundTraces";
import type { TraceRun, TraceStep } from "../lib/traceTypes";
import { stepIcons, stepColors } from "../lib/traceTypes";
import { traceRunToSnapshot, saveSnapshot, snapshotUrl } from "../lib/loadSnapshots";

// Re-export shared types for backward compatibility
export type { TraceRun, TraceStep } from "../lib/traceTypes";
export { stepIcons, stepColors } from "../lib/traceTypes";

// ── Props ──────────────────────────────────────────────────────────

interface TraceTimelineProps {
  /** Real captured traces (V2). Takes priority over `results`. */
  traces?: TraceRun[];
  /** Benchmark results — synthesized into pseudo-traces as fallback. */
  results?: BenchmarkResult[];
  /** Pre-select a specific trace by ID (e.g., from ?trace_id= query param). */
  initialTraceId?: string;
}

// ── Generate trace steps from real BenchmarkResult data ──────────

function generateStepsFromResult(r: BenchmarkResult): TraceStep[] {
  const steps: TraceStep[] = [];
  const tps = r.performance.tokens_per_sec.toFixed(1);

  // System instruction (always present)
  steps.push({
    id: `${r.run_id}-s0`,
    type: "system",
    label: "System Instruction",
    detail: `Benchmark mode. Packs: ${r.packs_used.join(", ") || "default"}. Seed: ${r.seed ?? "random"}. Prompt version: ${r.prompt_version}.`,
    timing_ms: 0,
    status: "success",
  });

  // Category scores → tool_call steps
  const categories = Object.entries(r.category_scores || {});
  if (categories.length > 0) {
    categories.forEach(([cat, scores], i) => {
      const subEntries = Object.entries(scores as Record<string, number>).slice(
        0,
        3,
      );
      steps.push({
        id: `${r.run_id}-cat${i}`,
        type: "tool_call",
        label: `Evaluating: ${cat}`,
        tool: `eval_${cat}`,
        input: subEntries
          .map(([k, v]) => `${k}: ${(v * 100).toFixed(0)}%`)
          .join("\n"),
        timing_ms: Math.round(r.performance.total_latency_ms * 0.12),
        status: "success",
      });
    });
  }

  // Reasoning step (aggregate score breakdown)
  steps.push({
    id: `${r.run_id}-reasoning`,
    type: "reasoning",
    label: "Score Analysis",
    detail: [
      `Coding: ${(r.metrics.coding_score * 100).toFixed(1)}%`,
      `Reasoning: ${(r.metrics.reasoning_score * 100).toFixed(1)}%`,
      `Instruction: ${(r.metrics.instruction_score * 100).toFixed(1)}%`,
      `Overall: ${(r.metrics.overall_score * 100).toFixed(1)}%`,
      `Tokens/sec: ${tps}`,
      `Hardware: ${r.hardware.processor} (${r.hardware.memory_gb}GB)`,
    ].join(" · "),
    timing_ms: Math.round(r.performance.total_latency_ms * 0.05),
    status: "success",
  });

  // Failures as error steps
  const failures = Object.entries(r.failures || {}).filter(
    ([, count]) => count > 0,
  );
  if (failures.length > 0) {
    failures.forEach(([key, count], i) => {
      steps.push({
        id: `${r.run_id}-err${i}`,
        type: "error",
        label: `Failure: ${key.replace(/_/g, " ")}`,
        detail: `${count} occurrence${count !== 1 ? "s" : ""} detected. ${key === "hallucinated_api" ? "Model referenced non-existent APIs." : key === "syntax_error" ? "Generated code had syntax errors." : key === "logic_error" ? "Logical flaws in output." : key === "type_error" ? "Type mismatches in generated code." : ""}`,
        timing_ms: 0,
        status: "failure",
      });
    });
  }

  // Response step
  steps.push({
    id: `${r.run_id}-response`,
    type: "response",
    label: "Benchmark Complete",
    detail: [
      `Model: ${r.model} (${r.model_metadata.size || "unknown"})`,
      `Overall score: ${(r.metrics.overall_score * 100).toFixed(1)}%`,
      `Throughput: ${tps} tok/s · Latency: ${r.performance.total_latency_ms}ms`,
      `Memory: ${(r.performance.memory_pressure_mb / 1024).toFixed(1)}GB used`,
      `Failures: ${failures.length} categories`,
    ].join(" | "),
    timing_ms: Math.round(r.performance.total_latency_ms * 0.6),
    status: failures.length > 0 ? "failure" : "success",
  });

  return steps;
}

function buildTraceRuns(results: BenchmarkResult[]): TraceRun[] {
  if (results.length === 0) return [];

  return results.map((r) => ({
    id: r.run_id,
    model: r.model,
    pack: r.packs_used[0] || "default",
    prompt: `benchmark/${r.model}`,
    timestamp: new Date(r.timestamp).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }),
    totalTimeMs: r.performance.total_latency_ms,
    status:
      r.metrics.overall_score >= 0.6
        ? ("completed" as const)
        : ("failed" as const),
    steps: generateStepsFromResult(r),
  }));
}

// ── Demo fallback ─────────────────────────────────────────────────

function generateDemoTraces(): TraceRun[] {
  return [
    {
      id: "run-8821-llama-3",
      model: "Llama 3 70B",
      pack: "nestjs-agentic-pack",
      prompt: "auth/JWT Guard Implementation",
      timestamp: "Today, 2:14 PM",
      totalTimeMs: 482,
      status: "completed",
      steps: [
        {
          id: "s1",
          type: "system",
          label: "System Instruction",
          detail:
            "You are a NestJS backend engineer. Implement with proper error handling.",
          timing_ms: 0,
          status: "success",
        },
        {
          id: "s2",
          type: "tool_call",
          label: "Calling: prisma.user.findUnique",
          tool: "prisma_user_service",
          input: '{ id: "user_123" }',
          timing_ms: 42,
          status: "success",
        },
        {
          id: "s3",
          type: "reasoning",
          label: "Analyzing schema relations",
          detail:
            "User → Posts (1:M), User → Profile (1:1). Need to include both relations.",
          timing_ms: 28,
          status: "success",
        },
        {
          id: "s4",
          type: "tool_call",
          label: "Calling: prisma.user.findUnique (with includes)",
          tool: "prisma_user_service",
          input: '{ id: "user_123", include: { posts: true, profile: true } }',
          timing_ms: 38,
          status: "success",
        },
        {
          id: "s5",
          type: "response",
          label: "Generated Implementation",
          detail:
            "Exported UserService.getUserWithRelations() with Prisma includes and error handling.",
          timing_ms: 156,
          status: "success",
        },
      ],
    },
    {
      id: "run-7712-mistral",
      model: "Mistral Large 2",
      pack: "debugging-pack",
      prompt: "debug_race_condition/Async Queue",
      timestamp: "Today, 11:02 AM",
      totalTimeMs: 623,
      status: "completed",
      steps: [
        {
          id: "s1",
          type: "system",
          label: "System Instruction",
          detail: "Find and fix the race condition.",
          timing_ms: 0,
          status: "success",
        },
        {
          id: "s2",
          type: "reasoning",
          label: "Identifying the race condition",
          detail:
            "Promise.all on line 42 fires concurrent writes to same cache key.",
          timing_ms: 45,
          status: "success",
        },
        {
          id: "s3",
          type: "tool_call",
          label: "Calling: grep for cache.set",
          tool: "file_search",
          input: "cache.set",
          timing_ms: 18,
          status: "success",
        },
        {
          id: "s4",
          type: "response",
          label: "Applied Fix",
          detail: "Added async-mutex. Race condition resolved.",
          timing_ms: 312,
          status: "success",
        },
      ],
    },
  ];
}

// ── Download helper (pure utility, no component deps) ────────────

function downloadJSON(data: unknown, filename: string) {
  const json = JSON.stringify(data, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Component ─────────────────────────────────────────────────────

export default function TraceTimeline({ traces, results, initialTraceId }: TraceTimelineProps) {
  // Priority: real traces > synthesized from results > demo
  const tracesFromResults =
    results && results.length > 0 ? buildTraceRuns(results) : null;

  const initialTraces: TraceRun[] =
    (() => {
      // Load playground-captured traces from localStorage (V2)
      const localTraces = loadPlaygroundTraces();

      const base =
        traces && traces.length > 0
          ? traces
          : tracesFromResults && tracesFromResults.length > 0
            ? tracesFromResults
            : generateDemoTraces();

      // Merge: prepend local traces, skip duplicates by ID
      const baseIds = new Set(base.map((t) => t.id));
      const newLocal = localTraces.filter((t) => !baseIds.has(t.id));
      if (newLocal.length > 0) {
        return [...newLocal, ...base];
      }
      return base;
    })();

  // Determine the initial selected run ID:
  // 1. If initialTraceId is provided and exists in the traces, use it
  // 2. Otherwise use the first trace
  const resolvedInitialId = (() => {
    if (initialTraceId) {
      const match = initialTraces.find(t => t.id === initialTraceId);
      if (match) return match.id;
    }
    return initialTraces[0]?.id ?? null;
  })();

  const [allTraces, setAllTraces] = useState<TraceRun[]>(initialTraces);
  const allTracesRef = useRef(allTraces);
  allTracesRef.current = allTraces;

  const [selectedRunId, setSelectedRunId] = useState(resolvedInitialId);
  const [hoveredStep, setHoveredStep] = useState<string | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isScrubbing, setIsScrubbing] = useState(false);
  const [flashStepId, setFlashStepId] = useState<string | null>(null);
  const [slideDirection, setSlideDirection] = useState<"forward" | "backward" | null>(null);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [filterText, setFilterText] = useState("");

  // ── Client-side filtering ──────────────────────────────────
  const filteredTraces = filterText.trim()
    ? allTraces.filter((t) => {
        const q = filterText.toLowerCase();
        return (
          t.model.toLowerCase().includes(q) ||
          t.pack.toLowerCase().includes(q) ||
          t.status.toLowerCase().includes(q)
        );
      })
    : allTraces;
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const slideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navDirectionRef = useRef<"forward" | "backward">("forward");
  const skipSlideRef = useRef(true);
  const wasPlayingBeforeScrub = useRef(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const currentIndexRef = useRef(currentStepIndex);
  const trackRef = useRef<HTMLDivElement | null>(null);
  const stepsRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Keep step-index ref in sync (read inside setInterval to avoid stale closures)
  currentIndexRef.current = currentStepIndex;

  const selectedRun = allTraces.find((t) => t.id === selectedRunId) ?? null;

  // Reset playback state when switching runs
  const handleSelectRun = (id: string) => {
    setIsPlaying(false);
    setIsScrubbing(false);
    skipSlideRef.current = true;
    setSelectedRunId(id);
    setCurrentStepIndex(0);
  };

  // Auto-playback engine
  useEffect(() => {
    if (isPlaying && selectedRun && selectedRun.steps.length > 0) {
      const baseInterval = 600; // ms per step at 1x
      const intervalMs = baseInterval / playbackSpeed;

      intervalRef.current = setInterval(() => {
        const idx = currentIndexRef.current;
        const steps = selectedRun.steps;
        if (idx >= steps.length - 1) {
          // Reached the end — stop and loop back
          setIsPlaying(false);
          navDirectionRef.current = "backward";
          setCurrentStepIndex(0);
        } else {
          navDirectionRef.current = "forward";
          setCurrentStepIndex(idx + 1);
        }
      }, intervalMs);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isPlaying, playbackSpeed, selectedRun]);

  // Playback handlers
  const handlePrevious = useCallback(() => {
    if (!selectedRun || selectedRun.steps.length === 0) return;
    navDirectionRef.current = "backward";
    setCurrentStepIndex(Math.max(0, currentStepIndex - 1));
  }, [selectedRun, currentStepIndex]);

  const handleNext = useCallback(() => {
    if (!selectedRun || selectedRun.steps.length === 0) return;
    navDirectionRef.current = "forward";
    setCurrentStepIndex(
      Math.min(selectedRun.steps.length - 1, currentStepIndex + 1),
    );
  }, [selectedRun, currentStepIndex]);

  const handlePlayPause = useCallback(() => {
    if (!selectedRun || selectedRun.steps.length === 0) return;
    // If at the end, restart from beginning
    if (currentStepIndex >= selectedRun.steps.length - 1 && !isPlaying) {
      navDirectionRef.current = "backward";
      setCurrentStepIndex(0);
    }
    setIsPlaying((prev) => !prev);
  }, [selectedRun, currentStepIndex, isPlaying]);

  const handleSpeedCycle = useCallback(() => {
    setPlaybackSpeed((prev) => (prev >= 4 ? 1 : prev * 2));
  }, []);

  // ── Scrubbing (drag progress bar to jump to any step) ──────────

  const stepFromTrack = useCallback(
    (clientX: number) => {
      if (!trackRef.current || !selectedRun || selectedRun.steps.length === 0) return 0;
      const rect = trackRef.current.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      return Math.min(
        selectedRun.steps.length - 1,
        Math.floor(ratio * selectedRun.steps.length),
      );
    },
    [selectedRun],
  );

  const handleScrubStart = useCallback(
    (e: React.MouseEvent) => {
      // Pause playback during scrub (restore on end)
      wasPlayingBeforeScrub.current = isPlaying;
      if (isPlaying) setIsPlaying(false);
      setIsScrubbing(true);
      const newIndex = stepFromTrack(e.clientX);
      navDirectionRef.current = newIndex >= currentIndexRef.current ? "forward" : "backward";
      setCurrentStepIndex(newIndex);
    },
    [isPlaying, stepFromTrack],
  );

  useEffect(() => {
    if (!isScrubbing) return;

    const handleMove = (e: MouseEvent) => {
      const newIndex = stepFromTrack(e.clientX);
      navDirectionRef.current = newIndex >= currentIndexRef.current ? "forward" : "backward";
      setCurrentStepIndex(newIndex);
    };
    const handleUp = () => {
      setIsScrubbing(false);
      // Restore playback if it was playing before scrubbing
      if (wasPlayingBeforeScrub.current) {
        setIsPlaying(true);
      }
    };

    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [isScrubbing, stepFromTrack]);

  // ── Slide transition: animate step content card when direction changes ─

  useEffect(() => {
    if (!selectedRun) return;

    // Skip animation on initial mount and after run-switch
    if (skipSlideRef.current) {
      skipSlideRef.current = false;
      return;
    }

    // Clear any pending slide timer
    if (slideTimerRef.current) {
      clearTimeout(slideTimerRef.current);
    }

    // Only animate after the initial mount (skip first render)
    const dir = navDirectionRef.current;
    setSlideDirection(dir);
    slideTimerRef.current = setTimeout(() => {
      setSlideDirection(null);
      slideTimerRef.current = null;
    }, 350);

    return () => {
      if (slideTimerRef.current) {
        clearTimeout(slideTimerRef.current);
        slideTimerRef.current = null;
      }
    };
  }, [currentStepIndex, selectedRun]);

  // ── Handler refs (stable across renders for keyboard listener) ─
  const handlePreviousRef = useRef(handlePrevious);
  handlePreviousRef.current = handlePrevious;
  const handleNextRef = useRef(handleNext);
  handleNextRef.current = handleNext;
  const handlePlayPauseRef = useRef(handlePlayPause);
  handlePlayPauseRef.current = handlePlayPause;

  // ── Keyboard shortcuts ────────────────────────────────────────

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept when user is typing in an input/textarea
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      switch (e.key) {
        case " ":
          e.preventDefault();
          handlePlayPauseRef.current();
          break;
        case "ArrowLeft":
          e.preventDefault();
          handlePreviousRef.current();
          break;
        case "ArrowRight":
          e.preventDefault();
          handleNextRef.current();
          break;
        case "1":
          setPlaybackSpeed(1);
          break;
        case "2":
          setPlaybackSpeed(2);
          break;
        case "4":
          setPlaybackSpeed(4);
          break;
        case "?":
          e.preventDefault();
          setShowShortcuts((prev) => !prev);
          break;
      }
    };      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }, []);

    // ── Close shortcuts overlay on Escape ────────────────────────

    useEffect(() => {
      if (!showShortcuts) return;

      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          setShowShortcuts(false);
        }
      };

      window.addEventListener("keydown", handleEscape);
      return () => window.removeEventListener("keydown", handleEscape);
    }, [showShortcuts]);

  // Auto-scroll: keep the current step visible when it changes
  useEffect(() => {
    if (!stepsRef.current || !selectedRun) return;
    const stepElement = stepsRef.current.querySelector(
      `.traces-step-current`,
    ) as HTMLElement | null;
    if (stepElement) {
      stepElement.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [currentStepIndex, selectedRun]);

  // Flash pulse: briefly highlight the newly-arrived step
  useEffect(() => {
    if (!selectedRun) return;
    const step = selectedRun.steps[currentStepIndex];
    if (!step) return;

    // Clear any pending flash timer
    if (flashTimerRef.current) {
      clearTimeout(flashTimerRef.current);
    }

    // Set the flash and schedule removal
    setFlashStepId(step.id);
    flashTimerRef.current = setTimeout(() => {
      setFlashStepId(null);
      flashTimerRef.current = null;
    }, 600);

    return () => {
      if (flashTimerRef.current) {
        clearTimeout(flashTimerRef.current);
        flashTimerRef.current = null;
      }
    };
  }, [currentStepIndex, selectedRun]);

  // ── Scroll parallax: GPU-accelerated dot drift on scroll ─────

  useEffect(() => {
    const stepsEl = stepsRef.current;
    if (!stepsEl) return;

    const handleScroll = () => {
      const scrollTop = stepsEl.scrollTop;
      stepsEl.style.setProperty("--steps-scroll-y", `${scrollTop}px`);
    };

    stepsEl.addEventListener("scroll", handleScroll, { passive: true });
    // Seed initial value
    handleScroll();

    return () => stepsEl.removeEventListener("scroll", handleScroll);
  }, []);

  // ── Export: Copy JSON to clipboard ───────────────────────────

  const showToast = useCallback((message: string) => {
    setToastMessage(message);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => {
      setToastMessage(null);
      toastTimerRef.current = null;
    }, 2000);
  }, []);

  const handleCopyJSON = useCallback(() => {
    if (!selectedRun) return;
    const json = JSON.stringify(selectedRun, null, 2);
    navigator.clipboard.writeText(json).then(() => {
      showToast("Copied to clipboard");
    }).catch(() => {
      // Clipboard API may fail in insecure contexts — silently ignore
    });
  }, [selectedRun, showToast]);

  // ── Snapshot: Save as shareable snapshot ────────────────────

  const [isSavingSnapshot, setIsSavingSnapshot] = useState(false);

  const handleSaveSnapshot = useCallback(async () => {
    if (!selectedRun) return;
    setIsSavingSnapshot(true);
    try {
      const snapshot = traceRunToSnapshot(selectedRun);
      const result = await saveSnapshot(snapshot);
      // Copy the URL to clipboard automatically
      try {
        await navigator.clipboard.writeText(result.url);
        showToast(`Snapshot saved! Link copied: ${result.snapshot_id}`);
      } catch {
        showToast(`Snapshot saved: ${result.url}`);
      }
    } catch {
      showToast("Failed to save snapshot");
    } finally {
      setIsSavingSnapshot(false);
    }
  }, [selectedRun, showToast]);

  const handleCopySnapshotLink = useCallback(async () => {
    if (!selectedRun) return;
    try {
      const snapshot = traceRunToSnapshot(selectedRun);
      const result = await saveSnapshot(snapshot);
      await navigator.clipboard.writeText(result.url);
      showToast(`Link copied: ${result.snapshot_id}`);
    } catch {
      showToast("Failed to create snapshot link");
    }
  }, [selectedRun, showToast]);

  const handleDownloadTrace = useCallback(() => {
    if (!selectedRun) return;
    downloadJSON(selectedRun, `${selectedRun.id}.json`);
    showToast("Trace downloaded");
  }, [selectedRun, showToast]);

  const handleExportAllTraces = useCallback(() => {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    downloadJSON(allTraces, `model-lens-traces-${timestamp}.json`);
    showToast("All traces exported");
  }, [allTraces, showToast]);

  // ── Import: load exported traces JSON back into the sidebar ──

  const handleImportTraces = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = () => {
        try {
          const raw = JSON.parse(reader.result as string);
          const imported = Array.isArray(raw) ? raw : [raw];

          // Basic validation: must have id, model, and steps
          const valid = imported.filter(
            (t: unknown) =>
              t && typeof t === "object" &&
              "id" in t && "model" in t && "steps" in t,
          ) as TraceRun[];

          if (valid.length === 0) {
            showToast("No valid traces found in file");
            return;
          }

          // Merge: skip ids already present, prepend new ones
          // Use ref for latest dedup check (avoids stale-closure bug)
          const existingIds = new Set(allTracesRef.current.map((t) => t.id));
          const newTraces = valid.filter((t) => !existingIds.has(t.id));

          if (newTraces.length === 0) {
            showToast("All traces already loaded");
          } else {
            setAllTraces((prev) => [...newTraces, ...prev]);
            showToast(`Imported ${newTraces.length} trace${newTraces.length !== 1 ? "s" : ""}`);
          }
        } catch {
          showToast("Invalid JSON file");
        }
      };
      reader.readAsText(file);

      // Reset so the same file can be re-imported
      e.target.value = "";
    },
    [showToast],
  );

  // Clean up toast timer on unmount
  useEffect(() => {
    return () => {
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    };
  }, []);

  const progressPct =
    selectedRun && selectedRun.steps.length > 0
      ? ((currentStepIndex + 1) / selectedRun.steps.length) * 100
      : 0;

  return (
    <div className="traces-layout">
      {/* Run List Sidebar */}
      <aside className="traces-sidebar">
        <div className="traces-sidebar-header">
          <span className="mono-label">Recent Runs</span>
          <div className="traces-sidebar-actions">
            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              onChange={handleFileChange}
              style={{ display: "none" }}
            />
            <button
              className="traces-sidebar-export"
              title="Import traces from JSON"
              onClick={handleImportTraces}
              aria-label="Import traces"
            >
              <span className="material-symbols-outlined">file_upload</span>
            </button>
            <button
              className="traces-sidebar-export"
              title="Export all traces"
              onClick={handleExportAllTraces}
              aria-label="Export all traces"
            >
              <span className="material-symbols-outlined">archive</span>
            </button>
            <span className="material-symbols-outlined traces-filter-icon">
              filter_list
            </span>
          </div>
        </div>
        <div className="traces-filter">
          <span className="material-symbols-outlined traces-filter-search-icon">search</span>
          <input
            className="traces-filter-input"
            type="text"
            placeholder="Filter by model, pack, or status…"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            aria-label="Filter traces"
          />
          {filterText && (
            <button
              className="traces-filter-clear"
              onClick={() => setFilterText("")}
              aria-label="Clear filter"
              title="Clear filter"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          )}
        </div>
        <div className="traces-run-list">
          {filteredTraces.map((run) => (
            <div
              key={run.id}
              onClick={() => handleSelectRun(run.id)}
              className={`traces-run-item ${selectedRunId === run.id ? "traces-run-active" : ""}`}
            >
              <div className="traces-run-top">
                <span className="traces-run-id mono-data">{run.id}</span>
                <span
                  className={`material-symbols-outlined traces-run-status traces-status-${run.status}`}
                >
                  {run.status === "completed"
                    ? "check_circle"
                    : run.status === "running"
                      ? "sync"
                      : "cancel"}
                </span>
              </div>
              <div className="traces-run-model">{run.model}</div>
              <div className="traces-run-meta">
                <span>{run.pack}</span>
                <span>·</span>
                <span>{run.prompt}</span>
              </div>
              <div className="traces-run-time">{run.timestamp}</div>
            </div>
          ))}
          {filterText.trim() && filteredTraces.length === 0 && (
            <div className="traces-filter-empty">
              <span className="material-symbols-outlined">search_off</span>
              <p>No traces match "{filterText}"</p>
            </div>
          )}
        </div>
      </aside>

      {/* Timeline */}
      <section className="traces-timeline">
        {selectedRun ? (
          <>
            <div className="traces-timeline-header">
              <div className="traces-tl-info">
                <h2 className="traces-tl-model">{selectedRun.model}</h2>
                <span className="traces-tl-prompt mono-data">
                  {selectedRun.pack} › {selectedRun.prompt}
                </span>
              </div>
              <div className="traces-tl-actions">
                <button
                  className="traces-tl-export"
                  title={toastMessage === "Copied to clipboard" ? "Copied!" : "Copy trace JSON"}
                  onClick={handleCopyJSON}
                  aria-label="Copy trace JSON"
                >
                  <span className="material-symbols-outlined">
                    {toastMessage === "Copied to clipboard" ? "check" : "content_copy"}
                  </span>
                </button>
                <button
                  className="traces-tl-export"
                  title={isSavingSnapshot ? "Saving…" : "Save snapshot + copy link"}
                  onClick={handleSaveSnapshot}
                  disabled={isSavingSnapshot}
                  aria-label="Save snapshot"
                >
                  <span className="material-symbols-outlined">
                    {isSavingSnapshot ? "sync" : "camera"}
                  </span>
                </button>
                <button
                  className="traces-tl-export"
                  title="Copy shareable snapshot link"
                  onClick={handleCopySnapshotLink}
                  aria-label="Copy snapshot link"
                >
                  <span className="material-symbols-outlined">link</span>
                </button>
                <button
                  className="traces-tl-export"
                  title="Download trace JSON"
                  onClick={handleDownloadTrace}
                  aria-label="Download trace JSON"
                >
                  <span className="material-symbols-outlined">download</span>
                </button>
                <div className="traces-tl-total">
                  <span className="mono-label">Total Time</span>
                  <span className="traces-tl-time">
                    {selectedRun.totalTimeMs}ms
                  </span>
                </div>
              </div>
            </div>

            {/* Success toast */}
            {toastMessage && (
              <div className="traces-toast" role="status" aria-live="polite">
                <span className="material-symbols-outlined traces-toast-icon">check_circle</span>
                <span className="traces-toast-text">{toastMessage}</span>
              </div>
            )}

            <div className="traces-steps" ref={stepsRef}>
              {selectedRun.steps.map((step, i) => {
                const isHovered = hoveredStep === step.id;
                const isLast = i === selectedRun.steps.length - 1;
                const isCurrent = i === currentStepIndex;
                const isFlashing = step.id === flashStepId;
                const isSliding = isCurrent && slideDirection !== null;

                return (
                  <div
                    key={step.id}
                    className={`traces-step ${isHovered ? "traces-step-hovered" : ""} ${isCurrent ? "traces-step-current" : ""} ${isFlashing ? "traces-step-flash" : ""}`}
                    onMouseEnter={() => setHoveredStep(step.id)}
                    onMouseLeave={() => setHoveredStep(null)}
                  >
                    <div className="traces-step-gutter">
                      <div
                        className={`traces-step-dot ${isCurrent && isPlaying ? "traces-step-dot-pulse" : ""}`}
                        style={{
                          background:
                            stepColors[step.type] || "var(--text-tertiary)",
                        }}
                      />
                      {!isLast && <div className="traces-step-line" />}
                    </div>

                    <div className={`traces-step-content ${isSliding ? (slideDirection === "forward" ? "traces-step-slide-right" : "traces-step-slide-left") : ""}`}>
                      <div className="traces-step-header">
                        <span
                          className="material-symbols-outlined traces-step-icon"
                          style={{
                            color:
                              stepColors[step.type] || "var(--text-tertiary)",
                          }}
                        >
                          {stepIcons[step.type] || "circle"}
                        </span>
                        <span
                          className="traces-step-type-chip"
                          style={{
                            background: `${stepColors[step.type]}15`,
                            color: stepColors[step.type],
                            borderColor: `${stepColors[step.type]}30`,
                          }}
                        >
                          {step.type.replace("_", " ")}
                        </span>
                        <span className="traces-step-label">{step.label}</span>
                        <span className="traces-step-time">
                          {step.timing_ms}ms
                        </span>
                      </div>

                      {step.detail && (
                        <p className="traces-step-detail">{step.detail}</p>
                      )}

                      {step.type === "tool_call" && step.tool && isHovered && (
                        <div className="traces-tool-detail animate-entrance">
                          <div className="traces-tool-header">
                            <span className="material-symbols-outlined">
                              terminal
                            </span>
                            <code className="traces-tool-name">
                              {step.tool}
                            </code>
                          </div>
                          {step.input && (
                            <pre className="traces-tool-input">
                              <code>{step.input}</code>
                            </pre>
                          )}
                        </div>
                      )}

                      {step.type === "token" && step.detail && isHovered && (
                        <div className="traces-tool-detail animate-entrance">
                          <div className="traces-tool-header">
                            <span className="material-symbols-outlined">
                              text_fields
                            </span>
                            <code className="traces-tool-name">
                              Token stream
                            </code>
                          </div>
                          <pre className="traces-tool-input">
                            <code>{step.detail}</code>
                          </pre>
                        </div>
                      )}

                      {step.type === "response" && step.detail && isHovered && (
                        <div className="traces-response-preview animate-entrance">
                          {step.detail}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="traces-playback">
              <button
                className="traces-pb-btn"
                title="Previous step (←)"
                onClick={handlePrevious}
                disabled={currentStepIndex === 0}
              >
                <span className="material-symbols-outlined">skip_previous</span>
              </button>
              <button
                className={`traces-pb-btn ${isPlaying ? "traces-pb-pause" : "traces-pb-play"}`}
                title={isPlaying ? "Pause (Space)" : "Play (Space)"}
                onClick={handlePlayPause}
              >
                <span className="material-symbols-outlined">
                  {isPlaying ? "pause" : "play_arrow"}
                </span>
              </button>
              <button
                className="traces-pb-btn"
                title="Next step (→)"
                onClick={handleNext}
                disabled={
                  selectedRun
                    ? currentStepIndex >= selectedRun.steps.length - 1
                    : true
                }
              >
                <span className="material-symbols-outlined">skip_next</span>
              </button>
              <div className="traces-pb-divider" />
              <button
                className="traces-pb-btn"
                title={`Speed ${playbackSpeed}x (1-4)`}
                onClick={handleSpeedCycle}
              >
                <span className="traces-pb-speed">{playbackSpeed}×</span>
              </button>
              <div className={`traces-pb-progress ${isScrubbing ? "traces-pb-scrubbing" : ""}`}>
                <div
                  className="traces-pb-track"
                  ref={trackRef}
                  onMouseDown={handleScrubStart}
                  title="Drag to scrub through steps"
                >
                  <div
                    className="traces-pb-fill"
                    style={{ width: `${progressPct}%` }}
                  />
                  <div
                    className="traces-pb-thumb"
                    style={{ left: `${progressPct}%` }}
                  />
                </div>
                <span className="traces-pb-time mono-data">
                  {selectedRun
                    ? `${currentStepIndex + 1} / ${selectedRun.steps.length} steps`
                    : "0 steps"}
                </span>
              </div>
              <button
                className="traces-pb-help"
                title="Keyboard shortcuts (?)"
                onClick={() => setShowShortcuts((prev) => !prev)}
                aria-label="Keyboard shortcuts"
              >
                ?
              </button>
            </div>
          </>
        ) : (
          <div className="empty-state">
            <span
              className="material-symbols-outlined"
              style={{
                fontSize: 48,
                marginBottom: 16,
                color: "var(--text-tertiary)",
              }}
            >
              account_tree
            </span>
            <p>Select a trace run to view its execution timeline.</p>
          </div>
        )}

        {/* Keyboard Shortcuts Overlay */}
        {showShortcuts && (
          <>
            <div
              className="traces-shortcuts-backdrop"
              onClick={() => setShowShortcuts(false)}
            />
            <div className="traces-shortcuts-overlay">
              <div className="traces-shortcuts-header">
                <span className="traces-shortcuts-title">Keyboard Shortcuts</span>
                <button
                  className="traces-shortcuts-close"
                  onClick={() => setShowShortcuts(false)}
                  title="Close shortcuts"
                >
                  <span className="material-symbols-outlined">close</span>
                </button>
              </div>
              <div className="traces-shortcuts-grid">
                <div className="traces-shortcut-row">
                  <kbd className="traces-kbd">Space</kbd>
                  <span className="traces-shortcut-desc">Play / Pause</span>
                </div>
                <div className="traces-shortcut-row">
                  <kbd className="traces-kbd">←</kbd>
                  <span className="traces-shortcut-desc">Previous step</span>
                </div>
                <div className="traces-shortcut-row">
                  <kbd className="traces-kbd">→</kbd>
                  <span className="traces-shortcut-desc">Next step</span>
                </div>
                <div className="traces-shortcut-row">
                  <div className="traces-kbd-group">
                    <kbd className="traces-kbd">1</kbd>
                    <kbd className="traces-kbd">2</kbd>
                    <kbd className="traces-kbd">4</kbd>
                  </div>
                  <span className="traces-shortcut-desc">Set speed (1× / 2× / 4×)</span>
                </div>
                <div className="traces-shortcut-row">
                  <kbd className="traces-kbd">?</kbd>
                  <span className="traces-shortcut-desc">Toggle this help</span>
                </div>
              </div>
              <div className="traces-shortcuts-footer">
                <span className="traces-shortcuts-hint">
                  Press <kbd className="traces-kbd traces-kbd-inline">Esc</kbd> or click outside to close
                </span>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
