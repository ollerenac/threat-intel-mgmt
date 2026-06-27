# TIM — Sistema de Gestión de Inteligencia de Amenazas

Plataforma de threat intelligence autohospedada y air-gapped. Ingiere feeds estructurados e informes PDF no estructurados, correlaciona IOCs semánticamente y genera briefings ejecutivos — sin enviar un solo indicador fuera de la máquina.

---

## ¿Qué es un TIM y qué cubre esta plataforma?

Un **Threat Intelligence Management System (TIM)** centraliza, normaliza y analiza inteligencia sobre amenazas cibernéticas proveniente de múltiples fuentes. Esta plataforma cubre las cinco funciones nucleares de un TIM empresarial:

| Función | Descripción | Implementación |
|---------|-------------|----------------|
| **Ingestión multi-feed** | Consumir feeds de IOCs de múltiples proveedores | 5 feeds automáticos + conector CVE NVD |
| **Normalización y deduplicación** | Unificar formatos heterogéneos en un modelo común | feed-orchestrator: STIX 2.1 nativo; deduplicación por `(type, value)` |
| **Correlación y enriquecimiento** | Relacionar IOCs con actores, campañas y técnicas ATT&CK | OpenCTI como knowledge graph; MITRE ATT&CK importado automáticamente |
| **Búsqueda e investigación** | Consultar IOCs por valor exacto o por comportamiento | semantic-engine: búsqueda vectorial + ChromaDB; Threat Hunt en dashboard |
| **Distribución y reporte** | Exportar inteligencia y comunicarla a stakeholders | STIX 2.1 export endpoint; TAXII 2.1 nativo; briefings PDF ejecutivos |

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        FUENTES DE INTELIGENCIA                          │
│  URLhaus · OTX · Feodo · MalwareBazaar · ThreatFox · NVD CVE · PDFs   │
└──────────────┬──────────────────────────────────────┬───────────────────┘
               │ feeds automáticos                    │ extracción IA
               ▼                                      ▼
┌──────────────────────────┐          ┌───────────────────────────────┐
│   feed-orchestrator      │          │   intel-extractor              │
│   :8001                  │          │   llama3.2:3b via Ollama       │
│   APScheduler + STIX 2.1 │          │   PDF / URL → IOCs + TTPs     │
└──────────────┬───────────┘          └──────────────┬────────────────┘
               │                                      │
               └──────────────┬───────────────────────┘
                              ▼
          ┌───────────────────────────────────────────────┐
          │                  OpenCTI 6.x                   │
          │   Knowledge graph STIX 2.1 · TAXII 2.1        │
          │   MITRE ATT&CK · Elasticsearch 8              │
          │   Redis · RabbitMQ · MinIO                     │
          └──────────┬────────────────────────────────────┘
                     │
          ┌──────────┴──────────────────────┐
          ▼                                 ▼
┌──────────────────────┐        ┌───────────────────────────┐
│   semantic-engine    │        │   briefing-generator       │
│   :8002              │        │   :8003                    │
│   nomic-embed-text   │        │   llama3.2:3b via Ollama  │
│   ChromaDB 23k+ IOCs │        │   resúmenes ejecutivos PDF │
└──────────┬───────────┘        └──────────┬────────────────┘
           └──────────────┬────────────────┘
                          ▼
         ┌────────────────────────────────────┐
         │          SOC Dashboard              │
         │          :443 (HTTPS)              │
         │  Overview · Threat Hunt            │
         │  Briefings · Alerts                │
         └────────────────┬───────────────────┘
                          │
         ┌────────────────▼───────────────────┐
         │   Kibana 8.15  :5602 (nginx auth)  │
         │   Índice tim-iocs — SIEM view       │
         └────────────────────────────────────┘
