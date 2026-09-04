"""Baseline (rule-based) content classifier for clipboard text.

This is a deterministic, transparent classifier. It is **NOT machine
learning** — no model is trained, no probabilities are learned from
data, and there is no calibrated confidence. The reported "confidence"
is a heuristic strength indicator of how strongly the rules fired.

Design constraints
------------------
  * No external dependencies. Pure stdlib.
  * Deterministic. Same input -> same output.
  * Auditable. The label set and rule catalogue are constants in this
    file, not learned from data.
  * The interface in ``app.classification.content_base`` is the single
    point of truth — a real ML model can replace this implementation
    without touching call sites.

Detection order
---------------
The classifier tries each label in priority order. The first label
whose rules match wins. Order matters: JSON before code (so a JSON
object isn't mislabelled as code), URL before email (so a URL that
happens to contain an ``@`` isn't mislabelled as email), etc.
"""

from __future__ import annotations

import json
import re
from typing import Iterable

from app.classification.content_base import (
    CLIPBOARD_CONTENT_LABELS,
    ContentClassifier,
    ContentInput,
    ContentResult,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Rule catalogue
# ---------------------------------------------------------------------------
# Each rule returns True iff the text "looks like" the label. Rules are
# pure regex / structural checks; no semantic inference.
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_WINDOWS_PATH_RE = re.compile(r"^[a-zA-Z]:[\\/](?:[^\\/:*?\"<>|\r\n]+[\\/]?)*$")
_POSIX_PATH_RE = re.compile(r"^(?:/|~/?)(?:[^/\0]+/)*[^/\0]+$")
_FILE_URI_RE = re.compile(r"^file://[^\s]+$", re.IGNORECASE)

# Code signals: classic markers in popular languages. We intentionally
# avoid over-fitting to any single language; the classifier reports
# ``code`` if the text *looks* like source.
_CODE_RULES: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*def\s+\w+\([^)]*\)\s*(?:->\s*\S+)?\s*:", re.MULTILINE),
    re.compile(r"^\s*class\s+\w+\s*[:\(]", re.MULTILINE),
    re.compile(r"^\s*(?:import|from)\s+\w+(?:\s+import\s+[^\n]+)?", re.MULTILINE),
    re.compile(r"^\s*function\s+\w+\s*\(", re.MULTILINE),
    re.compile(r"^\s*(?:public|private|protected)\s+[\w<>,\[\]]+\s+\w+\s*\(", re.MULTILINE),
    re.compile(r"^\s*#include\s*[<\"][^>\"]+[>\"]", re.MULTILINE),
    re.compile(r"^\s*(?:if|else|elif|for|while|switch|case|return)\b", re.MULTILINE),
    re.compile(r"^#!/.+", re.MULTILINE),  # shebang
    re.compile(r"\bconsole\.log\(", re.IGNORECASE),
    re.compile(r"^\s*(?:var|let|const)\s+\w+\s*=", re.MULTILINE),
    re.compile(r"^\s*<\?php\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*(?:pub\s+)?fn\s+\w+\s*\(", re.MULTILINE),
)

# A "long single line" of balanced code-shape punctuation is a soft
# code signal (e.g. ``a = {x: 1, y: 2}; return a;``).
_CODE_PUNCTUATION_RE = re.compile(r"[{};=<>]")


def _looks_like_url(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    # Common cases: must be a single line, no spaces in the body.
    if any(c.isspace() for c in text):
        return False
    return bool(_URL_RE.match(text))


def _looks_like_email(text: str) -> bool:
    text = text.strip()
    if not text or any(c.isspace() for c in text):
        return False
    return bool(_EMAIL_RE.match(text))


def _looks_like_file_path(text: str) -> bool:
    text = text.strip()
    if not text or any(c.isspace() for c in text):
        return False
    if _WINDOWS_PATH_RE.match(text) or _POSIX_PATH_RE.match(text) or _FILE_URI_RE.match(text):
        # A bare file name like "notes.txt" is not a path. Require at
        # least one separator.
        return ("/" in text) or ("\\" in text) or text.startswith("file:")
    return False


def _looks_like_json(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    if not (text.startswith("{") and text.endswith("}")) and not (
        text.startswith("[") and text.endswith("]")
    ):
        return False
    try:
        json.loads(text)
    except (ValueError, TypeError):
        return False
    return True


def _looks_like_code(text: str) -> bool:
    # Empty / whitespace-only text is never code.
    if not text or not text.strip():
        return False
    # Already classified as a single other type? Skip — we rely on the
    # caller's priority order, so this is only called for leftover text.
    hits = sum(1 for p in _CODE_RULES if p.search(text))
    if hits >= 1:
        return True
    # Heuristic: a multi-line block where most lines look like code.
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 3:
        code_like_lines = 0
        for ln in lines:
            stripped = ln.lstrip()
            if (
                stripped.startswith(("def ", "class ", "import ", "from ", "function ",
                                     "var ", "let ", "const ", "if ", "else ", "for ",
                                     "while ", "return ", "pub ", "fn ", "//", "#", "/*"))
                or _CODE_PUNCTUATION_RE.search(stripped)
            ):
                code_like_lines += 1
        if code_like_lines / len(lines) >= 0.6:
            return True
    return False


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------
class BaselineContentClassifier(ContentClassifier):
    """Deterministic rule-based clipboard content classifier.

    NOT an ML model. The reported "confidence" is a heuristic indicator
    of how strongly the rules fired, not a calibrated probability.
    """

    version = "baseline-content-1"

    def classify(self, data: ContentInput) -> ContentResult:
        text = (data.text or "").strip()
        signals: dict[str, Any] = {
            "char_count": len(data.text or ""),
            "word_count": len((data.text or "").split()),
            "source_app": data.source_app,
        }

        if not text:
            return ContentResult(
                label="unknown",
                confidence=0.0,
                signals={**signals, "reason": "empty_text"},
                version=self.version,
            )

        # Priority order: each check populates ``label`` only if not
        # already set, and contributes a heuristic confidence.
        label: str | None = None
        confidence = 0.0
        rule_hits: list[str] = []

        if _looks_like_url(text):
            label = "url"
            confidence = 0.95
            rule_hits.append("url_pattern")
        elif _looks_like_email(text):
            label = "email"
            confidence = 0.95
            rule_hits.append("email_pattern")
        elif _looks_like_file_path(text):
            label = "file_path"
            confidence = 0.9
            rule_hits.append("file_path_pattern")
        elif _looks_like_json(text):
            label = "json"
            confidence = 0.95
            rule_hits.append("json_parse_ok")
        elif _looks_like_code(text):
            label = "code"
            # Heuristic: more rule hits -> higher confidence.
            hits = sum(1 for p in _CODE_RULES if p.search(text))
            confidence = min(0.95, 0.6 + 0.1 * hits)
            rule_hits.append(f"code_rules:{hits}")

        if label is None:
            label = "text"
            # Plain text confidence: highest when there's no structure
            # at all, lower for very long blocks (which *might* be code
            # we didn't recognise).
            char_count = signals["char_count"]
            if char_count < 4_000:
                confidence = 0.6
            else:
                confidence = 0.4
            rule_hits.append("fallback_text")

        signals["rule_hits"] = rule_hits
        return ContentResult(
            label=label,
            confidence=round(confidence, 3),
            signals=signals,
            version=self.version,
        )


def iter_rules() -> Iterable[re.Pattern[str]]:
    """Expose the regex catalogue for inspection / tests."""
    return _CODE_RULES
