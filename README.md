# ALMA — Backend API (DOM 07 · SUELO)

Servidor central de **ALMA Care**, el módulo B2C del sistema **ALMA Health Intelligence System**, enfocado en salud del suelo pélvico (DOM 07 — SUELO). Provee el motor clínico, evaluaciones estandarizadas y seguimiento de progreso para pacientes y profesionales.

## 🚀 Instalación Rápida

1. **Entorno Virtual**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Base de Datos**:
   El proyecto incluye un `docker-compose.yml` para levantar PostgreSQL rápidamente:
   ```bash
   docker-compose up -d
   ```

3. **Configuración**:
   Copia el archivo `.env.example` a `.env` y configura tus variables locales.

4. **Migraciones y Datos iniciales**:
   ```bash
   export PYTHONPATH=$PYTHONPATH:.
   alembic upgrade head
   python app/db/seeds.py
   ```

## 🧪 Sistema de Semillas (Seeders)

El script `app/db/seeds.py` deja el sistema listo para usar. Realiza las siguientes acciones:

1.  **Limpieza**: Elimina configuraciones clínicas previas para evitar duplicados.
2.  **Targets**: Configura la segmentación clínica (Todas, Embarazadas, Post-parto, Menopausia, Deportista).
3.  **Formularios Clínicos Reales** (DOM 07 — SUELO):
    *   **ICIQ-SF**: Cuestionario internacional de incontinencia con scoring automático.
    *   **PFDI-20**: Inventario de disfunción pélvica (Sección POPDI-6).
4.  **Entorno de Prueba**: Crea una usuaria de prueba (`ana@alma.com`) con historial de 4 semanas de snapshots clínicos para que gráficas y progreso sean visibles inmediatamente.

## 🛠️ Ejecución
```bash
uvicorn app.main:app --reload --port 8001
```
