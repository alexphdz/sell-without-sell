"""Main PII detection orchestrator combining all detectors."""

from __future__ import annotations

import uuid
from typing import Any, Sequence

from kipu_pay.anonymization.llm_adapter import LLMDetector, LLMSettings
from kipu_pay.anonymization.models import (
    Action,
    DetectionCategory,
    DetectionResult,
    DetectionSpan,
)
from kipu_pay.anonymization.patterns import (
    PatternDetector,
    RegistryDictionaryDetector,
    SchemaDetector,
)
from kipu_pay.core.logging import get_logger
from kipu_pay.identity.resolver import IdentityResolver
from kipu_pay.normalization.models import (
    ChatRecord,
    DocumentRecord,
    ExtractionContext,
    NormalizedDataset,
    TableRecord,
)

logger = get_logger(__name__)


class Detector:
    """Hybrid PII detector: rules + registry + optional LLM."""

    def __init__(
        self,
        resolver: IdentityResolver | None = None,
        llm: LLMDetector | None = None,
    ) -> None:
        self.pattern = PatternDetector()
        self.schema = SchemaDetector()
        self.registry_dict = RegistryDictionaryDetector(resolver)
        self.llm = llm or LLMDetector()
        if resolver is not None:
            self.registry_dict.load(resolver)

    def detect_chat(self, record: ChatRecord, ctx: ExtractionContext | None = None) -> DetectionResult:
        spans: list[DetectionSpan] = []
        # Author
        spans.extend(self._detect_person_text(record.author, f"{record.id}:author"))
        # Body text
        spans.extend(self._detect_free_text(record.text, f"{record.id}:text"))
        # Attachments filenames
        for i, att in enumerate(record.attachments):
            fn = att.get("filename", "")
            if fn:
                spans.extend(self._detect_free_text(fn, f"{record.id}:attachments:{i}:filename"))
        spans = self._arbitrate(spans)
        return DetectionResult(record_id=record.id, spans=spans)

    def detect_document(self, record: DocumentRecord) -> DetectionResult:
        spans: list[DetectionSpan] = []
        # Filename
        spans.extend(self._detect_free_text(record.filename, f"{record.id}:filename"))
        # Title
        if record.title:
            spans.extend(self._detect_free_text(record.title, f"{record.id}:title"))
        # Body
        spans.extend(self._detect_free_text(record.body, f"{record.id}:body"))
        # Metadata values (walk nested)
        spans.extend(self._walk_metadata(record.metadata, record.id))
        spans = self._arbitrate(spans)
        return DetectionResult(record_id=record.id, spans=spans)

    def detect_table(self, record: TableRecord) -> DetectionResult:
        spans: list[DetectionSpan] = []
        for col, val in record.columns.items():
            if not val:
                continue
            schema_span = self.schema.detect_column(col, val, record.id)
            if schema_span:
                spans.append(schema_span)
            else:
                # Free-text detection on columns not explicitly mapped
                fn = col.lower().strip()
                if fn not in SchemaDetector._KEEP_FIELDS and fn not in SchemaDetector._FIELD_MAP:
                    spans.extend(self._detect_free_text(str(val), f"{record.id}:columns:{col}"))
        spans = self._arbitrate(spans)
        return DetectionResult(record_id=record.id, spans=spans)

    def detect_dataset(self, dataset: NormalizedDataset) -> dict[str, DetectionResult]:
        results: dict[str, DetectionResult] = {}
        for c in dataset.chats:
            results[c.id] = self.detect_chat(c)
        for d in dataset.docs:
            results[d.id] = self.detect_document(d)
        for t in dataset.tables:
            results[t.id] = self.detect_table(t)
        return results

    def _detect_free_text(self, text: str, surface_path: str) -> list[DetectionSpan]:
        spans: list[DetectionSpan] = []
        spans.extend(self.pattern.detect(text, surface_path))
        spans.extend(self.registry_dict.detect(text, surface_path))
        return spans

    def _detect_person_text(self, text: str, surface_path: str) -> list[DetectionSpan]:
        spans: list[DetectionSpan] = []
        # First check registry full names
        reg_spans = self.registry_dict.detect(text, surface_path)
        if reg_spans:
            spans.extend(reg_spans)
        else:
            # Unknown person: still detect as person but unresolved
            spans.append(
                DetectionSpan(
                    start=0,
                    end=len(text),
                    surface_path=surface_path,
                    category=DetectionCategory.PERSON,
                    matched_text=text,
                    confidence="weak",
                    detector="fallback_person",
                )
            )
        return spans

    def _walk_metadata(self, meta: dict[str, Any], record_id: str, path_prefix: str = "metadata") -> list[DetectionSpan]:
        spans: list[DetectionSpan] = []
        for k, v in meta.items():
            surface = f"{record_id}:{path_prefix}:{k}"
            if isinstance(v, str):
                spans.extend(self._detect_free_text(v, surface))
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    if isinstance(item, str):
                        spans.extend(self._detect_free_text(item, f"{surface}:{i}"))
            elif isinstance(v, dict):
                spans.extend(self._walk_metadata(v, record_id, f"{path_prefix}:{k}"))
        return spans

    def _arbitrate(self, spans: Sequence[DetectionSpan]) -> list[DetectionSpan]:
        """Deduplicate, resolve overlaps, sort. Only compare spans on same surface."""
        if not spans:
            return []
        # Group by surface_path
        from collections import defaultdict
        by_surface: dict[str, list[DetectionSpan]] = defaultdict(list)
        for s in spans:
            by_surface[s.surface_path].append(s)
        result: list[DetectionSpan] = []
        for surface, surf_spans in by_surface.items():
            sorted_spans = sorted(surf_spans, key=lambda s: (s.start, -s.end))
            surf_result: list[DetectionSpan] = []
            for span in sorted_spans:
                if any(
                    existing.start <= span.start and existing.end >= span.end
                    for existing in surf_result
                ):
                    continue
                overlap = False
                for existing in surf_result:
                    if self._overlaps(existing, span):
                        existing_strength = self._strength_rank(existing)
                        span_strength = self._strength_rank(span)
                        if span_strength <= existing_strength:
                            overlap = True
                            break
                if not overlap:
                    surf_result.append(span)
            result.extend(surf_result)
        result.sort(key=lambda s: (s.surface_path, s.start))
        return result

    def _overlaps(self, a: DetectionSpan, b: DetectionSpan) -> bool:
        return not (a.end <= b.start or b.end <= a.start)

    def _strength_rank(self, span: DetectionSpan) -> int:
        ranks = {"strong": 3, "contextual": 2, "weak": 1}
        r = ranks.get(span.confidence, 0)
        # Registry-detected person names are preferred over pattern matches
        if span.detector.startswith("registry"):
            r += 1
        return r
