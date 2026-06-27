# Threat Intelligence Management (TIM) System — Design Document

**Date:** 2026-06-23
**Author:** Researcher
**Status:** Draft — In Progress
**Target:** SOC client demo + product proposal

---

## 1. Executive Summary

A local Threat Intelligence Management system that demonstrates both operational maturity and AI-augmented intelligence capabilities. The system combines OpenCTI (industry-standard knowledge graph platform) with custom AI services powered by local LLMs — eliminating data egress risk while providing capabilities most commercial TIM implementations lack.

**Core differentiators:**
- 100% local AI processing — no IOC sent to external APIs (VirusTotal, etc.)
- IOC extraction from unstructured text (PDFs, blogs, advisories) via local LLM
- Semantic similarity search via local embeddings — finds related threats without exact IOC match
- Automated executive briefing generation from live intelligence data
- Full data sovereignty — all processing on-premises

---

## 2. Hardware Baseline

| Resource | Available | Allocated to TIM | Buffer |
|---|---|---|---|
| CPU | 16 vCPUs | 12 | 4 |
| RAM | 31 GB | 14 GB | 17 GB |
| Disk | 112 GB free | 28 GB | 84 GB |
| GPU | RTX 3050, 4 GB VRAM | 4 GB (Ollama) | — |
| OS | Ubuntu 22.04 | — | — |
| Runtime | Docker 29.5 + Compose v5 | — | — |

---

## 3. Architecture Overview

The system is organized into four decoupled layers:

```
┌─────────────────────────────────────────────────────────────┐
│                     CAPA DE FUENTES                         │
│                                                             │
│  Estructuradas                    No estructuradas          │
│  URLhaus · MalwareBazaar          PDFs de threat reports    │
│  ThreatFox · Feodo Tracker        Blogs de investigadores   │
│  AlienVault OTX · CIRCL           Advisories CISA/CERT      │
└────────────┬────────────────────────────┬───────────────────┘
             │                            │
             ▼                            ▼
┌────────────────────────┐   ┌────────────────────────────────┐
│   CAPA DE INGESTA      │   │     CAPA AI (DIFERENCIADOR)    │
│   (custom Python)      │   │     (custom Python + Ollama)   │
│                        │   │                                │
│  feed-orchestrator     │   │  intel-extractor               │
│  · descarga feeds      │   │  · lee PDF/texto/URL           │
│  · normaliza a STIX    │   │  · LLM extrae IOCs + TTPs      │
│  · deduplica           │   │  · produce STIX 2.1            │
│  · puntúa confianza    │   │                                │
│                        │   │  semantic-engine               │
│                        │   │  · embeddings de IOCs          │
│                        │   │  · búsqueda por similitud      │
│                        │   │  · clustering de campañas      │
└────────────┬───────────┘   └──────────────┬─────────────────┘
             │                              │
             └──────────────┬───────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              CAPA DE PLATAFORMA — OpenCTI                   │
│                                                             │
│  Knowledge Graph · STIX 2.1 nativo · MITRE ATT&CK          │
│  Correlación · Actores · Campañas · Malware · TTPs          │
│  TAXII Server · REST API · Dashboards nativos               │
│                                                             │
│  [Elasticsearch]  [Redis]  [RabbitMQ]  [MinIO]             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           CAPA DE PRESENTACIÓN (custom)                     │
│                                                             │
│  briefing-generator (LLM local)                            │
│  · resúmenes ejecutivos desde datos de OpenCTI             │
│                                                             │
│  SOC Dashboard (React + Vite)                              │
│  · feed health · top threats · actor timelines             │
│  · búsqueda semántica de IOCs                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Component Details

### 4.1 OpenCTI Platform Layer

**Stack interno (5 servicios orquestados):**

```
┌─────────────────────────────────────────────┐
│              OpenCTI Platform               │
│  (Node.js — GraphQL API + business logic)   │
│  Port: 8080                                 │
└──────┬──────┬──────┬──────┬─────────────────┘
       │      │      │      │
       ▼      ▼      ▼      ▼
  [ES 8]  [Redis] [RabbitMQ] [MinIO]
  Graph   Cache   Message    File
  Store   + Auth  Queue      Storage
  4GB RAM 1GB     1GB        1GB
