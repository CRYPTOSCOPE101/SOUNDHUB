"""SQLAlchemy setup for SoundHub."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DATABASE_URL, ensure_dirs

ensure_dirs()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate() -> None:
    """Lightweight dev migration: add missing columns to existing tables."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if not inspector.has_table("users"):
        return
    users_cols = {c["name"] for c in inspector.get_columns("users")}
    projects_cols = {c["name"] for c in inspector.get_columns("projects")}
    with engine.begin() as conn:
        if "wallet_address" not in users_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN wallet_address VARCHAR(42)"))
            conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_wallet_address ON users (wallet_address)")
            )
        for col, ddl in (
            ("release_token_id", "INTEGER"),
            ("release_contract", "VARCHAR(256)"),
            ("release_name", "VARCHAR(256)"),
            ("default_branch", "VARCHAR(64) DEFAULT 'main'"),
        ):
            if col not in projects_cols:
                conn.execute(text(f"ALTER TABLE projects ADD COLUMN {col} {ddl}"))
        if inspector.has_table("review_sessions"):
            review_cols = {c["name"] for c in inspector.get_columns("review_sessions")}
            for col, ddl in (
                ("share_password", "VARCHAR(256)"),
                ("share_expires_at", "DATETIME"),
                ("share_permission", "VARCHAR(32) DEFAULT 'comment'"),
                ("share_allowlist", "TEXT DEFAULT ''"),
            ):
                if col not in review_cols:
                    conn.execute(text(f"ALTER TABLE review_sessions ADD COLUMN {col} {ddl}"))
        if "password_hash" in users_cols and not inspector.get_columns("users"):
            pass  # no-op guard


def init_db() -> None:
    from . import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
    _migrate()
