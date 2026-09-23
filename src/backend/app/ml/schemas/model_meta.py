"""Model metadata and version representation for Phase 5 ML artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any
from datetime import datetime


@dataclass(frozen=True)
class SchemaVersion:
    """Feature and schema version identifier."""

    major: int = 1
    minor: int = 0
    patch: int = 0

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class FeatureSchema:
    """Description of the feature schema used by a model."""

    version: SchemaVersion = field(default_factory=lambda: SchemaVersion())
    features: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": str(self.version),
            "features": list(self.features),
            "description": self.description,
        }


@dataclass(frozen=True)
class ModelMeta:
    """Local model artifact metadata — no personal data, no cloud dependency."""

    model_version: str = "unknown"
    feature_version: SchemaVersion = field(default_factory=lambda: SchemaVersion())
    created_at: str = ""
    framework: str = "scikit-learn"
    labels: tuple[str, ...] = field(default_factory=tuple)
    dataset_hash: str = ""
    evaluation_summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Ensure created_at is set if empty
        if not self.created_at:
            object.__setattr__(
                self, "created_at", datetime.utcnow().isoformat() + "Z"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "feature_version": str(self.feature_version),
            "created_at": self.created_at,
            "framework": self.framework,
            "labels": list(self.labels),
            "dataset_hash": self.dataset_hash,
            "evaluation_summary": self.evaluation_summary,
        }
