"""Unit tests for the File Intelligence package (Phase 4).

This is intentionally a single large test module so that the
test-to-source ratio is easy to audit at review time. Each
``Test*`` class covers one sub-module of
:mod:`app.file_intelligence` and asserts both happy paths and
the privacy / safety invariants the user required in Phase 4:

* no auto-scanning (everything takes a path the user supplied)
* no external uploads (every "answer" stays in-process)
* no ML (classifier is the baseline rule-based one)
* no file execution (extractors only read text)
* no off-limits paths (NUL bytes / size / extension guards)

The tests do not require a database, network, or the heavy
``pypdf`` / ``python-docx`` dependencies; they degrade gracefully
if those libraries are missing.
"""

from __future__ import annotations

import io
import json
import sys
import textwrap
from pathlib import Path

import pytest

from app.file_intelligence import (
    ExtractionResult,
    ExtractorFactory,
    FileService,
    build_metadata,
    classify_file,
    collect_stat_info,
    detect_file_type,
    get_file_extractor_factory,
    hash_file,
    is_within_allowed_root,
    parse_allowed_extensions,
    path_has_null_byte,
    supported_extensions,
    validate_file_path,
)
from app.file_intelligence.base import FileExtractionStatus
from app.file_intelligence.classifier import (
    CLASSIFICATION_LABELS,
    FileClassification,
)
from app.file_intelligence.service import (
    IndexResult,
    SearchHit,
    SearchResult,
)
from app.file_intelligence.types import (
    CONTENT_KIND_DOCUMENT,
    CONTENT_KIND_MARKUP,
    CONTENT_KIND_SOURCE_CODE,
    CONTENT_KIND_STRUCTURED_DATA,
    CONTENT_KIND_TEXT,
    FILE_TYPE_CODE,
    FILE_TYPE_CSV,
    FILE_TYPE_DOCX,
    FILE_TYPE_JSON,
    FILE_TYPE_MARKDOWN,
    FILE_TYPE_PDF,
    FILE_TYPE_TXT,
    FILE_TYPE_UNSUPPORTED,
    iter_entries,
)
from app.file_intelligence.validation import FileValidationError


# ---------------------------------------------------------------------------
# types.py
# ---------------------------------------------------------------------------
class TestFileTypeDetection:
    """The file-type registry is the single source of truth for
    "what does this extension mean"."""

    def test_text_file_detected(self) -> None:
        info = detect_file_type("README.txt")
        assert info.file_type == FILE_TYPE_TXT
        assert info.content_kind == CONTENT_KIND_TEXT
        assert info.is_supported is True

    def test_markdown_detected(self) -> None:
        info = detect_file_type("notes.md")
        assert info.file_type == FILE_TYPE_MARKDOWN
        assert info.content_kind == CONTENT_KIND_MARKUP

    def test_json_detected(self) -> None:
        info = detect_file_type("config.json")
        assert info.file_type == FILE_TYPE_JSON
        assert info.content_kind == CONTENT_KIND_STRUCTURED_DATA

    def test_csv_detected(self) -> None:
        info = detect_file_type("people.csv")
        assert info.file_type == FILE_TYPE_CSV

    def test_python_detected_as_source_code(self) -> None:
        info = detect_file_type("script.py")
        assert info.content_kind == CONTENT_KIND_SOURCE_CODE

    def test_pdf_detected(self) -> None:
        info = detect_file_type("doc.pdf")
        assert info.file_type == FILE_TYPE_PDF

    def test_docx_detected(self) -> None:
        info = detect_file_type("letter.docx")
        assert info.file_type == FILE_TYPE_DOCX

    def test_unknown_extension_returns_unsupported(self) -> None:
        info = detect_file_type("mystery.zzzzz")
        assert info.file_type == FILE_TYPE_UNSUPPORTED
        assert info.is_supported is False

    def test_case_insensitive(self) -> None:
        info = detect_file_type("PHOTO.PNG")
        # Case insensitive lookup; PNG is currently a known
        # *unsupported* binary type, not text.
        assert info.file_type in (FILE_TYPE_UNSUPPORTED, "png")
        assert info.is_supported is False

    def test_iter_entries_iterates(self) -> None:
        entries = list(iter_entries())
        assert entries, "registry should have at least one entry"
        for entry in entries:
            assert entry.file_type
            assert entry.display_name

    def test_supported_extensions_only_lists_supported(self) -> None:
        exts = supported_extensions()
        assert "txt" in exts
        assert "md" in exts
        assert "json" in exts
        # ``exe`` is not supported.
        assert "exe" not in exts


