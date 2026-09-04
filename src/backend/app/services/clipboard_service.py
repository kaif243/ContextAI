"""Phase 3 clipboard service.

High-level orchestration for the clipboard pipeline:

    raw text
        ↓
    validate (size, emptiness, duplicate suppression)
        ↓
    classify content type (baseline rule-based)
        ↓
    detect sensitive material (local regex + Luhn)
        ↓
    apply storage policy (drop, store raw, store redacted)
        ↓
    persist ClipboardItem
        ↓
    return sanitised record for the API

The service keeps the API layer thin: endpoints just call into it.
Service collaborators (classifier) are injected so they can be
swapped in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.classification import (
    ContentClassifier,
    ContentInput,
    get_content_classifier,
)
from app.classification.sensitive_detector import (
    SensitiveDetectionResult,
    detect_sensitive,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.models.clipboard import ClipboardItem

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass
class CaptureResult:
    """Outcome of a single ``capture`` call.

    Either a stored ``ClipboardItem`` (persisted=True) or a rejection
    reason. Always safe to serialise — raw sensitive content is
    replaced by the redacted preview when the policy is "redact".
    """

    stored: bool
    reason: str
    item: ClipboardItem | None
    # The raw text passed in, only set when the policy keeps it on disk.
    raw_content: str = ""
    is_sensitive: bool = False
    redacted_content: str = ""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class ClipboardService:
    """High-level clipboard orchestration.

    Constructed per-request (it owns a database session) and is
    intentionally stateless beyond its collaborators.
    """

    def __init__(
        self,
        db: Session,
        *,
        classifier: Optional[ContentClassifier] = None,
    ) -> None:
        self.db = db
        self.classifier = classifier or get_content_classifier()

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    @property
    def max_bytes(self) -> int:
        """Maximum size (in bytes) of accepted clipboard text."""
        return max(0, int(getattr(settings, "clipboard_max_bytes", 200_000)))

    @property
    def retention_days(self) -> int:
        """Retention window in days for stored clipboard items."""
        return max(0, int(getattr(settings, "clipboard_retention_days", 30)))

    @property
    def store_sensitive(self) -> bool:
        """Whether sensitive items are stored at all (raw or redacted)."""
        return bool(getattr(settings, "clipboard_store_sensitive", False))

    @property
    def keep_raw_when_sensitive(self) -> bool:
        """When sensitive items are stored, whether the raw content is
        kept (True) or only the redacted preview (False)."""
        return bool(getattr(settings, "clipboard_keep_raw_when_sensitive", False))

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------
    def capture(
        self,
        content: str,
        *,
        source_app: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        content_type: Optional[str] = None,
    ) -> CaptureResult:
        """Process a clipboard change event.

        The pipeline is:
          1. Validate (size + emptiness).
          2. Suppress exact duplicates against the most recent row.
          3. Classify content type (unless caller pre-classified).
          4. Run the sensitive-data detector.
          5. Apply the storage policy.
          6. Persist the row + return a ``CaptureResult``.

        Errors are converted into non-storing ``CaptureResult`` rather
        than exceptions so the Tauri poller can stay simple and the
        API can return them as a structured response.
        """
        if content is None:
            return CaptureResult(stored=False, reason="empty_content", item=None)

        if not isinstance(content, str):
            content = str(content)

        # 1. Validate size + emptiness.
        raw = content
        if not raw:
            return CaptureResult(stored=False, reason="empty_content", item=None)
        if len(raw.encode("utf-8")) > self.max_bytes:
            logger.info(
                f"clipboard.capture rejected: {len(raw.encode('utf-8'))} bytes "
                f"exceeds limit of {self.max_bytes}"
            )
            return CaptureResult(stored=False, reason="too_large", item=None)

        # 2. Suppress exact duplicates against the most recent row.
        last = (
            self.db.query(ClipboardItem)
            .order_by(ClipboardItem.timestamp.desc())
            .first()
        )
        if last is not None and last.content == raw and not last.is_sensitive:
            return CaptureResult(
                stored=False,
                reason="duplicate",
                item=last,
                raw_content="",
                is_sensitive=last.is_sensitive,
                redacted_content=last.redacted_content or "",
            )

        # 3. Classify.
        clf_result = self.classifier.classify(
            ContentInput(text=raw, source_app=source_app, metadata=metadata or {})
        )
        detected_type = content_type or clf_result.label
        # We always store the classifier version; if the caller passed
        # in their own ``content_type`` we still record what the
        # classifier would have said in ``metadata`` for diagnostics.
        if content_type and content_type != clf_result.label:
            metadata = dict(metadata or {})
            metadata.setdefault("caller_content_type", content_type)
            metadata.setdefault("classifier_content_type", clf_result.label)

        # 4. Detect sensitive material.
        sensitive: SensitiveDetectionResult = detect_sensitive(raw)
        is_sensitive = sensitive.is_sensitive

        # 5. Apply storage policy.
        if is_sensitive and not self.store_sensitive:
            # Drop entirely. The redacted preview is returned to the
            # caller for visibility but nothing is written to the DB.
            logger.info(
                f"clipboard.capture: sensitive content dropped "
                f"(rules={sorted({m.rule_name for m in sensitive.matches})})"
            )
            return CaptureResult(
                stored=False,
                reason="sensitive_dropped",
                item=None,
                raw_content="",
                is_sensitive=True,
                redacted_content=sensitive.redacted_text,
            )

        # Decide what to put in ``content``.
        stored_raw = raw
        if is_sensitive and not self.keep_raw_when_sensitive:
            stored_raw = ""  # never keep raw secret material

        # Compute the expiry timestamp from the retention policy.
        expires_at: datetime | None = None
        if self.retention_days > 0:
            expires_at = datetime.now(timezone.utc) + timedelta(days=self.retention_days)

        item = ClipboardItem(
            content=stored_raw,
            redacted_content=sensitive.redacted_text if is_sensitive else None,
            content_type=detected_type,
            classification=detected_type,
            classification_confidence=clf_result.confidence,
            classifier_version=clf_result.version,
            is_sensitive=is_sensitive,
            sensitive_reasons=",".join(
                sorted({m.rule_name for m in sensitive.matches})
            )
            if is_sensitive
            else None,
            source_app=source_app,
            metadata_json=metadata or {},
            char_count=len(raw),
            word_count=len(raw.split()),
            timestamp=datetime.now(timezone.utc),
            expires_at=expires_at,
            is_pinned=False,
            is_encrypted=False,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        logger.info(
            f"clipboard.capture stored: id={item.id} type={item.content_type} "
            f"sensitive={item.is_sensitive}"
        )
        return CaptureResult(
            stored=True,
            reason="stored",
            item=item,
            raw_content=stored_raw,
            is_sensitive=is_sensitive,
            redacted_content=item.redacted_content or "",
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def get(self, item_id: int) -> Optional[ClipboardItem]:
        return self.db.get(ClipboardItem, item_id)

    def list_history(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        content_type: Optional[str] = None,
        classification: Optional[str] = None,
        include_sensitive: bool = True,
    ) -> tuple[list[ClipboardItem], int]:
        query = self.db.query(ClipboardItem)
        if content_type:
            query = query.filter(ClipboardItem.content_type == content_type)
        if classification:
            query = query.filter(ClipboardItem.classification == classification)
        if not include_sensitive:
            query = query.filter(ClipboardItem.is_sensitive == False)  # noqa: E712
        query = query.order_by(ClipboardItem.timestamp.desc())
        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return list(items), total

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def delete(self, item_id: int) -> bool:
        item = self.db.get(ClipboardItem, item_id)
        if item is None:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

    def toggle_pin(self, item_id: int, pinned: bool) -> Optional[ClipboardItem]:
        item = self.db.get(ClipboardItem, item_id)
        if item is None:
            return None
        item.is_pinned = pinned
        self.db.commit()
        self.db.refresh(item)
        return item

    def clear_history(self, *, keep_pinned: bool = True) -> int:
        query = self.db.query(ClipboardItem)
        if keep_pinned:
            query = query.filter(ClipboardItem.is_pinned == False)  # noqa: E712
        count = query.delete()
        self.db.commit()
        return count

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------
    def purge_expired(self) -> int:
        """Delete every row whose ``expires_at`` is in the past.

        Pinned items are exempt regardless of their ``expires_at`` —
        users explicitly asked to keep them.
        """
        now = datetime.now(timezone.utc)
        query = self.db.query(ClipboardItem).filter(
            ClipboardItem.expires_at.isnot(None),
            ClipboardItem.expires_at < now,
            ClipboardItem.is_pinned == False,  # noqa: E712
        )
        count = query.delete()
        self.db.commit()
        return count

    def reclassify(self, item_id: int) -> Optional[ClipboardItem]:
        """Re-run the content classifier on a stored item."""
        item = self.db.get(ClipboardItem, item_id)
        if item is None:
            return None
        # Only re-classify non-sensitive items, because sensitive
        # items may have an empty ``content`` column.
        if item.is_sensitive:
            return item
        clf = self.classifier.classify(
            ContentInput(text=item.content, source_app=item.source_app, metadata=item.metadata_json or {})
        )
        item.classification = clf.label
        item.content_type = clf.label
        item.classification_confidence = clf.confidence
        item.classifier_version = clf.version
        meta = dict(item.metadata_json or {})
        meta["reclassified"] = True
        item.metadata_json = meta
        self.db.commit()
        self.db.refresh(item)
        return item
