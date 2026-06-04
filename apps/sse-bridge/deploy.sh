#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "-> Typechecking..."
npx tsc --noEmit

echo "-> Deploying SSE Bridge Worker..."
npx wrangler deploy

echo ""
echo "✓ SSE Bridge deployed"
echo "  https://modellens-sse-bridge.kevin-jobin-1.workers.dev"
echo ""
echo "  Endpoints:"
echo "    POST /events  — Python benchmark publishes events"
echo "    GET  /events  — Dashboard SSE stream"
echo "    GET  /health  — Connection count and status"
