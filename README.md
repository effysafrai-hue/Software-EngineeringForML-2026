# SE_ML_effy: Campus AI Calendar & Community Hub

Full-stack application combining smart AI scheduling, shared group calendars, course-grounded conversational AI, real-time WebSocket notifications, and an anonymous student forum.

---

## 🌐 Quick Access Links

| Service / Interface | URL | Description |
| :--- | :--- | :--- |
| **Frontend Application** | [http://localhost:5173](http://localhost:5173) | Main UI: Calendar, AI Assistant, Shared Calendars, Forum |
| **Backend API Root** | [http://localhost:8000](http://localhost:8000) | FastAPI application root |
| **Swagger UI Documentation** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive API exploration & testing |
| **ReDoc Documentation** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Alternative structured API documentation |
| **API Health Check** | [http://localhost:8000/health](http://localhost:8000/health) | System health & readiness status |
| **OpenAPI Specification** | [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json) | Raw OpenAPI JSON schema |
| **Ollama Local LLM Service** | [http://localhost:11434](http://localhost:11434) | Local LLM inference server (Llama 3.1) |
| **Static Uploads Directory** | [http://localhost:8000/uploads/](http://localhost:8000/uploads/) | Hosted media attachments (images/videos) |

---

## 🚀 Quick Start

### 1. Start All Services with Docker Compose
```bash
docker compose up -d --build
```

### 2. View Service Logs
```bash
docker compose logs -f backend
docker compose logs -f frontend
```

### 3. Run Automated Tests
```bash
# Run a single suite (tests live at /app/tests inside the container)
docker compose exec backend pytest -v tests/test_forum.py

# Run all backend tests
docker compose exec backend pytest -v
```

### 4. Database Migrations
```bash
# Run migrations
docker compose exec backend alembic upgrade head

# Rollback one migration
docker compose exec backend alembic downgrade -1
```

---

## 🤖 Local LLM Configuration

The assistant runs entirely on the local Ollama model — there is no keyword-matching
fallback, so a chat request fails loudly (HTTP 503) if the model is unreachable or
was never pulled. `docker compose up` pulls `OLLAMA_MODEL` before the backend starts.

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `ollama` | `ollama` or `gemini` |
| `OLLAMA_MODEL` | `llama3.1:8b` | Must be a tool-calling model |
| `OLLAMA_NUM_CTX` | `8192` | Context window per request. The agent prompt (rules + course grounding + tool schemas) does not fit in Ollama's 4096-token default, and an over-long prompt is truncated silently — losing the tool definitions |
| `OLLAMA_TIMEOUT` | `300` | Seconds. A cold model load plus a multi-step reschedule takes several round-trips |
| `OLLAMA_TEMPERATURE` | `0.0` | Greedy decoding; scheduling is extraction, not creative writing |
| `OLLAMA_MAX_TOOL_TURNS` | `4` | Tool-calling rounds before the model is asked for a final answer with the tools withheld |

Troubleshooting the chat endpoint:

```bash
# Is the model present?
docker compose exec ollama ollama list

# What did the agent send and get back? Every tool call is logged.
docker compose logs -f backend | grep -E "OLLAMA|AI_AGENT"
```

The chat tests (`tests/test_chat.py`, `tests/test_courses.py`) call the live model
rather than a mock, so they are slow and depend on the model's instruction
following. If a scheduling test fails on `llama3.1:8b`, a larger quantisation
(`llama3.1:8b-instruct-q8_0`) or `qwen2.5:7b-instruct` follows tool schemas more
reliably: `OLLAMA_MODEL=qwen2.5:7b-instruct docker compose up -d`.

---

## 🏗️ Architecture & Features

- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Lucide Icons.
- **Backend**: FastAPI (Python 3.12), SQLAlchemy 2.0, Alembic, SlowAPI (rate limiting).
- **Database**: PostgreSQL 16 with `pgvector` extension.
- **AI & LLM**: Switchable dual provider (`LLM_PROVIDER=ollama|gemini`) with priority queue worker pool (`asyncio.PriorityQueue`).
- **Real-Time**: WebSocket notification hub (`/ws/notifications`) with auto-reconnect and live reminder broadcasts.
- **Community Forum**: Anonymous posting, media upload validation, post/comment threading, and calendar event conversion.
