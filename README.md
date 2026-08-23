# SE_ML_effy

Full-stack application skeleton built with **FastAPI** (Python 3.12), **React + Vite + TypeScript + Tailwind CSS**, and **PostgreSQL 16**, fully containerized with **Docker Compose** and hot-reloading support.

## Project Structure

```
SE_ML_effy/
├── backend/
│   ├── alembic/              # Alembic database migration scripts
│   │   ├── versions/
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── app/
│   │   ├── core/
│   │   │   └── config.py     # Application configuration & settings
│   │   ├── db/
│   │   │   └── session.py    # SQLAlchemy engine & session factory
│   │   └── main.py           # FastAPI entrypoint with GET /health
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
├── docker-compose.yml        # Multi-container orchestration (Hot Reloading)
└── README.md
```

## Quick Start

### 1. Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & Docker Compose (v2+)

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 3. Launch Services
Start all containers with hot reload:
```bash
docker compose up --build
```

### 4. Access the Application
- **Frontend Dashboard**: [http://localhost:5173](http://localhost:5173)
- **Backend API Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **PostgreSQL Database**: `localhost:5432` (`user: postgres`, `password: postgres`, `db: se_ml_effy`)

### 5. Running Database Migrations
To create and run Alembic migrations inside the backend container:
```bash
# Generate a new migration
docker compose exec backend alembic revision --autogenerate -m "initial migration"

# Apply migrations
docker compose exec backend alembic upgrade head
```

### 6. Stop Services
```bash
docker compose down
# To also remove postgres volume data:
docker compose down -v
```
