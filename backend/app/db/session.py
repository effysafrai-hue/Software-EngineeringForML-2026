from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

@event.listens_for(engine, "connect")
def connect(dbapi_connection, connection_record):
    try:
        from pgvector.psycopg import register_vector
        register_vector(dbapi_connection)
    except Exception:
        pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
