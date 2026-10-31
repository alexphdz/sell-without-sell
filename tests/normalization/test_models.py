"""Tests for canonical normalization models."""

from __future__ import annotations

import json

import pytest

from kipu_pay.normalization.models import (
    ChatRecord,
    DocumentRecord,
    ExtractionContext,
    NormalizationManifest,
    NormalizedDataset,
    TableRecord,
)


class TestChatRecord:
    def test_valid_chat_record(self) -> None:
        r = ChatRecord(
            id="msg-1",
            thread_id="chan:123.456",
            author="Alice",
            ts="123.456",
            text="Hello",
            attachments=[{"filename": "file.pdf"}],
        )
        assert r.id == "msg-1"
        assert r.author == "Alice"
        assert r.attachments[0]["filename"] == "file.pdf"

    def test_missing_required_id_fails(self) -> None:
        with pytest.raises(Exception):
            ChatRecord(thread_id="x", author="A", ts="1", text="t")

    def test_extra_fields_ignored(self) -> None:
        r = ChatRecord(
            id="msg-1",
            thread_id="chan:123.456",
            author="Alice",
            ts="123.456",
            text="Hello",
            unknown_field="should_be_ignored",
        )
        assert "unknown_field" not in r.model_dump()


class TestDocumentRecord:
    def test_valid_document(self) -> None:
        r = DocumentRecord(
            id="doc_01",
            format="pdf",
            filename="test.pdf",
            title="Title",
            body="Body text",
            metadata={"author": "Someone"},
        )
        assert r.format == "pdf"
        assert r.metadata["author"] == "Someone"

    def test_metadata_must_be_dict(self) -> None:
        with pytest.raises(Exception):
            DocumentRecord(id="d", format="pdf", filename="f", body="b", metadata="bad")


class TestTableRecord:
    def test_valid_table(self) -> None:
        r = TableRecord(
            id="clientes:CL-1",
            table="clientes",
            columns={"nombre": "Alice", "edad": "30"},
        )
        assert r.table == "clientes"
        assert r.columns["nombre"] == "Alice"

    def test_columns_must_be_dict(self) -> None:
        with pytest.raises(Exception):
            TableRecord(id="t", table="tbl", columns="bad")


class TestExtractionContext:
    def test_context_extra_fields_allowed(self) -> None:
        ctx = ExtractionContext(
            snapshot_id="s1",
            source_resource_id="r1",
            source_format="csv",
            custom_key="custom_value",
        )
        assert ctx.custom_key == "custom_value"


class TestSerialization:
    def test_chat_jsonl(self) -> None:
        r = ChatRecord(id="m1", thread_id="c:1", author="A", ts="1", text="hi")
        line = json.dumps(r.model_dump(mode="json"), ensure_ascii=False)
        parsed = json.loads(line)
        assert parsed["id"] == "m1"
        assert parsed["text"] == "hi"

    def test_utf8_preservation(self) -> None:
        r = ChatRecord(id="m1", thread_id="c:1", author="Adrián", ts="1", text="Señor")
        dumped = r.model_dump(mode="json")
        assert dumped["author"] == "Adrián"
        assert dumped["text"] == "Señor"


class TestNormalizationManifest:
    def test_manifest_defaults(self) -> None:
        m = NormalizationManifest(snapshot_id="s1", status="complete")
        assert m.chats_count == 0
        assert m.extraction_errors == []


class TestNormalizedDataset:
    def test_dataset_structure(self) -> None:
        ds = NormalizedDataset(
            snapshot_id="s1",
            manifest=NormalizationManifest(snapshot_id="s1", status="complete"),
            chats=[ChatRecord(id="m1", thread_id="c:1", author="A", ts="1", text="hi")],
        )
        assert len(ds.chats) == 1
        assert len(ds.docs) == 0
