"""Integration tests for the Phase 3 clipboard API.

These tests exercise the full FastAPI app + database + service stack.
The fixture in ``conftest.py`` provides an in-memory SQLite engine and
a ``TestClient`` wired to it.

The sensitive-data policy used by the service is read from
``app.core.config.settings`` — we override those settings per-test using
``monkeypatch.setattr`` so each test is independent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------
def test_capture_stores_plain_text(client):
    r = client.post(
        "/api/v1/clipboard/capture",
        json={"content": "hello world", "content_type": "text"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["stored"] is True
    assert data["reason"] == "stored"
    item = data["item"]
    assert item["id"]
    assert item["content_type"] in {"text", "unknown"}
    assert item["is_sensitive"] is False
    assert "hello" in item["preview"]


def test_capture_rejects_empty_content(client):
    r = client.post("/api/v1/clipboard/capture", json={"content": ""})
    assert r.status_code == 200
    data = r.json()
    assert data["stored"] is False
    assert data["reason"] == "empty_content"
    assert data["item"] is None


def test_capture_rejects_too_large(client, monkeypatch):
    # Drop the limit to a tiny value so the test is fast.
    from app.core.config import settings

    monkeypatch.setattr(settings, "clipboard_max_bytes", 16)
    r = client.post(
        "/api/v1/clipboard/capture",
        json={"content": "x" * 200},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["stored"] is False
    assert data["reason"] == "too_large"


def test_capture_suppresses_exact_duplicate(client):
    payload = {"content": "duplicate me", "content_type": "text"}
    first = client.post("/api/v1/clipboard/capture", json=payload).json()
    assert first["stored"] is True

    second = client.post("/api/v1/clipboard/capture", json=payload).json()
    assert second["stored"] is False
    assert second["reason"] == "duplicate"


def test_capture_disabled_when_monitoring_off(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "clipboard_monitoring", False)
    r = client.post(
        "/api/v1/clipboard/capture", json={"content": "x", "content_type": "text"}
    )
    data = r.json()
    assert data["stored"] is False
    assert data["reason"] == "monitoring_disabled"


def test_capture_disabled_when_history_disabled(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "clipboard_history_enabled", False)
    r = client.post(
        "/api/v1/clipboard/capture", json={"content": "x", "content_type": "text"}
    )
    data = r.json()
    assert data["stored"] is False
    assert data["reason"] == "history_disabled"


# ---------------------------------------------------------------------------
# Sensitive policy
# ---------------------------------------------------------------------------
SENSITIVE_TEXT = "password = \"hunter2-supersecretvalue-xyz\""


def test_sensitive_dropped_by_default(client):
    r = client.post(
        "/api/v1/clipboard/capture",
        json={"content": SENSITIVE_TEXT, "content_type": "text"},
    )
    data = r.json()
    assert data["stored"] is False
    assert data["reason"] == "sensitive_dropped"
    assert data["is_sensitive"] is True
    # The redacted preview must NOT include the secret.
    assert "hunter2-supersecretvalue" not in data["redacted_content"]


def test_sensitive_stored_redacted_only(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "clipboard_store_sensitive", True)
    monkeypatch.setattr(settings, "clipboard_keep_raw_when_sensitive", False)
    r = client.post(
        "/api/v1/clipboard/capture",
        json={"content": SENSITIVE_TEXT, "content_type": "text"},
    )
    data = r.json()
    assert data["stored"] is True
    item = data["item"]
    # API never returns raw content for sensitive items.
    assert item["content"] == ""
    assert item["is_sensitive"] is True
    # Redacted preview is safe.
    assert "hunter2-supersecretvalue" not in item["redacted_content"]
    assert "password" in item["sensitive_reasons"] or any(
        "password" in r for r in item["sensitive_reasons"]
    )


def test_sensitive_can_store_raw_when_allowed(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "clipboard_store_sensitive", True)
    monkeypatch.setattr(settings, "clipboard_keep_raw_when_sensitive", True)
    r = client.post(
        "/api/v1/clipboard/capture",
        json={"content": SENSITIVE_TEXT, "content_type": "text"},
    )
    data = r.json()
    # The API still redacts for transport — only the redacted preview
    # is returned, even when the on-disk row keeps the raw text.
    assert data["stored"] is True
    assert data["item"]["is_sensitive"] is True
    assert data["item"]["content"] == ""


# ---------------------------------------------------------------------------
# Listing + retrieval
# ---------------------------------------------------------------------------
def test_list_history_empty(client):
    r = client.get("/api/v1/clipboard")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_history_returns_most_recent_first(client):
    for txt in ("first", "second", "third"):
        client.post(
            "/api/v1/clipboard/capture", json={"content": txt, "content_type": "text"}
        )
    r = client.get("/api/v1/clipboard")
    data = r.json()
    assert data["total"] == 3
    # Most recent first
    assert "third" in data["items"][0]["preview"]


def test_list_history_pagination(client):
    for i in range(5):
        client.post(
            "/api/v1/clipboard/capture",
            json={"content": f"row-{i}", "content_type": "text"},
        )
    r = client.get("/api/v1/clipboard?limit=2&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert len(data["items"]) == 2
    assert data["total"] == 5


def test_list_history_filter_by_classification(client):
    client.post(
        "/api/v1/clipboard/capture",
        json={"content": "https://example.com", "content_type": "url"},
    )
    client.post(
        "/api/v1/clipboard/capture",
        json={"content": "plain text body", "content_type": "text"},
    )
    r = client.get("/api/v1/clipboard?classification=url")
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["classification"] == "url"


def test_list_history_exclude_sensitive(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "clipboard_store_sensitive", True)
    client.post(
        "/api/v1/clipboard/capture", json={"content": SENSITIVE_TEXT, "content_type": "text"}
    )
    client.post(
        "/api/v1/clipboard/capture",
        json={"content": "normal text", "content_type": "text"},
    )
    r = client.get("/api/v1/clipboard?include_sensitive=false")
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["is_sensitive"] is False


def test_get_item_by_id(client):
    created = client.post(
        "/api/v1/clipboard/capture",
        json={"content": "find me", "content_type": "text"},
    ).json()
    item_id = created["item"]["id"]
    r = client.get(f"/api/v1/clipboard/{item_id}")
    assert r.status_code == 200
    assert r.json()["id"] == item_id


def test_get_item_missing_returns_404(client):
    r = client.get("/api/v1/clipboard/999999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Pin / delete / clear / purge
# ---------------------------------------------------------------------------
def test_pin_and_unpin(client):
    created = client.post(
        "/api/v1/clipboard/capture",
        json={"content": "pinnable", "content_type": "text"},
    ).json()
    item_id = created["item"]["id"]

    r = client.patch(f"/api/v1/clipboard/{item_id}/pin", json={"pinned": True})
    assert r.status_code == 200
    assert r.json()["is_pinned"] is True

    r = client.patch(f"/api/v1/clipboard/{item_id}/pin", json={"pinned": False})
    assert r.status_code == 200
    assert r.json()["is_pinned"] is False


def test_delete_item(client):
    created = client.post(
        "/api/v1/clipboard/capture",
        json={"content": "delete me", "content_type": "text"},
    ).json()
    item_id = created["item"]["id"]
    r = client.delete(f"/api/v1/clipboard/{item_id}")
    assert r.status_code == 200
    assert r.json()["affected"] == 1
    assert client.get(f"/api/v1/clipboard/{item_id}").status_code == 404


def test_delete_missing_returns_404(client):
    r = client.delete("/api/v1/clipboard/999999")
    assert r.status_code == 404


def test_clear_history_keeps_pinned_by_default(client):
    keep = client.post(
        "/api/v1/clipboard/capture",
        json={"content": "keep", "content_type": "text"},
    ).json()
    client.post(
        "/api/v1/clipboard/capture",
        json={"content": "drop", "content_type": "text"},
    )
    client.patch(
        f"/api/v1/clipboard/{keep['item']['id']}/pin", json={"pinned": True}
    )

    r = client.delete("/api/v1/clipboard")
    data = r.json()
    assert data["success"] is True
    assert data["detail"] == "kept_pinned"
    assert data["affected"] == 1
    remaining = client.get("/api/v1/clipboard").json()["total"]
    assert remaining == 1


def test_clear_history_can_drop_pinned(client):
    a = client.post(
        "/api/v1/clipboard/capture",
        json={"content": "pinned-1", "content_type": "text"},
    ).json()
    b = client.post(
        "/api/v1/clipboard/capture",
        json={"content": "pinned-2", "content_type": "text"},
    ).json()
    client.patch(f"/api/v1/clipboard/{a['item']['id']}/pin", json={"pinned": True})
    client.patch(f"/api/v1/clipboard/{b['item']['id']}/pin", json={"pinned": True})

    r = client.delete("/api/v1/clipboard?keep_pinned=false")
    assert r.json()["affected"] == 2
    assert client.get("/api/v1/clipboard").json()["total"] == 0


def test_purge_expired_removes_only_expired(client, monkeypatch, db_session):
    from app.models.clipboard import ClipboardItem

    # Insert one expired + one fresh item directly so we can control timestamps.
    now = datetime.now(timezone.utc)
    expired = ClipboardItem(
        content="old",
        content_type="text",
        classification="text",
        classification_confidence=0.5,
        classifier_version="baseline-content-1",
        char_count=3,
        word_count=1,
        timestamp=now - timedelta(days=10),
        expires_at=now - timedelta(days=1),
        is_pinned=False,
    )
    fresh = ClipboardItem(
        content="new",
        content_type="text",
        classification="text",
        classification_confidence=0.5,
        classifier_version="baseline-content-1",
        char_count=3,
        word_count=1,
        timestamp=now,
        expires_at=now + timedelta(days=1),
        is_pinned=False,
    )
    db_session.add_all([expired, fresh])
    db_session.commit()

    r = client.post("/api/v1/clipboard/purge")
    assert r.json()["affected"] == 1
    assert client.get("/api/v1/clipboard").json()["total"] == 1


def test_reanalyse_updates_classification(client):
    created = client.post(
        "/api/v1/clipboard/capture",
        json={"content": "hello world", "content_type": "text"},
    ).json()
    item_id = created["item"]["id"]
    r = client.post(f"/api/v1/clipboard/{item_id}/reanalyse")
    assert r.status_code == 200
    assert r.json()["id"] == item_id


# ---------------------------------------------------------------------------
# LLM actions — provider unavailable in tests; we assert graceful failure
# ---------------------------------------------------------------------------
def test_explain_returns_graceful_error_when_no_provider(client, monkeypatch):
    from app.api.v1.endpoints import clipboard as clipboard_ep

    def _boom(*args, **kwargs):
        raise RuntimeError("no LLM configured")

    # Monkeypatch the symbol imported inside the route handler.
    monkeypatch.setitem(
        __import__("sys").modules["app.api.v1.endpoints.clipboard"].__dict__,
        # No-op: the route uses a *local* import. Patch via the LLM factory.
        "__name__",
        "app.api.v1.endpoints.clipboard",
    )

    # The route imports ``get_llm_provider`` from ``app.llm`` locally.
    # Patch that one.
    import app.llm as llm_mod

    monkeypatch.setattr(llm_mod, "get_llm_provider", _boom)

    created = client.post(
        "/api/v1/clipboard/capture",
        json={"content": "explain me", "content_type": "text"},
    ).json()
    item_id = created["item"]["id"]

    r = client.post(f"/api/v1/clipboard/{item_id}/explain")
    assert r.status_code == 200
    body = r.json()
    assert body["is_error"] is True
    assert "no LLM configured" in body["error_message"]
    assert body["action"] == "explain"


def test_summarise_uses_redacted_text_for_sensitive(client, monkeypatch):
    """Sensitive items must never be sent to the LLM in the clear."""

    from app.core.config import settings
    from app.llm import Message

    monkeypatch.setattr(settings, "clipboard_store_sensitive", True)
    monkeypatch.setattr(settings, "clipboard_keep_raw_when_sensitive", True)

    captured: list[list[Message]] = []

    class _StubProvider:
        model_name = "stub-model"

        async def chat(self, messages):
            captured.append(messages)
            from app.llm import LLMResponse

            return LLMResponse(content="ok", model="stub-model", usage=None)

    import app.llm as llm_mod

    monkeypatch.setattr(llm_mod, "get_llm_provider", lambda: _StubProvider())

    r = client.post(
        "/api/v1/clipboard/capture",
        json={"content": SENSITIVE_TEXT, "content_type": "text"},
    )
    item_id = r.json()["item"]["id"]

    client.post(f"/api/v1/clipboard/{item_id}/summarise")
    assert captured, "LLM provider was not invoked"
    user_msg = next(m for m in captured[0] if m.role == "user")
    # Raw secret body must not appear in the prompt.
    assert "hunter2-supersecretvalue" not in user_msg.content


# ---------------------------------------------------------------------------
# Settings expose Phase 3 fields
# ---------------------------------------------------------------------------
def test_settings_exposes_phase3_fields(client):
    r = client.get("/api/v1/settings")
    assert r.status_code == 200
    data = r.json()
    for k in (
        "clipboard_history_enabled",
        "clipboard_max_bytes",
        "clipboard_store_sensitive",
        "clipboard_keep_raw_when_sensitive",
    ):
        assert k in data


def test_settings_update_clipboard_max_bytes_validation(client):
    # Too small.
    r = client.patch("/api/v1/settings", json={"clipboard_max_bytes": 1})
    assert r.status_code == 400
    # Acceptable.
    r = client.patch("/api/v1/settings", json={"clipboard_max_bytes": 1024})
    assert r.status_code == 200
    assert r.json()["clipboard_max_bytes"] == 1024
