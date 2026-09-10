#!/bin/bash
# Vehicle Counting AI — Start Script (macOS/Linux)

set -e

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the application
python main.py
