"""Pseudonym repository and span replacement engine."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kipu_pay.anonymization.models import Action, DetectionCategory, DetectionSpan
from kipu_pay.anonymization.generator import (
    generate_address,
    generate_birth_year,
    generate_cedula,
    generate_email,
    generate_handle,
    generate_person_name,
    generate_phone,
    generalize_dob,
    generalize_neighborhood,
    generalize_occupation,
)
from kipu_pay.anonymization.pseudonym_models import (
    EntityPseudonym,
    UnknownPersonPseudonym,
)
from kipu_pay.core.logging import get_logger

logger = get_logger(__name__)


def _scope_hash(text: str, secret: str) -> str:
    return hashlib.sha256(f"{text}:{secret}".encode("utf-8")).hexdigest()


class PseudonymRepository:
    """CRUD for persistent pseudonym mappings."""

    def __init__(self, session: AsyncSession, secret: str) -> None:
        self.session = session
        self.secret = secret

    async def get_or_create(
        self,
        entity_id: uuid.UUID | None,
        category: DetectionCategory,
        original_value: str,
        generator_fn: Any,
    ) -> str:
        if entity_id is not None:
            cat_val = category.value if hasattr(category, "value") else category
            existing = await self.session.scalar(
                select(EntityPseudonym).where(
                    EntityPseudonym.entity_id == entity_id,
                    EntityPseudonym.category == cat_val,
                )
            )
            if existing:
                return existing.pseudonym
            pseudonym = generator_fn(original_value, entity_id, self.secret)
            self.session.add(
                EntityPseudonym(
                    entity_id=entity_id,
                    category=cat_val,
                    pseudonym=pseudonym,
                )
            )
            await self.session.flush()
            return pseudonym
        else:
            sh = _scope_hash(original_value, self.secret)
            cat_val = category.value if hasattr(category, "value") else category
            existing = await self.session.scalar(
                select(UnknownPersonPseudonym).where(
                    UnknownPersonPseudonym.scope_hash == sh,
                    UnknownPersonPseudonym.category == cat_val,
                )
            )
            if existing:
                return existing.pseudonym
            det_id = uuid.UUID(hashlib.md5(sh.encode()).hexdigest()[:32])
            pseudonym = generator_fn(original_value, det_id, self.secret)
            self.session.add(
                UnknownPersonPseudonym(
                    scope_hash=sh,
                    category=cat_val,
                    pseudonym=pseudonym,
                )
            )
            await self.session.flush()
            return pseudonym

    async def get_pseudonym_any(
        self, entity_id: uuid.UUID | None, scope_hash: str | None, category: DetectionCategory
    ) -> str | None:
        cat_val = category.value if hasattr(category, "value") else category
        if entity_id is not None:
            existing = await self.session.scalar(
                select(EntityPseudonym).where(
                    EntityPseudonym.entity_id == entity_id,
                    EntityPseudonym.category == cat_val,
                )
            )
            if existing:
                return existing.pseudonym
        if scope_hash:
            existing = await self.session.scalar(
                select(UnknownPersonPseudonym).where(
                    UnknownPersonPseudonym.scope_hash == scope_hash,
                    UnknownPersonPseudonym.category == cat_val,
                )
            )
            if existing:
                return existing.pseudonym
        return None

    async def resolve_manager_pseudonym(self, manager_name: str) -> str | None:
        from kipu_pay.identity.db_models import IdentityAlias, IdentityEntity
        from kipu_pay.identity.normalizers import normalize_name

        norm = normalize_name(manager_name)
        alias = await self.session.scalar(
            select(IdentityAlias)
            .join(IdentityEntity, IdentityEntity.id == IdentityAlias.entity_id)
            .where(
                IdentityAlias.normalized_alias == norm,
                IdentityEntity.source_type == "empleados",
            )
        )
        if alias:
            existing = await self.session.scalar(
                select(EntityPseudonym).where(
                    EntityPseudonym.entity_id == alias.entity_id,
                    EntityPseudonym.category == "person",
                )
            )
            if existing:
                return existing.pseudonym
        return None


async def resolve_replacement(span: DetectionSpan, repo: PseudonymRepository) -> str:
    cat = span.category
    cat_str = cat.value if hasattr(cat, "value") else str(cat)
    action = span.action
    action_str = action.value if hasattr(action, "value") else str(action)
    val = span.matched_text
    eid = span.entity_id

    if action_str == "keep":
        return val
    if action_str == "generalize":
        if cat_str == "occupation":
            return generalize_occupation(val)
        if cat_str == "neighborhood":
            return generalize_neighborhood(val, "")
        if cat_str == "dob":
            return generalize_dob(val)
        if cat_str == "birth_year":
            det_id = eid if eid else uuid.uuid4()
            return generate_birth_year(val, det_id, repo.secret)
        if span.generalization:
            return span.generalization
        return val

    if cat_str == "person":
        return await repo.get_or_create(eid, cat, val, generate_person_name)
    if cat_str == "email":
        return await repo.get_or_create(eid, cat, val, generate_email)
    if cat_str == "phone":
        return await repo.get_or_create(eid, cat, val, generate_phone)
    if cat_str == "national_id":
        return await repo.get_or_create(eid, cat, val, generate_cedula)
    if cat_str == "address":
        return await repo.get_or_create(eid, cat, val, generate_address)
    if cat_str == "handle":
        return await repo.get_or_create(eid, cat, val, generate_handle)
    if cat_str == "reports_to":
        manager_pseudo = await repo.resolve_manager_pseudonym(val)
        if manager_pseudo:
            return manager_pseudo
        return await repo.get_or_create(eid, DetectionCategory.PERSON, val, generate_person_name)
    return val


class ReplacementEngine:
    """Replace spans in text right-to-left."""

    async def apply(self, text: str, spans: list[DetectionSpan], repo: PseudonymRepository) -> str:
        if not spans:
            return text
        sorted_spans = sorted(spans, key=lambda s: s.start, reverse=True)
        result = text
        for span in sorted_spans:
            replacement = await resolve_replacement(span, repo)
            result = result[: span.start] + replacement + result[span.end :]
        return result