```

### Servicios

| Servicio | Puerto | Rol |
|----------|--------|-----|
| **soc-dashboard** | `:443` | UI React unificada — 4 vistas |
| **feed-orchestrator** | `127.0.0.1:8001` | Ingestión de 5 feeds + STIX export endpoint |
| **intel-extractor** | `127.0.0.1:8001` | Extracción IA de PDFs/URLs (perfil separado) |
| **semantic-engine** | `127.0.0.1:8002` | Búsqueda vectorial de IOCs |
| **briefing-generator** | `127.0.0.1:8003` | Generación de briefings + PDF export |
| **OpenCTI** | `127.0.0.1:8080` | Knowledge graph STIX 2.1 |
| **Kibana** | `127.0.0.1:5602` | Visualización SIEM del índice tim-iocs |
| **Ollama** | interno | Inferencia LLM local |
| **ChromaDB** | interno | Vector store para búsqueda semántica |
| **Elasticsearch 8** | interno | Storage de OpenCTI + índice tim-iocs |

---

## Funcionalidades

### Ingestión automática de feeds

Cinco feeds de threat intelligence actualizados automáticamente por APScheduler:

| Feed | Tipo de IOCs | IOCs típicos por ciclo | Requiere clave |
|------|-------------|------------------------|----------------|
| URLhaus (Abuse.ch) | URLs maliciosas | ~2.500 | No |
| AlienVault OTX | Multi-tipo | variable | Sí (gratuita) |
| Feodo Tracker (Abuse.ch) | IPs C2 botnet | ~300 | No |
| MalwareBazaar (Abuse.ch) | Hashes malware | variable | Sí (gratuita) |
| ThreatFox (Abuse.ch) | Multi-tipo | ~3.500 | Sí (gratuita) |

Todos los IOCs se normalizan a STIX 2.1 con puntuación de confianza calculada como:

```
confianza = min(100, feeds_que_lo_reportan × 25 + max(0, 10 − días_desde_primera_vista) + peso_calidad)
```

IOCs con confianza ≥ 55 se indexan adicionalmente en el índice Elasticsearch `tim-iocs` para consumo SIEM.

### Extracción IA de documentos

Sube un informe PDF o pasa una URL: `intel-extractor` usa `llama3.2:3b` para extraer:

- IPs, dominios, hashes MD5/SHA1/SHA256, URLs, emails
- Técnicas MITRE ATT&CK (lenguaje natural → código Txxxx con resolución via OpenCTI)
- Familias de malware y actores de amenaza mencionados

El resultado se escribe directamente en OpenCTI como objetos STIX 2.1 (`indicator`, `report`, `relationship`).

```bash
# Extraer IOCs de un PDF
curl -F "file=@informe-amenaza.pdf" http://localhost:8001/extract

# Extraer desde URL
curl -X POST http://localhost:8001/extract -d '{"url": "https://ejemplo.com/report"}' -H "Content-Type: application/json"
```

### Búsqueda semántica

El `semantic-engine` indexa más de 23.000 IOCs como vectores de 768 dimensiones con `nomic-embed-text`. No requiere coincidencia exacta de cadena:

```bash
# Buscar por comportamiento
curl "http://localhost:8002/search?q=malware+con+DNS+tunneling+hacia+dominios+rusos&limit=10"

# Pivoting por técnica
curl "http://localhost:8002/search?q=cobalt+strike+beacon+C2&limit=5"
```

### Briefings ejecutivos

Genera resúmenes en lenguaje natural para las últimas 24h, 72h o 7 días. Basados en datos reales de OpenCTI — el sistema rechaza fabricar información cuando los datos son escasos. Exportables a PDF desde el dashboard.

### SIEM Export

IOCs de alta confianza accesibles como bundle STIX 2.1 y en Elasticsearch:

```bash
# Bundle STIX 2.1 completo
curl http://localhost:8001/feeds/export/stix | jq '.objects | length'

# Ver IOCs en Kibana
open http://localhost:5602  # usuario: analyst / contraseña en .env
```

### Kibana — Visualización SIEM

Kibana 8.15 conectado al mismo Elasticsearch de OpenCTI, accesible en `http://localhost:5602` protegido por autenticación básica nginx. Permite crear data views sobre `tim-iocs` para dashboards de timeline, heatmaps por tipo de IOC y análisis de tendencias temporales.

---

## Diferenciación competitiva

