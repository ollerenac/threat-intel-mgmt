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
_gen_uuid() {
  if command -v uuidgen > /dev/null 2>&1; then uuidgen; else python3 -c "import uuid; print(uuid.uuid4())"; fi
}
OPENCTI_TOKEN=$(_gen_uuid)
CONNECTOR_MITRE_UUID=$(_gen_uuid)
CONNECTOR_IPINFO_UUID=$(_gen_uuid)
CONNECTOR_CVE_UUID=$(_gen_uuid)
CONNECTOR_CISA_KEV_UUID=$(_gen_uuid)

# Password generation: alphanumeric only — avoids shell quoting issues with sed
RABBITMQ_PASS=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 24)
MINIO_SECRET=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 24)

# Write generated values to .env: sed replaces existing lines; append if the
# template predates the variable (keeps script correct as connectors are added)
_set_var() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$PROJECT_ROOT/.env"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$PROJECT_ROOT/.env"
  else
    echo "${key}=${val}" >> "$PROJECT_ROOT/.env"
  fi
}
_set_var OPENCTI_ADMIN_TOKEN "$OPENCTI_TOKEN"
_set_var CONNECTOR_MITRE_ID "$CONNECTOR_MITRE_UUID"
_set_var CONNECTOR_IPINFO_ID "$CONNECTOR_IPINFO_UUID"
_set_var CONNECTOR_CVE_ID "$CONNECTOR_CVE_UUID"
_set_var CONNECTOR_CISA_KEV_ID "$CONNECTOR_CISA_KEV_UUID"
_set_var RABBITMQ_PASSWORD "$RABBITMQ_PASS"
_set_var MINIO_SECRET_KEY "$MINIO_SECRET"

echo "[setup-env] Generated .env with:"
echo "  OPENCTI_ADMIN_TOKEN   = ${OPENCTI_TOKEN}"
echo "  CONNECTOR_MITRE_ID    = ${CONNECTOR_MITRE_UUID}"
echo "  CONNECTOR_IPINFO_ID   = ${CONNECTOR_IPINFO_UUID}"
echo "  CONNECTOR_CVE_ID      = ${CONNECTOR_CVE_UUID}"
echo "  CONNECTOR_CISA_KEV_ID = ${CONNECTOR_CISA_KEV_UUID}"
echo "  RABBITMQ_PASSWORD     = ${RABBITMQ_PASS}"
echo "  MINIO_SECRET_KEY      = ${MINIO_SECRET}"
echo ""
echo "[setup-env] Next step: docker compose --profile platform up -d"
