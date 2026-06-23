#!/bin/bash
# Generates .env from .env.example with auto-created UUIDs and passwords.
# Usage: ./scripts/setup-env.sh

set -e

# Resolve project root relative to script location (not cwd)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Idempotency guard (D-07): exit 0 if .env already exists
if [ -f "$PROJECT_ROOT/.env" ]; then
  echo "[setup-env] .env already exists. Remove it to regenerate."
  exit 0
fi

# NVIDIA GPU check: warn but do not block
# nvidia-container-toolkit may need manual install (see docs/SETUP.md)
if command -v nvidia-smi > /dev/null 2>&1; then
  if ! docker info 2>/dev/null | grep -q nvidia; then
    echo "[setup-env] WARN: NVIDIA GPU detected but nvidia-container-toolkit is not configured."
    echo "            Ollama will fail to start. See docs/SETUP.md for installation steps."
  fi
fi

# Copy template (Plan 01 fixed .env.example permissions)
cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"

echo "[setup-env] Generating UUIDs and passwords..."

# UUID generation: uuidgen preferred; python3 fallback
if command -v uuidgen > /dev/null 2>&1; then
  OPENCTI_TOKEN=$(uuidgen)
  CONNECTOR_MITRE_UUID=$(uuidgen)
else
  OPENCTI_TOKEN=$(python3 -c "import uuid; print(uuid.uuid4())")
  CONNECTOR_MITRE_UUID=$(python3 -c "import uuid; print(uuid.uuid4())")
fi

# Password generation: alphanumeric only — avoids shell quoting issues with sed
RABBITMQ_PASS=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 24)
MINIO_SECRET=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 24)

# Write generated values to .env via sed (| delimiter avoids conflicts with URL values)
sed -i "s|^OPENCTI_ADMIN_TOKEN=.*|OPENCTI_ADMIN_TOKEN=${OPENCTI_TOKEN}|" "$PROJECT_ROOT/.env"
sed -i "s|^CONNECTOR_MITRE_ID=.*|CONNECTOR_MITRE_ID=${CONNECTOR_MITRE_UUID}|" "$PROJECT_ROOT/.env"
sed -i "s|^RABBITMQ_PASSWORD=.*|RABBITMQ_PASSWORD=${RABBITMQ_PASS}|" "$PROJECT_ROOT/.env"
sed -i "s|^MINIO_SECRET_KEY=.*|MINIO_SECRET_KEY=${MINIO_SECRET}|" "$PROJECT_ROOT/.env"

echo "[setup-env] Generated .env with:"
echo "  OPENCTI_ADMIN_TOKEN = ${OPENCTI_TOKEN}"
echo "  CONNECTOR_MITRE_ID  = ${CONNECTOR_MITRE_UUID}"
echo "  RABBITMQ_PASSWORD   = ${RABBITMQ_PASS}"
echo "  MINIO_SECRET_KEY    = ${MINIO_SECRET}"
echo ""
echo "[setup-env] Next step: docker compose --profile platform up -d"
