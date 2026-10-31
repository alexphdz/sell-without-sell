"""Module 04 resolution tests (RES-01..RES-36 core coverage). Requires PostgreSQL."""

from __future__ import annotations

import pytest

from kipu_pay.identity.models import (
    ConfidenceLevel,
    ResolutionContext,
    ResolutionStatus,
)
from kipu_pay.identity.registry import RegistryService, deterministic_entity_id
from kipu_pay.identity.resolver import IdentityResolver
from kipu_pay.normalization.models import TableRecord

pytestmark = pytest.mark.asyncio


def _client(cid: str, name: str, cedula: str = "", email: str = "", phone: str = "") -> TableRecord:
    return TableRecord(
        id=f"clientes:{cid}",
        table="clientes",
        columns={
            "cliente_id": cid,
            "nombre_completo": name,
            "num_doc": cedula or None,
            "correo": email or None,
            "celular": phone or None,
        },
    )


def _employee(eid: str, name: str, cedula: str = "", email: str = "") -> TableRecord:
    return TableRecord(
        id=f"empleados:{eid}",
        table="empleados",
        columns={"id": eid, "nombre": name, "documento": cedula or None, "correo": email or None},
    )


@pytest.fixture
async def resolver(db_session) -> IdentityResolver:
    svc = RegistryService(db_session)
    await svc.build_registry(
        [
            _client("CL-1", "Sofía Ramírez López", "1.000.000.001", "sofia@gmail.com", "3000000001"),
            _client("CL-2", "Carlos Pérez", "22222222"),
            _client("CL-3", "Carlos Pérez", "33333333"),  # homonym of CL-2
            _employee("KP-001", "Mateo Herrera Ríos", "80000002", "mateo.herrera@demo-fintech.co"),
        ],
        chat_users=[
            {"id": "U0MATEO1", "is_bot": False, "profile": {"email": "mateo.herrera@demo-fintech.co"}},
        ],
    )
    r = IdentityResolver(db_session)
    await r.load()
    return r


class TestStrongIdentifiers:
    async def test_exact_client_id(self, resolver) -> None:
        res = await resolver.resolve("CL-1")
        assert res.status == ResolutionStatus.MATCHED
        assert res.entity_id == deterministic_entity_id("clientes", "CL-1")
        assert res.confidence_level == ConfidenceLevel.STRONG

    async def test_exact_employee_id(self, resolver) -> None:
        res = await resolver.resolve("KP-001")
        assert res.status == ResolutionStatus.MATCHED
        assert res.entity_id == deterministic_entity_id("empleados", "KP-001")

    async def test_dotted_cedula(self, resolver) -> None:
        res = await resolver.resolve("1.000.000.001")
        assert res.status == ResolutionStatus.MATCHED
        assert res.entity_id == deterministic_entity_id("clientes", "CL-1")

    async def test_plain_cedula_same_entity(self, resolver) -> None:
        dotted = await resolver.resolve("1.000.000.001")
        plain = await resolver.resolve("1000000001")
        assert dotted.entity_id == plain.entity_id

    async def test_verified_email(self, resolver) -> None:
        res = await resolver.resolve("sofia@gmail.com")
        assert res.status == ResolutionStatus.MATCHED
        assert res.entity_id == deterministic_entity_id("clientes", "CL-1")

    async def test_email_domain_case_insensitive(self, resolver) -> None:
        res = await resolver.resolve("sofia@GMAIL.COM")
        assert res.status == ResolutionStatus.MATCHED

    async def test_verified_phone(self, resolver) -> None:
        res = await resolver.resolve("3000000001")
        assert res.status == ResolutionStatus.MATCHED
        assert res.entity_id == deterministic_entity_id("clientes", "CL-1")

    async def test_known_slack_uid(self, resolver) -> None:
        res = await resolver.resolve("U0MATEO1")
        assert res.status == ResolutionStatus.MATCHED
        assert res.entity_id == deterministic_entity_id("empleados", "KP-001")

    async def test_unknown_slack_uid(self, resolver) -> None:
        res = await resolver.resolve("U0ZZZZZZ")
        assert res.status == ResolutionStatus.UNKNOWN

    async def test_unknown_client_id(self, resolver) -> None:
        res = await resolver.resolve("CL-99999")
        assert res.status == ResolutionStatus.UNKNOWN
        assert res.detail == "unknown_source_id"

    async def test_id_shaped_token_never_matches_as_name(self, resolver) -> None:
        # e.g. TX-000158 is a transaction key, not a person
        res = await resolver.resolve("TX-000158")
        assert res.status == ResolutionStatus.UNKNOWN
        assert res.detail == "unknown_source_id"


