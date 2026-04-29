# AI Interview Assistant

A transparent overlay application that captures audio during interviews and provides real-time AI-powered response suggestions using local Ollama models.

## Features

- Transparent overlay window that stays on top of other applications
- Real-time audio capture and speech transcription
- AI-powered interview response suggestions via Ollama
- Draggable window with customizable opacity
- Configurable interview context and response style
- Auto-analyze mode for hands-free operation
- Works completely offline with local AI models

## Quick Start

### 1. Run Setup

```bash
bash setup.sh
```

Or manually:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Install Ollama (if not installed)

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 3. Download AI Model

```bash
ollama pull llama3.2
```

Or use a different model:

```bash
ollama pull mistral
ollama pull phi3
```

### 4. Run the Application

```bash
bash run.sh
```

Or manually:

```bash
source venv/bin/activate
python main.py
```

## Usage

1. **Start Listening**: Click the microphone button to begin capturing audio
2. **View Transcript**: Spoken words appear in the transcript section
3. **Get AI Suggestions**: After 3 transcriptions, AI automatically analyzes and suggests responses
4. **Manual Analysis**: Click the Analyze button anytime for immediate AI feedback
5. **Drag Window**: Click and drag the header to reposition the overlay
6. **Settings**: Click ⚙ to configure Ollama URL, model, context, and more

## Settings

- **Ollama URL**: Default `http://localhost:11434`
- **Model**: Choose any downloaded Ollama model (default: `llama3.2`)
- **Interview Context**: Add job role, company, or interview type for better suggestions
- **Response Style**: concise, detailed, bullet-points, or example-focused
- **Auto-analyze**: Toggle automatic analysis after 3 transcriptions
- **Window Opacity**: Adjust transparency from 50-100%

## Supported Models

Any Ollama model works. Recommended:
- `llama3.2` - Fast and capable (default)
- `mistral` - Good balance of speed and quality
- `phi3` - Lightweight, fast responses
- `llama3` - More detailed responses

## Requirements

- Python 3.8+
- macOS, Linux, or Windows
- Ollama installed and running
- Microphone access
