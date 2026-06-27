# TIM — Threat Intelligence Management System

A self-hosted, air-gapped threat intelligence platform. Ingest structured feeds and unstructured PDFs, correlate IOCs semantically, and generate analyst briefings — all without sending a single indicator off the machine.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Ingestion                                                       │
│  URLhaus · OTX · Feodo · MalwareBazaar · ThreatFox              │
│              │                                                   │
│              ▼                                                   │
│       feed-orchestrator (:8001)  ◄──  intel-extractor (:8001)  │
│              │                              (PDF/report upload)  │
│              ▼                                                   │
│          OpenCTI (:8080)  ←  MITRE ATT&CK connector            │
│              │                                                   │
│              ▼                                                   │
│       semantic-engine (:8002)  →  ChromaDB (vector store)       │
│              │                                                   │
│              ▼                                                   │
│     briefing-generator (:8003)  →  Ollama (llama3.2:3b)        │
│                                                                  │
│          soc-dashboard (:3000)  — unified React UI              │
└─────────────────────────────────────────────────────────────────┘
```

**Key design choices:**
- Ollama runs locally — no cloud LLM calls, ever
- ChromaDB holds semantic embeddings for IOC correlation
- OpenCTI stores the STIX 2.1 graph; MITRE ATT&CK imported automatically on first boot
- `feed-orchestrator` and `intel-extractor` both bind `:8001` — they're in separate Docker Compose profiles and run independently, not simultaneously

---

## Prerequisites

| Requirement | Minimum | Tested on |
|-------------|---------|-----------|
| Docker Engine | 24.0 | 29.5.2 |
| Docker Compose v2 | 2.0 | 5.1.4 |
| NVIDIA GPU (CUDA) | 4 GB VRAM | RTX 3050 |
| nvidia-container-toolkit | latest | see below |
| Disk space | 28 GB | — |

**Verify:**
```bash
docker version --format '{{.Server.Version}}'
docker compose version
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
```

**Install nvidia-container-toolkit (Ubuntu 22.04):**
```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -sL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

---

## Quick Start

### Step 1 — Generate `.env`

```bash
./scripts/setup-env.sh
```

This copies `.env.example` to `.env` and fills in auto-generated UUIDs and passwords. Idempotent — safe to run again if `.env` already exists.

### Step 2 — Add API keys

Edit `.env` and fill in the three feed keys:

```
OTX_API_KEY=          # https://otx.alienvault.com → API Keys
MALWAREBAZAAR_AUTH_KEY=   # https://auth.abuse.ch → same key for both
THREATFOX_AUTH_KEY=       # https://auth.abuse.ch
```

URLhaus and Feodo Tracker require no key.

### Step 3 — Start the platform

```bash
docker compose --profile platform up -d
```

Starts: Elasticsearch, Redis, RabbitMQ, MinIO, OpenCTI, OpenCTI Worker, MITRE ATT&CK connector, Ollama, ChromaDB.

The MITRE ATT&CK connector begins importing in the background (~5–15 min depending on hardware).

### Step 4 — Pull Ollama models

```bash
./scripts/init-models.sh
```

Downloads `llama3.2:3b` (extraction + briefings) and `nomic-embed-text` (embeddings). Can run in parallel with Step 3's MITRE import.

### Step 5 — Verify platform readiness

```bash
./scripts/verify-platform.sh
```

Polls every 30 s until 100+ ATT&CK objects are present in OpenCTI. Times out at 15 min with an actionable message.

### Step 6 — Create TAXII collection (one-time, manual)

The TAXII 2.1 endpoint won't serve data until a collection is created through the OpenCTI UI:

1. Open `http://localhost:8080` → log in (default: `admin@opencti.io` / password from `.env`)
2. Go to **Data → Data Sharing → TAXII Collections**
3. Click **+** → name it `TIM` → save

The feed-orchestrator and semantic engine use this collection to pull structured STIX bundles.

### Step 7 — Start TIM services

```bash
docker compose --profile feeds --profile semantic --profile briefings --profile dashboard up -d
```

All four services start. The semantic engine begins indexing IOCs from OpenCTI on a 5-minute poll cycle.

To also run the AI extraction service for uploading PDFs/threat reports (uses the same `:8001` port as feed-orchestrator — stop feeds first):

```bash
docker compose --profile extract up -d
```

---

## Port Map

| Service | URL | Notes |
|---------|-----|-------|
| SOC Dashboard | `http://localhost:3000` | Main UI |
| OpenCTI | `http://localhost:8080` | Full threat graph |
| feed-orchestrator | `http://localhost:8001` | Feed status + manual trigger |
| intel-extractor | `http://localhost:8001` | PDF upload (separate profile) |
| semantic-engine | `http://localhost:8002` | IOC semantic search API |
| briefing-generator | `http://localhost:8003` | Briefing generation API |
| RabbitMQ Management | `http://localhost:15672` | localhost only |
| MinIO Console | `http://localhost:9001` | localhost only |

---

## Features

### SOC Dashboard (`localhost:3000`)

**Overview tab** — live feed health, IOC counts by type, recent threat activity.

**Threat Hunt tab** — semantic search across 20k+ IOCs. Type a domain, IP, hash, or natural-language description; returns ranked results with confidence scores from ChromaDB.

**Briefings tab** — generate a threat intelligence briefing for the last 24 h, 72 h, or 7 days. Uses `llama3.2:3b` to summarize active threats, IOC patterns, and MITRE ATT&CK techniques observed. Grounded in real OpenCTI data — refuses to fabricate when data is sparse.

### Feed Orchestrator (`localhost:8001/feeds/status`)

Returns live status for all 5 feeds with last-run time and IOC counts. Trigger a manual run:

```bash
curl -X POST http://localhost:8001/feeds/run
```

### Intel Extractor (`localhost:8001`) — `extract` profile

Upload a PDF threat report and extract structured IOCs directly into OpenCTI:

```bash
curl -F "file=@report.pdf" http://localhost:8001/extract
```

### Semantic Engine (`localhost:8002/search`)

Direct semantic search API:

```bash
curl "http://localhost:8002/search?q=cobalt+strike+beacon&limit=10"
```

---

## Troubleshooting

See [`docs/SETUP.md`](docs/SETUP.md) for:
- Elasticsearch memory lock errors
- MinIO healthcheck failures (`mc` binary missing)
- MITRE ATT&CK import timeout
- NVIDIA container toolkit setup issues

---

## Improvement Backlog

| Item | Priority |
|------|----------|
| Briefing persistence (SQLite) | High |
| Alerting on high-confidence IOC | High |
| connector-mitre ATT&CK pattern gap | Medium |
| SIEM export (CEF/STIX) | Low |
