# TIM Platform — First-Run Setup Guide

This document covers everything an operator needs to bring up the Threat Intelligence
Management (TIM) platform from a clean Ubuntu 22.04 machine. Follow the sections in
order on first run.

---

## 1. Prerequisites

Before running any setup commands, verify the following are present:

| Requirement | Minimum Version | Confirmed on Dev Machine |
|-------------|----------------|--------------------------|
| Docker Engine | 24.0 | 29.5.2 |
| Docker Compose v2 | v2.0 | v5.1.4 |
| NVIDIA GPU with driver | any CUDA-capable | RTX 3050, driver 580.159.03 |
| nvidia-container-toolkit | latest | See Section 2 |

**Check your versions:**

```bash
docker version --format '{{.Server.Version}}'
docker compose version
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
```

---

## 2. NVIDIA Container Toolkit Installation (Ubuntu 22.04)

The `ollama` service requires the NVIDIA Container Toolkit so Docker can pass the
GPU through to the container. Without it, `docker compose --profile platform up -d`
will fail on the ollama service.

**Install nvidia-container-toolkit:**

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

**Verify the installation:**

```bash
docker run --rm --gpus all ubuntu nvidia-smi
```

You should see the standard `nvidia-smi` table output inside the container. If the
command fails, re-run `sudo nvidia-ctk runtime configure --runtime=docker` and
restart Docker again.

---

## 3. First-Run Sequence

Run these four commands in order from the project root:

```bash
# Step 1: Generate .env with UUIDs and passwords
./scripts/setup-env.sh

# Step 2: Start all 8 platform services
docker compose --profile platform up -d

# Step 3: Download Ollama models (llama3.2:3b + nomic-embed-text)
./scripts/init-models.sh

# Step 4: Poll until MITRE ATT&CK import is complete and TAXII is verified
./scripts/verify-platform.sh
```

**What each step does:**

- **Step 1 — `setup-env.sh`:** Copies `.env.example` to `.env` and replaces the four
  placeholder values (`OPENCTI_ADMIN_TOKEN`, `CONNECTOR_MITRE_ID`, `RABBITMQ_PASSWORD`,
  `MINIO_SECRET_KEY`) with auto-generated UUIDs and 24-character alphanumeric passwords.
  Idempotent: running it a second time exits cleanly without overwriting `.env`.

- **Step 2 — `docker compose up`:** Starts elasticsearch, redis, rabbitmq, minio,
  opencti, connector-mitre, ollama, and chromadb. Health-gate dependency chains ensure
  services start in the correct order. The MITRE ATT&CK connector begins importing in the
  background once OpenCTI is healthy.

- **Step 3 — `init-models.sh`:** Waits for Ollama to become ready, then pulls
  `llama3.2:3b` (extraction and briefings) and `nomic-embed-text` (embeddings). This
  can run in parallel with the MITRE import.

- **Step 4 — `verify-platform.sh`:** Polls the OpenCTI GraphQL API every 30 seconds
  until more than 100 ATT&CK attack-pattern objects are present (full import typically
  delivers 600–900+ objects across Enterprise, Mobile, ICS, and CAPEC). Also verifies
  the TAXII 2.1 endpoint returns HTTP 200. Times out after 15 minutes with an actionable
  error message.

---

## 4. Optional: IpInfo Geolocation Token

The `connector-ipinfo` service enriches IP observables with geolocation data, which
populates the world map widget on the OpenCTI dashboard. It requires a free ipinfo.io
account (50k lookups/month on the free tier).

**Get a free token:**

1. Sign up at https://ipinfo.io/signup
2. Copy the token shown on your dashboard and add it to `.env`:

```bash
IPINFO_TOKEN=your_token_here
```

3. Restart the connector:

```bash
docker compose --profile platform up -d connector-ipinfo
```

The connector will automatically enrich IP observables as they are created or updated.
Allow a few minutes for existing IPs to be processed and the world map to populate.

**NVD API key (optional):** The `connector-cve` service syncs the full CVE database
from NVD without a key, but NVD rate-limits unauthenticated requests. For faster initial
sync, get a free API key at https://nvd.nist.gov/developers/request-an-api-key and set:

```bash
CVE_NVD_API_KEY=your_key_here
```

---

## 5. Troubleshooting

### Issue A — Elasticsearch fails to start with memory lock error

**Symptom:** Elasticsearch logs contain "unable to lock memory":

```bash
docker compose --profile platform logs elasticsearch | grep -i "lock"
```

**Cause:** The Docker daemon on Ubuntu 22.04 may not have `LimitMEMLOCK=infinity`
set in its systemd unit, which prevents Elasticsearch from locking heap memory.

**Fix:**

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
printf '[Service]\nLimitMEMLOCK=infinity\n' | sudo tee /etc/systemd/system/docker.service.d/override.conf
sudo systemctl daemon-reload && sudo systemctl restart docker
```

Then restart the platform:

```bash
docker compose --profile platform up -d
```

---

### Issue B — MinIO healthcheck fails (mc command not in image)

**Symptom:** `docker compose --profile platform ps` shows MinIO as `unhealthy`; as a
result OpenCTI never starts (it depends on MinIO being healthy).

**Cause:** Some versions of the `minio/minio:latest` image do not include the `mc`
client binary. The default healthcheck (`CMD mc ready local`) therefore always fails.

**Fix:** Replace the MinIO healthcheck in `docker-compose.yml`:

```yaml
# Change this:
test: ["CMD", "mc", "ready", "local"]

# To this:
test: ["CMD-SHELL", "curl -f http://localhost:9000/minio/health/live || exit 1"]
```

Then restart:

```bash
docker compose --profile platform up -d
```

---

### Issue C — verify-platform.sh times out (MITRE import still running)

**Symptom:** The script prints `ERROR: 15-minute timeout` before completing.

**Cause:** The MITRE ATT&CK import takes longer than 15 minutes on this machine, or
the `connector-mitre` service failed to start / connect to OpenCTI.

**Fix:**

1. Check whether the import is still progressing:
   ```bash
   docker compose --profile platform logs connector-mitre
   ```

2. If the connector is running and importing, simply re-run the verify script:
   ```bash
   ./scripts/verify-platform.sh
   ```

3. If `connector-mitre` is not starting, verify OpenCTI itself is healthy:
   ```bash
   docker compose --profile platform ps
   ```
   If OpenCTI shows as `unhealthy`, check its logs:
   ```bash
   docker compose --profile platform logs opencti
   ```
