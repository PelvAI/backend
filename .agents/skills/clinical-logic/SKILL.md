---
name: backend-clinical-logic
description: Detailed instructions for the Backend Clinical Engine, including ScoringEngine implementation, formula evaluation with simpleeval, and Alembic migrations.
---

# Backend: Clinical Logic & Scoring (Template)

**Estado**: [ ] Estructura Inicial | [ ] Completado Parcial | [ ] Finalizado

## 🏗️ 1. Arquitectura Core
*Describe aquí los patrones de diseño principales del backend (Ej: Repository Pattern, Services, etc.)*
- **Framework**: FastAPI (Async)
- **ORM**: SQLAlchemy 2.0
- **Validación**: Pydantic v2

## 📚 Índice de Documentación Detallada
Para evitar alucinaciones y errores, consulta estos archivos específicos:
- [Mapa de Endpoints API](file:///Users/kid/code/pelvia/backend/.agents/skills/clinical-logic/endpoints.md): Lista completa de rutas, parámetros y respuestas.
- [Esquema de Base de Datos](file:///Users/kid/code/pelvia/backend/.agents/skills/clinical-logic/database-schema.md): Modelos SQLAlchemy y relaciones.
- [Lógica del Scoring Engine](file:///Users/kid/code/pelvia/backend/.agents/skills/clinical-logic/scoring-logic.md): Detalles de simpleeval y reglas de negocio.

## 📦 2. Módulos Clave
*Define qué hace cada carpeta/archivo importante para que el Agente sepa dónde tocar.*
- `app/models/`: [ ] Definición de tablas
- `app/services/`: [ ] Lógica de negocio (ej: `scoring.py`)
- `app/api/`: [ ] Rutas y Endpoints

## 📝 3. Convenciones Locales
*Guía de nombres y estilos técnicos específicos para este repo.*
- **Nombres**: [snake_case]
- **Tipado**: Uso obligatorio de Type Hints (Python 3.10+)
- **Migraciones**: [ ] Reglas para Alembic

## ⚙️ 4. Workflows (Paso a Paso)
*Instrucciones para tareas comunes.*
- **Levantar local**: `docker-compose up`
- **Correr Tests**: `pytest`
- **Nueva Migración**: `alembic revision --autogenerate -m "desc"`

## ⚠️ 5. Gotchas & Reglas de Oro
- *Ej: No usar `sync` sessions en endpoints `async`.*
- *Ej: Recordar actualizar los esquemas de Pydantic al cambiar un modelo.*