```

| Servicio | Rol | RAM asignada |
|---|---|---|
| **Elasticsearch 8** | Almacena todos los objetos STIX 2.1 como documentos de grafo | 4 GB (heap 2-4 GB) |
| **Redis** | Caché de sesiones + event streams (notifica a workers de nuevos IOCs) | 1 GB |
| **RabbitMQ** | Cola de mensajes entre conectores y plataforma — desacopla ingesta de procesamiento | 1 GB |
| **MinIO** | Almacenamiento de archivos adjuntos (PDFs, muestras) — S3 compatible local | 1 GB |
| **OpenCTI Platform** | Node.js — GraphQL API, lógica de negocio, UI | 2 GB |

**Configuración demo (ajustada para no desperdiciar RAM):**
```yaml
elasticsearch:
  ES_JAVA_OPTS: "-Xms2g -Xmx4g"

opencti-platform:
  APP__TELEMETRY__METRICS__ENABLED: "true"
  REDIS__TRIM_SLEEP_TIME: 10000
```

**Capacidades incluidas sin desarrollo adicional:**
- UI completa con knowledge graph visualization
- TAXII 2.1 server (compartir inteligencia en estándar abierto)
- REST API + GraphQL API (consumida por servicios custom)
- MITRE ATT&CK framework pre-cargado
- Sistema de roles y permisos
- 200+ conectores oficiales disponibles

**Nota de arquitectura:** OpenCTI usa STIX 2.1 como modelo de datos nativo (no como formato de exportación). Todo objeto insertado via API es STIX internamente, por lo que el TAXII server lo sirve sin transformación.

### 4.2 Feed Orchestrator (custom)

**Responsabilidad:** Descargar inteligencia estructurada de fuentes externas, normalizarla a STIX 2.1 y entregarla a OpenCTI.

**Pipeline interno:**
```
Downloader (APScheduler) → Normalizer → Deduplicator + Scorer → OpenCTI Client (pycti)
```

**Fuentes configuradas:**

| Feed | Formato origen | Cadencia | Contenido |
|---|---|---|---|
| URLhaus (Abuse.ch) | CSV / JSON | Cada 1h | URLs distribuyendo malware activo |
| MalwareBazaar | JSON API | Cada 2h | Hashes + familias de malware |
| ThreatFox | JSON API | Cada 2h | IOCs de malware recientes con contexto |
| Feodo Tracker | CSV | Cada 4h | IPs de servidores C2 de botnets |
| AlienVault OTX | JSON API | Cada 6h | Pulsos con contexto de actores/campañas |
| CIRCL MISP | MISP format | Cada 12h | Eventos curados, alta calidad |

**Confidence scoring:**
```python
score = (
    feed_count * 25 +        # cuántos feeds independientes lo reportan
    recency_bonus +          # más reciente = más relevante
    feed_quality_weight      # fuentes curadas pesan más
)  # rango: 0-100
```

**Stack técnico:**
- Python 3.12
- `pycti` — cliente oficial OpenCTI (maneja idempotencia + merge automático)
- `APScheduler` — scheduling de descargas por feed
- `stix2` — construcción de objetos STIX 2.1 válidos
- Redis — caché de hashes vistos para deduplicación O(1)

### 4.3 AI Layer

#### 4.3.1 intel-extractor

**Responsabilidad:** Extraer IOCs y TTPs de documentos no estructurados (PDFs, URLs, texto libre) y producir objetos STIX 2.1.

**Pipeline:**
```
Document Parser (PDF/URL/texto) → LLM llama3.2:3b → STIX Builder → OpenCTI (pycti)
```

**Qué extrae el LLM del texto:**
- IOCs: IPs, dominios, hashes MD5/SHA1/SHA256, URLs, emails
- Threat actor mencionado
- Técnicas ATT&CK (lenguaje natural → código Txxxx)
- Malware families
- Industrias objetivo y fechas de actividad

**Restricción de contexto:** `llama3.2:3b` soporta ~8K tokens. Documentos largos se procesan por **chunking con solapamiento** — fragmentos consecutivos comparten contexto para no perder IOCs en los bordes. Los resultados de todos los chunks se consolidan y deduaplican.

**Stack:** Python 3.12 · `pypdf2` / `trafilatura` (parsing) · `ollama` Python SDK · `stix2` library

---

#### 4.3.2 semantic-engine

**Responsabilidad:** Indexar todos los IOCs como vectores y responder búsquedas por similitud semántica — sin requerir coincidencia exacta.

**Pipeline:**
```
Texto / IOC → nomic-embed-text (Ollama) → vector 768D → ChromaDB → top-K similares
```

**Casos de uso:**
- Búsqueda en lenguaje natural: *"malware con DNS tunneling hacia .ru"*
- Clasificación de IOC desconocido: *"85% similar a campaña Emotet Q1 2026"*
- Pivoting por comportamiento: encontrar campañas relacionadas sin IOC en común

**Stack:** Python 3.12 · `ollama` Python SDK (`nomic-embed-text`) · ChromaDB (vector DB local) · FastAPI (endpoint de búsqueda)

---

#### 4.3.3 briefing-generator

**Responsabilidad:** Generar resúmenes ejecutivos en lenguaje natural desde los datos de OpenCTI — para audiencia no técnica (CISO, gerencia).

**Pipeline:**
```
Scheduler / trigger → OpenCTI GraphQL → datos 24-72h → LLM llama3.2:3b → texto ejecutivo
```

**Datos consultados a OpenCTI:**
- Nuevos IOCs en el período
- Actores con actividad reciente
- Campañas en curso
- Top 5 técnicas ATT&CK observadas
- Sectores más afectados

**Output:** párrafo de 200-300 palabras, tono profesional, exportable a PDF o visible en dashboard.

**Stack:** Python 3.12 · `pycti` (GraphQL client) · `ollama` Python SDK · `reportlab` (PDF export)

---

**Nota compartida — Ollama:** Los tres servicios comparten una instancia de Ollama. Los modelos se cargan/descargan de GPU según demanda. `llama3.2:3b` (~2GB VRAM) e `intel-extractor` / `briefing-generator` no corren simultáneamente con `nomic-embed-text` en condiciones normales — los 4GB de VRAM son suficientes.

### 4.4 SOC Dashboard (custom)

**Responsabilidad:** Frontend orientado a la demo y al cliente — presenta los datos de OpenCTI y los servicios AI en vistas ejecutivas sin requerir conocimiento previo de la plataforma.

**Vistas:**

| Vista | Audiencia | Contenido |
|---|---|---|
| **Overview** | CISO / cliente | Feed health, IOCs 24h, top actores, top técnicas ATT&CK, geo heatmap, timeline |
| **Threat Hunt** | Analista SOC | Búsqueda semántica en lenguaje natural, resultados con score de similitud, pivot a OpenCTI |
| **Briefings** | CISO / gerencia | Resúmenes ejecutivos generados por LLM, trigger manual, export PDF |

**Fuentes de datos:**
```
OpenCTI GraphQL API  →  Overview
semantic-engine API  →  Threat Hunt
briefing-generator   →  Briefings
```

El dashboard no tiene base de datos propia — es capa de presentación pura.

**Stack:** React 18 + Vite · TanStack Query · Recharts · Leaflet · Tailwind CSS

---

## 5. Data Model & Standards

### 5.1 Objetos STIX 2.1 utilizados

**SDOs (Domain Objects):**

| Objeto | Representa | Creado por |
|---|---|---|
| `indicator` | IOC con patrón de detección y confianza | Feed Orchestrator, intel-extractor |
| `malware` | Familia de malware | intel-extractor, feeds |
| `threat-actor` | Actor de amenaza | intel-extractor, feeds |
| `intrusion-set` | APT con infraestructura y TTPs consistentes | intel-extractor, feeds |
| `campaign` | Operación de ataque en un período | intel-extractor |
| `attack-pattern` | Técnica MITRE ATT&CK (Txxxx) | intel-extractor, OpenCTI (pre-cargado) |
| `course-of-action` | Medida defensiva D3FEND | OpenCTI (pre-cargado) |
| `report` | Threat report completo procesado | intel-extractor |

**SCOs (Cyber Observables):**
`ipv4-addr` · `domain-name` · `file` (+ hashes) · `url` · `email-addr`

### 5.2 Estructura de un indicator

```json
{
  "type": "indicator",
  "spec_version": "2.1",
  "id": "indicator--3b3cf503-...",
  "name": "Feodo Tracker C2 IP",
  "indicator_types": ["malicious-activity"],
  "pattern": "[ipv4-addr:value = '185.220.101.47']",
  "pattern_type": "stix",
  "valid_from": "2026-06-23T10:00:00Z",
  "confidence": 85,
  "labels": ["c2", "botnet"],
  "external_references": [{"source_name": "Feodo Tracker"}]
}
```

El campo `confidence` (0–100) es el score calculado por el Feed Orchestrator.

### 5.3 Grafo de relaciones

```
[indicator]──"indicates"──→[malware]──"uses"──→[attack-pattern: Txxxx]
                                                        │