class TestNamesAndAmbiguity:
    async def test_unique_exact_full_name_contextual(self, resolver) -> None:
        res = await resolver.resolve("Sofía Ramírez López")
        assert res.status == ResolutionStatus.MATCHED
        assert res.confidence_level == ConfidenceLevel.CONTEXTUAL
        assert res.entity_id == deterministic_entity_id("clientes", "CL-1")

    async def test_homonym_ambiguous(self, resolver) -> None:
        res = await resolver.resolve("Carlos Pérez")
        assert res.status == ResolutionStatus.AMBIGUOUS
        assert len(res.candidate_entity_ids) == 2
        assert res.entity_id is None

    async def test_homonyms_are_separate_entities(self, resolver) -> None:
        a = await resolver.resolve("22222222")
        b = await resolver.resolve("33333333")
        assert a.status == b.status == ResolutionStatus.MATCHED
        assert a.entity_id != b.entity_id

    async def test_first_name_only_not_forced(self, resolver) -> None:
        res = await resolver.resolve("Sofía")
        assert res.status == ResolutionStatus.UNKNOWN
        assert res.confidence_level == ConfidenceLevel.WEAK

    async def test_surname_only_not_forced(self, resolver) -> None:
        res = await resolver.resolve("Ramírez")
        assert res.status == ResolutionStatus.UNKNOWN

    async def test_initials_not_forced(self, resolver) -> None:
        res = await resolver.resolve("S.R.L.")
        assert res.status == ResolutionStatus.UNKNOWN

    async def test_accent_insensitive_lookup(self, resolver) -> None:
        res = await resolver.resolve("Sofia Ramirez Lopez")  # no accents
        assert res.status == ResolutionStatus.MATCHED

    async def test_uppercase_lookup(self, resolver) -> None:
        res = await resolver.resolve("SOFÍA RAMÍREZ LÓPEZ")
        assert res.status == ResolutionStatus.MATCHED

    async def test_extra_spaces_lookup(self, resolver) -> None:
        res = await resolver.resolve("  Sofía   Ramírez  López ")
        assert res.status == ResolutionStatus.MATCHED

    async def test_unknown_full_name(self, resolver) -> None:
        res = await resolver.resolve("Persona Inexistente Total")
        assert res.status == ResolutionStatus.UNKNOWN


class TestConflicts:
    async def test_contradictory_context(self, resolver) -> None:
        # Mention resolves to CL-1 but the context expects CL-2 → conflict.
        ctx = ResolutionContext(expected_source_id="CL-2")
        res = await resolver.resolve("Sofía Ramírez López", ctx)
        assert res.status == ResolutionStatus.CONFLICT
        assert res.entity_id is None
        assert deterministic_entity_id("clientes", "CL-1") in res.candidate_entity_ids

    async def test_matching_context_no_conflict(self, resolver) -> None:
        ctx = ResolutionContext(expected_source_id="CL-1")
        res = await resolver.resolve("Sofía Ramírez López", ctx)
        assert res.status == ResolutionStatus.MATCHED


