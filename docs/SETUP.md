# Plataforma TIM — Guía de Configuración Inicial

Este documento cubre todo lo que un operador necesita para poner en marcha la plataforma de
Gestión de Inteligencia de Amenazas (TIM) desde una máquina Ubuntu 22.04 limpia. Seguir las
secciones en orden en la primera ejecución.

---

## 1. Requisitos previos

Antes de ejecutar cualquier comando de configuración, verificar que los siguientes componentes
estén presentes:

| Requisito | Versión mínima | Confirmado en máquina de desarrollo |
|-----------|---------------|--------------------------------------|
| Docker Engine | 24.0 | 29.5.2 |
| Docker Compose v2 | v2.0 | v5.1.4 |
| GPU NVIDIA con driver | cualquier CUDA | RTX 3050, driver 580.159.03 |
| nvidia-container-toolkit | latest | Ver Sección 2 |

**Verificar las versiones:**

```bash
docker version --format '{{.Server.Version}}'
docker compose version
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
```

---

## 2. Instalación del NVIDIA Container Toolkit (Ubuntu 22.04)

El servicio `ollama` requiere el NVIDIA Container Toolkit para que Docker pueda pasar la GPU
al contenedor. Sin él, `docker compose --profile platform up -d` fallará en el servicio ollama.

**Instalar nvidia-container-toolkit:**

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

**Verificar la instalación:**

```bash
docker run --rm --gpus all ubuntu nvidia-smi
```

Debería aparecer la tabla estándar de `nvidia-smi` dentro del contenedor. Si el comando falla,
volver a ejecutar `sudo nvidia-ctk runtime configure --runtime=docker` y reiniciar Docker.

---

## 3. Secuencia de primera ejecución

Ejecutar estos cuatro comandos en orden desde la raíz del proyecto:

```bash
# Paso 1: Generar .env con UUIDs y contraseñas
./scripts/setup-env.sh

# Paso 2: Iniciar los 8 servicios de la plataforma
docker compose --profile platform up -d

# Paso 3: Descargar los modelos de Ollama (llama3.2:3b + nomic-embed-text)
./scripts/init-models.sh

# Paso 4: Esperar hasta que la importación de MITRE ATT&CK finalice y verificar TAXII
./scripts/verify-platform.sh
```

**Qué hace cada paso:**

- **Paso 1 — `setup-env.sh`:** Copia `.env.example` a `.env` y reemplaza los cuatro valores
  marcadores (`OPENCTI_ADMIN_TOKEN`, `CONNECTOR_MITRE_ID`, `RABBITMQ_PASSWORD`,
  `MINIO_SECRET_KEY`) con UUIDs y contraseñas alfanuméricas de 24 caracteres generadas
  automáticamente. Idempotente: una segunda ejecución termina sin sobrescribir `.env`.

- **Paso 2 — `docker compose up`:** Inicia elasticsearch, redis, rabbitmq, minio, opencti,
  connector-mitre, ollama y chromadb. Las dependencias de salud garantizan el orden correcto
  de inicio. El conector MITRE ATT&CK comienza a importar en segundo plano una vez que
  OpenCTI está disponible.

- **Paso 3 — `init-models.sh`:** Espera a que Ollama esté listo y descarga `llama3.2:3b`
  (extracción e informes) y `nomic-embed-text` (embeddings). Puede ejecutarse en paralelo
  con la importación de MITRE.

- **Paso 4 — `verify-platform.sh`:** Consulta la API GraphQL de OpenCTI cada 30 segundos
  hasta que haya más de 100 objetos ATT&CK de tipo attack-pattern (la importación completa
  entrega 600–900+ objetos entre Enterprise, Mobile, ICS y CAPEC). También verifica que el
  endpoint TAXII 2.1 devuelva HTTP 200. Termina con error descriptivo tras 15 minutos.

---

## 4. Opcional: token de geolocalización IpInfo

El servicio `connector-ipinfo` enriquece los observables IP con datos de geolocalización, lo
que popula el widget de mapa mundial en el dashboard de OpenCTI. Requiere una cuenta gratuita
en ipinfo.io (50 000 consultas/mes en el nivel gratuito).

**Obtener un token gratuito:**

1. Registrarse en https://ipinfo.io/signup
2. Copiar el token del dashboard y añadirlo a `.env`:

