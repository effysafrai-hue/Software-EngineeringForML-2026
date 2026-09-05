# SE_ML_effy — Project Report

**Campus AI Calendar & Community Hub**
Student: Effy Safrai · Course: Software Engineering for ML, Spring 2026

---

## Contents

1. [What the app is](#1-what-the-app-is)
2. [Features, and the tests behind each one](#2-features-and-the-tests-behind-each-one)
3. [Risk assessment](#3-risk-assessment)
4. [Mandatory requirements checklist](#4-mandatory-requirements-checklist)

Companion documents: [README.md](README.md) for how to run it,
[PROGRESS.md](PROGRESS.md) for the point-by-point mapping to the project
guidelines.

---

# 1. What the app is

A student's day is scheduling work that nobody wants to do: turning "the ML
project is due in three weeks and I'm ill this week" into calendar entries, then
keeping them honest as things change. **SE_ML_effy** is a localhost web
application where that conversation *is* the interface. You write what you want
in your own words; an LLM decides what belongs on your calendar, puts it there,
and remembers the things about you that should shape next week's plan.

Around that core sit the things that make it a product rather than a demo: a
manually editable calendar, calendars shared with other students, a
course-grounded answer path that refuses to invent facts, live notifications, and
an anonymous campus forum.

## 1.1 Architecture

Four containers, one internal network, and exactly two doors to the outside.

```
                    ┌──────────── host ────────────┐
  browser ─────────►│ :5173  frontend  (React/Vite)│
       │            │ :8000  backend   (FastAPI)   │
       └───────────►└──────────────────────────────┘
                            │        │        │
              internal network only  │        │
                            ▼        ▼        ▼
                     postgres:5432  ollama:11434
                     (pgvector)     (llama3.1:8b, optional profile)
                            │
                     postgres_data volume
```

| Container | Image | Exposed to clients? | Role |
| :--- | :--- | :--- | :--- |
| `frontend` | built on `node:20-alpine` | **Yes** — `:5173` | React 18 + TypeScript + Tailwind UI |
| `backend` | built on `python:3.12-slim` | **Yes** — `:8000` | FastAPI: auth, calendar, AI orchestration, forum, WebSocket hub |
| `postgres` | `pgvector/pgvector:pg16` | **No** — internal only | All persistent state; pgvector for course embeddings |
| `ollama` | `ollama/ollama:latest` | **No** — internal only, `--profile ollama` | Local LLM, the alternative to the Gemini API |

That is **three images in the default configuration and four with the local
LLM**, against a requirement of two. The database and the model have no `ports:`
mapping at all, so they are reachable only as `postgres:5432` and `ollama:11434`
from inside the compose network — see [3.4 Security](#34-security).

## 1.2 Technology and why

| Layer | Choice | Reason |
| :--- | :--- | :--- |
| API | FastAPI (async) + SQLAlchemy 2.0 + Alembic | Async is not decoration here: a chat turn blocks on a model for seconds, and the event loop has to keep serving everyone else meanwhile |
| Database | PostgreSQL 16 + `pgvector` | Relational data with real constraints, plus a vector column for course retrieval |
| AI | Switchable provider: Google Gemini **or** a local Ollama model | One code path, one prompt, one set of tools; `LLM_PROVIDER` decides where it runs |
| Concurrency | `asyncio.PriorityQueue` + 4 worker tasks + `asyncio.to_thread` | Bounds how much work reaches the model and keeps a slow call off the loop |
| Real-time | WebSocket hub (`/ws/notifications`) | Reminders and forum activity arrive without polling |
| Auth | JWT access/refresh + bcrypt | Stateless, and no password is ever stored |

## 1.3 The idea worth stealing: tools, not text parsing

The assistant has no keyword matching anywhere. The model is given real
functions — `create_event`, `update_event`, `delete_event`, `list_events`,
`remember_about_user`, `forget_about_user` — and it decides which to call. Two
consequences shaped the whole design:

- **Every write goes through a validating function.** A bad timestamp or an
  unknown event id is not guessed at; the tool returns an error *to the model*
  with the real ids, and the model corrects itself. The database never receives
  a fabricated value.
- **A broken model is loudly broken.** There is no template fallback that
  "sort of" schedules things, so an unreachable provider answers HTTP 503 with
  the reason. A silent fallback would make a broken AI path look healthy, which
  is the worst possible failure for this app.

---

# 2. Features, and the tests behind each one

**Suite totals: 267 tests — 241 offline and 26 live-model.**

```bash
docker compose exec backend pytest --no-ai      # 241, no key, no network, deterministic
docker compose exec backend pytest --ai-only    # 26, real LLM calls, needs GEMINI_API_KEY
docker compose exec backend pytest              # everything
```

The split matters and is a deliberate design decision. A test that calls a real
model is slow, costs quota, and can fail because the model had an off day — so
those are marked `live_llm` and excluded by `--no-ai`. **Everything around the
model is tested deterministically with the model stubbed**, which means a
failure in the offline suite is always a real defect. Per-file counts below are
exact (`pytest --collect-only`).

| Test file | Tests | Live? |
| :--- | ---: | :--- |
| `test_user_memory.py` | 48 | no |
| `test_timezones.py` | 33 | 32 no / 1 live |
| `test_auth.py` | 18 | no |
| `test_llm_and_queue.py` | 18 | no |
| `test_forum.py` | 16 | no |
| `test_forum_abuse.py` | 16 | no |
| `test_forum_reactions.py` | 16 | no |
| `test_chat.py` | 13 | **live** |
| `test_realtime.py` | 13 | no |
| `test_access_control.py` | 12 | no |
| `test_shared_calendars.py` | 12 | 11 no / 1 live |
| `test_events.py` | 10 | no |
| `test_notifications.py` | 10 | no |
| `test_chat_api.py` | 8 | no |
| `test_messages.py` | 8 | no |
| `test_memory_ai.py` | 7 | **live** |
| `test_seed_forum.py` | 5 | no |
| `test_courses.py` | 4 | **live** |

## 2.1 Users, passwords, authentication

Sign-up with a strength-checked password, login returning a 30-minute access
token and a 7-day refresh token, `GET /auth/me`, and `POST /auth/refresh`.
Passwords are bcrypt hashes with a per-password salt.

**Tests — `test_auth.py` (18), `test_access_control.py` (12):**

- *Passwords are never plaintext* — `test_password_is_hashed_and_never_returned`
  signs up, then asserts the plaintext appears nowhere in the response body and
  that the stored column starts with `$2` (bcrypt) and differs from the input.
  This is the mandatory requirement, asserted against the database itself.
- *Brute force costs something* — `test_login_is_rate_limited_against_brute_force`
  reads the configured budget, sends that many wrong passwords (all 401), and
  asserts the next one is **429**. Same for sign-up.
- *Token integrity* — a token with a flipped signature byte, one signed with a
  different secret, and one with no `type` claim are each rejected 401.
- *Deleted accounts* — `test_a_token_for_a_deleted_user_is_rejected`: the token
  is still cryptographically valid, the account is gone, the answer is 401.
- *Token types are not interchangeable* — a refresh token is rejected as a
  bearer credential on five different data-reading routes, and an access token
  is rejected at `/auth/refresh`. Both directions, because either gap turns a
  leaked short-lived credential into a long-lived one.
- *No route ships open by accident* —
  `test_every_protected_route_requires_a_token` **enumerates the routes from the
  live app object**, calls each with no token and a deliberately malformed body,
  and asserts 401 everywhere. A companion test asserts the public list (sign-up,
  login, refresh, health, and the two static sign-up-question endpoints) is
  exactly what we intended. A newly added router cannot quietly be unprotected.
- *Refresh tokens stay out of URLs* — the token is accepted only in the body;
  passing it as a query parameter is a 422. URLs end up in access logs and
  browser history.

## 2.2 AI chat → calendar

Free-text requests become calendar events. The model resolves relative dates
("Thursday", "next week"), clock times, and durations, and calls the tools.

**Tests — `test_chat.py` (13, live) + `test_chat_api.py` (8, offline):**

The two files split by *what* is being tested. `test_chat.py` drives the real
model to check its judgement; `test_chat_api.py` stubs the model to check the
route around it, deterministically.

- *Intent → event* — "Make sure I buy groceries on Thursday" produces exactly
  one `create_event`, and the stored row lands on Thursday 11 June.
- *Times and durations* — "Dr. Smith consultation at 3pm on Friday for 45
  minutes" is asserted down to the hour and a 40–50 minute duration.
- *Reschedule and cancel* — a seeded event is moved and deleted through the
  two-step `list_events` → `update_event` / `delete_event` path, proving the
  model uses a real id instead of inventing one.
- *Agenda questions* — "what do I need to do today / this week" are separate
  tests, and `test_agenda_query_only_sees_your_own_events` seeds another user's
  event and asserts it never appears.
- *Ambiguity is asked about, not guessed* — "move it to Friday" with no named
  event asserts **no tool call at all** and a clarifying question. Guessing here
  would silently rewrite the wrong event.
- *Self-correction* — "Friday — wait, no, make it Saturday at 4pm" must produce
  one event, on Saturday. The retracted half must not be scheduled.
- *Route behaviour, deterministically* — both sides of the exchange are
  persisted; history is ordered and private to its owner; an empty message is
  422 and stores nothing; an unavailable model is **503, not 500**.

## 2.3 Wall-clock correctness (a bug this suite now prevents)

Worth its own section because it was a real, shipped, silent bug: the assistant
would say "set for 6pm" and the calendar showed 9pm. The prompt declared all
times UTC, while the browser renders instants in the reader's zone — so every
AI-created event was off by the user's offset.

The fix: the browser sends its IANA zone with every message; the prompt states
the user's local time, local weekday table and offset as a literal to copy;
timestamps from the model are read as that wall clock and converted to UTC once;
and tool results are rendered *back* to local so the hour the assistant quotes
is the hour on the calendar.

**Tests — `test_timezones.py` (33):**

- *The bug itself* — `test_a_6pm_request_is_stored_as_6pm_local`: 18:00 local at
  UTC+3 must store as 15:00Z and render back as 18:00.
- *Every shape the model might write* — an explicit offset, a naive timestamp,
  and a stray `Z` each land on the stated hour. The `Z` case is the interesting
  one and is documented in the code: models append it out of habit to the local
  time they were told to write, and reading it as UTC is exactly what made the
  reply and the calendar disagree.
- *Summaries too* — `test_a_listed_event_is_reported_in_local_time` covers the
  same bug in reverse, where the AI read 15:00Z and said "3pm".
- *The date boundary* — at 00:30 local (21:30Z the previous day) the prompt must
  say "Today is Thursday, 2026-06-11". Anchoring to UTC put "today" a day behind
  every evening.
- *DST* — Israel is +03:00 in June and +02:00 in January, asserted both ways,
  because the offset is handed to the model as a literal.
- *Fallbacks* — an unknown, empty or malformed zone falls back to the configured
  default and never raises; a misconfigured default falls back to UTC. A bad
  header is not a reason to refuse to schedule anything.
- *The manual path is unchanged* — a regression guard that `POST /events` stores
  exactly the instant the browser sends, since the browser already converts.
- *One live test* — a real model, a real "6pm" request at UTC+3, asserting both
  the stored hour and that the reply names 6pm.

A lesson the suite itself learned here: pinning `DEFAULT_TIMEZONE` in
`conftest.py`, because reading the deployment's `.env` let an operator's
configuration decide what a test measured.

## 2.4 Long-term memory

Each user has a persistent, categorised memory (`user_memories`) that is rebuilt
into the system prompt on **every** turn. The model decides what to keep and
what to drop, through two tools of its own.

**Tests — `test_user_memory.py` (48, offline) + `test_memory_ai.py` (7, live):**

- *Sign-up answers become memory* — the questionnaire is served by the API, and
  answers posted with the account are translated into sentences the model can
  read ("prefers to do the hardest task first"), not raw enum values. Skipping
  the questions still produces a working account; an invalid choice is a 422 and
  creates nothing.
- *Storage rules* — repeating a fact refreshes one row instead of duplicating it;
  a single-answer category (tone, task order) retires its old value because both
  cannot be true; independent facts accumulate.
- *Discarding* — `forget` retires without destroying the record; a temporary
  state expires on its own and the row is retired the next time memory is read;
  an absurd expiry is clamped; the live memory is capped at 60 rows and evicts
  inferred facts before sign-up answers.
- *It actually reaches the model* — the prompt-level tests are the point of the
  requirement: memory is in the system prompt of every turn, what was remembered
  on turn one is in turn two's prompt (proving nothing lives in process state),
  and a forgotten or expired fact stops appearing.
- *The AI's decisions* — the tools are offered every turn; a stored fact appears
  in the response's `memory_actions`; a rejected write is **not** reported as a
  save; forgetting an id the user does not own is refused and answered with the
  real ids.
- *Prompt injection* — memory text is markup-stripped before storage, and the
  prompt states the block is data that can never issue instructions.
- *Live judgement* — a real model keeps a stated preference, gives "I'm unwell
  this week" a horizon in days, changes what it advises today because of it,
  drops it when retracted, and does **not** store "buy milk" as a lasting fact.

## 2.5 Course grounding (anti-hallucination)

A course database (content, syllabus topics, reviews) is retrieved into a
"VERIFIED KNOWLEDGE BASE" block, and the prompt allows course facts to come only
from there.

**Tests — `test_courses.py` (4, live):**

- *Grounded answer* — "What topics are covered in CS101?" must mention Python
  and at least one real syllabus topic.
- *No invented courses* — asking for the syllabus of a course that does not
  exist. The strong assertion is the **absence of fabrication** (no "topics
  include", no "week 1"), because inventing content is the failure; a second,
  looser assertion checks it acknowledged the gap, matched against ~30 phrasings
  and printing the actual reply on failure. This test taught its own lesson: it
  originally asserted eight exact phrasings and failed on a perfectly correct
  refusal worded differently.
- *Student claims are checked* — "I heard CS101 covers quantum computing" must
  be contradicted, with what the course does cover.
- *Retrieval, without the model* — exact course-code match, keyword match, and a
  miss producing `NO MATCHING COURSES`.

## 2.6 Manual calendar, shared calendars, notifications

**Tests — `test_events.py` (10), `test_shared_calendars.py` (12), `test_notifications.py` (10):**

- *Calendar CRUD* — create, list by range, update, delete, plus
  `test_another_users_event_is_invisible_and_unmodifiable` and a backwards
  date range rejected.
- *Shared calendars* — membership is enforced on every calendar-scoped route
  (403 for a non-member, including the memories endpoint); both members see and
  edit the same events; an event created through one member's own chat is
  attached to the shared calendar and visible to the other; the shared chat is
  shared, and stays out of the private history.
- *Group memory* — extracted from a message, visible to the other member, fed
  back into the next prompt, and *not* created by an ordinary message.
- *Notifications* — the scheduler creates a reminder for an upcoming event,
  never twice for the same user+event, notifies every member of a shared
  calendar, and read/unread state is per-user with cross-user access refused.

## 2.7 Forum, direct messages, real-time

**Tests — `test_forum.py` (16), `test_forum_reactions.py` (16), `test_messages.py` (8), `test_realtime.py` (13), `test_seed_forum.py` (5):**

- *Anonymity* — the assertion is that the author leaks nowhere: not in the REST
  response, not in the live WebSocket frame, and not in a notification. Tested
  for both posts and comments.
- *Media* — a valid image and video upload; an invalid content type refused; an
  oversized file refused **and leaving no partial file on disk**.
- *Deletion rights* — author can, non-author gets 403, and deleting a post
  removes its comments.
- *Reactions* — switching like→dislike replaces rather than adds; repeating is
  idempotent and does not re-notify; counts are shared while `my_reaction` is
  per-viewer; comment reactions counted separately from the post's.
- *Direct messages* — `test_a_dm_is_invisible_to_a_third_user` is the privacy
  requirement; a DM is **never broadcast**, only pushed to the two parties
  (`test_a_direct_message_is_never_broadcast`); unread counts; sanitisation.
- *Real-time routing* — `ConnectionManager` is driven directly with stub sockets
  so "who receives which frame" is asserted without event-loop timing: only that
  user, all their tabs, everyone-but-the-excluded-user, and a dead socket
  dropped without blocking the others.
- *Cold seeding* — the demo content script is idempotent and hashes its
  passwords.

---

# 3. Risk assessment

## 3.1 Availability & redundancy

*What can go wrong, and what happens then.* The answer is never "it crashes" —
each dependency has a defined degraded mode.

| What goes wrong | What actually happens | Where |
| :--- | :--- | :--- |
| **The LLM provider is down, keyless, or over quota** | The chat request answers **HTTP 503** with the reason, the user's message is still persisted, and the calendar is untouched. There is deliberately no template fallback: a fake schedule that looks real is worse than a visible outage. Everything else in the app — calendar, forum, notifications — keeps working, because only the chat path depends on the model | `LLMUnavailableError`, asserted by `test_an_unavailable_model_surfaces_as_503` |
| **Google retires a Gemini model id** | Real failure mode: retired ids are still returned by `list_models()` and only fail at generate time. The client recognises that error, retires the id for the process, and walks a fallback chain of newer→older models. A restart is not needed | `llm_client.py`, 10 tests in `test_llm_and_queue.py` |
| **The local model is not downloaded yet** | 503 with "pull it first: `ollama pull …`", rather than a timeout with no explanation | `test_ollama_client_reports_missing_model` |
| **The model returns nothing, or loops calling the same tool** | A repeated identical tool call replays the stored result instead of writing the event twice; if the turn budget is spent, the model is asked once more with the tools withheld so it has to put what it did into words; a still-empty reply raises rather than storing silence | `test_ollama_client_does_not_repeat_an_identical_tool_call`, `test_ollama_client_forces_a_final_answer_when_tool_turns_run_out` |
| **The model sends a bad timestamp or an unknown event id** | The tool refuses and hands the error back to the model with the valid ids, so it can correct itself. Nothing is guessed, and a rejected call is never counted as a completed action | `_unknown_event_error`, `_record` |
| **Postgres is not ready at boot** | `depends_on: condition: service_healthy` plus a `pg_isready` healthcheck holds the backend back; the backend then runs migrations before serving | `docker-compose.yml` |
| **A migration fails** | The backend exits instead of serving against a half-built schema, which is the safe direction. Course seeding, by contrast, is explicitly non-fatal: a seeding hiccup logs a warning and the API still starts | compose `command` |
| **The API process wedges** | A `/health` healthcheck (15s interval) marks it unhealthy, and `restart: unless-stopped` brings it back | `docker-compose.yml` |
| **A client's WebSocket dies mid-push** | The dead socket is dropped from the registry without blocking the other recipients, and **every notification is also a durable row** — so a disconnected user still sees it in `GET /notifications`. Nothing is lost by being offline | `test_a_dead_socket_is_dropped_and_does_not_block_the_others` |
| **The notification scheduler throws** | Wrapped in try/except with a rollback; the next 60-second sweep retries. Reminders are deduplicated per user+event, so a retry cannot double-notify | `notification_scheduler.py`, `test_no_duplicate_notifications` |
| **A WebSocket push happens with no event loop bound** (scripts, tests) | The push is dropped, not raised — a notification is not worth failing the request that caused it | `test_dispatch_without_a_bound_loop_does_not_raise` |
| **Two users react to the same post simultaneously** | The unique constraint rejects the second insert; the code catches `IntegrityError`, rolls back, and updates the row that won | `_upsert_reaction` |
| **An upload dies halfway** | Size is enforced *while streaming*, so an oversized file is refused without being written, and no partial file is left behind | `test_oversized_upload_leaves_no_partial_file_on_disk` |

**Honest gaps.** This is a single-host deployment: one Postgres instance with no
replica, one backend replica, and no configured backup schedule. Data survives
container restarts (named volume) but not a lost host. The first three things I
would add for a real deployment: `pg_dump` on a schedule to off-host storage, a
streaming replica, and moving rate-limit state into Redis (see 3.2).

## 3.2 Scalability

**Where the pressure actually is.** Every request is cheap except one: a chat
turn blocks on an LLM for seconds. Nothing else in the app comes close, so the
design puts all its effort there.

**1. Async all the way to the model.** The API is async, and the blocking model
call is pushed off the event loop with `asyncio.to_thread`. One user waiting 8
seconds for a model does not stall the calendar, the forum, or anyone else's
request.

**2. A priority queue in front of the model, not a free-for-all.**
`asyncio.PriorityQueue` with a pool of 4 workers and three levels:

| Priority | Work | Why it ranks there |
| ---: | :--- | :--- |
| 1 | Interactive chat | A person is watching a cursor blink |
| 2 | Shared-calendar chat | Also interactive, but a group can wait behind an individual |
| 3 | Background summaries | Nobody is waiting |

Under a spike, requests queue instead of piling onto the model — the difference
between slower answers and a thrashed, OOM-killed runner. `max_workers` is the
one number to turn up when there is more capacity behind it. Ordering is
asserted in `test_priority_queue_ordering`, and `submit()` falls back to a
direct threaded call when the pool is not running, so the queue is never a
single point of failure.

**3. The local model is serialised on purpose.** `OLLAMA_NUM_PARALLEL=1`: Ollama
sizes its KV cache as `num_ctx × slots`, so letting it pick 4 slots turns an
8192-token context into 32k of cache and the runner gets OOM-killed. Concurrency
belongs in the queue, where it is bounded and ordered, not in the model runner.

**4. Cheap requests stay cheap.** Indexes on every foreign key and on the
composite `(user_id, active)` that the memory read filters on; feeds paginate
with capped `limit`; course retrieval short-circuits before touching the
database when the message is not course-related.

**5. Bounded prompt growth.** Long-term memory is capped at 60 live rows per
user and each entry at 400 characters, with expiry and eviction. Without that,
the prompt — and therefore the cost and latency of *every* future turn — grows
without limit for the app's heaviest users.

**How expansion would work.** The backend is stateless apart from two things:
the in-process chat queue and in-memory rate-limit counters. So horizontal
scaling is: put N backend containers behind a load balancer, move the rate-limit
store to Redis (slowapi supports it with a config change), and either accept
per-instance queues or move to a shared broker. Postgres scales first by
read replicas — the read-heavy paths (feed, calendar, course lookup) are the
obvious candidates. The AI is already independently scalable: `LLM_PROVIDER` and
`OLLAMA_BASE_URL` mean the model can move to its own GPU host without an
application change.

## 3.3 Spamming requests

Unbounded requests are money in the bin — every chat turn is a paid API call or
GPU time.

**Per-user rate limits, keyed on the JWT subject, not the IP.** This is the
important detail: a campus NAT means thousands of students share one address, so
IP keying would let one abuser hide in the crowd *and* let one abuser throttle
everyone else. Exceeding a budget is a 429.

| Budget | Default | Protects |
| :--- | :--- | :--- |
| `RATE_LIMIT_LOGIN` / `_SIGNUP` | 5/min | Password guessing, account flooding |
| `RATE_LIMIT_POST` | 5/min | Feed flooding |
| `RATE_LIMIT_COMMENT` | 15/min | Thread flooding |
| `RATE_LIMIT_MESSAGE` | 20/min | DM harassment |
| `RATE_LIMIT_REACTION` | 60/min | Like-button scripting |
| `RATE_LIMIT_UPLOAD` | 10/min | Storage exhaustion |
| `RATE_LIMIT_MEMORY` | 30/min | Prompt stuffing |

**Payload limits, not just request counts.** Uploads are capped server-side at
10 MB for images and 100 MB for video against a content-type allow-list, checked
*while streaming* so an oversized body is refused without being written.
Bodies are capped at 20 000 characters. Memory entries are capped in size and
number. Feed endpoints cap `limit` at 100.

**The queue is itself a spam control.** A burst of chat requests cannot become a
burst of model calls: four workers drain a priority queue, so the cost ceiling is
throughput, not concurrency.

**Tested** — `test_forum_abuse.py` (16) asserts each budget triggers exactly
after the configured burst, that limits are **per user rather than per
connection**, that the reset helper really clears storage (so one test cannot
spend another's budget), and the oversized-upload behaviour.

**Gap, stated plainly.** The rate-limit store is in-process, so counters are
per-container and reset on restart; and `POST /events` is the one write path with
no budget. Redis-backed storage and a `RATE_LIMIT_EVENT` are the fixes.

## 3.4 Security

### Passwords are never stored as plain text

bcrypt with a per-password salt (`app/core/security.py`); the hash never leaves
the server and no response body contains a password field. Asserted against the
database, not just the API, in
`test_auth.py::test_password_is_hashed_and_never_returned`.

### Only the web tier is exposed

The `postgres` and `ollama` services have **no `ports:` mapping**. They are
reachable only over the internal compose network as `postgres:5432` and
`ollama:11434`; the published ports are `5173` (UI) and `8000` (API) and nothing
else. `docker compose config` confirms it.

> This was a genuine finding while writing this report: both the database and the
> model *were* published to the host. An exposed Postgres puts one password
> between the internet and every row; an exposed Ollama is an unauthenticated
> inference endpoint on your hardware, bypassing the app's grounding rules, rate
> limits and queue entirely. Both mappings are now removed, with the reason
> documented in `docker-compose.yml` and a `docker compose exec` recipe for
> legitimate admin access.

Two ports are published rather than one, and that is deliberate: the frontend is
a single-page app, so the **browser itself** is the client of the API — `:5173`
serves the JavaScript and `:8000` answers its requests. Both are the web tier;
the requirement's actual subjects, the AI model and the database, are
unreachable from outside. A stricter topology would put nginx in front, serving
the built SPA and reverse-proxying `/api` to the backend on the internal
network, leaving exactly one published port. That is the right shape for
production — it also removes CORS entirely — but it is a deployment change with
no security benefit for the model and database, which are already isolated.

### Everything else

- **Authorisation on every route.** Every endpoint except sign-up, login,
  refresh, `/health` and the two static questionnaire endpoints requires a
  bearer token, and every query is scoped to the caller — another user's id
  answers 404/403 rather than confirming the row exists.
  `test_access_control.py` enumerates the routes *from the running app* and
  asserts this, so a new router cannot ship open.
- **Token hygiene.** Access and refresh tokens are not interchangeable in either
  direction; refresh tokens are body-only, never in a URL; tampered, wrongly
  signed, type-less and deleted-user tokens are all rejected.
- **The WebSocket is authenticated to the same standard.** Its token must
  travel in the query string (a browser cannot set a handshake header), so it is
  checked for signature, token type *and* that the account still exists.
- **Injection.** SQLAlchemy parameterises every query. Forum bodies are
  markup-stripped with a "no tags at all" policy rather than a tag allow-list,
  which an attribute payload like `<img onerror=…>` defeats. `media_urls` must
  be paths this server itself minted under `/uploads/`, so the field cannot
  become an injection point for whatever renders it.
- **Prompt injection.** Long-term memory is user-authored text replayed into a
  system prompt, so it is markup-stripped and length-capped, and the prompt
  states the memory block is data that can never issue instructions.
- **Secrets.** `.env` is gitignored and has never been committed; no key or
  password is in the repository. The development `JWT_SECRET_KEY` is a working
  fallback, so the server logs a warning at startup while it is still in use.

**Known gaps, documented rather than hidden** (also in
[README → Auth model & known gaps](README.md#-auth-model--known-gaps)):

1. `/uploads/*` is served by `StaticFiles` with **no authentication** — anyone
   with the URL can fetch any uploaded file, including media attached to a DM
   the API otherwise restricts to two people. Filenames are `uuid4`, so
   unguessable rather than protected. Fix: an authenticated media route plus
   short-lived signed URLs.
2. Upload content-type trusts the client's header rather than sniffing magic
   bytes.
3. Shared-calendar roles are stored but not enforced: any member can add another.
4. The dev JWT secret is a working default (warned, not fatal).

## 3.5 Persistent data

All state lives in PostgreSQL, across **14 tables**: `users`, `user_memories`,
`events`, `chat_messages`, `courses`, `course_reviews`, `shared_calendars`,
`shared_calendar_members`, `shared_memories`, `notifications`, `posts`,
`comments`, `reactions`, `messages`.

Schema changes go through Alembic (10 migrations, applied automatically at
boot), so the schema is versioned and reversible rather than something the ORM
happens to create. Data survives container rebuilds in the named
`postgres_data` volume. Nothing that matters is kept in memory: long-term
memory in particular is written on the request that produced it, which is what
lets the assistant remember a preference across a restart. Uploaded media is
stored on disk with only its path in the database — the standard trade-off, and
the reason the volume is part of the backup story.

## 3.6 Complexity and creativity

- **Tool-calling agent, not intent parsing.** Six functions the model can call,
  with server-side validation that refuses bad arguments and hands the error
  back so the model can correct itself.
- **Long-term memory the AI curates.** It decides what to keep, what to discard,
  and what expires — with categories, single-answer replacement, self-expiry and
  eviction — and every fact is visible and correctable by the user.
- **Grounded answers with an explicit "I don't know".** A retrieval block the
  prompt treats as the only source of course truth, so the model contradicts a
  student's false claim instead of agreeing with it.
- **Dual provider, one code path.** The same prompt and tools run against
  Gemini or a local Llama; the Gemini client survives Google retiring a model id
  mid-flight.
- **Priority queue + worker pool** so an individual's chat outranks a group's,
  and a spike queues instead of thrashing the model.
- **Real-time hub** with anonymity-preserving masking applied to live frames as
  well as REST responses.
- **The wall-clock work in 2.3** — unglamorous and the difference between an app
  people trust and one they don't.
- **A test suite designed around a non-deterministic dependency**: 241
  deterministic tests where a failure is always a real defect, 26 live tests for
  the model's judgement, and route coverage generated from the app itself so it
  cannot go stale.

---

# 4. Mandatory requirements checklist

| Requirement | Status | Evidence |
| :--- | :--- | :--- |
| At least two images in the backend | ✅ **3 by default, 4 with the local LLM** | `frontend` (node:20-alpine), `backend` (python:3.12-slim), `postgres` (pgvector/pgvector:pg16), `ollama` (ollama/ollama) |
| Availability & redundancy assessed | ✅ | [3.1](#31-availability--redundancy) — 13 named failure modes with their degraded behaviour, plus stated gaps |
| Scalability, with async & parallel programming | ✅ | [3.2](#32-scalability) — async API, `to_thread` offload, 4-worker pool, 3-level priority queue, bounded prompt growth |
| Spam handling | ✅ | [3.3](#33-spamming-requests) — 8 per-user budgets, payload caps, streaming upload enforcement, queue as cost ceiling; 16 tests |
| No plaintext passwords | ✅ | bcrypt + salt, asserted against the database |
| Only the web container exposed | ✅ **(fixed while writing this)** | `postgres` and `ollama` have no `ports:`; only 5173 and 8000 are published |
| Persistent data in a database | ✅ | PostgreSQL, 14 tables, 10 Alembic migrations, named volume |
| Complexity and creativity | ✅ | [3.6](#36-complexity-and-creativity) |

**Verified for this report:** `pytest --no-ai` → **241 passed**;
`docker compose config` → only 5173 and 8000 published. The 26 live-model tests
need a `GEMINI_API_KEY` and were not run in this environment.
