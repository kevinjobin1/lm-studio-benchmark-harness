import React, { useEffect, useState } from "react";

interface StatusResponse {
  connected: boolean;
  models: string[];
  provider: string;
}

export default function ConnectionStatusBadge() {
  const [connected, setConnected] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [provider, setProvider] = useState("");

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

  const label = connected
    ? models.length === 1
      ? `${models[0].split("/").pop() || models[0]}${provider ? ` • ${provider}` : ""}`
      : `${models.length} models${provider ? ` • ${provider}` : ""}`
    : "Disconnected";

  return (
    <div className="connection-badge" title={label}>
      <span className={`connection-dot ${connected ? "connected" : "disconnected"}`} />
      <span className="connection-label">{label}</span>
    </div>
  );
}