class TestCrossSource:
    async def test_client_in_table_and_chat_same_entity(self, resolver) -> None:
        by_fk = await resolver.resolve("CL-1", ResolutionContext(source_type="table"))
        by_name = await resolver.resolve("Sofía Ramírez López", ResolutionContext(source_type="chat"))
        assert by_fk.entity_id == by_name.entity_id

    async def test_employee_in_table_and_document_same_entity(self, resolver) -> None:
        by_id = await resolver.resolve("KP-001", ResolutionContext(source_type="table"))
        by_name = await resolver.resolve("Mateo Herrera Ríos", ResolutionContext(source_type="document"))
        assert by_id.entity_id == by_name.entity_id

    async def test_orphan_fk_unresolved(self, resolver) -> None:
        res = await resolver.resolve("CL-55555")
        assert res.status == ResolutionStatus.UNKNOWN
        assert res.entity_id is None

    async def test_two_names_in_same_message_independent(self, resolver) -> None:
        r1 = await resolver.resolve("Sofía Ramírez López")
        r2 = await resolver.resolve("Mateo Herrera Ríos")
        assert r1.entity_id != r2.entity_id
        assert r1.status == r2.status == ResolutionStatus.MATCHED

    async def test_author_not_assumed_pii_owner(self, resolver) -> None:
        # An agent (author) mentions a client: the mention resolves to the
        # client, independent of the author's slack UID in context.
        ctx = ResolutionContext(source_type="chat", author_slack_uid="U0MATEO1")
        res = await resolver.resolve("Sofía Ramírez López", ctx)
        assert res.entity_id == deterministic_entity_id("clientes", "CL-1")

    async def test_unknown_third_party(self, resolver) -> None:
        res = await resolver.resolve("Vecino Desconocido García")
        assert res.status == ResolutionStatus.UNKNOWN


class TestGrowthAndDeterminism:
    async def test_new_client_resolvable_after_growth(self, db_session, resolver) -> None:
        svc = RegistryService(db_session)
        await svc.build_registry([_client("CL-9", "Nueva Cliente Pagalo")])
        await resolver.load()  # reload lookup maps
        res = await resolver.resolve("CL-9")
        assert res.status == ResolutionStatus.MATCHED

    async def test_old_identity_stable_after_growth(self, db_session, resolver) -> None:
        before = (await resolver.resolve("CL-1")).entity_id
        svc = RegistryService(db_session)
        await svc.build_registry([_client("CL-9", "Nueva Cliente Pagalo")])
        await resolver.load()
        after = (await resolver.resolve("CL-1")).entity_id
        assert before == after

    async def test_repeated_resolution_deterministic(self, resolver) -> None:
        results = [await resolver.resolve("CL-1") for _ in range(5)]
        assert len({r.entity_id for r in results}) == 1

    async def test_reimport_no_resolution_drift(self, db_session, resolver) -> None:
        before = (await resolver.resolve("1000000001")).entity_id
        svc = RegistryService(db_session)
        await svc.build_registry(
            [_client("CL-1", "Sofía Ramírez López", "1.000.000.001", "sofia@gmail.com", "3000000001")]
        )
        await resolver.load()
        after = (await resolver.resolve("1000000001")).entity_id
        assert before == after


class TestMisc:
    async def test_empty_mention(self, resolver) -> None:
        res = await resolver.resolve("")
        assert res.status == ResolutionStatus.UNKNOWN

    async def test_resolve_many_batched(self, resolver) -> None:
        results = await resolver.resolve_many(["CL-1", "KP-001", "CL-99999"])
        assert [r.status for r in results] == [
            ResolutionStatus.MATCHED,
            ResolutionStatus.MATCHED,
            ResolutionStatus.UNKNOWN,
        ]

    async def test_lookup_maps_preloaded_once(self, resolver) -> None:
        # After load(), resolution is in-memory: no per-token DB queries.
        assert resolver._loaded
        assert len(resolver._identifiers) > 0
        assert len(resolver._aliases) > 0
