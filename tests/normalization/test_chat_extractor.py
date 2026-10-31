"""Tests for chat extraction."""

from __future__ import annotations

import json

import pytest

from kipu_pay.normalization.chat_extractor import ChatExtractor


@pytest.fixture
def user_catalog() -> list[dict]:
    return [
        {
            "id": "U001",
            "name": "alice",
            "real_name": "Alice Smith",
            "is_bot": False,
            "profile": {"display_name": "AliceS"},
        },
        {
            "id": "U002",
            "name": "bob",
            "real_name": "Bob Jones",
            "is_bot": False,
            "profile": {},
        },
        {
            "id": "B001",
            "name": "kipi",
            "real_name": "Kipi Bot",
            "is_bot": True,
            "profile": {"display_name": "Kipi"},
        },
    ]


@pytest.fixture
def extractor(user_catalog: list[dict]) -> ChatExtractor:
    return ChatExtractor(user_catalog)


class TestAuthorResolution:
    def test_known_user(self, extractor: ChatExtractor) -> None:
        name, anomaly = extractor.resolve_author("U001")
        assert name == "Alice Smith"
        assert anomaly is None

    def test_bot_user(self, extractor: ChatExtractor) -> None:
        name, anomaly = extractor.resolve_author("B001")
        assert name == "Kipi Bot"
        assert anomaly is None

    def test_unknown_user(self, extractor: ChatExtractor) -> None:
        name, anomaly = extractor.resolve_author("U999")
        assert "unknown" in name
        assert anomaly is not None

    def test_missing_user(self, extractor: ChatExtractor) -> None:
        name, anomaly = extractor.resolve_author(None)
        assert name == "unknown"
        assert anomaly is not None

    def test_fallback_to_name(self, extractor: ChatExtractor) -> None:
        catalog = [{"id": "U003", "name": "charlie"}]
        ext = ChatExtractor(catalog)
        name, _ = ext.resolve_author("U003")
        assert name == "charlie"


