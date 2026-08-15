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
                ("round_number", "INTEGER DEFAULT 1"),
                ("feedback_due_at", "DATETIME"),
                ("feedback_owner", "VARCHAR(128) DEFAULT ''"),
                ("included_rounds", "INTEGER DEFAULT 1"),
                ("rounds_open", "BOOLEAN DEFAULT 1"),
                ("deposit_due_cents", "INTEGER"),
                ("deposit_status", "VARCHAR(32) DEFAULT 'none'"),
                ("extra_round_price_cents", "INTEGER"),
                ("rounds_paid", "INTEGER DEFAULT 0"),
                ("portfolio_public", "BOOLEAN DEFAULT 0"),
                ("watermark_enabled", "BOOLEAN DEFAULT 1"),
                ("service_type", "VARCHAR(32) DEFAULT 'mix'"),
                ("genre", "VARCHAR(128) DEFAULT ''"),
                ("goal", "VARCHAR(64) DEFAULT ''"),
                ("deadline_at", "DATETIME"),
                ("review_start_at", "DATETIME"),
                ("reference_links", "TEXT DEFAULT ''"),
                ("do_not_change", "TEXT DEFAULT ''"),
                ("required_deliverables", "TEXT DEFAULT ''"),
                ("retention_until", "DATETIME"),
                ("recall_fee_cents", "INTEGER"),
                ("revision_fee_cents", "INTEGER"),
                ("change_rounds_granted", "INTEGER DEFAULT 0"),
                ("reminders_enabled", "BOOLEAN DEFAULT 1"),
                ("reminder_categories", "TEXT DEFAULT ''"),
                ("reminders_client_opt_out", "BOOLEAN DEFAULT 0"),
                ("client_email", "VARCHAR(256) DEFAULT ''"),
                ("approval_preset", "VARCHAR(32) DEFAULT 'solo_client'"),
            ):
                if col not in review_cols:
                    conn.execute(text(f"ALTER TABLE review_sessions ADD COLUMN {col} {ddl}"))
        if inspector.has_table("review_versions"):
            v_cols = {c["name"] for c in inspector.get_columns("review_versions")}
            if "round_number" not in v_cols:
                conn.execute(text("ALTER TABLE review_versions ADD COLUMN round_number INTEGER DEFAULT 1"))
            if "watermark_sha" not in v_cols:
                conn.execute(text("ALTER TABLE review_versions ADD COLUMN watermark_sha VARCHAR(64)"))
        if inspector.has_table("review_comments"):
            cm_cols = {c["name"] for c in inspector.get_columns("review_comments")}
            for col, ddl in (
                ("status", "VARCHAR(32) DEFAULT 'open'"),
                ("fixed_in", "INTEGER"),
                ("verified_at", "DATETIME"),
                ("voice_blob_sha", "VARCHAR(64)"),
                ("voice_format", "VARCHAR(16) DEFAULT ''"),
                ("voice_duration_s", "FLOAT DEFAULT 0"),
                ("transcript", "TEXT DEFAULT ''"),
            ):
                if col not in cm_cols:
                    conn.execute(text(f"ALTER TABLE review_comments ADD COLUMN {col} {ddl}"))
        if inspector.has_table("review_approvals"):
            ap_cols = {c["name"] for c in inspector.get_columns("review_approvals")}
            if "role" not in ap_cols:
                conn.execute(text("ALTER TABLE review_approvals ADD COLUMN role VARCHAR(32) DEFAULT ''"))
        if inspector.has_table("change_orders"):
            co_cols = {c["name"] for c in inspector.get_columns("change_orders")}
            for col, ddl in (
                ("quote_expires_at", "DATETIME"),
                ("quote_version", "INTEGER DEFAULT 0"),
            ):
                if col not in co_cols:
                    conn.execute(text(f"ALTER TABLE change_orders ADD COLUMN {col} {ddl}"))
        if inspector.has_table("version_comparisons"):
            cmp_cols = {c["name"] for c in inspector.get_columns("version_comparisons")}
            if "stem_logical_name" not in cmp_cols:
                conn.execute(
                    text("ALTER TABLE version_comparisons ADD COLUMN stem_logical_name VARCHAR(32)")
                )
        if inspector.has_table("release_packages"):
            pkg_cols = {c["name"] for c in inspector.get_columns("release_packages")}
            for col, ddl in (
                ("amount_due_cents", "INTEGER"),
                ("currency", "VARCHAR(8) DEFAULT 'usd'"),
                ("stripe_session_id", "VARCHAR(128)"),
                ("template", "VARCHAR(32) DEFAULT 'custom'"),
                ("plugin_manifest", "TEXT DEFAULT ''"),
                ("session_manifest", "JSON DEFAULT '{}'"),
                ("consolidate_audio", "BOOLEAN DEFAULT 0"),
                ("archive_expires_at", "DATETIME"),
                ("archive_status", "VARCHAR(32) DEFAULT 'available_now'"),
                ("last_verified_opened_at", "DATETIME"),
                ("force_locked_reason", "TEXT DEFAULT ''"),
                ("force_locked_by", "VARCHAR(128) DEFAULT ''"),
                ("invoice_due_at", "DATETIME"),
            ):
                if col not in pkg_cols:
                    conn.execute(text(f"ALTER TABLE release_packages ADD COLUMN {col} {ddl}"))
        if inspector.has_table("release_deliverables"):
            del_cols = {c["name"] for c in inspector.get_columns("release_deliverables")}
            if "channels" not in del_cols:
                conn.execute(text("ALTER TABLE release_deliverables ADD COLUMN channels INTEGER"))
        if "password_hash" in users_cols and not inspector.get_columns("users"):
            pass  # no-op guard


def init_db() -> None:
    from . import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
    _migrate()
