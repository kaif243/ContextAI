"""Unit tests for the Phase 3 sensitive-data detector.

The detector is deterministic, local-only, and intentionally
over-eager. These tests assert both *detection* (the right rule
fires) and *redaction* (the raw secret never appears in the
returned text).
"""

from app.classification.sensitive_detector import (
    SENSITIVE_RULE_NAMES,
    detect_sensitive,
)


def _rules_triggered(text: str) -> set[str]:
    return {m.rule_name for m in detect_sensitive(text).matches}


def test_no_match_for_normal_text():
    res = detect_sensitive("Just a normal sentence with no secrets.")
    assert res.is_sensitive is False
    assert res.matches == []
    assert res.redacted_text == "Just a normal sentence with no secrets."


def test_openai_api_key_detected_and_redacted():
    text = "Here is my key: sk-abc1234567890XYZabcdEFGHijklMNOPqrstUVWX"
    res = detect_sensitive(text)
    assert res.is_sensitive is True
    assert "openai_api_key" in _rules_triggered(text)
    # Raw key body must NOT appear in the redacted output.
    assert "abc1234567890XYZ" not in res.redacted_text


def test_anthropic_api_key_detected():
    text = "anthropic key sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890"
    assert "anthropic_api_key" in _rules_triggered(text)


def test_google_api_key_detected():
    text = "google key: AIzaSyD-1234567890abcdefghijklmnopqrstuvwxyz"
    assert "google_api_key" in _rules_triggered(text)


def test_github_personal_access_token_detected():
    text = "ghp_1234567890abcdefghijklmnopqrstuvwx"
    assert "github_pat" in _rules_triggered(text)


def test_github_fine_grained_pat_detected():
    text = "github_pat_11ABCDEFG0_abcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmnopqrstuvwxyz12"
    assert "github_fine_grained_pat" in _rules_triggered(text)


def test_slack_token_detected():
    text = "xoxb-FAKE-TEST-TOKEN-NOT-REAL"
    assert "slack_token" in _rules_triggered(text)


def test_aws_access_key_detected():
    text = "AKIAIOSFODNN7EXAMPLE"
    assert "aws_access_key" in _rules_triggered(text)


def test_private_key_pem_detected():
    text = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA...\n"
        "-----END RSA PRIVATE KEY-----\n"
    )
    assert "private_key_pem" in _rules_triggered(text)


def test_jwt_detected():
    text = (
        "Authorization: Bearer "
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    rules = _rules_triggered(text)
    assert "jwt" in rules or "bearer_token" in rules


def test_password_assignment_detected():
    text = 'password = "hunter2-cant-see-me"'
    assert "password_assignment" in _rules_triggered(text)


def test_generic_secret_assignment_detected():
    text = "secret=topsecretvalue-12345"
    assert "generic_secret_assignment" in _rules_triggered(text)


def test_credit_card_detected_with_luhn():
    # Standard Luhn-valid Visa test number.
    text = "Card: 4111 1111 1111 1111"
    assert "credit_card_number" in _rules_triggered(text)


def test_credit_card_random_digits_ignored():
    # Not Luhn valid -> should not trigger.
    text = "Random id: 4111 1111 1111 1112"
    assert "credit_card_number" not in _rules_triggered(text)


def test_connection_string_detected():
    text = "postgres://user:p@ssw0rd@db.example.com:5432/app"
    assert "connection_string" in _rules_triggered(text)


def test_redaction_preserves_text_around_secret():
    text = "before sk-abcdefghijklmnopqrstuvwxyz0123456789ABCD after"
    res = detect_sensitive(text)
    assert res.is_sensitive is True
    assert "before" in res.redacted_text
    assert "after" in res.redacted_text
    # Raw body of the secret must not survive.
    assert "abcdefghijklmnopqrstuvwxyz0123456789ABCD" not in res.redacted_text


def test_multiple_secrets_in_one_string():
    text = (
        "sk-abc1234567890XYZabcdEFGHijklMNOPqrstUVWX and "
        "AKIAIOSFODNN7EXAMPLE"
    )
    rules = _rules_triggered(text)
    assert "openai_api_key" in rules
    assert "aws_access_key" in rules


def test_known_rule_names_is_a_tuple_of_strings():
    assert isinstance(SENSITIVE_RULE_NAMES, tuple)
    for name in SENSITIVE_RULE_NAMES:
        assert isinstance(name, str)
        assert name  # non-empty
