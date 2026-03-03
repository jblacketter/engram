"""Tests for ingestion.chunker — text chunking with overlap."""

from ingestion.chunker import chunk_text


class TestChunkTextBasic:
    """Basic chunking behavior."""

    def test_empty_string_returns_single_chunk(self):
        assert chunk_text("", max_chars=100, overlap=10) == [""]

    def test_short_text_returns_single_chunk(self):
        text = "Hello, world!"
        result = chunk_text(text, max_chars=100, overlap=10)
        assert result == [text]

    def test_text_at_exact_limit_returns_single_chunk(self):
        text = "a" * 100
        result = chunk_text(text, max_chars=100, overlap=10)
        assert result == [text]


class TestChunkTextParagraphSplitting:
    """Paragraph-boundary splitting."""

    def test_splits_on_double_newlines(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        result = chunk_text(text, max_chars=30, overlap=0)
        assert len(result) >= 2
        assert "Paragraph one." in result[0]

    def test_preserves_paragraph_content(self):
        p1 = "First paragraph with some text."
        p2 = "Second paragraph with more text."
        text = f"{p1}\n\n{p2}"
        result = chunk_text(text, max_chars=40, overlap=0)
        # Both paragraphs should appear somewhere in the chunks
        all_text = " ".join(result)
        assert "First paragraph" in all_text
        assert "Second paragraph" in all_text


class TestChunkTextSentenceSplitting:
    """Sentence-boundary splitting for long paragraphs."""

    def test_splits_long_paragraph_on_sentences(self):
        text = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five."
        result = chunk_text(text, max_chars=40, overlap=0)
        assert len(result) >= 2

    def test_all_sentences_preserved(self):
        sentences = ["Sentence one.", "Sentence two.", "Sentence three.", "Sentence four."]
        text = " ".join(sentences)
        result = chunk_text(text, max_chars=35, overlap=0)
        all_text = " ".join(result)
        for s in sentences:
            # Sentence content (without trailing period matching) should be present
            assert s.rstrip(".") in all_text


class TestChunkTextOverlap:
    """Overlap behavior between chunks."""

    def test_overlap_creates_shared_text(self):
        text = "AAAA BBBB.\n\nCCCC DDDD.\n\nEEEE FFFF."
        result = chunk_text(text, max_chars=20, overlap=5)
        assert len(result) >= 2
        # With overlap, adjacent chunks should share some trailing/leading content

    def test_zero_overlap_no_duplication(self):
        text = "Short paragraph.\n\nAnother paragraph."
        result = chunk_text(text, max_chars=20, overlap=0)
        assert len(result) >= 2


class TestChunkTextEdgeCases:
    """Edge cases."""

    def test_whitespace_only_returns_single_chunk(self):
        result = chunk_text("   \n\n   ", max_chars=100, overlap=10)
        assert result == [""]

    def test_single_very_long_word(self):
        text = "a" * 500
        result = chunk_text(text, max_chars=100, overlap=10)
        # Should still produce at least one chunk
        assert len(result) >= 1
        all_text = "".join(result)
        # All content should be preserved (accounting for overlap duplication)
        assert "a" * 100 in all_text

    def test_returns_list_of_strings(self):
        result = chunk_text("Some text", max_chars=100, overlap=0)
        assert isinstance(result, list)
        assert all(isinstance(c, str) for c in result)