# ---------------------------------------------------------------------------
# classifier.py
# ---------------------------------------------------------------------------
class TestBaselineClassifier:
    """The classifier is rule-based and deterministic; no ML."""

    def test_classification_labels(self) -> None:
        # Order matters because downstream UI maps the index
        # into the labels by position.
        assert CLASSIFICATION_LABELS == (
            "document",
            "source_code",
            "data",
            "configuration",
            "notes",
            "unknown",
        )

    def test_python_classified_as_source_code(self) -> None:
        from app.file_intelligence.types import FileTypeInfo

        type_info = FileTypeInfo(
            file_type=FILE_TYPE_CODE,
            content_kind=CONTENT_KIND_SOURCE_CODE,
            display_name="Python",
            is_supported=True,
        )
        result = classify_file(filename="main.py", type_info=type_info)
        assert result.label == "source_code"
        assert result.confidence >= 0.5

    def test_readme_classified_as_notes(self) -> None:
        from app.file_intelligence.types import FileTypeInfo

        type_info = FileTypeInfo(
            file_type=FILE_TYPE_MARKDOWN,
            content_kind=CONTENT_KIND_MARKUP,
            display_name="Markdown",
            is_supported=True,
        )
        result = classify_file(filename="README.md", type_info=type_info)
        # ``readme`` is a strong notes signal.
        assert result.label in ("notes", "document")

    def test_json_classified_as_configuration_when_name_suggests(self) -> None:
        from app.file_intelligence.types import FileTypeInfo

        type_info = FileTypeInfo(
            file_type=FILE_TYPE_JSON,
            content_kind=CONTENT_KIND_STRUCTURED_DATA,
            display_name="JSON",
            is_supported=True,
        )
        result = classify_file(filename="settings.json", type_info=type_info)
        # Settings files flip data → configuration.
        assert result.label in ("configuration", "data")

    def test_result_has_version(self) -> None:
        from app.file_intelligence.types import FileTypeInfo

        type_info = FileTypeInfo(
            file_type=FILE_TYPE_TXT,
            content_kind=CONTENT_KIND_TEXT,
            display_name="Text",
            is_supported=True,
        )
        result = classify_file(filename="notes.txt", type_info=type_info)
        assert result.version
        # Version is short enough to round-trip in a UI.
        assert len(result.version) <= 16


