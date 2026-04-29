#!/bin/bash

set -e

echo "========================================="
echo "  AI Interview Assistant - Setup Script"
echo "========================================="
echo ""

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

if ! command_exists python3; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f2)
if [ "$PYTHON_VERSION" -lt 8 ]; then
    echo "❌ Python 3.8+ is required. You have $(python3 --version)"
    exit 1
fi

echo "✅ Python $(python3 --version) detected"
echo ""

echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate
echo "✅ Virtual environment created and activated"
echo ""

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Python dependencies installed"
echo ""

if ! command_exists ollama; then
    echo "⚠️  Ollama is not installed."
    echo "   Install it from: https://ollama.com/download"
    echo "   Or run: curl -fsSL https://ollama.com/install.sh | sh"
    echo ""
    read -p "Do you want to install Ollama now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Installing Ollama..."
        curl -fsSL https://ollama.com/install.sh | sh
        echo "✅ Ollama installed"
    fi
else
    echo "✅ Ollama is already installed: $(ollama --version)"
fi
echo ""

echo "Checking if Ollama is running..."
if curl -s http://localhost:11434 >/dev/null 2>&1; then
    echo "✅ Ollama is running"
else
    echo "⚠️  Ollama is not running. Starting it..."
    ollama serve &
    sleep 3
    echo "✅ Ollama started"
fi
echo ""

MODEL="${1:-llama3.2}"
echo "Checking for model: $MODEL"
if ollama list 2>/dev/null | grep -q "$MODEL"; then
    echo "✅ Model '$MODEL' is already downloaded"
else
    echo "Downloading model '$MODEL' (this may take a while)..."
    ollama pull "$MODEL"
    echo "✅ Model '$MODEL' downloaded"
fi
echo ""

echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "To run the application:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "Or use the run script:"
echo "  ./run.sh"
echo ""
