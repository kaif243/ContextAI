"""Local, deterministic sensitive-data detector.

This module identifies likely secret material in plaintext clipboard
content using regex + a small Luhn check for credit-card-shaped numbers.
It is **NOT** an ML model and it is **NOT** a perfect secret scanner —
it errs toward privacy (false positives are better than leaked
credentials).

Design constraints
------------------
  * Pure stdlib. No external dependencies.
  * Deterministic. Same input -> same output.
  * Auditable. Every rule name is a public string in
    ``SensitiveMatch.rule_name`` so callers can show *why* content was
    redacted.
  * Local only. No network calls, no external services.

The detector never raises; if a regex is broken it returns "no match"
for that rule. This keeps the clipboard pipeline safe to call on
arbitrary user input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional


# A canonical set of rule names. Keep stable — they are part of the API
# contract (the schema exposes ``sensitive_reasons`` as a list of these
# strings) and they show up in user-facing "why was this redacted?"
# explanations.
SENSITIVE_RULE_NAMES: tuple[str, ...] = (
    "openai_api_key",
    "anthropic_api_key",
    "google_api_key",
    "github_pat",
    "github_fine_grained_pat",
    "slack_token",
    "stripe_secret",
    "aws_access_key",
    "aws_secret_key",
    "private_key_pem",
    "bearer_token",
    "authorization_header",
    "password_assignment",
    "generic_secret_assignment",
    "credit_card_number",
    "jwt",
    "ssh_private_key_marker",
    "connection_string",
)


@dataclass
class SensitiveMatch:
    """A single match produced by the detector."""

    rule_name: str
    start: int
    end: int
    # The matched substring (or a redacted preview for very long matches).
    matched: str

    def to_dict(self) -> dict:
        return {
            "rule_name": self.rule_name,
            "start": self.start,
            "end": self.end,
            "matched": self.matched,
        }


@dataclass
class SensitiveDetectionResult:
    """Result of running the detector on a piece of text."""

    is_sensitive: bool
    matches: list[SensitiveMatch] = field(default_factory=list)
    # Pre-computed redacted preview of the text. Safe to display.
    redacted_text: str = ""

    def to_dict(self) -> dict:
        return {
            "is_sensitive": self.is_sensitive,
            "match_count": len(self.matches),
            "rule_names": sorted({m.rule_name for m in self.matches}),
            "redacted_text": self.redacted_text,
        }


# ---------------------------------------------------------------------------
# Rule catalogue
# ---------------------------------------------------------------------------
# Each rule is ``(name, compiled_regex)``. The detector tries every rule;
# matches are merged and sorted. The pipeline is intentionally
# conservative: high-precision patterns first, broader patterns later.
# ---------------------------------------------------------------------------
def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.MULTILINE)


_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Provider-shaped keys (very high precision).
    (
        "openai_api_key",
        _compile(r"sk-[A-Za-z0-9]{20,}(?:T3BlbkFJ[A-Za-z0-9]{20,})?"),
    ),
    (
        "anthropic_api_key",
        _compile(r"sk-ant-(?:api03-)?[A-Za-z0-9_\-]{20,}"),
    ),
    (
        "google_api_key",
        _compile(r"AIza[0-9A-Za-z_\-]{35}"),
    ),
    (
        "github_pat",
        _compile(r"ghp_[A-Za-z0-9]{30,}"),
    ),
    (
        "github_fine_grained_pat",
        _compile(r"github_pat_[A-Za-z0-9_]{60,}"),
    ),
    (
        "slack_token",
        _compile(r"xox[abprs]-[A-Za-z0-9\-]{10,}"),
    ),
    (
        "stripe_secret",
        _compile(r"sk_(?:live|test)_[A-Za-z0-9]{20,}"),
    ),
    (
        "aws_access_key",
        _compile(r"AKIA[0-9A-Z]{16}"),
    ),
    # AWS secret keys are paired with the access key; we look for the
    # common assignment shape.
    (
        "aws_secret_key",
        _compile(
            r"(?i)aws[_\-]?secret[_\-]?(?:access[_\-]?)?key[^A-Za-z0-9]{0,5}"
            r"([A-Za-z0-9/+=]{40})"
        ),
    ),
    # PEM private keys (RSA, EC, OPENSSH, ...).
    (
        "private_key_pem",
        _compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
    ),
    (
        "ssh_private_key_marker",
        _compile(r"-----BEGIN OPENSSH PRIVATE KEY-----"),
    ),
    # JWT: three base64url segments separated by dots.
    (
        "jwt",
        _compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    ),
    # HTTP authorization headers (Bearer / Basic).
    (
        "bearer_token",
        _compile(r"(?im)^authorization\s*:\s*bearer\s+[A-Za-z0-9._\-]{8,}"),
    ),
    (
        "authorization_header",
        _compile(r"(?im)^authorization\s*:\s*basic\s+[A-Za-z0-9+/=]{4,}"),
    ),
    # Assignment-shaped secrets: ``password=...`` / ``token: ...``.
    (
        "password_assignment",
        _compile(
            r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"<>,;]{4,}['\"]?"
        ),
    ),
    (
        "generic_secret_assignment",
        _compile(
            r"(?i)\b(?:api[_\-]?key|secret|token|access[_\-]?key|client[_\-]?secret)"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9._\-/+=]{8,}['\"]?"
        ),
    ),
    # Database / cloud connection strings. These often contain passwords.
    (
        "connection_string",
        _compile(
            r"(?i)(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp|mssql)"
            r"://[^\s:@/]+:[^\s@/]+@"
        ),
    ),
    # Credit-card shaped numbers; the Luhn check below filters false
    # positives before we report a match.
    (
        "credit_card_number",
        _compile(r"\b(?:\d[ -]?){13,19}\b"),
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _luhn_check(digits: str) -> bool:
    """Return True iff ``digits`` is a Luhn-valid number.

    Used to avoid false-positive credit-card detections on arbitrary
    long digit strings (order numbers, UUIDs, etc.).
    """
    digits = re.sub(r"\D", "", digits)
    if not (13 <= len(digits) <= 19):
        return False
    total = 0
    parity = (len(digits) - 2) % 2
    for i, ch in enumerate(digits):
        n = ord(ch) - 48
        if i % 2 == parity:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _redact_match(text: str, start: int, end: int) -> str:
    """Return a redacted preview for a sensitive match.

    Shows the first 2 and last 2 characters and replaces the middle
    with bullets. Never returns the original secret material, even when
    the match is short.
    """
    raw = text[start:end]
    if len(raw) <= 6:
        return "*" * len(raw)
    return raw[:2] + "*" * min(8, len(raw) - 4) + raw[-2:]


def _build_redacted_text(text: str, matches: list[SensitiveMatch]) -> str:
    """Replace every match in ``text`` with a redacted preview, keeping
    the rest of the text intact. The returned string is safe to log /
    display in the UI.
    """
    if not matches:
        return text
    out: list[str] = []
    cursor = 0
    for m in sorted(matches, key=lambda x: x.start):
        if m.start < cursor:
            # Overlapping matches: skip the second one to avoid
            # double-substitution that would leak material.
            continue
        out.append(text[cursor:m.start])
        out.append(_redact_match(text, m.start, m.end))
        cursor = m.end
    out.append(text[cursor:])
    return "".join(out)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def detect_sensitive(text: str) -> SensitiveDetectionResult:
    """Run every rule in the catalogue against ``text``.

    Args:
        text: Arbitrary clipboard text. Empty input is safe and returns
            a non-sensitive result with no matches.

    Returns:
        A ``SensitiveDetectionResult`` with:
          * ``is_sensitive`` — True iff at least one rule fired.
          * ``matches``      — every individual hit.
          * ``redacted_text``— a display-safe version of the input.

    Never raises; broken rules simply produce no matches.
    """
    if not text:
        return SensitiveDetectionResult(is_sensitive=False, matches=[], redacted_text="")

    matches: list[SensitiveMatch] = []
    for rule_name, pattern in _RULES:
        try:
            for m in pattern.finditer(text):
                # Special case: credit cards need a Luhn check to avoid
                # false positives on arbitrary long digit strings.
                if rule_name == "credit_card_number" and not _luhn_check(m.group(0)):
                    continue
                matches.append(
                    SensitiveMatch(
                        rule_name=rule_name,
                        start=m.start(),
                        end=m.end(),
                        matched=_redact_match(text, m.start(), m.end()),
                    )
                )
        except re.error:
            # Bad regex — skip this rule rather than crashing the
            # pipeline. (Defensive; should never happen with our
            # static catalogue.)
            continue

    # De-duplicate exact (start, end, rule_name) tuples — different
    # rules can hit the same span (e.g. ``private_key_pem`` and
    # ``ssh_private_key_marker``).
    seen: set[tuple[int, int, str]] = set()
    deduped: list[SensitiveMatch] = []
    for m in matches:
        key = (m.start, m.end, m.rule_name)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)

    return SensitiveDetectionResult(
        is_sensitive=len(deduped) > 0,
        matches=deduped,
        redacted_text=_build_redacted_text(text, deduped),
    )


def iter_rules() -> Iterable[tuple[str, re.Pattern[str]]]:
    """Expose the rule catalogue for inspection / tests."""
    return _RULES
