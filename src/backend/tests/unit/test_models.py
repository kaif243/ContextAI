"""Test database models."""

import pytest
from datetime import datetime, timezone


def test_user_model(db_session):
    """Test creating a User."""
    from app.models.user import User

    user = User(username="testuser", email="test@example.com")
    db_session.add(user)
    db_session.commit()

    assert user.id is not None
    assert user.username == "testuser"
    assert user.is_active is True
    assert user.is_superuser is False
    assert user.created_at is not None


def test_settings_model(db_session):
    """Test creating Settings."""
    from app.models.settings import Settings

    settings = Settings(
        hotkey="Ctrl+Space",
        llm_provider="ollama",
        llm_model="llama3.1:8b",
    )
    db_session.add(settings)
    db_session.commit()

    assert settings.id is not None
    assert settings.hotkey == "Ctrl+Space"
    assert settings.privacy_mode is False
    assert settings.clipboard_monitoring is True


def test_settings_to_dict(db_session):
    """Test Settings serialization."""
    from app.models.settings import Settings

    settings = Settings(hotkey="Ctrl+Shift+A", llm_provider="openai")
    db_session.add(settings)
    db_session.commit()

    data = settings.to_dict()
    assert data["hotkey"] == "Ctrl+Shift+A"
    assert data["llm_provider"] == "openai"
    assert "auto_start" in data
    assert "privacy_mode" in data


def test_clipboard_item_model(db_session):
    """Test creating ClipboardItem."""
    from app.models.clipboard import ClipboardItem

    item = ClipboardItem(
        content="Test clipboard content",
        content_type="text",
        timestamp=datetime.now(timezone.utc),
        char_count=21,
        word_count=3,
    )
    db_session.add(item)
    db_session.commit()

    assert item.id is not None
    assert item.content == "Test clipboard content"
    assert item.is_pinned is False
    assert item.is_encrypted is False


def test_clipboard_item_to_dict(db_session):
    """Test ClipboardItem serialization."""
    from app.models.clipboard import ClipboardItem

    item = ClipboardItem(
        content="Test",
        timestamp=datetime.now(timezone.utc),
    )
    db_session.add(item)
    db_session.commit()

    data = item.to_dict()
    assert data["id"] == str(item.id)
    assert data["content"] == "Test"
    assert data["content_type"] == "text"
    assert data["is_pinned"] is False


def test_memory_item_model(db_session):
    """Test creating MemoryItem."""
    from app.models.memory import MemoryItem

    item = MemoryItem(
        title="Test Memory",
        content="Test content",
        memory_type="note",
    )
    db_session.add(item)
    db_session.commit()

    assert item.id is not None
    assert item.title == "Test Memory"
    assert item.memory_type == "note"
    assert item.importance == "normal"
    assert item.is_pinned is False


def test_file_index_model(db_session):
    """Test creating FileIndex."""
    from app.models.file_index import FileIndex

    file = FileIndex(
        path="/tmp/test.txt",
        name="test.txt",
        file_type="text",
        extension="txt",
        size_bytes=100,
    )
    db_session.add(file)
    db_session.commit()

    assert file.id is not None
    assert file.path == "/tmp/test.txt"
    assert file.is_indexed is False
    assert file.is_deleted is False


def test_agent_task_model(db_session):
    """Test creating AgentTask."""
    from app.models.agent import AgentTask

    task = AgentTask(
        request="Find duplicate files",
        status="pending",
    )
    db_session.add(task)
    db_session.commit()

    assert task.id is not None
    assert task.status == "pending"
    assert task.total_steps == 0
    assert task.completed_steps == 0
