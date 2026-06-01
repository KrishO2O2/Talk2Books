"""
backend/tests/test_rag_chain.py
Talk2Books — Phase 3 Day 7
Unit tests for every function in rag_chain.py.

Key technique: mocking — we replace real services (Qdrant, Ollama)
with fake objects that return predictable responses. This means:
  - Tests run without Qdrant or Ollama running
  - Tests are fast (no network calls)
  - Tests are reliable (no flaky network conditions)
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Make sure Python can find backend/rag_chain.py
sys.path.insert(0, str(Path(__file__).parent.parent))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 1 — detect_query_language()
# These tests need NO mocking — langdetect works standalone
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestDetectQueryLanguage:

    def setup_method(self):
        # Import here so module-level singletons (embedder, qdrant, llm)
        # are not loaded until we actually need them — keeps test startup fast
        from rag_chain import detect_query_language
        self.detect = detect_query_language

    def test_english_detected(self):
        lang = self.detect(
            "What are the deliverables for this project task?"
        )
        assert lang == "en"

    def test_hindi_detected(self):
        lang = self.detect(
            "इस कार्य के लिए डिलिवरेबल्स क्या हैं? यह एक परीक्षण वाक्य है।"
        )
        assert lang == "hi"

    def test_empty_string_returns_unknown(self):
        # langdetect raises on empty string — we must return 'unknown', not crash
        lang = self.detect("")
        assert lang == "unknown"

    def test_very_short_string_does_not_crash(self):
        # Single characters are ambiguous — must not raise an exception
        lang = self.detect("a")
        assert isinstance(lang, str)

    def test_returns_string_always(self):
        # Whatever happens, the return type must always be str
        for text in ["Hello", "", "123", "!@#$"]:
            result = self.detect(text)
            assert isinstance(result, str)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 2 — build_prompt()
# No mocking needed — pure string formatting function
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestBuildPrompt:

    def setup_method(self):
        from rag_chain import build_prompt
        self.build = build_prompt

    def _make_chunks(self, texts):
        """Helper — create fake chunk dicts for testing."""
        return [
            {
                "text":      t,
                "score":     0.5,
                "source":    "data/test.docx",
                "language":  "en",
                "file_name": "test.docx",
            }
            for t in texts
        ]

    def test_question_appears_in_prompt(self):
        question = "What are the deliverables?"
        chunks   = self._make_chunks(["Some relevant context."])
        prompt   = self.build(question, chunks)
        assert question in prompt

    def test_answer_label_present(self):
        prompt = self.build("Test?", self._make_chunks(["Context."]))
        assert "Answer:" in prompt

    def test_chunk_text_appears_in_prompt(self):
        chunks = self._make_chunks(["Bridge design specifications."])
        prompt = self.build("What is this about?", chunks)
        assert "Bridge design specifications." in prompt

    def test_source_filename_in_prompt(self):
        chunks = self._make_chunks(["Some text."])
        prompt = self.build("Question?", chunks)
        assert "test.docx" in prompt

    def test_multiple_chunks_all_appear(self):
        chunks = self._make_chunks([
            "First passage content.",
            "Second passage content.",
            "Third passage content.",
        ])
        prompt = self.build("Question?", chunks)
        assert "First passage content."  in prompt
        assert "Second passage content." in prompt
        assert "Third passage content."  in prompt

    def test_passages_numbered(self):
        chunks = self._make_chunks(["Text A.", "Text B."])
        prompt = self.build("Question?", chunks)
        assert "Passage 1" in prompt
        assert "Passage 2" in prompt

    def test_separator_between_passages(self):
        chunks = self._make_chunks(["First.", "Second."])
        prompt = self.build("Question?", chunks)
        assert "---" in prompt

    def test_empty_chunks_handled_gracefully(self):
        # When no chunks are retrieved, prompt should still be valid
        prompt = self.build("Question?", [])
        assert "Question?" in prompt
        assert "Answer:" in prompt
        assert "No relevant passages" in prompt

    def test_returns_string(self):
        prompt = self.build("Q?", self._make_chunks(["Text."]))
        assert isinstance(prompt, str)

    def test_prompt_is_not_empty(self):
        prompt = self.build("Q?", self._make_chunks(["Text."]))
        assert len(prompt) > 100


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 3 — embed_query()
# Mocked — we don't want to load the real 400MB model in tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestEmbedQuery:

    def test_returns_768_floats(self):
        """Mock the embedder so we don't load the real model."""
        fake_vector = [0.01] * 768

        with patch("rag_chain.embedder") as mock_embedder:
            mock_embedder.embed_query.return_value = fake_vector
            from rag_chain import embed_query
            result = embed_query("What is this document about?")

        assert len(result) == 768
        assert all(isinstance(v, float) for v in result)

    def test_embed_query_called_with_question(self):
        """Verify the question string is passed to the embedder."""
        fake_vector = [0.0] * 768
        question    = "What are the deliverables?"

        with patch("rag_chain.embedder") as mock_embedder:
            mock_embedder.embed_query.return_value = fake_vector
            from rag_chain import embed_query
            embed_query(question)

        mock_embedder.embed_query.assert_called_once_with(question)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 4 — retrieve_chunks()
