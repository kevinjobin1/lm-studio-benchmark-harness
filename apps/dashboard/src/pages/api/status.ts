/**
 * GET /api/status
 * Check which providers are connected and list available models.
 */

import type { APIRoute } from "astro";

export const GET: APIRoute = async () => {
  let connected = false;
  let models: string[] = [];
  let provider = "";

  // Try LM Studio
  try {
    const lmResp = await fetch("http://localhost:1234/v1/models", {
      signal: AbortSignal.timeout(3000),
    });
    if (lmResp.ok) {
      const data = await lmResp.json();
      const lmModels: string[] = (data.data || []).map((m: { id: string }) => m.id);
      if (lmModels.length > 0) {
        connected = true;
        models = lmModels;
        provider = "lm-studio";
      }
    }
  } catch { /* LM Studio not reachable */ }

  // Try Ollama if LM Studio had no models
  if (!connected) {
    try {
      const ollamaResp = await fetch("http://localhost:11434/api/tags", {
        signal: AbortSignal.timeout(3000),
      });
      if (ollamaResp.ok) {
        const data = await ollamaResp.json();
        const ollamaModels: string[] = (data.models || []).map((m: { name: string }) => m.name);
        if (ollamaModels.length > 0) {
          connected = true;
          models = ollamaModels;
          provider = "ollama";
        }
      }
    } catch { /* Ollama not reachable */ }
  }

  return new Response(
    JSON.stringify({ connected, models, provider }),
    { status: 200, headers: { "Content-Type": "application/json" } }
  );
};
