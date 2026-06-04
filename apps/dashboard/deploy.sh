#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "-> Building..."
rm -rf dist .astro .wrangler
bun astro build

echo "-> Patching ASSETS binding name in generated files..."
# The adapter generates "ASSETS" as the binding name, which is reserved.
# Rename to "STATIC_CONTENT" in both wrangler.json and the worker code.
find dist/server -name '*.mjs' -o -name '*.json' | xargs sed -i '' 's/"ASSETS"/"STATIC_CONTENT"/g' 2>/dev/null || true
# Also handle the case without quotes (variable references like env.ASSETS)
find dist/server -name '*.mjs' | xargs sed -i '' 's/\.ASSETS\b/.STATIC_CONTENT/g' 2>/dev/null || true

echo "-> Deploying as Cloudflare Worker..."
cd dist/server
rm -rf ../../.wrangler
npx wrangler deploy
