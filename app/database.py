"""
Phase 3: Database Layer

Configures the async SQLAlchemy engine, session factory, and declarative base.
Call `await init_db()` once at application startup to create all tables.
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Async engine — connects to SQLite via aiosqlite driver
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True to log all SQL for debugging
    future=True,
)

# Session factory — use this to open DB sessions throughout the app
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Shared declarative base — all ORM models inherit from this."""
    pass


async def init_db() -> None:
    """
    Creates all database tables defined by ORM models (migration-free).
    Safe to call repeatedly — only creates tables that don't already exist.
    """
    async with engine.begin() as conn:
        # Import models here to ensure they are registered on Base before create_all
        from app import models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
