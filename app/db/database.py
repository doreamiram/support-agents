import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_DEFAULT_URL = os.getenv("DATABASE_URL", "sqlite:///./modelyo_support.db")


class Base(DeclarativeBase):
    pass


def make_engine(url: str = _DEFAULT_URL):
    return create_engine(url, connect_args={"check_same_thread": False})


def make_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Module-level defaults used by the running application.
_engine = make_engine()
SessionLocal: sessionmaker[Session] = make_session_factory(_engine)


def init_db(engine=None) -> None:
    """Create all tables. Safe to call multiple times (CREATE TABLE IF NOT EXISTS)."""
    import app.db.models  # noqa: F401 — registers all ORM models on Base
    target = engine or _engine
    Base.metadata.create_all(bind=target)


def get_db():
    """FastAPI dependency — yields a DB session and closes it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