# Mocked — replaces both Qdrant and the embedder
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRetrieveChunks:

    def _make_qdrant_hit(self, text, score, language="en", file_name="test.docx"):
        """Helper — create a fake Qdrant search result object."""
        hit = MagicMock()
        hit.score   = score
        hit.payload = {
            "page_content": text,
            "metadata": {
                "language":  language,
                "source":    f"data/{file_name}",
                "file_name": file_name,
            }
        }
        return hit

    def test_returns_list_of_dicts(self):
        fake_hits = [
            self._make_qdrant_hit("Passage one text.", 0.85),
            self._make_qdrant_hit("Passage two text.", 0.72),
        ]
        fake_result      = MagicMock()
        fake_result.points = fake_hits

        with patch("rag_chain.embedder") as mock_emb, \
             patch("rag_chain.qdrant")   as mock_qd:
            mock_emb.embed_query.return_value   = [0.1] * 768
            mock_qd.query_points.return_value   = fake_result

            from rag_chain import retrieve_chunks
            chunks = retrieve_chunks("Test question?")

        assert isinstance(chunks, list)
        assert len(chunks) == 2

    def test_chunk_fields_present(self):
        fake_hits = [self._make_qdrant_hit("Some text.", 0.8)]
        fake_result        = MagicMock()
        fake_result.points = fake_hits

        with patch("rag_chain.embedder") as mock_emb, \
             patch("rag_chain.qdrant")   as mock_qd:
            mock_emb.embed_query.return_value = [0.1] * 768
            mock_qd.query_points.return_value = fake_result

            from rag_chain import retrieve_chunks
            chunks = retrieve_chunks("Test?")

        chunk = chunks[0]
        assert "text"      in chunk
        assert "score"     in chunk
        assert "language"  in chunk
        assert "file_name" in chunk
        assert "source"    in chunk

    def test_scores_are_floats(self):
        fake_hits = [
            self._make_qdrant_hit("Text.", 0.91),
            self._make_qdrant_hit("Text.", 0.74),
        ]
        fake_result        = MagicMock()
        fake_result.points = fake_hits

        with patch("rag_chain.embedder") as mock_emb, \
             patch("rag_chain.qdrant")   as mock_qd:
            mock_emb.embed_query.return_value = [0.1] * 768
            mock_qd.query_points.return_value = fake_result

            from rag_chain import retrieve_chunks
            chunks = retrieve_chunks("Test?")

        for chunk in chunks:
            assert isinstance(chunk["score"], float)

    def test_empty_results_returns_empty_list(self):
        fake_result        = MagicMock()
        fake_result.points = []

        with patch("rag_chain.embedder") as mock_emb, \
             patch("rag_chain.qdrant")   as mock_qd:
            mock_emb.embed_query.return_value = [0.1] * 768
            # Both calls return empty (filtered + fallback)
            mock_qd.query_points.return_value = fake_result

            from rag_chain import retrieve_chunks
            chunks = retrieve_chunks("Test?")

        assert chunks == []

    def test_metadata_correctly_parsed(self):
        fake_hits = [self._make_qdrant_hit(
            "Content text.", 0.8, language="hi", file_name="hindi_doc.pdf"
        )]
        fake_result        = MagicMock()
        fake_result.points = fake_hits

        with patch("rag_chain.embedder") as mock_emb, \
             patch("rag_chain.qdrant")   as mock_qd:
            mock_emb.embed_query.return_value = [0.1] * 768
            mock_qd.query_points.return_value = fake_result

            from rag_chain import retrieve_chunks
            chunks = retrieve_chunks("परीक्षण?", filter_language=False)

        assert chunks[0]["language"]  == "hi"
        assert chunks[0]["file_name"] == "hindi_doc.pdf"
        assert chunks[0]["text"]      == "Content text."


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 5 — generate_answer()
# Mocked — replaces the real LLM call
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestGenerateAnswer:

    def test_returns_answer_string(self):
        mock_response         = MagicMock()
        mock_response.content = "  The deliverables include a video.  "

        with patch("rag_chain.llm") as mock_llm:
            mock_llm.invoke.return_value = mock_response
            from rag_chain import generate_answer
            answer = generate_answer("Some prompt text here.")

        # Should be stripped of surrounding whitespace
        assert answer == "The deliverables include a video."

    def test_ollama_down_returns_safe_message(self):
        """When Ollama is unreachable, should return a friendly message, not crash."""
        with patch("rag_chain.llm") as mock_llm:
            mock_llm.invoke.side_effect = Exception("Connection refused")
            from rag_chain import generate_answer
            answer = generate_answer("Some prompt.")

        assert isinstance(answer, str)
        assert len(answer) > 0
        # Must not raise — must return a safe fallback string
        assert "Sorry" in answer or "could not" in answer.lower()

    def test_llm_called_with_message(self):
        mock_response         = MagicMock()
        mock_response.content = "Answer text."

        with patch("rag_chain.llm") as mock_llm:
            mock_llm.invoke.return_value = mock_response
            from rag_chain import generate_answer
            generate_answer("My prompt.")

        # Verify invoke() was actually called once
        mock_llm.invoke.assert_called_once()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 6 — ask() full pipeline
