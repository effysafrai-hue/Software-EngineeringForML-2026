from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import auth
from app.core.config import settings
from app.core.limiter import limiter

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Full-stack SE_ML_effy FastAPI backend with JWT Auth & Postgres",
    version="0.1.0",
)

# SlowAPI Rate Limiter Setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint returning application status."""
    return {"status": "ok"}
