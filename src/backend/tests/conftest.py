"""Pytest configuration and fixtures."""

import os
import sys
from pathlib import Path

# Add src/backend to path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test environment BEFORE importing app modules
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["DEBUG"] = "false"


@pytest.fixture(scope="function")
def test_db_engine():
    """Create a test database engine for each test function."""
    from app.models.base import BaseModel

    # Use a static pool so all connections see the same in-memory database
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Import all models to ensure they are registered with the Base
    from app.models import user, settings as settings_model, clipboard, file_index, memory, agent

    # Create all tables
    BaseModel.metadata.create_all(bind=engine)
    yield engine
    BaseModel.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(test_db_engine):
    """Create a database session for tests."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db_engine,
    )
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(test_db_engine):
    """Create a test client with the test engine."""
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.core.database import get_db

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db_engine,
    )

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
