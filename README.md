# SE_ML_effy: Campus AI Calendar & Community Hub

Full-stack application combining smart AI scheduling, shared group calendars, course-grounded conversational AI, real-time WebSocket notifications, and an anonymous student forum.

> **Grading / status:** [PROGRESS.md](PROGRESS.md) walks every requirement in the
> project guidelines and says what is fully implemented, what is partial and
> why — with the file and the test behind each claim.

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

## 🚀 Running the whole system

**Prerequisites:** Docker Desktop (or Docker Engine + Compose v2) and nothing
else — Python, Node and Postgres all run inside the containers. Ports 5173, 8000
and 5432 must be free. Roughly 2 GB of disk for the images; add ~6 GB and 5 GB of
free RAM if you choose the local-LLM path.

### 1. Configure the environment

```bash
cp .env.example .env
```

Then open `.env` and set the two variables that matter. Everything else has a
working default, and `.env` is gitignored.

| Variable | Required? | What happens without it |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | **Yes**, unless you switch to Ollama | Every chat request answers **HTTP 503**. The assistant has no keyword fallback on purpose: a broken model path must not look healthy. Get a key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `JWT_SECRET_KEY` | **Yes** for anything but localhost | Falls back to the value published in this repository, so anyone could forge a token for any account. The server logs a warning at startup while that default is in use. Generate one with `openssl rand -hex 32` |
| `LLM_PROVIDER` | No (`gemini`) | `gemini` or `ollama` — see [switching to the local LLM](#4-optional-switch-to-the-local-llm) |
| `POSTGRES_USER` / `_PASSWORD` / `_DB`, `DATABASE_URL` | No | Defaults to `postgres:postgres@postgres:5432/se_ml_effy`, which is fine for a local container and must be changed for anything else |
| `DEFAULT_TIMEZONE` | No (`UTC`) | The wall clock the assistant uses for a user whose browser has not reported a zone. The browser's zone always wins when present, so this is a fallback — but set it to your own zone anyway (`Asia/Jerusalem`), because on UTC an unreported user's "6pm" renders at their real offset |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | No | 30 minutes / 7 days |
| `RATE_LIMIT_*` (8 vars) | No | The per-user anti-spam budgets listed in `.env.example` |
| `CORS_ORIGINS` | No | `["http://localhost:5173", "http://127.0.0.1:5173"]`. Change it if you serve the frontend from another origin, or every request fails CORS |
| `VITE_API_URL` | No | `http://localhost:8000` — where the **browser** reaches the API |

> Only variables listed in the `environment:` blocks of `docker-compose.yml` reach
> a container. Every setting the backend reads is passed through there explicitly,
> so a variable you add to `.env` that is not in that list is silently ignored.

### 2. Bring it up

```bash
docker compose up -d --build
```

That is the whole startup. The backend container applies the database schema and
seeds the course knowledge base before serving traffic, so there is no manual
migration step:

1. `alembic upgrade head` — creates/updates every table (idempotent).
2. `python -m app.db.seed_courses` — fills the course/review tables that ground
   the AI's course answers (idempotent, and non-fatal: a failure here logs
   `[warn] course seeding skipped` and the API still starts).
3. `uvicorn app.main:app` — the API, with the notification scheduler and the
   chat priority queue started by the app's lifespan hook.

First build takes a few minutes (pip install + npm install). Watch it with:

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

### 3. Check it works

```bash
curl http://localhost:8000/health          # {"status":"ok"}
docker compose ps                          # postgres healthy, backend + frontend up
```

Then open **<http://localhost:5173>**, sign up (the second sign-up step asks the
long-term-memory questions), and try *"remind me to water the plant on Thursday
at 5pm"* in the chat panel. `http://localhost:8000/docs` is the full API.

If chat answers 503, the model is the problem, not the app —
`docker compose logs backend | grep -E "GEMINI|OLLAMA"` says which.

### 4. Optional: switch to the local LLM

No external API calls, ~5 GB of RAM in the Docker VM:

```bash
# in .env
LLM_PROVIDER=ollama

docker compose --profile ollama up -d      # starts ollama + the model pull
docker compose logs -f ollama-pull         # chat returns 503 until this finishes
```

