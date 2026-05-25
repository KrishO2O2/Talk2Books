"""
backend/tests/test_ingest.py
Talk2Books — Unit Tests for Phase 2
Spec Module 1 & 2 testing requirements:
  - Unit tests for each loader and normalization step
  - Edge cases and invalid data
  - Verify chunk sizes and overlap
  - Tests with complex formatting and multiple languages
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from langchain_core.documents import Document

# Adjust import path as needed when running from project root
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingest import (
    normalize_text,
    detect_language,
    load_document,
    split_documents,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    SUPPORTED_EXTENSIONS,
)


# ── Module 1: normalize_text ───────────────────────────────────────────────────

class TestNormalizeText:

    def test_basic_whitespace_collapsed(self):
        result = normalize_text("Hello   world\n\n  foo")
        assert result == "Hello world foo"

    def test_unicode_nfc_normalization(self):
        # Devanagari text should pass through intact
        text = "यह एक परीक्षण है"
        result = normalize_text(text)
        assert "परीक्षण" in result

    def test_gurmukhi_passthrough(self):
        text = "ਇਹ ਇੱਕ ਟੈਸਟ ਹੈ"
        result = normalize_text(text)
        assert "ਟੈਸਟ" in result

    def test_lowercase_disabled_by_default(self):
        result = normalize_text("Hello World")
        assert result == "Hello World"

    def test_lowercase_enabled(self):
        result = normalize_text("Hello World", lowercase=True)
        assert result == "hello world"

    def test_empty_string(self):
        assert normalize_text("") == ""

    def test_only_whitespace(self):
        assert normalize_text("   \n\t  ") == ""

    def test_mixed_language_text(self):
        text = "Hello  यह  ਟੈਸਟ   world"
        result = normalize_text(text)
        # All words should be present, collapsed to single spaces
        assert "Hello" in result
        assert "यह" in result
        assert "ਟੈਸਟ" in result


# ── Module 1: detect_language ─────────────────────────────────────────────────

class TestDetectLanguage:

    def test_english_detection(self):
        lang = detect_language(
            "The quick brown fox jumps over the lazy dog. "
            "This is a longer sentence to improve detection accuracy."
        )
        assert lang == "en"

    def test_hindi_detection(self):
        lang = detect_language(
            "यह एक हिंदी वाक्य है जो भाषा पहचान का परीक्षण करता है।"
        )
        assert lang == "hi"

    def test_unknown_on_empty(self):
        # Very short or empty strings should gracefully return 'unknown'
        lang = detect_language("")
        assert lang == "unknown"

    def test_short_text_does_not_crash(self):
        # Should not raise, just return 'unknown' or a best-guess
        lang = detect_language("Hi")
        assert isinstance(lang, str)


# ── Module 1: load_document ────────────────────────────────────────────────────

class TestLoadDocument:

    def test_load_txt_file(self, tmp_path):
        txt_file = tmp_path / "sample.txt"
        txt_file.write_text("Hello from a text file.", encoding="utf-8")
        docs = load_document(txt_file)
        assert len(docs) >= 1
        assert "Hello from a text file." in docs[0].page_content

    def test_load_csv_file(self, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("name,age\nAlice,30\nBob,25", encoding="utf-8")
        docs = load_document(csv_file)
        assert len(docs) >= 1

    def test_unsupported_extension_raises(self, tmp_path):
        bad_file = tmp_path / "file.xyz"
        bad_file.write_text("content")
        with pytest.raises(ValueError, match="Unsupported file type"):
            load_document(bad_file)

    def test_missing_file_raises(self, tmp_path):
        missing = tmp_path / "nonexistent.txt"
        with pytest.raises(Exception):
            load_document(missing)

    def test_utf8_encoding_preserved(self, tmp_path):
        txt_file = tmp_path / "multilang.txt"
        content = "English text और हिंदी और ਪੰਜਾਬੀ"
        txt_file.write_text(content, encoding="utf-8")
        docs = load_document(txt_file)
        assert "हिंदी" in docs[0].page_content
        assert "ਪੰਜਾਬੀ" in docs[0].page_content


# ── Module 2: split_documents ─────────────────────────────────────────────────

class TestSplitDocuments:

    def _make_doc(self, text: str) -> Document:
        return Document(page_content=text, metadata={"source": "test"})

    def test_single_short_doc_not_split(self):
        doc = self._make_doc("Short text.")
        chunks = split_documents([doc], chunk_size=500, chunk_overlap=50)
        assert len(chunks) == 1

    def test_long_doc_is_split(self):
        long_text = "This is sentence number {}. " * 100
        doc = self._make_doc(long_text)
        chunks = split_documents([doc], chunk_size=200, chunk_overlap=20)
        assert len(chunks) > 1

    def test_chunk_size_respected(self):
        long_text = "word " * 500   # 2500 chars
        doc = self._make_doc(long_text)
        chunks = split_documents([doc], chunk_size=100, chunk_overlap=10)
        for chunk in chunks:
            # Allow a small buffer for the splitter's boundary detection
            assert len(chunk.page_content) <= 120

    def test_overlap_creates_shared_content(self):
        # Generate text that will definitely split
        sentences = [f"Sentence {i} with some padding text to reach length. " for i in range(30)]
        doc = self._make_doc(" ".join(sentences))
        chunks = split_documents([doc], chunk_size=200, chunk_overlap=50)
        if len(chunks) > 1:
            # The end of chunk N should appear in the start of chunk N+1
            end_of_first   = chunks[0].page_content[-30:]
            start_of_second = chunks[1].page_content[:100]
            # At least some text should overlap
            assert any(word in start_of_second for word in end_of_first.split() if len(word) > 3)

    def test_metadata_preserved_through_split(self):
        doc = self._make_doc("text " * 200)
        doc.metadata = {"source": "test.txt", "language": "en"}
        chunks = split_documents([doc], chunk_size=100, chunk_overlap=10)
        for chunk in chunks:
            assert chunk.metadata.get("source") == "test.txt"
            assert chunk.metadata.get("language") == "en"

    def test_multilingual_document_splits(self):
        # Mix of English, Hindi, Punjabi — should not crash
        mixed = (
            "This is English content. " * 10 +
            "यह हिंदी सामग्री है। " * 10 +
            "ਇਹ ਪੰਜਾਬੀ ਸਮੱਗਰੀ ਹੈ। " * 10
        )
        doc = self._make_doc(mixed)
        chunks = split_documents([doc], chunk_size=200, chunk_overlap=20)
        assert len(chunks) >= 1

    def test_empty_document_list(self):
        chunks = split_documents([])
        assert chunks == []

    def test_default_config_values(self):
        # Verify defaults match spec (chunk_size=500, overlap=50)
        assert CHUNK_SIZE    == 500
        assert CHUNK_OVERLAP == 50


# ── Module 1: supported extensions ────────────────────────────────────────────

class TestSupportedExtensions:

    def test_all_spec_formats_supported(self):
        # Spec Module 1: txt, pdf, docx, csv
        for ext in [".txt", ".pdf", ".docx", ".csv"]:
            assert ext in SUPPORTED_EXTENSIONS, f"{ext} must be supported per spec"
