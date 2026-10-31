"""Document extraction from PDF, HTML, and Markdown sources."""

from __future__ import annotations

import io
from typing import Any

from kipu_pay.core.logging import get_logger
from kipu_pay.normalization.models import DocumentRecord, ExtractionContext

logger = get_logger(__name__)


def _detect_format(data: bytes) -> str:
    """Detect document format from raw bytes."""
    if data[:4] == b"%PDF":
        return "pdf"
    start = data[:256].lower()
    if b"<!doctype html" in start or b"<html" in start:
        return "html"
    # Markdown: check for front matter or common markdown patterns
    text_start = data[:512].decode("utf-8", errors="replace")
    if text_start.strip().startswith("---") or text_start.strip().startswith("#"):
        return "markdown"
    # Fallback: if it looks like plain text, assume markdown
    return "markdown"


class DocumentExtractor:
    """Extract canonical document records from PDF, HTML, and Markdown."""

    def extract(
        self,
        snapshot_id: str,
        resource_id: str,
        doc_id: str,
        raw_bytes: bytes,
    ) -> tuple[DocumentRecord | None, ExtractionContext | None, dict[str, Any] | None]:
        """Extract a single document.

        Returns (record, context, error).
        """
        fmt = _detect_format(raw_bytes)

        try:
            if fmt == "pdf":
                return self._extract_pdf(snapshot_id, resource_id, doc_id, raw_bytes)
            elif fmt == "html":
                return self._extract_html(snapshot_id, resource_id, doc_id, raw_bytes)
            else:
                return self._extract_markdown(snapshot_id, resource_id, doc_id, raw_bytes)
        except Exception as exc:
            error = {
                "resource_id": resource_id,
                "stage": f"extract_{fmt}",
                "error": str(exc),
            }
            return None, None, error

    def _extract_pdf(
        self,
        snapshot_id: str,
        resource_id: str,
        doc_id: str,
        raw_bytes: bytes,
    ) -> tuple[DocumentRecord | None, ExtractionContext | None, dict[str, Any] | None]:
        import fitz

        warnings: list[str] = []
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        try:
            pages_text: list[str] = []
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                text = page.get_text()
                if text:
                    pages_text.append(text)

            body = "\n\n".join(pages_text)

            # Metadata from PDF info
            metadata: dict[str, Any] = {}
            title = None
            try:
                info = doc.metadata
                if info:
                    for key in ("title", "author", "subject", "keywords", "creator", "producer"):
                        val = info.get(key)
                        if val:
                            metadata[key] = val
                            if key == "title":
                                title = val
            except Exception as exc:
                warnings.append(f"metadata_error:{exc}")

            record = DocumentRecord(
                id=doc_id,
                format="pdf",
                filename=resource_id,
                title=title or "",
                body=body,
                metadata=metadata,
            )

            context = ExtractionContext(
                snapshot_id=snapshot_id,
                source_resource_id=resource_id,
                source_format="pdf",
                source_filename=resource_id,
                parser_warnings=warnings,
            )

            return record, context, None
        finally:
            doc.close()

    def _extract_html(
        self,
        snapshot_id: str,
        resource_id: str,
        doc_id: str,
        raw_bytes: bytes,
    ) -> tuple[DocumentRecord | None, ExtractionContext | None, dict[str, Any] | None]:
        from bs4 import BeautifulSoup, Comment

        warnings: list[str] = []
        text = raw_bytes.decode("utf-8", errors="replace")
        soup = BeautifulSoup(text, "lxml")

        # Extract title
        title = None
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title = title_tag.string.strip()

        # Extract meta tags
        metadata: dict[str, Any] = {}
        for meta in soup.find_all("meta"):
            name = meta.get("name") or meta.get("property")
            content = meta.get("content")
            if name and content:
                metadata[name] = content

        # Extract comments
        comments: list[str] = []
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment_text = str(comment).strip()
            if comment_text:
                comments.append(comment_text)
        if comments:
            metadata["_html_comments"] = comments

        # Extract body text in reading order
        # Remove script and style elements
        for tag in soup(["script", "style"]):
            tag.decompose()

        body_parts: list[str] = []
        for elem in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "div"]):
            txt = elem.get_text(strip=True)
            if txt:
                if elem.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                    body_parts.append(f"{'#' * int(elem.name[1])} {txt}")
                elif elem.name == "li":
                    body_parts.append(f"- {txt}")
                else:
                    body_parts.append(txt)

        # Also get general text as fallback
        if not body_parts:
            body = soup.get_text(separator="\n", strip=True)
        else:
            body = "\n\n".join(body_parts)

        record = DocumentRecord(
            id=doc_id,
            format="html",
            filename=resource_id,
            title=title or "",
            body=body,
            metadata=metadata,
        )

        context = ExtractionContext(
            snapshot_id=snapshot_id,
            source_resource_id=resource_id,
            source_format="html",
            source_filename=resource_id,
            parser_warnings=warnings,
        )

        return record, context, None

    def _extract_markdown(
        self,
        snapshot_id: str,
        resource_id: str,
        doc_id: str,
        raw_bytes: bytes,
    ) -> tuple[DocumentRecord | None, ExtractionContext | None, dict[str, Any] | None]:
        import yaml

        warnings: list[str] = []
        text = raw_bytes.decode("utf-8", errors="replace")

        metadata: dict[str, Any] = {}
        body = text
        title = None

        # Detect YAML front matter
        if text.strip().startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                front_matter_text = parts[1].strip()
                body = parts[2].strip()
                try:
                    front = yaml.safe_load(front_matter_text)
                    if isinstance(front, dict):
                        metadata = front
                        title = front.get("title")
                except yaml.YAMLError as exc:
                    warnings.append(f"front_matter_parse_error:{exc}")
                    # Keep original text as body
                    body = text

        record = DocumentRecord(
            id=doc_id,
            format="markdown",
            filename=resource_id,
            title=title or "",
            body=body,
            metadata=metadata,
        )

        context = ExtractionContext(
            snapshot_id=snapshot_id,
            source_resource_id=resource_id,
            source_format="markdown",
            source_filename=resource_id,
            parser_warnings=warnings,
        )

        return record, context, None
