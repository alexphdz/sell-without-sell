"""Chat extraction from Slack-style JSON messages."""

from __future__ import annotations

import json
from typing import Any

from kipu_pay.core.logging import get_logger
from kipu_pay.normalization.models import ChatRecord, ExtractionContext

logger = get_logger(__name__)


class ChatExtractor:
    """Extract canonical chat records from Slack-style channel-date JSON."""

    def __init__(self, user_catalog: list[dict[str, Any]]) -> None:
        self._uid_to_profile: dict[str, dict[str, Any]] = {}
        for user in user_catalog:
            uid = user.get("id")
            if uid:
                self._uid_to_profile[uid] = user

    def resolve_author(self, user_uid: str | None) -> tuple[str, str | None]:
        """Return (display_name, anomaly_note) for a user UID."""
        if not user_uid:
            return ("unknown", "missing_user_field")

        profile = self._uid_to_profile.get(user_uid)
        if not profile:
            return (f"unknown:{user_uid}", f"unresolved_uid:{user_uid}")

        if profile.get("is_bot"):
            real_name = profile.get("real_name", profile.get("name", user_uid))
            return (real_name, None)

        # Prefer real_name, then display_name from profile, then name
        display = profile.get("real_name")
        if not display:
            prof = profile.get("profile", {})
            display = prof.get("real_name") or prof.get("display_name")
        if not display:
            display = profile.get("name", user_uid)
        return (display, None)

    def extract_messages(
        self,
        snapshot_id: str,
        resource_id: str,
        channel_name: str,
        raw_bytes: bytes,
    ) -> tuple[list[ChatRecord], list[ExtractionContext], list[dict[str, Any]]]:
        """Extract canonical chat records from a channel-date JSON resource.

        Returns (records, contexts, errors).
        """
        records: list[ChatRecord] = []
        contexts: list[ExtractionContext] = []
        errors: list[dict[str, Any]] = []

        try:
            data = json.loads(raw_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            errors.append({
                "resource_id": resource_id,
                "stage": "parse",
                "error": str(exc),
            })
            return records, contexts, errors

        if not isinstance(data, list):
            errors.append({
                "resource_id": resource_id,
                "stage": "parse",
                "error": "expected_list_of_messages",
            })
            return records, contexts, errors

        for position, msg in enumerate(data):
            if not isinstance(msg, dict):
                continue

            try:
                record, ctx = self._extract_message(
                    snapshot_id, resource_id, channel_name, position, msg
                )
                if record:
                    records.append(record)
                    contexts.append(ctx)
            except Exception as exc:
                errors.append({
                    "resource_id": resource_id,
                    "stage": "extract_message",
                    "position": position,
                    "error": str(exc),
                })

        return records, contexts, errors

    def _extract_message(
        self,
        snapshot_id: str,
        resource_id: str,
        channel_name: str,
        position: int,
        msg: dict[str, Any],
    ) -> tuple[ChatRecord | None, ExtractionContext]:
        """Extract a single message."""
        msg_type = msg.get("type", "message")
        if msg_type != "message":
            # Skip non-message types (e.g. channel_join) unless they have text
            if not msg.get("text"):
                return None, ExtractionContext(snapshot_id=snapshot_id, source_resource_id=resource_id, source_format="chat_json")

        client_msg_id = msg.get("client_msg_id")
        if not client_msg_id:
            # Skip messages without IDs silently (they're not in record_index)
            return None, ExtractionContext(snapshot_id=snapshot_id, source_resource_id=resource_id, source_format="chat_json")

        user_uid = msg.get("user")
        author, anomaly = self.resolve_author(user_uid)

        ts = str(msg.get("ts", ""))
        thread_ts = msg.get("thread_ts")
        if thread_ts:
            thread_id = f"{channel_name}:{thread_ts}"
        else:
            thread_id = f"{channel_name}:{ts}"

        text = msg.get("text", "")
        if text is None:
            text = ""

        attachments_raw = msg.get("attachments", [])
        attachments: list[dict[str, Any]] = []
        if isinstance(attachments_raw, list):
            for att in attachments_raw:
                if isinstance(att, dict):
                    attachments.append({
                        "filename": att.get("filename", att.get("title", "")),
                        "filetype": att.get("filetype", ""),
                    })

        record = ChatRecord(
            id=str(client_msg_id),
            thread_id=thread_id,
            author=author,
            ts=ts,
            text=text,
            attachments=attachments,
        )

        warnings: list[str] = []
        if anomaly:
            warnings.append(anomaly)

        context = ExtractionContext(
            snapshot_id=snapshot_id,
            source_resource_id=resource_id,
            source_format="chat_json",
            source_record_position=position,
            original_user_uid=user_uid,
            channel_name=channel_name,
            parser_warnings=warnings,
            source_metadata={
                "team": msg.get("team"),
                "reactions": msg.get("reactions"),
                "parent_user_id": msg.get("parent_user_id"),
            },
        )

        return record, context
