import React, { useEffect, useState } from "react";

interface StatusResponse {
  connected: boolean;
  models: string[];
  provider: string;
  hardware?: {
    cpu?: { model?: string };
    memory?: { ram_total_mb?: number };
    gpu?: { model?: string };
    os?: { name?: string; version?: string };
    apple_silicon?: boolean;
  };
}

function fmtHardware(hw: StatusResponse["hardware"]): string {
  if (!hw) return "";
  const parts: string[] = [];
  if (hw.cpu?.model) {
    const short = hw.cpu.model.replace(/Apple /, "").split(" ").slice(0, 3).join(" ");
    parts.push(short);
  }
  if (hw.memory?.ram_total_mb) {
    parts.push(`${(hw.memory.ram_total_mb / 1024).toFixed(0)}GB`);
  }
  if (hw.os?.name) {
    parts.push(`${hw.os.name} ${hw.os.version || ""}`);
  }
  return parts.join(" • ");
}

export default function ConnectionStatusBadge() {
  const [connected, setConnected] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [provider, setProvider] = useState("");
  const [hardware, setHardware] = useState<StatusResponse["hardware"]>();

  useEffect(() => {
    let mounted = true;

    async function poll() {
      try {
        const resp = await fetch("/api/status");
        const data: StatusResponse = await resp.json();
        if (mounted) {
          setConnected(data.connected);
          setModels(data.models || []);
          setProvider(data.provider || "");
          setHardware(data.hardware);
        }
      } catch {
        if (mounted) {
          setConnected(false);
          setModels([]);
          setProvider("");
        }
      }
    }

    poll();
    const interval = setInterval(poll, 5000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const hwLabel = fmtHardware(hardware);
  const label = connected
    ? models.length === 1
      ? `${models[0].split("/").pop() || models[0]}${provider ? ` • ${provider}` : ""}`
      : `${models.length} models${provider ? ` • ${provider}` : ""}`
    : "Disconnected";
  const title = [label, hwLabel].filter(Boolean).join(" | ");

  return (
    <div className="connection-badge" title={title}>
      <span className={`connection-dot ${connected ? "connected" : "disconnected"}`} />
      <span className="connection-label">
        {label}
        {hwLabel && <span className="connection-hw"> • {hwLabel}</span>}
      </span>
    </div>
  );
}
