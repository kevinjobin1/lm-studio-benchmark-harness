import React, { useEffect, useState } from "react";

interface HealthResponse {
  status: string;
  uptime: string;
  uptime_seconds: number;
  started_at: string;
  version: string;
}

export function fmtUptime(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function ServerUptimeBadge() {
  const [uptime, setUptime] = useState<string>("");
  const [startedAt, setStartedAt] = useState<string>("");
  const [hwCacheFresh, setHwCacheFresh] = useState<boolean | null>(null);

  useEffect(() => {
    let mounted = true;

    async function poll() {
      try {
        const resp = await fetch("/api/health");
        const data: HealthResponse = await resp.json();
        if (mounted) {
          setUptime(fmtUptime(data.uptime_seconds));
          setStartedAt(new Date(data.started_at).toLocaleString());
        }
      } catch {
        if (mounted) setUptime("");
      }

      // Also check hardware cache freshness from /api/status
      try {
        const statusResp = await fetch("/api/status");
        const statusData = await statusResp.json();
        if (mounted && statusData.hardware_cache) {
          setHwCacheFresh(statusData.hardware_cache.fresh);
        }
      } catch {
        // best-effort
      }
    }

    poll();
    const interval = setInterval(poll, 10000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  if (!uptime) return null;

  return (
    <span
      className="server-uptime-badge"
      title={startedAt ? `Server started ${startedAt}` : ""}
    >
      <span className="material-symbols-outlined uptime-icon">schedule</span>
      <span className="uptime-label">{uptime}</span>
      {hwCacheFresh !== null && (
        <span
          className={`hw-cache-indicator ${hwCacheFresh ? "fresh" : "stale"}`}
          title={hwCacheFresh ? "Hardware cache fresh" : "Hardware cache stale — refreshing"}
        >
          <span className="material-symbols-outlined">
            {hwCacheFresh ? "memory" : "sync"}
          </span>
        </span>
      )}
    </span>
  );
}