[campaign]──"uses"──→[malware]          "mitigates"    │
     │                                                  ▼
"attributed-to"                              [course-of-action]
     │
     ▼
[intrusion-set]──"attributed-to"──→[threat-actor]
```

### 5.4 Flujo STIX entre componentes

```
Feed Orchestrator + intel-extractor
         │  STIX 2.1 bundles (via pycti)
         ▼
   OpenCTI / Elasticsearch
         │
         ├── GraphQL API  →  SOC Dashboard + briefing-generator
         ├── TAXII 2.1    →  clientes externos (SIEM, otros TIPs)
         └── REST API     →  semantic-engine (indexación)
```

### 5.5 TAXII 2.1 — distribución estándar

OpenCTI expone un servidor TAXII 2.1 nativo. Cualquier herramienta compatible puede suscribirse y recibir inteligencia automáticamente sin integración custom.

Endpoints:
```
GET /taxii2/root/collections/              → colecciones disponibles
GET /taxii2/root/collections/{id}/objects/ → objetos STIX paginados
```

### 5.6 MITRE ATT&CK en el sistema

OpenCTI pre-carga el framework ATT&CK completo al iniciar (vía conector oficial). Cada `attack-pattern` en ATT&CK es un objeto STIX `attack-pattern` con su ID (Txxxx), descripción, y plataformas afectadas. El intel-extractor mapea menciones de texto a estos objetos existentes — no los crea, los referencia.

---

## 6. Integration Points

### 6.1 Puertos y accesibilidad

| Servicio | Puerto | Accesible desde |
|---|---|---|
| OpenCTI Platform | 8080 | Browser + servicios internos |
| Elasticsearch | 9200 | Solo interno |
| Redis | 6379 | Solo interno |
| RabbitMQ | 5672 / 15672 | Interno / browser (UI admin) |
| MinIO | 9000 / 9001 | Interno / browser (consola) |
| Ollama | 11434 | Solo interno (servicios AI) |
| ChromaDB | 8000 | Solo interno (semantic-engine) |
| intel-extractor | 8001 | Browser + servicios internos |
| semantic-engine | 8002 | Browser + servicios internos |
| briefing-generator | 8003 | Browser + servicios internos |
| SOC Dashboard | 3000 | Browser |

Todos los servicios viven en red Docker `tim-network`. Solo los puertos de browser se exponen al host.

### 6.2 Autenticación entre servicios

| Conexión | Mecanismo |
|---|---|
| Servicios Python → OpenCTI | API Token (`Authorization: Bearer <token>`) |
| OpenCTI → Elasticsearch / RabbitMQ / MinIO | Usuario/contraseña en variables de entorno |
| Servicios AI → Ollama | Sin auth (red interna privada) |
| Servicios AI → ChromaDB | Sin auth (red interna privada) |
| Browser → servicios custom | Sin auth (demo en red local) |

Credenciales gestionadas en `.env` — nunca hardcodeadas en código.

### 6.3 Contratos de API — servicios custom

**intel-extractor** `:8001`
```
POST /extract   body: {type, content}  →  {job_id, status}
GET  /jobs/{id}                        →  {status, iocs_extracted, stix_bundle_id}
GET  /health                           →  {status: "ok"}
```

**semantic-engine** `:8002`
```
POST /search    body: {query, top_k, min_score}  →  {results: [{indicator_id, name, score, opencti_url}]}
POST /index     body: {indicator: <STIX object>} →  {indexed: true}
GET  /health                                     →  {status: "ok"}
```

**briefing-generator** `:8003`
```
POST /generate  body: {period_hours, language}  →  {briefing_id, text, generated_at}
GET  /briefings                                 →  {briefings: [...]}
GET  /briefings/{id}/pdf                        →  archivo PDF
GET  /health                                    →  {status: "ok"}
```

### 6.4 Flujo de un IOC de punta a punta

```
1. feed-orchestrator descarga feed (scheduled)
2. Normaliza IOC → STIX indicator con confidence score
3. pycti inserta en OpenCTI :8080
4. OpenCTI persiste en Elasticsearch
5. semantic-engine consulta OpenCTI (pull cada 5 min)
6. Llama Ollama :11434 → embedding del indicator
7. Guarda vector en ChromaDB
8. SOC Dashboard consulta OpenCTI GraphQL (polling 60s)
9. Overview actualizado con nuevo IOC
10. Analista busca en Threat Hunt → semantic-engine :8002/search
11. Resultado con score → click abre objeto en OpenCTI
```

---

## 7. Deployment (Docker Compose)

### 7.1 Estructura de directorios

```
threat_int_mgmt/
├── docker-compose.yml
├── .env.example
├── docs/plans/
├── services/
│   ├── feed-orchestrator/   (Python + APScheduler)
│   ├── intel-extractor/     (Python + FastAPI)
│   ├── semantic-engine/     (Python + FastAPI + ChromaDB)
│   ├── briefing-generator/  (Python + FastAPI)
│   └── soc-dashboard/       (React + Vite)
└── scripts/
    ├── init-models.sh        ← descarga modelos Ollama post-arranque
    └── seed-demo-data.sh     ← precarga IOCs y actores para el demo
