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
| **Ollama Local LLM Service** | [http://localhost:11434](http://localhost:11434) | Local LLM fallback, only with `--profile ollama` (Llama 3.1) |
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
# Everything (default)
docker compose exec backend pytest -v

# A single suite (tests live at /app/tests inside the container)
docker compose exec backend pytest -v tests/test_forum.py
```

Tests that call a real model are marked `live_llm`. Either half can be run on
its own:

| Command | Runs | Notes |
| :--- | :--- | :--- |
| `pytest` | Everything | Needs `GEMINI_API_KEY` |
| `pytest --no-ai` | Only tests that never touch a model | Fast, offline, no quota. A failure is a real defect |
| `pytest --ai-only` | Only the live-model tests | Slow; a failure may just mean the model had an off day |

```bash
docker compose exec backend pytest -v --no-ai
docker compose exec backend pytest -v --ai-only
```

The flags are defined in `tests/conftest.py` and are equivalent to
`-m "not live_llm"` and `-m live_llm`.

Two things to know about the live half: on a free-tier key it can exceed the
requests-per-minute quota and return 429s (run it a file at a time if so), and
`tests/test_courses.py` is marked live at module level because its seeding
fixture calls the embeddings endpoint, not only because of the assertions.

### 4. Database Migrations
```bash
# Run migrations
docker compose exec backend alembic upgrade head

# Rollback one migration
docker compose exec backend alembic downgrade -1
```

---

## 🤖 LLM Configuration

The assistant needs a tool-calling model and has no keyword-matching fallback, so a
chat request fails loudly (HTTP 503) rather than faking an answer when the provider
is unreachable. Two providers are supported, selected by `LLM_PROVIDER`.

### Gemini (default)

Set `GEMINI_API_KEY` in `.env` and start normally — no model download, no local RAM.

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `gemini` | `gemini` or `ollama` |
| `GEMINI_API_KEY` | *(none)* | Required. Without it every chat request returns HTTP 503 |
| `GEMINI_MODEL` | `gemini-3.6-flash` | The current flash model. Older ids (2.5, 2.0, 1.5) are being closed to new projects and answer `NOT_FOUND` at call time even though `list_models()` still lists them — the client detects that, retires the id for the process, and walks back through `FALLBACK_GEMINI_MODELS` |

### Ollama (local fallback)

Runs the model in-container, so it needs roughly **5 GB of free RAM in the Docker
VM**. Below that the `llama-server` runner is OOM-killed mid-generation and chat
returns `llama-server process has terminated: signal: killed`. Check with
`docker compose exec ollama free -h` before choosing this path.

```bash
LLM_PROVIDER=ollama docker compose --profile ollama up -d
```

The model download runs in the `ollama-pull` container; chat returns HTTP 503 until
it completes (`docker compose logs -f ollama-pull`).

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `OLLAMA_MODEL` | `llama3.1:8b` | Must be a tool-calling model |
| `OLLAMA_NUM_CTX` | `8192` | Context window per request. The agent prompt (rules + course grounding + tool schemas) does not fit in Ollama's 4096-token default, and an over-long prompt is truncated silently — losing the tool definitions |
| `OLLAMA_TIMEOUT` | `300` | Seconds. A cold model load plus a multi-step reschedule takes several round-trips |
| `OLLAMA_TEMPERATURE` | `0.0` | Greedy decoding; scheduling is extraction, not creative writing |
| `OLLAMA_MAX_TOOL_TURNS` | `4` | Tool-calling rounds before the model is asked for a final answer with the tools withheld |

`OLLAMA_NUM_PARALLEL=1` is pinned in `docker-compose.yml`: Ollama sizes the KV cache
as `num_ctx × parallel slots`, and on auto it picks up to 4, turning an 8192-token
context into 32k worth of cache.

Troubleshooting the chat endpoint:

```bash
# Is the model present?
docker compose exec ollama ollama list

# What did the agent send and get back? Every tool call is logged.
docker compose logs -f backend | grep -E "GEMINI|OLLAMA|AI_AGENT"
```

`tests/test_chat.py`, `tests/test_courses.py`, `tests/test_memory_ai.py` and one
shared-calendar chat test call the live model rather than a mock, so they are slow
and depend on the model's instruction following. All are marked `live_llm`;
`pytest --no-ai` excludes them. The code *around* the model — persistence, history,
memory storage and expiry, the 503 path — is covered deterministically with the
model stubbed in `tests/test_chat_api.py`, `tests/test_user_memory.py` and
`tests/test_shared_calendars.py`, so `--no-ai` still exercises both chat endpoints
end to end.

On Ollama, if a scheduling test fails on `llama3.1:8b`, a larger quantisation
(`llama3.1:8b-instruct-q8_0`) or `qwen2.5:7b-instruct` follows tool schemas more
reliably.

---

## 🧠 Long-Term Memory (per user)

Every user has a persistent memory of their own: one row per remembered fact in
`user_memories`, rebuilt into the system prompt on **every** chat turn. That is
what makes a preference stated last week reach today's reply — nothing is held in
process state, so a restart changes nothing.

A fact is filed under a category (`wants`, `preference`, `communication_style`,
`routine`, `task_order`, `constraint`, `other`) and carries where it came from:
`signup`, `ai` (the assistant decided to keep it) or `user` (typed in by hand).

### The assistant decides what to keep and what to drop

Two tools are offered alongside the calendar tools on every turn, so no keyword
rule is making the call:

| Tool | Effect |
| :--- | :--- |
| `remember_about_user(content, category, expires_in_days)` | Stores one short third-person fact. `expires_in_days` gives a temporary state a horizon — "I'm ill this week" becomes a constraint that stops applying after 7 days |
| `forget_about_user(memory_id)` | Retires a fact the user says is wrong or finished. An id the caller does not own is refused and the real ids are handed back, so a mistaken call cannot drop something else |

What it actually stored or dropped comes back on the chat response as
`memory_actions`, and is shown under the reply in the UI — a rejected write is
never reported as a saved one.

Three things keep the memory from degrading over time:

- **Expiry.** A row past its horizon is retired the next time the memory is read.
- **Single-answer categories.** Tone and task order hold one value; a new answer
  retires the old one instead of leaving two contradictory lines in the prompt.
- **A cap** of 60 live rows per user. Past it the oldest inferred fact is evicted;
  sign-up answers are evicted last.

Memory text is markup-stripped and length-capped before storage, and the prompt
states that the block is data and can never issue instructions — it is
user-authored text being replayed into a system prompt.

### Sign-up questions

`GET /memory/questions` serves the questionnaire (task order, tone, study times,
interests, goals, routine); the sign-up form renders it from there rather than
hard-coding it, because the server is what turns each answer into the sentence the
AI reads. Answers ride along with `POST /auth/signup` as `preferences` and are
seeded into memory immediately, so the first message is already personalised.
Answering nothing is a normal sign-up.

### Endpoints

| Method & path | Purpose |
| :--- | :--- |
| `GET /memory/questions` | The sign-up questionnaire. No token — the form needs it before an account exists |
| `GET /memory/categories` | Category → the heading it appears under in the prompt |
| `GET /memory` | Everything remembered about the caller (`?include_inactive=true` for discarded rows) |
| `GET /memory/context` | The verbatim block the assistant is given, plus per-category counts |
| `POST /memory` | Add a fact by hand |
| `PATCH /memory/{id}` | Correct a fact, recategorise it, or restore a discarded one |
| `DELETE /memory/{id}` | Make the assistant forget it. The row is retired, not deleted, so the decision stays auditable and undoable |
| `GET` / `PUT /memory/preferences` | Read or re-answer the sign-up questions later. Answers merge; the derived memories are re-seeded |

Every query is scoped to the caller, so another account's memory id reads as 404
rather than confirming the row exists. Writes are rate-limited
(`RATE_LIMIT_MEMORY`, default `30/minute`).

In the UI: the **Memory** button in the header opens the panel — grouped by
category, showing where each fact came from and when it expires, with controls to
add, forget and restore.

---

## 💬 Forum, Reactions & Direct Messages

### Seeding a cold forum

An empty forum gives a first visitor nothing to react to. Run once after migrations:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.db.seed_forum
```

It creates four demo accounts (`*.demo@campus.example`, password `DemoPassword123!`)
with five posts, comments, reactions and a short DM thread. It is idempotent — a
second run adds nothing. **The demo accounts share one well-known password; do not
seed them into an internet-facing deployment.**

### Endpoints added

| Method & path | Purpose |
| :--- | :--- |
| `PUT` / `DELETE` `/posts/{id}/reactions` | Set or clear the caller's like/dislike. One row per user per item — changing your mind updates it |
| `PUT` / `DELETE` `/comments/{id}/reactions` | The same for a comment |
| `GET /posts/mine` | The caller's own posts plus `total_likes` / `total_dislikes` received |
| `POST /posts/{id}/share-as-event` | Copy a post onto the **caller's** calendar. Body: `start_time`, optional `end_time` (defaults to +1h) and `title` |
| `POST /messages` | Send a DM (`receiver_id`, `body`, `media_urls`) |
| `GET /messages/{other_user_id}` | The thread between the caller and one other user |
| `POST /messages/{other_user_id}/read` | Mark that thread read. Explicit, so a GET stays idempotent |

Every post/comment response now also carries `like_count`, `dislike_count` and
`my_reaction` (the caller's own, or `null`).

### Real-time frames

All pushed over the existing `/ws/notifications` socket. Clients switch on `type`:

| `type` | Delivery | Payload |
| :--- | :--- | :--- |
| `forum.post.created` | broadcast | `post` (anonymity-masked) |
| `forum.comment.created` | broadcast + notification to the post author | `post_id`, `comment` |
| `forum.reaction.changed` | broadcast + notification to the post author | `post_id`, `comment_id`, counts |
| `dm.message.created` | the two parties only, never broadcast | `message_data` |

Anything addressed to a specific person goes through `send_to_user`; `broadcast`
carries only content that is already public through the REST API, with the same
masking. Notifications are persisted as `Notification` rows too, so they survive a
disconnect and still appear in `GET /notifications`.

### Abuse protections

- **Per-user rate limits** (`RATE_LIMIT_POST`, `_COMMENT`, `_MESSAGE`, `_REACTION`,
  `_UPLOAD`). Keyed on the JWT subject rather than the client address, so one
  account cannot hide behind a shared campus NAT and a shared NAT cannot throttle
  everyone on it. Exceeding a limit returns 429.
- **Upload limits are server-side** in `app/services/upload_service.py` (10MB
  images / 100MB video, content-type allow-list), enforced while streaming so an
  oversized file is refused without being written.
- **`media_urls` must be paths this server minted** under `/uploads/`. An absolute
  or protocol-relative URL is refused, so the field cannot become an injection
  point for whatever renders it.
- **Bodies are stripped of all markup** (`app/services/sanitize.py`). Forum text is
  plain text, so the policy is "no tags at all" rather than a tag allow-list, which
  an attribute payload like `<img onerror=…>` can slip past. Known limitation: the
  content-type check trusts the client's header rather than sniffing magic bytes.

---

## 🏗️ Architecture & Features

- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Lucide Icons.
- **Backend**: FastAPI (Python 3.12), SQLAlchemy 2.0, Alembic, SlowAPI (rate limiting).
- **Database**: PostgreSQL 16 with `pgvector` extension.
- **AI & LLM**: Switchable dual provider (`LLM_PROVIDER=gemini|ollama`) with priority queue worker pool (`asyncio.PriorityQueue`).
- **Long-Term Memory**: per-user `user_memories` table with categories, expiry and eviction, written by the model's own tools and rebuilt into every prompt.
- **Real-Time**: WebSocket notification hub (`/ws/notifications`) with auto-reconnect, live reminder broadcasts, and live forum/DM frames.
- **Community Forum**: Anonymous posting, media upload validation, post/comment threading, likes/dislikes, direct messages, and calendar event conversion.
