---
layout: home
title: Inicio
---

# TIM — Manual de Usuario

**Plataforma de Gestión de Inteligencia de Amenazas**

Esta documentación cubre casos de uso prácticos de la plataforma TIM: cómo navegar OpenCTI, correlacionar actores con malware, explorar técnicas ATT&CK y generar briefings de inteligencia.

---

## Casos de Uso
- [APT39 — Recorrido Remexi y MechaFlounder](casos-de-uso/apt39-remexi-mechaFlounder.md)

## Guías
- [Manual de Usuario](index.md)
- [Instalación y Configuración](SETUP.md)

## Referencia
- [Documento de Diseño del Sistema](plans/2026-06-23-tim-system-design.md)

---

## Infraestructura de la Plataforma

| Servicio | URL | Descripción |
|----------|-----|-------------|
| Dashboard | `https://localhost` | Panel principal SOC |
| OpenCTI | `http://localhost:8080` | Plataforma de inteligencia |
| Kibana | `http://localhost:5602` | Visualización de IOCs en Elasticsearch |
| Búsqueda semántica | `http://localhost:8002` | Motor de búsqueda por embeddings |
| Generador de briefings | `http://localhost:8003` | Briefings en PDF con LLM local |
