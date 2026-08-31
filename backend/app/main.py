import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import auth, events, chat, shared_calendars, notifications
from app.core.config import settings
from app.core.limiter import limiter
from app.services.chat_queue import chat_queue
from app.services.notification_scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle: launch scheduler and chat worker pool."""
    logger.info("Starting notification scheduler and chat queue...")
    start_scheduler()
    await chat_queue.start()
    yield
    logger.info("Stopping notification scheduler and chat queue...")
    await chat_queue.stop()
    stop_scheduler()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Full-stack SE_ML_effy FastAPI backend with JWT Auth, Shared Calendars, Notifications, Course Grounding, Ollama & Gemini AI",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(chat.router)
app.include_router(shared_calendars.router)
app.include_router(notifications.router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}