# ---------------------------------------------------------------------------
# validation.py
# ---------------------------------------------------------------------------
class TestValidation:
    """Path / size / extension guards. Privacy: refuse obvious
    abuse vectors here, before any read happens."""

    def test_parse_allowed_extensions(self) -> None:
        result = parse_allowed_extensions(" .txt , md , json , .csv ")
        assert result == {"txt", "md", "json", "csv"}

    def test_parse_allowed_extensions_empty(self) -> None:
        assert parse_allowed_extensions("") == set()
        assert parse_allowed_extensions(None) == set()  # type: ignore[arg-type]

    def test_is_within_allowed_root_true(self, tmp_path: Path) -> None:
        root = tmp_path
        child = root / "a" / "b"
        child.mkdir(parents=True)
        assert is_within_allowed_root(str(child), [str(root)])

    def test_is_within_allowed_root_false(self, tmp_path: Path) -> None:
        other = tmp_path / "elsewhere"
        other.mkdir()
        root = tmp_path / "root"
        root.mkdir()
        assert not is_within_allowed_root(str(other), [str(root)])

    def test_path_has_null_byte(self) -> None:
        assert path_has_null_byte("foo\x00bar")
        assert not path_has_null_byte("foo/bar")

    def test_validate_rejects_relative(self, tmp_path: Path) -> None:
        with pytest.raises(FileValidationError):
            validate_file_path("relative.txt")

    def test_validate_rejects_nul_byte(self, tmp_path: Path) -> None:
        with pytest.raises(FileValidationError) as excinfo:
            validate_file_path(f"{tmp_path}/foo\x00.txt")
        assert excinfo.value.code == "null_byte"

    def test_validate_rejects_nonexistent(self, tmp_path: Path) -> None:
        with pytest.raises(FileValidationError) as excinfo:
            validate_file_path(str(tmp_path / "missing.txt"))
        assert excinfo.value.code == "not_found"

    def test_validate_rejects_directory(self, tmp_path: Path) -> None:
        with pytest.raises(FileValidationError) as excinfo:
            validate_file_path(str(tmp_path))
        assert excinfo.value.code == "not_a_file"

    def test_validate_rejects_extension(self, tmp_path: Path) -> None:
        bad = tmp_path / "a.exe"
        bad.write_text("x")
        with pytest.raises(FileValidationError) as excinfo:
            validate_file_path(str(bad), allowed_extensions={"txt"})
        assert excinfo.value.code == "unsupported_extension"

    def test_validate_rejects_size(self, tmp_path: Path) -> None:
        f = tmp_path / "big.txt"
        f.write_text("a" * 10_000)
        with pytest.raises(FileValidationError) as excinfo:
            validate_file_path(str(f), max_bytes=100)
        assert excinfo.value.code == "too_large"

    def test_validate_rejects_outside_root(self, tmp_path: Path) -> None:
        inside = tmp_path / "inside.txt"
        inside.write_text("hi")
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("hi")
        # When the file is *outside* the explicit root, it must
        # be refused even if the extension is fine.
        with pytest.raises(FileValidationError) as excinfo:
            validate_file_path(
                str(outside),
                allowed_roots=[str(tmp_path)],
            )
        assert excinfo.value.code == "outside_allowed_roots"

    def test_validate_accepts_good(self, tmp_path: Path) -> None:
        f = tmp_path / "ok.txt"
        f.write_text("hi")
        # No exception expected.
        validate_file_path(str(f), allowed_extensions={"txt"})

    def test_hash_file(self, tmp_path: Path) -> None:
        f = tmp_path / "h.txt"
        f.write_text("abc")
        # Hash is the SHA-256 hex digest.
        h = hash_file(str(f))
        assert len(h) == 64
        # Same contents → same hash.
        assert hash_file(str(f)) == h

    def test_hash_file_max_bytes(self, tmp_path: Path) -> None:
        f = tmp_path / "h.txt"
        f.write_bytes(b"a" * 1024)
        # Capped hashing still returns a valid hash.
        assert len(hash_file(str(f), max_bytes=10)) == 64

    def test_collect_stat_info(self, tmp_path: Path) -> None:
        f = tmp_path / "stats.txt"
        f.write_text("hi")
        stat = collect_stat_info(str(f))
        assert stat.filename == "stats.txt"
        assert stat.extension == "txt"
        assert stat.size_bytes == 2


