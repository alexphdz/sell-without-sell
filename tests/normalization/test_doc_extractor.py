"""Tests for document extraction."""

from __future__ import annotations

import pytest

from kipu_pay.normalization.doc_extractor import DocumentExtractor, _detect_format


class TestDetectFormat:
    def test_pdf(self) -> None:
        assert _detect_format(b"%PDF-1.4") == "pdf"

    def test_html(self) -> None:
        assert _detect_format(b"<!DOCTYPE html><html>") == "html"
        assert _detect_format(b"<HTML>") == "html"

    def test_markdown_front_matter(self) -> None:
        assert _detect_format(b"---\ntitle: x\n---\n# Hello") == "markdown"

    def test_markdown_heading(self) -> None:
        assert _detect_format(b"# Title\nBody") == "markdown"

    def test_markdown_fallback(self) -> None:
        assert _detect_format(b"plain text here") == "markdown"


class TestPdfExtraction:
    @pytest.fixture
    def extractor(self) -> DocumentExtractor:
        return DocumentExtractor()

    def test_standard_pdf(self, extractor: DocumentExtractor) -> None:
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello PDF World")
        pdf_bytes = doc.tobytes()
        doc.close()

        record, context, error = extractor.extract("snap", "doc_01", "doc_01", pdf_bytes)
        assert error is None
        assert record is not None
        assert record.format == "pdf"
        assert "Hello PDF World" in record.body
        assert context is not None

    def test_multipage_pdf(self, extractor: DocumentExtractor) -> None:
        import fitz

        doc = fitz.open()
        for i in range(3):
            page = doc.new_page()
            page.insert_text((72, 72), f"Page {i + 1}")
        pdf_bytes = doc.tobytes()
        doc.close()

        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", pdf_bytes)
        assert record is not None
        assert "Page 1" in record.body
        assert "Page 3" in record.body

    def test_pdf_metadata(self, extractor: DocumentExtractor) -> None:
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Body")
        doc.set_metadata({"title": "Test Doc", "author": "Alice"})
        pdf_bytes = doc.tobytes()
        doc.close()

        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", pdf_bytes)
        assert record is not None
        assert record.title == "Test Doc"
        assert record.metadata.get("author") == "Alice"

    def test_empty_pdf(self, extractor: DocumentExtractor) -> None:
        import fitz

        doc = fitz.open()
        doc.new_page()
        pdf_bytes = doc.tobytes()
        doc.close()

        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", pdf_bytes)
        assert record is not None
        assert record.body == ""

    def test_corrupted_pdf(self, extractor: DocumentExtractor) -> None:
        record, _, error = extractor.extract("snap", "doc_01", "doc_01", b"%PDF bad data")
        assert record is None or error is not None


class TestHtmlExtraction:
    @pytest.fixture
    def extractor(self) -> DocumentExtractor:
        return DocumentExtractor()

    def test_standard_html(self, extractor: DocumentExtractor) -> None:
        html = b"""<!DOCTYPE html>
<html><head><title>Test</title></head>
<body><h1>Heading</h1><p>Paragraph text</p></body></html>
"""
        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", html)
        assert record is not None
        assert record.format == "html"
        assert record.title == "Test"
        assert "Heading" in record.body
        assert "Paragraph text" in record.body

    def test_meta_tags(self, extractor: DocumentExtractor) -> None:
        html = b"""<!DOCTYPE html>
<html><head>
<meta name="author" content="Alice">
<meta name="description" content="Desc">
</head><body><p>Text</p></body></html>
"""
        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", html)
        assert record is not None
        assert record.metadata.get("author") == "Alice"
        assert record.metadata.get("description") == "Desc"

    def test_html_comments(self, extractor: DocumentExtractor) -> None:
        html = b"""<!DOCTYPE html>
<html><body><!-- Author: Alice --><p>Text</p></body></html>
"""
        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", html)
        assert record is not None
        comments = record.metadata.get("_html_comments", [])
        assert any("Alice" in c for c in comments)

    def test_html_entities(self, extractor: DocumentExtractor) -> None:
        html = b"""<!DOCTYPE html>
<html><body><p>&amp; &lt; &gt;</p></body></html>
"""
        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", html)
        assert record is not None
        assert "&" in record.body
        assert "<" in record.body
        assert ">" in record.body

    def test_html_table(self, extractor: DocumentExtractor) -> None:
        html = b"""<!DOCTYPE html>
<html><body><table><tr><td>A</td><td>B</td></tr></table></body></html>
"""
        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", html)
        assert record is not None
        assert "A" in record.body
        assert "B" in record.body

    def test_html_script_removed(self, extractor: DocumentExtractor) -> None:
        html = b"""<!DOCTYPE html>
<html><body><script>alert(1)</script><p>Text</p></body></html>
"""
        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", html)
        assert record is not None
        assert "alert" not in record.body

    def test_malformed_html(self, extractor: DocumentExtractor) -> None:
        html = b"<html><body><p>Unclosed<div>Text</div></body></html>"
        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", html)
        assert record is not None
        assert "Text" in record.body

    def test_html_list(self, extractor: DocumentExtractor) -> None:
        html = b"""<!DOCTYPE html>
<html><body><ul><li>Item 1</li><li>Item 2</li></ul></body></html>
"""
        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", html)
        assert record is not None
        assert "Item 1" in record.body
        assert "Item 2" in record.body


class TestMarkdownExtraction:
    @pytest.fixture
    def extractor(self) -> DocumentExtractor:
        return DocumentExtractor()

    def test_standard_markdown(self, extractor: DocumentExtractor) -> None:
        md = b"# Title\n\nBody paragraph."
        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", md)
        assert record is not None
        assert record.format == "markdown"
        assert "# Title" in record.body
        assert "Body paragraph." in record.body

    def test_yaml_front_matter(self, extractor: DocumentExtractor) -> None:
        md = b"""---
title: Test Doc
author: alice@example.com
date: 2026-01-01
---

# Introduction

Body text.
"""
        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", md)
        assert record is not None
        assert record.title == "Test Doc"
        assert record.metadata.get("author") == "alice@example.com"
        assert "# Introduction" in record.body
        assert "---" not in record.body  # front matter removed from body

    def test_missing_front_matter(self, extractor: DocumentExtractor) -> None:
        md = b"# Title\n\nBody"
        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", md)
        assert record is not None
        assert record.title == ""
        assert record.body == "# Title\n\nBody"

    def test_invalid_yaml_front_matter(self, extractor: DocumentExtractor) -> None:
        md = b"""---
key: [unclosed
---

Body
"""
        record, context, _ = extractor.extract("snap", "doc_01", "doc_01", md)
        assert record is not None
        assert any("front_matter_parse_error" in w for w in context.parser_warnings)

    def test_unicode_markdown(self, extractor: DocumentExtractor) -> None:
        md = "# Señor\n\nAdrián".encode("utf-8")
        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", md)
        assert record is not None
        assert "Señor" in record.body
        assert "Adrián" in record.body

    def test_code_blocks(self, extractor: DocumentExtractor) -> None:
        md = b"```python\nprint(1)\n```\n"
        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", md)
        assert record is not None
        assert "print(1)" in record.body

    def test_front_matter_author_email_preserved(self, extractor: DocumentExtractor) -> None:
        md = b"""---
author: john.doe@example.com
---

Text
"""
        record, _, _ = extractor.extract("snap", "doc_01", "doc_01", md)
        assert record is not None
        assert record.metadata.get("author") == "john.doe@example.com"
