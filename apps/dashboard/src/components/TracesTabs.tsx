import React, { useState } from "react";
import TraceTimeline from "./TraceTimeline";
import ReplayViewer from "./ReplayViewer";
import type { TraceRun } from "../lib/traceTypes";
import type { BenchmarkResult } from "../lib/loadResults";

// ── Props ──────────────────────────────────────────────────────────

interface TracesTabsProps {
  /** Real captured traces for the timeline. */
  traces?: TraceRun[];
  /** Benchmark results (fallback for synthesized traces). */
  results?: BenchmarkResult[];
  /** Pre-select a specific trace by ID (from ?trace_id= query param). */
  initialTraceId?: string;
}

type TabId = "traces" | "replays";

// ── Tab config ─────────────────────────────────────────────────────

interface TabConfig {
  id: TabId;
  label: string;
  icon: string;
  description: string;
}

const TABS: TabConfig[] = [
  {
    id: "traces",
    label: "Execution Traces",
    icon: "account_tree",
    description: "Step-by-step tool calls, reasoning chains, and response generation.",
  },
  {
    id: "replays",
    label: "Replay Sessions",
    icon: "history",
    description: "Recorded event streams from past benchmark and workload runs.",
  },
];

// ── Component ─────────────────────────────────────────────────────

export default function TracesTabs({ traces, results, initialTraceId }: TracesTabsProps) {
  const [activeTab, setActiveTab] = useState<TabId>("traces");

  return (
    <div className="traces-tabs-layout">
      {/* Tab bar */}
      <div className="traces-tabs-bar" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`traces-tab-btn ${activeTab === tab.id ? "traces-tab-active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
            aria-selected={activeTab === tab.id}
            role="tab"
          >
            <span className="material-symbols-outlined traces-tab-icon" aria-hidden="true">{tab.icon}</span>
            <div className="traces-tab-info">
              <span className="traces-tab-label">{tab.label}</span>
              <span className="traces-tab-desc">{tab.description}</span>
            </div>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="traces-tab-content" role="tabpanel">
        {activeTab === "traces" && (
          <TraceTimeline
            traces={traces}
            results={results}
            initialTraceId={initialTraceId}
          />
        )}
        {activeTab === "replays" && (
          <ReplayViewer />
        )}
      </div>
    </div>
  );
}
