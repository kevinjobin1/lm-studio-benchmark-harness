import React, { useState, useCallback } from "react";
import type { TraceRun, TraceStep } from "../lib/traceTypes";
import { savePlaygroundTrace } from "../lib/playgroundTraces";

// ── Available Skills ──────────────────────────────────────────────

interface SkillInfo {
  name: string;
  description: string;
  inputSchema: Record<string, any>;
  selected: boolean;
}

const AVAILABLE_SKILLS: SkillInfo[] = [
  {
    name: "read_file",
    description: "Read a file within the sandbox and return its contents",
    inputSchema: { path: "string (required)", encoding: "string" },
    selected: true,
  },
  {
    name: "write_file",
    description: "Write content to a file within the sandbox",
    inputSchema: { path: "string (required)", content: "string (required)" },
    selected: true,
  },
  {
    name: "json_parse",
    description: "Parse a JSON string into a structured object",
    inputSchema: { json_string: "string (required)" },
    selected: true,
  },
  {
    name: "diff",
    description: "Compute a unified diff between two text strings",
    inputSchema: { a: "string (required)", b: "string (required)" },
    selected: true,
  },
  {
    name: "nestjs_prisma_service",
    description:
      "Prisma ORM database operations: findUnique, create, update, delete, transactions",
    inputSchema: { operation: "string", model: "string", data: "object" },
    selected: false,
  },
  {
    name: "nestjs_jwt_guard",
    description:
      "JWT authentication guard: validate tokens, extract user, role-based access",
    inputSchema: { token: "string (required)", secret: "string" },
    selected: false,
  },
  {
    name: "nestjs_cache_interceptor",
    description: "Cache interceptor: set TTL, invalidate, cache-key strategies",
    inputSchema: { key: "string (required)", ttl: "number" },
    selected: false,
  },
  {
    name: "nestjs_validation_pipe",
    description:
      "Validation pipe: validate DTOs, transform types, sanitize input",
    inputSchema: { schema: "object (required)", data: "object (required)" },
    selected: false,
  },
];

// ── Task Templates ────────────────────────────────────────────────

const TASK_TEMPLATES = [
  {
    label: "Read & Fix Bug",
    template:
      "Read the file src/buggy.ts, fix the race condition bug, write the fix, and show the diff of changes.",
  },
  {
    label: "JSON Transform",
    template:
      "Read config.json, parse its JSON content, transform the structure to add versioning, and write the result to config_v2.json.",
  },
  {
    label: "Code Review Diff",
    template:
      "Read both src/original.ts and src/modified.ts, compute their diff, and verify the changes are correct.",
  },
  {
    label: "Auth Guard Debug",
    template:
      "Read src/auth/jwt-auth.guard.ts, identify why token validation is broken, write the fix with proper super.canActivate() call, and show the diff.",
  },
  {
    label: "Cache Race Fix",
    template:
      "Read src/common/cache.service.ts, fix the cache stampede problem using Promise deduplication, write the fix, and show the diff.",
  },
];

// ── Components ────────────────────────────────────────────────────

interface PlaygroundResult {
  actions: Array<{ skill: string; input: Record<string, any> }>;
  scores?: {
    validity: number;
    planning: number;
    correctness: number;
    constraints: number;
    overall: number;
  };
  errors?: string[];
  rawResponse?: string;
}

