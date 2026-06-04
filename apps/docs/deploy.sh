#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

DOCS_DIST="dist"

echo "-> Building docs site..."
rm -rf "$DOCS_DIST" .astro
bun run build

echo "-> Deploying to Cloudflare Pages..."
npx wrangler pages deploy "$DOCS_DIST" --project-name modellens-docs

echo ""
echo "✓ Docs deployed to https://modellens-docs.pages.dev"
