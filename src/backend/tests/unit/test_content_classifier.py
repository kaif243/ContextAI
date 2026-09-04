"""Unit tests for the Phase 3 content classifier.

The baseline content classifier is a small rule-based pipeline.
We cover the priority order (URL > email > file_path > JSON > code > text)
plus a few edge cases that have caused regressions in the past.
"""

from app.classification import ContentInput, get_content_classifier


def _classify(text: str, **kw) -> str:
    clf = get_content_classifier()
    return clf.classify(ContentInput(text=text, **kw)).label


def test_empty_text_is_unknown():
    assert _classify("") == "unknown"


def test_plain_text():
    assert _classify("Just a normal sentence with words.") == "text"


def test_url_https():
    # The classifier expects the input to *be* a URL, not contain one.
    assert _classify("https://example.com/path?q=1") == "url"


def test_url_requires_scheme():
    # The baseline requires an explicit scheme (`http://`, `https://`,
    # `ftp://`, ...). A bare domain is treated as text — false positives
    # here would mean redacting ordinary prose.
    assert _classify("example.org") == "text"
    assert _classify("https://example.org") == "url"
    assert _classify("http://example.org") == "url"


def test_email():
    # The classifier expects the input to *be* an email.
    assert _classify("user.name+tag@sub.example.co.uk") == "email"


def test_windows_path():
    assert _classify(r"C:\Users\me\Documents\file.txt") == "file_path"


def test_posix_path():
    assert _classify("/usr/local/bin/python") == "file_path"


def test_home_path():
    # The bare tilde alone isn't a path under the current heuristic.
    assert _classify("~/projects/notes.md") == "file_path"


def test_file_uri():
    assert _classify("file:///etc/hosts") == "file_path"


def test_json_object_is_classified_as_json():
    text = '{"name": "contextai", "version": 1, "tags": ["a", "b"]}'
    assert _classify(text) == "json"


def test_json_array_is_classified_as_json():
    text = "[1, 2, 3, 4, 5]"
    assert _classify(text) == "json"


def test_invalid_json_falls_through():
    # Looks like JSON intent but is not valid — should not label as json.
    assert _classify("{not: valid, json,}") != "json"


def test_python_code_is_classified_as_code():
    text = (
        "def greet(name):\n"
        "    return f'Hello, {name}!'\n"
        "\n"
        "print(greet('world'))\n"
    )
    assert _classify(text) == "code"


def test_javascript_code_is_classified_as_code():
    text = (
        "function add(a, b) {\n"
        "  return a + b;\n"
        "}\n"
        "console.log(add(1, 2));\n"
    )
    assert _classify(text) == "code"


def test_url_wins_over_code():
    # Even if it has code-like characters, a URL is a URL.
    text = "https://example.com/api?x={}"
    assert _classify(text) == "url"


def test_email_wins_over_text():
    text = "test@example.com"
    assert _classify(text) == "email"


def test_confidence_in_range():
    clf = get_content_classifier()
    r = clf.classify(ContentInput(text="Hello world"))
    assert 0.0 <= r.confidence <= 1.0
    assert r.version  # non-empty


def test_classifier_version_is_stable():
    clf = get_content_classifier()
    r1 = clf.classify(ContentInput(text="hello"))
    r2 = clf.classify(ContentInput(text="hello"))
    assert r1.version == r2.version
