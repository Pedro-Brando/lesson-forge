import pytest
from sqlalchemy import JSON, String, create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, GenerationLog


@pytest.fixture
def db_session():
    """Create an in-memory SQLite session for testing.

    Excludes GenerationLog table (uses JSONB/UUID not supported by SQLite).
    """
    engine = create_engine("sqlite:///:memory:")

    # Create all tables except GenerationLog (JSONB/UUID incompatible with SQLite)
    tables_to_create = [
        t for t in Base.metadata.sorted_tables if t.name != "generation_logs"
    ]
    Base.metadata.create_all(engine, tables=tables_to_create)

    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
