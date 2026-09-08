#!/bin/bash
# Start a local dev server for the Option 1 UI
cd "$(dirname "$0")"
PORT=${1:-8080}
echo "Starting dev server at http://localhost:$PORT"
python3 -m http.server "$PORT"
