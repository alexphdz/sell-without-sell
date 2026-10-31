"""Module 03 registry tests (REG-01..REG-20). Requires PostgreSQL."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from kipu_pay.identity.db_models import (
    IdentityAlias,
    IdentityConflict,
    IdentityEntity,
    IdentityIdentifier,
    IdentitySourceLink,
)
from kipu_pay.identity.registry import RegistryService, deterministic_entity_id
from kipu_pay.normalization.models import TableRecord

pytestmark = pytest.mark.asyncio


def _client(cid: str, name: str, cedula: str = "", email: str = "", phone: str = "") -> TableRecord:
    return TableRecord(
        id=f"clientes:{cid}",
        table="clientes",
        columns={
            "cliente_id": cid,
            "nombre_completo": name,
            "tipo_doc": "CC",
            "num_doc": cedula or None,
            "correo": email or None,
            "celular": phone or None,
        },
    )


def _employee(eid: str, name: str, cedula: str = "", email: str = "", phone: str = "") -> TableRecord:
    return TableRecord(
        id=f"empleados:{eid}",
        table="empleados",
        columns={
            "id": eid,
            "nombre": name,
            "documento": cedula or None,
            "correo": email or None,
            "celular": phone or None,
        },
    )


class TestImport:
    async def test_import_client(self, db_session) -> None:
        svc = RegistryService(db_session)
        result = await svc.build_registry([_client("CL-1", "Ana Gómez", "12345678", "ana@x.com", "3001234567")])
        assert result.entities_created == 1
        entity = await db_session.scalar(select(IdentityEntity))
        assert entity.canonical_name == "Ana Gómez"
        assert entity.source_type == "clientes"
        assert entity.source_id == "CL-1"

    async def test_import_employee(self, db_session) -> None:
        svc = RegistryService(db_session)
        result = await svc.build_registry([_employee("KP-001", "Luis Pérez", "87654321")])
        assert result.entities_created == 1
        entity = await db_session.scalar(select(IdentityEntity))
        assert entity.source_type == "empleados"
        assert entity.source_id == "KP-001"

    async def test_import_same_client_twice_no_duplicate(self, db_session) -> None:
        svc = RegistryService(db_session)
        rec = _client("CL-1", "Ana Gómez", "12345678")
        r1 = await svc.build_registry([rec])
        r2 = await svc.build_registry([rec])
        assert r1.entities_created == 1
        assert r2.entities_created == 0
        assert r2.entities_existing == 1
        count = await db_session.scalar(select(func.count(IdentityEntity.id)))
        assert count == 1

    async def test_import_same_employee_twice_no_duplicate(self, db_session) -> None:
        svc = RegistryService(db_session)
        rec = _employee("KP-001", "Luis Pérez")
        await svc.build_registry([rec])
        await svc.build_registry([rec])
        count = await db_session.scalar(select(func.count(IdentityEntity.id)))
        assert count == 1

    async def test_reorder_input_same_identities(self, db_session) -> None:
        svc = RegistryService(db_session)
        a = _client("CL-1", "Ana Gómez")
        b = _client("CL-2", "Bea Ruiz")
        await svc.build_registry([a, b])
        ids_1 = {
            (e.source_id, e.id)
            for e in (await db_session.scalars(select(IdentityEntity))).all()
        }
        # Reimport in reverse order; identities must be identical.
        await svc.build_registry([b, a])
        ids_2 = {
            (e.source_id, e.id)
            for e in (await db_session.scalars(select(IdentityEntity))).all()
        }
        assert ids_1 == ids_2

    async def test_growth_preserves_existing_ids(self, db_session) -> None:
        svc = RegistryService(db_session)
        await svc.build_registry([_client("CL-1", "Ana Gómez")])
        before = (await db_session.scalar(select(IdentityEntity))).id
        await svc.build_registry([_client("CL-1", "Ana Gómez"), _client("CL-2", "Bea Ruiz")])
        rows = (await db_session.scalars(select(IdentityEntity))).all()
        assert len(rows) == 2
        preserved = next(e for e in rows if e.source_id == "CL-1")
        assert preserved.id == before


class TestDeterministicIds:
    async def test_stable_uuid(self, db_session) -> None:
        assert deterministic_entity_id("clientes", "CL-1") == deterministic_entity_id("clientes", "CL-1")
        assert deterministic_entity_id("clientes", "CL-1") != deterministic_entity_id("empleados", "CL-1")

    async def test_entity_uses_deterministic_id(self, db_session) -> None:
        svc = RegistryService(db_session)
        await svc.build_registry([_client("CL-1", "Ana Gómez")])
        entity = await db_session.scalar(select(IdentityEntity))
        assert entity.id == deterministic_entity_id("clientes", "CL-1")


class TestIdentifiers:
    async def test_dotted_cedula_normalized(self, db_session) -> None:
        svc = RegistryService(db_session)
        await svc.build_registry([_client("CL-1", "Ana Gómez", "1.234.567.890")])
        ident = await db_session.scalar(
            select(IdentityIdentifier).where(IdentityIdentifier.identifier_type == "cedula")
        )
        assert ident.normalized_value == "1234567890"
        assert ident.original_value == "1.234.567.890"  # original preserved

    async def test_email_original_preserved(self, db_session) -> None:
        svc = RegistryService(db_session)
        await svc.build_registry([_client("CL-1", "Ana Gómez", email="Ana.Gomez@X.COM")])
        ident = await db_session.scalar(
            select(IdentityIdentifier).where(IdentityIdentifier.identifier_type == "email")
        )
        assert ident.original_value == "Ana.Gomez@X.COM"
        assert ident.normalized_value == "Ana.Gomez@x.com"  # domain lowered, local kept

    async def test_phone_original_preserved(self, db_session) -> None:
        svc = RegistryService(db_session)
        await svc.build_registry([_client("CL-1", "Ana Gómez", phone="300 123-4567")])
        ident = await db_session.scalar(
            select(IdentityIdentifier).where(IdentityIdentifier.identifier_type == "phone")
        )
        assert ident.original_value == "300 123-4567"
        assert ident.normalized_value == "3001234567"

    async def test_unknown_optional_identifier_not_fabricated(self, db_session) -> None:
        svc = RegistryService(db_session)
        await svc.build_registry([_client("CL-1", "Ana Gómez")])  # no cedula/email/phone
        types = {
            i.identifier_type
            for i in (await db_session.scalars(select(IdentityIdentifier))).all()
        }
        assert types == {"client_id"}


class TestHomonymsAndConflicts:
    async def test_two_people_same_name_separate_entities(self, db_session) -> None:
        svc = RegistryService(db_session)
        await svc.build_registry([
            _client("CL-1", "Carlos Gómez", "11111111"),
            _client("CL-2", "Carlos Gómez", "22222222"),
        ])
        count = await db_session.scalar(select(func.count(IdentityEntity.id)))
        assert count == 2

    async def test_conflicting_cedula_no_merge(self, db_session) -> None:
        svc = RegistryService(db_session)
        result = await svc.build_registry([
            _client("CL-1", "Ana Gómez", "11111111"),
            _client("CL-2", "Bea Ruiz", "11111111"),  # same cedula!
        ])
        assert result.conflicts_recorded == 1
        # Both entities exist (no merge), cedula stays with first owner.
        count = await db_session.scalar(select(func.count(IdentityEntity.id)))
        assert count == 2
        conflict = await db_session.scalar(select(IdentityConflict))
        assert conflict.identifier_type == "cedula"
        # Conflict row stores a hash, never the raw value.
        assert "11111111" not in conflict.normalized_value_hash

    async def test_conflict_preserves_original_mapping(self, db_session) -> None:
        svc = RegistryService(db_session)
        await svc.build_registry([_client("CL-1", "Ana Gómez", "11111111")])
        first_owner = (await db_session.scalar(select(IdentityEntity))).id
        await svc.build_registry([_client("CL-2", "Bea Ruiz", "11111111")])
        ident = await db_session.scalar(
            select(IdentityIdentifier).where(IdentityIdentifier.identifier_type == "cedula")
        )
        assert ident.entity_id == first_owner


class TestIdempotency:
    async def test_duplicate_alias_idempotent(self, db_session) -> None:
        svc = RegistryService(db_session)
        rec = _client("CL-1", "Ana Gómez")
        await svc.build_registry([rec])
        await svc.build_registry([rec])
        count = await db_session.scalar(select(func.count(IdentityAlias.id)))
        assert count == 1

    async def test_repeated_source_link_idempotent(self, db_session) -> None:
        svc = RegistryService(db_session)
        rec = _client("CL-1", "Ana Gómez")
        await svc.build_registry([rec])
        await svc.build_registry([rec])
        count = await db_session.scalar(select(func.count(IdentitySourceLink.id)))
        assert count == 1

    async def test_repeated_identifiers_idempotent(self, db_session) -> None:
        svc = RegistryService(db_session)
        rec = _client("CL-1", "Ana Gómez", "12345678", "a@x.com", "3001234567")
        r1 = await svc.build_registry([rec])
        r2 = await svc.build_registry([rec])
        assert r1.identifiers_created == 4  # client_id, cedula, email, phone
        assert r2.identifiers_created == 0
        assert r2.conflicts_recorded == 0


class TestProvenance:
    async def test_source_provenance(self, db_session) -> None:
        svc = RegistryService(db_session)
        await svc.build_registry([_client("CL-9", "Ana Gómez", "12345678")])
        link = await db_session.scalar(select(IdentitySourceLink))
        assert link.source_type == "clientes"
        assert link.source_record_id == "clientes:CL-9"
        alias = await db_session.scalar(select(IdentityAlias))
        assert alias.provenance == "clientes.nombre_completo"

    async def test_unsupported_table_ignored_explicitly(self, db_session) -> None:
        svc = RegistryService(db_session)
        other = TableRecord(id="pqrs:PQR-1", table="pqrs", columns={"radicado": "PQR-1"})
        result = await svc.build_registry([other])
        assert result.entities_created == 0
        assert result.errors == []  # not an error: simply not authoritative

    async def test_missing_required_reported(self, db_session) -> None:
        svc = RegistryService(db_session)
        bad = TableRecord(id="clientes:CL-X", table="clientes", columns={"cliente_id": "CL-X"})
        result = await svc.build_registry([bad])
        assert result.entities_created == 0
        assert any("client_missing_required" in e for e in result.errors)


class TestSlackUidMapping:
    async def test_email_backed_uid_mapped(self, db_session) -> None:
        svc = RegistryService(db_session)
        users = [{
            "id": "U0AAAA1",
            "is_bot": False,
            "profile": {"email": "ana@x.com"},
        }]
        result = await svc.build_registry(
            [_client("CL-1", "Ana Gómez", email="ana@x.com")], chat_users=users
        )
        assert result.slack_uids_mapped == 1
        ident = await db_session.scalar(
            select(IdentityIdentifier).where(IdentityIdentifier.identifier_type == "slack_uid")
        )
        assert ident.normalized_value == "U0AAAA1"

    async def test_bot_never_mapped(self, db_session) -> None:
        svc = RegistryService(db_session)
        users = [{"id": "UBOT01", "is_bot": True, "profile": {"email": "ana@x.com"}}]
        result = await svc.build_registry(
            [_client("CL-1", "Ana Gómez", email="ana@x.com")], chat_users=users
        )
        assert result.slack_uids_mapped == 0

    async def test_name_only_never_mapped(self, db_session) -> None:
        svc = RegistryService(db_session)
        users = [{
            "id": "U0AAAA1",
            "is_bot": False,
            "real_name": "Ana Gómez",
            "profile": {"real_name": "Ana Gómez"},  # no email/phone
        }]
        result = await svc.build_registry([_client("CL-1", "Ana Gómez")], chat_users=users)
        assert result.slack_uids_mapped == 0


class TestTransactionality:
    async def test_persisted_after_commit(self, db_engine, db_session) -> None:
        svc = RegistryService(db_session)
        await svc.build_registry([_client("CL-1", "Ana Gómez")])
        # New session == new connection: simulates restart persistence.
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        maker = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
        async with maker() as other:
            entity = await other.scalar(select(IdentityEntity))
            assert entity is not None
            assert entity.id == deterministic_entity_id("clientes", "CL-1")
