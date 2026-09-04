"""Simple, regex-based entity extraction for OCR text.

This is a deliberately small, deterministic extractor used by the screen
intelligence pipeline. It is NOT an NER model and it is not ML — it is
the same kind of baseline the spec calls out for the activity classifier
and exists so the screen Q&A flow has structured context to work with.

It is intentionally conservative: it prefers precision over recall and
caps the number of items returned per category.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_DATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(r"\b\d{1,2}-\d{1,2}-\d{2,4}\b"),
    re.compile(
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:\s+\d{4})?\b", re.IGNORECASE),
)

_TIME_PATTERN = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\s?(?:am|pm))?\b", re.IGNORECASE)

_URL_PATTERN = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")

_AMOUNT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\$\s?\d{1,3}(?:[,]\d{3})*(?:\.\d{2})?"),
    re.compile(r"€\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?"),
    re.compile(r"£\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?"),
    re.compile(r"\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})\s?(?:usd|eur|gbp|inr)\b", re.IGNORECASE),
)

# "Capitalised Words" used as a naive name detector. The constraints keep
# the false-positive rate manageable for receipts and documents.
_NAME_PATTERN = re.compile(r"\b[A-Z][a-z]{1,}(?:\s+[A-Z][a-z]{1,}){0,3}\b")

# Phone numbers — loose on purpose, but requires a country code or
# dashes / parens to look phone-shaped.
_PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}\b")

_MAX_PER_CATEGORY = 25


@dataclass
class ExtractedEntities:
    """Structured representation of entities found in OCR text."""

    dates: list[str]
    times: list[str]
    urls: list[str]
    emails: list[str]
    amounts: list[str]
    names: list[str]
    phone_numbers: list[str]
    extra: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dates": self.dates,
            "times": self.times,
            "urls": self.urls,
            "emails": self.emails,
            "amounts": self.amounts,
            "names": self.names,
            "phone_numbers": self.phone_numbers,
            "extra": self.extra,
        }


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower() if item else ""
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def extract_entities(text: str, *, max_per_category: int = _MAX_PER_CATEGORY) -> ExtractedEntities:
    """Extract structured entities from OCR text.

    Args:
        text: Raw OCR text. Empty input is safe.
        max_per_category: Cap the size of each list so a noisy OCR pass
            cannot produce a giant response payload.

    Returns:
        An ``ExtractedEntities`` populated with the unique matches.
    """
    if not text:
        return ExtractedEntities(
            dates=[],
            times=[],
            urls=[],
            emails=[],
            amounts=[],
            names=[],
            phone_numbers=[],
            extra={"char_count": 0, "word_count": 0},
        )

    dates: list[str] = []
    for pat in _DATE_PATTERNS:
        dates.extend(m.group(0) for m in pat.finditer(text))
    times = [m.group(0) for m in _TIME_PATTERN.finditer(text)]
    urls = [m.group(0).rstrip(".,;:") for m in _URL_PATTERN.finditer(text)]
    emails = [m.group(0) for m in _EMAIL_PATTERN.finditer(text)]
    amounts: list[str] = []
    for pat in _AMOUNT_PATTERNS:
        amounts.extend(m.group(0) for m in pat.finditer(text))
    names = [m.group(0) for m in _NAME_PATTERN.finditer(text)]
    phones = [m.group(0) for m in _PHONE_PATTERN.finditer(text)]

    return ExtractedEntities(
        dates=_dedupe_keep_order(dates)[:max_per_category],
        times=_dedupe_keep_order(times)[:max_per_category],
        urls=_dedupe_keep_order(urls)[:max_per_category],
        emails=_dedupe_keep_order(emails)[:max_per_category],
        amounts=_dedupe_keep_order(amounts)[:max_per_category],
        names=_dedupe_keep_order(names)[:max_per_category],
        phone_numbers=_dedupe_keep_order(phones)[:max_per_category],
        extra={"char_count": len(text), "word_count": len(text.split())},
    )
