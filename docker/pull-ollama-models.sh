#!/bin/sh
# Модели в Ollama на хосте (не в Docker)
set -e
echo "Pulling qwen2.5, qwen2.5:14b, nomic-embed-text (host ollama)..."
ollama pull qwen2.5
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
ollama list