```

### 7.2 Servicios y orden de arranque

```
Elasticsearch → Redis → RabbitMQ → MinIO
                                      │
                                   OpenCTI  ←─── connector-mitre
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
      feed-orchestrator         Ollama + ChromaDB       soc-dashboard
                            intel-extractor
                            semantic-engine
                            briefing-generator
```

El orden se garantiza con `depends_on` + `healthcheck` en cada servicio base. OpenCTI no arranca hasta que ES, Redis, RabbitMQ y MinIO reportan healthy.

### 7.3 Inicialización (primera vez)

```bash
# 1. Copiar y configurar variables de entorno
cp .env.example .env
# editar .env: generar UUIDs para OPENCTI_ADMIN_TOKEN y CONNECTOR_MITRE_ID

# 2. Levantar el stack completo
docker compose up -d

# 3. Descargar modelos Ollama (una sola vez, ~3 GB)
./scripts/init-models.sh

# 4. Verificar que todos los servicios están healthy
docker compose ps
```

### 7.4 Variables de entorno (.env.example)

```bash
OPENCTI_BASE_URL=http://localhost:8080
OPENCTI_ADMIN_EMAIL=admin@tim.local
OPENCTI_ADMIN_PASSWORD=<strong_password>
OPENCTI_ADMIN_TOKEN=<uuid-v4>
RABBITMQ_USER=tim
RABBITMQ_PASSWORD=<password>
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=<password>
CONNECTOR_MITRE_ID=<uuid-v4>
OTX_API_KEY=                    # opcional — AlienVault OTX gratuito
```

### 7.5 Puertos expuestos al host

| URL | Servicio |
|---|---|
| http://localhost:8080 | OpenCTI (plataforma principal) |
| http://localhost:3000 | SOC Dashboard (custom) |
| http://localhost:8001 | intel-extractor API |
| http://localhost:8002 | semantic-engine API |
| http://localhost:8003 | briefing-generator API |
| http://localhost:15672 | RabbitMQ management UI |
| http://localhost:9001 | MinIO console |

---

## 8. Demo Scenarios

> **Status:** Pendiente — estructura definida, contenido por completar

Esta sección define el guión narrativo completo para la presentación al cliente SOC.
Debe contener:

### 8.1 Contexto narrativo
- Historia ficticia pero realista: "una empresa del sector financiero en Latinoamérica"
- Threat actor preseleccionado para el demo (ej. TA505, Lazarus, o grupo regional)
- Período de campaña simulada (fechas, industria objetivo, países afectados)
- Por qué este escenario es relevante para el cliente

### 8.2 Datos precargados (seed data)
- Lista de IOCs reales (de feeds públicos) que se cargan antes del demo
- Perfiles de actores y campañas que aparecerán en el grafo de OpenCTI
- Threat reports en PDF que intel-extractor habrá procesado previamente
- Estados de feeds (todos en verde, uno en amarillo para mostrar alertas)

### 8.3 Guión por escena (duración total: ~30-40 min)

**Escena 1 — "¿Qué está pasando ahora mismo?"** (~5 min)
- Abrir SOC Dashboard: Overview con feeds activos, IOCs de las últimas 24h
- Mostrar feed health, geo heatmap, top técnicas ATT&CK de la semana
- Mensaje clave: visibilidad en tiempo real sin esfuerzo manual

**Escena 2 — "Conoce a tu enemigo"** (~8 min)
- Navegar al grafo en OpenCTI: actor → campaña → malware → técnicas
- Demostrar pivoting: click en un nodo, explorar relaciones
- Mostrar timeline de actividad del actor seleccionado
- Mensaje clave: inteligencia contextual, no solo listas de IPs

**Escena 3 — "Inteligencia desde documentos"** (~7 min)
- Subir un PDF de threat report (ej. advisory CISA real)
- intel-extractor lo procesa en vivo: mostrar IOCs extraídos y técnicas ATT&CK mapeadas
- Los objetos aparecen en OpenCTI segundos después
- Mensaje clave: el sistema lee lo que los humanos escriben

**Escena 4 — "Busca sin saber exactamente qué buscar"** (~7 min)
- Abrir vista Threat Hunt en SOC Dashboard
- Escribir consulta en lenguaje natural (ej. "malware que roba credenciales bancarias")
- Mostrar resultados con scores de similitud
- Hacer click en resultado → pivot a OpenCTI
- Mensaje clave: búsqueda semántica, no solo coincidencia exacta

**Escena 5 — "El reporte que el CISO quiere leer"** (~5 min)
- Trigger manual de briefing-generator
- Mostrar texto ejecutivo generado: qué pasó, qué riesgo representa, qué hacer
- Exportar como PDF
- Mensaje clave: inteligencia accionable para tomadores de decisión, no solo para analistas

**Escena 6 — "Interoperabilidad con tu stack existente"** (~5 min)
- Mostrar endpoint TAXII 2.1 con curl o Postman
- Explicar cómo un SIEM existente consumiría este feed automáticamente
- Mencionar que todo procesamiento es local — ningún IOC salió de la red
- Mensaje clave: se integra con lo que ya tienen, y protege la información sensible

### 8.4 Preguntas frecuentes esperadas y respuestas
- "¿Qué pasa cuando un feed deja de funcionar?" → feed health + alertas en dashboard
- "¿Cómo se actualiza el modelo de ATT&CK?" → conector automático en OpenCTI
- "¿Puede conectarse a nuestro Splunk/ELK?" → sí, via TAXII 2.1 o API REST
- "¿El LLM local es tan bueno como ChatGPT?" → no para todo, pero no necesita serlo: su tarea es extracción estructurada, no conversación general
- "¿Qué tan difícil es agregar nuevos feeds?" → mostrar feed-orchestrator: agregar una fuente es implementar una clase con dos métodos

### 8.5 Checklist pre-demo
- [ ] Stack levantado y todos los servicios en estado healthy
- [ ] Modelos Ollama descargados y respondiendo
- [ ] Seed data cargada: mínimo 500 IOCs, 3 actores, 2 campañas
- [ ] PDFs de threat reports listos para subir en vivo
- [ ] OpenCTI con conector MITRE ATT&CK sincronizado
- [ ] SOC Dashboard mostrando datos reales (no vacío)
- [ ] Briefing pre-generado de las últimas 24h disponible

---

## 9. Technology Stack Summary

| Component | Technology | Role |
|---|---|---|
| **OpenCTI** | OpenCTI v6 + ES 8 + Redis + RabbitMQ + MinIO | Knowledge graph central |
| **feed-orchestrator** | Python + APScheduler | Ingesta y normalización STIX |
| **intel-extractor** | Python + Ollama (`llama3.2:3b`) | IOC extraction de texto libre |
| **semantic-engine** | Python + Ollama (`nomic-embed-text`) + ChromaDB | Búsqueda semántica |
| **briefing-generator** | Python + Ollama (`llama3.2:3b`) | Narrativas ejecutivas automáticas |
| **SOC Dashboard** | React + Vite | Frontend custom |

---

## 10. AI Model Upgrade Roadmap

El único cambio de código requerido para actualizar el modelo de extracción o generación de briefings es una línea en `config.py` del servicio correspondiente:

```python
OLLAMA_MODEL = "llama3.3:70b"  # era llama3.2:3b
```

`nomic-embed-text` (semantic-engine) no requiere actualización — ya es near-optimal para embeddings de IOCs independientemente del hardware disponible.

### Hardware actual (demo): RTX 3050 — 4 GB VRAM

Modelos activos: `llama3.2:3b` (~2 GB VRAM) + `nomic-embed-text` (~0.3 GB). No corren simultáneamente; Ollama carga y descarga según demanda. Latencia de primera respuesta incluye tiempo de carga del modelo (~3–5 s).

---

### Nivel 1 — 16–24 GB VRAM (RTX 3090/4090, A10, L4)

| Modelo | VRAM aprox. | Caso de uso prioritario |
|--------|------------|------------------------|
| `llama3.1:8b` | ~8 GB | Primera actualización recomendada — JSON estructurado significativamente más fiable |
| `mistral-nemo:12b` | ~14 GB | Excelente adherencia a JSON-schema; óptimo para intel-extractor |
| `qwen2.5:14b` | ~16 GB | Familia Qwen 2.5 lidera benchmarks de extracción estructurada open-source |
| `llama3.2:11b-vision` | ~12 GB | Añade comprensión de imágenes — útil para PDFs escaneados |

---

### Nivel 2 — 40–80 GB VRAM (A100 40/80 GB, 2× RTX 4090, A6000 48 GB)

| Modelo | VRAM aprox. | Caso de uso prioritario |
|--------|------------|------------------------|
| `qwen2.5:72b` | ~42 GB Q4 | **Recomendado para producción** — mejor open-source en extracción JSON estructurada según benchmarks |
| `llama3.3:70b` | ~40 GB Q4 | Calidad cercana a GPT-4; ideal para briefings ejecutivos de alta calidad |
| `mixtral:8x7b` | ~28 GB Q4 | Arquitectura MoE — alta velocidad por token; adecuado para documentos largos chunkeados |
| `deepseek-r1:70b` | ~40 GB Q4 | Modelo de razonamiento; útil como capa de validación post-extracción |

---

### Nivel 3 — 160+ GB VRAM (cluster multi-GPU H100/A100)

| Modelo | VRAM aprox. | Nota |
|--------|------------|------|
| `llama3.1:405b` | ~200 GB Q4 | Mejor modelo open-weights disponible; calidad GPT-4 Turbo |

---

### Opciones especializadas en ciberseguridad

**Fine-tuning sobre corpus STIX 2.1:** ajustar `llama3.1:8b` con pares {informe de amenazas → bundle STIX anotado}. MITRE y CISA publican corpus CTI públicos aptos para este propósito. Un modelo fine-tuned de 8B supera a generalistas de 70B en la tarea específica de extracción CTI.

**Filigran Import Document AI on-prem:** `filigran/import-document-ai-webservice` es el modelo propietario de Filigran/OpenCTI diseñado específicamente para extracción STIX. Requiere credenciales de cuenta Filigran (registro Docker privado) y mínimo 8 GB VRAM GPU / 16 GB RAM CPU. La versión cloud (`importdoc.ariane.filigran.io`) no es compatible con el constraint de soberanía de datos de este proyecto (ningún IOC o documento sale de la red local).

---

## 11. Open Questions

- [ ] ¿Qué feeds gratuitos se priorizan para el demo?
- [ ] ¿El dashboard custom reemplaza o complementa el UI nativo de OpenCTI?
- [ ] ¿Se implementa autenticación en el demo o se asume red interna?
- [ ] ¿Qué threat actors/campañas se precargan para el demo narrative?
