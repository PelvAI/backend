# PelvIA Backend: Mapa de Endpoints API (v1)

Este archivo sirve como referencia estricta para evitar la creación de endpoints redundantes o el uso incorrecto de parámetros.

## 📋 Grupos de Endpoints

### 1. Admin Forms (`/api/v1/admin`)
Gestión completa de la estructura de cuestionarios.
- `GET /forms`: Listado paginado con filtros (`status`, `target_code`, `search`).
- `POST /forms`: Crear nuevo formulario (DRAFT).
- `GET /forms/{id}`: Detalle completo con secciones, preguntas y reglas cargadas.
- `PUT /forms/{id}`: Actualizar metadatos.
- `POST /forms/{id}/sections`: Agregar sección.
- `POST /sections/{id}/questions`: Agregar pregunta con opciones.
- `POST /forms/{id}/rules`: Agregar regla de scoring global o por target.
- `GET /targets`: Listado de segmentos de usuario disponibles.

### 2. Clinical (`/api/v1/clinical`)
Endpoints para la aplicación de usuario final.
- `GET /forms`: Formularios disponibles para el usuario según sus targets.
- `GET /forms/{code}/schema`: Estructura optimizada para renderizado móvil.
- `POST /submissions/start`: Iniciar una nueva entrega.
- `POST /submissions/{id}/finalize`: Procesar respuestas, calcular puntaje y generar alertas.
- `GET /snapshots/history`: Historial de estados clínicos del usuario.

### 3. Autenticación (`/api/v1/auth`)
- `POST /login`: Mock de Firebase UID. Crea perfil y billetera si no existe.
- `GET /me`: Perfil del usuario actual.

### 4. Otros Módulos
- `/training`: Planes y ejercicios.
- `/gamification`: Billetera, XP y tienda.
- `/ai`: Chat interactivo y consultas.
- `/education`: Contenido educativo.

---

## ⚠️ Reglas de Oro para Endpoints
- **Paginación**: Siempre usar `skip` y `limit` en listados.
- **Eager Loading**: Usar `selectinload` para relaciones anidadas para evitar errores de Async.
- **Validación**: Cada endpoint debe tener un schema de Pydantic para entrada y salida.