# Mocked — tests the complete pipeline with all services faked
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAskPipeline:

    def _mock_chunk(self):
        return {
            "text":      "The deliverables include a video demonstration.",
            "score":     0.82,
            "source":    "data/Sample.docx",
            "language":  "en",
            "file_name": "Sample.docx",
        }

    def test_ask_returns_required_keys(self):
        with patch("rag_chain.retrieve_chunks") as mock_ret, \
             patch("rag_chain.generate_answer") as mock_gen:
            mock_ret.return_value = [self._mock_chunk()]
            mock_gen.return_value = "The deliverables include a video."

            from rag_chain import ask
            result = ask("What are the deliverables?")

        assert "answer"   in result
        assert "sources"  in result
        assert "language" in result
        assert "chunks"   in result

    def test_ask_answer_is_string(self):
        with patch("rag_chain.retrieve_chunks") as mock_ret, \
             patch("rag_chain.generate_answer") as mock_gen:
            mock_ret.return_value = [self._mock_chunk()]
            mock_gen.return_value = "The answer."

            from rag_chain import ask
            result = ask("Test question?")

        assert isinstance(result["answer"], str)

    def test_ask_sources_extracted_correctly(self):
        with patch("rag_chain.retrieve_chunks") as mock_ret, \
             patch("rag_chain.generate_answer") as mock_gen:
            mock_ret.return_value = [self._mock_chunk(), self._mock_chunk()]
            mock_gen.return_value = "Answer."

            from rag_chain import ask
            result = ask("Test?")

        # Both chunks have same source — deduplicated to one entry
        assert result["sources"] == ["Sample.docx"]

    def test_ask_empty_chunks_does_not_crash(self):
        """Pipeline must work even when Qdrant returns nothing."""
        with patch("rag_chain.retrieve_chunks") as mock_ret, \
             patch("rag_chain.generate_answer") as mock_gen:
            mock_ret.return_value = []
            mock_gen.return_value = "I could not find an answer."

            from rag_chain import ask
            result = ask("Unknown topic question?")

        assert isinstance(result["answer"], str)
        assert result["sources"] == []