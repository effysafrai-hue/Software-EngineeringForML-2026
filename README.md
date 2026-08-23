# SE_ML_effy

Full-stack application built with **FastAPI** (Python 3.12) with JWT Authentication, Calendar Events & Gemini AI Assistant, **React + Vite + TypeScript + Tailwind CSS**, and **PostgreSQL 16**, fully containerized with **Docker Compose** and hot-reloading.

## Features

- **Semantic AI Intent Understanding**: Understands tasks, appointments, implied deadlines, reschedules, cancellations, agenda lookups, ambiguity clarification, and greetings by meaning rather than rigid keyword matching.
- **Auto-Model Resolution**: Discovers active Gemini models supporting `generateContent` (e.g. `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-flash-latest`, `gemini-pro-latest`).
- **Personal Calendar**: Monthly & weekly views, date-range filtering, and interactive create/edit/delete event modal dialogs.
- **Authentication & Security**: Email/password signup, bcrypt hashing, in-memory JWT access token (30m) + refresh token, and SlowAPI rate limiting (5 req/min).
- **Persistent Chat History**: `chat_messages` table retaining all user prompts and assistant replies.
- **Docker Compose**: Seamless containerized local development with instant hot-reloading.

## Quick Start

### 1. Configure Environment Variables
```bash
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY
```

### 2. Launch Services
Start all containers with hot reload:
```bash
docker compose up --build
```

### 3. Run Database Migrations
Apply all migrations:
```bash
docker compose exec backend alembic upgrade head
```

### 4. Run Pytest Test Suite
Run automated backend tests covering all intent categories:
```bash
docker compose exec backend pytest -v
```

### 5. Access the Application
- **Frontend App & AI Calendar**: [http://localhost:5173](http://localhost:5173)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend API Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
