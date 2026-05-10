# 🌸 Vela Backend API

Este es el servidor central de **Vela**, una plataforma DTx (Digital Therapeutics) especializada en salud pélvica. Proporciona el motor clínico, la gestión de planes de entrenamiento y el sistema de scoring para pacientes y profesionales.

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
   Copia el archivo `.env.example` a `.env` y configura tus variables locales (DB_URL, etc.).

4. **Migraciones y Datos iniciales**:
   ```bash
   export PYTHONPATH=$PYTHONPATH:.
   alembic upgrade head
   python app/db/seeds.py
   ```

## 🧪 Sistema de Semillas (Seeders)

El script `app/db/seeds.py` es el encargado de dejar el sistema listo para usar. Realiza las siguientes acciones técnicas:

1.  **Limpieza**: Elimina cualquier configuración clínica previa para evitar duplicados.
2.  **Targets**: Configura la segmentación clínica (Todas, Embarazadas, Post-parto, Menopausia, Deportista).
3.  **Formularios Reales**: Carga las evaluaciones estándar de la industria:
    *   **ICIQ-SF**: Cuestionario internacional de incontinencia con scoring automático.
    *   **PFDI-20**: Inventario de disfunción pélvica (Sección POPDI-6).
4.  **Entorno de Prueba**: Crea una usuaria de prueba (`ana@vela.com`) con un historial de 4 semanas de "Snapshots" clínicos para que las gráficas y el progreso sean visibles inmediatamente en la App.

## 🛠️ Ejecución
```bash
uvicorn app.main:app --reload --port 8001
```
