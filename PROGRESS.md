# Implementation status against the project guidelines

Every requirement in [AI_Dairy_Project_Requirements.md](AI_Dairy_Project_Requirements.md),
in the guidelines' own order and numbering, with what actually exists behind it.

Written to be checked, not to be believed: each row points at the code and the
test that backs it. Where something is half-done it says so and names what is
missing — a claim that turns out to be false costs more than an honest gap.

| Legend | Meaning |
| :--- | :--- |
| ✅ | Fully implemented, wired into the UI where it is user-facing, and covered by tests |
| 🟡 | Partially implemented — works, but with a stated limitation or no UI |
| ⬜ | Not implemented |

**Start here:** [README.md → Running the whole system](README.md#-running-the-whole-system).
`docker compose up -d --build` after `cp .env.example .env` and setting
`GEMINI_API_KEY` is the whole setup; the schema and the course database are
applied on boot.

**Test suite:** 237 offline tests (`pytest --no-ai`, no key or network needed) and
26 live-model tests (`pytest --ai-only`, needs `GEMINI_API_KEY`). See
[Test map](#test-map) at the bottom for which file proves what.

---

## Summary

| Guidelines section | Weight | Status |
| :--- | ---: | :--- |
| 1. Project proposal / core application | 60 | ✅ Complete |
| 2. Long-term memory | 5 | ✅ Complete |
| 3. Robustness to hallucinations | 5 | ✅ Complete (retrieval is lexical — see 3.1) |
| 4. Shared calendars | 10 | 🟡 Complete except AI-driven memory extraction (4.4) |
| 5. Local LLM instead of API calls | 10 | 🟡 Fully supported, not the default provider |
| 6. Online forum | 10 | 🟡 Backend complete and tested; UI covers posts, comments, media and anonymity only |
| 7. Security & reliability | — | ✅ With four documented gaps |

Nothing in the guidelines was skipped outright. The three 🟡 rows are honest
partials, detailed below and collected in [Known gaps](#known-gaps).

---

## 1. Project proposal — 60 points

### 1.1 Users, passwords & authentication — ✅

| Requirement | Status | Where |
| :--- | :--- | :--- |
| Users | ✅ | `app/models/user.py`, `POST /auth/signup` |
| Passwords | ✅ | bcrypt with a per-password salt (`app/core/security.py`). Never stored or returned in plaintext — asserted in `test_auth.py::test_password_is_hashed_and_never_returned` |
| Authentication system | ✅ | JWT bearer tokens, 30-minute access + 7-day refresh, `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me` |
| "Must be secure" | ✅ | Password strength rules; brute-force rate limits on login and signup (429); tampered, wrongly-signed, expired, type-confused and deleted-user tokens all rejected; every route scoped to its owner. `test_auth.py`, `test_access_control.py` |

The access/refresh split is enforced in both directions: a refresh token is
rejected as a bearer credential, and an access token is rejected at
`/auth/refresh`. `test_access_control.py` enumerates the routes from the running
app and asserts each one answers 401 without a token, so a new router cannot
ship open by accident.

### 1.2 AI chat — ✅

| Requirement | Status | Where |
| :--- | :--- | :--- |
| Chat with an AI | ✅ | `POST /chat`, `GET /chat/history`; UI in `frontend/src/components/ChatPanel.tsx` |
| Free-speech requests | ✅ | e.g. *"Make sure I buy groceries on Thursday"* → `test_chat.py::test_intent_task_and_reminder_creation` |
| AI decides what goes on the calendar | ✅ | Four tools (`create_event`, `update_event`, `delete_event`, `list_events`) in `app/services/ai_agent.py`; the model calls them, no keyword parsing |
| AI works out an appropriate schedule | ✅ | The prompt resolves "Thursday", "next week", "3pm for 45 minutes" against a generated weekday table; defaults are stated (09:00, one hour). `test_chat.py::test_intent_scheduled_appointment` |
| Times mean what the user meant | ✅ | The whole AI path works in the user's own wall clock — browser zone per request, local prompt, local tool results, UTC only in the database. `test_timezones.py`; see [README → Times and timezones](README.md#-times-and-timezones) |
| Gemini API | ✅ | `GeminiClient` in `app/services/llm_client.py`, with automatic fallback when Google retires a model id |

There is deliberately **no** keyword fallback: if the model is unreachable, chat
answers HTTP 503 rather than faking a calendar action
(`test_chat_api.py::test_an_unavailable_model_surfaces_as_503`).

### 1.3 Ask the AI about the schedule — ✅

| Requirement | Status | Where |
| :--- | :--- | :--- |
| "What do I need to do today?" | ✅ | `test_chat.py::test_intent_query_today_agenda` |
| "What do I need to do this week?" | ✅ | `test_chat.py::test_intent_query_this_week_agenda` |
| AI summarises the relevant tasks | ✅ | `list_events` is called with a bounded range and the reply names the events. Another user's events are never in scope — `test_chat.py::test_agenda_query_only_sees_your_own_events` |

### 1.4 Manual calendar editing — ✅

| Requirement | Status | Where |
| :--- | :--- | :--- |
| Open the calendar in the app | ✅ | Month and week views, `frontend/src/pages/CalendarPage.tsx` |
| Change it manually | ✅ | Click a day to add, click an event to edit or delete (`EventModal.tsx`) |
| Without going through the chat | ✅ | `GET/POST/PATCH/DELETE /events`, covered by `test_events.py` including cross-user isolation |

### 1.5 Notifications — ✅

| Requirement | Status | Where |
| :--- | :--- | :--- |
| Users notified according to their calendar | ✅ | APScheduler sweeps every 60s for events starting within 30 minutes (`app/services/notification_scheduler.py`), writes a durable `Notification` row and pushes it over the WebSocket |
| Delivered live | ✅ | `frontend/src/components/NotificationBell.tsx` consumes the `notification` frame and updates the badge without a refresh |
| Shared-calendar events notify every member | ✅ | `test_notifications.py` |
| No duplicates | ✅ | Deduplicated per user+event — `test_notifications.py::test_no_duplicate_notifications` |

---

## 2. Long-Term Memory — 5 points — ✅

| Requirement | Status | Where |
| :--- | :--- | :--- |
| 2.1 Persistent per-user memory record | ✅ | `user_memories` table (`app/models/memory.py`), one row per fact, categorised |
| Store user wants | ✅ | `wants` category |
| Store preferences | ✅ | `preference` category |
| Store preferred communication style | ✅ | `communication_style` (single-valued) |
| Store what normally happens in the day | ✅ | `routine` category |
| Store easy-vs-hard task ordering | ✅ | `task_order` (single-valued) |
| 2.2 Sign-up questions | ✅ | `GET /memory/questions` serves them; the sign-up form renders it (step 2 of `SignupPage.tsx`) and posts answers with the account. Skipping them is a normal sign-up |
| 2.3 Server persists what matters | ✅ | Written on the request that produced it; nothing in process state. `test_user_memory.py::test_what_was_remembered_on_one_turn_reaches_the_next_one` |
| 2.4 AI decides what to save | ✅ | `remember_about_user(content, category, expires_in_days)` offered on every turn |
| 2.4 AI decides what to discard | ✅ | `forget_about_user(memory_id)`, plus self-expiring temporary states and a 60-row cap that evicts inferred facts before sign-up answers |
| 2.5 Memory is actually used | ✅ | The block is rebuilt into the system prompt on **every** turn (`ai_agent.py`), with instructions to honour it |
| 2.5 Memory affects scheduling | ✅ | The guidelines' own example — "unwell this week" changes what the AI advises today — is `test_memory_ai.py::test_a_stored_constraint_changes_what_the_ai_suggests_today` |

Also implemented, beyond the requirement: a **Memory** panel in the header where
the user can see exactly what the assistant knows, grouped by category and
labelled with where each fact came from, and correct, delete or restore any of
it (`frontend/src/components/MemoryPanel.tsx`); `GET /memory/context` returns the
verbatim prompt block. Memory text is markup-stripped and length-capped before
storage, and the prompt states the block is data that can never issue
instructions.

Details: [README → Long-Term Memory](README.md#-long-term-memory-per-user).

---

## 3. Robustness to Hallucinations — 5 points — ✅

| Requirement | Status | Where |
| :--- | :--- | :--- |
| 3.1 Course database | ✅ | `courses` + `course_reviews` (`app/models/course.py`), seeded on boot from `app/db/seed_courses.py` |
| Course content stored | ✅ | Description plus a structured `syllabus_topics` list per course |
| Course reviews stored | ✅ | Rating, text and author per review |
| Course explanations stored | ✅ | The description and topic list are what the AI is allowed to explain from |
| 3.2 AI checks the database first | ✅ | `retrieve_relevant_courses` builds a "VERIFIED COURSE KNOWLEDGE BASE" block and the prompt says facts about courses come **only** from it. `test_courses.py::test_query_real_course_returns_grounded_info` |
| AI does not invent courses | ✅ | A miss renders as `NO MATCHING COURSES FOUND` and the AI must say it has no information. `test_courses.py::test_query_nonexistent_course_returns_explicit_unknown` |
| AI does not invent course content | ✅ | Same block; the syllabus list bounds what it may claim |
| 3.3 Student claims are checked, not assumed | ✅ | The prompt refuses to agree with a topic the syllabus does not contain and states what the course does cover. `test_courses.py::test_reverse_fact_check_gentle_correction` |

**Limitation worth knowing:** retrieval is lexical — exact course-code matching
plus keyword scoring over name, description and topics
(`test_courses.py::test_hybrid_retrieval_service_direct`). Embeddings *are*
computed and stored in a pgvector column at seed time, but nothing ranks by
vector similarity yet, so a question phrased entirely in synonyms can miss. It
fails safe: a miss produces "I don't have information on that course", never an
invented answer.

---

## 4. Shared Calendars — 10 points — 🟡

| Requirement | Status | Where |
| :--- | :--- | :--- |
| 4.1 Create a shared calendar | ✅ | `POST /shared-calendars`; creator becomes `owner`. UI: `CalendarSwitcher.tsx` |
| Share it with other users | ✅ | `POST /shared-calendars/{id}/members` by email; invite box in the switcher |
| 4.2 Members see each other's tasks | ✅ | `GET /shared-calendars/{id}/events`, members only (403 otherwise) |
| 4.2 Members can edit the shared calendar | ✅ | `POST`/`PATCH`/`DELETE` on `/shared-calendars/{id}/events`, tested from both accounts |
| 4.3 Each user's own chat can add to it | ✅ | `POST /shared-calendars/{id}/chat`; an event the AI creates there is attached to the shared calendar. `test_shared_calendars.py::test_an_event_created_through_shared_chat_lands_on_the_shared_calendar` |
| 4.3 …and alter it | ✅ | The same tools operate on it |
| 4.4 Shared calendar has its own memory | ✅ | `shared_memories` table, `GET`/`POST /shared-calendars/{id}/memories`, shown as a "Group Context & Memories" banner in the chat panel |
| 4.4 That memory is used by the chat | ✅ | Injected into the prompt on every shared turn. `test_shared_calendars.py::test_stored_memory_is_fed_back_into_the_next_prompt` |
| 4.4 The AI decides what to remember for the group | 🟡 | **Extraction is keyword-based**, not model-driven: `app/api/routes/shared_calendars.py` matches a fixed phrase list ("remember that this group", "our team prefers", "avoid scheduling", …). The per-user memory in section 2 gives the model real tools for this; the group memory has not been migrated to them yet |
| 4.5 Shared chat | ✅ | One thread per calendar, visible to every member, and kept out of the private `/chat/history`. `test_shared_calendars.py` |

Also missing here: there is no way to **remove** a member or **delete** a shared
calendar, and the `role` column is stored but never enforced — any member can
add further members. Neither is asked for by the guidelines.

---

## 5. Local LLM instead of API calls — 10 points — 🟡

| Requirement | Status | Where |
| :--- | :--- | :--- |
| 5.1 Download and run a local LLM | ✅ | `ollama` service behind the `ollama` compose profile; `ollama-pull` fetches the model |
| Any open-source model | ✅ | `OLLAMA_MODEL`, default `llama3.1:8b` |
| Strong enough for complex conversation | 🟡 | 8B follows the tool schemas but is weaker than Gemini on multi-step rescheduling; the README names larger quantisations that do better |
| Capable of complex mathematical conversation | 🟡 | Whatever the chosen model can do — nothing in the app assists with maths specifically |
| Does not hallucinate over database content | ✅ | Same grounding block and rules as Gemini; `OLLAMA_NUM_CTX=8192` exists because the grounded prompt does not fit Ollama's 4096 default and would be truncated silently, dropping the tool definitions |
| 5.2 Local LLM used for everything | 🟡 | It is a **fully supported alternative, not the default.** `LLM_PROVIDER=ollama` routes every AI feature — chat, scheduling, course answers, memory decisions — through the local model with no code change. Gemini is the default because a local 8B needs ~5 GB of RAM in the Docker VM, and below that the runner is OOM-killed mid-generation |
| 5.3 Parallel programming | 🟡 | Four asyncio worker tasks consume the queue, and each blocking model call runs in a thread (`asyncio.to_thread`), so the API never blocks and requests are handled concurrently. The **model itself** is serialised on purpose (`OLLAMA_NUM_PARALLEL=1`): Ollama sizes its KV cache as `num_ctx × slots`, so parallel slots turn an 8k context into 32k of cache and get the runner killed |
| 5.4 Priority queue for chat requests | ✅ | `asyncio.PriorityQueue` with three levels — interactive chat > shared-calendar chat > background summaries (`app/services/chat_queue.py`). Ordering asserted in `test_llm_and_queue.py::test_priority_queue_ordering` |
| 5.5 Works with many students at once | ✅ | Requests queue instead of piling onto the model; the pool drains them by priority. Load has been verified logically (queue ordering, worker pool, thread offload), **not** measured under a real concurrent load test |

The honest summary: everything in this section exists and works, but the marked
implementation is "dual-provider with Gemini default", not "local-only".

---

## 6. Online Forum — 10 points — 🟡

The API is complete and tested for every item below. The **web UI covers posts,
comments, media and anonymity**; likes/dislikes, direct messages, the personal
area and share-as-event are reachable through the API and Swagger only. That is
the single biggest gap in the project.

| Requirement | API | UI | Where |
| :--- | :--- | :--- | :--- |
| 6.1 Create posts, visible to others | ✅ | ✅ | `POST /posts`, `GET /posts`; `ForumPage.tsx` |
| Post title / body | ✅ | ✅ | |
| Image attachments | ✅ | ✅ | `POST /uploads`, 10 MB limit, content-type allow-list |
| Video attachments | ✅ | ✅ | 100 MB limit |
| 6.2 Anonymous posting, name hidden | ✅ | ✅ | Masked in the REST response *and* the live frame. `test_forum.py::test_create_anonymous_post_never_leaks_author` |
| 6.3 Comments, visible to others | ✅ | ✅ | `POST /posts/{id}/comments` |
| Comment body / image / video | ✅ | ✅ | |
| 6.4 Like / dislike posts | ✅ | ⬜ | `PUT`/`DELETE /posts/{id}/reactions`; `test_forum_reactions.py` |
| Like / dislike comments | ✅ | ⬜ | `PUT`/`DELETE /comments/{id}/reactions` |
| Like / dislike counts on both | ✅ | ⬜ | `like_count`, `dislike_count`, `my_reaction` on every post and comment response |
| Personal area: own posts + total likes/dislikes | ✅ | ⬜ | `GET /posts/mine`; `test_forum_reactions.py::test_my_posts_reports_totals_received` |
| 6.5 Direct messages, sender+receiver only | ✅ | ⬜ | `POST /messages`, `GET /messages/{user_id}`; `test_messages.py::test_a_dm_is_invisible_to_a_third_user` |
| DM body / image / video | ✅ | ⬜ | |
| 6.6 Notified on a new DM | ✅ | 🟡 | Row written and frame pushed; the bell only renders `type: "notification"` frames, so it appears after a reload rather than live |
| 6.6 Notified on likes/dislikes of your post or comment | ✅ | 🟡 | Same: persisted and pushed, not rendered live. Never says *who* did it — that would out someone who reacted to an anonymous thread |
| 6.7 Create/share an event, others add it to their calendar | ✅ | ⬜ | `POST /posts/{id}/share-as-event` copies a post onto the **caller's** calendar, so any number of readers can add it independently |
| 6.8 Protection against spam & abuse | ✅ | — | Per-user rate limits on posts, comments, messages, reactions, uploads and memory writes; server-side upload size/type limits enforced while streaming; markup stripped from every body; `media_urls` must be paths this server minted. `test_forum_abuse.py` |
| 6.9 Cold seeding | ✅ | — | `python -m app.db.seed_forum` — 4 demo users, 5 posts, comments, reactions and a DM thread; idempotent. Opt-in because the demo accounts share one password. `test_seed_forum.py` |
| 6.10 Live updates without a refresh | ✅ | 🟡 | The backend broadcasts `forum.post.created`, `forum.comment.created`, `forum.reaction.changed` and `dm.message.created` (`test_realtime.py`). The UI does not subscribe to them yet — only calendar reminders redraw live |
| 6.10 Chats saved and retrievable, history accessible | ✅ | 🟡 | `Message` rows persist; `GET /messages/{user_id}` returns the thread with an unread count. No UI |

---

## 7. Security & Reliability — ✅

| Area | Status | Notes |
| :--- | :--- | :--- |
| Authentication | ✅ | JWT, both token types enforced in both directions, deleted accounts rejected, WebSocket held to the same standard |
| Passwords | ✅ | bcrypt + salt, strength rules, never returned |
| Forum requests | ✅ | Auth + per-user rate limits + sanitisation on every write |
| Direct messages | ✅ | Anchored to the caller on both sides of the query; never broadcast |
| Media uploads | ✅ | Size and content-type enforced server-side while streaming, so an oversized file is refused without being written |
| Excessive requests | ✅ | Per-user budgets, 429 on exceed. Keyed on the JWT subject, not the IP, so a shared campus NAT neither hides an abuser nor throttles everyone |
| Concurrent users | ✅ | Priority queue + worker pool; no shared mutable state between requests |
| Database access | ✅ | SQLAlchemy parameterised queries throughout; every row scoped to its owner |
| Server hard to crash | ✅ | Uploads bounded, bodies capped, memory capped per user, model failures surface as 503 rather than 500 |

### Known gaps

Found in the audit and left in place deliberately, each with the fix it needs.
Also listed in [README → Auth model & known gaps](README.md#-auth-model--known-gaps).

1. **`/uploads/*` is served with no authentication.** Anyone with the URL can
   fetch any uploaded file, including media attached to a DM that the API
   otherwise restricts to two people. Filenames are `uuid4` hex, so unguessable
   rather than protected. Fix: an authenticated media route that checks the
   caller may see the parent object, plus short-lived signed URLs for the
   browser.
2. **`POST /events` and `POST /posts/{id}/share-as-event` are not rate-limited.**
   Every forum write is; these two are the uncapped write path. Fix: a
   `RATE_LIMIT_EVENT` budget on both.
3. **Shared-calendar roles are not enforced** — any member can add further
   members, and nobody can be removed.
4. **The development `JWT_SECRET_KEY` is a working fallback**, and it is
   published in this repository. The server now logs a warning at startup while
   that default is in use; it should be fatal outside localhost.

No secrets are committed: `.env` is gitignored and has never been in the
history, and the only credential-shaped strings in the tree are the local
Postgres default (`postgres:postgres`), the seed script's demo password, and the
placeholder JWT secret described above.

---

## Complete requirements checklist

The guidelines' own checklist (section 8), ticked against what exists.

**Core project — 60 points**

- [x] Working localhost web application
- [x] Implements the proposed idea
- [x] Users
- [x] Secure passwords
- [x] Secure authentication
- [x] AI chat
- [x] Free-speech requests
- [x] AI can translate requests into calendar tasks
- [x] AI can determine a schedule
- [x] Ask AI for today's tasks
- [x] Ask AI for this week's tasks
- [x] AI summarises tasks
- [x] Manual calendar editing
- [x] Calendar-based notifications

**Long-term memory — 5 points**

- [x] Persistent memory for every user
- [x] Store user wants
- [x] Store user preferences
- [x] Store preferred communication style
- [x] Store relevant daily routine information
- [x] Store task-order preferences
- [x] Optional/useful sign-up questions
- [x] Server persists important information
- [x] AI decides what information to save
- [x] AI decides what information to discard
- [x] AI uses stored memory in future conversations
- [x] Memory affects scheduling/recommendations

**Hallucination robustness — 5 points**

- [x] Course database
- [x] Course content stored
- [x] Course reviews stored
- [x] Course explanations stored
- [x] AI checks database before answering course questions
- [x] AI does not invent courses
- [x] AI does not invent course content
- [x] AI verifies student claims against the database when appropriate

**Shared calendars — 10 points**

- [x] Create shared calendars
- [x] Share calendars with other users
- [x] Both users can view tasks
- [x] Both users can edit tasks
- [x] Individual AI chats can modify shared calendars
- [x] Shared calendar has long-term memory
- [x] Shared calendar has a personality/memory file — *stored and used in the prompt; entries are extracted by keyword rather than by the model (4.4)*
- [x] Shared chat

**Local LLM — 10 points**

- [x] Download local open-source LLM
- [x] Use local LLM for AI functionality — *supported via `LLM_PROVIDER=ollama`; Gemini is the default*
- [x] Model supports complex conversations
- [~] Model is capable of complex mathematical conversations — *depends on the chosen model; nothing app-side assists*
- [x] Model minimises hallucination when using database information
- [x] Parallel programming — *request-level: worker pool + thread offload; the model is serialised deliberately*
- [x] Priority queue for chat
- [x] Support many students chatting simultaneously — *by design and unit-tested; not load-tested*

**Online forum — 10 points**

- [x] Forum/social-network style page
- [x] Create posts
- [x] Post title
- [x] Post body
- [x] Image attachments
- [x] Video attachments
- [x] Anonymous posting
- [x] Anonymous names hidden from other clients
- [x] Comments
- [x] Comment body
- [x] Comment image attachments
- [x] Comment video attachments
- [~] Like posts — *API only, no UI*
- [~] Dislike posts — *API only, no UI*
- [~] Like comments — *API only, no UI*
- [~] Dislike comments — *API only, no UI*
- [~] Display like counts — *in the API response, not rendered*
- [~] Display dislike counts — *in the API response, not rendered*
- [~] Personal area with user's posts — *`GET /posts/mine`, no UI*
- [~] Personal overall like count — *API only*
- [~] Personal overall dislike count — *API only*
- [~] Direct messaging — *API only, no UI*
- [x] Private messages visible only to sender/receiver
- [~] Message image attachments — *API only*
- [~] Message video attachments — *API only*
- [~] New-message notifications — *persisted and pushed; not rendered live*
- [~] Like/dislike notifications — *persisted and pushed; not rendered live*
- [~] Share events — *`POST /posts/{id}/share-as-event`, no UI*
- [~] Add shared events to personal calendar — *same endpoint, no UI*
- [x] Spam protection
- [x] Large-file protection
- [x] Cold-seeded fake users
- [x] Cold-seeded posts
- [x] Cold-seeded comments
- [~] Real-time updates without page refresh — *frames are broadcast and tested; only calendar reminders are rendered live*
- [x] Persistent chats
- [x] Retrievable chat history — *`GET /messages/{user_id}`, no UI*
- [x] Live web-app notifications — *for calendar reminders*
- [x] Server security against malicious users

`[~]` = implemented server-side and tested, not reachable from the web UI.

---

## Verifying by hand

A click-path per feature, after `docker compose up -d --build` and signing up.
Anything marked API-only is easiest to exercise from
<http://localhost:8000/docs> — authorise once with a token from `POST /auth/login`.

| Feature | How to see it |
| :--- | :--- |
| Secure auth | Sign up, log out, log back in. Try `GET /auth/me` in Swagger with no token → 401 |
| Sign-up questions → memory | On sign-up, answer step 2. Then open **Memory** in the header: your answers are there as sentences, tagged "from sign-up" |
| AI chat → calendar | *"Remind me to water the plant on Thursday at 5pm"* → the event appears in the grid |
| Ask about the schedule | *"What do I need to do this week?"* |
| Manual editing | Click any day to add; click an event to edit or delete |
| Notifications | Create an event starting in ~20 minutes and wait for the sweep (≤60s) — the bell updates without a refresh |
| Long-term memory | *"I'm ill this week and can't do much"*, then *"what should I do today?"*. The **Memory** panel shows what it kept; delete it there and ask again |
| Course grounding | *"What does CS229 cover?"* then *"Does CS229 cover quantum computing?"* — it should refuse the second and say what the course does cover |
| Shared calendar | Create one in the switcher, invite a second account by email, add events from both, use the group chat |
| Local LLM | `LLM_PROVIDER=ollama` in `.env`, `docker compose --profile ollama up -d`, wait for `ollama-pull`, then chat |
| Forum | Second tab in the header: post with an image, comment, post anonymously |
| Likes / DMs / my posts / share-as-event | Swagger: `PUT /posts/{id}/reactions`, `POST /messages`, `GET /posts/mine`, `POST /posts/{id}/share-as-event` |
| Cold seeding | `docker compose exec backend python -m app.db.seed_forum`, then reload the forum |
| Abuse protection | Post six times in a minute → the sixth is 429. Upload a >10 MB image → refused |

---

## Test map

```bash
docker compose exec backend pytest --no-ai      # 237 tests, no key or network
docker compose exec backend pytest --ai-only    # 26 tests, needs GEMINI_API_KEY
```

| File | Covers | Live model? |
| :--- | :--- | :--- |
| `test_auth.py` | Signup, login, hashing, token lifetime, tamper, brute-force limits | No |
| `test_access_control.py` | Every route needs a token (enumerated from the app), token-type confusion, WebSocket auth | No |
| `test_events.py` | Manual calendar CRUD and cross-user isolation | No |
| `test_chat_api.py` | `/chat` persistence, history, privacy, the 503 path | No |
| `test_user_memory.py` | Memory storage, expiry, eviction, API, tools, and the prompt on every turn | No |
| `test_shared_calendars.py` | Membership, shared events, shared memory, shared chat | Mostly no |
| `test_courses.py` | Course grounding and retrieval | Yes |
| `test_chat.py` | Scheduling intent, agenda queries, ambiguity, self-correction | Yes |
| `test_memory_ai.py` | Whether the model keeps, drops and uses the right things | Yes |
| `test_forum.py` | Posts, comments, media, anonymity, deletion rights | No |
| `test_forum_reactions.py` | Likes/dislikes, counts, personal area, share-as-event, notifications | No |
| `test_forum_abuse.py` | Rate limits, upload limits, XSS sanitisation, media-URL validation | No |
| `test_messages.py` | DMs, privacy from a third party, unread counts, sanitisation | No |
| `test_notifications.py` | Scheduler, dedup, read state, cross-user isolation | No |
| `test_realtime.py` | WebSocket routing and which frames each route emits | No |
| `test_llm_and_queue.py` | Priority queue, Ollama tool-calling, Gemini model fallback | No |
| `test_seed_forum.py` | Cold seeding, idempotence | No |