export default function PlaygroundApp() {
  const [skills, setSkills] = useState<SkillInfo[]>(
    AVAILABLE_SKILLS.map((s) => ({ ...s })),
  );
  const [prompt, setPrompt] = useState("");
  const [results, setResults] = useState<PlaygroundResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"custom" | "template">("template");
  const [selectedTemplate, setSelectedTemplate] = useState(0);
  const [tab, setTab] = useState<"actions" | "scores" | "raw">("actions");
  const [capturedTraceId, setCapturedTraceId] = useState<string | null>(null);

  const toggleSkill = useCallback((index: number) => {
    setSkills((prev) =>
      prev.map((s, i) => (i === index ? { ...s, selected: !s.selected } : s)),
    );
  }, []);

  const selectedSkills = skills.filter((s) => s.selected).map((s) => s.name);

  const applyTemplate = useCallback((index: number) => {
    setSelectedTemplate(index);
    setPrompt(TASK_TEMPLATES[index].template);
    setMode("template");
  }, []);

  const runPlayground = useCallback(async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setResults(null);

    // Simulate model response + evaluation
    await new Promise((r) => setTimeout(r, 1200));

    // Build mock response based on selected skills
    const actions: Array<{ skill: string; input: Record<string, any> }> = [];

    if (selectedSkills.includes("read_file")) {
      actions.push({ skill: "read_file", input: { path: "src/index.ts" } });
    }
    if (selectedSkills.includes("json_parse")) {
      actions.push({
        skill: "json_parse",
        input: { json_string: '{"version": 1}' },
      });
    }
    if (selectedSkills.includes("write_file")) {
      actions.push({
        skill: "write_file",
        input: { path: "src/index.ts", content: "// fixed" },
      });
    }
    if (selectedSkills.includes("diff")) {
      actions.push({ skill: "diff", input: { a: "original", b: "modified" } });
    }
    if (
      selectedSkills.includes("nestjs_jwt_guard") &&
      prompt.includes("auth")
    ) {
      actions.push({ skill: "nestjs_jwt_guard", input: { token: "eyJ..." } });
    }
    if (
      selectedSkills.includes("nestjs_cache_interceptor") &&
      prompt.includes("cache")
    ) {
      actions.push({
        skill: "nestjs_cache_interceptor",
        input: { key: "user:123", ttl: 300 },
      });
    }

    // Compute mock scores
    const totalSkills = selectedSkills.length;
    const usedCount = new Set(actions.map((a) => a.skill)).size;
    const hallucinated = actions.filter(
      (a) => !selectedSkills.includes(a.skill),
    ).length;
    const valid = actions.length > 0 && hallucinated === 0;

    const validity = actions.length > 0 ? 1.0 : 0.0;
    const planning = usedCount >= Math.ceil(totalSkills * 0.5) ? 0.8 : 0.4;
    const correctness = valid ? 1.0 : 0.5;
    const constraints = hallucinated === 0 ? 1.0 : 0.7;
    const overall =
      validity * 0.25 + planning * 0.25 + correctness * 0.3 + constraints * 0.2;

    const mockResult: PlaygroundResult = {
      actions,
      scores: { validity, planning, correctness, constraints, overall },
      errors: hallucinated > 0 ? [`Hallucinated skill: unknown_tool`] : [],
      rawResponse: JSON.stringify({ actions }, null, 2),
    };

    setResults(mockResult);
    setLoading(false);

    // ── V2: Build and capture an execution trace ────────────────
    const traceId = `pg-${Date.now()}`;
    const now = new Date();
    const traceSteps: TraceStep[] = [
      {
        id: `${traceId}-s0`,
        type: "system",
        label: "System Instruction",
        detail: `Playground mode. Skills enabled: ${selectedSkills.join(", ") || "none"}.`,
        timing_ms: 0,
        status: "success",
      },
      {
        id: `${traceId}-s1`,
        type: "prompt",
        label: "Prompt Received",
        detail: prompt.slice(0, 200),
        timing_ms: 5,
        status: "success",
      },
      ...actions.map((action, i) => ({
        id: `${traceId}-tool${i}`,
        type: "tool_call" as const,
        label: `Calling: ${action.skill}`,
        tool: action.skill,
        input: JSON.stringify(action.input),
        timing_ms: 50 + i * 30,
        status: "success" as const,
      })),
      {
        id: `${traceId}-reasoning`,
        type: "reasoning",
        label: "Analyzing results",
        detail: `Used ${actions.length} skill${actions.length !== 1 ? "s" : ""} out of ${selectedSkills.length} selected. Hallucinations: ${hallucinated}.`,
        timing_ms: 100,
        status: "success",
      },
      {
        id: `${traceId}-response`,
        type: "response",
        label: "Evaluation Complete",
        detail: `Overall score: ${(overall * 100).toFixed(0)}%. Actions: ${actions.length}. Errors: ${hallucinated > 0 ? 1 : 0}.`,
        timing_ms: 150,
        status: hallucinated > 0 ? "failure" : "success",
      },
    ];

    const traceRun: TraceRun = {
      id: traceId,
      model: "Playground (simulated)",
      pack: selectedSkills.join(", ").slice(0, 30) || "mcp-playground",
      prompt: prompt.slice(0, 100),
      timestamp: now.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }),
      totalTimeMs: traceSteps.reduce((s, st) => s + st.timing_ms, 0),
      status: hallucinated > 0 ? "failed" : "completed",
      steps: traceSteps,
    };

    savePlaygroundTrace(traceRun);
    setCapturedTraceId(traceId);
  }, [prompt, selectedSkills]);

  return (
    <div className="playground-app">
      {/* Skill Selector */}
      <div className="skills-grid">
        {skills.map((skill, i) => (
          <button
            key={skill.name}
            className={`skill-chip ${skill.selected ? "selected" : ""}`}
            onClick={() => toggleSkill(i)}
            title={skill.description}
          >
            <span className="skill-name">{skill.name}</span>
            <span className="skill-desc">{skill.description}</span>
          </button>
        ))}
      </div>

      {/* Task Input */}
      <div className="task-section">
        <div className="task-tabs">
          <button
            className={`tab-btn ${mode === "template" ? "active" : ""}`}
            onClick={() => setMode("template")}
          >
            Templates
          </button>
          <button
            className={`tab-btn ${mode === "custom" ? "active" : ""}`}
            onClick={() => setMode("custom")}
          >
            Custom Task
          </button>
        </div>

        {mode === "template" && (
          <div className="template-grid">
            {TASK_TEMPLATES.map((t, i) => (
              <button
                key={i}
                className={`template-card ${selectedTemplate === i ? "active" : ""}`}
                onClick={() => applyTemplate(i)}
              >
                <span className="template-label">{t.label}</span>
                <span className="template-preview">
                  {t.template.substring(0, 80)}...
                </span>
              </button>
            ))}
          </div>
        )}

        <textarea
          id="playground-prompt"
          className="prompt-input"
          value={prompt}
          onChange={(e) => {
            setPrompt(e.target.value);
            setMode("custom");
          }}
          placeholder="Describe the task for the model using ONLY the selected skills above..."
          rows={4}
        />

        <div className="action-bar">
          <span className="skills-count">
            {selectedSkills.length} skill
            {selectedSkills.length !== 1 ? "s" : ""} selected
          </span>
          <button
            className="run-btn"
            onClick={runPlayground}
            disabled={loading || !prompt.trim()}
          >
            {loading ? (
              <span className="spinner" />
            ) : (
              "▶  Run Agentic Evaluation"
            )}
          </button>
        </div>
      </div>

      {/* Results */}
      {results && (
        <div className="results-section">
          <div className="pg-results-header">
            <h3>📊 Evaluation Results</h3>
            {capturedTraceId && (
              <a
                href={`/traces?trace_id=${encodeURIComponent(capturedTraceId)}`}
                className="pg-view-trace-btn"
              >
                <span className="material-symbols-outlined">replay</span>
                View Trace
              </a>
            )}
          </div>

          <div className="results-tabs">
            <button
              className={`tab-btn ${tab === "actions" ? "active" : ""}`}
              onClick={() => setTab("actions")}
            >
              Actions ({results.actions.length})
            </button>
            <button
              className={`tab-btn ${tab === "scores" ? "active" : ""}`}
              onClick={() => setTab("scores")}
            >
              Scores
            </button>
            <button
              className={`tab-btn ${tab === "raw" ? "active" : ""}`}
              onClick={() => setTab("raw")}
            >
              Raw JSON
            </button>
          </div>

          {tab === "actions" && (
            <div className="actions-list">
              {results.actions.map((action, i) => (
                <div key={i} className="action-card">
                  <div className="action-header">
                    <span className="action-order">{i + 1}</span>
                    <span className="action-skill">{action.skill}</span>
                    {!selectedSkills.includes(action.skill) && (
                      <span className="action-warning">⚠ hallucinated</span>
                    )}
                  </div>
                  <pre className="action-input">
                    {JSON.stringify(action.input, null, 2)}
                  </pre>
                </div>
              ))}
              {results.actions.length === 0 && (
                <p className="empty-state">
                  No actions returned. Model may have failed to produce valid
                  JSON.
                </p>
              )}
            </div>
          )}

          {tab === "scores" && results.scores && (
            <div className="scores-grid">
              <div className="score-card">
                <div className="score-label">Overall</div>
                <div
                  className={`score-value ${results.scores.overall >= 0.8 ? "good" : results.scores.overall >= 0.5 ? "ok" : "bad"}`}
                >
                  {(results.scores.overall * 100).toFixed(0)}%
                </div>
              </div>
              <div className="score-card">
                <div className="score-label">Validity</div>
                <div className="score-sub">JSON + schema</div>
                <div className="score-bar">
                  <div
                    className="bar-fill"
                    style={{ width: `${results.scores.validity * 100}%` }}
                  />
                </div>
                <span className="score-pct">
                  {(results.scores.validity * 100).toFixed(0)}%
                </span>
              </div>
              <div className="score-card">
                <div className="score-label">Planning</div>
                <div className="score-sub">Sequence correctness</div>
                <div className="score-bar">
                  <div
                    className="bar-fill"
                    style={{ width: `${results.scores.planning * 100}%` }}
                  />
                </div>
                <span className="score-pct">
                  {(results.scores.planning * 100).toFixed(0)}%
                </span>
              </div>
              <div className="score-card">
                <div className="score-label">Skill Correctness</div>
                <div className="score-sub">Tool + params</div>
                <div className="score-bar">
                  <div
                    className="bar-fill"
                    style={{ width: `${results.scores.correctness * 100}%` }}
                  />
                </div>
                <span className="score-pct">
                  {(results.scores.correctness * 100).toFixed(0)}%
                </span>
              </div>
              <div className="score-card">
                <div className="score-label">Constraint Adherence</div>
                <div className="score-sub">No hallucinations</div>
                <div className="score-bar">
                  <div
                    className="bar-fill"
                    style={{ width: `${results.scores.constraints * 100}%` }}
                  />
                </div>
                <span className="score-pct">
                  {(results.scores.constraints * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          )}

          {tab === "raw" && (
            <pre className="raw-output">
              {results.rawResponse || "No raw response available"}
            </pre>
          )}

          {results.errors && results.errors.length > 0 && (
            <div className="errors-list">
              <h4>⚠ Errors</h4>
              {results.errors.map((err, i) => (
                <div key={i} className="error-item">
                  {err}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
