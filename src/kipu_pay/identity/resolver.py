"""Identity resolution: match mentions against the persistent registry.

Tiered strategy:
  Tier 1 — strong identifiers (source IDs, cédula, email, phone, Slack UID)
  Tier 2 — contextual evidence (unique exact full-name alias)
  Tier 3 — weak evidence (partial names) never establishes identity

Lookup tables are preloaded in one pass to avoid per-token queries.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kipu_pay.core.logging import get_logger
from kipu_pay.identity.db_models import IdentityAlias, IdentityEntity, IdentityIdentifier
from kipu_pay.identity.models import (
    ConfidenceLevel,
    ResolutionContext,
    ResolutionResult,
    ResolutionStatus,
)
from kipu_pay.identity.normalizers import (
    normalize_cedula,
    normalize_email,
    normalize_name,
    normalize_phone,
)

logger = get_logger(__name__)

# Source IDs are prefix-coded (CL-/PG- clients, KP- employees, future
# prefixes after dataset growth). Match the generic shape and consult the
# registry rather than hardcoding prefixes.
_SOURCE_ID_RE = re.compile(r"^[A-Z]{2,4}-\d+$")
_SLACK_UID_RE = re.compile(r"^U[A-Z0-9]{6,12}$")
_DIGITSEP_RE = re.compile(r"^[\d.\s\-]+$")


class IdentityResolver:
    """Resolve mentions against preloaded registry lookup tables."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._identifiers: dict[tuple[str, str], uuid.UUID] = {}
        self._aliases: dict[str, set[uuid.UUID]] = defaultdict(set)
        self._entity_source: dict[uuid.UUID, tuple[str, str]] = {}
        self._loaded = False

    async def load(self) -> None:
        """Preload identifier and alias lookup maps (batched, not per-token)."""
        rows = await self.session.execute(
            select(
                IdentityIdentifier.identifier_type,
                IdentityIdentifier.normalized_value,
                IdentityIdentifier.entity_id,
            )
        )
        self._identifiers = {
            (itype, value): entity_id for itype, value, entity_id in rows
        }

        alias_rows = await self.session.execute(
            select(IdentityAlias.normalized_alias, IdentityAlias.entity_id)
        )
        self._aliases = defaultdict(set)
        for normalized_alias, entity_id in alias_rows:
            self._aliases[normalized_alias].add(entity_id)

        entity_rows = await self.session.execute(
            select(IdentityEntity.id, IdentityEntity.source_type, IdentityEntity.source_id)
        )
        self._entity_source = {
            eid: (stype, sid) for eid, stype, sid in entity_rows
        }

        self._loaded = True
        logger.info(
            "resolver_loaded",
            identifiers=len(self._identifiers),
            aliases=len(self._aliases),
            entities=len(self._entity_source),
        )

    # ------------------------------------------------------------------ public

    async def resolve(self, mention: str, context: ResolutionContext | None = None) -> ResolutionResult:
        """Resolve a single mention. Deterministic; registry is never mutated."""
        if not self._loaded:
            await self.load()
        context = context or ResolutionContext()
        mention = (mention or "").strip()
        if not mention:
            return ResolutionResult(status=ResolutionStatus.UNKNOWN, detail="empty_mention")

        result = self._resolve_strong(mention)
        if result is None:
            result = self._resolve_name(mention)

        # Contextual contradiction check: an authoritative expectation
        # (e.g. FK cliente_id) that disagrees with the resolved entity.
        if (
            result.status == ResolutionStatus.MATCHED
            and context.expected_source_id
            and result.entity_id is not None
        ):
            source = self._entity_source.get(result.entity_id)
            if source is not None and source[1] != context.expected_source_id:
                return ResolutionResult(
                    status=ResolutionStatus.CONFLICT,
                    entity_id=None,
                    evidence=result.evidence + ["context_expected_source_id_mismatch"],
                    confidence_level=ConfidenceLevel.NONE,
                    candidate_entity_ids=[result.entity_id],
                    detail="resolved_entity_contradicts_context",
                )

        return result

    # ------------------------------------------------------------ tier 1

    def _resolve_strong(self, mention: str) -> ResolutionResult | None:
        """Try strong identifier interpretations; conflict if they disagree."""
        hits: list[tuple[str, uuid.UUID]] = []

        if _SOURCE_ID_RE.match(mention):
            client_eid = self._identifiers.get(("client_id", mention))
            employee_eid = self._identifiers.get(("employee_id", mention))
            if client_eid:
                hits.append(("client_id", client_eid))
            if employee_eid:
                hits.append(("employee_id", employee_eid))
            if not client_eid and not employee_eid:
                # ID-shaped tokens are never treated as names.
                return ResolutionResult(
                    status=ResolutionStatus.UNKNOWN,
                    detail="unknown_source_id",
                    evidence=["source_id_pattern"],
                )

        if "@" in mention:
            email = normalize_email(mention)
            if email:
                eid = self._identifiers.get(("email", email))
                if eid:
                    hits.append(("email", eid))
                else:
                    return ResolutionResult(
                        status=ResolutionStatus.UNKNOWN,
                        detail="unknown_email",
                        evidence=["email_pattern"],
                    )

        if _SLACK_UID_RE.match(mention):
            eid = self._identifiers.get(("slack_uid", mention))
            if eid:
                hits.append(("slack_uid", eid))
            else:
                return ResolutionResult(
                    status=ResolutionStatus.UNKNOWN,
                    detail="unknown_slack_uid",
                    evidence=["slack_uid_pattern"],
                )

        if _DIGITSEP_RE.match(mention):
            digits_hits = self._resolve_numeric(mention)
            if digits_hits is not None:
                hits.extend(digits_hits)

        if not hits:
            return None

        entity_ids = {eid for _, eid in hits}
        if len(entity_ids) > 1:
            return ResolutionResult(
                status=ResolutionStatus.CONFLICT,
                evidence=[t for t, _ in hits],
                candidate_entity_ids=sorted(entity_ids),
                confidence_level=ConfidenceLevel.NONE,
                detail="strong_identifiers_disagree",
            )

        entity_id = next(iter(entity_ids))
        return ResolutionResult(
            status=ResolutionStatus.MATCHED,
            entity_id=entity_id,
            evidence=[t for t, _ in hits],
            confidence_level=ConfidenceLevel.STRONG,
        )

    def _resolve_numeric(self, mention: str) -> list[tuple[str, uuid.UUID]] | None:
        """Interpret a numeric-looking mention as phone and/or cédula."""
        hits: list[tuple[str, uuid.UUID]] = []

        phone = normalize_phone(mention)
        if phone:
            eid = self._identifiers.get(("phone", phone))
            if eid:
                hits.append(("phone", eid))

        cedula = normalize_cedula(mention)
        if cedula:
            eid = self._identifiers.get(("cedula", cedula))
            if eid:
                hits.append(("cedula", eid))

        return hits or None

    # ------------------------------------------------------------ tier 2/3

    def _resolve_name(self, mention: str) -> ResolutionResult:
        normalized = normalize_name(mention)
        if not normalized:
            return ResolutionResult(status=ResolutionStatus.UNKNOWN, detail="unparseable_mention")

        candidates = self._aliases.get(normalized, set())

        # Tier 3: partial names (single token / initials) never force a match.
        token_count = len(normalized.split())
        if token_count < 2:
            return ResolutionResult(
                status=ResolutionStatus.UNKNOWN,
                evidence=["partial_name"],
                confidence_level=ConfidenceLevel.WEAK,
                candidate_entity_ids=sorted(candidates),
                detail="weak_evidence_insufficient",
            )

        if not candidates:
            return ResolutionResult(
                status=ResolutionStatus.UNKNOWN,
                evidence=["full_name_no_candidate"],
                detail="no_alias_match",
            )

        if len(candidates) == 1:
            return ResolutionResult(
                status=ResolutionStatus.MATCHED,
                entity_id=next(iter(candidates)),
                evidence=["unique_exact_full_name"],
                confidence_level=ConfidenceLevel.CONTEXTUAL,
            )

        return ResolutionResult(
            status=ResolutionStatus.AMBIGUOUS,
            evidence=["multiple_alias_candidates"],
            confidence_level=ConfidenceLevel.WEAK,
            candidate_entity_ids=sorted(candidates),
            detail="homonym_protection",
        )

    # ------------------------------------------------------------ batch helper

    async def resolve_many(
        self, mentions: list[str], context: ResolutionContext | None = None
    ) -> list[ResolutionResult]:
        if not self._loaded:
            await self.load()
        return [await self.resolve(m, context) for m in mentions]