| | **TIM** (este proyecto) | MISP | OpenCTI solo | Recorded Future / Anomali |
|--|--|--|--|--|
| **Soberanía de datos** | ✅ 100% local, air-gapped | ✅ self-hosted | ✅ self-hosted | ❌ cloud / SaaS |
| **Extracción IA de PDFs** | ✅ LLM local (Ollama) | ❌ manual | ❌ sin IA nativa | ✅ pero cloud |
| **Búsqueda semántica** | ✅ ChromaDB + nomic-embed | ❌ solo exacta | ❌ sin semántica | ✅ pero cloud |
| **Briefings ejecutivos** | ✅ LLM local → PDF | ❌ | ❌ | ✅ pero cloud |
| **Knowledge graph STIX** | ✅ vía OpenCTI | ⚠️ básico | ✅ nativo | ✅ |
| **MITRE ATT&CK nativo** | ✅ conector automático | ⚠️ manual | ✅ conector | ✅ |
| **TAXII 2.1** | ✅ nativo | ✅ | ✅ | ✅ |
| **SIEM export STIX 2.1** | ✅ endpoint + ES index | ⚠️ exportación manual | ⚠️ | ✅ |
| **Coste de licencia** | ✅ gratuito | ✅ gratuito | ✅ gratuito | ❌ alto |
| **Deploy en un comando** | ✅ `docker compose` | ⚠️ complejo | ⚠️ complejo | ❌ SaaS |

**Frente a OpenCTI solo:** TIM añade la capa de IA (extracción, embeddings, briefings) y la UI analítica unificada encima del knowledge graph de OpenCTI. OpenCTI es el motor de datos; TIM es la plataforma completa de analista.

**Frente a MISP:** MISP está optimizado para compartir IOCs entre organizaciones. TIM está optimizado para el ciclo analítico completo: ingerir → correlacionar → investigar → briefar. Ambos son complementarios; TIM puede exportar via TAXII 2.1 hacia MISP.

**Frente a plataformas cloud:** ningún IOC, documento ni consulta sale de la red local. Apto para entornos con restricciones regulatorias en defensa, banca y salud.

---

## Hardware — Despliegue demo actual

| Recurso | Disponible | Asignado a TIM |
|---------|-----------|----------------|
| CPU | 16 vCPUs | 12 |
| RAM | 31 GB | ~14 GB activos |
| Disco | 112 GB libres | 28 GB |
| GPU | NVIDIA RTX 3050, 4 GB VRAM | 4 GB (Ollama exclusivo) |
| SO | Ubuntu 22.04 LTS | — |
| Runtime | Docker 29.5 + Compose v5 | — |

Con 4 GB de VRAM, `llama3.2:3b` (~2 GB) y `nomic-embed-text` (~0.3 GB) no corren simultáneamente. Ollama carga y descarga modelos según demanda.

---

## Escalabilidad — Roadmap de modelos IA

El único cambio de código para actualizar el modelo LLM es una línea en `config.py` del servicio correspondiente:

```python
OLLAMA_MODEL = "llama3.3:70b"  # era llama3.2:3b
```

`nomic-embed-text` (embeddings del semantic-engine) no requiere sustitución en ningún nivel de hardware.

### Niveles de hardware recomendados

**Nivel 1 — 16–24 GB VRAM** (RTX 3090/4090, A10, L4)

| Modelo | VRAM aprox. | Ventaja principal |
|--------|------------|-------------------|
| `llama3.1:8b` | ~8 GB | Primera actualización recomendada — JSON estructurado mucho más fiable |
| `mistral-nemo:12b` | ~14 GB | Excelente adherencia a JSON-schema; óptimo para intel-extractor |
| `qwen2.5:14b` | ~16 GB | Mejor open-source en benchmarks de extracción estructurada |
| `llama3.2:11b-vision` | ~12 GB | Comprensión de imágenes — útil para PDFs escaneados |

**Nivel 2 — 40–80 GB VRAM** (A100 40/80 GB, 2× RTX 4090, A6000 48 GB)

| Modelo | VRAM aprox. | Ventaja principal |
|--------|------------|-------------------|
| `qwen2.5:72b` | ~42 GB Q4 | **Recomendado para producción** — líder open-source en extracción JSON estructurada |
| `llama3.3:70b` | ~40 GB Q4 | Calidad cercana a GPT-4; ideal para briefings ejecutivos |
| `mixtral:8x7b` | ~28 GB Q4 | Alta velocidad por token; adecuado para documentos largos |

**Nivel 3 — 160+ GB VRAM** (cluster multi-GPU H100/A100)

| Modelo | VRAM aprox. | Nota |
|--------|------------|------|
| `llama3.1:405b` | ~200 GB Q4 | Mejor modelo open-weights; calidad GPT-4 Turbo |

