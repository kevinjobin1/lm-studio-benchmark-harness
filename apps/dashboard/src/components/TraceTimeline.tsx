import React, { useState } from "react";
import type { BenchmarkResult } from "../lib/loadResults";

// ── Trace Step ─────────────────────────────────────────────────────

interface TraceStep {
  id: string;
  type: "tool_call" | "reasoning" | "response" | "system" | "error";
  label: string;
  detail?: string;
  timing_ms: number;
  tool?: string;
  input?: string;
  output?: string;
  status: "success" | "failure" | "pending";
}

interface TraceRun {
  id: string;
  model: string;
  pack: string;
  prompt: string;
  timestamp: string;
  totalTimeMs: number;
  status: "completed" | "failed" | "running";
  steps: TraceStep[];
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

// ── Props ──────────────────────────────────────────────────────────

interface TraceTimelineProps {
  results?: BenchmarkResult[];
}

// ── Icon / Color mappings ─────────────────────────────────────────

const stepIcons: Record<string, string> = {
  system: "settings",
  tool_call: "build",
  reasoning: "psychology",
  response: "chat",
  error: "error",
};

const stepColors: Record<string, string> = {
  system: "var(--text-tertiary)",
  tool_call: "var(--brand-primary)",
  reasoning: "var(--warning)",
  response: "var(--success)",
  error: "var(--error)",
};

// ── Component ─────────────────────────────────────────────────────

export default function TraceTimeline({ results }: TraceTimelineProps) {
  const tracesFromData =
    results && results.length > 0 ? buildTraceRuns(results) : null;

  const [traces] = useState<TraceRun[]>(
    tracesFromData && tracesFromData.length > 0
      ? tracesFromData
      : generateDemoTraces(),
  );
  const [selectedRunId, setSelectedRunId] = useState(traces[0]?.id ?? null);
  const [hoveredStep, setHoveredStep] = useState<string | null>(null);

  const selectedRun = traces.find((t) => t.id === selectedRunId) ?? null;

  return (
    <div className="traces-layout">
      {/* Run List Sidebar */}
      <aside className="traces-sidebar">
        <div className="traces-sidebar-header">
          <span className="mono-label">Recent Runs</span>
          <span className="material-symbols-outlined traces-filter-icon">
            filter_list
          </span>
        </div>
        <div className="traces-run-list">
          {traces.map((run) => (
            <div
              key={run.id}
              onClick={() => setSelectedRunId(run.id)}
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
              <div className="traces-tl-total">
                <span className="mono-label">Total Time</span>
                <span className="traces-tl-time">
                  {selectedRun.totalTimeMs}ms
                </span>
              </div>
            </div>

            <div className="traces-steps">
              {selectedRun.steps.map((step, i) => {
                const isHovered = hoveredStep === step.id;
                const isLast = i === selectedRun.steps.length - 1;

                return (
                  <div
                    key={step.id}
                    className={`traces-step ${isHovered ? "traces-step-hovered" : ""}`}
                    onMouseEnter={() => setHoveredStep(step.id)}
                    onMouseLeave={() => setHoveredStep(null)}
                  >
                    <div className="traces-step-gutter">
                      <div
                        className="traces-step-dot"
                        style={{
                          background:
                            stepColors[step.type] || "var(--text-tertiary)",
                        }}
                      />
                      {!isLast && <div className="traces-step-line" />}
                    </div>

                    <div className="traces-step-content">
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
              <button className="traces-pb-btn" title="Previous step">
                <span className="material-symbols-outlined">skip_previous</span>
              </button>
              <button className="traces-pb-btn traces-pb-play" title="Play">
                <span className="material-symbols-outlined">play_arrow</span>
              </button>
              <button className="traces-pb-btn" title="Next step">
                <span className="material-symbols-outlined">skip_next</span>
              </button>
              <div className="traces-pb-divider" />
              <button className="traces-pb-btn" title="Speed 1x">
                <span className="traces-pb-speed">1×</span>
              </button>
              <div className="traces-pb-progress">
                <div className="traces-pb-track">
                  <div className="traces-pb-fill" style={{ width: "60%" }} />
                </div>
                <span className="traces-pb-time mono-data">
                  {selectedRun.steps.length} steps
                </span>
              </div>
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
      </section>
    </div>
  );
}