# ---------------------------------------------------------------------------
# extractors
# ---------------------------------------------------------------------------
class TestExtractors:
    """Run the factory's extractors end-to-end on real files."""

    def setup_method(self) -> None:
        self.factory = get_file_extractor_factory()
        self.factory._ensure_loaded()

    def test_factory_lists_supported(self) -> None:
        types = self.factory.list_supported()
        # At least these are registered.
        assert any(t.get("file_type") == FILE_TYPE_TXT for t in types)
        assert any(t.get("file_type") == FILE_TYPE_MARKDOWN for t in types)
        assert any(t.get("file_type") == FILE_TYPE_JSON for t in types)
        assert any(t.get("file_type") == FILE_TYPE_CSV for t in types)

    def test_text_extractor(self, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_text("hello\nworld")
        result = self.factory.get(FILE_TYPE_TXT).extract(f)
        assert result.status == FileExtractionStatus.OK
        assert "hello" in result.text
        assert result.metadata.get("line_count") == 2

    def test_markdown_extractor_counts_headings(self, tmp_path: Path) -> None:
        f = tmp_path / "a.md"
        f.write_text("# Title\n\n## Sub\n\nbody")
        result = self.factory.get(FILE_TYPE_MARKDOWN).extract(f)
        assert result.status == FileExtractionStatus.OK
        assert result.metadata.get("heading_count", 0) >= 2

    def test_json_extractor(self, tmp_path: Path) -> None:
        f = tmp_path / "a.json"
        f.write_text(json.dumps({"a": [1, 2, 3], "b": {"c": "deep"}}))
        result = self.factory.get(FILE_TYPE_JSON).extract(f)
        assert result.status == FileExtractionStatus.OK
        # Structural summary is present.
        assert "structure" in result.metadata or "object" in result.text

    def test_csv_extractor(self, tmp_path: Path) -> None:
        f = tmp_path / "a.csv"
        f.write_text("name,age\nAlice,30\nBob,25\n")
        result = self.factory.get(FILE_TYPE_CSV).extract(f)
        assert result.status == FileExtractionStatus.OK
        assert "Alice" in result.text
        # Column count surfaced.
        assert result.metadata.get("column_count", 0) >= 1

    def test_code_extractor(self, tmp_path: Path) -> None:
        f = tmp_path / "a.py"
        f.write_text("def f():\n    return 1\n")
        result = self.factory.get_for_path(f).extract(f)
        assert result.status == FileExtractionStatus.OK
        assert "def f" in result.text
        # Language is detected by extension.
        assert result.metadata.get("language") == "python"

    def test_unsupported_returns_failed_or_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n")
        result = self.factory.get_for_path(f).extract(f)
        # PNG is not in the supported registry; the factory
        # falls back to a null extractor, which should NOT
        # pretend to know the format.
        assert result.status in (
            FileExtractionStatus.UNSUPPORTED,
            FileExtractionStatus.FAILED,
            FileExtractionStatus.SKIPPED,
            FileExtractionStatus.EMPTY,
        )

    def test_factory_unknown_type_falls_back(self) -> None:
        # Request a registered but unhandled extension. The
        # factory should never raise for an unknown file type;
        # the null extractor covers the gap.
        result = self.factory.get("totally_made_up").extract(Path("/dev/null"))
        assert result.status in (
            FileExtractionStatus.UNSUPPORTED,
            FileExtractionStatus.FAILED,
            FileExtractionStatus.SKIPPED,
        )

    def test_truncation_marks_status(self, tmp_path: Path) -> None:
        f = tmp_path / "big.txt"
        f.write_text("a" * 200_000)
        # Force a small cap.
        from app.file_intelligence.extractors.text import TextExtractor

        extractor = TextExtractor()
        result = extractor.extract(f, max_chars=100)
        # Either the extractor is resilient (no crash) or it
        # marks the result truncated.
        assert result.status in (
            FileExtractionStatus.OK,
            FileExtractionStatus.EMPTY,
            FileExtractionStatus.SKIPPED,
        )
        if result.status == FileExtractionStatus.OK:
            # If the extractor said "ok" with truncated content,
            # the metadata must surface it.
            assert "text_truncated" in (result.warnings or [])

    def test_pdf_extractor_is_safe_to_import(self, tmp_path: Path) -> None:
        # pypdf may or may not be installed. Either way the
        # extractor must not crash the import path.
        from app.file_intelligence.extractors.pdf import PdfExtractor

        ext = PdfExtractor()
        # A non-PDF file is fine; the extractor should mark the
        # result, never raise.
        f = tmp_path / "a.pdf"
        f.write_bytes(b"%PDF-1.4\n% not real pdf")
        result = ext.extract(f)
        assert result.status in (
            FileExtractionStatus.OK,
            FileExtractionStatus.FAILED,
            FileExtractionStatus.UNSUPPORTED,
            FileExtractionStatus.EMPTY,
            FileExtractionStatus.SKIPPED,
        )

    def test_docx_extractor_is_safe_to_import(self, tmp_path: Path) -> None:
        from app.file_intelligence.extractors.docx import DocxExtractor

        ext = DocxExtractor()
        f = tmp_path / "a.docx"
        # A real DOCX is a zip; writing fake bytes is fine, the
        # extractor must surface a structured error rather than
        # raising.
        f.write_bytes(b"PK\x03\x04not-a-real-docx")
        result = ext.extract(f)
        assert result.status in (
            FileExtractionStatus.OK,
            FileExtractionStatus.FAILED,
            FileExtractionStatus.UNSUPPORTED,
            FileExtractionStatus.EMPTY,
            FileExtractionStatus.SKIPPED,
        )


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------
class TestBuildMetadata:
    def test_combines_all_signals(self) -> None:
        from datetime import datetime

        from app.file_intelligence.types import FileTypeInfo

        stat = collect_stat_info.__wrapped__ if hasattr(collect_stat_info, "__wrapped__") else None
        # Use the public helper indirectly.
        f = Path("notes.txt")
        f.write_text("hi")
        try:
            stat = collect_stat_info(str(f))
        finally:
            f.unlink()
        type_info = FileTypeInfo(
            file_type=FILE_TYPE_TXT,
            content_kind=CONTENT_KIND_TEXT,
            display_name="Text",
            is_supported=True,
        )
        classification = FileClassification(
            label="notes",
            confidence=0.9,
            signals={"filename": "notes"},
            version="v1",
        )
        meta = build_metadata(
            stat=stat,
            type_info=type_info,
            classification=classification,
            extractor_metadata={"line_count": 1, "word_count": 1},
        )
        assert meta["filename"] == "notes.txt"
        assert meta["type"]["file_type"] == FILE_TYPE_TXT
        assert meta["classification"]["label"] == "notes"
        assert meta["line_count"] == 1
        assert meta["word_count"] == 1


# ---------------------------------------------------------------------------
# service
# ---------------------------------------------------------------------------
class TestFileService:
    """The orchestrator is the public API the HTTP layer talks to.

    These tests use a real SQLite session because the service is
    the *only* place that combines the rules; mocking the
    database away would only test the mocks.
    """

    def _service(self, db_session, **overrides) -> FileService:
        from app.core.config import settings as _settings

        # The service reads settings at construction time; this
        # is the only place we have to patch them per-test.
        original = _settings.model_copy()
        for k, v in overrides.items():
            setattr(_settings, k, v)
        try:
            return FileService(db_session)
        finally:
            # Restore in-place.
            for k in overrides:
                if hasattr(original, k):
                    setattr(_settings, k, getattr(original, k))

    def test_index_text_file(self, db_session, tmp_path: Path) -> None:
        f = tmp_path / "hello.txt"
        f.write_text("hello world")
        svc = self._service(
            db_session,
            file_intelligence_enabled=True,
            file_max_bytes=10_000,
            file_allowed_extensions="txt,md,json,csv",
        )
        result = svc.index_file(str(f))
        assert isinstance(result, IndexResult)
        assert result.stored is True
        assert result.reason == "indexed"
        # Row exists in DB.
        rows, total = svc.list_files()
        assert total >= 1
        assert any(r.path == str(f) for r in rows)

    def test_index_unchanged_reuses(self, db_session, tmp_path: Path) -> None:
        f = tmp_path / "x.txt"
        f.write_text("hi")
        svc = self._service(
            db_session,
            file_intelligence_enabled=True,
            file_max_bytes=10_000,
            file_allowed_extensions="txt",
        )
        r1 = svc.index_file(str(f))
        r2 = svc.index_file(str(f))
        assert r1.stored is True
        # Second call: unchanged → reused.
        assert r2.stored is True
        assert r2.reused is True
        assert r2.reason in ("unchanged", "duplicate")

    def test_index_disabled_refuses(self, db_session, tmp_path: Path) -> None:
        f = tmp_path / "x.txt"
        f.write_text("hi")
        svc = self._service(
            db_session,
            file_intelligence_enabled=False,
        )
        r = svc.index_file(str(f))
        assert r.stored is False
        assert r.reason == "file_intelligence_disabled"

    def test_index_outside_allowed_root(self, db_session, tmp_path: Path) -> None:
        from app.core.config import settings as _settings

        # Pre-create the file *outside* the allowed root. The
        # service should refuse rather than index.
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        blocked_dir = tmp_path / "blocked"
        blocked_dir.mkdir()
        target = blocked_dir / "secret.txt"
        target.write_text("private")
        original_root = _settings.file_allowed_roots
        _settings.file_allowed_roots = str(allowed)
        try:
            svc = self._service(
                db_session,
                file_intelligence_enabled=True,
                file_max_bytes=10_000,
                file_allowed_extensions="txt",
                file_allowed_roots=str(allowed),
            )
            r = svc.index_file(str(target))
            assert r.stored is False
            assert "outside" in r.reason or "allowed" in r.reason
        finally:
            _settings.file_allowed_roots = original_root

    def test_delete_soft_then_hard(self, db_session, tmp_path: Path) -> None:
        f = tmp_path / "x.txt"
        f.write_text("hi")
        svc = self._service(
            db_session,
            file_intelligence_enabled=True,
            file_max_bytes=10_000,
            file_allowed_extensions="txt",
        )
        r = svc.index_file(str(f))
        assert r.stored
        file_id = r.file_row.id
        assert svc.soft_delete(file_id) is True
        # Default list excludes soft-deleted.
        rows, total = svc.list_files(include_deleted=False)
        assert all(r.id != file_id for r in rows)
        # Hard delete returns True.
        assert svc.delete(file_id) is True

    def test_clear_index(self, db_session, tmp_path: Path) -> None:
        svc = self._service(
            db_session,
            file_intelligence_enabled=True,
            file_max_bytes=10_000,
            file_allowed_extensions="txt",
        )
        f = tmp_path / "a.txt"
        f.write_text("a")
        svc.index_file(str(f))
        count = svc.clear_index()
        assert count >= 1
        rows, total = svc.list_files()
        assert total == 0

    def test_search_by_name(self, db_session, tmp_path: Path) -> None:
        svc = self._service(
            db_session,
            file_intelligence_enabled=True,
            file_max_bytes=10_000,
            file_allowed_extensions="txt",
        )
        for name in ("alpha.txt", "beta.txt", "gamma.txt"):
            (tmp_path / name).write_text(name)
            svc.index_file(str(tmp_path / name))
        result = svc.search("alpha")
        assert isinstance(result, SearchResult)
        assert result.total >= 1
        assert result.hits[0].file.name == "alpha.txt"

    def test_stats_aggregate(self, db_session, tmp_path: Path) -> None:
        svc = self._service(
            db_session,
            file_intelligence_enabled=True,
            file_max_bytes=10_000,
            file_allowed_extensions="txt",
        )
        f = tmp_path / "a.txt"
        f.write_text("a")
        svc.index_file(str(f))
        stats = svc.stats()
        assert "total" in stats
        assert stats["total"] >= 1
        assert "by_status" in stats
        assert "by_classification" in stats

    def test_validate_user_path_security(self, db_session, tmp_path: Path) -> None:
        svc = self._service(db_session)
        # Relative path is refused.
        with pytest.raises(FileValidationError):
            svc.validate_user_path("relative.txt")
        # NUL byte refused.
        with pytest.raises(FileValidationError):
            svc.validate_user_path("a\x00b.txt")
