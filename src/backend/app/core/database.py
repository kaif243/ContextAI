"""Database configuration and session management."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings, database_settings
from app.models.base import BaseModel

# Ensure data directory exists
settings.data_dir.mkdir(parents=True, exist_ok=True)

# Create engine with SQLite-specific settings
connect_args: dict = {}
if database_settings.url.startswith("sqlite"):
    # SQLite-specific configuration
    connect_args = {
        "check_same_thread": False,
        "timeout": 30,
    }

engine_kwargs: dict = {
    "echo": database_settings.echo,
    "connect_args": connect_args,
    "pool_pre_ping": True,
}

# SQLite doesn't support pool_size and max_overflow
if not database_settings.url.startswith("sqlite"):
    engine_kwargs["pool_size"] = database_settings.pool_size
    engine_kwargs["max_overflow"] = database_settings.max_overflow

engine = create_engine(database_settings.url, **engine_kwargs)


# Enable foreign keys for SQLite
if database_settings.url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn: object, connection_record: object) -> None:
        """Enable SQLite pragmas for better compatibility."""
        import sqlite3

        if isinstance(dbapi_conn, sqlite3.Connection):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()


# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Single base reference for all database tables
Base = BaseModel


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.

    Yields:
        Database session that auto-closes after use.

    Example:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database tables.

    Creates all tables defined in the models.
    For production, prefer using Alembic migrations.
    """
    # Import all models to ensure they are registered
    from app.models import (
        user,
        settings as settings_model,
        clipboard,
        file_index,
        memory,
        agent,
        screenshot,
    )

    BaseModel.metadata.create_all(bind=engine)


def reset_db() -> None:
    """
    Reset database - drops all tables and recreates them.

    WARNING: This will delete all data. Use only in development/test.
    """
    BaseModel.metadata.drop_all(bind=engine)
    BaseModel.metadata.create_all(bind=engine)
