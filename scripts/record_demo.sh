#!/usr/bin/env bash
# Shell launcher for demo video recording
set -e
cd "$(dirname "$0")/.."
echo "[Demo] Running scripts/record_demo.py..."
python scripts/record_demo.py
