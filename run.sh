#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Running setup first..."
    bash setup.sh
fi

source venv/bin/activate

if ! curl -s http://localhost:11434 >/dev/null 2>&1; then
    echo "Starting Ollama..."
    ollama serve &
    sleep 2
fi

echo "Starting AI Interview Assistant..."
python main.py
