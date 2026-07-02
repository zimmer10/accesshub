#!/usr/bin/env bash
set -euo pipefail

docker run --rm \
  -v "$(pwd)":/workspace \
  -w /workspace \
  python:3.12-slim \
  bash -c "pip install --quiet -e .[dev] && pytest --cov=app --cov-report=term-missing"
