"""Baseline, rule-based activity classifier.

NOT a machine learning model.

This is a deterministic, transparent classifier that fires a set of
weighted heuristics on the OCR text and image metadata. Each rule
contributes to a per-label score; the label with the highest score
wins, and the "confidence" is a normalised version of the gap between
the winner and runner-up.

Why start with rules?
  * Zero training data required, so the system is usable on day one.
  * Easy to inspect: ``result.signals`` shows exactly why a label was
    chosen. This matters for the user-facing "Why?" question.
  * The interface in ``app.classification.base`` is the single point of
    truth — a real ML model can replace this implementation without
    touching call sites.

Design constraints
  * No external dependencies. Pure stdlib + the already-installed
    ``Pillow`` for image-derived signals.
  * Deterministic. Same input -> same output.
  * Auditable. The label list and rule weights are constants in this
    file, not learned from data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.classification.base import (
    CLASSIFICATION_LABELS,
    ActivityClassifier,
    ClassificationInput,
    ClassificationResult,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class _Rule:
    """A single classification rule.

    A rule fires if the regex matches against the OCR text. The label
    then receives ``weight`` added to its score.
    """

    label: str
    pattern: str
    weight: float
    flags: int = re.IGNORECASE | re.MULTILINE

    def matches(self, text: str) -> int:
        """Return the number of matches for this rule."""
        if not self.pattern:
            return 0
        return len(re.findall(self.pattern, text, self.flags))


# Rule catalogue. Order does not matter; weights are tuned by hand.
_RULES: tuple[_Rule, ...] = (
    # ---- error / stack-trace signals ----
    _Rule("error", r"\b(traceback|stack ?trace|exception|error)\b", 2.0),
    _Rule("error", r"\b\d{3,4}\s+internal\s+server\s+error\b", 3.0),
    _Rule("error", r"(module|attribute|type|name|import)error", 2.5),
    _Rule("error", r"^error[:\s]", 2.0),
    _Rule("error", r"\bfailed\s+to\b", 1.0),
    # ---- code signals ----
    _Rule("code", r"^\s*def\s+\w+\(", 3.0),
    _Rule("code", r"^\s*class\s+\w+\s*[:\(]", 3.0),
    _Rule("code", r"^\s*(import|from)\s+\w+", 2.0),
    _Rule("code", r"^\s*function\s+\w+\(", 3.0),
    _Rule("code", r"^\s*(public|private|protected)\s+\w+\s*\(", 2.5),
    _Rule("code", r"^\s*(\$\s*|\>\s*|#\s*|/)[^\n]{4,}$", 1.0),
    _Rule("code", r"\bconsole\.log\b", 2.0),
    _Rule("code", r"\bprint\s*\(", 1.0),
    _Rule("code", r"^\s*[{}\[\]]\s*$", 0.3),
    # ---- receipt signals ----
    _Rule("receipt", r"\b(receipt|invoice|order\s*#|subtotal|tax|total)\b", 2.5),
    _Rule("receipt", r"\$\s?\d+\.\d{2}", 1.5),
    _Rule("receipt", r"€\s?\d+[.,]\d{2}", 1.5),
    _Rule("receipt", r"£\s?\d+[.,]\d{2}", 1.5),
    _Rule("receipt", r"\b(visa|mastercard|amex)\b", 2.0),
    # ---- timetable signals ----
    _Rule("timetable", r"\b(mon|tue|wed|thu|fri|sat|sun)day\b", 1.5),
    _Rule("timetable", r"\b\d{1,2}:\d{2}\s*(am|pm)\b", 2.0),
    _Rule("timetable", r"\b(class|lecture|lab|seminar|tutorial)\b", 2.0),
    _Rule("timetable", r"\b(spring|fall|summer|winter|autumn)\s+(semester|term)\b", 3.0),
    # ---- table signals ----
    _Rule("table", r"\|.*\|.*\|", 2.0),  # markdown-style row
    _Rule("table", r"^\s*\w+(\s{2,}\w+){2,}\s*$", 1.5),  # columnar whitespace
    # ---- form signals ----
    _Rule("form", r"\b(submit|sign\s*in|log\s*in|register|forgot\s+password)\b", 2.5),
    _Rule("form", r"\b(please\s+enter|enter\s+your|required\s+field)\b", 2.0),
    # ---- webpage signals ----
    _Rule("webpage", r"https?://\S+", 1.0),
    _Rule("webpage", r"\b(navigation|navbar|sidebar|breadcrumb)\b", 2.0),
    _Rule("webpage", r"\b(home|about|contact|blog|article)\b", 0.5),
    # ---- document signals ----
    _Rule("document", r"\b(chapter|section|abstract|introduction|conclusion)\b", 2.0),
    _Rule("document", r"\b(references|bibliography|appendix)\b", 2.0),
    _Rule("document", r"\bpage\s+\d+\s+of\s+\d+\b", 3.0),
    _Rule("document", r"\b\d+\s+words?\b", 1.0),
)


# Common application → label hints. The hint is used only when the OCR
# rules produce an empty/weak result, because the user's source app is
# a very strong signal (e.g. ``code.exe`` → code).
_APP_HINTS: dict[str, str] = {
    "code": "code",
    "code.exe": "code",
    "code - insiders": "code",
    "pycharm": "code",
    "pycharm64.exe": "code",
    "intellij": "code",
    "devenv.exe": "code",
    "sublime_text": "code",
    "terminal": "code",
    "windowsterminal": "code",
    "powershell": "code",
    "word": "document",
    "winword.exe": "document",
    "excel": "table",
    "excel.exe": "table",
    "powerpnt": "document",
    "outlook": "document",
    "chrome": "webpage",
    "msedge": "webpage",
    "firefox": "webpage",
}


def _normalise_app_name(source_app: str | None) -> str:
    if not source_app:
        return ""
    return source_app.strip().lower()


def _normalise_text(text: str) -> str:
    if not text:
        return ""
    return text.strip()


class BaselineActivityClassifier(ActivityClassifier):
    """Deterministic rule-based classifier.

    NOT an ML model. The reported "confidence" is a heuristic indicator
    of how strongly the rules fired, not a calibrated probability.
    """

    version = "baseline-1"

    def classify(self, data: ClassificationInput) -> ClassificationResult:
        """Classify the activity.

        Strategy:
          1. Score every label from rule matches.
          2. If scores are weak, fall back to the source-app hint.
          3. If both fail, return ``"unknown"`` with low confidence.
        """
        text = _normalise_text(data.ocr_text)
        scores: dict[str, float] = {label: 0.0 for label in CLASSIFICATION_LABELS}
        rule_hits: dict[str, list[dict]] = {label: [] for label in CLASSIFICATION_LABELS}

        for rule in _RULES:
            hits = rule.matches(text)
            if hits == 0:
                continue
            contribution = rule.weight * hits
            scores[rule.label] = scores.get(rule.label, 0.0) + contribution
            rule_hits[rule.label].append(
                {"pattern": rule.pattern, "weight": rule.weight, "hits": hits}
            )

        # ---- image / app signals ----
        text_density = self._text_density(text, data.image_width, data.image_height)
        # Only treat the screenshot as an "image" when the image is large
        # enough for the density reading to be meaningful. Tiny test images
        # (e.g. 64x64) with no text are not a reliable image signal — they
        # could just be empty UI, a dark screen, etc.
        if (
            text
            and text_density < 0.0005
            and data.image_width >= 800
            and data.image_height >= 600
        ):
            scores["image"] = scores.get("image", 0.0) + 1.5
            rule_hits["image"].append(
                {"pattern": "low_text_density", "weight": 1.5, "hits": 1}
            )

        app_hint = self._app_hint(data.source_app, data.window_title)
        if app_hint:
            scores[app_hint] = scores.get(app_hint, 0.0) + 1.5

        # ---- pick winner ----
        best_label, best_score = self._argmax(scores)
        sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        runner_up_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0

        signals = {
            "scores": {k: round(v, 3) for k, v in scores.items()},
            "rule_hits": {k: v for k, v in rule_hits.items() if v},
            "text_density": text_density,
            "app_hint": app_hint,
        }

        if best_score <= 0.0:
            return ClassificationResult(
                label="unknown",
                confidence=0.0,
                signals=signals,
                version=self.version,
            )

        # Heuristic confidence: 1 - 1/(1+best_score), modulated by gap to runner-up.
        raw = 1.0 - 1.0 / (1.0 + best_score)
        gap = max(0.0, best_score - runner_up_score)
        confidence = max(0.0, min(1.0, raw * 0.7 + min(gap / max(best_score, 1.0), 1.0) * 0.3))

        return ClassificationResult(
            label=best_label,
            confidence=round(confidence, 3),
            signals=signals,
            version=self.version,
        )

    @staticmethod
    def _text_density(text: str, width: int, height: int) -> float:
        if width <= 0 or height <= 0:
            return 0.0
        return len(text) / float(width * height)

    @staticmethod
    def _app_hint(source_app: str | None, window_title: str | None) -> str | None:
        if source_app:
            key = _normalise_app_name(source_app)
            base = key.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
            for candidate in (key, base):
                if candidate in _APP_HINTS:
                    return _APP_HINTS[candidate]
        if window_title:
            low = window_title.lower()
            for needle, label in _APP_HINTS.items():
                if needle in low:
                    return label
        return None

    @staticmethod
    def _argmax(scores: dict[str, float]) -> tuple[str, float]:
        best_label = "unknown"
        best_score = -1.0
        for label, score in scores.items():
            if score > best_score:
                best_score = score
                best_label = label
        if best_score < 0:
            best_score = 0.0
        return best_label, best_score


def iter_rules() -> Iterable[_Rule]:
    """Expose the rule catalogue for inspection / tests."""
    return _RULES
