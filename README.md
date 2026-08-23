# SE_ML_effy

Full-stack application built with **FastAPI** (Python 3.12) with JWT Authentication & rate limiting, **React + Vite + TypeScript + Tailwind CSS**, and **PostgreSQL 16**, fully containerized with **Docker Compose** and hot-reloading.

## Project Structure

```
SE_ML_effy/
├── backend/
│   ├── alembic/              # Alembic database migration scripts
│   │   ├── versions/
│   │   │   └── 001_create_users_table.py
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   └── auth.py   # /auth/signup, /auth/login, /auth/me
│   │   │   └── deps.py       # JWT get_current_user dependency
│   │   ├── core/
│   │   │   ├── config.py     # Pydantic Settings
│   │   │   ├── limiter.py    # SlowAPI rate limiter
│   │   │   └── security.py   # Bcrypt hashing & JWT utilities
│   │   ├── db/
│   │   │   └── session.py    # SQLAlchemy engine & session factory
│   │   ├── models/
│   │   │   └── user.py       # User table with JSON preferences
│   │   ├── schemas/
│   │   │   └── auth.py       # Pydantic request/response schemas
│   │   └── main.py           # FastAPI entrypoint with CORS & SlowAPI
│   ├── tests/
│   │   ├── conftest.py       # Pytest fixtures with SQLite in-memory DB
│   │   └── test_auth.py      # Auth tests (signup, login, me, validation)
│   ├── alembic.ini           # Alembic configuration
│   ├── Dockerfile            # Python 3.12 backend container
│   └── requirements.txt      # Python dependencies
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.tsx           # React UI fetching GET /health
│   │   ├── index.css         # Tailwind & theme styling
│   │   ├── main.tsx          # React application entrypoint
│   │   └── vite-env.d.ts
│   ├── Dockerfile            # Node 20 frontend container
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   └── vite.config.ts
├── .env.example              # Environment variables template
├── .gitignore
├── docker-compose.yml        # Multi-container orchestration (Compose V2)
└── README.md
```

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
Apply the initial migration creating the `users` table:
```bash
docker compose exec backend alembic upgrade head
```

### 4. Run Pytest Test Suite
Run automated backend unit and integration tests:
```bash
docker compose exec backend pytest -v
```

### 5. Access the Application
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Frontend Dashboard**: [http://localhost:5173](http://localhost:5173)
- **Backend API Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

## Authentication Endpoints

- `POST /auth/signup`: Create a new user account with email & password strength validation.
- `POST /auth/login`: Authenticate credentials, returning JWT `access_token` and `refresh_token`. Rate-limited to 5 requests/min.
- `GET /auth/me`: Protected route returning the current user's profile and preferences.
