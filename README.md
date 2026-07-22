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

## 🤖 Integração com Chatbot (PelvAI)

O backend é o **único** cliente do chatbot. Frontend e admin-panel nunca chamam a porta `:8000`.

### Variáveis (ver `.env.example`)

| Variável | Descrição |
|----------|-----------|
| `CHATBOT_BASE_URL` | URL do PelvAI (ex. `http://127.0.0.1:8000` ou `http://chatbot:8000` no Compose) |
| `CHATBOT_SERVICE_TOKEN` | Segredo partilhado com `ALMA_SERVICE_TOKEN` do ChatBot |
| `CHATBOT_TIMEOUT_SECONDS` | Timeout HTTP (default 120; RAG+LLM pode demorar) |
| `CHATBOT_REQUIRED` | Se `true`, `/ai/chat/{id}/send` devolve 503/502 quando o chatbot falha |

### Endpoints novos / alterados

| Path | Papel |
|------|-------|
| `POST /api/v1/ai/chat/{id}/send` | Monta `clinical_context`, chama chatbot, grava resposta + `meta` RAG |
| `GET /api/v1/ai/chat/active` | Última conversa do utilizador |
| `POST /api/v1/ai/feedback/{msg_id}` | Feedback 👍/👎 em `ai_messages.meta` |
| `GET/POST/... /api/v1/admin/rag/*` | Proxy autenticado → documentos / reindex / analytics do chatbot |
| `GET /api/v1/admin/chat/conversations` | Monitor staff (fonte de verdade = BD Alma) |

**Fonte de verdade RAG (catálogo de docs):** chatbot (`document_registry`). A tabela Alma `ai_rag_sources` é legado e não é sincronizada no MVP.

### Smoke local

```bash
# Com chatbot a correr na 8000 e o mesmo token em ambos os .env:
python -c "
import asyncio
from app.services.chatbot_client import ChatbotClient
async def main():
    print(await ChatbotClient().health())
asyncio.run(main())
"
```
