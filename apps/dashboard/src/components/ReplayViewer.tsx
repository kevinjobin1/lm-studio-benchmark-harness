import React, { useState, useEffect, useRef, useCallback } from "react";
import { loadReplay, loadReplayManifest } from "../lib/loadReplays";
import type { ReplayData, ReplayEvent, ReplayIndexEntry } from "../lib/loadReplays";

// ── Constants ─────────────────────────────────────────────────────

const SPEEDS = [0.5, 1, 2, 4] as const;
const DEFAULT_STEP_MS = 800;
const MAX_VISIBLE_LIST_EVENTS = 5;

// ── Helpers ───────────────────────────────────────────────────────

function safeStr(v: unknown, fallback: string = ""): string {
  return typeof v === "string" ? v : fallback;
}

function safeNum(v: unknown, fallback: number = 0): number {
  return typeof v === "number" ? v : fallback;
}

function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms)}ms`;
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    // Use UTC timezone so SSR (Node.js) and client hydration (browser)
    // produce the same timestamp string — preventing React hydration errors.
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit", timeZone: "UTC" });
  } catch {
    return iso;
  }
}

// ── Event type metadata ───────────────────────────────────────────

interface EventMeta {
  icon: string;
  color: string;
  label: string;
}

const EVENT_META: Record<string, EventMeta> = {
  RunLifecycleEvent: { icon: "cycle", color: "var(--brand-primary)", label: "Run Lifecycle" },
  TokenGeneratedEvent: { icon: "text_fields", color: "var(--success)", label: "Token Generated" },
  CompletionEvent: { icon: "check_circle", color: "var(--success)", label: "Completion" },
  MetricEvent: { icon: "bar_chart", color: "var(--warning)", label: "Metric" },
  ErrorEvent: { icon: "error", color: "var(--error)", label: "Error" },
  ToolCallEvent: { icon: "build", color: "var(--code-keyword)", label: "Tool Call" },
};

function getEventMeta(eventType: string): EventMeta {
  return EVENT_META[eventType] || { icon: "circle", color: "var(--text-tertiary)", label: eventType };
}

function formatEventDetail(event: ReplayEvent): React.ReactNode {
  const type = event._event_type;

  if (type === "TokenGeneratedEvent") {
    const token = safeStr(event.token);
    return <span className="rpv-detail-token">{token}</span>;
  }

  if (type === "CompletionEvent") {
    const tokens = safeNum(event.tokens_used);
    const latency = safeNum(event.latency_ms);
    const tps = safeNum(event.tokens_per_second);
    const success = event.success !== false;
    return (
      <span className="rpv-detail-mono">
        {success ? "✓" : "✗"} {tokens} tok · {formatMs(latency)} · {tps.toFixed(1)} tok/s
      </span>
    );
  }

  if (type === "MetricEvent") {
    const name = safeStr(event.name);
    const value = safeNum(event.value);
    return (
      <span className="rpv-detail-mono">
        {name}: <strong>{(value * 100).toFixed(1)}%</strong>
      </span>
    );
  }

  if (type === "ErrorEvent") {
    const msg = safeStr(event.message);
    const exc = safeStr(event.exception);
    return (
      <span className="rpv-detail-mono rpv-detail-error">
        {exc ? `${exc}: ` : ""}{msg}
      </span>
    );
  }

  if (type === "RunLifecycleEvent") {
    const status = safeStr(event.status);
    const duration = safeNum(event.duration_ms);
    const workload = safeStr(event.workload);
    return (
      <span className="rpv-detail-mono">
        {status}{workload ? ` — ${workload}` : ""}{duration > 0 ? ` (${formatMs(duration)})` : ""}
      </span>
    );
  }

  return null;
}

// ── Component ─────────────────────────────────────────────────────

interface ReplayViewerProps {
  /** Optional run_id to auto-select on mount (from ?run_id= URL param). */
  initialRunId?: string;
  /** Optional model name to filter sidebar (from ?model= URL param). */
  initialModel?: string;
}

export default function ReplayViewer({ initialRunId, initialModel }: ReplayViewerProps = {}) {
  // ── State ─────────────────────────────────────────────────────
  const [replays, setReplays] = useState<ReplayIndexEntry[]>([]);
  const [selectedReplay, setSelectedReplay] = useState<ReplayData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Playback state
  const [currentEventIndex, setCurrentEventIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isScrubbing, setIsScrubbing] = useState(false);
  const [hoveredEventId, setHoveredEventId] = useState<string | null>(null);

  // Refs
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const currentIndexRef = useRef(currentEventIndex);
  const wasPlayingBeforeScrub = useRef(false);
  const trackRef = useRef<HTMLDivElement | null>(null);
  const eventListRef = useRef<HTMLDivElement | null>(null);

  // Keep ref in sync
  currentIndexRef.current = currentEventIndex;

  // ── Load selected replay data ───────────────────────────────
  const handleSelectReplay = useCallback(async (entry: ReplayIndexEntry) => {
    setIsPlaying(false);
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setCurrentEventIndex(0);
    setLoadingDetail(true);
    setError(null);

    try {
      const data = await loadReplay(entry.run_id);
      if (data) {
        setSelectedReplay(data);
      } else {
        setError(`Replay "${entry.run_id}" not found`);
      }
    } catch {
      setError("Failed to load replay data");
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  // ── Load replay manifest on mount ────────────────────────────
  useEffect(() => {
    let mounted = true;
    setLoading(true);
    loadReplayManifest()
      .then((manifest) => {
        if (!mounted) return;
        let filtered = manifest.replays;

        // Filter by model if initialModel is specified
        if (initialModel) {
          const model = initialModel.toLowerCase();
          filtered = filtered.filter((r) =>
            r.model.toLowerCase().includes(model),
          );
        }

        setReplays(filtered);
        setLoading(false);

        // Auto-select a specific replay if initialRunId is specified
        if (initialRunId) {
          const match = filtered.find((r) => r.run_id === initialRunId);
          if (match) {
            handleSelectReplay(match);
          } else {
            setError(`Replay "${initialRunId}" not found in manifest`);
          }
        }
      })
      .catch(() => {
        if (!mounted) return;
        setError("Failed to load replay list");
        setLoading(false);
      });
    return () => { mounted = false; };
  }, [initialRunId, initialModel, handleSelectReplay]);

  // ── Auto-playback engine ────────────────────────────────────
  useEffect(() => {
    if (isPlaying && selectedReplay && selectedReplay.events.length > 0) {
      const baseInterval = DEFAULT_STEP_MS;
      const intervalMs = baseInterval / playbackSpeed;

      intervalRef.current = setInterval(() => {
        const idx = currentIndexRef.current;
        const events = selectedReplay.events;
        if (idx >= events.length - 1) {
          setIsPlaying(false);
          setCurrentEventIndex(0);
        } else {
          setCurrentEventIndex(idx + 1);
        }
      }, intervalMs);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isPlaying, playbackSpeed, selectedReplay]);

  // ── Playback handlers ───────────────────────────────────────
  const handlePrevious = useCallback(() => {
    if (!selectedReplay || selectedReplay.events.length === 0) return;
    setCurrentEventIndex((prev) => Math.max(0, prev - 1));
  }, [selectedReplay]);

  const handleNext = useCallback(() => {
    if (!selectedReplay || selectedReplay.events.length === 0) return;
    setCurrentEventIndex((prev) =>
      Math.min(selectedReplay.events.length - 1, prev + 1),
    );
  }, [selectedReplay]);

  const handlePlayPause = useCallback(() => {
    if (!selectedReplay || selectedReplay.events.length === 0) return;
    if (currentEventIndex >= selectedReplay.events.length - 1 && !isPlaying) {
      setCurrentEventIndex(0);
    }
    setIsPlaying((prev) => !prev);
  }, [selectedReplay, currentEventIndex, isPlaying]);

  const handleSpeedCycle = useCallback(() => {
    setPlaybackSpeed((prev) => {
      const idx = SPEEDS.indexOf(prev as typeof SPEEDS[number]);
      return SPEEDS[(idx + 1) % SPEEDS.length];
    });
  }, []);

  // ── Scrubbing (drag progress bar) ───────────────────────────
  const eventIndexFromTrack = useCallback(
    (clientX: number) => {
      if (!trackRef.current || !selectedReplay || selectedReplay.events.length === 0) return 0;
      const rect = trackRef.current.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      return Math.min(selectedReplay.events.length - 1, Math.floor(ratio * selectedReplay.events.length));
    },
    [selectedReplay],
  );

  const handleScrubStart = useCallback(
    (e: React.MouseEvent) => {
      wasPlayingBeforeScrub.current = isPlaying;
      if (isPlaying) setIsPlaying(false);
      setIsScrubbing(true);
      setCurrentEventIndex(eventIndexFromTrack(e.clientX));
    },
    [isPlaying, eventIndexFromTrack],
  );

  useEffect(() => {
    if (!isScrubbing) return;
    const handleMove = (e: MouseEvent) => {
      setCurrentEventIndex(eventIndexFromTrack(e.clientX));
    };
    const handleUp = () => {
      setIsScrubbing(false);
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
  }, [isScrubbing, eventIndexFromTrack]);

  // ── Keyboard shortcuts ──────────────────────────────────────
  const handlePreviousRef = useRef(handlePrevious);
  handlePreviousRef.current = handlePrevious;
  const handleNextRef = useRef(handleNext);
  handleNextRef.current = handleNext;
  const handlePlayPauseRef = useRef(handlePlayPause);
  handlePlayPauseRef.current = handlePlayPause;

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
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
        case "1": setPlaybackSpeed(1); break;
        case "2": setPlaybackSpeed(2); break;
        case "4": setPlaybackSpeed(4); break;
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // ── Auto-scroll to keep current event visible ───────────────
  useEffect(() => {
    if (!eventListRef.current || !selectedReplay) return;
    const el = eventListRef.current.querySelector(".rpv-event-current") as HTMLElement | null;
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [currentEventIndex, selectedReplay]);

  // ── Derived state ───────────────────────────────────────────
  const currentEvent = selectedReplay?.events[currentEventIndex] ?? null;
  const progressPct = selectedReplay && selectedReplay.events.length > 0
    ? ((currentEventIndex + 1) / selectedReplay.events.length) * 100
    : 0;

  // ── Render ───────────────────────────────────────────────────
  return (
    <div className="rpv-layout">
      {/* Left sidebar: replay list */}
      <aside className="rpv-sidebar">
        <div className="rpv-sidebar-header">
          <span className="mono-label">Replay Sessions</span>
          <span className="rpv-sidebar-count">{replays.length}</span>
        </div>

        <div className="rpv-sidebar-list">
          {loading && (
            <div className="rpv-sidebar-loading">
              <span className="material-symbols-outlined rpv-spin">sync</span>
              <span>Loading replays…</span>
            </div>
          )}

          {!loading && replays.length === 0 && (
            <div className="rpv-sidebar-empty">
              <span className="material-symbols-outlined">history</span>
              <p>No replay sessions found.</p>
              <p className="rpv-sidebar-hint">
                Run a benchmark with <code>--sse-port 9090</code> to generate replay data.
              </p>
            </div>
          )}

          {replays.map((entry) => (
            <div
              key={entry.run_id}
              className={`rpv-sidebar-item ${selectedReplay?.run_id === entry.run_id ? "rpv-sidebar-active" : ""}`}
              onClick={() => handleSelectReplay(entry)}
            >
              <div className="rpv-sidebar-item-top">
                <span className="rpv-sidebar-model">{entry.model}</span>
                <span className="rpv-sidebar-events mono-data">{entry.event_count} events</span>
              </div>
              <div className="rpv-sidebar-meta">
                {entry.workload && <span className="rpv-sidebar-workload">{entry.workload}</span>}
                <span className="rpv-sidebar-time">{formatTimestamp(entry.started_at)}</span>
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* Main timeline area */}
      <section className="rpv-main">
        {error && (
          <div className="rpv-error-banner">
            <span className="material-symbols-outlined">error</span>
            <span>{error}</span>
            <button className="rpv-error-dismiss" onClick={() => setError(null)} aria-label="Dismiss error">
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        )}

        {loadingDetail && (
          <div className="rpv-loading-detail">
            <span className="material-symbols-outlined rpv-spin">sync</span>
            <span>Loading replay…</span>
          </div>
        )}

        {!selectedReplay && !loadingDetail && !error && (
          <div className="rpv-empty">
            <span className="material-symbols-outlined rpv-empty-icon">history</span>
            <p>Select a replay session from the sidebar to view its event timeline.</p>
          </div>
        )}

        {selectedReplay && !loadingDetail && (
          <>
            {/* Header */}
            <div className="rpv-header">
              <div className="rpv-header-left">
                <h2 className="rpv-model-name">{selectedReplay.model}</h2>
                <div className="rpv-header-meta">
                  <span className="rpv-meta-chip">{selectedReplay.workload || "benchmark"}</span>
                  <span className="rpv-meta-divider">·</span>
                  <span className="mono-data">{selectedReplay.event_count} events</span>
                  <span className="rpv-meta-divider">·</span>
                  <span className="mono-data">{selectedReplay.run_id}</span>
                </div>
              </div>
              <div className="rpv-header-right">
                <span className="mono-label">Started</span>
                <span className="rpv-header-time">{formatTimestamp(selectedReplay.started_at)}</span>
              </div>
            </div>

            {/* Event timeline */}
            <div className="rpv-event-list" ref={eventListRef}>
              {selectedReplay.events.map((event, i) => {
                const meta = getEventMeta(event._event_type);
                const isCurrent = i === currentEventIndex;
                const isHovered = hoveredEventId === `${i}`;
                const isLast = i === selectedReplay.events.length - 1;

                return (
                  <div
                    key={`${selectedReplay.run_id}-${i}`}
                    className={`rpv-event ${isCurrent ? "rpv-event-current" : ""} ${isHovered ? "rpv-event-hovered" : ""}`}
                    onMouseEnter={() => setHoveredEventId(`${i}`)}
                    onMouseLeave={() => setHoveredEventId(null)}
                    onClick={() => {
                      setIsPlaying(false);
                      setCurrentEventIndex(i);
                    }}
                  >
                    {/* Gutter with dot and line */}
                    <div className="rpv-event-gutter">
                      <div
                        className={`rpv-event-dot ${isCurrent && isPlaying ? "rpv-dot-pulse" : ""}`}
                        style={{ background: meta.color }}
                      />
                      {!isLast && <div className="rpv-event-line" />}
                    </div>

                    {/* Event card */}
                    <div className="rpv-event-card">
                      <div className="rpv-event-header">
                        <span className="rpv-event-type-chip" style={{ background: `${meta.color}15`, color: meta.color, borderColor: `${meta.color}30` }}>
                          <span className="material-symbols-outlined rpv-event-chip-icon">{meta.icon}</span>
                          {meta.label}
                        </span>
                        <span className="rpv-event-index mono-data">#{i + 1}</span>
                      </div>
                      <div className="rpv-event-detail">
                        {formatEventDetail(event)}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Playback controls */}
            <div className="rpv-playback">
              <button
                className="rpv-pb-btn"
                title="Previous event (←)"
                onClick={handlePrevious}
                disabled={currentEventIndex === 0}
                aria-label="Previous event"
              >
                <span className="material-symbols-outlined">skip_previous</span>
              </button>
              <button
                className={`rpv-pb-btn ${isPlaying ? "rpv-pb-pause" : "rpv-pb-play"}`}
                title={isPlaying ? "Pause (Space)" : "Play (Space)"}
                onClick={handlePlayPause}
                aria-label={isPlaying ? "Pause" : "Play"}
              >
                <span className="material-symbols-outlined">
                  {isPlaying ? "pause" : "play_arrow"}
                </span>
              </button>
              <button
                className="rpv-pb-btn"
                title="Next event (→)"
                onClick={handleNext}
                disabled={currentEventIndex >= selectedReplay.events.length - 1}
                aria-label="Next event"
              >
                <span className="material-symbols-outlined">skip_next</span>
              </button>
              <div className="rpv-pb-divider" />
              <button
                className="rpv-pb-btn"
                title={`Speed ${playbackSpeed}× (1-4)`}
                onClick={handleSpeedCycle}
                aria-label="Cycle playback speed"
              >
                <span className="rpv-pb-speed">{playbackSpeed}×</span>
              </button>
              <div className={`rpv-pb-progress ${isScrubbing ? "rpv-pb-scrubbing" : ""}`}>
                <div className="rpv-pb-track" ref={trackRef} onMouseDown={handleScrubStart} title="Drag to scrub through events">
                  <div className="rpv-pb-fill" style={{ width: `${progressPct}%` }} />
                  <div className="rpv-pb-thumb" style={{ left: `${progressPct}%` }} />
                </div>
                <span className="rpv-pb-label mono-data">
                  {currentEventIndex + 1} / {selectedReplay.events.length} events
                </span>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
