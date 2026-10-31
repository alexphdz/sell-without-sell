"""Tests for shared utilities."""

from kipu_pay.core.utils import clean_digits, is_likely_numeric_id, normalize_text, safe_request_id


def test_normalize_text_basic():
    assert normalize_text("  hello world  ") == "hello world"


def test_normalize_text_none():
    assert normalize_text(None) == ""


def test_normalize_text_nfc():
    # e is composed differently in NFD vs NFC
    text = "cafe\u0301"  # NFD: e + combining acute
    normalized = normalize_text(text)
    assert normalized == "caf\u00e9"  # NFC: precomposed é


def test_clean_digits():
    assert clean_digits("abc123def456") == "123456"


def test_clean_digits_none():
    assert clean_digits(None) == ""


def test_is_likely_numeric_id_true():
    assert is_likely_numeric_id("1234567890") is True


def test_is_likely_numeric_id_too_short():
    assert is_likely_numeric_id("1234") is False


def test_is_likely_numeric_id_non_numeric():
    assert is_likely_numeric_id("mostly-letters") is False


def test_is_likely_numeric_id_mixed():
    assert is_likely_numeric_id("CC-12345678") is True


def test_safe_request_id_valid():
    assert safe_request_id("abc-123") == "abc-123"


def test_safe_request_id_none():
    assert safe_request_id(None) is None


def test_safe_request_id_empty():
    assert safe_request_id("") is None


def test_safe_request_id_trims_and_limits():
    long_id = "x" * 100
    result = safe_request_id(long_id)
    assert len(result) == 64
    assert result == "x" * 64


def test_safe_request_id_strips_control_chars():
    assert safe_request_id("hello\x00world") == "helloworld"


def test_safe_request_id_all_control_chars():
    assert safe_request_id("\x00\x01\x02") is None