```bash
IPINFO_TOKEN=your_token_here
```

3. Reiniciar el conector:

```bash
docker compose --profile platform up -d connector-ipinfo
```

El conector enriquecerá automáticamente los observables IP a medida que se creen o actualicen.
Esperar unos minutos para que los IPs existentes sean procesados y el mapa mundial se complete.

**Clave de API de NVD (opcional):** El servicio `connector-cve` sincroniza la base de datos
completa de CVEs desde NVD sin necesidad de clave, pero NVD limita las solicitudes no
autenticadas. Para una sincronización inicial más rápida, obtener una clave gratuita en
https://nvd.nist.gov/developers/request-an-api-key y configurar:

```bash
CVE_NVD_API_KEY=your_key_here
```

---

## 5. Solución de problemas

### Problema A — Elasticsearch falla al iniciar con error de bloqueo de memoria

**Síntoma:** Los logs de Elasticsearch contienen "unable to lock memory":

```bash
docker compose --profile platform logs elasticsearch | grep -i "lock"
```

**Causa:** El daemon Docker en Ubuntu 22.04 puede no tener `LimitMEMLOCK=infinity`
configurado en su unidad systemd, lo que impide que Elasticsearch bloquee memoria del heap.

**Solución:**

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
printf '[Service]\nLimitMEMLOCK=infinity\n' | sudo tee /etc/systemd/system/docker.service.d/override.conf
sudo systemctl daemon-reload && sudo systemctl restart docker
```

Luego reiniciar la plataforma:

```bash
docker compose --profile platform up -d
```

---

### Problema B — El healthcheck de MinIO falla (comando mc no disponible en la imagen)

**Síntoma:** `docker compose --profile platform ps` muestra MinIO como `unhealthy`; como
consecuencia, OpenCTI nunca inicia (depende de que MinIO esté saludable).

**Causa:** Algunas versiones de la imagen `minio/minio:latest` no incluyen el cliente `mc`.
El healthcheck por defecto (`CMD mc ready local`) falla siempre.

**Solución:** Reemplazar el healthcheck de MinIO en `docker-compose.yml`:

```yaml
# Cambiar esto:
test: ["CMD", "mc", "ready", "local"]

# Por esto:
test: ["CMD-SHELL", "curl -f http://localhost:9000/minio/health/live || exit 1"]
```

Luego reiniciar:

```bash
docker compose --profile platform up -d
```

---

### Problema C — verify-platform.sh agota el tiempo de espera (importación MITRE en curso)

**Síntoma:** El script imprime `ERROR: 15-minute timeout` antes de completarse.

**Causa:** La importación de MITRE ATT&CK tarda más de 15 minutos en esta máquina, o el
servicio `connector-mitre` no pudo iniciarse o conectarse a OpenCTI.

**Solución:**

1. Verificar si la importación sigue progresando:
   ```bash
   docker compose --profile platform logs connector-mitre
   ```

2. Si el conector está ejecutándose e importando, simplemente volver a ejecutar el script:
   ```bash
   ./scripts/verify-platform.sh
   ```

3. Si `connector-mitre` no está iniciando, verificar que OpenCTI esté saludable:
   ```bash
   docker compose --profile platform ps
   ```
   Si OpenCTI aparece como `unhealthy`, revisar sus logs:
   ```bash
   docker compose --profile platform logs opencti
   ```

---

## 6. Operación diaria — encender y apagar

### Encender la plataforma

Desde la raíz del proyecto:

```bash
docker compose --profile platform --profile feeds up -d
```

Esto inicia los 17 servicios (plataforma + feeds). En arranques posteriores a la primera
configuración no es necesario volver a ejecutar los scripts de la Sección 3.

**Verificar que todo está corriendo:**

```bash
docker compose ps
```

Todos los servicios deben mostrar `Up` o `Up (healthy)` en la columna de estado. Los feeds
comienzan a consultar fuentes de inteligencia automáticamente en los primeros 5 minutos.

### Apagar la plataforma

```bash
docker compose --profile platform --profile feeds down
```

Los datos **no se pierden**: IOCs, reportes de OpenCTI, briefings y modelos de Ollama
permanecen en los volúmenes de Docker y están disponibles al volver a encender.
