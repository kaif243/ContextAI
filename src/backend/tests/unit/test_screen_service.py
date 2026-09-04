"""Tests for the entity extractor used by the screen pipeline."""

from __future__ import annotations

from app.services.entity_extractor import extract_entities


def test_empty_text_yields_empty_lists():
    e = extract_entities("")
    assert e.dates == []
    assert e.times == []
    assert e.urls == []
    assert e.emails == []
    assert e.amounts == []
    assert e.names == []
    assert e.phone_numbers == []
    assert e.extra["char_count"] == 0
    assert e.extra["word_count"] == 0


def test_extract_iso_dates():
    e = extract_entities("Today is 2026-09-03 and tomorrow is 2026-09-04.")
    assert "2026-09-03" in e.dates
    assert "2026-09-04" in e.dates


def test_extract_slash_dates():
    e = extract_entities("Meeting 9/3/2026 and party on 10/15/26.")
    assert any("/" in d for d in e.dates)


def test_extract_month_dates():
    e = extract_entities("Class starts Sep 4, 2026 and review is on December 12.")
    joined = " ".join(e.dates).lower()
    assert "sep" in joined
    assert "december" in joined


def test_extract_times():
    e = extract_entities("Standup at 9:00 AM, lunch at 12:30 PM, deploy 14:05.")
    assert any("9:00" in t for t in e.times)
    assert any("12:30" in t for t in e.times)
    assert any("14:05" in t for t in e.times)


def test_extract_urls():
    e = extract_entities("Visit https://example.com/foo and http://docs.test/api for info.")
    assert "https://example.com/foo" in e.urls
    assert "http://docs.test/api" in e.urls


def test_extract_emails():
    e = extract_entities("Reach me at hello@example.com or support@contextai.io.")
    assert "hello@example.com" in e.emails
    assert "support@contextai.io" in e.emails


def test_extract_amounts():
    e = extract_entities("Subtotal $10.00, tax $1.50, total $11.50 USD.")
    assert any("10.00" in a for a in e.amounts)
    assert any("11.50" in a for a in e.amounts)


def test_extract_eur_and_gbp():
    e = extract_entities("Price €1,99 or £2.50.")
    assert any("€" in a for a in e.amounts)
    assert any("£" in a for a in e.amounts)


def test_extract_capitalised_names():
    e = extract_entities("Dear John Smith, please meet with Alice Johnson and Bob.")
    joined = " ".join(e.names)
    assert "John Smith" in joined
    assert "Alice Johnson" in joined


def test_extract_phone_numbers():
    e = extract_entities("Call (555) 123-4567 or +1 415-555-0199.")
    assert any("555" in p for p in e.phone_numbers)


def test_max_per_category_caps_results():
    text = " ".join(f"2026-01-{i:02d}" for i in range(1, 32))
    e = extract_entities(text, max_per_category=5)
    assert len(e.dates) == 5


def test_dedupe_preserves_order():
    e = extract_entities("Visit https://a.test then https://a.test again and https://b.test.")
    # The duplicate should be removed and order preserved.
    assert e.urls == ["https://a.test", "https://b.test"]
