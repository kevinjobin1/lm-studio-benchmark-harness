#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "-> Building..."
rm -rf dist .astro .wrangler
bun astro build

echo "-> Patching ASSETS binding name in generated files..."
find dist/server -name '*.mjs' -o -name '*.json' | xargs sed -i '' 's/"ASSETS"/"STATIC_CONTENT"/g' 2>/dev/null || true
find dist/server -name '*.mjs' | xargs sed -i '' 's/\.ASSETS\b/.STATIC_CONTENT/g' 2>/dev/null || true

echo "-> Deploying as Cloudflare Worker..."
cd dist/server
rm -rf ../../.wrangler
npx wrangler deploy