class TestMessageExtraction:
    def test_standard_message(self, extractor: ChatExtractor) -> None:
        messages = [
            {
                "type": "message",
                "user": "U001",
                "text": "Hello team",
                "ts": "123.001",
                "client_msg_id": "msg-1",
            }
        ]
        raw = json.dumps(messages).encode("utf-8")
        records, contexts, errors = extractor.extract_messages(
            "snap", "res1", "general", raw
        )
        assert len(records) == 1
        assert records[0].id == "msg-1"
        assert records[0].author == "Alice Smith"
        assert records[0].text == "Hello team"
        assert records[0].thread_id == "general:123.001"
        assert len(errors) == 0

    def test_thread_reply(self, extractor: ChatExtractor) -> None:
        messages = [
            {
                "type": "message",
                "user": "U001",
                "text": "Root",
                "ts": "123.001",
                "client_msg_id": "msg-1",
            },
            {
                "type": "message",
                "user": "U002",
                "text": "Reply",
                "ts": "123.002",
                "client_msg_id": "msg-2",
                "thread_ts": "123.001",
            },
        ]
        raw = json.dumps(messages).encode("utf-8")
        records, _, _ = extractor.extract_messages("snap", "res1", "general", raw)
        assert records[0].thread_id == "general:123.001"
        assert records[1].thread_id == "general:123.001"

    def test_different_channels_same_ts(self, extractor: ChatExtractor) -> None:
        messages = [
            {
                "type": "message",
                "user": "U001",
                "text": "A",
                "ts": "123.001",
                "client_msg_id": "msg-a",
            }
        ]
        raw = json.dumps(messages).encode("utf-8")
        r1, _, _ = extractor.extract_messages("snap", "r1", "chan1", raw)
        r2, _, _ = extractor.extract_messages("snap", "r2", "chan2", raw)
        assert r1[0].thread_id == "chan1:123.001"
        assert r2[0].thread_id == "chan2:123.001"

    def test_attachment_preserved(self, extractor: ChatExtractor) -> None:
        messages = [
            {
                "type": "message",
                "user": "U001",
                "text": "See attached",
                "ts": "123.001",
                "client_msg_id": "msg-1",
                "attachments": [
                    {"filename": "report.pdf", "filetype": "pdf"}
                ],
            }
        ]
        raw = json.dumps(messages).encode("utf-8")
        records, _, _ = extractor.extract_messages("snap", "res1", "general", raw)
        assert len(records[0].attachments) == 1
        assert records[0].attachments[0]["filename"] == "report.pdf"

    def test_multiple_attachments(self, extractor: ChatExtractor) -> None:
        messages = [
            {
                "type": "message",
                "user": "U001",
                "text": "Files",
                "ts": "123.001",
                "client_msg_id": "msg-1",
                "attachments": [
                    {"filename": "a.pdf"},
                    {"filename": "b.pdf"},
                ],
            }
        ]
        raw = json.dumps(messages).encode("utf-8")
        records, _, _ = extractor.extract_messages("snap", "res1", "general", raw)
        assert len(records[0].attachments) == 2

    def test_mention_preserved(self, extractor: ChatExtractor) -> None:
        messages = [
            {
                "type": "message",
                "user": "U001",
                "text": "Hey <@U002> check this",
                "ts": "123.001",
                "client_msg_id": "msg-1",
            }
        ]
        raw = json.dumps(messages).encode("utf-8")
        records, _, _ = extractor.extract_messages("snap", "res1", "general", raw)
        assert "<@U002>" in records[0].text

    def test_missing_client_msg_id_skipped(self, extractor: ChatExtractor) -> None:
        messages = [
            {
                "type": "message",
                "user": "U001",
                "text": "No ID",
                "ts": "123.001",
            }
        ]
        raw = json.dumps(messages).encode("utf-8")
        records, _, _ = extractor.extract_messages("snap", "res1", "general", raw)
        assert len(records) == 0

    def test_edited_message_text_preserved(self, extractor: ChatExtractor) -> None:
        messages = [
            {
                "type": "message",
                "user": "U001",
                "text": "Edited text",
                "ts": "123.001",
                "client_msg_id": "msg-1",
                "edited": {"user": "U001", "ts": "123.002"},
            }
        ]
        raw = json.dumps(messages).encode("utf-8")
        records, _, _ = extractor.extract_messages("snap", "res1", "general", raw)
        assert records[0].text == "Edited text"

    def test_accented_text(self, extractor: ChatExtractor) -> None:
        messages = [
            {
                "type": "message",
                "user": "U001",
                "text": "Señor Adrián",
                "ts": "123.001",
                "client_msg_id": "msg-1",
            }
        ]
        raw = json.dumps(messages).encode("utf-8")
        records, _, _ = extractor.extract_messages("snap", "res1", "general", raw)
        assert records[0].text == "Señor Adrián"

    def test_empty_text(self, extractor: ChatExtractor) -> None:
        messages = [
            {
                "type": "message",
                "user": "U001",
                "text": "",
                "ts": "123.001",
                "client_msg_id": "msg-1",
            }
        ]
        raw = json.dumps(messages).encode("utf-8")
        records, _, _ = extractor.extract_messages("snap", "res1", "general", raw)
        assert records[0].text == ""

    def test_invalid_json(self, extractor: ChatExtractor) -> None:
        raw = b"not json"
        records, _, errors = extractor.extract_messages("snap", "res1", "general", raw)
        assert len(records) == 0
        assert len(errors) == 1

    def test_not_list(self, extractor: ChatExtractor) -> None:
        raw = json.dumps({"error": "bad"}).encode("utf-8")
        records, _, errors = extractor.extract_messages("snap", "res1", "general", raw)
        assert len(records) == 0
        assert len(errors) == 1

    def test_bot_identity_preserved(self, extractor: ChatExtractor) -> None:
        messages = [
            {
                "type": "message",
                "user": "B001",
                "text": "Reminder",
                "ts": "123.001",
                "client_msg_id": "msg-1",
            }
        ]
        raw = json.dumps(messages).encode("utf-8")
        records, _, _ = extractor.extract_messages("snap", "res1", "general", raw)
        assert records[0].author == "Kipi Bot"

    def test_context_provenance(self, extractor: ChatExtractor) -> None:
        messages = [
            {
                "type": "message",
                "user": "U001",
                "text": "Hello",
                "ts": "123.001",
                "client_msg_id": "msg-1",
            }
        ]
        raw = json.dumps(messages).encode("utf-8")
        _, contexts, _ = extractor.extract_messages("snap", "res1", "general", raw)
        assert contexts[0].snapshot_id == "snap"
        assert contexts[0].source_resource_id == "res1"
        assert contexts[0].channel_name == "general"
        assert contexts[0].original_user_uid == "U001"
