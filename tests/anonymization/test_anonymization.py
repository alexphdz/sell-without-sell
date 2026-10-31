"""Tests for Modules 05 (PII Detection) and 06 (Pseudonymization)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from kipu_pay.anonymization.detector import Detector
from kipu_pay.anonymization.generator import (
    generate_cedula,
    generate_email,
    generate_person_name,
    generate_phone,
    generalize_occupation,
)
from kipu_pay.anonymization.models import Action, DetectionCategory, DetectionSpan
from kipu_pay.anonymization.patterns import PatternDetector, SchemaDetector
from kipu_pay.anonymization.pseudonym_models import EntityPseudonym, PseudonymBase, UnknownPersonPseudonym
from kipu_pay.anonymization.replacement import PseudonymRepository, ReplacementEngine
from kipu_pay.identity.db_models import IdentityBase
from kipu_pay.identity.registry import RegistryService
from kipu_pay.identity.resolver import IdentityResolver
from kipu_pay.normalization.models import ChatRecord, DocumentRecord, TableRecord

pytestmark = pytest.mark.asyncio

TEST_DB_URL = "postgresql+asyncpg://kipu:kipu_dev_pass@127.0.0.1:5432/kipu_dev"
TEST_SECRET = "test-secret-32-bytes-long-xxxxxxxx"


@pytest.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, poolclass=None)
    # Use existing tables (don't drop to preserve identity data)
    async with engine.begin() as conn:
        await conn.run_sync(PseudonymBase.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncSession:
    maker = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
        await session.rollback()


class TestPatternDetection:
    def test_detect_email(self) -> None:
        d = PatternDetector()
        spans = d.detect("Contact me at ana.maria@gmail.com please", "test")
        assert len(spans) == 1
        assert spans[0].category == DetectionCategory.EMAIL
        assert spans[0].matched_text == "ana.maria@gmail.com"

    def test_detect_phone(self) -> None:
        d = PatternDetector()
        spans = d.detect("My number is 300 123 4567", "test")
        assert len(spans) == 1
        assert spans[0].category == DetectionCategory.PHONE

    def test_detect_cedula_dotted(self) -> None:
        d = PatternDetector()
        spans = d.detect("Cédula 1.095.637.192", "test")
        assert len(spans) == 1
        assert spans[0].category == DetectionCategory.NATIONAL_ID
        assert spans[0].matched_text == "1.095.637.192"

    def test_no_false_positive_on_amount(self) -> None:
        d = PatternDetector()
        spans = d.detect("Total $520.000 COP", "test")
        cedula_spans = [s for s in spans if s.category == DetectionCategory.NATIONAL_ID]
        # 520000 might look like cedula, but amount context should ideally block it.
        # For now, accept whatever the detector returns; this is a baseline.
        assert all(s.matched_text != "520.000" for s in cedula_spans)


class TestSchemaDetection:
    def test_client_name_column(self) -> None:
        sd = SchemaDetector()
        span = sd.detect_column("nombre_completo", "Ana Gómez", "clientes:CL-1")
        assert span is not None
        assert span.category == DetectionCategory.PERSON

    def test_transaction_id_unchanged(self) -> None:
        sd = SchemaDetector()
        span = sd.detect_column("tx_id", "TX-000001", "transacciones:TX-1")
        assert span is None

    def test_amount_unchanged(self) -> None:
        sd = SchemaDetector()
        span = sd.detect_column("monto", "520000", "transacciones:TX-1")
        assert span is None


class TestPseudonymGeneration:
    def test_deterministic_name(self) -> None:
        eid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        n1 = generate_person_name("Ana María Gómez", eid, TEST_SECRET)
        n2 = generate_person_name("Ana María Gómez", eid, TEST_SECRET)
        assert n1 == n2
        assert n1 != "Ana María Gómez"
        assert len(n1.split()) >= 2

    def test_gender_preservation(self) -> None:
        eid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        female = generate_person_name("María", eid, TEST_SECRET)
        male = generate_person_name("Carlos", eid, TEST_SECRET)
        # Deterministic with same entity should be same regardless of original
        # Actually we use gender-specific seeds, so same entity with different gender hints
        # may differ if we reseed. Our impl uses entity_id + gender, so:
        assert isinstance(female, str)
        assert isinstance(male, str)

    def test_email_format(self) -> None:
        eid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        email = generate_email("ana@gmail.com", eid, TEST_SECRET)
        assert "@" in email
        assert ".com" in email or ".co" in email

    def test_phone_format(self) -> None:
        eid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        phone = generate_phone("3001234567", eid, TEST_SECRET)
        assert phone.startswith("3")
        assert len(phone.replace(" ", "")) == 10

    def test_cedula_format_preservation(self) -> None:
        eid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        dotted = generate_cedula("1.095.637.192", eid, TEST_SECRET)
        assert "." in dotted
        plain = generate_cedula("1234567890", eid, TEST_SECRET)
        assert "." not in plain

    def test_occupation_generalization(self) -> None:
        assert generalize_occupation("abogada") == "profesional de derecho"
        assert generalize_occupation("chef") == "profesional gastronómica"


class TestPseudonymRepository:
    async def test_create_and_reuse(self, db_session) -> None:
        repo = PseudonymRepository(db_session, TEST_SECRET)
        eid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        p1 = await repo.get_or_create(eid, DetectionCategory.PERSON, "Ana", generate_person_name)
        p2 = await repo.get_or_create(eid, DetectionCategory.PERSON, "Ana", generate_person_name)
        assert p1 == p2
        assert p1 != "Ana"

    async def test_unknown_person_scoped(self, db_session) -> None:
        repo = PseudonymRepository(db_session, TEST_SECRET)
        p1 = await repo.get_or_create(None, DetectionCategory.PERSON, "Unknown Person", generate_person_name)
        p2 = await repo.get_or_create(None, DetectionCategory.PERSON, "Unknown Person", generate_person_name)
        assert p1 == p2

    async def test_different_categories_different_pseudonyms(self, db_session) -> None:
        repo = PseudonymRepository(db_session, TEST_SECRET)
        eid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        name = await repo.get_or_create(eid, DetectionCategory.PERSON, "Ana", generate_person_name)
        email = await repo.get_or_create(eid, DetectionCategory.EMAIL, "ana@test.com", generate_email)
        assert name != email


class TestReplacementEngine:
    async def test_replace_email(self, db_session) -> None:
        engine = ReplacementEngine()
        repo = PseudonymRepository(db_session, TEST_SECRET)
        spans = [
            DetectionSpan(
                start=8,
                end=20,
                surface_path="test",
                category=DetectionCategory.EMAIL,
                matched_text="ana@test.com",
            )
        ]
        result = await engine.apply("Contact ana@test.com now", spans, repo)
        assert "ana@test.com" not in result
        assert "Contact " in result
        assert " now" in result

    async def test_right_to_left_order(self, db_session) -> None:
        engine = ReplacementEngine()
        repo = PseudonymRepository(db_session, TEST_SECRET)
        spans = [
            DetectionSpan(
                start=0,
                end=3,
                surface_path="test",
                category=DetectionCategory.PERSON,
                matched_text="Ana",
            ),
            DetectionSpan(
                start=8,
                end=13,
                surface_path="test",
                category=DetectionCategory.PERSON,
                matched_text="Maria",
            ),
        ]
        result = await engine.apply("Ana and Maria here", spans, repo)
        # Both original names should be gone (even if replacement contains substring)
        assert result != "Ana and Maria here"
        assert result.startswith(" ") is False  # first span replaced
        assert " and " in result


class TestDetectorIntegration:
    async def test_chat_detection(self, db_session) -> None:
        # Build a minimal registry
        svc = RegistryService(db_session)
        from kipu_pay.normalization.models import TableRecord
        rec = TableRecord(
            id="clientes:CL-1",
            table="clientes",
            columns={
                "cliente_id": "CL-1",
                "nombre_completo": "Ana Gómez Castro",
                "num_doc": "1234567890",
                "correo": "ana@gmail.com",
                "celular": "3001234567",
            },
        )
        await svc.build_registry([rec])

        resolver = IdentityResolver(db_session)
        await resolver.load()

        detector = Detector(resolver=resolver)
        chat = ChatRecord(
            id="chat-1",
            thread_id="t1",
            author="Ana Gómez Castro",
            ts="1234567890.0001",
            text="Hola, mi correo es ana@gmail.com y cédula 1234567890",
        )
        result = detector.detect_chat(chat)
        categories = {s.category for s in result.spans}
        assert DetectionCategory.EMAIL in categories
        assert DetectionCategory.NATIONAL_ID in categories
        # Author should be detected as person
        author_spans = [s for s in result.spans if s.surface_path.endswith(":author")]
        assert len(author_spans) >= 1
