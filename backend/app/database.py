from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine() -> Engine | None:
    settings = get_settings()
    if not settings.database_url:
        return None

    return create_engine(settings.database_url, pool_pre_ping=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False) if engine else None


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database() -> dict[str, str]:
    if engine is None:
        return {
            "status": "not_configured",
            "message": "DATABASE_URL is not set",
        }

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "message": "Database connection verified"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def create_database_tables() -> dict[str, str]:
    if engine is None:
        return {
            "status": "skipped",
            "message": "DATABASE_URL is not set",
        }

    # Import models before create_all so SQLAlchemy metadata is populated.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    return {"status": "ok", "message": "Database tables are ready"}
