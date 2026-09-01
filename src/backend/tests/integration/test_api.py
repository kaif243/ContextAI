"""Integration tests for API endpoints."""

import pytest


def test_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert "timestamp" in data
    assert "services" in data
    assert "database" in data["services"]


def test_health_detailed_endpoint(client):
    """Test the detailed health check endpoint."""
    response = client.get("/api/v1/health/detailed")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "config" in data


def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "app" in data
    assert "version" in data


def test_simple_health_endpoint(client):
    """Test the simple /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_get_settings_default(client):
    """Test getting default settings."""
    response = client.get("/api/v1/settings")
    assert response.status_code == 200

    data = response.json()
    assert data["hotkey"] == "Ctrl+Space"
    assert data["llm_provider"] == "ollama"
    assert data["minimize_to_tray"] is True


def test_update_settings(client):
    """Test updating settings."""
    response = client.patch(
        "/api/v1/settings",
        json={"hotkey": "Ctrl+Shift+A", "privacy_mode": True},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["hotkey"] == "Ctrl+Shift+A"
    assert data["privacy_mode"] is True


def test_settings_persistence(client):
    """Test settings are persistent across requests."""
    # Update settings
    client.patch("/api/v1/settings", json={"hotkey": "Alt+X"})

    # Get settings
    response = client.get("/api/v1/settings")
    assert response.json()["hotkey"] == "Alt+X"


def test_get_clipboard_history_empty(client):
    """Test getting clipboard history when empty."""
    response = client.get("/api/v1/clipboard/history")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_add_clipboard_item(client):
    """Test adding a clipboard item."""
    response = client.post(
        "/api/v1/clipboard/add",
        params={"content": "Test content", "content_type": "text"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "id" in data


def test_clipboard_history_with_items(client):
    """Test clipboard history with items."""
    # Add items
    client.post("/api/v1/clipboard/add", params={"content": "Item 1"})
    client.post("/api/v1/clipboard/add", params={"content": "Item 2"})

    # Get history
    response = client.get("/api/v1/clipboard/history")
    data = response.json()

    assert data["total"] >= 2
    assert len(data["items"]) >= 2


def test_files_search(client):
    """Test file search endpoint."""
    response = client.post(
        "/api/v1/files/search",
        params={"query": "test", "limit": 10},
    )
    assert response.status_code == 200

    data = response.json()
    assert "results" in data
    assert "total" in data
    assert "query_time_ms" in data


def test_files_list(client):
    """Test file list endpoint."""
    response = client.get("/api/v1/files")
    assert response.status_code == 200

    data = response.json()
    assert "files" in data
    assert "total" in data


def test_files_index(client):
    """Test folder index endpoint."""
    response = client.post(
        "/api/v1/files/index",
        json={"folder_path": "/tmp", "recursive": True},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
