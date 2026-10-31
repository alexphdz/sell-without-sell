"""Dataset anonymizer: produce full output from detections."""

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from typing import Any

from kipu_pay.anonymization.models import Action, DetectionCategory, DetectionResult, DetectionSpan
from kipu_pay.anonymization.replacement import PseudonymRepository, ReplacementEngine
from kipu_pay.core.logging import get_logger
from kipu_pay.normalization.models import (
    ChatRecord,
    DocumentRecord,
    NormalizedDataset,
    TableRecord,
)

logger = get_logger(__name__)


class DatasetAnonymizer:
    """Anonymize a full normalized dataset into output records and entity dictionary."""

    def __init__(self, repo: PseudonymRepository, secret: str) -> None:
        self.repo = repo
        self.secret = secret
        self.engine = ReplacementEngine()
        self.entity_originals: dict[str, set[str]] = defaultdict(set)
        self.entity_records: dict[str, set[str]] = defaultdict(set)
        self.entity_type: dict[str, str] = {}
        self.kept: list[dict[str, Any]] = []

    async def anonymize(
        self,
        dataset: NormalizedDataset,
        detections: dict[str, DetectionResult],
    ) -> dict[str, Any]:
        logger.info("anonymization_start", records=len(detections))

        chats_out: list[dict[str, Any]] = []
        docs_out: list[dict[str, Any]] = []
        tables_out: list[dict[str, Any]] = []

        for c in dataset.chats:
            det = detections.get(c.id, DetectionResult(record_id=c.id))
            ac = await self._anonymize_chat(c, det)
            chats_out.append(ac)
            self._track_entities(c.id, det)

        for d in dataset.docs:
            det = detections.get(d.id, DetectionResult(record_id=d.id))
            ad = await self._anonymize_document(d, det)
            docs_out.append(ad)
            self._track_entities(d.id, det)

        for t in dataset.tables:
            det = detections.get(t.id, DetectionResult(record_id=t.id))
            at = await self._anonymize_table(t, det)
            tables_out.append(at)
            self._track_entities(t.id, det)

        entities_json = await self._build_entities_json()

        return {
            "chats": chats_out,
            "docs": docs_out,
            "tables": tables_out,
            "entities": entities_json,
        }

    async def _anonymize_chat(self, record: ChatRecord, det: DetectionResult) -> dict[str, Any]:
        author_spans = [s for s in det.spans if s.surface_path.endswith(":author")]
        text_spans = [s for s in det.spans if s.surface_path.endswith(":text")]
        att_spans = [s for s in det.spans if ":attachments:" in s.surface_path]

        new_author = await self.engine.apply(record.author, author_spans, self.repo)
        new_text = await self.engine.apply(record.text, text_spans, self.repo)
        new_attachments = []
        for i, att in enumerate(record.attachments):
            fn = att.get("filename", "")
            spans = [s for s in att_spans if f":attachments:{i}:" in s.surface_path]
            new_fn = await self.engine.apply(fn, spans, self.repo)
            new_attachments.append({"filename": new_fn})

        return {
            "id": record.id,
            "thread_id": record.thread_id,
            "author": new_author,
            "ts": record.ts,
            "text": new_text,
            "attachments": new_attachments,
        }

    async def _anonymize_document(self, record: DocumentRecord, det: DetectionResult) -> dict[str, Any]:
        filename_spans = [s for s in det.spans if s.surface_path.endswith(":filename")]
        title_spans = [s for s in det.spans if s.surface_path.endswith(":title")]
        body_spans = [s for s in det.spans if ":body" in s.surface_path]
        meta_spans = [s for s in det.spans if ":metadata:" in s.surface_path]

        new_filename = await self.engine.apply(record.filename, filename_spans, self.repo)
        new_title = await self.engine.apply(record.title or "", title_spans, self.repo)
        new_body = await self.engine.apply(record.body, body_spans, self.repo)
        new_metadata = await self._apply_to_metadata(record.metadata, meta_spans)

        return {
            "id": record.id,
            "format": record.format,
            "filename": new_filename,
            "title": new_title,
            "body": new_body,
            "metadata": new_metadata,
        }

    async def _apply_to_metadata(self, meta: dict[str, Any], spans: list[DetectionSpan]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for k, v in meta.items():
            key_spans = [s for s in spans if f":metadata:{k}" in s.surface_path or f":metadata:{k}:" in s.surface_path]
            if isinstance(v, str):
                result[k] = await self.engine.apply(v, key_spans, self.repo)
            elif isinstance(v, list):
                new_list = []
                for i, item in enumerate(v):
                    item_spans = [s for s in spans if f":metadata:{k}:{i}" in s.surface_path]
                    if isinstance(item, str):
                        new_list.append(await self.engine.apply(item, item_spans, self.repo))
                    else:
                        new_list.append(item)
                result[k] = new_list
            elif isinstance(v, dict):
                result[k] = await self._apply_to_metadata(v, spans)
            else:
                result[k] = v
        return result

    async def _anonymize_table(self, record: TableRecord, det: DetectionResult) -> dict[str, Any]:
        new_columns: dict[str, str | None] = {}
        for col, val in record.columns.items():
            if val is None:
                new_columns[col] = None
                continue
            col_spans = [s for s in det.spans if f":columns:{col}" in s.surface_path]
            new_columns[col] = await self.engine.apply(str(val), col_spans, self.repo)
        return {
            "id": record.id,
            "table": record.table,
            "columns": new_columns,
        }

    def _track_entities(self, record_id: str, det: DetectionResult) -> None:
        for span in det.spans:
            if span.action.value if hasattr(span.action, "value") else str(span.action) == "keep":
                self.kept.append({
                    "text": span.matched_text,
                    "category": span.category,
                    "reason": "public_entity",
                })
                continue
            eid_str = str(span.entity_id) if span.entity_id else None
            cat_str = span.category.value if hasattr(span.category, "value") else str(span.category)
            if eid_str:
                self.entity_originals[eid_str].add(span.matched_text)
                self.entity_records[eid_str].add(record_id)
                self.entity_type[eid_str] = "person"
            else:
                # Use same hashing as PseudonymRepository for unknown scopes
                scope = f"{span.matched_text}:{self.secret}"
                uh = hashlib.sha256(scope.encode()).hexdigest()
                self.entity_originals[uh].add(span.matched_text)
                self.entity_records[uh].add(record_id)
                self.entity_type[uh] = "person"

    async def _build_entities_json(self) -> dict[str, Any]:
        entities_list = []
        for eid in sorted(self.entity_originals.keys()):
            originals = sorted(self.entity_originals[eid])
            records = sorted(self.entity_records[eid])
            etype = self.entity_type.get(eid, "person")
            pseudonyms: dict[str, str] = {}

            try:
                eid_uuid = uuid.UUID(eid)
                scope_hash = None
            except ValueError:
                eid_uuid = None
                scope_hash = eid

            if etype == "person":
                name_pseudo = await self.repo.get_pseudonym_any(eid_uuid, scope_hash, DetectionCategory.PERSON)
                if name_pseudo:
                    pseudonyms["name"] = name_pseudo
                email_pseudo = await self.repo.get_pseudonym_any(eid_uuid, scope_hash, DetectionCategory.EMAIL)
                if email_pseudo:
                    pseudonyms["email"] = email_pseudo
                phone_pseudo = await self.repo.get_pseudonym_any(eid_uuid, scope_hash, DetectionCategory.PHONE)
                if phone_pseudo:
                    pseudonyms["phone"] = phone_pseudo
                cedula_pseudo = await self.repo.get_pseudonym_any(eid_uuid, scope_hash, DetectionCategory.NATIONAL_ID)
                if cedula_pseudo:
                    pseudonyms["cedula"] = cedula_pseudo
                addr_pseudo = await self.repo.get_pseudonym_any(eid_uuid, scope_hash, DetectionCategory.ADDRESS)
                if addr_pseudo:
                    pseudonyms["address"] = addr_pseudo

            entry = {
                "entity_id": eid,
                "type": etype,
                "originals": originals,
                "pseudonyms": pseudonyms,
                "records": records,
            }
            entities_list.append(entry)
        return {"entities": entities_list}
