# SE_ML_effy

Full-stack application built with **FastAPI** (Python 3.12) with JWT Authentication, Calendar Events, Course Knowledge Base (pgvector + Grounding Layer) & Gemini AI Assistant, **React + Vite + TypeScript + Tailwind CSS**, and **PostgreSQL 16 with pgvector**, fully containerized with **Docker Compose** and hot-reloading.

## Features

- **Course Knowledge Base & Factual Grounding**: Pre-LLM hybrid retrieval (code lookup, token search, pgvector similarity) feeding verified syllabus and review data directly into prompt context.
- **Reverse Fact-Checking Guard**: When users assert incorrect information about courses ("CS101 covers quantum computing"), the assistant cross-references verified DB syllabi and gently corrects them.
- **Explicit Unknown Responses**: Never hallucinates fake courses; answers "I don't have information on that course" when querying nonexistent courses.
- **Semantic Calendar AI Assistant**: Handles reminders, appointments, implied deadlines, reschedules, cancellations, agenda summaries, and ambiguity questions.
- **Auto-Model Resolution**: Dynamically selects active Google Gemini models (`gemini-3.6-flash`, `gemini-3.7-flash`, etc.).
- **Authentication & Security**: JWT access + refresh tokens, bcrypt hashing, and SlowAPI rate limiting.

## Quick Start

```bash
# 1. Start containers
docker compose up -d --build

# 2. Run migrations
docker compose exec backend alembic upgrade head

# 3. Seed Course Knowledge Base
docker compose exec backend python -m app.db.seed_courses

# 4. Run Pytest Suite
docker compose exec backend pytest -v
```
