# SE_ML_effy

Full-stack application built with **FastAPI** (Python 3.12) with JWT Authentication, Calendar Events & rate limiting, **React + Vite + TypeScript + Tailwind CSS**, and **PostgreSQL 16**, fully containerized with **Docker Compose** and hot-reloading.

## Features

- **Authentication**: Email/password signup, password hashing (bcrypt), JWT access token (30 min) in memory + refresh token, and SlowAPI rate limiting (5 req/min).
- **Personal Calendar**: Full monthly & weekly calendar views, date range filtering, create/edit/delete event modal dialogs with start/end time validation.
- **Role Isolation**: User events are strictly scoped in database queries (`403 Forbidden` if attempting to touch another user's event).
- **Docker Compose**: Seamless local development with backend & frontend hot-reloading.

## Quick Start

### 1. Configure Environment Variables
```bash
cp .env.example .env
```

### 2. Launch Services
Start all containers with hot reload:
```bash
docker compose up --build
```

### 3. Run Database Migrations
Apply all migrations creating `users` and `events` tables:
```bash
docker compose exec backend alembic upgrade head
```

### 4. Run Pytest Test Suite
Run automated backend unit and integration tests:
```bash
docker compose exec backend pytest -v
```

### 5. Access the Application
- **Frontend App**: [http://localhost:5173](http://localhost:5173)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend API Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
