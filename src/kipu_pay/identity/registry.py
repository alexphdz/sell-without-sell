"""Persistent identity registry service.

Builds stable person identities from authoritative normalized sources
(clientes.csv, empleados.xml) and maps verified chat users.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kipu_pay.core.logging import get_logger
from kipu_pay.identity.db_models import (
    IdentityAlias,
    IdentityConflict,
    IdentityEntity,
    IdentityIdentifier,
    IdentitySourceLink,
)
from kipu_pay.identity.models import RegistryResult
from kipu_pay.identity.normalizers import (
    normalize_cedula,
    normalize_email,
    normalize_name,
    normalize_phone,
)
from kipu_pay.normalization.models import TableRecord

logger = get_logger(__name__)

# Project namespace for deterministic entity UUIDs.
_ENTITY_NAMESPACE = uuid.UUID("7c9e4a02-55f1-4f3a-9e38-000000000001")


def deterministic_entity_id(source_type: str, source_id: str) -> uuid.UUID:
    """Stable UUID derived from the authoritative source identity."""
    return uuid.uuid5(_ENTITY_NAMESPACE, f"{source_type}:{source_id}")


def _value_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class RegistryService:
    """CRUD + import operations over the identity registry."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------------------------------------------------------------- imports

    async def build_registry(
        self,
        tables: Sequence[TableRecord],
        chat_users: Sequence[dict[str, Any]] | None = None,
    ) -> RegistryResult:
        """Import authoritative identities; idempotent and conflict-safe."""
        result = RegistryResult()

        clientes = [t for t in tables if t.table == "clientes"]
        empleados = [t for t in tables if t.table == "empleados"]

        # Deterministic processing order: sort by record id.
        for record in sorted(clientes, key=lambda r: r.id):
            await self._import_client(record, result)
        for record in sorted(empleados, key=lambda r: r.id):
            await self._import_employee(record, result)

        if chat_users:
            await self._import_chat_users(chat_users, result)

        await self.session.commit()
        logger.info(
            "registry_build_complete",
            created=result.entities_created,
            existing=result.entities_existing,
            identifiers=result.identifiers_created,
            conflicts=result.conflicts_recorded,
            slack_uids=result.slack_uids_mapped,
        )
        return result

    async def _import_client(self, record: TableRecord, result: RegistryResult) -> None:
        cols = record.columns
        source_id = (cols.get("cliente_id") or "").strip()
        name = (cols.get("nombre_completo") or "").strip()
        if not source_id or not name:
            result.errors.append(f"client_missing_required:{record.id}")
            return

        entity = await self._get_or_create_entity(
            source_type="clientes", source_id=source_id, canonical_name=name, result=result
        )

        src_ref = record.id
        await self._attach_identifier(entity, "client_id", source_id, source_id, src_ref, result)

        cedula = normalize_cedula(cols.get("num_doc") or "")
        if cedula:
            await self._attach_identifier(
                entity, "cedula", cedula, cols.get("num_doc") or "", src_ref, result
            )

        email = normalize_email(cols.get("correo") or "")
        if email:
            await self._attach_identifier(
                entity, "email", email, cols.get("correo") or "", src_ref, result
            )

        phone = normalize_phone(cols.get("celular") or "")
        if phone:
            await self._attach_identifier(
                entity, "phone", phone, cols.get("celular") or "", src_ref, result
            )

        await self._attach_alias(entity, name, "clientes.nombre_completo", result)
        await self._attach_source_link(entity, "clientes", record.id, result)

    async def _import_employee(self, record: TableRecord, result: RegistryResult) -> None:
        cols = record.columns
        source_id = (cols.get("id") or "").strip()
        name = (cols.get("nombre") or "").strip()
        if not source_id or not name:
            result.errors.append(f"employee_missing_required:{record.id}")
            return

        entity = await self._get_or_create_entity(
            source_type="empleados", source_id=source_id, canonical_name=name, result=result
        )

        src_ref = record.id
        await self._attach_identifier(entity, "employee_id", source_id, source_id, src_ref, result)

        cedula = normalize_cedula(cols.get("documento") or "")
        if cedula:
            await self._attach_identifier(
                entity, "cedula", cedula, cols.get("documento") or "", src_ref, result
            )

        email = normalize_email(cols.get("correo") or "")
        if email:
            await self._attach_identifier(
                entity, "email", email, cols.get("correo") or "", src_ref, result
            )

        phone = normalize_phone(cols.get("celular") or "")
        if phone:
            await self._attach_identifier(
                entity, "phone", phone, cols.get("celular") or "", src_ref, result
            )

        await self._attach_alias(entity, name, "empleados.nombre", result)
        await self._attach_source_link(entity, "empleados", record.id, result)

    async def _import_chat_users(
        self, users: Sequence[dict[str, Any]], result: RegistryResult
    ) -> None:
        """Map Slack UIDs to entities using strong (email/phone) evidence only.

        Name-only similarity never creates a slack_uid mapping.
        """
        for user in sorted(users, key=lambda u: str(u.get("id", ""))):
            uid = user.get("id")
            if not uid or user.get("is_bot") or user.get("deleted"):
                continue
            profile = user.get("profile", {}) or {}

            entity = None
            evidence = None

            email = normalize_email(profile.get("email") or "")
            if email:
                entity = await self._entity_by_identifier("email", email)
                evidence = "profile_email"

            if entity is None:
                phone = normalize_phone(profile.get("phone") or "")
                if phone:
                    entity = await self._entity_by_identifier("phone", phone)
                    evidence = "profile_phone"

            if entity is None:
                continue

            attached = await self._attach_identifier(
                entity, "slack_uid", str(uid), str(uid), f"chat_users:{evidence}", result
            )
            if attached:
                result.slack_uids_mapped += 1

    # ---------------------------------------------------------------- helpers

    async def _get_or_create_entity(
        self, source_type: str, source_id: str, canonical_name: str, result: RegistryResult
    ) -> IdentityEntity:
        existing = await self.session.scalar(
            select(IdentityEntity).where(
                IdentityEntity.source_type == source_type,
                IdentityEntity.source_id == source_id,
            )
        )
        if existing is not None:
            result.entities_existing += 1
            return existing

        entity = IdentityEntity(
            id=deterministic_entity_id(source_type, source_id),
            entity_type="person",
            canonical_name=canonical_name,
            source_type=source_type,
            source_id=source_id,
        )
        self.session.add(entity)
        await self.session.flush()
        result.entities_created += 1
        return entity

    async def _attach_identifier(
        self,
        entity: IdentityEntity,
        identifier_type: str,
        normalized_value: str,
        original_value: str,
        source_reference: str,
        result: RegistryResult,
    ) -> bool:
        """Attach identifier; record conflict if mapped to another entity."""
        existing = await self.session.scalar(
            select(IdentityIdentifier).where(
                IdentityIdentifier.identifier_type == identifier_type,
                IdentityIdentifier.normalized_value == normalized_value,
            )
        )
        if existing is not None:
            if existing.entity_id == entity.id:
                return False  # idempotent
            # Conflict: same identifier, different entity. Never merge.
            value_hash = _value_hash(normalized_value)
            already_recorded = await self.session.scalar(
                select(IdentityConflict).where(
                    IdentityConflict.identifier_type == identifier_type,
                    IdentityConflict.normalized_value_hash == value_hash,
                    IdentityConflict.existing_entity_id == existing.entity_id,
                    IdentityConflict.incoming_source_reference == source_reference,
                )
            )
            if already_recorded is None:
                self.session.add(
                    IdentityConflict(
                        identifier_type=identifier_type,
                        normalized_value_hash=value_hash,
                        existing_entity_id=existing.entity_id,
                        incoming_source_reference=source_reference,
                        detail=f"identifier_already_mapped:{identifier_type}",
                    )
                )
                result.conflicts_recorded += 1
                logger.warning(
                    "identity_conflict",
                    identifier_type=identifier_type,
                    source_reference=source_reference,
                )
            return False

        self.session.add(
            IdentityIdentifier(
                entity_id=entity.id,
                identifier_type=identifier_type,
                normalized_value=normalized_value,
                original_value=original_value,
                source_reference=source_reference,
            )
        )
        await self.session.flush()
        result.identifiers_created += 1
        return True

    async def _attach_alias(
        self, entity: IdentityEntity, alias: str, provenance: str, result: RegistryResult
    ) -> None:
        normalized = normalize_name(alias)
        existing = await self.session.scalar(
            select(IdentityAlias).where(
                IdentityAlias.entity_id == entity.id,
                IdentityAlias.normalized_alias == normalized,
                IdentityAlias.provenance == provenance,
            )
        )
        if existing is not None:
            return
        self.session.add(
            IdentityAlias(
                entity_id=entity.id,
                alias=alias,
                normalized_alias=normalized,
                provenance=provenance,
            )
        )
        await self.session.flush()
        result.aliases_created += 1

    async def _attach_source_link(
        self, entity: IdentityEntity, source_type: str, source_record_id: str, result: RegistryResult
    ) -> None:
        existing = await self.session.scalar(
            select(IdentitySourceLink).where(
                IdentitySourceLink.source_type == source_type,
                IdentitySourceLink.source_record_id == source_record_id,
            )
        )
        if existing is not None:
            return
        self.session.add(
            IdentitySourceLink(
                entity_id=entity.id,
                source_type=source_type,
                source_record_id=source_record_id,
            )
        )
        await self.session.flush()
        result.source_links_created += 1

    # ---------------------------------------------------------------- lookups

    async def _entity_by_identifier(
        self, identifier_type: str, normalized_value: str
    ) -> IdentityEntity | None:
        return await self.session.scalar(
            select(IdentityEntity)
            .join(IdentityIdentifier, IdentityIdentifier.entity_id == IdentityEntity.id)
            .where(
                IdentityIdentifier.identifier_type == identifier_type,
                IdentityIdentifier.normalized_value == normalized_value,
            )
        )

    async def get_entity(self, entity_id: uuid.UUID) -> IdentityEntity | None:
        return await self.session.get(IdentityEntity, entity_id)

    async def entity_count(self) -> int:
        from sqlalchemy import func as sa_func

        return (
            await self.session.scalar(select(sa_func.count(IdentityEntity.id)))
        ) or 0
