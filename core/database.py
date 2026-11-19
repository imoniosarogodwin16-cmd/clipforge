import os
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event

# Determine Database URL
# Default: Local SQLite database stored in the project directory
# Cloud: Set DATABASE_URL to your free Supabase or Neon PostgreSQL connection string!
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_FILE = BASE_DIR / "clipforge.db"
DEFAULT_DB_URL = f"sqlite:///{DEFAULT_DB_FILE}"

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

# Fix Heroku/Render postgres:// prefix to postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

is_sqlite = DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
    pool_pre_ping=True
)

# Enable WAL mode and foreign keys for SQLite for high concurrency & zero file locks
if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

def init_db():
    """Initializes tables in database."""
    from core import models  # Ensure all models are registered
    SQLModel.metadata.create_all(engine)

def get_session():
    """FastAPI dependency or standalone context for database session."""
    with Session(engine) as session:
        yield session
