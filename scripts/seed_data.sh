#!/usr/bin/env bash
set -euo pipefail

docker compose exec app python scripts/seed.py
