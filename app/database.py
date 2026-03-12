"""Database engine and session for Ansible UI."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./data/ansible_ui.db",
)
# Sync URL for SQLAlchemy create_engine (use aiosqlite only with async)
SYNC_DATABASE_URL = DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://", 1)

engine = create_engine(
    SYNC_DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in SYNC_DATABASE_URL else {},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables and data directory for SQLite. Migrate existing DBs (add new columns)."""
    if "sqlite" in SYNC_DATABASE_URL:
        os.makedirs("data", exist_ok=True)
    from app import models  # noqa: F401 - register models
    Base.metadata.create_all(bind=engine)
    # Migration: add Git columns to projects (SQLite; no-op if already present)
    if "sqlite" in SYNC_DATABASE_URL:
        from sqlalchemy import text
        with engine.connect() as conn:
            for col, sql in [
                ("git_url", "ALTER TABLE projects ADD COLUMN git_url VARCHAR(512)"),
                ("git_branch", "ALTER TABLE projects ADD COLUMN git_branch VARCHAR(64)"),
                ("git_credential_id", "ALTER TABLE projects ADD COLUMN git_credential_id INTEGER"),
            ]:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    pass
            for col, sql in [
                ("schedule_enabled", "ALTER TABLE job_templates ADD COLUMN schedule_enabled BOOLEAN DEFAULT 0"),
                ("schedule_cron", "ALTER TABLE job_templates ADD COLUMN schedule_cron VARCHAR(128)"),
                ("schedule_tz", "ALTER TABLE job_templates ADD COLUMN schedule_tz VARCHAR(64)"),
            ]:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    pass
