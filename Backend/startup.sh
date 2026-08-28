#!/usr/bin/env bash
# Start the app from the Backend/ directory (modules import by bare name).
set -e
cd "$(dirname "$0")"
exec python -m uvicorn main:app --host 0.0.0.0 --port 8000
