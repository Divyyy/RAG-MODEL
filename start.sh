#!/bin/bash
set -e

echo "▶ Starting Ollama server..."
ollama serve &
OLLAMA_PID=$!

# Wait until Ollama is ready to accept requests
echo "⏳ Waiting for Ollama to be ready..."
until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 1
done
echo "✅ Ollama is ready."

# Pull required models (skipped automatically if already cached)
echo "📦 Pulling models..."
ollama pull phi3:mini
ollama pull minicpm-v
ollama pull nomic-embed-text
echo "✅ All models ready."

# Start Flask
echo "🚀 Starting Flask app..."
exec python app.py