The `ollama` profile is off by default so an idle 8B runner does not hold several
GB for nothing. Switching back is `LLM_PROVIDER=gemini` plus
`docker compose up -d backend`. Tuning knobs and troubleshooting are in
[LLM Configuration](#-llm-configuration) below.

### 5. Optional: seed the forum with demo content

An empty forum gives a first visitor nothing to react to:

```bash
docker compose exec backend python -m app.db.seed_forum
```

Idempotent. It creates four demo accounts that **share one well-known password**,
so it stays a deliberate command rather than part of startup — never run it on an
internet-facing deployment.

### Stopping, resetting, migrations

```bash
docker compose down                        # stop, keep the database
docker compose down -v                     # stop and delete the database volume
docker compose restart backend             # after changing .env

docker compose exec backend alembic upgrade head   # normally automatic on boot
docker compose exec backend alembic downgrade -1   # roll back one migration
```

### Troubleshooting

| Symptom | Cause and fix |
| :--- | :--- |
| Chat returns `503 ... currently unavailable` | No `GEMINI_API_KEY`, or `LLM_PROVIDER=ollama` and the model has not finished downloading |
| `port is already allocated` | Something else holds 5173/8000/5432. Stop it, or change the left-hand side of the `ports:` mapping |
| Backend restarts in a loop | Migrations failed — `docker compose logs backend`. A stale volume from an older schema is fixed with `docker compose down -v` |
| Requests fail with a CORS error | `CORS_ORIGINS` does not include the origin the browser loaded the app from |
| `llama-server process has terminated: signal: killed` | The Docker VM does not have ~5 GB free for the local model. Check with `docker compose exec ollama free -h`, or switch back to Gemini |
| Login works, then everything is 401 | The access token expired (30 min by default). Log in again, or raise `ACCESS_TOKEN_EXPIRE_MINUTES` |
| The AI says "6pm" but the event lands at another hour | The browser's timezone is not reaching the server. Hard-reload the frontend (an old bundle sends no `timezone` field) and set `DEFAULT_TIMEZONE` to your zone as a backstop. See [Times and timezones](#-times-and-timezones) |

### Running the tests

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

The offline half is **237 tests** and needs no key, no network and no model.

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

## 🕒 Times and timezones

The database stores **instants in UTC**; the browser renders them in the
reader's zone. The manual calendar path needs nothing more than that — the event
modal converts local → UTC with `toISOString()` on save and back on display.

The AI path is the one place a zone has to be chosen explicitly, because a user
who says *"6pm"* means 6pm **where they are**. So:

- The frontend sends `Intl.DateTimeFormat().resolvedOptions().timeZone` with
  every chat message; the server remembers it on the user (`users.timezone`) for
  anything that runs without a request in hand, and falls back to
  `DEFAULT_TIMEZONE`.
- The prompt states the user's zone, their **local** current time, their local
  weekday table, and their offset as a literal to copy — the model is told
  never to convert to UTC and never to write `Z`.
- Timestamps coming back from the model are read as that zone's wall clock and
  converted to UTC once, on the way into the database.
- Tool results are rendered **back** into local time, so the hour the assistant
  quotes in its reply is the hour on the calendar.

Two bugs this fixes, both silent before: "set it for 6pm" storing 18:00 UTC and
displaying as 21:00 for a user at UTC+3, and a late-evening request resolving
"today" to the UTC date — a day behind, east of UTC. Covered by
`tests/test_timezones.py` (28 offline tests plus one live-model check).

Note that `tzdata` is a dependency: without the IANA database, `zoneinfo`
silently has no zones to resolve and every wall clock falls back to UTC.

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

## 🔐 Auth model & known gaps

Every route except `/auth/signup`, `/auth/login`, `/auth/refresh`, `/health`,
`/memory/questions` and `/memory/categories` requires a bearer token, and every
row is looked up scoped to the caller — another user's id answers 404 (or 403 on
a shared calendar) rather than confirming the row exists.
`tests/test_access_control.py` enumerates the routes from the live app and
asserts that, so a newly added router cannot quietly ship open.

**Token rules.** Access tokens (30 min) are the only credential accepted as a
bearer token or on the notification WebSocket; refresh tokens (7 days) are only
accepted in the body of `/auth/refresh`. Neither type is usable in the other's
place. The WebSocket credential has to travel in the query string — a browser
cannot set a header on a handshake — so it is checked to the same standard:
signature, token type, and that the account still exists.

**Known gaps, deliberately not fixed here:**

| Gap | Impact | Suggested fix |
| :--- | :--- | :--- |
| `/uploads/*` is served by `StaticFiles` with **no authentication** | Anyone with the URL can fetch any uploaded image or video, including media attached to a direct message that the API otherwise restricts to two people. Filenames are `uuid4` hex, so they are unguessable rather than protected | Serve media through an authenticated route that checks the caller may see the parent post/comment/DM, and hand the browser short-lived signed URLs |
| `POST /events` and `POST /posts/{id}/share-as-event` have no rate limit | A token holder can create unbounded calendar rows. Every *forum* write is limited, so this is the one uncapped write path | Add a `RATE_LIMIT_EVENT` budget and apply it to both |
| Any member of a shared calendar can add further members | There is no owner-only operation; the `role` column is stored but not enforced | Restrict `POST /shared-calendars/{id}/members` to `role == "owner"` if that is the intent |
| The dev `JWT_SECRET_KEY` is a working fallback | An operator who never sets it runs with a secret published in this repository | Already warned at startup; make it fatal in a non-local deployment |

---

## 🏗️ Architecture & Features

- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Lucide Icons.
- **Backend**: FastAPI (Python 3.12), SQLAlchemy 2.0, Alembic, SlowAPI (rate limiting).
- **Database**: PostgreSQL 16 with `pgvector` extension.
- **AI & LLM**: Switchable dual provider (`LLM_PROVIDER=gemini|ollama`) with priority queue worker pool (`asyncio.PriorityQueue`).
- **Long-Term Memory**: per-user `user_memories` table with categories, expiry and eviction, written by the model's own tools and rebuilt into every prompt.
- **Real-Time**: WebSocket notification hub (`/ws/notifications`) with auto-reconnect, live reminder broadcasts, and live forum/DM frames.
- **Community Forum**: Anonymous posting, media upload validation, post/comment threading, likes/dislikes, direct messages, and calendar event conversion.
