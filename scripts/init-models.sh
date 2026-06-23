#!/bin/bash
# Descarga los modelos Ollama necesarios para el stack TIM.
# Ejecutar una sola vez después de levantar el stack.
# Uso: ./scripts/init-models.sh

set -e

echo "[init-models] Esperando que Ollama esté listo..."
until curl -sf http://localhost:11434/api/tags > /dev/null; do
  sleep 3
done

echo "[init-models] Descargando nomic-embed-text (embeddings)..."
docker compose exec ollama ollama pull nomic-embed-text

echo "[init-models] Descargando llama3.2:3b (extracción + briefings)..."
docker compose exec ollama ollama pull llama3.2:3b

echo "[init-models] Modelos listos."
docker compose exec ollama ollama list