**Opción especializada:** Fine-tuning de `llama3.1:8b` sobre corpus STIX 2.1 (MITRE y CISA publican corpus CTI públicos). Un modelo ajustado de 8B supera a modelos generalistas de 70B en la tarea específica de extracción CTI.

---

## Prerrequisitos

| Requisito | Mínimo | Probado en |
|-----------|--------|-----------|
| Docker Engine | 24.0 | 29.5.2 |
| Docker Compose v2 | 2.0 | 5.1.4 |
| GPU NVIDIA (CUDA) | 4 GB VRAM | RTX 3050 |
| nvidia-container-toolkit | latest | Ubuntu 22.04 |
| Espacio en disco | 28 GB | — |

**Verificar entorno:**
```bash
docker version --format '{{.Server.Version}}'
docker compose version
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
```

**Instalar nvidia-container-toolkit (Ubuntu 22.04):**
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

## Inicio rápido

### Paso 1 — Generar `.env`
```bash
./scripts/setup-env.sh
```
Copia `.env.example` a `.env` y rellena UUIDs y contraseñas automáticamente. Idempotente.

### Paso 2 — Añadir API keys
Editar `.env` con las claves de feed (todas gratuitas):
```
OTX_API_KEY=              # https://otx.alienvault.com → API Keys
MALWAREBAZAAR_AUTH_KEY=   # https://auth.abuse.ch
THREATFOX_AUTH_KEY=       # https://auth.abuse.ch (misma clave)
```
URLhaus y Feodo Tracker no requieren clave.

### Paso 3 — Levantar la plataforma base
```bash
docker compose --profile platform up -d
```
Arranca: Elasticsearch, Redis, RabbitMQ, MinIO, OpenCTI, Worker, conector MITRE ATT&CK, Ollama, ChromaDB.
El conector ATT&CK importa en segundo plano (~5–15 min según hardware).

### Paso 4 — Descargar modelos Ollama (una sola vez, ~3 GB)
```bash
./scripts/init-models.sh
```

### Paso 5 — Verificar disponibilidad de la plataforma
```bash
./scripts/verify-platform.sh
```
Espera hasta que OpenCTI tenga 100+ objetos ATT&CK. Timeout de 15 min con mensaje accionable.

### Paso 6 — Crear colección TAXII (manual, una sola vez)
1. Abrir `http://localhost:8080` → iniciar sesión (`admin@opencti.io` / contraseña del `.env`)
2. **Data → Data Sharing → TAXII Collections → +** → nombre `TIM` → guardar

### Paso 7 — Levantar servicios TIM
```bash
docker compose --profile feeds --profile semantic --profile briefings --profile dashboard up -d
```

**Para extracción IA de PDFs** (perfil separado; usa el mismo puerto `:8001` que feeds — detener feeds primero):
```bash
docker compose --profile extract up -d
```

---

## Mapa de puertos

| Servicio | URL | Notas |
|----------|-----|-------|
| SOC Dashboard | `https://localhost:443` | UI principal |
| Kibana | `http://localhost:5602` | Auth básica nginx (analyst / `.env`) |
| OpenCTI | `http://localhost:8080` | Solo acceso local |
| feed-orchestrator | `http://localhost:8001` | Solo acceso local |
| semantic-engine | `http://localhost:8002` | Solo acceso local |
| briefing-generator | `http://localhost:8003` | Solo acceso local |
| RabbitMQ Management | `http://localhost:15672` | Solo acceso local |
| MinIO Console | `http://localhost:9001` | Solo acceso local |

---

## Resolución de problemas

Ver [`docs/SETUP.md`](docs/SETUP.md) para:
- Errores de memory lock en Elasticsearch
- Fallos de healthcheck de MinIO (binario `mc` faltante)
- Timeout en importación MITRE ATT&CK
- Problemas con nvidia-container-toolkit

---

## Documentación técnica

- [`docs/plans/2026-06-23-tim-system-design.md`](docs/plans/2026-06-23-tim-system-design.md) — diseño completo: modelo de datos STIX, contratos de API, flujos end-to-end, roadmap de modelos IA, guión de demo
- [`docs/SETUP.md`](docs/SETUP.md) — troubleshooting detallado y procedimientos de inicialización
