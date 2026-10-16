#!/usr/bin/env bash
# Render's Python runtime: build API, frontend and original artwork.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -r requirements.txt -r requirements-assets.txt
npm ci --no-audit --no-fund
npm run build
python3 scripts/prepare_minecraft_assets.py
