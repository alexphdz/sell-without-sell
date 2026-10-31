"""Tests for identifier normalization (REG-07..REG-10 support)."""

from __future__ import annotations

from kipu_pay.identity.normalizers import (
    normalize_cedula,
    normalize_email,
    normalize_name,
    normalize_phone,
)


class TestCedula:
    def test_dotted_cedula(self) -> None:
        assert normalize_cedula("1.234.567.890") == "1234567890"

    def test_plain_cedula(self) -> None:
        assert normalize_cedula("1234567890") == "1234567890"

    def test_spaced_cedula(self) -> None:
        assert normalize_cedula("71 170 753") == "71170753"

    def test_equivalence(self) -> None:
        assert normalize_cedula("1.234.567.890") == normalize_cedula("1234567890")

    def test_not_numeric(self) -> None:
        assert normalize_cedula("CL-12345") is None

    def test_too_short(self) -> None:
        assert normalize_cedula("12345") is None

    def test_too_long(self) -> None:
        assert normalize_cedula("123456789012") is None

    def test_empty(self) -> None:
        assert normalize_cedula("") is None


class TestEmail:
    def test_domain_lowercased(self) -> None:
        assert normalize_email("a@EXAMPLE.COM") == "a@example.com"

    def test_local_part_preserved(self) -> None:
        # Dots and plus tags must not be removed (conservative).
        assert normalize_email("John.Doe+tag@example.com") == "John.Doe+tag@example.com"

    def test_case_equivalence_domain_only(self) -> None:
        assert normalize_email("x@Foo.Com") == normalize_email("x@foo.com")

    def test_invalid_no_at(self) -> None:
        assert normalize_email("not-an-email") is None

    def test_invalid_double_at(self) -> None:
        assert normalize_email("a@b@c.com") is None

    def test_invalid_no_tld(self) -> None:
        assert normalize_email("a@localhost") is None


class TestPhone:
    def test_plain_mobile(self) -> None:
        assert normalize_phone("3229730911") == "3229730911"

    def test_formatted(self) -> None:
        assert normalize_phone("322 973-0911") == "3229730911"

    def test_country_prefix_preserved(self) -> None:
        assert normalize_phone("+57 322 9730911") == "+573229730911"

    def test_too_short(self) -> None:
        assert normalize_phone("12345") is None

    def test_empty(self) -> None:
        assert normalize_phone("") is None


class TestName:
    def test_accent_insensitive(self) -> None:
        assert normalize_name("Adrián Ospina") == normalize_name("Adrian Ospina")

    def test_case_folding(self) -> None:
        assert normalize_name("DORA MUÑOZ") == normalize_name("dora muñoz")

    def test_whitespace_collapse(self) -> None:
        assert normalize_name("  Dora   Muñoz ") == normalize_name("Dora Muñoz")

    def test_original_untouched(self) -> None:
        original = "Adrián Ospina"
        normalize_name(original)
        assert original == "Adrián Ospina"

    def test_empty(self) -> None:
        assert normalize_name("") == ""
